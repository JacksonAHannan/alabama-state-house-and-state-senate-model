#!/usr/bin/env python3
"""Read-only missing-context sensitivity and uncertainty audit for Southern WAR v3.

The v3 field contract states that zero-filled lag design entries are
compatibility encodings, not observed zero values, and requires their
sensitivity to be reviewed before release.  This audit binds itself to one
exact run through a parity gate: the training frame is rebuilt from the
read-only warehouse exactly as v3 does, the selected structural specification
is refitted within each cycle, and every published fitted value must reproduce
within tolerance before any alternative is computed.

Every alternative here is a descriptive same-cycle refit used to measure how
much headline WAR depends on the zero-fill encoding.  None is a replacement WAR
definition, a forward validation, or an external reference check.  The audit
never writes to the warehouse or to the model run directory and does not
approve release.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import retrain_post2016_southern_war as v1
import retrain_post2016_southern_war_v2 as v2
import retrain_post2016_southern_war_v3 as v3


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = v3.OUT
DEFAULT_OUTPUT_DIR = ROOT / "data/processed/war/post2016_southern_war_v3_context_sensitivity"
DEFAULT_REPORT = ROOT / "project_docs/audits/SOUTHERN_V3_CONTEXT_SENSITIVITY.md"
RACE_KEYS = v3.RACE_KEYS
PARITY_TOLERANCE = 1e-8
PARITY_COLUMNS = ("fitted_structural_expected_gap", "fitted_structural_nonlag_expected_gap", "war")
EVEN_TOLERANCE = 1e-12
MIN_FIT_ROWS = 2
NO_LAG_SPECIFICATION = "fundamentals_no_lag"
ALTERNATIVES = ("no_lag_spec", "lag_available_fit", "missing_excluded_fit")
DEFAULT_DRAWS = 400
DEFAULT_SEED = 20260908
PUBLISHED_COLUMNS = [
    "model_run_id", "raw_gap", "war", "war_party", "war_magnitude", "war_definition",
    "structural_specification", "structural_alpha", "structural_fit_scope",
    "structural_training_rows", "fitted_structural_expected_gap",
    "fitted_structural_nonlag_expected_gap", "fitted_lag_component",
    "validation_cross_fitted_expected_gap", "validation_cross_fitted_residual",
]
INPUT_PARITY_COLUMNS = ("direct_overperformance", "baseline_dem_margin", "incumbency_balance")
OUTPUT_FILES = (
    "context_sensitivity_by_race.csv",
    "context_sensitivity_summary.csv",
    "bootstrap_uncertainty_by_race.csv",
    "bootstrap_summary.csv",
    "cross_fit_comparison.csv",
    "summary.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def war_party_labels(values: np.ndarray) -> np.ndarray:
    """Apply the v3 D/R/EVEN rule; non-finite inputs receive None."""
    values = np.asarray(values, dtype=float)
    labels = np.select(
        [values > EVEN_TOLERANCE, values < -EVEN_TOLERANCE], ["D", "R"], default="EVEN"
    ).astype(object)
    labels[~np.isfinite(values)] = None
    return labels


# --------------------------------------------------------------------------- loading


def load_run(root: Path) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    """Return manifest, published race table and the v3 training frame, aligned by race.

    The warehouse is opened read-only through ``v2.load_training``.  The run is
    rejected when the warehouse build run or the race universe differs from the
    manifest, or when the published input columns no longer match the warehouse.
    """
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    published = pd.read_csv(root / "race_war.csv", low_memory=False)
    raw, _ = v2.load_training()
    training = v2.add_finance_features(v2.attach_lag_context(raw))

    warehouse_runs = sorted(training.build_run_id.astype(str).unique())
    if warehouse_runs != [str(manifest["warehouse_build_run_id"])]:
        raise ValueError(
            f"Warehouse build run {warehouse_runs} differs from manifest "
            f"{manifest['warehouse_build_run_id']!r}; the audit cannot bind to this run"
        )
    if not published.model_run_id.astype(str).eq(str(manifest["model_run_id"])).all():
        raise ValueError("Published race table carries a model_run_id other than the manifest")
    for name, frame in (("published", published), ("training", training)):
        if frame.war_outcome_id.duplicated().any():
            raise ValueError(f"Duplicate war_outcome_id in the {name} table")
    published_ids = set(published.war_outcome_id)
    training_ids = set(training.war_outcome_id)
    if published_ids != training_ids:
        raise ValueError(
            f"Race universe differs: {len(published_ids - training_ids)} published-only and "
            f"{len(training_ids - published_ids)} warehouse-only races"
        )
    published = (
        published.set_index("war_outcome_id").reindex(training.war_outcome_id).reset_index()
    )
    training = training.reset_index(drop=True)
    for key in RACE_KEYS:
        if not published[key].astype(str).eq(training[key].astype(str)).all():
            raise ValueError(f"Published {key} disagrees with the warehouse race keys")
    if not published.lag_context_available.astype(bool).eq(training.lag_context_available).all():
        raise ValueError("Published lag_context_available disagrees with the rebuilt context")
    for column in INPUT_PARITY_COLUMNS:
        gap = np.abs(published[column].to_numpy(float) - training[column].to_numpy(float))
        if not np.isfinite(gap).all() or gap.max() > PARITY_TOLERANCE:
            raise ValueError(f"Published {column} disagrees with the warehouse training frame")
    return manifest, published, training


def audit_frame(published: pd.DataFrame, training: pd.DataFrame) -> pd.DataFrame:
    """Attach the published headline columns to the rebuilt training frame."""
    columns = ["war_outcome_id"] + [column for column in PUBLISHED_COLUMNS if column in published]
    missing = [column for column in ("war", *PARITY_COLUMNS) if column not in published]
    if missing:
        raise ValueError(f"Published race table lacks required columns: {missing}")
    frame = training.merge(published[columns], on="war_outcome_id", how="left", validate="one_to_one")
    if frame.war.isna().any():
        raise ValueError("Published headline WAR is missing for some rebuilt races")
    return frame


# --------------------------------------------------------------------------- fitting


def cycle_fit_predictions(
    races: pd.DataFrame,
    design: pd.DataFrame,
    alpha: float,
    lag_columns: list[str],
    fit_mask: np.ndarray | None = None,
    score_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit the ridge design within each cycle on ``fit_mask`` rows and score ``score_mask`` rows.

    Returns expected gap, non-lag expected gap (lag columns set to the zero-fill
    encoding) and the number of fitting rows used for each scored row.  Rows that
    are not scored, or whose cycle has fewer than ``MIN_FIT_ROWS`` fitting rows,
    stay NaN.
    """
    target = races.direct_overperformance.to_numpy(float)
    cycles = races.cycle.to_numpy()
    matrix = design.to_numpy(float)
    lag_index = [list(design.columns).index(column) for column in lag_columns if column in design]
    fit = np.ones(len(races), dtype=bool) if fit_mask is None else np.asarray(fit_mask, dtype=bool)
    score = np.ones(len(races), dtype=bool) if score_mask is None else np.asarray(score_mask, dtype=bool)
    expected = np.full(len(races), np.nan)
    nonlag = np.full(len(races), np.nan)
    fit_rows = np.zeros(len(races), dtype=int)
    for cycle in sorted(np.unique(cycles)):
        in_cycle = cycles == cycle
        train = in_cycle & fit
        test = in_cycle & score
        if not test.any() or train.sum() < MIN_FIT_ROWS:
            continue
        model = v2.ridge_model(alpha).fit(matrix[train], target[train])
        expected[test] = model.predict(matrix[test])
        counterfactual = matrix[test].copy()
        counterfactual[:, lag_index] = 0.0
        nonlag[test] = model.predict(counterfactual)
        fit_rows[test] = int(train.sum())
    return expected, nonlag, fit_rows


def reproduce_headline(races: pd.DataFrame, manifest: dict[str, object]) -> dict[str, object]:
    """Refit the selected specification within each cycle and enforce exact-run parity."""
    configuration = manifest["configuration"]
    specification = str(configuration["selected_structural_specification"])
    alpha = float(configuration["selected_structural_alpha"])
    designs, lag_columns = v2.design_matrices(races)
    if specification not in designs:
        raise ValueError(f"Manifest specification {specification!r} is not a v2 design")
    design = designs[specification]
    selected_lag = [column for column in lag_columns if column in design.columns]
    expected, nonlag, fit_rows = cycle_fit_predictions(races, design, alpha, selected_lag)
    if not np.isfinite(expected).all():
        raise ValueError("Within-cycle refit left unscored races")
    reproduced = {
        "fitted_structural_expected_gap": expected,
        "fitted_structural_nonlag_expected_gap": nonlag,
        "war": races.direct_overperformance.to_numpy(float) - expected,
    }
    differences: dict[str, float] = {}
    for column in PARITY_COLUMNS:
        gap = np.abs(races[column].to_numpy(float) - reproduced[column])
        if not np.isfinite(gap).all():
            raise ValueError(f"Parity gate failed: {column} has non-finite published or refit values")
        differences[column] = float(gap.max())
        if differences[column] > PARITY_TOLERANCE:
            offenders = races.loc[gap > PARITY_TOLERANCE, "war_outcome_id"].head(5).tolist()
            raise ValueError(
                f"Parity gate failed: {column} differs by up to {differences[column]:.3e} "
                f"(> {PARITY_TOLERANCE}) for {int((gap > PARITY_TOLERANCE).sum())} races, "
                f"e.g. {offenders}"
            )
    if "structural_training_rows" in races and not np.array_equal(
        races.structural_training_rows.to_numpy(int), fit_rows
    ):
        raise ValueError("Parity gate failed: within-cycle training row counts differ")
    return {
        "specification": specification,
        "alpha": alpha,
        "designs": designs,
        "design": design,
        "lag_columns": selected_lag,
        "max_abs_difference": differences,
        "tolerance": PARITY_TOLERANCE,
        "status": "passed",
    }


# --------------------------------------------------------------------------- sensitivity


def _comparison_metrics(headline: np.ndarray, alternative: np.ndarray) -> dict[str, float]:
    finite = np.isfinite(alternative) & np.isfinite(headline)
    n = int(finite.sum())
    if n == 0:
        return {
            "n": 0, "mean_diff": np.nan, "mae": np.nan, "max_abs_diff": np.nan,
            "sign_change_share": np.nan, "spearman": np.nan,
        }
    diff = alternative[finite] - headline[finite]
    sign_change = war_party_labels(alternative[finite]) != war_party_labels(headline[finite])
    spearman = np.nan
    if n >= 3:
        spearman = pd.Series(headline[finite]).corr(pd.Series(alternative[finite]), method="spearman")
    return {
        "n": n,
        "mean_diff": float(diff.mean()),
        "mae": float(np.abs(diff).mean()),
        "max_abs_diff": float(np.abs(diff).max()),
        "sign_change_share": float(sign_change.mean()),
        "spearman": float(spearman) if pd.notna(spearman) else np.nan,
    }


def _group_masks(races: pd.DataFrame) -> list[tuple[str, str, np.ndarray]]:
    available = races.lag_context_available.to_numpy(bool)
    cycles = races.cycle.to_numpy()
    groups: list[tuple[str, str, np.ndarray]] = []
    for cycle_label, cycle_mask in [("all", np.ones(len(races), dtype=bool))] + [
        (str(int(cycle)), cycles == cycle) for cycle in sorted(np.unique(cycles))
    ]:
        for lag_label, lag_mask in (
            ("all", np.ones(len(races), dtype=bool)),
            ("available", available),
            ("missing", ~available),
        ):
            groups.append((cycle_label, lag_label, cycle_mask & lag_mask))
    return groups


def context_sensitivity(
    races: pd.DataFrame,
    designs: dict[str, pd.DataFrame],
    specification: str,
    alpha: float,
    lag_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare headline WAR with descriptive refits that treat missing lag context differently.

    ``war_no_lag_spec`` drops the lag columns and fits every race in the cycle;
    ``war_lag_available_fit`` fits and scores only lag-available races;
    ``war_missing_excluded_fit`` uses that lag-available fit to score every race,
    keeping the zero-fill encoding for missing rows so that only the fitting
    influence of those rows is removed.
    """
    design = designs[specification]
    no_lag_design = designs[NO_LAG_SPECIFICATION]
    available = races.lag_context_available.to_numpy(bool)
    target = races.direct_overperformance.to_numpy(float)
    headline_war = races.war.to_numpy(float)

    no_lag_expected, _, _ = cycle_fit_predictions(races, no_lag_design, alpha, [])
    available_expected, _, available_fit_rows = cycle_fit_predictions(
        races, design, alpha, lag_columns, fit_mask=available, score_mask=available
    )
    excluded_expected, _, _ = cycle_fit_predictions(
        races, design, alpha, lag_columns, fit_mask=available, score_mask=None
    )
    alternatives = {
        "no_lag_spec": no_lag_expected,
        "lag_available_fit": available_expected,
        "missing_excluded_fit": excluded_expected,
    }

    by_race = races[["war_outcome_id", *RACE_KEYS, "lag_context_available"]].copy()
    if "lag_context_status" in races:
        by_race["lag_context_status"] = races.lag_context_status
    by_race["raw_gap"] = target
    by_race["war"] = headline_war
    by_race["war_party"] = war_party_labels(headline_war)
    by_race["headline_expected_gap"] = races.fitted_structural_expected_gap.to_numpy(float)
    by_race["headline_zero_fill_lag_component"] = races.fitted_lag_component.to_numpy(float)
    by_race["lag_available_fit_rows"] = cycle_fit_rows(races, available)
    for name, expected in alternatives.items():
        war = target - expected
        by_race[f"expected_gap_{name}"] = expected
        by_race[f"war_{name}"] = war
        by_race[f"diff_{name}"] = war - headline_war
        by_race[f"war_party_{name}"] = war_party_labels(war)
        by_race[f"sign_change_{name}"] = np.where(
            np.isfinite(war), by_race[f"war_party_{name}"] != by_race["war_party"], np.nan
        )

    rows = []
    lag_component = races.fitted_lag_component.to_numpy(float)
    for cycle_label, lag_label, mask in _group_masks(races):
        n = int(mask.sum())
        row: dict[str, object] = {
            "cycle": cycle_label,
            "lag_context_available": lag_label,
            "n": n,
            "missing_context_share": float((~available[mask]).mean()) if n else np.nan,
            "lag_available_fit_rows": int((available & mask_cycle(races, cycle_label)).sum()),
            "headline_mean_abs_lag_component": float(np.abs(lag_component[mask]).mean()) if n else np.nan,
        }
        for name, expected in alternatives.items():
            metrics = _comparison_metrics(headline_war[mask], (target - expected)[mask])
            row.update({f"{name}_{key}": value for key, value in metrics.items()})
        rows.append(row)
    summary = pd.DataFrame(rows)
    return by_race, summary


def mask_cycle(races: pd.DataFrame, cycle_label: str) -> np.ndarray:
    if cycle_label == "all":
        return np.ones(len(races), dtype=bool)
    return races.cycle.to_numpy() == int(cycle_label)


def cycle_fit_rows(races: pd.DataFrame, fit_mask: np.ndarray) -> np.ndarray:
    """Number of ``fit_mask`` rows in each race's own cycle."""
    cycles = races.cycle.to_numpy()
    counts = pd.Series(fit_mask.astype(int)).groupby(cycles).transform("sum").to_numpy()
    return counts.astype(int)


# --------------------------------------------------------------------------- bootstrap


def bootstrap_uncertainty(
    races: pd.DataFrame,
    design: pd.DataFrame,
    alpha: float,
    lag_columns: list[str],
    draws: int = DEFAULT_DRAWS,
    seed: int = DEFAULT_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Within-cycle race bootstrap of the selected structural fit.

    Each draw resamples the races of one cycle with replacement, refits the
    selected specification and scores every race of that cycle.  The interval is
    the 5th/95th percentile of the expected gap; implied WAR bounds subtract those
    percentiles from the observed raw gap.  This is sampling uncertainty of the
    descriptive structural fit conditional on the design, alpha and zero-fill
    encoding; it is not a forecast interval.
    """
    if draws < 2:
        raise ValueError("Bootstrap requires at least two draws")
    absent = [column for column in lag_columns if column not in design.columns]
    if absent:
        raise ValueError(f"Selected lag columns are missing from the design: {absent}")
    rng = np.random.default_rng(seed)
    target = races.direct_overperformance.to_numpy(float)
    cycles = races.cycle.to_numpy()
    matrix = design.to_numpy(float)
    expected_draws = np.full((draws, len(races)), np.nan)
    for cycle in sorted(np.unique(cycles)):
        index = np.flatnonzero(cycles == cycle)
        if len(index) < MIN_FIT_ROWS:
            continue
        for draw in range(draws):
            sample = rng.choice(index, size=len(index), replace=True)
            model = v2.ridge_model(alpha).fit(matrix[sample], target[sample])
            expected_draws[draw, index] = model.predict(matrix[index])
    if not np.isfinite(expected_draws).all():
        raise ValueError("Bootstrap left unscored races")

    headline_war = races.war.to_numpy(float)
    headline_party = war_party_labels(headline_war)
    draw_party = war_party_labels(target[None, :] - expected_draws)
    agreement = (draw_party == headline_party[None, :]).mean(axis=0)
    p05, p95 = np.percentile(expected_draws, [5, 95], axis=0)

    by_race = races[["war_outcome_id", *RACE_KEYS, "lag_context_available"]].copy()
    by_race["raw_gap"] = target
    by_race["fitted_structural_expected_gap"] = races.fitted_structural_expected_gap.to_numpy(float)
    by_race["war"] = headline_war
    by_race["war_party"] = headline_party
    by_race["bootstrap_draws"] = draws
    by_race["expected_gap_bootstrap_mean"] = expected_draws.mean(axis=0)
    by_race["expected_gap_se"] = expected_draws.std(axis=0, ddof=1)
    by_race["expected_gap_p05"] = p05
    by_race["expected_gap_p95"] = p95
    by_race["war_p05"] = target - p95
    by_race["war_p95"] = target - p05
    by_race["war_interval_width"] = by_race.war_p95 - by_race.war_p05
    by_race["war_interval_excludes_zero"] = (by_race.war_p05 > 0) | (by_race.war_p95 < 0)
    by_race["war_party_draw_agreement_share"] = agreement
    by_race["war_party_stable_all_draws"] = agreement >= 1.0

    groups: list[tuple[str, str, pd.DataFrame]] = [("all", "all", by_race)]
    groups += [("cycle", str(int(cycle)), part) for cycle, part in by_race.groupby("cycle", sort=True)]
    groups += [("state_code", str(state), part) for state, part in by_race.groupby("state_code", sort=True)]
    summary = pd.DataFrame([
        {
            "group_type": group_type,
            "group": group,
            "n": len(part),
            "median_expected_gap_se": float(part.expected_gap_se.median()),
            "mean_expected_gap_se": float(part.expected_gap_se.mean()),
            "median_war_interval_width": float(part.war_interval_width.median()),
            "share_war_interval_excludes_zero": float(part.war_interval_excludes_zero.mean()),
            "share_war_party_stable_all_draws": float(part.war_party_stable_all_draws.mean()),
            "mean_war_party_draw_agreement": float(part.war_party_draw_agreement_share.mean()),
        }
        for group_type, group, part in groups
    ])
    return by_race, summary


# --------------------------------------------------------------------------- cross-fit


def cross_fit_comparison(races: pd.DataFrame) -> pd.DataFrame:
    """Headline WAR versus the published same-cycle cross-fitted residual, by cycle."""
    if "validation_cross_fitted_residual" not in races:
        raise ValueError("Published race table lacks validation_cross_fitted_residual")
    war = races.war.to_numpy(float)
    residual = races.validation_cross_fitted_residual.to_numpy(float)
    cycles = races.cycle.to_numpy()
    rows = []
    for label, mask in [("all", np.ones(len(races), dtype=bool))] + [
        (str(int(cycle)), cycles == cycle) for cycle in sorted(np.unique(cycles))
    ]:
        diff = residual[mask] - war[mask]
        pearson = np.nan
        if mask.sum() >= 3:
            pearson = pd.Series(war[mask]).corr(pd.Series(residual[mask]), method="pearson")
        rows.append({
            "cycle": label,
            "n": int(mask.sum()),
            "headline_war_mae": float(np.abs(war[mask]).mean()),
            "cross_fitted_residual_mae": float(np.abs(residual[mask]).mean()),
            "mean_difference": float(diff.mean()),
            "mae_difference": float(np.abs(diff).mean()),
            "max_abs_difference": float(np.abs(diff).max()),
            "pearson_correlation": float(pearson) if pd.notna(pearson) else np.nan,
            "sign_agreement_share": float(
                (war_party_labels(war[mask]) == war_party_labels(residual[mask])).mean()
            ),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- reporting


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def missing_context_by_cycle(races: pd.DataFrame) -> pd.DataFrame:
    available = races.lag_context_available.astype(bool)
    frame = races.assign(_missing=~available).groupby("cycle", sort=True).agg(
        races=("war_outcome_id", "size"),
        lag_context_rows=("lag_context_available", "sum"),
        missing_context_rows=("_missing", "sum"),
    ).reset_index()
    frame["missing_context_share"] = frame.missing_context_rows / frame.races
    frame["lag_context_rows"] = frame.lag_context_rows.astype(int)
    frame["missing_context_rows"] = frame.missing_context_rows.astype(int)
    return frame


def _summary_rows(summary: pd.DataFrame, cycle: str, lag: str) -> dict[str, object]:
    part = summary[summary.cycle.eq(cycle) & summary.lag_context_available.eq(lag)]
    return part.iloc[0].to_dict() if len(part) else {}


def _relative(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved)


def build_summary(
    manifest: dict[str, object],
    run_dir: Path,
    parity: dict[str, object],
    races: pd.DataFrame,
    sensitivity_summary: pd.DataFrame,
    bootstrap_summary: pd.DataFrame,
    cross_fit: pd.DataFrame,
    draws: int,
    seed: int,
    runtime_seconds: float,
) -> dict[str, object]:
    run_dir = Path(run_dir)
    hashes = {
        "manifest.json": sha256(run_dir / "manifest.json"),
        "race_war.csv": sha256(run_dir / "race_war.csv"),
        "scripts/audit_southern_v3_context_sensitivity.py": sha256(Path(__file__).resolve()),
        "scripts/retrain_post2016_southern_war.py": sha256(Path(v1.__file__).resolve()),
        "scripts/retrain_post2016_southern_war_v2.py": sha256(Path(v2.__file__).resolve()),
        "scripts/retrain_post2016_southern_war_v3.py": sha256(Path(v3.__file__).resolve()),
    }
    metric_keys = ("n", "mae", "max_abs_diff", "sign_change_share", "spearman", "mean_diff")
    sensitivity = {}
    for lag in ("all", "available", "missing"):
        row = _summary_rows(sensitivity_summary, "all", lag)
        sensitivity[lag] = {
            name: {key: row.get(f"{name}_{key}") for key in metric_keys} for name in ALTERNATIVES
        }
    by_cycle_boot = bootstrap_summary[bootstrap_summary.group_type.eq("cycle")]
    overall_boot = bootstrap_summary[bootstrap_summary.group_type.eq("all")].iloc[0]
    overall_cross = cross_fit[cross_fit.cycle.eq("all")].iloc[0]
    return _json_safe({
        "schema_version": 1,
        "audit": "southern_v3_missing_context_sensitivity_and_uncertainty",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runtime_seconds": round(runtime_seconds, 2),
        "model_run_id": manifest["model_run_id"],
        "warehouse_build_run_id": manifest["warehouse_build_run_id"],
        "run_dir": _relative(run_dir),
        "sha256": hashes,
        "parity_gate": parity["status"],
        "parity_tolerance": parity["tolerance"],
        "parity_max_abs_difference": parity["max_abs_difference"],
        "selected_structural_specification": parity["specification"],
        "selected_structural_alpha": parity["alpha"],
        "selected_lag_columns": parity["lag_columns"],
        "training_rows": int(len(races)),
        "lag_context_rows": int(races.lag_context_available.astype(bool).sum()),
        "missing_context_rows": int((~races.lag_context_available.astype(bool)).sum()),
        "missing_context_by_cycle": missing_context_by_cycle(races).to_dict("records"),
        "context_sensitivity": sensitivity,
        "bootstrap": {
            "draws": draws,
            "seed": seed,
            "median_expected_gap_se_by_cycle": dict(zip(
                by_cycle_boot.group, by_cycle_boot.median_expected_gap_se
            )),
            "median_expected_gap_se": overall_boot.median_expected_gap_se,
            "share_war_interval_excludes_zero": overall_boot.share_war_interval_excludes_zero,
            "share_war_interval_excludes_zero_by_cycle": dict(zip(
                by_cycle_boot.group, by_cycle_boot.share_war_interval_excludes_zero
            )),
            "share_war_party_stable_all_draws": overall_boot.share_war_party_stable_all_draws,
            "mean_war_party_draw_agreement": overall_boot.mean_war_party_draw_agreement,
        },
        "cross_fit": {
            "mae_difference": overall_cross.mae_difference,
            "pearson_correlation": overall_cross.pearson_correlation,
            "sign_agreement_share": overall_cross.sign_agreement_share,
            "by_cycle": cross_fit.to_dict("records"),
        },
        "interpretation_limits": [
            "descriptive same-cycle refits; no predictive validation",
            "no external reference certification; no source lineage certification",
            "bootstrap reflects sampling variability of the structural fit conditional on design, alpha and zero-fill encoding",
            "this audit records evidence and does not approve release",
        ],
    })


def _fmt(value, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "n/a"
    if isinstance(value, (bool, np.bool_)):
        return str(bool(value))
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        text = f"{float(value):.{digits}f}"
        return text[1:] if text == "-" + f"{0.0:.{digits}f}" else text
    return str(value)


def markdown_table(frame: pd.DataFrame, columns: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    rule = "|" + "|".join(" --- " for _ in columns) + "|"
    lines = [header, rule]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(_fmt(row[name]) for name, _ in columns) + " |")
    return "\n".join(lines)


def _alternative_columns(name: str) -> list[tuple[str, str]]:
    return [
        ("cycle", "Cycle"), ("lag_context_available", "Lag context"), ("n", "Races"),
        (f"{name}_n", "Scored"), (f"{name}_mean_diff", "Mean diff"), (f"{name}_mae", "MAE"),
        (f"{name}_max_abs_diff", "Max abs diff"), (f"{name}_sign_change_share", "Sign change share"),
        (f"{name}_spearman", "Spearman"),
    ]


def write_report(
    path: Path,
    summary: dict[str, object],
    races: pd.DataFrame,
    sensitivity_summary: pd.DataFrame,
    bootstrap_summary: pd.DataFrame,
    cross_fit: pd.DataFrame,
    output_dir: Path,
) -> None:
    coverage = missing_context_by_cycle(races)
    coverage["cycle"] = coverage.cycle.astype(str)
    parity = summary["parity_max_abs_difference"]
    alternative_titles = {
        "no_lag_spec": (
            "`war_no_lag_spec`: `fundamentals_no_lag` design fitted within each cycle on the full sample"
        ),
        "lag_available_fit": (
            "`war_lag_available_fit`: selected design fitted and scored only on lag-available races"
        ),
        "missing_excluded_fit": (
            "`war_missing_excluded_fit`: lag-available fit scoring every race with the zero-fill encoding"
        ),
    }
    sections = [
        "# Southern WAR v3 missing-context sensitivity and uncertainty audit",
        "",
        "Read-only audit of the exact run below. It refits the published structural "
        "specification within each cycle, checks parity with the published values, and "
        "then measures how much headline WAR depends on the zero-filled lag compatibility "
        "encoding and on within-cycle sampling. Nothing here changes model values or "
        "approves release.",
        "",
        f"- Model run: `{summary['model_run_id']}`",
        f"- Warehouse build run: `{summary['warehouse_build_run_id']}`",
        f"- Manifest SHA256: `{summary['sha256']['manifest.json']}`",
        f"- race_war.csv SHA256: `{summary['sha256']['race_war.csv']}`",
        f"- Audit script SHA256: `{summary['sha256']['scripts/audit_southern_v3_context_sensitivity.py']}`",
        f"- Generated (UTC): {summary['generated_at_utc']}; runtime {summary['runtime_seconds']} s",
        f"- Selected specification: `{summary['selected_structural_specification']}` with alpha "
        f"{summary['selected_structural_alpha']:g}; lag columns {summary['selected_lag_columns']}",
        f"- Machine-readable outputs: `{_relative(output_dir)}`",
        "",
        "## Parity gate",
        "",
        f"Status: **{summary['parity_gate']}** (tolerance {summary['parity_tolerance']:g}). "
        "Maximum absolute difference between the within-cycle refit and the published values:",
        "",
        *[f"- `{column}`: {value:.3e}" for column, value in parity.items()],
        "",
        "## Missing-context coverage by cycle",
        "",
        "Rows without validated prior-presidential context enter the selected design with "
        "`prior_pres_margin`, `lag_current_ticket_change` and `lag_change_x_years` set to 0.0. "
        "Their published `fitted_lag_component` is therefore exactly zero by construction; "
        "the encoding still influences the fitted coefficients.",
        "",
        markdown_table(coverage, [
            ("cycle", "Cycle"), ("races", "Races"), ("lag_context_rows", "Lag context"),
            ("missing_context_rows", "Missing context"), ("missing_context_share", "Missing share"),
        ]),
        "",
        "## Context sensitivity",
        "",
        "Each alternative is a descriptive same-cycle refit compared with headline WAR "
        "(`alternative - headline`). Sign change share uses the published D/R/EVEN rule. "
        "Cycles with no lag-available races cannot support the lag-available fits and show "
        "`n/a` for those alternatives. States absent from the lag-available fit carry zero "
        "state coefficients in `war_missing_excluded_fit`, so that alternative isolates the "
        "fitting influence of missing rows rather than offering a like-for-like score.",
    ]
    for name in ALTERNATIVES:
        sections += ["", f"### {alternative_titles[name]}", "",
                     markdown_table(sensitivity_summary, _alternative_columns(name))]
    sections += [
        "",
        "## Bootstrap uncertainty of the structural expected gap",
        "",
        f"{summary['bootstrap']['draws']} within-cycle race bootstrap draws (seed "
        f"{summary['bootstrap']['seed']}). SE is the standard deviation of the expected gap "
        "across draws; the WAR interval subtracts the 5th/95th expected-gap percentiles from the "
        "observed raw gap. `Stable party` is the share of races whose D/R/EVEN label matched the "
        "headline in every draw.",
        "",
        "### By cycle",
        "",
        markdown_table(
            bootstrap_summary[bootstrap_summary.group_type.isin(["all", "cycle"])],
            [("group", "Cycle"), ("n", "Races"), ("median_expected_gap_se", "Median SE"),
             ("mean_expected_gap_se", "Mean SE"), ("median_war_interval_width", "Median WAR interval width"),
             ("share_war_interval_excludes_zero", "Interval excludes zero"),
             ("share_war_party_stable_all_draws", "Stable party"),
             ("mean_war_party_draw_agreement", "Mean party agreement")],
        ),
        "",
        "### By state",
        "",
        markdown_table(
            bootstrap_summary[bootstrap_summary.group_type.eq("state_code")],
            [("group", "State"), ("n", "Races"), ("median_expected_gap_se", "Median SE"),
             ("median_war_interval_width", "Median WAR interval width"),
             ("share_war_interval_excludes_zero", "Interval excludes zero"),
             ("share_war_party_stable_all_draws", "Stable party")],
        ),
        "",
        "## Headline WAR versus the same-cycle cross-fitted residual",
        "",
        "The published `validation_cross_fitted_residual` is a separate validation diagnostic "
        "and is never WAR. This table describes how far the descriptive headline sits from it.",
        "",
        markdown_table(cross_fit, [
            ("cycle", "Cycle"), ("n", "Races"), ("headline_war_mae", "Headline WAR MAE"),
            ("cross_fitted_residual_mae", "Cross-fitted residual MAE"), ("mae_difference", "MAE of difference"),
            ("max_abs_difference", "Max abs difference"), ("pearson_correlation", "Pearson"),
            ("sign_agreement_share", "Sign agreement"),
        ]),
        "",
        "## What this audit does not establish",
        "",
        "- **No predictive validation.** Every alternative, interval and comparison is a "
        "same-cycle descriptive refit on the published race universe. Nothing here is a forward, "
        "held-out or prospective test, and the cross-fitted comparison remains a same-cycle "
        "descriptive residual diagnostic, not out-of-time evidence.",
        "- **No external reference certification.** The audit does not compare any value with "
        "Split Ticket or another external WAR series, does not certify the baseline comparators, "
        "the warehouse source lineage, plan vintages or excluded races, and does not resolve the "
        "open source-file lineage findings recorded elsewhere.",
        "- **Descriptive same-cycle residual only.** Bootstrap SE and intervals describe sampling "
        "variability of the structural fit conditional on the selected design, the ridge alpha, "
        "the zero-fill encoding and the observed race universe. They exclude specification and "
        "alpha selection uncertainty, baseline measurement error and the outcome's own noise, and "
        "they are not forecast intervals or candidate-effect estimates.",
        "- **Not a release decision.** The alternatives are audit instruments, not replacement WAR "
        "definitions. Running this audit records evidence for reviewers; it does not change model "
        "values, clear the upstream release gate or approve publication.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sections), encoding="utf-8")


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR,
                        help="v3 run directory holding manifest.json and race_war.csv")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    if args.draws < 2:
        parser.error("--draws must be at least 2")

    started = time.perf_counter()
    manifest, published, training = load_run(args.run_dir)
    races = audit_frame(published, training)
    parity = reproduce_headline(races, manifest)
    sensitivity_by_race, sensitivity_summary = context_sensitivity(
        races, parity["designs"], parity["specification"], parity["alpha"], parity["lag_columns"]
    )
    bootstrap_by_race, bootstrap_summary = bootstrap_uncertainty(
        races, parity["design"], parity["alpha"], parity["lag_columns"],
        draws=args.draws, seed=args.seed,
    )
    cross_fit = cross_fit_comparison(races)
    summary = build_summary(
        manifest, args.run_dir, parity, races, sensitivity_summary, bootstrap_summary,
        cross_fit, args.draws, args.seed, time.perf_counter() - started,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = {
        "context_sensitivity_by_race.csv": sensitivity_by_race,
        "context_sensitivity_summary.csv": sensitivity_summary,
        "bootstrap_uncertainty_by_race.csv": bootstrap_by_race,
        "bootstrap_summary.csv": bootstrap_summary,
        "cross_fit_comparison.csv": cross_fit,
    }
    for name, frame in frames.items():
        frame = frame.copy()
        frame.insert(0, "model_run_id", manifest["model_run_id"])
        frame.to_csv(output_dir / name, index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(
        Path(args.report), summary, races, sensitivity_summary, bootstrap_summary, cross_fit,
        output_dir,
    )
    missing = summary["context_sensitivity"]["missing"]
    print(
        f"Southern v3 context audit: run={summary['model_run_id']} parity={summary['parity_gate']} "
        f"races={summary['training_rows']:,} missing_context={summary['missing_context_rows']:,} "
        f"no_lag_mae_missing={missing['no_lag_spec']['mae']:.3f} "
        f"missing_excluded_mae_missing={missing['missing_excluded_fit']['mae']:.3f} "
        f"median_se={summary['bootstrap']['median_expected_gap_se']:.3f} "
        f"runtime={summary['runtime_seconds']}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
