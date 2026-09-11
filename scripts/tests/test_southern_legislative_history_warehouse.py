import sqlite3
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from load_southern_legislative_history_warehouse import (
    SCHEMA,
    finalize_candidates,
    parse_medsl,
    parse_ms_2023,
    scheduled_post2016_keys,
)
from load_southern_election_warehouse import SCHEMA as OFFICIAL_SCHEMA
from warehouse import initialize


def test_medsl_total_mode_precedence_and_vote_reconciliation(tmp_path):
    path = tmp_path / "fixture.zip"
    frame = pd.DataFrame([
        ["P1", "STATE HOUSE", "DEMOCRATIC", "DEMOCRAT", "TOTAL", 10, "A", "01001", "Alice", "1", 2024, "GEN", False, False, "AL", "2024-11-05"],
        ["P1", "STATE HOUSE", "DEMOCRATIC", "DEMOCRAT", "ABSENTEE", 3, "A", "01001", "Alice", "1", 2024, "GEN", False, False, "AL", "2024-11-05"],
        ["P1", "STATE HOUSE", "REPUBLICAN", "REPUBLICAN", "ELECTION DAY", 5, "A", "01001", "Bob", "1", 2024, "GEN", False, False, "AL", "2024-11-05"],
        ["P1", "STATE HOUSE", "REPUBLICAN", "REPUBLICAN", "ABSENTEE", 2, "A", "01001", "Bob", "1", 2024, "GEN", False, False, "AL", "2024-11-05"],
    ], columns=["precinct", "office", "party_detailed", "party_simplified", "mode", "votes",
                "county_name", "county_fips", "candidate", "district", "year", "stage", "special",
                "writein", "state_po", "date"])
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("al24.csv", frame.to_csv(index=False))
    meta = {"path": path, "provider": "MEDSL", "source_family": "medsl_github", "state": "AL", "year": 2024}
    sets, candidates, audits = parse_medsl(meta, "SRC-FIXTURE", "RUN-FIXTURE")
    assert len(sets) == 1
    assert {(row["candidate_name"], row["votes"]) for row in candidates} == {("ALICE", 10), ("BOB", 7)}
    assert audits[0]["vote_delta"] == 0
    assert audits[0]["reconciliation_status"] == "exact"


def test_mississippi_readme_columns_form_one_contest_set(tmp_path):
    path = tmp_path / "ms.zip"
    frame = pd.DataFrame({"UNIQUE_ID": ["A", "B"], "GSL001DALI": [3, 4], "GSL001RBOB": [5, 6]})
    readme = "\n".join([
        "GSL001DALI Alice Adams-:-DEM-:-State House-1",
        "GSL001RBOB Bob Baker-:-REP-:-State House-1",
    ])
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ms_gen_2023_prec.csv", frame.to_csv(index=False))
        archive.writestr("README.txt", readme)
    meta = {"path": path, "provider": "RDH", "source_family": "rdh_official_derivative"}
    sets, candidates, audits = parse_ms_2023(meta, "SRC-FIXTURE", "RUN-FIXTURE")
    assert len(sets) == 1
    assert {(row["candidate_name"], row["votes"]) for row in candidates} == {
        ("ALICE ADAMS", 7), ("BOB BAKER", 11)
    }
    assert audits[0]["vote_delta"] == 0


def test_canonical_name_collisions_collapse_without_losing_votes():
    sets = [{"observation_set_id": "SET-1"}]
    candidates = [
        {"observation_set_id": "SET-1", "candidate_source_id": "1", "candidate_name": "ALICE A",
         "candidate_name_original": "Alice A.", "party_family": "democratic", "party_original": "DEM",
         "votes": 3, "vote_value_status": "observed", "writein_status": "false",
         "incumbent_status": None, "winner_status": None, "validation_status": "passed"},
        {"observation_set_id": "SET-1", "candidate_source_id": "2", "candidate_name": "ALICE A",
         "candidate_name_original": "ALICE A", "party_family": "democratic", "party_original": "DEM",
         "votes": 4, "vote_value_status": "observed", "writein_status": "false",
         "incumbent_status": None, "winner_status": None, "validation_status": "passed"},
    ]
    finalize_candidates(sets, candidates)
    assert len(candidates) == 1
    assert candidates[0]["votes"] == 7
    assert candidates[0]["candidate_name_original"] == "ALICE A|Alice A."


def test_post2016_schedule_has_every_expected_state_chamber():
    keys = scheduled_post2016_keys()
    assert len(keys) == 95
    assert ("VA", 2023, "upper") in keys
    assert ("SC", 2022, "upper") not in keys
    assert ("AL", 2024, "lower") not in keys


def test_schema_installs_provider_specific_history_tables(tmp_path):
    connection = sqlite3.connect(tmp_path / "warehouse.sqlite")
    initialize(connection)
    connection.executescript(OFFICIAL_SCHEMA.read_text(encoding="utf-8"))
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    assert connection.execute("SELECT MAX(version) FROM warehouse_schema_version").fetchone()[0] == 13
    assert connection.execute(
        "SELECT type FROM sqlite_master WHERE name='fact_southern_legislative_candidate_election'"
    ).fetchone()[0] == "view"
    assert connection.execute(
        "SELECT type FROM sqlite_master WHERE name='fact_southern_legislative_final_candidate_election'"
    ).fetchone()[0] == "view"
    assert connection.execute(
        "SELECT type FROM sqlite_master WHERE name='qa_southern_legislative_final_competition_coverage'"
    ).fetchone()[0] == "view"


def test_final_stage_view_uses_louisiana_runoff_only_when_present(tmp_path):
    connection = sqlite3.connect(tmp_path / "warehouse.sqlite")
    initialize(connection)
    connection.executescript(OFFICIAL_SCHEMA.read_text(encoding="utf-8"))
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    columns = [
        row[1] for row in connection.execute(
            "PRAGMA table_info(canonical_southern_legislative_candidate_election)"
        )
    ]

    def add(contest, state, district, stage, date, candidate, party, votes):
        row = {
            "candidate_result_id": f"{contest}-{party}",
            "observation_set_id": contest,
            "contract_version": 2,
            "build_run_id": "TEST-RUN",
            "state_code": state,
            "cycle": 2023,
            "election_date": date,
            "election_date_status": "observed",
            "election_stage": stage,
            "election_stage_original": stage,
            "office_code": "SLDL",
            "chamber": "lower",
            "district_plan_id": f"{state}-2023-lower-test",
            "geography_vintage": "test",
            "district": str(district),
            "candidate_name": candidate,
            "candidate_name_original": candidate,
            "party_family": party,
            "party_original": party,
            "votes": votes,
            "vote_share": 0.5,
            "vote_value_status": "observed",
            "contest_status": "unknown",
            "source_provider": "fixture",
            "source_family": "official_state",
            "source_file_id": None,
            "authority_rank": 10,
            "validation_status": "passed",
            "as_of_utc": "2023-11-18T00:00:00Z",
        }
        connection.execute(
            f"INSERT INTO canonical_southern_legislative_candidate_election "
            f"({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            tuple(row[column] for column in columns),
        )

    for party, candidate in [("democratic", "FIRST D"), ("republican", "FIRST R")]:
        add("LA-D1-FIRST", "LA", 1, "general", "2023-10-14", candidate, party, 10)
    for party, candidate in [("democratic", "RUNOFF D"), ("republican", "RUNOFF R")]:
        add("LA-D1-RUNOFF", "LA", 1, "other", "2023-11-18", candidate, party, 10)
    for party, candidate in [("democratic", "SETTLED D"), ("republican", "SETTLED R")]:
        add("LA-D2-FIRST", "LA", 2, "general", "2023-10-14", candidate, party, 10)
    for party, candidate in [("democratic", "GEORGIA D"), ("republican", "GEORGIA R")]:
        add("GA-D1-GENERAL", "GA", 1, "general", "2023-11-07", candidate, party, 10)

    selected = connection.execute(
        "SELECT state_code,district,election_stage,candidate_name "
        "FROM fact_southern_legislative_final_candidate_election "
        "ORDER BY state_code,district,candidate_name"
    ).fetchall()
    assert ("LA", "1", "general", "FIRST D") not in selected
    assert ("LA", "1", "other", "RUNOFF D") in selected
    assert ("LA", "2", "general", "SETTLED D") in selected
    coverage = connection.execute(
        "SELECT final_contests,louisiana_first_round_final_contests,"
        "louisiana_runoff_final_contests,war_eligible_dr_contests "
        "FROM qa_southern_legislative_final_competition_coverage "
        "WHERE state_code='LA'"
    ).fetchone()
    assert coverage == (2, 1, 1, 2)
