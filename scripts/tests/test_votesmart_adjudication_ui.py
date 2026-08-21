from pathlib import Path
import json

import pandas as pd
import pytest

import serve_votesmart_adjudication as ui


def test_load_items_returns_cmo_review_queue():
    items = ui.load_items()

    assert len(items) == 114
    assert len({item["review_id"] for item in items}) == 114
    assert {item["adjudication_status"] for item in items} <= {
        "model_agreement_requires_rule",
        "model_disagreement_requires_review",
    }
    assert all(item["candidate_count"] > 0 for item in items)
    assert "NaN" not in json.dumps(items, allow_nan=False)


def test_save_decision_replaces_existing_review(tmp_path: Path, monkeypatch):
    destination = tmp_path / "manual.csv"
    monkeypatch.setattr(ui, "MANUAL", destination)
    item = ui.load_items()[0]
    base = {
        "review_id": item["review_id"],
        "election_year": item["election_year"],
        "normalized_option": item["normalized_option"],
        "decision": "adjudicated",
        "primary_domain": "economy",
        "effects_json": '[{"axis":"market_governance","pole":"market_autonomy","strength":"primary","rationale":""}]',
        "policy_key": "test_policy",
        "confidence": "high",
        "reviewer_notes": "first",
    }

    ui.save_decision(base)
    ui.save_decision({**base, "reviewer_notes": "revised"})
    saved = pd.read_csv(destination)

    assert len(saved) == 1
    assert saved.loc[0, "reviewer_notes"] == "revised"
    assert "market_autonomy" in saved.loc[0, "effects_json"]


def test_save_decision_validates_axis_pole(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ui, "MANUAL", tmp_path / "manual.csv")

    with pytest.raises(ValueError, match="invalid pole"):
        ui.save_decision({
            "review_id": "example",
            "decision": "adjudicated",
            "primary_domain": "economy",
            "effects_json": '[{"axis":"market_governance","pole":"progressive","strength":"primary","rationale":""}]',
        })


def test_create_server_can_select_free_port():
    server = ui.create_server(0)
    try:
        assert server.server_address[0] == "127.0.0.1"
        assert server.server_address[1] > 0
    finally:
        server.server_close()


def test_auto_consensus_reduces_manual_queue():
    items = ui.load_items()
    automatic = pd.read_csv(ui.AUTO)
    auto_ids = set(automatic.review_id)
    assert len(auto_ids) == 91
    assert sum(item["review_id"] not in auto_ids for item in items) == 23
