import math

import pandas as pd

from build_votesmart_pct_ideology import (
    build_item_crosswalk, candidate_features, classify_item, code_responses, response_sign,
)


def test_clear_policy_items_have_expected_direction():
    assert classify_item("Allow citizens to carry concealed guns.")["affirmative_direction"] == 1
    assert classify_item("Require background checks on gun sales at gun shows.")["affirmative_direction"] == -1
    assert classify_item("Do you generally support pro-choice or pro-life legislation?")["dimension"] == "abortion_position"
    assert classify_item("Other or expanded principles")["coding_status"] == "unmapped"
    assert classify_item("Should abortions be illegal after the first trimester of pregnancy?")["affirmative_direction"] == 1
    assert classify_item("Should abortion be legal only within the first trimester?")["affirmative_direction"] == -1
    assert classify_item("Should voters present photo identification before voting?")["dimension"] == "government_reform_position"
    assert classify_item("College and university admissions", "Affirmative Action", "Should race be considered?")["affirmative_direction"] == -1
    position = classify_item(
        "Support term limits", "Government Reform",
        "Should Alabama limit the number of terms legislators may serve?",
    )
    assert position["coding_status"] == "position_only"
    assert math.isnan(position["affirmative_direction"])


def test_response_sign_does_not_treat_unselected_checkbox_as_no():
    assert response_sign("X", "Allow concealed carry", True) == 1
    assert response_sign("No", "Support gun restrictions", True) == -1
    assert math.isnan(response_sign("", "Support gun restrictions", False))
    assert math.isnan(response_sign("Undecided", "Support gun restrictions", True))


def test_ordinal_budget_and_tax_responses_preserve_intensity():
    item = classify_item("b) Education (K-12)", "State Budget", "Indicate funding levels")
    assert item["response_mode"] == "ordinal"
    assert item["affirmative_direction"] == -1
    assert response_sign("Greatly Increase", "Education (K-12)", True, "ordinal") == 1
    assert response_sign("Slightly Decrease Funding", "Education (K-12)", True, "ordinal") == -0.5
    assert response_sign("Maintain Status", "Corporate taxes", True, "ordinal") == 0
    assert math.isnan(response_sign("Undecided", "Corporate taxes", True, "ordinal"))


def test_negative_response_reverses_affirmative_direction():
    pct = pd.DataFrame([{
        "votesmart_candidate_id": 1, "candidate": "A", "election_year": 2010,
        "section": "Gun Issues", "question": "", "option_number": 1,
        "option_text": "Do you support restrictions on the purchase and possession of guns?",
        "raw_answer": "No", "selected": True, "source_type": "candidate_supplied_pct_response",
        "source_url": "https://example.test",
    }])
    items = build_item_crosswalk(pct)
    coded = code_responses(pct, items).iloc[0]
    assert coded.ideology_score == 1
    assert coded.score_eligible


def test_candidate_features_never_backfills_later_questionnaire():
    coded = pd.DataFrame([{
        "votesmart_candidate_id": 1, "election_year": 1998, "candidate": "A",
        "dimension": "guns_position", "policy_key": "guns_concealed_carry",
        "ideology_score": 1.0, "score_eligible": True,
    }])
    crosswalk = pd.DataFrame([
        {"canonical_candidate_id": "C94", "person_id": "P", "election_year": 1994,
         "votesmart_candidate_id": 1, "accepted": True},
        {"canonical_candidate_id": "C98", "person_id": "P", "election_year": 1998,
         "votesmart_candidate_id": 1, "accepted": True},
    ])
    result = candidate_features(coded, crosswalk).set_index("canonical_candidate_id")
    assert pd.isna(result.loc["C94", "guns_position"])
    assert result.loc["C98", "guns_position"] == 1
