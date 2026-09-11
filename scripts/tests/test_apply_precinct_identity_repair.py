import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from scripts import apply_precinct_identity_repair as repair
from scripts import stage_precinct_identity_repair as staging
from scripts.build_precinct_identity import build_nodes, match_sources
from scripts.tests.test_precinct_identity import identity_fixture, observations


def fixture_stage(tmp_path):
    votes, _, _, _, _ = identity_fixture()
    votes = pd.concat([votes, observations().assign(year=2014, county_key='JEFFERSON'),
                       observations().assign(year=2014, county_key='JEFFERSON', source='openelections')], ignore_index=True)
    nodes, fingerprints = build_nodes(votes)
    candidates, links = match_sources(nodes, fingerprints, 'alabama_sos', 'openelections')
    links['relationship'] = 'one_to_one'
    retired = int(nodes.query("year==1994 and source=='alabama_sos' and precinct_key=='002 B'").node_id.iloc[0])
    direct = int(nodes.query("year==2014 and source=='alabama_sos' and precinct_key=='002 B'").node_id.iloc[0])
    untouched = int(nodes.query("year==2014 and source=='alabama_sos' and precinct_key=='001 A'").node_id.iloc[0])
    database = tmp_path / 'warehouse.sqlite'
    with sqlite3.connect(database) as connection:
        frames = dict(zip(repair.IDENTITY, (nodes, fingerprints, candidates, links)))
        frames['vote_observations'] = votes
        frames['precinct_geography_match_candidates'] = pd.DataFrame({'source_node_id': [retired, direct, untouched], 'geo_node_id': [1, 2, 3]})
        frames['precinct_geography_links'] = frames['precinct_geography_match_candidates'].assign(match_method='exact_name', accepted=1)
        raw = pd.DataFrame([[retired, '000001', 'source_transfer'], [direct, '000002', 'direct_geography'],
                            [direct, '000099', 'source_transfer'], [untouched, '000003', 'direct_geography']],
                           columns=['source_node_id', 'vtd', 'evidence'])
        frames['canonical_geography_evidence'] = raw
        frames['canonical_precinct_geography_links'] = raw[raw.source_node_id.ne(direct)]
        frames['precinct_geography_conflicts'] = raw[raw.source_node_id.eq(direct)]
        frames['geographic_precinct_nodes'] = pd.DataFrame({'geo_node_id': [1, 2, 3], 'vtd': ['000001', '000002', '000003'],
            'geography_name': ['A', 'B', 'C'], 'geography_source': ['fixture'] * 3})
        frames['unrelated_domain'] = pd.DataFrame({'id': [1], 'value': ['preserve me']})
        for name, frame in frames.items():
            frame.to_sql(name, connection, index=False)
        connection.execute('CREATE TABLE warehouse_build_run(build_run_id TEXT PRIMARY KEY,target TEXT,started_at_utc TEXT,completed_at_utc TEXT,status TEXT,code_commit TEXT,configuration_json TEXT,validation_json TEXT)')
        connection.execute('CREATE TABLE qa_warehouse_source_repair(issue_id TEXT PRIMARY KEY,build_run_id TEXT,warehouse_object TEXT,scope TEXT,status TEXT,evidence_json TEXT,recorded_at_utc TEXT)')
        connection.execute("UPDATE vote_observations SET precinct_key='002 B UPDATED' WHERE source='alabama_sos' AND year=1994 AND precinct_key='002 B'")
        connection.execute("UPDATE vote_observations SET votes=votes+5 WHERE source='alabama_sos' AND year=2014 AND precinct_key='002 B'")
    directory = tmp_path / 'stage'
    staging.stage(database, directory)
    return database, directory, repair.file_sha256(directory / 'manifest.json'), retired, direct, untouched


def snapshot(database):
    with sqlite3.connect(database) as connection:
        return {name: connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
                for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def test_apply_preserves_unrelated_rows_revokes_transfers_and_exports(tmp_path):
    database, directory, accepted, retired, direct, untouched = fixture_stage(tmp_path)
    before = snapshot(database)
    for name in repair.EXPORTS:
        (tmp_path / name).write_text('old export\n', encoding='utf-8')
    backup = tmp_path / 'before.sqlite'
    result = repair.apply(database, directory, backup, accepted)
    assert result['exports_status'] == 'complete'
    assert snapshot(backup) == before
    after = snapshot(database)
    for name in ('unrelated_domain', 'vote_observations', 'geographic_precinct_nodes'):
        assert after[name] == before[name]
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT count(*) FROM precinct_nodes WHERE node_id=?', (retired,)).fetchone()[0] == 0
        for name in repair.GEOGRAPHY:
            assert connection.execute(f'SELECT count(*) FROM {name} WHERE source_node_id=?', (retired,)).fetchone()[0] == 0
        assert connection.execute('SELECT vtd,evidence FROM canonical_geography_evidence WHERE source_node_id=?', (direct,)).fetchall() == [('000002', 'direct_geography')]
        assert connection.execute('SELECT vtd,evidence FROM canonical_precinct_geography_links WHERE source_node_id=?', (direct,)).fetchall() == [('000002', 'direct_geography')]
        assert connection.execute('SELECT count(*) FROM precinct_geography_conflicts WHERE source_node_id=?', (direct,)).fetchone()[0] == 0
        assert connection.execute('SELECT accepted FROM precinct_geography_links WHERE source_node_id=?', (direct,)).fetchone()[0] == 1
        assert connection.execute('SELECT accepted FROM precinct_source_links WHERE left_node_id=?', (direct,)).fetchone()[0] == 0
        assert connection.execute('SELECT status FROM warehouse_build_run').fetchone()[0] == 'validated'
    for name, item in result['outputs'].items():
        assert repair.file_sha256(tmp_path / name) == item['sha256']
        assert (tmp_path / f'before.sqlite.{name}').read_text() == 'old export\n'


def test_apply_validation_failure_rolls_back_every_owned_change(tmp_path, monkeypatch):
    database, directory, accepted, *_ = fixture_stage(tmp_path)
    before = snapshot(database)
    def fail(*args):
        raise ValueError('injected post-write validation failure')
    monkeypatch.setattr(repair, 'validate', fail)
    with pytest.raises(ValueError, match='injected'):
        repair.apply(database, directory, tmp_path / 'before.sqlite', accepted)
    assert snapshot(database) == before
    assert snapshot(tmp_path / 'before.sqlite') == before
    assert not (tmp_path / repair.EXPORTS[0]).exists()


@pytest.mark.parametrize('change', ['source', 'output', 'manifest', 'metadata'])
def test_apply_refuses_stale_or_unaccepted_stage(tmp_path, change):
    database, directory, accepted, *_ = fixture_stage(tmp_path)
    if change == 'source':
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE vote_observations SET votes=votes+1 WHERE year=1994")
    elif change == 'output':
        with (directory / 'precinct_nodes.csv').open('a') as stream:
            stream.write('tampered\n')
    elif change == 'manifest':
        accepted = '0' * 64
    else:
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE precinct_nodes SET name_norm='CHANGED' WHERE year=2014")
    before = snapshot(database)
    with pytest.raises(ValueError):
        repair.apply(database, directory, tmp_path / 'before.sqlite', accepted)
    assert snapshot(database) == before
    assert not (tmp_path / 'before.sqlite').exists()


def test_apply_existing_backup_is_refused_before_source_access(tmp_path):
    backup = tmp_path / 'before.sqlite'
    backup.write_bytes(b'keep')
    with pytest.raises(FileExistsError):
        repair.apply(tmp_path / 'missing.sqlite', tmp_path / 'missing-stage', backup, '0' * 64)
    assert backup.read_bytes() == b'keep'
    assert not (tmp_path / 'missing.sqlite').exists()


def test_changed_2014_metadata_blocks_retaining_direct_geography(tmp_path):
    database, _, _, _, direct, _ = fixture_stage(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE precinct_nodes SET name_norm='DIFFERENT PRIOR METADATA' WHERE node_id=?", (direct,))
    directory = tmp_path / 'restaged'
    staging.stage(database, directory)
    accepted = repair.file_sha256(directory / 'manifest.json')
    before = snapshot(database)
    with pytest.raises(AssertionError):
        repair.apply(database, directory, tmp_path / 'before.sqlite', accepted)
    assert snapshot(database) == before
    assert not (tmp_path / 'before.sqlite').exists()


def test_owned_table_trigger_is_rejected_without_widening_scope(tmp_path):
    database, directory, accepted, *_ = fixture_stage(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TRIGGER unrelated_delete AFTER DELETE ON precinct_nodes BEGIN DELETE FROM unrelated_domain; END')
    before = snapshot(database)
    with pytest.raises(ValueError, match='Triggers'):
        repair.apply(database, directory, tmp_path / 'before.sqlite', accepted)
    assert snapshot(database) == before


def test_apply_export_failure_is_explicit_after_database_commit(tmp_path, monkeypatch):
    database, directory, accepted, *_ = fixture_stage(tmp_path)
    original = pd.DataFrame.to_csv
    def fail_export(self, path_or_buf=None, *args, **kwargs):
        if isinstance(path_or_buf, Path) and path_or_buf.name in repair.EXPORTS:
            raise OSError('injected export failure')
        return original(self, path_or_buf, *args, **kwargs)
    monkeypatch.setattr(pd.DataFrame, 'to_csv', fail_export)
    result = repair.apply(database, directory, tmp_path / 'before.sqlite', accepted)
    assert result['warehouse_status'] == 'committed'
    assert result['exports_status'] == 'failed_after_commit'
    report = json.loads((tmp_path / 'before.sqlite.application.json').read_text())
    assert report['exports_status'] == 'failed_after_commit'
    with sqlite3.connect(database) as connection:
        validation = json.loads(connection.execute('SELECT validation_json FROM warehouse_build_run').fetchone()[0])
    assert validation['exports'] == 'failed_after_commit'
