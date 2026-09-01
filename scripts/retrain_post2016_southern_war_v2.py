#!/usr/bin/env python3
"""Build post-2016 Southern WAR v2 with explicit lag and finance audits.

Headline WAR is fit without finance.  Its structural expectation is selected
in expanding-window validation and estimated out of fold: a race may use
earlier cycles and contemporaneous peer races, but never its own outcome.
Validated prior-presidential context enters only on exact race keys; missing
context remains explicit.  Candidate fundraising is tested separately with a
Split Ticket-inspired viability gate and is never silently treated as total
spending or promoted into headline WAR.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import retrain_post2016_southern_war as v1


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data/processed/elections/alabama_elections.sqlite"
PROBABILITY_CONTEXT = ROOT / "data/processed/forecast_calibration/southern_legislative_probability_panel.csv"
ALABAMA_CONTEXT_2018 = ROOT / "data/processed/presidential/2018_district_presidential_features.csv"
ALABAMA_CONTEXT_2022 = ROOT / "data/processed/presidential/2022_district_presidential_features.csv"
V1_OUT = ROOT / "data/processed/war/post2016_southern_war"
OUT = ROOT / "data/processed/war/post2016_southern_war_v2"
METHOD_REPORT = ROOT / "project_docs/model/POST2016_SOUTHERN_WAR_V2.md"
AUDIT_REPORT = ROOT / "project_docs/audits/POST2016_SOUTHERN_WAR_V2_VALIDATION.md"

CUTOFF_CYCLE = 2016
TRAINING_STATUS = "strict_war_ready_no_finance"
STRUCTURAL_ALPHAS = (1.0, 10.0, 30.0, 100.0)
STRUCTURAL_SPECS = ("fundamentals_no_lag", "constant_lag", "decaying_lag")
FINANCE_THRESHOLDS = tuple(float(value) for value in range(10_000, 100_001, 10_000)) + (250_000.0,)
QUALITY_PENALTIES = v1.QUALITY_PENALTIES
RACE_KEYS = ["state_code", "cycle", "chamber", "district"]
SPLIT_TICKET_METHOD_URL = "https://split-ticket.org/2025/08/15/deconstructing-war/"


def sha256(path: Path) -> str:
    return v1.sha256(path)


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def normalized_district(value: object) -> str:
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def normalized_chamber(value: object) -> str:
    return {"house": "lower", "senate": "upper"}.get(str(value).lower(), str(value).lower())


def load_training() -> tuple[pd.DataFrame, dict[str, object]]:
    query = """
        SELECT war_outcome_id,build_run_id,state_code,cycle,chamber,district,
               election_stage,election_date,district_plan_id,geography_vintage,
               dem_candidate_result_id,rep_candidate_result_id,
               dem_candidate_name,rep_candidate_name,dem_votes,rep_votes,
               two_party_votes,third_party_votes,legislative_dem_margin,
               baseline_dem_margin,baseline_source,baseline_office,baseline_class,
               baseline_quality,baseline_coverage,dem_incumbent,rep_incumbent,
               incumbency_balance,incumbency_source,incumbency_quality,
               direct_overperformance,training_status,selection_status,
               source_provider,source_family,source_file_id,
               democratic_fundraising,republican_fundraising,
               democratic_finance_status,republican_finance_status,
               finance_complete,race_finance_status
        FROM mart_southern_war_training_with_finance
        WHERE cycle > ? AND training_status = ?
        ORDER BY state_code,cycle,chamber,CAST(district AS INTEGER),district
    """
    uri = f"file:{DATABASE.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        frame = pd.read_sql_query(query, connection, params=(CUTOFF_CYCLE, TRAINING_STATUS))
        run_ids = frame.build_run_id.drop_duplicates().tolist()
        if len(run_ids) != 1:
            raise ValueError(f"Expected one warehouse run, found {run_ids}")
        run = pd.read_sql_query(
            "SELECT * FROM warehouse_build_run WHERE build_run_id=?", connection, params=(run_ids[0],)
        )
    if len(run) != 1 or run.iloc[0].status != "validated":
        raise ValueError("Input warehouse run is not validated")
    if frame.empty or not frame.cycle.gt(CUTOFF_CYCLE).all():
        raise ValueError("Post-2016 cutoff failed")
    if not frame.training_status.eq(TRAINING_STATUS).all() or frame.duplicated(RACE_KEYS).any():
        raise ValueError("Training gate or race-key uniqueness failed")
    expected = frame.legislative_dem_margin - frame.baseline_dem_margin
    np.testing.assert_allclose(frame.direct_overperformance, expected, atol=1e-10)
    frame["district"] = frame.district.map(normalized_district)
    frame["baseline_office_family"] = frame.baseline_office.map(v1.office_family)
    return frame, run.iloc[0].to_dict()


def load_probability_context() -> pd.DataFrame:
    columns = [
        "state", "year", "chamber", "district", "prior_pres_margin", "presidential_source",
        "national_swing", "environment_baseline_margin", "primary_calibration_eligible",
    ]
    frame = pd.read_csv(PROBABILITY_CONTEXT, usecols=columns, low_memory=False).rename(
        columns={"state": "state_code", "year": "cycle"}
    )
    frame["chamber"] = frame.chamber.map(normalized_chamber)
    frame["district"] = frame.district.map(normalized_district)
    frame = frame[frame.prior_pres_margin.notna()].copy()
    frame["lag_context_source"] = frame.presidential_source
    frame["lag_context_scope"] = "southern_probability_panel"
    keep = RACE_KEYS + [
        "prior_pres_margin", "national_swing", "environment_baseline_margin",
        "lag_context_source", "lag_context_scope",
    ]
    if frame.duplicated(RACE_KEYS).any():
        raise ValueError("Southern probability context is not unique")
    return frame[keep]


def load_alabama_context() -> pd.DataFrame:
    frames = []
    for path, margin_column, complete_column in (
        (ALABAMA_CONTEXT_2018, "pres_2016_dem_margin", "pres_2016_source_complete"),
        (ALABAMA_CONTEXT_2022, "pres_2020_dem_margin", "pres_2020_source_complete"),
    ):
        frame = pd.read_csv(
            path,
            usecols=["cycle", "chamber", "district", margin_column, complete_column],
            low_memory=False,
        )
        frame = frame[frame[complete_column].eq(True)].copy()
        frame = frame.rename(columns={margin_column: "prior_pres_margin"})
        frames.append(frame)
    frame = pd.concat(frames, ignore_index=True)
    frame["state_code"] = "AL"
    frame["chamber"] = frame.chamber.map(normalized_chamber)
    frame["district"] = frame.district.map(normalized_district)
    frame["national_swing"] = np.nan
    frame["environment_baseline_margin"] = np.nan
    frame["lag_context_source"] = "canonical Alabama prior-presidential district feature"
    frame["lag_context_scope"] = "alabama_canonical"
    keep = RACE_KEYS + [
        "prior_pres_margin", "national_swing", "environment_baseline_margin",
        "lag_context_source", "lag_context_scope",
    ]
    frame = frame[keep].drop_duplicates(RACE_KEYS)
    if frame.duplicated(RACE_KEYS).any():
        raise ValueError("Alabama presidential context is not unique")
    return frame


def attach_lag_context(races: pd.DataFrame) -> pd.DataFrame:
    southern = load_probability_context()
    alabama = load_alabama_context()
    context = pd.concat([southern, alabama], ignore_index=True)
    if context.duplicated(RACE_KEYS).any():
        overlaps = context[context.duplicated(RACE_KEYS, keep=False)][RACE_KEYS]
        raise ValueError(f"Overlapping lag context: {overlaps.head().to_dict('records')}")
    frame = races.merge(context, on=RACE_KEYS, how="left", validate="one_to_one")
    frame["lag_context_available"] = frame.prior_pres_margin.notna()
    frame["lag_current_ticket_change"] = frame.baseline_dem_margin - frame.prior_pres_margin
    frame["years_since_2016"] = frame.cycle - CUTOFF_CYCLE
    frame["lag_change_x_years"] = frame.lag_current_ticket_change * frame.years_since_2016
    frame["current_ticket_is_presidential"] = frame.baseline_office_family.eq("president")
    frame["lag_context_status"] = np.where(
        frame.lag_context_available,
        np.where(frame.current_ticket_is_presidential, "validated_prior_and_current_presidential",
                 "validated_prior_with_nonpresidential_current_ticket"),
        "missing_validated_prior_presidential_context",
    )
    return frame


def add_finance_features(races: pd.DataFrame) -> pd.DataFrame:
    frame = races.copy()
    complete = frame.finance_complete.eq(1)
    if frame.loc[complete, ["democratic_fundraising", "republican_fundraising"]].isna().any().any():
        raise ValueError("Finance-complete rows contain missing amounts")
    frame["finance_direct_log_ratio_50k"] = np.where(
        complete,
        np.log1p(frame.democratic_fundraising / 50_000.0)
        - np.log1p(frame.republican_fundraising / 50_000.0),
        np.nan,
    )
    for threshold in FINANCE_THRESHOLDS:
        label = f"{int(threshold / 1000)}k"
        dem_viable = frame.democratic_fundraising.ge(threshold)
        rep_viable = frame.republican_fundraising.ge(threshold)
        one_sided = complete & dem_viable.ne(rep_viable)
        ratio = (
            np.log1p(frame.democratic_fundraising / threshold)
            - np.log1p(frame.republican_fundraising / threshold)
        )
        frame[f"finance_one_sided_viability_{label}"] = np.where(
            complete, one_sided.astype(int), np.nan
        )
        frame[f"finance_viability_gated_log_ratio_{label}"] = np.where(
            complete, np.where(one_sided, ratio, 0.0), np.nan
        )
    return frame


def design_matrices(races: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], list[str]]:
    base = pd.DataFrame(index=races.index)
    base["incumbency_balance"] = races.incumbency_balance.astype(float)
    base["baseline_dem_margin"] = races.baseline_dem_margin.astype(float)
    base["baseline_margin_squared"] = np.square(races.baseline_dem_margin.astype(float)) / 100.0
    base["years_since_2016"] = races.years_since_2016.astype(float)
    base["odd_year"] = races.cycle.mod(2).astype(float)
    base["presidential_cycle"] = races.cycle.mod(4).eq(0).astype(float)
    categorical = pd.get_dummies(
        races[["state_code", "chamber", "baseline_office_family"]].astype(str),
        drop_first=False, dtype=float,
    )
    base = pd.concat([base, categorical], axis=1)
    lag = pd.DataFrame(index=races.index)
    lag["prior_pres_margin"] = races.prior_pres_margin.fillna(0.0)
    lag["lag_current_ticket_change"] = races.lag_current_ticket_change.fillna(0.0)
    decay = lag.copy()
    decay["lag_change_x_years"] = races.lag_change_x_years.fillna(0.0)
    designs = {
        "fundamentals_no_lag": base,
        "constant_lag": pd.concat([base, lag], axis=1),
        "decaying_lag": pd.concat([base, decay], axis=1),
    }
    return designs, list(decay.columns)


def ridge_model(alpha: float) -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("ridge", Ridge(alpha=alpha)),
    ])


def metric_record(
    actual: np.ndarray, prediction: np.ndarray, specification: str, alpha: float,
    scope: str, evaluation_cycle: str, train_min: int, train_max: int,
) -> dict[str, object]:
    error = actual - prediction
    return {
        "specification": specification,
        "alpha": alpha,
        "scope": scope,
        "evaluation_cycle": evaluation_cycle,
        "races": len(actual),
        "mae": float(np.mean(np.abs(error))),
        "zero_baseline_mae": float(np.mean(np.abs(actual))),
        "rmse": float(np.sqrt(np.mean(np.square(error)))),
        "bias": float(np.mean(error)),
        "train_min_cycle": train_min,
        "train_max_cycle": train_max,
    }


def structural_forward_tournament(
    races: pd.DataFrame, designs: dict[str, pd.DataFrame]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    target = races.direct_overperformance.to_numpy(float)
    prediction_rows = []
    cycles = sorted(races.cycle.unique())
    for specification, design in designs.items():
        for alpha in STRUCTURAL_ALPHAS:
            for test_cycle in cycles[1:]:
                train = races.cycle.lt(test_cycle).to_numpy()
                test = races.cycle.eq(test_cycle).to_numpy()
                model = ridge_model(alpha).fit(design.loc[train], target[train])
                prediction = model.predict(design.loc[test])
                part = races.loc[test, ["war_outcome_id", "cycle", "state_code", "lag_context_available"]].copy()
                part["specification"] = specification
                part["alpha"] = alpha
                part["prediction"] = prediction
                part["actual"] = target[test]
                part["error"] = part.actual - part.prediction
                part["train_min_cycle"] = int(races.loc[train, "cycle"].min())
                part["train_max_cycle"] = int(races.loc[train, "cycle"].max())
                prediction_rows.append(part)
    predictions = pd.concat(prediction_rows, ignore_index=True)
    metrics = []
    for (specification, alpha), group in predictions.groupby(["specification", "alpha"]):
        slices = [("all", group)] + [(str(int(cycle)), part) for cycle, part in group.groupby("cycle")]
        for evaluation_cycle, rows in slices:
            for scope, scoped in (
                ("all", rows),
                ("lag_context_available", rows[rows.lag_context_available]),
            ):
                if scoped.empty:
                    continue
                metrics.append(metric_record(
                    scoped.actual.to_numpy(), scoped.prediction.to_numpy(), specification, alpha,
                    scope, evaluation_cycle, int(scoped.train_min_cycle.min()),
                    int(scoped.train_max_cycle.max()),
                ))
    return predictions, pd.DataFrame(metrics)


def select_structural_spec(metrics: pd.DataFrame) -> tuple[str, float]:
    eligible = metrics[
        metrics.scope.eq("lag_context_available") & metrics.evaluation_cycle.eq("all")
    ].copy()
    if eligible.empty:
        raise ValueError("No lag-complete forward metrics")
    selected = eligible.sort_values(["mae", "rmse", "alpha", "specification"]).iloc[0]
    return str(selected.specification), float(selected.alpha)


def stable_fold(value: str, folds: int = 5) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16) % folds


def cross_fitted_structural_predictions(
    races: pd.DataFrame, design: pd.DataFrame, specification: str, alpha: float,
    lag_columns: list[str],
) -> tuple[pd.DataFrame, Pipeline]:
    target = races.direct_overperformance.to_numpy(float)
    folds = races.war_outcome_id.map(stable_fold).astype(int)
    prediction = np.full(len(races), np.nan)
    no_lag_prediction = np.full(len(races), np.nan)
    training_rows = np.zeros(len(races), dtype=int)
    for cycle in sorted(races.cycle.unique()):
        for fold in sorted(folds[races.cycle.eq(cycle)].unique()):
            test = races.cycle.eq(cycle).to_numpy() & folds.eq(fold).to_numpy()
            train = races.cycle.lt(cycle).to_numpy() | (
                races.cycle.eq(cycle).to_numpy() & folds.ne(fold).to_numpy()
            )
            model = ridge_model(alpha).fit(design.loc[train], target[train])
            prediction[test] = model.predict(design.loc[test])
            counterfactual = design.loc[test].copy()
            for column in lag_columns:
                if column in counterfactual:
                    counterfactual[column] = 0.0
            no_lag_prediction[test] = model.predict(counterfactual)
            training_rows[test] = int(train.sum())
    if not np.isfinite(prediction).all() or not np.isfinite(no_lag_prediction).all():
        raise ValueError("Structural cross-fitting left missing predictions")
    full_model = ridge_model(alpha).fit(design, target)
    output = pd.DataFrame({
        "war_outcome_id": races.war_outcome_id,
        "structural_specification": specification,
        "structural_alpha": alpha,
        "structural_oof_fold": folds,
        "structural_oof_training_rows": training_rows,
        "structural_oof_self_excluded": True,
        "structural_expected_gap": prediction,
        "structural_nonlag_expected_gap": no_lag_prediction,
        "lag_component": prediction - no_lag_prediction,
    })
    return output, full_model


def full_model_coefficients(model: Pipeline, columns: list[str]) -> pd.DataFrame:
    scale = model.named_steps["scale"]
    ridge = model.named_steps["ridge"]
    coefficients = ridge.coef_ / scale.scale_
    return pd.DataFrame({"feature": columns, "coefficient": coefficients})


def lag_diagnostics(races: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cycle, group in races.groupby("cycle"):
        raw = group.direct_overperformance.to_numpy(float)
        residual = group.war_target.to_numpy(float)
        available = group.lag_context_available
        rows.append({
            "cycle": int(cycle),
            "races": len(group),
            "lag_context_races": int(available.sum()),
            "current_presidential_ticket_races": int(group.current_ticket_is_presidential.sum()),
            "raw_gap_mae": float(np.mean(np.abs(raw))),
            "structural_residual_mae": float(np.mean(np.abs(residual))),
            "mean_abs_lag_component_all": float(np.mean(np.abs(group.lag_component))),
            "mean_abs_lag_component_available": (
                float(np.mean(np.abs(group.loc[available, "lag_component"]))) if available.any() else np.nan
            ),
            "lag_share_of_raw_mae_available": (
                float(np.mean(np.abs(group.loc[available, "lag_component"]))
                      / np.mean(np.abs(group.loc[available, "direct_overperformance"])))
                if available.any() else np.nan
            ),
        })
    return pd.DataFrame(rows)


def finance_tournament(
    races: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    feature_specs = {"no_finance": None, "direct_log_ratio_50k": "finance_direct_log_ratio_50k"}
    for threshold in FINANCE_THRESHOLDS:
        label = f"{int(threshold / 1000)}k"
        feature_specs[f"viability_gated_{label}"] = f"finance_viability_gated_log_ratio_{label}"
    complete = races.finance_complete.eq(1)
    prediction_rows = []
    cycles = sorted(races.loc[complete, "cycle"].unique())
    for specification, feature in feature_specs.items():
        for test_cycle in cycles[1:]:
            train = complete & races.cycle.lt(test_cycle)
            test = complete & races.cycle.eq(test_cycle)
            if not train.any() or not test.any():
                continue
            y_train = races.loc[train, "war_target"].to_numpy(float)
            if feature is None:
                prediction = np.repeat(y_train.mean(), int(test.sum()))
                coefficient = 0.0
            else:
                model = Ridge(alpha=10.0).fit(races.loc[train, [feature]], y_train)
                prediction = model.predict(races.loc[test, [feature]])
                coefficient = float(model.coef_[0])
            part = races.loc[test, ["war_outcome_id", "cycle", "state_code"]].copy()
            part["specification"] = specification
            part["feature"] = feature or "none"
            part["prediction"] = prediction
            part["actual"] = races.loc[test, "war_target"].to_numpy(float)
            part["error"] = part.actual - part.prediction
            part["coefficient"] = coefficient
            part["train_min_cycle"] = int(races.loc[train, "cycle"].min())
            part["train_max_cycle"] = int(races.loc[train, "cycle"].max())
            prediction_rows.append(part)
    predictions = pd.concat(prediction_rows, ignore_index=True)
    metrics = []
    for specification, group in predictions.groupby("specification"):
        slices = [("all", group)] + [(str(int(cycle)), part) for cycle, part in group.groupby("cycle")]
        for evaluation_cycle, rows in slices:
            metrics.append(metric_record(
                rows.actual.to_numpy(), rows.prediction.to_numpy(), specification, 10.0,
                "finance_complete", evaluation_cycle, int(rows.train_min_cycle.min()),
                int(rows.train_max_cycle.max()),
            ))
    metrics = pd.DataFrame(metrics)
    aggregate = metrics[metrics.evaluation_cycle.eq("all")].set_index("specification")
    gated = aggregate.loc[[name for name in aggregate.index if name.startswith("viability_gated_")]]
    retrospective_selected = str(gated.sort_values(["mae", "rmse"]).index[0])
    baseline_mae = float(aggregate.loc["no_finance", "mae"])
    retrospective_selected_mae = float(aggregate.loc[retrospective_selected, "mae"])
    latest = str(max(int(value) for value in metrics.evaluation_cycle if value != "all"))
    baseline_latest = float(metrics.loc[
        metrics.specification.eq("no_finance") & metrics.evaluation_cycle.eq(latest), "mae"
    ].iloc[0])
    nested_rows = []
    prediction_cycles = sorted(int(value) for value in predictions.cycle.unique())
    gated_names = [name for name in aggregate.index if name.startswith("viability_gated_")]
    for test_cycle in prediction_cycles:
        prior = predictions[predictions.cycle.lt(test_cycle)]
        if prior.cycle.nunique() < 2:
            continue
        prior_scores = (
            prior[prior.specification.isin(gated_names)].groupby("specification")
            .apply(lambda group: float(np.mean(np.abs(group.error))), include_groups=False)
            .sort_values()
        )
        chosen = str(prior_scores.index[0])
        for role, specification in (("nested_viability", chosen), ("no_finance", "no_finance")):
            part = predictions[
                predictions.cycle.eq(test_cycle) & predictions.specification.eq(specification)
            ].copy()
            part["nested_role"] = role
            part["nested_selected_specification"] = chosen
            nested_rows.append(part)
    nested_predictions = pd.concat(nested_rows, ignore_index=True)
    nested_metrics_rows = []
    for role, group in nested_predictions.groupby("nested_role"):
        slices = [("all", group)] + [(str(int(cycle)), part) for cycle, part in group.groupby("cycle")]
        for evaluation_cycle, rows in slices:
            nested_metrics_rows.append(metric_record(
                rows.actual.to_numpy(), rows.prediction.to_numpy(), role, 10.0,
                "finance_complete_nested", evaluation_cycle, int(rows.train_min_cycle.min()),
                int(rows.train_max_cycle.max()),
            ))
    nested_metrics = pd.DataFrame(nested_metrics_rows)
    nested_aggregate = nested_metrics[nested_metrics.evaluation_cycle.eq("all")].set_index("specification")
    nested_latest = str(max(int(value) for value in nested_metrics.evaluation_cycle if value != "all"))
    nested_selected_mae = float(nested_aggregate.loc["nested_viability", "mae"])
    nested_baseline_mae = float(nested_aggregate.loc["no_finance", "mae"])
    nested_selected_latest = float(nested_metrics.loc[
        nested_metrics.specification.eq("nested_viability")
        & nested_metrics.evaluation_cycle.eq(nested_latest), "mae"
    ].iloc[0])
    nested_baseline_latest = float(nested_metrics.loc[
        nested_metrics.specification.eq("no_finance")
        & nested_metrics.evaluation_cycle.eq(nested_latest), "mae"
    ].iloc[0])
    selected = str(
        nested_predictions.loc[
            nested_predictions.cycle.eq(int(nested_latest))
            & nested_predictions.nested_role.eq("nested_viability"),
            "nested_selected_specification",
        ].iloc[0]
    )
    selected_mae = float(aggregate.loc[selected, "mae"])
    selected_latest = float(metrics.loc[
        metrics.specification.eq(selected) & metrics.evaluation_cycle.eq(latest), "mae"
    ].iloc[0])
    predictive_gate = (
        "passes_nested_forward_gate"
        if nested_selected_mae < nested_baseline_mae and nested_selected_latest < nested_baseline_latest
        else "fails_nested_forward_gate"
    )
    feature = feature_specs[selected]
    fit = Ridge(alpha=10.0).fit(
        races.loc[complete, [feature]], races.loc[complete, "war_target"].to_numpy(float)
    )
    result = {
        "selected_sensitivity": selected,
        "selection_basis": "nested_forward_choice_for_latest_evaluation_cycle",
        "selected_feature": feature,
        "coefficient": float(fit.coef_[0]),
        "intercept": float(fit.intercept_),
        "aggregate_mae": selected_mae,
        "retrospective_best_sensitivity": retrospective_selected,
        "retrospective_best_aggregate_mae": retrospective_selected_mae,
        "no_finance_aggregate_mae": baseline_mae,
        "latest_cycle": int(latest),
        "latest_mae": selected_latest,
        "no_finance_latest_mae": baseline_latest,
        "nested_forward_mae": nested_selected_mae,
        "nested_no_finance_mae": nested_baseline_mae,
        "nested_latest_cycle": int(nested_latest),
        "nested_latest_mae": nested_selected_latest,
        "nested_no_finance_latest_mae": nested_baseline_latest,
        "predictive_gate_status": predictive_gate,
        "promotion_status": "rejected_not_comparable_total_spending_and_endogenous",
    }
    return predictions, metrics, nested_predictions, nested_metrics, result


def candidate_model(races: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict[str, object]]:
    candidates = v1.candidate_rows(races)
    forward_predictions, forward_metrics = v1.forward_predictions(races, candidates)
    selected_penalty = v1.choose_penalty(forward_metrics)
    targets = races.set_index("war_outcome_id").war_target
    effects, fitted, sigma = v1.fit_candidate_effects(candidates, targets, selected_penalty)
    appearances = candidates.groupby("candidate_effect_id").agg(
        appearances=("war_outcome_id", "size"), first_cycle=("cycle", "min"),
        last_cycle=("cycle", "max"), states=("state_code", lambda x: "|".join(sorted(set(x)))),
        parties=("canonical_party", lambda x: "|".join(sorted(set(x)))),
        identity_status=("identity_status", lambda x: "|".join(sorted(set(x)))),
        canonical_name=("candidate_name", "last"),
    ).reset_index()
    effects = effects.merge(appearances, on="candidate_effect_id", how="left", validate="one_to_one")
    effects["candidate_war_low"] = effects.candidate_war - 1.96 * effects.candidate_war_se
    effects["candidate_war_high"] = effects.candidate_war + 1.96 * effects.candidate_war_se
    effects["war_reliability"] = effects.appearances / (effects.appearances + selected_penalty)
    effects["war_status"] = np.select(
        [effects.candidate_war_low.gt(0), effects.candidate_war_high.lt(0)],
        ["positive", "negative"], default="uncertain",
    )
    effects.loc[effects.quality_identification.eq("pair_differential_only"), "war_status"] = "uncertain"
    effects["selected_penalty"] = selected_penalty
    race_fit = fitted.rename("candidate_war_differential").reset_index().rename(columns={"index": "war_outcome_id"})
    race_output = races.merge(race_fit, on="war_outcome_id", how="left", validate="one_to_one")
    race_output["war_unexplained"] = race_output.war_target - race_output.candidate_war_differential
    race_output["selected_quality_penalty"] = selected_penalty
    effect_score_columns = [
        column for column in effects.columns
        if column not in {"canonical_name", "identity_status", "states", "parties"}
    ]
    candidate_scores = candidates.merge(
        race_output[[
            "war_outcome_id", "structural_expected_gap", "lag_component", "war_target",
            "candidate_war_differential", "war_unexplained", "finance_complete",
            "finance_adjustment_sensitivity", "finance_adjusted_target_sensitivity",
        ]], on="war_outcome_id", how="left", validate="many_to_one",
    ).merge(effects[effect_score_columns], on="candidate_effect_id", how="left", validate="many_to_one")
    orientation = candidate_scores.canonical_party.map({"D": 1.0, "R": -1.0})
    candidate_scores["candidate_direct_overperformance"] = orientation * candidate_scores.direct_overperformance
    candidate_scores["candidate_structural_expected_gap"] = orientation * candidate_scores.structural_expected_gap
    candidate_scores["candidate_lag_component"] = orientation * candidate_scores.lag_component
    candidate_scores["candidate_war_target"] = orientation * candidate_scores.war_target
    candidate_scores = candidate_scores.merge(
        v1.pre_election_effects(race_output, candidates, selected_penalty),
        on=["cycle", "candidate_effect_id"], how="left", validate="many_to_one",
    )
    diagnostics = {
        "candidate_rows": len(candidate_scores),
        "candidate_effects": len(effects),
        "repeat_candidates": int(effects.appearances.gt(1).sum()),
        "selected_quality_penalty": selected_penalty,
        "candidate_residual_sigma": sigma,
    }
    return {
        "races.csv": race_output,
        "candidate_cycles.csv": candidate_scores,
        "candidate_effects.csv": effects,
        "candidate_forward_predictions.csv": forward_predictions,
        "candidate_forward_metrics.csv": forward_metrics,
    }, diagnostics


def v1_comparison(effects: pd.DataFrame) -> pd.DataFrame:
    old = pd.read_csv(V1_OUT / "candidate_effects.csv", low_memory=False)
    old = old[["candidate_effect_id", "canonical_name", "candidate_war", "candidate_war_se"]].rename(columns={
        "canonical_name": "v1_canonical_name", "candidate_war": "v1_candidate_war",
        "candidate_war_se": "v1_candidate_war_se",
    })
    new = effects[["candidate_effect_id", "canonical_name", "candidate_war", "candidate_war_se"]]
    joined = new.merge(old, on="candidate_effect_id", how="outer", indicator=True)
    joined["war_change_v2_minus_v1"] = joined.candidate_war - joined.v1_candidate_war
    return joined


def write_reports(
    manifest: dict[str, object], structural_metrics: pd.DataFrame, lag: pd.DataFrame,
    finance_result: dict[str, object], comparison: pd.DataFrame,
) -> None:
    spec = manifest["configuration"]["selected_structural_specification"]
    alpha = manifest["configuration"]["selected_structural_alpha"]
    structural = structural_metrics[
        structural_metrics.specification.eq(spec) & structural_metrics.alpha.eq(alpha)
        & structural_metrics.scope.eq("lag_context_available")
        & structural_metrics.evaluation_cycle.eq("all")
    ].iloc[0]
    lag_2018 = lag[lag.cycle.eq(2018)].iloc[0]
    lag_2022 = lag[lag.cycle.eq(2022)].iloc[0]
    dexter = comparison[comparison.canonical_name.str.contains("DEXTER GRIMSLEY", case=False, na=False)]
    dexter_text = "not matched"
    if not dexter.empty:
        row = dexter.iloc[0]
        dexter_text = f"v1 {row.v1_candidate_war:.3f}; v2 {row.candidate_war:.3f}"
    METHOD_REPORT.write_text(
        "# Post-2016 Southern WAR v2: explicit lag and finance sensitivity\n\n"
        "## Headline structural model\n\n"
        f"The selected specification is `{spec}` with ridge alpha {alpha:g}. It predicts the observed "
        "legislative-minus-ticket margin gap from incumbency, ticket partisanship, era, state, chamber, "
        "and ticket-office context. Validated prior-presidential margin and ticket change enter only where "
        "an exact race-key context exists; missing lag context stays labeled. The lag specification is "
        "selected in expanding-window tests, while the historical structural expectation used for WAR is "
        "cross-fitted within cycle so each race is excluded from its own prediction.\n\n"
        f"Lag context is available for {manifest['diagnostics']['lag_context_rows']:,} of "
        f"{manifest['diagnostics']['training_rows']:,} races. On forward lag-complete rows, selected-model "
        f"MAE is {structural.mae:.3f} points. Mean absolute modeled lag is "
        f"{lag_2018.mean_abs_lag_component_available:.3f} points in 2018 and "
        f"{lag_2022.mean_abs_lag_component_available:.3f} in 2022; these are model contributions, not raw "
        "group means.\n\n"
        "## Fundraising sensitivity\n\n"
        "Split Ticket's 2024 federal model treats spending mainly as a campaign-viability indicator: when "
        "both parties are above or both below $1.5 million, its spending feature is zero; otherwise it uses "
        "the spending ratio. Their published discussion says the median WAR adjustment is below 0.25 margin "
        "points and explicitly notes that finance could reasonably be excluded. See "
        f"{SPLIT_TICKET_METHOD_URL}.\n\n"
        "This repository has candidate fundraising, not comparable candidate-plus-outside spending, so the "
        "federal dollar threshold is not ported. We test a diagnostic grid at every $10k from $10k through "
        "$100k, plus $250k as an upper sensitivity, on the same finance-complete forward rows. The $10k "
        "lower bound is a stress-test gate, not a substantive claim that $10k makes a campaign viable. The "
        f"retrospective grid minimum is `{finance_result['retrospective_best_sensitivity']}` with MAE "
        f"{finance_result['retrospective_best_aggregate_mae']:.3f}; it is not promoted. Nested forward selection "
        f"chooses `{finance_result['selected_sensitivity']}` for the latest-cycle sensitivity: fixed-threshold MAE "
        f"{finance_result['aggregate_mae']:.3f} versus {finance_result['no_finance_aggregate_mae']:.3f} "
        f"without finance; latest-cycle MAE {finance_result['latest_mae']:.3f} versus "
        f"{finance_result['no_finance_latest_mae']:.3f}. Nested threshold selection yields MAE "
        f"{finance_result['nested_forward_mae']:.3f} versus "
        f"{finance_result['nested_no_finance_mae']:.3f}, with predictive status "
        f"`{finance_result['predictive_gate_status']}`. Promotion status is "
        f"`{finance_result['promotion_status']}`. Finance remains outside headline "
        "WAR because receipts are endogenous to candidate strength and source coverage is incomplete.\n\n"
        "## Interpretation\n\n"
        "WAR remains a partial-pooled candidate effect in two-party margin points after the selected "
        "cross-fitted structural expectation. Candidate-pair-only effects remain uncertain. The v1 model "
        "is preserved; v2 does not overwrite it. Dexter Grimsley comparison: " + dexter_text + ".\n\n"
        f"Model run: `{manifest['model_run_id']}`.\n",
        encoding="utf-8",
    )
    AUDIT_REPORT.write_text(
        "# Post-2016 Southern WAR v2 validation\n\n"
        f"Model run `{manifest['model_run_id']}` uses validated warehouse run "
        f"`{manifest['warehouse_build_run_id']}`.\n\n"
        "## Enforced gates\n\n"
        f"- All {manifest['diagnostics']['training_rows']:,} races are strict-ready and have `cycle > 2016`.\n"
        "- Race keys and prior-presidential joins are one-to-one.\n"
        "- Structural predictions exclude their own race and never use later cycles.\n"
        "- Missing lag context is explicit and contributes zero through unavailable lag features.\n"
        f"- Finance is complete for {manifest['diagnostics']['finance_complete_rows']:,} races; incomplete "
        "rows retain null amounts/adjustments in model interfaces.\n"
        "- Finance specifications are compared on identical complete-row forward folds.\n"
        "- Candidate D/R orientations, ridge differentials, and uncertainty labels reconcile.\n"
        "- Inputs, code, outputs, and reports are SHA-256 registered.\n\n"
        "## Release decision\n\n"
        "This is a research candidate pending independent validation. Finance is a sensitivity only and is "
        f"labeled `{finance_result['promotion_status']}` by its predictive gate; it is not part of headline WAR.\n",
        encoding="utf-8",
    )


def main() -> None:
    raw, warehouse_run = load_training()
    races = add_finance_features(attach_lag_context(raw))
    designs, all_lag_columns = design_matrices(races)
    structural_predictions, structural_metrics = structural_forward_tournament(races, designs)
    structural_spec, structural_alpha = select_structural_spec(structural_metrics)
    aggregate_structural = structural_metrics[
        structural_metrics.scope.eq("lag_context_available")
        & structural_metrics.evaluation_cycle.eq("all")
    ]
    selected_structural_row = aggregate_structural[
        aggregate_structural.specification.eq(structural_spec)
        & aggregate_structural.alpha.eq(structural_alpha)
    ].iloc[0]
    best_no_lag_row = aggregate_structural[
        aggregate_structural.specification.eq("fundamentals_no_lag")
    ].sort_values(["mae", "rmse"]).iloc[0]
    structural_selection = {
        "selected_forward_mae": float(selected_structural_row.mae),
        "best_no_lag_forward_mae": float(best_no_lag_row.mae),
        "mae_improvement_vs_no_lag": float(best_no_lag_row.mae - selected_structural_row.mae),
        "lag_added_value_status": (
            "passes_lag_added_value_gate"
            if selected_structural_row.mae < best_no_lag_row.mae
            else "fails_lag_added_value_gate"
        ),
    }
    selected_design = designs[structural_spec]
    selected_lag_columns = [column for column in all_lag_columns if column in selected_design]
    structural_oof, full_structural = cross_fitted_structural_predictions(
        races, selected_design, structural_spec, structural_alpha, selected_lag_columns
    )
    races = races.merge(structural_oof, on="war_outcome_id", how="left", validate="one_to_one")
    races["war_target"] = races.direct_overperformance - races.structural_expected_gap
    lag = lag_diagnostics(races)
    coefficients = full_model_coefficients(full_structural, list(selected_design.columns))

    (finance_predictions, finance_metrics, finance_nested_predictions,
     finance_nested_metrics, finance_result) = finance_tournament(races)
    complete = races.finance_complete.eq(1)
    feature = finance_result["selected_feature"]
    races["finance_adjustment_sensitivity"] = np.where(
        complete,
        finance_result["coefficient"] * races[feature],
        np.nan,
    )
    races["finance_adjusted_target_sensitivity"] = np.where(
        complete, races.war_target - races.finance_adjustment_sensitivity, np.nan
    )

    candidate_outputs, candidate_diagnostics = candidate_model(races)
    comparison = v1_comparison(candidate_outputs["candidate_effects.csv"])
    coverage = races.groupby(["state_code", "cycle", "chamber"], as_index=False).agg(
        races=("war_outcome_id", "size"), lag_context_rows=("lag_context_available", "sum"),
        finance_complete_rows=("finance_complete", "sum"),
        mean_abs_lag_component=("lag_component", lambda x: float(np.mean(np.abs(x)))),
        structural_residual_mae=("war_target", lambda x: float(np.mean(np.abs(x)))),
    )
    outputs = {
        **candidate_outputs,
        "structural_forward_predictions.csv": structural_predictions,
        "structural_forward_metrics.csv": structural_metrics,
        "structural_coefficients.csv": coefficients,
        "lag_diagnostics_by_cycle.csv": lag,
        "finance_forward_predictions.csv": finance_predictions,
        "finance_forward_metrics.csv": finance_metrics,
        "finance_nested_predictions.csv": finance_nested_predictions,
        "finance_nested_metrics.csv": finance_nested_metrics,
        "v1_candidate_comparison.csv": comparison,
        "coverage.csv": coverage,
    }
    diagnostics = {
        "training_rows": len(races),
        "states": int(races.state_code.nunique()),
        "cycles": sorted(int(value) for value in races.cycle.unique()),
        "lag_context_rows": int(races.lag_context_available.sum()),
        "lag_context_states": int(races.loc[races.lag_context_available, "state_code"].nunique()),
        "finance_complete_rows": int(complete.sum()),
        **candidate_diagnostics,
    }
    code_inputs = [Path(__file__).resolve(), Path(v1.__file__).resolve()]
    input_paths = [
        DATABASE, PROBABILITY_CONTEXT, ALABAMA_CONTEXT_2018, ALABAMA_CONTEXT_2022,
        V1_OUT / "manifest.json",
    ]
    run_basis = {
        "methodology_version": "post2016_southern_war_v2",
        "warehouse_build_run_id": raw.build_run_id.iloc[0],
        "input_hashes": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in input_paths},
        "code_hashes": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in code_inputs},
        "configuration": {
            "cutoff_rule": "cycle > 2016",
            "training_status": TRAINING_STATUS,
            "structural_specs": list(STRUCTURAL_SPECS),
            "structural_alphas": list(STRUCTURAL_ALPHAS),
            "selected_structural_specification": structural_spec,
            "selected_structural_alpha": structural_alpha,
            "structural_selection": structural_selection,
            "finance_thresholds": list(FINANCE_THRESHOLDS),
            "finance_threshold_grid_role": (
                "diagnostic sensitivity grid; the $10k lower bound is not an approved viability standard"
            ),
            "finance_headline_included": False,
            "finance_sensitivity": finance_result,
            "candidate_penalties": list(QUALITY_PENALTIES),
        },
    }
    model_run_id = "WAR-POST2016-V2-" + hashlib.sha256(
        json.dumps(run_basis, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20].upper()
    for frame in outputs.values():
        frame.insert(0, "model_run_id", model_run_id)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)
    manifest = {
        "schema_version": 1,
        "model_run_id": model_run_id,
        "status": "research_candidate_pending_independent_validation",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": git_commit(),
        **run_basis,
        "warehouse_code_commit": warehouse_run["code_commit"],
        "diagnostics": diagnostics,
        "split_ticket_methodology": {
            "url": SPLIT_TICKET_METHOD_URL,
            "published_2024_rule": "zero when both parties are above or below $1.5m spending; otherwise spending ratio",
            "portability_decision": "do not port federal threshold; test state fundraising thresholds as sensitivity only",
        },
        "outputs": [
            {"path": str((OUT / name).relative_to(ROOT)).replace("\\", "/"),
             "rows": len(frame), "sha256": sha256(OUT / name)}
            for name, frame in outputs.items()
        ],
    }
    write_reports(manifest, structural_metrics, lag, finance_result, comparison)
    manifest["reports"] = [
        {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
        for path in (METHOD_REPORT, AUDIT_REPORT)
    ]
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"Post-2016 Southern WAR v2: run={model_run_id} structural={structural_spec}/a{structural_alpha:g} "
        f"races={len(races):,} lag={diagnostics['lag_context_rows']:,} finance={diagnostics['finance_complete_rows']:,}"
    )


if __name__ == "__main__":
    main()
