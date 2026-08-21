from build_ideology_performance_page import build, payload
from run_headline_ideology_tournament import DIMENSIONS


def test_gun_and_racial_headlines_use_distinct_primitive_axes():
    assert DIMENSIONS["gun_rights"] == {
        "gun_access": 1, "gun_purchase_regulation": -1,
    }
    assert DIMENSIONS["racial_and_political_equality"] == {
        "racial_civil_rights": 1, "voting_access": 1,
    }
    assert not set(DIMENSIONS["gun_rights"]) & set(DIMENSIONS["racial_and_political_equality"])


def test_payload_supports_thesis_and_uncertainty():
    data = payload()
    assert data["stats"]["iqr_effect"] > 0
    assert data["stats"]["gop_wins"] >= 50
    assert len(data["scatter"]) >= 300
    assert len(data["matched"]) >= 12
    assert len(data["cases"]) >= 6
    assert len(data["fingerprint"]) >= 500
    assert len(data["observations"]) >= 500
    assert all(row["variation_class"] == "two_sided_usable" for row in data["forest"])
    assert all(row["specification"] == "pooled_historical_association" for row in data["forest"])
    forest = {row["dimension"]: row for row in data["forest"]}
    assert forest["gun_rights"]["iqr_effect"] > 10
    assert forest["gun_rights"]["ci_low"] > 0
    assert forest["racial_and_political_equality"]["ci_low"] < 0 < forest["racial_and_political_equality"]["ci_high"]
    assert {row["headline_dimension"] for row in data["fingerprint"]} <= {
        row["headline_dimension"] for row in data["balance"]
        if row["variation_class"] == "two_sided_usable"
    }
    assert {row["sensitivity"] for row in data["sensitivity"]} >= {
        "all", "majority_white", "nonincumbents", "pre_2008", "post_2016"
    }
    assert {row["term"] for row in data["interactions"]} >= {
        "fit_x_post_2008", "fit_x_post_2016"
    }


def test_page_is_self_contained_and_thesis_led():
    html = build()
    assert "__DATA__" not in html
    assert "How conservative Democrats outran partisanship" in html
    for element_id in (
        "gapChart", "forest", "tiers", "pairs", "cases", "eras",
        "fingerprint", "issueSelect", "counterexamples", "sensitivities",
    ):
        assert f'id="{element_id}"' in html
    assert "Mechanisms, not nuisance controls" in html
    assert "Counterexamples" in html
    assert "historical and associational" in html
    assert 'id="specSelect"' in html
    assert 'id="issueObservations"' in html
    assert "Why guns now appear correctly" not in html
    assert "principal components" not in html.lower()
