from __future__ import annotations

import pandas as pd

from scripts.build_ideology_performance_page import build, payload


def test_payload_uses_absolute_rebuild_contract() -> None:
    data = payload()
    assert data["stats"]["shorN"] == 407
    assert data["stats"]["demCmo"] > 10
    assert data["stats"]["demFederal"] > 10
    assert data["stats"]["commonSupport"] == 37
    assert {row["sample"] for row in data["absolute"]} == {"D", "R"}
    assert len(data["shorPoints"]) == 407
    assert len(data["issueRows"]) >= 4_000


def test_primitive_axes_are_distinct_and_explained() -> None:
    data = payload()
    metadata = {row["key"]: row for row in data["issueMeta"]}
    assert metadata["gun_access"]["label"] == "Gun access"
    assert metadata["racial_civil_rights"]["label"] == "Racial civil rights"
    assert metadata["civil_social_liberty"]["label"] == "Christian sexual morality"
    assert metadata["tax_burden"]["label"] == "Tax burden"
    assert metadata["tax_distribution"]["label"] == "Who bears taxes"
    assert "Racial civil rights are excluded" in metadata["civil_social_liberty"]["description"]
    assert "separate" in metadata["gun_access"]["description"]


def test_page_contains_merged_visual_system() -> None:
    html = build()
    for element_id in (
        "performance", "headline", "transition", "transitionChart", "positions",
        "profileChart", "performanceDistribution", "time", "eraEvidence", "issues",
        "issueSelect", "issuePlot", "issueCoverage", "cases", "caseStudies",
        "candidate-explorer", "constellation", "candidateDetail", "candidateRows", "methods",
    ):
        assert f'id="{element_id}"' in html
    assert "traditionalist-populist bloc ran substantially farther ahead" in html
    assert "Election performance was not used to assign candidates" in html
    assert "not proof that any one issue caused" in html
    assert "renderTransition" in html
    assert "renderConstellation" in html
    assert 'aria-live="polite"' in html


def test_page_uses_utilitarian_research_structure() -> None:
    html = build()
    assert 'class="contents" aria-label="On this page"' in html
    assert "Alabama Democratic blocs, 1998–2022" in html
    for section_id in (
        "performance", "transition", "positions", "time", "issues", "cases",
        "candidate-explorer", "methods",
    ):
        assert f'id="{section_id}"' in html
        assert f'href="#{section_id}"' in html
    assert "How Alabama Democrats kept outrunning partisanship" not in html


def test_legacy_analysis_artifacts_are_absent() -> None:
    html = build()
    for stale in (
        "conservative_fit_score", "matched pairs", "principal components",
        "Why guns now appear correctly", "Every issue, era, and candidate observation",
        "undefined", "Three-dimensional", "render3D", "threeD",
    ):
        assert stale not in html


def test_page_is_self_contained_and_safe_for_missing_estimates() -> None:
    html = build()
    assert "__DATA__" not in html
    assert "Not estimated" in html
    assert "No observations for this selection" in html
    assert 'aria-current="page"' in html


def test_era_cards_use_cqi_not_raw_federal_performance() -> None:
    data = payload()
    cqi = {
        row["sample"]: row for row in data["era"]
        if row["outcome"] == "candidate_quality_index"
        and row["sample"].startswith("D:")
    }
    assert 8.9 < cqi["D:pre_2008"]["coefficient"] < 9.2
    assert 7.7 < cqi["D:2008_2014"]["coefficient"] < 7.9
    assert cqi["D:post_2016"]["status"] == "underpowered"

    html = build()
    assert "CQI association by era" in html
    assert "const outcome='candidate_quality_index'" in html
    assert "const outcome='candidate_federal_overperformance',eras" not in html
    assert '"coefficient":7.8007516214' in html
    assert '"coefficient":-2.5043222061' not in html


def test_merged_payload_contains_transition_and_current_clusters() -> None:
    data = payload()
    assert len(data["cluster"]["members"]) == 274
    assert len([row for row in data["cluster"]["members"] if row["party"] == "D"]) == 115
    assert all(row["candidate_quality_index"] is not None
               for row in data["cluster"]["members"])
    assert all("candidate_quality_residual" not in row
               for row in data["cluster"]["members"])
    assert all("candidate_cmo" not in row for row in data["cluster"]["members"])
    assert {row["cycle"] for row in data["democraticTransition"]} == {
        1998, 2002, 2006, 2010, 2014, 2018, 2022,
    }
    federal = next(row for row in data["headlineBlocPerformance"]
                   if row["outcome"] == "candidate_federal_overperformance")
    assert federal["difference"] > 19
    quality = next(row for row in data["headlineBlocPerformance"]
                   if row["outcome"] == "candidate_quality_index")
    assert 2 < quality["difference"] < 3
    assert quality["traditionalist_mean"] > 1
    assert quality["progressive_mean"] < -1
    assert {row["cluster_label"] for row in data["caseStudies"]} == {
        "Progressive-modern Democrats", "Traditionalist-populist Democrats",
    }


def test_page_uses_candidate_quality_index_without_southern_residual() -> None:
    html = build()
    assert 'value="candidate_quality_index">Candidate Quality Index (CQI)</option>' in html
    assert 'value="candidate_cmo"' not in html
    assert "candidate_cmo" not in html
    assert "<span>CMO</span>" not in html
    assert '<th class="num">CQI</th>' in html
    assert "post-2016-invalid Southern structural residual" in html
    assert "candidate_quality_residual" not in html


def test_representative_cases_use_cqi_median() -> None:
    data = payload()
    members = pd.DataFrame(data["cluster"]["members"])
    representatives = [
        row for row in data["caseStudies"]
        if row["kind"] == "Near bloc median CQI"
    ]
    assert len(representatives) == 2
    for case in representatives:
        bloc = members[
            members.party.eq("D")
            & members.cluster_label.eq(case["cluster_label"])
        ]
        median = bloc.candidate_quality_index.median()
        eligible = bloc[
            bloc.candidate_quality_index.notna()
            & bloc.candidate_federal_overperformance.notna()
        ].copy()
        expected = eligible.loc[
            (eligible.candidate_quality_index - median).abs().idxmin()
        ]
        assert case["canonical_candidate_id"] == expected.canonical_candidate_id
    traditionalist = next(
        row for row in representatives
        if row["cluster_label"] == "Traditionalist-populist Democrats"
    )
    assert traditionalist["name"] == "Boyd"
    assert traditionalist["name"] != "White"


def test_modern_cqi_does_not_inherit_failed_southern_prior_sign() -> None:
    members = pd.DataFrame(payload()["cluster"]["members"])
    modern = members[(members.party == "D") & (members.era == "post_2016")]
    means = modern.groupby("cluster_label").candidate_quality_index.mean()
    assert means["Traditionalist-populist Democrats"] > 5
    assert abs(means["Progressive-modern Democrats"]) < 1


def test_public_docs_is_not_written_by_release_candidate_builder() -> None:
    from scripts import build_democratic_transition_page as builder

    assert "artifacts" in builder.OUTPUT.parts
    assert "docs" not in builder.OUTPUT.parts
