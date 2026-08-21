"""Score prospective RDH demographic scenarios without contaminating validation.

Historical model fitting remains cycle-matched.  RDH features are available
only for 2024/2026 and are therefore used solely as prospective sensitivity
inputs, never as if they had existed in an earlier holdout.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_forecast_experiment_tournament import (SPECS, cycle_balanced_weights,
                                                 pipeline, prepare_data,
                                                 prepare_prospective_data)

DEM = ROOT / "data" / "processed" / "demographics"
WAR = ROOT / "data" / "processed" / "war"

MODELS = {
    "post2016_ramp": ("post2016_ramp", 0.0),
    "ensemble_ramp_ridge_80_20": ("ramp_all_theory_ridge", 0.2),
    "ramp_demographic_response": ("ramp_demographic_response", 1.0),
    "ramp_all_spline_ridge": ("ramp_all_spline_ridge", 1.0),
    "ramp_all_extra_trees": ("ramp_all_extra_trees", 1.0),
}


def scenarios(test: pd.DataFrame) -> dict[str, pd.DataFrame]:
    cvap = pd.read_csv(DEM / "rdh_2024_sld_cvap.csv")
    vap = pd.read_csv(DEM / "rdh_2026_projected_vap_sld_experimental.csv")
    edu = pd.read_csv(DEM / "rdh_2024_sld_education_experimental.csv")
    comparison = pd.read_csv(ROOT / "data" / "processed" / "elections" / "validation" /
                             "rdh_2024_current_demographic_comparison.csv")
    l2 = pd.read_csv(DEM / "rdh_2024_l2_sld_turnout_experimental.csv")
    extra = (cvap[["chamber", "district", "cvap_nonwhite_share"]]
             .merge(vap[["chamber", "district", "projected_vap_nonwhite_share"]],
                    on=["chamber", "district"])
             .merge(edu[["chamber", "district", "college_share_2024"]],
                    on=["chamber", "district"])
             .merge(comparison[["chamber", "district", "college_2024_minus_2022"]],
                    on=["chamber", "district"])
             .merge(l2[["chamber", "district", "reg_eur", "reg_hisp", "reg_aa", "reg_esa", "reg_oth",
                        "voted_eur", "voted_hisp", "voted_aa", "voted_esa", "voted_oth"]],
                    on=["chamber", "district"]))
    known_registered = extra[["reg_eur", "reg_hisp", "reg_aa", "reg_esa", "reg_oth"]].sum(axis=1)
    known_voted = extra[["voted_eur", "voted_hisp", "voted_aa", "voted_esa", "voted_oth"]].sum(axis=1)
    extra["l2_registered_nonwhite_share"] = 1 - extra.reg_eur / known_registered.replace(0, np.nan)
    extra["l2_voter_nonwhite_share"] = 1 - extra.voted_eur / known_voted.replace(0, np.nan)
    base = test.merge(extra, on=["chamber", "district"], how="left", validate="one_to_one")
    definitions = {
        "current_2022_total_population": ("nonwhite_share", False),
        "rdh_2024_cvap": ("cvap_nonwhite_share", False),
        "rdh_2024_cvap_education_delta": ("cvap_nonwhite_share", True),
        "rdh_projected_2026_vap": ("projected_vap_nonwhite_share", False),
        "rdh_projected_vap_education_delta": ("projected_vap_nonwhite_share", True),
        "rdh_l2_2024_registered": ("l2_registered_nonwhite_share", False),
        "rdh_l2_2024_voters": ("l2_voter_nonwhite_share", False),
    }
    result = {}
    for name, (source, update_education) in definitions.items():
        frame = base.copy()
        if source != "nonwhite_share":
            frame["nonwhite_share"] = frame[source]
        if update_education:
            frame["white_college_share"] = (frame.white_college_share + frame.college_2024_minus_2022).clip(0, 1)
        frame["ramp_x_nonwhite"] = frame.ramp_swing * frame.nonwhite_share
        frame["ramp_x_white_college"] = frame.ramp_swing * frame.white_college_share
        result[name] = frame
    return result


def main() -> None:
    train = prepare_data().dropna(subset=["ramp_baseline", "legislative_dem_margin"]).copy()
    test = prepare_prospective_data()
    variants = scenarios(test)
    rows = []
    for model_name, (spec_name, scale) in MODELS.items():
        spec = SPECS[spec_name]
        fitted = None
        if spec["model"] != "none":
            fitted = pipeline(spec["model"], spec["features"])
            target = train.legislative_dem_margin - train.ramp_baseline
            fit_args = {} if spec["model"] == "bayesian_ridge" else {
                "model__sample_weight": cycle_balanced_weights(train)}
            fitted.fit(train[spec["features"] + ["chamber"]], target, **fit_args)
        for scenario, frame in variants.items():
            adjustment = np.zeros(len(frame))
            if fitted is not None:
                adjustment = scale * fitted.predict(frame[spec["features"] + ["chamber"]])
            prediction = frame.ramp_baseline.to_numpy() + adjustment
            for race, margin, adj in zip(frame.itertuples(), prediction, adjustment):
                rows.append({"model": model_name, "scenario": scenario, "chamber": race.chamber,
                             "district": race.district, "ramp_margin": race.ramp_baseline,
                             "model_adjustment": adj, "predicted_dem_margin": margin,
                             "nonwhite_feature": race.nonwhite_share})
    detail = pd.DataFrame(rows)
    current = (detail[detail.scenario.eq("current_2022_total_population")]
               [["model", "chamber", "district", "predicted_dem_margin"]]
               .rename(columns={"predicted_dem_margin": "current_margin"}))
    detail = detail.merge(current, on=["model", "chamber", "district"], validate="many_to_one")
    detail["margin_change"] = detail.predicted_dem_margin - detail.current_margin
    detail["winner_changed"] = ((detail.predicted_dem_margin >= 0) != (detail.current_margin >= 0))
    summary = (detail.groupby(["model", "scenario"], as_index=False)
               .agg(races=("district", "size"), mean_margin_change=("margin_change", "mean"),
                    mean_absolute_change=("margin_change", lambda z: z.abs().mean()),
                    max_absolute_change=("margin_change", lambda z: z.abs().max()),
                    winner_changes=("winner_changed", "sum")))
    detail.to_csv(WAR / "rdh_demographic_forecast_scenario_predictions.csv", index=False)
    summary.to_csv(WAR / "rdh_demographic_forecast_scenario_summary.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
