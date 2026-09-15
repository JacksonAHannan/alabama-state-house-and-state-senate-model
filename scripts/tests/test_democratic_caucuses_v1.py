"""Contract tests for the person-level Democratic caucus groupings.

The properties tested here are the ones a reader of the public page depends on:
groups are formed from issue evidence alone, uncontested Democrats are grouped,
missing WAR stays missing, the published k follows the stated stability rule and
every ungrouped person is accounted for with a reason.
"""
import json

import numpy as np
import pandas as pd
import pytest

from build_democratic_caucuses_v1 import (
    MIN_CLUSTER_N,
    MIN_FEATURE_PEOPLE,
    MIN_POLE_PEOPLE,
    OUT,
    centre_within,
    choose_k,
    eligible_features,
    order_clusters,
    person_features,
)

OUTCOME_COLUMNS = {
    "candidate_cycle_war", "candidate_raw_gap", "candidate_structural_expected_gap",
    "candidate_federal_ticket_cmo", "candidate_presidential_ticket_cmo", "winner", "career_war",
}


@pytest.fixture(scope="module")
def manifest():
    return json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def profiles():
    return pd.read_csv(OUT / "person_profiles.csv")


def test_groups_are_built_from_issue_families_only(manifest, profiles):
    features = manifest["configuration"]["features"]
    assert manifest["configuration"]["feature_spec"] == "ontology_v3_issue_families"
    assert features and not any(feature.startswith("axis:") for feature in features)
    assert OUTCOME_COLUMNS.isdisjoint(profiles.columns)
    assert manifest["configuration"]["excluded_axis_features"], "axis exclusion must stay auditable"


def test_uncontested_democrats_are_grouped(manifest):
    """WAR is attached after clustering, so a person with no scored race still gets a group."""
    membership = pd.read_csv(OUT / "person_membership.csv")
    assert membership.cluster_rank.notna().all()
    assert membership.cycles_scored.eq(0).sum() > 0
    assert int(manifest["diagnostics"]["candidate_cycles_unscored"]) > 0


def test_unscored_candidate_cycles_stay_missing(manifest):
    cycles = pd.read_csv(OUT / "member_cycles.csv")
    unscored = cycles[~cycles.war_scored]
    assert len(unscored) == int(manifest["diagnostics"]["candidate_cycles_unscored"])
    assert unscored.candidate_cycle_war.isna().all()
    assert cycles[cycles.war_scored].candidate_cycle_war.notna().all()


def test_published_k_follows_the_stability_rule(manifest):
    diagnostics = pd.read_csv(OUT / "cluster_diagnostics.csv")
    selected = diagnostics[diagnostics.selected]
    assert len(selected) == 1
    assert int(selected.clusters.iloc[0]) == choose_k(diagnostics) == manifest["configuration"]["selected_k"]
    assert int(selected.smallest_cluster.iloc[0]) >= MIN_CLUSTER_N


def test_every_person_is_grouped_or_explained(manifest):
    membership = pd.read_csv(OUT / "person_membership.csv")
    unclustered = pd.read_csv(OUT / "unclustered_people.csv")
    assert len(membership) + len(unclustered) == int(manifest["diagnostics"]["democratic_people"])
    assert set(unclustered.reason) <= {"no_ontology_evidence", "below_minimum_features"}
    assert unclustered[unclustered.reason.eq("no_ontology_evidence")].features_observed.eq(0).all()


def test_sensitivity_records_era_channel_and_threshold(manifest):
    sensitivity = pd.read_csv(OUT / "cluster_sensitivity.csv").iloc[0]
    for column in ("era_normalized_ari", "all_source_vs_legislative_only_ari",
                   "position_vs_missingness_ari", "knn_vs_median_ari", "threshold_ari"):
        assert -1.0 <= float(sensitivity[column]) <= 1.0
    assert manifest["diagnostics"]["era_normalized_ari"] == pytest.approx(sensitivity.era_normalized_ari)


def test_one_sided_features_are_not_eligible():
    people_count = MIN_FEATURE_PEOPLE + MIN_POLE_PEOPLE
    wide = pd.DataFrame({
        "two_sided": np.linspace(-1.0, 1.0, people_count),
        "one_sided": np.linspace(0.4, 1.0, people_count),
        "thin": [0.9, -0.9] + [np.nan] * (people_count - 2),
    })
    inventory = eligible_features(wide).set_index("feature")
    assert bool(inventory.loc["two_sided", "eligible"])
    assert not bool(inventory.loc["one_sided", "eligible"])
    assert not bool(inventory.loc["thin", "eligible"])


def test_person_position_is_evidence_weighted():
    signed = pd.DataFrame({
        "person_id": ["p1", "p1", "p2"],
        "feature": ["labor_capital"] * 3,
        "value": [1.0, -1.0, 0.5],
        "weight": [3.0, 1.0, 1.0],
        "evidence_id": ["e1", "e2", "e3"],
        "source_type": ["legislative_vote", "questionnaire", "questionnaire"],
        "legislative": [True, False, False],
    })
    wide, table = person_features(signed)
    assert wide.loc["p1", "labor_capital"] == pytest.approx(0.5)
    assert int(table[table.person_id.eq("p1")].legislative_records.iloc[0]) == 1


def test_clusters_are_ranked_from_the_liberal_pole():
    sample = pd.DataFrame({
        "social_liberty_equality": [1.0, 0.9, -1.0, -0.9],
        "order_justice": [-1.0, -0.9, 1.0, 0.9],
    })
    ranks = order_clusters(sample, list(sample.columns), np.array([7, 7, 3, 3]))
    assert ranks[7] == 1 and ranks[3] == 2


def test_era_centring_survives_a_constant_block():
    constant = pd.Series([0.5, 0.5, 0.5])
    assert centre_within(constant).tolist() == [0.0, 0.0, 0.0]
    assert centre_within(pd.Series([1.0, -1.0])).abs().tolist() == [1.0, 1.0]
