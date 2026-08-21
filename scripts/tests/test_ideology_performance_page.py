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


def test_page_contains_rebuilt_visual_system() -> None:
    html = build()
    for element_id in (
        "absoluteScatter", "selection", "decomposition", "issueForest",
        "issueSelect", "issueScatter", "issueSummary", "fitForest", "eras",
    ):
        assert f'id="{element_id}"' in html
    assert "Ideology no longer defines the expectation" in html
    assert "culturally conservative but economically mixed" in html
    assert "False-discovery-adjusted" in html
    assert "Underpowered" in html


def test_page_uses_editorial_research_template() -> None:
    html = build()
    assert 'class="article-grid"' in html
    assert 'class="toc" aria-label="On this page"' in html
    assert "Editorial research template" in html
    for section_id in (
        "measure", "absolute", "selection-audit", "mechanisms", "issues",
        "evidence", "district-fit", "time", "limits",
    ):
        assert f'id="{section_id}"' in html
        assert f'href="#{section_id}"' in html
    assert "How Alabama Democrats kept outrunning partisanship" not in html


def test_legacy_analysis_artifacts_are_absent() -> None:
    html = build()
    for stale in (
        "conservative_fit_score", "cluster_label", "matched pairs",
        "principal components", "Why guns now appear correctly",
        "Every issue, era, and candidate observation", "undefined",
        "2008â", "leftâ", "durabilityâ", "Â·",
    ):
        assert stale not in html


def test_page_is_self_contained_and_safe_for_missing_estimates() -> None:
    html = build()
    assert "__DATA__" not in html
    assert "v==null?'—'" in html
    assert "No adequately powered estimates" in html
    assert "No observations" in html
    assert 'aria-current="page"' in html


def test_public_docs_is_not_written_by_release_candidate_builder() -> None:
    from scripts import build_ideology_thesis_page as builder

    assert "artifacts" in builder.OUTPUT.parts
    assert "docs" not in builder.OUTPUT.parts
