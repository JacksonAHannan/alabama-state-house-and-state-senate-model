import csv
import io
import sqlite3
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from load_southern_election_warehouse import (
    SCHEMA, candidate_and_party, classify_office, combine_results, result_validation_status,
    parse_arkansas_pipe_zip, parse_florida_zip, parse_louisiana_csv, parse_north_carolina_zip,
)
from warehouse import initialize


def meta(state: str, year: int, path: Path, **extra) -> dict:
    return {"state": state, "election_year": str(year), "local_path": path.as_posix(), **extra}


def test_office_party_and_district_normalization_are_conservative():
    assert classify_office("State House of Representatives District 07 (Vote For 1)") == ("SLDL", "lower", "7")
    assert classify_office("Member House of Delegates", "003") == ("SLDL", "lower", "3")
    assert classify_office("Tennessee House District 38", "38.0") == ("SLDL", "lower", "38")
    assert classify_office("NC House of Representatives District 6", "Not Found") == ("SLDL", "lower", "6")
    assert classify_office("State Senator 32") == ("SLDU", "upper", "32")
    assert classify_office("State Representative -- 72nd Representative District") == ("SLDL", "lower", "72")
    assert classify_office("NC HOUSE (24)") == ("SLDL", "lower", "24")
    assert classify_office("KY REPRESENTATIVE 100TH DI") == ("SLDL", "lower", "100")
    assert classify_office("U.S. Senate") == ("USS", None, None)
    assert candidate_and_party('Gilbert "Gibby" Andry (DEM)') == ('GILBERT "GIBBY" ANDRY', "DEM")


def test_louisiana_wide_file_keeps_round_separate_and_reconciles(tmp_path):
    path = tmp_path / "ByPrecinct_1.csv"
    pd.DataFrame([
        ["State Senator -- 1st Senatorial District", "A", "1", "1", 3, 4],
        ["State Senator -- 1st Senatorial District", "A", "1", "2", 5, 6],
    ], columns=["Office", "Parish", "Ward", "Precinct", "Alice (DEM)", "Bob (REP)"]).to_csv(path, index=False)
    rows, audit = parse_louisiana_csv(path, meta("LA", 2023, path, election_date="20231014", election_stage="first_round"))
    assert {(row["candidate_name"], row["party_family"], row["votes"]) for row in rows} == {
        ("ALICE", "democratic", 8), ("BOB", "republican", 10)}
    assert {row["election_stage"] for row in rows} == {"general"}
    assert audit["reconciliation_status"] == "exact"


def test_florida_zip_ignores_non_result_members_and_strips_nuls(tmp_path):
    path = tmp_path / "precinctlevelelectionresults2016gen.zip"
    fields = ["ALA", "Alachua", "1", "11/08/2016", "General Election", "01", "Precinct", "1",
              "0", "0", "0", "State Representative", "District 1", "100", "Alice", "DEM", "0", "1", "12"]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ALA_results.txt", ("\t".join(fields) + "\x00\n").encode())
        archive.writestr("data_definition.doc", b"\x00\x01not election rows")
    rows, audit = parse_florida_zip(path, meta("FL", 2016, path))
    assert len(rows) == 1 and rows[0]["votes"] == 12 and rows[0]["district"] == "1"
    assert audit["vote_delta"] == 0


def test_arkansas_pipe_zip_sums_precinct_columns_once(tmp_path):
    path = tmp_path / "general2000p.zip"
    content = ("County\nOffice|Candidate|Party|Precinct 1|Precinct 2|\n"
               "State Representative District 099|Alice|Democrat|3|4|\n")
    with zipfile.ZipFile(path, "w") as archive: archive.writestr("county.txt", content)
    rows, audit = parse_arkansas_pipe_zip(path, meta("AR", 2000, path))
    assert len(rows) == 1 and rows[0]["votes"] == 7 and rows[0]["district"] == "99"
    assert audit["reconciliation_status"] == "exact"


def test_north_carolina_adapter_supports_modern_named_columns(tmp_path):
    path = tmp_path / "results_pct_20161108.zip"
    content = ("County\tElection Date\tPrecinct\tContest Group ID\tContest Type\tContest Name\tChoice\tChoice Party\tVote For\tElection Day\tOne Stop\tAbsentee by Mail\tProvisional\tTotal Votes\n"
               "ALAMANCE\t11/08/2016\t05\t1385\tS\tNC HOUSE OF REPRESENTATIVES DISTRICT 6\tAlice\tDEM\t1\t7\t3\t1\t0\t11\x00\n")
    with zipfile.ZipFile(path, "w") as archive: archive.writestr("results.txt", content.encode())
    rows, audit = parse_north_carolina_zip(path, meta("NC", 2016, path))
    assert len(rows) == 1
    assert (rows[0]["office_code"], rows[0]["district"], rows[0]["votes"]) == ("SLDL", "6", 11)
    assert audit["reconciliation_status"] == "exact"


def test_north_carolina_adapter_supports_legacy_headerless_rows(tmp_path):
    path = tmp_path / "results_pct_20001107.zip"
    content = "ALAMANCE\t11/07/2000\t01\tPATTERSON\tNC HOUSE OF REPRESENTATIVES DISTRICT 6\tAlice\tDEM\t11\t2000-11-08\n"
    with zipfile.ZipFile(path, "w") as archive: archive.writestr("results.txt", content)
    rows, audit = parse_north_carolina_zip(path, meta("NC", 2000, path))
    assert len(rows) == 1 and rows[0]["votes"] == 11
    assert rows[0]["election_stage"] == "general"
    assert audit["reconciliation_status"] == "exact"


def test_display_district_variants_collapse_to_one_candidate_election():
    base = {"state_code": "VA", "cycle": 2015, "election_date": "2015-11-03",
            "election_date_status": "observed", "election_stage": "general",
            "election_stage_original": "General", "office_code": "SLDL", "office_original": "House of Delegates",
            "chamber": "lower", "candidate_name": "ALICE", "candidate_original": "Alice",
            "party_family": "democratic", "party_original": "Democratic", "votes": 5,
            "reported_geography_count": 1, "source_coverage": "official_precinct_aggregate"}
    rows = combine_results([
        {**base, "district": "3", "district_original": "03", "source_path": "a.csv"},
        {**base, "district": "3", "district_original": "3", "source_path": "b.csv"},
    ])
    assert len(rows) == 1 and rows[0]["votes"] == 10
    assert rows[0]["district_original"] == "03|3"


def test_missing_or_out_of_range_legislative_districts_enter_review():
    base = {"state_code": "NC", "office_code": "SLDL"}
    assert result_validation_status({**base, "district": None}) == "review"
    assert result_validation_status({**base, "district": "121"}) == "review"
    assert result_validation_status({**base, "district": "120"}) == "passed"


def test_schema_enforces_candidate_election_contract(tmp_path):
    connection = sqlite3.connect(tmp_path / "warehouse.sqlite")
    initialize(connection)
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    assert connection.execute("select max(version) from warehouse_schema_version").fetchone()[0] == 10
    assert connection.execute("select type from sqlite_master where name='fact_southern_candidate_election'").fetchone()[0] == "view"
