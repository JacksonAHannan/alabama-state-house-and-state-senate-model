from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import build_southern_historical_war_v1 as builder
from southern_war_map_contract import scheduled_keys_2016_2024
from southern_war_release_gate import ReleaseGateError


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/war/southern_historical_war_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blocked_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """An exact but blocked upstream decision; independent of the live decision file."""
    published = tmp_path / "published"
    published.mkdir()
    manifest = published / "manifest.json"
    manifest.write_text(json.dumps({"model_run_id": "RUN-FIXTURE"}), encoding="utf-8")
    review = tmp_path / "project_docs/audits/review.md"
    review.parent.mkdir(parents=True)
    review.write_text("Decision: NOT APPROVED\n", encoding="utf-8")
    decision = tmp_path / "project_docs/audits/decision.json"
    decision.write_text(json.dumps({
        "schema_version": 1, "model_run_id": "RUN-FIXTURE", "manifest_path": "published/manifest.json",
        "manifest_sha256": digest(manifest), "decision": "blocked_insufficient_evidence",
        "review_record_path": "project_docs/audits/review.md", "review_record_sha256": digest(review),
    }), encoding="utf-8")
    return published, decision


def test_builder_refuses_pending_upstream_release_before_loading_history(monkeypatch, tmp_path) -> None:
    loaded = False

    def forbidden_load():
        nonlocal loaded
        loaded = True
        raise AssertionError("warehouse history should not be read")

    published, decision = blocked_fixture(tmp_path)
    monkeypatch.setattr(builder, "PUBLISHED", published)
    monkeypatch.setattr(builder, "V3_RELEASE_DECISION", decision)
    monkeypatch.setattr(builder, "load_strict_history", forbidden_load)
    monkeypatch.setattr(builder, "load_outcome_inventory", forbidden_load)
    with pytest.raises(ReleaseGateError, match="blocked_insufficient_evidence"):
        builder.main()
    assert loaded is False


def coverage_fixture():
    schedule = pd.DataFrame(sorted(scheduled_keys_2016_2024()), columns=["state_code", "cycle", "chamber"])
    strict = [
        ("S1", "AL", 2018, "lower", "1", builder.v2.TRAINING_STATUS, 1, 1, "SRC-CANVASS"),
        ("S2", "AL", 2022, "upper", "2", builder.v2.TRAINING_STATUS, 1, 1, "SRC-CANVASS"),
        ("S3", "VA", 2019, "lower", "3", builder.v2.TRAINING_STATUS, 1, 1, None),
        ("S4", "FL", 2016, "lower", "4", builder.v2.TRAINING_STATUS, 1, 1, "SRC-FL"),
    ]
    excluded = [
        ("E1", "VA", 2017, "lower", "5", "research_war_ready_no_finance", 0, 1, None),
        ("E2", "VA", 2021, "lower", "6", "research_war_ready_no_finance", 0, 1, None),
        ("E3", "FL", 2024, "lower", "7", "research_war_ready_no_finance", 1, 0, "SRC-FL"),
    ]
    inventory = pd.DataFrame(strict + excluded, columns=[
        "war_outcome_id", "state_code", "cycle", "chamber", "district", "training_status",
        "strict_baseline_eligible", "strict_incumbency_eligible", "source_file_id",
    ])
    races = pd.DataFrame({
        "war_outcome_id": ["S1", "S2", "S3", "S4"], "state_code": ["AL", "AL", "VA", "FL"],
        "cycle": [2018, 2022, 2019, 2016], "chamber": ["lower", "upper", "lower", "lower"],
        "district": ["1", "2", "3", "4"], "finance_complete": [1, 0, 1, 0],
        "geography_vintage": ["provider-reported; plan vintage unverified"] * 4,
    })
    return races, inventory, schedule


def test_state_release_coverage_conserves_counts_and_exclusion_classes() -> None:
    races, inventory, schedule = coverage_fixture()
    coverage = builder.state_release_coverage(races, inventory, schedule, "WAR-V3", "RUN-W").set_index("state_code")
    assert list(coverage.reset_index().columns) == builder.COVERAGE_COLUMNS
    assert len(coverage) == 14
    assert coverage.scheduled_slices.sum() == 116
    assert coverage.scored_races.sum() == 4
    assert coverage.excluded_research_outcomes.sum() == 3
    alabama = coverage.loc["AL"]
    assert (alabama.scored_races, alabama.strict_races_registered_source_file, alabama.strict_races_source_file_unresolved) == (2, 2, 0)
    assert alabama.published_post2016_races == 2 and alabama.backcast_2016_races == 0
    assert alabama.finance_complete_races == 1
    virginia = coverage.loc["VA"]
    assert (virginia.excluded_baseline_not_strict, virginia.excluded_incumbency_experimental) == (2, 0)
    assert virginia.strict_races_source_file_unresolved == 1
    assert virginia.empty_scheduled_slices == 5  # only the 2019 lower slice is scored in the fixture
    florida = coverage.loc["FL"]
    assert (florida.backcast_2016_races, florida.excluded_incumbency_experimental) == (1, 1)
    assert coverage.loc["TX", "plan_provenance"] == "no scored races"
    assert coverage.upstream_model_run_id.eq("WAR-V3").all() and coverage.warehouse_build_run_id.eq("RUN-W").all()


@pytest.mark.parametrize("change", ["extra_race", "unclassified_exclusion"])
def test_state_release_coverage_refuses_inconsistent_inventory(change) -> None:
    races, inventory, schedule = coverage_fixture()
    if change == "extra_race":
        races = pd.concat([races, races.iloc[[0]].assign(war_outcome_id="S9")], ignore_index=True)
    if change == "unclassified_exclusion":
        inventory.loc[inventory.war_outcome_id.eq("E3"), "strict_incumbency_eligible"] = 1
    with pytest.raises(ValueError):
        builder.state_release_coverage(races, inventory, schedule, "WAR-V3", "RUN-W")


def test_southern_historical_war_release_contract() -> None:
    races = pd.read_csv(OUT / "race_war.csv", low_memory=False)
    candidates = pd.read_csv(OUT / "candidate_cycle_war.csv", low_memory=False)
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert len(races) == manifest["diagnostics"]["scored_races"]
    assert len(candidates) == manifest["diagnostics"]["candidate_cycle_rows"]
    assert races.state_code.nunique() == 14
    assert set(races.cycle) == {2016, 2018, 2019, 2020, 2022, 2023, 2024}
    assert manifest["diagnostics"]["scheduled_slices"] == 116
    assert not races.duplicated(["state_code", "cycle", "chamber", "district"]).any()
    assert manifest["diagnostics"]["backcast_races"] == 620
    np.testing.assert_allclose(
        races.war, races.raw_gap - races.fitted_structural_expected_gap, atol=1e-10
    )
    for record in manifest["outputs"]:
        assert digest(ROOT / record["path"]) == record["sha256"]


def test_2016_is_backcast_and_later_scores_are_published_residuals() -> None:
    races = pd.read_csv(OUT / "race_war.csv", low_memory=False)
    assert races.loc[races.cycle.eq(2016), "scoring_scope"].eq(
        "post2016_southern_model_backcast"
    ).all()
    assert races.loc[races.cycle.gt(2016), "scoring_scope"].eq(
        "published_same_cycle_residual"
    ).all()
    published = pd.read_csv(
        ROOT / "data/processed/war/post2016_southern_war_v3/race_war.csv", low_memory=False
    )
    keys = ["state_code", "cycle", "chamber", "district"]
    check = races[races.cycle.gt(2016)].merge(
        published[keys + ["war"]], on=keys, validate="one_to_one", suffixes=("", "_published")
    )
    np.testing.assert_allclose(check.war, check.war_published, atol=1e-10)
    assert len(check) == len(published)
    assert set(races.loc[races.cycle.eq(2024), "state_code"]) == {
        "AR", "FL", "GA", "KY", "MO", "NC", "OK", "SC", "TN", "TX"
    }


def test_candidate_orientation_names_and_finance_missingness() -> None:
    races = pd.read_csv(OUT / "race_war.csv", low_memory=False)
    candidates = pd.read_csv(OUT / "candidate_cycle_war.csv", low_memory=False)
    paired = candidates.pivot(index="war_outcome_id", columns="canonical_party", values="candidate_cycle_war")
    np.testing.assert_allclose(paired.D + paired.R, 0.0, atol=1e-10)
    assert not candidates.candidate_name.str.fullmatch(r"[A-Z]{3}\d{2,3}[A-Z]{3,}", na=False).any()
    assert not candidates.candidate_name.str.contains("committee", case=False, na=False).any()
    assert not candidates.candidate_name.astype(str).str.strip().str.lower().isin({"", "nan", "none", "null"}).any()
    names = candidates.set_index(["state_code", "cycle", "chamber", "district", "canonical_party"])
    assert names.loc[("AL", 2022, "lower", 12, "D"), "candidate_name"] == "James C. Fields, Jr."
    assert names.loc[("AL", 2022, "lower", 27, "D"), "candidate_name"] == "Herb Neu"
    assert names.loc[("AL", 2022, "lower", 47, "D"), "candidate_name"] == "Christian Coleman"
    incomplete = races.finance_complete.eq(0)
    assert races.loc[incomplete, ["democratic_fundraising", "republican_fundraising", "log_fundraising_ratio_d_to_r"]].isna().all().all()
