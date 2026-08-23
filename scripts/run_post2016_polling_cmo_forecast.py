#!/usr/bin/env python3
"""Test a post-2016 polling-anchored CMO forecast for Alabama.

The experiment treats the polling-implied change in the national two-party
margin as the federal result that would otherwise anchor Direct CMO.  It then
models the remaining legislative-minus-federal gap using only post-2016
Alabama elections and explicitly separated generic lag, incumbency, and
fundraising terms.

This is an experimental forecast family.  Historical finance uses full-cycle
FCPA totals while 2026 finance is an in-progress snapshot, and only one true
forward Alabama holdout (train 2018, test 2022) is available.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, brier_score_loss, mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from build_historical_silver_generic_ballot import (
    POP_WEIGHT,
    PRIOR_PRES_MARGIN,
    match_ratings,
)


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data/processed/war"
ELECTIONS = ROOT / "data/processed/elections"
IDEOLOGY = ROOT / "data/processed/ideology"
POLLING = ROOT / "data/processed/polling"
RAW_POLLING = ROOT / "data/raw/polling"
PRESIDENTIAL = ROOT / "data/processed/presidential"
OUT = ROOT / "data/processed/forecast_calibration"
DOC = ROOT / "project_docs/model/POST2016_POLLING_CMO_EXPERIMENT.md"

SEED = 20260822
RIDGE_ALPHA = 10.0
FINANCE_SCALE = 50_000.0
POLL_WINDOW_DAYS = 21
ELIGIBLE_SILVER_GRADES = {"A+", "A", "A-", "A/B", "B+", "B"}
KEYS = ["cycle", "chamber", "district"]
PROBABILITY_DF = 5.0
PROBABILITY_SCALE = 5.75
FINANCE_STRUCTURE_FEATURES = [
    "incumbency_balance",
    "polling_federal_margin",
    "abs_polling_federal_margin",
]
PARTIAL_ORTHOGONAL_WEIGHTS = (0.25, 0.50, 0.75)

FINANCE_PANEL = WAR / "fcpa_fundraising_experiment_panel.csv"
FINANCE_CANDIDATES = WAR / "fcpa_candidate_cycle_finance.csv"
CANONICAL_CANDIDATES = ELECTIONS / "canonical_cmo_candidates.csv"
IDENTITY_CROSSWALK = IDEOLOGY / "candidate_legislator_identity_crosswalk.csv"
RAW_POLLS = RAW_POLLING / "fivethirtyeight_raw_polls.csv"
SILVER_RATINGS = RAW_POLLING / "nate_silver_pollster_ratings.csv"
ROSTER = WAR / "2026_final_candidate_roster.csv"
INCUMBENCY_2026 = WAR / "2026_candidate_incumbency.csv"
POLL_BASELINE_2026 = WAR / "2026_poll_adjusted_baseline.csv"
CURRENT_ENVIRONMENT = POLLING / "votehub_silver_bplus_topline_environment.csv"

SPECS: dict[str, list[str] | None] = {
    "polling_federal_only": None,
    "polling_federal_plus_generic_lag": [],
    "polling_federal_plus_incumbency": ["incumbency_balance"],
    "polling_federal_plus_fundraising": ["fundraising_gap_log50"],
    "polling_federal_plus_incumbency_fundraising": [
        "incumbency_balance",
        "fundraising_gap_log50",
    ],
    "polling_federal_plus_orthogonal_fundraising": ["fundraising_gap_residualized"],
    "polling_federal_plus_incumbency_orthogonal_fundraising": [
        "incumbency_balance",
        "fundraising_gap_residualized",
    ],
    "polling_federal_plus_within_cycle_orthogonal_fundraising": [
        "fundraising_gap_within_cycle_residualized",
    ],
    "polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising": [
        "incumbency_balance",
        "fundraising_gap_within_cycle_residualized",
    ],
    "polling_federal_plus_incumbency_partial_orthogonal25": [
        "incumbency_balance", "fundraising_gap_partial_orthogonal25",
    ],
    "polling_federal_plus_incumbency_partial_orthogonal50": [
        "incumbency_balance", "fundraising_gap_partial_orthogonal50",
    ],
    "polling_federal_plus_incumbency_partial_orthogonal75": [
        "incumbency_balance", "fundraising_gap_partial_orthogonal75",
    ],
    "polling_federal_plus_incumbency_viability": [
        "incumbency_balance",
        "finance_viability_gap_25k",
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    if "," in text:
        last, rest = text.split(",", 1)
        text = f"{rest} {last}"
    text = re.sub(r"\b(JR|SR|II|III|IV)\b", " ", text)
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def historical_b_or_better_polling() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rebuild final generic-ballot snapshots using the current B-or-better gate."""
    polls = pd.read_csv(RAW_POLLS, low_memory=False)
    ratings = pd.read_csv(SILVER_RATINGS)
    ratings["grade_clean"] = ratings.Grade.astype(str).str.split("@@").str[0]
    ratings = ratings[ratings.grade_clean.isin(ELIGIBLE_SILVER_GRADES)].copy()
    polls = polls[
        polls.type_simple.eq("House-G-US")
        & polls.cycle.isin([2018, 2022])
        & polls.partisan.isna()
    ].copy()
    polls["polldate"] = pd.to_datetime(polls.polldate)
    polls["electiondate"] = pd.to_datetime(polls.electiondate)
    crosswalk = match_ratings(polls.pollster, ratings)
    selected = polls.merge(crosswalk, on="pollster", how="inner", validate="many_to_one")
    selected["days_before_election"] = (selected.electiondate - selected.polldate).dt.days
    selected = selected[selected.days_before_election.between(0, POLL_WINDOW_DAYS)].copy()
    selected["dem_two_party_margin"] = (
        100.0 * (selected.cand1_pct - selected.cand2_pct) / (selected.cand1_pct + selected.cand2_pct)
    )
    selected = selected.sort_values(["cycle", "pollster", "polldate", "samplesize"]).drop_duplicates(
        ["cycle", "pollster"], keep="last"
    )
    selected["weight"] = (
        selected.get("population", pd.Series("rv", index=selected.index))
        .astype(str).str.lower().map(POP_WEIGHT).fillna(0.7)
    )
    rows = []
    for cycle, group in selected.groupby("cycle", sort=True):
        final_margin = float(np.average(group.dem_two_party_margin, weights=group.weight))
        prior_margin = float(PRIOR_PRES_MARGIN[int(cycle)])
        rows.append({
            "cycle": int(cycle),
            "eligible_pollsters": int(group.pollster.nunique()),
            "final_poll_margin": final_margin,
            "prior_presidential_margin": prior_margin,
            "poll_implied_national_swing": final_margin - prior_margin,
            "earliest_final_poll": str(group.polldate.min().date()),
            "latest_final_poll": str(group.polldate.max().date()),
            "minimum_silver_grade": "B",
            "poll_window_days": POLL_WINDOW_DAYS,
        })
    summary = pd.DataFrame(rows).sort_values("cycle").reset_index(drop=True)
    if set(summary.cycle) != {2018, 2022}:
        raise RuntimeError("Historical polling gate did not produce both 2018 and 2022")
    return summary, selected.sort_values(["cycle", "pollster"]).reset_index(drop=True)


def inferred_2022_incumbency() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Infer 2022 incumbency from resolved names of 2018 winners.

    District equality is deliberately not required because the 2022 election
    followed redistricting.  A candidate must match a 2018 winner in the same
    chamber and party by exact normalized resolved name.
    """
    candidates = pd.read_csv(CANONICAL_CANDIDATES)
    identities = pd.read_csv(IDENTITY_CROSSWALK, usecols=["canonical_candidate_id", "resolved_name"])
    candidates = candidates.merge(
        identities, on="canonical_candidate_id", how="left", validate="one_to_one"
    )
    candidates["resolved_name"] = candidates.resolved_name.fillna(candidates.canonical_name)
    candidates["normalized_resolved_name"] = candidates.resolved_name.map(normalized_name)
    winners = candidates[
        candidates.year.eq(2018) & candidates.winner.fillna(False).astype(bool)
    ][["chamber", "canonical_party", "normalized_resolved_name", "resolved_name", "district"]].copy()
    duplicate_winners = winners.duplicated(
        ["chamber", "canonical_party", "normalized_resolved_name"], keep=False
    )
    safe_winners = winners[~duplicate_winners].copy()
    current = candidates[candidates.year.eq(2022)].copy()
    current = current.merge(
        safe_winners.rename(columns={"resolved_name": "prior_winner_name", "district": "prior_district"}),
        on=["chamber", "canonical_party", "normalized_resolved_name"],
        how="left",
        validate="many_to_one",
    )
    current["inferred_incumbent"] = current.prior_winner_name.notna()
    audit = current[[
        "canonical_candidate_id", "chamber", "district", "canonical_party", "resolved_name",
        "inferred_incumbent", "prior_winner_name", "prior_district",
    ]].copy()
    wide = current.pivot_table(
        index=["chamber", "district"], columns="canonical_party",
        values="inferred_incumbent", aggfunc="max", fill_value=False,
    ).reset_index()
    for party in ("D", "R"):
        if party not in wide:
            wide[party] = False
    wide = wide.rename(columns={"D": "dem_incumbent_inferred", "R": "rep_incumbent_inferred"})
    return wide, audit


def add_finance_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["fundraising_gap_log50"] = (
        np.log1p(out.dem_fundraising.clip(lower=0) / FINANCE_SCALE)
        - np.log1p(out.rep_fundraising.clip(lower=0) / FINANCE_SCALE)
    )
    out["finance_viability_gap_25k"] = (
        out.dem_fundraising.ge(25_000).astype(int) - out.rep_fundraising.ge(25_000).astype(int)
    )
    return out


def historical_panel(polling: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = pd.read_csv(FINANCE_PANEL, low_memory=False)
    panel = panel[panel.cycle.isin([2018, 2022])].copy()
    incumbency, identity_audit = inferred_2022_incumbency()
    panel = panel.merge(incumbency, on=["chamber", "district"], how="left", validate="many_to_one")
    is_2022 = panel.cycle.eq(2022)
    panel.loc[is_2022, "dem_incumbent_i"] = panel.loc[is_2022, "dem_incumbent_inferred"].fillna(False).astype(int)
    panel.loc[is_2022, "rep_incumbent_i"] = panel.loc[is_2022, "rep_incumbent_inferred"].fillna(False).astype(int)
    panel["incumbency_balance"] = panel.dem_incumbent_i.astype(int) - panel.rep_incumbent_i.astype(int)
    panel = add_finance_features(panel)
    panel = panel.merge(
        polling[["cycle", "eligible_pollsters", "final_poll_margin", "poll_implied_national_swing"]],
        on="cycle", how="left", validate="many_to_one",
    )
    panel["polling_federal_margin"] = panel.prior_pres_dem_margin + panel.poll_implied_national_swing
    panel["abs_polling_federal_margin"] = panel.polling_federal_margin.abs()
    panel["polling_cmo_target"] = panel.legislative_dem_margin - panel.polling_federal_margin
    panel["post2016_training_eligible"] = panel.cycle.ge(2018)
    panel = panel.sort_values(KEYS).reset_index(drop=True)
    required = [
        "legislative_dem_margin", "polling_federal_margin", "incumbency_balance",
        "fundraising_gap_log50", "finance_viability_gap_25k",
    ]
    if panel[required].isna().any().any():
        raise RuntimeError("Post-2016 experiment panel contains missing required model values")
    return panel, identity_audit


def design(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    columns = ["senate_i", *features]
    out = pd.DataFrame(index=frame.index)
    out["senate_i"] = frame.chamber.eq("senate").astype(float)
    for feature in features:
        out[feature] = pd.to_numeric(frame[feature], errors="raise").astype(float)
    return out[columns]


def fit_adjustment(frame: pd.DataFrame, features: list[str]) -> Pipeline:
    model = Pipeline([
        ("scale", StandardScaler()),
        ("ridge", Ridge(alpha=RIDGE_ALPHA, fit_intercept=True)),
    ])
    model.fit(design(frame, features), frame.polling_cmo_target)
    return model


def predict_adjustment(model: Pipeline, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    return model.predict(design(frame, features))


def fit_finance_structure(frame: pd.DataFrame) -> Pipeline:
    """Predict the normal fundraising gap without using election outcomes."""
    model = Pipeline([
        ("scale", StandardScaler()),
        ("ridge", Ridge(alpha=RIDGE_ALPHA, fit_intercept=True)),
    ])
    model.fit(
        design(frame, FINANCE_STRUCTURE_FEATURES),
        frame.fundraising_gap_log50,
    )
    return model


def attach_orthogonal_fundraising(
    fit_frame: pd.DataFrame,
    apply_frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, Pipeline]:
    """Fit on ``fit_frame`` and attach unexpected fundraising to both frames."""
    model = fit_finance_structure(fit_frame)
    fit = fit_frame.copy()
    apply = apply_frame.copy()
    fit["fundraising_gap_structural_expectation"] = model.predict(
        design(fit, FINANCE_STRUCTURE_FEATURES)
    )
    apply["fundraising_gap_structural_expectation"] = model.predict(
        design(apply, FINANCE_STRUCTURE_FEATURES)
    )
    fit["fundraising_gap_residualized"] = (
        fit.fundraising_gap_log50 - fit.fundraising_gap_structural_expectation
    )
    apply["fundraising_gap_residualized"] = (
        apply.fundraising_gap_log50 - apply.fundraising_gap_structural_expectation
    )
    for weight in PARTIAL_ORTHOGONAL_WEIGHTS:
        suffix = int(weight * 100)
        fit[f"fundraising_gap_partial_orthogonal{suffix}"] = (
            fit.fundraising_gap_log50 - weight * fit.fundraising_gap_structural_expectation
        )
        apply[f"fundraising_gap_partial_orthogonal{suffix}"] = (
            apply.fundraising_gap_log50 - weight * apply.fundraising_gap_structural_expectation
        )
    return fit, apply, model


def attach_within_cycle_orthogonal_fundraising(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[int, Pipeline]]:
    """Residualize finance within each cycle using no election outcomes."""
    out = frame.copy()
    out["fundraising_gap_within_cycle_expectation"] = np.nan
    out["fundraising_gap_within_cycle_residualized"] = np.nan
    models: dict[int, Pipeline] = {}
    for cycle, group in frame.groupby("cycle", sort=True):
        scored, _, model = attach_orthogonal_fundraising(group, group)
        out.loc[group.index, "fundraising_gap_within_cycle_expectation"] = scored[
            "fundraising_gap_structural_expectation"
        ].to_numpy()
        out.loc[group.index, "fundraising_gap_within_cycle_residualized"] = scored[
            "fundraising_gap_residualized"
        ].to_numpy()
        models[int(cycle)] = model
    return out, models


def probability(margin: np.ndarray | pd.Series) -> np.ndarray:
    return student_t.cdf(np.asarray(margin, dtype=float) / PROBABILITY_SCALE, df=PROBABILITY_DF)


def forward_test(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Pipeline]]:
    train = panel[panel.cycle.eq(2018)].copy()
    test = panel[panel.cycle.eq(2022)].copy()
    train, test, _ = attach_orthogonal_fundraising(train, test)
    train, _ = attach_within_cycle_orthogonal_fundraising(train)
    test, _ = attach_within_cycle_orthogonal_fundraising(test)
    models: dict[str, Pipeline] = {}
    rows = []
    for name, features in SPECS.items():
        if features is None:
            adjustment = np.zeros(len(test))
        else:
            fitted = fit_adjustment(train, features)
            models[name] = fitted
            adjustment = predict_adjustment(fitted, test, features)
        predicted = test.polling_federal_margin.to_numpy() + adjustment
        probs = probability(predicted)
        for race, adj, estimate, prob in zip(test.itertuples(index=False), adjustment, predicted, probs):
            rows.append({
                "specification": name,
                "train_cycle": 2018,
                "test_cycle": 2022,
                "train_races": len(train),
                "test_races": len(test),
                "chamber": race.chamber,
                "district": int(race.district),
                "polling_federal_margin": race.polling_federal_margin,
                "actual_legislative_margin": race.legislative_dem_margin,
                "expected_cmo_adjustment": adj,
                "predicted_legislative_margin": estimate,
                "error": race.legislative_dem_margin - estimate,
                "dem_win_probability": prob,
                "actual_dem_win": int(race.legislative_dem_margin > 0),
                "incumbency_balance": race.incumbency_balance,
                "fundraising_gap_log50": race.fundraising_gap_log50,
                "fundraising_gap_structural_expectation": race.fundraising_gap_structural_expectation,
                "fundraising_gap_residualized": race.fundraising_gap_residualized,
                "fundraising_gap_within_cycle_expectation": race.fundraising_gap_within_cycle_expectation,
                "fundraising_gap_within_cycle_residualized": race.fundraising_gap_within_cycle_residualized,
            })
    predictions = pd.DataFrame(rows)
    predictions["absolute_error"] = predictions.error.abs()
    predictions["squared_error"] = predictions.error ** 2
    metrics = []
    baseline = predictions[predictions.specification.eq("polling_federal_only")].set_index(
        ["chamber", "district"]
    ).absolute_error
    for name, group in predictions.groupby("specification", sort=False):
        indexed = group.set_index(["chamber", "district"])
        metrics.append({
            "specification": name,
            "train_cycle": 2018,
            "test_cycle": 2022,
            "train_races": len(train),
            "test_races": len(test),
            "mae": mean_absolute_error(group.actual_legislative_margin, group.predicted_legislative_margin),
            "rmse": mean_squared_error(group.actual_legislative_margin, group.predicted_legislative_margin) ** 0.5,
            "mean_error": group.error.mean(),
            "winner_accuracy": accuracy_score(group.actual_dem_win, group.predicted_legislative_margin.gt(0)),
            "brier": brier_score_loss(group.actual_dem_win, group.dem_win_probability),
            "mae_improvement_vs_polling_federal": (baseline - indexed.absolute_error).mean(),
        })
    return predictions, pd.DataFrame(metrics).sort_values("mae"), models


def bootstrap_comparisons(predictions: pd.DataFrame) -> pd.DataFrame:
    errors = predictions.pivot(
        index=["chamber", "district"], columns="specification", values="absolute_error"
    )
    references = ["polling_federal_only", "polling_federal_plus_incumbency"]
    rng = np.random.default_rng(SEED)
    rows = []
    targets = [
        "polling_federal_plus_incumbency_fundraising",
        "polling_federal_plus_incumbency_orthogonal_fundraising",
        "polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising",
    ]
    for target in targets:
        for reference in references:
            delta = (errors[reference] - errors[target]).to_numpy()
            draws = rng.choice(delta, size=(20_000, len(delta)), replace=True).mean(axis=1)
            rows.append({
                "target": target,
                "reference": reference,
                "paired_mean_mae_improvement": delta.mean(),
                "bootstrap_ci_low": np.quantile(draws, 0.025),
                "bootstrap_ci_high": np.quantile(draws, 0.975),
                "bootstrap_probability_improvement": np.mean(draws > 0),
                "test_races": len(delta),
            })
    return pd.DataFrame(rows)


def shrinkage_sensitivity(predictions: pd.DataFrame) -> pd.DataFrame:
    """Evaluate global shrinkage after the sole holdout, as a sensitivity only."""
    rows = []
    targets = [
        "polling_federal_plus_incumbency_fundraising",
        "polling_federal_plus_incumbency_orthogonal_fundraising",
        "polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising",
    ]
    for target in targets:
        combined = predictions[predictions.specification.eq(target)].copy()
        for weight in (0.0, 0.25, 0.50, 0.75, 1.0):
            estimate = combined.polling_federal_margin + weight * combined.expected_cmo_adjustment
            rows.append({
                "specification": target,
                "adjustment_weight": weight,
                "test_cycle": 2022,
                "test_races": len(combined),
                "mae": mean_absolute_error(combined.actual_legislative_margin, estimate),
                "rmse": mean_squared_error(combined.actual_legislative_margin, estimate) ** 0.5,
                "post_holdout_selection_warning": True,
            })
    return pd.DataFrame(rows)


def original_scale_coefficients(
    name: str,
    model: Pipeline,
    features: list[str],
    fit_sample: str,
    fit_races: int,
) -> pd.DataFrame:
    scaler: StandardScaler = model.named_steps["scale"]
    ridge: Ridge = model.named_steps["ridge"]
    names = ["senate_i", *features]
    coefficients = ridge.coef_ / scaler.scale_
    intercept = ridge.intercept_ - np.sum(ridge.coef_ * scaler.mean_ / scaler.scale_)
    rows = [{"specification": name, "fit_sample": fit_sample, "fit_races": fit_races,
             "term": "intercept_house_generic_lag", "coefficient": intercept}]
    rows.extend({"specification": name, "fit_sample": fit_sample, "fit_races": fit_races,
                 "term": term, "coefficient": value}
                for term, value in zip(names, coefficients))
    return pd.DataFrame(rows)


def subgroup_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for specification, spec_group in predictions.groupby("specification", sort=False):
        groups = [("all", "all", spec_group)]
        groups.extend(("chamber", str(value), group) for value, group in spec_group.groupby("chamber"))
        groups.extend(
            ("incumbency_balance", str(int(value)), group)
            for value, group in spec_group.groupby("incumbency_balance")
        )
        for dimension, value, group in groups:
            rows.append({
                "specification": specification,
                "dimension": dimension,
                "value": value,
                "races": len(group),
                "mae": group.absolute_error.mean(),
                "mean_error": group.error.mean(),
                "winner_accuracy": (group.predicted_legislative_margin.gt(0) == group.actual_dem_win).mean(),
            })
    return pd.DataFrame(rows)


def finance_structure_diagnostics(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = panel[panel.cycle.eq(2018)].copy()
    test = panel[panel.cycle.eq(2022)].copy()
    train_scored, test_scored, forward_model = attach_orthogonal_fundraising(train, test)
    test_within_cycle, _ = attach_within_cycle_orthogonal_fundraising(test)
    test_within_cycle["fundraising_gap_structural_expectation"] = (
        test_within_cycle.fundraising_gap_within_cycle_expectation
    )
    test_within_cycle["fundraising_gap_residualized"] = (
        test_within_cycle.fundraising_gap_within_cycle_residualized
    )
    rows = []
    for label, frame in (
        ("2018_in_sample", train_scored),
        ("2022_forward", test_scored),
        ("2022_within_cycle_covariate_fit", test_within_cycle),
    ):
        rows.append({
            "sample": label,
            "races": len(frame),
            "fundraising_gap_mae": mean_absolute_error(
                frame.fundraising_gap_log50, frame.fundraising_gap_structural_expectation
            ),
            "fundraising_gap_rmse": mean_squared_error(
                frame.fundraising_gap_log50, frame.fundraising_gap_structural_expectation
            ) ** 0.5,
            "fundraising_gap_r2": r2_score(
                frame.fundraising_gap_log50, frame.fundraising_gap_structural_expectation
            ),
            "residual_correlation_incumbency": frame.fundraising_gap_residualized.corr(
                frame.incumbency_balance
            ),
            "residual_correlation_partisanship": frame.fundraising_gap_residualized.corr(
                frame.polling_federal_margin
            ),
            "residual_correlation_competitiveness": frame.fundraising_gap_residualized.corr(
                frame.abs_polling_federal_margin
            ),
        })
    coefficient_frames = [
        original_scale_coefficients(
            "fundraising_structure_model", forward_model, FINANCE_STRUCTURE_FEATURES,
            "cycle_2018_forward_fit", len(train),
        )
    ]
    for cycle, frame in panel.groupby("cycle", sort=True):
        fitted = fit_finance_structure(frame)
        coefficient_frames.append(original_scale_coefficients(
            "fundraising_structure_model", fitted, FINANCE_STRUCTURE_FEATURES,
            f"cycle_{int(cycle)}", len(frame),
        ))
    pooled = fit_finance_structure(panel)
    coefficient_frames.append(original_scale_coefficients(
        "fundraising_structure_model", pooled, FINANCE_STRUCTURE_FEATURES,
        "pooled_2018_2022", len(panel),
    ))
    return pd.DataFrame(rows), pd.concat(coefficient_frames, ignore_index=True)


def final_models(panel: pd.DataFrame) -> dict[str, Pipeline]:
    return {
        name: fit_adjustment(panel, features)
        for name, features in SPECS.items() if features is not None
    }


def prospective_finance(eligible: pd.DataFrame) -> pd.DataFrame:
    finance = pd.read_csv(FINANCE_CANDIDATES)
    finance = finance[finance.cycle.eq(2026) & finance.party.isin(["D", "R"])].copy()
    finance["usable"] = ~finance.aggregation_status.eq("multiple_active_pcc_records_review")
    values = finance.pivot_table(
        index=["chamber", "district"], columns="party", values="fundraising_total", aggfunc="first"
    )
    usable = finance.pivot_table(
        index=["chamber", "district"], columns="party", values="usable", aggfunc="max"
    )
    status = finance.pivot_table(
        index=["chamber", "district"], columns="party", values="aggregation_status", aggfunc="first"
    )
    result = eligible.copy().merge(values.reset_index(), on=["chamber", "district"], how="left")
    use = eligible.copy().merge(usable.reset_index(), on=["chamber", "district"], how="left")
    statuses = eligible.copy().merge(status.reset_index(), on=["chamber", "district"], how="left")
    for party in ("D", "R"):
        if party not in result:
            result[party] = np.nan
        if party not in use:
            use[party] = False
        if party not in statuses:
            statuses[party] = np.nan
    result = result.rename(columns={"D": "dem_fundraising", "R": "rep_fundraising"})
    result["dem_finance_status"] = statuses["D"]
    result["rep_finance_status"] = statuses["R"]
    result["finance_complete"] = (
        result[["dem_fundraising", "rep_fundraising"]].notna().all(axis=1)
        & use[["D", "R"]].eq(True).all(axis=1)
    )
    result = add_finance_features(result)
    result.loc[~result.finance_complete, ["fundraising_gap_log50", "finance_viability_gap_25k"]] = np.nan
    return result


def prospective_panel() -> pd.DataFrame:
    roster = pd.read_csv(ROSTER)
    counts = roster.pivot_table(
        index=["chamber", "district"], columns="party", values="candidate",
        aggfunc="nunique", fill_value=0,
    ).reset_index()
    eligible = counts[(counts.get("D", 0).eq(1)) & (counts.get("R", 0).eq(1))][["chamber", "district"]]
    baseline = pd.read_csv(POLL_BASELINE_2026)[[
        "chamber", "district", "baseline_2024_pres_dem_margin", "poll_adjusted_dem_margin",
        "uniform_poll_adjusted_dem_margin", "poll_average_as_of",
    ]]
    incumbency = pd.read_csv(INCUMBENCY_2026)
    incumbency = incumbency[incumbency.party.isin(["D", "R"])].pivot_table(
        index=["chamber", "district"], columns="party", values="incumbent",
        aggfunc="max", fill_value=False,
    ).reset_index()
    for party in ("D", "R"):
        if party not in incumbency:
            incumbency[party] = False
    incumbency = incumbency.rename(columns={"D": "dem_incumbent_i", "R": "rep_incumbent_i"})
    finance = prospective_finance(eligible)
    out = (
        eligible.merge(baseline, on=["chamber", "district"], validate="one_to_one")
        .merge(incumbency[["chamber", "district", "dem_incumbent_i", "rep_incumbent_i"]],
               on=["chamber", "district"], validate="one_to_one")
        .merge(finance, on=["chamber", "district"], validate="one_to_one")
    )
    out["cycle"] = 2026
    out["incumbency_balance"] = out.dem_incumbent_i.astype(int) - out.rep_incumbent_i.astype(int)
    environment = pd.read_csv(CURRENT_ENVIRONMENT).iloc[0]
    out["current_national_poll_margin"] = float(environment.dem_two_party_margin)
    out["current_national_pollsters"] = int(environment.pollsters)
    out["national_poll_swing_from_2024"] = (
        out.uniform_poll_adjusted_dem_margin - out.baseline_2024_pres_dem_margin
    )
    out["polling_federal_margin"] = out.uniform_poll_adjusted_dem_margin
    out["abs_polling_federal_margin"] = out.polling_federal_margin.abs()
    return out.sort_values(["chamber", "district"]).reset_index(drop=True)


def attach_prospective_orthogonal_fundraising(
    panel: pd.DataFrame,
    finance_structure_model: Pipeline,
) -> pd.DataFrame:
    out = panel.copy()
    out["fundraising_gap_structural_expectation"] = np.nan
    out["fundraising_gap_residualized"] = np.nan
    complete = out.finance_complete.astype(bool)
    expected = finance_structure_model.predict(
        design(out.loc[complete], FINANCE_STRUCTURE_FEATURES)
    )
    out.loc[complete, "fundraising_gap_structural_expectation"] = expected
    out.loc[complete, "fundraising_gap_residualized"] = (
        out.loc[complete, "fundraising_gap_log50"] - expected
    )
    for weight in PARTIAL_ORTHOGONAL_WEIGHTS:
        suffix = int(weight * 100)
        column = f"fundraising_gap_partial_orthogonal{suffix}"
        out[column] = np.nan
        out.loc[complete, column] = (
            out.loc[complete, "fundraising_gap_log50"] - weight * expected
        )
    return out


def attach_prospective_within_cycle_fundraising(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, Pipeline]:
    """Estimate the 2026 expected finance gap from the current covariate snapshot."""
    out = panel.copy()
    complete = out.finance_complete.astype(bool)
    model = fit_finance_structure(out.loc[complete])
    expected = model.predict(design(out.loc[complete], FINANCE_STRUCTURE_FEATURES))
    out["fundraising_gap_within_cycle_expectation"] = np.nan
    out["fundraising_gap_within_cycle_residualized"] = np.nan
    out.loc[complete, "fundraising_gap_within_cycle_expectation"] = expected
    out.loc[complete, "fundraising_gap_within_cycle_residualized"] = (
        out.loc[complete, "fundraising_gap_log50"] - expected
    )
    return out, model


def prospective_forecast(panel: pd.DataFrame, models: dict[str, Pipeline]) -> pd.DataFrame:
    incumbent_name = "polling_federal_plus_incumbency"
    incumbent_features = SPECS[incumbent_name]
    assert isinstance(incumbent_features, list)

    neutral = panel.copy()
    for feature in ("fundraising_gap_log50", "fundraising_gap_residualized", "finance_viability_gap_25k"):
        neutral[feature] = 0.0
    for weight in PARTIAL_ORTHOGONAL_WEIGHTS:
        neutral[f"fundraising_gap_partial_orthogonal{int(weight * 100)}"] = 0.0
    neutral["fundraising_gap_within_cycle_residualized"] = 0.0
    inc_reference = neutral.copy()
    inc_reference["incumbency_balance"] = 0.0
    inc_generic = predict_adjustment(models[incumbent_name], inc_reference, incumbent_features)
    inc_full = predict_adjustment(models[incumbent_name], neutral, incumbent_features)

    families = {
        "raw": "polling_federal_plus_incumbency_fundraising",
        "orthogonal": "polling_federal_plus_incumbency_orthogonal_fundraising",
        "within_cycle_orthogonal": "polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising",
    }
    components: dict[str, dict[str, np.ndarray]] = {}
    complete = panel.finance_complete.astype(bool)
    for family, combined_name in families.items():
        combined_features = SPECS[combined_name]
        assert isinstance(combined_features, list)
        generic_reference = neutral.copy()
        generic_reference["incumbency_balance"] = 0.0
        combined_generic = predict_adjustment(models[combined_name], generic_reference, combined_features)
        combined_with_inc = predict_adjustment(models[combined_name], neutral, combined_features)
        combined_full = combined_with_inc.copy()
        combined_full[complete] = predict_adjustment(
            models[combined_name], panel.loc[complete], combined_features
        )
        generic = np.where(complete, combined_generic, inc_generic)
        incumbency = np.where(complete, combined_with_inc - combined_generic, inc_full - inc_generic)
        finance = np.where(complete, combined_full - combined_with_inc, 0.0)
        components[family] = {
            "generic": generic,
            "incumbency": incumbency,
            "finance": finance,
            "total": generic + incumbency + finance,
        }

    scenarios = [
        ("uniform_polling_federal", "uniform_poll_adjusted_dem_margin", 1.0, "raw"),
        ("uniform_polling_federal_shrunk75_sensitivity", "uniform_poll_adjusted_dem_margin", 0.75, "raw"),
        ("demographic_transfer_sensitivity", "poll_adjusted_dem_margin", 1.0, "raw"),
        ("uniform_polling_federal_orthogonal", "uniform_poll_adjusted_dem_margin", 1.0, "orthogonal"),
        ("uniform_polling_federal_orthogonal_shrunk75_sensitivity", "uniform_poll_adjusted_dem_margin", 0.75, "orthogonal"),
        ("demographic_transfer_orthogonal_sensitivity", "poll_adjusted_dem_margin", 1.0, "orthogonal"),
        ("uniform_polling_federal_within_cycle_orthogonal", "uniform_poll_adjusted_dem_margin", 1.0, "within_cycle_orthogonal"),
        ("uniform_polling_federal_within_cycle_orthogonal_shrunk75_sensitivity", "uniform_poll_adjusted_dem_margin", 0.75, "within_cycle_orthogonal"),
        ("demographic_transfer_within_cycle_orthogonal_sensitivity", "poll_adjusted_dem_margin", 1.0, "within_cycle_orthogonal"),
    ]
    rows = []
    for scenario, column, adjustment_weight, family in scenarios:
        component = components[family]
        scenario_generic = adjustment_weight * component["generic"]
        scenario_incumbency = adjustment_weight * component["incumbency"]
        scenario_fundraising = adjustment_weight * component["finance"]
        scenario_adjustment = adjustment_weight * component["total"]
        estimated = panel[column].to_numpy() + scenario_adjustment
        for race, base, lag, inc, fin, adjustment, margin, prob in zip(
            panel.itertuples(index=False), panel[column], scenario_generic, scenario_incumbency,
            scenario_fundraising, scenario_adjustment, estimated, probability(estimated),
        ):
            rows.append({
                "scenario": scenario,
                "cycle": 2026,
                "chamber": race.chamber,
                "district": int(race.district),
                "polling_federal_margin": base,
                "generic_downballot_lag": lag,
                "incumbency_adjustment": inc,
                "fundraising_adjustment": fin,
                "expected_cmo_adjustment": adjustment,
                "adjustment_weight": adjustment_weight,
                "predicted_dem_margin": margin,
                "dem_win_probability": prob,
                "finance_complete": bool(race.finance_complete),
                "finance_model_applied": bool(race.finance_complete),
                "model_used": families[family] if race.finance_complete else incumbent_name,
                "fundraising_treatment": family,
                "dem_fundraising": race.dem_fundraising,
                "rep_fundraising": race.rep_fundraising,
                "fundraising_gap_log50": race.fundraising_gap_log50,
                "fundraising_gap_structural_expectation": race.fundraising_gap_structural_expectation,
                "fundraising_gap_residualized": race.fundraising_gap_residualized,
                "fundraising_gap_within_cycle_expectation": race.fundraising_gap_within_cycle_expectation,
                "fundraising_gap_within_cycle_residualized": race.fundraising_gap_within_cycle_residualized,
                "dem_finance_status": race.dem_finance_status,
                "rep_finance_status": race.rep_finance_status,
                "incumbency_balance": race.incumbency_balance,
                "current_national_poll_margin": race.current_national_poll_margin,
                "current_national_pollsters": race.current_national_pollsters,
                "poll_average_as_of": race.poll_average_as_of,
            })
    return pd.DataFrame(rows).sort_values(["scenario", "chamber", "district"]).reset_index(drop=True)


def write_methodology(
    polling: pd.DataFrame,
    panel: pd.DataFrame,
    metrics: pd.DataFrame,
    bootstrap: pd.DataFrame,
    shrinkage: pd.DataFrame,
    coefficients: pd.DataFrame,
    finance_structure_metrics: pd.DataFrame,
    forecast: pd.DataFrame,
) -> None:
    best = metrics.iloc[0]
    combined = metrics[metrics.specification.eq("polling_federal_plus_incumbency_fundraising")].iloc[0]
    orthogonal = metrics[
        metrics.specification.eq("polling_federal_plus_incumbency_orthogonal_fundraising")
    ].iloc[0]
    within_cycle = metrics[
        metrics.specification.eq(
            "polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising"
        )
    ].iloc[0]
    baseline = metrics[metrics.specification.eq("polling_federal_only")].iloc[0]
    finance_complete = forecast[
        forecast.scenario.eq("uniform_polling_federal")
    ].finance_complete.sum()
    lines = [
        "# Post-2016 polling-CMO forecast experiment",
        "",
        "## Question",
        "",
        "Treat the polling-implied national swing as the prospective federal result in each district, then estimate the legislative-minus-federal residual from generic downballot lag, incumbency, and fundraising. Training is restricted to elections after 2016.",
        "",
        "## Data and validation",
        "",
        f"The common finance-complete panel has {len(panel[panel.cycle.eq(2018)])} contested races in 2018 and {len(panel[panel.cycle.eq(2022)])} in 2022. The only genuine forward test trains on 2018 and predicts 2022.",
        f"Historical generic-ballot snapshots use the final nonpartisan poll from each currently B-or-better Silver-rated pollster within {POLL_WINDOW_DAYS} days of the election. The resulting polling margins are "
        + ", ".join(f"{int(r.cycle)}: D{r.final_poll_margin:+.2f} ({int(r.eligible_pollsters)} pollsters)" for r in polling.itertuples()) + ".",
        "",
        "The baseline is the previous presidential margin in the district plus the polling-implied national swing. Realized national House results are retained only for diagnostics and never enter a feature. The target is the observed legislative margin minus that polling-federal baseline.",
        "",
        "2022 incumbency is reconstructed by exact resolved-name matches to 2018 winners in the same chamber and party. District equality is not required because the 2022 election followed redistricting.",
        "",
        "Fundraising is cash contributions plus other receipts from the identified Alabama principal campaign committee during the election calendar year and preceding calendar year. The model uses `log1p(D / $50,000) - log1p(R / $50,000)`. Missing committee observations remain missing; the 2026 finance term is omitted for those races rather than converted to zero.",
        "",
        "The orthogonalized version first predicts that log fundraising gap from the polling-federal margin, its absolute value, chamber, and incumbency balance. In the forward test, this first-stage model is fit only on 2018 before generating 2022 residuals. No legislative result, CMO target, or realized national result enters the first stage.",
        "",
        "A second orthogonalization sensitivity fits that same outcome-free first stage separately within 2018 and 2022. This uses the 2022 covariate and fundraising distribution but never the 2022 legislative result, mirroring a forecast in which the current cycle's complete finance snapshot is available before Election Day.",
        "",
        "## Forward result",
        "",
        "| Specification | 2022 MAE | RMSE | Winner accuracy | Improvement vs polling federal |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in metrics.itertuples(index=False):
        lines.append(
            f"| {row.specification} | {row.mae:.2f} | {row.rmse:.2f} | {row.winner_accuracy:.1%} | {row.mae_improvement_vs_polling_federal:+.2f} |"
        )
    lines += [
        "",
        f"The best observed specification is `{best.specification}` at {best.mae:.2f} MAE. The raw combined incumbency-and-fundraising model records {combined.mae:.2f} MAE, the cross-cycle orthogonalized combined model records {orthogonal.mae:.2f}, the within-cycle covariate-orthogonalized model records {within_cycle.mae:.2f}, and the unadjusted polling-federal baseline records {baseline.mae:.2f}.",
        "",
        "Paired race bootstrap comparisons for the combined model:",
        "",
        "| Reference | Mean MAE improvement | 95% interval | Probability of improvement |",
        "|---|---:|---:|---:|",
    ]
    for row in bootstrap.itertuples(index=False):
        lines.append(
            f"| {row.reference} | {row.paired_mean_mae_improvement:+.2f} | [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}] | {row.bootstrap_probability_improvement:.1%} |"
        )
    stability = coefficients[
        coefficients.specification.isin([
            "polling_federal_plus_incumbency_fundraising",
            "polling_federal_plus_incumbency_orthogonal_fundraising",
            "polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising",
        ])
        & coefficients.term.isin(["incumbency_balance", "fundraising_gap_log50"])
    ]
    stability = pd.concat([
        stability,
        coefficients[
            coefficients.specification.isin([
                "polling_federal_plus_incumbency_orthogonal_fundraising",
                "polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising",
            ])
            & coefficients.term.isin([
                "fundraising_gap_residualized",
                "fundraising_gap_within_cycle_residualized",
            ])
        ],
    ], ignore_index=True)
    lines += [
        "",
        "Combined-model coefficient stability (points of Democratic margin per original-scale unit):",
        "",
        "| Model | Fit sample | Term | Coefficient |",
        "|---|---|---|---:|",
    ]
    for row in stability.itertuples(index=False):
        lines.append(f"| {row.specification} | {row.fit_sample} | {row.term} | {row.coefficient:+.2f} |")
    lines += [
        "",
        "Global shrinkage sensitivity for the combined adjustment:",
        "",
        "| Model | Adjustment weight | 2022 MAE | RMSE |",
        "|---|---:|---:|---:|",
    ]
    for row in shrinkage.itertuples(index=False):
        lines.append(f"| {row.specification} | {row.adjustment_weight:.0%} | {row.mae:.2f} | {row.rmse:.2f} |")
    lines += [
        "",
        "These weights were evaluated after inspecting the sole holdout. The locally best weight varies by fundraising treatment, so every shrunk result remains a sensitivity rather than an independently selected tuning parameter.",
        "",
        "Fundraising first-stage diagnostics:",
        "",
        "| Sample | Races | MAE | RMSE | R² | Residual corr. with incumbency |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in finance_structure_metrics.itertuples(index=False):
        lines.append(
            f"| {row.sample} | {row.races} | {row.fundraising_gap_mae:.2f} | {row.fundraising_gap_rmse:.2f} | {row.fundraising_gap_r2:.2f} | {row.residual_correlation_incumbency:+.2f} |"
        )
    lines += [
        "",
        "## 2026 construction",
        "",
        "The primary experimental baseline is the 2024 presidential district margin plus the current national generic-ballot swing. Parallel scenarios use raw fundraising, a cross-cycle structural residual, and a residual normalized within each election cycle using only contemporaneously observable covariates. Sensitivities show 75%-shrunk candidate adjustments and the existing demographic-transfer polling baseline. Models are refit on both 2018 and 2022 after the forward test.",
        "",
        f"Explicit FCPA records are complete for {int(finance_complete)}/48 currently contested Democratic-versus-Republican races. Complete races receive the combined lag, incumbency, and fundraising adjustment. The remaining races receive the separately fitted lag-plus-incumbency adjustment and are flagged `finance_model_applied = false`.",
        "",
        f"Win probabilities use the already validated Student-t link with {PROBABILITY_DF:.0f} degrees of freedom and a {PROBABILITY_SCALE:.2f}-point scale. This experiment changes predicted margins, not the probability calibration.",
        "",
        "## Interpretation and gate",
        "",
        "This design directly tests the proposed forecast interpretation of CMO: polling supplies the expected federal vote, while candidate and campaign factors explain the expected downballot deviation. The orthogonal feature asks whether fundraising is unusual relative to the amount predicted by district structure and incumbency. It is predictive, not causal; the residual can still reflect donor information, candidate quality, campaign strategy, and measurement error.",
        "",
        "Do not replace the live headline from this result alone. The post-2016 Alabama gate provides one forward holdout, historical finance is full-cycle rather than cutoff-aligned to the present 2026 snapshot, and candidate fundraising is endogenous. Promotion requires either comparable multi-state finance or a second Alabama forward cycle.",
    ]
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    polling, selected_polls = historical_b_or_better_polling()
    panel, identity_audit = historical_panel(polling)
    predictions, metrics, _ = forward_test(panel)
    bootstrap = bootstrap_comparisons(predictions)
    shrinkage = shrinkage_sensitivity(predictions)
    subgroups = subgroup_metrics(predictions)
    finance_structure_metrics, finance_structure_coefficients = finance_structure_diagnostics(panel)
    panel_model, _, finance_structure_model = attach_orthogonal_fundraising(panel, panel)
    panel_model, within_cycle_finance_models = attach_within_cycle_orthogonal_fundraising(panel_model)
    models = final_models(panel_model)
    coefficient_frames = [
        original_scale_coefficients(name, model, SPECS[name], "pooled_2018_2022", len(panel_model))
        for name, model in models.items()
        if isinstance(SPECS[name], list)
    ]
    for cycle, sample in panel.groupby("cycle", sort=True):
        sample_model, _, _ = attach_orthogonal_fundraising(sample, sample)
        sample_model, _ = attach_within_cycle_orthogonal_fundraising(sample_model)
        for name, features in SPECS.items():
            if features is None:
                continue
            fitted = fit_adjustment(sample_model, features)
            coefficient_frames.append(
                original_scale_coefficients(name, fitted, features, f"cycle_{int(cycle)}", len(sample_model))
            )
    coefficients = pd.concat(coefficient_frames, ignore_index=True)
    prospective = attach_prospective_orthogonal_fundraising(
        prospective_panel(), finance_structure_model
    )
    prospective, prospective_within_cycle_finance_model = attach_prospective_within_cycle_fundraising(
        prospective
    )
    forecast = prospective_forecast(prospective, models)

    # Mandatory invariants.
    assert set(panel.cycle) == {2018, 2022}
    assert not set(FINANCE_STRUCTURE_FEATURES) & {
        "legislative_dem_margin", "polling_cmo_target", "actual_national_swing", "winner",
    }
    assert predictions.train_cycle.eq(2018).all() and predictions.test_cycle.eq(2022).all()
    assert len(predictions[predictions.specification.eq("polling_federal_only")]) == len(panel[panel.cycle.eq(2022)])
    prediction_keys = ["chamber", "district"]
    expected_holdout = set(map(tuple, panel.loc[panel.cycle.eq(2022), prediction_keys].to_numpy()))
    for _, specification_predictions in predictions.groupby("specification"):
        assert set(map(tuple, specification_predictions[prediction_keys].to_numpy())) == expected_holdout
    cross_cycle = predictions[
        predictions.specification.eq(
            "polling_federal_plus_incumbency_orthogonal_fundraising"
        )
    ].sort_values(prediction_keys)
    within_cycle = predictions[
        predictions.specification.eq(
            "polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising"
        )
    ].sort_values(prediction_keys)
    assert not np.allclose(
        cross_cycle.fundraising_gap_residualized.to_numpy(),
        within_cycle.fundraising_gap_within_cycle_residualized.to_numpy(),
    )
    assert forecast.groupby("scenario").size().eq(48).all()
    assert not forecast.duplicated(["scenario", "chamber", "district"]).any()
    assert forecast.loc[~forecast.finance_complete, "fundraising_gap_log50"].isna().all()
    assert forecast.loc[~forecast.finance_complete, "fundraising_gap_residualized"].isna().all()
    assert forecast.loc[~forecast.finance_complete, "fundraising_gap_within_cycle_residualized"].isna().all()
    assert forecast.loc[~forecast.finance_complete, "finance_model_applied"].eq(False).all()
    assert np.allclose(
        forecast.predicted_dem_margin,
        forecast.polling_federal_margin + forecast.expected_cmo_adjustment,
    )

    outputs = {
        "post2016_polling_cmo_historical_polling.csv": polling,
        "post2016_polling_cmo_selected_polls.csv": selected_polls,
        "post2016_polling_cmo_panel.csv": panel_model,
        "post2016_polling_cmo_2022_incumbency_audit.csv": identity_audit,
        "post2016_polling_cmo_forward_predictions.csv": predictions,
        "post2016_polling_cmo_metrics.csv": metrics,
        "post2016_polling_cmo_subgroups.csv": subgroups,
        "post2016_polling_cmo_bootstrap.csv": bootstrap,
        "post2016_polling_cmo_shrinkage_sensitivity.csv": shrinkage,
        "post2016_polling_cmo_coefficients.csv": coefficients,
        "post2016_polling_cmo_finance_structure_metrics.csv": finance_structure_metrics,
        "post2016_polling_cmo_finance_structure_coefficients.csv": finance_structure_coefficients,
        "post2016_polling_cmo_2026_features.csv": prospective,
        "post2016_polling_cmo_2026_forecast.csv": forecast,
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)

    code_inputs = [Path(__file__).resolve(), ROOT / "scripts/build_historical_silver_generic_ballot.py"]
    data_inputs = [
        FINANCE_PANEL, FINANCE_CANDIDATES, CANONICAL_CANDIDATES, IDENTITY_CROSSWALK,
        RAW_POLLS, SILVER_RATINGS, ROSTER, INCUMBENCY_2026, POLL_BASELINE_2026,
        CURRENT_ENVIRONMENT,
    ]
    manifest = {
        "schema_version": 1,
        "status": "experimental_not_promoted",
        "methodology": "post2016_polling_cmo_forecast",
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "training_cycles": [2018],
        "forward_test_cycle": 2022,
        "final_fit_cycles": [2018, 2022],
        "ridge_alpha": RIDGE_ALPHA,
        "finance_scale": FINANCE_SCALE,
        "fundraising_residualizers": {
            "cross_cycle_forward_test_fit_cycles": [2018],
            "within_cycle_forward_test_covariate_fit_cycle": 2022,
            "uses_legislative_outcome": False,
        },
        "probability_family": {"family": "student_t", "df": PROBABILITY_DF, "scale": PROBABILITY_SCALE},
        "data_inputs": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)} for path in data_inputs],
        "code_inputs": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)} for path in code_inputs],
        "outputs": [{
            "path": f"data/processed/forecast_calibration/{name}",
            "rows": len(frame),
            "sha256": sha256(OUT / name),
        } for name, frame in outputs.items()],
        "promotion_gate": "failed_by_design_insufficient_forward_cycles_and_cutoff_mismatch",
    }
    stable = dict(manifest)
    manifest["build_id"] = hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()[:20]
    manifest_path = OUT / "post2016_polling_cmo_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_methodology(
        polling, panel, metrics, bootstrap, shrinkage, coefficients,
        finance_structure_metrics, forecast,
    )

    print(polling.to_string(index=False))
    print("\nForward test (2018 -> 2022):")
    print(metrics.to_string(index=False))
    print("\nPaired bootstrap:")
    print(bootstrap.to_string(index=False))
    print(f"\n2026 finance complete: {int(prospective.finance_complete.sum())}/{len(prospective)}")
    print(f"build={manifest['build_id']} status={manifest['status']}")


if __name__ == "__main__":
    main()
