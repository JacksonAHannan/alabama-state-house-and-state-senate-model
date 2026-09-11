import csv
import sqlite3
from contextlib import closing

import build_data_catalog as catalog


def test_catalog_has_no_duplicate_lineage_declarations():
    assert len(catalog.LINEAGE) == len(set(catalog.LINEAGE))


def test_catalog_export_and_sync_are_idempotent(tmp_path, monkeypatch):
    database = tmp_path / "warehouse.sqlite"
    monkeypatch.setenv("ALABAMA_WAREHOUSE_PATH", str(database))
    monkeypatch.setattr(catalog, "ROOT", tmp_path)
    (tmp_path / "project_docs").mkdir()

    catalog.main()
    output = tmp_path / "project_docs" / "data_catalog.csv"
    original = output.read_bytes()
    catalog.main()
    assert output.read_bytes() == original
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    assert rows[0] == [
        "asset_id", "asset_kind", "layer", "locator", "owner_script",
        "key_description", "status", "replacement_asset_id", "notes",
    ]
    assert rows[1:] == [["" if value is None else value for value in row]
                       for row in catalog.ASSETS]
    with closing(sqlite3.connect(database)) as connection:
        assert set(connection.execute("select * from warehouse_asset")) == set(catalog.ASSETS)
        assert set(connection.execute("select * from warehouse_asset_lineage")) == set(catalog.LINEAGE)
        assert connection.execute("pragma foreign_key_check").fetchall() == []
