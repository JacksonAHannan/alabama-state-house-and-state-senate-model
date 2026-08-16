import pandas as pd

from classify_votesmart_pct_items_ollama import build_queue, quote_supported


def test_review_queue_prioritizes_selected_unmapped_items():
    items = pd.DataFrame([
        {"election_year": 1998, "section": "A", "question": "Q", "option_text": "Policy A", "coding_status": "unmapped"},
        {"election_year": 1998, "section": "A", "question": "Q", "option_text": "Policy B", "coding_status": "unmapped"},
    ])
    pct = pd.DataFrame([
        {"election_year": 1998, "section": "A", "question": "Q", "option_text": "Policy A", "votesmart_candidate_id": 1, "selected": False},
        {"election_year": 1998, "section": "A", "question": "Q", "option_text": "Policy B", "votesmart_candidate_id": 2, "selected": True},
    ])
    queue = build_queue(items, pct)
    assert queue.iloc[0].option_text == "Policy B"


def test_quote_verification_requires_source_substring():
    source = "Section: Guns Prompt: Question Option: Require background checks."
    assert quote_supported("Require background checks", source)
    assert not quote_supported("Ban every firearm", source)
