"""Source-provenance safeguards, using only isolated temporary databases."""
import copy
import json
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

import repair_sos_cell_lineage as repair
from warehouse import file_sha256, initialize


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    source = tmp_path / "source.zip"
    source.write_bytes(b"immutable fixture")
    sha = file_sha256(source)
    database = tmp_path / "warehouse.sqlite"
    old = []
    for i, candidate in enumerate(["A", "B", "DUP", "DUP"], 1):
        old.append(dict(year=2012, county="Morgan", county_key="MORGAN", precinct="P", precinct_key="P",
                        office="Office", district=None, candidate=candidate, candidate_key=candidate,
                        party="", party_norm="O", votes=11.0, source="alabama_sos", authority_rank=1,
                        source_file=None, source_sheet=None, source_row=None, source_column=None,
                        source_file_id=None, build_run_id="original-ingest" if i == 1 else None,
                        precinct_code=None, ballot_code=None, party_method=None, stable_id=f"keep-{i}"))
    with sqlite3.connect(database) as c:
        initialize(c)
        c.execute("INSERT INTO warehouse_build_run VALUES ('BEFORE','fixture','2026-01-01','2026-01-01','validated','fixture','{}','{}')")
        c.execute("CREATE TABLE qa_warehouse_source_repair(issue_id PRIMARY KEY,build_run_id,warehouse_object,scope,status,evidence_json,recorded_at_utc)")
        c.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256) VALUES (?,'fixture','source.zip',?)", (repair.SOURCE_IDS[2012], sha))
        # Explicit SQLite affinities are part of the digest contract.
        pd.DataFrame(old).to_sql(repair.TABLE, c, index=False, dtype={"source_row": "INTEGER", "source_column": "INTEGER"})
        c.execute("CREATE TABLE unrelated(value)")
        c.execute("INSERT INTO unrelated VALUES ('preserve')")
        c.execute(f"INSERT INTO {repair.TABLE}(year,county_key,source,stable_id) VALUES(2000,'OTHER','other','outside')")
    fresh = copy.deepcopy(old)
    for i, row in enumerate(fresh, 2):
        row.update(source_file="Morgan.xlsx", source_sheet="1", source_row=3, source_column=i,
                   printed_precinct="P", printed_candidate=row["candidate"])
    key = ["year", "county_key", "precinct_key", "candidate_key", "party", "party_norm", "votes", "source", "authority_rank"]
    scope = dict(year=2012, county="Morgan", source_path="source.zip", source_sha256=sha,
                 source_member="Morgan.xlsx", member_sha256="a" * 64, stored_rows=4, reparsed_rows=4,
                 ambiguous_stored=[{"stored_rowid": i + 1} | {k: old[i][k] for k in key + ["office", "district"]} for i in (2, 3)],
                 ambiguous_reparsed=[{k: fresh[i][k] for k in key + ["office", "district", "source_sheet", "source_row", "source_column", "printed_precinct", "printed_candidate"]} for i in (2, 3)])
    audit = {"comparison_key": key, "cohorts": [scope]}
    frames = {(2012, "MORGAN"): pd.DataFrame(fresh)}
    sheets = {(2012, "MORGAN"): {"1": [["Printed office"], [], ["P", 11, 11, 11, 11]]}}
    monkeypatch.setattr(repair, "EXPECTED", {(2012, "MORGAN"): (4, 2, 2)})
    monkeypatch.setattr(repair, "load_sources", lambda root: (audit, frames, sheets, {"source.zip": sha}))
    return tmp_path, database, audit, frames, sheets


def apply(fixture, **kwargs):
    root, database, *_ = fixture
    return repair.repair(database, apply=True, expected_run="BEFORE", backup=root / "before.sqlite", root=root, **kwargs)


def snapshot(database):
    with sqlite3.connect(database) as c:
        return repair.rows(c, f"SELECT rowid AS stored_rowid,* FROM {repair.TABLE} ORDER BY rowid")


def test_null_only_fill_backup_all_column_parity_and_verified_replay(fixture):
    root, database, *_ = fixture
    before = snapshot(database)
    raw = database.read_bytes()
    report = repair.repair(database, root=root)
    assert report["changed_rows"] == 2 and report["unresolved_rows"] == 2
    assert database.read_bytes() == raw
    result = apply(fixture)
    after = snapshot(database)
    assert snapshot(root / "before.sqlite") == before
    assert after[2:] == before[2:]
    for i in (0, 1):
        expected = before[i] | dict(source_file="Morgan.xlsx", source_sheet="1", source_row=3,
                                   source_column=i + 2, source_file_id=repair.SOURCE_IDS[2012])
        assert after[i] == expected
    assert after[0]["build_run_id"] == "original-ingest"
    with sqlite3.connect(database) as c:
        assert c.execute("SELECT * FROM unrelated").fetchall() == [("preserve",)]
        evidence = json.loads(c.execute(f"SELECT evidence_json FROM {repair.QA}").fetchone()[0])
        assert evidence["changes"][0]["before"] == before[0]
        assert evidence["changes"][0]["after"] == after[0]
        assert len(evidence["unresolved"][0]["candidate_cells"]) == 2
        assert evidence["unresolved"][0]["stored_rows"] == before[2:4]
    replay = repair.repair(database, apply=True, expected_run=result["build_run_id"], backup=root / "unused.sqlite", root=root)
    assert replay["warehouse_status"] == "unchanged" and not (root / "unused.sqlite").exists()


@pytest.mark.parametrize("column,value", [("votes", 12), ("office", "different"), ("candidate", "different"), ("source_file", "wrong"), ("source_row", 3)])
def test_drift_or_non_null_partial_fill_refused(fixture, column, value):
    root, database, *_ = fixture
    with sqlite3.connect(database) as c:
        c.execute(f"UPDATE {repair.TABLE} SET {column}=? WHERE rowid=1", (value,))
    before = snapshot(database)
    with pytest.raises(ValueError): apply(fixture)
    assert snapshot(database) == before and not (root / "before.sqlite").exists()


@pytest.mark.parametrize("kind", ["cell", "duplicate_cell", "missing_cell", "ambiguous_row", "extra_row", "missing_row", "registered_hash", "source_hash"])
def test_source_and_ambiguity_rejection(fixture, kind):
    root, database, audit, frames, sheets = fixture
    frame = frames[(2012, "MORGAN")]
    if kind == "cell": sheets[(2012, "MORGAN")]["1"][2][1] = 999
    if kind == "duplicate_cell": frame.loc[1, "source_column"] = 2
    if kind == "missing_cell": frame.loc[1, "source_column"] = None
    with sqlite3.connect(database) as c:
        if kind == "ambiguous_row": c.execute(f"UPDATE {repair.TABLE} SET source_row=3 WHERE rowid=3")
        if kind == "extra_row": c.execute(f"INSERT INTO {repair.TABLE} SELECT * FROM {repair.TABLE} WHERE rowid=1")
        if kind == "missing_row": c.execute(f"DELETE FROM {repair.TABLE} WHERE rowid=1")
        if kind == "registered_hash": c.execute("UPDATE warehouse_source_file SET sha256=?", ("0" * 64,))
    if kind == "source_hash": (root / "source.zip").write_bytes(b"changed")
    with pytest.raises(ValueError): apply(fixture)
    assert not (root / "before.sqlite").exists()


def test_required_snapshot_backup_and_dry_run_guards(fixture):
    root, database, *_ = fixture
    with pytest.raises(ValueError, match="requires"): repair.repair(database, apply=True, root=root)
    with pytest.raises(ValueError, match="snapshot"): repair.repair(database, expected_run="stale", root=root)
    with pytest.raises(FileExistsError): repair.repair(database, apply=True, expected_run="BEFORE", backup=database, root=root)
    backup = root / "before.sqlite"
    backup.write_bytes(b"keep")
    with pytest.raises(FileExistsError): apply(fixture)
    assert backup.read_bytes() == b"keep"


@pytest.mark.parametrize("failure", ["after_updates", "outside_row", "forbidden_column", "code_hash"])
def test_transaction_rolls_back_and_retains_backup(fixture, monkeypatch, failure):
    root, database, *_ = fixture
    before = snapshot(database)
    if failure == "after_updates":
        monkeypatch.setattr(repair, "finish_run", lambda *args: (_ for _ in ()).throw(ValueError("injected failure")))
    elif failure in {"outside_row", "forbidden_column"}:
        original = repair.begin_run
        def inject(c, *args):
            run = original(c, *args)
            if failure == "outside_row": c.execute(f"UPDATE {repair.TABLE} SET source_file='bad' WHERE rowid=5")
            else: c.execute(f"UPDATE {repair.TABLE} SET votes=99 WHERE rowid=1")
            return run
        monkeypatch.setattr(repair, "begin_run", inject)
    else:
        original, seen = repair.file_sha256, {}
        def changed(path):
            path = str(path)
            seen[path] = seen.get(path, 0) + 1
            return "changed" if path.endswith("repair_sos_cell_lineage.py") and seen[path] > 1 else original(Path(path))
        monkeypatch.setattr(repair, "file_sha256", changed)
    with pytest.raises((ValueError, sqlite3.DatabaseError)): apply(fixture)
    assert snapshot(database) == before
    assert snapshot(root / "before.sqlite") == before
    with sqlite3.connect(database) as c:
        assert c.execute(f"SELECT COUNT(*) FROM {repair.QA}").fetchone() == (0,)
        assert c.execute(f"SELECT COUNT(*) FROM {repair.BUILD}").fetchone() == (1,)


def test_replay_refuses_changed_non_locator_value(fixture):
    root, database, *_ = fixture
    apply(fixture)
    with sqlite3.connect(database) as c:
        c.execute(f"UPDATE {repair.TABLE} SET stable_id='changed' WHERE rowid=1")
    with pytest.raises(ValueError, match="Previously repaired"): repair.repair(database, root=root)


def test_no_blind_replay(fixture):
    root, database, audit, frames, sheets = fixture
    with sqlite3.connect(database) as c:
        changes, _, _ = repair.stage(c, audit, frames, sheets)
        for change in changes:
            c.execute(f"UPDATE {repair.TABLE} SET " + ",".join(f"{k}=?" for k in repair.FIELDS) + " WHERE rowid=?",
                      [change["after"][k] for k in repair.FIELDS] + [change["stored_rowid"]])
    with pytest.raises(ValueError, match="No committed"): repair.repair(database, root=root)
