#!/usr/bin/env python3
"""Publish post-2016 Southern WAR as a fitted structural race residual.

Split Ticket defines WAR as the observed legislative-versus-presidential gap
minus the gap predicted from structural factors.  This build preserves the v2
forward tournament for specification selection, fits the selected model within
each election cycle for descriptive scoring, and does not apply a second-stage
candidate-effect regression to WAR.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

import retrain_post2016_southern_war as v1
import retrain_post2016_southern_war_v2 as v2


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/war/post2016_southern_war_v3"
V2_OUT = ROOT / "data/processed/war/post2016_southern_war_v2"
METHOD_REPORT = ROOT / "project_docs/model/POST2016_SOUTHERN_WAR_V3.md"
FIELD_CONTRACT = ROOT / "project_docs/model/POST2016_SOUTHERN_WAR_V3_FIELD_CONTRACT.md"
AUDIT_REPORT = ROOT / "project_docs/audits/POST2016_SOUTHERN_WAR_V3_VALIDATION.md"
SPLIT_TICKET_METHOD_URL = "https://split-ticket.org/2025/08/15/deconstructing-war/"
SPLIT_TICKET_DATABASE_URL = "https://split-ticket.org/full-wins-above-replacement-war-database/"
RACE_KEYS = ["state_code", "cycle", "chamber", "district"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def select_structural_model(
    races: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, str, float, dict[str, object]]:
    designs, lag_columns = v2.design_matrices(races)
    predictions, metrics = v2.structural_forward_tournament(races, designs)
    specification, alpha = v2.select_structural_spec(metrics)
    aggregate = metrics[
        metrics.scope.eq("lag_context_available") & metrics.evaluation_cycle.eq("all")
    ]
    selected = aggregate[
        aggregate.specification.eq(specification) & aggregate.alpha.eq(alpha)
    ].iloc[0]
    no_lag = aggregate[aggregate.specification.eq("fundamentals_no_lag")].sort_values(
        ["mae", "rmse"]
    ).iloc[0]
    selection = {
        "selected_forward_mae": float(selected.mae),
        "best_no_lag_forward_mae": float(no_lag.mae),
        "mae_improvement_vs_no_lag": float(no_lag.mae - selected.mae),
        "lag_added_value_status": (
            "passes_lag_added_value_gate" if selected.mae < no_lag.mae
            else "fails_lag_added_value_gate"
        ),
    }
    selected_lag_columns = [column for column in lag_columns if column in designs[specification]]
    return designs, predictions, metrics, specification, alpha, {
        **selection, "selected_lag_columns": selected_lag_columns,
    }


def fitted_cycle_predictions(
    races: pd.DataFrame,
    design: pd.DataFrame,
    specification: str,
    alpha: float,
    lag_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    target = races.direct_overperformance.to_numpy(float)
    prediction = np.full(len(races), np.nan)
    nonlag_prediction = np.full(len(races), np.nan)
    training_rows = np.zeros(len(races), dtype=int)
    coefficient_rows: list[pd.DataFrame] = []
    for cycle in sorted(int(value) for value in races.cycle.unique()):
        selected = races.cycle.eq(cycle).to_numpy()
        model = v2.ridge_model(alpha).fit(design.loc[selected], target[selected])
        prediction[selected] = model.predict(design.loc[selected])
        counterfactual = design.loc[selected].copy()
        for column in lag_columns:
            counterfactual[column] = 0.0
        nonlag_prediction[selected] = model.predict(counterfactual)
        training_rows[selected] = int(selected.sum())

        coefficients = v2.full_model_coefficients(model, list(design.columns))
        coefficients.insert(0, "cycle", cycle)
        coefficients["coefficient_type"] = "slope"
        scaler = model.named_steps["scale"]
        ridge = model.named_steps["ridge"]
        original_coefficients = ridge.coef_ / scaler.scale_
        intercept = float(ridge.intercept_ - np.dot(scaler.mean_, original_coefficients))
        intercept_row = pd.DataFrame({
            "cycle": [cycle], "feature": ["__intercept__"],
            "coefficient": [intercept], "coefficient_type": ["intercept"],
        })
        coefficient_rows.extend([intercept_row, coefficients])

    if not np.isfinite(prediction).all() or not np.isfinite(nonlag_prediction).all():
        raise ValueError("Cycle-fitted structural scoring left missing predictions")
    fitted = pd.DataFrame({
        "war_outcome_id": races.war_outcome_id,
        "structural_specification": specification,
        "structural_alpha": alpha,
        "structural_fit_scope": "same_cycle_full_sample_descriptive",
        "structural_training_rows": training_rows,
        "fitted_structural_expected_gap": prediction,
        "fitted_structural_nonlag_expected_gap": nonlag_prediction,
        "fitted_lag_component": prediction - nonlag_prediction,
    })
    return fitted, pd.concat(coefficient_rows, ignore_index=True)


def cross_fitted_validation(
    races: pd.DataFrame,
    design: pd.DataFrame,
    specification: str,
    alpha: float,
    lag_columns: list[str],
) -> pd.DataFrame:
    predictions, _ = v2.cross_fitted_structural_predictions(
        races, design, specification, alpha, lag_columns
    )
    return predictions.rename(columns={
        "structural_oof_fold": "validation_fold",
        "structural_oof_training_rows": "validation_training_rows",
        "structural_oof_self_excluded": "validation_self_excluded",
        "structural_expected_gap": "validation_cross_fitted_expected_gap",
        "structural_nonlag_expected_gap": "validation_cross_fitted_nonlag_expected_gap",
        "lag_component": "validation_cross_fitted_lag_component",
    })


def headline_races(
    races: pd.DataFrame, fitted: pd.DataFrame, validation: pd.DataFrame,
) -> pd.DataFrame:
    result = races.merge(fitted, on="war_outcome_id", how="left", validate="one_to_one")
    validation_columns = [column for column in validation.columns if column not in {
        "structural_specification", "structural_alpha",
    }]
    result = result.merge(
        validation[validation_columns], on="war_outcome_id", how="left", validate="one_to_one"
    )
    result["raw_gap"] = result.direct_overperformance
    result["war"] = result.raw_gap - result.fitted_structural_expected_gap
    result["war_party"] = np.select(
        [result.war.gt(1e-12), result.war.lt(-1e-12)], ["D", "R"], default="EVEN"
    )
    result["war_magnitude"] = result.war.abs()
    result["war_definition"] = "actual_raw_gap_minus_same_cycle_fitted_structural_gap"
    result["validation_cross_fitted_residual"] = (
        result.raw_gap - result.validation_cross_fitted_expected_gap
    )
    return result


def candidate_cycle_rows(races: pd.DataFrame) -> pd.DataFrame:
    candidates = v1.candidate_rows(races)
    race_fields = races[[
        "war_outcome_id", "raw_gap", "fitted_structural_expected_gap",
        "fitted_structural_nonlag_expected_gap", "fitted_lag_component",
        "war", "war_party", "war_magnitude", "war_definition",
    ]]
    candidates = candidates.merge(race_fields, on="war_outcome_id", how="left", validate="many_to_one")
    orientation = candidates.canonical_party.map({"D": 1.0, "R": -1.0})
    if orientation.isna().any():
        raise ValueError("Candidate-cycle WAR found a non-major-party orientation")
    candidates["candidate_cycle_war"] = orientation * candidates.war
    candidates["candidate_cycle_result"] = np.select(
        [candidates.candidate_cycle_war.gt(1e-12), candidates.candidate_cycle_war.lt(-1e-12)],
        ["overperformed", "underperformed"], default="even",
    )
    candidates["score_identification"] = "race_differential_party_orientation"
    return candidates


def lag_diagnostics(races: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cycle, group in races.groupby("cycle"):
        available = group.lag_context_available
        raw_available = group.loc[available, "raw_gap"].abs().mean() if available.any() else np.nan
        lag_available = (
            group.loc[available, "fitted_lag_component"].abs().mean() if available.any() else np.nan
        )
        rows.append({
            "cycle": int(cycle),
            "races": len(group),
            "lag_context_races": int(available.sum()),
            "raw_gap_mae": float(group.raw_gap.abs().mean()),
            "fitted_expected_gap_mae": float(group.fitted_structural_expected_gap.abs().mean()),
            "war_mae": float(group.war.abs().mean()),
            "war_bias": float(group.war.mean()),
            "mean_abs_lag_component_all": float(group.fitted_lag_component.abs().mean()),
            "mean_abs_lag_component_available": float(lag_available) if available.any() else np.nan,
            "lag_share_of_raw_mae_available": (
                float(lag_available / raw_available) if available.any() and raw_available else np.nan
            ),
        })
    return pd.DataFrame(rows)


def correction_comparison(races: pd.DataFrame) -> pd.DataFrame:
    old = pd.read_csv(V2_OUT / "races.csv", low_memory=False)
    old = old[[
        "war_outcome_id", "war_target", "candidate_war_differential", "war_unexplained",
    ]].rename(columns={
        "war_target": "v2_cross_fitted_residual_mislabeled_war_target",
        "candidate_war_differential": "v2_pooled_candidate_differential_not_war",
        "war_unexplained": "v2_second_stage_unattributed_residual",
    })
    corrected = races[[
        "war_outcome_id", *RACE_KEYS, "raw_gap", "fitted_structural_expected_gap", "war",
    ]]
    result = corrected.merge(old, on="war_outcome_id", how="left", validate="one_to_one")
    result["correction_status"] = "headline_war_replaced_with_same_cycle_structural_residual"
    return result


def finance_diagnostics(
    races: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], dict[str, object]]:
    evaluation = races.copy()
    evaluation["war_target"] = evaluation.validation_cross_fitted_residual
    predictions, metrics, nested_predictions, nested_metrics, result = v2.finance_tournament(evaluation)
    return {
        "finance_forward_predictions.csv": predictions,
        "finance_forward_metrics.csv": metrics,
        "finance_nested_predictions.csv": nested_predictions,
        "finance_nested_metrics.csv": nested_metrics,
    }, result


def write_reports(
    manifest: dict[str, object], races: pd.DataFrame, lag: pd.DataFrame,
) -> None:
    dexter = races[races.dem_candidate_name.eq("Dexter Grimsley")]
    dexter_text = "not present"
    if len(dexter) == 1:
        row = dexter.iloc[0]
        dexter_text = (
            f"raw gap D+{row.raw_gap:.3f}, fitted structural gap D+"
            f"{row.fitted_structural_expected_gap:.3f}, WAR D+{row.war:.3f}"
        )
    lag_2018 = lag[lag.cycle.eq(2018)].iloc[0]
    lag_2022 = lag[lag.cycle.eq(2022)].iloc[0]
    finance = manifest["configuration"]["finance_sensitivity"]
    METHOD_REPORT.write_text(
        "# Post-2016 Southern WAR v3: race-level structural residual\n\n"
        "## Definition\n\n"
        "Headline WAR is the observed Democratic legislative-minus-ticket margin gap minus the gap "
        "predicted by the fitted structural regression. This implements Split Ticket's published definition "
        "of WAR as the regression residual. The score belongs to the race differential: candidate-cycle "
        "rows merely reverse its sign for the Republican perspective. No second-stage candidate pooling "
        "or ridge penalty modifies WAR.\n\n"
        f"The `{manifest['configuration']['selected_structural_specification']}` specification with alpha "
        f"{manifest['configuration']['selected_structural_alpha']:g} was selected by earlier-cycle forward "
        "validation, then fitted separately within each cycle for descriptive post-election scoring. "
        "Cross-fitted predictions remain validation fields and are not WAR.\n\n"
        f"All {manifest['diagnostics']['training_rows']:,} strict races after 2016 were scored. Dexter "
        f"Grimsley: {dexter_text}.\n\n"
        "## Lag and finance\n\n"
        f"On lag-context races, mean absolute fitted lag is "
        f"{lag_2018.mean_abs_lag_component_available:.3f} points in 2018 and "
        f"{lag_2022.mean_abs_lag_component_available:.3f} in 2022. Missing lag context remains explicit.\n\n"
        "Candidate fundraising remains outside headline WAR. The diagnostic threshold grid runs every "
        "$10,000 through $100,000 plus $250,000, and its nested forward status is "
        f"`{finance['predictive_gate_status']}`. State fundraising is not treated as comparable to Split "
        "Ticket's candidate-plus-outside federal spending measure.\n\n"
        f"Split Ticket methodology: {SPLIT_TICKET_METHOD_URL}\n\n"
        f"Model run: `{manifest['model_run_id']}`.\n",
        encoding="utf-8",
    )
    AUDIT_REPORT.write_text(
        "# Post-2016 Southern WAR v3 validation\n\n"
        f"Research run `{manifest['model_run_id']}` uses warehouse build "
        f"`{manifest['warehouse_build_run_id']}`.\n\n"
        "## Enforced gates\n\n"
        f"- All {manifest['diagnostics']['training_rows']:,} rows are strict-ready and have `cycle > 2016`.\n"
        "- Race keys are unique and candidate-cycle grain is exactly two major-party rows per race.\n"
        "- Headline `war` exactly equals `raw_gap - fitted_structural_expected_gap`.\n"
        "- Democratic and Republican candidate-cycle scores are exact opposites.\n"
        "- No pooled candidate coefficient, second-stage penalty, or residual allocation enters WAR.\n"
        "- Structural specification selection remains time-forward; same-cycle fitted residuals are clearly "
        "labeled descriptive rather than forecasts.\n"
        "- Missing lag and finance evidence remains explicit; finance is excluded from headline WAR.\n"
        "- Inputs, code, outputs, field contract, and reports are SHA-256 registered.\n\n"
        "## Release decision\n\n"
        "This corrects the v2 WAR-definition error but remains a research candidate pending independent "
        "validation of structural specification, context coverage, calibration, and uncertainty.\n",
        encoding="utf-8",
    )


def main() -> None:
    raw, warehouse_run = v2.load_training()
    races = v2.add_finance_features(v2.attach_lag_context(raw))
    designs, forward_predictions, forward_metrics, specification, alpha, selection = (
        select_structural_model(races)
    )
    selected_design = designs[specification]
    lag_columns = list(selection.pop("selected_lag_columns"))
    fitted, coefficients = fitted_cycle_predictions(
        races, selected_design, specification, alpha, lag_columns
    )
    validation = cross_fitted_validation(
        races, selected_design, specification, alpha, lag_columns
    )
    races = headline_races(races, fitted, validation)
    candidates = candidate_cycle_rows(races)
    lag = lag_diagnostics(races)
    comparison = correction_comparison(races)
    finance_outputs, finance_result = finance_diagnostics(races)
    coverage = races.groupby(["state_code", "cycle", "chamber"], as_index=False).agg(
        races=("war_outcome_id", "size"),
        lag_context_rows=("lag_context_available", "sum"),
        finance_complete_rows=("finance_complete", "sum"),
        raw_gap_mae=("raw_gap", lambda values: float(values.abs().mean())),
        war_mae=("war", lambda values: float(values.abs().mean())),
        war_bias=("war", "mean"),
    )

    outputs = {
        "race_war.csv": races,
        "candidate_cycle_war.csv": candidates,
        "structural_forward_predictions.csv": forward_predictions,
        "structural_forward_metrics.csv": forward_metrics,
        "validation_cross_fitted_predictions.csv": validation,
        "structural_coefficients_by_cycle.csv": coefficients,
        "lag_diagnostics_by_cycle.csv": lag,
        "v2_correction_comparison.csv": comparison,
        "coverage.csv": coverage,
        **finance_outputs,
    }
    diagnostics = {
        "training_rows": len(races),
        "candidate_cycle_rows": len(candidates),
        "states": int(races.state_code.nunique()),
        "cycles": sorted(int(value) for value in races.cycle.unique()),
        "lag_context_rows": int(races.lag_context_available.sum()),
        "finance_complete_rows": int(races.finance_complete.sum()),
        "race_key_duplicates": int(races.duplicated(RACE_KEYS).sum()),
        "candidate_cycle_key_duplicates": int(
            candidates.duplicated(["war_outcome_id", "canonical_party"]).sum()
        ),
        "max_war_formula_error": float(np.max(np.abs(
            races.war - (races.raw_gap - races.fitted_structural_expected_gap)
        ))),
        "max_candidate_orientation_error": float(np.max(np.abs(
            candidates.candidate_cycle_war
            - candidates.canonical_party.map({"D": 1.0, "R": -1.0}) * candidates.war
        ))),
    }
    input_paths = [
        v2.DATABASE, v2.PROBABILITY_CONTEXT, v2.ALABAMA_CONTEXT_2018,
        v2.ALABAMA_CONTEXT_2022, V2_OUT / "manifest.json", FIELD_CONTRACT,
    ]
    code_paths = [Path(__file__).resolve(), Path(v2.__file__).resolve(), Path(v1.__file__).resolve()]
    run_basis = {
        "methodology_version": "post2016_southern_war_v3_residual",
        "warehouse_build_run_id": raw.build_run_id.iloc[0],
        "input_hashes": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in input_paths
        },
        "code_hashes": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in code_paths
        },
        "configuration": {
            "cutoff_rule": "cycle > 2016",
            "training_status": v2.TRAINING_STATUS,
            "headline_war_definition": "raw_gap - fitted_structural_expected_gap",
            "headline_fit_scope": "same_cycle_full_sample_descriptive",
            "candidate_pooling_in_headline_war": False,
            "selected_structural_specification": specification,
            "selected_structural_alpha": alpha,
            "structural_selection": selection,
            "finance_headline_included": False,
            "finance_thresholds": list(v2.FINANCE_THRESHOLDS),
            "finance_sensitivity": finance_result,
        },
    }
    model_run_id = "WAR-POST2016-V3-" + hashlib.sha256(
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
            "method_url": SPLIT_TICKET_METHOD_URL,
            "database_url": SPLIT_TICKET_DATABASE_URL,
            "implemented_definition": (
                "actual legislative-versus-ticket gap minus fitted structural gap"
            ),
            "portability_limit": (
                "state model lacks complete comparable demographics and candidate-plus-outside spending"
            ),
        },
        "outputs": [
            {
                "path": str((OUT / name).relative_to(ROOT)).replace("\\", "/"),
                "rows": len(frame), "sha256": sha256(OUT / name),
            }
            for name, frame in outputs.items()
        ],
    }
    write_reports(manifest, races, lag)
    manifest["reports"] = [
        {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(path),
        }
        for path in (METHOD_REPORT, FIELD_CONTRACT, AUDIT_REPORT)
    ]
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"Post-2016 Southern WAR v3: run={model_run_id} races={len(races):,} "
        f"candidate_cycles={len(candidates):,} structural={specification}/a{alpha:g}"
    )


if __name__ == "__main__":
    main()
