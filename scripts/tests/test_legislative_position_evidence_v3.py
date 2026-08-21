import pandas as pd

from build_legislative_position_evidence_v3 import TRANSLATIONS, general_election_date, text_mapping
from ideology_ontology_v3 import validate_primitive


def test_every_legacy_translation_is_a_valid_v3_primitive():
    for axis, pole in TRANSLATIONS.values():
        validate_primitive(axis, pole)


def test_tax_budget_is_not_coerced_to_one_axis():
    assert not any(issue == "taxes_budget" for issue, _ in TRANSLATIONS)


def test_specific_text_rules_adjudicate_policy_not_broad_topic():
    assert text_mapping(pd.Series({"title": "Income tax deduction for qualified overtime income", "description": ""}))[:2] == ("tax_burden", "decrease")
    assert text_mapping(pd.Series({"title": "General fund budget appropriations", "description": ""})) is None


def test_general_election_cutoff_is_tuesday_after_first_monday():
    assert str(general_election_date(2022)) == "2022-11-08"
    assert str(general_election_date(2018)) == "2018-11-06"
