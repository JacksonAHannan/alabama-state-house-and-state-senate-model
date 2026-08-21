"""Forward-test FCPA fundraising amount and viability features."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from fit_preliminary_war_model import estimator, prepare

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data/processed/war"
CORE = ["dem_incumbent_i", "rep_incumbent_i", "prior_pres_dem_margin", "nonwhite_share",
        "white_college_share", "prior_pres_swing", "pres_trend_available"]
SCALES = (10_000, 25_000, 50_000, 100_000, 200_000)
THRESHOLDS = (10_000, 25_000, 50_000, 100_000)


def race_finance() -> pd.DataFrame:
    candidate = pd.read_csv(WAR / "fcpa_candidate_cycle_finance.csv")
    candidate = candidate[candidate.cycle.isin([2014, 2018, 2022])].copy()
    candidate["usable"] = ~candidate.aggregation_status.eq("multiple_active_pcc_records_review")
    values = candidate.pivot(index=["cycle", "chamber", "district"], columns="party",
                             values="fundraising_total")
    usable = candidate.pivot(index=["cycle", "chamber", "district"], columns="party",
                             values="usable")
    complete = values[["D", "R"]].notna().all(axis=1) & usable[["D", "R"]].eq(True).all(axis=1)
    result = values.loc[complete, ["D", "R"]].rename(
        columns={"D": "dem_fundraising", "R": "rep_fundraising"}).reset_index()
    return add_features(result)


def add_features(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    dem, rep = data.dem_fundraising.clip(lower=0), data.rep_fundraising.clip(lower=0)
    data["raw_fundraising_gap_100k"] = (dem - rep) / 100_000
    data["sqrt_fundraising_gap"] = (np.sqrt(dem) - np.sqrt(rep)) / np.sqrt(50_000)
    for scale in SCALES:
        data[f"log1p_fundraising_gap_{scale//1000}k"] = np.log1p(dem / scale) - np.log1p(rep / scale)
    for threshold in THRESHOLDS:
        dem_viable, rep_viable = dem.ge(threshold).astype(int), rep.ge(threshold).astype(int)
        data[f"viable_gap_{threshold//1000}k"] = dem_viable - rep_viable
        data[f"both_viable_{threshold//1000}k"] = dem_viable * rep_viable
    return data


def specifications() -> dict[str, list[str]]:
    specs = {"nonfinance_baseline": CORE,
             "raw_amount_gap": CORE + ["raw_fundraising_gap_100k"],
             "sqrt_diminishing_gap": CORE + ["sqrt_fundraising_gap"]}
    for scale in SCALES:
        specs[f"log_diminishing_{scale//1000}k"] = CORE + [f"log1p_fundraising_gap_{scale//1000}k"]
    for threshold in THRESHOLDS:
        specs[f"viable_flag_{threshold//1000}k"] = CORE + [f"viable_gap_{threshold//1000}k",
                                                            f"both_viable_{threshold//1000}k"]
        specs[f"hybrid_log50_viable_{threshold//1000}k"] = CORE + ["log1p_fundraising_gap_50k",
                                                                    f"viable_gap_{threshold//1000}k",
                                                                    f"both_viable_{threshold//1000}k"]
    return specs


def metrics(actual, predicted) -> dict[str, float]:
    return {"mae": mean_absolute_error(actual, predicted),
            "rmse": mean_squared_error(actual, predicted) ** .5}


def forward_validate(data: pd.DataFrame, specs: dict[str, list[str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, predictions = [], []
    for test_cycle in (2018, 2022):
        train, test = data[data.cycle.lt(test_cycle)], data[data.cycle.eq(test_cycle)]
        for name, columns in specs.items():
            features = columns + ["chamber"]
            fitted = estimator(columns, ["chamber"]).fit(
                train[features], train.legislative_dem_margin)
            predicted = fitted.predict(test[features])
            rows.append({"specification": name, "test_cycle": test_cycle,
                         "train_races": len(train), "test_races": len(test),
                         "selected_alpha": fitted.best_params_["model__alpha"],
                         **metrics(test.legislative_dem_margin, predicted)})
            predictions.extend({"specification": name, "test_cycle": test_cycle,
                                "chamber": race.chamber, "district": race.district,
                                "actual_margin": race.legislative_dem_margin,
                                "predicted_margin": estimate,
                                "absolute_error": abs(race.legislative_dem_margin-estimate)}
                               for race, estimate in zip(test.itertuples(index=False), predicted))
    detail = pd.DataFrame(rows)
    summary = detail.groupby("specification", as_index=False).agg(
        forward_mae=("mae", "mean"), forward_rmse=("rmse", "mean"),
        worst_cycle_mae=("mae", "max"), latest_2022_mae=("mae", "last"))
    baseline = float(summary.loc[summary.specification.eq("nonfinance_baseline"), "forward_mae"].iloc[0])
    summary["mae_improvement_vs_nonfinance"] = baseline - summary.forward_mae
    summary["percent_mae_improvement"] = 100 * summary.mae_improvement_vs_nonfinance / baseline
    return summary.sort_values("forward_mae"), pd.DataFrame(predictions)


def leave_cycle_out(data: pd.DataFrame, specs: dict[str, list[str]]) -> pd.DataFrame:
    rows = []
    for test_cycle in (2014, 2018, 2022):
        train, test = data[data.cycle.ne(test_cycle)], data[data.cycle.eq(test_cycle)]
        for name, columns in specs.items():
            features = columns + ["chamber"]
            fitted = estimator(columns, ["chamber"]).fit(train[features], train.legislative_dem_margin)
            predicted = fitted.predict(test[features])
            rows.append({"specification": name, "test_cycle": test_cycle,
                         "loco_mae": mean_absolute_error(test.legislative_dem_margin, predicted)})
    detail = pd.DataFrame(rows)
    wide = detail.pivot(index="specification", columns="test_cycle", values="loco_mae")
    wide.columns = [f"loco_{cycle}_mae" for cycle in wide.columns]
    wide["loco_mean_cycle_mae"] = wide.mean(axis=1)
    return wide.reset_index()


def paired_uncertainty(predictions: pd.DataFrame) -> pd.DataFrame:
    errors = predictions.pivot(index=["test_cycle", "chamber", "district"],
                               columns="specification", values="absolute_error")
    baseline = errors.nonfinance_baseline
    rng = np.random.default_rng(20260817)
    rows = []
    for name in errors.columns:
        delta = (baseline - errors[name]).to_numpy()
        draws = rng.choice(delta, size=(20_000, len(delta)), replace=True).mean(axis=1)
        rows.append({"specification": name, "paired_mean_error_improvement": delta.mean(),
                     "paired_bootstrap_ci_low": np.quantile(draws, .025),
                     "paired_bootstrap_ci_high": np.quantile(draws, .975),
                     "paired_bootstrap_probability_improvement": np.mean(draws > 0)})
    return pd.DataFrame(rows)


def contrasts(data: pd.DataFrame, specs: dict[str, list[str]]) -> pd.DataFrame:
    template = data.iloc[[len(data)//2]].copy()
    rows = []
    for name, columns in specs.items():
        features = columns + ["chamber"]
        fitted = estimator(columns, ["chamber"]).fit(data[features], data.legislative_dem_margin)
        scenarios = []
        for dem, rep in ((200_000, 50_000), (50_000, 0), (50_000, 50_000)):
            scenario = template.copy()
            scenario["dem_fundraising"], scenario["rep_fundraising"] = dem, rep
            scenario = add_features(scenario)
            scenarios.append(float(fitted.predict(scenario[features])[0]))
        rows.append({"specification": name,
                     "effect_200k_vs_50k": scenarios[0]-scenarios[2],
                     "effect_50k_vs_0": scenarios[1]-scenarios[2],
                     "desired_order_200k_vs_50k_larger": scenarios[0]-scenarios[2] > scenarios[1]-scenarios[2]})
    return pd.DataFrame(rows)


def main() -> None:
    model = prepare(pd.read_csv(ROOT / "data/processed/elections/canonical_cmo_features.csv"))
    data = model.merge(race_finance(), on=["cycle", "chamber", "district"], validate="one_to_one")
    data = data[data.cycle.isin([2014, 2018, 2022])].copy()
    specs = specifications()
    summary, predictions = forward_validate(data, specs)
    contrast = contrasts(data, specs)
    summary = (summary.merge(contrast, on="specification", validate="one_to_one")
               .merge(leave_cycle_out(data, specs), on="specification", validate="one_to_one")
               .merge(paired_uncertainty(predictions), on="specification", validate="one_to_one"))
    data.to_csv(WAR / "fcpa_fundraising_experiment_panel.csv", index=False)
    predictions.to_csv(WAR / "fcpa_fundraising_experiment_predictions.csv", index=False)
    summary.to_csv(WAR / "fcpa_fundraising_experiment_summary.csv", index=False)
    print(data.groupby("cycle").size().rename("complete_races").to_string())
    print("\n" + summary.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
