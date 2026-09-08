"""Verify an exact independent release decision before Southern WAR reuse.

The model manifest records how an artifact was built.  Release approval is a
separate review decision, so downstream builders must verify both files and the
review record that supports the decision.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


APPROVED_DECISION = "approved_for_descriptive_historical_use"


class ReleaseGateError(ValueError):
    """Raised when an artifact lacks an exact, approved release decision."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_approved_release(
    manifest_path: Path,
    decision_path: Path,
    *,
    run_id_field: str = "model_run_id",
) -> tuple[dict[str, object], dict[str, object]]:
    """Return exact manifest/decision records only after the release gate passes."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    review_path = decision_path.parents[2] / str(decision["review_record_path"])

    checks = {
        "schema_version": decision.get("schema_version") == 1,
        "manifest_path": decision.get("manifest_path")
        == manifest_path.relative_to(decision_path.parents[2]).as_posix(),
        "manifest_sha256": decision.get("manifest_sha256") == sha256(manifest_path),
        "run_id": decision.get(run_id_field) == manifest.get(run_id_field),
        "review_record_exists": review_path.is_file(),
        "review_record_sha256": review_path.is_file()
        and decision.get("review_record_sha256") == sha256(review_path),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ReleaseGateError(
            "Southern WAR release decision does not match its evidence: "
            + ", ".join(failed)
        )
    if decision.get("decision") != APPROVED_DECISION:
        raise ReleaseGateError(
            "Southern WAR release is blocked by exact review decision: "
            f"{decision.get('decision', 'missing')}"
        )
    return manifest, decision
