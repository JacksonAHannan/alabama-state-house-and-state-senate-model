"""Append/replay/retention safeguards use isolated source-only fixture databases.

The fixture mirrors the accepted 2018 shape: 140 contests, 352 certified rows,
322 matched and 30 review rows (29 precinct subtotals below the certified total
plus one certified row with no precinct scope), and an unregistered canvass.
"""
import copy
import json
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

import load_alabama_2018_certified_source as loader
import load_southern_legislative_history_warehouse as history
from warehouse import file_sha256, initialize

PRIOR_PARSER = "alabama_2022_official_results.certified_canvass"


def insert(connection, table, row):
    connection.execute(f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))


@pytest.fixture
def stage(tmp_path, monkeypatch):
    manifest = {"source_file_id": "SRC-CANVASS18", "provider": "alabama_sos", "local_path": "canvass.pdf",
                "source_url": "https://example.test/2018-canvass.pdf", "retrieved_at": "2026-09-08T01:32:33Z",
                "media_type": "application/pdf", "license_or_terms": "review: fixture terms",
                "authoritative_scope": "certified general-election candidate and write-in contest totals",
                "geography_vintage": "reported 2018 districts; no geometry certification"}
    (tmp_path / "canvass.pdf").write_bytes(b"certified fixture 2018")
    manifest["sha256"] = file_sha256(tmp_path / "canvass.pdf")
    (tmp_path / "precinct.zip").write_bytes(b"precinct fixture 2018")
    precinct = {"source_path": "precinct.zip", "sha256": file_sha256(tmp_path / "precinct.zip")}
    registration = {"source_file_id": "SRC-PRECINCT18", "local_path": "precinct.zip", "sha256": precinct["sha256"]}
    for relative in [loader.AUDIT, loader.MANIFEST, loader.EVIDENCE]:
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text("{}")
    evidence = {"audit_sha256": file_sha256(tmp_path / loader.AUDIT),
                "evidence_sha256": file_sha256(tmp_path / loader.EVIDENCE),
                "manifest_sha256": file_sha256(tmp_path / loader.MANIFEST),
                "adapter_code_sha256": {}, "precinct_source": precinct, "precinct_registration": registration,
                "canvass_source": manifest,
                "summary": {"contests": 140, "certified_rows": 352, "precinct_subtotal_review": {"rows": 30}}}
    rows, cells = [], []
    index = 0
    for chamber, count in [("house", 105), ("senate", 35)]:
        for district in range(1, count + 1):
            parties = ["D", "L", "O"] if chamber == "house" and district <= 71 else ["R", "O"]
            for party in parties:
                index += 1
                writein = party == "O"
                printed = "Write-In" if writein else "Example"
                norm = "WRITE IN" if writein else {"D": "JANE EXAMPLE", "L": "JOHN EXAMPLE", "R": "JOAN EXAMPLE"}[party]
                certified = 1 if writein else 10
                mismatch = party == "D" and district <= 29
                observed = certified - 1 if mismatch else certified
                rows.append({"chamber": chamber, "district": district, "party": party,
                    "candidate_norm": norm, "category": "write_in" if writein else "named_candidate",
                    "certified_votes": certified, "observed_votes": observed,
                    "observed_cells": 1, "unknown_cells": 1, "source_cells": 2,
                    "aggregation_status": "observed_cell_subtotal",
                    "reconciliation_status": "review" if mismatch else "matched_certified_total",
                    "reconciliation_reason": "vote_mismatch" if mismatch else loader.MATCHED_REASON,
                    "candidate_alignment_method": "unique_exact_contest_party_category",
                    "canvass_candidate_norm": "WRITE IN" if writein else "EXAMPLE",
                    "canvass_page": 1, "canvass_column": index,
                    "canvass_value_bbox": [index * 10.0, 110.0, index * 10.0 + 5, 120.0],
                    "canvass_header_bbox": [index * 10.0, 90.0, index * 10.0 + 5, 100.0],
                    "canvass_header_text": printed, "canvass_header_token": 0,
                    "canvass_printed_candidate": printed, "canvass_printed_party": None if writein else party})
                for column, value in [(4, observed), (5, None)]:
                    cells.append({"chamber": chamber, "district": district, "category": "write_in" if writein else "named_candidate",
                        "candidate_norm": norm, "cell_kind": "precinct", "source_member": "fixture.xls",
                        "source_sheet": "Precinct Results", "source_row": index, "source_column": column,
                        "county": "Fixture", "precinct": f"P{column}",
                        "printed_party": {"D": "DEM", "R": "REP", "L": "LIB", "O": "NON"}[party],
                        "printed_candidate": norm.title(), "votes": value,
                        "value_status": "unknown" if value is None else "observed"})
    index += 1
    rows.append({"chamber": "senate", "district": 1, "party": "I", "candidate_norm": "ABSENT", "category": "named_candidate",
        "certified_votes": 3, "observed_votes": None, "observed_cells": None, "unknown_cells": None, "source_cells": None,
        "aggregation_status": None, "reconciliation_status": "review", "reconciliation_reason": "missing_precinct_candidate",
        "candidate_alignment_method": loader.ABSENT, "canvass_candidate_norm": "ABSENT",
        "canvass_page": 1, "canvass_column": index,
        "canvass_value_bbox": [index * 10.0, 110.0, index * 10.0 + 5, 120.0],
        "canvass_header_bbox": [index * 10.0, 90.0, index * 10.0 + 5, 100.0],
        "canvass_header_text": "Absent (I)", "canvass_header_token": 0,
        "canvass_printed_candidate": "Absent", "canvass_printed_party": "I"})
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
        for identifier, path, digest in [("SRC-PRECINCT18", "precinct.zip", precinct["sha256"]),
                                         ("SRC-CANVASS22", "prior-canvass.pdf", "0" * 64)]:
            connection.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256) VALUES (?,'fixture',?,?)", (identifier, path, digest))
        # A separately loaded prior cohort shares the source family; it must never be in scope.
        insert(connection, loader.SETS, {"observation_set_id": "AL22SET-PRIOR", "build_run_id": "RUN-BEFORE",
            "source_file_id": "SRC-CANVASS22", "source_member": None, "provider": "alabama_sos", "source_family": loader.FAMILY,
            "authority_rank": 10, "state_code": "AL", "cycle": 2022, "election_date": "2022-11-08", "election_date_status": "observed",
            "election_stage": "general", "election_stage_original": "General Election", "office_code": "SLDL", "chamber": "lower",
            "district_plan_id": "AL-2022-lower-reported-unknown-vintage", "geography_vintage": "fixture", "district": "1",
            "district_original": "1", "source_coverage": "certified_all_candidate_and_write_in_totals", "contest_status": "unknown",
            "parser_name": PRIOR_PARSER, "quality_flags_json": "{}", "validation_status": "review", "as_of_utc": "2026-01-01"})
        insert(connection, loader.CANDIDATES, {"source_candidate_result_id": "AL22CELL-PRIOR", "observation_set_id": "AL22SET-PRIOR",
            "candidate_source_id": "{}", "candidate_name": "Prior", "candidate_name_original": "Prior", "party_family": "republican",
            "party_original": "R", "votes": 5, "vote_share": None, "vote_value_status": "observed", "writein_status": "false",
            "incumbent_status": None, "winner_status": None, "validation_status": "passed", "as_of_utc": "2026-01-01"})
        insert(connection, loader.QA, {"reconciliation_id": "AL22QA-PRIOR", "build_run_id": "RUN-BEFORE", "source_file_id": "SRC-CANVASS22",
            "source_member": None, "state_code": "AL", "cycle": 2022, "parser_name": PRIOR_PARSER, "input_rows": 1,
            "output_candidate_rows": 1, "input_votes": 5, "output_votes": 5, "vote_delta": 0, "unknown_vote_rows": 0,
            "reconciliation_status": "exact", "note": None})
    return tmp_path, database, parsed


def apply(stage, **kwargs):
    root, database, _ = stage
    return loader.append_source(database, apply=True, expected_run="RUN-BEFORE", backup=root / "before.sqlite", root=root, **kwargs)


def register_canvass(database, manifest, *, sha256=None, identity=None, path=None):
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256) VALUES (?,'fixture',?,?)",
                           (identity or manifest["source_file_id"], path or manifest["local_path"], sha256 or manifest["sha256"]))


def counts(connection):
    return {"sets": connection.execute(f"SELECT COUNT(*) FROM {loader.SETS} WHERE cycle=2018").fetchone()[0],
            "candidates": connection.execute(f"SELECT COUNT(*) FROM {loader.CANDIDATES} WHERE source_candidate_result_id LIKE 'AL18CELL-%'").fetchone()[0],
            "qa": connection.execute(f"SELECT COUNT(*) FROM {loader.QA} WHERE parser_name=?", (loader.PARSER,)).fetchone()[0],
            "repair": connection.execute(f"SELECT COUNT(*) FROM {loader.REPAIR}").fetchone()[0],
            "runs": connection.execute("SELECT COUNT(*) FROM warehouse_build_run").fetchone()[0],
            "canvass_registered": connection.execute("SELECT COUNT(*) FROM warehouse_source_file WHERE source_file_id='SRC-CANVASS18'").fetchone()[0]}


def test_literal_counts_review_retention_and_source_only_fields(stage):
    _, _, parsed = stage
    rows, _, manifest, evidence = parsed
    result = loader.cohort(*parsed, "RUN-STAGE", "time")
    assert {k: len(v) for k, v in result.items()} == {loader.SETS: 140, loader.CANDIDATES: 352, loader.QA: 1}
    sets, candidates, qa = result[loader.SETS], result[loader.CANDIDATES], result[loader.QA][0]
    assert all(row["validation_status"] == "review" for row in sets)
    assert {row["cycle"] for row in sets} == {2018} and {row["election_date"] for row in sets} == {"2018-11-06"}
    assert {row["district_plan_id"] for row in sets} == {"AL-2018-lower-reported-unknown-vintage", "AL-2018-upper-reported-unknown-vintage"}
    assert {row["parser_name"] for row in sets} == {loader.PARSER} and {row["source_family"] for row in sets} == {loader.FAMILY}
    # Every certified total is an observed vote value; review rows are retained, not refused.
    assert sum(row["votes"] for row in candidates) == int(rows.certified_votes.sum())
    assert all(row["vote_value_status"] == "observed" for row in candidates)
    assert sum(row["validation_status"] == "review" for row in candidates) == 30
    assert sum(row["validation_status"] == "passed" for row in candidates) == 322
    assert all(row["vote_share"] is row["incumbent_status"] is row["winner_status"] is None for row in candidates)
    # Printed canvass labels only; precinct names stay in evidence.
    assert {row["candidate_name"] for row in candidates} == {"Example", "Write-In", "Absent"}
    assert all(row["candidate_name"] == row["candidate_name_original"] for row in candidates)
    assert sum(row["writein_status"] == "true" for row in candidates) == 140
    assert all(row["party_family"] == "unknown" and row["party_original"] is None for row in candidates if row["writein_status"] == "true")
    assert sum(row["party_original"] == "L" and row["party_family"] == "other" for row in candidates) == 71
    assert sum(row["party_original"] == "I" and row["party_family"] == "independent" for row in candidates) == 1
    assert all(row["source_candidate_result_id"].startswith("AL18CELL-") for row in candidates)
    assert all(row["observation_set_id"].startswith("AL18SET-") for row in sets) and qa["reconciliation_id"].startswith("AL18QA-")
    first = json.loads(sets[0]["quality_flags_json"])
    assert sets[0]["chamber"] == "lower" and sets[0]["district"] == "1"
    assert first["vote_share_denominator"] == 21 and first["denominator_categories"] == ["named_candidate", "write_in"]
    assert first["unknown_precinct_cells_are_zero"] is False
    assert first["precinct_subtotal_review_rows"] == 1 and first["review_reason_counts"] == {"vote_mismatch": 1}
    assert first["evidence_sha256"] == evidence["evidence_sha256"] and first["audit_sha256"] == evidence["audit_sha256"]
    mismatch = first["candidate_evidence"][0]
    assert mismatch["reconciliation_status"] == "review" and mismatch["reconciliation_reason"] == "vote_mismatch"
    assert mismatch["certified_votes"] == 10 and mismatch["observed_votes"] == 9
    assert (mismatch["observed_cells"], mismatch["unknown_cells"], mismatch["source_cells"]) == (1, 1, 2)
    assert mismatch["aligned_candidate_norm"] == "JANE EXAMPLE" and mismatch["canvass_candidate_norm"] == "EXAMPLE"
    assert mismatch["candidate_alignment_method"] == "unique_exact_contest_party_category"
    assert [cell["votes"] for cell in mismatch["precinct_cells"]] == [9, None]
    senate_one = next(row for row in sets if row["chamber"] == "upper" and row["district"] == "1")
    flags = json.loads(senate_one["quality_flags_json"])
    assert flags["precinct_subtotal_review_rows"] == 1 and flags["review_reason_counts"] == {"missing_precinct_candidate": 1}
    absent = next(item for item in flags["candidate_evidence"] if item["reconciliation_reason"] == "missing_precinct_candidate")
    assert absent["observed_votes"] is None and absent["aggregation_status"] is None and absent["precinct_cells"] == []
    assert (absent["observed_cells"], absent["unknown_cells"], absent["source_cells"]) == (0, 0, 0)
    assert absent["candidate_alignment_method"] == loader.ABSENT and absent["certified_votes"] == 3
    assert qa["input_rows"] == qa["output_candidate_rows"] == 352
    assert qa["input_votes"] == qa["output_votes"] == int(rows.certified_votes.sum())
    assert qa["vote_delta"] == 0 and qa["unknown_vote_rows"] == 0 and qa["reconciliation_status"] == "exact"
    note = json.loads(qa["note"])
    assert note["evidence_sha256"] == evidence["evidence_sha256"] and note["canonical_adoption"] == "pending"
    assert note["unknown_precinct_cells_retained"] == 351
    assert note["precinct_subtotal_review"] == {
        "rows": 30, "review_reason_counts": {"vote_mismatch": 29, "missing_precinct_candidate": 1},
        "signed_observed_minus_certified_delta": -29, "absolute_vote_delta": 29,
        "by_category_party": {"named_candidate_D": {"rows": 29, "signed_delta": -29, "absolute_delta": 29},
                              "named_candidate_I": {"rows": 1, "signed_delta": 0, "absolute_delta": 0}}}


def test_ids_use_physical_cells_not_names_or_order(stage):
    _, _, parsed = stage
    before = loader.cohort(*parsed, "run", "time")
    r, cells, manifest, evidence = copy.deepcopy(parsed)
    r.loc[0, "canvass_printed_candidate"] = "Corrected printed spelling"
    after = loader.cohort(r.sample(frac=1, random_state=4), cells, manifest, evidence, "other", "later")
    assert {row["source_candidate_result_id"] for row in before[loader.CANDIDATES]} == {row["source_candidate_result_id"] for row in after[loader.CANDIDATES]}
    assert {row["observation_set_id"] for row in before[loader.SETS]} == {row["observation_set_id"] for row in after[loader.SETS]}


@pytest.mark.parametrize("mutation", ["duplicate", "physical", "status_value", "status_counts", "status_disagrees",
                                      "missing", "null_count", "nan_count", "absent_reason", "observed_mismatch",
                                      "unknown_reason", "party"])
def test_bad_staged_inputs_fail(stage, mutation):
    _, _, parsed = stage
    r, cells, manifest, evidence = copy.deepcopy(parsed)
    r["observed_cells"] = r.observed_cells.astype(object)
    if mutation == "duplicate": r = pd.concat([r, r.iloc[[0]]])
    if mutation == "physical": r.at[1, "canvass_value_bbox"] = r.iloc[0].canvass_value_bbox
    if mutation == "status_value": r.loc[0, "reconciliation_status"] = "unknown"
    if mutation == "status_counts": r.loc[1, "reconciliation_status"] = "review"; r.loc[1, "reconciliation_reason"] = "vote_mismatch"
    if mutation == "status_disagrees":
        # Counts stay 322/30 but a mismatch row claims a match and a matched row claims review.
        r.loc[0, "reconciliation_status"], r.loc[0, "reconciliation_reason"] = "matched_certified_total", loader.MATCHED_REASON
        r.loc[1, "reconciliation_status"], r.loc[1, "reconciliation_reason"] = "review", "vote_mismatch"
    if mutation == "missing": r = r.iloc[1:]
    if mutation == "null_count": r.loc[1, "unknown_cells"] = 0
    if mutation == "nan_count": r.loc[1, "observed_cells"] = None
    if mutation == "absent_reason": r.loc[351, "reconciliation_reason"] = "vote_mismatch"
    if mutation == "observed_mismatch": r.loc[1, "observed_votes"] = 99
    if mutation == "unknown_reason": r.loc[0, "reconciliation_reason"] = "other"
    if mutation == "party": r.loc[1, "party"] = "X"
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


def test_dry_run_and_append_register_canvass_and_preserve_unrelated(stage):
    root, database, (_, _, manifest, _) = stage
    before_bytes = database.read_bytes()
    dry = loader.append_source(database, root=root)
    assert dry["warehouse_status"] == "dry_run" and database.read_bytes() == before_bytes
    assert dry["canvass_registration"] == "insert_pending" and dry["latest_run"] == "RUN-BEFORE"
    assert dry["source_files"]["SRC-CANVASS18"]["registration"] == "insert_pending"
    assert dry["source_files"]["SRC-PRECINCT18"]["registration"] == "present"
    assert dry["staged_counts"] == {loader.SETS: 140, loader.CANDIDATES: 352, loader.QA: 1}
    report = apply(stage)
    assert report["warehouse_status"] == "committed" and report["validation"]["canvass_registration"] == "inserted"
    assert report["configuration"]["canvass_registration"] == "insert_pending"
    with sqlite3.connect(database) as connection, sqlite3.connect(root / "before.sqlite") as backup:
        assert backup.execute("PRAGMA quick_check").fetchall() == [("ok",)]
        assert backup.execute(f"SELECT COUNT(*) FROM {loader.SETS} WHERE cycle=2018").fetchone() == (0,)
        assert backup.execute("SELECT COUNT(*) FROM warehouse_source_file WHERE source_file_id='SRC-CANVASS18'").fetchone() == (0,)
        assert counts(connection) == {"sets": 140, "candidates": 352, "qa": 1, "repair": 1, "runs": 2, "canvass_registered": 1}
        registered = connection.execute(f"SELECT {','.join(loader.REGISTRY_COLUMNS)} FROM warehouse_source_file WHERE source_file_id='SRC-CANVASS18'").fetchone()
        assert registered == tuple(loader.registry_row(manifest).values())
        assert registered[8] == "registered" and registered[3] == manifest["source_url"] and registered[7] == manifest["license_or_terms"]
        assert connection.execute("SELECT COUNT(*) FROM warehouse_source_file").fetchone()[0] == backup.execute("SELECT COUNT(*) FROM warehouse_source_file").fetchone()[0] + 1
        assert connection.execute("SELECT * FROM warehouse_source_file WHERE source_file_id<>'SRC-CANVASS18' ORDER BY rowid").fetchall() == backup.execute("SELECT * FROM warehouse_source_file ORDER BY rowid").fetchall()
        assert connection.execute("SELECT * FROM unrelated").fetchall() == [("preserve",)]
        assert connection.execute("SELECT * FROM warehouse_build_run WHERE build_run_id='RUN-BEFORE'").fetchall() == backup.execute("SELECT * FROM warehouse_build_run").fetchall()
        for table in [loader.SETS, loader.CANDIDATES, loader.QA]:
            prior = f"SELECT * FROM {table} WHERE {'reconciliation_id' if table == loader.QA else 'observation_set_id' if table == loader.SETS else 'source_candidate_result_id'} LIKE 'AL22%'"
            assert connection.execute(prior).fetchall() == backup.execute(prior).fetchall() and len(connection.execute(prior).fetchall()) == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(f"SELECT COUNT(*) FROM {loader.CANDIDATES} c JOIN {loader.SETS} USING(observation_set_id) WHERE cycle=2018 AND c.validation_status='review'").fetchone() == (30,)
        assert connection.execute(f"SELECT status FROM {loader.REPAIR}").fetchall() == [("source_loaded_pending_adoption",)]
    replay = loader.append_source(database, apply=True, expected_run=report["build_run_id"], backup=root / "unused.sqlite", root=root)
    assert replay["warehouse_status"] == "unchanged" and replay["canvass_registration"] == "present"
    assert not (root / "unused.sqlite").exists()


@pytest.mark.parametrize("case", ["matching", "hash", "identity", "path"])
def test_present_registration_must_match_reviewed_evidence(stage, case):
    root, database, (_, _, manifest, _) = stage
    if case == "matching":
        register_canvass(database, manifest)
        assert loader.append_source(database, root=root)["canvass_registration"] == "present"
        report = apply(stage)
        assert report["warehouse_status"] == "committed" and report["validation"]["canvass_registration"] == "present"
        with sqlite3.connect(database) as connection, sqlite3.connect(root / "before.sqlite") as backup:
            assert connection.execute("SELECT * FROM warehouse_source_file ORDER BY rowid").fetchall() == backup.execute("SELECT * FROM warehouse_source_file ORDER BY rowid").fetchall()
            assert counts(connection)["sets"] == 140
        return
    if case == "hash": register_canvass(database, manifest, sha256="f" * 64)
    if case == "identity": register_canvass(database, manifest, identity="SRC-OTHER")
    if case == "path": register_canvass(database, manifest, path="elsewhere.pdf")
    before_bytes = database.read_bytes()
    with pytest.raises(ValueError, match="inconsistent registered source"):
        loader.append_source(database, root=root)
    with pytest.raises(ValueError, match="inconsistent registered source"):
        apply(stage)
    assert database.read_bytes() == before_bytes and not (root / "before.sqlite").exists()


def test_existing_cohort_disagreement_refuses_overwrite(stage):
    root, database, _ = stage
    apply(stage)
    with sqlite3.connect(database) as connection:
        connection.execute(f"UPDATE {loader.CANDIDATES} SET votes=999 WHERE source_candidate_result_id="
                           f"(SELECT source_candidate_result_id FROM {loader.CANDIDATES} WHERE source_candidate_result_id LIKE 'AL18CELL-%' LIMIT 1)")
    with pytest.raises(ValueError, match="conflicts"):
        loader.append_source(database, root=root)


def test_prior_family_cohort_is_outside_scope(stage):
    root, database, _ = stage
    with sqlite3.connect(database) as connection:
        connection.execute(f"UPDATE {loader.CANDIDATES} SET votes=999 WHERE source_candidate_result_id='AL22CELL-PRIOR'")
    assert loader.append_source(database, root=root)["warehouse_status"] == "dry_run"
    assert apply(stage)["warehouse_status"] == "committed"
    with sqlite3.connect(database) as connection:
        assert connection.execute(f"SELECT votes FROM {loader.CANDIDATES} WHERE source_candidate_result_id='AL22CELL-PRIOR'").fetchone() == (999,)


@pytest.mark.parametrize("mutation", ["snapshot", "backup", "source", "precinct_source", "precinct_registration",
                                      "canvass_hash", "trigger", "registry_trigger"])
def test_guard_refusals_precede_live_mutation(stage, mutation):
    root, database, (_, _, manifest, _) = stage
    if mutation == "snapshot":
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE warehouse_build_run SET build_run_id='OTHER'")
    if mutation == "backup": (root / "before.sqlite").write_bytes(b"do not overwrite")
    if mutation == "source": (root / "canvass.pdf").write_bytes(b"changed")
    if mutation == "precinct_source": (root / "precinct.zip").write_bytes(b"changed")
    if mutation == "precinct_registration":
        with sqlite3.connect(database) as connection:
            connection.execute("DELETE FROM warehouse_source_file WHERE source_file_id='SRC-PRECINCT18'")
    if mutation == "canvass_hash": register_canvass(database, manifest, sha256="e" * 64)
    if mutation == "trigger":
        with sqlite3.connect(database) as connection:
            connection.execute(f"CREATE TRIGGER dangerous AFTER INSERT ON {loader.SETS} BEGIN INSERT INTO unrelated VALUES ('bad'); END")
    if mutation == "registry_trigger":
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TRIGGER dangerous AFTER INSERT ON warehouse_source_file BEGIN INSERT INTO unrelated VALUES ('bad'); END")
    with pytest.raises((ValueError, FileExistsError)):
        apply(stage)
    with sqlite3.connect(database) as connection:
        assert counts(connection)["sets"] == 0 and counts(connection)["runs"] == 1
        assert connection.execute("SELECT COUNT(*) FROM warehouse_source_file WHERE sha256=?", (manifest["sha256"],)).fetchone() == (0,)
        assert connection.execute("SELECT * FROM unrelated").fetchall() == [("preserve",)]


def test_application_requires_snapshot_backup_and_existing_database(stage):
    root, database, _ = stage
    with pytest.raises(ValueError, match="requires"):
        loader.append_source(database, apply=True, root=root)
    with pytest.raises(FileNotFoundError):
        loader.append_source(root / "absent.sqlite", root=root)
    assert not (root / "absent.sqlite").exists()


@pytest.mark.parametrize("sql,preregister", [
    ("INSERT INTO unrelated VALUES ('bad')", False),
    ("DELETE FROM warehouse_source_file", False),
    ("CREATE TABLE forbidden(x)", False),
    ("UPDATE warehouse_source_file SET sha256='" + "a" * 64 + "'", False),
    ("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256) VALUES ('SRC-X','f','x.pdf','" + "b" * 64 + "')", True),
])
def test_authorizer_blocks_unowned_actions_and_rolls_back(stage, monkeypatch, sql, preregister):
    root, database, (_, _, manifest, _) = stage
    if preregister:
        register_canvass(database, manifest)
    def forbidden(connection, *args):
        connection.execute(sql)
    monkeypatch.setattr(loader, "begin_run", forbidden)
    with pytest.raises(sqlite3.DatabaseError, match="authorized"):
        apply(stage)
    with sqlite3.connect(database) as connection:
        assert counts(connection)["sets"] == 0 and counts(connection)["runs"] == 1
        assert connection.execute("SELECT COUNT(*) FROM warehouse_source_file").fetchone() == (3 if preregister else 2,)
        assert connection.execute("SELECT * FROM unrelated").fetchall() == [("preserve",)]


def test_failure_after_insert_rolls_back_entire_cohort_and_registration(stage, monkeypatch):
    def fail(*args): raise RuntimeError("injected finish failure")
    monkeypatch.setattr(loader, "finish_run", fail)
    with pytest.raises(RuntimeError, match="injected"):
        apply(stage)
    with sqlite3.connect(stage[1]) as connection:
        assert counts(connection) == {"sets": 0, "candidates": 0, "qa": 0, "repair": 0, "runs": 1, "canvass_registered": 0}


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
        assert counts(connection)["sets"] == 0 and counts(connection)["canvass_registered"] == 0


def test_history_retention_preserves_separately_owned_cohort_and_empty_source_qa(stage):
    root, database, parsed = stage
    apply(stage)
    with sqlite3.connect(database) as connection:
        certified_before = loader.snapshot(connection)
        current = connection.execute("SELECT build_run_id FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone()[0]
        own = loader.cohort(*parsed, current, "time")
        for row in own[loader.SETS][:1]:
            row.update(observation_set_id="OWNED-SET", source_family="medsl_github", parser_name="parse_medsl_precinct_returns")
            insert(connection, loader.SETS, row)
        row = own[loader.CANDIDATES][0]
        row.update(source_candidate_result_id="OWNED-CELL", observation_set_id="OWNED-SET")
        insert(connection, loader.CANDIDATES, row)
        orphan = own[loader.QA][0]
        orphan.update(reconciliation_id="EMPTY-OWNED-QA", source_file_id="SRC-PRECINCT18", parser_name="parse_medsl_precinct_returns",
                      input_rows=0, output_candidate_rows=0, input_votes=0, output_votes=0, reconciliation_status="not_available")
        insert(connection, loader.QA, orphan)
        history.clear_owned_history_sources(connection)
        assert loader.snapshot(connection) == certified_before
        insert(connection, loader.QA, orphan)
        history.clear_owned_history_sources(connection)
        assert loader.snapshot(connection) == certified_before


def test_fixed_evidence_hash_is_required(tmp_path):
    with pytest.raises(ValueError, match="evidence hash"):
        loader.verified_evidence(tmp_path)
    (tmp_path / loader.EVIDENCE).parent.mkdir(parents=True)
    (tmp_path / loader.EVIDENCE).write_text("{}")
    with pytest.raises(ValueError, match="evidence hash"):
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


def test_write_evidence_cli_is_source_only(monkeypatch, capsys):
    def never(*args, **kwargs): raise AssertionError("warehouse opened during evidence write")
    monkeypatch.setattr(loader, "append_source", never)
    monkeypatch.setattr(loader, "write_evidence", lambda: {"sha256": "fixture"})
    assert loader.main(["--write-evidence"]) == 0
    assert json.loads(capsys.readouterr().out) == {"sha256": "fixture"}
    with pytest.raises(ValueError, match="cannot be combined"):
        loader.main(["--write-evidence", "--apply"])
