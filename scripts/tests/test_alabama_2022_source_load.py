"""Append/replay/retention safeguards use isolated source-only fixture databases."""
import copy
import json
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

import load_alabama_2022_certified_source as loader
import load_southern_legislative_history_warehouse as history
from warehouse import file_sha256, initialize


@pytest.fixture
def stage(tmp_path, monkeypatch):
    manifest = {"source_file_id": "SRC-CANVASS", "provider": "alabama_sos", "local_path": "canvass.pdf",
                "geography_vintage": "reported 2022 districts; no geometry certification"}
    (tmp_path / "canvass.pdf").write_bytes(b"certified fixture")
    manifest["sha256"] = file_sha256(tmp_path / "canvass.pdf")
    (tmp_path / "precinct.zip").write_bytes(b"precinct fixture")
    precinct = {"source_path": "precinct.zip", "sha256": file_sha256(tmp_path / "precinct.zip")}
    for relative in [loader.AUDIT, loader.MANIFEST]:
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text("{}")
    evidence = {"audit_sha256": file_sha256(tmp_path / loader.AUDIT),
                "manifest_sha256": file_sha256(tmp_path / loader.MANIFEST),
                "adapter_code_sha256": {}, "precinct_source": precinct, "canvass_source": manifest,
                "summary": {"contests": 140, "named_candidates": 211, "write_in_totals": 140}}
    rows, cells = [], []
    index = 0
    for chamber, count in [("house", 105), ("senate", 35)]:
        for district in range(1, count + 1):
            parties = ["D", "L", "O"] if chamber == "house" and district <= 71 else ["R", "O"]
            for party in parties:
                index += 1
                name = "Write-In" if party == "O" else "Jane Example" if party == "D" else "John Example"
                category = "write_in" if party == "O" else "named_candidate"
                norm = "WRITE IN" if party == "O" else name.upper()
                votes = 1 if party == "O" else 10
                rows.append({"chamber": chamber, "district": district, "party": party,
                    "candidate_norm": norm, "category": category, "certified_votes": votes,
                    "canvass_page": 1, "canvass_column": index,
                    "canvass_value_bbox": [index * 10.0, 110.0, index * 10.0 + 5, 120.0],
                    "canvass_header_bbox": [index * 10.0, 90.0, index * 10.0 + 5, 100.0],
                    "canvass_header_text": name, "canvass_header_token": 0,
                    "canvass_printed_candidate": name, "canvass_printed_party": None if party == "O" else party,
                    "observed_cells": 1, "unknown_cells": 1, "aggregation_status": "observed_cell_subtotal",
                    "reconciliation_status": "matched_certified_total"})
                for column, value in [(4, votes), (5, None)]:
                    cells.append({"chamber": chamber, "district": district, "category": category,
                        "candidate_norm": norm, "cell_kind": "precinct", "source_member": "fixture.xls",
                        "source_sheet": "Precinct Results", "source_row": index, "source_column": column,
                        "county": "Fixture", "precinct": f"P{column}",
                        "printed_party": {"D": "DEM", "R": "REP", "L": "LIB", "O": "NON"}[party],
                        "printed_candidate": name, "votes": value,
                        "value_status": "unknown" if value is None else "observed"})
    parsed = (pd.DataFrame(rows), pd.DataFrame(cells), manifest, evidence)
    monkeypatch.setattr(loader, "verified_evidence", lambda root: parsed)
    database = tmp_path / "fixture.sqlite"
    with sqlite3.connect(database) as connection:
        initialize(connection)
        sql = history.SCHEMA.read_text(encoding="utf-8").split("DROP VIEW IF EXISTS")[0]
        connection.executescript(sql)
        connection.execute("CREATE TABLE qa_warehouse_source_repair(issue_id PRIMARY KEY,build_run_id,warehouse_object,scope,status,evidence_json,recorded_at_utc)")
        connection.execute("INSERT INTO warehouse_build_run VALUES ('RUN-BEFORE','fixture','2026-01-01','2026-01-01','validated','fixture','{}','{}')")
        connection.execute("CREATE TABLE unrelated(value)")
        connection.execute("INSERT INTO unrelated VALUES ('preserve')")
        for identifier, path, digest in [("SRC-CANVASS", "canvass.pdf", manifest["sha256"]),
                                         ("SRC-PRECINCT", "precinct.zip", precinct["sha256"])]:
            connection.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256) VALUES (?,'fixture',?,?)", (identifier, path, digest))
    return tmp_path, database, parsed


def apply(stage, **kwargs):
    root, database, _ = stage
    return loader.append_source(database, apply=True, expected_run="RUN-BEFORE", backup=root / "before.sqlite", root=root, **kwargs)


def test_literal_counts_and_source_only_fields(stage):
    _, _, parsed = stage
    result = loader.cohort(*parsed, "RUN-STAGE", "time")
    assert {k: len(v) for k, v in result.items()} == {loader.SETS: 140, loader.CANDIDATES: 351, loader.QA: 1}
    assert all(row["validation_status"] == "review" for row in result[loader.SETS])
    assert all(row["vote_share"] is row["incumbent_status"] is row["winner_status"] is None for row in result[loader.CANDIDATES])
    first = json.loads(result[loader.SETS][0]["quality_flags_json"])
    assert first["vote_share_denominator"] == 21
    assert first["denominator_categories"] == ["named_candidate", "write_in"]
    assert first["unknown_precinct_cells_are_zero"] is False
    assert first["candidate_evidence"][0]["unknown_cells"] == 1
    assert any(row["party_original"] == "L" and row["party_family"] == "other" for row in result[loader.CANDIDATES])
    assert sum(row["writein_status"] == "true" for row in result[loader.CANDIDATES]) == 140


def test_ids_use_physical_cells_not_names_or_order(stage):
    _, _, parsed = stage
    before = loader.cohort(*parsed, "run", "time")
    r, cells, manifest, evidence = copy.deepcopy(parsed)
    r.loc[0, "canvass_printed_candidate"] = "Corrected printed spelling"
    after = loader.cohort(r.sample(frac=1, random_state=4), cells, manifest, evidence, "other", "later")
    assert {row["source_candidate_result_id"] for row in before[loader.CANDIDATES]} == {row["source_candidate_result_id"] for row in after[loader.CANDIDATES]}
    assert {row["observation_set_id"] for row in before[loader.SETS]} == {row["observation_set_id"] for row in after[loader.SETS]}


@pytest.mark.parametrize("mutation", ["duplicate", "physical", "review", "missing", "null_count"])
def test_bad_staged_inputs_fail(stage, mutation):
    _, _, parsed = stage
    r, cells, manifest, evidence = copy.deepcopy(parsed)
    if mutation == "duplicate": r = pd.concat([r, r.iloc[[0]]])
    if mutation == "physical": r.at[1, "canvass_value_bbox"] = r.iloc[0].canvass_value_bbox
    if mutation == "review": r.loc[0, "reconciliation_status"] = "review"
    if mutation == "missing": r = r.iloc[1:]
    if mutation == "null_count": r.loc[0, "unknown_cells"] = 0
    with pytest.raises(ValueError):
        loader.cohort(r, cells, manifest, evidence, "run", "time")


@pytest.mark.parametrize("value", [-1, 1.5, None, float("inf")])
def test_malformed_certified_vote_cannot_be_truncated(stage, value):
    _, _, parsed = stage
    r, cells, manifest, evidence = copy.deepcopy(parsed)
    r["certified_votes"] = r.certified_votes.astype(object)
    r.loc[0, "certified_votes"] = value
    with pytest.raises(ValueError, match="Malformed certified"):
        loader.cohort(r, cells, manifest, evidence, "run", "time")


def test_dry_run_and_append_preserve_unrelated_sources_and_controls(stage):
    root, database, _ = stage
    before_bytes = database.read_bytes()
    dry = loader.append_source(database, root=root)
    assert dry["warehouse_status"] == "dry_run" and database.read_bytes() == before_bytes
    report = apply(stage)
    assert report["warehouse_status"] == "committed"
    with sqlite3.connect(database) as connection, sqlite3.connect(root / "before.sqlite") as backup:
        assert backup.execute("PRAGMA quick_check").fetchall() == [("ok",)]
        assert backup.execute(f"SELECT COUNT(*) FROM {loader.SETS}").fetchone() == (0,)
        assert connection.execute(f"SELECT COUNT(*) FROM {loader.SETS}").fetchone() == (140,)
        assert connection.execute(f"SELECT COUNT(*) FROM {loader.CANDIDATES}").fetchone() == (351,)
        assert connection.execute(f"SELECT COUNT(*) FROM {loader.QA}").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM warehouse_build_run").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM qa_warehouse_source_repair").fetchone() == (1,)
        assert connection.execute("SELECT * FROM unrelated").fetchall() == [("preserve",)]
        assert connection.execute("SELECT * FROM warehouse_source_file").fetchall() == backup.execute("SELECT * FROM warehouse_source_file").fetchall()
        assert connection.execute("SELECT * FROM warehouse_build_run WHERE build_run_id='RUN-BEFORE'").fetchall() == backup.execute("SELECT * FROM warehouse_build_run").fetchall()
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    replay = loader.append_source(database, apply=True, expected_run=report["build_run_id"], backup=root / "unused.sqlite", root=root)
    assert replay["warehouse_status"] == "unchanged" and not (root / "unused.sqlite").exists()


def test_existing_cohort_disagreement_refuses_overwrite(stage):
    root, database, _ = stage
    apply(stage)
    with sqlite3.connect(database) as connection:
        connection.execute(f"UPDATE {loader.CANDIDATES} SET votes=999 WHERE rowid=1")
    with pytest.raises(ValueError, match="conflicts"):
        loader.append_source(database, root=root)


@pytest.mark.parametrize("mutation", ["snapshot", "backup", "source", "registration", "trigger"])
def test_guard_refusals_precede_live_mutation(stage, mutation):
    root, database, _ = stage
    if mutation == "snapshot":
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE warehouse_build_run SET build_run_id='OTHER'")
    if mutation == "backup": (root / "before.sqlite").write_bytes(b"do not overwrite")
    if mutation == "source": (root / "canvass.pdf").write_bytes(b"changed")
    if mutation == "registration":
        with sqlite3.connect(database) as connection:
            connection.execute("DELETE FROM warehouse_source_file WHERE source_file_id='SRC-CANVASS'")
    if mutation == "trigger":
        with sqlite3.connect(database) as connection:
            connection.execute(f"CREATE TRIGGER dangerous AFTER INSERT ON {loader.SETS} BEGIN INSERT INTO unrelated VALUES ('bad'); END")
    with pytest.raises((ValueError, FileExistsError)):
        apply(stage)
    with sqlite3.connect(database) as connection:
        assert connection.execute(f"SELECT COUNT(*) FROM {loader.SETS}").fetchone() == (0,)
        assert connection.execute("SELECT * FROM unrelated").fetchall() == [("preserve",)]


def test_application_requires_snapshot_backup_and_existing_database(stage):
    root, database, _ = stage
    with pytest.raises(ValueError, match="requires"):
        loader.append_source(database, apply=True, root=root)
    with pytest.raises(FileNotFoundError):
        loader.append_source(root / "absent.sqlite", root=root)
    assert not (root / "absent.sqlite").exists()


@pytest.mark.parametrize("sql", ["INSERT INTO unrelated VALUES ('bad')", "DELETE FROM warehouse_source_file", "CREATE TABLE forbidden(x)"])
def test_authorizer_blocks_unowned_actions_and_rolls_back(stage, monkeypatch, sql):
    def forbidden(connection, *args):
        connection.execute(sql)
    monkeypatch.setattr(loader, "begin_run", forbidden)
    with pytest.raises(sqlite3.DatabaseError, match="authorized"):
        apply(stage)
    with sqlite3.connect(stage[1]) as connection:
        assert connection.execute(f"SELECT COUNT(*) FROM {loader.SETS}").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM warehouse_build_run").fetchone() == (1,)


def test_failure_after_insert_rolls_back_entire_cohort(stage, monkeypatch):
    def fail(*args): raise RuntimeError("injected finish failure")
    monkeypatch.setattr(loader, "finish_run", fail)
    with pytest.raises(RuntimeError, match="injected"):
        apply(stage)
    with sqlite3.connect(stage[1]) as connection:
        for table in [loader.SETS, loader.CANDIDATES, loader.QA, loader.REPAIR]:
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM warehouse_build_run").fetchone() == (1,)


def test_prior_build_mutation_is_detected_and_rolled_back(stage, monkeypatch):
    original = loader.finish_run
    def corrupt(connection, *args):
        original(connection, *args)
        connection.execute("UPDATE warehouse_build_run SET target='bad' WHERE build_run_id='RUN-BEFORE'")
    monkeypatch.setattr(loader, "finish_run", corrupt)
    with pytest.raises(ValueError, match="Append changed prior"):
        apply(stage)
    with sqlite3.connect(stage[1]) as connection:
        assert connection.execute("SELECT target FROM warehouse_build_run").fetchall() == [("fixture",)]
        assert connection.execute(f"SELECT COUNT(*) FROM {loader.SETS}").fetchone() == (0,)


def test_history_retention_preserves_separately_owned_cohort_and_empty_source_qa(stage):
    root, database, parsed = stage
    apply(stage)
    with sqlite3.connect(database) as connection:
        certified_before = loader.snapshot(connection)
        current = connection.execute("SELECT build_run_id FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone()[0]
        own = loader.cohort(*parsed, current, "time")
        for row in own[loader.SETS][:1]:
            row.update(observation_set_id="OWNED-SET", source_family="medsl_github", parser_name="parse_medsl_precinct_returns")
            cols = list(row)
            connection.execute(f"INSERT INTO {loader.SETS} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", tuple(row.values()))
        row = own[loader.CANDIDATES][0]
        row.update(source_candidate_result_id="OWNED-CELL", observation_set_id="OWNED-SET")
        connection.execute(f"INSERT INTO {loader.CANDIDATES} ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
        orphan = own[loader.QA][0]
        orphan.update(reconciliation_id="EMPTY-OWNED-QA", source_file_id="SRC-PRECINCT", parser_name="parse_medsl_precinct_returns", input_rows=0, output_candidate_rows=0, input_votes=0, output_votes=0, reconciliation_status="not_available")
        def insert_empty():
            connection.execute(f"INSERT INTO {loader.QA} ({','.join(orphan)}) VALUES ({','.join('?' for _ in orphan)})", tuple(orphan.values()))
        insert_empty()
        history.clear_owned_history_sources(connection)
        assert loader.snapshot(connection) == certified_before
        insert_empty()
        history.clear_owned_history_sources(connection)
        assert loader.snapshot(connection) == certified_before


def test_fixed_audit_hash_is_required(tmp_path):
    (tmp_path / loader.AUDIT).parent.mkdir(parents=True)
    (tmp_path / loader.AUDIT).write_text("{}")
    with pytest.raises(ValueError, match="audit hash"):
        loader.verified_evidence(tmp_path)


def test_default_cli_does_not_apply(monkeypatch, capsys):
    seen = {}
    def fake(database, **kwargs):
        seen.update(kwargs)
        return {"warehouse_status": "dry_run"}
    monkeypatch.setattr(loader, "append_source", fake)
    assert loader.main([]) == 0
    assert seen["apply"] is False
    assert json.loads(capsys.readouterr().out)["warehouse_status"] == "dry_run"
