import pandas as pd

from build_frontier_rollcall_ontology import canonical_mapping


def test_high_value_issue_translations_remain_distinct():
    assert canonical_mapping("gun_access", "expand")[:2] == ("gun_access", "expand")
    assert canonical_mapping("punitive_law_and_order", "increase_penalties")[:2] == (
        "criminal_punishment", "punitive")
    assert canonical_mapping("racial_civil_rights", "expand_protections")[:2] == (
        "racial_civil_rights", "expand")
    assert canonical_mapping("christian_sexual_morality", "traditional")[:2] == (
        "christian_sexual_morality", "traditional_morality")


def test_targeted_or_ambiguous_concepts_fail_closed():
    assert canonical_mapping("named_nonprofit_sales_tax_exemption", "grant") is None
    assert canonical_mapping("government_administration", "revise") is None


def test_generated_rollcall_ledger_is_complete_and_noncontradictory():
    source = pd.read_csv("data/processed/legislative/comprehensive_rollcall_classifications.csv")
    mapped = pd.read_csv("data/processed/legislative/frontier_rollcall_ontology_v3.csv").fillna("")
    assert set(source.canonical_rollcall_id.astype(str)) == set(mapped.canonical_rollcall_id.astype(str))
    accepted = mapped[mapped.decision.eq("map")]
    assert accepted.groupby(["canonical_rollcall_id", "primitive_axis"]).policy_pole.nunique().max() == 1
    assert accepted.primitive_axis.ne("").all()
    assert accepted.policy_pole.ne("").all()
