"""Contract tests for the merged Democratic caucus page.

These assert what a reader of the published page can observe: the approved
labels, the coverage funnel, honest treatment of unscored races and unresolved
identities, and the sensitivity disclosure that keeps the groups descriptive.
"""
import json
import re
import shutil

import pandas as pd
import pytest

from scripts import alabama_candidate_identity as identity
from scripts import build_democratic_caucus_page as page

# Owner-approved 2026-10-04 for the two-group solution (the 2026-09-15 five-group labels are kept in
# data/manual/ideology/backups/democratic_caucus_labels.k5-approved-20260915.csv).
LABELS = {"Progressive Democrats", "Traditional Democrats"}


@pytest.fixture(scope="module")
def data():
    return page.payload()


def test_groups_carry_the_approved_labels(data):
    assert {group["label"] for group in data["groups"]} == LABELS
    approved = pd.read_csv(page.LABELS)
    assert set(approved.label) == LABELS
    assert approved.approved_by.eq("owner").all() and not approved.label.str.endswith("(provisional)").any()
    assert data["run"]["labelsSource"].endswith("democratic_caucus_labels.csv")


def test_group_totals_reconcile_with_the_run(data):
    summary = pd.read_csv(page.CAUCUS / "group_summary.csv").set_index("cluster_rank")
    for group in data["groups"]:
        row = summary.loc[group["rank"]]
        assert group["people"] == int(row.people)
        assert group["cyclesScored"] == int(row.cycles_scored)
        assert group["cycleWarMean"] == pytest.approx(float(row.cycle_war_mean))
    assert sum(g["people"] for g in data["groups"]) == data["coverage"]["peopleClustered"]
    assert len(data["members"]) == data["coverage"]["peopleClustered"]


def test_only_scored_races_appear_in_the_performance_view(data):
    assert data["warCycles"], "scored races must be published"
    assert all(row["candidate_cycle_war"] is not None for row in data["warCycles"])
    assert len(data["warCycles"]) == sum(g["cyclesScored"] for g in data["groups"])
    assert data["coverage"]["cyclesUnscored"] > 0


def test_every_member_is_named_from_evidence_never_from_a_source_code(data):
    unresolved = [m for m in data["members"] if not m["identityResolved"]]
    assert len(unresolved) == data["coverage"]["peopleWithUnresolvedIdentity"] == 0, (
        "the 2022 identities are adjudicated; a regression here would publish codes again")
    assert all(m["name"] and not identity.is_stub_name(m["name"]) for m in data["members"])
    # The seat fallback stays available for any future unadjudicated stub.
    fallback = page.resolve_public_names(pd.DataFrame({
        "person_id": ["ALPERSON-GSL099DNOPE"],
        "canonical_candidate_id": ["AL-2022-house-99-D-GSL099DNOPE"],
        "canonical_name": ["GSL099DNOPE"], "cycle": [2022],
        "chamber": ["house"], "district": [99],
    }))
    assert fallback.name.iloc[0] == "Unnamed 2022 HD-99 Democrat"
    assert not bool(fallback.identityResolved.iloc[0])


def test_sensitivity_disclosure_reaches_the_reader(data):
    tests = {row["test"]: row["statistic"] for row in data["sensitivity"]}
    assert "Era-normalized features" in tests
    assert all(-1.0 <= value <= 1.0 for value in tests.values())
    html = page.build()
    assert "not formal caucus membership" in html
    assert '<section id="limits"' in html
    embedded = json.loads(re.search(r"const DATA=(\{.*\});\n", html, re.S).group(1))
    assert [row["test"] for row in embedded["sensitivity"]] == list(tests)
    assert embedded["sensitivity"][-1]["statistic"] == pytest.approx(
        tests["Issue selection (families vs families+axes)"])
    assert "Alabama Legislative Black Caucus" in html


def test_page_renders_every_section_and_renderer():
    html = page.build()
    for section in ("groups", "positions", "performance", "composition",
                    "members", "coverage", "limits", "methods"):
        assert f'<section id="{section}"' in html
    for renderer in ("renderGroups", "renderProfiles", "renderDistribution", "renderComposition",
                     "renderFunnel", "renderSensitivity", "renderMembers", "renderMethods"):
        assert f"function {renderer}" in html
    assert 'aria-live="polite"' in html
    payload = json.loads(re.search(r"const DATA=(\{.*\});\n", html, re.S).group(1))
    assert payload["schemaVersion"] == 4


def test_release_candidate_is_local_only():
    assert "artifacts" in page.OUTPUT.parts and "docs" not in page.OUTPUT.parts


def test_unapproved_labels_refuse_to_render(tmp_path, monkeypatch):
    staged = tmp_path / "caucus"
    shutil.copytree(page.CAUCUS, staged)
    manifest = json.loads((staged / "manifest.json").read_text(encoding="utf-8"))
    manifest["status"] = "descriptive_groupings_labels_pending_owner_review"
    (staged / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(page, "CAUCUS", staged)
    page.payload.cache_clear()
    with pytest.raises(ValueError, match="not approved for rendering"):
        page.payload()
    page.payload.cache_clear()


def test_template_keeps_every_section_renderer_and_a_safe_data_boundary():
    root = page.ROOT / "dashboard"
    html = (root / "ideology_page.html").read_text(encoding="utf-8")
    js = (root / "ideology_page.js").read_text(encoding="utf-8")
    for section in ("groups", "positions", "performance", "composition", "members", "coverage", "limits", "methods"):
        assert f'<section id="{section}"' in html
    for renderer in ("renderGroups", "renderProfiles", "renderScatter", "renderDistribution", "renderComposition",
                     "renderFunnel", "renderSensitivity", "renderMembers", "renderMethods"):
        assert f"function {renderer}" in js
    assert "not formal caucus membership" in html and "Alabama Legislative Black Caucus" in html
    # The page's DATA regex is greedy to the last "};" + newline; the script must never contain one.
    assert "};\n" not in js


def test_group_palette_avoids_party_brand_and_war_colors():
    party_brand_war = {"#2878b5", "#c93f49", "#743b42", "#4b2585", "#8073ac", "#a64b05", "#e08214"}
    assert len(set(page.GROUP_COLORS)) == 5
    assert not set(page.GROUP_COLORS) & party_brand_war
