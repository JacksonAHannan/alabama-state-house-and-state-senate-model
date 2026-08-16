import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "research" / "cmo_ideology" / "candidate_issue_research_audit.json"


def test_audit_proves_completed_non_llm_layers():
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    requirements = payload["requirements"]
    for layer in [
        "bill_text_archive", "sponsorships", "amendment_attribution_and_text",
        "pre_floor_committee_activity", "matrix_integration",
    ]:
        assert requirements[layer]["complete"], layer


def test_audit_does_not_claim_completion_while_model_stages_are_running():
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    requirements = payload["requirements"]
    if not requirements["amendment_revision_direction"]["complete"]:
        assert not payload["overall_complete"]
    if not requirements["sponsorship_policy_direction"]["complete"]:
        assert not payload["overall_complete"]
    if not requirements["public_campaign_positions"]["complete"]:
        assert not payload["overall_complete"]


def test_human_review_is_a_real_completion_gate():
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    requirements = payload["requirements"]
    amendment = requirements["amendment_revision_direction"]
    sponsorship = requirements["sponsorship_policy_direction"]
    if amendment["complete"]:
        assert amendment["human_reviewed_amendments"] * 2 == amendment["expected_model_cases"]
    if sponsorship["complete"]:
        assert sponsorship["human_reviewed_bills"] == sponsorship["review_bills"]
