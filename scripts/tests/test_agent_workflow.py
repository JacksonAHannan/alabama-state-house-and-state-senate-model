import csv
import json

from scripts.validate_agent_workflow import scopes_overlap, validate


def test_repository_agent_workflow_is_valid():
    assert validate() == []


def test_scope_overlap_detects_parent_and_child():
    assert scopes_overlap("data/processed/war/", "data/processed/war/run.csv")
    assert not scopes_overlap("dashboard/", "research/cmo_ideology/")


def test_validator_rejects_concurrent_write_collision(tmp_path):
    registry = tmp_path / "roles.json"
    registry.write_text(
        json.dumps({"roles": {"one": {"owns": ["data/"]}, "two": {"owns": ["docs/"]}}}),
        encoding="utf-8",
    )
    ledger = tmp_path / "tasks.csv"
    columns = [
        "task_id",
        "role",
        "owner",
        "status",
        "objective",
        "write_scopes",
        "upstream_snapshot",
        "validation_command",
    ]
    with ledger.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerow({"task_id": "A", "role": "one", "status": "active", "write_scopes": "data/processed/"})
        writer.writerow({"task_id": "B", "role": "two", "status": "review", "write_scopes": "data/processed/file.csv"})
    errors = validate(registry, ledger)
    assert any("overlapping live write scopes" in error for error in errors)
