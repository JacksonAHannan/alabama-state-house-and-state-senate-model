"""Raw-source boundary checks only; never execute analytical builders."""
import importlib
import sqlite3

import pytest


BOUNDARIES = [
    ("build_candidate_identity", "main", None),
    ("build_canonical_geographic_weights", "main", None),
    ("build_presidential_district_features", "load_legislative_activity_weights", 2014),
    ("build_1998_2006_context_features", "legislative_weights", 2002),
    ("build_1998_2006_context_features", "_pres2004", None),
]


class ReachedPandas(Exception):
    """Stop at the validated read, before calculation or output."""


def source_row(boundary, **changes):
    module, function, cycle = boundary
    row = dict(source="alabama_sos", year=cycle or 2014,
               office="State House", district=1, votes=0,
               party_norm="D", source_file="fixture.xlsx", source_row=48)
    if function == "_pres2004":
        row.update(year=2004, office="President", district=None)
    row.update(changes)
    return row


def invoke_boundary(tmp_path, monkeypatch, boundary, rows):
    path = tmp_path / "source.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE vote_observations (
            source TEXT, year INTEGER, office TEXT, district INTEGER,
            votes, party_norm TEXT, source_file TEXT, source_row INTEGER)""")
        connection.executemany(
            "INSERT INTO vote_observations VALUES (?,?,?,?,?,?,?,?)",
            [tuple(row.values()) for row in rows])
    module_name, function, cycle = boundary
    module = importlib.import_module(module_name)
    monkeypatch.setattr(module, "DB", path, raising=False)

    def stop(*args, **kwargs):
        raise ReachedPandas

    monkeypatch.setattr(module.pd, "read_sql", stop)
    monkeypatch.setattr(module.pd, "read_sql_query", stop)
    if function == "load_legislative_activity_weights":
        module.load_legislative_activity_weights(path, cycle)
    elif cycle is not None:
        getattr(module, function)(cycle)
    else:
        getattr(module, function)()


@pytest.mark.parametrize("boundary", BOUNDARIES)
@pytest.mark.parametrize("votes,issue", [
    (None, "unknown_missing_votes"), (1.5, "fractional_source_vote"),
    (-1, "negative_source_vote"), ("bad", "nonnumeric_source_vote"),
    (float("inf"), "nonfinite_source_vote"),
])
def test_unusable_source_refused_before_pandas(tmp_path, monkeypatch, boundary, votes, issue):
    with pytest.raises(ValueError, match="Unusable reported votes") as error:
        invoke_boundary(tmp_path, monkeypatch, boundary,
                        [source_row(boundary), source_row(boundary, votes=votes)])
    assert issue in str(error.value)
    assert "fixture.xlsx" in str(error.value)
    assert '"source_row": 48' in str(error.value)


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_reported_zero_passes_boundary(tmp_path, monkeypatch, boundary):
    with pytest.raises(ReachedPandas):
        invoke_boundary(tmp_path, monkeypatch, boundary, [source_row(boundary)])


@pytest.mark.parametrize("boundary", BOUNDARIES)
@pytest.mark.parametrize("dimension", ["source", "year", "office", "district", "party_norm"])
def test_guard_matches_consumed_slice(tmp_path, monkeypatch, boundary, dimension):
    module, function, cycle = boundary
    outside = {"source": "other_provider", "year": 1900, "office": "Governor",
               "district": None, "party_norm": "O"}
    excluded = {"office", "district"}
    if module == "build_canonical_geographic_weights" or cycle is not None:
        excluded |= {"source", "year"}
    if function == "_pres2004":
        excluded = {"source", "year", "office", "party_norm"}
        outside["district"] = 1
    expected = ReachedPandas if dimension in excluded else ValueError
    with pytest.raises(expected):
        invoke_boundary(tmp_path, monkeypatch, boundary, [
            source_row(boundary),
            source_row(boundary, votes=None, **{dimension: outside[dimension]}),
        ])
