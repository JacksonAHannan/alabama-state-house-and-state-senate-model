"""Inventory every downloaded Vote Smart questionnaire item by policy family."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
ITEMS = IDEOLOGY / "votesmart_pct_item_crosswalk.csv"
PCT = IDEOLOGY / "votesmart_all_1998_2022_pct_options.csv"
ITEM_OUT = IDEOLOGY / "votesmart_pct_full_corpus_ontology_audit.csv"
SUMMARY_OUT = IDEOLOGY / "votesmart_pct_full_corpus_family_summary.csv"

FAMILY_RULES = [
    ("legislative_priorities", r"priorit"),
    ("abortion_reproductive", r"abortion|reproductive"),
    ("guns", r"\bgun"),
    ("drugs", r"drug|marijuana"),
    ("criminal_justice", r"crime|public safety|illegal drugs"),
    ("immigration", r"immigration"),
    ("healthcare", r"health"),
    ("education", r"educat"),
    ("welfare_poverty_housing", r"welfare|poverty|homeless"),
    ("labor_employment_civil_rights", r"employ|affirmative action|unemployment"),
    ("social_security_retirement", r"social security"),
    ("fiscal_tax_budget", r"budget|spending|tax|balanced budget|line item"),
    ("campaign_elections_government", r"campaign|government reform|election|term limit"),
    ("environment_energy_resources", r"environment|energy"),
    ("defense_security_terrorism", r"defense|national security|terrorism"),
    ("foreign_policy_aid", r"foreign policy|international aid|international policy"),
    ("trade_globalization", r"trade"),
    ("federalism_intergovernmental", r"federalism"),
    ("technology_communications_privacy", r"technology|communication"),
    ("social_civil_family", r"social issue|moral|marriage"),
    ("economy_business", r"econom"),
]


def normalized(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return re.sub(r"^(?:[a-z]|[0-9]+)\)\s*", "", text)


def family(section: object, question: object, option: object) -> str:
    section_text = normalized(section)
    for name, pattern in FAMILY_RULES:
        if re.search(pattern, section_text):
            return name
    context = " ".join([normalized(question), normalized(option)])
    for name, pattern in FAMILY_RULES:
        if re.search(pattern, context):
            return name
    return "other_unclassified"


def main() -> None:
    items = pd.read_csv(ITEMS).fillna("")
    pct = pd.read_csv(PCT).fillna("")
    keys = ["election_year", "section", "question", "option_text"]
    response_stats = pct.groupby(keys, dropna=False, as_index=False).agg(
        candidates_observed=("votesmart_candidate_id", "nunique"),
        selected_responses=("selected", "sum"),
    )
    audit = items.merge(response_stats, on=keys, how="left", validate="one_to_one")
    audit["normalized_option"] = audit.option_text.map(normalized)
    audit["policy_family"] = [
        family(section, question, option)
        for section, question, option in zip(audit.section, audit.question, audit.option_text)
    ]
    audit.to_csv(ITEM_OUT, index=False)
    summary = audit.groupby("policy_family", as_index=False).agg(
        year_items=("normalized_option", "size"),
        distinct_wordings=("normalized_option", "nunique"),
        candidates_observed=("candidates_observed", "sum"),
        selected_responses=("selected_responses", "sum"),
        deterministic_rules=("coding_status", lambda s: int(s.eq("rule_mapped").sum())),
        unmapped_items=("coding_status", lambda s: int(s.eq("unmapped").sum())),
        position_only_items=("coding_status", lambda s: int(s.eq("position_only").sum())),
        non_scorable_items=("coding_status", lambda s: int(s.eq("non_scorable").sum())),
    ).sort_values("year_items", ascending=False)
    summary["mapped_share"] = summary.deterministic_rules / summary.year_items
    summary.to_csv(SUMMARY_OUT, index=False)
    print(summary.to_string(index=False))
    print(f"\nAudited {len(audit):,} year-items and {audit.normalized_option.nunique():,} distinct wordings")


if __name__ == "__main__":
    main()
