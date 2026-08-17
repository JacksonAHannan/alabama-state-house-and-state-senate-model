"""Compare national-environment cadence and ML specifications by future cycle.

The effective sample for a cadence is the election cycle, not the race.  This
script therefore reports cycle-balanced errors and distinguishes descriptive
full-sample cadence estimates from genuine expanding-window predictions.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from fit_2026_prospective_model import historical

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "war"
CYCLES = (1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022)
NUMERIC = ["prior_pres_dem_margin", "national_environment_swing", "nonwhite_share",
           "white_college_share", "dem_incumbent_i", "rep_incumbent_i",
           "federal_contested_coverage", "years_since_2008", "years_since_2016",
           "swing_post2016", "swing_years_since2016"]
CATEGORICAL = ["chamber"]


def frame() -> pd.DataFrame:
    data = historical()
    data = data[data.cycle.isin(CYCLES) & data.prior_pres_dem_margin.notna()].copy()
    data["post2016"] = data.cycle.ge(2018).astype(int)
    data["years_since_2008"] = (data.cycle - 2008).clip(lower=0)
    data["years_since_2016"] = (data.cycle - 2016).clip(lower=0)
    data["swing_post2016"] = data.national_environment_swing * data.post2016
    data["swing_years_since2016"] = data.national_environment_swing * data.years_since_2016
    return data


def optimal_cycle_weights(data: pd.DataFrame) -> pd.DataFrame:
    grid = np.linspace(0.0, 3.0, 1201)
    rows = []
    for cycle, group in data.groupby("cycle"):
        swing = float(group.national_environment_swing.iloc[0])
        errors = [mean_absolute_error(group.legislative_dem_margin,
                                      group.prior_pres_dem_margin + weight * swing)
                  for weight in grid]
        best = int(np.argmin(errors))
        rows.append({"cycle": cycle, "races": len(group), "national_swing": swing,
                     "optimal_nonnegative_weight": float(grid[best]), "minimum_mae": errors[best],
                     "baseline_mae": mean_absolute_error(group.legislative_dem_margin,
                                                         group.prior_pres_dem_margin)})
    return pd.DataFrame(rows)


def cadence_comparison(data: pd.DataFrame, optimal: pd.DataFrame) -> pd.DataFrame:
    empirical = optimal.set_index("cycle").optimal_nonnegative_weight.to_dict()
    schedules = {
        "no_environment": {cycle: 0.0 for cycle in CYCLES},
        "full_every_cycle": {cycle: 1.0 for cycle in CYCLES},
        "post2016_step": {cycle: float(cycle >= 2018) for cycle in CYCLES},
        "post2016_ramp": {cycle: (0.5 if cycle == 2018 else float(cycle >= 2022)) for cycle in CYCLES},
        "descriptive_cycle_optimum": empirical,
    }
    rows = []
    for name, weights in schedules.items():
        for cycle, group in data.groupby("cycle"):
            weight = weights[cycle]
            pred = group.prior_pres_dem_margin + weight * group.national_environment_swing
            rows.append({"model": name, "test_cycle": cycle, "weight": weight,
                         "races": len(group), "mae": mean_absolute_error(group.legislative_dem_margin, pred),
                         "validation_status": "descriptive_in_sample" if name == "descriptive_cycle_optimum"
                                              else "predeclared_schedule"})
    return pd.DataFrame(rows)


def estimator(name: str) -> Pipeline:
    prep = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")),
                              ("scale", StandardScaler())]), NUMERIC),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
    ])
    models = {
        "ridge": Ridge(alpha=20.0),
        "elastic_net": ElasticNet(alpha=.25, l1_ratio=.25, max_iter=20000, random_state=20260816),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=100, max_depth=2, learning_rate=.03,
                                                        loss="huber", random_state=20260816),
        "random_forest": RandomForestRegressor(n_estimators=400, min_samples_leaf=12,
                                                max_features=.7, random_state=20260816, n_jobs=-1),
        "extra_trees": ExtraTreesRegressor(n_estimators=400, min_samples_leaf=12,
                                            max_features=.7, random_state=20260816, n_jobs=-1),
    }
    return Pipeline([("preprocess", prep), ("model", models[name])])


def expanding_ml(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for test_cycle in CYCLES[1:]:
        train, test = data[data.cycle.lt(test_cycle)], data[data.cycle.eq(test_cycle)]
        target = train.legislative_dem_margin - train.prior_pres_dem_margin
        for name in ("ridge", "elastic_net", "gradient_boosting", "random_forest", "extra_trees"):
            model = estimator(name)
            model.fit(train[NUMERIC + CATEGORICAL], target)
            adjustment = model.predict(test[NUMERIC + CATEGORICAL])
            pred = test.prior_pres_dem_margin + adjustment
            rows.append({"model": name, "test_cycle": test_cycle, "train_cycles": ",".join(map(str, sorted(train.cycle.unique()))),
                         "races": len(test), "mae": mean_absolute_error(test.legislative_dem_margin, pred),
                         "mean_adjustment": float(np.mean(adjustment))})
    return pd.DataFrame(rows)


def extrapolations(optimal: pd.DataFrame) -> pd.DataFrame:
    weights = optimal.set_index("cycle").optimal_nonnegative_weight
    jump = float(weights.loc[2022] - weights.loc[2018])
    # A two-point saturating curve is descriptive, not independently validated:
    # w(t)=A(1-exp(-k(t-2016))).  It exactly matches 2018 and 2022, then makes
    # the next increment smaller instead of assuming indefinite linear growth.
    ratio = float(weights.loc[2022] / weights.loc[2018])
    decay = (-1.0 + np.sqrt(max(0.0, 4.0 * ratio - 3.0))) / 2.0
    ceiling = float(weights.loc[2018] / (1.0 - decay))
    saturating_2026 = ceiling * (1.0 - decay ** 5)
    candidates = [
        ("hold_2022", float(weights.loc[2022]), "conservative plateau"),
        ("post2016_saturating_curve", saturating_2026,
         "two-point diminishing-jump curve; descriptive only"),
        ("half_last_jump", float(weights.loc[2022] + .5 * jump), "diminishing post-2022 increase"),
        ("repeat_last_jump", float(weights.loc[2022] + jump), "linear post-2018 extrapolation"),
    ]
    return pd.DataFrame(candidates, columns=["cadence", "weight_2026", "interpretation"])


def main() -> None:
    data = frame()
    optimal = optimal_cycle_weights(data)
    cadence = cadence_comparison(data, optimal)
    ml = expanding_ml(data)
    future = extrapolations(optimal)
    optimal.to_csv(OUT / "national_environment_cycle_weights.csv", index=False)
    cadence.to_csv(OUT / "national_environment_cadence_comparison.csv", index=False)
    ml.to_csv(OUT / "national_environment_ml_forward_comparison.csv", index=False)
    future.to_csv(OUT / "national_environment_2026_extrapolations.csv", index=False)
    print(optimal.to_string(index=False))
    print("\nCadence mean MAE")
    print(cadence.groupby("model").mae.mean().sort_values().to_string())
    print("\nML mean and 2022 MAE")
    print(ml.groupby("model").agg(mean_mae=("mae", "mean"), latest_mae=("mae", "last")).sort_values("mean_mae").to_string())
    print("\n2026 extrapolations")
    print(future.to_string(index=False))


if __name__ == "__main__":
    main()
