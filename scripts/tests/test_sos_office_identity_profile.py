"""Office-label profile must not widen precinct identity or geography scope."""
import pandas as pd
import json
import sqlite3
import pytest

from scripts import stage_precinct_identity_repair as staging
from scripts import apply_precinct_identity_repair as repair
from scripts.build_precinct_identity import build_nodes, match_sources
from scripts.build_precinct_geography_links import match as match_geography
from scripts.tests.test_apply_precinct_identity_repair import snapshot


def test_explicit_office_profile_selects_only_two_sos_cohorts():
    rows = pd.DataFrame({"year": [2010, 2012, 1994, 2010, 2012],
                         "county_key": ["GENEVA", "MORGAN", "MORGAN", "GENEVA", "OTHER"],
                         "source": ["alabama_sos", "alabama_sos", "alabama_sos", "openelections", "alabama_sos"]})
    assert staging.repair_scope(rows, profile="sos-office-labels").tolist() == [True, True, False, False, False]


@pytest.fixture
def office_database(tmp_path):
    rows = []
    for year, county, source in [(2010, "GENEVA", "alabama_sos"), (2012, "MORGAN", "alabama_sos"),
                                  (2012, "MORGAN", "openelections"), (2014, "OTHER", "alabama_sos")]:
        for precinct in ["001 A", "002 B"]:
            for office, votes in [("President", 100), ("OLD FEDERAL LABEL", 50)]:
                rows.append([year, source, county, precinct, office, votes])
    votes = pd.DataFrame(rows, columns=staging.KEYS + ["office", "votes"])
    nodes, fingerprints = build_nodes(votes)
    candidates, links = match_sources(nodes, fingerprints, "alabama_sos", "openelections")
    links["accepted"] = 0
    links["relationship"] = "unresolved"
    geneva = nodes[nodes.year.eq(2010)].copy()
    geo = geneva[["node_id", "year", "county_key", "name_norm", "precinct_code"]].rename(columns={"node_id": "geo_node_id", "year": "cycle"})
    geo["vtd"] = ["000001", "000002"]
    geo["geography_name"] = ["A", "B"]
    geo["geography_source"] = "fixture"
    geo_fp = pd.DataFrame({"geo_node_id": geo.geo_node_id, "office": "President", "votes": 100})
    geo_candidates, geo_links = match_geography(nodes, fingerprints, geo, geo_fp)
    direct = geo_links[geo_links.accepted.eq(1)].merge(geo[["geo_node_id", "vtd"]], on="geo_node_id")[["source_node_id", "vtd"]].assign(evidence="direct_geography")
    database = tmp_path / "warehouse.sqlite"
    with sqlite3.connect(database) as connection:
        tables = dict(zip(repair.IDENTITY, [nodes, fingerprints, candidates, links]))
        tables.update(vote_observations=votes, geographic_precinct_nodes=geo, geographic_vote_fingerprints=geo_fp,
                      precinct_geography_match_candidates=geo_candidates, precinct_geography_links=geo_links,
                      canonical_geography_evidence=direct, canonical_precinct_geography_links=direct,
                      precinct_geography_conflicts=direct.iloc[:0], unrelated=pd.DataFrame({"value": ["preserve"]}))
        for table, frame in tables.items(): frame.to_sql(table, connection, index=False)
        connection.execute('CREATE TABLE warehouse_build_run(build_run_id TEXT PRIMARY KEY,target TEXT,started_at_utc TEXT,completed_at_utc TEXT,status TEXT,code_commit TEXT,configuration_json TEXT,validation_json TEXT)')
        connection.execute("INSERT INTO warehouse_build_run VALUES ('RUN-OFFICE','source','time','time','validated','test','{}','{}')")
        connection.execute('CREATE TABLE qa_warehouse_source_repair(issue_id TEXT PRIMARY KEY,build_run_id TEXT,warehouse_object TEXT,scope TEXT,status TEXT,evidence_json TEXT,recorded_at_utc TEXT)')
        connection.execute("UPDATE vote_observations SET office='U.S. House' WHERE source='alabama_sos' AND office='OLD FEDERAL LABEL' AND year IN (2010,2012)")
        connection.execute("UPDATE vote_observations SET office='Public Service Commission President' WHERE source='alabama_sos' AND office='President' AND year=2012")
    return database


def staged(database, directory):
    report = staging.stage(database, directory, profile=staging.OFFICE_PROFILE, expected_run="RUN-OFFICE")
    return report, repair.file_sha256(directory / "manifest.json")


def test_office_profile_stage_and_apply_preserve_identity_geography_sources(office_database, tmp_path):
    before = snapshot(office_database)
    directory = tmp_path / "stage"
    report, accepted = staged(office_database, directory)
    assert snapshot(office_database) == before
    assert report["profile"] == staging.OFFICE_PROFILE and report["warehouse_latest_run"] == "RUN-OFFICE"
    assert report["validation"]["new_ids"] == report["validation"]["retired_ids"] == []
    result = repair.apply(office_database, directory, tmp_path / "backup.sqlite", accepted, expected_run="RUN-OFFICE")
    after = snapshot(office_database)
    assert result["exports_status"] == "complete"
    for table in ["vote_observations", "geographic_precinct_nodes", "geographic_vote_fingerprints", "unrelated", *repair.GEOGRAPHY]:
        assert after[table] == before[table]
    assert sorted(after["precinct_nodes"]) == sorted(before["precinct_nodes"])
    assert len(result["validation"]["geography"]["surviving_2010_name_code_parity_proven"]) == 2
    assert result["validation"]["geography"]["revoked_source_transfer_ids"] == []
    with sqlite3.connect(office_database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM precinct_source_links WHERE accepted=1").fetchone() == (0,)


def test_office_stage_requires_current_run_before_writing(office_database, tmp_path):
    for expected in [None, "WRONG"]:
        with pytest.raises(ValueError, match="expected run|run changed"):
            staging.stage(office_database, tmp_path / "not-created", profile=staging.OFFICE_PROFILE, expected_run=expected)
    assert not (tmp_path / "not-created").exists()


@pytest.mark.parametrize("mutation", ["run", "profile", "requested_run", "source", "geography", "canonical", "metadata"])
def test_apply_rejects_unproven_profile_drift(office_database, tmp_path, mutation):
    directory = tmp_path / "stage"
    _, accepted = staged(office_database, directory)
    requested = "RUN-OFFICE"
    if mutation == "requested_run": requested = "WRONG"
    if mutation == "profile":
        path = directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["profile"] = staging.DEFAULT_PROFILE
        path.write_text(json.dumps(manifest))
        accepted = repair.file_sha256(path)
    with sqlite3.connect(office_database) as connection:
        if mutation == "run": connection.execute("UPDATE warehouse_build_run SET build_run_id='NEW-RUN'")
        if mutation == "source": connection.execute("UPDATE vote_observations SET votes=votes+1 WHERE year=2010")
        if mutation == "geography": connection.execute("UPDATE precinct_geography_links SET accepted=0")
        if mutation == "canonical": connection.execute("UPDATE canonical_geography_evidence SET evidence='source_transfer'")
        if mutation == "metadata": connection.execute("UPDATE precinct_nodes SET name_norm='CHANGED' WHERE year=2010")
    before = snapshot(office_database)
    with pytest.raises((ValueError, AssertionError)):
        repair.apply(office_database, directory, tmp_path / "backup.sqlite", accepted, expected_run=requested)
    assert snapshot(office_database) == before and not (tmp_path / "backup.sqlite").exists()


def test_new_profile_cannot_create_or_retire_ids(office_database, tmp_path):
    with sqlite3.connect(office_database) as connection:
        connection.execute("UPDATE vote_observations SET precinct_key='NEW NAME' WHERE year=2010 AND precinct_key='001 A'")
    with pytest.raises(ValueError, match="preserve every existing node"):
        staged(office_database, tmp_path / "not-created")


def test_profile_apply_failure_rolls_back(office_database, tmp_path, monkeypatch):
    directory = tmp_path / "stage"
    _, accepted = staged(office_database, directory)
    before = snapshot(office_database)
    def fail(*args): raise ValueError("injected office-profile validation failure")
    monkeypatch.setattr(repair, "validate", fail)
    with pytest.raises(ValueError, match="injected office-profile"):
        repair.apply(office_database, directory, tmp_path / "backup.sqlite", accepted, expected_run="RUN-OFFICE")
    assert snapshot(office_database) == before
    assert snapshot(tmp_path / "backup.sqlite") == before


def test_default_scope_and_legacy_query_are_unchanged():
    assert staging.source_query() == staging.VOTE_QUERY
    example = pd.DataFrame({"year": [1994, 2002, 2014, 2010, 2012],
                            "county_key": ["ANY", "MARSHALL", "JEFFERSON", "GENEVA", "MORGAN"], "source": "alabama_sos"})
    assert staging.repair_scope(example).tolist() == [True, True, True, False, False]
    with pytest.raises(ValueError, match="Unknown precinct"):
        staging.source_query("unknown")
