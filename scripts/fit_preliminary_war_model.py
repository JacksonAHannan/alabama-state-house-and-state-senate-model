"""Fit a cross-validated preliminary Alabama legislative WAR model."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, GroupKFold, KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"


def main() -> None:
    model = pd.read_csv(WAR / "war_model_features.csv")
    eligible = model[model.war_eligible].copy().reset_index(drop=True)
    eligible["incumbency_advantage_d"] = (
        eligible.dem_incumbent.astype(int) - eligible.rep_incumbent.astype(int))
    eligible["dem_incumbent_i"] = eligible.dem_incumbent.astype(int)
    eligible["rep_incumbent_i"] = eligible.rep_incumbent.astype(int)
    eligible["prior_pres_dem_margin"] = np.select(
        [eligible.cycle.eq(2014), eligible.cycle.eq(2018), eligible.cycle.eq(2022)],
        [eligible.pres_2012_dem_margin, eligible.pres_2016_dem_margin,
         eligible.pres_2020_dem_margin], default=np.nan)
    eligible["finance_complete"] = eligible.finance_complete.fillna(False).astype(int)
    eligible["prior_pres_swing"] = np.select(
        [eligible.cycle.eq(2018), eligible.cycle.eq(2022)],
        [eligible.pres_swing_2012_2016, eligible.pres_swing_2016_2020], default=np.nan)
    eligible["pres_trend_available"] = eligible.cycle.ne(2014).astype(int)

    numeric = ["dem_incumbent_i", "rep_incumbent_i", "prior_pres_dem_margin",
               "nonwhite_share", "white_college_share", "log_spending_ratio_d_to_r",
               "finance_complete", "prior_pres_swing", "pres_trend_available"]
    categorical = ["cycle", "chamber"]
    features = numeric + categorical
    preprocess = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")),
                               ("scale", StandardScaler())]), numeric),
        ("categorical", OneHotEncoder(drop="first", handle_unknown="ignore"), categorical),
    ])
    pipeline = Pipeline([("preprocess", preprocess), ("model", Ridge())])
    inner = KFold(n_splits=5, shuffle=True, random_state=20260805)
    estimator = GridSearchCV(pipeline, {"model__alpha": [0.1, 0.3, 1, 3, 10, 30]},
                             scoring="neg_mean_absolute_error", cv=inner)
    outer = KFold(n_splits=10, shuffle=True, random_state=20260805)
    y = eligible.raw_overperformance
    predictions = cross_val_predict(estimator, eligible[features], y, cv=outer)
    eligible["expected_raw_overperformance_oof"] = predictions
    eligible["war_residual_oof"] = y - predictions
    loco = cross_val_predict(estimator, eligible[features], y,
                             cv=GroupKFold(n_splits=3), groups=eligible.cycle)
    eligible["expected_raw_overperformance_loco"] = loco
    eligible["war_residual_loco"] = y - loco

    estimator.fit(eligible[features], y)
    eligible["expected_raw_overperformance_final"] = estimator.predict(eligible[features])
    eligible["war_residual_final"] = y - eligible.expected_raw_overperformance_final
    eligible["selected_ridge_alpha"] = estimator.best_params_["model__alpha"]
    rng = np.random.default_rng(20260806)
    bootstrap_predictions = np.empty((300, len(eligible)))
    fixed = clone(pipeline).set_params(model__alpha=estimator.best_params_["model__alpha"])
    for iteration in range(300):
        sample = rng.integers(0, len(eligible), len(eligible))
        fitted = clone(fixed).fit(eligible.iloc[sample][features], y.iloc[sample])
        bootstrap_predictions[iteration] = fitted.predict(eligible[features])
    bootstrap_residuals = y.to_numpy()[None, :] - bootstrap_predictions
    eligible["war_model_se"] = bootstrap_residuals.std(axis=0, ddof=1)
    eligible["war_final_ci_low"] = np.quantile(bootstrap_residuals, 0.025, axis=0)
    eligible["war_final_ci_high"] = np.quantile(bootstrap_residuals, 0.975, axis=0)

    diagnostics = pd.DataFrame([{
        "eligible_races": len(eligible), "oof_folds": 10,
        "mae_oof": mean_absolute_error(y, predictions),
        "rmse_oof": mean_squared_error(y, predictions) ** 0.5,
        "r2_oof": r2_score(y, predictions),
        "mae_leave_cycle_out": mean_absolute_error(y, loco),
        "rmse_leave_cycle_out": mean_squared_error(y, loco) ** 0.5,
        "r2_leave_cycle_out": r2_score(y, loco),
        "selected_final_alpha": estimator.best_params_["model__alpha"],
        "bootstrap_replicates": 300,
        "feature_specification": "+".join(features),
        "model_status": "preliminary_with_spending_and_presidential_trend",
    }])
    by_cycle = []
    for cycle, part in eligible.groupby("cycle"):
        by_cycle.append({
            "cycle": cycle, "eligible_races": len(part),
            "mae_oof": mean_absolute_error(part.raw_overperformance,
                                           part.expected_raw_overperformance_oof),
            "rmse_oof": mean_squared_error(part.raw_overperformance,
                                            part.expected_raw_overperformance_oof) ** 0.5,
            "r2_oof": r2_score(part.raw_overperformance,
                               part.expected_raw_overperformance_oof),
            "mae_leave_cycle_out": mean_absolute_error(part.raw_overperformance,
                                                        part.expected_raw_overperformance_loco),
        })
    by_cycle = pd.DataFrame(by_cycle)

    candidates = pd.read_csv(WAR / "race_candidate_results.csv")
    candidates["district"] = candidates.district.astype(int)
    scores = candidates.merge(
        eligible[["cycle", "chamber", "district", "raw_overperformance",
                  "expected_raw_overperformance_oof", "war_residual_oof",
                  "expected_raw_overperformance_final", "war_residual_final",
                  "war_model_se", "war_final_ci_low", "war_final_ci_high"]],
        on=["cycle", "chamber", "district"], how="inner", validate="many_to_one")
    sign = scores.party.map({"D": 1, "R": -1})
    scores["candidate_war_oof"] = scores.war_residual_oof * sign
    scores["candidate_war_final"] = scores.war_residual_final * sign
    scores["candidate_war_model_se"] = scores.war_model_se
    scores["candidate_war_final_ci_low"] = np.where(
        scores.party.eq("D"), scores.war_final_ci_low, -scores.war_final_ci_high)
    scores["candidate_war_final_ci_high"] = np.where(
        scores.party.eq("D"), scores.war_final_ci_high, -scores.war_final_ci_low)

    eligible.to_csv(WAR / "preliminary_war_races.csv", index=False)
    scores.to_csv(WAR / "preliminary_war_candidates.csv", index=False)
    diagnostics.to_csv(WAR / "preliminary_war_diagnostics.csv", index=False)
    by_cycle.to_csv(WAR / "preliminary_war_diagnostics_by_cycle.csv", index=False)
    print(diagnostics.to_string(index=False))
    print("\nDiagnostics by cycle:")
    print(by_cycle.to_string(index=False))
    print("\nTop candidate OOF WAR:")
    print(scores.nlargest(10, "candidate_war_oof")[
        ["cycle", "chamber", "district", "candidate", "party", "candidate_war_oof"]
    ].to_string(index=False))


if __name__ == "__main__":
    main()
