#!/usr/bin/env python3
"""Build the current Alabama historical CMO decomposition from a Southern prior.

Direct CMO remains observed legislative margin minus the selected same-cycle
ticket.  A portable structural model is fitted on non-Alabama Southern races;
its incumbent-neutral and incumbent-inclusive expectations are then applied to
Alabama.  The remaining race differential is partial-pooled across candidates.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

import rebuild_cmo_candidate_quality_v5 as v5
from run_historical_southern_cmo_tournament import MODEL_SPECS, add_features, fit_estimator


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data/processed/war"
SOUTHERN_PANEL = ROOT / "data/processed/forecast_calibration/historical_southern_extended_v2_panel.csv"
SOUTHERN_MANIFEST = ROOT / "data/processed/war/extended_v2_historical_southern/historical_southern_cmo_manifest.json"
KEYS = ["cycle", "chamber", "district"]
PENALTIES = v5.QUALITY_LAMBDAS


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def alabama_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    races = pd.read_csv(WAR / "cmo_v5_races.csv", low_memory=False)
    candidates = pd.read_csv(WAR / "cmo_v5_candidates.csv", low_memory=False)
    incumbency = (candidates.groupby(KEYS, as_index=False)
                  .agg(dem_incumbent_i=("dem_incumbent_i", "max"),
                       rep_incumbent_i=("rep_incumbent_i", "max"),
                       headline_fit_eligible=("headline_fit_eligible", "max")))
    races = races.merge(incumbency, on=KEYS, how="left", validate="one_to_one")
    races["incumbency_balance"] = races.dem_incumbent_i - races.rep_incumbent_i
    races["year"] = races.cycle
    races["state"] = "AL"
    races["baseline_dem_margin"] = races.selected_ticket_margin
    return races, candidates


def southern_prior_predictions(races: pd.DataFrame) -> pd.DataFrame:
    panel = add_features(pd.read_csv(SOUTHERN_PANEL, low_memory=False))
    train = panel.loc[panel.model_eligible.eq(True) & panel.state.ne("AL")].copy()
    spec = MODEL_SPECS["portable_temporal"]
    model, columns = fit_estimator(train, spec)

    target = add_features(races.rename(columns={"cycle": "_cycle"}).rename(columns={"year": "year"}))
    # Federal baselines can combine House and Senate votes in the Alabama mart.
    # Average the two source-office predictions and retain their spread rather
    # than pretending one office was observed.
    scenarios = []
    for office in ("USP", "USS"):
        frame = target.copy()
        frame["office"] = np.where(frame.selected_ticket_source.eq("same_cycle_federal"), office, "GOV")
        scenarios.append(model.predict(frame[columns]))
    prediction_matrix = np.vstack(scenarios)
    inclusive = prediction_matrix.mean(axis=0)

    neutral = target.copy()
    neutral["incumbency_balance"] = 0.0
    neutral["inc_year_interaction"] = 0.0
    neutral_scenarios = []
    for office in ("USP", "USS"):
        frame = neutral.copy()
        frame["office"] = np.where(frame.selected_ticket_source.eq("same_cycle_federal"), office, "GOV")
        neutral_scenarios.append(model.predict(frame[columns]))
    neutral_matrix = np.vstack(neutral_scenarios)

    out = races.copy()
    out["southern_expected_gap"] = inclusive
    out["southern_expected_gap_low"] = prediction_matrix.min(axis=0)
    out["southern_expected_gap_high"] = prediction_matrix.max(axis=0)
    out["southern_incumbent_neutral_gap"] = neutral_matrix.mean(axis=0)
    out["generic_incumbency_gap"] = out.southern_expected_gap - out.southern_incumbent_neutral_gap
    out["southern_candidate_quality_residual"] = out.direct_cmo - out.southern_expected_gap
    out["southern_prior_training_rows"] = len(train)
    out["southern_prior_training_states"] = train.state.nunique()
    return out


def choose_penalty(candidate_rows: pd.DataFrame, residual: pd.Series) -> tuple[float, pd.DataFrame]:
    table = v5.forward_quality_tournament(candidate_rows, residual)
    seen = table.loc[table.specification.eq("seen_candidate")].sort_values(["mae", "parameter"])
    eligible = seen.loc[seen.mae.lt(seen.zero_baseline_mae)]
    selected = float((eligible if not eligible.empty else seen).iloc[0].parameter)
    table["selected"] = table.parameter.eq(selected) & table.specification.eq("seen_candidate")
    return selected, table


def candidate_outputs(races: pd.DataFrame, candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    keep = KEYS + ["southern_expected_gap", "southern_incumbent_neutral_gap",
                   "generic_incumbency_gap", "southern_candidate_quality_residual"]
    rows = candidates.merge(races[keep], on=KEYS, how="inner", validate="many_to_one")
    rows = rows.loc[rows.canonical_party.isin(["D", "R"])].copy()
    counts = rows.groupby(KEYS).canonical_party.nunique()
    valid = counts[counts.eq(2)].index
    rows = rows.set_index(KEYS).loc[valid].reset_index()
    race_index = races.set_index(KEYS).southern_candidate_quality_residual
    selected, tournament = choose_penalty(rows, race_index)
    race_design, parties, ids, lookup, x, y = v5.quality_design(rows, race_index)
    effect, se, unexplained = v5.fit_quality(x, y, selected)
    appearances = rows.groupby("candidate_effect_id").size()
    effects = pd.DataFrame({
        "candidate_effect_id": ids,
        "southern_candidate_quality_index": effect,
        "southern_candidate_quality_se": se,
        "southern_quality_appearances": [int(appearances.get(value, 0)) for value in ids],
    })
    effects["southern_candidate_quality_low"] = (
        effects.southern_candidate_quality_index - 1.96 * effects.southern_candidate_quality_se)
    effects["southern_candidate_quality_high"] = (
        effects.southern_candidate_quality_index + 1.96 * effects.southern_candidate_quality_se)
    effects["southern_quality_status"] = np.select(
        [effects.southern_candidate_quality_low.gt(0), effects.southern_candidate_quality_high.lt(0)],
        ["positive", "negative"], default="uncertain")
    effects["selected_quality_penalty"] = selected

    rows = rows.merge(effects, on="candidate_effect_id", how="left", validate="many_to_one")
    orientation = rows.canonical_party.map({"D": 1.0, "R": -1.0})
    rows["candidate_direct_cmo"] = orientation * rows.direct_cmo
    rows["candidate_southern_expected_gap"] = orientation * rows.southern_expected_gap
    rows["candidate_quality_residual"] = orientation * rows.southern_candidate_quality_residual
    rows["candidate_generic_incumbency_component"] = orientation * rows.generic_incumbency_gap / 2
    rows["candidate_total_electoral_value"] = (
        rows.southern_candidate_quality_index + rows.candidate_generic_incumbency_component)
    race_quality = pd.Series(x @ effect, index=pd.MultiIndex.from_frame(race_design), name="pooled_quality_differential")
    race_unexplained = pd.Series(unexplained, index=pd.MultiIndex.from_frame(race_design), name="quality_unexplained")
    races = races.set_index(KEYS).join(race_quality).join(race_unexplained).reset_index()
    return races, rows, pd.concat([tournament, effects.assign(specification="fitted_effect")], ignore_index=True, sort=False)


def validation_table(races: pd.DataFrame) -> pd.DataFrame:
    eligible = races.headline_fit_eligible.fillna(False) & races.direct_cmo.notna()
    rows = []
    for cycle, group in races.loc[eligible].groupby("cycle"):
        for model, prediction in {
            "ticket_baseline_only": np.zeros(len(group)),
            "southern_incumbent_neutral": group.southern_incumbent_neutral_gap,
            "southern_portable_temporal": group.southern_expected_gap,
        }.items():
            error = group.direct_cmo.to_numpy() - np.asarray(prediction)
            rows.append({"cycle": cycle, "model": model, "races": len(group),
                         "mae": np.mean(np.abs(error)), "rmse": np.sqrt(np.mean(error ** 2)),
                         "bias": np.mean(error)})
    return pd.DataFrame(rows)


def main() -> None:
    races, candidates = alabama_inputs()
    races = southern_prior_predictions(races)
    races, candidates, quality = candidate_outputs(races, candidates)
    validation = validation_table(races)
    cases = candidates.loc[
        candidates.normalized_candidate_name.eq("MIKE CURTIS")
        | candidates.canonical_name.str.contains("BARBARA.*BOYD|BOYD.*BARBARA", case=False, na=False)
    ]

    outputs = {
        "cmo_v6_southern_races.csv": races,
        "cmo_v6_southern_candidates.csv": candidates,
        "cmo_v6_southern_quality.csv": quality,
        "cmo_v6_southern_validation.csv": validation,
        "cmo_v6_southern_case_studies.csv": cases,
    }
    for name, frame in outputs.items():
        frame.to_csv(WAR / name, index=False)
    code_inputs = [
        Path(__file__).resolve(),
        ROOT / "scripts/rebuild_cmo_candidate_quality_v5.py",
        ROOT / "scripts/run_historical_southern_cmo_tournament.py",
    ]
    manifest = {
        "schema_version": 2,
        "status": "validated_historical_decomposition",
        "methodology_version": "cmo_v6_southern_prior",
        "source_commit": git_commit(),
        "selected_structural_model": "portable_temporal",
        "southern_training_excludes_alabama": True,
        "direct_cmo_definition": "candidate-oriented legislative margin minus selected same-cycle ticket margin",
        "direct_cmo_invariant_to_v5": True,
        "forecast_promotion_status": "rejected_modern_era_gate",
        "public_scope": "historical decomposition; not a direct 2026 forecast adjustment",
        "inputs": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
                   for path in (SOUTHERN_PANEL, SOUTHERN_MANIFEST, WAR / "cmo_v5_races.csv",
                                WAR / "cmo_v5_candidates.csv")],
        "code_inputs": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
                        for path in code_inputs],
        "outputs": [{"path": f"data/processed/war/{name}", "rows": len(frame),
                     "sha256": sha256(WAR / name)} for name, frame in outputs.items()],
    }
    manifest["build_id"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:20]
    (WAR / "cmo_v6_southern_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"CMO v6 Southern prior: races={len(races)}, candidates={len(candidates)}, build={manifest['build_id']}")
    print(validation.groupby("model").mae.mean().sort_values().to_string())


if __name__ == "__main__":
    main()
