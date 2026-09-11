"""Network-free tests for the bill-level Luna frontier adjudicator."""
import adjudicate_frontier_bills_luna as bill
from ideology_ontology_v3 import PRIMITIVES


def _item(bill_id="123456"):
    return {"bill_id": bill_id, "session_year": "2019", "bill_number": "HB1",
            "title": "An act", "description": "text"}


def test_norm_bill_id_strips_float_suffix():
    assert bill.norm_bill_id("296541.0") == "296541"
    assert bill.norm_bill_id("296541") == "296541"
    assert bill.norm_bill_id("nan") == ""
    assert bill.norm_bill_id("") == ""


def test_validate_item_accepts_single_map():
    axis = "gun_access"
    pole = PRIMITIVES[axis][0]
    row, reason = bill.validate_item(
        {"decision": "map", "axes": [{"axis": axis, "pole": pole}],
         "confidence": "high", "rationale": "clear"}, _item())
    assert reason is None
    assert row["decision"] == "map"
    assert row["primitive_axes"] == axis and row["policy_poles"] == pole
    assert row["reviewer"] == bill.REVIEWER


def test_validate_item_accepts_multi_axis_and_joins_with_semicolons():
    a1, p1 = "gun_access", PRIMITIVES["gun_access"][0]
    a2, p2 = "abortion_access", PRIMITIVES["abortion_access"][1]
    row, reason = bill.validate_item(
        {"decision": "multi_axis", "confidence": "medium", "rationale": "two",
         "axes": [{"axis": a1, "pole": p1}, {"axis": a2, "pole": p2}]}, _item())
    assert reason is None
    assert row["decision"] == "multi_axis"
    assert row["primitive_axes"] == f"{a1};{a2}"
    assert row["policy_poles"] == f"{p1};{p2}"


def test_validate_item_fails_closed_on_invalid_axis():
    row, reason = bill.validate_item(
        {"decision": "map", "axes": [{"axis": "not_an_axis", "pole": "x"}],
         "confidence": "high", "rationale": "bad"}, _item())
    assert reason is not None and "invalid_axis_pole" in reason
    assert row["decision"] == "mixed_no_scalar_direction"
    assert row["primitive_axes"] == "" and row["policy_poles"] == ""


def test_validate_item_nonscoring_carries_no_axis():
    for decision in ("local_non_generalizable", "procedural", "symbolic"):
        row, reason = bill.validate_item(
            {"decision": decision, "axes": [], "confidence": "high",
             "rationale": "local"}, _item())
        assert reason is None
        assert row["decision"] == decision
        assert row["primitive_axes"] == "" and row["policy_poles"] == ""


def test_validate_item_unknown_decision_falls_to_insufficient_text():
    row, reason = bill.validate_item(
        {"decision": "banana", "axes": [], "confidence": "low", "rationale": "?"}, _item())
    assert reason is not None and "unrecognized_decision" in reason
    assert row["decision"] == "insufficient_text"
    assert row["primitive_axes"] == "" and row["policy_poles"] == ""


def test_build_prompt_lists_ontology_and_echoes_ids():
    prompt = bill.build_prompt([_item("999001"), _item("999002")])
    assert "999001" in prompt and "999002" in prompt
    assert "gun_access" in prompt and "allowed poles" in prompt.lower()
