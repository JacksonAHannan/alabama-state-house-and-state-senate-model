import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/war/post2016_southern_war_v3"
# The exact run reviewed on 2026-09-07 is preserved unchanged; its documentation-only
# contract disposition is verified against this archive, not against the live run.
ARCHIVED_RUN = ROOT / "data/processed/war/post2016_southern_war_v3_archive/WAR-POST2016-V3-8BB52074EC806C5BF6BF"
RACE_KEYS = ["state_code", "cycle", "chamber", "district"]


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / name, low_memory=False)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_report(record, manifest, run_dir=OUT, disposition=None):
    actual = digest(ROOT / record["path"])
    if actual == record["sha256"]:
        return
    # Only this independently reviewed documentation change has a disposition.
    if disposition is None:
        disposition = json.loads((ROOT / "project_docs/audits/SOUTHERN_V3_CONTRACT_COMPATIBILITY.json").read_text())
    assert disposition["status"] == "approved_documentation_only"
    assert disposition["reviewer"] == "/root/al2022_source_implementation"
    assert record["path"] == disposition["contract_path"] == "project_docs/model/POST2016_SOUTHERN_WAR_V3_FIELD_CONTRACT.md"
    assert manifest["model_run_id"] == disposition["model_run_id"] == "WAR-POST2016-V3-8BB52074EC806C5BF6BF"
    assert digest(run_dir / "manifest.json") == disposition["manifest_sha256"] == "0ea558730b9e953d95853d552960886c855b8bb3f9fb9cb2ee0a3c44a47c7638"
    assert disposition["archived_contract_path"] == "project_docs/audits/SOUTHERN_V3_RUN_8BB52074_FIELD_CONTRACT.md"
    assert digest(ROOT / disposition["archived_contract_path"]) == record["sha256"] == disposition["recorded_sha256"] == "272c60027414654d37ef6d5851cc6224cb432ea12bdf6df05cf53a48b0c7ae32"
    assert actual == disposition["current_sha256"] == "3de27261136fb5574fc7be90b23d599de919c9b8226a2c62772b5936190618dc"
    assert manifest["code_hashes"] == disposition["code_hashes"]
    for path, expected in disposition["code_hashes"].items():
        assert digest(ROOT / path) == expected


@pytest.mark.parametrize("field", ["status", "reviewer", "model_run_id", "manifest_sha256", "contract_path", "archived_contract_path", "recorded_sha256", "current_sha256", "code_hashes"])
def test_contract_disposition_cannot_mask_changed_evidence(field):
    manifest = json.loads((ARCHIVED_RUN / "manifest.json").read_text())
    disposition = json.loads((ROOT / "project_docs/audits/SOUTHERN_V3_CONTRACT_COMPATIBILITY.json").read_text())
    record = next(r for r in manifest["reports"] if r["path"] == disposition["contract_path"])
    assert digest(ROOT / record["path"]) != record["sha256"], "archived run must carry the run-era contract hash"
    verify_report(record, manifest, ARCHIVED_RUN)
    disposition[field] = {} if field == "code_hashes" else "changed"
    with pytest.raises(AssertionError):
        verify_report(record, manifest, ARCHIVED_RUN, disposition)


def test_archived_reviewed_run_is_preserved_byte_for_byte():
    manifest = json.loads((ARCHIVED_RUN / "manifest.json").read_text())
    assert manifest["model_run_id"] == "WAR-POST2016-V3-8BB52074EC806C5BF6BF"
    assert digest(ARCHIVED_RUN / "manifest.json") == "0ea558730b9e953d95853d552960886c855b8bb3f9fb9cb2ee0a3c44a47c7638"
    for record in manifest["outputs"]:
        assert digest(ARCHIVED_RUN / Path(record["path"]).name) == record["sha256"]


def test_all_strict_post2016_races_receive_residual_war():
    races = load("race_war.csv")
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert len(races) == manifest["diagnostics"]["training_rows"]
    assert len(races) >= 3658
    assert races.cycle.gt(2016).all()
    assert races.training_status.eq("strict_war_ready_no_finance").all()
    assert not races.duplicated(RACE_KEYS).any()
    np.testing.assert_allclose(
        races.raw_gap,
        races.legislative_dem_margin - races.baseline_dem_margin,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        races.war,
        races.raw_gap - races.fitted_structural_expected_gap,
        atol=1e-10,
    )
    np.testing.assert_allclose(races.war_magnitude, races.war.abs(), atol=1e-10)
    assert races.fitted_structural_expected_gap.notna().all()
    assert races.structural_fit_scope.eq("same_cycle_full_sample_descriptive").all()


def test_candidate_cycle_scores_are_orientations_not_pooled_effects():
    races = load("race_war.csv").set_index("war_outcome_id")
    candidates = load("candidate_cycle_war.csv")
    assert len(candidates) == 2 * len(races)
    assert not candidates.duplicated(["war_outcome_id", "canonical_party"]).any()
    assert candidates.score_identification.eq("race_differential_party_orientation").all()
    forbidden = {"candidate_war", "selected_penalty", "candidate_war_differential", "war_unexplained"}
    assert not forbidden.intersection(candidates.columns)
    oriented = candidates.pivot(
        index="war_outcome_id", columns="canonical_party", values="candidate_cycle_war"
    )
    np.testing.assert_allclose(oriented.D, races.war.reindex(oriented.index), atol=1e-10)
    np.testing.assert_allclose(oriented.R, -oriented.D, atol=1e-10)


def test_cross_fitted_values_are_separate_validation_diagnostics():
    races = load("race_war.csv")
    validation = load("validation_cross_fitted_predictions.csv")
    assert validation.validation_self_excluded.eq(True).all()
    assert validation.validation_training_rows.gt(0).all()
    assert validation.validation_cross_fitted_expected_gap.notna().all()
    assert races.validation_cross_fitted_residual.notna().all()
    assert not np.allclose(
        races.fitted_structural_expected_gap,
        races.validation_cross_fitted_expected_gap,
    )


def test_grimsley_and_v2_correction_are_race_residuals():
    races = load("race_war.csv")
    dexter = races[races.dem_candidate_name.eq("Dexter Grimsley")]
    assert len(dexter) == 1
    row = dexter.iloc[0]
    assert row.war > 10
    assert row.war_party == "D"
    comparison = load("v2_correction_comparison.csv")
    assert len(comparison) == len(races)
    assert comparison.v2_pooled_candidate_differential_not_war.notna().all()
    np.testing.assert_allclose(comparison.war, races.war, atol=1e-10)


def test_manifest_hashes_contract_and_finance_exclusion():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    configuration = manifest["configuration"]
    assert configuration["headline_war_definition"] == "raw_gap - fitted_structural_expected_gap"
    assert configuration["headline_fit_scope"] == "same_cycle_full_sample_descriptive"
    assert configuration["candidate_pooling_in_headline_war"] is False
    assert configuration["finance_headline_included"] is False
    assert configuration["structural_selection"]["lag_added_value_status"] == "passes_lag_added_value_gate"
    assert manifest["diagnostics"]["training_rows"] == len(load("race_war.csv"))
    assert manifest["diagnostics"]["candidate_cycle_rows"] == len(load("candidate_cycle_war.csv"))
    assert manifest["diagnostics"]["max_war_formula_error"] < 1e-10
    assert manifest["diagnostics"]["max_candidate_orientation_error"] < 1e-10
    assert "split-ticket.org" in manifest["split_ticket_methodology"]["method_url"]
    for record in manifest["outputs"]:
        assert digest(ROOT / record["path"]) == record["sha256"]
    for record in manifest["reports"]:
        verify_report(record, manifest)
    for record in manifest["outputs"]:
        ids = pd.read_csv(ROOT / record["path"], usecols=["model_run_id"]).model_run_id
        assert ids.eq(manifest["model_run_id"]).all()
