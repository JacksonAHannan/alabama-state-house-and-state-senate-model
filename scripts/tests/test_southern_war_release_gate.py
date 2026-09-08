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
