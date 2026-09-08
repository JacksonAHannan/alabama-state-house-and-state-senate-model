import sqlite3

import pytest

import audit_southern_release_readiness as mod


@pytest.fixture
def connection():
    with sqlite3.connect(":memory:") as c:
        c.execute(f"CREATE TABLE {mod.VIEW} (" + ",".join(mod.FIELDS) + ")")
        c.execute("CREATE TABLE mart_southern_war_outcome(war_outcome_id,state_code,cycle,chamber,district)")
        c.execute("CREATE TABLE mart_southern_war_context_feature(context_feature_id,build_run_id,state_code,cycle,chamber,district)")
        c.execute("INSERT INTO mart_southern_war_context_feature VALUES ('ctx','context-run','AL',2022,'lower','1')")
        for i, status in enumerate([mod.STRICT, "missing_context"], 1):
            values = dict.fromkeys(mod.FIELDS)
            values.update(war_outcome_id=str(i), state_code="AL", cycle=2022, chamber="lower", district=str(i), training_status=status)
            if i == 1: values["context_feature_id"] = "ctx"
            c.execute(f"INSERT INTO {mod.VIEW} VALUES (" + ",".join("?" for _ in mod.FIELDS) + ")", list(values.values()))
            c.execute("INSERT INTO mart_southern_war_outcome VALUES (?,?,?,?,?)", (str(i), "AL", 2022, "lower", str(i)))
        yield c


def test_exact_schedule_and_conservation(connection):
    report = mod.inventory(connection)
    assert report["scheduled_slices"] == 116
    assert report["total"] == report["strict"] + report["excluded"] == 2
    assert report["missing_source_file_id"] == 2
    assert len(report["slices"]) == 116
    item = report["excluded_outcomes"][0]
    assert item["war_outcome_id"] == "2"
    assert "training_status:missing_context" in item["reason_codes"]
    assert "missing:baseline_source_path" in item["reason_codes"]
    assert not any("margin" in f or "votes" in f for f in mod.FIELDS)
    assert "Overlapping" in report["reason_count_semantics"]
    assert report["outcome_build_run_ids"] == []
    assert report["context_build_run_ids"] == ["context-run"]
    assert report["missing_outcome_build_run_id_rows"] == 2
    assert report["missing_context_rows"] == 1
    assert report["missing_context_build_run_id_rows"] == 0


@pytest.mark.parametrize("change", ["duplicate", "outside", "disappear", "missing_id", "missing_status"])
def test_bad_inventory_fails(connection, change):
    if change == "duplicate": connection.execute(f"INSERT INTO {mod.VIEW} SELECT * FROM {mod.VIEW} LIMIT 1")
    if change == "outside": connection.execute(f"UPDATE {mod.VIEW} SET cycle=1900")
    if change == "disappear": connection.execute(f"DELETE FROM {mod.VIEW} WHERE war_outcome_id='2'")
    if change == "missing_id": connection.execute(f"UPDATE {mod.VIEW} SET war_outcome_id=NULL")
    if change == "missing_status": connection.execute(f"UPDATE {mod.VIEW} SET training_status=NULL")
    with pytest.raises(ValueError): mod.inventory(connection)


def test_audit_opens_readonly_snapshot(connection, tmp_path):
    path = tmp_path / "fixture.sqlite"
    connection.commit()
    with sqlite3.connect(path) as destination: connection.backup(destination)
    before = path.read_bytes()
    report = mod.audit(path)
    assert report["total"] == 2
    assert report["latest_warehouse_build_run_id"] is None
    assert set(report["code_sha256"]) == {"audit_southern_release_readiness.py", "southern_war_map_contract.py", "load_southern_war_preparation_warehouse.py"}
    assert all(len(v) == 64 for v in report["code_sha256"].values())
    assert path.read_bytes() == before
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE warehouse_build_run(build_run_id)")
        c.executemany("INSERT INTO warehouse_build_run VALUES (?)", [("older",), ("latest",)])
        c.execute(f"UPDATE {mod.VIEW} SET build_run_id='consumed'")
    report = mod.audit(path)
    assert report["latest_warehouse_build_run_id"] == "latest"
    assert report["outcome_build_run_ids"] == ["consumed"]
    assert report["missing_outcome_build_run_id_rows"] == 0
    assert report["sqlite_definition_sha256"][mod.VIEW]["type"] == "table"


@pytest.mark.parametrize("change", ["duplicate", "wrong_key", "missing", "hidden"])
def test_context_join_cardinality(connection, change):
    if change == "duplicate": connection.execute("INSERT INTO mart_southern_war_context_feature SELECT * FROM mart_southern_war_context_feature")
    if change == "wrong_key": connection.execute("UPDATE mart_southern_war_context_feature SET district='9'")
    if change == "missing": connection.execute("DELETE FROM mart_southern_war_context_feature")
    if change == "hidden": connection.execute(f"UPDATE {mod.VIEW} SET context_feature_id=NULL")
    with pytest.raises(ValueError): mod.inventory(connection)
