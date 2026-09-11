from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "load_southern_finance_warehouse.py"
SCRIPT_DIR = str(SCRIPT.parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
SPEC = importlib.util.spec_from_file_location("southern_finance_warehouse", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def finance_row(name: str, party: str, identifier: str) -> dict:
    return {
        "finance_candidate_cycle_id": identifier,
        "state_code": "VA", "cycle": 2024, "chamber": "lower", "district": "1",
        "party_family": party, "candidate_name": name.upper(),
        "candidate_name_original": name, "total_fundraising": 100.0,
        "finance_observed": 1, "finance_observation_status": "observed_positive",
    }


def test_incumbency_is_positive_support_for_a_scoped_name_match() -> None:
    finance = [finance_row("Doe, Jane", "democratic", "FIN-D")]
    candidates = pd.DataFrame([{
        "candidate_result_id": "CAND-D", "state_code": "VA", "cycle": 2024,
        "chamber": "lower", "district": "1", "party_family": "democratic",
        "candidate_name": "JANE DOE",
    }])
    incumbency = [{
        "incumbency_evidence_id": "INC-1", "state_code": "VA", "cycle": 2024,
        "chamber": "lower", "district": "1", "incumbent_name": "Jane Doe",
        "incumbent_ran": 1,
    }]
    matches = MOD.match_finance_candidates(finance, candidates, incumbency)
    assert len(matches) == 1
    assert matches[0]["review_status"] == "accepted"
    assert matches[0]["incumbency_support"] == 1
    assert matches[0]["incumbency_evidence_id"] == "INC-1"


def test_supplied_incumbency_workbook_is_currently_2026_only() -> None:
    rows = MOD.incumbency_records(MOD.INCUMBENCY, "RUN-TEST", "SRC-TEST")
    assert len(rows) == 140
    assert {row["cycle"] for row in rows} == {2026}
    assert not any(2016 <= row["cycle"] <= 2024 for row in rows)


def test_generated_incumbency_preserves_florida_2020_sd20_vacancy() -> None:
    rows = MOD.generated_incumbency_records(
        MOD.GENERATED_INCUMBENCY, "RUN-TEST", "SRC-GENERATED"
    )
    match = [
        row for row in rows
        if (row["state_code"], row["cycle"], row["chamber"], row["district"])
        == ("FL", 2020, "upper", "20")
    ]
    assert len(match) == 1
    assert match[0]["incumbent_name"] == "Tom Lee"
    assert match[0]["incumbent_ran"] == 0
    assert match[0]["open_seat"] == 1


def test_loader_builds_candidate_and_complete_race_marts(tmp_path: Path) -> None:
    database = tmp_path / "finance.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript((SCRIPT.parent / "warehouse_schema.sql").read_text(encoding="utf-8"))
        connection.executescript("""
          CREATE TABLE canonical_southern_legislative_candidate_election (
            candidate_result_id TEXT PRIMARY KEY,
            state_code TEXT NOT NULL,
            cycle INTEGER NOT NULL,
            chamber TEXT NOT NULL,
            district TEXT NOT NULL,
            candidate_name TEXT NOT NULL,
            party_family TEXT NOT NULL
          );
          INSERT INTO canonical_southern_legislative_candidate_election VALUES
            ('CAND-D','VA',2024,'lower','1','JANE DOE','democratic'),
            ('CAND-R','VA',2024,'lower','1','JOHN ROE','republican');
          CREATE VIEW fact_southern_legislative_final_candidate_election AS
            SELECT * FROM canonical_southern_legislative_candidate_election;
        """)
    finance_path = tmp_path / "finance.csv"
    pd.DataFrame([
        {
            "state": "VA", "cycle": 2024, "chamber": "house", "district": 1,
            "party": "D", "candidate": "Doe, Jane", "provider_candidate": "Jane Doe",
            "committee_id": "D1", "total_fundraising": 1000.0,
            "cash_contributions": 900.0, "other_receipts": 100.0,
            "in_kind_contributions": 50.0, "loans_received": 25.0,
            "expenditures": 700.0, "ending_cash": 300.0, "report_count": 2,
            "period_start": "2023-01-01", "period_end": "2024-12-31",
            "finance_observation_status": "observed_positive",
            "aggregation_status": "fixture", "source_name": "fixture",
            "source_measure": "cash_plus_other", "source_path": "",
            "source_reported_total": 1000.0, "data_run_id": "UPSTREAM",
            "generated_at_utc": "2026-08-30T00:00:00+00:00",
            "build_code_sha256": "a" * 64, "build_config_id": "fixture",
        },
        {
            "state": "VA", "cycle": 2024, "chamber": "house", "district": 1,
            "party": "R", "candidate": "Roe, John", "provider_candidate": "John Roe",
            "committee_id": "R1", "total_fundraising": 2000.0,
            "cash_contributions": 2000.0, "other_receipts": 0.0,
            "in_kind_contributions": 0.0, "loans_received": 0.0,
            "expenditures": 1500.0, "ending_cash": 500.0, "report_count": 2,
            "period_start": "2023-01-01", "period_end": "2024-12-31",
            "finance_observation_status": "observed_positive",
            "aggregation_status": "fixture", "source_name": "fixture",
            "source_measure": "cash_plus_other", "source_path": "",
            "source_reported_total": 2000.0, "data_run_id": "UPSTREAM",
            "generated_at_utc": "2026-08-30T00:00:00+00:00",
            "build_code_sha256": "a" * 64, "build_config_id": "fixture",
        },
    ]).to_csv(finance_path, index=False)
    incumbency_path = tmp_path / "incumbency.xlsx"
    pd.DataFrame([{
        "Year": 2024, "State": "VA", "Chamber": "House", "District": 1,
        "Incumbent": "Jane Doe", "Party": "D", "Incumbent_Ran": "Yes",
        "Open_Seat": "No", "Election_Status": "Complete", "Won_General": "Yes",
        "Method": "fixture", "Roster_Source_URL": "https://example.test/roster",
        "Ballotpedia_URL": "https://example.test/ballotpedia",
        "Wikipedia_URL": "https://example.test/wikipedia",
        "Coverage_Status": "Populated", "Notes": "fixture",
    }]).to_excel(incumbency_path, sheet_name="Incumbents", index=False)

    result = MOD.build(
        database, finance_path=finance_path, incumbency_path=incumbency_path,
        manifest_paths=[], export=False,
    )
    assert result["validation"]["candidate_mart_rows"] == 2
    assert result["validation"]["finance_complete_races"] == 1
    assert result["validation"]["incumbency_supported_matches"] == 1
    with sqlite3.connect(database) as connection:
        race = connection.execute(
            "SELECT finance_complete,log_fundraising_ratio_d_to_r "
            "FROM mart_southern_race_finance"
        ).fetchone()
        assert race[0] == 1
        assert race[1] is not None
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
