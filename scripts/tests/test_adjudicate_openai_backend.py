"""Network-free tests for the OpenAI backend of the v3 legislative adjudicator."""
import json
import os

import pytest

import adjudicate_legislative_ontology_v3_all as adj
from ideology_ontology_v3 import PRIMITIVES


def _valid_axis_pole(issue_code):
    for axis in adj.ISSUE_AXES[issue_code]:
        if axis in PRIMITIVES and PRIMITIVES[axis]:
            return axis, PRIMITIVES[axis][0]
    raise AssertionError("no valid axis/pole")


def test_call_model_openai_parses_items_and_records_usage(monkeypatch):
    axis, pole = _valid_axis_pole("guns")
    captured = {}

    def fake_chat(key, model, user_prompt):
        captured["model"] = model
        captured["prompt"] = user_prompt
        adj.USAGE["api_requests"] += 1
        return json.dumps({"items": [
            {"id": "U1", "decision": "map", "primitive_axis": axis, "policy_pole": pole,
             "confidence": "high", "rationale": "clear final-passage pole"},
        ]})

    monkeypatch.setattr(adj, "openai_chat", fake_chat)
    adj.USAGE["api_requests"] = 0
    items = [{"id": "U1", "issue_code": "guns", "title": "An act", "description": "text"}]
    out = adj.call_model_openai(items, "gpt-5.6-luna", "sk-test")
    assert isinstance(out, list) and out[0]["id"] == "U1"
    assert captured["model"] == "gpt-5.6-luna"
    assert "guns" not in captured["prompt"].lower() or "allowed_axes_and_poles" in captured["prompt"]
    assert adj.USAGE["api_requests"] == 1


def test_validate_result_enforces_allowed_axis():
    axis, pole = _valid_axis_pole("healthcare")
    ok = adj.validate_result(
        {"id": "U2", "decision": "map", "primitive_axis": axis, "policy_pole": pole},
        {"id": "U2", "issue_code": "healthcare"})
    assert ok["decision"] == "map" and ok["primitive_axis"] == axis
    with pytest.raises(ValueError):
        adj.validate_result(
            {"id": "U3", "decision": "map", "primitive_axis": "not_an_axis", "policy_pole": "x"},
            {"id": "U3", "issue_code": "healthcare"})
    exc = adj.validate_result({"id": "U4", "decision": "exclude"}, {"id": "U4", "issue_code": "guns"})
    assert exc["decision"] == "exclude" and exc["primitive_axis"] == ""


def test_load_openai_key_prefers_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-value")
    assert adj.load_openai_key() == "sk-env-value"


def test_openai_chat_never_places_key_in_body(monkeypatch):
    seen = {}

    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "{\"items\": []}"}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url; seen["headers"] = headers; seen["body"] = json
        return Resp()

    monkeypatch.setattr(adj.requests, "post", fake_post)
    content = adj.openai_chat("sk-secret", "gpt-5.6-luna", "prompt text")
    assert content == "{\"items\": []}"
    assert seen["url"] == adj.OPENAI_ENDPOINT
    assert seen["headers"]["Authorization"] == "Bearer sk-secret"
    assert "sk-secret" not in json.dumps(seen["body"])
    assert seen["body"]["model"] == "gpt-5.6-luna"
