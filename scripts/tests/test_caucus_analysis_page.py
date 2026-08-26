from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from scripts.build_caucus_analysis_page import build, payload


def test_payload_uses_validated_current_cluster_outputs() -> None:
    data = payload()
    root = Path(__file__).resolve().parents[2]
    focal = pd.read_csv(root / "research/cmo_ideology/democratic_clusters/democratic_candidate_cluster_membership.csv")
    diagnostics = pd.read_csv(root / "research/cmo_ideology/democratic_clusters/cluster_model_diagnostics.csv")
    assert len(data["members"]) == len(focal)
    assert {row["party"] for row in data["members"]} == {"D", "R"}
    selected = {row["party"]: row["clusters"] for row in data["diagnostics"]}
    expected = dict(zip(diagnostics.loc[diagnostics.selected, "party"],
                        diagnostics.loc[diagnostics.selected, "clusters"]))
    assert selected == expected
    assert all(row["candidate_cmo"] is not None for row in data["members"])
    assert len(data["issues"]) >= 17
    selected_features = dict(zip(
        diagnostics.loc[diagnostics.selected, "party"],
        diagnostics.loc[diagnostics.selected, "features"],
    ))
    assert data["constellation"]["D"]["dimensions"] == selected_features["D"]
    democratic_labels = {
        row["cluster_label"] for row in data["members"] if row["party"] == "D"
    }
    assert democratic_labels == {
        "Traditionalist-populist Democrats",
        "Bridge-coalition Democrats",
        "Progressive-modern Democrats",
    }
    assert data["constellation"]["R"]["dimensions"] == selected_features["R"]
    assert all(math.isfinite(row["constellation_x"]) and math.isfinite(row["constellation_y"])
               for row in data["members"])


def test_old_page_is_a_compatibility_redirect() -> None:
    html = build()
    assert 'http-equiv="refresh"' in html
    assert 'ideology-performance.html#candidate-explorer' in html
    assert "location.replace" in html
    assert "Legislative caucus explorer" not in html
    assert "render3D" not in html


def test_redirect_is_registered_with_public_builder() -> None:
    html = build()
    assert "https://cdn" not in html
    from scripts import build_blue_oxblood_site as site
    assert "build_caucus_analysis_page.py" in site.BUILDERS
    assert "build_democratic_transition_page.py" in site.BUILDERS
    assert "caucuses.html" in site.PUBLIC_PAGES
    from scripts.build_ideology_thesis_page import build as build_ideology
    assert 'href="caucuses.html"' not in build_ideology()
    assert 'Ideology &amp; caucuses' in build_ideology()
