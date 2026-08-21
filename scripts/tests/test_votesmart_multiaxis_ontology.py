import pytest

from classify_votesmart_pct_multiaxis_ollama import prompt, sanitize_result
from adjudicate_votesmart_pct_multiaxis_remaining import DECISIONS
from serve_votesmart_adjudication import load_items
from votesmart_position_ontology import AXES, ONTOLOGY_VERSION, validate_effect


def test_requested_axes_are_distinct():
    assert "market_governance" in AXES
    assert "welfare_policy" in AXES
    assert "business_scale_alignment" in AXES
    assert "childcare_support" in AXES
    assert "environmental_protection" in AXES
    assert "conservation_preservation" in AXES
    assert "resource_management" in AXES
    assert "hunting_rural_recreation" in AXES


def test_prompt_rejects_universal_left_right_framing():
    text = prompt(load_items()[0])
    assert ONTOLOGY_VERSION in text
    assert "Do not label it progressive, conservative" in text
    assert "childcare" in text


def test_effect_validation_is_axis_specific():
    validate_effect({"axis": "welfare_policy", "pole": "expansion", "strength": "primary"})
    with pytest.raises(ValueError):
        validate_effect({"axis": "welfare_policy", "pole": "market_autonomy", "strength": "primary"})


def test_invalid_model_effect_is_removed_and_flagged():
    result, errors = sanitize_result({
        "effects": [{"axis": "welfare_policy", "pole": "market_autonomy",
                     "strength": "primary", "rationale": "bad"}],
        "confidence": "high", "needs_human_review": False, "review_reason": "",
    })
    assert result["effects"] == []
    assert result["needs_human_review"] is True
    assert result["confidence"] == "low"
    assert errors


def test_direct_adjudications_cover_remaining_queue_and_validate():
    assert len(DECISIONS) == 23
    for specification in DECISIONS.values():
        for position_effect in specification[3]:
            validate_effect(position_effect)
