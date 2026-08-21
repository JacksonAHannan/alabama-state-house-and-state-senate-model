"""Translate adjudicated legislative roll calls into ontology-v3 evidence.

Only already-directional substantive motions with an unambiguous mapping into a
v3 primitive are admitted. Old broad directions are not used for taxes/budgets,
ethics, omnibus measures, or other cases where "conservative/progressive" fails
to identify a concrete policy pole. Those records remain in the audit queue.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import calendar
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ideology_ontology_v3 import ONTOLOGY_VERSION, family_loading, validate_primitive

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
DB = LEG / "alabama_legislative_rollcalls_1998_2026.sqlite"
WINDOWS = {1998:(1998,1998), 2002:(1999,2002), 2006:(2003,2006), 2010:(2007,2010),
           2014:(2011,2014), 2018:(2015,2018), 2022:(2019,2022)}

# (old issue code, old +1/-1 direction) -> concrete v3 pole. This is deliberately
# narrower than the legacy classification universe.
TRANSLATIONS = {
    ("abortion", 1): ("abortion_access", "restrict"),
    ("abortion", -1): ("abortion_access", "expand"),
    ("assisted_dying", 1): ("bioethics_end_of_life", "restrictive"),
    ("assisted_dying", -1): ("bioethics_end_of_life", "permissive"),
    ("criminal_justice", 1): ("criminal_punishment", "punitive"),
    ("criminal_justice", -1): ("criminal_punishment", "rehabilitative"),
    ("culture_lgbtq", 1): ("civil_social_liberty", "restrict"),
    ("culture_lgbtq", -1): ("civil_social_liberty", "expand"),
    ("lgbtq_rights", 1): ("anti_discrimination", "restrict"),
    ("lgbtq_rights", -1): ("anti_discrimination", "expand"),
    ("guns", 1): ("gun_access", "expand"),
    ("guns", -1): ("gun_access", "restrict"),
    ("healthcare", 1): ("healthcare_access", "restrict"),
    ("healthcare", -1): ("healthcare_access", "expand"),
    ("healthcare_conscience", 1): ("religion_state", "accommodation_establishment"),
    ("immigration", 1): ("immigration_enforcement", "strengthen"),
    ("immigration", -1): ("immigration_enforcement", "relax"),
    ("labor_unions", 1): ("labor_rights", "restrict"),
    ("labor_unions", -1): ("labor_rights", "expand"),
    ("occupational_licensing", 1): ("market_governance", "market_autonomy"),
    ("occupational_licensing", -1): ("market_governance", "intervention"),
    ("public_education", 1): ("education_public_funding", "reduce"),
    ("public_education", -1): ("education_public_funding", "expand"),
    ("public_employee_benefits", 1): ("public_employee_compensation", "reduce"),
    ("public_employee_benefits", -1): ("public_employee_compensation", "protect"),
    ("public_private_partnerships", 1): ("public_private_provision", "private_provision"),
    ("public_private_partnerships", -1): ("public_private_provision", "public_provision"),
    ("school_choice", 1): ("education_market_choice", "expand"),
    ("school_choice", -1): ("education_market_choice", "restrict"),
    ("social_services", 1): ("welfare_generosity", "restrict"),
    ("social_services", -1): ("welfare_generosity", "expand"),
    ("environment_energy", 1): ("environmental_protection", "weaken"),
    ("environment_energy", -1): ("environmental_protection", "strengthen"),
}


TEXT_RULES = [
    ("school_choice_expand", r"charter schools?.{0,80}(?:authoriz|establish)|education savings accounts?|scholarship.{0,80}(?:private|nonpublic)|tax credits?.{0,100}(?:private school|scholarship)", "education_market_choice", "expand"),
    ("abortion_restrict", r"abortions?.{0,100}(?:prohibit|ban|criminal|unlawful)|(?:prohibit|ban).{0,100}abortions?|unborn (?:child|life)|fetal heartbeat", "abortion_access", "restrict"),
    ("abortion_expand", r"repeal.{0,100}(?:abortion ban|abortion prohibition)|protect.{0,80}(?:abortion|reproductive)", "abortion_access", "expand"),
    ("gun_access_expand", r"right to bear arms|permitless carry|constitutional carry|pistol permits?.{0,80}(?:repeal|not required)|firearms? preemption", "gun_access", "expand"),
    ("gun_regulation_strengthen", r"background checks?|red flag|prohibit.{0,80}(?:firearm|pistol)|firearms?.{0,80}prohibit", "gun_purchase_regulation", "strengthen"),
    ("immigration_enforcement", r"illegal (?:alien|immigrant)|unauthorized alien|e-verify|verify.{0,60}(?:citizenship|immigration|lawful presence)", "immigration_enforcement", "strengthen"),
    ("right_to_work", r"right to work|payment of dues.{0,80}(?:not|required|prohibit)|payroll deductions?.{0,100}(?:union|membership organization)", "labor_rights", "restrict"),
    ("collective_bargaining", r"collective bargaining.{0,80}(?:authoriz|right|permit)|organizing rights", "labor_rights", "expand"),
    ("welfare_conditions", r"(?:snap|tanf|public assistance|benefit funds?).{0,160}(?:prohibit|ineligib|required to|drug test|work requirement|restriction)", "welfare_conditionality", "strengthen_conditions"),
    ("welfare_expand", r"(?:snap|tanf|public assistance).{0,120}(?:expand|increase|additional eligibility)|expand.{0,80}(?:snap|tanf|public assistance)", "welfare_generosity", "expand"),
    ("punishment_expand", r"death penalty|execution by|sex offenders?.{0,100}(?:restriction|penalt)|criminal penalt(?:y|ies).{0,60}(?:increase|enhance)|mandatory minimum", "criminal_punishment", "punitive"),
    ("rehabilitation_due_process", r"expungement|record sealing|reduce.{0,80}(?:sentence|penalt)|parole eligibility.{0,80}(?:expand|earlier)|rehabilitation program", "criminal_punishment", "rehabilitative"),
    ("voting_controls", r"photo identification|voter identification|proof of citizenship|absentee ballot.{0,100}(?:restrict|limit|identification)", "election_integrity_controls", "strengthen"),
    ("voting_access", r"early voting|same.day registration|automatic voter registration|expand.{0,80}(?:absentee|voting access)", "voting_access", "expand"),
    ("tax_decrease", r"(?:income|sales|property|business|ad valorem|excise) tax.{0,100}(?:credit|deduction|exemption|reduc)|tax (?:credit|deduction|exemption|reduction)|deduction for qualified", "tax_burden", "decrease"),
    ("tax_increase", r"(?:levy|increase|raise|additional).{0,80}(?:income|sales|property|business|ad valorem|excise) tax|tax rate.{0,50}increase", "tax_burden", "increase"),
    ("environment_strengthen", r"environmental protection|pollution.{0,80}(?:control|limit|reduc)|emissions?.{0,80}(?:limit|reduc)|conservation easement", "environmental_protection", "strengthen"),
    ("resource_development", r"oil and gas.{0,100}(?:lease|drill|development)|mineral development|conversion of oil and gas wells", "resource_development", "expand"),
    ("health_access_expand", r"medicaid.{0,100}(?:expand|eligibility)|health coverage.{0,80}(?:expand|required)|insurance.{0,80}preexisting condition", "healthcare_access", "expand"),
    ("market_autonomy", r"occupational licens.{0,100}(?:repeal|exempt|reduce)|regulation.{0,80}(?:repeal|eliminate)|prohibited from regulating or licensing", "market_governance", "market_autonomy"),
    ("lgbtq_restrict", r"transgender.{0,120}(?:prohibit|restrict)|biological sex.{0,100}(?:bathroom|athletic|sports)|prohibit.{0,100}(?:gender identity|same.sex)", "civil_social_liberty", "restrict"),
]


def text_mapping(row: pd.Series) -> tuple[str, str, str] | None:
    text = " ".join(str(row.get(c, "") or "") for c in ("title", "description")).lower()
    for name, pattern, axis, pole in TEXT_RULES:
        if re.search(pattern, text, re.I):
            return axis, pole, name
    return None


def digest(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:20].upper()


def general_election_date(year: int) -> date:
    """Federal general-election date: Tuesday after the first Monday."""
    first_monday = min(day for day in range(1, 8) if date(year, 11, day).weekday() == calendar.MONDAY)
    return date(year, 11, first_monday + 1)


def main() -> None:
    frontier_path = LEG / "frontier_rollcall_ontology_v3.csv"
    if not frontier_path.exists():
        raise FileNotFoundError("run build_frontier_rollcall_ontology.py first")
    frontier = pd.read_csv(frontier_path, low_memory=False).fillna("")
    calls = pd.read_csv(LEG / "comprehensive_rollcall_classifications.csv", low_memory=False)
    metadata = calls[["canonical_rollcall_id", "vote_date", "url", "title", "description",
                      "issue_code", "classification_source"]].drop_duplicates("canonical_rollcall_id")
    accepted = frontier[frontier.decision.eq("map")].merge(
        metadata, on="canonical_rollcall_id", how="left", validate="many_to_one")
    accepted = accepted.sort_values(
        ["canonical_rollcall_id", "primitive_axis", "policy_pole", "source_axis"]
    ).drop_duplicates(["canonical_rollcall_id", "primitive_axis", "policy_pole"])
    for row in accepted.itertuples(index=False):
        validate_primitive(row.primitive_axis, row.policy_pole)
    candidates = pd.read_csv(IDEOLOGY / "candidate_ideology_full_universe.csv", dtype=str).fillna("")
    candidates = candidates[candidates.member_source_id.ne("") & candidates.year.astype(int).isin(WINDOWS)].copy()
    candidates["year"] = candidates.year.astype(int)
    with sqlite3.connect(DB) as con:
        votes = pd.read_sql("SELECT * FROM member_vote WHERE vote IN ('Yea','Nay')", con)
    joined = votes.merge(accepted, on=["canonical_rollcall_id", "session_year", "chamber"], how="inner", suffixes=("_member", ""))
    joined["vote_date_parsed"] = pd.to_datetime(joined.vote_date, errors="coerce").dt.date
    historical = joined.canonical_rollcall_id.astype(str).str.contains("JRC-")
    # The journal extractor currently preserves session year and page but not
    # an exact calendar date. Regular-session actions necessarily precede the
    # November election; use a transparent midyear placeholder solely for the
    # temporal cutoff and retain the historical authority label below.
    joined.loc[historical & joined.vote_date_parsed.isna(), "vote_date_parsed"] = joined.loc[
        historical & joined.vote_date_parsed.isna(), "session_year"
    ].map(lambda year: date(int(year), 6, 1))
    joined.loc[historical & joined.vote_date.fillna("").eq(""), "vote_date"] = joined.loc[
        historical & joined.vote_date.fillna("").eq(""), "session_year"
    ].map(lambda year: f"{int(year)}-session-date-unavailable")
    rows = []
    for candidate in candidates.itertuples():
        start, end = WINDOWS[candidate.year]
        cutoff = general_election_date(candidate.year)
        hit = joined[(joined.member_source_id.eq(candidate.member_source_id)) & joined.session_year.between(start, end)]
        hit = hit[hit.vote_date_parsed.notna() & hit.vote_date_parsed.le(cutoff)]
        for vote in hit.itertuples():
            validate_primitive(vote.primitive_axis, vote.policy_pole)
            family, direction = family_loading(vote.primitive_axis, vote.policy_pole)
            value = 1.0 if vote.vote == "Yea" else -1.0
            rows.append({
                "ontology_version": ONTOLOGY_VERSION,
                "evidence_id": digest("rollcall", candidate.canonical_candidate_id, vote.canonical_rollcall_id, vote.primitive_axis),
                "canonical_candidate_id": candidate.canonical_candidate_id, "person_id": candidate.person_id,
                "candidate_name": candidate.canonical_name, "election_cycle": candidate.year,
                "evidence_date": vote.vote_date, "temporal_status": "pre_or_same_cycle_legislative_action",
                "source_type": "legislative_vote", "source_provider": "Alabama Legislature via LegiScan",
                "source_record_id": vote.canonical_rollcall_id, "source_url": vote.url,
                "item_id": digest(vote.canonical_rollcall_id, vote.primitive_axis), "policy_family": vote.source_axis,
                "policy_key": f"{vote.primitive_axis}_{vote.bill_number}", "primitive_axis": vote.primitive_axis,
                "policy_pole": vote.policy_pole, "candidate_stance": "support" if value > 0 else "oppose",
                "position_value": value, "response_mode": "recorded_vote",
                "family": family or "", "family_direction": direction if direction is not None else np.nan,
                "family_contribution": value * direction if direction is not None else np.nan,
                "constituency_tags_json": "[]", "confidence": vote.frontier_confidence or "medium",
                "adjudication_authority": f"frontier_manual_review:{vote.translation_rule}",
                "evidence_weight": 1.0, "source_text": f"{vote.vote_description}: {vote.title}", "raw_answer": vote.vote,
            })
    evidence = pd.DataFrame(rows)
    evidence.to_csv(IDEOLOGY / "candidate_legislative_position_evidence_v3.csv", index=False)
    summary = frontier.groupby("terminal_status", dropna=False).canonical_rollcall_id.nunique().rename("rollcalls").reset_index()
    summary.to_csv(LEG / "legislative_rollcall_ontology_v3_audit_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Wrote {len(evidence):,} candidate legislative evidence records from {len(accepted):,} accepted roll calls")


if __name__ == "__main__":
    main()
