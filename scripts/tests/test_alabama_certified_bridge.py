"""Alabama canonical/certified bridge and guarded total repair on isolated fixtures."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

import alabama_certified_bridge as bridge
import load_southern_legislative_history_warehouse as history
import repair_alabama_canonical_certified_totals as repair
from warehouse import file_sha256, initialize

DECODER = {"GSL001DABC": "Alice Abc", "GSL001RXYZ": "Xavier Xyz"}
CANONICAL_TABLE = """
CREATE TABLE canonical_candidates("year" INTEGER, chamber TEXT, district INTEGER, canonical_party TEXT,
  canonical_votes REAL, canonical_name TEXT, canonical_source TEXT, person_id TEXT,
  canonical_candidate_id TEXT, incumbent INTEGER, winner INTEGER)"""
MATERIALIZED_TABLE = """
CREATE TABLE IF NOT EXISTS canonical_southern_legislative_candidate_election (
    candidate_result_id TEXT PRIMARY KEY, observation_set_id TEXT NOT NULL, contract_version INTEGER NOT NULL,
    build_run_id TEXT NOT NULL, state_code TEXT NOT NULL, cycle INTEGER NOT NULL, election_date TEXT,
    election_date_status TEXT NOT NULL, election_stage TEXT NOT NULL, election_stage_original TEXT NOT NULL,
    office_code TEXT NOT NULL, chamber TEXT NOT NULL, district_plan_id TEXT, geography_vintage TEXT NOT NULL,
    district TEXT NOT NULL, candidate_name TEXT NOT NULL, candidate_name_original TEXT, party_family TEXT NOT NULL,
    party_original TEXT, votes INTEGER, vote_share REAL, vote_value_status TEXT NOT NULL, contest_status TEXT NOT NULL,
    source_provider TEXT NOT NULL, source_family TEXT NOT NULL, source_file_id TEXT, authority_rank INTEGER NOT NULL,
    validation_status TEXT NOT NULL, as_of_utc TEXT NOT NULL)"""
LIVE_VIEW = """
CREATE VIEW all_southern_legislative_candidate_election_observations AS
SELECT canonical_candidate_id AS candidate_result_id, 'ALCANON-' || year || '-' || chamber || '-' || district AS observation_set_id,
       year AS cycle, canonical_votes AS votes,
       CASE WHEN SUM(canonical_votes) OVER (PARTITION BY year,chamber,district)>0
            THEN 1.0*canonical_votes/SUM(canonical_votes) OVER (PARTITION BY year,chamber,district) END AS vote_share,
       'alabama_canonical' AS source_family
FROM canonical_candidates"""


def canonical_row(year, chamber, district, party, votes, name, winner):
    return (year, chamber, district, party, float(votes), name, "official_consolidated_candidate_results",
            f"ALPERSON-{name.upper().replace(' ', '-')}", f"AL-{year}-{chamber}-{district}-{party}-{name.upper().replace(' ', '-')}",
            0, winner)


def certified_set(connection, set_id, source_id, cycle, chamber, district, rows):
    connection.execute("""INSERT INTO source_southern_legislative_observation_set VALUES
        (?, 'RUN-BEFORE', ?, NULL, 'alabama_sos', ?, 10, 'AL', ?, ?, 'observed', 'general', 'General Election',
         ?, ?, ?, 'reported', ?, ?, 'certified_all_candidate_and_write_in_totals', 'unknown',
         'fixture', '{}', 'review', 'fixture')""",
        (set_id, source_id, bridge.CERTIFIED_FAMILY, cycle, f"{cycle}-11-06", "SLDL" if chamber == "lower" else "SLDU",
         chamber, f"AL-{cycle}-{chamber}-reported-unknown-vintage", str(district), str(district)))
    for index, (name, family, original, votes, writein) in enumerate(rows):
        connection.execute("""INSERT INTO source_southern_legislative_candidate_result VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'observed', ?, NULL, NULL, 'passed', 'fixture')""",
            (f"{set_id}-CELL-{index}", set_id, json.dumps({"cell": index}), name, name, family, original, votes, writein))


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "ROOT", tmp_path)
    path = tmp_path / "warehouse.sqlite"
    (tmp_path / "canvass18.pdf").write_bytes(b"2018 canvass")
    (tmp_path / "canvass22.pdf").write_bytes(b"2022 canvass")
    with sqlite3.connect(path) as connection:
        initialize(connection)
        connection.executescript(history.SCHEMA.read_text(encoding="utf-8").split("DROP VIEW IF EXISTS")[0])
        connection.execute(MATERIALIZED_TABLE)
        connection.execute(CANONICAL_TABLE)
        connection.execute(LIVE_VIEW)
        connection.execute("""CREATE TABLE qa_warehouse_source_repair(issue_id TEXT PRIMARY KEY,
            build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id), warehouse_object TEXT NOT NULL,
            scope TEXT NOT NULL, status TEXT NOT NULL, evidence_json TEXT NOT NULL, recorded_at_utc TEXT NOT NULL)""")
        connection.execute("INSERT INTO warehouse_build_run VALUES ('RUN-BEFORE','fixture','2026-01-01','2026-01-01','validated','fixture','{}','{}')")
        for identifier, name in (("SRC-C18", "canvass18.pdf"), ("SRC-C22", "canvass22.pdf")):
            connection.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256) VALUES (?,'alabama_sos',?,?)",
                               (identifier, name, file_sha256(tmp_path / name)))
        # 2018 HD1: canonical D short by 3 votes (precinct blanks), R equal; canvass labels are surnames.
        # 2018 HD2: canvass mislabels the Republican; precinct alignment supplies exact-name evidence.
        # 2022 HD1: opaque ballot codes decoded through the README decoder; R equal, D short by 5.
        canonical = [
            canonical_row(2018, "house", 1, "D", 100, "Jane Smith", 0), canonical_row(2018, "house", 1, "R", 200, "Robert Jones II", 1),
            canonical_row(2018, "house", 2, "D", 300, "Ann Gray", 1), canonical_row(2018, "house", 2, "R", 120, "Michael Holden II", 0),
            canonical_row(2022, "house", 1, "D", 95, "GSL001DABC", 0), canonical_row(2022, "house", 1, "R", 150, "GSL001RXYZ", 1),
        ]
        connection.executemany("INSERT INTO canonical_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?)", canonical)
        for row in canonical:
            year, chamber, district, party, votes, name = row[:6]
            total = sum(r[4] for r in canonical if r[:3] == row[:3])
            connection.execute("""INSERT INTO canonical_southern_legislative_candidate_election VALUES
                (?, ?, 1, 'legacy', 'AL', ?, NULL, 'derived', 'general', 'general', 'SLDL', 'lower', NULL, 'unverified', ?, ?, ?,
                 ?, ?, ?, ?, 'observed', 'unknown', 'canonical', 'alabama_canonical', NULL, 5, 'passed', 'legacy')""",
                (row[8], f"ALCANON-{year}-{chamber}-{district}", year, str(district), name, name,
                 bridge.PARTY_FAMILY[party], party, int(votes), votes / total))
        certified_set(connection, "AL18SET-1", "SRC-C18", 2018, "lower", 1, [
            ("Smith", "democratic", "D", 103, "false"), ("Jones II", "republican", "R", 200, "false"),
            ("Free", "other", "L", 7, "false"), ("Write-In", "unknown", None, 4, "true")])
        certified_set(connection, "AL18SET-2", "SRC-C18", 2018, "lower", 2, [
            ("Gray", "democratic", "D", 300, "false"), ("Gray II", "republican", "R", 120, "false"),
            ("Write-In", "unknown", None, 2, "true")])
        certified_set(connection, "AL22SET-1", "SRC-C22", 2022, "lower", 1, [
            ("Alice Abc", "democratic", "D", 100, "false"), ("Xavier Xyz", "republican", "R", 150, "false"),
            ("Write-In", "unknown", None, 9, "true")])
        connection.execute("CREATE TABLE mart_southern_war_outcome(war_outcome_id TEXT, dem_votes INTEGER)")
        connection.execute("INSERT INTO mart_southern_war_outcome VALUES ('OUT-1', 100)")
        connection.execute("CREATE VIEW mart_southern_war_training_no_finance AS SELECT war_outcome_id, 'strict' AS training_status FROM mart_southern_war_outcome")
        connection.execute("CREATE VIEW mart_southern_war_training_with_finance AS SELECT war_outcome_id, 'strict' AS evaluation_status FROM mart_southern_war_outcome")
        connection.execute("CREATE TABLE unrelated_domain(value TEXT)")
        connection.execute("INSERT INTO unrelated_domain VALUES ('preserved')")
    return path


ALIGNMENT = {(2018, "lower", "2", "R", "Gray II"): "MICHAEL HOLDEN II"}


def staged(database):
    with sqlite3.connect(database) as connection:
        return repair.stage(connection, decoder=DECODER, precinct_alignment=ALIGNMENT)


def test_bridge_matches_every_canonical_candidate_with_explicit_evidence(database):
    result = staged(database)
    frame = result["bridge"].set_index("canonical_candidate_id")
    assert len(frame) == 6
    assert frame.loc["AL-2018-house-1-D-JANE-SMITH", "match_method"] == "surname_unique_race_party"
    assert frame.loc["AL-2018-house-1-R-ROBERT-JONES-II", "match_method"] == "surname_unique_race_party"
    assert frame.loc["AL-2018-house-2-R-MICHAEL-HOLDEN-II", "match_method"] == "precinct_workbook_exact_name_alignment_canvass_label_disagrees"
    assert frame.loc["AL-2022-house-1-D-GSL001DABC", "match_method"] == "decoded_ballot_code_exact_normalized_name"
    assert frame.loc["AL-2022-house-1-D-GSL001DABC", "decoded_canonical_name"] == "Alice Abc"
    assert frame.correction_status.value_counts().to_dict() == {"agrees": 4, "corrected_to_certified": 2}
    assert frame.loc["AL-2018-house-1-D-JANE-SMITH", ["canonical_votes_before", "certified_votes", "vote_delta"]].tolist() == [100, 103, 3]
    assert frame.review_status.eq("approved").all()
    assert set(frame.source_file_id) == {"SRC-C18", "SRC-C22"}
    assert result["affected_observation_sets"] == ["ALCANON-2018-house-1", "ALCANON-2022-house-1"]
    updates = {row["candidate_result_id"]: row for row in result["materialized_updates"]}
    assert updates["AL-2018-house-1-D-JANE-SMITH"]["votes"] == 103
    assert updates["AL-2018-house-1-R-ROBERT-JONES-II"]["vote_share"] == pytest.approx(200 / 303)


def test_bridge_ids_do_not_depend_on_row_order_or_run(database):
    with sqlite3.connect(database) as connection:
        canonical = bridge.canonical_rows(connection)
        certified = bridge.certified_rows(connection)
    first = bridge.build_bridge(canonical, certified, DECODER, ALIGNMENT, run_id="a", recorded_at="t1")
    second = bridge.build_bridge(canonical.sample(frac=1, random_state=3), certified.sample(frac=1, random_state=5), DECODER, ALIGNMENT, run_id="b", recorded_at="t2")
    assert set(first.bridge_id) == set(second.bridge_id)


@pytest.mark.parametrize("change,message", [
    ("DELETE FROM source_southern_legislative_candidate_result WHERE source_candidate_result_id='AL18SET-1-CELL-0'", "no_certified_candidate"),
    ("INSERT INTO source_southern_legislative_candidate_result VALUES ('DUP','AL18SET-1','{}','Other Smith','Other Smith','democratic','D',5,NULL,'observed','false',NULL,NULL,'passed','f')", "ambiguous_certified_candidates"),
    ("UPDATE source_southern_legislative_candidate_result SET candidate_name='Nobody', candidate_name_original='Nobody' WHERE source_candidate_result_id='AL18SET-1-CELL-1'", "no_name_evidence"),
    ("UPDATE canonical_candidates SET canonical_name='GSL001DQQQ' WHERE canonical_candidate_id='AL-2022-house-1-D-GSL001DABC'", "no_name_evidence"),
])
def test_bridge_never_invents_a_match(database, change, message):
    with sqlite3.connect(database) as connection:
        connection.execute(change)
        with pytest.raises(ValueError, match=message):
            repair.stage(connection, decoder=DECODER, precinct_alignment=ALIGNMENT)


def test_label_disagreement_without_alignment_is_not_bridged(database):
    with sqlite3.connect(database) as connection:
        with pytest.raises(ValueError, match="no_name_evidence"):
            repair.stage(connection, decoder=DECODER, precinct_alignment={})


def test_stage_requires_both_cycles_and_refuses_winner_flips_and_drift(database):
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM source_southern_legislative_observation_set WHERE cycle=2022")
        with pytest.raises(ValueError, match="required"):
            repair.stage(connection, decoder=DECODER, precinct_alignment=ALIGNMENT)
        connection.rollback()
        connection.execute("UPDATE source_southern_legislative_candidate_result SET votes=999 WHERE source_candidate_result_id='AL18SET-1-CELL-0'")
        with pytest.raises(ValueError, match="winner"):
            repair.stage(connection, decoder=DECODER, precinct_alignment=ALIGNMENT)
        connection.rollback()
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE canonical_southern_legislative_candidate_election SET votes=1 WHERE candidate_result_id='AL-2018-house-1-D-JANE-SMITH'")
        with pytest.raises(ValueError, match="already differ"):
            repair.stage(connection, decoder=DECODER, precinct_alignment=ALIGNMENT)


def test_set_totals_and_outcome_fields_keep_third_party_components_separate(database):
    with sqlite3.connect(database) as connection:
        totals = bridge.set_totals(bridge.certified_rows(connection)).set_index("observation_set_id")
    assert totals.loc["AL18SET-1", ["total_votes", "write_in_votes", "other_named_votes", "dem_votes", "rep_votes"]].tolist() == [314, 4, 7, 103, 200]
    candidates = {
        "D": {"observation_set_id": "AL18SET-1", "source_file_id": "SRC-C18", "certified_votes": 103,
              "match_method": "surname_unique_race_party", "correction_status": "corrected_to_certified", "canonical_candidate_id": "D"},
        "R": {"observation_set_id": "AL18SET-1", "source_file_id": "SRC-C18", "certified_votes": 200,
              "match_method": "surname_unique_race_party", "correction_status": "agrees", "canonical_candidate_id": "R"},
    }
    sets = {row["observation_set_id"]: row for row in totals.reset_index().to_dict("records")}
    group = pd.DataFrame({"candidate_result_id": ["D", "R"], "votes": [103, 200], "party_family": ["democratic", "republican"]})
    source_file, third_party, flags = bridge.alabama_certified_outcome_fields(group, candidates, sets)
    assert (source_file, third_party) == ("SRC-C18", 11)
    assert flags["alabama_certified_bridge"]["write_in_votes"] == 4
    assert flags["alabama_certified_bridge"]["other_named_votes"] == 7
    assert flags["alabama_certified_bridge"]["corrected_candidates"] == ["D"]
    with pytest.raises(ValueError, match="disagrees"):
        bridge.alabama_certified_outcome_fields(group.assign(votes=[100, 200]), candidates, sets)
    with pytest.raises(ValueError, match="lacks a certified bridge"):
        bridge.alabama_certified_outcome_fields(group.assign(candidate_result_id=["D", "Q"]), candidates, sets)


def test_bridge_lookup_absent_until_repair(database):
    with sqlite3.connect(database) as connection:
        assert bridge.bridge_lookup(connection) == (None, None)


def apply(database, **kwargs):
    root = database.parent
    return repair.repair(database, apply=True, expected_run="RUN-BEFORE", backup=root / "before.sqlite",
                         root=root, decoder=DECODER, precinct_alignment=ALIGNMENT, **kwargs)


def test_dry_run_is_read_only(database):
    before = database.read_bytes()
    result = repair.repair(database, root=database.parent, decoder=DECODER, precinct_alignment=ALIGNMENT)
    assert result["warehouse_status"] == "dry_run"
    assert result["summary"]["corrections"] == 2
    assert database.read_bytes() == before


def test_apply_corrects_totals_preserves_everything_else_and_replays_safely(database):
    report = apply(database)
    assert report["warehouse_status"] == "committed"
    assert report["report_status"] == "written"
    with sqlite3.connect(database) as connection, sqlite3.connect(database.parent / "before.sqlite") as backup:
        assert backup.execute("PRAGMA quick_check").fetchall() == [("ok",)]
        assert backup.execute("SELECT COUNT(*) FROM sqlite_master WHERE name=?", (bridge.BRIDGE_TABLE,)).fetchone() == (0,)
        votes = dict(connection.execute("SELECT canonical_candidate_id, canonical_votes FROM canonical_candidates"))
        assert votes["AL-2018-house-1-D-JANE-SMITH"] == 103.0
        assert votes["AL-2022-house-1-D-GSL001DABC"] == 100.0
        assert votes["AL-2018-house-2-R-MICHAEL-HOLDEN-II"] == 120.0
        shares = dict(connection.execute("SELECT candidate_result_id, vote_share FROM canonical_southern_legislative_candidate_election"))
        assert shares["AL-2018-house-1-D-JANE-SMITH"] == pytest.approx(103 / 303)
        assert shares["AL-2018-house-2-D-ANN-GRAY"] == pytest.approx(300 / 420)
        assert connection.execute(f"SELECT COUNT(*) FROM {bridge.BRIDGE_TABLE}").fetchone() == (6,)
        assert connection.execute("SELECT MAX(version) FROM warehouse_schema_version").fetchone() == (27,)
        assert connection.execute("SELECT COUNT(*) FROM warehouse_build_run").fetchone() == (2,)
        assert connection.execute("SELECT status FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone() == ("validated",)
        evidence = json.loads(connection.execute("SELECT evidence_json FROM qa_warehouse_source_repair").fetchone()[0])
        assert {image["canonical_candidate_id"] for image in evidence["before_images"]} == {"AL-2018-house-1-D-JANE-SMITH", "AL-2022-house-1-D-GSL001DABC"}
        assert evidence["not_rebuilt"]
        assert connection.execute("SELECT * FROM unrelated_domain").fetchall() == [("preserved",)]
        assert connection.execute("SELECT * FROM mart_southern_war_outcome").fetchall() == backup.execute("SELECT * FROM mart_southern_war_outcome").fetchall()
        assert connection.execute("SELECT * FROM source_southern_legislative_candidate_result").fetchall() == backup.execute("SELECT * FROM source_southern_legislative_candidate_result").fetchall()
        assert connection.execute("SELECT * FROM warehouse_source_file").fetchall() == backup.execute("SELECT * FROM warehouse_source_file").fetchall()
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        candidates, sets = bridge.bridge_lookup(connection)
        assert candidates["AL-2018-house-1-D-JANE-SMITH"]["certified_votes"] == 103
        assert sets["AL18SET-1"]["total_votes"] == 314
    run = report["build_run_id"]
    replay = repair.repair(database, apply=True, expected_run=run, backup=database.parent / "unused.sqlite",
                          root=database.parent, decoder=DECODER, precinct_alignment=ALIGNMENT)
    assert replay["warehouse_status"] == "unchanged"
    assert not (database.parent / "unused.sqlite").exists()


def test_conflicting_existing_bridge_refuses_overwrite(database):
    apply(database)
    with sqlite3.connect(database) as connection:
        connection.execute(f"UPDATE {bridge.BRIDGE_TABLE} SET certified_votes=1 WHERE canonical_party='D' AND cycle=2018 AND district='1'")
    with pytest.raises(ValueError, match="conflicts"):
        repair.repair(database, root=database.parent, decoder=DECODER, precinct_alignment=ALIGNMENT)


@pytest.mark.parametrize("mutation", ["snapshot", "backup", "source", "trigger"])
def test_guard_refusals_precede_mutation(database, mutation):
    root = database.parent
    if mutation == "snapshot":
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE warehouse_build_run SET build_run_id='OTHER'")
    if mutation == "backup":
        (root / "before.sqlite").write_bytes(b"do not overwrite")
    if mutation == "source":
        (root / "canvass18.pdf").write_bytes(b"changed")
    if mutation == "trigger":
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TRIGGER dangerous AFTER UPDATE ON canonical_candidates BEGIN INSERT INTO unrelated_domain VALUES ('bad'); END")
    with pytest.raises((ValueError, FileExistsError)):
        apply(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT canonical_votes FROM canonical_candidates WHERE canonical_candidate_id='AL-2018-house-1-D-JANE-SMITH'").fetchone() == (100.0,)
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE name=?", (bridge.BRIDGE_TABLE,)).fetchone() == (0,)
        assert connection.execute("SELECT * FROM unrelated_domain").fetchall() == [("preserved",)]


def test_injected_failure_rolls_back_and_keeps_backup(database, monkeypatch):
    def fail(*args):
        raise RuntimeError("injected finish failure")
    monkeypatch.setattr(repair, "finish_run", fail)
    with pytest.raises(RuntimeError, match="injected"):
        apply(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT canonical_votes FROM canonical_candidates WHERE canonical_candidate_id='AL-2018-house-1-D-JANE-SMITH'").fetchone() == (100.0,)
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE name=?", (bridge.BRIDGE_TABLE,)).fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM warehouse_build_run").fetchone() == (1,)
    assert (database.parent / "before.sqlite").is_file()


def test_authorizer_rejects_unowned_writes(database):
    with sqlite3.connect(database) as connection:
        connection.set_authorizer(repair.authorize)
        for sql in ("UPDATE canonical_candidates SET canonical_name='x'", "DELETE FROM unrelated_domain",
                    "INSERT INTO unrelated_domain VALUES ('bad')", "CREATE TABLE forbidden(x)",
                    "UPDATE canonical_southern_legislative_candidate_election SET candidate_name='x'"):
            with pytest.raises(sqlite3.DatabaseError, match="authorized"):
                connection.execute(sql)


def test_cli_defaults_to_dry_run_and_requires_full_cycles_for_apply(database, monkeypatch, capsys):
    seen = {}
    def fake(database_path, **kwargs):
        seen.update(kwargs)
        return {"warehouse_status": "dry_run"}
    monkeypatch.setattr(repair, "repair", fake)
    assert repair.main(["--database", str(database)]) == 0
    assert seen["apply"] is False and seen["cycles"] == bridge.CYCLES
    assert json.loads(capsys.readouterr().out)["warehouse_status"] == "dry_run"
    with pytest.raises(SystemExit):
        repair.main(["--database", str(database), "--apply", "--cycles", "2022"])
