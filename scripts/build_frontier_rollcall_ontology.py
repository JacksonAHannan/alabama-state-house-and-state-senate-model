"""Translate frontier bill review into canonical roll-call ideology evidence.

The frontier ledger is authoritative for bill meaning.  Its deliberately
specific labels are retained verbatim, while a conservative translation layer
admits only recognizable issue/pole pairs into ontology v3.  Every roll call
receives either one or more auditable mappings or an explicit non-scoring
disposition.  Legacy model classifications are never consulted.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ideology_ontology_v3 import PRIMITIVES, validate_primitive

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
MANUAL = ROOT / "data" / "manual" / "ideology" / "frontier_legislative_bill_adjudications.csv"
OUT = LEG / "frontier_rollcall_ontology_v3.csv"


def words(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def has(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text))


def canonical_mapping(axis: str, pole: str) -> tuple[str, str, str] | None:
    """Return (axis, pole, rule) only for an unambiguous translation."""
    a, p = words(axis), words(pole)
    if a in PRIMITIVES and p in PRIMITIVES[a]:
        return a, p, "exact_ontology_v3_pair"

    # Social and cultural rights.
    if has(a, r"abortion"):
        if has(p, r"restrict|prohibit|ban|criminal|funding_prohibit|protect_unborn"):
            return "abortion_access", "restrict", "abortion_restriction"
        if has(p, r"expand|protect_access|repeal_restriction|permiss"):
            return "abortion_access", "expand", "abortion_expansion"
    if has(a, r"christian_sexual|sexual_morality"):
        if has(p, r"traditional|restrict|prohibit|strengthen"):
            return "christian_sexual_morality", "traditional_morality", "sexual_morality_traditional"
        if has(p, r"plural|autonomy|expand|relax"):
            return "christian_sexual_morality", "sexual_pluralism_autonomy", "sexual_morality_pluralist"
    if has(a, r"racial_civil_right|racial_equal|civil_rights_racial"):
        if has(p, r"expand|strengthen|protect|enforce"):
            return "racial_civil_rights", "expand", "racial_rights_expansion"
        if has(p, r"restrict|weaken|limit|repeal"):
            return "racial_civil_rights", "restrict", "racial_rights_restriction"
    if has(a, r"lgbt|same_sex|gender_identity|sexual_orientation"):
        if has(p, r"restrict|prohibit|ban|traditional|biological"):
            return "civil_social_liberty", "restrict", "lgbtq_restriction"
        if has(p, r"expand|protect|recogn|nondiscrimination|plural"):
            return "civil_social_liberty", "expand", "lgbtq_expansion"
    if has(a, r"religion_state|religious_(?:liberty|accommodation)"):
        if has(p, r"accommod|expand|protect|permit"):
            return "religion_state", "accommodation_establishment", "religious_accommodation"
        if has(p, r"separat|restrict|prohibit"):
            return "religion_state", "separation", "religion_state_separation"

    # Guns and public order are intentionally separate.
    if has(a, r"gun|firearm|pistol|second_amendment"):
        if has(a, r"purchase|background|storage"):
            if has(p, r"strengthen|require|expand|regulat"):
                return "gun_purchase_regulation", "strengthen", "gun_purchase_controls"
            if has(p, r"weaken|repeal|relax|exempt"):
                return "gun_purchase_regulation", "weaken", "gun_purchase_deregulation"
        if has(p, r"expand|protect|permitless|preempt|relax|exempt|authorize"):
            return "gun_access", "expand", "gun_access_expansion"
        if has(p, r"restrict|prohibit|ban|limit|regulat"):
            return "gun_access", "restrict", "gun_access_restriction"
    if has(a, r"criminal_punishment|punitive|penalt|sentenc|incarcer|death_penalty|public_order|law_and_order|stalking|assault|homicide|sex_crime"):
        if has(p, r"punitive|increase|expand|enhance|felony|criminalize|mandatory|restrict_parole|elevate|strengthen_enforcement"):
            return "criminal_punishment", "punitive", "punishment_expansion"
        if has(p, r"rehabil|reduce|decriminal|expung|relief|lenien|exclude_nonfelony|narrow|reentry"):
            return "criminal_punishment", "rehabilitative", "punishment_reduction"
    if has(a, r"due_process|notice_and_appeal|access_to_justice"):
        if has(p, r"strengthen|expand|require|protect|add"):
            return "due_process", "strengthen", "due_process_expansion"
        if has(p, r"weaken|restrict|limit|remove"):
            return "due_process", "weaken", "due_process_restriction"
    if has(a, r"police_authority|law_enforcement_authority"):
        if has(p, r"expand|authorize|strengthen"):
            return "police_authority", "expand", "police_authority_expansion"
        if has(p, r"restrict|limit|reduce"):
            return "police_authority", "restrict", "police_authority_restriction"

    # Immigration and elections.
    if has(a, r"immigration|lawful_presence|undocumented"):
        if has(a, r"benefit"):
            if has(p, r"expand|allow|include"):
                return "immigrant_public_benefits", "expand", "immigrant_benefits_expansion"
            if has(p, r"restrict|deny|prohibit"):
                return "immigrant_public_benefits", "restrict", "immigrant_benefits_restriction"
        if has(p, r"strengthen|restrict|require|invalidate|enforce|verify|prohibit"):
            return "immigration_enforcement", "strengthen", "immigration_enforcement_expansion"
        if has(p, r"relax|reduce|permit|recognize"):
            return "immigration_enforcement", "relax", "immigration_enforcement_relaxation"
    if has(a, r"voting_access|voter_registration|absentee|ballot_access"):
        if has(p, r"expand|allow|restore|extend|facilitate"):
            return "voting_access", "expand", "voting_access_expansion"
        if has(p, r"restrict|limit|shorten|prohibit|require"):
            return "voting_access", "restrict", "voting_access_restriction"
    if has(a, r"election_integrity|election_control|voter_id"):
        if has(p, r"strengthen|require|expand|verify"):
            return "election_integrity_controls", "strengthen", "election_controls_expansion"
        if has(p, r"weaken|relax|remove|reduce"):
            return "election_integrity_controls", "weaken", "election_controls_relaxation"
    if has(a, r"campaign_finance.*(?:disclosure|transparency)"):
        if has(p, r"strengthen|expand|require"):
            return "campaign_finance_disclosure", "strengthen", "campaign_disclosure_expansion"
        if has(p, r"weaken|restrict|reduce"):
            return "campaign_finance_disclosure", "weaken", "campaign_disclosure_restriction"

    # Political economy and public provision. Targeted tax preferences remain
    # issue evidence only unless the pole unambiguously changes tax liability.
    if has(a, r"labor_right|collective_bargain|union"):
        if has(p, r"expand|protect|authorize|support"):
            return "labor_rights", "expand", "labor_rights_expansion"
        if has(p, r"restrict|prohibit|weaken|right_to_work"):
            return "labor_rights", "restrict", "labor_rights_restriction"
    if has(a, r"public_employee_(?:compensation|benefit)|state_employee_compensation"):
        if has(p, r"protect|expand|increase|raise|restore"):
            return "public_employee_compensation", "protect", "public_employee_support"
        if has(p, r"reduce|cut|restrict|exclude"):
            return "public_employee_compensation", "reduce", "public_employee_retrenchment"
    if has(a, r"education_(?:public_)?funding|public_education_(?:investment|spending)|higher_education.*funding"):
        if has(p, r"expand|increase|fund|appropriate|invest|protect"):
            return "education_public_funding", "expand", "public_education_expansion"
        if has(p, r"reduce|cut|restrict|redirect"):
            return "education_public_funding", "reduce", "public_education_reduction"
    if has(a, r"school_choice|education_market_choice|private_school_choice"):
        if has(p, r"expand|authorize|establish|fund|credit"):
            return "education_market_choice", "expand", "school_choice_expansion"
        if has(p, r"restrict|prohibit|reduce|repeal"):
            return "education_market_choice", "restrict", "school_choice_restriction"
    if has(a, r"education_access"):
        if has(p, r"expand|allow|include"):
            return "education_access", "expand", "education_access_expansion"
        if has(p, r"restrict|deny|limit"):
            return "education_access", "restrict", "education_access_restriction"
    if has(a, r"welfare_conditional"):
        if has(p, r"strengthen|require|restrict"):
            return "welfare_conditionality", "strengthen_conditions", "welfare_conditions_strengthen"
        if has(p, r"relax|remove|reduce"):
            return "welfare_conditionality", "relax_conditions", "welfare_conditions_relax"
    if has(a, r"public_assistance|welfare_generosity|social_services|childrens_services_public_funding"):
        if has(p, r"expand|increase|fund|allow|extend"):
            return "welfare_generosity", "expand", "material_support_expansion"
        if has(p, r"restrict|reduce|cut|deny"):
            return "welfare_generosity", "restrict", "material_support_restriction"
    if has(a, r"healthcare_access|medicaid_eligibility|rural_healthcare_access|maternal_healthcare_access"):
        if has(p, r"expand|increase|allow|extend"):
            return "healthcare_access", "expand", "healthcare_access_expansion"
        if has(p, r"restrict|reduce|deny|limit"):
            return "healthcare_access", "restrict", "healthcare_access_restriction"
    if has(a, r"occupational_(?:licensing|regulation|scope)|scope_of_practice"):
        if has(p, r"repeal|reduce|relax|exempt|expand_scope|allow|recognize"):
            return "market_governance", "market_autonomy", "occupational_market_autonomy"
        if has(p, r"require|strengthen|regulat|restrict_scope|license"):
            return "market_governance", "intervention", "occupational_regulation"
    if has(a, r"business_subsid|industrial_policy|targeted_.*(?:incentive|subsid)|economic_development_incentive"):
        if has(p, r"expand|authorize|fund|credit|establish|increase"):
            return "business_subsidy", "expand", "business_subsidy_expansion"
        if has(p, r"restrict|repeal|reduce|prohibit"):
            return "business_subsidy", "restrict", "business_subsidy_restriction"
    if has(a, r"tax_(?:general_sales|personal_income|property|corporate|business)|tax_burden"):
        if has(p, r"increase|raise|levy|apply|broaden"):
            return "tax_burden", "increase", "tax_increase"
        if has(p, r"decrease|reduce|exempt|credit|deduct|relief|repeal|narrow"):
            return "tax_burden", "decrease", "tax_decrease"
    if has(a, r"public_spending|public_infrastructure_investment|public_health_spending"):
        if has(p, r"expand|increase|fund|invest|appropriate"):
            return "public_spending", "expand", "public_spending_expansion"
        if has(p, r"reduce|cut|restrict"):
            return "public_spending", "reduce", "public_spending_reduction"

    # Environment, land, and governance.
    if has(a, r"environmental_protection|pollution"):
        if has(p, r"strengthen|expand|protect|reduce_emission|regulat"):
            return "environmental_protection", "strengthen", "environmental_protection_expansion"
        if has(p, r"weaken|relax|exempt|limit"):
            return "environmental_protection", "weaken", "environmental_protection_reduction"
    if has(a, r"property_right"):
        if has(p, r"expand|protect|strengthen|limit_regulation"):
            return "land_use_property_rights", "property_rights", "property_rights_expansion"
        if has(p, r"regulat|restrict|limit"):
            return "land_use_property_rights", "regulation", "land_use_regulation"
    if has(a, r"government_(?:ethics|accountability|transparency)|public_records_access|open_government"):
        if has(p, r"strengthen|expand|require|increase"):
            return "government_ethics_transparency", "strengthen", "government_transparency_expansion"
        if has(p, r"weaken|restrict|reduce|exempt"):
            return "government_ethics_transparency", "weaken", "government_transparency_restriction"
    return None


def split_pairs(row: pd.Series) -> list[tuple[str, str]]:
    axes = [x.strip() for x in str(row.primitive_axes or "").split(";") if x.strip()]
    poles = [x.strip() for x in str(row.policy_poles or "").split(";") if x.strip()]
    return list(zip(axes, poles)) if len(axes) == len(poles) else []


def main() -> None:
    calls = pd.read_csv(LEG / "comprehensive_rollcall_classifications.csv", low_memory=False)
    manual = pd.read_csv(MANUAL, low_memory=False).fillna("")
    manual = manual[["bill_id", "decision", "primitive_axes", "policy_poles", "confidence", "rationale", "reviewed_document_type", "reviewer"]]
    manual = manual.rename(columns={"reviewed_document_type": "text_basis"})
    calls = calls.merge(manual, on="bill_id", how="left", validate="many_to_one")
    missing_link = calls.decision.isna() & calls.bill_id.notna()
    if missing_link.any():
        missing = calls.loc[missing_link, "bill_id"].unique()
        raise ValueError(f"{len(missing)} linked roll-call bills lack frontier adjudication")
    # Pre-LegiScan journal roll calls do not have a LegiScan bill_id and cannot
    # inherit a frontier bill review. Keep them visible as a separate terminal
    # disposition instead of pretending they were reviewed through this path.
    calls["decision"] = calls.decision.fillna("no_frontier_bill_link")
    for column in ["primitive_axes", "policy_poles", "confidence", "rationale", "text_basis", "reviewer"]:
        calls[column] = calls[column].fillna("")

    rows: list[dict[str, object]] = []
    for row in calls.itertuples(index=False):
        base = {
            "canonical_rollcall_id": row.canonical_rollcall_id, "bill_id": row.bill_id,
            "session_year": row.session_year, "chamber": row.chamber,
            "bill_number": row.bill_number, "vote_description": row.vote_description,
            "frontier_bill_decision": row.decision, "frontier_axes": row.primitive_axes,
            "frontier_poles": row.policy_poles, "frontier_confidence": row.confidence,
            "frontier_rationale": row.rationale, "frontier_text_basis": row.text_basis,
        }
        if row.motion_disposition != "bill_direction_applies":
            rows.append(base | {"decision": "exclude", "primitive_axis": "", "policy_pole": "",
                                "translation_rule": "motion_not_final_policy_support",
                                "terminal_status": "excluded_procedural_or_ambiguous_motion"})
            continue
        if row.decision not in {"map", "multi_axis"}:
            rows.append(base | {"decision": "exclude", "primitive_axis": "", "policy_pole": "",
                                "translation_rule": "frontier_explicit_non_scoring_disposition",
                                "terminal_status": f"excluded_frontier_{row.decision}"})
            continue
        pairs = split_pairs(pd.Series(row._asdict()))
        translated = [(a, p, canonical_mapping(a, p)) for a, p in pairs]
        admitted = [(a, p, m) for a, p, m in translated if m]
        if not admitted:
            rows.append(base | {"decision": "exclude", "primitive_axis": "", "policy_pole": "",
                                "translation_rule": "no_conservative_canonical_translation",
                                "terminal_status": "excluded_issue_specific_not_scalarized"})
            continue
        for source_axis, source_pole, mapping in admitted:
            axis, pole, rule = mapping
            validate_primitive(axis, pole)
            rows.append(base | {"decision": "map", "primitive_axis": axis, "policy_pole": pole,
                                "source_axis": source_axis, "source_pole": source_pole,
                                "translation_rule": rule, "terminal_status": "mapped_frontier_policy_pole"})

    out = pd.DataFrame(rows)
    historical_path = LEG / "historical_frontier_rollcall_ontology_v3.csv"
    if historical_path.exists():
        historical = pd.read_csv(historical_path, low_memory=False).fillna("")
        historical_ids = set(historical.canonical_rollcall_id.astype(str))
        out = pd.concat([
            out[~out.canonical_rollcall_id.astype(str).isin(historical_ids)],
            historical,
        ], ignore_index=True, sort=False)
    mapped = out.decision.eq("map")
    pole_counts = (out[mapped].groupby(["canonical_rollcall_id", "primitive_axis"])
                   .policy_pole.transform("nunique"))
    conflict_index = pole_counts[pole_counts.gt(1)].index
    if len(conflict_index):
        out.loc[conflict_index, "decision"] = "exclude"
        out.loc[conflict_index, ["primitive_axis", "policy_pole"]] = ""
        out.loc[conflict_index, "translation_rule"] = "conflicting_canonical_poles"
        out.loc[conflict_index, "terminal_status"] = "excluded_conflicting_canonical_poles"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    covered = set(calls.canonical_rollcall_id.astype(str))
    emitted = set(out.canonical_rollcall_id.astype(str))
    if covered != emitted:
        raise AssertionError("frontier roll-call output does not cover the input universe")
    summary = out.groupby(["decision", "terminal_status"]).canonical_rollcall_id.nunique().reset_index(name="rollcalls")
    summary.to_csv(LEG / "frontier_rollcall_ontology_v3_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Input roll calls: {len(calls):,}; mapped roll calls: {out.loc[out.decision.eq('map'),'canonical_rollcall_id'].nunique():,}; rows: {len(out):,}")


if __name__ == "__main__":
    main()
