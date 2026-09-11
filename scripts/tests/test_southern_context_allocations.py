from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data/processed/elections/alabama_elections.sqlite"
ASSIGNMENT_MANIFEST = (
    ROOT / "data/processed/source_audits/southern_context_assignment_manifest.csv"
)
OUTPUT = ROOT / "data/processed/presidential/southern_context_allocations"


def test_assignment_manifest_registers_two_immutable_national_archives() -> None:
    manifest = pd.read_csv(ASSIGNMENT_MANIFEST, dtype=str).fillna("")
    assert set(manifest.source_file_id) == {
        "RDH-NATIONAL-2022-SLD-BAF",
        "RDH-NATIONAL-2024-SLD-BAF",
    }
    assert manifest.source_file_id.is_unique
    assert manifest.ingest_status.eq("acquired").all()
    assert manifest.sha256.str.fullmatch(r"[0-9a-f]{64}").all()
    assert manifest.retrieved_at.ne("").all()
    assert manifest.geography_vintage.str.contains("2020 Census blocks", regex=False).all()


def test_central_allocations_are_unique_complete_and_vote_conserving() -> None:
    with sqlite3.connect(DB) as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM warehouse_schema_version"
        ).fetchone()[0] >= 18
        assert connection.execute(
            """SELECT COUNT(*) FROM source_southern_assignment_file
               WHERE source_file_id IN ('RDH-NATIONAL-2022-SLD-BAF',
                                        'RDH-NATIONAL-2024-SLD-BAF')"""
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM bridge_southern_block_district_assignment"
        ).fetchone()[0] == 6_324_382
        assert connection.execute(
            """SELECT COUNT(*) FROM fact_southern_presidential_district_result
               WHERE election_cycle=2020 AND plan_cycle IN (2022,2024)"""
        ).fetchone()[0] == 4_532
        assert connection.execute(
            """SELECT COUNT(*) FROM qa_southern_presidential_district_allocation
               WHERE election_cycle=2020 AND plan_cycle IN (2022,2024)"""
        ).fetchone()[0] == 56
        assert connection.execute(
            """SELECT COUNT(*)
               FROM qa_southern_presidential_district_allocation
               WHERE election_cycle=2020
                 AND plan_cycle IN (2022,2024)
                 AND (reconciliation_status='review' OR allocation_coverage < 0.999999999)"""
        ).fetchone()[0] == 0
        assert connection.execute(
            """SELECT COUNT(*) FROM (
                 SELECT source_file_id,state_code,block_geoid,COUNT(*) AS n
                 FROM bridge_southern_block_district_assignment
                 GROUP BY 1,2,3 HAVING n>1)"""
        ).fetchone()[0] == 0
        assert connection.execute(
            """SELECT COUNT(*)
               FROM fact_southern_presidential_district_result
               WHERE election_cycle=2020
                 AND plan_cycle IN (2022,2024)
                 AND ABS(total_votes-(dem_votes+rep_votes+other_votes))>0.011"""
        ).fetchone()[0] == 0


def test_2020_on_2022_plan_has_all_southern_districts_and_exact_margin_math() -> None:
    with sqlite3.connect(DB) as connection:
        rows = connection.execute(
            """SELECT dem_votes,rep_votes,two_party_dem_margin
               FROM fact_southern_presidential_district_result
               WHERE election_cycle=2020 AND plan_cycle=2022"""
        ).fetchall()
        states = connection.execute(
            """SELECT COUNT(DISTINCT state_code)
               FROM fact_southern_presidential_district_result
               WHERE election_cycle=2020 AND plan_cycle=2022"""
        ).fetchone()[0]
    assert len(rows) == 2_266
    assert states == 14
    for dem_votes, rep_votes, margin in rows:
        expected = (dem_votes - rep_votes) / (dem_votes + rep_votes)
        assert abs(margin - expected) < 1e-12


def test_allocation_export_matches_latest_validated_build() -> None:
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    validation = manifest["validation"]
    assert validation["assignment_sources"] == 2
    assert validation["block_assignment_rows"] == 6_324_382
    assert validation["district_result_rows"] == 4_532
    assert validation["allocation_audits"] == 56
    assert validation["review_audits"] == 0
    assert validation["minimum_two_party_vote_coverage"] >= 0.999999999
    with sqlite3.connect(DB) as connection:
        run = connection.execute(
            """SELECT build_run_id,status
               FROM warehouse_build_run
               WHERE target='southern_presidential_district_allocations'
               ORDER BY started_at_utc DESC LIMIT 1"""
        ).fetchone()
    assert run == (manifest["build_run_id"], "validated")
