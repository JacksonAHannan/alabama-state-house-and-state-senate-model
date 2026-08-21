"""Versioned descriptive ontology for Vote Smart questionnaire positions.

Axes record what a policy does. They do not imply a universal left/right score.
An item may have multiple effects, each with its own axis and pole.
"""

ONTOLOGY_VERSION = "2.0.1"

AXES = {
    # Economic structure and constituency
    "market_governance": ("intervention", "market_autonomy"),
    "welfare_policy": ("expansion", "restriction"),
    "business_scale_alignment": ("small_business", "large_business"),
    "labor_capital_alignment": ("labor", "capital_management"),
    "tax_distribution": ("progressive", "regressive"),
    "tax_burden": ("increase", "decrease"),
    "public_spending": ("expand", "reduce"),
    "public_private_provision": ("public_provision", "private_provision"),
    "public_employee_compensation": ("protect", "reduce"),
    # Child care
    "childcare_support": ("expansion", "restriction"),
    "childcare_delivery": (
        "public_provision", "family_subsidy", "employer_incentive",
        "employer_mandate", "regulation_quality",
    ),
    "family_support_enforcement": ("strict_enforcement", "lenient_enforcement"),
    # Environment, land, and rural recreation
    "environmental_protection": ("strengthen", "weaken"),
    "conservation_preservation": ("preserve", "develop"),
    "resource_development": ("expand", "restrict"),
    "resource_management": ("active_management", "limited_management"),
    "hunting_rural_recreation": ("expand_access", "restrict_access"),
    "land_use_property_rights": ("regulation", "property_rights"),
    "climate_energy": ("decarbonization", "fossil_expansion"),
    "renewable_energy_support": ("expand", "restrict"),
    # Other recurring questionnaire domains remain descriptive axes.
    "abortion_access": ("expand", "restrict"),
    "gun_access": ("expand", "restrict"),
    "labor_rights": ("expand", "restrict"),
    "education_governance": ("public_system", "market_choice"),
    "healthcare_access": ("expand", "restrict"),
    "criminal_punishment": ("punitive", "rehabilitative"),
    "drug_criminalization": ("criminalize", "decriminalize"),
    "immigration_access": ("expand", "restrict"),
    "civil_social_liberty": ("expand", "restrict"),
    "marriage_equality": ("expand", "restrict"),
    "institutional_populism": ("popular_control", "institutional_control"),
    "campaign_finance_restrictions": ("strengthen", "weaken"),
    "redistricting_governance": ("independent_commission", "legislative_control"),
    "security_preparedness": ("expand", "reduce"),
}

DOMAINS = [
    "economy", "welfare", "business", "labor", "taxation", "childcare",
    "environment", "conservation", "natural_resources", "hunting_recreation",
    "energy", "abortion", "guns", "education", "healthcare",
    "criminal_justice", "immigration", "civil_social", "government_reform",
    "other", "non_substantive",
]

EFFECT_STRENGTHS = ["primary", "secondary"]
CONFIDENCE_LEVELS = ["high", "medium", "low"]


def ontology_for_prompt() -> str:
    lines = []
    for axis, poles in AXES.items():
        lines.append(f"- {axis}: {', '.join(poles)}")
    return "\n".join(lines)


def validate_effect(effect: dict) -> None:
    axis = effect.get("axis")
    if axis not in AXES:
        raise ValueError(f"unknown axis: {axis!r}")
    if effect.get("pole") not in AXES[axis]:
        raise ValueError(f"invalid pole {effect.get('pole')!r} for {axis}")
    if effect.get("strength") not in EFFECT_STRENGTHS:
        raise ValueError(f"invalid effect strength: {effect.get('strength')!r}")


def canonical_effects(result: dict) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(
        (effect.get("axis", ""), effect.get("pole", ""))
        for effect in result.get("effects", [])
    ))
