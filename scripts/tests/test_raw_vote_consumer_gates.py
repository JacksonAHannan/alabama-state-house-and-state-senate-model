"""Input refusal only: never execute downstream analysis or matching."""
import importlib
import sqlite3

import pytest


@pytest.mark.parametrize('module_name,entry', [
    ('build_canonical_cmo_features', 'main'),
    ('analyze_canonical_baselines', 'source_votes'),
    ('build_adjacent_precinct_alias_graph', 'nodes_and_turnout'),
    ('build_historical_precinct_adjudication_queue', 'activity'),
])
def test_fractional_source_refused_before_pandas_or_outputs(tmp_path, monkeypatch, module_name, entry):
    module = importlib.import_module(module_name)
    path = tmp_path / 'source.sqlite'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE vote_observations (source,year,office,district,votes)')
        connection.execute('INSERT INTO vote_observations VALUES (?,?,?,?,?)',
                           ('alabama_sos', 1994, 'Attorney General', None, 144.4))
    before = path.read_bytes()
    monkeypatch.setattr(module, 'DB', path)
    def forbidden(*args, **kwargs):
        pytest.fail('Downstream read or calculation reached before source refusal')
    monkeypatch.setattr(module.pd, 'read_sql', forbidden)
    monkeypatch.setattr(module.pd, 'read_sql_query', forbidden)
    with pytest.raises(ValueError, match='fractional'):
        if entry == 'source_votes':
            with sqlite3.connect(path) as connection:
                module.source_votes(connection)
        else:
            getattr(module, entry)()
    assert path.read_bytes() == before
