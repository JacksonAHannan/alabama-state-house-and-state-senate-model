#!/usr/bin/env python3
"""Backcast the modern Southern residual-WAR model onto Alabama, 1994–2022."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import retrain_post2016_southern_war as v1  # noqa: E402
import retrain_post2016_southern_war_v2 as v2  # noqa: E402


WAR = ROOT / "data/processed/war"
HISTORICAL_RACES = WAR / "cmo_v5_races.csv"
HISTORICAL_CANDIDATES = WAR / "cmo_v5_candidates.csv"
HISTORICAL_CONTEXT = ROOT / "data/processed/elections/canonical_cmo_features.csv"
PUBLISHED_ALABAMA = WAR / "alabama_war_v1"
SOUTHERN_MANIFEST = WAR / "post2016_southern_war_v3/manifest.json"
FIELD_CONTRACT = ROOT / "project_docs/model/ALABAMA_HISTORICAL_WAR_V1_FIELD_CONTRACT.md"
DISPLAY_NAME_ALIASES = ROOT / "data/manual/ideology/candidate_research_aliases.csv"
METHOD_REPORT = ROOT / "project_docs/model/ALABAMA_HISTORICAL_WAR_V1.md"
AUDIT_REPORT = ROOT / "project_docs/audits/ALABAMA_HISTORICAL_WAR_V1_VALIDATION.md"
OUT = WAR / "alabama_historical_war_v1"

RACE_KEYS = ["cycle", "chamber", "district"]
ALPHA = 100.0
SPECIFICATION = "decaying_lag"
COMMITTEE_PATTERN = re.compile(
    r"committee|campaign|friends of|\bfor (?:house|senate|representative)\b|\bpac\b",
    re.IGNORECASE,
)
SOURCE_ID_PATTERN = re.compile(r"^[A-Z]{3}\d{3}[A-Z]{4,}$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def prepare_historical_races() -> pd.DataFrame:
    races = pd.read_csv(HISTORICAL_RACES, low_memory=False)
    context = pd.read_csv(
        HISTORICAL_CONTEXT,
        usecols=[
            "cycle", "chamber", "district", "dem_incumbent", "rep_incumbent",
            "incumbency_complete", "model_tier", "baseline_fallback_share",
            "prior_pres_fallback_share", "prior_pres_source_complete",
        ],
        low_memory=False,
    )
    if races.duplicated(RACE_KEYS).any() or context.duplicated(RACE_KEYS).any():
        raise ValueError("Historical race/context keys are not unique")
    races = races.merge(context, on=RACE_KEYS, how="left", validate="one_to_one")
    if len(races) != 509 or races[RACE_KEYS].isna().any().any():
        raise ValueError("Historical Alabama race coverage changed")
    if races[["dem_incumbent", "rep_incumbent"]].isna().any().any():
        raise ValueError("Historical backcast requires explicit incumbency")

    races["state_code"] = "AL"
    races["historical_chamber"] = races.chamber
    races["chamber"] = races.chamber.map({"house": "lower", "senate": "upper"})
    if races.chamber.isna().any():
        raise ValueError("Unknown historical chamber")
    races["baseline_dem_margin"] = races.selected_ticket_margin.astype(float)
    races["baseline_office_family"] = races.selected_ticket_source.map(v1.office_family)
    races["incumbency_balance"] = (
        races.dem_incumbent.astype(float) - races.rep_incumbent.astype(float)
    )
    races["prior_pres_margin"] = races.prior_presidential_margin
    races["lag_context_available"] = races.prior_pres_margin.notna()
    races["lag_current_ticket_change"] = (
        races.baseline_dem_margin - races.prior_pres_margin
    )
    races["years_since_2016"] = races.cycle - 2016
    races["lag_change_x_years"] = (
        races.lag_current_ticket_change * races.years_since_2016
    )
    races["direct_overperformance"] = races.direct_cmo
    races["raw_gap"] = races.direct_cmo
    return races


def fit_modern_backcast(
    historical: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    modern, warehouse_run = v2.load_training()
    modern = v2.attach_lag_context(modern)
    if not modern.cycle.gt(2016).all():
        raise ValueError("Modern backcast training leaked a pre-2017 race")

    combined = pd.concat([modern, historical], ignore_index=True, sort=False)
    designs, lag_columns = v2.design_matrices(combined)
    design = designs[SPECIFICATION]
    modern_rows = len(modern)
    model = v2.ridge_model(ALPHA).fit(
        design.iloc[:modern_rows], modern.direct_overperformance.to_numpy(float)
    )
    historical_design = design.iloc[modern_rows:].copy()
    prediction = model.predict(historical_design)
    nonlag_design = historical_design.copy()
    for column in lag_columns:
        nonlag_design[column] = 0.0
    nonlag_prediction = model.predict(nonlag_design)

    result = historical.copy()
    result["modern_backcast_structural_expected_gap"] = prediction
    result["modern_backcast_nonlag_expected_gap"] = nonlag_prediction
    result["modern_backcast_lag_component"] = prediction - nonlag_prediction
    result["modern_backcast_war"] = result.raw_gap - prediction

    coefficients = v2.full_model_coefficients(model, list(design.columns))
    scaler = model.named_steps["scale"]
    ridge = model.named_steps["ridge"]
    original = ridge.coef_ / scaler.scale_
    intercept = float(ridge.intercept_ - np.dot(scaler.mean_, original))
    coefficients = pd.concat([
        pd.DataFrame({"feature": ["__intercept__"], "coefficient": [intercept]}),
        coefficients,
    ], ignore_index=True)
    coefficients.insert(0, "structural_alpha", ALPHA)
    coefficients.insert(0, "structural_specification", SPECIFICATION)
    return result, coefficients, str(warehouse_run["build_run_id"])


def apply_published_modern_scores(races: pd.DataFrame) -> pd.DataFrame:
    published = pd.read_csv(PUBLISHED_ALABAMA / "race_war.csv", low_memory=False)
    published["chamber"] = published.chamber.map({"lower": "lower", "upper": "upper"})
    keep = RACE_KEYS + [
        "raw_gap", "fitted_structural_expected_gap",
        "fitted_structural_nonlag_expected_gap", "fitted_lag_component", "war",
    ]
    published = published[keep].rename(columns={
        "raw_gap": "published_raw_gap",
        "fitted_structural_expected_gap": "published_structural_expected_gap",
        "fitted_structural_nonlag_expected_gap": "published_nonlag_expected_gap",
        "fitted_lag_component": "published_lag_component",
        "war": "published_war",
    })
    if published.duplicated(RACE_KEYS).any() or len(published) != 97:
        raise ValueError("Published Alabama WAR keys changed")
    result = races.merge(published, on=RACE_KEYS, how="left", validate="one_to_one")
    modern = result.cycle.gt(2016)
    if result.loc[modern, "published_war"].isna().any():
        raise ValueError("A modern historical race is missing published Alabama WAR")
    np.testing.assert_allclose(
        result.loc[modern, "raw_gap"], result.loc[modern, "published_raw_gap"], atol=1e-9
    )

    result["scoring_scope"] = np.where(
        modern, "published_same_cycle_residual", "post2016_southern_model_backcast"
    )
    result["fitted_structural_expected_gap"] = np.where(
        modern,
        result.published_structural_expected_gap,
        result.modern_backcast_structural_expected_gap,
    )
    result["fitted_structural_nonlag_expected_gap"] = np.where(
        modern,
        result.published_nonlag_expected_gap,
        result.modern_backcast_nonlag_expected_gap,
    )
    result["fitted_lag_component"] = np.where(
        modern, result.published_lag_component, result.modern_backcast_lag_component
    )
    result["war"] = np.where(modern, result.published_war, result.modern_backcast_war)
    result["war_definition"] = "raw_gap_minus_fitted_structural_expected_gap"
    result["backcast_extrapolation_years"] = np.maximum(0, 2018 - result.cycle)
    result["chamber"] = result.historical_chamber
    return result


def build_candidate_rows(races: pd.DataFrame) -> pd.DataFrame:
    candidates = pd.read_csv(HISTORICAL_CANDIDATES, low_memory=False)
    if candidates.duplicated(RACE_KEYS + ["canonical_party"]).any() or len(candidates) != 1018:
        raise ValueError("Historical candidate grain changed")
    race_fields = races[RACE_KEYS + [
        "raw_gap", "fitted_structural_expected_gap",
        "fitted_structural_nonlag_expected_gap", "fitted_lag_component", "war",
        "scoring_scope", "lag_context_available", "backcast_extrapolation_years",
        "modern_backcast_structural_expected_gap", "modern_backcast_war",
    ]]
    candidates = candidates.merge(race_fields, on=RACE_KEYS, how="left", validate="many_to_one")
    orientation = candidates.canonical_party.map({"D": 1.0, "R": -1.0})
    if orientation.isna().any():
        raise ValueError("Historical candidate output contains a non-major party")
    aliases = pd.read_csv(DISPLAY_NAME_ALIASES, low_memory=False)
    aliases = aliases[aliases.identity_status.astype(str).str.startswith("verified_")][
        ["canonical_candidate_id", "research_name"]
    ].copy()
    if aliases.canonical_candidate_id.duplicated().any():
        raise ValueError("Verified candidate display-name adjudications are not unique")
    candidates["source_candidate_name"] = candidates.canonical_name
    candidates = candidates.merge(
        aliases.rename(columns={"research_name": "verified_research_name"}),
        on="canonical_candidate_id", how="left", validate="many_to_one",
    )
    identifier_like = candidates.source_candidate_name.astype(str).str.fullmatch(
        SOURCE_ID_PATTERN, na=False
    )
    unresolved = identifier_like & candidates.verified_research_name.isna()
    if unresolved.any():
        values = candidates.loc[
            unresolved, ["canonical_candidate_id", "source_candidate_name"]
        ].to_dict("records")
        raise ValueError(f"Unresolved source IDs entered historical WAR: {values[:5]}")
    candidates["canonical_name"] = candidates.source_candidate_name.where(
        ~identifier_like, candidates.verified_research_name
    )
    candidates["candidate_name"] = candidates.canonical_name
    candidates["candidate_cycle_war"] = orientation * candidates.war
    candidates["candidate_raw_gap"] = orientation * candidates.raw_gap
    candidates["candidate_structural_expected_gap"] = (
        orientation * candidates.fitted_structural_expected_gap
    )
    candidates["candidate_lag_component"] = orientation * candidates.fitted_lag_component
    candidates["score_identification"] = "race_differential_party_orientation"
    candidates["display_name_source"] = np.where(
        identifier_like,
        "verified_candidate_research_alias",
        "canonical_alabama_election_candidate",
    )
    committee_like = candidates.candidate_name.astype(str).str.contains(
        COMMITTEE_PATTERN, na=False
    )
    if committee_like.any():
        values = candidates.loc[committee_like, "candidate_name"].tolist()
        raise ValueError(f"Committee-like name entered historical WAR: {values[:5]}")
    if candidates.candidate_name.astype(str).str.fullmatch(SOURCE_ID_PATTERN, na=False).any():
        raise ValueError("Identifier-shaped candidate name entered historical WAR")
    return candidates


def output_columns(races: pd.DataFrame, candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    race_columns = [
        "cycle", "chamber", "district", "dem_votes", "rep_votes", "two_party_votes",
        "legislative_dem_margin", "selected_ticket_margin", "selected_ticket_source",
        "raw_gap", "prior_presidential_margin", "incumbency_balance",
        "lag_context_available", "fitted_structural_nonlag_expected_gap",
        "fitted_lag_component", "fitted_structural_expected_gap", "war",
        "scoring_scope", "backcast_extrapolation_years",
        "modern_backcast_structural_expected_gap", "modern_backcast_war",
        "state_ticket_cmo", "federal_ticket_cmo", "presidential_ticket_cmo",
        "contest_tier", "model_tier", "baseline_fallback_share",
        "prior_pres_fallback_share", "prior_pres_source_complete", "war_definition",
    ]
    candidate_columns = [
        "cycle", "chamber", "district", "canonical_party", "candidate_name",
        "canonical_name", "source_candidate_name", "canonical_candidate_id", "person_id", "candidate_effect_id",
        "identity_status", "display_name_source", "canonical_votes", "winner", "incumbent",
        "candidate_raw_gap", "candidate_structural_expected_gap", "candidate_lag_component",
        "candidate_cycle_war", "scoring_scope", "lag_context_available",
        "backcast_extrapolation_years", "modern_backcast_structural_expected_gap",
        "modern_backcast_war", "candidate_state_ticket_cmo",
        "candidate_federal_ticket_cmo", "candidate_presidential_ticket_cmo",
        "selected_ticket_margin", "selected_ticket_source", "prior_presidential_margin",
        "contest_tier", "score_identification",
    ]
    return races[race_columns].copy(), candidates[candidate_columns].copy()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    historical = prepare_historical_races()
    races, coefficients, warehouse_run_id = fit_modern_backcast(historical)
    races = apply_published_modern_scores(races)
    candidates = build_candidate_rows(races)
    race_output, candidate_output = output_columns(races, candidates)

    formula_error = float(np.max(np.abs(
        race_output.war
        - (race_output.raw_gap - race_output.fitted_structural_expected_gap)
    )))
    paired = candidate_output.pivot(
        index=RACE_KEYS, columns="canonical_party", values="candidate_cycle_war"
    )
    orientation_error = float(np.max(np.abs(paired.D + paired.R)))
    if formula_error > 1e-9 or orientation_error > 1e-9:
        raise ValueError("Historical WAR arithmetic failed")

    source_manifest = json.loads(SOUTHERN_MANIFEST.read_text(encoding="utf-8"))
    alabama_manifest = json.loads(
        (PUBLISHED_ALABAMA / "manifest.json").read_text(encoding="utf-8")
    )
    run_material = "".join([
        sha256(HISTORICAL_RACES), sha256(HISTORICAL_CANDIDATES),
        sha256(HISTORICAL_CONTEXT), sha256(PUBLISHED_ALABAMA / "race_war.csv"),
        sha256(SOUTHERN_MANIFEST), sha256(FIELD_CONTRACT), sha256(DISPLAY_NAME_ALIASES),
    ])
    run_id = "AL-HIST-WAR-V1-" + hashlib.sha256(run_material.encode()).hexdigest()[:20].upper()
    generated = dt.datetime.now(dt.timezone.utc).isoformat()
    for frame in (race_output, candidate_output, coefficients):
        frame.insert(0, "historical_war_run_id", run_id)

    paths = {
        "race_war.csv": race_output,
        "candidate_cycle_war.csv": candidate_output,
        "structural_coefficients.csv": coefficients,
    }
    for filename, frame in paths.items():
        frame.to_csv(OUT / filename, index=False)
    coverage = race_output.groupby(["cycle", "chamber", "scoring_scope"], as_index=False).agg(
        races=("district", "size"),
        mean_war=("war", "mean"),
        mean_absolute_war=("war", lambda values: float(values.abs().mean())),
        lag_context_races=("lag_context_available", "sum"),
    )
    coverage.insert(0, "historical_war_run_id", run_id)
    coverage.to_csv(OUT / "coverage.csv", index=False)

    manifest = {
        "schema_version": 1,
        "methodology_version": "alabama_historical_war_v1_modern_backcast",
        "historical_war_run_id": run_id,
        "generated_at_utc": generated,
        "git_commit": git_commit(),
        "warehouse_build_run_id": warehouse_run_id,
        "source_southern_war_run_id": source_manifest["model_run_id"],
        "source_alabama_war_run_id": alabama_manifest["alabama_war_run_id"],
        "configuration": {
            "training_cutoff_rule": "cycle > 2016",
            "backcast_cycles": [1994, 1998, 2002, 2006, 2010, 2014],
            "published_cycles": [2018, 2022],
            "structural_specification": SPECIFICATION,
            "structural_alpha": ALPHA,
            "candidate_pooling": False,
            "finance_in_war": False,
            "committee_names_allowed": False,
            "identifier_shaped_names_allowed": False,
        },
        "diagnostics": {
            "race_rows": int(len(race_output)),
            "candidate_cycle_rows": int(len(candidate_output)),
            "backcast_races": int(race_output.cycle.le(2014).sum()),
            "published_modern_races": int(race_output.cycle.gt(2016).sum()),
            "lag_context_missing_races": int((~race_output.lag_context_available).sum()),
            "max_war_formula_error": formula_error,
            "max_candidate_orientation_error": orientation_error,
            "committee_like_candidate_names": 0,
            "identifier_shaped_candidate_names": 0,
            "verified_display_name_adjudications": int(
                candidate_output.display_name_source.eq("verified_candidate_research_alias").sum()
            ),
        },
        "input_hashes": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in (
                HISTORICAL_RACES, HISTORICAL_CANDIDATES, HISTORICAL_CONTEXT,
                PUBLISHED_ALABAMA / "race_war.csv", SOUTHERN_MANIFEST, FIELD_CONTRACT,
                DISPLAY_NAME_ALIASES,
            )
        },
        "outputs": [],
        "status": "validated_historical_backcast_with_extrapolation_warning",
    }
    for filename in (*paths, "coverage.csv"):
        path = OUT / filename
        rows = len(pd.read_csv(path, low_memory=False))
        manifest["outputs"].append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "rows": rows,
            "sha256": sha256(path),
        })
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    METHOD_REPORT.write_text(
        "# Alabama historical WAR v1\n\n"
        f"Run: `{run_id}`\n\n"
        "This product restores the 1994–2022 Alabama race explorer under the corrected "
        "race-residual definition. For 1994–2014, the selected post-2016 Southern "
        "`decaying_lag` ridge model (alpha 100) is fit only on strict races after 2016 "
        "and applied backward to Alabama. For 2018 and 2022, the output preserves the "
        "exact published Alabama WAR v1 same-cycle residual.\n\n"
        "`WAR = legislative-minus-ticket gap - fitted structural expected gap`.\n\n"
        "The backcast is descriptive extrapolation, not a contemporaneous fit or forecast. "
        "Candidate rows are opposite orientations of one race residual. Finance, ideology, "
        "candidate history, pooled effects, and committee identities are excluded.\n",
        encoding="utf-8",
    )
    AUDIT_REPORT.write_text(
        "# Alabama historical WAR v1 validation\n\n"
        f"- Run: `{run_id}`.\n"
        f"- Coverage: {len(race_output)} races and {len(candidate_output)} candidate-cycle rows.\n"
        f"- Backcast races, 1994–2014: {int(race_output.cycle.le(2014).sum())}.\n"
        f"- Exact published modern races, 2018/2022: {int(race_output.cycle.gt(2016).sum())}.\n"
        f"- Missing lag-context races retained explicitly: {int((~race_output.lag_context_available).sum())}.\n"
        f"- Maximum formula error: {formula_error:.3g}.\n"
        f"- Maximum candidate-orientation error: {orientation_error:.3g}.\n"
        "- Candidate display names use canonical election identity, with evidence-backed aliases "
        "for malformed source IDs; committee-like and identifier-shaped names: 0.\n"
        "- Publication limitation: pre-2016 scores extrapolate a modern relationship backward.\n",
        encoding="utf-8",
    )
    print(
        f"Built {run_id}: races={len(race_output)} candidates={len(candidate_output)} "
        f"backcast={int(race_output.cycle.le(2014).sum())}"
    )


if __name__ == "__main__":
    main()
