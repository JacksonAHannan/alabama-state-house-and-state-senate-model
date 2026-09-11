#!/usr/bin/env python3
"""Audit Alabama roll-call and candidate ideology coverage end to end.

This script is read-only with respect to source and canonical data.  It emits
diagnostic CSVs that distinguish unavailable source records, unresolved person
identity, insufficient contested votes, and missing issue classification.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LEGISLATIVE = ROOT / "data" / "processed" / "legislative"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
ELECTION_DB = ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite"
ROLLCALL_DB = LEGISLATIVE / "alabama_legislative_rollcalls_1998_2026.sqlite"
PREFIX = IDEOLOGY / "legislative_ideology_coverage_audit"
WINDOWS = {
    1998: (1998, 1998), 2002: (1999, 2002), 2006: (2003, 2006),
    2010: (2007, 2010), 2014: (2011, 2014), 2018: (2015, 2018),
    2022: (2019, 2022),
}


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    text = re.sub(r'"[^"]*"|\([^)]*\)|\b(?:JR|SR|II|III|IV)\b', " ", text.upper())
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def surname(value: object) -> str:
    tokens = norm(value).split()
    return tokens[-1] if tokens else ""


def district_number(value: object) -> float:
    hit = re.search(r"(\d+)", str(value or ""))
    return float(int(hit.group(1))) if hit else np.nan


def member_roster() -> pd.DataFrame:
    rows = pd.read_csv(LEGISLATIVE / "legiscan_alabama_legislators.csv", low_memory=False)
    prefix = rows.district.astype(str).str.extract(r"^(HD|SD)", expand=False)
    # Role is the authoritative chamber field.  LegiScan sometimes stores a
    # member's future district label during the last session before a
    # House-to-Senate move (for example William Beasley and Cam Ward in 2010).
    # Letting the district prefix override role creates a false same-chamber
    # match and can attach House votes as Senate service.
    rows["chamber"] = rows.role.astype(str).str.upper().map(
        {"REP": "house", "SEN": "senate"}
    ).fillna(prefix.map({"HD": "house", "SD": "senate"}))
    rows["district_number"] = rows.district.map(district_number)
    rows["name_norm"] = rows.name.map(norm)
    rows["surname"] = rows.name.map(surname)
    rows = rows[rows.chamber.isin(["house", "senate"])].copy()
    return (rows.sort_values(["people_id", "chamber", "session_year"])
            .groupby(["people_id", "chamber"], as_index=False)
            .agg(member_display_name=("name", "last"),
                 name_norm=("name_norm", "last"), surname=("surname", "last"),
                 first_session=("session_year", "min"), last_session=("session_year", "max"),
                 sessions=("session_year", "nunique"),
                 parties=("party", lambda x: "|".join(sorted(set(x.dropna().astype(str))))),
                 districts=("district_number", lambda x: "|".join(
                     str(int(v)) for v in sorted(set(x.dropna()))))))


def candidate_facts() -> pd.DataFrame:
    with sqlite3.connect(ELECTION_DB) as connection:
        rows = pd.read_sql("""SELECT canonical_candidate_id,person_id,year,chamber,
          district AS district_candidate,party AS canonical_party,ballot_name AS canonical_name,
          incumbent,winner FROM fact_candidate_election""", connection)
    rows["incumbent"] = rows.incumbent.fillna(0).astype(int)
    rows["winner"] = rows.winner.fillna(0).astype(int)
    rows = rows.sort_values(["person_id", "year", "chamber", "district_candidate"])
    prior_winner_year = (rows.year.where(rows.winner.eq(1))
                         .groupby(rows.person_id).transform(lambda x: x.shift().cummax()))
    rows["prior_winner_i"] = prior_winner_year.lt(rows.year).fillna(False)
    rows["expected_prior_officeholder"] = rows.incumbent.eq(1) | rows.prior_winner_i
    return rows


def source_session_audit() -> pd.DataFrame:
    observed = pd.read_csv(LEGISLATIVE / "unified_legislative_rollcall_coverage.csv")
    expected = pd.MultiIndex.from_product(
        [range(1998, 2027), ["house", "senate"]], names=["session_year", "chamber"]
    ).to_frame(index=False)
    result = expected.merge(observed, on=["session_year", "chamber"], how="left")
    result["source_expected"] = True
    result["source_present"] = result.rollcalls.notna()
    for column in ["rollcalls", "member_votes", "identified_member_votes"]:
        result[column] = result[column].fillna(0).astype(int)
    result["identified_vote_share"] = np.where(
        result.member_votes.gt(0), result.identified_member_votes / result.member_votes, np.nan
    )
    median = result.groupby("chamber").rollcalls.transform(
        lambda x: x.where(x.gt(0)).median()
    )
    result["low_rollcall_volume"] = result.rollcalls.gt(0) & result.rollcalls.lt(median * 0.25)
    result["coverage_flag"] = np.select(
        [~result.source_present, result.identified_vote_share.lt(0.95), result.low_rollcall_volume],
        ["missing_session_chamber", "member_identity_below_95pct", "unusually_low_rollcall_volume"],
        default="covered",
    )
    return result


def rollcall_classification_audit() -> tuple[pd.DataFrame, pd.DataFrame]:
    classifications = pd.read_csv(
        LEGISLATIVE / "comprehensive_rollcall_classifications.csv", low_memory=False
    )
    ontology = pd.read_csv(LEGISLATIVE / "frontier_rollcall_ontology_v3.csv", low_memory=False)
    mapped = set(ontology.loc[ontology.decision.eq("map"), "canonical_rollcall_id"].astype(str))
    classifications["canonical_rollcall_id"] = classifications.canonical_rollcall_id.astype(str)
    classifications["mapped_issue_rollcall"] = classifications.canonical_rollcall_id.isin(mapped)
    classifications["status_family"] = np.select(
        [classifications.mapped_issue_rollcall,
         classifications.classification_status.astype(str).str.contains("procedural", case=False, na=False),
         classifications.classification_status.astype(str).str.contains("insufficient", case=False, na=False)],
        ["mapped", "procedural_or_motion", "insufficient_text"], default="other_excluded"
    )
    with sqlite3.connect(ROLLCALL_DB) as connection:
        warehouse = pd.read_sql(
            """SELECT canonical_rollcall_id,session_year,chamber,source_system,
                      bill_type,motion_type
               FROM rollcall""", connection
        )
    warehouse["canonical_rollcall_id"] = warehouse.canonical_rollcall_id.astype(str)
    disposition = classifications[["canonical_rollcall_id", "status_family"]].drop_duplicates(
        "canonical_rollcall_id"
    )
    classifications = warehouse.merge(
        disposition, on="canonical_rollcall_id", how="left", validate="one_to_one"
    )
    classifications["status_family"] = classifications.status_family.fillna(
        "not_in_classification_table"
    )
    detail = (classifications.groupby(
        ["session_year", "chamber", "status_family"], dropna=False, as_index=False
    ).agg(rollcalls=("canonical_rollcall_id", "nunique")))
    funnel = (classifications.groupby("status_family", as_index=False)
              .agg(rollcalls=("canonical_rollcall_id", "nunique")))
    return detail, funnel


def member_window_counts(mapped_ids: set[str]) -> pd.DataFrame:
    with sqlite3.connect(ROLLCALL_DB) as connection:
        votes = pd.read_sql("""SELECT v.member_source_id,v.chamber,v.session_year,
          v.canonical_rollcall_id,v.vote,r.bill_type,r.yea_total,r.nay_total
          FROM member_vote v JOIN rollcall r USING(canonical_rollcall_id)
          WHERE v.vote IN ('Yea','Nay')""", connection)
    votes["canonical_rollcall_id"] = votes.canonical_rollcall_id.astype(str)
    recorded = votes.yea_total.fillna(0) + votes.nay_total.fillna(0)
    minority = votes[["yea_total", "nay_total"]].min(axis=1)
    votes["scoring_eligible"] = (
        votes.bill_type.isin(["HB", "SB"]) & minority.ge(2)
        & minority.div(recorded.replace(0, np.nan)).ge(0.025)
    )
    votes["mapped_issue_vote"] = votes.canonical_rollcall_id.isin(mapped_ids)
    parts = []
    for cycle, (start, end) in WINDOWS.items():
        window = votes[votes.session_year.between(start, end)]
        grouped = (window.groupby(["member_source_id", "chamber"], as_index=False)
                   .agg(raw_yea_nay_votes=("canonical_rollcall_id", "size"),
                        raw_rollcalls=("canonical_rollcall_id", "nunique"),
                        scoring_eligible_votes=("scoring_eligible", "sum"),
                        scoring_eligible_rollcalls=(
                            "canonical_rollcall_id",
                            lambda x: x[window.loc[x.index, "scoring_eligible"]].nunique()),
                        mapped_issue_votes=("mapped_issue_vote", "sum"),
                        mapped_issue_rollcalls=(
                            "canonical_rollcall_id",
                            lambda x: x[window.loc[x.index, "mapped_issue_vote"]].nunique())))
        grouped["year"] = cycle
        parts.append(grouped)
    return pd.concat(parts, ignore_index=True)


def identity_recovery_queue(candidates: pd.DataFrame, crosswalk: pd.DataFrame,
                            roster: pd.DataFrame) -> pd.DataFrame:
    unresolved = candidates.merge(
        crosswalk[["canonical_candidate_id", "resolved_name", "identity_status"]],
        on="canonical_candidate_id", how="left", validate="one_to_one"
    )
    unresolved = unresolved[~unresolved.identity_status.eq("resolved")].copy()
    rows = []
    for candidate in unresolved.itertuples(index=False):
        candidate_name = candidate.resolved_name if pd.notna(candidate.resolved_name) else candidate.canonical_name
        candidate_norm, candidate_surname = norm(candidate_name), surname(candidate_name)
        district = int(candidate.district_candidate)
        active = roster.loc[
            roster["chamber"].eq(candidate.chamber)
            & roster["first_session"].le(int(candidate.year))
            & roster["last_session"].ge(int(candidate.year))
        ].copy()
        exact = roster.loc[roster["name_norm"].eq(candidate_norm)]
        if len(exact["people_id"].unique()) == 1:
            exact_candidate_chamber = exact.loc[exact["chamber"].eq(candidate.chamber)]
            proposed = (exact_candidate_chamber.iloc[-1]
                        if len(exact_candidate_chamber) else exact.iloc[-1])
            method, confidence = "unique_exact_name_any_service", "high"
        else:
            district_mask = (active["districts"].fillna("").str.split("|").map(
                lambda values: str(district) in values
            ))
            same_district = active.loc[district_mask]
            party_mask = (same_district["parties"].fillna("").str.split("|").map(
                lambda values: candidate.canonical_party in values
            ))
            same_party = same_district.loc[party_mask]
            surname_hit = same_party.loc[same_party["surname"].eq(candidate_surname)]
            if len(surname_hit["people_id"].unique()) == 1:
                proposed = surname_hit.iloc[0]
                method, confidence = "same_chamber_active_district_party_surname", "high"
            else:
                proposed = None
                method = ("officeholder_name_support_required"
                          if candidate.expected_prior_officeholder and len(same_party)
                          else "no_unique_deterministic_recovery")
                confidence = "none"
        rows.append({
            "canonical_candidate_id": candidate.canonical_candidate_id,
            "year": int(candidate.year), "chamber": candidate.chamber,
            "district": district, "party": candidate.canonical_party,
            "candidate_name": candidate_name,
            "canonical_incumbent": int(candidate.incumbent),
            "inferred_prior_winner": bool(candidate.prior_winner_i),
            "expected_prior_officeholder": bool(candidate.expected_prior_officeholder),
            "proposed_people_id": np.nan if proposed is None else int(proposed.people_id),
            "proposed_member_name": np.nan if proposed is None else proposed.member_display_name,
            "proposed_member_chamber": np.nan if proposed is None else proposed.chamber,
            "recovery_method": method, "recovery_confidence": confidence,
        })
    return pd.DataFrame(rows)


def candidate_coverage_audit() -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = candidate_facts()
    crosswalk = pd.read_csv(IDEOLOGY / "candidate_legislator_identity_crosswalk.csv", low_memory=False)
    universe = pd.read_csv(IDEOLOGY / "candidate_ideology_full_universe.csv", low_memory=False)
    evidence = pd.read_csv(
        IDEOLOGY / "candidate_legislative_position_evidence_v3.csv", low_memory=False
    )
    evidence_counts = (evidence.groupby("canonical_candidate_id", as_index=False)
                       .agg(legislative_evidence_rows=("evidence_id", "size"),
                            legislative_issue_axes=("primitive_axis", "nunique")))
    ontology = pd.read_csv(LEGISLATIVE / "frontier_rollcall_ontology_v3.csv", low_memory=False)
    mapped_ids = set(ontology.loc[ontology.decision.eq("map"), "canonical_rollcall_id"].astype(str))
    counts = member_window_counts(mapped_ids)

    audit = (candidates.merge(
        crosswalk[["canonical_candidate_id", "resolved_name", "identity_status",
                   "identity_match_method", "member_source_id", "member_display_name",
                   "first_session", "last_session", "legislative_sessions"]],
        on="canonical_candidate_id", how="left", validate="one_to_one")
        .merge(universe[["canonical_candidate_id", "legislative_ideology_available",
                         "coverage_status", "member_source_id", "identity_member_source_id",
                         "votes_used", "possible_votes"]].rename(
                             columns={"member_source_id": "score_member_source_id"}),
               on="canonical_candidate_id", how="left", validate="one_to_one")
        .merge(evidence_counts, on="canonical_candidate_id", how="left", validate="one_to_one"))
    audit["effective_window_member_id"] = audit.score_member_source_id.fillna(
        audit.identity_member_source_id
    ).fillna(audit.member_source_id)
    audit = audit.merge(
        counts, left_on=["year", "chamber", "effective_window_member_id"],
        right_on=["year", "chamber", "member_source_id"], how="left",
        validate="many_to_one", suffixes=("", "_window")
    )
    for column in ["raw_yea_nay_votes", "raw_rollcalls", "scoring_eligible_votes",
                   "scoring_eligible_rollcalls", "mapped_issue_votes",
                   "mapped_issue_rollcalls", "legislative_evidence_rows",
                   "legislative_issue_axes"]:
        audit[column] = audit[column].fillna(0).astype(int)
    audit["legislative_ideology_available"] = audit.legislative_ideology_available.fillna(False)
    audit["legiscan_identity_resolved"] = audit.identity_status.eq("resolved")
    # Journal-era voting identities use AL-prefixed member IDs and are matched
    # inside a cycle window rather than through the LegiScan person crosswalk.
    # Count them as verified pre-election identities when a unique score-side
    # member ID survived duplicate-assignment quarantine.
    audit["pre_election_identity_resolved"] = (
        audit.legiscan_identity_resolved | audit.score_member_source_id.notna()
    )
    audit["gap_reason"] = np.select(
        [audit.year.eq(1994),
         audit.legislative_ideology_available & audit.legislative_evidence_rows.gt(0),
         audit.legislative_ideology_available & audit.legislative_evidence_rows.eq(0),
         ~audit.pre_election_identity_resolved & audit.expected_prior_officeholder,
         ~audit.pre_election_identity_resolved,
         audit.raw_yea_nay_votes.eq(0),
         audit.scoring_eligible_rollcalls.lt(20),
         audit.mapped_issue_rollcalls.eq(0),
         audit.legislative_ideology_available.eq(False)],
        ["archive_unavailable_1994", "score_and_issue_evidence_available",
         "behavioral_score_but_no_issue_evidence", "expected_officeholder_identity_unresolved",
         "no_verified_pre_election_legislative_identity", "identity_resolved_no_window_votes",
         "insufficient_contested_rollcalls", "no_mapped_issue_rollcalls",
         "sufficient_votes_but_score_missing"], default="covered_or_nonstandard"
    )
    recovery = identity_recovery_queue(candidates, crosswalk, member_roster())
    return audit, recovery


def build_funnel(session: pd.DataFrame, classification_funnel: pd.DataFrame,
                 candidates: pd.DataFrame, recovery: pd.DataFrame) -> pd.DataFrame:
    rows = [
        ("expected_session_chambers_1998_2026", len(session)),
        ("present_session_chambers", int(session.source_present.sum())),
        ("normalized_rollcalls", int(session.rollcalls.sum())),
        ("normalized_member_votes", int(session.member_votes.sum())),
        ("identified_member_votes", int(session.identified_member_votes.sum())),
    ]
    rows.extend((f"rollcalls_{r.status_family}", int(r.rollcalls))
                for r in classification_funnel.itertuples(index=False))
    rows.extend([
        ("candidate_cycles", len(candidates)),
        ("candidate_legiscan_identity_resolved", int(candidates.legiscan_identity_resolved.sum())),
        ("candidate_pre_election_identity_resolved", int(
            candidates.pre_election_identity_resolved.sum())),
        ("candidate_behavioral_score_available", int(candidates.legislative_ideology_available.sum())),
        ("candidate_issue_evidence_available", int(candidates.legislative_evidence_rows.gt(0).sum())),
        ("expected_officeholder_identity_unresolved", int(
            candidates.gap_reason.eq("expected_officeholder_identity_unresolved").sum())),
        ("high_confidence_identity_recoveries", int(recovery.recovery_confidence.eq("high").sum())),
    ])
    return pd.DataFrame(rows, columns=["metric", "count"])


def main() -> None:
    IDEOLOGY.mkdir(parents=True, exist_ok=True)
    session = source_session_audit()
    classification_detail, classification_funnel = rollcall_classification_audit()
    candidates, recovery = candidate_coverage_audit()
    funnel = build_funnel(session, classification_funnel, candidates, recovery)

    session.to_csv(f"{PREFIX}_session_chamber.csv", index=False)
    classification_detail.to_csv(f"{PREFIX}_classification.csv", index=False)
    candidates.to_csv(f"{PREFIX}_candidates.csv", index=False)
    recovery.to_csv(f"{PREFIX}_identity_recovery_queue.csv", index=False)
    funnel.to_csv(f"{PREFIX}_funnel.csv", index=False)

    print(funnel.to_string(index=False))
    print("\nSession flags:", session.coverage_flag.value_counts().to_dict())
    print("Candidate gaps:", candidates.gap_reason.value_counts().to_dict())
    print("Recovery confidence:", recovery.recovery_confidence.value_counts().to_dict())


if __name__ == "__main__":
    main()
