from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data/processed/elections/alabama_elections.sqlite"
MANIFEST = ROOT / "data/processed/source_audits/southern_2016_vest_manifest.csv"
VALIDATION = ROOT / "data/processed/source_audits/southern_2016_vest_warehouse_validation.json"


def test_vest_manifest_is_complete_immutable_and_redistributable() -> None:
    manifest = pd.read_csv(MANIFEST, dtype=str).fillna("")
    assert len(manifest) == 14
    assert manifest.state_code.nunique() == 14
    assert manifest.source_file_id.is_unique
    assert manifest.sha256.str.fullmatch(r"[0-9a-f]{64}").all()
    assert manifest.upstream_md5.str.fullmatch(r"[0-9a-f]{32}").all()
    assert manifest.retrieved_at.ne("").all()
    assert manifest.license_or_terms.str.contains("CC BY 4.0", regex=False).all()
    assert manifest.ingest_status.eq("acquired").all()


def test_vest_results_and_geometry_have_an_exact_one_to_one_bridge() -> None:
    with sqlite3.connect(DB) as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM warehouse_schema_version"
        ).fetchone()[0] >= 19
        sources = connection.execute(
            "SELECT COUNT(*) FROM source_southern_vest_context_file"
        ).fetchone()[0]
        results = connection.execute(
            """SELECT COUNT(*) FROM source_southern_presidential_geography_result
               WHERE source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)"""
        ).fetchone()[0]
        units = connection.execute(
            """SELECT COUNT(*) FROM dim_southern_geography_unit u
               JOIN dim_southern_geography_layer l USING(geography_layer_id)
               WHERE l.source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)"""
        ).fetchone()[0]
        links = connection.execute(
            """SELECT COUNT(*) FROM bridge_southern_result_geography b
               JOIN source_southern_presidential_geography_result r USING(result_observation_id)
               WHERE r.source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)
                 AND b.match_method='same_archive_precinct_identifier'
                 AND b.review_status='accepted' AND b.allocation_weight=1.0"""
        ).fetchone()[0]
        bad_math = connection.execute(
            """SELECT COUNT(*) FROM source_southern_presidential_geography_result
               WHERE source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)
                 AND ABS(total_votes-(dem_votes+rep_votes+other_votes))>0.011"""
        ).fetchone()[0]
        audits = connection.execute(
            """SELECT COUNT(*),SUM(repaired_input_geometries),SUM(normalized_precincts),
                      SUM(result_geometry_links)
               FROM qa_southern_vest_context_ingest
               WHERE reconciliation_status='exact'"""
        ).fetchone()
    assert sources == 14
    assert results == units == links == 45_990
    assert bad_math == 0
    assert audits == (14, 15, 45_990, 45_990)


def test_vest_validation_file_matches_latest_validated_run() -> None:
    report = json.loads(VALIDATION.read_text(encoding="utf-8"))
    assert report["validation"]["states"] == 14
    assert report["validation"]["input_features"] == 46_065
    assert report["validation"]["normalized_precincts"] == 45_990
    assert report["validation"]["review_states"] == 0
    with sqlite3.connect(DB) as connection:
        run = connection.execute(
            """SELECT build_run_id,status FROM warehouse_build_run
               WHERE target='southern_2016_vest_context'
               ORDER BY started_at_utc DESC LIMIT 1"""
        ).fetchone()
    assert run == (report["build_run_id"], "validated")
