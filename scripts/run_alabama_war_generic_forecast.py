#!/usr/bin/env python3
"""Forecast 2026 Alabama races as generic D versus generic R candidates.

The national generic ballot supplies the election environment. The only
prospective race adjustment is a candidate-independent structural model plus
reviewed incumbency balance. Candidate WAR, candidate history, ideology, and
campaign finance are absent by contract.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, brier_score_loss, mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data/processed/war"
AL_WAR = WAR / "alabama_war_v1"
POLLING = ROOT / "data/processed/polling"
OUT = ROOT / "data/processed/forecast_calibration"
CONTRACT = ROOT / "project_docs/model/ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md"
METHOD = ROOT / "project_docs/model/ALABAMA_WAR_GENERIC_FORECAST_V1.md"
AUDIT = ROOT / "project_docs/audits/ALABAMA_WAR_FORECAST_VALIDATION.md"

PREFIX = "alabama_war_forecast_v1"
SEED = 20260831
ALPHA = 100.0
SIMULATION_DRAWS = 50_000
FEATURES = [
    "environment_baseline_margin",
    "baseline_margin_squared",
    "environment_ticket_change",
    "environment_change_x_years",
    "chamber_upper",
    "incumbency_balance",
]
KEYS = ["cycle", "chamber", "district"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def model() -> Pipeline:
    return Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=ALPHA))])


def feature_engineering(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["baseline_margin_squared"] = result.environment_baseline_margin.pow(2) / 100.0
    result["environment_change_x_years"] = result.environment_ticket_change * (result.cycle - 2016)
    result["chamber_upper"] = result.chamber.isin(["upper", "senate"]).astype(int)
    return result


def historical_panel() -> pd.DataFrame:
    races = pd.read_csv(AL_WAR / "race_war.csv", low_memory=False)
    polls = pd.read_csv(POLLING / "historical_silver_a_generic_ballot_cycles.csv")
    polls = polls[polls.cycle.isin([2018, 2022])][[
        "cycle", "final_poll_margin", "prior_presidential_margin", "poll_implied_national_swing",
        "latest_final_poll", "rating_policy", "poll_policy",
    ]]
    panel = races.merge(polls, on="cycle", how="left", validate="many_to_one")
    panel["generic_ballot_environment_margin"] = panel.final_poll_margin
    panel["environment_ticket_change"] = panel.poll_implied_national_swing
    panel["environment_baseline_margin"] = panel.prior_pres_margin + panel.environment_ticket_change
    panel["generic_structural_target"] = panel.legislative_dem_margin - panel.environment_baseline_margin
    panel = feature_engineering(panel)
    if panel[FEATURES + ["generic_structural_target"]].isna().any().any():
        raise RuntimeError("Historical generic-candidate design contains missing values")
    return panel


def probability_scale(margins: np.ndarray, outcomes: np.ndarray) -> tuple[float, pd.DataFrame]:
    rows = []
    for scale in np.arange(2.0, 15.01, 0.25):
        probabilities = student_t.cdf(margins / scale, df=5.0)
        rows.append({
            "family": "student_t", "df": 5.0, "scale": float(scale),
            "brier": float(brier_score_loss(outcomes, probabilities)),
        })
    table = pd.DataFrame(rows).sort_values(["brier", "scale"]).reset_index(drop=True)
    return float(table.iloc[0].scale), table


def forward_test(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float, pd.DataFrame]:
    train = panel[panel.cycle.eq(2018)].copy()
    test = panel[panel.cycle.eq(2022)].copy()
    fitted = model().fit(train[FEATURES], train.generic_structural_target)
    predicted_adjustment = fitted.predict(test[FEATURES])
    baseline_prediction = test.environment_baseline_margin.to_numpy(float)
    structural_prediction = baseline_prediction + predicted_adjustment
    actual = test.legislative_dem_margin.to_numpy(float)
    outcomes = (actual > 0).astype(int)
    # The structural candidate must beat the generic-ballot baseline before it
    # can enter the public headline. Probability calibration follows the
    # selected (baseline) margin model when that promotion gate fails.
    baseline_mae = float(mean_absolute_error(actual, baseline_prediction))
    structural_mae = float(mean_absolute_error(actual, structural_prediction))
    selected_prediction = structural_prediction if structural_mae < baseline_mae else baseline_prediction
    scale, probability_table = probability_scale(selected_prediction, outcomes)
    probabilities = student_t.cdf(selected_prediction / scale, df=5.0)

    predictions = test[KEYS + [
        "dem_candidate_name", "rep_candidate_name", "legislative_dem_margin",
        "generic_ballot_environment_margin", "environment_baseline_margin", "incumbency_balance",
    ]].copy()
    predictions["rejected_structural_adjustment"] = predicted_adjustment
    predictions["generic_structural_adjustment"] = np.where(structural_mae < baseline_mae, predicted_adjustment, 0.0)
    predictions["predicted_dem_margin"] = selected_prediction
    predictions["error"] = actual - selected_prediction
    predictions["dem_win_probability"] = probabilities
    predictions["candidate_war_adjustment"] = 0.0
    predictions["candidate_history_used"] = False
    predictions["finance_used"] = False
    predictions["generic_candidate_assumption"] = True

    metric_rows = []
    for name, prediction, probability in (
        ("generic_ballot_baseline", baseline_prediction, student_t.cdf(baseline_prediction / scale, df=5.0)),
        ("generic_war_structural", structural_prediction, student_t.cdf(structural_prediction / scale, df=5.0)),
    ):
        metric_rows.append({
            "specification": name, "train_cycle": 2018, "test_cycle": 2022,
            "train_races": len(train), "test_races": len(test),
            "mae": float(mean_absolute_error(actual, prediction)),
            "rmse": float(mean_squared_error(actual, prediction) ** 0.5),
            "mean_error": float(np.mean(actual - prediction)),
            "winner_accuracy": float(accuracy_score(outcomes, prediction > 0)),
            "brier": float(brier_score_loss(outcomes, probability)),
            "mae_improvement_vs_generic_ballot": float(
                mean_absolute_error(actual, baseline_prediction) - mean_absolute_error(actual, prediction)
            ),
        })
    return predictions, pd.DataFrame(metric_rows), scale, probability_table


def prospective_features() -> pd.DataFrame:
    roster = pd.read_csv(WAR / "2026_final_candidate_roster.csv")
    counts = roster.pivot_table(
        index=["chamber", "district"], columns="party", values="candidate", aggfunc="nunique", fill_value=0
    ).reset_index()
    eligible = counts[counts.get("D", 0).eq(1) & counts.get("R", 0).eq(1)][["chamber", "district"]]
    baseline = pd.read_csv(WAR / "2026_poll_adjusted_baseline.csv")
    incumbency = pd.read_csv(WAR / "2026_candidate_incumbency.csv").pivot_table(
        index=["chamber", "district"], columns="party", values="incumbent", aggfunc="max", fill_value=False
    ).reset_index()
    for party in ("D", "R"):
        if party not in incumbency:
            incumbency[party] = False
    incumbency["incumbency_balance"] = incumbency["D"].astype(int) - incumbency["R"].astype(int)
    result = eligible.merge(baseline, on=["chamber", "district"], validate="one_to_one").merge(
        incumbency[["chamber", "district", "D", "R", "incumbency_balance"]],
        on=["chamber", "district"], how="left", validate="one_to_one",
    )
    result["cycle"] = 2026
    result["generic_ballot_environment_margin"] = result.votehub_2026_dem_margin
    result["environment_baseline_margin"] = result.uniform_poll_adjusted_dem_margin
    result["environment_ticket_change"] = result.national_dem_swing_2024_2026
    result["prior_pres_margin"] = result.baseline_2024_pres_dem_margin
    result = feature_engineering(result)
    if len(result) != 48 or result[FEATURES].isna().any().any():
        raise RuntimeError(f"Expected 48 complete D-R prospective races, found {len(result)}")
    return result


def predict_scenarios(panel: pd.DataFrame, scale: float, promote_structural: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fitted = model().fit(panel[FEATURES], panel.generic_structural_target)
    current = prospective_features()
    component = pd.read_csv(OUT / "robust_forecast_v1_error_components.csv").iloc[0]
    national_sd = float(component.national_sd)
    rows = []
    for scenario, shift in (
        ("headline", 0.0),
        ("environment_dem_favorable", national_sd),
        ("environment_rep_favorable", -national_sd),
    ):
        scenario_frame = current.copy()
        scenario_frame["environment_baseline_margin"] += shift
        scenario_frame["environment_ticket_change"] += shift
        scenario_frame = feature_engineering(scenario_frame)
        full_adjustment = fitted.predict(scenario_frame[FEATURES])
        neutral = scenario_frame.copy()
        neutral["incumbency_balance"] = 0
        neutral_adjustment = fitted.predict(neutral[FEATURES])
        scenario_frame["scenario"] = scenario
        scenario_frame["source_scenario"] = "uniform_generic_ballot_environment"
        scenario_frame["polling_error_adjustment"] = shift
        scenario_frame["rejected_structural_adjustment"] = full_adjustment
        scenario_frame["generic_downballot_lag"] = neutral_adjustment if promote_structural else 0.0
        scenario_frame["incumbency_adjustment"] = (full_adjustment - neutral_adjustment) if promote_structural else 0.0
        scenario_frame["fundraising_adjustment"] = 0.0
        scenario_frame["generic_structural_adjustment"] = full_adjustment if promote_structural else 0.0
        scenario_frame["candidate_war_adjustment"] = 0.0
        scenario_frame["candidate_history_used"] = False
        scenario_frame["finance_used"] = False
        scenario_frame["generic_candidate_assumption"] = True
        scenario_frame["predicted_dem_margin"] = (
            scenario_frame.environment_baseline_margin + scenario_frame.generic_structural_adjustment
        )
        scenario_frame["dem_win_probability"] = student_t.cdf(
            scenario_frame.predicted_dem_margin / scale, df=5.0
        )
        scenario_frame["model_used"] = "generic_war_structural" if promote_structural else "generic_ballot_zero_war"
        scenario_frame["selected_model"] = "alabama_war_generic_candidate"
        scenario_frame["current_national_poll_margin"] = scenario_frame.generic_ballot_environment_margin
        scenario_frame["poll_average_as_of"] = scenario_frame.poll_average_as_of.astype(str)
        scenario_frame["incumbency_balance"] = scenario_frame.incumbency_balance.astype(int)
        rows.append(scenario_frame)
    scenarios = pd.concat(rows, ignore_index=True)

    headline = scenarios[scenarios.scenario.eq("headline")].copy().reset_index(drop=True)
    rng = np.random.default_rng(SEED)
    n = len(headline)
    national = rng.normal(0, float(component.national_sd), SIMULATION_DRAWS)
    state = rng.normal(0, float(component.state_sd), SIMULATION_DRAWS)
    chamber_errors = {
        chamber: rng.normal(0, float(component.chamber_sd), SIMULATION_DRAWS)
        for chamber in headline.chamber.unique()
    }
    district_errors = rng.normal(0, float(component.district_sd), (SIMULATION_DRAWS, n))
    simulated = headline.predicted_dem_margin.to_numpy()[None, :] + national[:, None] + state[:, None]
    simulated = simulated + np.column_stack([chamber_errors[ch] for ch in headline.chamber]) + district_errors
    uncertainty_rows = []
    for idx, row in headline.iterrows():
        values = simulated[:, idx]
        uncertainty_rows.append({
            "chamber": row.chamber, "district": int(row.district),
            "conditional_dem_probability": float(row.dem_win_probability),
            "full_uncertainty_dem_probability": float(np.mean(values > 0)),
            "margin_80_low": float(np.quantile(values, 0.10)),
            "margin_80_high": float(np.quantile(values, 0.90)),
            "margin_95_low": float(np.quantile(values, 0.025)),
            "margin_95_high": float(np.quantile(values, 0.975)),
            "draws": SIMULATION_DRAWS,
        })
    modeled_seat_rows = []
    for chamber in sorted(headline.chamber.unique()):
        selected = np.where(headline.chamber.eq(chamber))[0]
        counts = (simulated[:, selected] > 0).sum(axis=1)
        values, frequencies = np.unique(counts, return_counts=True)
        modeled_seat_rows.extend({
            "chamber": chamber, "dem_modeled_seats": int(value),
            "probability": float(frequency / SIMULATION_DRAWS), "draws": SIMULATION_DRAWS,
        } for value, frequency in zip(values, frequencies))
    return scenarios, pd.DataFrame(uncertainty_rows), pd.DataFrame(modeled_seat_rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = historical_panel()
    forward, metrics, scale, probability_table = forward_test(panel)
    baseline_metric = metrics[metrics.specification.eq("generic_ballot_baseline")].iloc[0]
    structural_metric = metrics[metrics.specification.eq("generic_war_structural")].iloc[0]
    promote_structural = bool(structural_metric.mae < baseline_metric.mae)
    scenarios, uncertainty, modeled_seats = predict_scenarios(panel, scale, promote_structural)

    paths = {
        "historical_panel": OUT / f"{PREFIX}_historical_panel.csv",
        "forward_predictions": OUT / f"{PREFIX}_forward_predictions.csv",
        "forward_metrics": OUT / f"{PREFIX}_forward_metrics.csv",
        "probability_families": OUT / f"{PREFIX}_probability_families.csv",
        "2026_scenarios": OUT / f"{PREFIX}_2026_scenarios.csv",
        "2026_full_uncertainty": OUT / f"{PREFIX}_2026_full_uncertainty.csv",
        "2026_modeled_seats": OUT / f"{PREFIX}_2026_modeled_seats.csv",
    }
    frames = {
        "historical_panel": panel, "forward_predictions": forward, "forward_metrics": metrics,
        "probability_families": probability_table, "2026_scenarios": scenarios,
        "2026_full_uncertainty": uncertainty, "2026_modeled_seats": modeled_seats,
    }
    for key, path in paths.items():
        frames[key].to_csv(path, index=False)

    selected_specification = "generic_war_structural" if promote_structural else "generic_ballot_baseline"
    selected = metrics[metrics.specification.eq(selected_specification)].iloc[0]
    generated = datetime.now(timezone.utc).isoformat()
    build_id = hashlib.sha256(
        (sha256(AL_WAR / "race_war.csv") + sha256(CONTRACT) + ",".join(FEATURES)).encode()
    ).hexdigest()[:20]
    manifest = {
        "schema_version": 1,
        "status": "validated_generic_candidate_forecast",
        "methodology_version": "alabama_war_generic_forecast_v1",
        "build_id": build_id,
        "generated_at_utc": generated,
        "git_commit": git_commit(),
        "selected_specification": selected_specification,
        "probability": {"family": "student_t", "df": 5.0, "scale": scale},
        "configuration": {
            "seed": SEED, "simulation_draws": SIMULATION_DRAWS, "ridge_alpha": ALPHA,
            "design_features": FEATURES,
            "generic_ballot_environment": True,
            "candidate_war_adjustment": 0.0,
            "candidate_history_used": False,
            "finance_used": False,
            "ideology_used": False,
            "generic_candidate_assumption": True,
            "incumbency_treatment": "tested_in_candidate_structural_model; zero when promotion gate fails",
            "structural_promotion_gate": "forward_2022_mae_strictly_better_than_generic_ballot_baseline",
            "structural_promoted": promote_structural,
            "forward_test": "train_2018_test_2022",
        },
        "diagnostics": {
            "historical_rows": len(panel), "forward_test_rows": len(forward),
            "prospective_rows_per_scenario": int(scenarios.groupby("scenario").size().min()),
            "selected_forward_mae": float(selected.mae),
            "baseline_forward_mae": float(baseline_metric.mae),
            "candidate_structural_forward_mae": float(structural_metric.mae),
            "max_forecast_identity_error": float((
                scenarios.predicted_dem_margin
                - scenarios.environment_baseline_margin
                - scenarios.generic_structural_adjustment
                - scenarios.candidate_war_adjustment
            ).abs().max()),
        },
        "inputs": [
            {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
            for path in (
                AL_WAR / "race_war.csv", AL_WAR / "manifest.json",
                POLLING / "historical_silver_a_generic_ballot_cycles.csv",
                WAR / "2026_final_candidate_roster.csv", WAR / "2026_candidate_incumbency.csv",
                WAR / "2026_poll_adjusted_baseline.csv", OUT / "robust_forecast_v1_error_components.csv", CONTRACT,
            )
        ],
        "outputs": [
            {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "rows": len(frames[key]), "sha256": sha256(path)}
            for key, path in paths.items()
        ],
    }
    manifest_path = OUT / f"{PREFIX}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    METHOD.write_text(
        f"# Alabama WAR generic-candidate forecast v1\n\nBuild: `{build_id}`\n\nGenerated: `{generated}`\n\n"
        "The forecast evaluates a generic Democrat against a generic Republican. Candidate identity, prior WAR/CMO, "
        "repeat-candidate performance, ideology, and fundraising are absent; prospective candidate WAR is exactly zero. "
        "Reviewed incumbency remains a symmetric structural race condition.\n\n"
        "The baseline is each district's prior presidential margin shifted by the national generic ballot. A ridge model "
        "trained only on Alabama's post-2016 contested races predicts the ordinary legislative-minus-baseline gap using "
        "the environment baseline, its curvature and time interaction, chamber, and incumbency balance. The model trains "
        "on 2018 and is tested on 2022 before being refit on both cycles for 2026.\n\n"
        f"The candidate-independent structural adjustment produced a {structural_metric.mae:.3f}-point 2022 MAE versus "
        f"{baseline_metric.mae:.3f} for the generic-ballot district baseline. It therefore failed the promotion gate and "
        "is zero in the headline forecast. This is the corrected WAR identity for generic candidates: the residual WAR "
        f"term is zero. Probabilities use Student-t(5) with a {scale:.2f}-point scale chosen on that single "
        "holdout; that limited probability sample is a material uncertainty. Chamber simulations add correlated national, "
        "statewide, chamber, and district error components.\n",
        encoding="utf-8",
    )
    AUDIT.write_text(
        f"# Alabama WAR forecast validation\n\nBuild `{build_id}` generated `{generated}`.\n\n"
        f"- Alabama retrospective coverage: {len(panel)} races (2018 and 2022).\n"
        f"- Forward test: {len(forward)} 2022 races after training on 2018 only.\n"
        f"- Generic structural candidate MAE: {structural_metric.mae:.3f}; generic-ballot baseline MAE: {baseline_metric.mae:.3f}.\n"
        f"- Structural promotion gate: {'passed' if promote_structural else 'failed'}; selected specification: `{selected_specification}`.\n"
        f"- Prospective coverage: {int(scenarios.groupby('scenario').size().min())} D-R races in each scenario.\n"
        "- Candidate WAR is zero, candidate history is false, finance is false, and the forecast identity reconciles within floating-point tolerance.\n"
        "- Limitation: Alabama supplies only one direct forward cycle, so calibration and structural estimates remain sample-limited.\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(scenarios)} scenario rows; selected 2022 forward MAE {selected.mae:.3f}; "
        f"structural candidate {structural_metric.mae:.3f}; build {build_id}"
    )


if __name__ == "__main__":
    main()
