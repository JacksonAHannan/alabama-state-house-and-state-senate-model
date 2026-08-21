import pandas as pd

from scripts.analyze_black_candidate_turnout import (
    adjusted_effect,
    build_review_queue,
    load_labels,
)


def test_manual_candidate_identity_file_is_valid():
    assert load_labels().canonical_candidate_id.is_unique


def test_review_queue_does_not_infer_unreviewed_identity():
    candidates = pd.DataFrame([
        {"canonical_candidate_id": "A", "person_id": "P", "year": 2014,
         "chamber": "house", "district": 1, "canonical_party": "D",
         "canonical_name": "Example", "incumbent": 0, "winner": 0},
    ])
    labels = load_labels()
    queue = build_review_queue(candidates, labels)
    assert len(queue) == 1
    assert queue.iloc[0].race_ethnicity == ""
    assert "Do not infer" in queue.iloc[0].notes


def test_adjusted_effect_recovers_positive_synthetic_signal():
    rows = []
    for i in range(80):
        treated = int(i % 2 == 0)
        rows.append({
            "any_black_candidate": treated,
            "legislative_turnout_cvap": 0.45 + 0.04 * treated + (i % 5) / 1000,
            "cvap_black_share": (i % 10) / 10,
            "cvap_hispanic_share": 0.03,
            "white_college_share": 0.2,
            "prior_pres_dem_margin": -20 + i % 8,
            "dem_incumbent_i": i % 3 == 0,
            "rep_incumbent_i": i % 4 == 0,
            "year": [2014, 2018, 2022][i % 3],
            "chamber": "house" if i % 4 else "senate",
        })
    result = adjusted_effect(pd.DataFrame(rows), "any_black_candidate",
                             "legislative_turnout_cvap")
    assert result["adjusted_mean_difference"] > 0.02
    assert result["overlap_share"] > 0.5
