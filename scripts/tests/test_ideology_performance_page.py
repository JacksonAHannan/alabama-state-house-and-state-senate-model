from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from scripts.build_ideology_performance_page import build, payload


ROOT = Path(__file__).resolve().parents[2]
TRADITIONALIST = "Traditionalist-populist Democrats"
BRIDGE = "Bridge-coalition Democrats"
PROGRESSIVE = "Progressive-modern Democrats"
GROUPS = {TRADITIONALIST, BRIDGE, PROGRESSIVE}


def test_payload_uses_current_three_group_contract() -> None:
    data = payload()
    current = pd.read_csv(
        ROOT / "research/cmo_ideology/democratic_clusters/democratic_candidate_cluster_membership.csv",
        low_memory=False,
    )
    assert data["schemaVersion"] == 3
    assert set(data["groups"]) == GROUPS
    assert len(data["members"]) == len(current)
    assert len([row for row in data["members"] if row["party"] == "D"]) == int(current.party.eq("D").sum())
    assert {row["cluster_label"] for row in data["members"] if row["party"] == "D"} == GROUPS
    assert all("candidate_cmo" not in row for row in data["members"])
    assert all("candidate_quality_residual" not in row for row in data["members"])
    assert all(row["candidate_cycle_war"] is not None for row in data["members"])
    assert all(row["war_scoring_scope"] in {
        "post2016_southern_model_backcast", "published_same_cycle_residual"
    } for row in data["members"])
    assert all("candidate_quality_index" not in row for row in data["members"])


def test_group_summaries_are_recomputed_from_members() -> None:
    data = payload()
    members = pd.DataFrame(data["members"])
    outcomes = {
        "candidate_cycle_war",
        "candidate_federal_overperformance",
        "candidate_presidential_overperformance",
    }
    assert len(data["groupSummary"]) == 9
    assert {row["group"] for row in data["groupSummary"]} == GROUPS
    assert {row["outcome"] for row in data["groupSummary"]} == outcomes
    for row in data["groupSummary"]:
        values = members.loc[
            members.party.eq("D") & members.cluster_label.eq(row["group"]),
            row["outcome"],
        ].dropna()
        assert row["n"] == len(values)
        assert abs(row["mean"] - values.mean()) < 1e-9


def test_adjusted_comparisons_include_both_nonreference_groups() -> None:
    data = payload()
    assert len(data["contrasts"]) == 6
    assert {row["group"] for row in data["contrasts"]} == {TRADITIONALIST, BRIDGE}
    assert {row["reference_group"] for row in data["contrasts"]} == {PROGRESSIVE}
    assert all(row["method"] == "cycle_chamber_fixed_effects_person_clustered_se" for row in data["contrasts"])
    quality = next(
        row for row in data["contrasts"]
        if row["group"] == TRADITIONALIST and row["outcome"] == "candidate_cycle_war"
    )
    assert quality["difference"] > 0
    assert quality["ci_low"] > 0


def test_transition_profiles_and_trends_use_all_three_groups() -> None:
    data = payload()
    transition = pd.DataFrame(data["transition"])
    assert set(transition.cluster_label) == GROUPS
    assert set(transition.cycle) == {1998, 2002, 2006, 2010, 2014, 2018, 2022}
    for _, rows in transition.groupby("cycle"):
        assert abs(rows.share.sum() - 1) < 1e-9
    assert len(data["profiles"]) >= 15
    assert all({"traditionalist", "bridge", "progressive", "range"} <= set(row) for row in data["profiles"])
    assert all(row["range"] >= 0 for row in data["profiles"])
    assert {row["group"] for row in data["cyclePerformance"]} == GROUPS


def test_cases_cover_every_group_and_use_reproducible_selection() -> None:
    data = payload()
    counts = Counter(row["group"] for row in data["cases"])
    assert counts == {group: 2 for group in GROUPS}
    assert {row["kind"] for row in data["cases"]} == {
        "Near group median WAR",
        "Upper-decile federal overperformance",
    }
    members = pd.DataFrame(data["members"])
    for case in [row for row in data["cases"] if row["kind"] == "Near group median WAR"]:
        group = members[
            members.party.eq("D")
            & members.cluster_label.eq(case["group"])
            & members.candidate_cycle_war.notna()
            & members.candidate_federal_overperformance.notna()
        ].copy()
        distances = (group.candidate_cycle_war - group.candidate_cycle_war.median()).abs()
        selected_distance = float(distances[
            group.canonical_candidate_id.eq(case["canonical_candidate_id"])
        ].iloc[0])
        # JSON precision can reverse an exact near-tie at the final decimal.
        assert selected_distance <= float(distances.min()) + 1e-6


def test_evidence_coverage_is_current_and_exhaustive() -> None:
    data = payload()
    evidence = pd.read_csv(
        ROOT / "data/processed/ideology/candidate_position_evidence_v3_all_sources.csv",
        low_memory=False,
    )
    assert sum(row["evidence_rows"] for row in data["sourceCoverage"]) == len(evidence)
    assert {row["source_category"] for row in data["sourceCoverage"]} >= {
        "Recorded legislative votes",
        "Candidate questionnaires",
        "Interest-group evidence",
    }
    assert data["diagnostics"]["clusters"] == 3
    assert data["diagnostics"]["features"] >= 17
    assert 0 <= data["diagnostics"]["silhouette"] <= 1
    assert 0 <= data["diagnostics"]["bootstrap_ari_mean"] <= 1


def test_page_rebuilds_every_section_and_graphic() -> None:
    html = build()
    for section_id in (
        "overview", "performance", "transition", "positions", "distribution",
        "time", "issues", "cases", "candidate-explorer", "continuous", "methods",
    ):
        assert f'id="{section_id}"' in html
        assert f'href="#{section_id}"' in html
    for graphic_id in (
        "warHeadline", "groupGrid", "contrastList", "ticketContrastList",
        "transitionChart", "profileChart",
        "performanceDistribution", "trendChart", "issuePlot", "issueCoverage",
        "caseStudies", "constellation", "candidateDetail", "candidateRows",
        "eraEvidence", "sourceGrid",
    ):
        assert f'id="{graphic_id}"' in html
    for renderer in (
        "renderWarHeadline", "renderGroups", "renderContrasts", "renderTransition", "renderProfiles",
        "renderDistribution", "renderTrend", "renderIssue", "renderCases",
        "renderConstellation", "renderRows", "renderEra", "renderSources",
    ):
        assert f"function {renderer}" in html


def test_page_language_and_measurements_are_explicit() -> None:
    html = build()
    for group in GROUPS:
        assert group in html
    assert "WAR is the candidate-oriented race residual" in html
    assert "Race-residual WAR" in html
    assert "Candidate Quality Index" not in html
    assert "CQI" not in html
    assert "Raw margin overperformance versus federal candidates" in html
    assert "versus the previous presidential result" in html
    assert "Shor" in html and "McCarty" in html
    assert "separate continuous measurement" in html.lower()
    assert "Election performance was not used to create the groups" in html
    assert "https://split-ticket.org/2025/08/15/deconstructing-war/" in html
    assert "Split Ticket's WAR methodology" in html
    assert html.index('id="performance"') < html.index('id="overview"')
    assert "const OUTCOME_LABELS={candidate_cycle_war:'Race-residual WAR'" in html
    assert "No pooled individual effect, fundraising term, or ideology term enters WAR" in html
    assert "post-2016 Southern races" in html
    for stale in (
        "candidate_cmo", "candidate_quality_residual", "candidate_quality_index",
        "two blocs", "binary comparison",
        "Three-dimensional", "Candidate Atlas", "undefined", "https://cdn",
    ):
        assert stale not in html


def test_release_candidate_is_local_only() -> None:
    from scripts import build_democratic_transition_page as builder
    assert "artifacts" in builder.OUTPUT.parts
    assert "docs" not in builder.OUTPUT.parts
    html = build()
    assert "__DATA__" not in html
    assert 'aria-live="polite"' in html


def test_focusable_chart_points_receive_accessible_names() -> None:
    html = build()
    assert "dot.setAttribute('aria-label'" in html
    assert "circle.setAttribute('role','button')" in html
    assert "circle.setAttribute('aria-label'" in html
    assert "percent issue-dimension coverage" in html
