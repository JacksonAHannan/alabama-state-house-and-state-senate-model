from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

import load_southern_context_warehouse as mod
from southern_war_map_contract import scheduled_keys_2016_2024


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data/processed/elections/alabama_elections.sqlite"
BASE_SCHEMA = ROOT / "scripts/warehouse_schema.sql"
CORRECTION_SCHEMA = ROOT / "scripts/warehouse_southern_presidential_correction_schema.sql"


def test_candidate_rows_are_widened_without_losing_votes() -> None:
    source = pd.DataFrame([
        {"county": "A", "precinct": "One", "candidate": "Obama", "party": "DEM", "votes": 60},
        {"county": "A", "precinct": "One", "candidate": "Romney", "party": "REP", "votes": 35},
        {"county": "A", "precinct": "One", "candidate": "Other", "party": "LIB", "votes": 5},
    ])
    rows, audit = mod.candidate_rows_to_precincts(
        source, state="GA", source_file_id="SOURCE", build_run_id="RUN"
    )
    record = dict(zip(mod.RESULT_COLUMNS, rows[0]))
    assert record["geography_id"] == "GA|A|ONE"
    assert record["dem_votes"] == 60
    assert record["rep_votes"] == 35
    assert record["other_votes"] == 5
    assert record["total_votes"] == 100
    assert round(record["two_party_dem_margin"], 8) == round(25 / 95, 8)
    assert audit["reconciliation_status"] == "exact"


def test_mississippi_harrison_presidential_columns_are_corrected(tmp_path: Path) -> None:
    source = pd.DataFrame([
        {"county": "Harrison", "precinct": "One", "office": "President",
         "candidate": "Barack Obama", "party": "Democrat", "votes": 70},
        {"county": "Harrison", "precinct": "One", "office": "President",
         "candidate": "Mitt Romney", "party": "Republican", "votes": 30},
        {"county": "Adams", "precinct": "One", "office": "President",
         "candidate": "Barack Obama", "party": "Democrat", "votes": 60},
        {"county": "Adams", "precinct": "One", "office": "President",
         "candidate": "Mitt Romney", "party": "Republican", "votes": 40},
    ])
    path = tmp_path / "ms.csv"
    source.to_csv(path, index=False)
    parsed, _ = mod.parse_ms(path)
    harrison = parsed[parsed.county.eq("Harrison")].set_index("party").votes.astype(int)
    adams = parsed[parsed.county.eq("Adams")].set_index("party").votes.astype(int)
    assert harrison.to_dict() == {"Democrat": 30, "Republican": 70}
    assert adams.to_dict() == {"Democrat": 60, "Republican": 40}


def test_presidential_correction_schema_records_its_migration() -> None:
    with sqlite3.connect(":memory:") as connection:
        connection.executescript(BASE_SCHEMA.read_text(encoding="utf-8"))
        connection.executescript(CORRECTION_SCHEMA.read_text(encoding="utf-8"))
        row = connection.execute(
            "SELECT applied_at_utc FROM warehouse_schema_version WHERE version=24"
        ).fetchone()
    assert row is not None and row[0]


def test_context_manifests_have_unique_auditable_assets() -> None:
    presidential, geography = mod.manifests()
    assert len(presidential) == 23
    assert len(geography) == 116
    assert set(zip(geography.state_code, geography.cycle.astype(int), geography.chamber)) == scheduled_keys_2016_2024()
    assert presidential.source_file_id.is_unique
    assert not geography.duplicated(["state_code", "cycle", "chamber"]).any()
    normalized = {
        "RDH-NATIONAL-2020-PRES-BLOCKS",
        "NYT-NATIONAL-2024-PRES-PRECINCT-RESULTS",
        *mod.PARSERS.keys(),
    }
    acquired = presidential[presidential.source_file_id.isin(normalized)]
    assert acquired.ingest_status.eq("acquired").all()
    assert acquired.sha256.str.fullmatch(r"[0-9a-f]{64}").all()


def test_central_warehouse_has_schema_17_source_family_without_implicit_links() -> None:
    with sqlite3.connect(DB) as connection:
        assert connection.execute("SELECT MAX(version) FROM warehouse_schema_version").fetchone()[0] >= 17
        results = connection.execute(
            """SELECT COUNT(*) FROM source_southern_presidential_geography_result
               WHERE source_file_id IN (SELECT source_file_id FROM source_southern_context_file)"""
        ).fetchone()[0]
        layers = connection.execute(
            """SELECT COUNT(*) FROM dim_southern_geography_layer
               WHERE source_file_id IN (SELECT source_file_id FROM source_southern_context_file)"""
        ).fetchone()[0]
        units = connection.execute(
            """SELECT COUNT(*) FROM dim_southern_geography_unit u
               JOIN dim_southern_geography_layer l USING(geography_layer_id)
               WHERE l.source_file_id IN (SELECT source_file_id FROM source_southern_context_file)"""
        ).fetchone()[0]
        links = connection.execute(
            """SELECT COUNT(*) FROM bridge_southern_result_geography b
               JOIN source_southern_presidential_geography_result r USING(result_observation_id)
               WHERE r.source_file_id IN (SELECT source_file_id FROM source_southern_context_file)"""
        ).fetchone()[0]
        bad_math = connection.execute(
            """SELECT COUNT(*) FROM source_southern_presidential_geography_result
               WHERE ABS(total_votes-(dem_votes+rep_votes+other_votes))>0.011"""
        ).fetchone()[0]
        assert results == 3_224_020
        assert layers == 90
        assert units == 7_520
        assert links == 0
        assert bad_math == 0


def test_virginia_discrepancy_remains_review_data() -> None:
    with sqlite3.connect(DB) as connection:
        status = connection.execute(
            """SELECT q.reconciliation_status,ROUND(q.vote_delta,0)
               FROM qa_southern_context_ingest q
               JOIN source_southern_context_file f USING(source_file_id)
               WHERE f.manifest_source_file_id='VAELECTIONS-2012-VA-PRESIDENT-PRECINCT'"""
        ).fetchone()
        review_rows = connection.execute(
            """SELECT COUNT(*) FROM source_southern_presidential_geography_result r
               JOIN source_southern_context_file f USING(source_file_id)
               WHERE f.manifest_source_file_id='VAELECTIONS-2012-VA-PRESIDENT-PRECINCT'
                 AND r.validation_status='review'"""
        ).fetchone()[0]
        assert status == ("review", 6837.0)
        assert review_rows == 2723
