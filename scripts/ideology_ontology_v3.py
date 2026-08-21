"""Layered ideology ontology for multi-source candidate evidence."""

from __future__ import annotations

ONTOLOGY_VERSION = "3.0.0"

FAMILIES = {
    "market_government_direction": ("market_autonomy", "government_direction"),
    "material_support": ("restriction", "generosity"),
    "labor_capital": ("capital_management", "labor"),
    "social_liberty_equality": ("traditional_restriction", "liberty_equality"),
    "order_justice": ("rehabilitation_due_process", "punitive_enforcement"),
    "immigration_inclusion": ("restriction_national_identity", "inclusion"),
    "environment_resources": ("extraction_property_priority", "protection_preservation"),
    "institutional_reform": ("institutional_control", "democratic_reform"),
}

# Primitive poles describe policy content. A pole may load onto a higher-order
# family, remain issue-only, or be a categorical delivery mechanism.
PRIMITIVES = {
    "market_governance": ("intervention", "market_autonomy"),
    "public_private_provision": ("public_provision", "private_provision"),
    "economic_stimulus": ("public_stimulus", "tax_reduction"),
    "tax_burden": ("increase", "decrease"),
    "tax_distribution": ("progressive", "regressive"),
    "public_spending": ("expand", "reduce"),
    # Specific regulated/public-service price position; retained issue-only so
    # a user-fee stance is not silently recoded as taxation or spending.
    "public_utility_rates": ("increase", "decrease"),
    # Substantive legalization/availability of lotteries, bingo, casinos, and
    # related gaming. Kept issue-only rather than treating gambling as a
    # generic social-liberty or revenue position.
    "gambling_policy": ("expand", "restrict"),
    "deficit_discipline": ("fiscal_restraint", "fiscal_flexibility"),
    "welfare_generosity": ("expand", "restrict"),
    "welfare_conditionality": ("strengthen_conditions", "relax_conditions"),
    "labor_capital_alignment": ("labor", "capital_management"),
    "labor_rights": ("expand", "restrict"),
    "public_employee_compensation": ("protect", "reduce"),
    "business_subsidy": ("expand", "restrict"),
    "childcare_support": ("expansion", "restriction"),
    "childcare_delivery": ("public_provision", "family_subsidy", "employer_incentive", "employer_mandate", "regulation_quality"),
    "family_support_enforcement": ("strict_enforcement", "lenient_enforcement"),
    "healthcare_access": ("expand", "restrict"),
    "healthcare_public_responsibility": ("public_responsibility", "private_responsibility"),
    "healthcare_delivery": ("public_delivery", "private_delivery"),
    "healthcare_regulation_patient_rights": ("strengthen", "weaken"),
    "medicaid_structure": ("managed_care", "direct_public_program"),
    "malpractice_liability": ("limit_damages", "preserve_claims"),
    "bioethics_end_of_life": ("permissive", "restrictive"),
    "education_public_funding": ("expand", "reduce"),
    "education_market_choice": ("expand", "restrict"),
    "education_accountability": ("strengthen", "weaken"),
    "education_teacher_labor": ("support", "restrict"),
    "education_access": ("expand", "restrict"),
    "education_curriculum_traditionalism": ("traditional", "pluralist"),
    "environmental_protection": ("strengthen", "weaken"),
    "conservation_preservation": ("preserve", "develop"),
    "resource_development": ("expand", "restrict"),
    "resource_management": ("active_management", "limited_management"),
    "climate_energy": ("decarbonization", "fossil_expansion"),
    "renewable_energy_support": ("expand", "restrict"),
    "land_use_property_rights": ("regulation", "property_rights"),
    "hunting_rural_recreation": ("expand_access", "restrict_access"),
    "abortion_access": ("expand", "restrict"),
    "abortion_public_funding": ("fund", "prohibit_funding"),
    "marriage_equality": ("expand", "restrict"),
    "civil_social_liberty": ("expand", "restrict"),
    "christian_sexual_morality": ("traditional_morality", "sexual_pluralism_autonomy"),
    "racial_civil_rights": ("expand", "restrict"),
    "anti_discrimination": ("expand", "restrict"),
    "affirmative_action": ("use", "prohibit"),
    "religion_state": ("accommodation_establishment", "separation"),
    # Alabama-specific cultural-symbol conflict. Kept issue-level because it
    # should not be mechanically equated with the broader liberty/equality axis.
    "confederate_commemoration": ("preserve", "remove"),
    "gun_access": ("expand", "restrict"),
    "gun_purchase_regulation": ("strengthen", "weaken"),
    "criminal_punishment": ("punitive", "rehabilitative"),
    "incarceration": ("expand", "reduce"),
    "due_process": ("strengthen", "weaken"),
    "police_authority": ("expand", "restrict"),
    "drug_criminalization": ("criminalize", "decriminalize"),
    "drug_treatment": ("expand", "restrict"),
    "immigration_access": ("expand", "restrict"),
    "immigration_enforcement": ("strengthen", "relax"),
    "immigrant_public_benefits": ("expand", "restrict"),
    "national_language_identity": ("strengthen", "pluralist"),
    "campaign_finance_restrictions": ("strengthen", "weaken"),
    "campaign_finance_disclosure": ("strengthen", "weaken"),
    "campaign_public_funding": ("expand", "restrict"),
    "government_ethics_transparency": ("strengthen", "weaken"),
    "voting_access": ("expand", "restrict"),
    "election_integrity_controls": ("strengthen", "weaken"),
    "term_limits": ("support", "oppose"),
    "redistricting_governance": ("independent_commission", "legislative_control"),
    "direct_democracy": ("expand", "restrict"),
    "constitutional_reform": ("reform", "status_quo"),
    "institutional_populism": ("popular_control", "institutional_control"),
    "security_preparedness": ("expand", "reduce"),
    # Federal-questionnaire supplements, not default Alabama CMO dimensions.
    "defense_spending": ("increase", "decrease"),
    "military_intervention": ("interventionist", "restrained"),
    "multilateralism": ("multilateral", "unilateral"),
    "foreign_aid": ("expand", "restrict"),
    "trade_openness": ("open", "protectionist"),
    "federalism": ("federal_authority", "state_local_authority"),
    "social_security_provision": ("public_insurance", "private_accounts"),
    "social_security_generosity": ("expand", "retrench"),
    "digital_privacy": ("strengthen", "weaken"),
    "digital_content_regulation": ("regulate", "free_expression"),
    "surveillance_authority": ("expand", "restrict"),
}

CONSTITUENCY_TAGS = {
    "small_business", "large_business", "labor_union", "public_employee",
    "low_income", "middle_income", "high_income", "rural", "agriculture",
    "extractive_industry", "healthcare_industry", "education_workforce",
}

# Direction is within the named family, never a universal left/right sign.
LOADINGS = {
    ("market_governance", "intervention"): ("market_government_direction", 1.0),
    ("market_governance", "market_autonomy"): ("market_government_direction", -1.0),
    ("public_private_provision", "public_provision"): ("market_government_direction", 1.0),
    ("public_private_provision", "private_provision"): ("market_government_direction", -1.0),
    ("welfare_generosity", "expand"): ("material_support", 1.0),
    ("welfare_generosity", "restrict"): ("material_support", -1.0),
    ("childcare_support", "expansion"): ("material_support", 1.0),
    ("childcare_support", "restriction"): ("material_support", -1.0),
    ("healthcare_access", "expand"): ("material_support", 1.0),
    ("healthcare_access", "restrict"): ("material_support", -1.0),
    ("labor_capital_alignment", "labor"): ("labor_capital", 1.0),
    ("labor_capital_alignment", "capital_management"): ("labor_capital", -1.0),
    ("labor_rights", "expand"): ("labor_capital", 1.0),
    ("labor_rights", "restrict"): ("labor_capital", -1.0),
    ("marriage_equality", "expand"): ("social_liberty_equality", 1.0),
    ("marriage_equality", "restrict"): ("social_liberty_equality", -1.0),
    ("civil_social_liberty", "expand"): ("social_liberty_equality", 1.0),
    ("civil_social_liberty", "restrict"): ("social_liberty_equality", -1.0),
    ("christian_sexual_morality", "traditional_morality"): ("social_liberty_equality", -1.0),
    ("christian_sexual_morality", "sexual_pluralism_autonomy"): ("social_liberty_equality", 1.0),
    ("racial_civil_rights", "expand"): ("social_liberty_equality", 1.0),
    ("racial_civil_rights", "restrict"): ("social_liberty_equality", -1.0),
    ("anti_discrimination", "expand"): ("social_liberty_equality", 1.0),
    ("anti_discrimination", "restrict"): ("social_liberty_equality", -1.0),
    ("abortion_access", "expand"): ("social_liberty_equality", 1.0),
    ("abortion_access", "restrict"): ("social_liberty_equality", -1.0),
    ("criminal_punishment", "punitive"): ("order_justice", 1.0),
    ("criminal_punishment", "rehabilitative"): ("order_justice", -1.0),
    ("drug_criminalization", "criminalize"): ("order_justice", 1.0),
    ("drug_criminalization", "decriminalize"): ("order_justice", -1.0),
    ("immigration_access", "expand"): ("immigration_inclusion", 1.0),
    ("immigration_access", "restrict"): ("immigration_inclusion", -1.0),
    ("environmental_protection", "strengthen"): ("environment_resources", 1.0),
    ("environmental_protection", "weaken"): ("environment_resources", -1.0),
    ("conservation_preservation", "preserve"): ("environment_resources", 1.0),
    ("conservation_preservation", "develop"): ("environment_resources", -1.0),
    ("climate_energy", "decarbonization"): ("environment_resources", 1.0),
    ("climate_energy", "fossil_expansion"): ("environment_resources", -1.0),
    ("institutional_populism", "popular_control"): ("institutional_reform", 1.0),
    ("institutional_populism", "institutional_control"): ("institutional_reform", -1.0),
    ("redistricting_governance", "independent_commission"): ("institutional_reform", 1.0),
    ("redistricting_governance", "legislative_control"): ("institutional_reform", -1.0),
    ("government_ethics_transparency", "strengthen"): ("institutional_reform", 1.0),
    ("government_ethics_transparency", "weaken"): ("institutional_reform", -1.0),
}


def validate_primitive(axis: str, pole: str) -> None:
    if axis not in PRIMITIVES:
        raise ValueError(f"unknown primitive axis: {axis}")
    if pole not in PRIMITIVES[axis]:
        raise ValueError(f"invalid pole {pole!r} for {axis}")


def family_loading(axis: str, pole: str) -> tuple[str | None, float | None]:
    validate_primitive(axis, pole)
    return LOADINGS.get((axis, pole), (None, None))


def primitive_axis_direction(axis: str, pole: str) -> float | None:
    """Orient binary primitive poles on one issue-specific coordinate.

    The first declared pole is +1 and the second is -1. Multi-category delivery
    mechanisms are intentionally non-scalar and return None.
    """
    validate_primitive(axis, pole)
    poles = PRIMITIVES[axis]
    if len(poles) != 2:
        return None
    return 1.0 if pole == poles[0] else -1.0
