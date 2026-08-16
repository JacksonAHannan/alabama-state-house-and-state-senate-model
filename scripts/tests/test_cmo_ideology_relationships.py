import pandas as pd

from scripts.test_cmo_ideology_relationships import coefficient, result_row, zscore


def fixture():
    return pd.DataFrame({
        "person_id": [f"p{i}" for i in range(12)],
        "cycle": [2010] * 6 + [2014] * 6,
        "chamber": ["house", "senate"] * 6,
        "incumbent": [0, 1] * 6,
        "x": list(range(12)),
        "y": [2 * i + (i % 2) for i in range(12)],
    })


def test_zscore_is_centered_and_scaled():
    values = zscore(pd.Series([1, 2, 3, 4]))
    assert abs(values.mean()) < 1e-12
    assert abs(values.std(ddof=0) - 1) < 1e-12


def test_coefficient_recovers_positive_relationship():
    data = fixture()
    assert coefficient(data, "y", "x", []) > 1.5


def test_result_reports_sample_and_direction():
    data = fixture()
    row = result_row(data, "synthetic", "y", "x", [], "positive")
    assert row["n"] == 12
    assert row["people"] == 12
    assert row["direction_matches_hypothesis"]
