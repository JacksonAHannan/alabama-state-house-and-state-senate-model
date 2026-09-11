"""Every publication builder must refuse stale, unreviewed, or drifted inputs.

The fixture builds a miniature repository whose declared hashes all agree, then
mutates exactly one declaration per test.  No builder reads the real manifests,
so a real upstream refresh cannot make these checks vacuous.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_2026_forecast_dashboard as dashboard
import build_alabama_historical_war_v1 as historical
import build_alabama_war_v1 as alabama
import build_war_story_page as story
from southern_war_release_gate import APPROVED_DECISION, ReleaseGateError


SOUTHERN_RUN = "WAR-TEST-APPROVED"
ALABAMA_RUN = "AL-WAR-TEST"
HISTORICAL_RUN = "AL-HIST-WAR-TEST"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict) -> Path:
    return _write(path, json.dumps(payload, indent=2) + "\n")


def _build_tree(root: Path) -> SimpleNamespace:
    southern_dir = root / "data/processed/war/post2016_southern_war_v3"
    alabama_dir = root / "data/processed/war/alabama_war_v1"
    historical_dir = root / "data/processed/war/alabama_historical_war_v1"
    forecast_dir = root / "data/processed/forecast_calibration"

    southern_race = _write(southern_dir / "race_war.csv", "cycle,war\n2018,1.0\n")
    southern_candidate = _write(southern_dir / "candidate_cycle_war.csv", "cycle,party\n2018,D\n")
    southern_coverage = _write(southern_dir / "coverage.csv", "chamber,races\nlower,1\n")
    contract = _write(
        root / "project_docs/model/ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md",
        "# contract\n",
    )

    southern_manifest = {
        "schema_version": 1,
        "model_run_id": SOUTHERN_RUN,
        "input_hashes": {
            "data/processed/war/post2016_southern_war_v3/race_war.csv": _digest(southern_race),
            "data/processed/war/post2016_southern_war_v3/candidate_cycle_war.csv": _digest(southern_candidate),
        },
        "outputs": [
            {
                "path": "data/processed/war/post2016_southern_war_v3/coverage.csv",
                "sha256": _digest(southern_coverage),
            }
        ],
    }
    southern_manifest_path = _write_json(southern_dir / "manifest.json", southern_manifest)

    review = _write(root / "project_docs/audits/review.md", "independent review\n")
    decision_path = _write_json(
        root / "project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json",
        {
            "schema_version": 1,
            "model_run_id": SOUTHERN_RUN,
            "manifest_path": "data/processed/war/post2016_southern_war_v3/manifest.json",
            "manifest_sha256": _digest(southern_manifest_path),
            "decision": APPROVED_DECISION,
            "review_record_path": "project_docs/audits/review.md",
            "review_record_sha256": _digest(review),
        },
    )

    alabama_race = _write(alabama_dir / "race_war.csv", "cycle,war\n2018,1.0\n")
    alabama_manifest_path = _write_json(
        alabama_dir / "manifest.json",
        {
            "alabama_war_run_id": ALABAMA_RUN,
            "source_model_run_id": SOUTHERN_RUN,
            "input_hashes": {
                "data/processed/war/post2016_southern_war_v3/race_war.csv": _digest(southern_race),
                "project_docs/model/ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md": _digest(contract),
            },
            "outputs": [
                {"path": "data/processed/war/alabama_war_v1/race_war.csv", "sha256": _digest(alabama_race)}
            ],
        },
    )

    historical_race = _write(historical_dir / "race_war.csv", "cycle,war\n1994,0.5\n")
    historical_manifest_path = _write_json(
        historical_dir / "manifest.json",
        {
            "historical_war_run_id": HISTORICAL_RUN,
            "source_southern_war_run_id": SOUTHERN_RUN,
            "source_alabama_war_run_id": ALABAMA_RUN,
            "input_hashes": {
                "data/processed/war/alabama_war_v1/race_war.csv": _digest(alabama_race),
            },
            "outputs": [
                {
                    "path": "data/processed/war/alabama_historical_war_v1/race_war.csv",
                    "sha256": _digest(historical_race),
                }
            ],
        },
    )

    scenarios = _write(
        forecast_dir / "alabama_war_forecast_v1_scenarios.csv", "district,margin\n1,0.0\n"
    )
    forecast_manifest_path = _write_json(
        forecast_dir / "alabama_war_forecast_v1_manifest.json",
        {
            "build_id": "TEST-BUILD",
            "inputs": [
                {"path": "data/processed/war/alabama_war_v1/race_war.csv", "sha256": _digest(alabama_race)}
            ],
            "outputs": [
                {
                    "path": "data/processed/forecast_calibration/alabama_war_forecast_v1_scenarios.csv",
                    "sha256": _digest(scenarios),
                }
            ],
        },
    )

    return SimpleNamespace(
        root=root,
        southern_dir=southern_dir,
        alabama_dir=alabama_dir,
        historical_dir=historical_dir,
        forecast_dir=forecast_dir,
        southern_manifest=southern_manifest_path,
        alabama_manifest=alabama_manifest_path,
        historical_manifest=historical_manifest_path,
        forecast_manifest=forecast_manifest_path,
        decision=decision_path,
        southern_race=southern_race,
        contract=contract,
        alabama_race=alabama_race,
        historical_race=historical_race,
        scenarios=scenarios,
    )


@pytest.fixture
def tree(tmp_path: Path) -> SimpleNamespace:
    return _build_tree(tmp_path)


def _patch_alabama(monkeypatch: pytest.MonkeyPatch, tree: SimpleNamespace) -> None:
    monkeypatch.setattr(alabama, "ROOT", tree.root)
    monkeypatch.setattr(alabama, "SOURCE", tree.southern_dir)
    monkeypatch.setattr(alabama, "DECISION", tree.decision)


def _patch_historical(monkeypatch: pytest.MonkeyPatch, tree: SimpleNamespace) -> None:
    monkeypatch.setattr(historical, "ROOT", tree.root)
    monkeypatch.setattr(historical, "SOUTHERN_MANIFEST", tree.southern_manifest)
    monkeypatch.setattr(historical, "PUBLISHED_ALABAMA", tree.alabama_dir)
    monkeypatch.setattr(historical, "DECISION", tree.decision)


def _patch_story(monkeypatch: pytest.MonkeyPatch, tree: SimpleNamespace) -> None:
    monkeypatch.setattr(story, "ROOT", tree.root)
    monkeypatch.setattr(story, "HISTORICAL_MANIFEST", tree.historical_manifest)
    monkeypatch.setattr(story, "PUBLISHED_ALABAMA", tree.alabama_dir)
    monkeypatch.setattr(story, "DECISION", tree.decision)


def _patch_dashboard(monkeypatch: pytest.MonkeyPatch, tree: SimpleNamespace) -> None:
    monkeypatch.setattr(dashboard, "ROOT", tree.root)
    monkeypatch.setattr(dashboard, "FORECAST_MANIFEST", tree.forecast_manifest)


def _reject(monkeypatch, tree, patch, message: str, *mutations) -> None:
    patch(monkeypatch, tree)
    for mutate in mutations:
        mutate()


# --- Alabama WAR v1 -------------------------------------------------------


def test_alabama_war_v1_fresh_inputs_pass(monkeypatch, tree):
    _patch_alabama(monkeypatch, tree)
    manifest, decision = alabama.require_fresh_inputs()
    assert manifest["model_run_id"] == SOUTHERN_RUN
    assert decision["decision"] == APPROVED_DECISION


def test_alabama_war_v1_rejects_unapproved_decision(monkeypatch, tree):
    original = json.loads(tree.decision.read_text(encoding="utf-8"))
    original["decision"] = "blocked_insufficient_evidence"
    _reject(
        monkeypatch,
        tree,
        _patch_alabama,
        re.escape("blocked_insufficient_evidence"),
        lambda: _write_json(tree.decision, original),
    )


def test_alabama_war_v1_rejects_mismatched_derived_run_id(monkeypatch, tree):
    original = json.loads(tree.decision.read_text(encoding="utf-8"))
    original["model_run_id"] = "WAR-TEST-OTHER"
    _reject(
        monkeypatch,
        tree,
        _patch_alabama,
        re.escape("run_id"),
        lambda: _write_json(tree.decision, original),
    )


def test_alabama_war_v1_rejects_changed_declared_input(monkeypatch, tree):
    _reject(
        monkeypatch,
        tree,
        _patch_alabama,
        re.escape("Declared manifest file changed"),
        lambda: _write(tree.southern_race, "cycle,war\n2018,9.9\n"),
    )


def test_alabama_war_v1_rejects_missing_declared_output(monkeypatch, tree):
    _reject(
        monkeypatch,
        tree,
        _patch_alabama,
        re.escape("Declared manifest file unavailable"),
        lambda: (tree.southern_dir / "coverage.csv").unlink(),
    )


# --- Alabama historical WAR v1 -------------------------------------------


def test_alabama_historical_war_v1_fresh_inputs_pass(monkeypatch, tree):
    _patch_historical(monkeypatch, tree)
    approved, published, decision = historical.require_fresh_inputs()
    assert approved["model_run_id"] == SOUTHERN_RUN
    assert published["alabama_war_run_id"] == ALABAMA_RUN
    assert decision["decision"] == APPROVED_DECISION


def test_alabama_historical_war_v1_rejects_unapproved_southern_decision(monkeypatch, tree):
    original = json.loads(tree.decision.read_text(encoding="utf-8"))
    original["decision"] = "blocked_insufficient_evidence"
    _reject(
        monkeypatch,
        tree,
        _patch_historical,
        re.escape("blocked_insufficient_evidence"),
        lambda: _write_json(tree.decision, original),
    )


def test_alabama_historical_war_v1_rejects_derived_run_id_mismatch(monkeypatch, tree):
    original = json.loads(tree.alabama_manifest.read_text(encoding="utf-8"))
    original["source_model_run_id"] = "WAR-POST2016-V3-NOTAPPROVED"
    _reject(
        monkeypatch,
        tree,
        _patch_historical,
        re.escape("Alabama WAR v1 derives from WAR-POST2016-V3-NOTAPPROVED"),
        lambda: _write_json(tree.alabama_manifest, original),
    )


def test_alabama_historical_war_v1_rejects_changed_declared_input(monkeypatch, tree):
    _reject(
        monkeypatch,
        tree,
        _patch_historical,
        re.escape("Declared manifest file changed"),
        lambda: _write(tree.contract, "# mutated contract\n"),
    )


def test_alabama_historical_war_v1_rejects_missing_declared_output(monkeypatch, tree):
    _reject(
        monkeypatch,
        tree,
        _patch_historical,
        re.escape("Declared manifest file unavailable"),
        lambda: tree.alabama_race.unlink(),
    )


# --- Historical Alabama WAR page -----------------------------------------


def test_story_page_fresh_inputs_pass(monkeypatch, tree):
    _patch_story(monkeypatch, tree)
    manifest = story.require_fresh_inputs()
    assert manifest["historical_war_run_id"] == HISTORICAL_RUN


def test_story_page_rejects_unapproved_southern_run(monkeypatch, tree):
    original = json.loads(tree.decision.read_text(encoding="utf-8"))
    original["model_run_id"] = "WAR-POST2016-V3-NOTAPPROVED"
    _reject(
        monkeypatch,
        tree,
        _patch_story,
        re.escape("not approved WAR-POST2016-V3-NOTAPPROVED"),
        lambda: _write_json(tree.decision, original),
    )


def test_story_page_rejects_alabama_run_mismatch(monkeypatch, tree):
    original = json.loads(tree.alabama_manifest.read_text(encoding="utf-8"))
    original["alabama_war_run_id"] = "AL-WAR-OTHER"
    _reject(
        monkeypatch,
        tree,
        _patch_story,
        re.escape("not published AL-WAR-OTHER"),
        lambda: _write_json(tree.alabama_manifest, original),
    )


def test_story_page_rejects_changed_declared_input(monkeypatch, tree):
    _reject(
        monkeypatch,
        tree,
        _patch_story,
        re.escape("Declared manifest file changed"),
        lambda: _write(tree.alabama_race, "cycle,war\n2018,9.9\n"),
    )


def test_story_page_rejects_missing_declared_output(monkeypatch, tree):
    _reject(
        monkeypatch,
        tree,
        _patch_story,
        re.escape("Declared manifest file unavailable"),
        lambda: tree.historical_race.unlink(),
    )


# --- 2026 forecast dashboard ---------------------------------------------


def test_forecast_dashboard_fresh_inputs_pass(monkeypatch, tree):
    _patch_dashboard(monkeypatch, tree)
    manifest = dashboard.require_fresh_inputs()
    assert manifest["build_id"] == "TEST-BUILD"


def test_forecast_dashboard_rejects_changed_declared_input(monkeypatch, tree):
    _reject(
        monkeypatch,
        tree,
        _patch_dashboard,
        re.escape("Declared forecast input changed: data/processed/war/alabama_war_v1/race_war.csv"),
        lambda: _write(tree.alabama_race, "cycle,war\n2018,9.9\n"),
    )


def test_forecast_dashboard_rejects_missing_declared_output(monkeypatch, tree):
    _reject(
        monkeypatch,
        tree,
        _patch_dashboard,
        re.escape("Declared forecast input unavailable"),
        lambda: tree.scenarios.unlink(),
    )


def test_forecast_dashboard_rejects_declaration_outside_repository(monkeypatch, tree):
    original = json.loads(tree.forecast_manifest.read_text(encoding="utf-8"))
    original["inputs"] = [{"path": "../escape.csv", "sha256": "0" * 64}]
    _reject(
        monkeypatch,
        tree,
        _patch_dashboard,
        re.escape("Forecast file outside repository"),
        lambda: _write_json(tree.forecast_manifest, original),
    )
