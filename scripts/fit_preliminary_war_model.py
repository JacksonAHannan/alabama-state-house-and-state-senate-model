"""Fit cross-validated Alabama legislative candidate-strength models.

The public statistic is CMO: observed two-party margin overperformance minus a
cross-fitted model expectation.  It is a retrospective index, not wins above a
replacement candidate.  The headline expectation excludes candidate-derived
variables (including incumbency, ideology, and prior performance), leaving
their electoral contribution in CMO for downstream explanation. Legacy WAR
columns are retained for downstream compatibility.
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


def add_longitudinal_candidate_features(
        races: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    """Attach strictly lagged candidate-history features to race rows.

    Prior overperformance is expressed in the candidate's own partisan
    direction (positive is good for either party) and is observed only for a
    prior contested D/R race.  Unopposed margins are represented separately;
    treating them as candidate quality would mechanically create enormous
    scores.  All joins use a prior appearance, never the current result.
    """
    out = races.copy()
    cand = candidates.copy().rename(columns={
        "year": "cycle", "canonical_party": "party",
        "canonical_votes": "votes",
    })
    required = {"cycle", "chamber", "district", "party", "person_id"}
    if not required.issubset(cand.columns):
        return out

    race_history = races[["cycle", "chamber", "district", "raw_overperformance",
                          "contest_status"]].copy()
    cand = cand.merge(race_history, on=["cycle", "chamber", "district"], how="left",
                      validate="many_to_one")
    cand = cand[cand.party.isin(["D", "R"]) & cand.person_id.notna()].copy()
    cand["person_id"] = cand.person_id.astype(str).str.strip()
    cand = cand[cand.person_id.ne("")].copy()
    cand["votes"] = pd.to_numeric(cand.get("votes"), errors="coerce").fillna(-1)
    cand = (cand.sort_values(["person_id", "cycle", "votes"])
            .drop_duplicates(["person_id", "cycle"], keep="last"))
    grouped = cand.groupby("person_id", sort=False)
    for column in ["cycle", "raw_overperformance", "contest_status", "incumbent", "winner"]:
        values = cand[column] if column in cand else pd.Series(np.nan, index=cand.index)
        cand[f"prior_{column}"] = values.groupby(cand.person_id, sort=False).shift(1)

    cand["candidate_history_available"] = cand.prior_cycle.notna().astype(int)
    cand["prior_cycle_gap"] = (cand.cycle - cand.prior_cycle).clip(lower=0, upper=12)
    cand["prior_recent"] = cand.prior_cycle.eq(cand.cycle - 4).astype(int)
    prior_contested = cand.prior_contest_status.eq("contested_two_party")
    own_party_sign = cand.party.map({"D": 1.0, "R": -1.0})
    cand["prior_candidate_overperformance"] = (
        pd.to_numeric(cand.prior_raw_overperformance, errors="coerce") * own_party_sign
    ).where(prior_contested).clip(-50, 50)
    cand["prior_contested"] = prior_contested.astype(int)
    cand["prior_unopposed"] = cand.prior_contest_status.astype("string").str.startswith(
        "unopposed_", na=False).astype(int)
    cand["prior_winner"] = pd.to_numeric(cand.prior_winner, errors="coerce").fillna(0).astype(int)

    incumbent = pd.to_numeric(cand.get("incumbent"), errors="coerce").fillna(0).astype(int).eq(1)
    prior_incumbent = pd.to_numeric(cand.prior_incumbent, errors="coerce").fillna(0).astype(int).eq(1)
    exact_prior_winner = cand.prior_recent.eq(1) & cand.prior_winner.eq(1)
    cand["first_term_incumbent"] = (incumbent & exact_prior_winner & ~prior_incumbent).astype(int)
    cand["established_incumbent"] = (incumbent & cand.prior_recent.eq(1) & prior_incumbent).astype(int)
    cand["unclassified_incumbent"] = (
        incumbent & cand.first_term_incumbent.eq(0) & cand.established_incumbent.eq(0)
    ).astype(int)
    cand["prior_incumbent_appearances"] = (
        pd.to_numeric(cand.get("incumbent"), errors="coerce").fillna(0)
        .groupby(cand.person_id, sort=False).cumsum()
        - pd.to_numeric(cand.get("incumbent"), errors="coerce").fillna(0)
    ).clip(0, 4)

    feature_names = [
        "candidate_history_available", "prior_cycle_gap", "prior_recent",
        "prior_candidate_overperformance", "prior_contested", "prior_unopposed",
        "prior_winner", "first_term_incumbent", "established_incumbent",
        "unclassified_incumbent", "prior_incumbent_appearances",
    ]
    history = cand[["cycle", "chamber", "district", "party", *feature_names]].copy()
    history = history.drop_duplicates(["cycle", "chamber", "district", "party"], keep="last")
    wide = history.pivot(index=["cycle", "chamber", "district"], columns="party",
                         values=feature_names)
    wide.columns = [f"{('dem' if party == 'D' else 'rep')}_{feature}"
                    for feature, party in wide.columns]
    return out.merge(wide.reset_index(), on=["cycle", "chamber", "district"], how="left",
                     validate="one_to_one")


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
    pres_2008 = pd.to_numeric(
        eligible.get("pres_2008_dem_margin", pd.Series(np.nan, index=eligible.index)),
        errors="coerce")
    modern_prior = np.select(
        [eligible.cycle.eq(2010), eligible.cycle.eq(2014), eligible.cycle.eq(2018), eligible.cycle.eq(2022)],
        [pres_2008, eligible.pres_2012_dem_margin, eligible.pres_2016_dem_margin,
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
    binary_history = [
        "candidate_history_available", "prior_recent", "prior_contested",
        "prior_unopposed", "prior_winner", "first_term_incumbent",
        "established_incumbent", "unclassified_incumbent",
    ]
    for party in ("dem", "rep"):
        for feature in binary_history:
            column = f"{party}_{feature}"
            eligible[column] = as_binary(
                eligible.get(column, pd.Series(0, index=eligible.index)))
        for feature in ("prior_cycle_gap", "prior_candidate_overperformance",
                        "prior_incumbent_appearances"):
            column = f"{party}_{feature}"
            eligible[column] = pd.to_numeric(
                eligible.get(column, pd.Series(np.nan, index=eligible.index)), errors="coerce")
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
    canonical_candidates = ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv"
    if canonical_candidates.exists():
        candidate_source = pd.read_csv(canonical_candidates)
        source = add_longitudinal_candidate_features(source, candidate_source)
    else:
        candidate_source = None
    funnel = (source.groupby(["cycle", "chamber"], as_index=False)
              .agg(districts=("district", "size"),
                   contested_dr_races=("war_eligible", "sum")))
    funnel["excluded_races"] = funnel.districts - funnel.contested_dr_races
    funnel["eligible_share"] = funnel.contested_dr_races / funnel.districts
    funnel.to_csv(CMO / "cmo_eligibility_funnel.csv", index=False)
    model = prepare(source)
    context = ["incumbency_conflict", "incumbency_evidence_complete", "prior_pres_dem_margin",
               "prior_pres_available", "demographics_available", "nonwhite_share",
               "white_college_share", "prior_pres_swing", "pres_trend_available"]
    predictive_core = ["dem_incumbent_i", "rep_incumbent_i", *context]
    # CMO is a candidate-strength estimand. Incumbency and prior candidate
    # performance are downstream of candidate quality, so the headline score
    # must not condition them away. They remain available in explicitly named
    # forecast/sensitivity specifications below.
    core = context
    candidate_history_forecast = predictive_core + [
        f"{party}_{feature}"
        for party in ("dem", "rep")
        for feature in ("candidate_history_available", "prior_candidate_overperformance",
                        "prior_unopposed", "first_term_incumbent", "established_incumbent")
    ]
    adjusted = core + ["log_spending_ratio_d_to_r", "finance_complete"]
    fundraising = core + ["log_fundraising_ratio_d_to_r", "ftm_finance_complete"]
    predictive, predictive_diag = fit_spec(model, "predictive_total", predictive_core)
    history_forecast, history_forecast_diag = fit_spec(
        model, "candidate_history_forecast", candidate_history_forecast)
    total, total_diag = fit_spec(model, "total", core)
    adjusted_races, adjusted_diag = fit_spec(model, "resource_adjusted", adjusted)
    fundraising_races, fundraising_diag = fit_spec(model, "fundraising_adjusted", fundraising)
    added = [c for c in adjusted_races if c.startswith("cmo_resource_adjusted") or
             c.startswith("expected_cmo_resource_adjusted")]
    predictive_added = [c for c in predictive if c.startswith("cmo_predictive_total") or
                        c.startswith("expected_cmo_predictive_total")]
    history_added = [c for c in history_forecast
                     if c.startswith("cmo_candidate_history_forecast") or
                     c.startswith("expected_cmo_candidate_history_forecast")]
    races = total.join(predictive[predictive_added]).join(
        history_forecast[history_added]).join(adjusted_races[added])
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

    if candidate_source is not None:
        candidate_input = candidate_source.rename(
            columns={"year":"cycle","canonical_name":"candidate","canonical_party":"party",
                     "canonical_votes":"votes"})
        candidate_input["candidate_code"] = candidate_input["canonical_candidate_id"]
    else:
        candidate_input = pd.read_csv(CMO / "race_candidate_results.csv")
    candidates = candidate_scores(races, candidate_input)
    diagnostics = pd.DataFrame([total_diag, predictive_diag, history_forecast_diag,
                                adjusted_diag, fundraising_diag])
    forward = (forward_validation(model, core, "total") +
               forward_validation(model, predictive_core, "predictive_total") +
               forward_validation(model, candidate_history_forecast, "candidate_history_forecast") +
               forward_validation(model, adjusted, "resource_adjusted") +
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
