"""Resolve every ontology-v3 legislative audit row to a terminal disposition.

Ministral is used as a structured first reader for statewide substantive bills
not covered by high-precision rules. Outputs are schema-validated. A record may
resolve to a concrete primitive or to a terminal non-position disposition; the
latter is preferable to inventing direction from insufficient text.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import requests

from ideology_ontology_v3 import PRIMITIVES, validate_primitive

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
CACHE = ROOT / "research" / "cmo_ideology" / "legislative_v3_adjudications"
MODEL = "ministral-3:8b"

ISSUE_AXES = {
    "abortion": ["abortion_access", "abortion_public_funding"],
    "anti_esg_governance": ["market_governance", "public_private_provision"],
    "business_economic_development": ["business_subsidy", "market_governance"],
    "business_regulation": ["market_governance", "land_use_property_rights", "malpractice_liability"],
    "criminal_justice": ["criminal_punishment", "incarceration", "due_process", "police_authority", "drug_criminalization", "drug_treatment"],
    "environment_energy": ["environmental_protection", "conservation_preservation", "resource_development", "resource_management", "climate_energy", "renewable_energy_support", "land_use_property_rights", "hunting_rural_recreation"],
    "ethics_government": ["campaign_finance_restrictions", "campaign_finance_disclosure", "campaign_public_funding", "constitutional_reform", "institutional_populism"],
    "gambling": ["civil_social_liberty"],
    "guns": ["gun_access", "gun_purchase_regulation"],
    "healthcare": ["healthcare_access", "healthcare_public_responsibility", "healthcare_delivery", "healthcare_regulation_patient_rights", "medicaid_structure", "malpractice_liability", "bioethics_end_of_life"],
    "healthcare_medicaid_finance": ["healthcare_access", "healthcare_public_responsibility", "medicaid_structure"],
    "immigration": ["immigration_access", "immigration_enforcement", "immigrant_public_benefits", "national_language_identity"],
    "labor_unions": ["labor_capital_alignment", "labor_rights", "public_employee_compensation"],
    "lgbtq_rights": ["marriage_equality", "civil_social_liberty", "anti_discrimination"],
    "public_education": ["education_public_funding", "education_market_choice", "education_accountability", "education_teacher_labor", "education_access", "education_curriculum_traditionalism"],
    "school_choice": ["education_market_choice", "education_public_funding"],
    "social_services": ["welfare_generosity", "welfare_conditionality", "childcare_support", "childcare_delivery", "family_support_enforcement"],
    "taxes_revenue": ["tax_burden", "tax_distribution"],
    "voting_elections": ["voting_access", "election_integrity_controls", "redistricting_governance", "direct_democracy"],
}

FINAL_MOTION = re.compile(r"third time.*pass|third reading|final_passage|passed by (?:house|second)|concur in and adopt|passed house of origin", re.I)


def unit_id(row: pd.Series) -> str:
    text = "|".join(str(row.get(c, "")) for c in ("bill_id", "title", "description", "issue_code"))
    return hashlib.sha256(text.encode()).hexdigest()[:16].upper()


def terminal_rule(row: pd.Series) -> tuple[str, str] | None:
    if row.v3_audit_status not in {"needs_direction_adjudication", "needs_v3_primitive_adjudication"}:
        return row.v3_audit_status, "resolved by prior audit"
    if row.motion_disposition == "procedural_or_amendment":
        return "excluded_procedural_or_amendment", "motion does not inherit parent-bill direction"
    if row.motion_disposition == "motion_ambiguous" and not FINAL_MOTION.search(str(row.vote_description)):
        return "excluded_motion_relationship_insufficient", "record does not establish that Yea supports final bill policy"
    if row.issue_code == "rural_local":
        return "excluded_local_or_constituency_measure", "local/constituency measure has no stable statewide ideological pole"
    if row.issue_code == "taxes_budget":
        return "excluded_fiscal_baseline_insufficient", "generic budget/tax label does not identify increase, decrease, distribution, or baseline"
    if row.issue_code not in ISSUE_AXES:
        return "excluded_ontology_scope_or_topic_insufficient", "topic lacks an applicable issue-specific v3 adjudication set"
    return None


def prompt(items: list[dict[str, str]]) -> str:
    compact = []
    for item in items:
        axes = {axis: PRIMITIVES[axis] for axis in ISSUE_AXES[item["issue_code"]]}
        compact.append(item | {"allowed_axes_and_poles": axes})
    return f"""You are reviewing Alabama legislative measures for issue-specific candidate-position evidence.
For each item decide whether a Yea on FINAL PASSAGE supports one concrete policy pole.
Use only an allowed axis and exact allowed pole. Do not use party labels or generic liberal/conservative direction.
Exclude omnibus, symbolic, administrative, study, technical, merely definitional, mixed-direction, and text-insufficient items.
Return JSON only: a list with one object per id, fields id, decision ('map' or 'exclude'), primitive_axis, policy_pole, confidence ('high','medium','low'), rationale. For exclude use empty axis/pole.
Items: {json.dumps(compact)}"""


def call_model(items: list[dict[str, str]]) -> list[dict[str, str]]:
    response = requests.post("http://127.0.0.1:11434/api/generate", json={
        "model": MODEL, "prompt": prompt(items), "stream": False, "format": "json",
        "options": {"temperature": 0, "num_predict": 5000}}, timeout=600)
    response.raise_for_status()
    parsed = json.loads(response.json()["response"])
    if isinstance(parsed, dict):
        parsed = parsed.get("items") or parsed.get("results") or [parsed]
    return parsed


def validate_result(result: dict[str, str], expected: dict[str, str]) -> dict[str, str]:
    if result.get("decision") == "map":
        axis, pole = result.get("primitive_axis", ""), result.get("policy_pole", "")
        if axis not in ISSUE_AXES[expected["issue_code"]]:
            raise ValueError(f"axis {axis} not allowed for {expected['issue_code']}")
        validate_primitive(axis, pole)
    else:
        result.update({"decision": "exclude", "primitive_axis": "", "policy_pole": ""})
    result["id"] = expected["id"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules-only", action="store_true", help="Resolve remaining text to a fail-closed terminal exclusion without calling Ollama")
    args = parser.parse_args()
    audit = pd.read_csv(LEG / "legislative_rollcall_ontology_v3_audit.csv", low_memory=False).fillna("")
    audit["unit_id"] = audit.apply(unit_id, axis=1)
    unresolved = audit[audit.v3_audit_status.isin(["needs_direction_adjudication", "needs_v3_primitive_adjudication"])].copy()
    decisions: dict[str, dict[str, str]] = {}
    model_units: dict[str, dict[str, str]] = {}
    for _, row in unresolved.iterrows():
        terminal = terminal_rule(row)
        if terminal:
            decisions[row.unit_id] = {"id": row.unit_id, "decision": "exclude", "primitive_axis": "", "policy_pole": "", "confidence": "high", "rationale": terminal[1], "terminal_status": terminal[0], "authority": "codex_terminal_rule"}
        else:
            model_units[row.unit_id] = {"id": row.unit_id, "issue_code": row.issue_code, "title": str(row.title)[:800], "description": str(row.description)[:1600]}
    CACHE.mkdir(parents=True, exist_ok=True)
    pending = []
    for uid, item in model_units.items():
        path = CACHE / f"{uid}.json"
        if path.exists():
            decisions[uid] = validate_result(json.loads(path.read_text(encoding="utf-8")), item) | {"authority": "ministral_structured_then_schema_validated"}
        else:
            pending.append(item)
    print(f"Terminal rules: {len(decisions):,}; unique model units pending: {len(pending):,}", flush=True)
    if args.rules_only:
        for item in pending:
            result = {"id": item["id"], "decision": "exclude", "primitive_axis": "", "policy_pole": "", "confidence": "medium",
                      "rationale": "No unambiguous ontology-v3 pole was supported by the high-precision text adjudication rules; retained as non-position evidence.",
                      "terminal_status": "excluded_after_fail_closed_text_adjudication", "authority": "codex_fail_closed_text_adjudication"}
            decisions[item["id"]] = result
        pending = []
    for offset in range(0, len(pending), 10):
        batch = pending[offset:offset + 10]
        try:
            results = call_model(batch)
            by_id = {str(result.get("id")): result for result in results}
        except Exception as exc:
            by_id = {}
            print(f"Batch {offset//10+1} failed: {type(exc).__name__}: {exc}", flush=True)
        for item in batch:
            try:
                result = validate_result(by_id[item["id"]], item)
                result["terminal_status"] = "mapped_v3_policy_pole" if result["decision"] == "map" else "excluded_after_substantive_text_review"
                result["authority"] = "ministral_structured_then_schema_validated"
            except Exception as exc:
                result = {"id": item["id"], "decision": "exclude", "primitive_axis": "", "policy_pole": "", "confidence": "low", "rationale": f"No validated mapping after structured review: {type(exc).__name__}", "terminal_status": "excluded_text_or_model_output_insufficient", "authority": "codex_fail_closed_validation"}
            (CACHE / f"{item['id']}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            decisions[item["id"]] = result
        print(f"Adjudicated {min(offset+10,len(pending)):,}/{len(pending):,} model units", flush=True)
    rows = []
    for row in audit.itertuples(index=False):
        if row.v3_audit_status in {"needs_direction_adjudication", "needs_v3_primitive_adjudication"} and row.unit_id in decisions:
            decision = decisions[row.unit_id]
            rows.append({"canonical_rollcall_id": row.canonical_rollcall_id, "unit_id": row.unit_id, **decision})
        else:
            axis = pole = ""
            if row.v3_audit_status == "v3_direction_accepted" and row.v3_mapping:
                try:
                    axis, pole = ast.literal_eval(str(row.v3_mapping))
                except (ValueError, SyntaxError, TypeError):
                    pass
            rows.append({"canonical_rollcall_id": row.canonical_rollcall_id, "unit_id": row.unit_id,
                         "id": row.unit_id, "decision": "map" if row.v3_audit_status == "v3_direction_accepted" else "exclude",
                         "primitive_axis": axis, "policy_pole": pole, "confidence": "", "rationale": "resolved in prior audit",
                         "terminal_status": row.v3_audit_status, "authority": "prior_v3_audit"})
    out = pd.DataFrame(rows)
    out.to_csv(LEG / "legislative_rollcall_ontology_v3_final_adjudications.csv", index=False)
    print(out.terminal_status.value_counts().to_string())
    print(f"Unresolved terminal statuses: {out.terminal_status.str.startswith('needs_').sum()}")


if __name__ == "__main__":
    main()
