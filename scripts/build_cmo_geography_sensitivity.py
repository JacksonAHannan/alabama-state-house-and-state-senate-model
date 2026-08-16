"""Refit headline OOF CMO under every audited precinct-geography scenario."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, cross_val_predict

from fit_preliminary_war_model import RANDOM_STATE, estimator, prepare


ROOT = Path(__file__).resolve().parents[1]
ELECTIONS = ROOT / "data" / "processed" / "elections"
RESEARCH = ROOT / "research" / "cmo_ideology"


def main() -> None:
    source = pd.read_csv(ELECTIONS / "canonical_cmo_features.csv")
    definitions = pd.read_csv(ELECTIONS / "canonical_district_baseline_definitions.csv")
    definitions = definitions[definitions.baseline_definition.eq("core_equal")].copy()
    core = [
        "dem_incumbent_i", "rep_incumbent_i", "prior_pres_dem_margin",
        "nonwhite_share", "white_college_share", "prior_pres_swing",
        "pres_trend_available",
    ]
    features = core + ["cycle", "chamber"]
    rows = []
    for scenario, baseline in definitions.groupby("scenario"):
        scenario_source = source.drop(columns=["core_index_margin", "statewide_index_margin"]).merge(
            baseline[["cycle", "chamber", "district", "baseline_margin"]],
            on=["cycle", "chamber", "district"], how="left", validate="one_to_one",
        )
        scenario_source["core_index_margin"] = scenario_source.baseline_margin
        scenario_source["statewide_index_margin"] = scenario_source.baseline_margin
        scenario_source["raw_overperformance"] = (
            scenario_source.legislative_dem_margin - scenario_source.baseline_margin
        )
        data = prepare(scenario_source)
        prediction = cross_val_predict(
            estimator(core, ["cycle", "chamber"]), data[features], data.raw_overperformance,
            cv=KFold(10, shuffle=True, random_state=RANDOM_STATE),
        )
        part = data[["cycle", "chamber", "district", "raw_overperformance"]].copy()
        part["scenario"] = scenario
        part["expected_cmo_total_oof"] = prediction
        part["cmo_total_oof"] = data.raw_overperformance.to_numpy() - prediction
        rows.append(part)
    races = pd.concat(rows, ignore_index=True)

    candidates = pd.read_csv(ELECTIONS / "canonical_cmo_candidates.csv")
    candidates = candidates.rename(columns={
        "year": "cycle", "canonical_name": "candidate", "canonical_party": "party",
    })
    scored = candidates.merge(
        races, on=["cycle", "chamber", "district"], how="inner", validate="many_to_many"
    )
    scored["candidate_cmo_total_oof"] = scored.cmo_total_oof * scored.party.map({"D": 1, "R": -1})
    scored.to_csv(RESEARCH / "cmo_geography_scenario_scores.csv", index=False)

    democrats = scored[scored.party.eq("D")].copy()
    keys = ["canonical_candidate_id", "person_id", "candidate", "cycle", "chamber", "district"]
    summary = (democrats.groupby(keys, as_index=False)
               .agg(cmo_geography_low=("candidate_cmo_total_oof", "min"),
                    cmo_geography_high=("candidate_cmo_total_oof", "max"),
                    cmo_geography_mean=("candidate_cmo_total_oof", "mean"),
                    geography_scenarios=("scenario", "nunique")))
    summary["cmo_geography_range"] = summary.cmo_geography_high - summary.cmo_geography_low
    production = democrats[democrats.scenario.eq("production_canonical_weights")][
        keys + ["candidate_cmo_total_oof"]
    ].rename(columns={"candidate_cmo_total_oof": "production_cmo_oof"})
    summary = summary.merge(production, on=keys, how="left", validate="one_to_one")
    published = pd.read_csv(ROOT / "data" / "processed" / "war" / "preliminary_cmo_candidates.csv")
    published = published[published.party.eq("D")][
        ["canonical_candidate_id", "candidate_cmo_total_oof"]
    ].rename(columns={"candidate_cmo_total_oof": "published_cmo_oof"})
    summary = summary.merge(published, on="canonical_candidate_id", how="left", validate="one_to_one")
    summary["production_minus_published"] = summary.production_cmo_oof - summary.published_cmo_oof
    if summary.production_minus_published.abs().max() > 1e-8:
        raise AssertionError("production geography scenario does not reproduce published OOF CMO")
    summary.sort_values("cmo_geography_range", ascending=False).to_csv(
        RESEARCH / "cmo_geography_sensitivity.csv", index=False
    )
    print(
        f"Wrote {len(scored)} scenario candidate rows and {len(summary)} Democratic summaries; "
        f"max production mismatch {summary.production_minus_published.abs().max():.3g}"
    )


if __name__ == "__main__":
    main()
