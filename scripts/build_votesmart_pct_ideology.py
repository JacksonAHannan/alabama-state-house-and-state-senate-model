"""Map Vote Smart PCT answers into transparent candidate ideology features.

The raw wording remains authoritative. Rules only code items whose affirmative
policy direction is clear across questionnaire vintages. Unmapped and ambiguous
items are retained in the item crosswalk for review rather than silently scored.
Higher scores always mean the conventionally more conservative position within
the named dimension; this is a coding convention, not a claim about causality.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
PCT = IDEOLOGY / "votesmart_all_1998_2022_pct_options.csv"
CROSSWALK = IDEOLOGY / "votesmart_candidate_crosswalk.csv"
RESOLVED_CROSSWALK = IDEOLOGY / "votesmart_candidate_crosswalk_resolved.csv"
ITEM_OUT = IDEOLOGY / "votesmart_pct_item_crosswalk.csv"
CODED_OUT = IDEOLOGY / "votesmart_pct_coded_responses.csv"
FEATURE_OUT = IDEOLOGY / "votesmart_pct_candidate_cycle_features.csv"
COVERAGE_OUT = IDEOLOGY / "votesmart_pct_coding_coverage.csv"
POSITION_OUT = IDEOLOGY / "votesmart_pct_position_only_responses.csv"


@dataclass(frozen=True)
class Rule:
    policy_key: str
    dimension: str
    pattern: str
    affirmative_direction: float
    confidence: str = "high"
    response_mode: str = "binary"


# Specific rules precede broad ones. An affirmative direction of +1 denotes
# the conventionally conservative response and -1 the progressive response.
RULES = (
    # Ordinal spending and tax batteries. Here affirmative_direction is the
    # ideological direction of an *increase*; response intensity is preserved.
    Rule("spending_k12_education", "education_position", r"education \(k-12\)", -1, "high", "ordinal"),
    Rule("spending_higher_education", "education_position", r"education \(higher\)", -1, "high", "ordinal"),
    Rule("spending_environment", "environment_position", r"^(?:[a-z]\) )?environment$", -1, "high", "ordinal"),
    Rule("spending_healthcare", "healthcare_position", r"^(?:[a-z]\) )?health care$", -1, "high", "ordinal"),
    Rule("spending_welfare", "economic_ideology", r"^(?:[a-z]\) )?welfare$", -1, "high", "ordinal"),
    Rule("spending_law_enforcement", "criminal_justice_position", r"^(?:[a-z]\) )?law enforcement$", 1, "medium", "ordinal"),
    Rule("tax_alcohol", "economic_ideology", r"alcohol taxes$", -1, "medium", "ordinal"),
    Rule("tax_capital_gains", "economic_ideology", r"capital gains taxes$", -1, "high", "ordinal"),
    Rule("tax_cigarette", "economic_ideology", r"cigarette taxes$", -1, "medium", "ordinal"),
    Rule("tax_corporate", "economic_ideology", r"corporate taxes$", -1, "high", "ordinal"),
    Rule("tax_gasoline", "economic_ideology", r"(?:gas|gasoline) taxes$", -1, "medium", "ordinal"),
    Rule("tax_income_lower", "economic_ideology", r"income taxes \(incomes below", -1, "high", "ordinal"),
    Rule("tax_income_upper", "economic_ideology", r"income taxes \(incomes above", -1, "high", "ordinal"),
    Rule("tax_inheritance", "economic_ideology", r"inheritance taxes$", -1, "high", "ordinal"),
    Rule("tax_property", "economic_ideology", r"property taxes$", -1, "medium", "ordinal"),
    Rule("tax_sales", "economic_ideology", r"sales taxes$", -1, "medium", "ordinal"),
    Rule("tax_sales_grocery", "economic_ideology", r"sales taxes \(grocery\)$", -1, "medium", "ordinal"),
    Rule("tax_income_low_family", "economic_ideology", r"income taxes \(low-income families\)$", -1, "high", "ordinal"),
    Rule("tax_income_middle_family", "economic_ideology", r"income taxes \(middle-income families\)$", -1, "high", "ordinal"),
    Rule("tax_income_high_family", "economic_ideology", r"income taxes \(high-income families\)$", -1, "high", "ordinal"),
    Rule("tax_vehicle", "economic_ideology", r"vehicle taxes$", -1, "medium", "ordinal"),
    Rule("abortion_general_pro_life", "abortion_position", r"pro-choice or pro-life|pro-life legislation", 1),
    Rule("abortion_always_illegal", "abortion_position", r"abortions? should always be illegal", 1),
    Rule("abortion_always_legal", "abortion_position", r"abortions? should always be legally? available|abortions? should always be legal", -1),
    Rule("abortion_public_funding_prohibition", "abortion_position", r"prohibit(?:ion)? (?:of )?public fund|eliminate public funding for abortions", 1),
    Rule("abortion_public_funding_support", "abortion_position", r"government funding be provided to clinics.*abortion", -1),
    Rule("abortion_parental_notification", "abortion_position", r"parental notification", 1),
    Rule("abortion_parental_consent", "abortion_position", r"parental consent", 1),
    Rule("abortion_late_term_ban", "abortion_position", r"partial-birth|late-term abortion", 1),
    Rule("abortion_after_first_trimester_ban", "abortion_position", r"abortion.*illegal after the first trimester", 1, "medium"),
    Rule("abortion_first_trimester_legality", "abortion_position", r"abortion.*legal only (?:within|in).*first trimester", -1, "medium"),
    Rule("abortion_rape_incest_exception", "abortion_position", r"abortion.*(?:incest|rape)", -1, "medium"),
    Rule("abortion_life_exception", "abortion_position", r"abortion.*life of the woman", -1, "medium"),
    Rule("guns_general_control", "guns_position", r"support gun-control legislation", -1),
    Rule("guns_restrictions", "guns_position", r"(?:increase|maintain|strengthen|support) .*restrictions? on the purchase and possession|support restrictions on the purchase", -1),
    Rule("guns_ease_restrictions", "guns_position", r"(?:ease|repeal) .*restrictions? on the purchase and possession", 1),
    Rule("guns_semiautomatic_ban", "guns_position", r"ban the sale or transfer.*semi-automatic", -1),
    Rule("guns_background_checks", "guns_position", r"background checks?.*gun sales", -1),
    Rule("guns_license", "guns_position", r"license (?:be required )?for gun (?:possession|ownership)", -1),
    Rule("guns_child_safety_locks", "guns_position", r"child-safety locks", -1),
    Rule("guns_concealed_carry", "guns_position", r"allow(?:ing)? (?:citizens|individuals) to carry concealed", 1),
    Rule("economic_reduce_regulation", "economic_ideology", r"reduc(?:e|ing) (?:state )?government regulations? on the private sector", 1),
    Rule("economic_lower_taxes_growth", "economic_ideology", r"lowering state taxes.*promoting economic growth", 1),
    Rule("economic_government_spending_growth", "economic_ideology", r"government spending as a means of promoting economic growth", -1),
    Rule("economic_unemployment_benefits", "economic_ideology", r"expand(?:ing)? access to unemployment benefits", -1),
    Rule("economic_job_training", "economic_ideology", r"(?:increase|increased) (?:state )?funding for (?:state )?job-training", -1),
    Rule("economic_welfare_job_training", "economic_ideology", r"(?:increase|increased) (?:funding for )?employment and job training programs for welfare", -1),
    Rule("economic_homeowner_assistance", "economic_ideology", r"direct financial assistance to homeowners", -1),
    Rule("economic_welfare_drug_test", "economic_ideology", r"welfare applicants? to pass a drug test", 1),
    Rule("economic_flat_income_tax", "economic_ideology", r"flat tax structure.*income tax", 1),
    Rule("economic_internet_sales_tax", "economic_ideology", r"internet sales be taxed", -1),
    Rule("economic_extend_internet_sales_tax", "economic_ideology", r"sales taxes be extended to internet sales", -1),
    Rule("economic_tort_damage_limits", "economic_ideology", r"limits? (?:on )?(?:cash )?damages?.*(?:lawsuits|malpractice)|limit the amount of damages.*malpractice", 1),
    Rule("economic_business_incentives", "economic_ideology", r"(?:low interest loans|tax (?:credits|incentives)).*(?:starting|expanding|relocating) businesses", 1, "medium"),
    Rule("economic_welfare_work_requirement", "economic_ideology", r"(?:able-bodied )?recipients?.*participate in work activities", 1),
    Rule("economic_welfare_increased_work_requirement", "economic_ideology", r"increased work requirements for able-bodied welfare", 1),
    Rule("economic_medicaid_benefit_reduction", "economic_ideology", r"reducing benefits for medicaid recipients", 1),
    Rule("economic_government_service_privatization", "economic_ideology", r"privatizing certain government services", 1),
    Rule("economic_public_university_tuition_increase", "economic_ideology", r"increasing tuition rates at public universities", 1, "medium"),
    Rule("economic_eminent_domain_public_use", "economic_ideology", r"restricting eminent domain to public uses", 1),
    Rule("economic_eminent_domain_compensation", "economic_ideology", r"pay the highest value.*property seized by eminent domain", 1),
    Rule("economic_welfare_family_cap", "economic_ideology", r"limit benefits.*additional children.*welfare", 1),
    Rule("economic_welfare_time_limits", "economic_ideology", r"(?:maintain|support) (?:the )?(?:current )?time limits? on welfare", 1),
    Rule("economic_welfare_transportation", "economic_ideology", r"increase access to public transportation for welfare", -1),
    Rule("economic_welfare_childcare", "economic_ideology", r"provide child care for welfare recipients", -1, "medium"),
    Rule("economic_tanf_working_poor", "economic_ideology", r"tanf.*expand state services.*working poor", -1),
    Rule("labor_minimum_wage", "labor_position", r"increase of the minimum wage|increase the state minimum wage", -1),
    Rule("labor_collective_bargaining", "labor_position", r"collective bargaining", -1),
    Rule("labor_right_to_work", "labor_position", r"right[- ]to[- ]work", 1),
    Rule("social_sexual_orientation_protection", "social_ideology", r"include sexual orientation.*anti-discrimination", -1),
    Rule("social_same_sex_marriage", "social_ideology", r"same-sex (?:couples|marriage)|marriage between two people of the same sex", -1),
    Rule("social_religious_display", "social_ideology", r"religious (?:symbols|display)|ten commandments", 1, "medium"),
    Rule("social_abstinence_education", "social_ideology", r"sex education.*(?:stress|stresses) abstinence|abstinence-only", 1),
    Rule("social_comprehensive_sex_education", "social_ideology", r"sexual education programs.*abstinence, contraceptives", -1),
    Rule("social_marriage_restriction", "social_ideology", r"restrict marriage.*(?:man and a woman|one man and one woman)", 1),
    Rule("social_affirmative_action", "social_ideology", r"affirmative action.*(?:college|university|public employment|state contracting)", -1, "medium"),
    Rule("social_moment_of_silence", "social_ideology", r"mandatory .*moment of silence.*public schools", 1, "medium"),
    Rule("social_voluntary_school_prayer", "social_ideology", r"(?:teacher-led )?voluntary prayer in public schools", 1),
    Rule("social_smoking_ban", "social_ideology", r"banning smoking in public places", -1, "medium"),
    Rule("social_teen_pregnancy_prevention", "social_ideology", r"funding for programs to prevent teen pregnancy", -1),
    Rule("social_low_income_childcare", "social_ideology", r"(?:provide child care|child care for children) .*low-income working families", -1),
    Rule("social_head_start", "social_ideology", r"increase (?:state )?funding for head start", -1),
    Rule("social_at_risk_youth_services", "social_ideology", r"funding for community centers and other social agencies.*at-risk youth", -1),
    Rule("social_at_risk_youth_programs", "social_ideology", r"state funding of programs for at-risk youth", -1),
    Rule("education_vouchers", "education_position", r"school vouchers?|vouchers.*school", 1, "medium"),
    Rule("education_charter_schools", "education_position", r"charter schools?", 1, "medium"),
    Rule("education_corporate_investment", "education_position", r"private or corporate investment in public school", 1, "medium"),
    Rule("education_school_construction_funding", "education_position", r"increase state funds for school construction", -1),
    Rule("education_school_capital_funding", "education_position", r"increase state funds for school capital improvements", -1),
    Rule("education_additional_teachers", "education_position", r"increase (?:state )?funds for hiring (?:of )?additional teachers", -1),
    Rule("education_teacher_development", "education_position", r"funds for professional development of public school teachers", -1),
    Rule("education_teacher_salaries", "education_position", r"state funding to increase teacher salaries", -1),
    Rule("education_college_affordability", "education_position", r"state funding for tax incentives and financial aid.*college more affordable", -1),
    Rule("education_teacher_testing_merit_pay", "education_position", r"teacher testing and reward.*merit pay", 1, "medium"),
    Rule("education_exit_exams", "education_position", r"public schools to administer high school exit exams", 1, "medium"),
    Rule("education_national_testing", "education_position", r"national standards and testing of public school students", 1, "medium"),
    Rule("education_corporporal_punishment", "education_position", r"teachers? to spank|corporal punishment", 1, "medium"),
    Rule("environment_emissions_regulation", "environment_position", r"regulat.*greenhouse gas|carbon emissions", -1),
    Rule("environment_renewable_energy", "environment_position", r"renewable (?:energy|sources)", -1),
    Rule("environment_federal_ceiling", "environment_position", r"environmental regulations? should not be stricter than federal", 1),
    Rule("environment_stricter_than_federal", "environment_position", r"environmental regulations? be stricter than federal", -1),
    Rule("environment_open_space_funding", "environment_position", r"state funding for open space preservation", -1),
    Rule("environment_cost_benefit", "environment_position", r"cost/benefit analysis.*environmental regulations", 1),
    Rule("environment_industry_self_audit", "environment_position", r"self-audit.*industries.*clean up pollution", 1, "medium"),
    Rule("environment_regulatory_takings", "environment_position", r"compensate citizens when environmental regulations limit uses", 1),
    Rule("environment_recycling_funding", "environment_position", r"funding for recycling programs", -1),
    Rule("environment_federal_flexibility", "environment_position", r"flexibility from the federal government.*environmental regulations", 1, "medium"),
    Rule("environment_suspend_unfunded_mandates", "environment_position", r"suspend participation in unfunded.*environmental protection", 1),
    Rule("environment_alternative_fuels", "environment_position", r"increased use of alternative fuel technology", -1),
    Rule("environment_traditional_energy", "environment_position", r"increased production of traditional domestic energy", 1),
    Rule("health_medicaid_expansion", "healthcare_position", r"expand(?:ing)? medicaid", -1),
    Rule("health_government_insurance", "healthcare_position", r"government.*health (?:insurance|care)|public health insurance", -1, "medium"),
    Rule("health_basic_access", "healthcare_position", r"ensure that citizens have access to basic health care", -1),
    Rule("health_not_government_responsibility", "healthcare_position", r"medical care to all citizens is not a responsibility of state government", 1),
    Rule("health_hmo_appeal", "healthcare_position", r"patients' right to appeal.*services are denied by their hmo", -1, "medium"),
    Rule("health_hmo_lawsuit", "healthcare_position", r"patients' right to sue their hmos", -1, "medium"),
    Rule("crime_death_penalty", "criminal_justice_position", r"death penalty|capital punishment", 1),
    Rule("crime_mandatory_minimum", "criminal_justice_position", r"mandatory minimum", 1, "medium"),
    Rule("crime_marijuana_legalization", "criminal_justice_position", r"legaliz.*marijuana", -1),
    Rule("crime_alternative_sentencing", "criminal_justice_position", r"penalties other than incarceration.*non-violent", -1),
    Rule("crime_repeat_violent_parole", "criminal_justice_position", r"end parole for repeat violent", 1),
    Rule("crime_drug_penalties", "criminal_justice_position", r"strengthen penalties.*drug-related", 1),
    Rule("crime_sex_offender_penalties", "criminal_justice_position", r"strengthen penalties.*sex offenders", 1),
    Rule("crime_strengthen_sex_offender_laws", "criminal_justice_position", r"strengthen sex-offender laws", 1),
    Rule("crime_sex_offender_notification", "criminal_justice_position", r"inform communities.*sex offender", 1, "medium"),
    Rule("crime_juvenile_adult_prosecution", "criminal_justice_position", r"prosecute juveniles.*as adults", 1),
    Rule("crime_minors_adult_prosecution", "criminal_justice_position", r"minors accused of a violent crime.*prosecuted as adults", 1),
    Rule("crime_prison_construction", "criminal_justice_position", r"funds for construction of state prisons.*additional prison staff", 1),
    Rule("crime_prison_rehabilitation", "criminal_justice_position", r"programs which rehabilitate and educate inmates", -1),
    Rule("crime_prison_job_training", "criminal_justice_position", r"prison inmates with vocational and job-related skills", -1),
    Rule("crime_chain_gangs", "criminal_justice_position", r"implement chain gangs", 1),
    Rule("crime_meth_precursor_restrictions", "criminal_justice_position", r"restriction of the sale of products used to make methamphetamine", 1),
    Rule("elections_photo_id", "government_reform_position", r"photo identification|photo id.*(?:vote|ballot)", 1),
    Rule("government_balanced_budget", "government_reform_position", r"balanced (?:federal )?budget", 1, "medium"),
    Rule("education_mandatory_testing", "education_position", r"mandatory state testing in public schools", 1, "medium"),
)

# These are meaningful positions, but assigning a stable left/right direction
# would add researcher judgment unsupported by the question itself. They remain
# available for issue-specific models and human review without entering scores.
POSITION_ONLY_RULES = (
    ("government_term_limits", r"term limits|limit(?:ing|s)? the number of terms|current limit of (?:two four-year )?terms"),
    ("campaign_contribution_limits", r"limit(?:ing)? .*contributions?|current limits on .*contributions"),
    ("campaign_finance_disclosure", r"disclosure of campaign finance"),
    ("campaign_spending_limits", r"spending limits on .*political campaigns"),
    ("campaign_public_funding", r"funding from state taxes.*political campaigns"),
    ("initiative_referendum", r"citizen initiative and referendum"),
    ("election_exit_polling", r"prohibiting media exit polling"),
    ("election_counting_standards", r"statewide standards for counting, verifying and ensuring accuracy of votes"),
    ("election_online_voting", r"support voting on-line"),
    ("constitution_rewrite", r"constitutional convention to rewrite|legislature rewrite the state constitution"),
    ("education_lottery", r"state lottery with proceeds funding education"),
    ("budget_rainy_day", r"rainy day.*balance the state budget|tapping into alabama's .*rainy day"),
    ("transportation_spending", r"transportation (?:and highway )?infrastructure|highways, roads, bridges"),
    ("agriculture_spending", r"^(?:[a-z]\) )?agriculture$"),
)


def normalize_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\x92", "'").replace("’", "'")
    text = re.sub(r"^[a-z]\)\s*", "", text.strip(), flags=re.I)
    return re.sub(r"\s+", " ", text).strip().lower()


def classify_item(option_text: object, section: object = "", question: object = "") -> dict[str, object]:
    normalized = normalize_text(option_text)
    context = " ".join(filter(None, [normalize_text(section), normalize_text(question), normalized]))
    if not normalized or normalized in {"other", "other or expanded principles"}:
        return {"policy_key": "", "dimension": "", "affirmative_direction": np.nan,
                "coding_confidence": "", "response_mode": "", "coding_status": "unmapped"}
    for rule in RULES:
        target = normalized if rule.response_mode == "ordinal" else context
        if re.search(rule.pattern, target, flags=re.I):
            return {"policy_key": rule.policy_key, "dimension": rule.dimension,
                    "affirmative_direction": rule.affirmative_direction,
                    "coding_confidence": rule.confidence, "response_mode": rule.response_mode,
                    "coding_status": "rule_mapped"}
    if (re.search(r"contributions?", context) and
            re.fullmatch(r"(?:[1-4]\)\s*)?(?:individual|pac|corporate|political parties)", normalized)):
        return {"policy_key": f"campaign_contribution_limits_{re.sub(r'[^a-z]+', '_', normalized).strip('_')}",
                "dimension": "position_only", "affirmative_direction": np.nan,
                "coding_confidence": "high", "response_mode": "binary",
                "coding_status": "position_only"}
    for policy_key, pattern in POSITION_ONLY_RULES:
        if re.search(pattern, normalized, flags=re.I):
            return {"policy_key": policy_key, "dimension": "position_only",
                    "affirmative_direction": np.nan, "coding_confidence": "high",
                    "response_mode": "ordinal" if policy_key.endswith("_spending") else "binary",
                    "coding_status": "position_only"}
    return {"policy_key": "", "dimension": "", "affirmative_direction": np.nan,
            "coding_confidence": "", "response_mode": "", "coding_status": "unmapped"}


def response_sign(raw_answer: object, option_text: object, selected: object,
                  response_mode: str = "binary") -> float:
    """Return +1 for affirmative, -1 for negative, and NaN when not answered."""
    answer = normalize_text(raw_answer)
    option = normalize_text(option_text)
    if response_mode == "ordinal":
        scale = {
            "greatly increase": 1.0, "greatly increase funding": 1.0,
            "slightly increase": 0.5, "slightly increase funding": 0.5,
            "maintain status": 0.0, "maintain funding status": 0.0,
            "slightly decrease": -0.5, "slightly decrease funding": -0.5,
            "greatly decrease": -1.0, "greatly decrease funding": -1.0,
            "eliminate": -1.0, "eliminate funding": -1.0,
        }
        return scale.get(answer, np.nan)
    if answer in {"undecided", "unknown", "n/a", "na", ""}:
        # Historical checkbox forms mark selected options with X. Unselected
        # options are absence of evidence, not negative answers.
        return 1.0 if answer == "" and bool(selected) else np.nan
    if answer in {"x", "yes", "support", "favor"}:
        return 1.0
    if answer in {"no", "oppose"}:
        return -1.0
    if "pro-life" in answer:
        return 1.0
    if "pro-choice" in answer:
        return -1.0
    # Some pages place the response label in the option cell.
    if "pro-life" in option and bool(selected):
        return 1.0
    if "pro-choice" in option and bool(selected):
        return -1.0
    return np.nan


def build_item_crosswalk(pct: pd.DataFrame) -> pd.DataFrame:
    keys = ["election_year", "section", "question", "option_text"]
    items = pct[keys].drop_duplicates().copy()
    coding = items.apply(
        lambda row: classify_item(row.option_text, row.section, row.question), axis=1
    ).apply(pd.Series)
    return pd.concat([items.reset_index(drop=True), coding.reset_index(drop=True)], axis=1)


def code_responses(pct: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    keys = ["election_year", "section", "question", "option_text"]
    coded = pct.merge(items, on=keys, how="left", validate="many_to_one")
    coded["response_sign"] = [
        response_sign(answer, option, selected, mode)
        for answer, option, selected, mode in zip(
            coded.raw_answer, coded.option_text, coded.selected, coded.response_mode
        )
    ]
    coded["ideology_score"] = coded.affirmative_direction * coded.response_sign
    coded["score_eligible"] = coded.coding_status.eq("rule_mapped") & coded.ideology_score.notna()
    return coded


def candidate_features(coded: pd.DataFrame, crosswalk: pd.DataFrame) -> pd.DataFrame:
    eligible = coded[coded.score_eligible].copy()
    # Multiple items can measure the same policy. Average within policy first so
    # long questionnaire batteries do not dominate shorter forms.
    policy = eligible.groupby(
        ["votesmart_candidate_id", "election_year", "candidate", "dimension", "policy_key"],
        as_index=False,
    ).agg(policy_score=("ideology_score", "mean"), response_items=("ideology_score", "size"))
    dimensions = policy.groupby(
        ["votesmart_candidate_id", "election_year", "candidate", "dimension"], as_index=False
    ).agg(dimension_score=("policy_score", "mean"), policies_scored=("policy_key", "nunique"),
          response_items=("response_items", "sum"))
    wide = dimensions.pivot_table(
        index=["votesmart_candidate_id", "election_year", "candidate"],
        columns="dimension", values="dimension_score"
    ).reset_index()
    counts = dimensions.groupby(
        ["votesmart_candidate_id", "election_year"], as_index=False
    ).agg(pct_dimensions_scored=("dimension", "nunique"), pct_policies_scored=("policies_scored", "sum"),
          pct_response_items_scored=("response_items", "sum"))
    wide = wide.merge(counts, on=["votesmart_candidate_id", "election_year"], validate="one_to_one")
    link = crosswalk[crosswalk.accepted].copy()
    link["votesmart_candidate_id"] = pd.to_numeric(link.votesmart_candidate_id, errors="coerce")
    # Join only to the questionnaire from the same election year. Later answers
    # never leak backward into an earlier candidate-cycle feature.
    return link.merge(
        wide, on=["votesmart_candidate_id", "election_year"], how="left",
        validate="many_to_one", suffixes=("_canonical", "_votesmart")
    )


def main() -> None:
    pct = pd.read_csv(PCT)
    crosswalk = pd.read_csv(RESOLVED_CROSSWALK if RESOLVED_CROSSWALK.exists() else CROSSWALK)
    items = build_item_crosswalk(pct)
    coded = code_responses(pct, items)
    features = candidate_features(coded, crosswalk)
    coverage = items.groupby(["election_year", "coding_status"], as_index=False).size()
    coverage["share"] = coverage["size"] / coverage.groupby("election_year")["size"].transform("sum")
    items.to_csv(ITEM_OUT, index=False)
    coded.to_csv(CODED_OUT, index=False)
    features.to_csv(FEATURE_OUT, index=False)
    coverage.to_csv(COVERAGE_OUT, index=False)
    coded[coded.coding_status.eq("position_only")].to_csv(POSITION_OUT, index=False)
    print(f"Mapped {items.coding_status.eq('rule_mapped').sum():,} / {len(items):,} unique year-items")
    print(f"Scored {coded.score_eligible.sum():,} candidate responses")
    print(f"Candidate-cycle rows with at least one score: {features.pct_dimensions_scored.notna().sum():,}")


if __name__ == "__main__":
    main()
