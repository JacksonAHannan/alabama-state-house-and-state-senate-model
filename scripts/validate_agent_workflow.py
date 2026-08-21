"""Validate the repository's multi-agent role registry and active-task ledger."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COORDINATION = ROOT / "project_docs" / "coordination"
REGISTRY = COORDINATION / "agent_ownership.json"
LEDGER = COORDINATION / "active_tasks.csv"
LIVE_STATUSES = {"active", "review"}
VALID_STATUSES = {"planned", "active", "blocked", "review", "complete"}
REQUIRED_COLUMNS = {
    "task_id",
    "role",
    "owner",
    "status",
    "objective",
    "write_scopes",
    "upstream_snapshot",
    "validation_command",
}


def normalize_scope(value: str) -> str:
    """Return a comparable repository-relative scope with POSIX separators."""
    scope = value.strip().replace("\\", "/").strip("/")
    while "//" in scope:
        scope = scope.replace("//", "/")
    return scope


def scopes_overlap(left: str, right: str) -> bool:
    """Conservatively detect equal, parent/child, and identical glob scopes."""
    left = normalize_scope(left)
    right = normalize_scope(right)
    if not left or not right:
        return False
    if left == right:
        return True
    # Glob patterns cannot safely be proven disjoint when their fixed roots nest.
    left_root = left.split("*", 1)[0].rstrip("/")
    right_root = right.split("*", 1)[0].rstrip("/")
    if not left_root or not right_root:
        return True
    return (
        left_root == right_root
        or left_root.startswith(right_root + "/")
        or right_root.startswith(left_root + "/")
    )


def validate(registry_path: Path = REGISTRY, ledger_path: Path = LEDGER) -> list[str]:
    errors: list[str] = []
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    roles = registry.get("roles", {})
    if not roles:
        errors.append("ownership registry defines no roles")
    for role, definition in roles.items():
        if not definition.get("owns"):
            errors.append(f"role {role!r} has no owned scopes")

    with ledger_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            errors.append(f"active task ledger is missing columns: {sorted(missing)}")
            return errors
        rows = list(reader)

    seen_ids: set[str] = set()
    live: list[tuple[str, str, str]] = []
    for line_number, row in enumerate(rows, start=2):
        task_id = row["task_id"].strip()
        role = row["role"].strip()
        status = row["status"].strip()
        if not task_id:
            errors.append(f"line {line_number}: missing task_id")
        elif task_id in seen_ids:
            errors.append(f"line {line_number}: duplicate task_id {task_id!r}")
        seen_ids.add(task_id)
        if role not in roles:
            errors.append(f"line {line_number}: unknown role {role!r}")
        if status not in VALID_STATUSES:
            errors.append(f"line {line_number}: invalid status {status!r}")
        scopes = [normalize_scope(scope) for scope in row["write_scopes"].split(";")]
        scopes = [scope for scope in scopes if scope]
        if status in LIVE_STATUSES and not scopes:
            errors.append(f"line {line_number}: live task {task_id!r} has no write scope")
        if status in LIVE_STATUSES:
            live.extend((task_id, role, scope) for scope in scopes)

    for index, (left_id, left_role, left_scope) in enumerate(live):
        for right_id, right_role, right_scope in live[index + 1 :]:
            if left_id == right_id:
                continue
            if scopes_overlap(left_scope, right_scope):
                errors.append(
                    "overlapping live write scopes: "
                    f"{left_id} ({left_role}: {left_scope}) and "
                    f"{right_id} ({right_role}: {right_scope})"
                )
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Agent workflow validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Agent workflow validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
