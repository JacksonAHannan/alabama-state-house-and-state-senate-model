import pandas as pd

from audit_votesmart_pct_full_ontology import family


def test_full_corpus_audit_covers_every_item():
    audit = pd.read_csv("data/processed/ideology/votesmart_pct_full_corpus_ontology_audit.csv")
    summary = pd.read_csv("data/processed/ideology/votesmart_pct_full_corpus_family_summary.csv")
    assert len(audit) == 1729
    assert audit.normalized_option.nunique() == 1001
    assert summary.year_items.sum() == 1729


def test_family_routing_uses_question_context_when_section_is_blank():
    assert family("", "Should federal immigration laws be enforced?", "Yes") == "immigration"
    assert family("Drug Issues", "", "Decriminalize marijuana") == "drugs"
