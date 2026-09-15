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

from scripts import build_democratic_caucus_page as page

LABELS = {
    "Progressive Democrats", "Mainstream statehouse Democrats", "Institutional traditionalists",
    "Rural labor Democrats", "Old-guard conservative Democrats",
}


@pytest.fixture(scope="module")
def data():
    return page.payload()


def test_groups_carry_the_approved_labels(data):
    assert {group["label"] for group in data["groups"]} == LABELS
    approved = pd.read_csv(page.LABELS)
    assert set(approved.label) == LABELS
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


def test_unresolved_identities_are_labelled_by_seat_not_invented(data):
    unresolved = [m for m in data["members"] if not m["identityResolved"]]
    assert len(unresolved) == data["coverage"]["peopleWithUnresolvedIdentity"]
    assert unresolved, "the 2022 canonical identity gap is still open and must stay visible"
    for member in unresolved:
        assert member["name"].startswith("Unnamed ")
    assert not any(page.SOURCE_ID_PATTERN.fullmatch(str(m["name"])) for m in data["members"])


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
