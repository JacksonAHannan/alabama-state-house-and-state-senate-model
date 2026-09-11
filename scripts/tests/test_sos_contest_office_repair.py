"""Focused office-only mutation safeguards; every write uses a temporary DB."""
import copy
import json
import sqlite3

import pandas as pd
import pytest

import repair_sos_contest_offices as repair
from warehouse import file_sha256, initialize


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    root, database = tmp_path, tmp_path / "fixture.sqlite"
    source = root / "source.zip"
    source.write_bytes(b"fixture source")
    sha = file_sha256(source)
    key = ["year", "county_key", "precinct_key", "candidate_key", "party", "party_norm", "votes", "source", "authority_rank"]
    old = []
    for i, candidate in enumerate(["TWINKLE", "LUCY", "OTHER", "AMBIGUOUS", "AMBIGUOUS"], 1):
        old.append({"year": 2012, "county": "Morgan", "county_key": "MORGAN", "precinct": "P", "precinct_key": "P",
                    "office": "President" if i < 3 else "Governor", "district": None, "candidate": candidate,
                    "candidate_key": candidate, "party": "", "party_norm": "O", "votes": 11.0 if i > 3 else float(10 + i),
                    "source": "alabama_sos", "authority_rank": 1, "source_file": None, "source_sheet": None,
                    "source_row": None, "source_column": None, "source_file_id": None, "build_run_id": None,
                    "stable_user_id": f"unchanged-{i}"})
    with sqlite3.connect(database) as c:
        initialize(c)
        c.execute("INSERT INTO warehouse_build_run VALUES ('RUN-BEFORE','fixture','2026-01-01','2026-01-01','validated','fixture','{}','{}')")
        c.execute("CREATE TABLE qa_warehouse_source_repair(issue_id PRIMARY KEY,build_run_id,warehouse_object,scope,status,evidence_json,recorded_at_utc)")
        c.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256) VALUES (?,'fixture','source.zip',?)", (repair.SOURCE_IDS[2012], sha))
        pd.DataFrame(old).to_sql(repair.TABLE, c, index=False)
        c.execute("CREATE TABLE unrelated(value)")
        c.execute("INSERT INTO unrelated VALUES ('preserve')")
    new = copy.deepcopy(old)
    for i, row in enumerate(new):
        if i < 2: row["office"] = "Public Service Commission President"
        row.update(source_sheet="1", source_row=4, source_column=i + 2,
                   printed_candidate=row["candidate"], printed_precinct="P")
    scope = {"year": 2012, "county": "Morgan", "source_path": "source.zip", "source_sha256": sha,
        "source_member": "Morgan.xlsx", "member_sha256": "a" * 64, "stored_rows": 5, "reparsed_rows": 5,
        "unique_pairs": 3, "ambiguous_stored_rows": 2, "ambiguous_reparsed_rows": 2, "semantic_change_pairs": 2,
        "changes_by_field": [{"office_old": "President", "office_new": "Public Service Commission President",
                               "district_old": None, "district_new": None, "rows": 2}],
        "ambiguous_stored": [], "ambiguous_reparsed": []}
    for i in [3, 4]:
        scope["ambiguous_stored"].append({"stored_rowid": i + 1} | {k: old[i][k] for k in key + ["office", "district"]})
        scope["ambiguous_reparsed"].append({k: new[i][k] for k in key + ["office", "district", "source_sheet", "source_row", "source_column", "printed_candidate", "printed_precinct"]})
    audit = {"comparison_key": key, "cohorts": [scope]}
    frames = {(2012, "MORGAN"): pd.DataFrame(new)}
    sheets = {(2012, "MORGAN"): {"1": [["PRESIDENT PSC"], [], [], ["P", 11, 12, 13, 11, 11]]}}
    hashes = {"source.zip": sha}
    monkeypatch.setattr(repair, "load_sources", lambda root: (audit, frames, sheets, hashes))
    return root, database, audit, frames, sheets


def apply(fixture):
    root, database, *_ = fixture
    return repair.repair(database, apply=True, expected_run="RUN-BEFORE", backup=root / "before.sqlite", root=root)


def test_office_only_repair_preserves_votes_rowids_all_other_columns(fixture):
    root, database, *_ = fixture
    before_bytes = database.read_bytes()
    report = repair.repair(database, root=root)
    assert report["changed_rows"] == 2 and report["ambiguous_rows_unchanged"] == 2
    assert database.read_bytes() == before_bytes
    with sqlite3.connect(database) as c:
        before = c.execute(f"SELECT rowid,* FROM {repair.TABLE} ORDER BY rowid").fetchall()
        assert c.execute(f"SELECT COUNT(*) FROM {repair.TABLE} WHERE office='President'").fetchone() == (2,)
    result = apply(fixture)
    with sqlite3.connect(database) as c, sqlite3.connect(root / "before.sqlite") as backup:
        assert backup.execute(f"SELECT rowid,* FROM {repair.TABLE} ORDER BY rowid").fetchall() == before
        after = c.execute(f"SELECT rowid,* FROM {repair.TABLE} ORDER BY rowid").fetchall()
        assert c.execute(f"SELECT COUNT(*) FROM {repair.TABLE} WHERE office='President'").fetchone() == (0,)
        assert after[2:] == before[2:]
        for index in [0, 1]:
            expected = list(before[index]); expected[6] = "Public Service Commission President"
            assert after[index] == tuple(expected)
        assert c.execute("SELECT * FROM unrelated").fetchall() == [("preserve",)]
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        qa = json.loads(c.execute(f"SELECT evidence_json FROM {repair.QA} WHERE issue_id=?", (result["qa_issue_id"],)).fetchone()[0])
        assert len(qa["changes"]) == 2 and qa["changes"][0]["printed_title"] == "PRESIDENT PSC"
    replay = repair.repair(database, apply=True, expected_run=result["build_run_id"], backup=root / "unused.sqlite", root=root)
    assert replay["warehouse_status"] == "unchanged" and not (root / "unused.sqlite").exists()


@pytest.mark.parametrize("mutation", ["vote", "name", "keycount", "ambiguous", "office", "title", "cell"])
def test_source_drift_or_unreviewed_change_is_rejected(fixture, mutation):
    root, database, _, frames, sheets = fixture
    if mutation in {"vote", "name", "ambiguous", "office", "keycount"}:
        with sqlite3.connect(database) as c:
            if mutation == "vote": c.execute(f"UPDATE {repair.TABLE} SET votes=100 WHERE rowid=1")
            if mutation == "name": c.execute(f"UPDATE {repair.TABLE} SET candidate_key='different' WHERE rowid=1")
            if mutation == "ambiguous": c.execute(f"UPDATE {repair.TABLE} SET office='different' WHERE rowid=4")
            if mutation == "office": c.execute(f"UPDATE {repair.TABLE} SET office='different' WHERE rowid=1")
            if mutation == "keycount": c.execute(f"DELETE FROM {repair.TABLE} WHERE rowid=5")
    if mutation == "title": sheets[(2012, "MORGAN")]["1"][0][0] = "PRESIDENT"
    if mutation == "cell": sheets[(2012, "MORGAN")]["1"][3][1] = 999
    with pytest.raises(ValueError):
        repair.repair(database, root=root)


@pytest.mark.parametrize("mutation", ["backup", "snapshot", "source", "registry", "trigger"])
def test_guarded_application_refuses_before_mutation(fixture, mutation):
    root, database, *_ = fixture
    if mutation == "backup": (root / "before.sqlite").write_bytes(b"preserve")
    if mutation == "source": (root / "source.zip").write_bytes(b"changed")
    with sqlite3.connect(database) as c:
        if mutation == "snapshot": c.execute("UPDATE warehouse_build_run SET build_run_id='changed'")
        if mutation == "registry": c.execute("UPDATE warehouse_source_file SET source_file_id='changed'")
        if mutation == "trigger": c.execute(f"CREATE TRIGGER dangerous AFTER UPDATE ON {repair.TABLE} BEGIN INSERT INTO unrelated VALUES ('bad'); END")
    with pytest.raises((ValueError, FileExistsError)):
        apply(fixture)
    with sqlite3.connect(database) as c:
        assert c.execute(f"SELECT COUNT(*) FROM {repair.TABLE} WHERE office='President'").fetchone() == (2,)
        assert c.execute("SELECT * FROM unrelated").fetchall() == [("preserve",)]


def test_apply_needs_explicit_snapshot_and_new_database_is_never_created(fixture):
    root, database, *_ = fixture
    with pytest.raises(ValueError, match="requires"):
        repair.repair(database, apply=True, root=root)
    with pytest.raises(FileNotFoundError): repair.repair(root / "missing.sqlite", root=root)
    assert not (root / "missing.sqlite").exists()


@pytest.mark.parametrize("sql", ["UPDATE vote_observations SET votes=0", "INSERT INTO unrelated VALUES ('bad')", "DELETE FROM vote_observations", "CREATE TABLE bad(x)"])
def test_authorizer_forbids_nonoffice_mutations(fixture, monkeypatch, sql):
    def forbidden(connection, *args): connection.execute(sql)
    monkeypatch.setattr(repair, "begin_run", forbidden)
    with pytest.raises(sqlite3.DatabaseError, match="authorized"):
        apply(fixture)
    with sqlite3.connect(fixture[1]) as c:
        assert c.execute(f"SELECT COUNT(*) FROM {repair.TABLE} WHERE office='President'").fetchone() == (2,)


def test_failure_after_updates_rolls_back(fixture, monkeypatch):
    def fail(*args): raise RuntimeError("injected finish failure")
    monkeypatch.setattr(repair, "finish_run", fail)
    with pytest.raises(RuntimeError, match="injected"):
        apply(fixture)
    with sqlite3.connect(fixture[1]) as c:
        assert c.execute(f"SELECT COUNT(*) FROM {repair.TABLE} WHERE office='President'").fetchone() == (2,)
        assert c.execute("SELECT COUNT(*) FROM warehouse_build_run").fetchone() == (1,)
        assert c.execute(f"SELECT COUNT(*) FROM {repair.QA}").fetchone() == (0,)


def test_full_table_digest_catches_unintended_office_change(fixture, monkeypatch):
    original = repair.begin_run
    def corrupt(connection, *args):
        run = original(connection, *args)
        connection.execute(f"UPDATE {repair.TABLE} SET office='bad' WHERE rowid=3")
        return run
    monkeypatch.setattr(repair, "begin_run", corrupt)
    with pytest.raises(ValueError, match="Unexpected source"):
        apply(fixture)


def test_prior_build_rows_are_preserved(fixture, monkeypatch):
    original = repair.finish_run
    def corrupt(connection, *args):
        original(connection, *args)
        connection.execute("UPDATE warehouse_build_run SET target='bad' WHERE build_run_id='RUN-BEFORE'")
    monkeypatch.setattr(repair, "finish_run", corrupt)
    with pytest.raises(ValueError, match="Prior control"):
        apply(fixture)


def test_replay_rejects_changed_unrelated_column(fixture):
    root, database, *_ = fixture
    apply(fixture)
    with sqlite3.connect(database) as c:
        c.execute(f"UPDATE {repair.TABLE} SET stable_user_id='tampered' WHERE rowid=1")
    with pytest.raises(ValueError, match="Previously repaired row"):
        repair.repair(database, root=root)


def test_cli_omits_large_before_after_arrays(monkeypatch, capsys):
    monkeypatch.setattr(repair, "repair", lambda *a, **kw: {"warehouse_status": "committed", "qa_issue_id": "QA1",
        "validation": {"changes": ["large"], "ambiguous_rows_unchanged": ["large"], "after_sha256": "hash"}})
    assert repair.main([]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["qa_issue_id"] == "QA1" and result["validation"] == {"after_sha256": "hash"}


def test_pinned_audit_is_required(tmp_path):
    (tmp_path / repair.AUDIT).parent.mkdir(parents=True)
    (tmp_path / repair.AUDIT).write_text("{}")
    with pytest.raises(ValueError, match="audit hash"):
        repair.load_sources(tmp_path)
