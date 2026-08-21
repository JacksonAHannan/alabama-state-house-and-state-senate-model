"""Frontier-style adjudication for 1998–2009 journal roll calls.

Historical journal records lack LegiScan bill IDs.  This module uses the exact
measure identity and recovered synopsis, never the legacy ideological fields.
High-precision text rules admit an issue pole; every other item receives an
auditable non-scoring disposition.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ideology_ontology_v3 import validate_primitive

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
OUT = LEG / "historical_frontier_rollcall_ontology_v3.csv"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def match(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.I | re.S))


NOISE = re.compile(
    r"^(?:was |and )?(?:adopted|lost|tabled|carried over|concurred|again read|as thus amended|passed|withdrawn)\b",
    re.I,
)


def classify_synopsis(value: object) -> dict[str, str]:
    text = clean(value)
    if len(text) < 24 or NOISE.search(text):
        return {"decision": "exclude", "primitive_axis": "", "policy_pole": "",
                "translation_rule": "recovered_text_not_substantive",
                "terminal_status": "excluded_historical_insufficient_text"}
    if match(text, r"\b(?:honoring|commending|congratulating|welcoming|mourning|recognizing)\b|designat(?:e|ing).{0,50}(?:day|week|month)"):
        return {"decision": "exclude", "primitive_axis": "", "policy_pole": "",
                "translation_rule": "ceremonial_resolution", "terminal_status": "excluded_historical_symbolic"}
    if match(text, r"^(?:relating to|to amend.{0,80}relating to) (?:the )?[A-Z][A-Za-z .'-]+ County\b|\blocal constitutional amendment\b"):
        return {"decision": "exclude", "primitive_axis": "", "policy_pole": "",
                "translation_rule": "county_specific_measure", "terminal_status": "excluded_historical_local"}
    if match(text, r"\b(?:make|making) an appropriation\b|general appropriations? bill|education budget|general fund budget"):
        return {"decision": "exclude", "primitive_axis": "", "policy_pole": "",
                "translation_rule": "appropriation_baseline_not_identified", "terminal_status": "excluded_historical_budget_baseline"}

    rules: list[tuple[str, str, str, str]] = [
        (r"\babortion\b.{0,160}(?:prohibit|ban|criminal|parental consent)|(?:prohibit|ban).{0,120}\babortion\b|unborn (?:child|life)", "abortion_access", "restrict", "abortion_restriction"),
        (r"repeal.{0,120}(?:abortion prohibition|abortion ban)|protect.{0,100}(?:abortion access|reproductive choice)", "abortion_access", "expand", "abortion_expansion"),
        (r"(?:concealed|pistol|firearm|handgun).{0,160}(?:permit|carry).{0,80}(?:allow|authorize|reciprocity)|right to (?:keep and )?bear arms|firearm preemption", "gun_access", "expand", "gun_access_expansion"),
        (r"(?:prohibit|restrict|ban).{0,100}(?:firearm|handgun|pistol)|(?:firearm|gun).{0,100}(?:background check|safe storage)", "gun_access", "restrict", "gun_access_restriction"),
        (r"(?:increase|enhance|provide).{0,100}(?:criminal penalt|felony|mandatory minimum)|death penalty|capital (?:offense|murder)|without parole", "criminal_punishment", "punitive", "punishment_expansion"),
        (r"(?:reduce|decrease).{0,100}(?:criminal penalt|sentence)|decriminaliz|expung|record sealing|expand.{0,100}(?:parole|probation)|alternative sentencing", "criminal_punishment", "rehabilitative", "punishment_reduction"),
        (r"(?:collective bargaining|labor organization|union).{0,140}(?:authorize|protect|recognize)|prevailing wage", "labor_rights", "expand", "labor_rights_expansion"),
        (r"right.to.work|(?:prohibit|restrict).{0,100}(?:collective bargaining|union dues|labor organization)|repeal.{0,80}prevailing wage", "labor_rights", "restrict", "labor_rights_restriction"),
        (r"(?:salary|pay|compensation|cost.of.living).{0,120}(?:increase|raise).{0,80}(?:state employees|teachers|education employees)|(?:state employees|teachers).{0,100}(?:salary|pay) increase", "public_employee_compensation", "protect", "public_employee_compensation_expansion"),
        (r"(?:reduce|decrease|freeze).{0,100}(?:state employee|teacher).{0,80}(?:pay|benefit|compensation)", "public_employee_compensation", "reduce", "public_employee_compensation_reduction"),
        (r"charter schools?|school choice|private schools?.{0,100}(?:tax credit|scholarship)|tuition (?:grant|tax credit)", "education_market_choice", "expand", "school_choice_expansion"),
        (r"(?:increase|provide|appropriate).{0,100}(?:funding|funds).{0,100}(?:public schools|classroom|teachers)|teacher pay (?:raise|increase)", "education_public_funding", "expand", "public_education_expansion"),
        (r"(?:reduce|cut|decrease).{0,100}(?:funding|appropriation).{0,100}(?:public schools|education)", "education_public_funding", "reduce", "public_education_reduction"),
        (r"(?:levy|increase|raise|additional).{0,100}(?:sales|income|property|ad valorem|corporate|business|excise) tax|(?:sales|income|property|ad valorem|corporate) tax.{0,80}(?:increase|raise)", "tax_burden", "increase", "broad_tax_increase"),
        (r"(?:reduce|decrease|repeal).{0,100}(?:sales|income|property|ad valorem|corporate|business|excise) tax|(?:sales|income|property|ad valorem|corporate) tax.{0,100}(?:credit|deduction|exemption|reduction)", "tax_burden", "decrease", "tax_reduction"),
        (r"(?:medicaid|health coverage|health insurance).{0,140}(?:expand|eligibility|cover|access)|expand.{0,100}(?:medicaid|health coverage)", "healthcare_access", "expand", "healthcare_access_expansion"),
        (r"(?:restrict|reduce|limit).{0,100}(?:medicaid|health coverage|health insurance)|medicaid.{0,100}work requirement", "healthcare_access", "restrict", "healthcare_access_restriction"),
        (r"(?:public assistance|food stamps?|tanf|welfare).{0,120}(?:expand|increase|eligibility)|expand.{0,80}(?:public assistance|food stamps?|tanf)", "welfare_generosity", "expand", "welfare_expansion"),
        (r"(?:public assistance|food stamps?|tanf|welfare).{0,140}(?:restrict|reduce|drug test|work requirement|ineligible)", "welfare_conditionality", "strengthen_conditions", "welfare_conditions"),
        (r"(?:voter registration|absentee voting|absentee ballot|voting).{0,120}(?:expand|allow|extend|early voting)|restore.{0,80}voting rights", "voting_access", "expand", "voting_access_expansion"),
        (r"(?:voter identification|photo identification|proof of citizenship)|(?:absentee voting|voter registration).{0,100}(?:restrict|limit)", "election_integrity_controls", "strengthen", "election_controls_expansion"),
        (r"illegal alien|unlawful alien|e.verify|proof of lawful presence", "immigration_enforcement", "strengthen", "immigration_enforcement_expansion"),
        (r"school prayer|quiet reflection|religious expression|ten commandments", "religion_state", "accommodation_establishment", "religious_accommodation"),
        (r"same.sex|homosexual|sodomy|sexual orientation|gender identity", "civil_social_liberty", "restrict", "sexual_liberty_restriction_context"),
        (r"racial discrimination|civil rights|voting rights act", "racial_civil_rights", "expand", "racial_rights_expansion_context"),
        (r"environmental protection|pollution control|emission.{0,80}(?:limit|reduce)|conservation easement", "environmental_protection", "strengthen", "environmental_protection_expansion"),
        (r"occupational licens.{0,120}(?:repeal|exempt|reciprocity|reduce)|repeal.{0,80}(?:licensing|regulation)", "market_governance", "market_autonomy", "occupational_deregulation"),
        (r"(?:economic|industrial) development.{0,120}(?:tax credit|incentive|grant|subsid)|tax increment financing", "business_subsidy", "expand", "business_subsidy_expansion"),
        (r"open meetings?|public records?.{0,100}(?:access|disclosure)|ethics commission.{0,100}(?:authority|disclosure)", "government_ethics_transparency", "strengthen", "government_transparency_expansion"),
    ]
    hits = [(axis, pole, name) for pattern, axis, pole, name in rules if match(text, pattern)]
    by_axis: dict[str, set[str]] = {}
    for axis, pole, _ in hits:
        by_axis.setdefault(axis, set()).add(pole)
    hits = [hit for hit in hits if len(by_axis[hit[0]]) == 1]
    if not hits:
        status = "excluded_historical_conflicting_poles" if any(len(v) > 1 for v in by_axis.values()) else "excluded_historical_non_scalar"
        return {"decision": "exclude", "primitive_axis": "", "policy_pole": "",
                "translation_rule": "no_unambiguous_high_precision_rule", "terminal_status": status}
    # A bill may map to several distinct primitives; caller expands the list.
    unique = list(dict.fromkeys(hits))
    return {"decision": "map", "primitive_axis": ";".join(x[0] for x in unique),
            "policy_pole": ";".join(x[1] for x in unique),
            "translation_rule": ";".join(x[2] for x in unique),
            "terminal_status": "mapped_historical_frontier_policy_pole"}


def main() -> None:
    calls = pd.read_csv(LEG / "comprehensive_rollcall_classifications.csv", low_memory=False)
    calls = calls[calls.bill_id.isna()].copy()
    recovery = pd.read_csv(LEG / "historical_rollcall_synopsis_recovery.csv", low_memory=False)
    recovery = recovery[["rollcall_id", "best_synopsis", "synopsis_source", "recovery_status"]]
    calls = calls.merge(recovery, left_on="canonical_rollcall_id", right_on="rollcall_id", how="left", validate="one_to_one")
    rows: list[dict[str, object]] = []
    for row in calls.itertuples(index=False):
        base = {"canonical_rollcall_id": row.canonical_rollcall_id, "bill_id": "",
                "session_year": row.session_year, "chamber": row.chamber,
                "bill_number": row.bill_number, "vote_description": row.vote_description,
                "frontier_bill_decision": "historical_recovered_synopsis_review",
                "frontier_axes": "", "frontier_poles": "", "frontier_confidence": "high",
                "frontier_rationale": clean(row.best_synopsis),
                "frontier_text_basis": row.synopsis_source or "unavailable"}
        if row.motion_disposition != "bill_direction_applies":
            rows.append(base | {"decision": "exclude", "primitive_axis": "", "policy_pole": "",
                                "translation_rule": "motion_not_final_policy_support",
                                "terminal_status": "excluded_procedural_or_ambiguous_motion"})
            continue
        result = classify_synopsis(row.best_synopsis)
        if result["decision"] == "map":
            axes, poles, rules = (result[key].split(";") for key in ("primitive_axis", "policy_pole", "translation_rule"))
            for axis, pole, rule in zip(axes, poles, rules):
                validate_primitive(axis, pole)
                rows.append(base | result | {"primitive_axis": axis, "policy_pole": pole,
                                             "source_axis": axis, "source_pole": pole,
                                             "translation_rule": f"historical_frontier:{rule}"})
        else:
            rows.append(base | result)
    out = pd.DataFrame(rows)
    if set(out.canonical_rollcall_id) != set(calls.canonical_rollcall_id):
        raise AssertionError("historical frontier ledger does not cover every journal roll call")
    out.to_csv(OUT, index=False)
    print(out.groupby(["decision", "terminal_status"]).canonical_rollcall_id.nunique().reset_index(name="rollcalls").to_string(index=False))
    print(f"Historical roll calls: {calls.canonical_rollcall_id.nunique():,}; mapped: {out.loc[out.decision.eq('map'),'canonical_rollcall_id'].nunique():,}")


if __name__ == "__main__":
    main()
