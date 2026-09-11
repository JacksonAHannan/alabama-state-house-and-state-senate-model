from pathlib import Path
import importlib.util

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "coverage_audit", ROOT / "scripts" / "audit_legislative_ideology_coverage.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
PREFIX = ROOT / "data" / "processed" / "ideology" / "legislative_ideology_coverage_audit"


def test_role_wins_when_legiscan_future_district_prefix_conflicts():
    roster = MODULE.member_roster()
    beasley = roster[(roster.people_id == 3386) & (roster.chamber == "house")]
    ward = roster[(roster.people_id == 3405) & (roster.chamber == "house")]
    assert int(beasley.first_session.min()) == 2010
    assert int(ward.first_session.min()) == 2010


def test_session_chamber_coverage_is_complete_except_known_2000_senate_gap():
    session = pd.read_csv(f"{PREFIX}_session_chamber.csv")
    assert len(session) == 58
    missing = session[~session.source_present]
    assert missing[["session_year", "chamber"]].to_dict("records") == [
        {"session_year": 2000, "chamber": "senate"}
    ]


def test_classification_audit_accounts_for_every_warehouse_rollcall():
    session = pd.read_csv(f"{PREFIX}_session_chamber.csv")
    classified = pd.read_csv(f"{PREFIX}_classification.csv")
    assert int(session.rollcalls.sum()) == int(classified.rollcalls.sum())
    omitted = classified[classified.status_family == "not_in_classification_table"]
    assert int(omitted.rollcalls.sum()) == 0


def test_candidate_audit_has_unique_rows_and_counts_journal_identities():
    candidates = pd.read_csv(f"{PREFIX}_candidates.csv", low_memory=False)
    assert candidates.canonical_candidate_id.is_unique
    assert candidates.pre_election_identity_resolved.sum() >= candidates.legiscan_identity_resolved.sum()
    covered = candidates[candidates.gap_reason == "score_and_issue_evidence_available"]
    assert covered.legislative_ideology_available.all()
    assert covered.legislative_evidence_rows.gt(0).all()


def test_no_high_confidence_recovery_remains_after_repairs():
    recovery = pd.read_csv(f"{PREFIX}_identity_recovery_queue.csv", low_memory=False)
    high = recovery[recovery.recovery_confidence == "high"]
    assert len(high) == 0


def test_repaired_cam_ward_is_absent_from_the_unresolved_queue():
    recovery = pd.read_csv(f"{PREFIX}_identity_recovery_queue.csv", low_memory=False)
    assert not recovery.canonical_candidate_id.eq("AL-2010-senate-14-R-CAM-WARD").any()
