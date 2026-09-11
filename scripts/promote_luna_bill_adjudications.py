"""Promote the full Luna bill-level adjudications into the live scoring file.

Per the accountable owner's decision on 2026-09-08, the human `frontier_manual_review`
layer is superseded by a complete Luna (`gpt-5.6-luna`) adjudication of every bill.
This script validates the Luna output produced by `adjudicate_frontier_bills_luna.py`,
backs up the existing human-curated manual file for provenance, then replaces the live
scoring file `data/manual/ideology/frontier_legislative_bill_adjudications.csv` with the
Luna adjudications in the identical schema.

Dry-run by default; pass --apply to perform the backup and replacement. The step performs
no commit and no publication.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
from pathlib import Path

import pandas as pd

from ideology_ontology_v3 import validate_primitive

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
MANUAL = ROOT / "data" / "manual" / "ideology" / "frontier_legislative_bill_adjudications.csv"
LUNA = ROOT / "data" / "manual" / "ideology" / "frontier_legislative_bill_adjudications_luna.csv"
COMPREHENSIVE = LEG / "comprehensive_rollcall_classifications.csv"
BACKUP_DIR = ROOT / "data" / "manual" / "ideology" / "backups"

EXPECTED_COLUMNS = [
    "bill_id", "session_year", "bill_number", "reviewed_document_type", "decision",
    "primitive_axes", "policy_poles", "confidence", "rationale", "reviewer",
    "review_date", "supersedes_authority",
]
SCORING = {"map", "multi_axis"}
NONSCORING = {"local_non_generalizable", "procedural", "symbolic",
              "mixed_no_scalar_direction", "insufficient_text"}
ALL_DECISIONS = SCORING | NONSCORING


def norm_bill_id(value: object) -> str:
    text = str(value).strip()
    if text in ("", "nan", "None", "NaN"):
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


def validate(luna: "pd.DataFrame") -> None:
    problems: list[str] = []
    if list(luna.columns) != EXPECTED_COLUMNS:
        problems.append(f"columns mismatch: {list(luna.columns)}")
    ids = luna["bill_id"].map(norm_bill_id)
    if not ids.is_unique:
        dupes = ids[ids.duplicated()].tolist()[:10]
        problems.append(f"non-unique bill_id (e.g. {dupes})")
    if (ids == "").any():
        problems.append("empty bill_id present")

    # Coverage: every comprehensive bill must be adjudicated.
    comp = pd.read_csv(COMPREHENSIVE, low_memory=False, usecols=["bill_id"])
    comp_ids = {norm_bill_id(x) for x in comp["bill_id"]}
    comp_ids.discard("")
    missing = comp_ids - set(ids)
    if missing:
        problems.append(f"{len(missing)} comprehensive bills lack a Luna adjudication "
                        f"(e.g. {sorted(missing)[:10]})")

    # Decision vocabulary and axis/pole validity.
    bad_decision = 0
    bad_axis = 0
    empty_scoring = 0
    nonscoring_with_axes = 0
    for row in luna.itertuples(index=False):
        decision = str(row.decision).strip()
        axes = [a for a in str(row.primitive_axes or "").split(";") if a.strip()]
        poles = [p for p in str(row.policy_poles or "").split(";") if p.strip()]
        if decision not in ALL_DECISIONS:
            bad_decision += 1
            continue
        if decision in SCORING:
            if not axes or len(axes) != len(poles):
                empty_scoring += 1
                continue
            if decision == "map" and len(axes) != 1:
                bad_axis += 1
            if decision == "multi_axis" and len(axes) < 2:
                bad_axis += 1
            for a, p in zip(axes, poles):
                try:
                    validate_primitive(a.strip(), p.strip())
                except ValueError:
                    bad_axis += 1
        else:  # non-scoring must carry no axes/poles
            if axes or poles:
                nonscoring_with_axes += 1
    if bad_decision:
        problems.append(f"{bad_decision} rows have an unrecognized decision")
    if empty_scoring:
        problems.append(f"{empty_scoring} scoring rows have missing/mismatched axes/poles")
    if bad_axis:
        problems.append(f"{bad_axis} scoring rows have an invalid axis/pole or wrong arity")
    if nonscoring_with_axes:
        problems.append(f"{nonscoring_with_axes} non-scoring rows carry axes/poles")

    if problems:
        raise SystemExit("VALIDATION FAILED:\n  - " + "\n  - ".join(problems))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="perform the backup and replacement")
    args = parser.parse_args()

    if not LUNA.exists():
        raise SystemExit(f"Luna output not found: {LUNA}")
    luna = pd.read_csv(LUNA, low_memory=False).fillna("")
    # Normalize bill_id to plain integer strings to match the existing manual file.
    luna["bill_id"] = luna["bill_id"].map(norm_bill_id)
    validate(luna)

    human = pd.read_csv(MANUAL, low_memory=False).fillna("") if MANUAL.exists() else None
    print(f"Luna rows: {len(luna):,}  (scoring: {int(luna['decision'].isin(SCORING).sum()):,})")
    print("Luna decision distribution:")
    for d, c in luna["decision"].value_counts().items():
        print(f"  {d:28s} {c}")
    if human is not None:
        print(f"\nHuman rows (to be superseded): {len(human):,}  "
              f"(scoring: {int(human['decision'].isin(SCORING).sum()):,})")
        print("Human decision distribution:")
        for d, c in human["decision"].value_counts().items():
            print(f"  {d:28s} {c}")

    if not args.apply:
        print("\n[dry-run] validation passed. Re-run with --apply to back up and replace.")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat().replace("-", "")
    backup = BACKUP_DIR / f"frontier_legislative_bill_adjudications.human_review.pre-luna-{stamp}.csv"
    if MANUAL.exists() and not backup.exists():
        shutil.copy2(MANUAL, backup)
        print(f"\nbacked up human manual file -> {backup.relative_to(ROOT)}")
    elif backup.exists():
        print(f"\nbackup already present -> {backup.relative_to(ROOT)} (not overwritten)")

    luna.to_csv(MANUAL, index=False)
    print(f"replaced live scoring file -> {MANUAL.relative_to(ROOT)} ({len(luna):,} rows)")


if __name__ == "__main__":
    main()
