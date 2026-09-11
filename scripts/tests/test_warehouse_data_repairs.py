import sqlite3
from pathlib import Path
import pytest

from shapely.geometry import Polygon

from warehouse import initialize, register_source_file


def test_registration_does_not_invent_acquisition_time(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("value\n1\n")
    with sqlite3.connect(":memory:") as connection:
        initialize(connection)
        identifier = register_source_file(connection, provider="fixture", path=source, project_root=tmp_path)
        assert connection.execute("SELECT retrieved_at_utc FROM warehouse_source_file").fetchone() == (None,)
        register_source_file(connection, provider="fixture", path=source, project_root=tmp_path,
                             retrieved_at_utc="2000-01-01T00:00:00Z")
        register_source_file(connection, provider="fixture", path=source, project_root=tmp_path)
        assert connection.execute("SELECT retrieved_at_utc FROM warehouse_source_file WHERE source_file_id=?",
                                  (identifier,)).fetchone() == ("2000-01-01T00:00:00Z",)


def test_registration_does_not_erase_known_provenance(tmp_path):
    source = tmp_path/'source.csv'
    source.write_text('value\n1\n')
    with sqlite3.connect(':memory:') as connection:
        initialize(connection)
        register_source_file(connection, provider='fixture', path=source, project_root=tmp_path,
                             original_url='https://example.org/source.csv', license_name='fixture terms',
                             authoritative_scope='fixture observations', media_type='text/csv')
        register_source_file(connection, provider='fixture', path=source, project_root=tmp_path)
        assert connection.execute('SELECT original_url,license,authoritative_scope,media_type FROM warehouse_source_file').fetchone() == (
            'https://example.org/source.csv', 'fixture terms', 'fixture observations', 'text/csv')


def test_storage_geometry_repairs_collapsed_rings_without_lines():
    from load_southern_2016_vest_warehouse import storage_geometry
    shape = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)],
                    [[(.5, .5), (1, 1), (.5, .5)]])
    assert not shape.is_valid
    repaired = storage_geometry(shape)
    assert repaired.is_valid and not repaired.is_empty
    assert repaired.geom_type in {"Polygon", "MultiPolygon"}
    assert repaired.area == 4
    assert storage_geometry(repaired).wkb == repaired.wkb


def test_finance_sql_masks_incomplete_inputs_without_erasing_source_amounts():
    schema = (Path(__file__).resolve().parents[1] / "warehouse_southern_war_preparation_schema.sql").read_text()
    view = schema.split("DROP VIEW IF EXISTS mart_southern_war_training_with_finance;")[1].split(
        "DROP VIEW IF EXISTS qa_southern_war_training_with_finance_coverage;")[0]
    with sqlite3.connect(":memory:") as connection:
        connection.executescript("""
          CREATE TABLE mart_southern_war_training_no_finance(state_code,cycle,chamber,district,training_status);
          CREATE TABLE mart_southern_race_finance(state_code,cycle,chamber,district,
            democratic_candidate_result_id,republican_candidate_result_id,
            democratic_fundraising,republican_fundraising,democratic_finance_status,
            republican_finance_status,finance_complete,log_fundraising_ratio_d_to_r,
            smoothing_constant,race_finance_status);
          INSERT INTO mart_southern_war_training_no_finance VALUES ('XX',2000,'lower','1','fixture');
          INSERT INTO mart_southern_race_finance VALUES ('XX',2000,'lower','1',NULL,NULL,
            100,NULL,'observed','unknown',0,NULL,1,'incomplete');
        """)
        connection.executescript(view)
        assert connection.execute("SELECT democratic_fundraising,republican_fundraising,log_fundraising_ratio_d_to_r FROM mart_southern_war_training_with_finance").fetchone() == (None, None, None)
        assert connection.execute("SELECT democratic_fundraising FROM mart_southern_race_finance").fetchone() == (100,)


def test_roll_call_quality_checks_categories_not_only_total():
    schema = (Path(__file__).resolve().parents[1] / "warehouse_legislative_quality.sql").read_text()
    with sqlite3.connect(":memory:") as connection:
        connection.executescript("""
          CREATE TABLE source_legiscan_roll_call(roll_call_id,source_file_id,source_member,total,yea,nay,not_voting,absent);
          CREATE TABLE source_legiscan_member_vote(roll_call_id,people_id,vote_id);
          INSERT INTO source_legiscan_roll_call VALUES (1,'fixture','vote.json',2,2,0,0,0);
          INSERT INTO source_legiscan_member_vote VALUES (1,1,1),(1,2,2);
        """)
        connection.executescript(schema)
        assert connection.execute("SELECT validation_status FROM qa_legiscan_roll_call_reconciliation").fetchone() == ('review',)
        assert connection.execute("SELECT COUNT(*) FROM canonical_legiscan_member_vote").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM source_legiscan_member_vote").fetchone() == (2,)
        connection.execute("UPDATE source_legiscan_roll_call SET yea=1,nay=1")
        assert connection.execute("SELECT COUNT(*) FROM canonical_legiscan_member_vote").fetchone() == (2,)


def test_repair_ddl_preserves_transaction_rollback():
    from repair_warehouse_source_defects import execute_statements
    with sqlite3.connect(':memory:') as connection:
        connection.execute('CREATE TABLE original(value)')
        connection.execute('INSERT INTO original VALUES (1)')
        connection.commit()
        connection.execute('BEGIN IMMEDIATE')
        execute_statements(connection, 'CREATE TABLE repair(value);\nINSERT INTO repair VALUES (2);\n')
        connection.execute('DELETE FROM original')
        connection.rollback()
        assert connection.execute('SELECT * FROM original').fetchall() == [(1,)]
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='repair'").fetchall() == []


def test_repair_refuses_existing_backup_before_any_database_access(tmp_path):
    from repair_warehouse_source_defects import repair
    backup = tmp_path/'before.sqlite'
    backup.write_bytes(b'preserved backup')
    with pytest.raises(FileExistsError):
        repair(tmp_path/'absent.sqlite', backup)
    assert backup.read_bytes() == b'preserved backup'
    assert not (tmp_path/'absent.sqlite').exists()


def test_source_repair_staging_reconciles_all_vote_cells():
    from repair_warehouse_source_defects import stage_votes
    from warehouse import connect
    from contextlib import closing
    with closing(connect(readonly=True)) as connection:
        staged, sources, checks = stage_votes(connection)
    assert staged.groupby('year').size().to_dict() == {1994: 150753, 2002: 2950, 2014: 11059}
    assert len(checks) == 164
    assert all(check['reported'] == check['precinct_sum'] for check in checks)
    assert len(sources) == 3
    assert staged[['source_file', 'source_sheet', 'source_row', 'source_column']].notna().all().all()
