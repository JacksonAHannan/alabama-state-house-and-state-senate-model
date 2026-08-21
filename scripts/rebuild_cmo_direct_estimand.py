"""Build CMO v3 as direct, source-aware ticket overperformance.

Regression expectations remain in the pathology audit, but never determine the
headline score.  This keeps the estimand auditable at the race level and avoids
out-of-era covariate extrapolation.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

import rebuild_cmo_methodology_v2 as v2

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
REPORT = ROOT / "project_docs" / "model" / "CMO_METHODOLOGY_V3.md"
KEYS = ["cycle", "chamber", "district"]


def candidate_scores(races: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    keep = KEYS + [
        "headline_cmo", "state_ticket_cmo", "federal_ticket_cmo",
        "presidential_ticket_cmo", "headline_cmo_low", "headline_cmo_high",
        "baseline_source_v3", "baseline_reliability", "contest_tier",
    ]
    out = candidates.merge(races[keep], on=KEYS, how="inner", validate="many_to_one")
    sign = out.canonical_party.map({"D": 1.0, "R": -1.0})
    for col in ("headline_cmo", "state_ticket_cmo", "federal_ticket_cmo",
                "presidential_ticket_cmo"):
        out[f"candidate_{col}"] = out[col] * sign
    out["candidate_headline_cmo_low"] = np.where(
        sign.eq(1), out.headline_cmo_low, -out.headline_cmo_high)
    out["candidate_headline_cmo_high"] = np.where(
        sign.eq(1), out.headline_cmo_high, -out.headline_cmo_low)

    # Career attribution is secondary and explicitly partial-pooled. Individual
    # election scores above remain the observed direct residual without shrinkage.
    group = out.groupby("candidate_effect_id").candidate_headline_cmo
    career = group.agg([("career_cmo_mean", "mean"), ("appearances", "size")]).reset_index()
    career["career_reliability"] = career.appearances / (career.appearances + 2.0)
    career["career_cmo_partial_pooled"] = career.career_cmo_mean * career.career_reliability
    return out.merge(career, on="candidate_effect_id", how="left", validate="many_to_one")


def build() -> None:
    source_races, candidates = v2.load_panel()
    data = v2.prepare_features(v2.attach_candidate_history(v2.build_source_aware_baseline(source_races), candidates))
    prior = pd.read_csv(WAR / "cmo_v2_races.csv")[KEYS + [
        "expected_margin_context", "context_cmo", "within_cycle_cmo"]]
    data = data.merge(prior, on=KEYS, how="left", validate="one_to_one")

    data["state_ticket_cmo"] = data.legislative_dem_margin - data.baseline_state_margin_v2
    data["federal_ticket_cmo"] = data.legislative_dem_margin - data.federal_index_margin
    data["presidential_ticket_cmo"] = data.legislative_dem_margin - data.prior_pres_dem_margin_v2
    data["headline_cmo"] = data.raw_ticket_overperformance
    data["baseline_source_v3"] = data.baseline_source_v2
    data["baseline_reliability"] = (1 - pd.to_numeric(
        data.baseline_fallback_share, errors="coerce").fillna(0)).clip(0, 1)

    alternatives = data[["state_ticket_cmo", "federal_ticket_cmo", "presidential_ticket_cmo"]]
    data["baseline_specification_sd"] = alternatives.std(axis=1, skipna=True).fillna(0)
    quality_penalty = 5 * (1 - data.baseline_reliability)
    contest_penalty = data.contest_tier.map({"meaningful": 0.0, "marginal": 2.0, "nominal": 5.0})
    data["headline_uncertainty_radius"] = (
        1.96 * data.baseline_specification_sd + quality_penalty + contest_penalty).clip(lower=2)
    data["headline_cmo_low"] = data.headline_cmo - data.headline_uncertainty_radius
    data["headline_cmo_high"] = data.headline_cmo + data.headline_uncertainty_radius
    data["context_extrapolation_delta"] = data.context_cmo - data.headline_cmo
    data["context_pathology_flag"] = data.context_extrapolation_delta.abs().gt(20)

    race_columns = KEYS + [
        "dem_votes", "rep_votes", "two_party_votes", "legislative_dem_margin",
        "baseline_ensemble_margin", "baseline_state_margin_v2", "federal_index_margin",
        "prior_pres_dem_margin_v2", "headline_cmo", "state_ticket_cmo",
        "federal_ticket_cmo", "presidential_ticket_cmo", "headline_cmo_low",
        "headline_cmo_high", "headline_uncertainty_radius", "baseline_specification_sd",
        "baseline_reliability", "baseline_source_v3", "contest_tier",
    ]
    races = data[race_columns].copy()
    scored = candidate_scores(races, candidates)

    tournament = []
    choices = {
        "state_ticket": data.baseline_state_margin_v2,
        "selected_source_aware": data.baseline_ensemble_margin,
        "state_80_federal_20": .8 * data.baseline_state_margin_v2 + .2 * data.federal_index_margin,
        "state_70_federal_30": .7 * data.baseline_state_margin_v2 + .3 * data.federal_index_margin,
        "prior_presidential": data.prior_pres_dem_margin_v2,
    }
    for name, baseline in choices.items():
        residual = data.legislative_dem_margin - baseline
        valid = residual.notna()
        tournament.append({
            "baseline": name, "races": int(valid.sum()),
            "mean_absolute_gap": float(residual[valid].abs().mean()),
            "median_gap": float(residual[valid].median()),
            "p95_absolute_gap": float(residual[valid].abs().quantile(.95)),
        })
    tournament = pd.DataFrame(tournament)

    pathology = data.loc[data.context_pathology_flag, KEYS + [
        "legislative_dem_margin", "baseline_ensemble_margin", "headline_cmo",
        "expected_margin_context", "context_cmo", "within_cycle_cmo",
        "context_extrapolation_delta"]].sort_values("context_extrapolation_delta", key=lambda x: x.abs(), ascending=False)

    races.to_csv(WAR / "cmo_v3_races.csv", index=False)
    scored.to_csv(WAR / "cmo_v3_candidates.csv", index=False)
    tournament.to_csv(WAR / "cmo_v3_baseline_tournament.csv", index=False)
    pathology.to_csv(WAR / "cmo_v3_context_pathology_audit.csv", index=False)
    manifest_rows = [
        {"record_type": "input", "name": name,
         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, path in [
            ("canonical_cmo_features.csv", v2.ELECTIONS / "canonical_cmo_features.csv"),
            ("canonical_cmo_candidates.csv", v2.ELECTIONS / "canonical_cmo_candidates.csv"),
            ("canonical_cmo_district_office_baselines.csv", v2.ELECTIONS / "canonical_cmo_district_office_baselines.csv"),
            ("historical_federal_district_baselines.csv", v2.ELECTIONS / "historical_federal_district_baselines.csv"),
            ("cmo_v2_races.csv", WAR / "cmo_v2_races.csv"),
        ]
    ]
    manifest_rows.extend([
        {"record_type": "code", "name": "scripts/rebuild_cmo_direct_estimand.py",
         "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        {"record_type": "config", "name": "headline_estimand", "sha256": "direct_source_aware_ticket_residual"},
        {"record_type": "config", "name": "modern_federal_weight", "sha256": "0.30"},
    ])
    for name in ["cmo_v3_races.csv", "cmo_v3_candidates.csv", "cmo_v3_baseline_tournament.csv",
                 "cmo_v3_context_pathology_audit.csv"]:
        manifest_rows.append({"record_type": "output", "name": name,
                              "sha256": hashlib.sha256((WAR / name).read_bytes()).hexdigest()})
    run_material = "\n".join(f"{x['record_type']}|{x['name']}|{x['sha256']}" for x in manifest_rows)
    manifest_rows.append({"record_type": "run", "name": "build_run_id",
                          "sha256": hashlib.sha256(run_material.encode()).hexdigest()})
    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(WAR / "cmo_v3_provenance.csv", index=False)

    morrow = races[(races.cycle.eq(1998)) & races.chamber.eq("house") & races.district.eq(18)].iloc[0]
    REPORT.write_text(
        "# CMO methodology v3: direct ticket overperformance\n\n"
        "## Headline estimand\n\n"
        "The headline CMO is the party-oriented difference between the legislative margin and the "
        "source-aware same-district ticket baseline. It does not residualize the result a second time "
        "using demographics, incumbency, finance, ideology, or candidate history.\n\n"
        "Regression-based context expectations are retained only in the pathology audit. Career scores "
        "are separately labeled partial-pooled summaries; they do not replace election-level CMO.\n\n"
        "## Morrow 1998 HD-18 reconciliation\n\n"
        f"- Legislative Democratic margin: {morrow.legislative_dem_margin:.3f}\n"
        f"- Source-aware ticket baseline: {morrow.baseline_ensemble_margin:.3f}\n"
        f"- Headline CMO: {morrow.headline_cmo:.3f}\n\n"
        "## Baseline comparison\n\n" + v2.markdown_table(tournament) + "\n\n"
        f"The superseded context model generated {len(pathology)} race estimates more than 20 points "
        "away from the direct ticket residual. Those cases are published for audit, not used as CMO.\n",
        encoding="utf-8")
    print(f"races={len(races)} candidates={len(scored)} context_pathologies={len(pathology)}")


if __name__ == "__main__":
    build()
