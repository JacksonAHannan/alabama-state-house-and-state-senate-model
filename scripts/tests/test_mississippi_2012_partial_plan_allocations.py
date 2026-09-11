from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from audit_mississippi_2012_precinct_plan_readiness import (
    abbreviation_aliases,
    normalize,
    result_prefix_code,
    validate_alias_source,
)


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data/processed/elections/alabama_elections.sqlite"
OUTPUT = ROOT / "data/processed/presidential/mississippi_2012_partial_plan_allocations"


def test_name_normalization_and_alias_source_are_deterministic() -> None:
    assert normalize("Mt. Olive Comm. Ctr.") == "MOUNT OLIVE COMMUNITY CENTER"
    assert result_prefix_code("(0042) - Courthouse") == "42"
    assert {"PN"}.issubset(abbreviation_aliases("Pinehaven"))
    source = validate_alias_source()
    assert source["state_code"] == "MS"
    assert source["cycle"] == "2019"
    assert source["sha256"] == "b43a1ba41c75e584a2e22fb9f34597b9e2929d373a61d975719088c9d569acc9"


def test_partial_allocation_keeps_ambiguous_districts_out_of_fact_view() -> None:
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == 2
    assert manifest["alias_source_file_id"] == "RDH-VEST-2019-MS-PRECINCT"
    validation = manifest["validation"]
    assert validation["result_rows"] == 1_867
    assert validation["matched_rows"] == 1_733
    assert validation["unresolved_rows"] == 134
    assert validation["district_rows"] == 174
    assert validation["passed_districts"] == 68
    assert validation["review_districts"] == 106

    with sqlite3.connect(DB) as connection:
        latest = connection.execute(
            """SELECT build_run_id,status FROM warehouse_build_run
               WHERE target='mississippi_2012_partial_plan_allocations'
               ORDER BY started_at_utc DESC LIMIT 1"""
        ).fetchone()
        assert latest == (manifest["build_run_id"], "validated")
        readiness = pd.read_sql_query(
            """SELECT chamber,district,ambiguous_result_rows,ambiguous_two_party_votes,
                      validation_status
               FROM qa_southern_presidential_district_readiness
               WHERE state_code='MS' AND election_cycle=2012 AND plan_cycle=2019""",
            connection,
        )
        mart = pd.read_sql_query(
            """SELECT chamber,district,dem_votes,rep_votes,two_party_dem_margin,allocation_status
               FROM mart_southern_presidential_district_result
               WHERE state_code='MS' AND election_cycle=2012 AND plan_cycle=2019""",
            connection,
        )
        fact = pd.read_sql_query(
            """SELECT chamber,district FROM fact_southern_presidential_district_result
               WHERE state_code='MS' AND election_cycle=2012 AND plan_cycle=2019""",
            connection,
        )

    assert len(readiness) == 174
    assert len(mart) == 174
    assert len(fact) == 68
    assert readiness[readiness.validation_status.eq("passed")].ambiguous_result_rows.eq(0).all()
    assert readiness[readiness.validation_status.eq("review")].ambiguous_result_rows.gt(0).all()
    passed_keys = set(map(tuple, fact[["chamber", "district"]].astype(str).to_numpy()))
    expected_keys = set(map(tuple, readiness.loc[
        readiness.validation_status.eq("passed"), ["chamber", "district"]
    ].astype(str).to_numpy()))
    assert passed_keys == expected_keys
    expected_margin = (mart.dem_votes - mart.rep_votes) / (mart.dem_votes + mart.rep_votes)
    assert (mart.two_party_dem_margin - expected_margin).abs().max() < 1e-12


def test_only_nine_observed_2019_races_pass_the_district_gate() -> None:
    with sqlite3.connect(DB) as connection:
        rows = pd.read_sql_query(
            """SELECT r.chamber,r.district,d.validation_status
               FROM mart_southern_war_training_no_finance r
               JOIN qa_southern_presidential_district_readiness d
                 ON d.state_code=r.state_code AND d.plan_cycle=r.cycle
                AND d.chamber=r.chamber AND d.district=r.district
               WHERE r.state_code='MS' AND r.cycle=2019
                 AND r.training_status='strict_war_ready_no_finance'""",
            connection,
        )
    assert len(rows) == 40
    passed = rows[rows.validation_status.eq("passed")]
    assert set(map(tuple, passed[["chamber", "district"]].astype(str).to_numpy())) == {
        ("lower", "3"), ("lower", "12"), ("lower", "17"), ("lower", "68"),
        ("lower", "74"), ("upper", "5"), ("upper", "10"), ("upper", "13"),
        ("upper", "31"),
    }
    blocked = pd.read_csv(OUTPUT / "war_blocked_races.csv", dtype={"district": str})
    assert len(blocked) == 31
    assert blocked.war_outcome_id.is_unique
    assert blocked.validation_status.eq("review").all()
    assert blocked.ambiguous_result_rows.gt(0).all()
    assert blocked.resolution_needed.str.contains("official precinct identity evidence").all()
