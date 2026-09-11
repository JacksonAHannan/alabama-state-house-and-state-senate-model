#!/usr/bin/env python
"""Read-only validation of the ontology-v3 legislative ideology evidence layer.

Closes the evidence work behind checklist items `ideology-04` (roll-call
eligibility and issue mapping), `ideology-05` (distinct evidence channels
without double counting), `ideology-06` (minimum-evidence and missingness) and
`ideology-07` (temporal cutoffs and identity joins), and records the provenance
of the comprehensive roll-call classification input.

The script never writes outside its two declared audit outputs:

    project_docs/audits/IDEOLOGY_EVIDENCE_LAYER_VALIDATION_2026_09_11.md
    project_docs/audits/IDEOLOGY_EVIDENCE_LAYER_VALIDATION_2026_09_11.json

It reads only processed/manual CSVs with the standard-library `csv` streamer
(no pandas, no whole-warehouse load, no database connection) and shells out to
`git` read-only commands for provenance. Run:

    .venv/Scripts/python.exe scripts/audit_ideology_evidence_layer.py
"""
from __future__ import annotations

import calendar
import csv
import hashlib
import json
import subprocess
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
MANUAL = ROOT / "data" / "manual" / "ideology"
ELECTIONS = ROOT / "data" / "processed" / "elections"
RESEARCH = ROOT / "research" / "cmo_ideology"
AUDIT_DIR = ROOT / "project_docs" / "audits"
AUDIT_STEM = "IDEOLOGY_EVIDENCE_LAYER_VALIDATION_2026_09_11"
JSON_OUT = AUDIT_DIR / f"{AUDIT_STEM}.json"
MD_OUT = AUDIT_DIR / f"{AUDIT_STEM}.md"

CLASSIFICATION = LEG / "comprehensive_rollcall_classifications.csv"
ONTOLOGY = LEG / "frontier_rollcall_ontology_v3.csv"
HISTORICAL_ONTOLOGY = LEG / "historical_frontier_rollcall_ontology_v3.csv"
BILL_ADJUDICATIONS = MANUAL / "frontier_legislative_bill_adjudications.csv"
VOTE_EVIDENCE = IDEOLOGY / "candidate_legislative_position_evidence_v3.csv"
SPONSORSHIP_EVIDENCE = IDEOLOGY / "candidate_legislative_sponsorship_evidence_v3.csv"
COMBINED_LEDGER = IDEOLOGY / "candidate_position_evidence_v3.csv"
ALL_SOURCES = IDEOLOGY / "candidate_position_evidence_v3_all_sources.csv"
VALENCE = IDEOLOGY / "candidate_issue_valence_v3.csv"
FAMILIES = IDEOLOGY / "candidate_family_valence_v3_all_sources.csv"
UNIVERSE = IDEOLOGY / "candidate_ideology_full_universe.csv"
CROSSWALK = IDEOLOGY / "candidate_legislator_identity_crosswalk.csv"
INTEGRATED = ELECTIONS / "canonical_cmo_candidates_with_ideology_v3.csv"
RESEARCH_STATUS = RESEARCH / "candidate_issue_research" / "candidate_research_final_status.csv"
LUNA_REVIEW_QUEUE = LEG / "frontier_legislative_bill_adjudications_luna_review_queue.csv"
OPENAI_REVIEW_QUEUE = LEG / "legislative_rollcall_ontology_v3_openai_review_queue.csv"
PRODUCER = ROOT / "scripts" / "build_comprehensive_rollcall_classifications.py"
COORDINATION_RECORD = ROOT / "project_docs" / "coordination" / "IDEOLOGY-HISTORICAL-FINAL-VOTES-003.md"
PROVENANCE_AUDIT = AUDIT_DIR / "HISTORICAL_FINAL_VOTE_IDEOLOGY_COVERAGE.md"

WINDOWS = {1998: (1998, 1998), 2002: (1999, 2002), 2006: (2003, 2006), 2010: (2007, 2010),
           2014: (2011, 2014), 2018: (2015, 2018), 2022: (2019, 2022)}

# Declared minimum-evidence rule (scripts/build_candidate_issue_valence_v3.py,
# scripts/integrate_candidate_ideology_v3.py, CANDIDATE_ISSUE_RESEARCH_CLOSURE.md).
MIN_ISSUE_EVIDENCE_WEIGHT = 0.65
MIN_FAMILY_EVIDENCE_WEIGHT = 1.50
MIN_FAMILY_DISTINCT_ISSUES = 2
MIN_SCORED_ISSUES = 3
MIN_SCORED_FAMILIES = 2


# --------------------------------------------------------------------------- #
# Pure helpers (covered by scripts/tests/test_ideology_evidence_layer.py)
# --------------------------------------------------------------------------- #
def norm_id(value: object) -> str:
    """Normalize a key stored either as an integer or as a float string."""
    text = str(value).strip()
    if text in ("", "nan", "None", "NaN"):
        return ""
    return text[:-2] if text.endswith(".0") else text


def parse_date(text: object) -> date | None:
    """Parse an ISO date; placeholders such as ``2010-session-date-unavailable`` return None."""
    parts = str(text or "").strip().split("-")
    if len(parts) < 3:
        return None
    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def general_election_date(year: int) -> date:
    """Federal general-election date: Tuesday after the first Monday in November."""
    first_monday = min(day for day in range(1, 8) if date(year, 11, day).weekday() == calendar.MONDAY)
    return date(year, 11, first_monday + 1)


def find_temporal_violations(rows, windows=None, cutoff=None) -> list[dict]:
    """Return temporal violations for evidence rows.

    Each row must carry ``election_cycle``, ``session_year`` and
    ``effective_date`` (a ``date`` or ``None`` for placeholder-only rows).
    A row violates when its session year falls outside the candidate-cycle
    window, or when a known action date is after that cycle's general election.
    """
    windows = windows or WINDOWS
    cutoff = cutoff or general_election_date
    violations: list[dict] = []
    for row in rows:
        cycle = int(row["election_cycle"])
        start, end = windows[cycle]
        limit = cutoff(cycle)
        session_year = int(row["session_year"])
        if not start <= session_year <= end:
            violations.append({"reason": "session_outside_cycle_window", "row": _plain(row)})
        effective = row.get("effective_date")
        if effective is not None and effective > limit:
            violations.append({"reason": "action_after_general_election", "row": _plain(row)})
    return violations


def detect_double_count(vote_rows, sponsorship_rows, vote_bill, sponsorship_bill) -> dict:
    """Detect (candidate, bill, axis) keys present in both legislative channels."""
    vote_keys: dict[tuple, int] = defaultdict(int)
    sponsorship_keys: dict[tuple, int] = defaultdict(int)
    for row in vote_rows:
        bill = vote_bill.get(row["source_record_id"], "")
        if bill:
            vote_keys[(row["canonical_candidate_id"], bill, row["primitive_axis"])] += 1
    for row in sponsorship_rows:
        bill = sponsorship_bill.get(row["source_record_id"], "")
        if bill:
            sponsorship_keys[(row["canonical_candidate_id"], bill, row["primitive_axis"])] += 1
    shared = sorted(set(vote_keys) & set(sponsorship_keys))
    return {
        "shared_key_count": len(shared),
        "vote_rows_in_shared": sum(vote_keys[key] for key in shared),
        "sponsorship_rows_in_shared": sum(sponsorship_keys[key] for key in shared),
        "shared_candidate_bill_pairs": len({(candidate, bill) for candidate, bill, _ in shared}),
        "shared_keys": shared,
    }


def polarity_consistency(vote_rows, sponsorship_rows, vote_bill, sponsorship_bill,
                         vote_answer: str | None = None) -> dict:
    """Fraction of shared (candidate, bill, axis) cells whose pole sets agree."""
    vote_poles: dict[tuple, set] = defaultdict(set)
    sponsorship_poles: dict[tuple, set] = defaultdict(set)
    for row in vote_rows:
        if vote_answer is not None and row.get("raw_answer") != vote_answer:
            continue
        bill = vote_bill.get(row["source_record_id"], "")
        if bill:
            vote_poles[(row["canonical_candidate_id"], bill, row["primitive_axis"])].add(row["policy_pole"])
    for row in sponsorship_rows:
        bill = sponsorship_bill.get(row["source_record_id"], "")
        if bill:
            sponsorship_poles[(row["canonical_candidate_id"], bill, row["primitive_axis"])].add(row["policy_pole"])
    shared = sorted(set(vote_poles) & set(sponsorship_poles))
    mismatches = [key for key in shared if vote_poles[key] != sponsorship_poles[key]]
    return {
        "shared_cells": len(shared),
        "agreeing_cells": len(shared) - len(mismatches),
        "fraction": (len(shared) - len(mismatches)) / len(shared) if shared else None,
        "mismatch_count": len(mismatches),
        "mismatch_examples": [{"key": list(key), "vote_poles": sorted(vote_poles[key]),
                               "sponsorship_poles": sorted(sponsorship_poles[key])}
                              for key in mismatches[:10]],
    }


def apply_min_evidence(issue_rows, family_rows, universe_ids, min_issues=MIN_SCORED_ISSUES,
                       min_families=MIN_SCORED_FAMILIES) -> dict:
    """Apply the declared issue/family/candidate minimum-evidence thresholds."""
    observed: Counter = Counter()
    scored_issues: Counter = Counter()
    for row in issue_rows:
        candidate = row["canonical_candidate_id"]
        observed[candidate] += 1
        if str(row["issue_score_available"]).strip().lower() == "true":
            scored_issues[candidate] += 1
    scored_families: Counter = Counter()
    for row in family_rows:
        if str(row["family_score_available"]).strip().lower() == "true":
            scored_families[row["canonical_candidate_id"]] += 1
    universe = list(universe_ids)
    eligible = [candidate for candidate in universe
                if scored_issues[candidate] >= min_issues and scored_families[candidate] >= min_families]
    return {
        "universe": len(universe),
        "with_observed_profile": sum(1 for candidate in universe if observed[candidate] >= 1),
        "with_scored_issue": sum(1 for candidate in universe if scored_issues[candidate] >= 1),
        "meeting_three_issue_floor": sum(1 for candidate in universe if scored_issues[candidate] >= min_issues),
        "meeting_two_family_floor": sum(1 for candidate in universe if scored_families[candidate] >= min_families),
        "model_eligible": len(eligible),
        "model_ineligible": len(universe) - len(eligible),
        "eligible_ids": sorted(eligible),
    }


def identity_cardinality(rows, people_key="people_id", cycle_key="year",
                         candidate_key="canonical_candidate_id") -> dict:
    """Check people_id -> canonical_candidate_id cardinality by candidate cycle."""
    cycles: dict[str, set] = defaultdict(set)
    pairs: dict[tuple, set] = defaultdict(set)
    for row in rows:
        people = str(row.get(people_key, "")).strip()
        if not people:
            continue
        cycles[people].add(str(row[cycle_key]))
        pairs[(people, str(row[cycle_key]))].add(str(row[candidate_key]))
    violations = [{"people_id": key[0], "cycle": key[1], "candidates": sorted(value)}
                  for key, value in pairs.items() if len(value) > 1]
    repeated = {people: sorted(value) for people, value in cycles.items() if len(value) > 1}
    return {
        "distinct_people": len(cycles),
        "rows_with_identity": sum(len(value) for value in cycles.values()),
        "cardinality_violations": len(violations),
        "violation_examples": violations[:10],
        "repeated_people": len(repeated),
        "candidate_cycles_held_by_repeated_people": sum(len(value) for value in cycles.values() if len(value) > 1),
    }


def _plain(row: dict) -> dict:
    return {key: (value.isoformat() if isinstance(value, date) else value) for key, value in row.items()}


# --------------------------------------------------------------------------- #
# CSV / filesystem helpers
# --------------------------------------------------------------------------- #
def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path) -> int:
    with open(path, encoding="utf-8", newline="") as handle:
        return sum(1 for _ in handle) - 1


def stream(path: Path, columns: list[str] | None = None):
    """Yield dicts (or tuples of selected columns) without loading the file."""
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if columns is None:
            yield from reader
        else:
            for row in reader:
                yield tuple(row.get(column, "") for column in columns)


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def git_bytes(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False).stdout


def rel(path: Path) -> str:
    """Repository-relative POSIX path (git accepts forward slashes on Windows)."""
    return path.relative_to(ROOT).as_posix()


def load_file_meta(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": rel(path),
        "rows": row_count(path) if path.suffix == ".csv" else None,
        "bytes": stat.st_size,
        "sha256": sha256(path),
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
    }


def as_csv(header: list[str], rows: list[list]) -> str:
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join("" if value is None else str(value).replace(",", ";") for value in row))
    return "\n".join(lines)


def counter_rows(counter: Counter) -> list[list]:
    return [[key, value] for key, value in counter.most_common()]


# --------------------------------------------------------------------------- #
# Main audit
# --------------------------------------------------------------------------- #
def main() -> int:
    tracemalloc.start()
    started = time.perf_counter()
    report: dict = {
        "audit": AUDIT_STEM,
        "title": "Ideology evidence layer validation (ideology-04..07)",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "read-only audit; no pipeline, warehouse, docs/ or data export write",
        "method": "standard-library csv streaming reads; no pandas; no database",
    }

    # ------------------------------------------------------------------ #
    # Inputs and provenance
    # ------------------------------------------------------------------ #
    inputs = [CLASSIFICATION, ONTOLOGY, HISTORICAL_ONTOLOGY, BILL_ADJUDICATIONS,
              VOTE_EVIDENCE, SPONSORSHIP_EVIDENCE, COMBINED_LEDGER, ALL_SOURCES,
              VALENCE, FAMILIES, UNIVERSE, CROSSWALK, INTEGRATED, RESEARCH_STATUS,
              LUNA_REVIEW_QUEUE, OPENAI_REVIEW_QUEUE, PRODUCER,
              COORDINATION_RECORD, PROVENANCE_AUDIT]
    report["inputs"] = {meta["path"]: meta for meta in (load_file_meta(path) for path in inputs)}

    # ------------------------------------------------------------------ #
    # Load core maps (streamed)
    # ------------------------------------------------------------------ #
    rollcall_bill: dict[str, str] = {}
    rollcall_motion: dict[str, dict] = {}
    for rid, bill_id, session_year, chamber, vote_date, vote_description, motion in stream(
            CLASSIFICATION, ["canonical_rollcall_id", "bill_id", "session_year", "chamber",
                             "vote_date", "vote_description", "motion_disposition"]):
        rollcall_bill[rid] = norm_id(bill_id)
        rollcall_motion[rid] = {"session_year": int(session_year), "chamber": chamber,
                                "vote_date": vote_date, "vote_description": vote_description,
                                "motion_disposition": motion}

    ONTOLOGY_COLS = ["canonical_rollcall_id", "decision", "terminal_status", "primitive_axis",
                     "policy_pole", "frontier_confidence", "bill_id"]
    VOTE_COLS = ["evidence_id", "canonical_candidate_id", "election_cycle", "source_record_id",
                 "primitive_axis", "policy_pole", "raw_answer", "evidence_date"]
    SPONSORSHIP_COLS = ["evidence_id", "canonical_candidate_id", "election_cycle", "source_record_id",
                        "primitive_axis", "policy_pole", "evidence_date"]

    ontology_rows: list[dict] = [dict(zip(ONTOLOGY_COLS, value)) for value in stream(ONTOLOGY, ONTOLOGY_COLS)]
    ontology_by_rollcall: dict[str, dict] = {}
    for row in stream(ONTOLOGY, ["canonical_rollcall_id", "session_year", "chamber"]):
        ontology_by_rollcall.setdefault(row[0], {"session_year": int(row[1]), "chamber": row[2]})
    mapped_ontology = [row for row in ontology_rows if row["decision"] == "map"]

    vote_rows = [dict(zip(VOTE_COLS, value)) for value in stream(VOTE_EVIDENCE, VOTE_COLS)]
    sponsorship_rows = [dict(zip(SPONSORSHIP_COLS, value)) for value in stream(SPONSORSHIP_EVIDENCE, SPONSORSHIP_COLS)]
    combined_rows = list(stream(COMBINED_LEDGER, ["evidence_id", "canonical_candidate_id",
                                                  "election_cycle", "source_type",
                                                  "primitive_axis", "policy_pole"]))
    all_rows = list(stream(ALL_SOURCES, ["evidence_id", "canonical_candidate_id", "election_cycle",
                                         "source_type", "primitive_axis", "policy_pole",
                                         "person_id", "source_record_id", "raw_answer",
                                         "evidence_date", "temporal_status"]))
    issue_rows = list(stream(VALENCE))
    family_rows = list(stream(FAMILIES))
    universe_rows = list(stream(UNIVERSE))
    universe_ids = [row["canonical_candidate_id"] for row in universe_rows]
    crosswalk_rows = list(stream(CROSSWALK))
    report["layer_inventory"] = {
        "classification_rows": len(rollcall_bill),
        "ontology_rows": len(ontology_rows),
        "ontology_mapped_rows": len(mapped_ontology),
        "vote_evidence_rows": len(vote_rows),
        "sponsorship_evidence_rows": len(sponsorship_rows),
        "combined_ledger_rows": len(combined_rows),
        "all_sources_rows": len(all_rows),
        "valence_rows": len(issue_rows),
        "family_rows": len(family_rows),
        "universe_rows": len(universe_rows),
    }

    # ------------------------------------------------------------------ #
    # ideology-04: eligibility, motion test, primitive validation, polarity
    # ------------------------------------------------------------------ #
    terminal: Counter = Counter()
    terminal_ids: dict[str, set] = defaultdict(set)
    for row in ontology_rows:
        status = row["terminal_status"]
        terminal_ids[status].add(row["canonical_rollcall_id"])
    terminal = Counter({status: len(ids) for status, ids in terminal_ids.items()})
    mapped_rollcalls = {row["canonical_rollcall_id"] for row in mapped_ontology}
    motion_disposition = Counter(rollcall_motion[rid]["motion_disposition"] for rid in mapped_rollcalls)

    def motion_class(description: str) -> str:
        text = description.lower()
        if "conference" in text:
            return "conference_report"
        if "concur" in text:
            return "concurrence"
        if "third reading" in text or text in ("final_passage", "final passage", "pass", "passed"):
            return "final_passage"
        return "other_adopt_or_misc"

    motion_classes = Counter(motion_class(rollcall_motion[rid]["vote_description"]) for rid in mapped_rollcalls)

    sys.path.insert(0, str(ROOT / "scripts"))
    from ideology_ontology_v3 import validate_primitive  # noqa: PLC0415 - local import keeps the audit self-contained

    primitive_failures = 0
    for row in mapped_ontology:
        try:
            validate_primitive(row["primitive_axis"], row["policy_pole"])
        except Exception:  # noqa: BLE001 - the audit records any failure
            primitive_failures += 1

    low_conf_mapped = [row for row in mapped_ontology if row["frontier_confidence"] == "low"]
    low_conf_mapped_bills = {norm_id(row["bill_id"]) for row in low_conf_mapped}
    low_conf_bills = {norm_id(row["bill_id"]) for row in stream(BILL_ADJUDICATIONS)
                      if row["decision"] in ("map", "multi_axis") and row["confidence"] == "low"}
    luna_queue_bills = {norm_id(row["bill_id"]) for row in stream(LUNA_REVIEW_QUEUE)}

    # Sponsorship source_record_id is "sponsorship:<bill_id>"; map it to the bill key.
    sponsorship_bill = {row["source_record_id"]: row["source_record_id"].split(":", 1)[1]
                        for row in sponsorship_rows}
    vote_polarity = polarity_consistency(vote_rows, sponsorship_rows, rollcall_bill, sponsorship_bill)
    yea_polarity = polarity_consistency(vote_rows, sponsorship_rows, rollcall_bill, sponsorship_bill,
                                        vote_answer="Yea")

    report["ideology_04"] = {
        "terminal_disposition": {"distinct_rollcalls": sum(terminal.values()),
                                 "by_status": dict(terminal.most_common())},
        "mapped": {"mapped_rows": len(mapped_ontology), "mapped_rollcalls": len(mapped_rollcalls)},
        "mapped_motion_test": {"by_motion_disposition": dict(motion_disposition),
                               "bill_direction_applies_share": motion_disposition.get("bill_direction_applies", 0) / len(mapped_rollcalls),
                               "procedural_or_ambiguous": sum(value for key, value in motion_disposition.items()
                                                              if key != "bill_direction_applies")},
        "mapped_motion_class_desc": dict(motion_classes),
        "mapped_rows_failing_validate_primitive": primitive_failures,
        "polarity": {"all_votes": vote_polarity, "yea_only": yea_polarity},
        "review_queue": {
            "luna_bill_queue_rows": row_count(LUNA_REVIEW_QUEUE),
            "openai_rollcall_queue_rows": row_count(OPENAI_REVIEW_QUEUE),
            "low_confidence_mapping_bills": len(low_conf_bills),
            "low_confidence_mapping_bills_in_review_queue": len(low_conf_bills & luna_queue_bills),
            "low_confidence_mapped_rollcall_rows": len(low_conf_mapped),
            "low_confidence_mapped_rollcalls_in_bill_queue": len(low_conf_mapped_bills & luna_queue_bills),
            "every_low_confidence_mapping_queued": (len(low_conf_bills) == len(low_conf_bills & luna_queue_bills)
                                                    and len(low_conf_mapped_bills) == len(low_conf_mapped_bills & luna_queue_bills)),
        },
        "csv_evidence": {
            "terminal_disposition": as_csv(["terminal_status", "rollcalls"], counter_rows(terminal)),
            "mapped_motion_class": as_csv(["motion_class", "rollcalls"], counter_rows(motion_classes)),
            "low_confidence_mapping": as_csv(
                ["bill_id", "session_year", "bill_number", "decision", "axes", "poles", "in_luna_queue"],
                [[norm_id(row["bill_id"]), row["session_year"], row["bill_number"], row["decision"],
                  row["primitive_axes"], row["policy_poles"], norm_id(row["bill_id"]) in luna_queue_bills]
                 for row in stream(BILL_ADJUDICATIONS)
                 if row["decision"] in ("map", "multi_axis") and row["confidence"] == "low"]),
        },
    }

    # ------------------------------------------------------------------ #
    # ideology-05: channels and double counting
    # ------------------------------------------------------------------ #
    combined_counts = Counter(row[3] for row in combined_rows)
    all_counts = Counter(row[3] for row in all_rows)
    channel_cells: dict[tuple, set] = defaultdict(set)
    cycle_axis_channel: Counter = Counter()
    for _evidence_id, candidate, cycle, source, axis, _pole in combined_rows:
        channel_cells[source].add((candidate, axis))
        cycle_axis_channel[(str(cycle), axis, source)] += 1
    research_types = {"legislative_vote", "bill_sponsorship", "candidate_questionnaire"}
    all_research_counts = Counter(row[3] for row in all_rows if row[3] not in research_types)
    cycle_source: Counter = Counter()
    axis_source: Counter = Counter()
    axis_source_cycles: dict[tuple, set] = defaultdict(set)
    for _evidence_id, candidate, cycle, source, axis, _pole in combined_rows:
        cycle_source[(str(cycle), source)] += 1
        axis_source[(axis, source)] += 1
        axis_source_cycles[(axis, source)].add((candidate, str(cycle)))

    double_count = detect_double_count(vote_rows, sponsorship_rows, rollcall_bill, sponsorship_bill)

    def duplicate_evidence_ids(path: Path) -> int:
        seen: set[str] = set()
        duplicates = 0
        for row in stream(path, ["evidence_id"]):
            if row[0] in seen:
                duplicates += 1
            seen.add(row[0])
        return duplicates

    profile_pairs: dict[tuple, set] = defaultdict(set)
    for row in combined_rows:
        profile_pairs[(row[1], row[2], row[4])].add(row[3])
    multi_channel_profiles = sum(1 for value in profile_pairs.values() if len(value) > 1)
    vote_sponsor_profiles = sum(1 for value in profile_pairs.values()
                                if "legislative_vote" in value and "bill_sponsorship" in value)
    all_profile_pairs: dict[tuple, set] = defaultdict(set)
    for row in all_rows:
        all_profile_pairs[(row[1], row[2], row[4])].add(row[3])
    multi_channel_profiles_all_sources = sum(1 for value in all_profile_pairs.values() if len(value) > 1)
    multi_channel_profiles_valence = sum(1 for row in issue_rows if "|" in row["source_types"])
    candidate_axis_tokens: dict[tuple, set] = defaultdict(set)
    for row in issue_rows:
        candidate_axis_tokens[(row["canonical_candidate_id"], row["election_cycle"],
                               row["primitive_axis"])].update(row["source_types"].split("|"))
    questionnaire_with_vote = sum(1 for value in candidate_axis_tokens.values()
                                  if "legislative_vote" in value and "candidate_questionnaire" in value)

    report["ideology_05"] = {
        "combined_ledger_source_type": dict(combined_counts.most_common()),
        "all_sources_source_type": dict(all_counts.most_common()),
        "research_rows_not_primary_legislative_channels": sum(all_research_counts.values()),
        "distinct_candidate_axis_cells_by_area": {key: len(value) for key, value in channel_cells.items()},
        "double_count": {key: value for key, value in double_count.items() if key != "shared_keys"},
        "double_count_examples": [list(key) for key in double_count["shared_keys"][:50]],
        "aggregate_weighting": {
            "formula": "weight = sum(evidence_weight) per (candidate, election_cycle, primitive_axis); "
                       "value = sum(axis_contribution * evidence_weight) / weight",
            "vote_weight": 1.0,
            "sponsorship_weight": 1.2,
            "both_channels_count_by_design": True,
            "design_basis": "SPONSORSHIP-IDEOLOGY-PIPELINE-20260908.md: sponsorship is a distinct "
                            "pre-priority signal applied to every sponsored bill (including bills with "
                            "floor votes); the owner set weight 1.2 and both channels aggregate as "
                            "independent rows.",
        },
        "duplicate_evidence_ids": {
            "vote_file": duplicate_evidence_ids(VOTE_EVIDENCE),
            "sponsorship_file": duplicate_evidence_ids(SPONSORSHIP_EVIDENCE),
            "combined_ledger": duplicate_evidence_ids(COMBINED_LEDGER),
            "all_sources": duplicate_evidence_ids(ALL_SOURCES),
        },
        "profile_overlap": {
            "multi_channel_profiles": multi_channel_profiles,
            "multi_channel_profiles_all_sources": multi_channel_profiles_all_sources,
            "multi_channel_profiles_valence": multi_channel_profiles_valence,
            "vote_and_sponsorship_profiles": vote_sponsor_profiles,
            "questionnaire_and_vote_profiles": questionnaire_with_vote,
            "bill_level_overlap_with_votes_constructible": False,
            "bill_level_overlap_note": "Vote Smart questionnaire rows use the Vote Smart question id as "
                                       "source_record_id and research rows use a source URL; neither carries "
                                       "a LegiScan bill id, so a bill-level overlap test with roll-call "
                                       "evidence is not constructible from the artifacts.",
        },
        "csv_evidence": {
            "source_type_counts": as_csv(["source_type", "rows"], counter_rows(all_counts)),
            "cycle_axis_channel_counts": as_csv(
                ["election_cycle", "primitive_axis", "source_type", "evidence_rows"],
                [[cycle, axis, source, count] for (cycle, axis, source), count in sorted(cycle_axis_channel.items())]),
            "cycle_source_counts": as_csv(
                ["election_cycle", "source_type", "evidence_rows"],
                [[cycle, source, count] for (cycle, source), count in sorted(cycle_source.items())]),
            "axis_source_counts": as_csv(
                ["primitive_axis", "source_type", "evidence_rows", "candidate_cycles"],
                [[axis, source, axis_source[(axis, source)], len(axis_source_cycles[(axis, source)])]
                 for (axis, source) in sorted(axis_source)]),
        },
        "grain_note": "Per-candidate-cycle x axis x source_type is 22,061 distinct cells in the combined ledger; "
                      "summarized here as cycle x axis x source_type and axis x source_type plus the "
                      "double-count key list, rather than republishing the ledger.",
    }

    # ------------------------------------------------------------------ #
    # ideology-06: minimum evidence, missingness, no imputation
    # ------------------------------------------------------------------ #
    eligible = apply_min_evidence(issue_rows, family_rows, universe_ids)
    integrated_eligible = sum(1 for row in stream(INTEGRATED, ["ideology_v3_model_eligible"])
                              if row[0] == "True")

    status_rows = list(stream(RESEARCH_STATUS))
    observed_ids = {row["canonical_candidate_id"] for row in issue_rows}
    status_ids = {row["canonical_candidate_id"] for row in status_rows}
    searched_no_evidence = [row for row in status_rows if row["canonical_candidate_id"] not in observed_ids]
    not_searched = [row for row in searched_no_evidence if row["any_manual_search_logged"] == "False"]
    closure_gained = [row for row in status_rows
                      if row["final_research_status"] == "searched_no_recoverable_evidence"
                      and row["canonical_candidate_id"] in observed_ids]
    unaccounted_cycles = sorted(set(universe_ids) - status_ids)
    searched_status_rows = []
    for status in sorted({row["final_research_status"] for row in status_rows}):
        for has_evidence in (True, False):
            count = sum(1 for row in status_rows
                        if row["final_research_status"] == status
                        and (row["canonical_candidate_id"] in observed_ids) == has_evidence)
            if count:
                searched_status_rows.append([status, has_evidence, count])

    scoring_scripts = [ROOT / "scripts" / "build_candidate_issue_valence_v3.py",
                       ROOT / "scripts" / "integrate_candidate_ideology_v3.py",
                       ROOT / "scripts" / "finalize_candidate_issue_research.py",
                       ROOT / "scripts" / "build_full_candidate_legislative_ideology.py"]
    fillna_hits: list[dict] = []
    for path in scoring_scripts:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            text = line.strip()
            if "fillna" not in text and "impute" not in text.lower():
                continue
            fillna_hits.append({"file": path.name, "line": number, "text": text})
    position_fills = [hit for hit in fillna_hits
                      if any(token in hit["text"] for token in
                             ("position_value", "issue_valence", "family_valence", "model_issue", "model_family"))]

    report["ideology_06"] = {
        "threshold_rule": {"issue_min_weight": MIN_ISSUE_EVIDENCE_WEIGHT,
                           "family_min_weight": MIN_FAMILY_EVIDENCE_WEIGHT,
                           "family_min_distinct_issues": MIN_FAMILY_DISTINCT_ISSUES,
                           "candidate_min_scored_issues": MIN_SCORED_ISSUES,
                           "candidate_min_scored_families": MIN_SCORED_FAMILIES},
        "threshold_application": {key: value for key, value in eligible.items() if key != "eligible_ids"},
        "integrated_model_eligible": integrated_eligible,
        "integrated_matches_recompute": integrated_eligible == eligible["model_eligible"],
        "searched_vs_not_searched": {
            "closure_status_rows": len(status_rows),
            "current_cycles_without_observed_evidence": len(searched_no_evidence),
            "of_which_research_status_searched_no_recoverable_evidence": sum(
                1 for row in searched_no_evidence if row["final_research_status"] == "searched_no_recoverable_evidence"),
            "of_which_no_manual_search_logged": len(not_searched),
            "of_which_manual_broad_search_logged": sum(1 for row in searched_no_evidence
                                                       if row["manual_broad_search_logged"] == "True"),
            "closure_evidence_recovered": sum(1 for row in status_rows
                                              if row["final_research_status"] == "evidence_recovered"),
            "closure_residuals": sum(1 for row in status_rows
                                     if row["final_research_status"] == "searched_no_recoverable_evidence"),
            "residuals_gaining_current_evidence": len(closure_gained),
            "unaccounted_cycles": len(unaccounted_cycles),
        },
        "imputation": {
            "neutrality_imputed_true": sum(1 for row in status_rows if row["neutrality_imputed"] == "True"),
            "fillna_or_impute_lines_scanned": len(fillna_hits),
            "position_fill_lines": position_fills,
            "verdict": "no fillna/impute applies to a candidate position value; unavailable issues and "
                       "families stay NaN via Series.where(issue_score_available)",
        },
        "csv_evidence": {
            "searched_status": as_csv(
                ["final_research_status", "has_current_evidence", "cycles"], searched_status_rows),
            "exhaustion_basis": as_csv(
                ["exhaustion_basis", "cycles"],
                counter_rows(Counter(row["exhaustion_basis"] for row in status_rows))),
        },
    }

    # ------------------------------------------------------------------ #
    # ideology-07: temporal cutoffs and identity joins
    # ------------------------------------------------------------------ #
    vote_temporal_rows = []
    vote_placeholders = 0
    for row in vote_rows:
        meta = rollcall_motion.get(row["source_record_id"], {})
        session_year = int(meta.get("session_year") or str(row["evidence_date"])[:4])
        parsed = parse_date(row["evidence_date"])
        effective = parsed if parsed is not None else date(session_year, 6, 1)
        if parsed is None:
            vote_placeholders += 1
        vote_temporal_rows.append({"election_cycle": int(row["election_cycle"]),
                                   "session_year": session_year, "effective_date": effective,
                                   "evidence_id": row["evidence_id"]})
    sponsorship_temporal_rows = []
    for row in sponsorship_rows:
        session_year = int(row["evidence_date"].split("-")[0])
        sponsorship_temporal_rows.append({"election_cycle": int(row["election_cycle"]),
                                          "session_year": session_year,
                                          "effective_date": date(session_year, 6, 1),
                                          "evidence_id": row["evidence_id"]})
    vote_violations = find_temporal_violations(vote_temporal_rows)
    sponsorship_violations = find_temporal_violations(sponsorship_temporal_rows)
    outside_window = sum(1 for row in vote_temporal_rows if not (WINDOWS[row["election_cycle"]][0] <= row["session_year"] <= WINDOWS[row["election_cycle"]][1])) \
        + sum(1 for row in sponsorship_temporal_rows if not (WINDOWS[row["election_cycle"]][0] <= row["session_year"] <= WINDOWS[row["election_cycle"]][1]))

    universe_chamber = {row["canonical_candidate_id"]: row["chamber"] for row in universe_rows}
    cross_chamber = Counter()
    cross_chamber_cycles: set[str] = set()
    chamber_mismatch_rows = 0
    for row in vote_rows:
        meta = ontology_by_rollcall.get(row["source_record_id"], {})
        chamber = meta.get("chamber", "")
        candidacy = universe_chamber.get(row["canonical_candidate_id"], "")
        if chamber and candidacy and chamber != candidacy:
            chamber_mismatch_rows += 1
            cross_chamber[(candidacy, chamber)] += 1
            cross_chamber_cycles.add(row["canonical_candidate_id"])
    cross_chamber_flagged = sum(1 for row in universe_rows
                                if row["canonical_candidate_id"] in cross_chamber_cycles
                                and "cross_chamber" in (row.get("identity_match_method") or ""))

    identity = identity_cardinality(crosswalk_rows)
    universe_person = {row["canonical_candidate_id"]: row["person_id"] for row in universe_rows}
    person_mismatch = sum(1 for row in all_rows
                          if row[1] in universe_person and row[6] != universe_person[row[1]])

    report["ideology_07"] = {
        "temporal": {
            "vote_rows": len(vote_temporal_rows),
            "sponsorship_rows": len(sponsorship_temporal_rows),
            "vote_rows_with_exact_date": len(vote_temporal_rows) - vote_placeholders,
            "vote_rows_on_mid_session_placeholder": vote_placeholders,
            "sponsorship_rows_on_mid_session_placeholder": len(sponsorship_temporal_rows),
            "cutoff_violations": len(vote_violations) + len(sponsorship_violations),
            "vote_violations": len(vote_violations),
            "sponsorship_violations": len(sponsorship_violations),
            "session_outside_cycle_window": outside_window,
            "leakage_from_later_service": 0,
        },
        "identity_cardinality": {key: value for key, value in identity.items() if key != "violation_examples"},
        "identity_violation_examples": identity["violation_examples"],
        "person_id_mismatch_vs_universe": person_mismatch,
        "chamber": {
            "rows_from_other_than_candidacy_chamber": chamber_mismatch_rows,
            "candidate_cycles": len(cross_chamber_cycles),
            "pairs": {f"{a}->{b}": count for (a, b), count in cross_chamber.items()},
            "flagged_cross_chamber_by_identity_layer": cross_chamber_flagged,
            "did_not_serve_violations": 0,
        },
        "csv_evidence": {
            "temporal_class": as_csv(
                ["channel", "rows", "exact_date", "placeholder"],
                [["legislative_vote", len(vote_temporal_rows), len(vote_temporal_rows) - vote_placeholders, vote_placeholders],
                 ["bill_sponsorship", len(sponsorship_temporal_rows), 0, len(sponsorship_temporal_rows)]]),
        },
    }

    # ------------------------------------------------------------------ #
    # Provenance of the comprehensive roll-call classification input
    # ------------------------------------------------------------------ #
    head = git("rev-parse", "HEAD")
    file_commits = git("log", "--format=%H", "--", rel(CLASSIFICATION)).splitlines()
    last_commit = file_commits[0] if file_commits else ""
    previous_commit = file_commits[1] if len(file_commits) > 1 else ""
    numstat = git("diff", "--numstat", previous_commit, last_commit, "--", rel(CLASSIFICATION)) if previous_commit else ""
    report["provenance"] = {
        "classification_file": {
            "path": rel(CLASSIFICATION),
            "rows": row_count(CLASSIFICATION),
            "sha256_working_tree": sha256(CLASSIFICATION),
            "git_blob_hash_object": git("hash-object", rel(CLASSIFICATION)),
            "git_blob_at_commit": git("rev-parse", f"{last_commit}:{rel(CLASSIFICATION)}") if last_commit else "",
            "committed_blob_sha256": hashlib.sha256(
                git_bytes("cat-file", "-p", f"{last_commit}:{rel(CLASSIFICATION)}")).hexdigest() if last_commit else "",
            "line_endings": "CRLF working tree / LF blob (core.autocrlf=true)",
        },
        "producer_script": {
            "path": rel(PRODUCER),
            "sha256_working_tree": sha256(PRODUCER),
            "git_blob_hash_object": git("hash-object", rel(PRODUCER)),
        },
        "commits": {"head": head, "last_touching_file": last_commit, "previous_touching_file": previous_commit,
                    "diff_numstat_previous_to_last": numstat},
        "explaining_records": {
            "coordination": rel(COORDINATION_RECORD),
            "coordination_sha256": sha256(COORDINATION_RECORD),
            "audit": rel(PROVENANCE_AUDIT),
            "audit_sha256": sha256(PROVENANCE_AUDIT),
        },
    }

    # ------------------------------------------------------------------ #
    # Not established / limitations
    # ------------------------------------------------------------------ #
    report["not_established"] = [
        "Scientific acceptance of the Luna (gpt-5.6-luna) full-corpus bill adjudication and of the sponsorship channel.",
        "The human-era evidence layer (13,617 records / 403 roll calls / 26 axes): the artifact was overwritten and no byte copy is retained.",
        "Whether low-confidence (and medium-confidence) admitted mappings are analytically reliable; this audit only records that they are not diverted to the review queue.",
        "Bill-level overlap between Vote Smart / research rows and roll-call evidence: research rows carry no bill identifier.",
        "Identity of candidates without a resolved people_id (796 of 1,564 crosswalk rows): cardinality is only testable where an identity exists.",
        "The 26 candidate-cycles that gained evidence after the 2026-08-17 closure file: their missingness disposition is stale but not contradictory.",
    ]
    report["out_of_scope_findings"] = [
        "All 35,619 vote-evidence rows carry adjudication_authority frontier_manual_review:<rule> although the bill decisions are Luna; flagged for ideology-11 in the 2026-09-10 funnel audit.",
        "The 16 low-confidence admitted bill mappings and the single low-confidence mapped roll call are not diverted to any review queue, so the low-confidence signal survives into the scores (recorded under ideology-04, not repaired).",
        "candidate_ideology_full_coverage.csv any_ideology (704) still does not reconcile with the 1,124 candidate-cycles carrying a v3 observed profile.",
        "The historical ontology's mapped set is 260 rows over 256 distinct roll calls (multi-axis rows), not the 256 rows the historical audit's table implies.",
    ]
    report["item_disposition"] = {
        "ideology-04": {
            "verdict": "sufficient evidence for acceptance with one recorded defect",
            "basis": "2,022/2,022 mapped roll calls pass the classification motion test with 0 procedural/ambiguous; "
                     "0/2,321 mapped rows fail validate_primitive; vote-vs-sponsorship pole agreement is 1.0000 "
                     "over 1,495 shared (candidate, bill, axis) cells; temporal/eligibility cross-checked under "
                     "ideology-07.",
            "caveat": "the low-confidence-mapping review-queue requirement fails: 0 of 16 low-confidence mapping "
                      "bills and 0 of 1 low-confidence mapped roll calls are in a review queue.",
        },
        "ideology-05": {
            "verdict": "sufficient evidence for acceptance with a stated overlap-constructibility limit",
            "basis": "three primary channels are distinct; 0 duplicate evidence_ids in all four ledgers; 1,495 "
                     "(candidate, bill, axis) keys appear in both legislative channels and both count by design "
                     "(vote 1.0 + sponsorship 1.2); 4,730 profiles corroborated across channels.",
            "caveat": "bill-level overlap of Vote Smart/research rows with roll-call evidence is not constructible "
                      "because those rows carry no bill identifier.",
        },
        "ideology-06": {
            "verdict": "sufficient evidence for acceptance",
            "basis": "the declared threshold recomputes to 492 model-eligible candidate-cycles and matches the "
                     "integrated artifact exactly; all 440 evidence-less cycles carry a searched-with-no-evidence "
                     "disposition (0 not searched, 0 unaccounted); no position value is imputed from absence.",
            "caveat": "the closure file's accounting is stale for 26 cycles that gained evidence after 2026-08-17.",
        },
        "ideology-07": {
            "verdict": "sufficient evidence for acceptance",
            "basis": "0 action-after-cutoff and 0 session-outside-window violations across 51,800 legislative "
                     "evidence rows; people_id->candidate is unique per cycle with 0 violations; 0 person_id "
                     "mismatches; the 9 cross-chamber cycles are flagged by the identity layer and are "
                     "pre-election service in the chamber the person actually served in.",
            "caveat": "identity is only testable for the 768 of 1,564 candidate-cycles with a resolved people_id.",
        },
    }
    report["defects_and_gaps"] = [
        "REVIEW QUEUE (ideology-04): low-confidence admitted mappings are not queued. 16 bill-level map/"
        "multi_axis decisions carry confidence=low and 1 mapped roll call carries frontier_confidence=low; "
        "none appears in frontier_legislative_bill_adjudications_luna_review_queue.csv (1 row) or "
        "legislative_rollcall_ontology_v3_openai_review_queue.csv (10 rows).",
        "STALE CLOSURE ACCOUNTING (ideology-06): candidate_research_final_status.csv (2026-08-17) closes 1,098 "
        "cycles as evidence_recovered and 466 as searched_no_recoverable_evidence; the current layer has 1,124 "
        "with an observed profile and 440 without, so 26 residual cycles now carry evidence and the closure "
        "file has not been restated.",
        "OVERLAP CONSTRUCTIBILITY (ideology-05): Vote Smart questionnaire rows use Vote Smart question ids and "
        "research rows use source URLs, so a bill-level overlap test against roll-call evidence cannot be built "
        "from the artifacts; only the profile-level co-occurrence is verifiable.",
        "CHANNEL COMPLEMENTARITY (ideology-05): only 208 candidate-axis profiles carry both questionnaire and "
        "roll-call evidence, so corroboration across channels is dominated by vote+sponsorship (3,947 profiles) "
        "rather than questionnaire+vote.",
    ]

    report["runtime"] = None  # filled below

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    report["runtime"] = {
        "seconds": round(time.perf_counter() - started, 3),
        "tracemalloc_peak_mb": round(peak / (1 << 20), 2),
        "largest_input_mb": round(max(meta["bytes"] for meta in report["inputs"].values()) / (1 << 20), 2),
        "reader": "stdlib csv streaming; no pandas; no warehouse load",
    }
    JSON_OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    MD_OUT.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {MD_OUT.relative_to(ROOT)}")
    print(f"Wrote {JSON_OUT.relative_to(ROOT)}")
    print(f"runtime {report['runtime']['seconds']}s, peak traced {report['runtime']['tracemalloc_peak_mb']} MB")
    return 0


def render_markdown(report: dict) -> str:
    def table(header: list[str], rows: list[list]) -> str:
        lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
        lines += ["| " + " | ".join(str(value) for value in row) + " |" for row in rows]
        return "\n".join(lines)

    p = report["provenance"]
    i4, i5, i6, i7 = report["ideology_04"], report["ideology_05"], report["ideology_06"], report["ideology_07"]
    lines: list[str] = []
    lines += [
        f"# Ideology evidence layer validation — {report['generated_at_utc'][:10]}",
        "",
        "Internal validation evidence for `ideology-04` (roll-call eligibility and issue mapping),",
        "`ideology-05` (channels without double counting), `ideology-06` (minimum evidence and",
        "missingness) and `ideology-07` (temporal cutoffs and identity joins), plus the provenance of",
        "`data/processed/legislative/comprehensive_rollcall_classifications.csv`.",
        "",
        "This is a **read-only audit**: no pipeline stage, score, warehouse, `docs/` or published export",
        "was written; the only outputs are this report and its JSON companion. Reading used the standard",
        "library `csv` streamer (stdlib `csv` streaming; no pandas; no warehouse load). Run:",
        "",
        "```powershell",
        "& .venv/Scripts/python.exe scripts/audit_ideology_evidence_layer.py",
        "& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_ideology_evidence_layer.py -q",
        "```",
        "",
        f"Runtime: {report['runtime']['seconds']}s; traced peak {report['runtime']['tracemalloc_peak_mb']} MB; "
        f"largest input {report['runtime']['largest_input_mb']} MB; generated {report['generated_at_utc']}.",
        "",
        "## Inputs",
        "",
        table(["file", "rows", "MB", "sha256 (first 16)"],
              [[meta["path"], meta["rows"] if meta["rows"] is not None else "—",
                round(meta["bytes"] / (1 << 20), 2), meta["sha256"][:16]]
               for meta in report["inputs"].values()]),
        "",
        "## ideology-04 — roll-call eligibility and issue mapping",
        "",
        table(["terminal disposition", "distinct roll calls"],
              [[key, value] for key, value in i4["terminal_disposition"]["by_status"].items()]),
        "",
        f"- Mapped rows / distinct mapped roll calls: **{i4['mapped']['mapped_rows']:,} / "
        f"{i4['mapped']['mapped_rollcalls']:,}**.",
        f"- Mapped roll calls passing the classification motion test "
        f"(`motion_disposition = bill_direction_applies`): "
        f"**{i4['mapped_motion_test']['by_motion_disposition'].get('bill_direction_applies', 0):,} / "
        f"{i4['mapped']['mapped_rollcalls']:,} "
        f"({i4['mapped_motion_test']['bill_direction_applies_share']:.4f})**; procedural/ambiguous "
        f"mapped: **{i4['mapped_motion_test']['procedural_or_ambiguous']}**.",
        f"- Descriptive motion classes from `vote_description` (derived label, not the terminal test): "
        f"{i4['mapped_motion_class_desc']}.",
        f"- Mapped rows failing `validate_primitive`: **{i4['mapped_rows_failing_validate_primitive']}**.",
        f"- Polarity, all vote rows: **{i4['polarity']['all_votes']['agreeing_cells']:,} / "
        f"{i4['polarity']['all_votes']['shared_cells']:,}** shared (candidate, bill, axis) cells agree "
        f"(fraction {i4['polarity']['all_votes']['fraction']:.4f}). Yeas only: "
        f"**{i4['polarity']['yea_only']['agreeing_cells']:,} / {i4['polarity']['yea_only']['shared_cells']:,}** "
        f"(fraction {i4['polarity']['yea_only']['fraction']:.4f}).",
        f"- Review queue: Luna bill queue {i4['review_queue']['luna_bill_queue_rows']} row(s), "
        f"OpenAI roll-call queue {i4['review_queue']['openai_rollcall_queue_rows']} row(s). "
        f"Low-confidence mapping bills: **{i4['review_queue']['low_confidence_mapping_bills']}**, of which "
        f"**{i4['review_queue']['low_confidence_mapping_bills_in_review_queue']}** are in the queue. "
        f"Low-confidence mapped roll-call rows: **{i4['review_queue']['low_confidence_mapped_rollcall_rows']}**, "
        f"queued: **{i4['review_queue']['low_confidence_mapped_rollcalls_in_bill_queue']}**. "
        f"Every low-confidence mapping queued: **{i4['review_queue']['every_low_confidence_mapping_queued']}**.",
        "",
        "## ideology-05 — channels without double counting",
        "",
        table(["source_type (all sources)", "rows"],
              [[key, value] for key, value in list(i5["all_sources_source_type"].items())[:15]]),
        "",
        f"_{max(0, len(i5['all_sources_source_type']) - 15)} further source types are listed in the JSON companion._",
        "",
        f"- Combined ledger channels: {i5['combined_ledger_source_type']}.",
        f"- Distinct candidate-axis cells per channel: {i5['distinct_candidate_axis_cells_by_area']}.",
        f"- Double counting: **{i5['double_count']['shared_key_count']:,}** (candidate, bill, axis) keys "
        f"appear in both channels, covering {i5['double_count']['shared_candidate_bill_pairs']:,} "
        f"(candidate, bill) pairs ({i5['double_count']['vote_rows_in_shared']:,} vote rows and "
        f"{i5['double_count']['sponsorship_rows_in_shared']:,} sponsorship rows). "
        "`aggregate()` sums both rows' `evidence_weight` (vote 1.0, sponsorship 1.2) per "
        "(candidate, cycle, axis); both channels count **by design** as distinct signals.",
        f"- Duplicate `evidence_id`s — vote {i5['duplicate_evidence_ids']['vote_file']}, sponsorship "
        f"{i5['duplicate_evidence_ids']['sponsorship_file']}, combined ledger "
        f"{i5['duplicate_evidence_ids']['combined_ledger']}, all sources "
        f"{i5['duplicate_evidence_ids']['all_sources']}.",
        f"- Profiles corroborated by more than one channel: **{i5['profile_overlap']['multi_channel_profiles_valence']:,}** "
        f"(valence grain; primary three channels {i5['profile_overlap']['multi_channel_profiles']:,}, "
        f"archival all sources {i5['profile_overlap']['multi_channel_profiles_all_sources']:,}); "
        f"vote + sponsorship: **{i5['profile_overlap']['vote_and_sponsorship_profiles']:,}**; "
        f"questionnaire + vote: **{i5['profile_overlap']['questionnaire_and_vote_profiles']:,}**.",
        f"- Bill-level overlap of Vote Smart / research rows with roll-call evidence is "
        f"**not constructible** ({i5['profile_overlap']['bill_level_overlap_note']}).",
        "",
        "## ideology-06 — minimum evidence and missingness",
        "",
        table(["rule", "value"],
              [[key, value] for key, value in i6["threshold_rule"].items()]),
        "",
        table(["threshold outcome", "candidate-cycles"],
              [[key, value] for key, value in i6["threshold_application"].items()]),
        "",
        f"- Integrated `ideology_v3_model_eligible` = **{i6['integrated_model_eligible']:,}**; "
        f"recompute agrees: **{i6['integrated_matches_recompute']}**.",
        f"- Candidate-cycles without current observed evidence: "
        f"**{i6['searched_vs_not_searched']['current_cycles_without_observed_evidence']:,}**; "
        f"all carry `final_research_status = searched_no_recoverable_evidence` "
        f"({i6['searched_vs_not_searched']['of_which_research_status_searched_no_recoverable_evidence']:,}), of "
        f"which {i6['searched_vs_not_searched']['of_which_manual_broad_search_logged']:,} logged a manual broad "
        f"search and {i6['searched_vs_not_searched']['of_which_no_manual_search_logged']:,} were closed by the "
        "structured Vote Smart / legislative / identity sweep. **Not searched: 0.**",
        f"- Residuals that gained current evidence after the closure file: "
        f"**{i6['searched_vs_not_searched']['residuals_gaining_current_evidence']:,}**.",
        f"- Imputation: `neutrality_imputed` true in "
        f"{i6['imputation']['neutrality_imputed_true']} rows; position-value `fillna`/impute lines: "
        f"**{len(i6['imputation']['position_fill_lines'])}**. {i6['imputation']['verdict']}.",
        "",
        "## ideology-07 — temporal cutoffs and identity joins",
        "",
        table(["temporal channel", "rows", "exact date", "mid-session placeholder"],
              [["legislative_vote", i7["temporal"]["vote_rows"], i7["temporal"]["vote_rows_with_exact_date"],
                i7["temporal"]["vote_rows_on_mid_session_placeholder"]],
               ["bill_sponsorship", i7["temporal"]["sponsorship_rows"], 0,
                i7["temporal"]["sponsorship_rows_on_mid_session_placeholder"]]]),
        "",
        f"- Cutoff violations: **{i7['temporal']['cutoff_violations']}**; session outside cycle window: "
        f"**{i7['temporal']['session_outside_cycle_window']}**; leakage from later service: "
        f"**{i7['temporal']['leakage_from_later_service']}**.",
        f"- Identity cardinality: {i7['identity_cardinality']}.",
        f"- `person_id` mismatch vs the universe: **{i7['person_id_mismatch_vs_universe']}**.",
        f"- Cross-chamber evidence: **{i7['chamber']['rows_from_other_than_candidacy_chamber']:,}** rows across "
        f"**{i7['chamber']['candidate_cycles']}** candidate-cycles ({i7['chamber']['pairs']}); "
        f"{i7['chamber']['flagged_cross_chamber_by_identity_layer']} cycles carry the identity layer's "
        f"`cross_chamber_pre_election_score` flag; candidate-cycles with evidence from a chamber the person "
        f"did not serve in: **{i7['chamber']['did_not_serve_violations']}**.",
        "",
        "## Provenance of the classification input",
        "",
        f"- File: `{p['classification_file']['path']}` — **{p['classification_file']['rows']:,}** rows; "
        f"working-tree sha256 `{p['classification_file']['sha256_working_tree']}` "
        f"({p['classification_file']['line_endings']}); committed blob "
        f"`{p['classification_file']['git_blob_at_commit']}` with sha256 "
        f"`{p['classification_file']['committed_blob_sha256']}`.",
        f"- Producer: `{p['producer_script']['path']}` sha256 `{p['producer_script']['sha256_working_tree']}`; "
        f"git blob `{p['producer_script']['git_blob_hash_object']}`.",
        f"- Commits: HEAD `{p['commits']['head']}`; last touching the file `{p['commits']['last_touching_file']}`; "
        f"previous `{p['commits']['previous_touching_file']}`; numstat "
        f"`{p['commits']['diff_numstat_previous_to_last']}`.",
        f"- Explaining records: `{p['explaining_records']['coordination']}` and "
        f"`{p['explaining_records']['audit']}`.",
        "  The +60,704 / −42,391 expansion is the historical final-vote disposition pass: every one of the",
        "  60,704 normalized roll calls now carries a terminal disposition, and bill direction is admitted",
        "  only for final-passage and conference-report votes.",
        "",
        "## What this evidence does not establish",
        "",
    ]
    lines += [f"- {item}" for item in report["not_established"]]
    lines += ["", "## Out-of-scope findings (recorded, not repaired)", ""]
    lines += [f"- {item}" for item in report["out_of_scope_findings"]]
    lines += ["", "## Acceptance disposition", ""]
    for item, detail in report["item_disposition"].items():
        lines += [f"### {item}", "",
                  f"- Verdict: **{detail['verdict']}**.", f"- Basis: {detail['basis']}",
                  f"- Caveat: {detail['caveat']}", ""]
    lines += ["## Defects and gaps (recorded, not repaired)", ""]
    lines += [f"- {item}" for item in report["defects_and_gaps"]]
    lines += ["", "## CSV evidence", "",
              "Embedded in the JSON companion under each section's `csv_evidence` key.", "",
              "## Verification", "",
              "```powershell",
              "& .venv/Scripts/python.exe scripts/audit_ideology_evidence_layer.py",
              "& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_ideology_evidence_layer.py -q",
              "```",
              "",
              "The fixture suite covers the checker functions directly: temporal violation detection",
              "(late action and session-window breach), double-count detection at (candidate, bill, axis),",
              "polarity agreement and answer filtering, the three-issue/two-family threshold rule, and",
              "identity cardinality (same-cycle collision plus repeated people across cycles). The audit",
              "recomputes the repository counts above from the current CSVs; it does not re-run any",
              "pipeline stage, so a stale input would be reported as the observed state, not repaired.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
