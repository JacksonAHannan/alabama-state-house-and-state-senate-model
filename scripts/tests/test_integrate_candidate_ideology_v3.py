import pandas as pd


def test_model_features_are_candidate_unique_and_not_overall_ideology():
    frame = pd.read_csv("data/processed/ideology/candidate_ideology_v3_model_features.csv")
    assert frame.canonical_candidate_id.is_unique
    assert "overall_ideology" not in frame.columns
    assert all(column.startswith("ideology_v3_") or column == "canonical_candidate_id" for column in frame.columns)
