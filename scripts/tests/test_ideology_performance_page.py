from __future__ import annotations

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


def test_merged_payload_contains_transition_and_current_clusters() -> None:
    data = payload()
    assert len(data["cluster"]["members"]) == 274
    assert len([row for row in data["cluster"]["members"] if row["party"] == "D"]) == 115
    assert all(row["candidate_quality_residual"] is not None
               for row in data["cluster"]["members"])
    assert all("candidate_cmo" not in row for row in data["cluster"]["members"])
    assert {row["cycle"] for row in data["democraticTransition"]} == {
        1998, 2002, 2006, 2010, 2014, 2018, 2022,
    }
    federal = next(row for row in data["headlineBlocPerformance"]
                   if row["outcome"] == "candidate_federal_overperformance")
    assert federal["difference"] > 19
    quality = next(row for row in data["headlineBlocPerformance"]
                   if row["outcome"] == "candidate_quality_residual")
    assert 12 < quality["difference"] < 13
    assert quality["traditionalist_mean"] > 8
    assert quality["progressive_mean"] < -4
    assert {row["cluster_label"] for row in data["caseStudies"]} == {
        "Progressive-modern Democrats", "Traditionalist-populist Democrats",
    }


def test_page_does_not_label_candidate_quality_residual_as_cmo() -> None:
    html = build()
    assert 'value="candidate_quality_residual">Candidate quality residual</option>' in html
    assert 'value="candidate_cmo"' not in html
    assert "candidate_cmo" not in html
    assert "<span>CMO</span>" not in html
    assert '<th class="num">Quality residual</th>' in html
    assert "it is neither Direct CMO nor the career-pooled quality index" in html


def test_public_docs_is_not_written_by_release_candidate_builder() -> None:
    from scripts import build_democratic_transition_page as builder

    assert "artifacts" in builder.OUTPUT.parts
    assert "docs" not in builder.OUTPUT.parts
