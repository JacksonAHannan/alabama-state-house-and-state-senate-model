from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from southern_war_release_gate import (
    APPROVED_DECISION,
    ReleaseGateError,
    require_approved_release,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data/processed/war/post2016_southern_war_v3/manifest.json"
DECISION = ROOT / "project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_v3_release_decision_is_exact_and_enforced() -> None:
    """The live decision must bind the live manifest and review record exactly.

    Whether it approves or blocks is a review outcome, not a test fixture; the
    gate must pass only for an approval and must otherwise name the decision.
    """
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert decision["manifest_sha256"] == digest(MANIFEST)
    assert decision["model_run_id"] == manifest["model_run_id"]
    review = ROOT / decision["review_record_path"]
    assert review.is_file() and decision["review_record_sha256"] == digest(review)
    if decision["decision"] == APPROVED_DECISION:
        loaded_manifest, loaded_decision = require_approved_release(MANIFEST, DECISION)
        assert loaded_manifest["model_run_id"] == manifest["model_run_id"]
        assert loaded_decision["decision"] == APPROVED_DECISION
    else:
        with pytest.raises(ReleaseGateError, match=decision["decision"]):
            require_approved_release(MANIFEST, DECISION)


def test_exact_approved_decision_passes(tmp_path: Path) -> None:
    root = tmp_path
    manifest = root / "artifacts/manifest.json"
    review = root / "project_docs/audits/review.md"
    decision = root / "project_docs/audits/decision.json"
    manifest.parent.mkdir(parents=True)
    review.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"model_run_id": "RUN-EXACT"}), encoding="utf-8")
    review.write_text("Decision: approved.\n", encoding="utf-8")
    decision.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "model_run_id": "RUN-EXACT",
                "manifest_path": "artifacts/manifest.json",
                "manifest_sha256": digest(manifest),
                "decision": APPROVED_DECISION,
                "review_record_path": "project_docs/audits/review.md",
                "review_record_sha256": digest(review),
            }
        ),
        encoding="utf-8",
    )
    loaded_manifest, loaded_decision = require_approved_release(manifest, decision)
    assert loaded_manifest["model_run_id"] == "RUN-EXACT"
    assert loaded_decision["decision"] == APPROVED_DECISION


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("manifest_sha256", "0" * 64, "manifest_sha256"),
        ("model_run_id", "RUN-OTHER", "run_id"),
        ("review_record_sha256", "0" * 64, "review_record_sha256"),
    ],
)
def test_decision_cannot_mask_changed_evidence(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    manifest = tmp_path / "artifacts/manifest.json"
    review = tmp_path / "project_docs/audits/review.md"
    decision = tmp_path / "project_docs/audits/decision.json"
    manifest.parent.mkdir(parents=True)
    review.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"model_run_id": "RUN-EXACT"}), encoding="utf-8")
    review.write_text("Decision: approved.\n", encoding="utf-8")
    record = {
        "schema_version": 1,
        "model_run_id": "RUN-EXACT",
        "manifest_path": "artifacts/manifest.json",
        "manifest_sha256": digest(manifest),
        "decision": APPROVED_DECISION,
        "review_record_path": "project_docs/audits/review.md",
        "review_record_sha256": digest(review),
    }
    record[field] = value
    decision.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ReleaseGateError, match=message):
        require_approved_release(manifest, decision)


@pytest.mark.parametrize("section", ["input_hashes", "code_hashes", "outputs", "reports"])
@pytest.mark.parametrize("change", ["changed", "missing"])
def test_approval_cannot_hide_changed_declared_files(tmp_path, section, change):
    """An unchanged approval must not authorize different dependency bytes."""
    test_exact_approved_decision_passes(tmp_path)
    manifest = tmp_path / "artifacts/manifest.json"
    decision = tmp_path / "project_docs/audits/decision.json"
    dependency = tmp_path / "artifacts/source.txt"
    dependency.write_text("reviewed bytes", encoding="utf-8")
    record = json.loads(manifest.read_text(encoding="utf-8"))
    path = dependency.relative_to(tmp_path).as_posix()
    record[section] = ({path: digest(dependency)} if section.endswith("hashes")
                       else [{"path": path, "sha256": digest(dependency)}])
    manifest.write_text(json.dumps(record), encoding="utf-8")
    approval = json.loads(decision.read_text(encoding="utf-8"))
    approval["manifest_sha256"] = digest(manifest)
    decision.write_text(json.dumps(approval), encoding="utf-8")
    require_approved_release(manifest, decision)
    if change == "changed":
        dependency.write_text("unreviewed bytes", encoding="utf-8")
    else:
        dependency.unlink()
    with pytest.raises(ReleaseGateError, match="source.txt"):
        require_approved_release(manifest, decision)


def _approved_with_drifted_input(tmp_path: Path) -> tuple[Path, Path, Path, str, str]:
    """Approved bundle whose one declared input drifted after approval."""
    test_exact_approved_decision_passes(tmp_path)
    manifest = tmp_path / "artifacts/manifest.json"
    decision = tmp_path / "project_docs/audits/decision.json"
    dependency = tmp_path / "artifacts/source.txt"
    dependency.write_text("reviewed bytes", encoding="utf-8")
    declared = digest(dependency)
    record = json.loads(manifest.read_text(encoding="utf-8"))
    record["input_hashes"] = {"artifacts/source.txt": declared}
    manifest.write_text(json.dumps(record), encoding="utf-8")
    approval = json.loads(decision.read_text(encoding="utf-8"))
    approval["manifest_sha256"] = digest(manifest)
    decision.write_text(json.dumps(approval), encoding="utf-8")
    dependency.write_text("metadata-only bytes", encoding="utf-8")
    return manifest, decision, dependency, declared, digest(dependency)


def _revision(tmp_path: Path, declared: str, accepted: str, **overrides) -> dict:
    review = tmp_path / "project_docs/audits/revision_review.md"
    review.write_text("Revision reviewed: identical outputs.\n", encoding="utf-8")
    entry = {
        "path": "artifacts/source.txt",
        "declared_sha256": declared,
        "accepted_sha256": accepted,
        "review_record_path": "project_docs/audits/revision_review.md",
        "review_record_sha256": digest(review),
    }
    entry.update(overrides)
    return entry


def test_reviewed_input_revision_accepts_exact_revised_bytes(tmp_path: Path) -> None:
    manifest, decision, _dependency, declared, accepted = _approved_with_drifted_input(tmp_path)
    with pytest.raises(ReleaseGateError, match="source.txt"):
        require_approved_release(manifest, decision)
    approval = json.loads(decision.read_text(encoding="utf-8"))
    approval["accepted_input_revisions"] = [_revision(tmp_path, declared, accepted)]
    decision.write_text(json.dumps(approval), encoding="utf-8")
    loaded_manifest, _ = require_approved_release(manifest, decision)
    assert loaded_manifest["input_hashes"] == {"artifacts/source.txt": declared}


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"accepted_sha256": "0" * 64}, "source.txt"),          # third, unreviewed byte state
        ({"declared_sha256": "1" * 64}, "source.txt"),          # revision for a different declaration
        ({"path": "artifacts/other.txt"}, "source.txt"),        # revision for a different file
        ({"review_record_sha256": "2" * 64}, "review record"),  # unreviewed revision
        ({"review_record_path": "project_docs/audits/missing.md"}, "review record"),
        ({"accepted_sha256": None}, "Malformed"),
    ],
)
def test_input_revision_cannot_widen_into_file_existence(
    tmp_path: Path, override: dict, message: str
) -> None:
    manifest, decision, _dependency, declared, accepted = _approved_with_drifted_input(tmp_path)
    approval = json.loads(decision.read_text(encoding="utf-8"))
    entry = _revision(tmp_path, declared, accepted)
    entry.update(override)
    approval["accepted_input_revisions"] = [entry]
    decision.write_text(json.dumps(approval), encoding="utf-8")
    with pytest.raises(ReleaseGateError, match=message):
        require_approved_release(manifest, decision)


def test_input_revision_does_not_cover_a_second_drift(tmp_path: Path) -> None:
    manifest, decision, dependency, declared, accepted = _approved_with_drifted_input(tmp_path)
    approval = json.loads(decision.read_text(encoding="utf-8"))
    approval["accepted_input_revisions"] = [_revision(tmp_path, declared, accepted)]
    decision.write_text(json.dumps(approval), encoding="utf-8")
    require_approved_release(manifest, decision)
    dependency.write_text("a later, unreviewed change", encoding="utf-8")
    with pytest.raises(ReleaseGateError, match="source.txt"):
        require_approved_release(manifest, decision)


def test_training_frame_declaration_checks_live_content(tmp_path: Path) -> None:
    from southern_war_release_gate import require_declared_training_frame

    manifest = {"training_frame": {"sha256": "a" * 64}, "warehouse_build_run_id": "RUN-A"}
    require_declared_training_frame(manifest, live_digest=lambda: ("a" * 64, "RUN-A"))
    # Identical content from a later preparation run is not a changed dependency.
    require_declared_training_frame(manifest, live_digest=lambda: ("a" * 64, "RUN-B"))
    with pytest.raises(ReleaseGateError, match="training frame changed"):
        require_declared_training_frame(manifest, live_digest=lambda: ("b" * 64, "RUN-A"))
    with pytest.raises(ReleaseGateError, match="Malformed"):
        require_declared_training_frame({"training_frame": {"sha256": "short"}}, live_digest=lambda: ("a" * 64, "RUN-A"))
    # Manifests without the declaration are governed by file hashes alone.
    require_declared_training_frame({}, live_digest=lambda: (_ for _ in ()).throw(AssertionError("must not be called")))


def test_training_frame_digest_is_content_only() -> None:
    import pandas as pd

    from southern_war_training_frame import training_frame_digest

    frame = pd.DataFrame({"state_code": ["AL", "AL"], "cycle": [2018, 2022], "chamber": ["lower", "lower"],
                          "district": ["1", "2"], "war": [1.5, -0.25], "build_run_id": ["RUN-A", "RUN-A"]})
    rerun = frame.assign(build_run_id="RUN-B").iloc[::-1].reset_index(drop=True)
    assert training_frame_digest(frame) == training_frame_digest(rerun)
    assert training_frame_digest(frame) != training_frame_digest(frame.assign(war=[1.5, -0.26]))
