"""Fuse ontology-v3 candidate evidence into issue-specific, source-audited valence.

This stage does not manufacture positions from party or broad ideological group
scores. Questionnaire responses are combined with only explicitly mapped,
issue-specific ratings and endorsements. Legislative evidence joins here after
its policy direction has been adjudicated under ontology v3.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from ideology_ontology_v3 import ONTOLOGY_VERSION, family_loading, primitive_axis_direction, validate_primitive

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
MANUAL = ROOT / "data" / "manual" / "ideology"
LEGISLATIVE_EVIDENCE = IDEOLOGY / "candidate_legislative_position_evidence_v3.csv"
TARGETED_RESEARCH = MANUAL / "candidate_issue_research_findings.csv"
BALLOTPEDIA_ADJUDICATIONS = MANUAL / "ballotpedia_candidate_position_adjudications.csv"
BALLOTPEDIA_SCORECARDS = IDEOLOGY / "ballotpedia_candidate_scorecard_ratings.csv"

WEIGHTS = {"candidate_questionnaire": 1.0, "legislative_rollcall": 1.0,
           "interest_group_rating": 0.65, "interest_group_endorsement": 0.45,
           "candidate_public_statement": 0.9, "candidate_biography": 0.55}

# Evidence remains in the archival all-sources table even when it cannot be
# used to estimate what a candidate stood for at the modeled election.  This
# explicit allow-list prevents a later position from being silently backcast.
TEMPORALLY_ELIGIBLE = {
    "pre_or_same_cycle_legislative_action", "same_cycle_candidate_statement",
    "pre_or_same_cycle_group_signal", "pre_or_during_election",
    "historical_pre_election", "historical_pre_election_record",
    "career_record_before_election", "prior_public_record",
    "recent_pre_election",
}
MIN_ISSUE_EVIDENCE_WEIGHT = 0.65
MIN_FAMILY_EVIDENCE_WEIGHT = 1.50
MIN_FAMILY_DISTINCT_ISSUES = 2


def mark_temporal_model_eligibility(evidence: pd.DataFrame) -> pd.DataFrame:
    evidence = evidence.copy()
    evidence["temporal_model_eligible"] = evidence.temporal_status.fillna("").isin(
        TEMPORALLY_ELIGIBLE)
    return evidence


def canonicalize_evidence_identities(evidence: pd.DataFrame) -> pd.DataFrame:
    """Resolve legacy/import IDs to the canonical candidate-cycle roster.

    Source artifacts may retain an older candidate ID scheme. Match first on
    the stable election/chamber/district/party tuple embedded in the ID, then
    on unique person+cycle or name+cycle fallbacks. The current election
    warehouse roster is authoritative.
    """
    roster = pd.read_csv(
        ROOT / "data" / "processed" / "elections" /
        "canonical_cmo_candidates.csv", dtype=str).fillna("")
    roster["cycle_num"] = pd.to_numeric(roster.year, errors="coerce")
    roster["name_key"] = roster.canonical_name.str.lower().str.replace(
        r"[^a-z0-9]+", "", regex=True)
    person = roster[roster.person_id.ne("")].drop_duplicates(
        ["person_id", "cycle_num"], keep=False).set_index(["person_id", "cycle_num"])
    names = roster[roster.name_key.ne("")].drop_duplicates(
        ["name_key", "cycle_num"], keep=False).set_index(["name_key", "cycle_num"])
    result = evidence.copy()
    result["source_canonical_candidate_id"] = result.canonical_candidate_id.fillna("")
    for index, row in result.iterrows():
        cycle = pd.to_numeric(row.election_cycle, errors="coerce")
        match = None
        parsed = re.match(
            r"^AL-(\d{4})-(house|senate)-(\d+)-([DR])-",
            str(row.canonical_candidate_id))
        if parsed:
            candidates = roster[
                roster.cycle_num.eq(float(parsed.group(1)))
                & roster.chamber.eq(parsed.group(2))
                & pd.to_numeric(roster.district, errors="coerce").eq(float(parsed.group(3)))
                & roster.canonical_party.eq(parsed.group(4))]
            if len(candidates) == 1:
                match = candidates.iloc[0]
        person_key = (str(row.person_id or ""), cycle)
        if match is None and person_key in person.index:
            match = person.loc[person_key]
        elif match is None:
            name_key = re.sub(r"[^a-z0-9]+", "", str(row.candidate_name or "").lower())
            if (name_key, cycle) in names.index:
                match = names.loc[(name_key, cycle)]
        if match is not None:
            result.at[index, "canonical_candidate_id"] = match["canonical_candidate_id"]
            result.at[index, "person_id"] = match.get("person_id", person_key[0])
            result.at[index, "candidate_name"] = match["canonical_name"]
    return result


def rating_value(value: object) -> float | None:
    text = str(value or "").strip().upper()
    pct = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if pct:
        return float(np.clip((float(pct.group(1)) - 50) / 50, -1, 1))
    number = re.fullmatch(r"-?\d+(?:\.\d+)?", text)
    if number:
        n = float(text)
        return float(np.clip((n - 50) / 50, -1, 1)) if 0 <= n <= 100 else None
    grades = {"A+": 1, "A": .9, "A-": .8, "B+": .7, "B": .6, "B-": .5,
              "C+": .3, "C": 0, "C-": -.2, "D+": -.4, "D": -.6,
              "D-": -.75, "F": -1}
    return grades.get(text)


def evidence_id(parts: list[object]) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:20].upper()


def targeted_research_evidence() -> pd.DataFrame:
    paths = [path for path in (TARGETED_RESEARCH, BALLOTPEDIA_ADJUDICATIONS) if path.exists()]
    if not paths:
        return pd.DataFrame()
    findings = pd.concat([pd.read_csv(path).fillna("") for path in paths], ignore_index=True)
    findings = findings[findings.adjudication_status.eq("adjudicated")].copy()
    records = []
    source_types = {"candidate_public_statement": "public_statement",
                    "legislative_sponsorship": "bill_sponsorship"}
    weights = {"public_statement": .9, "bill_sponsorship": .85}
    for row in findings.itertuples(index=False):
        validate_primitive(row.primitive_axis, row.policy_pole)
        family, direction = family_loading(row.primitive_axis, row.policy_pole)
        source_type = source_types.get(row.source_type, row.source_type)
        value = float(row.position_value)
        records.append({
            "ontology_version": ONTOLOGY_VERSION,
            "evidence_id": evidence_id(["targeted_research", row.canonical_candidate_id,
                                        row.source_url, row.primitive_axis, row.evidence_date]),
            "canonical_candidate_id": row.canonical_candidate_id, "person_id": row.person_id,
            "candidate_name": row.candidate_name, "election_cycle": int(row.election_cycle),
            "evidence_date": row.evidence_date, "temporal_status": row.temporal_status,
            "source_type": source_type, "source_provider": row.source_provider,
            "source_record_id": row.source_url, "source_url": row.source_url,
            "item_id": evidence_id([row.source_url, row.primitive_axis]),
            "policy_family": "targeted_candidate_research", "policy_key": row.primitive_axis,
            "primitive_axis": row.primitive_axis, "policy_pole": row.policy_pole,
            "candidate_stance": row.candidate_stance, "position_value": value,
            "response_mode": "explicit_statement" if source_type == "public_statement" else "sponsorship",
            "family": family or "", "family_direction": direction if direction is not None else np.nan,
            "family_contribution": value * direction if direction is not None else np.nan,
            "constituency_tags_json": "[]", "confidence": row.confidence,
            "adjudication_authority": "manual_targeted_research_adjudication",
            "evidence_weight": weights.get(source_type, .75), "source_text": row.source_text,
            "raw_answer": row.source_text,
        })
    return pd.DataFrame(records)


def mapped_group_evidence() -> pd.DataFrame:
    mapping = pd.read_csv(MANUAL / "interest_group_ontology_v3.csv").fillna("")
    for row in mapping.itertuples():
        validate_primitive(row.primitive_axis, row.policy_pole)
    crosswalk = pd.read_csv(IDEOLOGY / "votesmart_candidate_crosswalk_resolved.csv", dtype=str).fillna("")
    crosswalk = crosswalk[crosswalk.accepted.str.lower().eq("true")].copy()
    crosswalk["votesmart_candidate_id"] = crosswalk.votesmart_candidate_id.str.replace(r"\.0$", "", regex=True)
    crosswalk["election_year"] = pd.to_numeric(crosswalk.election_year)

    ratings = pd.read_csv(IDEOLOGY / "votesmart_all_1998_2022_ratings.csv", dtype=str).fillna("")
    ratings["votesmart_candidate_id"] = ratings.votesmart_candidate_id.str.replace(r"\.0$", "", regex=True)
    ratings["rating_year_start"] = pd.to_numeric(ratings.rating_year_start, errors="coerce")
    ratings["rating_year_end"] = pd.to_numeric(ratings.rating_year_end, errors="coerce")
    ratings["position_value"] = ratings.rating.map(rating_value)
    ratings = ratings[ratings.position_value.notna()].merge(mapping, on="organization", how="inner")
    rating_cycles = ratings.merge(crosswalk, on="votesmart_candidate_id", how="inner", suffixes=("", "_candidate"))
    rating_cycles = rating_cycles[
        rating_cycles.rating_year_start.le(rating_cycles.election_year) &
        rating_cycles.rating_year_end.ge(rating_cycles.election_year - 4)
    ].copy()
    # Prevent repeated scorecards from dominating: retain the most recent one
    # for each organization, primitive, and candidate-cycle.
    rating_cycles = rating_cycles.sort_values("rating_year_end").drop_duplicates(
        ["canonical_candidate_id", "organization", "primitive_axis", "policy_pole"], keep="last")

    endorsements = pd.read_csv(IDEOLOGY / "votesmart_all_1998_2022_endorsements.csv", dtype=str).fillna("")
    endorsements["votesmart_candidate_id"] = endorsements.votesmart_candidate_id.str.replace(r"\.0$", "", regex=True)
    endorsements["endorsement_year"] = pd.to_numeric(endorsements.endorsement_year, errors="coerce")
    endorsement_cycles = endorsements.merge(mapping, on="organization", how="inner").merge(
        crosswalk, on="votesmart_candidate_id", how="inner", suffixes=("", "_candidate"))
    endorsement_cycles = endorsement_cycles[endorsement_cycles.endorsement_year.eq(endorsement_cycles.election_year)].copy()
    endorsement_cycles["position_value"] = 1.0

    records = []
    for source_type, frame in (("interest_group_rating", rating_cycles), ("interest_group_endorsement", endorsement_cycles)):
        for row in frame.itertuples():
            family, direction = family_loading(row.primitive_axis, row.policy_pole)
            date = str(int(row.rating_year_end)) if source_type == "interest_group_rating" else str(int(row.endorsement_year))
            source_record = row.scorecard_id if source_type == "interest_group_rating" else row.interest_group_id
            raw = row.rating if source_type == "interest_group_rating" else "endorsed"
            records.append({
                "ontology_version": ONTOLOGY_VERSION,
                "evidence_id": evidence_id([source_type, row.canonical_candidate_id, row.organization, source_record, row.primitive_axis]),
                "canonical_candidate_id": row.canonical_candidate_id, "person_id": row.person_id,
                "candidate_name": row.canonical_candidate, "election_cycle": int(row.election_year),
                "evidence_date": date, "temporal_status": "pre_or_same_cycle_group_signal",
                "source_type": source_type, "source_provider": row.organization,
                "source_record_id": source_record, "source_url": row.source_url,
                "item_id": evidence_id([row.organization, row.policy_key]), "policy_family": row.policy_family,
                "policy_key": row.policy_key, "primitive_axis": row.primitive_axis, "policy_pole": row.policy_pole,
                "candidate_stance": "alignment", "position_value": float(row.position_value),
                "response_mode": "continuous_alignment" if source_type == "interest_group_rating" else "endorsement",
                "family": family or "", "family_direction": direction if direction is not None else np.nan,
                "family_contribution": float(row.position_value) * direction if direction is not None else np.nan,
                "constituency_tags_json": row.constituency_tags_json, "confidence": row.mapping_confidence,
                "adjudication_authority": "explicit_interest_group_ontology_v3",
                "evidence_weight": WEIGHTS[source_type],
                "source_text": row.mapping_note, "raw_answer": raw,
            })
    return pd.DataFrame(records)


def ballotpedia_scorecard_evidence() -> pd.DataFrame:
    """Admit issue-mapped external scorecards not already represented by Vote Smart.

    NFIB's recovered 2018 ratings duplicate Vote Smart and ACU is deliberately
    broad. The recovered Club for Growth economic scorecards add a specific
    market-autonomy signal; only the latest pre-election score is retained.
    """
    if not BALLOTPEDIA_SCORECARDS.exists():
        return pd.DataFrame()
    ratings = pd.read_csv(BALLOTPEDIA_SCORECARDS, dtype=str).fillna("")
    ratings = ratings[(ratings.organization.eq("The Club for Growth"))
                      & ratings.canonical_candidate_id.ne("")].copy()
    ratings["rating_year"] = pd.to_numeric(ratings.rating_year, errors="coerce")
    ratings["election_cycle"] = pd.to_numeric(ratings.election_cycle, errors="coerce")
    ratings["rating_num"] = pd.to_numeric(ratings.rating, errors="coerce")
    ratings = ratings[ratings.rating_year.le(ratings.election_cycle) & ratings.rating_num.notna()]
    ratings = ratings.sort_values("rating_year").drop_duplicates(
        ["canonical_candidate_id", "organization", "election_cycle"], keep="last")
    mapping = pd.read_csv(MANUAL / "interest_group_ontology_v3.csv").fillna("")
    mapping = mapping[mapping.organization.eq("The Club for Growth")]
    ratings = ratings.merge(mapping, on="organization", how="inner", validate="many_to_one")
    records = []
    for row in ratings.itertuples(index=False):
        validate_primitive(row.primitive_axis, row.policy_pole)
        family, direction = family_loading(row.primitive_axis, row.policy_pole)
        value = float(np.clip((row.rating_num - 50) / 50, -1, 1))
        records.append({
            "ontology_version":ONTOLOGY_VERSION,
            "evidence_id":evidence_id(["ballotpedia_scorecard", row.canonical_candidate_id,
                                        row.organization, row.rating_year, row.source_sha256]),
            "canonical_candidate_id":row.canonical_candidate_id,"person_id":row.person_id,
            "candidate_name":row.canonical_name,"election_cycle":int(row.election_cycle),
            "evidence_date":str(int(row.rating_year)),"temporal_status":"pre_or_same_cycle_group_signal",
            "source_type":"interest_group_rating","source_provider":row.organization,
            "source_record_id":row.source_sha256,"source_url":row.source_url,
            "item_id":evidence_id([row.organization,row.rating_year,row.primitive_axis]),
            "policy_family":row.policy_family,"policy_key":row.policy_key,
            "primitive_axis":row.primitive_axis,"policy_pole":row.policy_pole,
            "candidate_stance":"alignment","position_value":value,
            "response_mode":"continuous_alignment","family":family or "",
            "family_direction":direction if direction is not None else np.nan,
            "family_contribution":value * direction if direction is not None else np.nan,
            "constituency_tags_json":row.constituency_tags_json,"confidence":row.mapping_confidence,
            "adjudication_authority":"external_scorecard_explicit_ontology_mapping",
            "evidence_weight":WEIGHTS["interest_group_rating"],
            "source_text":f"{row.organization} {int(row.rating_year)} economic growth score: {row.rating_num:g}%",
            "raw_answer":f"{row.rating_num:g}%",
        })
    return pd.DataFrame(records)


def aggregate(evidence: pd.DataFrame) -> pd.DataFrame:
    usable = evidence[evidence.canonical_candidate_id.notna() & evidence.position_value.notna()
                      & evidence.temporal_model_eligible].copy()
    usable["axis_direction"] = [primitive_axis_direction(a, p) for a, p in zip(usable.primitive_axis, usable.policy_pole)]
    usable = usable[usable.axis_direction.notna()].copy()
    usable["axis_contribution"] = usable.position_value * usable.axis_direction
    usable["weighted"] = usable.axis_contribution * usable.evidence_weight
    rows = []
    keys = ["canonical_candidate_id", "election_cycle", "primitive_axis"]
    for key, group in usable.groupby(keys, dropna=False):
        weight = group.evidence_weight.sum()
        value = group.weighted.sum() / weight if weight else np.nan
        positive = group.loc[group.axis_contribution.gt(0), "evidence_weight"].sum()
        negative = group.loc[group.axis_contribution.lt(0), "evidence_weight"].sum()
        conflict = min(positive, negative) / max(positive, negative) if max(positive, negative) else 0
        rows.append(dict(zip(keys, key)) | {
            "person_id": group.person_id.iloc[0],
            "candidate_name": group.candidate_name.iloc[0],
            "issue_valence": value, "absolute_evidence_weight": weight,
            "evidence_records": len(group), "source_types": "|".join(sorted(group.source_type.unique())),
            "source_type_count": group.source_type.nunique(), "conflict_ratio": conflict,
            "position_status": "conflicted" if conflict >= .5 else ("supported" if value > .15 else "opposed" if value < -.15 else "mixed_or_unclear"),
        })
    result = pd.DataFrame(rows)
    if not result.empty:
        result["issue_score_available"] = (
            result.absolute_evidence_weight.ge(MIN_ISSUE_EVIDENCE_WEIGHT)
            & result.conflict_ratio.lt(.5)
            & result.issue_valence.abs().gt(.15)
        )
        result["model_issue_valence"] = result.issue_valence.where(result.issue_score_available)
    return result


def aggregate_families(evidence: pd.DataFrame) -> pd.DataFrame:
    usable = evidence[evidence.canonical_candidate_id.notna() & evidence.family_contribution.notna()
                      & evidence.temporal_model_eligible].copy()
    usable["weighted"] = usable.family_contribution * usable.evidence_weight
    keys = ["canonical_candidate_id", "election_cycle", "family"]
    summary = (usable.groupby(keys, dropna=False)
               .agg(weighted_sum=("weighted", "sum"), evidence_weight=("evidence_weight", "sum"),
                    evidence_records=("evidence_id", "nunique"), distinct_issues=("primitive_axis", "nunique"),
                    source_type_count=("source_type", "nunique"))
               .reset_index())
    identity = usable.drop_duplicates("canonical_candidate_id").set_index(
        "canonical_candidate_id")[["person_id", "candidate_name"]]
    summary = summary.join(identity, on="canonical_candidate_id")
    summary["family_valence"] = summary.weighted_sum / summary.evidence_weight
    # A broad dimension needs either two concrete issues or two source types;
    # otherwise retain the issue result but do not call it a family estimate.
    summary["family_score_available"] = (
        summary.distinct_issues.ge(MIN_FAMILY_DISTINCT_ISSUES)
        & summary.evidence_weight.ge(MIN_FAMILY_EVIDENCE_WEIGHT)
    )
    summary["model_family_valence"] = summary.family_valence.where(summary.family_score_available)
    return summary.drop(columns="weighted_sum")


def main() -> None:
    questionnaire = pd.read_csv(IDEOLOGY / "candidate_position_evidence_v3_votesmart.csv", low_memory=False)
    questionnaire["evidence_weight"] = WEIGHTS["candidate_questionnaire"]
    layers = [questionnaire, mapped_group_evidence()]
    ballotpedia_ratings = ballotpedia_scorecard_evidence()
    if not ballotpedia_ratings.empty:
        layers.append(ballotpedia_ratings)
    targeted = targeted_research_evidence()
    if not targeted.empty:
        layers.append(targeted)
    if LEGISLATIVE_EVIDENCE.exists():
        layers.append(pd.read_csv(LEGISLATIVE_EVIDENCE, low_memory=False))
    combined = pd.concat(layers, ignore_index=True, sort=False)
    combined = combined.drop_duplicates("evidence_id", keep="last")
    combined = canonicalize_evidence_identities(combined)
    combined = mark_temporal_model_eligibility(combined)
    canonical = set(pd.read_csv(
        ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv",
        usecols=["canonical_candidate_id"]).canonical_candidate_id)
    unmatched = combined[~combined.canonical_candidate_id.isin(canonical)].copy()
    unmatched.to_csv(IDEOLOGY / "candidate_position_evidence_v3_unmatched.csv", index=False)
    combined = combined[combined.canonical_candidate_id.isin(canonical)].copy()
    combined.to_csv(IDEOLOGY / "candidate_position_evidence_v3_all_sources.csv", index=False)
    positions = aggregate(combined)
    positions.to_csv(IDEOLOGY / "candidate_issue_valence_v3.csv", index=False)
    families = aggregate_families(combined)
    families.to_csv(IDEOLOGY / "candidate_family_valence_v3_all_sources.csv", index=False)
    model = (families.pivot_table(index="canonical_candidate_id", columns="family", values="model_family_valence", aggfunc="first")
             .add_prefix("ideology_v3_").reset_index())
    model.to_csv(IDEOLOGY / "candidate_ideology_v3_model_features.csv", index=False)
    coverage = (positions.groupby("election_cycle", as_index=False)
                .agg(candidates_with_positions=("canonical_candidate_id", "nunique"),
                     candidate_issue_profiles=("primitive_axis", "size"),
                     distinct_issues=("primitive_axis", "nunique")))
    coverage.to_csv(IDEOLOGY / "candidate_issue_valence_v3_coverage.csv", index=False)
    print(f"Wrote {len(combined):,} evidence records, {len(positions):,} candidate-issue profiles, and {len(families):,} family profiles")
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
