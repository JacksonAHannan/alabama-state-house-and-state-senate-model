from scripts.build_caucus_analysis_page import build, payload


def test_payload_uses_validated_current_cluster_outputs():
    data = payload()
    assert len(data["members"]) == 281
    assert {row["party"] for row in data["members"]} == {"D", "R"}
    selected = {row["party"]: row["clusters"] for row in data["diagnostics"]}
    assert selected == {"D": 2, "R": 3}
    assert all(row["candidate_cmo"] is not None for row in data["members"])
    assert len(data["issues"]) >= 17


def test_page_has_interactive_controls_and_candidate_detail():
    html = build()
    for element_id in ("party", "issue", "outcome", "era", "clusters", "profile", "eras",
                       "performance", "scatter", "candidate", "search", "rows"):
        assert f'id="{element_id}"' in html
    assert "renderProfile" in html
    assert "renderScatter" in html
    assert "renderCandidate" in html
    assert "Cluster assignment uses issue positions only" in html
    assert "Weak discrete structure" in html
    assert "__DATA__" not in html


def test_page_is_self_contained_and_public_builder_registered():
    html = build()
    assert "caucuses.html" in html
    assert "https://cdn" not in html
    from scripts import build_blue_oxblood_site as site
    assert "build_caucus_analysis_page.py" in site.BUILDERS
    assert "caucuses.html" in site.PUBLIC_PAGES
    from scripts.build_ideology_thesis_page import build as build_ideology
    assert 'href="caucuses.html"' in build_ideology()
