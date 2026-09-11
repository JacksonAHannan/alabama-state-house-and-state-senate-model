"""Build descriptive 2026 ideology features with explicit missingness.

The export is prospective evidence, not a forecast specification.  It links the
reviewed 2026 roster to prior candidate identities and, where available, to a
legislator's record through the 2026 session.  Missing challenger evidence is
left missing and no ideology value is imputed to zero.
"""
from __future__ import annotations

from pathlib import Path
import re
import unicodedata

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
WAR = ROOT / "data" / "processed" / "war"
ELECTIONS = ROOT / "data" / "processed" / "elections"
OUT = ROOT / "data" / "processed" / "forecast_calibration"

ROSTER = WAR / "2026_final_candidate_roster.csv"
INCUMBENCY = WAR / "2026_candidate_incumbency.csv"
CANDIDATES = ELECTIONS / "canonical_cmo_candidates.csv"
CROSSWALK = IDEOLOGY / "candidate_legislator_identity_crosswalk.csv"
CAREER = IDEOLOGY / "candidate_career_ideology_through_2026.csv"
CYCLE_FEATURES = IDEOLOGY / "candidate_ideology_v3_model_features.csv"

KEYS = ["cycle", "chamber", "district", "party", "candidate"]
FAMILY_FEATURES = [
    "ideology_v3_environment_resources",
    "ideology_v3_institutional_reform",
    "ideology_v3_labor_capital",
    "ideology_v3_market_government_direction",
    "ideology_v3_material_support",
    "ideology_v3_order_justice",
    "ideology_v3_social_liberty_equality",
]
CAREER_FIELDS = [
    "behavioral_ideology", "chamber_percentile", "votes_used",
    "possible_votes", "participation_rate", "distance_from_caucus_median",
]


def normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"\b(JR|SR|II|III|IV)\b", " ", text.upper())
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def normalized_identifier(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def historical_aliases() -> pd.DataFrame:
    crosswalk = pd.read_csv(CROSSWALK, low_memory=False)
    candidates = pd.read_csv(CANDIDATES, low_memory=False)[
        ["canonical_candidate_id", "year", "canonical_party", "canonical_name"]
    ]
    source = crosswalk.merge(
        candidates, on=["canonical_candidate_id", "year", "canonical_party", "canonical_name"],
        how="left", validate="one_to_one",
    )
    rows = []
    for row in source.itertuples(index=False):
        for field in ("canonical_name", "resolved_name", "member_display_name"):
            name = getattr(row, field, None)
            key = normalized_name(name)
            if key:
                rows.append({
                    "normalized_candidate": key,
                    "party": row.canonical_party,
                    "source_candidate_id": row.canonical_candidate_id,
                    "source_candidate_year": row.year,
                    "source_person_id": row.person_id,
                    "people_id": row.people_id,
                    "member_source_id": row.member_source_id,
                    "identity_status": row.identity_status,
                })
    aliases = pd.DataFrame(rows).drop_duplicates()
    return aliases


def safe_name_matches(roster: pd.DataFrame, aliases: pd.DataFrame) -> pd.DataFrame:
    """Return one historical identity only where name and party are unambiguous."""
    candidates = []
    for (name, party), group in aliases.groupby(["normalized_candidate", "party"]):
        identities = group.source_person_id.dropna().astype(str).unique()
        people = group.people_id.dropna().astype(str).unique()
        # Repeated candidate cycles are safe; distinct people with the same name
        # are not.  A resolved legislative people_id is stronger when present.
        if len(people) > 1 or (len(people) == 0 and len(identities) > 1):
            continue
        ordered = group.sort_values(["source_candidate_year", "source_candidate_id"])
        row = ordered.iloc[-1].to_dict()
        row["name_match_cycles"] = int(group.source_candidate_id.nunique())
        candidates.append(row)
    lookup = pd.DataFrame(candidates)
    if lookup.empty:
        return roster.assign(source_candidate_id=np.nan)
    return roster.merge(
        lookup, on=["normalized_candidate", "party"], how="left", validate="many_to_one"
    )


def build_candidate_features() -> pd.DataFrame:
    roster = pd.read_csv(ROSTER, low_memory=False)
    incumbency = pd.read_csv(INCUMBENCY, low_memory=False)[
        KEYS + ["incumbent", "prior_winner_candidate_id", "incumbency_source"]
    ]
    roster = roster.merge(incumbency, on=KEYS, how="left", validate="one_to_one")
    roster["normalized_candidate"] = roster.candidate.map(normalized_name)
    linked = safe_name_matches(roster, historical_aliases())

    crosswalk = pd.read_csv(CROSSWALK, low_memory=False)[
        ["canonical_candidate_id", "person_id", "people_id", "member_source_id",
         "resolved_name", "identity_status"]
    ].rename(columns={
        "canonical_candidate_id": "prior_winner_candidate_id",
        "person_id": "prior_person_id", "people_id": "prior_people_id",
        "member_source_id": "prior_member_source_id",
        "resolved_name": "prior_resolved_name", "identity_status": "prior_identity_status",
    })
    linked = linked.merge(crosswalk, on="prior_winner_candidate_id", how="left", validate="many_to_one")
    incumbent_link = linked.incumbent.fillna(False) & linked.prior_winner_candidate_id.notna()
    for target, source in [
        ("source_candidate_id", "prior_winner_candidate_id"),
        ("source_person_id", "prior_person_id"),
        ("people_id", "prior_people_id"),
        ("member_source_id", "prior_member_source_id"),
        ("identity_status", "prior_identity_status"),
    ]:
        linked.loc[incumbent_link, target] = linked.loc[incumbent_link, source]
    linked["ideology_identity_match_method"] = np.select(
        [incumbent_link, linked.source_candidate_id.notna()],
        ["reviewed_prior_winner_identity", "unique_exact_historical_name_party"],
        default="unmatched",
    )

    career = pd.read_csv(CAREER, low_memory=False)
    career["normalized_roster_name"] = career.member_display_name_roster.map(normalized_name)
    career["people_id"] = career.people_id.map(normalized_identifier).astype("string")
    career_lookup = career[
        ["normalized_roster_name", "party_roster", "chamber", "people_id", "member_source_id"]
    ].dropna(subset=["normalized_roster_name", "people_id"]).copy()
    unique_people = (career_lookup.groupby(
        ["normalized_roster_name", "party_roster", "chamber"]
    ).people_id.nunique().eq(1))
    valid_keys = unique_people[unique_people].index
    career_lookup = career_lookup.set_index(
        ["normalized_roster_name", "party_roster", "chamber"]
    ).loc[valid_keys].reset_index().drop_duplicates(
        ["normalized_roster_name", "party_roster", "chamber"]
    ).rename(columns={
        "normalized_roster_name": "normalized_candidate",
        "party_roster": "party",
        "people_id": "career_name_people_id",
        "member_source_id": "career_name_member_source_id",
    })
    linked = linked.merge(
        career_lookup, on=["normalized_candidate", "party", "chamber"],
        how="left", validate="many_to_one",
    )
    linked["people_id"] = linked.people_id.map(normalized_identifier).astype("string")
    linked["member_source_id"] = linked.member_source_id.astype("string")
    direct_career = linked.people_id.isna() & linked.career_name_people_id.notna()
    linked.loc[direct_career, "people_id"] = linked.loc[direct_career, "career_name_people_id"]
    linked.loc[direct_career, "member_source_id"] = linked.loc[
        direct_career, "career_name_member_source_id"
    ]
    linked.loc[direct_career, "ideology_identity_match_method"] = (
        "unique_exact_current_legislator_name_party_chamber"
    )
    career_issue = [column for column in career if column.startswith("legislative_issue_")
                    and not column.startswith("legislative_issue_votes_")]
    career_columns = ["people_id", "chamber", "member_display_name_roster", "party_roster",
                      "first_session", "last_session", "legislative_sessions",
                      "career_ideology_available", *CAREER_FIELDS, *career_issue]
    career = career[career_columns].copy()
    # Prefer the chamber being contested, then the most recent service record.
    linked["people_id"] = linked.people_id.map(normalized_identifier).astype("string")
    career = career.sort_values(["people_id", "last_session", "legislative_sessions"])
    exact = linked.merge(career, on=["people_id", "chamber"], how="left", validate="many_to_one")
    missing = exact.behavioral_ideology.isna() & exact.people_id.notna()
    fallback = career.drop_duplicates("people_id", keep="last").set_index("people_id")
    for column in [c for c in career_columns if c not in {"people_id", "chamber"}]:
        exact.loc[missing, column] = exact.loc[missing, "people_id"].map(fallback[column])
    exact.loc[missing & exact.member_display_name_roster.notna(), "career_cross_chamber_fallback"] = True
    if "career_cross_chamber_fallback" not in exact:
        exact["career_cross_chamber_fallback"] = False
    else:
        exact["career_cross_chamber_fallback"] = exact[
            "career_cross_chamber_fallback"
        ].eq(True)

    cycle = pd.read_csv(CYCLE_FEATURES, low_memory=False).rename(
        columns={"canonical_candidate_id": "source_candidate_id"}
    )
    exact = exact.merge(cycle, on="source_candidate_id", how="left", validate="many_to_one")
    observed_fields = ["behavioral_ideology", *career_issue, *FAMILY_FEATURES]
    exact["ideology_features_observed"] = exact[observed_fields].notna().sum(axis=1)
    exact["ideology_available"] = exact.ideology_features_observed.gt(0)
    exact["legislative_ideology_available"] = exact[
        ["behavioral_ideology", *career_issue]
    ].notna().any(axis=1)
    exact["cycle_valid_candidate_ideology_available"] = exact[FAMILY_FEATURES].notna().any(axis=1)
    exact["forecast_ideology_status"] = np.where(
        exact.ideology_available,
        "descriptive_only_not_headline_selection_biased",
        "missing_explicit_not_zero",
    )
    keep = KEYS + [
        "incumbent", "incumbency_source", "source_candidate_id", "source_candidate_year",
        "source_person_id", "people_id", "member_source_id", "identity_status",
        "ideology_identity_match_method", "name_match_cycles", "career_cross_chamber_fallback",
        "first_session", "last_session", "legislative_sessions", *CAREER_FIELDS,
        *career_issue, *FAMILY_FEATURES, "ideology_features_observed", "ideology_available",
        "legislative_ideology_available", "cycle_valid_candidate_ideology_available",
        "forecast_ideology_status",
    ]
    result = exact[[column for column in keep if column in exact]].copy()
    if len(result) != len(roster) or result.duplicated(KEYS).any():
        raise ValueError("2026 candidate ideology feature key is not complete and unique")
    return result.sort_values(["chamber", "district", "party", "candidate"]).reset_index(drop=True)


def build_race_features(candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    numeric = ["behavioral_ideology", *FAMILY_FEATURES]
    for (chamber, district), group in candidates.groupby(["chamber", "district"]):
        parties = {party: part.iloc[0] for party, part in group.groupby("party") if len(part) == 1}
        row = {"chamber": chamber, "district": district}
        for party, prefix in [("D", "dem"), ("R", "rep")]:
            member = parties.get(party)
            row[f"{prefix}_candidate"] = member.candidate if member is not None else np.nan
            row[f"{prefix}_ideology_available"] = bool(member.ideology_available) if member is not None else False
            row[f"{prefix}_ideology_features_observed"] = (
                int(member.ideology_features_observed) if member is not None else 0
            )
            for column in numeric:
                row[f"{prefix}_{column}"] = member[column] if member is not None else np.nan
        row["both_candidates_ideology_available"] = (
            row["dem_ideology_available"] and row["rep_ideology_available"]
        )
        for column in numeric:
            dem, rep = row[f"dem_{column}"], row[f"rep_{column}"]
            row[f"ideology_gap_d_minus_r_{column}"] = (
                dem - rep if pd.notna(dem) and pd.notna(rep) else np.nan
            )
        row["forecast_use_status"] = (
            "descriptive_only_not_headline_selection_biased"
            if row["dem_ideology_available"] or row["rep_ideology_available"]
            else "missing_both_explicit_not_zero"
        )
        rows.append(row)
    result = pd.DataFrame(rows).sort_values(["chamber", "district"]).reset_index(drop=True)
    if result.duplicated(["chamber", "district"]).any():
        raise ValueError("2026 race ideology features are not unique")
    return result


def coverage(candidate: pd.DataFrame, race: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in candidate.groupby(["chamber", "party", "incumbent"], dropna=False):
        rows.append({
            "level": "candidate", "chamber": keys[0], "party": keys[1],
            "incumbent": keys[2], "records": len(group),
            "ideology_available": int(group.ideology_available.sum()),
            "coverage_rate": float(group.ideology_available.mean()),
            "both_candidates_ideology_available": np.nan,
        })
    rows.append({
        "level": "candidate_total", "chamber": "all", "party": "all", "incumbent": np.nan,
        "records": len(candidate), "ideology_available": int(candidate.ideology_available.sum()),
        "coverage_rate": float(candidate.ideology_available.mean()),
        "both_candidates_ideology_available": np.nan,
    })
    contested = race[race.dem_candidate.notna() & race.rep_candidate.notna()]
    rows.append({
        "level": "contested_race", "chamber": "all", "party": "both", "incumbent": np.nan,
        "records": len(contested), "ideology_available": int(
            (contested.dem_ideology_available | contested.rep_ideology_available).sum()
        ),
        "coverage_rate": float(
            (contested.dem_ideology_available | contested.rep_ideology_available).mean()
        ),
        "both_candidates_ideology_available": int(contested.both_candidates_ideology_available.sum()),
    })
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidate = build_candidate_features()
    race = build_race_features(candidate)
    audit = coverage(candidate, race)
    candidate.to_csv(OUT / "2026_candidate_ideology_features.csv", index=False)
    race.to_csv(OUT / "2026_race_ideology_features.csv", index=False)
    audit.to_csv(OUT / "2026_ideology_feature_coverage.csv", index=False)
    print(audit.to_string(index=False))


if __name__ == "__main__":
    main()
