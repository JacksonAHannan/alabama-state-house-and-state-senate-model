#!/usr/bin/env python3
"""Build an evidence-backed candidate-to-LegiScan identity crosswalk.

This repairs source ballot codes, district formatting, initials, suffixes, and
nicknames without changing canonical election facts. Ambiguous matches remain
in a review table and are never promoted automatically.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
LEGISLATIVE = ROOT / "data" / "processed" / "legislative"
ELECTION_DB = ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite"
OVERRIDES = ROOT / "data" / "manual" / "ideology" / "candidate_legislator_identity_overrides.csv"


def normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    text = re.sub(r'"[^\"]*"|\([^)]*\)|\b(?:JR|SR|II|III|IV)\b', " ", text.upper())
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def compact_name(value: object) -> str:
    return normalized_name(value).replace(" ", "")


def name_signature(value: object) -> str:
    tokens = normalized_name(value).split()
    if not tokens:
        return ""
    return f"{tokens[0][0]}|{tokens[-1]}"


def numeric_district(value: object) -> float:
    hit = re.search(r"(\d+)", str(value or ""))
    return float(int(hit.group(1))) if hit else np.nan


def chamber_from_role(value: object) -> str:
    return {"REP": "house", "SEN": "senate"}.get(str(value).upper(), "")


def load_candidates() -> pd.DataFrame:
    with sqlite3.connect(ELECTION_DB) as con:
        candidates = pd.read_sql("""SELECT canonical_candidate_id,person_id,year,chamber,
          district AS district_candidate,party AS canonical_party,ballot_name AS canonical_name,
          incumbent,winner FROM fact_candidate_election""", con)
    candidates["incumbent"] = candidates.incumbent.fillna(0).astype(int)
    candidates["winner"] = candidates.winner.fillna(0).astype(int)
    candidates = candidates.sort_values(
        ["person_id", "year", "chamber", "district_candidate"]
    ).copy()
    prior_win = (candidates.year.where(candidates.winner.eq(1))
                 .groupby(candidates.person_id).transform(lambda x: x.shift().cummax()))
    candidates["prior_winner_i"] = prior_win.lt(candidates.year).fillna(False)
    candidates["expected_prior_officeholder"] = (
        candidates.incumbent.eq(1) | candidates.prior_winner_i
    )
    candidates["resolved_name"] = candidates.canonical_name
    candidates["name_source"] = "canonical_election_ballot"

    aliases = pd.read_csv(ROOT / "data/manual/ideology/candidate_research_aliases.csv")
    aliases = aliases[aliases.identity_status.eq("verified_identity")].drop_duplicates("canonical_candidate_id")
    alias_map = aliases.set_index("canonical_candidate_id").research_name
    use = candidates.canonical_candidate_id.isin(alias_map.index)
    candidates.loc[use, "resolved_name"] = candidates.loc[use, "canonical_candidate_id"].map(alias_map)
    candidates.loc[use, "name_source"] = "manual_verified_candidate_alias"

    bp = pd.read_csv(IDEOLOGY / "ballotpedia_candidate_crosswalk.csv", low_memory=False)
    bp = bp[bp.accepted.eq(True) & bp.review_required.eq(False)].drop_duplicates("canonical_candidate_id")
    bp_map = bp.set_index("canonical_candidate_id").matched_name
    is_code = candidates.canonical_name.str.match(r"^GSL\d{3}[DR].+", na=False)
    use = is_code & candidates.canonical_candidate_id.isin(bp_map.index)
    candidates.loc[use, "resolved_name"] = candidates.loc[use, "canonical_candidate_id"].map(bp_map)
    candidates.loc[use, "name_source"] = "verified_ballotpedia_election_crosswalk"
    return candidates


def load_members() -> pd.DataFrame:
    members = pd.read_csv(LEGISLATIVE / "legiscan_alabama_legislators.csv", low_memory=False)
    district_chamber = members.district.astype(str).str.extract(r"^(HD|SD)", expand=False).map(
        {"HD": "house", "SD": "senate"})
    # Role is authoritative. A few transition-year roster rows retain the
    # member's future district prefix even though that session's role is still
    # in the other chamber (Cam Ward and Billy Beasley in 2010).
    members["chamber"] = members.role.map(chamber_from_role).replace("", np.nan).fillna(
        district_chamber
    )
    members["district_number"] = members.district.map(numeric_district)
    members["name_exact"] = members.name.map(normalized_name)
    members["name_compact"] = members.name.map(compact_name)
    members["name_signature"] = members.name.map(name_signature)
    return members[members.chamber.ne("")]


def choose_match(candidate: pd.Series, members: pd.DataFrame) -> tuple[pd.Series | None, str, str]:
    # Person identity persists through chamber changes.  Chamber is evidence,
    # not an identity boundary; exact names can therefore link a House member
    # running for Senate (or vice versa).
    pool = members
    if pool.empty:
        return None, "unmatched", "no same-chamber-party legislative members"
    people = (pool.sort_values("session_year").groupby("people_id", as_index=False)
              .agg(member_display_name=("name", "last"), first_session=("session_year", "min"),
                   last_session=("session_year", "max"), sessions=("session_year", "nunique"),
                   name_exact=("name_exact", "last"), name_compact=("name_compact", "last"),
                   name_signature=("name_signature", "last"),
                   surname=("name_exact", lambda x: str(x.iloc[-1]).split()[-1]),
                   parties=("party", lambda x: tuple(sorted(set(x.dropna())))),
                   districts=("district_number", lambda x: tuple(sorted(set(x.dropna()))))))
    def method(name: str, match: pd.Series) -> str:
        return name if candidate.canonical_party in match.parties else name + "_party_transition"
    district = float(candidate.district_candidate)
    same_chamber = pool[pool.chamber.eq(candidate.chamber)]
    same_chamber_district_ids = set(
        same_chamber[same_chamber.district_number.eq(district)].people_id
    )
    active_ids = set(same_chamber[
        same_chamber.session_year.eq(int(candidate.year))
        & same_chamber.district_number.eq(district)
    ].people_id)
    local = people[people.people_id.isin(same_chamber_district_ids)]
    exact_local = local[local.name_exact.eq(normalized_name(candidate.resolved_name))]
    if len(exact_local) == 1:
        return exact_local.iloc[0], method("exact_name_same_chamber_district", exact_local.iloc[0]), ""
    compact_local = local[local.name_compact.eq(compact_name(candidate.resolved_name))]
    if len(compact_local) == 1:
        return compact_local.iloc[0], method("compact_name_same_chamber_district", compact_local.iloc[0]), ""
    signature_local = local[local.name_signature.eq(name_signature(candidate.resolved_name))]
    if len(signature_local) == 1:
        return signature_local.iloc[0], method("first_initial_surname_same_chamber_district", signature_local.iloc[0]), ""
    code_hit = re.match(r"^GSL\d{3}[DR]([A-Z]+)$", str(candidate.canonical_name or ""))
    if code_hit:
        surname_prefix = code_hit.group(1)
        coded = local[
            local.name_exact.str.split().str[-1].str.startswith(surname_prefix, na=False)
        ]
        if len(coded) == 1:
            return coded.iloc[0], method("ballot_code_surname_prefix_same_chamber_district", coded.iloc[0]), ""
    # Only after chamber/district-supported options have been exhausted may a
    # globally unique exact name establish a cross-chamber person identity.
    exact = people[people.name_exact.eq(normalized_name(candidate.resolved_name))]
    if len(exact) == 1:
        return exact.iloc[0], method("unique_exact_name_person", exact.iloc[0]), ""
    compact = people[people.name_compact.eq(compact_name(candidate.resolved_name))]
    if len(compact) == 1:
        return compact.iloc[0], method("unique_compact_name_person", compact.iloc[0]), ""
    signature = people[people.name_signature.eq(name_signature(candidate.resolved_name))]
    # Incumbents can be resolved by a unique district-party member who served
    # no later than the election. This fallback was previously broken because
    # strings such as HD-086 were passed directly to numeric conversion.
    served_ids = set(same_chamber[
        same_chamber.session_year.eq(int(candidate.year))
    ].people_id)
    served = people[people.people_id.isin(served_ids)]
    district_hit = served[served.people_id.isin(active_ids)]
    candidate_tokens = normalized_name(candidate.resolved_name).split()
    candidate_surname = candidate_tokens[-1]
    candidate_first = candidate_tokens[0]
    name_supported = district_hit.apply(
        lambda row: (
            row.surname == candidate_surname
            or (row.name_exact.split()[0] == candidate_first
                and candidate_surname in row.name_exact.split())
        ),
        axis=1,
    )
    named_district_hit = district_hit[
        district_hit["parties"].map(lambda values: candidate.canonical_party in values)
        & name_supported
    ]
    if bool(candidate.expected_prior_officeholder) and len(named_district_hit) == 1:
        return (named_district_hit.iloc[0],
                method("officeholder_same_chamber_district_party_surname", named_district_hit.iloc[0]), "")
    # Some 2022 SOS observations preserve a GSL ballot code instead of a
    # person's name.  A unique prior member in the same chamber, district,
    # and party is sufficient documentary evidence to decode an incumbent
    # code; do not extend this rule to ordinary named candidates.
    code_district = district_hit[
        district_hit["parties"].map(lambda values: candidate.canonical_party in values)
    ]
    if re.match(r"^GSL\d{3}[DR].+", str(candidate.canonical_name or "")) and len(code_district) == 1:
        return code_district.iloc[0], method("ballot_code_unique_prior_district", code_district.iloc[0]), ""
    reason = ("multiple plausible members" if len(signature) > 1 else
              "no verified candidate-to-member identity")
    return None, "ambiguous" if len(signature) > 1 else "unmatched", reason


def load_overrides(members: pd.DataFrame) -> pd.DataFrame:
    overrides = pd.read_csv(OVERRIDES, low_memory=False)
    if overrides.canonical_candidate_id.duplicated().any():
        raise ValueError("candidate legislator overrides must be unique by candidate")
    if not overrides.identity_status.eq("verified_identity").all():
        raise ValueError("every candidate legislator override must be verified")
    if overrides.source_url.fillna("").eq("").any():
        raise ValueError("every candidate legislator override requires a source URL")
    missing = set(overrides.people_id.astype(int)) - set(members.people_id.astype(int))
    if missing:
        raise ValueError(f"override people IDs absent from LegiScan roster: {sorted(missing)}")
    return overrides


def main() -> None:
    candidates, members = load_candidates(), load_members()
    overrides = load_overrides(members).set_index("canonical_candidate_id")
    person_summary = (members.sort_values("session_year").groupby("people_id", as_index=False)
                      .agg(member_display_name=("name", "last"),
                           first_session=("session_year", "min"),
                           last_session=("session_year", "max"),
                           sessions=("session_year", "nunique")))
    rows, review = [], []
    for candidate in candidates.itertuples(index=False):
        c = pd.Series(candidate._asdict())
        if c.canonical_candidate_id in overrides.index:
            override = overrides.loc[c.canonical_candidate_id]
            match = person_summary.loc[
                person_summary.people_id.eq(int(override.people_id))
            ].iloc[0]
            method, reason = "manual_verified_legislator_identity", ""
        else:
            match, method, reason = choose_match(c, members)
        row = c.to_dict()
        if match is None:
            row.update({"people_id": np.nan, "member_source_id": np.nan,
                        "member_display_name": np.nan, "first_session": np.nan,
                        "last_session": np.nan, "legislative_sessions": 0,
                        "identity_status": method, "identity_match_method": method})
            review.append({**row, "review_reason": reason})
        else:
            if re.match(r"^GSL\d{3}[DR].+", str(row.get("resolved_name") or "")):
                row["resolved_name"] = match.member_display_name
                row["name_source"] = "legislative_prior_service_district_party"
            row.update({"people_id": int(match.people_id),
                        "member_source_id": f"LEGISCAN-{int(match.people_id)}",
                        "member_display_name": match.member_display_name,
                        "first_session": int(match.first_session), "last_session": int(match.last_session),
                        "legislative_sessions": int(match.sessions), "identity_status": "resolved",
                        "identity_match_method": method})
        rows.append(row)
    result = pd.DataFrame(rows).sort_values(["year", "chamber", "district_candidate", "canonical_party"])
    # A member may map to multiple candidates across elections, but never twice
    # within one election/chamber. Quarantine any such collision.
    assigned = result.member_source_id.notna()
    collisions = result[assigned & result.duplicated(["year", "chamber", "member_source_id"], keep=False)]
    if len(collisions):
        for idx in collisions.index:
            result.loc[idx, ["people_id", "member_source_id", "member_display_name"]] = np.nan
            result.loc[idx, "identity_status"] = "ambiguous"
            result.loc[idx, "identity_match_method"] = "duplicate_cycle_member_quarantined"
        review.extend([{**r._asdict(), "review_reason": "duplicate member assignment within cycle"}
                       for r in collisions.itertuples(index=False)])
    keep = ["canonical_candidate_id", "person_id", "year", "chamber", "district_candidate",
            "canonical_party", "canonical_name", "resolved_name", "name_source", "people_id",
            "member_source_id", "member_display_name", "first_session", "last_session",
            "legislative_sessions", "identity_status", "identity_match_method",
            "prior_winner_i", "expected_prior_officeholder"]
    result[keep].to_csv(IDEOLOGY / "candidate_legislator_identity_crosswalk.csv", index=False)
    pd.DataFrame(review).to_csv(IDEOLOGY / "candidate_legislator_identity_review.csv", index=False)
    print(f"Resolved {result.identity_status.eq('resolved').sum()} of {len(result)} candidate rows; "
          f"2022={result[result.year.eq(2022)].identity_status.eq('resolved').sum()}/"
          f"{result.year.eq(2022).sum()}; review={len(review)}")


if __name__ == "__main__":
    main()
