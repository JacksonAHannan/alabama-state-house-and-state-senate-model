"""Fit cross-validated Alabama legislative candidate margin overperformance models.

The public statistic is CMO: observed two-party margin overperformance minus a
cross-fitted model expectation.  It is a retrospective index, not wins above a
replacement candidate.  Legacy WAR columns are retained for downstream
compatibility.
"""

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
CMO = ROOT / "data" / "processed" / "war"
ALPHAS = [0.1, 0.3, 1, 3, 10, 30]
RANDOM_STATE = 20260805


def prepare(model: pd.DataFrame) -> pd.DataFrame:
    def as_binary(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce")
        text = series.astype("string").str.strip().str.lower().map(
            {"true": 1, "false": 0, "yes": 1, "no": 0})
        return numeric.fillna(text).fillna(0).astype(int)

    mask = as_binary(model.war_eligible).astype(bool)
    if "model_eligible" in model:
        mask &= as_binary(model.model_eligible).astype(bool)
    eligible = model[mask].copy().reset_index(drop=True)
    eligible["dem_incumbent_i"] = as_binary(eligible.dem_incumbent)
    eligible["rep_incumbent_i"] = as_binary(eligible.rep_incumbent)
    eligible["incumbency_conflict"] = (
        eligible.dem_incumbent_i.eq(1) & eligible.rep_incumbent_i.eq(1)).astype(int)
    eligible.loc[eligible.incumbency_conflict.eq(1),
                 ["dem_incumbent_i", "rep_incumbent_i"]] = 0
    modern_prior = np.select(
        [eligible.cycle.eq(2014), eligible.cycle.eq(2018), eligible.cycle.eq(2022)],
        [eligible.pres_2012_dem_margin, eligible.pres_2016_dem_margin,
         eligible.pres_2020_dem_margin], default=np.nan)
    historical_prior = pd.to_numeric(
        eligible.get("prior_pres_dem_margin", pd.Series(np.nan, index=eligible.index)),
        errors="coerce")
    pres_1992 = pd.to_numeric(
        eligible.get("pres_1992_dem_margin", pd.Series(np.nan, index=eligible.index)),
        errors="coerce")
    eligible["prior_pres_dem_margin"] = pd.Series(modern_prior, index=eligible.index).fillna(historical_prior).fillna(pres_1992)
    eligible["prior_pres_swing"] = np.select(
        [eligible.cycle.eq(2018), eligible.cycle.eq(2022)],
        [eligible.pres_swing_2012_2016, eligible.pres_swing_2016_2020], default=np.nan)
    eligible["finance_complete"] = as_binary(eligible.finance_complete)
    if "ftm_finance_complete" not in eligible:
        eligible["ftm_finance_complete"] = False
    eligible["ftm_finance_complete"] = as_binary(eligible.ftm_finance_complete)
    eligible["pres_trend_available"] = eligible["prior_pres_swing"].notna().astype(int)
    eligible["prior_pres_available"] = eligible["prior_pres_dem_margin"].notna().astype(int)
    demographic_context = pd.DataFrame({
        column: pd.to_numeric(eligible.get(column, pd.Series(np.nan, index=eligible.index)), errors="coerce")
        for column in ("nonwhite_share", "white_college_share")})
    eligible["demographics_available"] = demographic_context.notna().all(axis=1).astype(int)
    default_incumbency_complete = pd.Series(eligible.cycle.ge(2010), index=eligible.index)
    incumbency_complete = eligible.get("incumbency_complete", default_incumbency_complete)
    eligible["incumbency_evidence_complete"] = as_binary(
        incumbency_complete.where(incumbency_complete.notna(), default_incumbency_complete))
    eligible["era"] = np.select(
        [eligible.cycle.le(2006), eligible.cycle.le(2014)],
        ["pre_2008", "obama_era"], default="trump_era")
    return eligible


def estimator(numeric: list[str], categorical: list[str]) -> GridSearchCV:
    prep = ColumnTransformer([
        ("numeric", Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("scale", StandardScaler()),
        ]), numeric),
        ("categorical", OneHotEncoder(drop="first", handle_unknown="ignore"), categorical),
    ])
    pipe = Pipeline([("preprocess", prep), ("model", Ridge())])
    return GridSearchCV(
        pipe, {"model__alpha": ALPHAS}, scoring="neg_mean_absolute_error",
        cv=KFold(5, shuffle=True, random_state=RANDOM_STATE),
    )


def metrics(y: pd.Series, pred: np.ndarray, prefix: str = "") -> dict[str, float]:
    return {
        f"{prefix}mae": mean_absolute_error(y, pred),
        f"{prefix}rmse": mean_squared_error(y, pred) ** 0.5,
        f"{prefix}r2": r2_score(y, pred),
    }


def fit_spec(data: pd.DataFrame, name: str, numeric: list[str]) -> tuple[pd.DataFrame, dict]:
    categorical = ["cycle", "chamber", "era"]
    features = numeric + categorical
    est = estimator(numeric, categorical)
    y = data.raw_overperformance
    random_cv = KFold(10, shuffle=True, random_state=RANDOM_STATE)
    random_pred = cross_val_predict(est, data[features], y, cv=random_cv)
    cycle_pred = cross_val_predict(
        est, data[features], y,
        cv=GroupKFold(data.cycle.nunique()), groups=data.cycle,
    )
    district_group = data.chamber.astype(str) + "-" + data.district.astype(str)
    district_pred = cross_val_predict(
        est, data[features], y,
        cv=GroupKFold(min(10, district_group.nunique())), groups=district_group,
    )
    est.fit(data[features], y)
    final_pred = est.predict(data[features])

    result = data.copy()
    result[f"expected_cmo_{name}_oof"] = random_pred
    result[f"cmo_{name}_oof"] = y - random_pred
    result[f"expected_cmo_{name}_cycle_holdout"] = cycle_pred
    result[f"cmo_{name}_cycle_holdout"] = y - cycle_pred
    result[f"expected_cmo_{name}_district_grouped"] = district_pred
    result[f"cmo_{name}_district_grouped"] = y - district_pred
    result[f"expected_cmo_{name}_final"] = final_pred
    result[f"cmo_{name}_final"] = y - final_pred

    # This is deliberately called a stability band, not a confidence interval.
    # It measures how much the CMO changes when an entire election cycle is
    # unavailable.  The finite-sample conformal order statistic is conservative.
    instability = np.abs((y - random_pred) - (y - cycle_pred))
    rank = min(len(instability) - 1, int(np.ceil((len(instability) + 1) * .95)) - 1)
    radius = float(np.sort(instability)[rank])
    result[f"cmo_{name}_stability_low"] = result[f"cmo_{name}_oof"] - radius
    result[f"cmo_{name}_stability_high"] = result[f"cmo_{name}_oof"] + radius

    diag = {"specification": name, "eligible_races": len(data),
            "selected_alpha": est.best_params_["model__alpha"],
            "stability_band_radius": radius,
            **metrics(y, random_pred, "random_"),
            **metrics(y, cycle_pred, "cycle_holdout_"),
            **metrics(y, district_pred, "district_grouped_")}
    return result, diag


def forward_validation(data: pd.DataFrame, numeric: list[str], name: str) -> list[dict]:
    rows = []
    features = numeric + ["cycle", "chamber", "era"]
    cycles = sorted(data.cycle.unique())
    for position in range(1, len(cycles)):
        train_cycles, test_cycle = cycles[:position], cycles[position]
        train, test = data[data.cycle.isin(train_cycles)], data[data.cycle.eq(test_cycle)]
        # A cycle category unseen in training is safely ignored by the encoder.
        est = estimator(numeric, ["cycle", "chamber", "era"])
        est.fit(train[features], train.raw_overperformance)
        pred = est.predict(test[features])
        rows.append({"specification": name, "train_cycles": "+".join(map(str, train_cycles)),
                     "test_cycle": test_cycle, "train_races": len(train),
                     "test_races": len(test), **metrics(test.raw_overperformance, pred)})
    return rows


def benchmark_diagnostics(data: pd.DataFrame) -> pd.DataFrame:
    y = data.raw_overperformance
    folds = list(KFold(10, shuffle=True, random_state=RANDOM_STATE).split(data))
    rows = []
    for name, cols in [("zero_overperformance", []), ("incumbency_only", ["dem_incumbent_i", "rep_incumbent_i"]),
                       ("prior_presidential_only", ["prior_pres_dem_margin"])]:
        pred = np.empty(len(data))
        for train, test in folds:
            if not cols:
                pred[test] = y.iloc[train].mean()
            else:
                est = estimator(cols, ["cycle", "chamber", "era"])
                est.fit(data.iloc[train][cols + ["cycle", "chamber", "era"]], y.iloc[train])
                pred[test] = est.predict(data.iloc[test][cols + ["cycle", "chamber", "era"]])
        rows.append({"benchmark": name, **metrics(y, pred)})
    return pd.DataFrame(rows)


def candidate_scores(races: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    candidates = candidates.copy()
    candidates["district"] = candidates.district.astype(int)
    keep = [c for c in races.columns if c.startswith("cmo_") or c.startswith("expected_cmo_")]
    keep += ["cycle", "chamber", "district", "raw_overperformance"]
    scores = candidates.merge(races[keep], on=["cycle", "chamber", "district"],
                              how="inner", validate="many_to_one")
    sign = scores.party.map({"D": 1, "R": -1})
    for column in [c for c in keep if c.startswith("cmo_")]:
        low_suffix = "_stability_low"
        if column.endswith(low_suffix):
            continue
        if column.endswith("_stability_high"):
            continue
        scores[f"candidate_{column}"] = scores[column] * sign
    for spec in ["total", "resource_adjusted", "fundraising_adjusted"]:
        low, high = f"cmo_{spec}_stability_low", f"cmo_{spec}_stability_high"
        if low not in scores or high not in scores:
            continue
        scores[f"candidate_{low}"] = np.where(sign.eq(1), scores[low], -scores[high])
        scores[f"candidate_{high}"] = np.where(sign.eq(1), scores[high], -scores[low])
    spec_columns=[c for c in ["candidate_cmo_total_oof", "candidate_cmo_resource_adjusted_oof",
                              "candidate_cmo_fundraising_adjusted_oof"] if c in scores]
    scores["candidate_cmo_specification_range"] = scores[spec_columns].max(axis=1)-scores[spec_columns].min(axis=1)
    scores["candidate_cmo_sign_consistent"] = (
        np.sign(scores.candidate_cmo_total_oof) ==
        np.sign(scores.candidate_cmo_resource_adjusted_oof))
    # Compatibility aliases now point to the headline, cross-fitted total CMO.
    scores["candidate_war_oof"] = scores["candidate_cmo_total_oof"]
    scores["candidate_war_final"] = scores["candidate_cmo_total_final"]
    return scores


def main() -> None:
    canonical_path = ROOT / "data" / "processed" / "elections" / "canonical_cmo_features.csv"
    source = pd.read_csv(canonical_path if canonical_path.exists() else CMO / "war_model_features.csv")
    funnel = (source.groupby(["cycle", "chamber"], as_index=False)
              .agg(districts=("district", "size"),
                   contested_dr_races=("war_eligible", "sum")))
    funnel["excluded_races"] = funnel.districts - funnel.contested_dr_races
    funnel["eligible_share"] = funnel.contested_dr_races / funnel.districts
    funnel.to_csv(CMO / "cmo_eligibility_funnel.csv", index=False)
    model = prepare(source)
    core = ["dem_incumbent_i", "rep_incumbent_i", "incumbency_conflict", "incumbency_evidence_complete",
            "prior_pres_dem_margin", "prior_pres_available", "demographics_available",
            "nonwhite_share", "white_college_share", "prior_pres_swing",
            "pres_trend_available"]
    adjusted = core + ["log_spending_ratio_d_to_r", "finance_complete"]
    fundraising = core + ["log_fundraising_ratio_d_to_r", "ftm_finance_complete"]
    total, total_diag = fit_spec(model, "total", core)
    adjusted_races, adjusted_diag = fit_spec(model, "resource_adjusted", adjusted)
    fundraising_races, fundraising_diag = fit_spec(model, "fundraising_adjusted", fundraising)
    added = [c for c in adjusted_races if c.startswith("cmo_resource_adjusted") or
             c.startswith("expected_cmo_resource_adjusted")]
    races = total.join(adjusted_races[added])
    fundraising_added = [c for c in fundraising_races if c.startswith("cmo_fundraising_adjusted") or
                         c.startswith("expected_cmo_fundraising_adjusted")]
    races = races.join(fundraising_races[fundraising_added])

    # Legacy race aliases retain old consumers while changing the headline to OOF total CMO.
    races["expected_raw_overperformance_oof"] = races.expected_cmo_total_oof
    races["war_residual_oof"] = races.cmo_total_oof
    races["expected_raw_overperformance_loco"] = races.expected_cmo_total_cycle_holdout
    races["war_residual_loco"] = races.cmo_total_cycle_holdout
    races["expected_raw_overperformance_final"] = races.expected_cmo_total_final
    races["war_residual_final"] = races.cmo_total_final

    canonical_candidates = ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv"
    if canonical_candidates.exists():
        candidate_input = pd.read_csv(canonical_candidates).rename(
            columns={"year":"cycle","canonical_name":"candidate","canonical_party":"party",
                     "canonical_votes":"votes"})
        candidate_input["candidate_code"] = candidate_input["canonical_candidate_id"]
    else:
        candidate_input = pd.read_csv(CMO / "race_candidate_results.csv")
    candidates = candidate_scores(races, candidate_input)
    diagnostics = pd.DataFrame([total_diag, adjusted_diag, fundraising_diag])
    forward = (forward_validation(model, core, "total") + forward_validation(model, adjusted, "resource_adjusted") +
               forward_validation(model, fundraising, "fundraising_adjusted"))
    benchmarks = benchmark_diagnostics(model)

    races.to_csv(CMO / "preliminary_cmo_races.csv", index=False)
    candidates.to_csv(CMO / "preliminary_cmo_candidates.csv", index=False)
    diagnostics.to_csv(CMO / "cmo_diagnostics.csv", index=False)
    pd.DataFrame(forward).to_csv(CMO / "cmo_forward_validation.csv", index=False)
    benchmarks.to_csv(CMO / "cmo_benchmark_diagnostics.csv", index=False)
    # Compatibility files.
    races.to_csv(CMO / "preliminary_war_races.csv", index=False)
    candidates.to_csv(CMO / "preliminary_war_candidates.csv", index=False)
    diagnostics.to_csv(CMO / "preliminary_war_diagnostics.csv", index=False)
    print(diagnostics.to_string(index=False))
    print("\nForward validation:\n", pd.DataFrame(forward).to_string(index=False))


if __name__ == "__main__":
    main()
