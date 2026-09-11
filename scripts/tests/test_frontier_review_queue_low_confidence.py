"""Fixture tests for the low-confidence admitted-mapping review-queue invariant.

A ``map``/``multi_axis`` bill whose model confidence is only ``low`` is still
admitted to scoring (the 2026-09-08 owner contract queues it, it does not
exclude it), so it must appear in the Luna review queue and a low-confidence
mapped roll call must appear in the roll-call queue. These tests drive the
reconciliation step against small synthetic frames; they never touch the real
repository artifacts.
"""
from __future__ import annotations

import build_frontier_legislative_review_ledger as ledger
import pandas as pd

MANUAL_HEADER = ("bill_id,session_year,bill_number,reviewed_document_type,decision,primitive_axes,"
                 "policy_poles,confidence,rationale,reviewer,review_date,supersedes_authority\n")
LUNA_HEADER = ("bill_id,session_year,bill_number,reviewed_document_type,confidence,rationale,reviewer,"
               "review_date,supersedes_authority,decision,primitive_axes,policy_poles,review_reason\n")
OPENAI_HEADER = ("unit_id,issue_code,title,decision,primitive_axis,policy_pole,confidence,"
                 "terminal_status,rationale\n")
ONTOLOGY_HEADER = ("canonical_rollcall_id,bill_id,session_year,bill_number,vote_description,decision,"
                   "primitive_axis,policy_pole,frontier_confidence,terminal_status\n")


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _fixture(tmp_path, *, luna_existing=True, openai_existing=True):
    manual = _write(tmp_path, "manual.csv", MANUAL_HEADER +
                    "100,2019,HB1,official_synopsis,map,gun_access,expand,low,weak,gpt-5.6-luna,2026-09-08,frontier_manual_review\n"
                    "200,2019,HB2,official_synopsis,map,gun_access,restrict,high,clear,gpt-5.6-luna,2026-09-08,frontier_manual_review\n"
                    "300,2020,SB3,official_synopsis,procedural,,,,low,admin,gpt-5.6-luna,2026-09-08,frontier_manual_review\n"
                    "400,2021,HB4,official_synopsis,multi_axis,gun_access;tax_burden,expand;decrease,low,fuzzy,gpt-5.6-luna,2026-09-08,frontier_manual_review\n")
    ontology = _write(tmp_path, "ontology.csv", ONTOLOGY_HEADER +
                      "LS-1,100,2019,HB1,Third Reading,map,gun_access,expand,low,mapped_frontier_policy_pole\n"
                      "LS-2,200,2019,HB2,Third Reading,map,gun_access,restrict,high,mapped_frontier_policy_pole\n"
                      "LS-9,999,2018,HB9,Third Reading,exclude,,,low,excluded_frontier_procedural\n")
    luna_path = tmp_path / "luna_queue.csv"
    if luna_existing:
        luna_path.write_text(LUNA_HEADER +
                             "999,2018,HB9,official_synopsis,high,bad axis,gpt-5.6-luna,2026-09-08,"
                             "frontier_manual_review,mixed_no_scalar_direction,,,invalid_axis_pole:x\n",
                             encoding="utf-8")
    openai_path = tmp_path / "openai_queue.csv"
    if openai_existing:
        openai_path.write_text(OPENAI_HEADER +
                               "DEADBEEF,criminal_justice,Some bill,exclude,,,low,"
                               "excluded_after_substantive_text_review,insufficient text\n",
                               encoding="utf-8")
    return manual, ontology, luna_path, openai_path


def _reconcile(manual, ontology, luna, openai):
    return ledger.reconcile_low_confidence_review_queues(
        manual_path=str(manual), ontology_path=str(ontology),
        luna_queue_path=str(luna), openai_queue_path=str(openai))


def test_low_confidence_admitted_mapping_is_queued(tmp_path):
    manual, ontology, luna, openai = _fixture(tmp_path)
    counts = _reconcile(manual, ontology, luna, openai)
    assert counts["luna_queue_rows_appended"] == 2  # the map and the multi_axis

    queued = pd.read_csv(luna, dtype=str).fillna("")
    by_bill = {row.bill_id: row for row in queued.itertuples(index=False)}
    assert "100" in by_bill and "400" in by_bill
    assert "200" not in by_bill  # high confidence is not queued
    assert "300" not in by_bill  # non-scoring is not queued
    assert by_bill["100"].decision == "map"
    assert by_bill["400"].decision == "multi_axis"
    for bill in ("100", "400"):
        assert by_bill[bill].review_reason == ledger.LOW_CONFIDENCE_REASON
        assert by_bill[bill].confidence == "low"


def test_existing_queue_rows_and_adjudications_are_preserved(tmp_path):
    manual, ontology, luna, openai = _fixture(tmp_path)
    manual_before = manual.read_bytes()
    luna_before = pd.read_csv(luna, dtype=str).fillna("")
    openai_before = pd.read_csv(openai, dtype=str).fillna("")
    _reconcile(manual, ontology, luna, openai)

    # The scoring input is never rewritten: queue membership does not change scores.
    assert manual.read_bytes() == manual_before

    queued = pd.read_csv(luna, dtype=str).fillna("")
    original = queued[queued.bill_id == "999"].iloc[0]
    assert original.review_reason == "invalid_axis_pole:x"
    assert original.decision == "mixed_no_scalar_direction"
    assert len(queued) == len(luna_before) + 2

    rollcalls = pd.read_csv(openai, dtype=str).fillna("")
    existing = rollcalls[rollcalls.unit_id == "DEADBEEF"].iloc[0]
    assert existing.terminal_status == "excluded_after_substantive_text_review"
    assert len(rollcalls) == len(openai_before) + 1


def test_low_confidence_mapped_rollcall_goes_to_rollcall_queue(tmp_path):
    manual, ontology, luna, openai = _fixture(tmp_path)
    counts = _reconcile(manual, ontology, luna, openai)
    assert counts["openai_queue_rows_appended"] == 1

    rollcalls = pd.read_csv(openai, dtype=str).fillna("")
    by_unit = {row.unit_id: row for row in rollcalls.itertuples(index=False)}
    assert "LS-1" in by_unit and "LS-2" not in by_unit and "LS-9" not in by_unit
    assert by_unit["LS-1"].decision == "map"
    assert by_unit["LS-1"].review_reason == ledger.LOW_CONFIDENCE_REASON
    assert by_unit["LS-1"].primitive_axis == "gun_access"
    assert by_unit["LS-1"].policy_pole == "expand"


def test_reconcile_is_idempotent(tmp_path):
    manual, ontology, luna, openai = _fixture(tmp_path)
    first = _reconcile(manual, ontology, luna, openai)
    luna_rows, openai_rows = first["luna_queue_rows"], first["openai_queue_rows"]
    second = _reconcile(manual, ontology, luna, openai)
    assert second == {"luna_queue_rows_appended": 0, "openai_queue_rows_appended": 0,
                      "luna_queue_rows": luna_rows, "openai_queue_rows": openai_rows}


def test_high_confidence_only_produces_no_queue_rows(tmp_path):
    manual, ontology, luna, openai = _fixture(tmp_path)
    manual.write_text(MANUAL_HEADER +
                      "200,2019,HB2,official_synopsis,map,gun_access,restrict,high,clear,gpt-5.6-luna,2026-09-08,frontier_manual_review\n",
                      encoding="utf-8")
    ontology.write_text(ONTOLOGY_HEADER +
                        "LS-2,200,2019,HB2,Third Reading,map,gun_access,restrict,high,mapped_frontier_policy_pole\n",
                        encoding="utf-8")
    counts = _reconcile(manual, ontology, luna, openai)
    assert counts["luna_queue_rows_appended"] == 0
    assert counts["openai_queue_rows_appended"] == 0
