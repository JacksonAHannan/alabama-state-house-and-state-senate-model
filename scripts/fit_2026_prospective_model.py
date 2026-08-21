"""Build the baseline-first 2026 Alabama legislative forecast.

The poll-adjusted 2024 presidential margin is the forecast anchor. Candidate,
incumbency, demographic, and finance layers are modeled as residual adjustments
and are promoted only when expanding-cycle tests improve on the direct baseline.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from fit_preliminary_war_model import prepare

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
ELECTIONS = ROOT / "data" / "processed" / "elections"
PRES = ROOT / "data" / "processed" / "presidential"
DEM = ROOT / "data" / "processed" / "demographics"
POLLING = ROOT / "data" / "processed" / "polling"
FORECAST = WAR / "2026_prospective_features_and_forecast.csv"
BASE_FEATURES = WAR / "2026_prospective_baseline_features.csv"
LEGACY = WAR / "2026_prospective_features_and_forecast_legacy_core_20260815.csv"
RNG_SEED = 20260815

SPECS = {
    "baseline": [],
    "national_environment": [],
    "national_environment_post2016_ramp": [],
    "national_environment_demographics": ["dem_incumbent_i", "rep_incumbent_i", "nonwhite_share",
                                            "white_college_share", "national_swing_x_nonwhite",
                                            "national_swing_x_white_college"],
    "national_environment_finance": ["dem_incumbent_i", "rep_incumbent_i", "log_fundraising_ratio_d_to_r",
                                     "ftm_finance_complete"],
    "incumbency": ["dem_incumbent_i", "rep_incumbent_i"],
    "incumbency_demographics": ["dem_incumbent_i", "rep_incumbent_i", "nonwhite_share", "white_college_share"],
    "finance_scenario": ["dem_incumbent_i", "rep_incumbent_i", "log_fundraising_ratio_d_to_r", "ftm_finance_complete"],
    "federal_realign_finance": ["dem_incumbent_i", "rep_incumbent_i", "log_fundraising_ratio_d_to_r",
                                "ftm_finance_complete", "federal_contested_coverage"],
}


def national_midterm_swings() -> dict[int, float]:
    """Official national Democratic-margin change from President to midterm."""
    data = pd.read_csv(ROOT / "data" / "manual" / "national_midterm_environment.csv")
    return data.set_index("cycle").national_environment_swing.to_dict()


def historical() -> pd.DataFrame:
    data = prepare(pd.read_csv(ELECTIONS / "canonical_cmo_features.csv"))
    federal = pd.read_csv(ELECTIONS / "historical_federal_district_baselines.csv")
    data = data.merge(federal[["cycle", "chamber", "district", "federal_index_margin",
                               "federal_contested_coverage"]],
                      on=["cycle", "chamber", "district"], how="left", validate="one_to_one")
    data["national_environment_swing"] = data.cycle.map(national_midterm_swings())
    data["national_environment_baseline"] = data.prior_pres_dem_margin + data.national_environment_swing
    # Exploratory nationalization schedule motivated by the 2016 realignment:
    # local results receive no national swing through 2014, half in the first
    # Trump-era midterm, and the full observed swing by 2022.
    data["national_environment_weight"] = data.cycle.map(
        {1994: 0.0, 1998: 0.0, 2002: 0.0, 2006: 0.0,
         2010: 0.0, 2014: 0.0, 2018: 0.5, 2022: 1.0})
    data["national_environment_ramp_baseline"] = (
        data.prior_pres_dem_margin + data.national_environment_weight * data.national_environment_swing)
    data["national_swing_x_nonwhite"] = data.national_environment_swing * data.nonwhite_share
    data["national_swing_x_white_college"] = data.national_environment_swing * data.white_college_share
    return data


def current_fundraising_features() -> pd.DataFrame:
    """Build race ratios from the current Alabama state campaign-finance export.

    An unmatched filing remains unknown. It is not silently converted to zero.
    """
    finance = pd.read_csv(WAR / "2026_state_candidate_finance_matches.csv")
    finance = finance[finance.cycle.eq(2026) & finance.party.isin(["D", "R"])].copy()
    finance["observed"] = finance.finance_observation_status.eq("observed")
    finance["receipts"] = pd.to_numeric(finance.state_contributions, errors="coerce")
    wide = finance.pivot_table(index=["chamber", "district"], columns="party", values="receipts", aggfunc="sum")
    observed = finance.pivot_table(index=["chamber", "district"], columns="party", values="observed", aggfunc="max")
    for party in ("D", "R"):
        if party not in wide: wide[party] = np.nan
        if party not in observed: observed[party] = False
    result = wide.reset_index()
    complete = observed["D"].fillna(False) & observed["R"].fillna(False)
    result["ftm_finance_complete"] = complete.to_numpy(dtype=int)
    result["log_fundraising_ratio_d_to_r"] = np.where(
        complete.to_numpy(), np.log((result["D"] + 500.0) / (result["R"] + 500.0)), np.nan)
    return result[["chamber", "district", "log_fundraising_ratio_d_to_r", "ftm_finance_complete"]]


def prospective_features() -> pd.DataFrame:
    roster = pd.read_csv(WAR / "2026_final_candidate_roster.csv")
    counts = roster.pivot_table(index=["chamber", "district"], columns="party", values="candidate", aggfunc="nunique", fill_value=0).reset_index()
    eligible = counts[(counts.get("D", 0).eq(1)) & (counts.get("R", 0).eq(1))][["chamber", "district"]]
    current = pd.read_csv(PRES / "2026_district_presidential_features.csv")
    old = pd.read_csv(PRES / "2022_district_presidential_features.csv")[["chamber", "district", "pres_2020_dem_margin"]]
    demo = pd.read_csv(DEM / "2026_sld_demographics.csv")
    inc = pd.read_csv(WAR / "2026_candidate_incumbency.csv").pivot_table(
        index=["chamber", "district"], columns="party", values="incumbent", aggfunc="max", fill_value=False
    ).reset_index()
    for party in ("D", "R"):
        if party not in inc:
            inc[party] = False
    inc = inc.rename(columns={"D": "dem_incumbent_i", "R": "rep_incumbent_i"})
    polling = pd.read_csv(WAR / "2026_poll_adjusted_baseline.csv").rename(columns={"status": "polling_baseline_status"})
    finance = current_fundraising_features()
    x = (eligible.merge(current, on=["chamber", "district"]).merge(old, on=["chamber", "district"])
         .merge(demo[["chamber", "district", "nonwhite_share", "white_college_share"]], on=["chamber", "district"])
         .merge(inc[["chamber", "district", "dem_incumbent_i", "rep_incumbent_i"]], on=["chamber", "district"])
         .merge(finance, on=["chamber", "district"], how="left")
         .merge(polling, on=["chamber", "district"], validate="one_to_one"))
    x["cycle"] = 2026
    x["prior_pres_dem_margin"] = x.poll_adjusted_dem_margin
    x["prior_pres_swing"] = x.pres_2024_dem_margin - x.pres_2020_dem_margin
    x["dem_incumbent_i"] = x.dem_incumbent_i.astype(int)
    x["rep_incumbent_i"] = x.rep_incumbent_i.astype(int)
    x["ftm_finance_complete"] = x.ftm_finance_complete.eq(True).astype(int)
    # The prospective anchor is itself a federal result (2024 President). The
    # historical federal-residual model therefore applies to this anchor without
    # inventing an unavailable 2026 state-office baseline.
    x["federal_index_margin"] = x.poll_adjusted_dem_margin
    x["federal_contested_coverage"] = 1.0
    national = pd.read_csv(POLLING / "votehub_silver_bplus_topline_environment.csv").iloc[0]
    catalist = pd.read_csv(POLLING / "catalist_national_demographic_master.csv")
    prior = catalist[(catalist.year.eq(2024)) & catalist.election_type.eq("president") &
                     catalist.dimension.eq("overall") & catalist.group.eq("Total") &
                     catalist.metric.eq("dem_two_party_share_pct")].iloc[0]
    x["national_environment_swing"] = (200.0 * float(national.dem_two_party_share) - 100.0) - (2.0 * float(prior.value) - 100.0)
    x["national_environment_baseline"] = x.poll_adjusted_dem_margin
    x["national_environment_weight"] = 1.0
    x["national_environment_ramp_baseline"] = x.poll_adjusted_dem_margin
    x["national_swing_x_nonwhite"] = x.national_environment_swing * x.nonwhite_share
    x["national_swing_x_white_college"] = x.national_environment_swing * x.white_college_share
    return x


def specification_baseline(name: str) -> str:
    if name.startswith("federal_"):
        return "federal_index_margin"
    if name.startswith("national_environment"):
        return ("national_environment_ramp_baseline"
                if name == "national_environment_post2016_ramp" else "national_environment_baseline")
    return "prior_pres_dem_margin"


def realignment_weights(cycles: pd.Series) -> np.ndarray:
    """Predeclared era weights: 2008 nationalization and the 2016 break."""
    return np.select([cycles.ge(2018), cycles.ge(2010)], [4.0, 2.0], default=1.0)


def residual_model(features: list[str]) -> Pipeline:
    prep = ColumnTransformer([("numeric", Pipeline([
        ("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
    ]), features)], remainder="drop")
    return Pipeline([("preprocess", prep), ("model", Ridge(alpha=10.0, fit_intercept=False))])


def backtest_layers(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, bool]]:
    # Use every available historical cycle. Promotion must improve the full
    # expanding-window record, the post-2016 mean, and the latest holdout.
    data = data[data.prior_pres_dem_margin.notna()].copy()
    rows, errors = [], []
    cycles = sorted(data.cycle.unique())
    for test_cycle in cycles[1:]:
        train = data[data.cycle.lt(test_cycle)]
        test = data[data.cycle.eq(test_cycle)]
        for name, features in SPECS.items():
            baseline_col = specification_baseline(name)
            usable_train = train.dropna(subset=[baseline_col])
            usable_test = test.dropna(subset=[baseline_col]).copy()
            if usable_test.empty:
                continue
            adjustment = np.zeros(len(test))
            if features:
                model = residual_model(features)
                target = usable_train.legislative_dem_margin - usable_train[baseline_col]
                fit_args = ({"model__sample_weight": realignment_weights(usable_train.cycle)}
                            if name.startswith("federal_") else {})
                model.fit(usable_train[features], target, **fit_args)
                adjustment = model.predict(usable_test[features])
            pred = usable_test[baseline_col].to_numpy() + adjustment
            err = usable_test.legislative_dem_margin.to_numpy() - pred
            for race, p, a, e in zip(usable_test.itertuples(), pred, adjustment, err):
                errors.append({"specification": name, "test_cycle": test_cycle, "chamber": race.chamber,
                               "district": race.district, "baseline": race.prior_pres_dem_margin,
                               "adjustment": a, "prediction": p, "actual": race.legislative_dem_margin, "error": e})
            rows.append({"specification": name, "test_cycle": test_cycle, "races": len(usable_test),
                         "mae": mean_absolute_error(usable_test.legislative_dem_margin, pred),
                         "rmse": mean_squared_error(usable_test.legislative_dem_margin, pred) ** .5})
    detail, errdf = pd.DataFrame(rows), pd.DataFrame(errors)
    summary = (detail.groupby("specification", as_index=False)
               .agg(forward_cycles=("test_cycle", "nunique"), mean_mae=("mae", "mean"),
                    latest_mae=("mae", "last"), mean_rmse=("rmse", "mean")))
    recent = (detail[detail.test_cycle.ge(2018)].groupby("specification").mae.mean()
              .rename("post2016_mean_mae"))
    summary = summary.merge(recent, on="specification", how="left")
    base = summary.set_index("specification").loc["baseline"]
    promoted = {r.specification: bool(r.mean_mae < base.mean_mae and
                                      r.post2016_mean_mae < base.post2016_mean_mae and
                                      r.latest_mae < base.latest_mae)
                for r in summary.itertuples()}
    promoted["baseline"] = True
    summary["promoted"] = summary.specification.map(promoted)
    summary["selection_rule"] = "improve_all_cycle_post2016_and_latest_forward_mae"
    return summary.sort_values("mean_mae"), errdf, promoted


def normalize_name(value: str) -> str:
    return " ".join(re.findall(r"[A-Z0-9]+", str(value).upper()))


def prior_cmo_scenario(roster: pd.DataFrame) -> pd.DataFrame:
    hist = pd.read_csv(WAR / "preliminary_cmo_candidates.csv")
    hist["name_key"] = hist.candidate.map(normalize_name)
    # Cross-fitted score only; two prior races are approximately one effective
    # observation after shrinkage, preventing a single historical race from dominating.
    agg = (hist.groupby(["name_key", "party"], as_index=False)
           .agg(prior_cmo_mean=("candidate_cmo_total_oof", "mean"), prior_cmo_races=("cycle", "nunique")))
    agg["prior_cmo_shrunk"] = agg.prior_cmo_mean * agg.prior_cmo_races / (agg.prior_cmo_races + 2.0)
    r = roster.copy(); r["name_key"] = r.candidate.map(normalize_name)
    r = r.merge(agg, on=["name_key", "party"], how="left")
    r[["prior_cmo_mean", "prior_cmo_shrunk"]] = r[["prior_cmo_mean", "prior_cmo_shrunk"]].fillna(0.0)
    r["prior_cmo_races"] = r.prior_cmo_races.fillna(0).astype(int)
    return r


def direct_error_components(errdf: pd.DataFrame) -> tuple[float, float, float]:
    e = errdf[errdf.specification.eq("baseline")].copy()
    cycle_mean = e.groupby("test_cycle").error.mean()
    national_sd = max(3.0, float(cycle_mean.std(ddof=1)) if len(cycle_mean) > 1 else 3.0)
    centered = e.assign(cycle_mean=e.test_cycle.map(cycle_mean), rem=lambda x: x.error - x.cycle_mean)
    chamber_mean = centered.groupby(["test_cycle", "chamber"]).rem.mean()
    chamber_sd = max(2.0, float(chamber_mean.std(ddof=1)) if len(chamber_mean) > 1 else 2.0)
    residual_var = max(1.0, float(e.error.var(ddof=1)) - national_sd ** 2 - chamber_sd ** 2)
    return national_sd, chamber_sd, residual_var ** .5


def simulate(test: pd.DataFrame, errdf: pd.DataFrame, draws=50000) -> tuple[pd.DataFrame, pd.DataFrame]:
    national_sd, chamber_sd, district_sd = direct_error_components(errdf)
    rng = np.random.default_rng(RNG_SEED)
    national = rng.normal(0, national_sd, draws)
    chamber_noise = {c: rng.normal(0, chamber_sd, draws) for c in ["house", "senate"]}
    margins = np.empty((draws, len(test)))
    for j, race in enumerate(test.itertuples()):
        margins[:, j] = (race.predicted_dem_margin + national + chamber_noise[race.chamber]
                         + rng.normal(0, district_sd, draws))
    test = test.copy()
    test["dem_win_probability"] = (margins > 0).mean(axis=0)
    for coverage, lo, hi in [(80, .10, .90), (95, .025, .975)]:
        test[f"margin_{coverage}_low"] = np.clip(np.quantile(margins, lo, axis=0), -100, 100)
        test[f"margin_{coverage}_high"] = np.clip(np.quantile(margins, hi, axis=0), -100, 100)
    roster = pd.read_csv(WAR / "2026_final_candidate_roster.csv")
    fixed = {}
    for chamber, total in [("house", 105), ("senate", 35)]:
        sub = roster[roster.chamber.eq(chamber)]
        fixed_d = fixed_r = 0
        for district in range(1, total + 1):
            parties = set(sub[sub.district.eq(district)].party) & {"D", "R"}
            fixed_d += parties == {"D"}; fixed_r += parties == {"R"}
        idx = test.index[test.chamber.eq(chamber)].to_numpy()
        seats_d = fixed_d + (margins[:, idx] > 0).sum(axis=1)
        counts = pd.Series(seats_d).value_counts().sort_index()
        fixed[chamber] = pd.DataFrame({"chamber": chamber, "dem_seats": counts.index,
                                       "probability": counts.values / draws,
                                       "national_error_sd": national_sd, "chamber_error_sd": chamber_sd,
                                       "district_error_sd": district_sd})
    return test, pd.concat(fixed.values(), ignore_index=True)


def main() -> None:
    if FORECAST.exists() and not LEGACY.exists():
        shutil.copy2(FORECAST, LEGACY)
    train, test = historical(), prospective_features()
    summary, errors, promoted = backtest_layers(train)
    summary.to_csv(WAR / "2026_residual_layer_backtest_summary.csv", index=False)
    errors.to_csv(WAR / "2026_residual_layer_backtest_predictions.csv", index=False)

    test["structural_2024_pres_margin"] = test.baseline_2024_pres_dem_margin
    test["environment_adjustment"] = test.poll_adjusted_dem_margin - test.baseline_2024_pres_dem_margin
    test["baseline_forecast_margin"] = test.poll_adjusted_dem_margin
    test["incumbency_adjustment"] = 0.0
    test["demographic_residual_adjustment"] = 0.0
    test["cmo_adjustment"] = 0.0
    test["finance_adjustment"] = 0.0

    # Fit every scenario, but only add it to the headline if it passed the gate.
    for name, features in SPECS.items():
        if not features:
            test[f"scenario_{name}_margin"] = test.baseline_forecast_margin
            continue
        baseline_col = specification_baseline(name)
        fit = train.dropna(subset=[baseline_col])
        model = residual_model(features)
        fit_args = ({"model__sample_weight": realignment_weights(fit.cycle)}
                    if name.startswith("federal_") else {})
        model.fit(fit[features], fit.legislative_dem_margin - fit[baseline_col], **fit_args)
        adj = model.predict(test[features])
        test[f"scenario_{name}_adjustment"] = adj
        test[f"scenario_{name}_margin"] = test.baseline_forecast_margin + adj
        if promoted.get(name, False):
            if name == "incumbency": test["incumbency_adjustment"] = adj
            elif "demographic" in name: test["demographic_residual_adjustment"] = adj
            elif "finance" in name: test["finance_adjustment"] = adj

    cmo = prior_cmo_scenario(pd.read_csv(WAR / "2026_final_candidate_roster.csv"))
    cmo.to_csv(WAR / "2026_candidate_prior_cmo_scenario.csv", index=False)
    pivot = cmo.pivot_table(index=["chamber", "district"], columns="party", values="prior_cmo_shrunk", aggfunc="first", fill_value=0).reset_index()
    pivot["cmo_scenario_adjustment"] = pivot.get("D", 0) - pivot.get("R", 0)
    test = test.merge(pivot[["chamber", "district", "cmo_scenario_adjustment"]], on=["chamber", "district"], how="left")
    test["cmo_scenario_adjustment"] = test.cmo_scenario_adjustment.fillna(0.0)
    # No candidate-CMO promotion without a genuine candidate-history forward backtest.
    test["predicted_dem_margin"] = (test.baseline_forecast_margin + test.incumbency_adjustment
                                    + test.demographic_residual_adjustment + test.cmo_adjustment + test.finance_adjustment)
    test["selected_specification"] = "poll_adjusted_direct_baseline"
    if promoted.get("national_environment_post2016_ramp", False):
        test["selected_specification"] = "poll_adjusted_post2016_national_environment_ramp"
        test["selection_reason"] = "national-environment ramp improved all-cycle, post-2016, and latest forward MAE"
    else:
        test["selection_reason"] = "complex layers failed declared forward-MAE promotion gate"
    test["model_status"] = "baseline_first_experimental"
    test, seats = simulate(test.reset_index(drop=True), errors)
    test["predicted_winner"] = np.where(test.predicted_dem_margin.gt(0), "D", "R")
    # This file is an auditable baseline/scenario input to model selection. The
    # tournament publishes the canonical forecast, decomposition, and seats.
    decomposition = test[["chamber", "district", "structural_2024_pres_margin", "environment_adjustment",
                          "baseline_forecast_margin", "incumbency_adjustment", "demographic_residual_adjustment",
                          "cmo_adjustment", "finance_adjustment", "cmo_scenario_adjustment",
                          "scenario_finance_scenario_adjustment", "predicted_dem_margin", "dem_win_probability",
                          "selected_specification", "selection_reason"]]
    test["model_status"] = "preselection_baseline_features"
    test.to_csv(BASE_FEATURES, index=False)
    print(summary.to_string(index=False))
    print("\nSD-2 decomposition")
    print(decomposition[(decomposition.chamber.eq("senate")) & (decomposition.district.eq(2))].to_string(index=False))
    print(f"\nBaseline features: {BASE_FEATURES.name}; scored {len(test)} D-R races")
    print("Run run_forecast_experiment_tournament.py to publish the canonical forecast.")


if __name__ == "__main__":
    main()
