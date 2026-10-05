"""Build the self-contained historical Alabama WAR explorer and its methodology page."""

from __future__ import annotations

import csv
import html
import json
import re
import shutil
import sqlite3
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

import site_geography
from site_brand import display_name, war_identity_figure
from southern_war_release_gate import require_alabama_historical_release


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
CAREER = WAR / "alabama_career_war_v1"
MAPS = ROOT / "data" / "raw" / "alabama_elections_and_geography"
OUTPUT = ROOT / "artifacts" / "site" / "alabama-legislative-cmo.html"
LEGACY_OUTPUT = ROOT / "artifacts" / "site" / "alabama-legislative-war-legacy.html"
SITE_OUTPUT = ROOT / "docs" / "cmo.html"
SITE_METHODOLOGY_OUTPUT = ROOT / "docs" / "cmo-methodology.html"
HISTORICAL_MANIFEST = WAR / "alabama_historical_war_v1" / "manifest.json"
MAP_SIMPLIFY_METERS = 250
PUBLISHED_ALABAMA = WAR / "alabama_war_v1"
DECISION = ROOT / "project_docs" / "audits" / "SOUTHERN_V3_RELEASE_DECISION.json"

MAP_FILES = {
    (1994, "house"): "al_lower_1992_2000.zip",
    (1994, "senate"): "al_upper_1992_2000.zip",
    (1998, "house"): "al_lower_1992_2000.zip",
    (1998, "senate"): "al_upper_1992_2000.zip",
    (2002, "house"): "al_lower_2002_2010.zip",
    (2002, "senate"): "al_upper_2002_2010.zip",
    (2006, "house"): "al_lower_2002_2010.zip",
    (2006, "senate"): "al_upper_2002_2010.zip",
    (2010, "house"): "tl_2010_01_sldl00.zip",
    (2010, "senate"): "tl_2010_01_sldu00.zip",
    (2014, "house"): "al_sldl_2012_to_2017.zip",
    (2014, "senate"): "al_sldu_2012_to_2017.zip",
    (2018, "house"): "al_sldl_2017_to_2021.zip",
    (2018, "senate"): "al_sldu_2017_to_2021.zip",
    (2022, "house"): "al_sldl_2021_to_2023.zip",
    (2022, "senate"): "al_sldu_2021_to_2023.zip",
}

PRIOR_PRESIDENTIAL_NOMINEES = {
    1994: (1992, "Bill Clinton", "George H. W. Bush"),
    1998: (1996, "Bill Clinton", "Bob Dole"),
    2002: (2000, "Al Gore", "George W. Bush"),
    2006: (2004, "John Kerry", "George W. Bush"),
    2010: (2008, "Barack Obama", "John McCain"),
    2014: (2012, "Barack Obama", "Mitt Romney"),
    2018: (2016, "Hillary Clinton", "Donald Trump"),
    2022: (2020, "Joe Biden", "Donald Trump"),
}


def number(value, default=None):
    try:
        parsed = float(value)
        return parsed if np.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def district_id(row, cycle, chamber):
    if cycle <= 2006:
        value = row.get("DISTRICT")
        if value is None or str(value) == "nan":
            value = row["SLDUST00"] if chamber == "senate" else row["SLDLST00"]
        return int(value)
    if cycle == 2010:
        return int(row["SLDLST00"] if chamber == "house" else row["SLDUST00"])
    if cycle == 2022:
        return int(row["DISTRICT"])
    if chamber == "house":
        return int(row["SLDLST"])
    if cycle == 2018:
        return int(row["SLDUST"])
    return int(str(row["LONGNAME"]).split()[-1])


def require_fresh_inputs() -> dict:
    """Refuse to render historical exports that are not bound to approved runs."""
    return require_alabama_historical_release(
        HISTORICAL_MANIFEST, PUBLISHED_ALABAMA / "manifest.json", DECISION
    )


def load_data():
    """Build the public payload from corrected historical residual WAR."""
    historical_war = WAR / "alabama_historical_war_v1"
    with (historical_war / "candidate_cycle_war.csv").open(encoding="utf-8-sig", newline="") as f:
        candidates = list(csv.DictReader(f))
    with (historical_war / "race_war.csv").open(encoding="utf-8-sig", newline="") as f:
        races = list(csv.DictReader(f))
    with (ROOT / "data" / "processed" / "elections" / "canonical_cmo_features.csv").open(encoding="utf-8-sig", newline="") as f:
        race_metadata = list(csv.DictReader(f))
    with (WAR / "wikipedia_legislative_candidates.csv").open(encoding="utf-8-sig", newline="") as f:
        public_candidates = list(csv.DictReader(f))
    with (WAR / "2022_wikipedia_vote_validation.csv").open(encoding="utf-8-sig", newline="") as f:
        validated_2022_names = list(csv.DictReader(f))
    with (ROOT / "data" / "processed" / "elections" / "canonical_cmo_district_office_baselines.csv").open(encoding="utf-8-sig", newline="") as f:
        office_baselines = list(csv.DictReader(f))

    race_index = {(int(r["cycle"]), r["chamber"], int(float(r["district"]))): r for r in races}
    metadata_index = {(int(r["cycle"]), r["chamber"], int(float(r["district"]))): r for r in race_metadata}
    public_name_index = {
        (int(r["cycle"]), r["chamber"], int(r["district"]), r["party"], int(number(r["votes_wikipedia"], 0))): r["candidate"]
        for r in public_candidates
    }
    name_db = sqlite3.connect(ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite")
    observed_names = name_db.execute("""
        SELECT year, office, party_norm, TRIM(candidate), COUNT(*) AS records, SUM(votes) AS votes
        FROM vote_observations WHERE authority_rank = 1 AND party_norm IN ('D','R')
        GROUP BY year, office, party_norm, TRIM(candidate)
        ORDER BY year, office, party_norm, records DESC, votes DESC
    """).fetchall()
    name_db.close()
    office_names = {}
    for year, office, party_code, candidate_name, _, _ in observed_names:
        office_names.setdefault((int(year), office, party_code), candidate_name)
    office_names.update({
        (2010, "Governor", "D"): "Ron Sparks", (2010, "Governor", "R"): "Robert Bentley",
        (2010, "Attorney General", "D"): "James H. Anderson", (2010, "Attorney General", "R"): "Luther Strange",
    })
    public_name_index.update({
        (int(r["cycle"]), r["chamber"], int(r["district"]), r["party"], int(number(r["votes_modeled"], 0))): r["candidate_modeled"]
        for r in validated_2022_names
    })
    office_index = {}
    for row in office_baselines:
        margin = number(row.get("office_margin"))
        if margin is not None:
            office_index.setdefault((int(row["cycle"]), row["chamber"], int(float(row["district"]))), []).append({
                "label": row["office"], "demMargin": round(margin, 2),
                "demVotes": round(number(row.get("D", row.get("dem_votes")), 0)),
                "repVotes": round(number(row.get("R", row.get("rep_votes")), 0)), "kind": "office",
                "demName": office_names.get((int(row["cycle"]), row["office"], "D"), "Democratic nominee"),
                "repName": office_names.get((int(row["cycle"]), row["office"], "R"), "Republican nominee"),
            })

    groups, excluded = {}, {}
    for row in candidates:
        cycle, chamber, district = int(row["cycle"]), row["chamber"], int(float(row["district"]))
        race = race_index[(cycle, chamber, district)]
        if row.get("scoring_scope") == "excluded_by_adjudication":
            # Observed but unscored: shown through the no-score panel, never as a zero.
            excluded.setdefault((cycle, chamber), {})[district] = race
            continue
        meta = metadata_index[(cycle, chamber, district)]
        party = row["canonical_party"]
        orient = 1 if party == "D" else -1
        item = {
            "district": district,
            "candidate": public_name_index.get((cycle, chamber, district, party, int(number(row["canonical_votes"], 0))), row["candidate_name"]),
            "personId": row.get("person_id") or row["candidate_effect_id"],
            "party": party, "votes": int(number(row["canonical_votes"], 0)),
            "war": number(row["candidate_cycle_war"], 0),
            "within": round(number(row.get("candidate_state_ticket_cmo")), 2) if number(row.get("candidate_state_ticket_cmo")) is not None else None,
            "raw": round(number(row.get("candidate_federal_ticket_cmo")), 2) if number(row.get("candidate_federal_ticket_cmo")) is not None else None,
            "predictiveResidual": round(number(row.get("candidate_presidential_ticket_cmo")), 2) if number(row.get("candidate_presidential_ticket_cmo")) is not None else None,
            "rawGap": round(number(row.get("candidate_raw_gap"), 0), 2),
            "predictedStructuralGap": round(number(row.get("candidate_structural_expected_gap"), 0), 2),
            "lagComponent": round(number(row.get("candidate_lag_component"), 0), 2),
            "partialPooled": number(row.get("candidate_cycle_war"), 0),
            "qualityLow": number(row.get("candidate_cycle_war"), 0),
            "qualityHigh": number(row.get("candidate_cycle_war"), 0),
            "qualityStatus": row.get("scoring_scope", ""),
            "qualityResidual": number(row.get("candidate_cycle_war"), 0),
            "southernExpectedGap": round(number(row.get("candidate_structural_expected_gap"), 0), 2),
            "genericIncumbency": 0.0,
            "totalElectoralValue": number(row.get("candidate_cycle_war"), 0),
            "replacementLevel": 0.0,
            "structuralAdjustment": round(number(row.get("candidate_structural_expected_gap"), 0), 2),
            "appearances": 1,
            "scoringScope": row.get("scoring_scope", ""),
            "lagContextAvailable": str(row.get("lag_context_available", "")).lower() in {"true", "1"},
            "backcastExtrapolationYears": int(number(row.get("backcast_extrapolation_years"), 0)),
            "identityStatus": row.get("identity_status", ""), "contestTier": row.get("contest_tier", ""),
            "low": number(row.get("candidate_cycle_war"), 0),
            "high": number(row.get("candidate_cycle_war"), 0),
            "specificationRange": 0.0,
            "signConsistent": True,
            "expectedMargin": round(orient * number(race["selected_ticket_margin"], 0), 2),
            "margin": round(orient * number(race["legislative_dem_margin"], 0), 2),
            "cycleTopTicket": round(orient * number(race["selected_ticket_margin"], 0), 2),
            "priorPres": (round(orient * number(race.get("prior_presidential_margin")), 2)
                          if number(race.get("prior_presidential_margin")) is not None else None),
            "priorPresYear": number(meta.get("prior_presidential_year")),
            "winner": str(row.get("winner", "")).lower() in {"true", "1"},
            "incumbent": str(row.get("incumbent", "")).lower() in {"true", "1"},
            "quality": "; ".join(filter(None, [
                "scored against the fixed 2018-24 reference" if row.get("scoring_scope") == "post2016_southern_model_backcast" else "published same-cycle residual",
                "prior-presidential lag context unavailable" if str(row.get("lag_context_available", "")).lower() not in {"true", "1"} else "",
                "nominal contest; excluded from fitting" if row.get("contest_tier") == "nominal" else "",
                "1994 sensitivity tier" if cycle == 1994 else "",
                "race-specific unresolved identity" if row.get("identity_status") == "surname_only_unresolved_race_specific" else "",
                "state-ticket fallback" if str(row.get("federal_primary", "")).lower() not in {"true", "1"} else "",
            ])) or "standard source checks passed",
            "modelTier": meta.get("model_tier", ""), "baselineMethod": race.get("selected_ticket_source", ""),
            "baselineFallbackShare": number(meta.get("baseline_fallback_share")),
            "priorPresFallbackShare": number(meta.get("prior_pres_fallback_share")),
            "priorPresComplete": str(meta.get("prior_pres_source_complete", "")).lower() in {"true", "1"},
            "demographicsMethod": meta.get("demographics_method", "") or meta.get("demographics_method_historical", ""),
            "demographicReferenceYear": number(meta.get("demographic_reference_year")),
            "nonwhiteShare": number(meta.get("nonwhite_share")), "whiteCollegeShare": number(meta.get("white_college_share")),
            "readinessStatus": meta.get("readiness_status", ""),
        }
        groups.setdefault((cycle, chamber), []).append(item)

    payload = {}
    for (cycle, chamber), items in groups.items():
        ordered = sorted(x["war"] for x in items)
        for item in items:
            item["percentile"] = round(100 * (sum(v < item["war"] for v in ordered) + .5 * sum(v == item["war"] for v in ordered)) / len(ordered), 1)
        winners = {x["district"]: x for x in items if x["winner"]}
        districts = sorted({x["district"] for x in items})
        dem_context = {d: number(race_index[(cycle, chamber, d)]["war"], 0) for d in districts}
        dem_within = {d: round(number(race_index[(cycle, chamber, d)].get("state_ticket_cmo")), 2) if number(race_index[(cycle, chamber, d)].get("state_ticket_cmo")) is not None else None for d in districts}
        dem_raw = {d: round(number(race_index[(cycle, chamber, d)].get("federal_ticket_cmo")), 2) if number(race_index[(cycle, chamber, d)].get("federal_ticket_cmo")) is not None else None for d in districts}
        dem_pair = dict(dem_context)
        ordered_dem = sorted(dem_context.values())
        percentiles = {d: round(2 * ((sum(v < s for v in ordered_dem) + .5 * sum(v == s for v in ordered_dem)) / len(ordered_dem)) - 1, 4) for d, s in dem_context.items()}
        gov = {d: next((o["demMargin"] for o in office_index.get((cycle, chamber, d), []) if o["label"] == "Governor"), None) for d in districts}
        raw_gov = {d: round(number(race_index[(cycle, chamber, d)]["legislative_dem_margin"], 0) - gov[d], 2) if gov[d] is not None else None for d in districts}
        raw_pres = {d: round(number(race_index[(cycle, chamber, d)]["legislative_dem_margin"], 0) - number(race_index[(cycle, chamber, d)]["prior_presidential_margin"]), 2) if number(race_index[(cycle, chamber, d)].get("prior_presidential_margin")) is not None else None for d in districts}
        payload[f"{cycle}-{chamber}"] = {
            "cycle": cycle, "chamber": chamber,
            "mapVintage": "1992 enacted plan" if cycle <= 1998 else "2001 enacted plan" if cycle <= 2010 else "2012 enacted plan" if cycle == 2014 else "2017 enacted plan" if cycle == 2018 else "2021 enacted plan",
            "plan": MAP_FILES[(cycle, chamber)].removesuffix(".zip"),
            "candidates": sorted(items, key=lambda x: x["war"], reverse=True), "winners": winners,
            "demWar": dem_context, "demWithin": dem_within, "demRawTicket": dem_raw, "demPair": dem_pair,
            "demPercentile": percentiles, "rawVsGovernor": raw_gov, "rawVsPresidential": raw_pres,
            "districtStatus": {**{str(d): f"{race_index[(cycle, chamber, d)]['contest_tier'].title()} contested D–R race" for d in districts},
                               **{str(d): (f"Contested D–R race; WAR withheld by adjudication {r['exclusion_id']} "
                                           f"({r['exclusion_reason_code'].replace('_', ' ')}).")
                                  for d, r in excluded.get((cycle, chamber), {}).items()}},
            "baselines": {str(d): ([{"label": "Selected ticket baseline", "demMargin": round(number(race_index[(cycle, chamber, d)]["selected_ticket_margin"], 0), 2), "kind": "composite", "demName": "Democratic baseline", "repName": "Republican baseline"}, {"label": f"{PRIOR_PRESIDENTIAL_NOMINEES[cycle][0]} President", "demMargin": round(number(race_index[(cycle, chamber, d)].get("prior_presidential_margin"), 0), 2), "kind": "presidential", "available": number(race_index[(cycle, chamber, d)].get("prior_presidential_margin")) is not None, "demName": PRIOR_PRESIDENTIAL_NOMINEES[cycle][1], "repName": PRIOR_PRESIDENTIAL_NOMINEES[cycle][2]}] + office_index.get((cycle, chamber, d), [])) for d in districts},
            "summary": {"races": len(winners), "candidates": len(items), "median": round(float(np.median([x["war"] for x in winners.values()])), 1), "top": max(winners.values(), key=lambda x: x["war"])["candidate"], "warMedian": round(float(np.median([x["partialPooled"] for x in winners.values()])), 1), "warTop": max(winners.values(), key=lambda x: x["partialPooled"])["candidate"]},
        }
    return payload


def plan_geometry() -> dict:
    """Draw each enacted plan once in the shared Alabama frame; cycles on one plan share it."""
    frame = site_geography.alabama_frame()
    drawn = {}
    for (cycle, chamber), name in MAP_FILES.items():
        key = name.removesuffix(".zip")
        if key in drawn:
            continue
        gdf = gpd.read_file(f"zip://{(MAPS / name).resolve()}")
        gdf["district"] = gdf.apply(lambda r: district_id(r, cycle, chamber), axis=1)
        drawn[key] = site_geography.district_geometry(
            gdf, "district", simplify=MAP_SIMPLIFY_METERS, frame=frame, metros=True)
    return drawn


PAGE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Race-residual WAR for every modeled Alabama legislative election, 1994 to 2022">
<title>Alabama historical WAR · Jackson Hannan</title>
<style>__CSS__</style></head><body>
<header><nav class="nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html" aria-current="page">Alabama WAR</a><a href="southern-war.html">Southern WAR</a><a href="ideology-performance.html">Ideology &amp; caucuses</a><a href="methods.html">Methods</a></nav></header>
<main><section class="story-head"><div class="kicker">Historical Alabama WAR</div><h1>Alabama historical WAR</h1><div class="dek">Race-residual performance for every modeled Alabama legislative election from 1994 through 2022, with the modern post-2016 structural relationship applied backward to earlier elections.</div><div class="byline">Model and analysis by <b>Jackson Hannan</b> · September 2026</div>
<p class="lede"><strong>WAR is the race residual:</strong> the actual legislative-minus-ticket gap minus the fitted structural expected gap, in two-party margin points. The Democratic candidate receives the residual and the Republican its exact negative. <strong>One fixed reference model</strong> scores every cycle, so early-era Democrats show large positive WAR by construction.</p>
<details class="how-to-read"><summary>How to read these scores</summary><div><p>Every cycle is scored against the fixed 2018–24 reference model: the post-2016 Southern <code>decaying_lag</code> ridge fit, applied unchanged to 1994–2014 and identical to the published same-cycle residual for 2018 and 2022. Pre-2016 expectations are modern partisan expectations, so read early levels as distance from modern partisan gravity, not as a contemporaneous fit.</p><p>No pooled candidate effect, career average, fundraising, ideology, or committee identity enters WAR. A residual cannot uniquely divide credit between candidate strength, opponent weakness, and omitted local conditions.</p></div></details></section>
<section class="explorer" id="explorer" aria-labelledby="explorerTitle"><div class="explorer-top"><div><h2 id="explorerTitle">Explore the results</h2><p class="note">Color shows which side ran ahead of expectation. It is not the district's partisan lean. Colors are capped at ±30 points; race details show uncapped values.</p></div></div>
<div class="controls-bar"><div><span class="seg-label" id="chamberLabel">Chamber</span><div class="seg" role="group" aria-labelledby="chamberLabel"><button data-chamber="house" aria-pressed="true">House</button><button data-chamber="senate" aria-pressed="false">Senate</button></div></div>
<div class="timeline"><label class="seg-label" for="cycleRange">Election</label><div class="timeline-row"><input id="cycleRange" type="range" min="0" max="7" step="1" value="7"><button class="play" id="play" aria-pressed="false" aria-label="Play elections in order">▶</button></div><div class="timeline-ticks" id="cycleTicks" aria-hidden="true"></div><div class="drift" id="drift"></div></div>
<div><span class="seg-label" id="viewLabel">View</span><div class="seg" role="group" aria-labelledby="viewLabel"><button data-view="map" aria-pressed="true">Map</button><button data-view="tiles" aria-pressed="false">Tiles</button></div></div></div>
<div class="dashboard"><div class="map-panel"><div class="map-head"><div><h3 class="map-title" id="map-title"></h3><p class="map-sub" id="map-sub"></p><p class="vintage" id="vintage"></p></div></div>
<div class="map-tools"><div><label class="seg-label" for="highlight">Highlight</label><select id="highlight"><option value="0">All races</option><option value="10">±10 points or more</option><option value="20">±20 points or more</option></select></div><div><span class="seg-label" id="modeLabel">Measure</span><div class="seg" role="group" aria-labelledby="modeLabel"><button data-map-mode="absolute" aria-pressed="true">Alabama WAR</button><button data-map-mode="governor" aria-pressed="false">Vs. governor</button><button data-map-mode="presidential" aria-pressed="false">Vs. previous president</button></div></div></div>
<div class="presets" id="presets" role="group" aria-label="Zoom to an area"></div><div class="map-host" id="map"></div><div class="war-legend" id="legend" role="group" aria-label="Map legend"></div></div>
<aside class="detail" id="detail" aria-live="polite"></aside></div></section>
<section class="rankings" aria-labelledby="rankingsTitle"><h2 id="rankingsTitle">Candidate-cycle WAR results</h2><div class="note">Each pair of candidate rows is one opposite-signed race residual. Pre-2016 cycles scored against the fixed reference model and published modern residuals are labeled separately.</div><div class="filters"><label class="sr-only" for="candidate-search">Search candidate or district</label><input id="candidate-search" type="search" placeholder="Search candidate or district"><label class="sr-only" for="scope-filter">Rows to show</label><select id="scope-filter"><option value="active">Selected cycle and chamber</option><option value="all">All cycles and chambers</option></select><label class="sr-only" for="party-filter">Party</label><select id="party-filter"><option value="all">All parties</option><option value="D">Democratic</option><option value="R">Republican</option></select><label class="sr-only" for="outcome-filter">Candidates</label><select id="outcome-filter"><option value="all">All candidates</option><option value="winner">Winners</option><option value="incumbent">Incumbents</option></select></div><p class="table-scroll-hint">Swipe sideways for every column.</p><div class="table-wrap"><table><thead><tr><th data-sort="cycle">Cycle</th><th data-sort="district">District</th><th data-sort="candidate">Candidate</th><th data-sort="war">Alabama WAR</th><th data-sort="rawGap">Raw ticket gap</th><th data-sort="predictedStructuralGap">Structural expectation</th><th data-sort="lagComponent">Lag component</th><th data-sort="scoringScope">Scoring method</th><th data-sort="cycleTopTicket">Baseline margin</th><th data-sort="margin">Actual margin</th><th data-sort="votes">Votes</th></tr></thead><tbody id="rows"></tbody></table></div></section>
__CAREER__
<section class="section validation" id="validation"><div class="section-head"><div><h2>Historical scoring boundary</h2><p class="note">One reference model scores every cycle, and it is never trained on the elections it scores.</p></div><span class="warning-chip">Extrapolation</span></div><div class="validation-grid"><div><h3>1994–2014</h3><p>The selected post-2016 Southern structural model is fit once on 3,658 strict modern races, then applied backward to 412 Alabama races. Negative years-since-2016 values make this an extrapolation outside the training era.</p></div><div><h3>2018–2022</h3><p>The 97 modern Alabama races exactly preserve the published same-cycle residual WAR values.</p></div></div><p class="validation-note">Historical WAR is descriptive. It cannot uniquely divide a race residual between candidate strength, opponent weakness, and omitted local conditions.</p></section>
<section class="section downloads"><h2>Data and provenance</h2><p class="note">Download the complete historical race residuals, candidate orientations, coverage, coefficients, and content-addressed manifest.</p><div class="download-links"><a href="data/alabama_historical_war_v1_candidate_cycle_war.csv">Candidate-cycle WAR</a><a href="data/alabama_historical_war_v1_race_war.csv">Race WAR</a><a href="data/alabama_historical_war_v1_coverage.csv">Coverage</a><a href="data/alabama_historical_war_v1_structural_coefficients.csv">Reference-model coefficients</a><a href="data/alabama_career_war_v1_career_war.csv">Career cumulative WAR</a><a href="data/alabama_historical_war_v1_manifest.json">Manifest</a><a href="cmo-methodology.html">Methodology</a></div></section>
<section class="section method"><h2>How to read historical WAR</h2><p>Positive WAR means the candidate performed better than the fitted structural expectation; negative WAR means worse. The Democratic candidate receives the race residual and the Republican receives its exact negative.</p><p>Candidate display names come from election records, with archived election pages used only as a spelling cross-check. Names printed in capitals in the records are shown in title case. Finance provider and committee names are prohibited.</p><p><a href="cmo-methodology.html">Read the full methodology</a> or <a href="index.html">view the 2026 forecast</a>.</p></section></main>
<script>__MAPJS__</script><script>const GEOMETRY=__GEOMETRY__;const CONTEXT=__CONTEXT__;</script>
<script>const DATA=__PAYLOAD__;
__JS__</script></body></html>"""


def build_page(payload, geometry=None, context=None):
    """Render the historical explorer from the payload and the shared map geometry."""
    styles = ((ROOT / "dashboard/site_components.css").read_text(encoding="utf-8")
              + (ROOT / "dashboard/war_explorer.css").read_text(encoding="utf-8"))
    return (PAGE_TEMPLATE.replace("__CSS__", styles)
            .replace("__CAREER__", career_section())
            .replace("__MAPJS__", (ROOT / "dashboard/site_map.js").read_text(encoding="utf-8"))
            .replace("__GEOMETRY__", json.dumps(geometry or {}, separators=(",", ":")))
            .replace("__CONTEXT__", json.dumps(context or {}, separators=(",", ":")))
            .replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
            .replace("__JS__", (ROOT / "dashboard/war_explorer.js").read_text(encoding="utf-8")))


def career_chart(frame: pd.DataFrame, title: str) -> str:
    """Ranked horizontal bars of career cumulative WAR, labelled with each career's span."""
    rows = list(frame.itertuples())
    width, label, row_h = 620, 230, 30
    extent = max(10.0, float(frame.career_war.abs().max()))
    scale = (width - label - 70) / extent
    height = row_h * len(rows) + 30
    if frame.career_war.min() >= 0:
        zero = label + 4
    elif frame.career_war.max() <= 0:
        zero = width - 60
    else:
        zero = label + (width - label - 70) / 2
        scale /= 2
    bars = []
    for i, row in enumerate(rows):
        y = 18 + i * row_h
        value = float(row.career_war)
        x0, x1 = sorted((zero, zero + value * scale))
        name = html.escape(display_name(row.display_name))
        span = f"{int(row.first_cycle)}–{int(row.last_cycle)} · {int(row.cycles_scored)} cycles"
        text_x = x1 + 5 if value >= 0 else x0 - 5
        anchor = "start" if value >= 0 else "end"
        bars.append(
            f'<text x="0" y="{y + 12}" font-size="13" font-weight="700" fill="var(--ink)">{name} '
            f'<tspan font-weight="400" fill="var(--muted)">({html.escape(str(row.canonical_party))})</tspan></text>'
            f'<text x="0" y="{y + 24}" font-size="11" fill="var(--muted)">{span}</text>'
            f'<rect x="{x0:.1f}" y="{y + 3}" width="{max(1.5, x1 - x0):.1f}" height="14" fill="var(--ink-2)"/>'
            f'<text x="{text_x:.1f}" y="{y + 14}" font-size="12" text-anchor="{anchor}" fill="var(--ink)">{value:+.1f}</text>'
        )
    return (f'<figure class="career-chart"><figcaption><b>{html.escape(title)}</b></figcaption>'
            f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">'
            f'<line x1="{zero:.1f}" x2="{zero:.1f}" y1="10" y2="{height - 4}" stroke="var(--ink)"/>'
            + "".join(bars) + '</svg></figure>')


def career_section() -> str:
    """Career cumulative WAR, the Q14 durability measure: ranked charts plus the exact table."""
    career = pd.read_csv(CAREER / "career_war.csv")
    manifest = json.loads((CAREER / "manifest.json").read_text(encoding="utf-8"))
    multi = career[career.cycles_scored.gt(1)].copy()
    top = multi.sort_values("career_war", ascending=False).head(10)
    bottom = multi.sort_values("career_war").head(5)

    def rows(frame):
        return "".join(
            f'<tr><td>{html.escape(display_name(row.display_name))}</td><td>{html.escape(str(row.canonical_party))}</td>'
            f'<td>{int(row.first_cycle)}–{int(row.last_cycle)}</td><td class="num">{int(row.cycles_scored)}</td>'
            f'<td class="num">{row.career_war:+.1f}</td><td class="num">{row.mean_cycle_war:+.1f}</td></tr>'
            for row in frame.itertuples()
        )

    head = ('<thead><tr><th>Candidate</th><th>Party</th><th>Cycles</th><th class="num">Scored</th>'
            '<th class="num">Career WAR</th><th class="num">Mean cycle</th></tr></thead>')
    unresolved = manifest["diagnostics"]["identity_methods"].get("unresolved_source_stub", 0)
    return (
        '<section class="career" id="career"><div class="section-head"><div>'
        '<h2>Career cumulative WAR</h2>'
        '<p class="note">Single-cycle WAR credits the first defiant cycle in full and later ones only net of the decayed prior gap, '
        'so sustained overperformance is spread thin. Career WAR sums a person’s scored cycles and is the measure of '
        'defying partisan gravity for longer than expected.</p></div></div>'
        + career_chart(top, "Largest Democratic-oriented careers")
        + career_chart(bottom, "Largest Republican-oriented careers")
        + '<details class="how-to-read"><summary>Show these careers as a table</summary><div>'
        f'<div class="table-wrap"><table class="career-table">{head}<tbody>{rows(top)}{rows(bottom)}</tbody></table></div></div></details>'
        f'<p class="validation-note">{len(career):,} scored people, {int(career.cycles_scored.gt(1).sum())} of them across '
        f'more than one cycle. Pre-2016 cycles are scored against the fixed 2018–24 reference model, so long careers that '
        f'began in the 1990s accumulate large positive values by construction. {unresolved} 2022 candidate-cycles carry a '
        'source identifier that cannot be linked to earlier cycles and are counted as single-cycle careers.</p></section>'
    )


def build_historical_residual_war_methodology():
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Alabama historical WAR methodology</title><style>body{margin:0;font:16px/1.65 Arial,sans-serif;color:#211d1e;background:#f6f7f5}header nav,main{width:min(900px,calc(100% - 36px));margin:auto}header{background:#fff;border-bottom:1px solid #ccd4d5}header nav{display:flex;gap:20px;padding:18px 0}a{color:#743b42;font-weight:700}h1,h2{font-family:Georgia,serif}h1{font-size:52px;line-height:1;margin:60px 0 18px}section{padding:10px 0 22px;border-bottom:1px solid #ccd4d5}.formula{background:#e9eef0;border-left:4px solid #743b42;padding:18px 20px;font-family:Georgia,serif}.warning{background:#fff3d6;border-left:4px solid #ae7b26;padding:14px}.links{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:70px}</style></head><body><header><nav><a href="index.html">Forecast</a><a href="cmo.html">Alabama WAR</a><a href="methods.html">Methods</a></nav></header><main><h1>Alabama historical WAR methodology</h1><p>Race-residual WAR for Alabama legislative elections from 1994 through 2022.</p><section><h2>1. Estimand</h2><div class="formula">Raw gap = Democratic legislative margin − Democratic ticket margin<br>Race WAR = raw gap − fitted structural expected gap<br>Democratic WAR = race WAR; Republican WAR = −race WAR</div><p>Every score is a race differential in two-party margin points. No pooled candidate coefficient, career average, fundraising, or ideology adjustment enters WAR.</p></section><section><h2>2. Modern training model</h2><p>The backcast uses the selected <code>decaying_lag</code> ridge specification with alpha 100. It is trained on 3,658 strict Southern races after 2016. Predictors are incumbency balance, ticket margin and its square, time and cycle indicators, state, chamber, ticket-office family, prior presidential margin, ticket change, and the ticket-change-by-years interaction.</p></section><section><h2>3. Historical backcast</h2><p>For the __BACKCAST_RACES__ races from 1994 through 2014, the modern fitted relationship is applied backward to the historical Alabama ticket, incumbency, chamber, and prior-presidential context. The model is not refit on those historical outcomes.</p><div class="warning"><b>Extrapolation warning.</b> These scores answer how historical races compare with a modern structural relationship. They are not contemporaneous historical fits, and negative years-since-2016 values extend the model outside its training era.</div></section><section><h2>4. Published modern scores</h2><p>The 97 races in 2018 and 2022 retain the exact published Alabama WAR v1 same-cycle residuals. The pooled modern-model prediction is retained only as a diagnostic.</p></section><section><h2>5. Missingness and names</h2><p>Missing prior-presidential context remains labeled. For compatibility with the selected modern design, unavailable numeric lag inputs receive its zero-valued model encoding; that is not treated as an observed zero.</p><p>Candidate display names come from election identity records, with archived election pages used only as a spelling cross-check. Finance provider names, committee names, and committee IDs cannot supply display identity.</p></section><section><h2>6. Interpretation and limitations</h2><ul><li>WAR is retrospective, not a forecast probability.</li><li>A race residual cannot distinguish candidate strength from opponent weakness or omitted local conditions.</li><li>Historical baselines, district allocation, and map vintages carry source uncertainty. Pre-2010 precinct-to-district allocation uses provisional legislative-activity splits and county fallbacks, not certified boundaries; the drawn district outlines are display geometry.</li><li>Same-cycle ticket baselines for a few districts rest on thin or conflicting source coverage and moved materially when the warehouse identity repairs were applied on 2026-09-11: 2014 House 52 and 56 (federal contested coverage about 55% that cycle) and 2002 House 26 (conflicting precinct observation sets under review). Their residuals should be read as source-limited; see the release card in the downloads for run identifiers and the full list.</li><li>Backcast scores keep the within-cycle ranking of a same-era fit (correlation above 0.9 in every cycle) but not its level: a descriptive fit on 1994&ndash;2014 Alabama alone sits about 20 points lower on average and the incumbency effect is roughly twice the modern estimate. Compare backcast WAR within a cycle, not against 2018 and 2022 levels; see the release card in the downloads.</li><li>The 2018 and 2022 scores are the exact Alabama rows of the independently reviewed Southern WAR run recorded in the published manifest; the 1994&ndash;2014 rows are backcasts of that run and are flagged as such in every download.</li><li>The public forecast evaluates generic candidates at zero expected WAR.</li></ul></section><section><h2>7. Downloads</h2><div class="links"><a href="data/alabama_historical_war_v1_candidate_cycle_war.csv">Candidate-cycle WAR</a><a href="data/alabama_historical_war_v1_race_war.csv">Race WAR</a><a href="data/alabama_historical_war_v1_coverage.csv">Coverage</a><a href="data/alabama_historical_war_v1_structural_coefficients.csv">Coefficients</a><a href="data/alabama_historical_war_v1_manifest.json">Manifest</a><a href="data/alabama_historical_war_release_card.md">Release card and limitations</a></div></section></main></body></html>'''


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Render the historical Alabama WAR explorer.")
    parser.add_argument(
        "--artifact-only",
        action="store_true",
        help="Write the local release-candidate HTML under artifacts/site/ without touching docs/.",
    )
    args = parser.parse_args()
    require_fresh_inputs()
    rendered = build_page(load_data(), plan_geometry(),
                          site_geography.alabama_context(site_geography.alabama_frame()))
    methodology_html = build_historical_residual_war_methodology()
    methodology_html = re.sub(r'(<h2>1\. Estimand</h2><div class="formula">.*?</div>)',
                              lambda m: m.group(1) + war_identity_figure(), methodology_html, count=1, flags=re.S)
    _hist_manifest = json.loads(HISTORICAL_MANIFEST.read_text(encoding="utf-8"))
    methodology_html = methodology_html.replace(
        "__BACKCAST_RACES__", str(_hist_manifest["diagnostics"]["backcast_races"])
    )
    methodology_html = methodology_html.replace(
        "Candidate display names come from election identity records, with archived election pages used only as a spelling cross-check.",
        "Candidate display names come from election identity records. Evidence-backed manual adjudications replace malformed identifier-shaped source labels, while archived election pages provide a spelling cross-check.",
    ).replace(
        "The public forecast evaluates generic candidates at zero expected WAR.",
        "The public forecast carries part of each matched nominee's prior Alabama WAR forward and retains the fitted WAR structure and incumbency effect; historical WAR itself is retrospective.",
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    LEGACY_OUTPUT.write_text(rendered, encoding="utf-8")
    (OUTPUT.parent / "cmo-methodology.html").write_text(methodology_html, encoding="utf-8")
    if args.artifact_only:
        print(f"Wrote {OUTPUT} and {OUTPUT.parent / 'cmo-methodology.html'} (artifact only)")
        raise SystemExit(0)
    SITE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SITE_OUTPUT.write_text(rendered, encoding="utf-8")
    SITE_METHODOLOGY_OUTPUT.write_text(methodology_html, encoding="utf-8")
    site_data = SITE_OUTPUT.parent / "data"
    site_data.mkdir(parents=True, exist_ok=True)
    # Owner-authorized removal (2026-09-11, DOCS_DATA_INVENTORY_2026_09_11.md): legacy
    # CMO v4/v5/v6 exports, diagnostics and model cards are no longer published;
    # their upstream artifacts remain under data/processed/war.
    for pattern in ("cmo_v4_*", "cmo_v5_*", "cmo_v6_*", "cmo_methodology_v*.md", "cmo_model_card.md",
                    "cmo_benchmark_diagnostics.csv", "cmo_diagnostics.csv", "cmo_forward_interval_calibration.csv",
                    "cmo_forward_validation.csv", "rdh_2024_sld_cvap.csv"):
        for stale in site_data.glob(pattern):
            if stale.is_file():
                stale.unlink()
    sources = {
        WAR / "alabama_historical_war_v1" / "candidate_cycle_war.csv": "alabama_historical_war_v1_candidate_cycle_war.csv",
        WAR / "alabama_historical_war_v1" / "race_war.csv": "alabama_historical_war_v1_race_war.csv",
        WAR / "alabama_historical_war_v1" / "coverage.csv": "alabama_historical_war_v1_coverage.csv",
        WAR / "alabama_historical_war_v1" / "structural_coefficients.csv": "alabama_historical_war_v1_structural_coefficients.csv",
        WAR / "alabama_historical_war_v1" / "manifest.json": "alabama_historical_war_v1_manifest.json",
        WAR / "alabama_war_v1" / "candidate_cycle_war.csv": "alabama_war_v1_candidate_cycle_war.csv",
        WAR / "alabama_war_v1" / "race_war.csv": "alabama_war_v1_race_war.csv",
        WAR / "alabama_war_v1" / "coverage.csv": "alabama_war_v1_coverage.csv",
        WAR / "alabama_war_v1" / "manifest.json": "alabama_war_v1_manifest.json",
        ROOT / "data/processed/forecast_calibration/alabama_war_forecast_v1_forward_metrics.csv": "alabama_war_forecast_v1_forward_metrics.csv",
        WAR / "alabama_career_war_v1" / "career_war.csv": "alabama_career_war_v1_career_war.csv",
        WAR / "alabama_career_war_v1" / "manifest.json": "alabama_career_war_v1_manifest.json",
        ROOT / "project_docs/audits/ALABAMA_HISTORICAL_WAR_RELEASE_CARD_2026_09_11.md": "alabama_historical_war_release_card.md",
    }
    for source, name in sources.items():
        shutil.copy2(source, site_data / name)
    print(f"Wrote historical Alabama WAR map ({OUTPUT})")
