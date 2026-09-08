#!/usr/bin/env python3
"""Build the public 2016-2024 Southern legislative WAR explorer."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np

from southern_war_map_contract import scheduled_keys_2016_2024
from southern_war_release_gate import require_approved_release
from site_brand import apply_theme


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "data/processed/war/southern_historical_war_v1"
GEOGRAPHY = ROOT / "data/processed/source_audits/southern_legislative_geography_manifest.csv"
DOCS_DATA = ROOT / "docs/data"
PAYLOAD = DOCS_DATA / "southern_war_map_payload.json"
SITE = ROOT / "docs/southern-war.html"
METHOD = ROOT / "docs/southern-war-methodology.html"
ARTIFACT = ROOT / "artifacts/site/southern-war.html"
TEMPLATE = ROOT / "dashboard/southern_war.html"
EXPLORER_STYLE = ROOT / "dashboard/war_explorer.css"
V3_MANIFEST = ROOT / "data/processed/war/post2016_southern_war_v3/manifest.json"
V3_RELEASE_DECISION = ROOT / "project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json"
JOIN_AUDIT = DOCS_DATA / "southern_war_map_join_audit.csv"
STATE_COVERAGE = MODEL / "state_release_coverage.csv"
STATE_COVERAGE_PUBLIC = DOCS_DATA / "southern_historical_war_v1_state_release_coverage.csv"
STATE_NAMES = {
    "AL": "Alabama", "AR": "Arkansas", "FL": "Florida", "GA": "Georgia",
    "KY": "Kentucky", "LA": "Louisiana", "MO": "Missouri", "MS": "Mississippi",
    "NC": "North Carolina", "OK": "Oklahoma", "SC": "South Carolina",
    "TN": "Tennessee", "TX": "Texas", "VA": "Virginia",
}
# Exact column contract of the historical builder's state_release_coverage.csv,
# in file order.  Readable headers are keyed by the same names so the public
# table mirrors the download column for column.
STATE_COVERAGE_HEADERS = {
    "historical_war_run_id": "Historical WAR run",
    "state_code": "Code",
    "state_name": "State",
    "scheduled_slices": "Scheduled maps",
    "empty_scheduled_slices": "Maps with no strict race",
    "scored_races": "Strict scored races",
    "backcast_2016_races": "2016 backcast races",
    "published_post2016_races": "Published v3 same-cycle races",
    "strict_races_registered_source_file": "Strict races with registered source file",
    "strict_races_source_file_unresolved": "Strict races with unresolved source file",
    "excluded_research_outcomes": "Excluded: research-only outcomes",
    "excluded_baseline_not_strict": "Excluded: baseline not strict",
    "excluded_incumbency_experimental": "Excluded: incumbency experimental",
    "finance_complete_races": "Finance-complete races (share of strict)",
    "plan_provenance": "Plan provenance",
    "upstream_model_run_id": "Upstream v3 model run",
    "warehouse_build_run_id": "Warehouse build run",
}
STATE_COVERAGE_COLUMNS = tuple(STATE_COVERAGE_HEADERS)
# Public table order: the state identifies the row, run identifiers close it.
STATE_COVERAGE_DISPLAY_ORDER = (
    "state_name", "state_code",
    *(column for column in STATE_COVERAGE_COLUMNS if column not in {
        "state_name", "state_code", "historical_war_run_id", "upstream_model_run_id", "warehouse_build_run_id",
    }),
    "historical_war_run_id", "upstream_model_run_id", "warehouse_build_run_id",
)
STATE_COVERAGE_COUNTS = (
    "scheduled_slices", "empty_scheduled_slices", "scored_races", "backcast_2016_races",
    "published_post2016_races", "strict_races_registered_source_file",
    "strict_races_source_file_unresolved", "excluded_research_outcomes",
    "excluded_baseline_not_strict", "excluded_incumbency_experimental",
    "finance_complete_races",
)
RUN_ID_COLUMNS = {
    "historicalRunId": "historical_war_run_id",
    "upstreamModelRunId": "upstream_model_run_id",
    "warehouseBuildRunId": "warehouse_build_run_id",
}
# Per-state counts the map builder can recompute from its own payload and must
# agree with the historical builder's file before publication.
STATE_COVERAGE_RECONCILED = (
    "scheduled_slices", "empty_scheduled_slices", "scored_races", "backcast_2016_races",
    "published_post2016_races", "strict_races_registered_source_file",
    "strict_races_source_file_unresolved", "finance_complete_races",
)
QA_DOWNLOADS = (
    ("data/southern_war_map_join_audit.csv", "Map join audit"),
    ("data/southern_historical_war_v1_state_release_coverage.csv", "State release coverage"),
    ("data/southern_historical_war_v1_manifest.json", "Run manifest"),
    ("data/southern_historical_war_v1_coverage.csv", "Slice coverage"),
)


def number(value: object, default=None):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def integer(value: object, default=0) -> int:
    parsed = number(value)
    return int(parsed) if parsed is not None else default


def normalized_district(value: object) -> str:
    text = str(value).strip()
    if text.isdigit():
        return str(int(text))
    return text


def path_for_geometry(geom, bounds, width=640, height=700, pad=12) -> str:
    minx, miny, maxx, maxy = bounds
    scale = min((width - 2 * pad) / (maxx - minx), (height - 2 * pad) / (maxy - miny))
    ox = (width - (maxx - minx) * scale) / 2
    oy = (height - (maxy - miny) * scale) / 2

    def ring(coords) -> str:
        points = [
            (ox + (x - minx) * scale, height - (oy + (y - miny) * scale))
            for x, y in coords
        ]
        return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in points) + "Z"

    polygons = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    return "".join(
        ring(polygon.exterior.coords)
        + "".join(ring(interior.coords) for interior in polygon.interiors)
        for polygon in polygons if polygon.geom_type == "Polygon"
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def display_geometry(frame: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, int]:
    frame = frame.to_crs(5070)
    simplified = frame.geometry.simplify(1800, preserve_topology=True)
    keep_source = ~simplified.is_valid | simplified.is_empty
    # Keep the valid source outline when simplification breaks a hole or island.
    frame["geometry"] = simplified.where(~keep_source, frame.geometry)
    return frame, int(keep_source.sum())


def state_limitations(rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    """Type the per-state release-coverage rows; exactly one row per scheduled state."""
    limitations: dict[str, dict[str, object]] = {}
    for row in rows:
        if set(row) != set(STATE_COVERAGE_COLUMNS):
            raise ValueError(
                "State release coverage columns do not match the contract: "
                f"missing={sorted(set(STATE_COVERAGE_COLUMNS) - set(row))} "
                f"extra={sorted(set(row) - set(STATE_COVERAGE_COLUMNS))}"
            )
        state = str(row["state_code"]).strip()
        if state in limitations:
            raise ValueError(f"Duplicate state release coverage row: {state}")
        typed: dict[str, object] = {}
        for column in STATE_COVERAGE_COLUMNS:
            text = str(row[column] if row[column] is not None else "").strip()
            if column in STATE_COVERAGE_COUNTS:
                if not text.isdigit():
                    raise ValueError(
                        f"State release coverage count must be a non-negative integer: {state}/{column}={row[column]!r}"
                    )
                typed[column] = int(text)
            else:
                if not text:
                    raise ValueError(f"State release coverage text is empty: {state}/{column}")
                typed[column] = text
        limitations[state] = typed
    if set(limitations) != set(STATE_NAMES):
        raise ValueError(
            "State release coverage must cover exactly the 14 scheduled states: "
            f"missing={sorted(set(STATE_NAMES) - set(limitations))} "
            f"extra={sorted(set(limitations) - set(STATE_NAMES))}"
        )
    for state, typed in limitations.items():
        if typed["state_name"] != STATE_NAMES[state]:
            raise ValueError(f"State release coverage name disagrees for {state}: {typed['state_name']!r}")
        # The label columns partition the strict races; neither may exceed the whole.
        if typed["backcast_2016_races"] + typed["published_post2016_races"] != typed["scored_races"]:
            raise ValueError(f"Backcast and published races do not sum to strict races for {state}")
        if typed["strict_races_registered_source_file"] + typed["strict_races_source_file_unresolved"] != typed["scored_races"]:
            raise ValueError(f"Registered and unresolved source files do not sum to strict races for {state}")
        if typed["finance_complete_races"] > typed["scored_races"]:
            raise ValueError(f"Finance-complete races exceed strict races for {state}")
        if typed["empty_scheduled_slices"] > typed["scheduled_slices"]:
            raise ValueError(f"Empty slices exceed scheduled slices for {state}")
    return limitations


def release_run_ids(limitations: dict[str, dict[str, object]]) -> dict[str, str]:
    """Return the single historical, upstream v3, and warehouse run ID shared by every state."""
    run_ids = {}
    for key, column in RUN_ID_COLUMNS.items():
        values = {str(row[column]) for row in limitations.values()}
        if len(values) != 1:
            raise ValueError(f"State release coverage carries {len(values)} distinct {column} values: {sorted(values)}")
        run_ids[key] = values.pop()
    return run_ids


def observed_state_counts(slices: dict[str, dict[str, object]]) -> dict[str, dict[str, int]]:
    """Recompute the reconcilable per-state coverage counts from the public map slices."""
    counts = {
        state: dict.fromkeys(STATE_COVERAGE_RECONCILED, 0) for state in STATE_NAMES
    }
    for section in slices.values():
        tally = counts[str(section["state"])]
        races = section["races"]
        tally["scheduled_slices"] += 1
        tally["empty_scheduled_slices"] += int(not races)
        for race in races.values():
            tally["scored_races"] += 1
            backcast = "backcast" in str(race["scope"])
            tally["backcast_2016_races"] += int(backcast)
            tally["published_post2016_races"] += int(not backcast)
            registered = race["sourceFileStatus"] == "registered"
            tally["strict_races_registered_source_file"] += int(registered)
            tally["strict_races_source_file_unresolved"] += int(not registered)
            tally["finance_complete_races"] += int(bool(race["financeComplete"]))
    return counts


def _count(value: object) -> str:
    return f"{int(value):,}"


def _share(part: object, whole: object) -> str:
    return "n/a" if not int(whole) else f"{100 * int(part) / int(whole):.1f}%"


def _states_with(rows: list[dict[str, object]], column: str) -> str:
    names = [str(row["state_name"]) for row in rows if int(row[column]) > 0]
    return ", ".join(names) if names else "none"


def limitations_table_html(rows: list[dict[str, object]], run_ids: dict[str, str]) -> str:
    """Render the per-state coverage table, exact run IDs, and machine-readable QA links."""
    rows = sorted(rows, key=lambda row: str(row["state_name"]))
    header = "".join(
        '<th scope="col"' + (' class="num"' if column in STATE_COVERAGE_COUNTS else "") + f">{html.escape(STATE_COVERAGE_HEADERS[column])}</th>"
        for column in STATE_COVERAGE_DISPLAY_ORDER
    )
    body = []
    for row in rows:
        cells = []
        for column in STATE_COVERAGE_DISPLAY_ORDER:
            value = row[column]
            if column == "finance_complete_races":
                cells.append(f'<td class="num">{_count(value)} ({html.escape(_share(value, row["scored_races"]))})</td>')
            elif column in STATE_COVERAGE_COUNTS:
                cells.append(f'<td class="num">{_count(value)}</td>')
            elif column in RUN_ID_COLUMNS.values():
                cells.append(f"<td><code>{html.escape(str(value))}</code></td>")
            elif column == "state_name":
                cells.append(f'<th scope="row">{html.escape(str(value))}</th>')
            else:
                cells.append(f"<td>{html.escape(str(value))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    totals = {column: sum(int(row[column]) for row in rows) for column in STATE_COVERAGE_COUNTS}
    foot = []
    for column in STATE_COVERAGE_DISPLAY_ORDER:
        if column == "finance_complete_races":
            foot.append(f'<td class="num">{_count(totals[column])} ({html.escape(_share(totals[column], totals["scored_races"]))})</td>')
        elif column in STATE_COVERAGE_COUNTS:
            foot.append(f'<td class="num">{_count(totals[column])}</td>')
        elif column == "state_name":
            foot.append('<th scope="row">All 14 states</th>')
        elif column in RUN_ID_COLUMNS.values():
            key = next(k for k, v in RUN_ID_COLUMNS.items() if v == column)
            foot.append(f"<td><code>{html.escape(run_ids[key])}</code></td>")
        else:
            foot.append("<td>—</td>")
    table = (
        '<div class="table-scroll" role="region" aria-label="State coverage and release limitations; scroll horizontally for every column" tabindex="0">'
        '<table class="limitations"><caption>State-level coverage and release limitations, one row per scheduled state. Every column matches the state release coverage download; scroll horizontally for every column.</caption>'
        f"<thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody><tfoot><tr>{''.join(foot)}</tr></tfoot></table></div>"
    )
    ids = (
        '<dl class="run-ids"><dt>Historical WAR run</dt><dd><code>'
        f'{html.escape(run_ids["historicalRunId"])}</code></dd><dt>Upstream Southern WAR v3 run</dt><dd><code>'
        f'{html.escape(run_ids["upstreamModelRunId"])}</code></dd><dt>Warehouse build run</dt><dd><code>'
        f'{html.escape(run_ids["warehouseBuildRunId"])}</code></dd></dl>'
    )
    links = " · ".join(
        f'<a href="{html.escape(href)}">{html.escape(label)}</a>' for href, label in QA_DOWNLOADS
    )
    return f'{table}{ids}<p class="qa-links">Machine-readable QA: {links}</p>'


def limitations_section_html(limitations: dict[str, dict[str, object]], run_ids: dict[str, str]) -> str:
    """Render the state coverage section with prose driven by the coverage rows."""
    rows = sorted(limitations.values(), key=lambda row: str(row["state_name"]))
    total = {column: sum(int(row[column]) for row in rows) for column in STATE_COVERAGE_COUNTS}
    provenance = sorted({str(row["plan_provenance"]) for row in rows})
    provenance_text = "; ".join(
        f"“{html.escape(label)}” ({html.escape(', '.join(str(r['state_name']) for r in rows if r['plan_provenance'] == label))})"
        for label in provenance
    )
    if total["strict_races_source_file_unresolved"]:
        lineage = (
            f"{_count(total['strict_races_registered_source_file'])} of {_count(total['scored_races'])} strict races resolve to a registered source file. "
            f"The remaining {_count(total['strict_races_source_file_unresolved'])} ({html.escape(_states_with(rows, 'strict_races_source_file_unresolved'))}) "
            "carry provider-reported outcomes whose legacy source-file linkage is unresolved; the race download marks them "
            "<code>legacy_lineage_unresolved</code> and the wikibox shows the provider instead of a file identifier. "
            "Their vote totals are observed provider values, not reconstructions."
        )
    else:
        lineage = f"All {_count(total['scored_races'])} strict races resolve to a registered source file."
    zero_finance = [str(row["state_name"]) for row in rows if int(row["finance_complete_races"]) == 0]
    partial_finance = [
        f"{html.escape(str(row['state_name']))} {html.escape(_share(row['finance_complete_races'], row['scored_races']))}"
        for row in rows if 0 < int(row["finance_complete_races"]) < int(row["scored_races"])
    ]
    finance = (
        f"{_count(total['finance_complete_races'])} of {_count(total['scored_races'])} strict races "
        f"({html.escape(_share(total['finance_complete_races'], total['scored_races']))}) display a complete two-candidate fundraising overlay. "
        + (f"No finance-complete races: {html.escape(', '.join(zero_finance))}. " if zero_finance else "")
        + (f"Partial coverage: {', '.join(partial_finance)}. " if partial_finance else "")
        + "Missing finance is unavailable, not zero, and finance never enters WAR."
    )
    return (
        '<section id="state-limitations"><h2>7. State coverage and release limitations</h2>'
        "<p>One row per scheduled state: scheduled state/election/chamber maps, maps that contain no strict race, "
        "strict D-versus-R races that received WAR, the split between 2016 backcasts and published v3 same-cycle residuals, "
        "source-file lineage, excluded outcomes by class, finance overlay completeness, the plan-provenance label, and the exact run identifiers. "
        "The machine-readable copy is the state release coverage download linked below.</p>"
        f"{limitations_table_html(rows, run_ids)}"
        "<h3>Score labels</h3>"
        f"<p><b>Published v3 same-cycle residual.</b> {_count(total['published_post2016_races'])} races carry the exact residual from Southern WAR v3 run "
        f"<code>{html.escape(run_ids['upstreamModelRunId'])}</code>, fitted in the same cycle. "
        f"<b>2016 backcast.</b> {_count(total['backcast_2016_races'])} strict 2016 races are backward applications of the post-2016 model; "
        "the explorer labels them “post-2016-model backcast” and they are descriptive, not contemporaneous fits.</p>"
        "<h3>Excluded outcomes</h3>"
        f"<p><b>Research-only outcomes</b> ({_count(total['excluded_research_outcomes'])}; {html.escape(_states_with(rows, 'excluded_research_outcomes'))}) are outcomes the model carries only as context and never scores. "
        f"<b>Baseline not strict</b> ({_count(total['excluded_baseline_not_strict'])}; {html.escape(_states_with(rows, 'excluded_baseline_not_strict'))}): "
        "Virginia 2017 and 2021 lower-chamber outcomes whose governor baseline uses 2019-plan cross-election precinct membership. "
        "The baseline is not a same-plan observation, so those races are excluded rather than scored, which is why those two scheduled maps contain no strict race. "
        f"<b>Incumbency experimental</b> ({_count(total['excluded_incumbency_experimental'])}; {html.escape(_states_with(rows, 'excluded_incumbency_experimental'))}): "
        "prior-winner continuity rows without roster evidence. Incumbency is a model input, so a race whose incumbency rests on an unverified continuity inference is excluded. "
        "Exclusion is not a claim that a district was uncontested.</p>"
        "<h3>Source lineage</h3>"
        f"<p>{lineage}</p>"
        "<h3>Plan provenance</h3>"
        f"<p>Plan-provenance labels by state: {provenance_text}. “Provider-reported district” means the district number is the election provider’s; "
        "“plan vintage unverified” means the warehouse did not confirm which redistricting plan the provider applied; and the election-year Census "
        "boundary drawn in the explorer is display geometry that does not certify the provider’s allocation of votes to districts.</p>"
        "<h3>Finance overlay coverage</h3>"
        f"<p>{finance}</p>"
        "<h3>Scheduled maps</h3>"
        f"<p>{_count(total['scheduled_slices'])} scheduled maps; {_count(total['empty_scheduled_slices'])} contain no strict race "
        f"({html.escape(_states_with(rows, 'empty_scheduled_slices'))}). Empty maps still show every district outline and explain the missing score.</p>"
        "</section>"
    )


def build_payload() -> dict[str, object]:
    # A prior generated map must not turn a pending analytical run into a
    # release.  Check the exact upstream decision before reading model rows.
    v3_manifest, _decision = require_approved_release(V3_MANIFEST, V3_RELEASE_DECISION)
    races = read_csv(MODEL / "race_war.csv")
    candidates = read_csv(MODEL / "candidate_cycle_war.csv")
    coverage = read_csv(MODEL / "coverage.csv")
    geometry_manifest = read_csv(GEOGRAPHY)
    model_manifest = json.loads((MODEL / "manifest.json").read_text(encoding="utf-8"))
    if model_manifest["status"] != "validated_descriptive_historical_release":
        raise ValueError("Historical WAR model release is not validated")
    for output in model_manifest["outputs"]:
        if hashlib.sha256((ROOT / output["path"]).read_bytes()).hexdigest() != output["sha256"]:
            raise ValueError(f"Historical WAR output hash mismatch: {output['path']}")
    if not STATE_COVERAGE.is_file():
        raise ValueError(f"State release coverage output is missing: {STATE_COVERAGE.relative_to(ROOT).as_posix()}")
    if STATE_COVERAGE.relative_to(ROOT).as_posix() not in {output["path"] for output in model_manifest["outputs"]}:
        raise ValueError("State release coverage is not a hashed output of the historical WAR manifest")
    limitations = state_limitations(read_csv(STATE_COVERAGE))
    run_ids = release_run_ids(limitations)
    expected_run_ids = {
        "historicalRunId": model_manifest["historical_war_run_id"],
        "upstreamModelRunId": v3_manifest["model_run_id"],
        "warehouseBuildRunId": model_manifest["warehouse_build_run_id"],
    }
    if run_ids != expected_run_ids:
        raise ValueError(f"State release coverage run IDs disagree with the manifests: {run_ids} != {expected_run_ids}")
    schedule = scheduled_keys_2016_2024()
    geometry_keys = [(r["state_code"], int(r["cycle"]), r["chamber"]) for r in geometry_manifest]
    if len(geometry_keys) != len(set(geometry_keys)) or set(geometry_keys) != schedule:
        raise ValueError("Geometry must match all 116 scheduled slices exactly")
    candidate_index = {
        (row["state_code"], int(row["cycle"]), row["chamber"], normalized_district(row["district"]), row["canonical_party"]): row
        for row in candidates
    }
    if len(candidate_index) != len(candidates):
        raise ValueError("Candidate-cycle payload key is not unique")
    race_index = {
        (row["state_code"], int(row["cycle"]), row["chamber"], normalized_district(row["district"])): row
        for row in races
    }
    if len(race_index) != len(races):
        raise ValueError("Race payload key is not unique")
    coverage_index = {
        (row["state_code"], int(row["cycle"]), row["chamber"]): row for row in coverage
    }
    if len(coverage_index) != len(coverage) or set(coverage_index) != schedule:
        raise ValueError("Coverage must match all 116 scheduled slices exactly")
    slices = {}
    join_audit = []
    total_features = 0
    for source in geometry_manifest:
        state, cycle, chamber = source["state_code"], int(source["cycle"]), source["chamber"]
        layer = "SLDLST" if chamber == "lower" else "SLDUST"
        path = ROOT / source["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Immutable geometry hash changed: {path}")
        frame = gpd.read_file(f"zip://{path.resolve()}")
        if layer not in frame.columns:
            raise ValueError(f"Missing {layer} in {path}")
        frame["district"] = frame[layer].map(normalized_district)
        frame = frame[frame.district.str.fullmatch(r"\d+")].copy()
        if frame.empty or frame.district.duplicated().any():
            raise ValueError(f"Census geometry district grain failed for {state}/{cycle}/{chamber}")
        if frame.crs is None or frame.geometry.isna().any() or frame.geometry.is_empty.any() or not frame.geometry.is_valid.all():
            raise ValueError(f"Invalid source geometry for {state}/{cycle}/{chamber}")
        frame, retained = display_geometry(frame)
        if frame.geometry.is_empty.any() or not frame.geometry.is_valid.all():
            raise ValueError(f"Invalid simplified geometry for {state}/{cycle}/{chamber}")
        bounds = frame.total_bounds
        scored = {
            district: row for (s, c, h, district), row in race_index.items()
            if (s, c, h) == (state, cycle, chamber)
        }
        missing_geometry = sorted(set(scored) - set(frame.district), key=lambda x: int(x))
        if missing_geometry:
            raise ValueError(f"Scored races lack exact Census geometry for {state}/{cycle}/{chamber}: {missing_geometry}")
        public_races = {}
        for district, row in scored.items():
            dem = candidate_index[(state, cycle, chamber, district, "D")]
            rep = candidate_index[(state, cycle, chamber, district, "R")]
            finance_complete = integer(row["finance_complete"]) == 1
            dem_votes, rep_votes = number(row["dem_votes"]), number(row["rep_votes"])
            if any(v is None or v <= 0 or not v.is_integer() for v in (dem_votes, rep_votes)):
                raise ValueError("Observed positive integer D/R votes required")
            if dem_votes + rep_votes != number(row["two_party_votes"]):
                raise ValueError("Two-party vote total does not reconcile")
            if abs(100 * (dem_votes - rep_votes) / (dem_votes + rep_votes) - number(row["legislative_dem_margin"])) > 1e-8:
                raise ValueError("Observed legislative margin does not reconcile")
            if number(dem["votes"]) != dem_votes or number(rep["votes"]) != rep_votes:
                raise ValueError("Candidate and race vote totals disagree")
            public_races[district] = {
                "district": district,
                "demCandidate": dem["candidate_name"], "repCandidate": rep["candidate_name"],
                "demVotes": integer(row["dem_votes"]), "repVotes": integer(row["rep_votes"]),
                "thirdPartyVotes": number(row["third_party_votes"]),
                "electionDate": row["election_date"], "electionStage": row["election_stage"],
                "sourceProvider": row["source_provider"], "sourceFamily": row["source_family"],
                "sourceFileId": row["source_file_id"] or None,
                "sourceFileStatus": "registered" if row["source_file_id"] else "legacy_lineage_unresolved",
                "demIncumbent": integer(dem["incumbent"]) == 1,
                "repIncumbent": integer(rep["incumbent"]) == 1,
                "legislativeMargin": number(row["legislative_dem_margin"]),
                "ticketMargin": number(row["baseline_dem_margin"]),
                "rawGap": number(row["raw_gap"]),
                "structuralGap": number(row["fitted_structural_expected_gap"]),
                "lagComponent": number(row["fitted_lag_component"]),
                "war": number(row["war"]), "warParty": row["war_party"],
                "scope": row["scoring_scope"], "baselineOffice": row["baseline_office"],
                "baselineSource": row["baseline_source"],
                "warehousePlan": row["district_plan_id"],
                "warehouseGeography": row["geography_vintage"],
                "financeComplete": finance_complete,
                "demFundraising": number(row["democratic_fundraising"]) if finance_complete else None,
                "repFundraising": number(row["republican_fundraising"]) if finance_complete else None,
                "financeStatus": row["race_finance_status"],
                "lagContextAvailable": str(row["lag_context_available"]).lower() in {"true", "1"},
            }
        features = [
            {"district": row.district, "path": path_for_geometry(row.geometry, bounds)}
            for row in frame.sort_values("district", key=lambda values: values.astype(int)).itertuples()
        ]
        total_features += len(features)
        cov = coverage_index[(state, cycle, chamber)]
        if integer(cov["scored_races"]) != len(public_races):
            raise ValueError("Scored-race coverage disagrees with map payload")
        audit = {
            "historical_war_run_id": model_manifest["historical_war_run_id"],
            "state_code": state, "cycle": cycle, "chamber": chamber,
            "geometry_source_id": source["source_file_id"], "geometry_sha256": source["sha256"],
            "geometry_features": len(features), "matched_races": len(public_races),
            "unmatched_races": len(missing_geometry), "unscored_features": len(features) - len(public_races),
            "duplicate_keys": 0, "invalid_geometries": 0,
            "unsimplified_features": retained,
        }
        for party in ("dem", "rep"):
            before = sum(integer(row[f"{party}_votes"]) for row in scored.values())
            after = sum(row[f"{party}Votes"] for row in public_races.values())
            if before != after:
                raise ValueError("Geometry join changed vote totals")
            audit.update({f"{party}_votes_before": before, f"{party}_votes_after": after})
        join_audit.append(audit)
        key = f"{state}-{cycle}-{chamber}"
        slices[key] = {
            "state": state, "stateName": STATE_NAMES[state], "cycle": cycle, "chamber": chamber,
            "censusVintage": source["geography_vintage"], "sourceUrl": source["source_url"],
            "geometrySourceId": source["source_file_id"], "districts": len(features),
            "features": features, "races": public_races,
            "coverage": {
                "scored": integer(cov["scored_races"]),
                "financeComplete": integer(cov["finance_complete_races"]),
                "lagContext": integer(cov["lag_context_races"]),
            },
        }
    if len(slices) != len(schedule):
        raise ValueError("Public Southern WAR payload must contain all 116 scheduled slices")
    if sum(len(value["races"]) for value in slices.values()) != len(races):
        raise ValueError("Public race payload lost a scored race")
    for state, observed in observed_state_counts(slices).items():
        declared = {column: limitations[state][column] for column in STATE_COVERAGE_RECONCILED}
        if declared != observed:
            raise ValueError(f"State release coverage disagrees with the map payload for {state}: {declared} != {observed}")
        if model_manifest["finance_coverage_by_state"][state]["complete_races"] != observed["finance_complete_races"]:
            raise ValueError(f"Finance coverage disagrees between the manifest and the map payload for {state}")
    return {
        "runId": model_manifest["historical_war_run_id"],
        "generatedAt": model_manifest["generated_at_utc"],
        "publicationProvenance": {
            "builderSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "modelManifestSha256": hashlib.sha256((MODEL / "manifest.json").read_bytes()).hexdigest(),
            "geometryManifestSha256": hashlib.sha256(GEOGRAPHY.read_bytes()).hexdigest(),
            "templateSha256": hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
            "explorerStyleSha256": hashlib.sha256(EXPLORER_STYLE.read_bytes()).hexdigest(),
            "themeSha256": hashlib.sha256((ROOT / "dashboard/blue_oxblood_theme.css").read_bytes()).hexdigest(),
            "sourceCommit": model_manifest["source_commit"],
            "configuration": "election-year Census geometry simplified at 1,800 meters in EPSG:5070; retain source outline if simplification is invalid; 640x700 viewport; +/-30-point scale",
        },
        "states": STATE_NAMES, "slices": slices,
        "diagnostics": {
            "scheduledSlices": len(slices), "geometryFeatures": total_features,
            "scoredRaces": len(races), "candidateRows": len(candidates),
            "financeCompleteRaces": model_manifest["diagnostics"]["finance_complete_races"],
        },
        "financeCoverageByState": model_manifest["finance_coverage_by_state"],
        "stateLimitations": limitations,
        "runIds": run_ids,
        "joinAudit": join_audit,
    }


def page_html() -> str:
    return TEMPLATE.read_text(encoding="utf-8").replace(
        "__EXPLORER_CSS__", EXPLORER_STYLE.read_text(encoding="utf-8")
    )


def methodology_html(
    run_id: str,
    limitations: dict[str, dict[str, object]],
    run_ids: dict[str, str],
) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Southern WAR methodology</title><style>body{{margin:0;background:#f4f8fa;color:#222;font:16px/1.65 Arial,sans-serif}}header nav,main{{width:min(900px,calc(100% - 36px));margin:auto}}header{{background:#fff;border-bottom:1px solid #aab9c2}}header nav{{display:flex;gap:18px;padding:17px 0}}a{{color:#743b42;font-weight:700}}h1{{font-size:52px;line-height:1;margin:58px 0 18px}}section{{padding:8px 0 24px;border-bottom:1px solid #aab9c2}}.formula,.warning{{padding:15px 18px;border-left:4px solid #743b42;background:#e7eff3}}.warning{{border-color:#a87928;background:#fff4d8}}table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #aab9c2;padding:9px;text-align:left}}.table-scroll{{max-width:100%;overflow-x:auto;margin:14px 0}}.table-scroll:focus-visible{{outline:3px solid #3d77a8;outline-offset:2px}}table.limitations{{width:max-content;min-width:100%;font-size:14px}}table.limitations caption{{text-align:left;padding:0 0 8px;font-size:14px;color:#586772}}table.limitations th,table.limitations td{{white-space:nowrap;vertical-align:top}}table.limitations .num{{text-align:right;font-variant-numeric:tabular-nums}}table.limitations th:first-child{{position:sticky;left:0;z-index:1;background:#743b42;color:#fff;box-shadow:1px 0 0 #aab9c2}}table.limitations tfoot td,table.limitations tfoot th{{font-weight:700;border-top:2px solid #743b42}}code{{overflow-wrap:anywhere}}.run-ids{{display:grid;grid-template-columns:max-content 1fr;gap:6px 18px;margin:18px 0}}.run-ids dt{{font-weight:700}}.run-ids dd{{margin:0}}@media(max-width:600px){{.run-ids{{grid-template-columns:1fr}}}}</style></head><body><header><nav><a href="index.html">Forecast</a><a href="cmo.html">Alabama WAR</a><a href="southern-war.html" aria-current="page">Southern WAR</a><a href="methods.html">Methods</a></nav></header><main><h1>Southern WAR methodology</h1><p>Construction, coverage, geography, finance, and interpretation for the 2016–2024 Southern state-legislative WAR map.</p><section><h2>1. Estimand</h2><div class="formula">Raw gap = Democratic legislative margin − Democratic ticket margin<br>Race WAR = raw gap − fitted structural expected gap<br>Democratic WAR = race WAR; Republican WAR = −race WAR</div><p>The score is a race differential, not a pooled candidate-career effect. A residual cannot uniquely divide credit between candidate strength, opponent weakness, and omitted local conditions.</p></section><section><h2>2. Structural model</h2><p>The selected <code>decaying_lag</code> ridge specification (alpha 100) models the ordinary legislative-ticket gap using ticket margin and its square, state, chamber, baseline office family, election timing, symmetric incumbency, prior presidential margin, ticket change, and a ticket-change-by-years interaction. Specification selection used earlier-cycle forward validation.</p></section><section><h2>3. Historical scoring</h2><p>Races after 2016 preserve the published Southern WAR v3 same-cycle fitted residual. The strict 2016 races are a backward application of the selected model fitted only on strict races after 2016.</p><div class="warning"><b>2016 extrapolation.</b> Those scores compare 2016 results with a modern post-2016 structural relationship. No 2016 outcome enters model fitting, but the result is descriptive rather than a contemporaneous fit.</div></section><section><h2>4. Coverage and missing races</h2><p>The explorer contains all 116 scheduled state/cycle/chamber map slices and every district outline in the exact election-year Census cartographic-boundary file. Only strict observed D–R regular contests receive WAR. Uncontested races, non-D/R races, research-only context, and missing outcomes remain unscored; gray never means WAR zero.</p><p>Louisiana, Mississippi, and Virginia retain their actual odd-year election schedules. South Carolina’s staggered Senate schedule is also retained.</p></section><section><h2>5. Fundraising</h2><p>Fundraising is displayed only when both major-party observations and both candidate identities are complete. The model tested viability gates at every $10,000 from $10,000 through $100,000, plus $250,000. Finance failed the prespecified nested time-forward promotion gate, so it does not enter headline WAR.</p><p>Missouri has no usable finance in the warehouse run underlying this map, and Mississippi has very limited electronic coverage. Other states have residual race-level gaps. Missing finance is unavailable, not zero.</p></section><section><h2>6. Geography</h2><p>Each slice uses the U.S. Census Bureau’s cartographic boundary released for that election year and chamber. A scored race must match one unique district feature in the exact state/year/chamber file. Census geometry is display evidence; it does not overwrite the warehouse’s provider-reported plan-vintage label.</p></section>{limitations_section_html(limitations, run_ids)}<section><h2>8. Downloads</h2><p><a href="data/southern_historical_war_v1_race_war.csv">Race WAR</a> · <a href="data/southern_historical_war_v1_candidate_cycle_war.csv">Candidate orientations</a> · <a href="data/southern_historical_war_v1_coverage.csv">Coverage</a> · <a href="data/southern_historical_war_v1_state_release_coverage.csv">State release coverage</a> · <a href="data/southern_war_map_join_audit.csv">Map join audit</a> · <a href="data/southern_historical_war_v1_manifest.json">Run manifest</a> · <a href="data/southern_legislative_geography_manifest.csv">Geometry sources</a></p><p><small>Run {html.escape(run_id)}</small></p></section></main></body></html>'''


def main() -> None:
    payload = build_payload()
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    PAYLOAD.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    with JOIN_AUDIT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(payload["joinAudit"][0]))
        writer.writeheader()
        writer.writerows(payload["joinAudit"])
    copies = {
        MODEL / "race_war.csv": DOCS_DATA / "southern_historical_war_v1_race_war.csv",
        MODEL / "candidate_cycle_war.csv": DOCS_DATA / "southern_historical_war_v1_candidate_cycle_war.csv",
        MODEL / "coverage.csv": DOCS_DATA / "southern_historical_war_v1_coverage.csv",
        MODEL / "manifest.json": DOCS_DATA / "southern_historical_war_v1_manifest.json",
        STATE_COVERAGE: STATE_COVERAGE_PUBLIC,
        GEOGRAPHY: DOCS_DATA / "southern_legislative_geography_manifest.csv",
    }
    for source, target in copies.items():
        shutil.copy2(source, target)
    page = apply_theme(page_html())
    method = apply_theme(methodology_html(str(payload["runId"]), payload["stateLimitations"], payload["runIds"]))
    SITE.write_text(page, encoding="utf-8")
    METHOD.write_text(method, encoding="utf-8")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(page, encoding="utf-8")
    digest = hashlib.sha256(PAYLOAD.read_bytes()).hexdigest()
    print(f"Southern WAR map: slices={len(payload['slices'])} races={payload['diagnostics']['scoredRaces']:,} payload_sha256={digest}")


if __name__ == "__main__":
    main()
