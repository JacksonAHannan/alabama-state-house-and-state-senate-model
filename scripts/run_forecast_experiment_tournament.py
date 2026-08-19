"""Run leakage-aware 2026 forecast experiments over the full CMO archive."""
from __future__ import annotations

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import BayesianRidge, ElasticNet, Ridge
from sklearn.metrics import brier_score_loss, mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

from fit_2026_prospective_model import BASE_FEATURES, FORECAST, historical, simulate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "war"
SEED = 20260816
PUBLIC_MODELS = {
    "ensemble_ramp_ridge_80_20": "80/20 ramp + ridge",
    "post2016_ramp": "Post-2016 ramp",
    "ramp_all_extra_trees": "Extra Trees",
    "ramp_all_gradient_boosting": "Gradient boosting",
    "ramp_all_spline_ridge": "Spline ridge",
    "ramp_all_elastic_net": "Elastic Net",
}


def prepare_data() -> pd.DataFrame:
    data = historical().copy()
    national = pd.read_csv(ROOT / "data" / "manual" / "national_midterm_environment.csv")
    data = data.merge(national[["cycle", "midterm_house_dem_margin"]], on="cycle", how="left", validate="many_to_one")
    data["ramp_baseline"] = data.national_environment_ramp_baseline
    data["finance_ratio_capped"] = data.log_fundraising_ratio_d_to_r.clip(-3, 3)
    data["spending_ratio_capped"] = data.log_spending_ratio_d_to_r.clip(-3, 3)
    data["open_seat"] = ((data.dem_incumbent_i.eq(0)) & (data.rep_incumbent_i.eq(0))).astype(int)
    data["finance_x_open"] = data.finance_ratio_capped * data.open_seat
    data["finance_x_dem_inc"] = data.finance_ratio_capped * data.dem_incumbent_i
    data["finance_x_rep_inc"] = data.finance_ratio_capped * data.rep_incumbent_i
    data["ramp_swing"] = data.national_environment_weight * data.national_environment_swing
    data["ramp_x_nonwhite"] = data.ramp_swing * data.nonwhite_share
    data["ramp_x_white_college"] = data.ramp_swing * data.white_college_share
    data["post2008"] = data.cycle.ge(2010).astype(int)
    data["post2016"] = data.cycle.ge(2018).astype(int)
    data["years_since_2008"] = (data.cycle - 2008).clip(lower=0)
    data["years_since_2016"] = (data.cycle - 2016).clip(lower=0)
    data["prior_pres_swing_filled"] = data.prior_pres_swing
    data["trend_available"] = data.pres_trend_available.astype(int)
    data["federal_lean_to_nation"] = data.federal_index_margin - data.midterm_house_dem_margin
    data["federal_state_gap"] = data.federal_index_margin - data.statewide_index_margin
    data["federal_coverage_missing"] = data.federal_contested_coverage.isna().astype(int)
    return data


def prepare_prospective_data() -> pd.DataFrame:
    """Create the same forecast-eligible features for the 2026 districts."""
    from fit_2026_prospective_model import prospective_features

    data = prospective_features().copy()
    data["ramp_baseline"] = data.national_environment_ramp_baseline
    data["finance_ratio_capped"] = data.log_fundraising_ratio_d_to_r.clip(-3, 3)
    data["spending_ratio_capped"] = np.nan
    data["open_seat"] = ((data.dem_incumbent_i.eq(0)) & (data.rep_incumbent_i.eq(0))).astype(int)
    data["finance_x_open"] = data.finance_ratio_capped * data.open_seat
    data["finance_x_dem_inc"] = data.finance_ratio_capped * data.dem_incumbent_i
    data["finance_x_rep_inc"] = data.finance_ratio_capped * data.rep_incumbent_i
    data["ramp_swing"] = data.national_environment_weight * data.national_environment_swing
    data["ramp_x_nonwhite"] = data.ramp_swing * data.nonwhite_share
    data["ramp_x_white_college"] = data.ramp_swing * data.white_college_share
    data["post2008"] = 1
    data["post2016"] = 1
    data["years_since_2008"] = data.cycle - 2008
    data["years_since_2016"] = data.cycle - 2016
    data["prior_pres_swing_filled"] = data.prior_pres_swing
    data["trend_available"] = data.prior_pres_swing.notna().astype(int)
    return data


INC = ["dem_incumbent_i", "rep_incumbent_i"]
FIN = ["finance_ratio_capped", "ftm_finance_complete"]
FIN_OPEN = FIN + ["open_seat", "finance_x_open", "finance_x_dem_inc", "finance_x_rep_inc"]
DEMO = ["nonwhite_share", "white_college_share", "ramp_x_nonwhite", "ramp_x_white_college"]
TREND = ["prior_pres_swing_filled", "trend_available"]
FEDERAL = ["federal_lean_to_nation", "federal_state_gap", "federal_contested_coverage", "federal_coverage_missing"]
ALL = INC + FIN_OPEN + DEMO + TREND + ["post2008", "post2016", "years_since_2008", "years_since_2016"]
# Forecast analogue of the headline CMO expectation. These are contextual
# variables only: no incumbency status, fundraising, ideology, or prior CMO.
CMO_EXPECTATION = ["nonwhite_share", "white_college_share", "prior_pres_swing_filled",
                   "trend_available", "post2008", "post2016", "years_since_2008",
                   "years_since_2016"]

SPECS = {
    "prior_presidential": {"baseline": "prior_pres_dem_margin", "features": [], "model": "none", "eligible": True},
    "post2016_ramp": {"baseline": "ramp_baseline", "features": [], "model": "none", "eligible": True},
    "ramp_cmo_expected_performance": {"baseline": "ramp_baseline", "features": CMO_EXPECTATION,
                                       "model": "ridge", "eligible": True},
    "ramp_incumbency": {"baseline": "ramp_baseline", "features": INC, "model": "ridge", "eligible": True},
    "ramp_capped_fundraising": {"baseline": "ramp_baseline", "features": FIN, "model": "ridge", "eligible": True},
    "ramp_incumbency_fundraising": {"baseline": "ramp_baseline", "features": INC + FIN, "model": "ridge", "eligible": True},
    "ramp_finance_open_interactions": {"baseline": "ramp_baseline", "features": INC + FIN_OPEN, "model": "ridge", "eligible": True},
    "ramp_demographic_response": {"baseline": "ramp_baseline", "features": DEMO, "model": "ridge", "eligible": True},
    "ramp_presidential_trend": {"baseline": "ramp_baseline", "features": TREND, "model": "ridge", "eligible": True},
    "ramp_trend_incumbency": {"baseline": "ramp_baseline", "features": TREND + INC, "model": "ridge", "eligible": True},
    "ramp_trend_incumbency_finance": {"baseline": "ramp_baseline", "features": TREND + INC + FIN_OPEN, "model": "ridge", "eligible": True},
    "ramp_all_theory_ridge": {"baseline": "ramp_baseline", "features": ALL, "model": "ridge", "eligible": True},
    "ramp_all_elastic_net": {"baseline": "ramp_baseline", "features": ALL, "model": "elastic_net", "eligible": True},
    "ramp_all_bayesian_ridge": {"baseline": "ramp_baseline", "features": ALL, "model": "bayesian_ridge", "eligible": True},
    "ramp_all_spline_ridge": {"baseline": "ramp_baseline", "features": ALL, "model": "spline_ridge", "eligible": True},
    "ramp_all_gradient_boosting": {"baseline": "ramp_baseline", "features": ALL, "model": "gradient_boosting", "eligible": True},
    "ramp_all_hist_gradient": {"baseline": "ramp_baseline", "features": ALL, "model": "hist_gradient", "eligible": True},
    "ramp_all_random_forest": {"baseline": "ramp_baseline", "features": ALL, "model": "random_forest", "eligible": True},
    "ramp_all_extra_trees": {"baseline": "ramp_baseline", "features": ALL, "model": "extra_trees", "eligible": True},
    # Same-cycle federal results are unavailable before a forecast. These rows
    # measure an information upper bound and are never promotion-eligible.
    "same_cycle_federal_upper_bound": {"baseline": "federal_index_margin", "features": [], "model": "none", "eligible": False},
    "same_cycle_federal_plus_ramp_layers": {"baseline": "federal_index_margin", "features": ALL, "model": "ridge", "eligible": False},
}


def pipeline(kind: str, features: list[str]) -> Pipeline:
    if kind == "spline_ridge":
        prep = ColumnTransformer([
            ("spline", Pipeline([("impute", SimpleImputer(strategy="median")),
                                 ("spline", SplineTransformer(n_knots=3, degree=2)),
                                 ("scale", StandardScaler())]), features),
            ("chamber", OneHotEncoder(handle_unknown="ignore"), ["chamber"]),
        ])
    else:
        prep = ColumnTransformer([
            ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")),
                                  ("scale", StandardScaler())]), features),
            ("chamber", OneHotEncoder(handle_unknown="ignore"), ["chamber"]),
        ])
    models = {
        "ridge": Ridge(alpha=20.0),
        "elastic_net": ElasticNet(alpha=.3, l1_ratio=.2, max_iter=30000, random_state=SEED),
        "bayesian_ridge": BayesianRidge(),
        "spline_ridge": Ridge(alpha=40.0),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=120, max_depth=2, learning_rate=.025,
                                                        loss="huber", random_state=SEED),
        "hist_gradient": HistGradientBoostingRegressor(max_iter=120, max_leaf_nodes=10, l2_regularization=10,
                                                       learning_rate=.04, random_state=SEED),
        "random_forest": RandomForestRegressor(n_estimators=400, min_samples_leaf=15, max_features=.7,
                                                random_state=SEED, n_jobs=-1),
        "extra_trees": ExtraTreesRegressor(n_estimators=400, min_samples_leaf=15, max_features=.7,
                                            random_state=SEED, n_jobs=-1),
    }
    return Pipeline([("preprocess", prep), ("model", models[kind])])


def cycle_balanced_weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame.cycle.value_counts()
    return frame.cycle.map(lambda cycle: 1.0 / counts.loc[cycle]).to_numpy()


def evaluate() -> tuple[pd.DataFrame, pd.DataFrame]:
    data = prepare_data()
    detail = []
    cycles = sorted(data.cycle.unique())
    for test_cycle in cycles[1:]:
        train, test = data[data.cycle.lt(test_cycle)].copy(), data[data.cycle.eq(test_cycle)].copy()
        for name, spec in SPECS.items():
            train_use = train.dropna(subset=[spec["baseline"]])
            test_use = test.dropna(subset=[spec["baseline"]]).copy()
            if test_use.empty:
                continue
            adjustment = np.zeros(len(test_use))
            if spec["model"] != "none":
                model = pipeline(spec["model"], spec["features"])
                target = train_use.legislative_dem_margin - train_use[spec["baseline"]]
                fit_args = {}
                if spec["model"] not in {"bayesian_ridge"}:
                    fit_args["model__sample_weight"] = cycle_balanced_weights(train_use)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model.fit(train_use[spec["features"] + ["chamber"]], target, **fit_args)
                    adjustment = model.predict(test_use[spec["features"] + ["chamber"]])
            prediction = test_use[spec["baseline"]].to_numpy() + adjustment
            train_error = train_use.legislative_dem_margin - train_use[spec["baseline"]]
            scale = max(5.0, float(train_error.std(ddof=1)))
            probability = expit(prediction / scale)
            low, high = prediction - 1.28155 * scale, prediction + 1.28155 * scale
            for race, pred, adj, prob, lo, hi in zip(test_use.itertuples(), prediction, adjustment, probability, low, high):
                detail.append({"specification": name, "promotion_eligible": spec["eligible"],
                               "test_cycle": test_cycle, "chamber": race.chamber, "district": race.district,
                               "actual": race.legislative_dem_margin, "prediction": pred, "adjustment": adj,
                               "error": race.legislative_dem_margin - pred, "dem_probability": prob,
                               "interval_80_low": lo, "interval_80_high": hi,
                               "interval_80_covered": lo <= race.legislative_dem_margin <= hi})
    detail = pd.DataFrame(detail)
    detail["absolute_error"] = detail.error.abs()
    detail["squared_error"] = detail.error ** 2
    detail["dem_won"] = detail.actual.gt(0).astype(int)
    rows = []
    ramp_cycle = (detail[detail.specification.eq("post2016_ramp")]
                  .groupby("test_cycle").absolute_error.mean())
    for name, group in detail.groupby("specification"):
        cycle_mae = group.groupby("test_cycle").absolute_error.mean()
        recent = group[group.test_cycle.ge(2018)]
        latest = group[group.test_cycle.eq(2022)]
        rows.append({
            "specification": name, "promotion_eligible": bool(group.promotion_eligible.iloc[0]),
            "forward_cycles": group.test_cycle.nunique(), "cycle_balanced_mean_mae": cycle_mae.mean(),
            "race_weighted_mae": group.absolute_error.mean(), "rmse": np.sqrt(group.squared_error.mean()),
            "post2016_mean_mae": recent.groupby("test_cycle").absolute_error.mean().mean(),
            "latest_mae": latest.absolute_error.mean(),
            "latest_house_mae": latest[latest.chamber.eq("house")].absolute_error.mean(),
            "latest_senate_mae": latest[latest.chamber.eq("senate")].absolute_error.mean(),
            "worst_cycle_mae": cycle_mae.max(),
            "worst_cycle_degradation_vs_ramp": (cycle_mae - ramp_cycle.reindex(cycle_mae.index)).max(),
            "brier": brier_score_loss(group.dem_won, group.dem_probability),
            "interval_80_coverage": group.interval_80_covered.mean(),
        })
    return detail, pd.DataFrame(rows).sort_values("cycle_balanced_mean_mae")


def ensembles(detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pivot = detail.pivot_table(index=["test_cycle", "chamber", "district", "actual"],
                               columns="specification", values="prediction").reset_index()
    candidates = {
        "ensemble_ramp_incumbency_75_25": {"post2016_ramp": .75, "ramp_incumbency": .25},
        "ensemble_ramp_trend_75_25": {"post2016_ramp": .75, "ramp_presidential_trend": .25},
        "ensemble_ramp_finance_85_15": {"post2016_ramp": .85, "ramp_capped_fundraising": .15},
        "ensemble_ramp_ridge_80_20": {"post2016_ramp": .8, "ramp_all_theory_ridge": .2},
        "ensemble_ramp_inc_trend": {"post2016_ramp": .5, "ramp_incumbency": .25,
                                     "ramp_presidential_trend": .25},
    }
    rows, predictions = [], []
    ramp_cycle = (pivot.assign(ae=lambda x: (x.actual - x.post2016_ramp).abs())
                  .groupby("test_cycle").ae.mean())
    for name, weights in candidates.items():
        needed = list(weights)
        use = pivot.dropna(subset=needed).copy()
        use["prediction"] = sum(weight * use[column] for column, weight in weights.items())
        use["error"] = use.actual - use.prediction
        use["absolute_error"] = use.error.abs()
        cycle = use.groupby("test_cycle").absolute_error.mean()
        recent = use[use.test_cycle.ge(2018)].groupby("test_cycle").absolute_error.mean().mean()
        latest = use[use.test_cycle.eq(2022)]
        rows.append({"specification": name, "cycle_balanced_mean_mae": cycle.mean(),
                     "post2016_mean_mae": recent, "latest_mae": latest.absolute_error.mean(),
                     "latest_house_mae": latest[latest.chamber.eq("house")].absolute_error.mean(),
                     "latest_senate_mae": latest[latest.chamber.eq("senate")].absolute_error.mean(),
                     "worst_cycle_degradation_vs_ramp": (cycle-ramp_cycle.reindex(cycle.index)).max()})
        predictions.append(use.assign(specification=name))
    return pd.concat(predictions, ignore_index=True), pd.DataFrame(rows).sort_values("cycle_balanced_mean_mae")


def _sequential_contributions(model: Pipeline, train: pd.DataFrame, test: pd.DataFrame,
                              features: list[str], scale: float = 1.0) -> tuple[np.ndarray, list[dict]]:
    """Return predictions and an exact, explicitly ordered reveal-path decomposition."""
    actual = test[features + ["chamber"]].copy()
    reference = actual.copy()
    for feature in features:
        reference[feature] = pd.to_numeric(train[feature], errors="coerce").median()
    previous = model.predict(reference) * scale
    records: list[dict] = []
    for row_index, race in enumerate(test.itertuples()):
        records.append({"chamber": race.chamber, "district": race.district, "step": 1,
                        "variable": "model_intercept_and_chamber", "value": race.chamber,
                        "contribution": previous[row_index]})
    working = reference.copy()
    for step, feature in enumerate(features, start=2):
        working[feature] = actual[feature]
        current = model.predict(working) * scale
        delta = current - previous
        for row_index, race in enumerate(test.itertuples()):
            value = actual.iloc[row_index][feature]
            records.append({"chamber": race.chamber, "district": race.district, "step": step,
                            "variable": feature, "value": None if pd.isna(value) else value,
                            "contribution": delta[row_index]})
        previous = current
    return previous, records


def write_public_model_comparison() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit the strongest forecast-eligible models and export auditable 2026 comparisons."""
    train, test = prepare_data(), prepare_prospective_data()
    rows: list[dict] = []
    contributions: list[dict] = []
    ramp = test.ramp_baseline.to_numpy()

    for model_name, label in PUBLIC_MODELS.items():
        if model_name == "post2016_ramp":
            prediction = ramp
            model_records: list[dict] = []
        else:
            source_name = "ramp_all_theory_ridge" if model_name == "ensemble_ramp_ridge_80_20" else model_name
            spec = SPECS[source_name]
            fit_train = train.dropna(subset=["ramp_baseline", "legislative_dem_margin"]).copy()
            fitted = pipeline(spec["model"], spec["features"])
            target = fit_train.legislative_dem_margin - fit_train.ramp_baseline
            fitted.fit(fit_train[spec["features"] + ["chamber"]], target,
                       model__sample_weight=cycle_balanced_weights(fit_train))
            scale = .2 if model_name == "ensemble_ramp_ridge_80_20" else 1.0
            adjustment, model_records = _sequential_contributions(
                fitted, fit_train, test, spec["features"], scale=scale)
            prediction = ramp + adjustment
        for race, margin in zip(test.itertuples(), prediction):
            rows.append({"model": model_name, "model_label": label, "is_public_default":
                         model_name == "ensemble_ramp_ridge_80_20", "chamber": race.chamber,
                         "district": race.district, "predicted_dem_margin": margin})
        for record in model_records:
            record["model"] = model_name
            record["model_label"] = label
            contributions.append(record)

    comparison = pd.DataFrame(rows)
    detail = pd.DataFrame(contributions)
    if not detail.empty:
        base = test.set_index(["chamber", "district"]).ramp_baseline
        detail["running_margin"] = detail.groupby(["model", "chamber", "district"]).contribution.cumsum()
        detail["running_margin"] += [base.loc[(r.chamber, r.district)] for r in detail.itertuples()]
    comparison.to_csv(OUT / "2026_model_comparison.csv", index=False)
    detail.to_csv(OUT / "2026_model_variable_contributions.csv", index=False)
    return comparison, detail


def simulation_errors(predictions: pd.DataFrame, specification: str) -> pd.DataFrame:
    """Adapt a model's expanding-window errors to the shared simulator API."""
    use = predictions[predictions.specification.eq(specification)].copy()
    if use.empty:
        raise ValueError(f"No out-of-fold errors for {specification}")
    use["error"] = use.actual - use.prediction
    use["specification"] = "baseline"
    return use[["specification", "test_cycle", "chamber", "district", "error"]]


def publish_canonical_forecast() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Publish the selected 80/20 ensemble as the sole canonical forecast."""
    if not BASE_FEATURES.exists():
        raise FileNotFoundError(f"Run fit_2026_prospective_model.py first: {BASE_FEATURES}")
    detail, _ = evaluate()
    ensemble_predictions, ensemble_summary = ensembles(detail)
    comparison, _ = write_public_model_comparison()
    selected = "ensemble_ramp_ridge_80_20"
    score = ensemble_summary.set_index("specification").loc[selected]
    if not (score.worst_cycle_degradation_vs_ramp < 0):
        raise ValueError("Selected ensemble no longer improves every ramp holdout")
    base = pd.read_csv(BASE_FEATURES)
    margins = (comparison[comparison.model.eq(selected)]
               [["chamber", "district", "predicted_dem_margin"]])
    forecast = (base.drop(columns=["predicted_dem_margin", "dem_win_probability",
                                   "margin_80_low", "margin_80_high",
                                   "margin_95_low", "margin_95_high"], errors="ignore")
                .merge(margins, on=["chamber", "district"], validate="one_to_one"))
    forecast["ensemble_adjustment"] = forecast.predicted_dem_margin - forecast.poll_adjusted_dem_margin
    forecast["selected_specification"] = selected
    forecast["selection_reason"] = (
        "80/20 ramp-ridge ensemble improved every expanding-window holdout versus the ramp")
    forecast["model_status"] = "public_experimental_selected_ensemble"
    errors = simulation_errors(ensemble_predictions, selected)
    forecast, seats = simulate(forecast.reset_index(drop=True), errors)
    forecast["predicted_winner"] = np.where(forecast.predicted_dem_margin.gt(0), "D", "R")
    forecast.to_csv(FORECAST, index=False)
    seats.to_csv(OUT / "2026_correlated_seat_simulation.csv", index=False)
    decomposition_columns = [
        "chamber", "district", "structural_2024_pres_margin", "environment_adjustment",
        "baseline_forecast_margin", "ensemble_adjustment", "incumbency_adjustment",
        "demographic_residual_adjustment", "cmo_adjustment", "finance_adjustment",
        "cmo_scenario_adjustment", "scenario_finance_scenario_adjustment",
        "predicted_dem_margin", "dem_win_probability", "margin_80_low", "margin_80_high",
        "selected_specification", "selection_reason",
    ]
    forecast[decomposition_columns].to_csv(OUT / "2026_forecast_decomposition.csv", index=False)
    return forecast, seats


def main() -> None:
    detail, summary = evaluate()
    ensemble_detail, ensemble_summary = ensembles(detail)
    detail.to_csv(OUT / "forecast_experiment_tournament_predictions.csv", index=False)
    summary.to_csv(OUT / "forecast_experiment_tournament_summary.csv", index=False)
    ensemble_detail.to_csv(OUT / "forecast_experiment_ensemble_predictions.csv", index=False)
    ensemble_summary.to_csv(OUT / "forecast_experiment_ensemble_summary.csv", index=False)
    write_public_model_comparison()
    publish_canonical_forecast()
    print("Forecast-eligible specifications")
    print(summary[summary.promotion_eligible][["specification", "cycle_balanced_mean_mae", "post2016_mean_mae",
          "latest_mae", "latest_house_mae", "latest_senate_mae", "worst_cycle_degradation_vs_ramp",
          "brier", "interval_80_coverage"]].to_string(index=False))
    print("\nRetrospective upper bounds")
    print(summary[~summary.promotion_eligible][["specification", "cycle_balanced_mean_mae",
          "post2016_mean_mae", "latest_mae"]].to_string(index=False))
    print("\nConservative ensembles")
    print(ensemble_summary.to_string(index=False))


if __name__ == "__main__":
    main()
