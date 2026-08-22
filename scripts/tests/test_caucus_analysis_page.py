from scripts.build_caucus_analysis_page import build, payload
import math


def test_payload_uses_validated_current_cluster_outputs():
    data = payload()
    assert len(data["members"]) == 281
    assert {row["party"] for row in data["members"]} == {"D", "R"}
    selected = {row["party"]: row["clusters"] for row in data["diagnostics"]}
    assert selected == {"D": 2, "R": 3}
    assert all(row["candidate_cmo"] is not None for row in data["members"])
    assert len(data["issues"]) >= 17
    assert data["constellation"]["D"]["dimensions"] == 17
    assert data["constellation"]["R"]["dimensions"] == 13
    assert all(math.isfinite(row["constellation_x"]) and math.isfinite(row["constellation_y"])
               for row in data["members"])
    assert all(0 < row["constellation_coverage"] <= 1 for row in data["members"])


def test_page_has_interactive_controls_and_candidate_detail():
    html = build()
    for element_id in ("party", "issue", "outcome", "era", "clusters", "profile", "eras",
                       "performance", "constellationSection", "constellation",
                       "legendConstellation", "coverageConstellation",
                       "scatter", "candidate", "search", "rows"):
        assert f'id="{element_id}"' in html
    assert "renderProfile" in html
    assert "renderScatter" in html
    assert "renderCandidate" in html
    assert "renderConstellation" in html
    assert "ellipseFor" in html
    assert "constellation_coverage" in html
    assert "all issue dimensions used to fit" in html
    assert "threeD" not in html
    assert "Three-dimensional" not in html
    assert "threeIssueTab" not in html
    assert "render3D" not in html
    assert "legend3d" not in html
    assert 'class="constellation-legend"' in html
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
