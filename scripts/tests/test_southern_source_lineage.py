import json
from pathlib import Path
import sqlite3
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import repair_southern_source_lineage as repair
from load_southern_war_preparation_warehouse import (
    observation_source_file, unique_official_candidate_sources,
)
from warehouse import initialize


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "ROOT", tmp_path)
    path = tmp_path / "warehouse.sqlite"
    source = tmp_path / "source.txt"
    source.write_text("official fixture", encoding="utf-8")
    with sqlite3.connect(path) as connection:
        initialize(connection)
        connection.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256) VALUES (?,?,?,?)",
                           ("SRC-A", "fixture", "source.txt", repair.file_sha256(source)))
        connection.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256) VALUES (?,?,?,?)",
                           ("SRC-B", "fixture", "other-source.txt", repair.file_sha256(source)))
        connection.execute("""CREATE TABLE qa_warehouse_source_repair(
            issue_id TEXT PRIMARY KEY, build_run_id TEXT, table_name TEXT, scope TEXT,
            status TEXT, evidence_json TEXT, recorded_at_utc TEXT)""")
        rows = []
        for suffix, party, votes in (("D", "democratic", 60), ("R", "republican", 40), ("I", "independent", 5)):
            rows.append({"candidate_election_id": suffix, "contest_id": "C1", "state_code": "AL",
                "cycle": 2022, "chamber": "lower", "district": "1", "election_stage": "general",
                "election_date": "2022-11-08", "district_plan_id": "PLAN", "geography_vintage": "2022",
                "party_family": party, "votes": votes, "validation_status": "passed"})
        pd.DataFrame(rows).to_sql("source_southern_candidate_election", connection, index=False)
        pd.DataFrame({"candidate_election_id": ["D", "R", "I"],
                      "source_file_id": ["SRC-A"] * 3}).to_sql(
                          "bridge_southern_candidate_result_source", connection, index=False)
        outcome = {"war_outcome_id": "OUT-1", "source_family": "official_state", "source_file_id": None,
            "observation_set_id": "OFFICIAL-C1", "dem_candidate_result_id": "D", "rep_candidate_result_id": "R",
            "dem_votes": 60, "rep_votes": 40, "two_party_votes": 100, "third_party_votes": 5,
            "build_run_id": "ORIGINAL-RUN", "selection_status": "canonical_model_eligible",
            "validation_status": "passed", "legislative_dem_margin": 20.0,
            **{k: rows[0][k] for k in ("state_code", "cycle", "chamber", "district", "election_stage",
                                     "election_date", "district_plan_id", "geography_vintage")}}
        pd.DataFrame([outcome, {**outcome, "war_outcome_id": "OUT-AL", "source_family": "alabama_canonical"},
                      {**outcome, "war_outcome_id": "OUT-EXISTING", "source_file_id": "SRC-B"}]).to_sql(
                          repair.OUTCOMES, connection, index=False)
        connection.execute("CREATE TABLE unrelated_domain(value TEXT)")
        connection.execute("INSERT INTO unrelated_domain VALUES ('preserved')")
        connection.execute(f"CREATE VIEW training_status AS SELECT war_outcome_id,'research_only' AS status FROM {repair.OUTCOMES}")
        connection.execute(f"CREATE VIEW mart_southern_war_training_no_finance AS SELECT war_outcome_id,'research_only' AS training_status FROM {repair.OUTCOMES}")
        connection.execute(f"CREATE VIEW mart_southern_war_training_with_finance AS SELECT war_outcome_id,'research_only' AS evaluation_status FROM {repair.OUTCOMES}")
    return path


def test_singleton_consensus_recovers_missing_scalar_without_changing_inputs(database):
    with sqlite3.connect(database) as connection:
        before, mapping, unresolved = repair.stage(connection)
        assert before.loc[before.war_outcome_id.eq("OUT-1"), "source_file_id"].isna().all()
        assert mapping == {"OUT-1": "SRC-A"}
        assert not unresolved
        assert connection.execute(f"SELECT source_file_id FROM {repair.OUTCOMES} WHERE war_outcome_id='OUT-1'").fetchone() == (None,)


@pytest.mark.parametrize("change", [
    "DELETE FROM bridge_southern_candidate_result_source WHERE candidate_election_id='I'",
    "INSERT INTO bridge_southern_candidate_result_source VALUES ('I','SRC-B')",
    "INSERT INTO bridge_southern_candidate_result_source VALUES ('I','UNREGISTERED')",
    "UPDATE bridge_southern_candidate_result_source SET source_file_id='UNREGISTERED' WHERE candidate_election_id='I'",
    "UPDATE bridge_southern_candidate_result_source SET source_file_id='SRC-B' WHERE candidate_election_id='I'",
])
def test_incomplete_or_disagreeing_third_party_lineage_stays_unknown(database, change):
    with sqlite3.connect(database) as connection:
        connection.execute(change)
        _, mapping, unresolved = repair.stage(connection)
        assert mapping == {}
        assert unresolved == ["OUT-1"]


@pytest.mark.parametrize("sources,expected", [(["S", "S", "S"], "S"),
    (["S", None, "S"], None), (["S", "S", "OTHER"], None), (["", "", ""], None)])
def test_other_provider_scalar_requires_every_contributor(sources, expected):
    group = pd.DataFrame({"source_family": ["medsl"] * 3, "source_file_id": sources})
    assert observation_source_file(group, {}) == expected


@pytest.mark.parametrize("change,match", [
    ("UPDATE source_southern_candidate_election SET cycle=2020 WHERE candidate_election_id='I'", "scope mismatch"),
    (f"UPDATE {repair.OUTCOMES} SET dem_candidate_result_id='OTHER' WHERE war_outcome_id='OUT-1'", "Constituent mismatch"),
    ("UPDATE source_southern_candidate_election SET votes=6 WHERE candidate_election_id='I'", "vote total mismatch"),
])
def test_scope_and_constituents_must_match(database, change, match):
    with sqlite3.connect(database) as connection:
        connection.execute(change)
        connection.commit()
    backup = database.with_name("backup.sqlite")
    with pytest.raises(ValueError, match=match):
        repair.repair(database, backup)
    assert not backup.exists()


def test_matching_unknown_nullable_scope_is_preserved(database):
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE source_southern_candidate_election SET election_date=NULL")
        connection.execute(f"UPDATE {repair.OUTCOMES} SET election_date=NULL")
    result = repair.repair(database, database.with_name("backup.sqlite"))
    assert result["validation"]["repaired_rows"] == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute(f"SELECT COUNT(*) FROM {repair.OUTCOMES} WHERE election_date IS NOT NULL").fetchone() == (0,)


def test_repair_preserves_all_nonprovenance_data_and_is_replay_safe(database):
    backup = database.with_name("backup.sqlite")
    result = repair.repair(database, backup)
    assert result["warehouse_status"] == "committed"
    assert result["validation"]["repaired_rows"] == 1
    assert result["validation"]["readiness_before"] == result["validation"]["readiness_after"]
    assert all(result["validation"]["readiness_after"].values())
    with sqlite3.connect(database) as current, sqlite3.connect(backup) as old:
        before = pd.read_sql_query(f"SELECT * FROM {repair.OUTCOMES} ORDER BY war_outcome_id", old)
        after = pd.read_sql_query(f"SELECT * FROM {repair.OUTCOMES} ORDER BY war_outcome_id", current)
        before.loc[before.war_outcome_id.eq("OUT-1"), "source_file_id"] = "SRC-A"
        pd.testing.assert_frame_equal(after, before)
        for table in ("source_southern_candidate_election", "bridge_southern_candidate_result_source",
                      "warehouse_source_file", "unrelated_domain", "training_status"):
            assert current.execute(f"SELECT * FROM {table}").fetchall() == old.execute(f"SELECT * FROM {table}").fetchall()
        assert current.execute("SELECT count(*) FROM warehouse_build_run").fetchone() == (1,)
        evidence = json.loads(current.execute("SELECT evidence_json FROM qa_warehouse_source_repair").fetchone()[0])
        assert evidence["source_file_mapping"] == {"OUT-1": "SRC-A"}
    new_backup = database.with_name("replay.sqlite")
    assert repair.repair(database, new_backup)["warehouse_status"] == "unchanged"
    assert not new_backup.exists()
    assert backup.with_name(backup.name + ".application.json").exists()


def test_failed_validation_rolls_back_and_retains_backup(database, monkeypatch):
    with sqlite3.connect(database) as connection:
        before = repair.snapshot(connection)
    def fail(connection, expected):
        raise ValueError("injected validation failure")
    monkeypatch.setattr(repair, "validate", fail)
    backup = database.with_name("backup.sqlite")
    with pytest.raises(ValueError, match="injected"):
        repair.repair(database, backup)
    with sqlite3.connect(database) as connection:
        assert repair.snapshot(connection) == before
    assert backup.is_file()


def test_readiness_change_rolls_back(database):
    with sqlite3.connect(database) as connection:
        connection.execute("DROP VIEW mart_southern_war_training_no_finance")
        connection.execute(f"""CREATE VIEW mart_southern_war_training_no_finance AS
            SELECT war_outcome_id, CASE WHEN source_file_id IS NULL THEN 'review' ELSE 'ready' END AS training_status
            FROM {repair.OUTCOMES}""")
        before = repair.snapshot(connection)
    with pytest.raises(ValueError, match="Readiness states changed"):
        repair.repair(database, database.with_name("backup.sqlite"))
    with sqlite3.connect(database) as connection:
        assert repair.snapshot(connection) == before


def test_existing_backup_missing_database_and_changed_source_are_rejected(database):
    backup = database.with_name("backup.sqlite")
    backup.write_text("preserved", encoding="utf-8")
    with pytest.raises(FileExistsError):
        repair.repair(database, backup)
    assert backup.read_text(encoding="utf-8") == "preserved"
    with pytest.raises(FileNotFoundError):
        repair.repair(database.with_name("missing.sqlite"), database.with_name("new.sqlite"))
    (database.parent / "source.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        repair.repair(database, database.with_name("new.sqlite"))
    assert not database.with_name("new.sqlite").exists()


def test_owned_triggers_are_rejected(database):
    with sqlite3.connect(database) as connection:
        connection.execute(f"CREATE TRIGGER unexpected AFTER UPDATE ON {repair.OUTCOMES} BEGIN DELETE FROM unrelated_domain; END")
    with pytest.raises(ValueError, match="Triggers"):
        repair.repair(database, database.with_name("backup.sqlite"))


def test_authorizer_rejects_other_columns_domains_and_ddl(database):
    with sqlite3.connect(database) as connection:
        connection.set_authorizer(repair.authorize)
        for sql in (f"UPDATE {repair.OUTCOMES} SET dem_votes=1", "DELETE FROM unrelated_domain",
                    "CREATE TABLE unexpected(x)", "DROP TABLE unrelated_domain"):
            with pytest.raises(sqlite3.DatabaseError, match="authorized"):
                connection.execute(sql)


def test_report_failure_does_not_hide_committed_database_evidence(database, monkeypatch, capsys):
    original = Path.open
    def fail_report(path, *args, **kwargs):
        if path.name.endswith(".application.json"):
            raise OSError("injected report failure")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", fail_report)
    assert repair.main(["--database", str(database), "--backup", str(database.with_name("backup.sqlite"))]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["warehouse_status"] == "committed"
    assert result["report_status"] == "failed_after_commit"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT status FROM warehouse_build_run").fetchone() == ("validated",)
        assert connection.execute("SELECT COUNT(*) FROM qa_warehouse_source_repair").fetchone() == (1,)
