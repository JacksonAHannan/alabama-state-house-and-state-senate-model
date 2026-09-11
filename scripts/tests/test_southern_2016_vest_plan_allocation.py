from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data/processed/elections/alabama_elections.sqlite"
BLOCK_MANIFEST = ROOT / "data/processed/source_audits/southern_2020_census_block_manifest.csv"
OUTPUT = ROOT / "data/processed/presidential/southern_vest_2016_allocations"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def test_census_block_manifest_is_complete_and_matches_immutable_sources() -> None:
    manifest = pd.read_csv(BLOCK_MANIFEST, dtype=str).fillna("")
    assert len(manifest) == 14
    assert manifest.state_code.nunique() == 14
    assert manifest.source_file_id.is_unique
    assert manifest.ingest_status.eq("acquired").all()
    assert manifest.sha256.str.fullmatch(r"[0-9a-f]{64}").all()
    for row in manifest.itertuples(index=False):
        path = ROOT / row.local_path
        assert path.exists()
        assert path.stat().st_size == int(row.size_bytes)
        assert digest(path) == row.sha256


def test_vest_crosswalk_is_complete_unique_and_within_acceptance_gates() -> None:
    with sqlite3.connect(DB) as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM warehouse_schema_version"
        ).fetchone()[0] >= 20
        assert connection.execute(
            "SELECT COUNT(*) FROM source_southern_census_block_file"
        ).fetchone()[0] == 14
        assert connection.execute(
            "SELECT COUNT(*) FROM bridge_southern_vest_precinct_district_weight"
        ).fetchone()[0] == 96_114
        assert connection.execute(
            "SELECT COUNT(*) FROM qa_southern_vest_precinct_plan_allocation"
        ).fetchone()[0] == 28
        assert connection.execute(
            """SELECT COUNT(*) FROM qa_southern_vest_precinct_plan_allocation
               WHERE validation_status!='passed'
                  OR weighted_positive_vote_precincts!=positive_vote_precincts
                  OR max_precinct_weight_error>1e-10
                  OR unmatched_positive_vap/total_positive_vap>0.001
                  OR fallback_two_party_votes/total_two_party_votes>0.001"""
        ).fetchone()[0] == 0
        assert connection.execute(
            """SELECT COUNT(*) FROM (
                 SELECT result_observation_id,assignment_source_file_id,chamber,
                        ABS(SUM(allocation_weight)-1.0) AS error
                 FROM bridge_southern_vest_precinct_district_weight
                 GROUP BY 1,2,3 HAVING error>1e-10)"""
        ).fetchone()[0] == 0


def test_2016_on_2022_plan_fact_is_complete_and_vote_conserving() -> None:
    with sqlite3.connect(DB) as connection:
        rows = connection.execute(
            """SELECT dem_votes,rep_votes,two_party_dem_margin
               FROM fact_southern_presidential_district_result
               WHERE election_cycle=2016 AND plan_cycle=2022"""
        ).fetchall()
        states = connection.execute(
            """SELECT COUNT(DISTINCT state_code)
               FROM fact_southern_presidential_district_result
               WHERE election_cycle=2016 AND plan_cycle=2022"""
        ).fetchone()[0]
        reviews = connection.execute(
            """SELECT COUNT(*) FROM qa_southern_presidential_district_allocation
               WHERE election_cycle=2016 AND reconciliation_status!='exact'"""
        ).fetchone()[0]
    assert len(rows) == 2_266
    assert states == 14
    assert reviews == 0
    for dem_votes, rep_votes, margin in rows:
        expected = (dem_votes - rep_votes) / (dem_votes + rep_votes)
        assert abs(margin - expected) < 1e-12


def test_export_identifies_latest_validated_run() -> None:
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    validation = manifest["validation"]
    assert validation["district_result_rows"] == 2_266
    assert validation["state_chamber_audits"] == 28
    assert validation["review_audits"] == 0
    assert validation["maximum_fallback_vote_share"] <= 0.001
    assert validation["maximum_unmatched_vap_share"] <= 0.001
    with sqlite3.connect(DB) as connection:
        run = connection.execute(
            """SELECT build_run_id,status FROM warehouse_build_run
               WHERE target='southern_2016_vest_plan_allocation'
               ORDER BY started_at_utc DESC LIMIT 1"""
        ).fetchone()
    assert run == (manifest["build_run_id"], "validated")
