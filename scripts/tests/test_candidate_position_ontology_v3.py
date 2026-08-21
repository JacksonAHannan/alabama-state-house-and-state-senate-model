import pandas as pd

from build_candidate_position_evidence_v3 import validate
from ideology_ontology_v3 import FAMILIES, LOADINGS, ONTOLOGY_VERSION, PRIMITIVES, family_loading, primitive_axis_direction


def test_ontology_has_eight_cmo_families_and_valid_loadings():
    assert len(FAMILIES) == 8
    for (axis, pole), (family, direction) in LOADINGS.items():
        assert axis in PRIMITIVES
        assert pole in PRIMITIVES[axis]
        assert family in FAMILIES
        assert direction in {-1.0, 1.0}
        assert family_loading(axis, pole) == (family, direction)


def test_v3_item_crosswalk_is_complete_and_authority_is_explicit():
    items = pd.read_csv("data/processed/ideology/votesmart_pct_item_crosswalk_v3.csv")
    assert len(items) == 1729
    assert items.item_id_v3.nunique() == 1729
    assert items.score_eligible_v3.sum() == 557
    assert (items.mapping_authority_v3 == "direct_text_review").sum() == 23
    assert (items.mapping_authority_v3 == "legacy_rule_requires_v3_review").sum() == 55


def test_votesmart_evidence_conforms_to_shared_contract():
    path = "data/processed/ideology/candidate_position_evidence_v3_votesmart.csv"
    evidence = validate(pd.read_csv(path).fillna(""), __import__("pathlib").Path(path))
    assert len(evidence) == 10945
    assert evidence.evidence_id.nunique() == len(evidence)
    assert set(evidence.ontology_version) == {ONTOLOGY_VERSION}
    assert not evidence.adjudication_authority.str.contains("provisional").any()


def test_questionnaire_features_are_not_a_single_overall_score():
    features = pd.read_csv("data/processed/ideology/votesmart_candidate_family_features_v3.csv")
    # Candidate coverage grows as historical identities are resolved.  Test
    # the one-row-per-candidate contract rather than freezing a corpus count.
    assert len(features) == features.canonical_candidate_id.nunique()
    assert len(features) > 0
    assert "overall_ideology" not in features.columns
    assert "social_liberty_equality" in features.columns
    assert "market_government_direction" in features.columns


def test_opposite_primitive_poles_have_opposite_axis_direction():
    assert primitive_axis_direction("abortion_access", "expand") == 1
    assert primitive_axis_direction("abortion_access", "restrict") == -1
    assert primitive_axis_direction("childcare_delivery", "public_provision") is None
