from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

import pandas as pd
import numpy as np
import geopandas as gpd
import pytest
import build_southern_war_map as builder
from southern_war_release_gate import ReleaseGateError

from southern_war_map_contract import scheduled_keys_2016_2022, scheduled_keys_2016_2024


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
RUN_IDS = {
    "historicalRunId": "WAR-SOUTH-HIST-V1-FIXTURE",
    "upstreamModelRunId": "WAR-POST2016-V3-FIXTURE",
    "warehouseBuildRunId": "RUN-FIXTURE",
}
# Marker text that must reach the page escaped, never as markup.
RAW_MARKER = "<b>raw</b> & <script>alert(1)</script>"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blocked_release_fixture(root: Path) -> tuple[Path, Path]:
    """Write an exact v3 manifest/decision pair whose decision is blocked."""
    manifest = root / "data/processed/war/post2016_southern_war_v3/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"model_run_id": RUN_IDS["upstreamModelRunId"], "status": "research_candidate_pending_independent_validation"}),
        encoding="utf-8",
    )
    review = root / "project_docs/audits/SOUTHERN_V3_INDEPENDENT_REVIEW_FIXTURE.md"
    review.parent.mkdir(parents=True)
    review.write_text("# Independent review\n\nNot approved.\n", encoding="utf-8")
    decision = root / "project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json"
    decision.write_text(
        json.dumps({
            "schema_version": 1,
            "model_run_id": RUN_IDS["upstreamModelRunId"],
            "manifest_path": manifest.relative_to(root).as_posix(),
            "manifest_sha256": sha256(manifest),
            "decision": "blocked_insufficient_evidence",
            "review_record_path": review.relative_to(root).as_posix(),
            "review_record_sha256": sha256(review),
        }),
        encoding="utf-8",
    )
    assert decision.parents[2] == root
    return manifest, decision


def coverage_rows() -> list[dict[str, str]]:
    """Fixture rows in the historical builder's state_release_coverage.csv shape."""
    rows = []
    for i, (code, name) in enumerate(sorted(builder.STATE_NAMES.items())):
        scored = 100 + 10 * i
        rows.append({
            "historical_war_run_id": RUN_IDS["historicalRunId"],
            "state_code": code,
            "state_name": name,
            "scheduled_slices": "8",
            "empty_scheduled_slices": "2" if code == "VA" else "0",
            "scored_races": str(scored),
            "backcast_2016_races": "20",
            "published_post2016_races": str(scored - 20),
            "strict_races_registered_source_file": str(scored - 3) if code == "AL" else str(scored),
            "strict_races_source_file_unresolved": "3" if code == "AL" else "0",
            "excluded_research_outcomes": "7",
            "excluded_baseline_not_strict": "44" if code == "VA" else "0",
            "excluded_incumbency_experimental": "2" if code == "MS" else "0",
            "finance_complete_races": "0" if code == "MO" else str(scored - 5),
            "plan_provenance": f"provider-reported district; plan vintage unverified {RAW_MARKER}",
            "upstream_model_run_id": RUN_IDS["upstreamModelRunId"],
            "warehouse_build_run_id": RUN_IDS["warehouseBuildRunId"],
        })
    return rows


def test_map_builder_refuses_pending_upstream_before_reading_model_rows(monkeypatch, tmp_path):
    manifest, decision = blocked_release_fixture(tmp_path)
    monkeypatch.setattr(builder, "V3_MANIFEST", manifest)
    monkeypatch.setattr(builder, "V3_RELEASE_DECISION", decision)
    loaded = False

    def forbidden_read(_path):
        nonlocal loaded
        loaded = True
        raise AssertionError("model rows should not be read")

    monkeypatch.setattr(builder, "read_csv", forbidden_read)
    with pytest.raises(ReleaseGateError, match="blocked_insufficient_evidence"):
        builder.build_payload()
    assert loaded is False


def test_map_builder_refuses_inexact_release_decision_before_reading_model_rows(monkeypatch, tmp_path):
    manifest, decision = blocked_release_fixture(tmp_path)
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    monkeypatch.setattr(builder, "V3_MANIFEST", manifest)
    monkeypatch.setattr(builder, "V3_RELEASE_DECISION", decision)
    monkeypatch.setattr(builder, "read_csv", lambda _path: pytest.fail("model rows should not be read"))
    with pytest.raises(ReleaseGateError, match="manifest_sha256"):
        builder.build_payload()


def test_state_limitations_types_rows_and_requires_exactly_fourteen_states():
    limitations = builder.state_limitations(coverage_rows())
    assert set(limitations) == set(builder.STATE_NAMES)
    virginia = limitations["VA"]
    assert virginia["scheduled_slices"] == 8 and virginia["empty_scheduled_slices"] == 2
    assert virginia["excluded_baseline_not_strict"] == 44
    assert all(isinstance(virginia[column], int) for column in builder.STATE_COVERAGE_COUNTS)
    assert virginia["state_name"] == "Virginia"
    assert virginia["plan_provenance"].endswith(RAW_MARKER)
    assert limitations["MO"]["finance_complete_races"] == 0
    assert builder.release_run_ids(limitations) == RUN_IDS
    with pytest.raises(ValueError, match="missing=\\['VA'\\]"):
        builder.state_limitations([row for row in coverage_rows() if row["state_code"] != "VA"])
    extra = dict(coverage_rows()[0], state_code="WV", state_name="West Virginia")
    with pytest.raises(ValueError, match="extra=\\['WV'\\]"):
        builder.state_limitations(coverage_rows() + [extra])
    with pytest.raises(ValueError, match="Duplicate"):
        builder.state_limitations(coverage_rows() + [coverage_rows()[0]])
    bad_count = [dict(row, scored_races="n/a") if row["state_code"] == "AL" else row for row in coverage_rows()]
    with pytest.raises(ValueError, match="non-negative integer"):
        builder.state_limitations(bad_count)
    bad_columns = [{k: v for k, v in row.items() if k != "plan_provenance"} for row in coverage_rows()]
    with pytest.raises(ValueError, match="columns do not match"):
        builder.state_limitations(bad_columns)
    bad_split = [dict(row, backcast_2016_races="21") if row["state_code"] == "AL" else row for row in coverage_rows()]
    with pytest.raises(ValueError, match="do not sum"):
        builder.state_limitations(bad_split)
    mixed_run = [dict(row, warehouse_build_run_id="RUN-OTHER") if row["state_code"] == "TX" else row for row in coverage_rows()]
    with pytest.raises(ValueError, match="2 distinct warehouse_build_run_id"):
        builder.release_run_ids(builder.state_limitations(mixed_run))


def test_observed_state_counts_recompute_reconcilable_columns_from_slices():
    race = lambda scope, status, finance: {"scope": scope, "sourceFileStatus": status, "financeComplete": finance}
    slices = {
        "AL-2018-lower": {"state": "AL", "races": {
            "1": race("post2016_southern_model_backcast", "registered", True),
            "2": race("published_same_cycle_residual", "legacy_lineage_unresolved", False),
        }},
        "AL-2018-upper": {"state": "AL", "races": {}},
        "VA-2017-lower": {"state": "VA", "races": {}},
    }
    counts = builder.observed_state_counts(slices)
    assert set(counts) == set(builder.STATE_NAMES)
    assert counts["AL"] == {
        "scheduled_slices": 2, "empty_scheduled_slices": 1, "scored_races": 2,
        "backcast_2016_races": 1, "published_post2016_races": 1,
        "strict_races_registered_source_file": 1, "strict_races_source_file_unresolved": 1,
        "finance_complete_races": 1,
    }
    assert counts["VA"]["scheduled_slices"] == 1 and counts["VA"]["empty_scheduled_slices"] == 1
    assert counts["TX"] == dict.fromkeys(builder.STATE_COVERAGE_RECONCILED, 0)


def test_limitations_table_lists_every_state_run_id_and_qa_link():
    limitations = builder.state_limitations(coverage_rows())
    table = builder.limitations_table_html(list(limitations.values()), RUN_IDS)
    body = table[table.index("<tbody>") + len("<tbody>"):table.index("</tbody>")]
    assert body.count("<tr>") == 14
    assert body.index("<th scope=\"row\">Alabama</th>") < body.index("<th scope=\"row\">Virginia</th>")
    assert body.startswith('<tr><th scope="row">Alabama</th><td>AL</td>')
    assert set(builder.STATE_COVERAGE_DISPLAY_ORDER) == set(builder.STATE_COVERAGE_COLUMNS)
    assert table.index('<th scope="col">State</th>') < table.index('<th scope="col">Code</th>') < table.index('<th scope="col">Historical WAR run</th>')
    for label in builder.STATE_COVERAGE_HEADERS.values():
        assert f">{html.escape(label)}</th>" in table
    for run_id in RUN_IDS.values():
        assert table.count(f"<code>{run_id}</code>") >= 15
    for href, label in builder.QA_DOWNLOADS:
        assert f'<a href="{href}">{label}</a>' in table
    assert "data/southern_historical_war_v1_state_release_coverage.csv" in table
    assert "data/southern_war_map_join_audit.csv" in table
    assert 'class="table-scroll"' in table and 'tabindex="0"' in table
    assert "<tfoot>" in table and "All 14 states" in table
    assert "0 (0.0%)" in table  # Missouri finance
    assert RAW_MARKER not in table and html.escape(RAW_MARKER) in table


def test_methodology_page_publishes_state_coverage_section_with_escaped_text():
    limitations = builder.state_limitations(coverage_rows())
    method = builder.methodology_html(RUN_IDS["historicalRunId"], limitations, RUN_IDS)
    assert "State coverage and release limitations" in method
    assert method.index("State coverage and release limitations") < method.index("Downloads</h2>")
    assert "Virginia 2017 and 2021 lower-chamber outcomes" in method
    assert "2019-plan cross-election precinct membership" in method
    assert "prior-winner continuity rows without roster evidence" in method
    assert "does not certify the provider’s allocation" in method
    assert "Provider-reported district" in method and "plan vintage unverified" in method
    total_scored = sum(int(row["scored_races"]) for row in coverage_rows())
    assert f"{total_scored - 3:,} of {total_scored:,} strict races resolve to a registered source file" in method
    assert "The remaining 3 (Alabama)" in method
    assert "280 strict 2016 races are backward applications" in method
    assert f"{total_scored - 280:,} races carry the exact residual from Southern WAR v3 run" in method
    assert "No finance-complete races: Missouri." in method
    assert "112 scheduled maps; 2 contain no strict race (Virginia)" in method
    for run_id in RUN_IDS.values():
        assert run_id in method
    assert 'href="data/southern_historical_war_v1_state_release_coverage.csv"' in method
    assert "overflow-x:auto" in method
    assert RAW_MARKER not in method and html.escape(RAW_MARKER) in method
    assert "all 116 scheduled" in method and "strict 2016 races" in method


def test_simplification_retains_valid_louisiana_source_polygons():
    path = ROOT / "data/raw/census/southern_legislative_boundaries_2016_2022/cb_2019_22_sldu_500k.zip"
    original = gpd.read_file(f"zip://{path}").to_crs(5070)
    projected, retained = builder.display_geometry(original)
    assert retained == 2
    assert projected.geometry.is_valid.all()
    for district in ("029", "035"):
        i = original.index[original.SLDUST.eq(district)][0]
        assert original.geometry[i].equals_exact(projected.geometry[i], 0)


def test_geometry_manifest_is_complete_and_hashed() -> None:
    manifest = pd.read_csv(
        ROOT / "data/processed/source_audits/southern_legislative_geography_manifest.csv"
    )
    assert len(manifest) == 116
    assert set(zip(manifest.state_code, manifest.cycle, manifest.chamber)) == scheduled_keys_2016_2024()
    assert {key for key in scheduled_keys_2016_2024() if key[1] <= 2022} == scheduled_keys_2016_2022()
    assert not manifest.duplicated(["state_code", "cycle", "chamber"]).any()
    assert set(manifest.state_code) == {
        "AL", "AR", "FL", "GA", "KY", "LA", "MO", "MS", "NC", "OK", "SC", "TN", "TX", "VA"
    }
    for row in manifest.itertuples(index=False):
        path = ROOT / row.local_path
        assert path.exists()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row.sha256


def test_map_payload_contains_every_slice_outline_and_scored_race() -> None:
    payload = json.loads((DOCS / "data/southern_war_map_payload.json").read_text(encoding="utf-8"))
    model_manifest = json.loads(
        (ROOT / "data/processed/war/southern_historical_war_v1/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["diagnostics"] == {
        "scheduledSlices": 116,
        "geometryFeatures": sum(s["districts"] for s in payload["slices"].values()),
        "scoredRaces": model_manifest["diagnostics"]["scored_races"],
        "candidateRows": model_manifest["diagnostics"]["candidate_cycle_rows"],
        "financeCompleteRaces": model_manifest["diagnostics"]["finance_complete_races"],
    }
    assert len(payload["slices"]) == 116
    assert len([s for s in payload["slices"].values() if s["cycle"] == 2024]) == 20
    assert len([s for s in payload["slices"].values() if s["cycle"] == 2023]) == 6
    assert "AL-2024-lower" not in payload["slices"]
    assert "SC-2022-upper" not in payload["slices"]
    assert payload["slices"]["AL-2022-lower"]["districts"] == 105
    assert len(payload["slices"]["AL-2022-lower"]["races"]) == 25
    assert len(payload["slices"]["VA-2017-lower"]["races"]) == 0
    assert payload["slices"]["MO-2022-lower"]["coverage"]["financeComplete"] == 0
    names = payload["slices"]["AL-2022-lower"]["races"]
    assert names["12"]["demCandidate"] == "James C. Fields, Jr."
    assert names["27"]["demCandidate"] == "Herb Neu"
    assert names["47"]["demCandidate"] == "Christian Coleman"


def test_public_map_explains_missingness_backcast_and_finance() -> None:
    page = (DOCS / "southern-war.html").read_text(encoding="utf-8")
    method = (DOCS / "southern-war-methodology.html").read_text(encoding="utf-8")
    assert 'aria-label="Map filters"' in page
    assert 'tabindex="0"' in page
    assert "Missing WAR is not zero" in page
    assert "Fundraising unavailable" in page
    assert "post-2016-model backcast" in page
    assert "Southern WAR methodology" in method
    assert "strict 2016 races" in method
    assert "Missouri has no usable finance" in method
    assert "all 116 scheduled" in method
    assert 'class="dashboard"' in page
    assert 'viewBox="0 0 640 700"' in page
    assert 'class="racebox"' in page
    assert 'aria-label="District race outcomes and ticket baseline"' in page
    assert 'id="district"' in page
    assert 'id="blue-oxblood-theme"' in page
    assert 'prefers-reduced-motion' in page
    assert 'normalized to observed two-party turnout' in page


def test_map_joins_preserve_votes_and_distinguish_unscored_districts():
    payload = json.loads((DOCS / "data/southern_war_map_payload.json").read_text(encoding="utf-8"))
    audit = pd.read_csv(DOCS / "data/southern_war_map_join_audit.csv")
    assert len(audit) == 116
    assert audit[["unmatched_races", "duplicate_keys", "invalid_geometries"]].eq(0).all().all()
    assert audit.dem_votes_before.eq(audit.dem_votes_after).all()
    assert audit.rep_votes_before.eq(audit.rep_votes_after).all()
    assert audit.matched_races.sum() == payload["diagnostics"]["scoredRaces"]
    assert audit.unscored_features.gt(0).any()
    for section in payload["slices"].values():
        assert set(section["races"]).issubset({f["district"] for f in section["features"]})
        for race in section["races"].values():
            total = race["demVotes"] + race["repVotes"]
            np.testing.assert_allclose(100 * (race["demVotes"] - race["repVotes"]) / total, race["legislativeMargin"], atol=1e-8)
            assert race["sourceProvider"]
            assert bool(race["sourceFileId"]) == (race["sourceFileStatus"] == "registered")
            assert race["electionDate"]
