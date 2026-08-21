"""Validate the documented CMO hypothesis registry."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "project_docs" / "model" / "cmo_hypothesis_registry.csv"
REQUIRED = {
    "hypothesis_id", "family", "variable_or_construct", "unit",
    "temporal_status", "causal_role", "expected_cmo_relationship",
    "current_status", "current_field_or_source", "preferred_test", "priority",
}
PRIORITIES = {"P0", "P1", "P2"}


def validate(path: Path = REGISTRY) -> list[str]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    errors: list[str] = []
    missing = REQUIRED - set(frame.columns)
    if missing:
        return [f"missing columns: {sorted(missing)}"]
    if frame.hypothesis_id.duplicated().any():
        errors.append("hypothesis_id must be unique")
    blank_columns = [column for column in REQUIRED if frame[column].str.strip().eq("").any()]
    if blank_columns:
        errors.append(f"blank required values in: {sorted(blank_columns)}")
    invalid_priorities = set(frame.priority) - PRIORITIES
    if invalid_priorities:
        errors.append(f"invalid priorities: {sorted(invalid_priorities)}")
    required_families = {
        "partisan_context", "demographics", "candidate_history", "finance",
        "ideology", "measurement", "selection",
    }
    absent = required_families - set(frame.family)
    if absent:
        errors.append(f"missing hypothesis families: {sorted(absent)}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("CMO hypothesis registry validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    frame = pd.read_csv(REGISTRY)
    print(f"CMO hypothesis registry validation passed ({len(frame)} hypotheses).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
