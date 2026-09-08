from __future__ import annotations

import hashlib
import json
from pathlib import Path

import alabama_2018_official_results as adapter


ROOT = Path(__file__).resolve().parents[2]
CANVASS_SHA256 = "a83be9be26ac195989bf94ad5097e4269f516674f645373526a9d6621f310044"
PRECINCT_SHA256 = "fb467ac457e8ac30c3d817afa4ea94f72ca6b4d3bab6f677bee624c579946c4e"
AUDIT = ROOT / "project_docs/audits/ALABAMA_2018_CERTIFIED_SOURCE_RECONCILIATION.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_certified_canvass_has_exact_legislative_coverage() -> None:
    frame, metadata = adapter.load_certified_canvass(ROOT)
    assert metadata == {
        "source_path": adapter.CANVASS.as_posix(),
        "sha256": CANVASS_SHA256,
        "page_count": 192,
        "legislative_contests": 140,
        "total_pages": 38,
        "state_code": "AL",
        "cycle": 2018,
        "stage": "general",
    }
    assert len(frame) == 352
    assert frame.groupby("party").size().to_dict() == {
        "D": 94,
        "I": 6,
        "L": 2,
        "O": 140,
        "R": 110,
    }
    assert frame[frame.category.eq("write_in")].groupby(
        ["chamber", "district"]
    ).size().eq(1).all()
    assert not frame.duplicated(adapter.KEY + ["category"]).any()


def test_precinct_adapter_preserves_physical_blanks() -> None:
    cells, metadata = adapter.load_official_cells(ROOT)
    assert metadata["sha256"] == PRECINCT_SHA256
    assert metadata["county_count"] == len(metadata["members"]) == 67
    assert metadata["unknown_cells"] > 0
    assert not cells.duplicated(
        ["source_member", "source_sheet", "source_row", "source_column"]
    ).any()
    assert cells.loc[cells.value_status.eq("unknown"), "votes"].isna().all()
    assert cells.loc[cells.value_status.eq("observed"), "votes"].notna().all()


def test_precinct_and_certified_sources_reconcile_or_remain_review() -> None:
    reconciliation, sources = adapter.reconcile_sources(ROOT)
    assert sources["precinct_source"]["sha256"] == PRECINCT_SHA256
    assert sources["canvass_source"]["sha256"] == CANVASS_SHA256
    assert len(reconciliation) == 352
    assert reconciliation.groupby("reconciliation_status").size().to_dict() == {
        "matched_certified_total": 322,
        "review": 30,
    }
    assert reconciliation.groupby("reconciliation_reason").size().to_dict() == {
        "exact_name_party_contest_category_and_votes": 322,
        "missing_precinct_candidate": 1,
        "vote_mismatch": 29,
    }
    assert reconciliation.groupby("candidate_alignment_method").size().to_dict() == {
        "precinct_candidate_scope_absent": 1,
        "unique_exact_contest_party_category": 351,
    }
    assert reconciliation.unknown_cells.fillna(0).ge(0).all()
    assert int(reconciliation.unknown_cells.fillna(0).sum()) == 24912
    assert reconciliation.loc[
        reconciliation.unknown_cells.fillna(0).gt(0), "aggregation_status"
    ].eq("observed_cell_subtotal").all()
    review = reconciliation[reconciliation.reconciliation_status.eq("review")].copy()
    review["delta"] = review.observed_votes - review.certified_votes
    assert review.delta.dropna().le(0).all()
    assert int(review.delta.fillna(0).abs().sum()) == 1593


def test_reconciliation_audit_replays_exact_sources_and_code() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["status"] == "review_required_precinct_subtotals_below_certified_canvass"
    assert audit["precinct_source"]["sha256"] == digest(ROOT / adapter.ARCHIVE)
    assert audit["canvass_source"]["sha256"] == digest(ROOT / adapter.CANVASS)
    for path, expected in audit["code_sha256"].items():
        assert digest(ROOT / path) == expected
    reconciliation, _ = adapter.reconcile_sources(ROOT)
    assert len(reconciliation) == audit["coverage"]["certified_rows"]
    assert int(reconciliation.unknown_cells.fillna(0).sum()) == audit["coverage"][
        "unknown_precinct_cells_retained"
    ]
    assert int(reconciliation.reconciliation_status.eq("matched_certified_total").sum()) == audit[
        "reconciliation"
    ]["matched_certified_total_rows"]
    assert int(reconciliation.reconciliation_status.eq("review").sum()) == audit[
        "reconciliation"
    ]["review_rows"]
