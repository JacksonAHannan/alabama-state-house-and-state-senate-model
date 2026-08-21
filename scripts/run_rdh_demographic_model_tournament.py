"""Comprehensive leakage-aware tournament for historical RDH CVAP features."""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import (ExtraTreesRegressor, GradientBoostingRegressor,
                              HistGradientBoostingRegressor, RandomForestRegressor)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import BayesianRidge, ElasticNet, HuberRegressor, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_forecast_experiment_tournament import ALL, prepare_data, prepare_prospective_data

DEM = ROOT / "data" / "processed" / "demographics"
OUT = ROOT / "data" / "processed" / "elections" / "validation"
WAR = ROOT / "data" / "processed" / "war"
SEED = 20260817


def augment(frame: pd.DataFrame, prospective: bool = False) -> pd.DataFrame:
    x = frame.copy()
    if prospective:
        cvap = pd.read_csv(DEM / "rdh_2024_sld_cvap.csv")
        x = x.merge(cvap[["chamber", "district", "cvap_nonwhite_share", "cvap_black_nh_share",
                          "cvap_hispanic_share", "cvap_other_nonwhite_share", "cvap_total_moe_ratio"]],
                    on=["chamber", "district"], validate="one_to_one")
        x = x.rename(columns={"cvap_black_nh_share": "cvap_black_share",
                              "cvap_total_moe_ratio": "cvap_moe_ratio"})
    else:
        cvap = pd.read_csv(DEM / "rdh_historical_sld_cvap_2010_2022.csv")
        x = x.merge(cvap[["cycle", "chamber", "district", "cvap_nonwhite_share", "cvap_black_share",
                          "cvap_hispanic_share", "cvap_other_nonwhite_share", "cvap_moe_ratio"]],
                    on=["cycle", "chamber", "district"], how="left", validate="one_to_one")
    x["cvap_available"] = x.cvap_nonwhite_share.notna().astype(int)
    x["hybrid_nonwhite_share"] = x.cvap_nonwhite_share.fillna(x.nonwhite_share)
    x["cvap_total_gap"] = x.cvap_nonwhite_share - x.nonwhite_share
    x["hybrid_nonwhite_logit"] = np.log(x.hybrid_nonwhite_share.clip(.01, .99) /
                                         (1 - x.hybrid_nonwhite_share.clip(.01, .99)))
    x["ramp_swing"] = x.national_environment_weight * x.national_environment_swing
    for column in ["hybrid_nonwhite_share", "cvap_black_share", "cvap_hispanic_share",
                   "cvap_other_nonwhite_share", "cvap_total_gap", "white_college_share"]:
        x[f"{column}_x_swing"] = x[column] * x.ramp_swing
    x["senate_i"] = x.chamber.eq("senate").astype(int)
    return x


BASE_DEMO = ["hybrid_nonwhite_share", "white_college_share", "cvap_available",
             "hybrid_nonwhite_share_x_swing", "white_college_share_x_swing", "senate_i"]
COMPOSITION = ["cvap_black_share", "cvap_hispanic_share", "cvap_other_nonwhite_share", "cvap_available",
               "cvap_black_share_x_swing", "cvap_hispanic_share_x_swing",
               "cvap_other_nonwhite_share_x_swing", "senate_i"]
GAP = ["hybrid_nonwhite_share", "cvap_total_gap", "cvap_moe_ratio", "cvap_available",
       "hybrid_nonwhite_share_x_swing", "cvap_total_gap_x_swing", "senate_i"]
ALL_HYBRID = [{"nonwhite_share": "hybrid_nonwhite_share",
               "ramp_x_nonwhite": "hybrid_nonwhite_share_x_swing"}.get(c, c) for c in ALL]
TIME_EXTRAPOLATORS = {"post2008", "post2016", "years_since_2008", "years_since_2016"}
ALL_TOTAL_STABLE = [c for c in ALL if c not in TIME_EXTRAPOLATORS]
ALL_HYBRID_STABLE = [c for c in ALL_HYBRID if c not in TIME_EXTRAPOLATORS]

FEATURES = {
    "total_control": ALL + ["senate_i"],
    "cvap_core": BASE_DEMO,
    "cvap_composition": COMPOSITION,
    "cvap_gap": GAP,
    "cvap_rich": list(dict.fromkeys(BASE_DEMO + COMPOSITION + GAP + ["hybrid_nonwhite_logit"])),
    "all_hybrid": ALL_HYBRID + ["cvap_available", "senate_i"],
    "all_hybrid_gap": ALL_HYBRID + ["cvap_total_gap", "cvap_moe_ratio", "cvap_available", "senate_i"],
    "all_hybrid_composition": ALL_HYBRID + COMPOSITION,
    "total_stable": ALL_TOTAL_STABLE + ["senate_i"],
    "all_hybrid_stable": ALL_HYBRID_STABLE + ["cvap_available", "senate_i"],
    "all_hybrid_stable_gap": ALL_HYBRID_STABLE + ["cvap_total_gap", "cvap_moe_ratio",
                                                    "cvap_available", "senate_i"],
    "all_hybrid_stable_composition": ALL_HYBRID_STABLE + COMPOSITION,
}


def estimator(name: str):
    models = {
        "ridge_5": Ridge(alpha=5), "ridge_20": Ridge(alpha=20),
        "ridge_100": Ridge(alpha=100), "ridge_300": Ridge(alpha=300),
        "elastic_10": ElasticNet(alpha=.1, l1_ratio=.2, max_iter=30000, random_state=SEED),
        "elastic_30": ElasticNet(alpha=.3, l1_ratio=.2, max_iter=30000, random_state=SEED),
        "bayesian": BayesianRidge(), "huber": HuberRegressor(epsilon=1.5, alpha=1, max_iter=1000),
        "extra_trees": ExtraTreesRegressor(n_estimators=180, min_samples_leaf=12, max_features=.7,
                                             random_state=SEED, n_jobs=-1),
        "random_forest": RandomForestRegressor(n_estimators=180, min_samples_leaf=12, max_features=.7,
                                                 random_state=SEED, n_jobs=-1),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=100, max_depth=2, learning_rate=.025,
                                                        loss="huber", random_state=SEED),
        "hist_gradient": HistGradientBoostingRegressor(max_iter=100, max_leaf_nodes=10,
                                                        l2_regularization=10, learning_rate=.04,
                                                        random_state=SEED),
    }
    return models[name]


LINEAR = {"ridge_5", "ridge_20", "ridge_100", "ridge_300", "elastic_10", "elastic_30", "bayesian", "huber"}
MODELS = ["ridge_5", "ridge_20", "ridge_100", "ridge_300", "elastic_10", "elastic_30",
          "bayesian", "huber", "extra_trees", "random_forest", "gradient_boosting", "hist_gradient"]
BLENDS = [.10, .20, .35, 1.0]


def make_pipeline(name: str) -> Pipeline:
    steps = [("impute", SimpleImputer(strategy="median", add_indicator=True))]
    if name in LINEAR:
        steps.append(("scale", StandardScaler()))
    steps.append(("model", estimator(name)))
    return Pipeline(steps)


def weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame.cycle.value_counts()
    return frame.cycle.map(lambda c: 1 / counts.loc[c]).to_numpy()


def evaluate() -> tuple[pd.DataFrame, pd.DataFrame]:
    data = augment(prepare_data())
    records = []
    test_cycles = sorted(data.cycle.dropna().unique())[1:]
    for cycle in test_cycles:
        train = data[data.cycle < cycle].dropna(subset=["ramp_baseline", "legislative_dem_margin"])
        test = data[data.cycle == cycle].dropna(subset=["ramp_baseline", "legislative_dem_margin"])
        target = train.legislative_dem_margin - train.ramp_baseline
        for family, columns in FEATURES.items():
            for model_name in MODELS:
                model = make_pipeline(model_name)
                fit_args = {} if model_name in {"bayesian", "huber"} else {"model__sample_weight": weights(train)}
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model.fit(train[columns], target, **fit_args)
                    raw_adjustment = model.predict(test[columns])
                for blend in BLENDS:
                    prediction = test.ramp_baseline.to_numpy(copy=True) + blend * raw_adjustment
                    for race, pred in zip(test.itertuples(), prediction):
                        records.append({"test_cycle": cycle, "feature_family": family, "model": model_name,
                                        "blend": blend, "specification": f"{family}__{model_name}__{blend:g}",
                                        "chamber": race.chamber, "district": race.district,
                                        "actual": race.legislative_dem_margin, "prediction": pred,
                                        "absolute_error": abs(race.legislative_dem_margin - pred)})
    detail = pd.DataFrame(records)
    rows = []
    for name, group in detail.groupby("specification"):
        cycle = group.groupby("test_cycle").absolute_error.mean()
        modern = cycle.reindex([2014, 2018, 2022]).dropna()
        rows.append({"specification": name, "feature_family": group.feature_family.iloc[0],
                     "model": group.model.iloc[0], "blend": group.blend.iloc[0],
                     "mean_mae": cycle.mean(), "modern_mean_mae": modern.mean(),
                     "post2016_mean_mae": cycle.reindex([2018, 2022]).mean(),
                     "latest_mae": cycle.loc[2022], "worst_cycle_mae": cycle.max(),
                     "mae_2014": cycle.loc[2014], "mae_2018": cycle.loc[2018], "mae_2022": cycle.loc[2022],
                     "early_mean_mae": cycle[cycle.index < 2014].mean()})
    summary = pd.DataFrame(rows).sort_values(["mean_mae", "latest_mae"])
    control = summary[(summary.feature_family == "total_control") & (summary.model == "ridge_20") &
                      np.isclose(summary.blend, .2)].iloc[0]
    summary["improves_mean_vs_control"] = summary.mean_mae < control.mean_mae
    summary["improves_recent_vs_control"] = summary.post2016_mean_mae < control.post2016_mean_mae
    summary["improves_latest_vs_control"] = summary.latest_mae < control.latest_mae
    summary["passes_all_three"] = summary[["improves_mean_vs_control", "improves_recent_vs_control",
                                            "improves_latest_vs_control"]].all(axis=1)
    return detail, summary


def score_2026(summary: pd.DataFrame) -> pd.DataFrame:
    train = augment(prepare_data()).dropna(subset=["ramp_baseline", "legislative_dem_margin"])
    test = augment(prepare_prospective_data(), prospective=True)
    target = train.legislative_dem_margin - train.ramp_baseline
    candidates = pd.concat([summary.head(20), summary[summary.passes_all_three].head(20)]).drop_duplicates("specification")
    rows = []
    for spec in candidates.itertuples():
        columns = FEATURES[spec.feature_family]
        model = make_pipeline(spec.model)
        fit_args = {} if spec.model in {"bayesian", "huber"} else {"model__sample_weight": weights(train)}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(train[columns], target, **fit_args)
            pred = test.ramp_baseline.to_numpy(copy=True) + spec.blend * model.predict(test[columns])
        for race, margin in zip(test.itertuples(), pred):
            rows.append({"specification": spec.specification, "chamber": race.chamber,
                         "district": race.district, "predicted_dem_margin": margin})
    return pd.DataFrame(rows)


def main() -> None:
    detail, summary = evaluate()
    prospective = score_2026(summary)
    detail.to_csv(VALID := OUT / "rdh_demographic_model_tournament_predictions.csv", index=False)
    summary.to_csv(OUT / "rdh_demographic_model_tournament_summary.csv", index=False)
    prospective.to_csv(WAR / "rdh_demographic_model_tournament_2026.csv", index=False)
    print("Top models")
    print(summary.head(30).to_string(index=False))
    print(f"\nPass all three vs total-control 80/20 ridge: {summary.passes_all_three.sum()} / {len(summary)}")


if __name__ == "__main__":
    main()
