from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
WAR = ROOT / "data" / "processed" / "war"


def load(name):
    return pd.read_csv(WAR / name, low_memory=False)


def test_direct_cmo_reconciles_and_is_candidate_oriented():
    races, candidates = load("cmo_v5_races.csv"), load("cmo_v5_candidates.csv")
    assert len(races) == 509
    assert len(candidates) == 1018
    np.testing.assert_allclose(
        races.direct_cmo, races.legislative_dem_margin - races.selected_ticket_margin, atol=1e-9)
    paired = candidates.pivot(index=["cycle", "chamber", "district"],
                              columns="canonical_party", values="candidate_direct_cmo")
    np.testing.assert_allclose(paired.D, -paired.R, atol=1e-9)
    assert set(races.selected_ticket_source) == {"same_cycle_federal", "same_cycle_state_fallback"}


def test_lag_is_predetermined_and_current_federal_is_not_reused():
    source = (ROOT / "scripts" / "rebuild_cmo_candidate_quality_v5.py").read_text(encoding="utf-8")
    assert "predetermined_presidential_swing" in source
    assert "federal_index_margin - data.prior_pres" not in source
    assert "Current same-cycle federal margin appears only in the ticket baseline" in (
        ROOT / "project_docs" / "model" / "CMO_METHODOLOGY_V5.md").read_text(encoding="utf-8")
    races = load("cmo_v5_races.csv")
    assert races.loc[races.cycle.eq(2010), "predetermined_presidential_swing"].isna().all()
    assert races.loc[races.cycle.eq(2022), "predetermined_presidential_swing"].notna().all()


def test_quality_is_partial_pooled_predictive_and_uncertain_when_evidence_is_weak():
    candidates, effects = load("cmo_v5_candidates.csv"), load("cmo_v5_candidate_effects.csv")
    tournament = load("cmo_v5_model_tournament.csv")
    assert effects.candidate_quality_index.abs().max() < candidates.candidate_cycle_centered_cmo.abs().max()
    assert effects.quality_reliability.between(0, 1).all()
    selected = tournament[(tournament.stage == "quality") &
                          (tournament.specification == "seen_candidate")].sort_values("mae").iloc[0]
    assert selected.mae < selected.zero_baseline_mae
    assert selected.pearson > 0.45
    assert selected.pearson_p < 0.01
    first_cycle = candidates.cycle.min()
    assert candidates.loc[candidates.cycle.eq(first_cycle), "pre_election_appearances"].eq(0).all()
    assert candidates.loc[candidates.cycle.eq(first_cycle), "pre_election_quality_source"].eq("no_prior_race").all()


def test_mike_curtis_case_study_no_longer_reverses_observed_overperformance():
    candidates = load("cmo_v5_candidates.csv")
    mike = candidates[candidates.canonical_name.str.contains("MIKE CURTIS", case=False, na=False)]
    assert set(mike.cycle) == {2010, 2014}
    assert mike.candidate_direct_cmo.gt(10).all()
    assert mike.candidate_quality_index.gt(0).all()
    assert mike.candidate_quality_low.lt(0).all() and mike.candidate_quality_high.gt(0).all()
    assert set(mike.quality_status) == {"uncertain"}


def test_candidate_quality_differential_and_party_symmetry_are_auditable():
    races, candidates = load("cmo_v5_races.csv"), load("cmo_v5_candidates.csv")
    effects = candidates.pivot(index=["cycle", "chamber", "district"],
                               columns="canonical_party", values="candidate_quality_index")
    differential = effects.D - effects.R
    indexed = races.set_index(["cycle", "chamber", "district"])
    np.testing.assert_allclose(differential, indexed.candidate_quality_differential, atol=1e-9)
    symmetry = load("cmo_v5_party_symmetry.csv").set_index("canonical_party")
    assert abs(symmetry.loc["D", "mean_quality"] - symmetry.loc["R", "mean_quality"]) < 0.5
    assert {"positive", "negative", "uncertain"} >= set(candidates.quality_status)


def test_longitudinal_names_and_isolated_pairs_are_conservative():
    candidates = load("cmo_v5_candidates.csv")
    boyd = candidates[candidates.normalized_candidate_name.eq("BARBARA BIGSBY BOYD")]
    hammett = candidates[candidates.normalized_candidate_name.eq("SETH HAMMETT")]
    assert len(boyd) == 4 and boyd.candidate_effect_id.nunique() == 1
    assert len(hammett) == 2 and hammett.candidate_effect_id.nunique() == 1
    isolated = candidates[candidates.quality_identification.eq("pair_differential_only")]
    assert len(isolated) > 0
    assert isolated.quality_status.eq("uncertain").all()
    cases = load("cmo_v5_case_studies.csv")
    assert cases.normalized_candidate_name.eq("BARBARA BIGSBY BOYD").sum() == 4


def test_outputs_and_provenance_are_complete():
    required = [
        "cmo_v5_races.csv", "cmo_v5_candidates.csv", "cmo_v5_candidate_effects.csv",
        "cmo_v5_model_tournament.csv", "cmo_v5_case_studies.csv",
        "cmo_v5_incumbency_transitions.csv", "cmo_v5_party_symmetry.csv", "cmo_v5_provenance.csv",
    ]
    assert all((WAR / name).exists() and (WAR / name).stat().st_size > 0 for name in required)
    provenance = load("cmo_v5_provenance.csv")
    outputs = set(provenance.loc[provenance.record_type.eq("output"), "name"])
    assert set(required[:-1]) <= outputs
    inputs = set(provenance.loc[provenance.record_type.eq("input"), "name"])
    assert {"canonical_cmo_district_office_baselines.csv",
            "historical_federal_district_baselines.csv"} <= inputs
    assert "rebuild_cmo_methodology_v2.py" in set(provenance.name)
    configs = provenance[provenance.record_type.eq("config")]
    assert configs.sha256.isna().all() and configs.value.notna().all()
