"""Verify an exact independent release decision before Southern WAR reuse.

The model manifest records how an artifact was built.  Release approval is a
separate review decision, so downstream builders must verify both files and the
review record that supports the decision.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


APPROVED_DECISION = "approved_for_descriptive_historical_use"


class ReleaseGateError(ValueError):
    """Raised when an artifact lacks an exact, approved release decision."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_sha256(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def reviewed_input_revisions(decision: dict, root: Path) -> dict[tuple[str, str], str]:
    """Return {(path, declared_sha256): accepted_sha256} for reviewed revisions.

    A revision is an explicit, independently reviewed statement that one declared
    input changed bytes after approval without changing what the approved run
    consumed.  Each entry must name the exact old and new digests and bind its
    own review record; anything less is rejected so an approval can never drift
    into file-existence acceptance.
    """
    revisions = decision.get("accepted_input_revisions", [])
    if not isinstance(revisions, list):
        raise ReleaseGateError("Malformed accepted_input_revisions")
    accepted: dict[tuple[str, str], str] = {}
    root = root.resolve()
    for entry in revisions:
        if not isinstance(entry, dict):
            raise ReleaseGateError("Malformed accepted_input_revisions entry")
        path = entry.get("path")
        declared = entry.get("declared_sha256")
        revised = entry.get("accepted_sha256")
        review = entry.get("review_record_path")
        if (not isinstance(path, str) or not path or not _is_sha256(declared)
                or not _is_sha256(revised) or declared == revised
                or not isinstance(review, str) or not review
                or not _is_sha256(entry.get("review_record_sha256"))):
            raise ReleaseGateError(f"Malformed accepted input revision: {path!r}")
        review_path = (root / review).resolve()
        if (Path(review).is_absolute() or not review_path.is_relative_to(root)
                or not review_path.is_file()
                or sha256(review_path) != entry["review_record_sha256"]):
            raise ReleaseGateError(f"Input revision review record does not match: {path}")
        key = (path, declared)
        if key in accepted:
            raise ReleaseGateError(f"Duplicate accepted input revision: {path}")
        accepted[key] = revised
    return accepted


def require_declared_files(
    manifest: dict, root: Path, accepted_revisions: dict[tuple[str, str], str] | None = None,
) -> None:
    """Check the declared snapshot; unchanged approval cannot hide file drift.

    ``accepted_revisions`` maps ``(path, declared_sha256)`` to the one revised
    digest an independent review accepted for that declaration; see
    :func:`reviewed_input_revisions`.  A file matching neither its declared nor
    its accepted digest is still rejected.
    """
    declarations = []
    try:
        for section in ("input_hashes", "code_hashes"):
            declarations.extend(manifest.get(section, {}).items())
        for section in ("outputs", "reports"):
            declarations.extend((entry["path"], entry["sha256"])
                                for entry in manifest.get(section, []))
    except (AttributeError, KeyError, TypeError) as error:
        raise ReleaseGateError("Malformed manifest file declarations") from error
    checked = {}
    root = root.resolve()
    for relative, expected in declarations:
        if not isinstance(relative, str) or not relative or not _is_sha256(expected):
            raise ReleaseGateError(f"Malformed manifest file declaration: {relative!r}")
        path = (root / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(root):
            raise ReleaseGateError(f"Manifest file outside repository: {relative}")
        if path not in checked:
            try:
                checked[path] = sha256(path)
            except OSError as error:
                raise ReleaseGateError(f"Declared manifest file unavailable: {relative}") from error
        if checked[path] == expected:
            continue
        if accepted_revisions and accepted_revisions.get((relative, expected)) == checked[path]:
            continue
        raise ReleaseGateError(f"Declared manifest file changed: {relative}")


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
    root = decision_path.parents[2]
    require_declared_files(manifest, root, reviewed_input_revisions(decision, root))
    require_declared_training_frame(manifest)
    return manifest, decision


def require_declared_training_frame(manifest: dict, live_digest=None) -> None:
    """Refuse when the warehouse no longer yields the training frame the run consumed.

    Manifests that declare ``training_frame`` (content digest of the one query
    the model reads, plus its warehouse run) are checked against the current
    warehouse; manifests without it are governed by their file declarations
    alone.  ``live_digest`` is injectable for tests and returns
    ``(sha256, warehouse_build_run_id)``.
    """
    declared = manifest.get("training_frame")
    if declared is None:
        return
    if not isinstance(declared, dict) or not _is_sha256(declared.get("sha256")):
        raise ReleaseGateError("Malformed training_frame declaration")
    if live_digest is None:
        from southern_war_training_frame import live_training_frame_digest as live_digest
    try:
        digest, _run_id = live_digest()
    except (ValueError, sqlite3.Error) as error:
        raise ReleaseGateError(f"Training frame could not be reloaded from the warehouse: {error}") from error
    if digest != declared["sha256"]:
        raise ReleaseGateError("Declared training frame changed in the warehouse")


def require_alabama_historical_release(
    historical_manifest_path: Path,
    alabama_manifest_path: Path,
    decision_path: Path,
) -> dict[str, object]:
    """Return the historical Alabama WAR manifest only if it is bound to approved runs.

    The historical export is not itself decision-bound, so consumers check that
    its declared files are unchanged, that its Southern source is the run the
    decision approves, and that its modern Alabama source is the published
    Alabama WAR v1 run on disk.
    """
    root = decision_path.parents[2]
    manifest = json.loads(historical_manifest_path.read_text(encoding="utf-8"))
    require_declared_files(manifest, root)
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    approved_run = decision.get("model_run_id")
    southern_run = manifest.get("source_southern_war_run_id")
    if southern_run != approved_run:
        raise ReleaseGateError(
            f"Alabama historical WAR derives from {southern_run}, not approved {approved_run}"
        )
    published = json.loads(alabama_manifest_path.read_text(encoding="utf-8"))
    alabama_run = manifest.get("source_alabama_war_run_id")
    published_run = published.get("alabama_war_run_id")
    if alabama_run != published_run:
        raise ReleaseGateError(
            f"Alabama historical WAR derives from Alabama WAR run {alabama_run}, "
            f"not published {published_run}"
        )
    return manifest
