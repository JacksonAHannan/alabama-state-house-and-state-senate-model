#!/usr/bin/env python3
"""Read-only era-sensitivity and missing-lag audit for Alabama historical WAR v1.

Checklist items ``alabama-07`` (label and test the cross-era backcasts) and
``alabama-08`` (test the zero-fill compatibility encoding for the races without
validated lag context).

The published historical export labels 412 pre-2016 Alabama races as backcasts of
the post-2016 Southern ``decaying_lag`` ridge model (alpha 100) and preserves 97
same-cycle published modern races.  Eighteen of the 412 backcast races carry no
validated prior-presidential context and therefore enter the design through the
zero-fill compatibility encoding (``prior_pres_margin``,
``lag_current_ticket_change``, ``lag_change_x_years`` set to 0.0), which the field
contract calls an encoding rather than an observed zero.

This audit binds itself to one published run with a parity gate: the historical
frame is rebuilt from the compatibility inputs exactly as the builder does, the
modern training frame is read from the warehouse read-only, the published
specification and alpha are refitted on the modern rows only, and every published
backcast value must reproduce within tolerance before any diagnostic is computed.

Diagnostics:

* **Era transportability** — the same specification and alpha fitted on the
  1994-2014 Alabama compatibility frame itself, compared per cycle with the
  backcast (correlation, MAE, sign agreement, distribution of differences), plus a
  leave-one-era-out variant (1994-2006 versus 2010-2014) that exposes coefficient
  drift on the structural terms.
* **Missing lag context** — the 18 no-context races rescored with the
  ``fundamentals_no_lag`` design, plus the parallel lag-available-fit alternative
  from the Southern v3 sensitivity audit.
* **Bootstrap uncertainty** — a within-cycle training bootstrap of the backcast
  expected gap per cycle.

Every alternative here is a descriptive comparator.  None is a replacement WAR
definition, a forward or prospective validation, or a recertification, and this
audit never writes to the warehouse, to the published export, or to any other
product directory.
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
import build_alabama_historical_war_v1 as historical_builder


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = ROOT / "data/processed/war/alabama_historical_war_v1"
DEFAULT_OUTPUT_DIR = ROOT / "data/processed/war/alabama_historical_war_v1_sensitivity"
DEFAULT_REPORT = ROOT / "project_docs/audits/ALABAMA_BACKCAST_SENSITIVITY_2026_09_11.md"
DEFAULT_REPORT_JSON = ROOT / "project_docs/audits/ALABAMA_BACKCAST_SENSITIVITY_2026_09_11.json"
EXPECTED_HISTORICAL_RUN_ID = "AL-HIST-WAR-V1-76814789B2F7641E4255"

RACE_KEYS = ["cycle", "chamber", "district"]
CHAMBER_ALIASES = {"house": "lower", "senate": "upper", "lower": "lower", "upper": "upper"}
BACKCAST_MAX_CYCLE = 2014
SPECIFICATION = "decaying_lag"
NO_LAG_SPECIFICATION = "fundamentals_no_lag"
LAG_ALTERNATIVES = ("no_lag_spec", "lag_available_fit")
ALPHA = 100.0
PARITY_TOLERANCE = 1e-8
EVEN_TOLERANCE = 1e-12
MIN_FIT_ROWS = 2
DEFAULT_DRAWS = 200
DEFAULT_SEED = 20260911
ERAS = {"1994_2006": (1994, 1998, 2002, 2006), "2010_2014": (2010, 2014)}
ERA_PAIRS = (("1994_2006", "2010_2014"), ("2010_2014", "1994_2006"))

PARITY_PAIRS = {
    "raw_gap": "raw_gap",
    "fitted_structural_expected_gap": "backcast_expected_gap",
    "fitted_structural_nonlag_expected_gap": "backcast_nonlag_expected_gap",
    "fitted_lag_component": "backcast_lag_component",
    "war": "backcast_war",
    "modern_backcast_structural_expected_gap": "backcast_expected_gap",
    "modern_backcast_war": "backcast_war",
}
PARITY_REPRODUCED_COLUMNS = tuple(dict.fromkeys(PARITY_PAIRS.values()))
METRIC_KEYS = (
    "n", "mean_diff", "median_diff", "sd_diff", "min_diff", "max_diff", "p05_diff",
    "p95_diff", "mae", "max_abs_diff", "headline_mae", "alternative_mae",
    "sign_change_share", "pearson", "spearman",
)
OUTPUT_FILES = (
    "backcast_parity_by_race.csv",
    "era_transportability_by_race.csv",
    "era_transportability_summary.csv",
    "era_leaveout_summary.csv",
    "era_leaveout_coefficients.csv",
    "missing_lag_by_race.csv",
    "missing_lag_summary.csv",
    "bootstrap_backcast_by_race.csv",
    "bootstrap_backcast_summary.csv",
    "summary.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def war_party_labels(values: np.ndarray, tolerance: float = EVEN_TOLERANCE) -> np.ndarray:
    """Apply the published D/R/EVEN rule; non-finite inputs receive None."""
    values = np.asarray(values, dtype=float)
    labels = np.select(
        [values > tolerance, values < -tolerance], ["D", "R"], default="EVEN"
    ).astype(object)
    labels[~np.isfinite(values)] = None
    return labels


def comparison_metrics(headline: np.ndarray, alternative: np.ndarray) -> dict[str, object]:
    """Distribution of ``alternative - headline`` plus rank and sign agreement.

    Non-finite pairs are dropped.  ``sign_change_share`` uses the published
    D/R/EVEN rule, so a change of label (including EVEN to D or R) counts.
    Pearson/Spearman need at least three usable pairs, otherwise NaN.
    """
    headline = np.asarray(headline, dtype=float)
    alternative = np.asarray(alternative, dtype=float)
    finite = np.isfinite(headline) & np.isfinite(alternative)
    n = int(finite.sum())
    if n == 0:
        empty: dict[str, object] = {key: np.nan for key in METRIC_KEYS}
        empty["n"] = 0
        return empty
    head = headline[finite]
    alt = alternative[finite]
    diff = alt - head
    sign_change = war_party_labels(alt) != war_party_labels(head)
    pearson = spearman = np.nan
    if n >= 3:
        pearson = pd.Series(head).corr(pd.Series(alt), method="pearson")
        spearman = pd.Series(head).corr(pd.Series(alt), method="spearman")
    return {
        "n": n,
        "mean_diff": float(diff.mean()),
        "median_diff": float(np.median(diff)),
        "sd_diff": float(diff.std(ddof=1)) if n >= 2 else np.nan,
        "min_diff": float(diff.min()),
        "max_diff": float(diff.max()),
        "p05_diff": float(np.percentile(diff, 5)),
        "p95_diff": float(np.percentile(diff, 95)),
        "mae": float(np.abs(diff).mean()),
        "max_abs_diff": float(np.abs(diff).max()),
        "headline_mae": float(np.abs(head).mean()),
        "alternative_mae": float(np.abs(alt).mean()),
        "sign_change_share": float(sign_change.mean()),
        "pearson": float(pearson) if pd.notna(pearson) else np.nan,
        "spearman": float(spearman) if pd.notna(spearman) else np.nan,
    }


def normalize_race_keys(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize chamber and district labels so published rows can be aligned."""
    frame = frame.copy()
    frame["chamber"] = frame.chamber.map(
        lambda value: CHAMBER_ALIASES.get(str(value).lower(), str(value).lower())
    )
    if frame.chamber.isna().any() or not frame.chamber.isin({"lower", "upper"}).all():
        raise ValueError(f"Unknown chamber in race keys: {frame.chamber.unique().tolist()}")
    frame["district"] = (
        frame.district.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    )
    return frame


def parity_check(
    published: pd.DataFrame,
    reproduced: pd.DataFrame,
    pairs: dict[str, str] = PARITY_PAIRS,
    tolerance: float = PARITY_TOLERANCE,
) -> dict[str, float]:
    """Refuse when reproduced values differ from the published table beyond tolerance.

    ``pairs`` maps a published column to the reproduced column that must match it.
    Row order must already be aligned one-to-one.
    """
    if len(published) != len(reproduced):
        raise ValueError(
            f"Parity gate failed: {len(published)} published rows versus "
            f"{len(reproduced)} reproduced rows"
        )
    differences: dict[str, float] = {}
    for published_column, reproduced_column in pairs.items():
        for name, frame, column in (
            ("published", published, published_column),
            ("reproduced", reproduced, reproduced_column),
        ):
            if column not in frame.columns:
                raise ValueError(
                    f"Parity gate failed: {name} frame lacks {column!r}"
                )
        gap = np.abs(
            published[published_column].to_numpy(float)
            - reproduced[reproduced_column].to_numpy(float)
        )
        if not np.isfinite(gap).all():
            raise ValueError(
                f"Parity gate failed: {published_column} has non-finite published "
                "or reproduced values"
            )
        differences[published_column] = float(gap.max())
        if differences[published_column] > tolerance:
            offenders = np.flatnonzero(gap > tolerance)[:5].tolist()
            raise ValueError(
                f"Parity gate failed: {published_column} differs by up to "
                f"{differences[published_column]:.3e} (> {tolerance:g}) for "
                f"{int((gap > tolerance).sum())} races, e.g. rows {offenders}"
            )
    return differences


def align_published(published: pd.DataFrame, keys: pd.DataFrame) -> pd.DataFrame:
    """Order the published race table onto the given race keys, refusing key drift."""
    published = normalize_race_keys(published)
    if published.duplicated(RACE_KEYS).any():
        raise ValueError("Published race table keys are not unique")
    aligned = normalize_race_keys(keys[RACE_KEYS]).merge(
        published, on=RACE_KEYS, how="left", validate="one_to_one"
    )
    if aligned.war.isna().any():
        missing = aligned.loc[aligned.war.isna(), RACE_KEYS].head(5).to_dict("records")
        raise ValueError(f"Published race table lacks rebuilt races, e.g. {missing}")
    return aligned


def load_published_run(
    run_dir: Path, expected_run_id: str = EXPECTED_HISTORICAL_RUN_ID
) -> tuple[dict[str, object], pd.DataFrame]:
    """Return the manifest and race table of the one run this audit is bound to."""
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    published = pd.read_csv(run_dir / "race_war.csv", low_memory=False)
    actual = str(manifest.get("historical_war_run_id", ""))
    if actual != expected_run_id:
        raise ValueError(
            f"Published historical run {actual!r} is not the bound run "
            f"{expected_run_id!r}"
        )
    recorded = published.historical_war_run_id.astype(str).unique().tolist()
    if recorded != [actual]:
        raise ValueError(
            f"Published race table carries run ids {recorded}, not the manifest run "
            f"{actual!r}"
        )
    if published.duplicated(RACE_KEYS).any():
        raise ValueError("Published race keys are not unique")
    return manifest, published


def input_hash_drift(manifest: dict[str, object], root: Path = ROOT) -> list[dict[str, object]]:
    """Compare manifest-recorded input hashes with the bytes on disk (evidence only)."""
    drift = []
    for relative, recorded in (manifest.get("input_hashes") or {}).items():
        path = Path(root) / relative
        disk = sha256(path) if path.exists() else None
        if disk != recorded:
            drift.append({"path": relative, "recorded": recorded, "disk": disk})
    return drift


# --------------------------------------------------------------------------- fitting


def model_coefficients(model, columns: list[str]) -> pd.Series:
    """Unscale ridge coefficients back onto the design's original units."""
    scaler = model.named_steps["scale"]
    ridge = model.named_steps["ridge"]
    original = ridge.coef_ / scaler.scale_
    intercept = float(ridge.intercept_ - np.dot(scaler.mean_, original))
    return pd.Series({"__intercept__": intercept, **dict(zip(columns, original))})


def reproduce_backcast(
    historical: pd.DataFrame,
    design: pd.DataFrame,
    modern_rows: int,
    modern_target: np.ndarray,
    lag_columns: list[str],
    alpha: float = ALPHA,
) -> tuple[pd.DataFrame, pd.DataFrame, object]:
    """Refit the published specification on the modern rows and score the backcast rows."""
    if modern_rows < MIN_FIT_ROWS or modern_rows >= len(design):
        raise ValueError(f"Backcast needs a non-empty modern head and historical tail: {modern_rows}")
    target = np.asarray(modern_target, dtype=float)
    if not np.isfinite(target).all():
        raise ValueError("Modern training target contains non-finite values")
    model = v2.ridge_model(alpha).fit(
        design.iloc[:modern_rows], target[:modern_rows]
    )
    tail = design.iloc[modern_rows:]
    expected = model.predict(tail)
    nonlag_design = tail.copy()
    for column in lag_columns:
        nonlag_design[column] = 0.0
    nonlag = model.predict(nonlag_design)
    frame = historical[
        RACE_KEYS + ["raw_gap", "direct_overperformance", "incumbency_balance",
                     "baseline_dem_margin", "lag_context_available",
                     "prior_presidential_margin"]
    ].copy()
    frame["backcast_expected_gap"] = expected
    frame["backcast_nonlag_expected_gap"] = nonlag
    frame["backcast_lag_component"] = expected - nonlag
    frame["backcast_war"] = frame.raw_gap.to_numpy(float) - expected
    return frame, tail, model


def cycle_masks(cycles: np.ndarray) -> list[tuple[str, np.ndarray]]:
    cycles = np.asarray(cycles)
    return [("all", np.ones(len(cycles), dtype=bool))] + [
        (str(int(cycle)), cycles == cycle) for cycle in sorted(np.unique(cycles))
    ]


def era_transportability(
    backcast: pd.DataFrame, design: pd.DataFrame, alpha: float = ALPHA
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Same-era descriptive fit on the 1994-2014 frame compared with the backcast.

    The published specification and alpha are fitted on every backcast race at
    once (pooled 1994-2014) and used to score those same races.  The comparison is
    therefore an in-era descriptive residual fit, not a transportability test that
    could replace the modern-model contract.
    """
    target = backcast.direct_overperformance.to_numpy(float)
    raw_gap = backcast.raw_gap.to_numpy(float)
    backcast_war = backcast.backcast_war.to_numpy(float)
    model = v2.ridge_model(alpha).fit(design, target)
    expected = model.predict(design)
    same_era_war = raw_gap - expected

    by_race = backcast[RACE_KEYS + ["lag_context_available"]].copy()
    by_race["raw_gap"] = raw_gap
    by_race["direct_overperformance"] = target
    by_race["backcast_expected_gap"] = backcast.backcast_expected_gap.to_numpy(float)
    by_race["backcast_war"] = backcast_war
    by_race["same_era_expected_gap"] = expected
    by_race["same_era_war"] = same_era_war
    by_race["diff_same_era_minus_backcast"] = same_era_war - backcast_war
    by_race["war_party_backcast"] = war_party_labels(backcast_war)
    by_race["war_party_same_era"] = war_party_labels(same_era_war)
    by_race["sign_change_same_era"] = (
        by_race.war_party_backcast != by_race.war_party_same_era
    )

    cycles = backcast.cycle.to_numpy()
    rows = []
    for label, mask in cycle_masks(cycles):
        rows.append({
            "cycle": label,
            "fit_scope": "pooled_1994_2014",
            "n": int(mask.sum()),
            "backcast_mean_war": float(backcast_war[mask].mean()),
            "same_era_mean_war": float(same_era_war[mask].mean()),
            **comparison_metrics(backcast_war[mask], same_era_war[mask]),
        })
    return by_race, pd.DataFrame(rows)


def leave_one_era_out(
    backcast: pd.DataFrame,
    design: pd.DataFrame,
    alpha: float = ALPHA,
    eras: dict[str, tuple[int, ...]] = ERAS,
    pairs: tuple[tuple[str, str], ...] = ERA_PAIRS,
) -> pd.DataFrame:
    """Fit one era half and score the other, against the backcast WAR."""
    target = backcast.direct_overperformance.to_numpy(float)
    raw_gap = backcast.raw_gap.to_numpy(float)
    backcast_war = backcast.backcast_war.to_numpy(float)
    cycles = backcast.cycle.to_numpy()
    rows = []
    for fit_era, score_era in pairs:
        fit_mask = np.isin(cycles, eras[fit_era])
        score_mask = np.isin(cycles, eras[score_era])
        if fit_mask.sum() < MIN_FIT_ROWS or score_mask.sum() < MIN_FIT_ROWS:
            raise ValueError(f"Era window {fit_era}->{score_era} has too few races")
        model = v2.ridge_model(alpha).fit(design[fit_mask], target[fit_mask])
        out_of_era_war = raw_gap[score_mask] - model.predict(design[score_mask])
        rows.append({
            "fit_era": fit_era,
            "score_era": score_era,
            "fit_races": int(fit_mask.sum()),
            "n": int(score_mask.sum()),
            "backcast_mean_war": float(backcast_war[score_mask].mean()),
            "out_of_era_mean_war": float(out_of_era_war.mean()),
            **comparison_metrics(backcast_war[score_mask], out_of_era_war),
        })
    return pd.DataFrame(rows)


def coefficient_drift_table(
    design: pd.DataFrame,
    target: np.ndarray,
    cycles: np.ndarray,
    modern_coefficients: pd.Series,
    lag_columns: list[str],
    alpha: float = ALPHA,
    eras: dict[str, tuple[int, ...]] = ERAS,
) -> pd.DataFrame:
    """Coefficient drift between era fits, and between the pooled era and modern fits."""
    columns = list(design.columns)
    target = np.asarray(target, dtype=float)
    cycles = np.asarray(cycles)
    fits = {"historical_pooled_1994_2014": v2.ridge_model(alpha).fit(design, target)}
    standard_deviations: dict[str, pd.Series] = {
        "historical_pooled_1994_2014": design.std(ddof=0)
    }
    for name, cycles_in in eras.items():
        mask = np.isin(cycles, cycles_in)
        if mask.sum() < MIN_FIT_ROWS:
            raise ValueError(f"Era window {name} has too few races")
        fits[f"historical_{name}"] = v2.ridge_model(alpha).fit(design[mask], target[mask])
        standard_deviations[f"historical_{name}"] = design[mask].std(ddof=0)

    features = ["__intercept__", *columns]
    table = pd.DataFrame({"feature": features})
    table["term_family"] = [
        "intercept" if feature == "__intercept__"
        else ("lag" if feature in lag_columns else "structural")
        for feature in features
    ]
    for name, deviations in standard_deviations.items():
        table[f"std_{name}"] = [np.nan, *deviations.to_numpy(float)]
    table["coefficient_modern_backcast"] = modern_coefficients.reindex(features).to_numpy(float)
    for name, model in fits.items():
        table[f"coefficient_{name}"] = (
            model_coefficients(model, columns).reindex(features).to_numpy(float)
        )
    table["era_drift"] = (
        table["coefficient_historical_2010_2014"]
        - table["coefficient_historical_1994_2006"]
    )
    table["pooled_vs_modern_drift"] = (
        table["coefficient_historical_pooled_1994_2014"]
        - table["coefficient_modern_backcast"]
    )
    table["abs_era_drift"] = table.era_drift.abs()
    table["era_comparable"] = (
        (table["std_historical_1994_2006"] > 1e-12)
        & (table["std_historical_2010_2014"] > 1e-12)
    )
    return table


# --------------------------------------------------------------------------- missing lag


def missing_lag_sensitivity(
    backcast: pd.DataFrame,
    designs: dict[str, pd.DataFrame],
    modern_rows: int,
    modern_target: np.ndarray,
    modern_available: np.ndarray,
    lag_columns: list[str],
    tail_mask: np.ndarray | None = None,
    alpha: float = ALPHA,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rescore the backcast with alternatives to the zero-fill lag encoding.

    ``war_no_lag_spec`` fits the ``fundamentals_no_lag`` design on the modern rows;
    ``war_lag_available_fit`` fits the published design on the modern rows that do
    carry validated lag context.  Both are descriptive comparators for the
    published backcast, whose missing-context rows carry an exactly zero lag
    contribution by construction.  ``tail_mask`` selects the backcast rows out of
    the combined design's historical tail.
    """
    target = backcast.direct_overperformance.to_numpy(float)
    raw_gap = backcast.raw_gap.to_numpy(float)
    backcast_war = backcast.backcast_war.to_numpy(float)
    available = backcast.lag_context_available.to_numpy(bool)
    modern_target = np.asarray(modern_target, dtype=float)
    modern_available = np.asarray(modern_available, dtype=bool)

    no_lag = designs[NO_LAG_SPECIFICATION]
    no_lag_all = no_lag.iloc[modern_rows:]
    selected_all = designs[SPECIFICATION].iloc[modern_rows:]
    if tail_mask is None:
        tail_mask = np.ones(len(selected_all), dtype=bool)
    tail_mask = np.asarray(tail_mask, dtype=bool)
    if int(tail_mask.sum()) != len(backcast):
        raise ValueError(
            f"Backcast tail mask selects {int(tail_mask.sum())} rows for "
            f"{len(backcast)} backcast races"
        )
    selected = selected_all.iloc[tail_mask]
    no_lag_model = v2.ridge_model(alpha).fit(
        no_lag.iloc[:modern_rows], modern_target[:modern_rows]
    )
    if modern_available.sum() < MIN_FIT_ROWS:
        raise ValueError("No modern race carries validated lag context")
    lag_model = v2.ridge_model(alpha).fit(
        designs[SPECIFICATION].iloc[:modern_rows][modern_available],
        modern_target[:modern_rows][modern_available],
    )
    alternatives = {
        "no_lag_spec": no_lag_model.predict(no_lag_all.iloc[tail_mask]),
        "lag_available_fit": lag_model.predict(selected),
    }

    by_race = backcast[RACE_KEYS + ["lag_context_available"]].copy()
    by_race["prior_presidential_margin"] = backcast.prior_presidential_margin.to_numpy(float)
    by_race["raw_gap"] = raw_gap
    by_race["war"] = backcast_war
    by_race["war_party"] = war_party_labels(backcast_war)
    by_race["headline_expected_gap"] = backcast.backcast_expected_gap.to_numpy(float)
    by_race["headline_zero_fill_lag_component"] = backcast.backcast_lag_component.to_numpy(float)
    for name, expected in alternatives.items():
        war = raw_gap - expected
        by_race[f"expected_gap_{name}"] = expected
        by_race[f"war_{name}"] = war
        by_race[f"diff_{name}"] = war - backcast_war
        by_race[f"war_party_{name}"] = war_party_labels(war)
        by_race[f"sign_change_{name}"] = (
            by_race[f"war_party_{name}"] != by_race["war_party"]
        ).to_numpy(bool)

    rows = []
    cycles = backcast.cycle.to_numpy()
    for cycle_label, cycle_mask in cycle_masks(cycles):
        for status_label, status_mask in (
            ("all", np.ones(len(cycles), dtype=bool)),
            ("available", available),
            ("missing", ~available),
        ):
            mask = cycle_mask & status_mask
            n = int(mask.sum())
            row: dict[str, object] = {
                "cycle": cycle_label,
                "lag_context_available": status_label,
                "n": n,
                "missing_context_share": float((~available[mask]).mean()) if n else np.nan,
                "headline_mean_abs_lag_component": (
                    float(np.abs(by_race.headline_zero_fill_lag_component.to_numpy(float)[mask]).mean())
                    if n else np.nan
                ),
            }
            for name in LAG_ALTERNATIVES:
                metrics = comparison_metrics(backcast_war[mask], (raw_gap - alternatives[name])[mask])
                row.update({
                    f"{name}_{key}": value for key, value in metrics.items()
                })
                row[f"{name}_sign_changes"] = (
                    int(by_race.loc[mask, f"sign_change_{name}"].sum()) if n else 0
                )
            rows.append(row)
    return by_race, pd.DataFrame(rows)


# --------------------------------------------------------------------------- bootstrap


def bootstrap_expected_gap(
    design: pd.DataFrame,
    target: np.ndarray,
    cycles: np.ndarray,
    score_design: pd.DataFrame,
    alpha: float = ALPHA,
    draws: int = DEFAULT_DRAWS,
    seed: int = DEFAULT_SEED,
) -> np.ndarray:
    """Within-cycle training bootstrap of the fitted expected gap.

    Each draw resamples the training races with replacement inside each training
    cycle, refits the published specification and alpha, and scores every row of
    ``score_design``.  Returns a ``draws`` by ``len(score_design)`` array.
    """
    if draws < 2:
        raise ValueError("Bootstrap requires at least two draws")
    if list(design.columns) != list(score_design.columns):
        raise ValueError("Training and scoring designs carry different columns")
    matrix = design.to_numpy(float)
    target = np.asarray(target, dtype=float)
    cycles = np.asarray(cycles)
    score = score_design.to_numpy(float)
    if not np.isfinite(matrix).all() or not np.isfinite(score).all():
        raise ValueError("Bootstrap design contains non-finite values")
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(cycles == cycle) for cycle in sorted(np.unique(cycles))]
    draws_array = np.full((draws, len(score)), np.nan)
    for draw in range(draws):
        sample = np.concatenate([
            rng.choice(group, size=len(group), replace=True) for group in groups
        ])
        model = v2.ridge_model(alpha).fit(matrix[sample], target[sample])
        draws_array[draw] = model.predict(score)
    if not np.isfinite(draws_array).all():
        raise ValueError("Bootstrap left unscored races")
    return draws_array


def bootstrap_backcast(
    backcast: pd.DataFrame,
    design: pd.DataFrame,
    target: np.ndarray,
    cycles: np.ndarray,
    score_design: pd.DataFrame,
    alpha: float = ALPHA,
    draws: int = DEFAULT_DRAWS,
    seed: int = DEFAULT_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bootstrap the backcast expected gap per cycle and summarise the draws."""
    draws_array = bootstrap_expected_gap(
        design, target, cycles, score_design, alpha=alpha, draws=draws, seed=seed
    )
    raw_gap = backcast.raw_gap.to_numpy(float)
    backcast_war = backcast.backcast_war.to_numpy(float)
    party = war_party_labels(backcast_war)
    draw_party = war_party_labels(raw_gap[None, :] - draws_array)
    agreement = (draw_party == party[None, :]).mean(axis=0)
    p05, p95 = np.percentile(draws_array, [5, 95], axis=0)

    by_race = backcast[RACE_KEYS + ["lag_context_available"]].copy()
    by_race["raw_gap"] = raw_gap
    by_race["fitted_backcast_expected_gap"] = backcast.backcast_expected_gap.to_numpy(float)
    by_race["war"] = backcast_war
    by_race["war_party"] = party
    by_race["bootstrap_draws"] = draws
    by_race["expected_gap_bootstrap_mean"] = draws_array.mean(axis=0)
    by_race["expected_gap_se"] = draws_array.std(axis=0, ddof=1)
    by_race["expected_gap_p05"] = p05
    by_race["expected_gap_p95"] = p95
    by_race["war_p05"] = raw_gap - p95
    by_race["war_p95"] = raw_gap - p05
    by_race["war_interval_width"] = by_race.war_p95 - by_race.war_p05
    by_race["war_interval_excludes_zero"] = (by_race.war_p05 > 0) | (by_race.war_p95 < 0)
    by_race["war_party_draw_agreement_share"] = agreement
    by_race["war_party_stable_all_draws"] = agreement >= 1.0

    groups: list[tuple[str, str, pd.DataFrame]] = [("all", "all", by_race)]
    groups += [
        ("cycle", str(int(cycle)), part)
        for cycle, part in by_race.groupby("cycle", sort=True)
    ]
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


# --------------------------------------------------------------------------- reporting


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _relative(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved)


def build_summary(
    manifest: dict[str, object],
    warehouse_run: dict[str, object],
    run_dir: Path,
    parity: dict[str, float],
    configuration: dict[str, object],
    frame_counts: dict[str, object],
    training_frame: dict[str, object],
    era_by_cycle: pd.DataFrame,
    era_leaveout: pd.DataFrame,
    drift: pd.DataFrame,
    missing_summary: pd.DataFrame,
    missing_by_race: pd.DataFrame,
    bootstrap_summary: pd.DataFrame,
    input_drift: list[dict[str, object]],
    draws: int,
    seed: int,
    runtime_seconds: float,
) -> dict[str, object]:
    run_dir = Path(run_dir)
    hashes = {
        "manifest.json": sha256(run_dir / "manifest.json"),
        "race_war.csv": sha256(run_dir / "race_war.csv"),
        "scripts/audit_alabama_backcast_sensitivity.py": sha256(Path(__file__).resolve()),
        "scripts/build_alabama_historical_war_v1.py": sha256(
            Path(historical_builder.__file__).resolve()
        ),
        "scripts/retrain_post2016_southern_war.py": sha256(Path(v1.__file__).resolve()),
        "scripts/retrain_post2016_southern_war_v2.py": sha256(Path(v2.__file__).resolve()),
    }
    overall_era = era_by_cycle[era_by_cycle.cycle.eq("all")].iloc[0]
    missing_rows = missing_by_race[~missing_by_race.lag_context_available.astype(bool)]
    missing_headline: dict[str, object] = {}
    for name in LAG_ALTERNATIVES:
        diffs = missing_rows[f"diff_{name}"].to_numpy(float)
        changes = missing_rows[f"sign_change_{name}"].to_numpy(bool)
        missing_headline[name] = {
            "n": int(len(missing_rows)),
            "mean_diff": float(diffs.mean()),
            "median_diff": float(np.median(diffs)),
            "max_abs_diff": float(np.abs(diffs).max()),
            "min_diff": float(diffs.min()),
            "max_diff": float(diffs.max()),
            "sign_changes": int(changes.sum()),
            "sign_change_share": float(changes.mean()),
            "sign_change_races": missing_rows.loc[
                changes, ["cycle", "chamber", "district"]
            ].to_dict("records"),
        }
    comparable = drift[drift.term_family.eq("structural") & drift.era_comparable].sort_values(
        "abs_era_drift", ascending=False
    )
    structural_drift_headline = comparable.head(5)[[
        "feature", "coefficient_historical_1994_2006", "coefficient_historical_2010_2014",
        "era_drift", "coefficient_historical_pooled_1994_2014",
        "coefficient_modern_backcast",
    ]].to_dict("records")
    cycle_boot = bootstrap_summary[bootstrap_summary.group_type.eq("cycle")]
    overall_boot = bootstrap_summary[bootstrap_summary.group_type.eq("all")].iloc[0]
    return _json_safe({
        "schema_version": 1,
        "audit": "alabama_historical_backcast_era_sensitivity_and_missing_lag",
        "audit_id": "ALABAMA_BACKCAST_SENSITIVITY_2026_09_11",
        "checklist_items": ["alabama-07", "alabama-08"],
        "scope": (
            "Read-only sensitivity diagnostics for the 412 pre-2016 Alabama backcast races "
            "in the published historical export: same-era descriptive refit, leave-one-era-out "
            "coefficient drift, missing lag-context alternatives and a within-cycle training "
            "bootstrap. Not a recertification, replacement contract or forward validation."
        ),
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runtime_seconds": round(runtime_seconds, 2),
        "git_commit": historical_builder.git_commit(),
        "historical_war_run_id": manifest["historical_war_run_id"],
        "expected_historical_war_run_id": EXPECTED_HISTORICAL_RUN_ID,
        "warehouse_build_run_id": manifest.get("warehouse_build_run_id"),
        "warehouse_build_run_id_live": warehouse_run.get("build_run_id"),
        "source_southern_war_run_id": manifest.get("source_southern_war_run_id"),
        "source_alabama_war_run_id": manifest.get("source_alabama_war_run_id"),
        "run_dir": _relative(run_dir),
        "sha256": hashes,
        "parity_gate": "passed",
        "parity_tolerance": PARITY_TOLERANCE,
        "parity_max_abs_difference": parity,
        "configuration": configuration,
        "race_counts": frame_counts,
        "training_frame": training_frame,
        "input_hash_drift": input_drift,
        "era_transportability": {
            "fit_scope": "pooled_1994_2014_same_era_descriptive_fit",
            "all_cycles": _json_safe(overall_era.to_dict()),
            "by_cycle": _json_safe(
                era_by_cycle[era_by_cycle.cycle.ne("all")].to_dict("records")
            ),
        },
        "era_leaveout": {
            "directions": _json_safe(era_leaveout.to_dict("records")),
            "largest_structural_era_coefficient_drifts": _json_safe(structural_drift_headline),
            "coefficient_notes": [
                "era_drift is the 2010-2014 fit minus the 1994-2006 fit on the same feature space",
                "complementary dummy pairs carry mirrored coefficients; each pair is one degree "
                "of freedom",
                "features constant inside an era window are not identified there and carry a "
                "zero coefficient",
            ],
        },
        "missing_lag": {
            "by_status": _json_safe(
                missing_summary[missing_summary.cycle.eq("all")].to_dict("records")
            ),
            "missing_race_count": int(len(missing_rows)),
            "alternatives": missing_headline,
        },
        "bootstrap": {
            "draws": draws,
            "seed": seed,
            "resampling": (
                "training races resampled with replacement within each modern training cycle, "
                "refit on the published specification and alpha, scoring every backcast race"
            ),
            "median_expected_gap_se": overall_boot.median_expected_gap_se,
            "median_expected_gap_se_by_cycle": dict(
                zip(cycle_boot.group, cycle_boot.median_expected_gap_se)
            ),
            "share_war_interval_excludes_zero": overall_boot.share_war_interval_excludes_zero,
            "share_war_interval_excludes_zero_by_cycle": dict(
                zip(cycle_boot.group, cycle_boot.share_war_interval_excludes_zero)
            ),
            "share_war_party_stable_all_draws": overall_boot.share_war_party_stable_all_draws,
            "mean_war_party_draw_agreement": overall_boot.mean_war_party_draw_agreement,
        },
        "headline": {
            "era_transportability_by_cycle": {
                row.cycle: {
                    "n": int(row.n),
                    "pearson": row.pearson,
                    "spearman": row.spearman,
                    "sign_agreement_share": 1.0 - row.sign_change_share,
                    "mae": row.mae,
                    "mean_diff": row.mean_diff,
                }
                for row in era_by_cycle[era_by_cycle.cycle.ne("all")].itertuples()
            },
            "era_transportability_overall": {
                "n": int(overall_era.n),
                "pearson": overall_era.pearson,
                "spearman": overall_era.spearman,
                "sign_agreement_share": 1.0 - overall_era.sign_change_share,
                "mae": overall_era.mae,
                "mean_diff": overall_era.mean_diff,
                "median_diff": overall_era.median_diff,
                "p05_diff": overall_era.p05_diff,
                "p95_diff": overall_era.p95_diff,
            },
            "leave_one_era_out": {
                f"{row.fit_era}->{row.score_era}": {
                    "n": int(row.n),
                    "pearson": row.pearson,
                    "sign_agreement_share": 1.0 - row.sign_change_share,
                    "mae": row.mae,
                }
                for row in era_leaveout.itertuples()
            },
            "largest_structural_era_coefficient_drifts": structural_drift_headline,
            "missing_lag": missing_headline,
            "bootstrap_median_expected_gap_se_by_cycle": dict(
                zip(cycle_boot.group, cycle_boot.median_expected_gap_se)
            ),
        },
        "interpretation_limits": [
            "descriptive same-era and out-of-era refits; no predictive or prospective validation",
            "the backcast is a modern-relationship extrapolation, not a contemporaneous fit",
            "bootstrap reflects training-sample variability conditional on design, alpha, the "
            "zero-fill encoding and the observed race universe",
            "no external WAR reference comparison and no source-lineage certification",
            "this audit records evidence and does not approve release or recertify the run",
        ],
        "not_established": [
            "whether the modern structural relationship holds in 1994-2014 Alabama",
            "that the same-era fit is a better or worse WAR definition than the backcast",
            "any causal interpretation of residuals, incumbent effects or ticket-lag terms",
            "plan vintage, baseline provenance and source-cell lineage of the compatibility inputs",
            "any forward or prospective accuracy of the backcast",
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


def write_report(
    path: Path,
    summary: dict[str, object],
    era_by_cycle: pd.DataFrame,
    era_leaveout: pd.DataFrame,
    drift: pd.DataFrame,
    missing_summary: pd.DataFrame,
    missing_by_race: pd.DataFrame,
    bootstrap_summary: pd.DataFrame,
    output_dir: Path,
) -> None:
    output_dir = Path(output_dir)
    parity = summary["parity_max_abs_difference"]
    missing_rows = missing_by_race[~missing_by_race.lag_context_available.astype(bool)].copy()
    missing_rows["cycle"] = missing_rows.cycle.astype(int).astype(str)
    overall_era = era_by_cycle[era_by_cycle.cycle.eq("all")].iloc[0]
    comparable = drift[drift.term_family.eq("structural") & drift.era_comparable].sort_values(
        "abs_era_drift", ascending=False
    )
    structural = drift[drift.term_family.eq("structural")].copy()
    sections = [
        "# Alabama historical WAR backcast sensitivity — 2026-09-11",
        "",
        "Internal execution evidence for checklist items `alabama-07` (label and test the "
        "cross-era backcasts: era sensitivity and transportability of the 412 pre-2016 races) "
        "and `alabama-08` (18 races with missing lag context: test the effect of the zero-fill "
        "compatibility encoding).",
        "",
        "This is a **read-only sensitivity audit**. No data, model, warehouse, checklist or "
        "published export was modified. The machine-readable companion of this report is "
        "`ALABAMA_BACKCAST_SENSITIVITY_2026_09_11.json` in this directory; the full CSV set and "
        "an identical `summary.json` are written under "
        f"`{_relative(output_dir)}` (`generated_at_utc` `{summary['generated_at_utc']}`).",
        "",
        "## What was audited",
        "",
        f"- Published historical run: `{summary['historical_war_run_id']}` "
        f"(bound expected id `{summary['expected_historical_war_run_id']}`)",
        f"- Warehouse build run: `{summary['warehouse_build_run_id']}` "
        f"(live `{summary['warehouse_build_run_id_live']}`)",
        f"- Southern source run: `{summary['source_southern_war_run_id']}`; "
        f"Alabama modern source: `{summary['source_alabama_war_run_id']}`",
        f"- `manifest.json` SHA256 `{summary['sha256']['manifest.json']}`; "
        f"`race_war.csv` SHA256 `{summary['sha256']['race_war.csv']}`",
        f"- Audit script SHA256 `{summary['sha256']['scripts/audit_alabama_backcast_sensitivity.py']}`",
        f"- Generated (UTC) {summary['generated_at_utc']}; runtime {summary['runtime_seconds']} s; "
        f"repository commit `{summary['git_commit']}`",
        f"- Published specification `{summary['configuration']['specification']}` with alpha "
        f"{summary['configuration']['alpha']:g}; no-lag comparator "
        f"`{summary['configuration']['no_lag_specification']}`",
        f"- Machine-readable outputs: `{_relative(output_dir)}`",
        "- Commands: `.venv/Scripts/python.exe scripts/audit_alabama_backcast_sensitivity.py "
        f"--draws {summary['configuration']['bootstrap_draws']} "
        f"--seed {summary['configuration']['bootstrap_seed']}` and "
        "`.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider "
        "scripts/tests/test_alabama_backcast_sensitivity.py -q`",
        "",
        "Reproduction path: `scripts/build_alabama_historical_war_v1.prepare_historical_races()` "
        "rebuilds the 509-race historical frame from `data/processed/war/cmo_v5_races.csv` and "
        "`data/processed/elections/canonical_cmo_features.csv`; "
        "`retrain_post2016_southern_war_v2.load_training()` reads the modern strict training "
        "frame from the central warehouse read-only "
        "(`sqlite3.connect('file:...?mode=ro', uri=True)`, one bounded query over "
        "`mart_southern_war_training_with_finance` with "
        "`cycle > 2016 AND training_status = 'strict_war_ready_no_finance'`); the published "
        "design (`v2.design_matrices`) is refitted on the modern rows only and applied to the "
        "historical rows exactly as the builder does.",
        "",
        "## Parity gate",
        "",
        f"Status: **{summary['parity_gate']}** (tolerance {summary['parity_tolerance']:g}) on the "
        f"{summary['race_counts']['backcast_races']} backcast races (cycles 1994-2014). Maximum "
        "absolute difference between the rebuild and the published values:",
        "",
        *[f"- `{column}`: {value:.3e}" for column, value in parity.items()],
        "",
        "The `raw_gap_all_509_races` line is an input-parity check over every historical race, "
        "including the 97 published 2018/2022 races, which preserve the Alabama WAR v1 "
        "same-cycle residual instead of being reproduced by this model. The remaining lines are "
        "the backcast parity gate on the 412 pre-2016 races; those 412 races are the only ones "
        "the diagnostics below use.",
        "",
        f"Modern training frame: {summary['training_frame']['rows']:,} strict races over cycles "
        f"{summary['training_frame']['cycles']}; "
        f"{summary['training_frame']['missing_lag_context_rows']:,} rows "
        f"({summary['training_frame']['missing_lag_context_share']:.1%}) carry no validated prior "
        "presidential context and therefore enter the selected design with the zero-fill "
        "compatibility encoding. Historical frame: "
        f"{summary['race_counts']['historical_rows']} races, "
        f"{summary['race_counts']['backcast_races']} backcast, "
        f"{summary['race_counts']['published_modern_races']} published modern (2018/2022).",
        "",
    ]
    drift_note = summary["input_hash_drift"]
    if drift_note:
        sections += [
            "Manifest-recorded input hashes that no longer match disk (recorded, not "
            "adjudicated here):",
            "",
            *[f"- `{row['path']}` (recorded `{row['recorded']}`, disk `{row['disk']}`)"
              for row in drift_note],
            "",
        ]
    else:
        sections += ["Every manifest-recorded input hash matches the bytes on disk.", ""]
    sections += [
        "## Era transportability: backcast versus same-era Alabama fit",
        "",
        "The published specification and alpha are fitted on the 412-race Alabama frame itself "
        "(pooled 1994-2014) to give a **same-era descriptive comparator**. It shares the "
        "specification but not the training data, so a level difference is expected: the modern "
        "fit extrapolates `years_since_2016` (training support 2-8 years) to -22…-2 years, while "
        "the era fit estimates that term inside the historical window. Correlation and sign "
        "agreement describe whether the two residuals order races alike; the difference "
        "distribution describes the level shift.",
        "",
        "### Per-cycle comparison",
        "",
        markdown_table(era_by_cycle, [
            ("cycle", "Cycle"), ("n", "Races"), ("backcast_mean_war", "Backcast mean WAR"),
            ("same_era_mean_war", "Same-era mean WAR"), ("pearson", "Pearson"),
            ("spearman", "Spearman"), ("mae", "MAE of difference"),
            ("mean_diff", "Mean diff"), ("median_diff", "Median diff"),
            ("p05_diff", "p05 diff"), ("p95_diff", "p95 diff"),
            ("max_abs_diff", "Max abs diff"),
            ("sign_change_share", "Sign change share"),
        ]),
        "",
        f"Overall: Pearson {_fmt(overall_era.pearson)} / Spearman {_fmt(overall_era.spearman)}, "
        f"MAE of the difference {_fmt(overall_era.mae)} points, sign agreement "
        f"{_fmt(1 - overall_era.sign_change_share)}.",
        "",
        "## Leave-one-era-out: 1994-2006 versus 2010-2014",
        "",
        "Each half is fitted separately with the published specification and alpha; the table "
        "scores the held-out half against the backcast. Coefficient drift on the structural "
        "terms shows how unstable the in-era relationship is between the two halves. Direction "
        "matters: a fit on the shorter 2010-2014 window extrapolates its `years_since_2016` "
        "trend 8-20 years back, so that direction is itself an extrapolation and its MAE and "
        "maximum difference are not a clean transportability estimate.",
        "",
        markdown_table(era_leaveout, [
            ("fit_era", "Fit era"), ("score_era", "Scored era"), ("fit_races", "Fit races"),
            ("n", "Scored"), ("pearson", "Pearson"), ("spearman", "Spearman"),
            ("mae", "MAE of difference"), ("mean_diff", "Mean diff"),
            ("max_abs_diff", "Max abs diff"), ("sign_change_share", "Sign change share"),
        ]),
        "",
        "### Coefficients and era drift (structural terms)",
        "",
        markdown_table(structural, [
            ("feature", "Feature"), ("coefficient_modern_backcast", "Modern backcast"),
            ("coefficient_historical_pooled_1994_2014", "Era pooled"),
            ("coefficient_historical_1994_2006", "1994-2006"),
            ("coefficient_historical_2010_2014", "2010-2014"),
            ("era_drift", "Era drift"), ("era_comparable", "Era-comparable"),
        ]),
        "",
    ]
    if len(comparable):
        top = comparable.iloc[0]
        sections += [
            f"Largest era drift among era-comparable structural terms: `{top.feature}` "
            f"{_fmt(top.era_drift)} (1994-2006 {_fmt(top.coefficient_historical_1994_2006)} to "
            f"2010-2014 {_fmt(top.coefficient_historical_2010_2014)}; pooled "
            f"{_fmt(top.coefficient_historical_pooled_1994_2014)}, modern backcast "
            f"{_fmt(top.coefficient_modern_backcast)}). Terms whose column is constant inside an "
            "era window are marked not era-comparable and their coefficients are not identified "
            "there. Because the design keeps every categorical level, complementary dummy pairs "
            "(`chamber_lower`/`chamber_upper`, "
            "`baseline_office_family_federal_composite`/`state_composite`) carry mirrored "
            "coefficients; each mirrored pair is one degree of freedom, not two.",
            "",
        ]
    sections += [
        "### Lag-term coefficients",
        "",
        markdown_table(drift[drift.term_family.eq("lag")], [
            ("feature", "Feature"), ("coefficient_modern_backcast", "Modern backcast"),
            ("coefficient_historical_pooled_1994_2014", "Era pooled"),
            ("coefficient_historical_1994_2006", "1994-2006"),
            ("coefficient_historical_2010_2014", "2010-2014"),
            ("era_drift", "Era drift"), ("era_comparable", "Era-comparable"),
        ]),
        "",
        "## Missing lag context: the zero-fill encoding",
        "",
        f"{summary['race_counts']['missing_lag_context_races']} of the 412 backcast races carry "
        "`lag_context_available == False`. Their three lag design columns are set to 0.0, so "
        "their published `fitted_lag_component` is exactly zero by construction while the "
        "encoding still influenced the modern coefficients those rows are scored with. "
        "`war_no_lag_spec` refits the `fundamentals_no_lag` design on the modern frame; "
        "`war_lag_available_fit` refits the published design on modern rows with validated lag "
        "context only. Both are recomputed alternatives, not replacement WAR. Missing-context "
        "counts by cycle: "
        + ", ".join(
            f"{cycle} {count}"
            for cycle, count in missing_rows.cycle.value_counts().sort_index().items()
        )
        + ".",
        "",
        f"Across those races the `no_lag_spec` delta ranges "
        f"{summary['headline']['missing_lag']['no_lag_spec']['min_diff']:+.3f} to "
        f"{summary['headline']['missing_lag']['no_lag_spec']['max_diff']:+.3f} WAR points (mean "
        f"{summary['headline']['missing_lag']['no_lag_spec']['mean_diff']:+.3f}), while "
        f"`lag_available_fit` ranges "
        f"{summary['headline']['missing_lag']['lag_available_fit']['min_diff']:+.3f} to "
        f"{summary['headline']['missing_lag']['lag_available_fit']['max_diff']:+.3f} (mean "
        f"{summary['headline']['missing_lag']['lag_available_fit']['mean_diff']:+.3f}). The "
        "larger swing comes from changing which modern rows estimate the base coefficients, so "
        "the encoding's influence is not confined to the zero entries of those 18 races.",
        "",
        "### The 18 no-context races",
        "",
        markdown_table(missing_rows, [
            ("cycle", "Cycle"), ("chamber", "Chamber"), ("district", "District"),
            ("prior_presidential_margin", "Prior pres margin"),
            ("raw_gap", "Raw gap"), ("war", "Backcast WAR"),
            ("war_no_lag_spec", "No-lag WAR"), ("diff_no_lag_spec", "No-lag diff"),
            ("war_party", "Party"), ("war_party_no_lag_spec", "No-lag party"),
            ("war_lag_available_fit", "Lag-avail WAR"),
            ("diff_lag_available_fit", "Lag-avail diff"),
        ]),
        "",
        "### Summary by cycle and lag-context status",
        "",
        *[
            item
            for name, title in (
                ("no_lag_spec", "fundamentals_no_lag design fitted on the modern frame"),
                ("lag_available_fit", "published design fitted on modern lag-available rows only"),
            )
            for item in (
                f"#### `{name}` ({title})",
                "",
                markdown_table(
                    missing_summary,
                    [("cycle", "Cycle"), ("lag_context_available", "Lag context"), ("n", "Races"),
                     (f"{name}_n", "Scored"), (f"{name}_mean_diff", "Mean diff"),
                     (f"{name}_mae", "MAE"), (f"{name}_max_abs_diff", "Max abs diff"),
                     (f"{name}_sign_change_share", "Sign change share"),
                     (f"{name}_sign_changes", "Sign changes"),
                     (f"{name}_pearson", "Pearson"), (f"{name}_spearman", "Spearman")],
                ),
                "",
            )
        ],
    ] + [
        "## Bootstrap uncertainty of the backcast expected gap",
        "",
        f"{summary['bootstrap']['draws']} within-cycle training-bootstrap draws (seed "
        f"{summary['bootstrap']['seed']}): {summary['bootstrap']['resampling']}. SE is the "
        "standard deviation of the backcast expected gap across draws; the WAR interval "
        "subtracts the 5th/95th expected-gap percentiles from the observed raw gap. This is "
        "training-sample variability of the descriptive fit, not a forecast interval.",
        "",
        markdown_table(
            bootstrap_summary[bootstrap_summary.group_type.isin(["all", "cycle"])],
            [("group", "Cycle"), ("n", "Races"), ("median_expected_gap_se", "Median SE"),
             ("mean_expected_gap_se", "Mean SE"),
             ("median_war_interval_width", "Median WAR interval width"),
             ("share_war_interval_excludes_zero", "Interval excludes zero"),
             ("share_war_party_stable_all_draws", "Stable party"),
             ("mean_war_party_draw_agreement", "Mean party agreement")],
        ),
        "",
        "## Headline numbers",
        "",
        f"- Same-era versus backcast, per cycle (Pearson / sign agreement): "
        + "; ".join(
            f"{row.cycle} {_fmt(row.pearson)} / {_fmt(1 - row.sign_change_share)}"
            for row in era_by_cycle[era_by_cycle.cycle.ne("all")].itertuples()
        )
        + ".",
        f"- Overall same-era comparison: MAE {_fmt(overall_era.mae)} points, differences "
        f"{_fmt(overall_era.p05_diff)} to {_fmt(overall_era.p95_diff)} (5th-95th), mean "
        f"{_fmt(overall_era.mean_diff)}.",
        "- Largest era coefficient drifts (structural, era-comparable): "
        + "; ".join(
            f"`{row.feature}` {_fmt(row.era_drift)}" for row in comparable.head(3).itertuples()
        ) + ".",
        f"- 18 no-context races, `no_lag_spec` versus backcast: max |delta| "
        f"{_fmt(summary['headline']['missing_lag']['no_lag_spec']['max_abs_diff'])} points, mean "
        f"{_fmt(summary['headline']['missing_lag']['no_lag_spec']['mean_diff'])}, "
        f"{summary['headline']['missing_lag']['no_lag_spec']['sign_changes']} sign changes; "
        f"`lag_available_fit`: max |delta| "
        f"{_fmt(summary['headline']['missing_lag']['lag_available_fit']['max_abs_diff'])}, "
        f"{summary['headline']['missing_lag']['lag_available_fit']['sign_changes']} sign changes.",
        f"- Bootstrap median SE by cycle: "
        + ", ".join(
            f"{cycle} {_fmt(value)}"
            for cycle, value in summary['bootstrap']['median_expected_gap_se_by_cycle'].items()
        ) + ".",
        "",
        "## What this audit does not establish",
        "",
        "- **No predictive validation.** The same-era and out-of-era fits are descriptive "
        "in-sample or held-out-half comparators on the same historical race universe; nothing "
        "here is a forward, as-of or prospective test, and the backcast remains an "
        "extrapolation of a modern relationship.",
        "- **No recertification.** Passing the parity gate proves the reconstruction reproduces "
        "the published backcast values from the declared inputs; it does not re-approve the run, "
        "the modern residual source, the plan vintages or the baseline provenance.",
        "- **No replacement contract.** The same-era fit is not an alternative WAR definition "
        "and its residuals are not candidate-quality measures; the published backcast label "
        "stands until a separately authorized decision replaces it.",
        "- **No lag identification.** The 18 no-context races cannot identify a lag "
        "contribution; the alternatives measure how much their WAR depends on the encoding, not "
        "what the correct prior-presidential context would be.",
        "- **Bootstrap limits.** The intervals exclude specification and alpha selection "
        "uncertainty, baseline measurement error and outcome noise, and the bootstrap resamples "
        "training rows, so it does not describe uncertainty in the historical frame.",
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
                        help="published historical run directory")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--expected-run-id", default=EXPECTED_HISTORICAL_RUN_ID)
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    if args.draws < 2:
        parser.error("--draws must be at least 2")

    started = time.perf_counter()
    manifest, published = load_published_run(args.run_dir, args.expected_run_id)
    historical = historical_builder.prepare_historical_races()
    modern, warehouse_run = v2.load_training()
    if str(manifest.get("warehouse_build_run_id")) != str(warehouse_run["build_run_id"]):
        raise ValueError(
            f"Live warehouse build run {warehouse_run['build_run_id']!r} differs from the "
            f"published manifest {manifest.get('warehouse_build_run_id')!r}; the audit cannot "
            "bind to this run"
        )
    modern = v2.attach_lag_context(modern)
    if not modern.cycle.gt(2016).all():
        raise ValueError("Modern training frame leaked a pre-2017 race")

    combined = pd.concat([modern, historical], ignore_index=True, sort=False)
    designs, lag_columns = v2.design_matrices(combined)
    design = designs[SPECIFICATION]
    modern_rows = len(modern)

    reproduced, reproduced_design, modern_model = reproduce_backcast(
        historical.reset_index(drop=True),
        design,
        modern_rows,
        modern.direct_overperformance.to_numpy(float),
        lag_columns,
    )
    backcast_mask = reproduced.cycle.le(BACKCAST_MAX_CYCLE).to_numpy(bool)
    published_all = align_published(published, reproduced)
    input_parity = parity_check(
        published_all, reproduced[RACE_KEYS + ["raw_gap"]], {"raw_gap": "raw_gap"}
    )
    published_backcast = published_all[backcast_mask].reset_index(drop=True)
    backcast = reproduced[backcast_mask].reset_index(drop=True)
    historical_design = reproduced_design[backcast_mask].reset_index(drop=True)
    parity = {
        "raw_gap_all_509_races": input_parity["raw_gap"],
        **parity_check(
            published_backcast,
            backcast[RACE_KEYS + list(PARITY_REPRODUCED_COLUMNS)],
            PARITY_PAIRS,
        ),
    }
    parity_frame = normalize_race_keys(backcast[RACE_KEYS].copy())
    for published_column, reproduced_column in PARITY_PAIRS.items():
        parity_frame[f"published_{published_column}"] = published_backcast[
            published_column
        ].to_numpy(float)
        parity_frame[f"reproduced_{reproduced_column}"] = backcast[
            reproduced_column
        ].to_numpy(float)
        parity_frame[f"abs_difference_{published_column}"] = np.abs(
            published_backcast[published_column].to_numpy(float)
            - backcast[reproduced_column].to_numpy(float)
        )

    era_by_race, era_by_cycle = era_transportability(backcast, historical_design)
    era_leaveout = leave_one_era_out(backcast, historical_design)
    drift = coefficient_drift_table(
        historical_design,
        backcast.direct_overperformance.to_numpy(float),
        backcast.cycle.to_numpy(),
        model_coefficients(modern_model, list(design.columns)),
        lag_columns,
    )
    missing_by_race, missing_summary = missing_lag_sensitivity(
        backcast,
        designs,
        modern_rows,
        modern.direct_overperformance.to_numpy(float),
        modern.lag_context_available.to_numpy(bool),
        lag_columns,
        tail_mask=backcast_mask,
    )
    bootstrap_by_race, bootstrap_summary = bootstrap_backcast(
        backcast,
        design.iloc[:modern_rows],
        modern.direct_overperformance.to_numpy(float),
        modern.cycle.to_numpy(),
        historical_design,
        draws=args.draws,
        seed=args.seed,
    )

    missing_share = float((~modern.lag_context_available.astype(bool)).mean())
    training_frame = {
        "rows": int(len(modern)),
        "cycles": [int(cycle) for cycle in sorted(modern.cycle.unique())],
        "states": sorted(modern.state_code.astype(str).unique()),
        "missing_lag_context_rows": int((~modern.lag_context_available.astype(bool)).sum()),
        "missing_lag_context_share": missing_share,
    }
    configuration = {
        "specification": SPECIFICATION,
        "alpha": ALPHA,
        "no_lag_specification": NO_LAG_SPECIFICATION,
        "era_windows": {name: list(cycles) for name, cycles in ERAS.items()},
        "bootstrap_draws": args.draws,
        "bootstrap_seed": args.seed,
        "parity_tolerance": PARITY_TOLERANCE,
        "even_tolerance": EVEN_TOLERANCE,
    }
    counts = {
        "historical_rows": int(len(historical)),
        "backcast_races": int(backcast_mask.sum()),
        "published_modern_races": int((~backcast_mask).sum()),
        "modern_training_rows": modern_rows,
        "missing_lag_context_races": int((~backcast.lag_context_available.astype(bool)).sum()),
        "publication_export_modified": False,
        "warehouse_writes": 0,
    }
    summary = build_summary(
        manifest, warehouse_run, args.run_dir, parity, configuration, counts, training_frame,
        era_by_cycle, era_leaveout, drift, missing_summary, missing_by_race, bootstrap_summary,
        input_hash_drift(manifest), args.draws, args.seed, time.perf_counter() - started,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = {
        "backcast_parity_by_race.csv": parity_frame,
        "era_transportability_by_race.csv": era_by_race,
        "era_transportability_summary.csv": era_by_cycle,
        "era_leaveout_summary.csv": era_leaveout,
        "era_leaveout_coefficients.csv": drift,
        "missing_lag_by_race.csv": missing_by_race,
        "missing_lag_summary.csv": missing_summary,
        "bootstrap_backcast_by_race.csv": bootstrap_by_race,
        "bootstrap_backcast_summary.csv": bootstrap_summary,
    }
    for name, frame in frames.items():
        frame = frame.copy()
        frame.insert(0, "historical_war_run_id", manifest["historical_war_run_id"])
        frame.to_csv(output_dir / name, index=False)
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    (output_dir / "summary.json").write_text(payload, encoding="utf-8")
    Path(args.report_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_json).write_text(payload, encoding="utf-8")
    write_report(
        Path(args.report), summary, era_by_cycle, era_leaveout, drift, missing_summary,
        missing_by_race, bootstrap_summary, output_dir,
    )

    missing_headline = summary["headline"]["missing_lag"]
    print(
        f"Alabama backcast audit: run={summary['historical_war_run_id']} "
        f"parity={summary['parity_gate']} backcast_races={counts['backcast_races']} "
        f"missing_lag={counts['missing_lag_context_races']} "
        f"era_all_pearson={summary['headline']['era_transportability_overall']['pearson']:.3f} "
        f"no_lag_max_abs_diff={missing_headline['no_lag_spec']['max_abs_diff']:.3f} "
        f"no_lag_sign_changes={missing_headline['no_lag_spec']['sign_changes']} "
        f"runtime={summary['runtime_seconds']}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
