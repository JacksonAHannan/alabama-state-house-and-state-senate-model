"""Integrate contemporaneous Vote Smart ideology with canonical CMO outputs.

Ideology is kept out of the baseline that defines CMO. It is joined afterward
as a candidate characteristic for explaining overperformance, avoiding a
tautology in which the outcome definition already controls for the treatment.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
ELECTIONS = ROOT / "data" / "processed" / "elections"
PCT = IDEOLOGY / "votesmart_pct_candidate_cycle_features.csv"
CANDIDATES = ELECTIONS / "canonical_cmo_candidates.csv"
RACES = ELECTIONS / "canonical_cmo_features.csv"
CANDIDATE_OUT = IDEOLOGY / "votesmart_pct_cmo_candidate_features.csv"
RACE_OUT = IDEOLOGY / "votesmart_pct_cmo_race_features.csv"
AUGMENTED_CANDIDATES = ELECTIONS / "canonical_cmo_candidates_with_votesmart.csv"
AUGMENTED_RACES = ELECTIONS / "canonical_cmo_features_with_votesmart.csv"

DIMENSIONS = [
    "abortion_position", "criminal_justice_position", "economic_ideology",
    "education_position", "environment_position", "government_reform_position",
    "guns_position", "healthcare_position", "labor_position", "social_ideology",
    "immigration_position",
]
MIN_COMPOSITE_DIMENSIONS = 3


def main() -> None:
    pct = pd.read_csv(PCT)
    candidates = pd.read_csv(CANDIDATES)
    races = pd.read_csv(RACES)
    race_identity = ["election_year", "chamber", "district", "party"]
    if pct.duplicated(race_identity).any():
        raise ValueError("PCT candidate-cycle features are not unique by election/chamber/district/party")

    keep = [*race_identity, "votesmart_candidate_id", "match_method",
            "pct_dimensions_scored", "pct_policies_scored", "pct_response_items_scored", *DIMENSIONS]
    pct_join = pct[keep].rename(columns={"election_year": "year", "party": "canonical_party"})
    candidate = candidates.merge(
        pct_join, on=["year", "chamber", "district", "canonical_party"],
        how="left", validate="one_to_one")
    candidate["pct_available"] = candidate.pct_dimensions_scored.notna()
    candidate["pct_composite_ideology"] = candidate[DIMENSIONS].mean(axis=1, skipna=True)
    candidate.loc[candidate.pct_dimensions_scored.fillna(0).lt(MIN_COMPOSITE_DIMENSIONS),
                  "pct_composite_ideology"] = np.nan

    race_keys = ["year", "chamber", "district"]
    party_rows = []
    for party, prefix in (("D", "dem"), ("R", "rep")):
        frame = candidate[candidate.canonical_party.eq(party)][
            race_keys + ["pct_available", "pct_composite_ideology", "pct_dimensions_scored", *DIMENSIONS]
        ].copy()
        frame = frame.rename(columns={
            "year": "cycle", "pct_available": f"{prefix}_pct_available",
            "pct_composite_ideology": f"{prefix}_pct_composite_ideology",
            "pct_dimensions_scored": f"{prefix}_pct_dimensions_scored",
            **{dimension: f"{prefix}_{dimension}" for dimension in DIMENSIONS},
        })
        party_rows.append(frame)
    race = party_rows[0].merge(party_rows[1], on=["cycle", "chamber", "district"],
                               how="outer", validate="one_to_one")
    race["both_pct_available"] = race.dem_pct_available.eq(True) & race.rep_pct_available.eq(True)
    race["pct_composite_contrast_d_minus_r"] = (
        race.dem_pct_composite_ideology - race.rep_pct_composite_ideology
    )
    for dimension in DIMENSIONS:
        race[f"pct_{dimension}_contrast_d_minus_r"] = (
            race[f"dem_{dimension}"] - race[f"rep_{dimension}"]
        )

    augmented_races = races.merge(race, on=["cycle", "chamber", "district"], how="left",
                                  validate="one_to_one")
    outcome = races[["cycle", "chamber", "district", "raw_overperformance",
                     "legislative_dem_margin", "core_index_margin", "war_eligible"]]
    candidate = candidate.merge(outcome, left_on=["year", "chamber", "district"],
                                right_on=["cycle", "chamber", "district"], how="left",
                                validate="many_to_one")
    candidate["candidate_margin_overperformance"] = candidate.raw_overperformance * np.where(
        candidate.canonical_party.eq("D"), 1.0, -1.0
    )

    candidate.to_csv(CANDIDATE_OUT, index=False)
    race.to_csv(RACE_OUT, index=False)
    candidate.to_csv(AUGMENTED_CANDIDATES, index=False)
    augmented_races.to_csv(AUGMENTED_RACES, index=False)
    print(f"Candidate rows: {len(candidate):,}; PCT available: {candidate.pct_available.sum():,}; "
          f"composite eligible: {candidate.pct_composite_ideology.notna().sum():,}")
    print(f"Race rows: {len(augmented_races):,}; both-party PCT: "
          f"{augmented_races.both_pct_available.fillna(False).sum():,}; composite contrasts: "
          f"{augmented_races.pct_composite_contrast_d_minus_r.notna().sum():,}")


if __name__ == "__main__":
    main()
