"""Codex human-language adjudication of the 23 remaining Vote Smart items."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from serve_votesmart_adjudication import DECISION_COLUMNS, MANUAL
from votesmart_position_ontology import ONTOLOGY_VERSION, validate_effect


def effect(axis: str, pole: str, strength: str = "primary", rationale: str = "") -> dict:
    value = {"axis": axis, "pole": pole, "strength": strength, "rationale": rationale}
    validate_effect(value)
    return value


# These decisions use only the original question/option wording. Model labels
# were consulted as review leads but are not authority.
DECISIONS = {
    "086F985BEC634E5D": ("childcare", ["childcare", "business", "taxation"], "childcare_employer_tax_credit", [
        effect("childcare_support", "expansion"), effect("childcare_delivery", "employer_incentive"),
        effect("market_governance", "intervention", "secondary")]),
    "09F1B16E2750CB09": ("abortion", ["abortion", "civil_social"], "abortion_clinic_buffer_zone", [
        effect("abortion_access", "expand"), effect("civil_social_liberty", "restrict", "secondary")]),
    "2E2B3DDA33D38BE7": ("labor", ["labor", "economy"], "reduce_state_employee_compensation", [
        effect("public_employee_compensation", "reduce"), effect("labor_capital_alignment", "capital_management", "secondary")]),
    "2F08B4F9818E6D93": ("criminal_justice", ["criminal_justice"], "marijuana_possession_decriminalization", [
        effect("drug_criminalization", "decriminalize")]),
    "36D1F14014E5B45B": ("energy", ["energy", "business", "environment"], "biofuel_crop_incentives", [
        effect("renewable_energy_support", "expand"), effect("market_governance", "intervention"),
        effect("climate_energy", "decarbonization", "secondary")]),
    "37789D41D1E3635D": ("government_reform", ["government_reform"], "limit_pac_contributions", [
        effect("campaign_finance_restrictions", "strengthen"), effect("institutional_populism", "popular_control", "secondary")]),
    "603FD902D633DD46": ("energy", ["energy", "natural_resources", "business", "environment"], "fund_traditional_energy_development", [
        effect("resource_development", "expand"), effect("climate_energy", "fossil_expansion"),
        effect("market_governance", "intervention", "secondary"), effect("business_scale_alignment", "large_business", "secondary")]),
    "675D5E71D85475BC": ("labor", ["labor", "economy"], "state_employee_furloughs_layoffs", [
        effect("public_employee_compensation", "reduce"), effect("labor_capital_alignment", "capital_management", "secondary")]),
    "7C88115BF8597BFE": ("taxation", ["taxation"], "mid_income_tax_level", [
        effect("tax_burden", "increase")], "ordinal"),
    "7D3BFAF4AB67E2B6": ("immigration", ["immigration", "criminal_justice"], "local_enforcement_federal_immigration_law", [
        effect("immigration_access", "restrict"), effect("criminal_punishment", "punitive", "secondary")]),
    "7FE6E08148272D4E": ("labor", ["labor", "economy"], "reduce_state_employee_compensation", [
        effect("public_employee_compensation", "reduce"), effect("labor_capital_alignment", "capital_management", "secondary")]),
    "850172B3EBD601E2": ("natural_resources", ["natural_resources", "business", "economy"], "agriculture_forestry_research_funding", [
        effect("public_spending", "expand"), effect("resource_management", "active_management"),
        effect("market_governance", "intervention", "secondary")]),
    "86F73CED0D2C803E": ("government_reform", ["government_reform"], "emergency_preparedness_funding", [
        effect("security_preparedness", "expand"), effect("public_spending", "expand")], "ordinal"),
    "90DAFBF66D8125A3": ("government_reform", ["government_reform", "business", "labor"], "regulate_indirect_campaign_contributions", [
        effect("campaign_finance_restrictions", "strengthen"), effect("institutional_populism", "popular_control", "secondary")]),
    "91A39BD191A5FD02": ("energy", ["energy", "natural_resources", "business", "environment"], "fund_traditional_energy_development", [
        effect("resource_development", "expand"), effect("climate_energy", "fossil_expansion"),
        effect("market_governance", "intervention", "secondary"), effect("business_scale_alignment", "large_business", "secondary")]),
    "9213CF20D5CEC9AB": ("government_reform", ["government_reform"], "independent_redistricting_commission", [
        effect("redistricting_governance", "independent_commission"), effect("institutional_populism", "popular_control", "secondary")]),
    "9395B1D2CF02F0D7": ("criminal_justice", ["criminal_justice"], "marijuana_possession_decriminalization", [
        effect("drug_criminalization", "decriminalize")]),
    "9420CEB59F3A5B54": ("childcare", ["childcare", "business", "labor", "taxation"], "childcare_employer_tax_credit", [
        effect("childcare_support", "expansion"), effect("childcare_delivery", "employer_incentive"),
        effect("labor_capital_alignment", "labor", "secondary"), effect("market_governance", "intervention", "secondary")]),
    "A7E047B2B299B4BB": ("immigration", ["immigration", "criminal_justice"], "local_enforcement_federal_immigration_law", [
        effect("immigration_access", "restrict"), effect("criminal_punishment", "punitive", "secondary")]),
    "BA4CFD7BC06EEBC3": ("labor", ["labor", "economy"], "state_employee_furloughs_layoffs", [
        effect("public_employee_compensation", "reduce"), effect("labor_capital_alignment", "capital_management", "secondary")]),
    "DC85E256045D3D09": ("immigration", ["immigration", "criminal_justice"], "local_enforcement_federal_immigration_law", [
        effect("immigration_access", "restrict"), effect("criminal_punishment", "punitive", "secondary")]),
    "E6D2D863E600914F": ("civil_social", ["civil_social"], "restrict_marriage_to_opposite_sex", [
        effect("marriage_equality", "restrict"), effect("civil_social_liberty", "restrict")]),
    "E9798404FBF8E10D": ("government_reform", ["government_reform"], "limit_political_party_contributions", [
        effect("campaign_finance_restrictions", "strengthen"), effect("institutional_populism", "popular_control", "secondary")]),
}


def main() -> None:
    queue = pd.read_csv("data/processed/ideology/votesmart_pct_multiaxis_v2_manual_queue.csv").fillna("")
    queue_ids = set(queue.review_id.astype(str))
    if set(DECISIONS) != queue_ids:
        raise ValueError(f"decision coverage mismatch: missing={queue_ids-set(DECISIONS)}, extra={set(DECISIONS)-queue_ids}")
    metadata = queue.set_index("review_id").to_dict("index")
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for review_id, specification in DECISIONS.items():
        primary, domains, policy_key, position_effects, *mode = specification
        source = metadata[review_id]
        rows.append({
            "ontology_version": ONTOLOGY_VERSION, "review_id": review_id,
            "election_year": source["election_year"],
            "normalized_option": source["normalized_option"], "decision": "adjudicated",
            "primary_domain": primary, "policy_domains_json": json.dumps(domains, separators=(",", ":")),
            "policy_key": policy_key, "effects_json": json.dumps(position_effects, separators=(",", ":")),
            "confidence": "high", "response_mode": mode[0] if mode else "binary",
            "reviewer_notes": "Direct adjudication from original questionnaire wording; model outputs non-authoritative.",
            "reviewed_at_utc": now,
        })
    MANUAL.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows)[DECISION_COLUMNS].to_csv(MANUAL, index=False)
    print(f"Wrote {len(rows)} direct adjudications to {MANUAL}")


if __name__ == "__main__":
    main()
