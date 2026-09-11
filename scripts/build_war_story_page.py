"""Build a self-contained Alabama candidate margin-overperformance page."""

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

from southern_war_release_gate import require_alabama_historical_release


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
MAPS = ROOT / "data" / "raw" / "alabama_elections_and_geography"
OUTPUT = ROOT / "artifacts" / "site" / "alabama-legislative-cmo.html"
LEGACY_OUTPUT = ROOT / "artifacts" / "site" / "alabama-legislative-war-legacy.html"
SITE_OUTPUT = ROOT / "docs" / "cmo.html"
SITE_METHODOLOGY_OUTPUT = ROOT / "docs" / "cmo-methodology.html"
HISTORICAL_MANIFEST = WAR / "alabama_historical_war_v1" / "manifest.json"
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


def path_for_geometry(geom, bounds, width=640, height=700, pad=12):
    minx, miny, maxx, maxy = bounds
    scale = min((width - 2 * pad) / (maxx - minx), (height - 2 * pad) / (maxy - miny))
    ox = (width - (maxx - minx) * scale) / 2
    oy = (height - (maxy - miny) * scale) / 2

    def ring(coords):
        pts = [(ox + (x - minx) * scale, height - (oy + (y - miny) * scale)) for x, y in coords]
        return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"

    polygons = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    return "".join(ring(poly.exterior.coords) + "".join(ring(h.coords) for h in poly.interiors) for poly in polygons)


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

    groups = {}
    for row in candidates:
        cycle, chamber, district = int(row["cycle"]), row["chamber"], int(float(row["district"]))
        race = race_index[(cycle, chamber, district)]
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
                "modern post-2016 structural backcast" if row.get("scoring_scope") == "post2016_southern_model_backcast" else "published same-cycle residual",
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
        frame = gpd.read_file(f"zip://{(MAPS / MAP_FILES[(cycle, chamber)]).resolve()}").to_crs(4326)
        frame["district"] = frame.apply(lambda r: district_id(r, cycle, chamber), axis=1)
        frame["geometry"] = frame.geometry.simplify(.007, preserve_topology=True)
        bounds = frame.total_bounds
        paths = [{"district": int(r.district), "path": path_for_geometry(r.geometry, bounds)} for _, r in frame.iterrows()]
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
            "paths": paths, "candidates": sorted(items, key=lambda x: x["war"], reverse=True), "winners": winners,
            "demWar": dem_context, "demWithin": dem_within, "demRawTicket": dem_raw, "demPair": dem_pair,
            "demPercentile": percentiles, "rawVsGovernor": raw_gov, "rawVsPresidential": raw_pres,
            "districtStatus": {str(d): f"{race_index[(cycle, chamber, d)]['contest_tier'].title()} contested D–R race" for d in districts},
            "baselines": {str(d): ([{"label": "Selected ticket baseline", "demMargin": round(number(race_index[(cycle, chamber, d)]["selected_ticket_margin"], 0), 2), "kind": "composite", "demName": "Democratic baseline", "repName": "Republican baseline"}, {"label": f"{PRIOR_PRESIDENTIAL_NOMINEES[cycle][0]} President", "demMargin": round(number(race_index[(cycle, chamber, d)].get("prior_presidential_margin"), 0), 2), "kind": "presidential", "available": number(race_index[(cycle, chamber, d)].get("prior_presidential_margin")) is not None, "demName": PRIOR_PRESIDENTIAL_NOMINEES[cycle][1], "repName": PRIOR_PRESIDENTIAL_NOMINEES[cycle][2]}] + office_index.get((cycle, chamber, d), [])) for d in districts},
            "summary": {"races": len(winners), "candidates": len(items), "median": round(float(np.median([x["war"] for x in winners.values()])), 1), "top": max(winners.values(), key=lambda x: x["war"])["candidate"], "warMedian": round(float(np.median([x["partialPooled"] for x in winners.values()])), 1), "warTop": max(winners.values(), key=lambda x: x["partialPooled"])["candidate"]},
        }
    return payload


def build_attribution_panel(tag="section"):
    sources = [
        ("Election returns", "Alabama Secretary of State", "Official legislative, statewide-office, and presidential returns; the authoritative election source.", "https://www.sos.alabama.gov/alabama-votes/voter/election-information"),
        ("Election reconciliation", "OpenElections", "Standardized secondary election files used for comparison, normalization, and documented fallback—not a replacement for official returns.", "https://github.com/openelections/openelections-data-al"),
        ("Population and demographics", "U.S. Census Bureau", "1990/2000 decennial Census SF3, American Community Survey estimates, Census blocks and VTD geography.", "https://data.census.gov/"),
        ("District boundaries", "U.S. Census Bureau TIGER/Line and archived Alabama enacted-plan shapefiles", "Legislative boundary geometry used to render maps and allocate geographic features; the page identifies the plan vintage.", "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html"),
        ("Precinct geography and presidential returns", "Voting and Election Science Team (VEST)", "Election-specific precinct files used for historical presidential comparisons where available.", "https://dataverse.harvard.edu/dataverse/electionscience"),
        ("Historical campaign finance", "Database on Ideology, Money in Politics, and Elections (DIME), Adam Bonica", "Recipient-level contribution totals used for pre-electronic-era resource coverage; missing records remain unknown.", "https://data.stanford.edu/dime"),
        ("State campaign finance", "Alabama Secretary of State FCPA", "Principal-campaign-committee summaries provide the preferred 2014-2022 fundraising observations; identified committees with no cycle activity are observed zeros, while unmatched candidates remain unknown.", "https://fcpa.alabamavotes.gov/"),
        ("Finance cross-check", "FollowTheMoney / National Institute on Money in Politics", "Candidate fundraising totals provide a secondary comparison with Alabama campaign-finance records.", "https://www.followthemoney.org/"),
        ("Historical roster evidence", "Shor–McCarty state legislative data", "Serving-legislator roster and party evidence used in historical incumbency review.", "https://americanlegislatures.com/"),
        ("Independent validation", "Wikipedia election pages", "Archived pages used only to cross-check candidate names and vote totals; discrepancies do not overwrite official returns.", "https://en.wikipedia.org/wiki/Alabama_Legislature"),
        ("WAR framework and terminology", "Split Ticket", "The public WAR name credits Split Ticket's candidate-quality framework; this project's Alabama construction, inputs, estimates, and limitations are its own.", "https://split-ticket.org/2025/08/15/deconstructing-war/"),
    ]
    cards = "".join(
        f'<article><span>{html.escape(role)}</span><h3><a href="{url}" target="_blank" rel="noopener">{html.escape(name)} ↗</a></h3><p>{html.escape(use)}</p></article>'
        for role, name, use, url in sources
    )
    return f'<{tag} class="attribution" id="sources"><div class="section-head"><div><h2>Data sources and attribution</h2><p>Credits describe how each source is used in CMO. Derived scores, allocations, matches, and errors are this project’s calculations and should not be attributed to the source organizations.</p></div></div><div class="source-ledger">{cards}</div><p class="attribution-note"><b>Attribution boundary:</b> Source organizations provide underlying records or geography; none endorses this model. Alabama Secretary of State returns remain authoritative. OpenElections and Wikipedia are secondary checks. Finance missingness is never interpreted as zero.</p></{tag}>'


def build_validation_panel_v6():
    validation = list(csv.DictReader((WAR / "cmo_v6_southern_validation.csv").open(encoding="utf-8-sig", newline="")))
    quality = list(csv.DictReader((WAR / "cmo_v6_southern_quality.csv").open(encoding="utf-8-sig", newline="")))
    by_model = {}
    for row in validation:
        by_model.setdefault(row["model"], []).append(row)
    labels = {
        "ticket_baseline_only": "Ticket baseline only",
        "southern_incumbent_neutral": "Southern prior, incumbent neutral",
        "southern_portable_temporal": "Southern prior, observed incumbency",
    }
    model_rows = "".join(
        f"<tr><td>{labels[key]}</td><td>{np.mean([number(r['mae'], 0) for r in rows]):.2f}</td>"
        f"<td>{np.mean([number(r['mae'], 0) for r in rows if int(float(r['cycle'])) >= 2018]):.2f}</td></tr>"
        for key, rows in by_model.items()
    )
    penalty_rows = "".join(
        f"<tr><td>{number(row.get('parameter'), 0):g}</td><td>{int(number(row.get('races'), 0))}</td>"
        f"<td>{number(row.get('mae'), 0):.2f}</td><td>{number(row.get('zero_baseline_mae'), 0):.2f}</td></tr>"
        for row in quality
        if row.get("specification") == "seen_candidate" and not row.get("candidate_effect_id")
    )
    return f'''<section class="validation" id="validation"><div class="section-head"><div><h2>Historical accuracy</h2><p>The Southern comparison improves the fit to elections across the full 1994–2022 period but is less accurate in 2018–2022. It is useful for understanding historical results, not as a direct adjustment to the current forecast.</p></div><span class="warning-chip">Historical comparison</span></div><div class="validation-grid"><div><h3>Structural expectation</h3><div class="table-wrap compact"><table><thead><tr><th>Model</th><th>All-cycle MAE</th><th>2018–2022 MAE</th></tr></thead><tbody>{model_rows}</tbody></table></div></div><div><h3>Residual-quality penalty</h3><div class="table-wrap compact"><table><thead><tr><th>Penalty</th><th>Seen races</th><th>Prior-quality MAE</th><th>Zero MAE</th></tr></thead><tbody>{penalty_rows}</tbody></table></div></div></div><p class="validation-note">CMO is the observed comparison with the selected ticket. Residual candidate quality, generic incumbency, and total electoral value are historical estimates with uncertainty.</p></section>'''


def build_page(payload):
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alabama Legislative Candidate Margin Overperformance (CMO)</title>
<style>
__EXPLORER_CSS__
</style></head><body>
<header><div class="mast"><div><div class="brand">Jackson Hannan</div><div class="tag">Alabama legislative models</div></div><nav class="nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html" aria-current="page">CMO</a><a href="ideology-performance.html">Issues & caucuses</a><a href="methodology.html">Forecast methodology</a><a href="cmo-methodology.html">CMO methodology</a><a href="https://github.com/JacksonAHannan" target="_blank" rel="me noopener">GitHub</a></nav></div></header>
<main><section class="story-head"><h1>Alabama Candidate Margin Overperformance</h1><div class="dek">How far Alabama legislative candidates ran ahead of or behind the model’s district-level expectation from 1994 through 2022.</div><div class="byline">Model and analysis by <b>Jackson Hannan</b> &nbsp;•&nbsp; August 2026</div></section>
<section class="model-status"><div class="status-card feature"><span>Historical CMO architecture</span><b>Direct ticket comparison</b><p>The headline score is the legislative margin minus a source-aware same-district ticket baseline. Demographics, incumbency, finance, ideology, and candidate history do not alter the election-level score.</p></div><div class="status-card"><b>__CYCLE_COUNT__</b><span>Historical cycles</span></div><div class="status-card"><b>__ELIGIBLE_RACES__</b><span>Contested D vs. R races</span></div><div class="status-card"><b>3</b><span>Map views</span></div></section>
<section class="intro"><p>Candidate Margin Overperformance compares a legislative result with same-district political conditions measured from the ticket. The main score is directly auditable from the actual legislative margin and selected baseline.</p><p><strong>Direct ticket CMO is the headline measure.</strong> Positive values indicate performance ahead of the source-aware ticket baseline. Scores are two-party margin percentage points, are zero-sum within a race, and are not causal estimates of individual candidate quality.</p></section>
<section class="explorer"><div class="explorer-top"><div><h2>Explore the results</h2><div class="note">The default view maps CMO in margin points. The raw comparison views show the legislative margin relative to the same district's governor result or previous presidential result. Those three views use a symmetric ±30-point red-to-blue scale. Residual quality uses a separate ±20-point gold-to-teal scale; tooltips show uncapped values.</div></div><div class="note" id="vintage"></div></div><div class="controls" id="controls"></div>
<div class="dashboard"><div class="map-panel"><h3 class="map-title" id="map-title"></h3><div class="map-sub" id="map-sub">CMO, observed margin points</div><div class="map-modes"><button data-map-mode="absolute" class="active">CMO</button><button data-map-mode="governor">Raw overperformance vs. governor</button><button data-map-mode="presidential">Raw overperformance vs. previous presidential margin</button></div><div class="map-wrap"><svg id="map" viewBox="0 0 640 700" role="img"></svg><div class="legend"><div class="gradient" id="map-gradient"></div><div class="ticks" id="legend-ticks"></div></div></div></div><aside class="detail" id="detail"><div class="detail-empty">Select a colored district to inspect the race.</div></aside></div><div class="summary" id="summary"></div></section>
<section class="rankings"><h2>Candidate results</h2><div class="note">Direct CMO is the headline comparison. Federal, presidential, and career-pooled columns are labeled alternatives rather than replacements for the observed score.</div><div class="filters"><input id="candidate-search" type="search" placeholder="Search candidate or district"><select id="scope-filter"><option value="active">Selected cycle and chamber</option><option value="all">All cycles and chambers</option></select><select id="party-filter"><option value="all">All parties</option><option value="D">Democratic</option><option value="R">Republican</option></select><select id="outcome-filter"><option value="all">All candidates</option><option value="winner">Winners</option><option value="incumbent">Incumbents</option></select></div><div class="table-wrap"><table><thead><tr><th data-sort="cycle">Cycle</th><th data-sort="district">District</th><th data-sort="candidate">Candidate</th><th data-sort="war">Direct CMO ↕</th><th data-sort="within">State-ticket CMO</th><th data-sort="raw">Federal CMO</th><th data-sort="predictiveResidual">Presidential CMO</th><th data-sort="partialPooled">Career pooled</th><th data-sort="specificationRange">Band width</th><th data-sort="cycleTopTicket">Baseline margin</th><th data-sort="margin">Actual margin</th><th data-sort="votes">Votes</th></tr></thead><tbody id="rows"></tbody></table></div></section>
__VALIDATION_PANEL__
__ATTRIBUTION_PANEL__
<section class="downloads"><h2>Data and provenance</h2><p>Build updated August 21, 2026 from CMO methodology v4. Download the current rows, components, tournament, diagnostics, and provenance manifest.</p><div class="download-links"><a href="data/cmo_v4_candidates.csv">Candidate output</a><a href="data/cmo_v4_races.csv">Race output</a><a href="data/cmo_v4_components.csv">Components</a><a href="data/cmo_v4_model_tournament.csv">Model tournament</a><a href="data/cmo_v4_construct_validity.csv">Construct checks</a><a href="data/cmo_v4_provenance.csv">Run manifest</a><a href="cmo-methodology.html">Methodology</a></div></section>
<section class="method"><h2>How to read CMO</h2><p>The preferred baseline is the same-cycle federal ticket inside the district, with a documented same-cycle state-ticket fallback when necessary.</p><p>The structural model uses symmetric incumbency, era-specific downballot lag, limited demographics, and capped campaign effort. WAR-style CMO is the observed ticket gap minus that prediction; ideology is excluded so it can be tested afterward.</p><p><a href="cmo-methodology.html">Read the full CMO methodology</a>, <a href="index.html">view the 2026 forecast</a>, or read the <a href="methodology.html#models">forecast methodology</a>.</p><div class="source">Model output: <code>cmo_v4_candidates.csv</code>. Scores cover contested Democratic-versus-Republican races.</div></section></main><div class="tooltip" id="tooltip"></div>
<script>const DATA=__PAYLOAD__;
let active='2010-house',sortKey='war',sortDir=-1,selected=null,selectedParty=null,mapMode='absolute',baselineChoices={};
const $=s=>document.querySelector(s), fmt=n=>(n>0?'+':'')+Number(n).toFixed(1), fmtMaybe=n=>n==null?'Unavailable':fmt(n), pct=n=>n==null?'Unavailable':(100*Number(n)).toFixed(1)+'%', esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const allCandidates=()=>Object.entries(DATA).flatMap(([section,d])=>d.candidates.map(x=>({...x,section,cycle:d.cycle,chamber:d.chamber})));
const MODE_CONFIG={absolute:{description:'CMO, observed margin points',headline:'CMO',title:'overperformance',cap:30,low:'#d34b45',mid:'#f2f1ed',high:'#3d77a8',ticks:['R +30','R +15','Even','D +15','D +30']},quality:{description:'Pooled residual-quality differential, D minus R',headline:'Residual quality differential vs. opponent',title:'residual quality',cap:20,low:'#a66a24',mid:'#f3efe5',high:'#267c78',ticks:['R +20','R +10','Even','D +10','D +20']},governor:{description:'Raw overperformance vs. governor',headline:'Raw overperformance vs. governor',title:'overperformance vs. governor',cap:30,low:'#d34b45',mid:'#f2f1ed',high:'#3d77a8',ticks:['R +30','R +15','Even','D +15','D +30']},presidential:{description:'Raw overperformance vs. previous presidential margin',headline:'Raw overperformance vs. previous presidential margin',title:'overperformance vs. previous president',cap:30,low:'#d34b45',mid:'#f2f1ed',high:'#3d77a8',ticks:['R +30','R +15','Even','D +15','D +30']}};
function modeConfig(){return MODE_CONFIG[mapMode]||MODE_CONFIG.absolute}
function color(v){if(v==null)return '#deded9';const c=modeConfig(),x=Math.max(-1,Math.min(1,Number(v)/c.cap));if(x<0)return mix(c.mid,c.low,-x);return mix(c.mid,c.high,x)}
function mapMetric(d,district){if(mapMode==='absolute')return d.demWar[district];if(mapMode==='quality')return d.demPair[district];if(mapMode==='governor')return d.rawVsGovernor[district];return d.rawVsPresidential[district]}
function mapRawValue(d,district){return mapMetric(d,district)}
function mapDescription(){return modeConfig().description}
function candidateMetric(x){if(!x)return null;if(mapMode==='absolute')return x.war;const value=mapMetric(DATA[active],x.district);return value==null?null:(x.party==='D'?Number(value):-Number(value))}
function candidateMetricPercentile(x){const value=candidateMetric(x);if(value==null)return null;const values=DATA[active].candidates.map(candidateMetric).filter(v=>v!=null&&Number.isFinite(v));return values.length?100*(values.filter(v=>v<value).length+.5*values.filter(v=>v===value).length)/values.length:null}
function ordinal(value){const n=Math.round(value),mod100=n%100;return n+(mod100>=11&&mod100<=13?'th':n%10===1?'st':n%10===2?'nd':n%10===3?'rd':'th')}
function candidateHeadline(x){const c=modeConfig(),value=candidateMetric(x),percentile=candidateMetricPercentile(x);if(value==null)return `<div class="war-number unavailable">Unavailable</div><div class="war-label">${esc(c.headline)}</div>`;return `<div class="war-number">${fmt(value)}</div><div class="war-label">${esc(c.headline)} &middot; ${ordinal(percentile)} percentile</div><div class="distribution" style="background:linear-gradient(90deg,${c.low},${c.mid} 50%,${c.high})"><i style="left:${percentile}%"></i><div class="distribution-label"><span>Lowest</span><span>Median</span><span>Highest</span></div></div>`}
function currentSelectedCandidate(){if(selected==null)return null;const d=DATA[active];return d.candidates.find(c=>c.district===Number(selected)&&(!selectedParty||c.party===selectedParty))||d.winners[selected]||null}
function mapValueText(value){const side=value>=0?'Democratic':'Republican',amount=Math.abs(value).toFixed(1);return mapMode==='quality'?`${side} residual-quality advantage: ${amount} points`:`${side} overperformance: ${amount} points`}
function mix(a,b,t){const A=a.match(/\w\w/g).map(x=>parseInt(x,16)),B=b.match(/\w\w/g).map(x=>parseInt(x,16));return '#'+A.map((x,i)=>Math.round(x+(B[i]-x)*t).toString(16).padStart(2,'0')).join('')}
function makeControls(){const box=$('#controls');box.innerHTML='';[['Early historical · 1994–2006',y=>y<=2006],['Modern series · 2010–2022',y=>y>=2010]].forEach(([label,include])=>{const group=document.createElement('div');group.className='cycle-group';const heading=document.createElement('span');heading.className='cycle-group-label';heading.textContent=label;const buttons=document.createElement('div');buttons.className='cycle-buttons';Object.keys(DATA).filter(k=>include(DATA[k].cycle)).forEach(k=>{const d=DATA[k],b=document.createElement('button');b.textContent=d.cycle+' '+(d.chamber==='house'?'House':'Senate');b.className=k===active?'active':'';b.setAttribute('aria-pressed',k===active?'true':'false');b.onclick=()=>{active=k;selected=null;selectedParty=null;render()};buttons.appendChild(b)});group.append(heading,buttons);box.appendChild(group)})}
function baselineOptions(x){const raw=DATA[active].baselines[String(x.district)]||[];return raw.filter(o=>o.available!==false).sort((a,b)=>{const rank=o=>o.label==='Governor'?0:o.kind==='office'?1:o.kind==='composite'?2:3;return rank(a)-rank(b)||a.label.localeCompare(b.label)})}
function setBaseline(district,index){baselineChoices[active+'-'+district]=index;detail(currentSelectedCandidate()||DATA[active].winners[district])}
function baselineContext(x,total){const options=baselineOptions(x);if(!options.length)return '';const key=active+'-'+x.district,index=Math.min(baselineChoices[key]??0,options.length-1),o=options[index],margin=o.demMargin,leader=margin>=0?'D':'R',demShare=(100+margin)/2,repShare=100-demShare,isObserved=o.kind==='office',boxTotal=isObserved?Number(o.demVotes)+Number(o.repVotes):total,demVotes=isObserved?Number(o.demVotes):Math.round(boxTotal*demShare/100),repVotes=isObserved?Number(o.repVotes):Math.round(boxTotal*repShare/100),gap=Math.abs(Math.round(demVotes-repVotes)),tabs=options.map((v,i)=>`<button class="${i===index?'active':''}" onclick="setBaseline(${x.district},${i})">${esc(v.label)}</button>`).join(''),subtitle=isObserved?'District-level two-party office result':'Margin normalized to legislative two-party turnout',note=isObserved?'Votes are the allocated district result for this statewide office.':'Vote totals are implied from the selected margin at the legislative race’s observed turnout.';return `<div class="baseline-context"><div class="baseline-title">District top-of-ticket context</div><div class="baseline-tabs">${tabs}</div><div class="baseline-wikibox"><div class="baseline-wikibox-head">${esc(o.label)}</div><div class="baseline-wikibox-sub">${subtitle}</div><table><thead><tr><th></th><th>Candidate</th><th>Party</th><th class="num">Votes</th><th class="num">Share</th></tr></thead><tbody><tr class="${leader==='D'?'leader':''}"><td class="party-cell D"></td><td>${esc(o.demName)}</td><td>D${leader==='D'?' <span class="check">✓</span>':''}</td><td class="num">${Math.round(demVotes).toLocaleString()}</td><td class="num">${demShare.toFixed(1)}%</td></tr><tr class="${leader==='R'?'leader':''}"><td class="party-cell R"></td><td>${esc(o.repName)}</td><td>R${leader==='R'?' <span class="check">✓</span>':''}</td><td class="num">${Math.round(repVotes).toLocaleString()}</td><td class="num">${repShare.toFixed(1)}%</td></tr></tbody></table><div class="baseline-wikibox-foot"><div><b>${Math.round(boxTotal).toLocaleString()}</b> two-party votes</div><div>Margin: <b>${leader}+${Math.abs(margin).toFixed(1)}</b> · ${gap.toLocaleString()} votes</div></div><div class="baseline-wikibox-note">${note}</div></div><div class="source-credit">Source: Alabama Secretary of State official returns; district allocation and composite calculations by this project.</div></div>`}
function raceBox(x){const d=DATA[active],race=d.candidates.filter(c=>c.district===x.district).sort((a,b)=>b.votes-a.votes),total=race.reduce((s,c)=>s+c.votes,0),actualGap=race.length>1?race[0].votes-race[1].votes:total,actualMargin=100*actualGap/total,dem=race.find(c=>c.party==='D'),expectedDem=dem?dem.expectedMargin:0,expectedLeader=expectedDem>=0?'Democratic':'Republican',expectedGap=Math.round(total*Math.abs(expectedDem)/100),rows=race.map(c=>{const expectedShare=(100+c.expectedMargin)/2,expectedVotes=Math.round(total*expectedShare/100);return `<tr class="${c.winner?'winner-row':''}"><td class="party-cell ${c.party}"></td><td class="candidate-col">${esc(c.candidate)} ${c.party}${c.incumbent?' <small>(inc.)</small>':''}${c.winner?' <span class="check">✓</span>':''}</td><td class="num">${c.votes.toLocaleString()}</td><td class="num">${(100*c.votes/total).toFixed(1)}%</td><td class="num expected">${expectedVotes.toLocaleString()}</td><td class="num expected">${expectedShare.toFixed(1)}%</td></tr>`}).join('');return `<div class="racebox"><div class="racebox-head">${d.cycle} Alabama ${d.chamber==='house'?'House':'Senate'} District ${x.district}</div><div class="racebox-sub">General election · actual versus ticket baseline</div><table><thead><tr><th rowspan="2"></th><th rowspan="2">Candidate</th><th colspan="2" class="group-head">Actual</th><th colspan="2" class="group-head">Ticket baseline</th></tr><tr><th class="num">Votes</th><th class="num">Share</th><th class="num">Votes</th><th class="num">Share</th></tr></thead><tbody>${rows}</tbody></table><div class="racebox-comparison"><div><span>Actual margin</span><b>${race[0].party==='D'?'Democratic':'Republican'} +${actualMargin.toFixed(1)} pts · ${actualGap.toLocaleString()} votes</b></div><div><span>Ticket baseline margin</span><b>${expectedLeader} +${Math.abs(expectedDem).toFixed(1)} pts · ${expectedGap.toLocaleString()} votes</b></div><div><span>Two-party turnout</span><b>${total.toLocaleString()} votes</b></div></div><div class="source-credit">Actual votes: Alabama Secretary of State. Candidate-name display may use archived Wikipedia pages only as a secondary cross-check; official totals control.</div>${baselineContext(x,total)}</div>`}
function detail(x){const box=$('#detail');if(!x){box.innerHTML='<div class="detail-empty">Select a district or candidate row to inspect the race.</div>';return}const history=allCandidates().filter(c=>c.personId&&c.personId===x.personId).sort((a,b)=>a.cycle-b.cycle),historyHtml=history.length>1?`<div class="decomp"><div class="decomp-title">Resolved candidate history</div>${history.map(c=>`<div class="stat"><span>${c.cycle} ${c.chamber} ${c.district}</span><b>${fmt(c.war)}</b></div>`).join('')}</div>`:'';box.innerHTML=`<div class="candidate-headline"><h3>${esc(x.candidate)}</h3><div class="party ${x.party}">${x.party==='D'?'Democratic':'Republican'} • District ${x.district}${x.incumbent?' • Incumbent':''}</div><div class="war-number">${fmt(x.war)}</div><div class="war-label">CMO • ${x.percentile.toFixed(0)}th percentile</div><div class="distribution"><i style="left:${x.percentile}%"></i><div class="distribution-label"><span>Lowest</span><span>Median</span><span>Highest</span></div></div></div>${raceBox(x)}<div class="stat"><span>Raw ticket gap</span><b>${fmtMaybe(x.raw)}</b></div><div class="stat"><span>Predicted structural gap</span><b>${fmtMaybe(x.predictedStructuralGap)}</b></div><div class="stat"><span>Career pooled CMO</span><b>${fmt(x.partialPooled)}</b></div><div class="stat"><span>Career reliability</span><b>${(100*x.attributionReliability).toFixed(0)}% · ${x.appearances} appearance${x.appearances===1?'':'s'}</b></div><div class="decomp"><div class="decomp-title">Source quality</div><div class="quality-grid"><div><span>Baseline method</span><b>${esc(x.baselineMethod||'Unavailable')}</b></div><div><span>Baseline fallback</span><b>${pct(x.baselineFallbackShare)}</b></div><div><span>Identity linkage</span><b>${esc(x.identityStatus)}</b></div><div><span>Demographics</span><b>${esc(x.demographicsMethod||'Unavailable')}${x.demographicReferenceYear?' · '+Math.round(x.demographicReferenceYear):''}</b></div><div><span>Previous president</span><b>${fmtMaybe(x.priorPres)}</b></div><div><span>Votes</span><b>${x.votes.toLocaleString()}</b></div></div></div>${historyHtml}<div class="explain">${x.war>=0?'This candidate ran ahead of':'This candidate ran behind'} the source-aware same-district ticket baseline by about <b>${Math.abs(x.war).toFixed(1)} points</b>.<br><br><b>Data note:</b> ${esc(x.quality)}</div>`}
function renderMap(){const d=DATA[active],map=$('#map'),tip=$('#tooltip'),config=modeConfig();map.innerHTML='';map.setAttribute('aria-label',`${d.cycle} Alabama ${d.chamber} ${config.title} map`);d.paths.forEach(p=>{const x=d.winners[p.district],display=mapMetric(d,p.district),raw=mapRawValue(d,p.district),status=d.districtStatus[String(p.district)]||'No election record available',el=document.createElementNS('http://www.w3.org/2000/svg','path');el.setAttribute('d',p.path);el.setAttribute('fill',color(display));el.setAttribute('class','district'+(selected===p.district?' selected':''));el.setAttribute('tabindex','0');el.setAttribute('aria-label',x&&raw!=null?`District ${p.district}, ${mapValueText(raw)}, won by ${x.candidate}`:`District ${p.district}, ${status}`);el.onmouseenter=e=>{tip.style.display='block';tip.innerHTML=x&&raw!=null?`<b>District ${p.district}</b><br>${mapDescription()}<br>${mapValueText(raw)}<br>Won by ${esc(x.candidate)}`:`<b>District ${p.district}</b><br>${esc(x?'Selected benchmark unavailable':status)}`;moveTip(e)};el.onmousemove=moveTip;el.onmouseleave=()=>tip.style.display='none';el.onclick=()=>{selected=p.district;selectedParty=x?x.party:null;detail(x);renderMap()};el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();el.onclick()}};map.appendChild(el)});$('#map-title').textContent=`${d.cycle} Alabama ${d.chamber[0].toUpperCase()+d.chamber.slice(1)} ${config.title}`;$('#vintage').textContent='Boundaries: '+d.mapVintage;$('#map-sub').textContent=mapDescription();$('#map-gradient').style.background=`linear-gradient(90deg,${config.low} 0%,${config.mid} 50%,${config.high} 100%)`;$('#legend-ticks').innerHTML=config.ticks.map(t=>`<span>${t}</span>`).join('')}
function moveTip(e){const t=$('#tooltip');t.style.left=(e.clientX+14)+'px';t.style.top=(e.clientY+14)+'px'}
function selectCandidate(section,district,party){active=section;selected=Number(district);selectedParty=party;const x=currentSelectedCandidate();render();detail(x);$('#detail').scrollIntoView({behavior:'smooth',block:'start'})}
function renderRows(){const d=DATA[active],scope=$('#scope-filter').value,q=$('#candidate-search').value.toLowerCase(),party=$('#party-filter').value,outcome=$('#outcome-filter').value,source=scope==='all'?allCandidates():d.candidates.map(x=>({...x,section:active,cycle:d.cycle,chamber:d.chamber})),rows=source.filter(x=>(party==='all'||x.party===party)&&(outcome==='all'||(outcome==='winner'&&x.winner)||(outcome==='incumbent'&&x.incumbent))&&(!q||x.candidate.toLowerCase().includes(q)||String(x.district)===q||String(x.cycle)===q||`${x.chamber} ${x.district}`.includes(q))).sort((a,b)=>{let A=a[sortKey],B=b[sortKey];return(typeof A==='string'?A.localeCompare(B):A-B)*sortDir});$('#rows').innerHTML=rows.map(x=>`<tr tabindex="0" data-section="${x.section}" data-district="${x.district}" data-party="${x.party}"><td>${x.cycle} ${x.chamber==='house'?'H':'S'}</td><td>${x.district}</td><td class="cand"><i class="party-dot ${x.party}"></i>${esc(x.candidate)}${x.winner?' <small>✓</small>':''}${x.contestTier==='nominal'?' <span class="tier-badge sensitivity">Nominal</span>':''}</td><td class="num"><b>${fmt(x.war)}</b></td><td class="num">${fmt(x.within)}</td><td class="num">${fmtMaybe(x.raw)}</td><td class="num">${fmtMaybe(x.predictiveResidual)}</td><td class="num">${fmt(x.partialPooled)}</td><td class="num">${x.specificationRange.toFixed(1)}</td><td class="num">${fmt(x.cycleTopTicket)}</td><td class="num">${fmt(x.margin)}</td><td class="num">${x.votes.toLocaleString()}</td></tr>`).join('');document.querySelectorAll('#rows tr').forEach(row=>{row.onclick=()=>selectCandidate(row.dataset.section,row.dataset.district,row.dataset.party);row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.onclick()}}})}
function render(){makeControls();const d=DATA[active];renderMap();detail(currentSelectedCandidate());renderRows();$('#summary').innerHTML=`<div><b>${d.summary.races}</b><span>Contested districts</span></div><div><b>${d.summary.candidates}</b><span>Candidates scored</span></div><div><b>${fmt(d.summary.median)}</b><span>Median winner CMO</span></div><div><b>${esc(d.summary.top)}</b><span>Top winner</span></div>`}
document.querySelectorAll('th[data-sort]').forEach(th=>th.onclick=()=>{const k=th.dataset.sort;sortDir=sortKey===k?-sortDir:(k==='candidate'?1:-1);sortKey=k;renderRows()});['candidate-search','scope-filter','party-filter','outcome-filter'].forEach(id=>$('#'+id).oninput=renderRows);document.querySelectorAll('[data-map-mode]').forEach(button=>button.onclick=()=>{mapMode=button.dataset.mapMode;document.querySelectorAll('[data-map-mode]').forEach(b=>b.classList.toggle('active',b===button));renderMap();detail(currentSelectedCandidate())});render();</script></body></html>'''
    eligible_races = sum(section["summary"]["races"] for section in payload.values())
    cycle_count = len({section["cycle"] for section in payload.values()})
    return (template.replace("__EXPLORER_CSS__", (ROOT / "dashboard/war_explorer.css").read_text(encoding="utf-8").strip())
            .replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
            .replace("__ELIGIBLE_RACES__", str(eligible_races))
            .replace("__CYCLE_COUNT__", str(cycle_count))
            .replace("__VALIDATION_PANEL__", build_validation_panel_v6())
            .replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
            .replace("Build updated August 16, 2026", "Build updated August 17, 2026")
            .replace("Spending ${x.financeComplete?'complete':'incomplete'} · FTM ${x.ftmFinanceComplete?'complete':'incomplete'}",
                     "Canonical fundraising ${x.ftmFinanceComplete?'complete':'incomplete'} · DIME/FCPA source priority"))


def modernize_historical_residual_war(rendered):
    """Retain the historical map while replacing every superseded CMO/WAR claim."""
    rendered = rendered.replace(
        "<title>Alabama Legislative Candidate Margin Overperformance (CMO)</title>",
        "<title>Alabama historical WAR · Jackson Hannan</title>",
    )
    rendered = re.sub(
        r'<section class="story-head">.*?</section>',
        '<section class="story-head"><h1>Alabama historical WAR</h1>'
        '<div class="dek">Race-residual performance for every modeled Alabama legislative election from 1994 through 2022, with the modern post-2016 structural relationship applied backward to earlier elections.</div>'
        '<div class="byline">Model and analysis by <b>Jackson Hannan</b> &nbsp;·&nbsp; September 2026</div></section>',
        rendered, count=1, flags=re.S,
    )
    rendered = re.sub(
        r'<section class="model-status">.*?</section>',
        '<section class="model-status"><div class="status-card feature"><span>Historical WAR architecture</span><b>Modern-model backcast</b><p>1994–2014 structural expectations come from the selected model trained only on strict Southern races after 2016. Published 2018/2022 Alabama WAR remains unchanged.</p></div><div class="status-card"><b>8</b><span>Historical cycles</span></div><div class="status-card"><b>509</b><span>Contested D vs. R races</span></div><div class="status-card"><b>3</b><span>Map views</span></div></section>',
        rendered, count=1, flags=re.S,
    )
    rendered = re.sub(
        r'<section class="intro">.*?</section>',
        '<section class="intro"><p><strong>WAR is the race residual:</strong> the actual legislative-minus-ticket gap minus the fitted structural expected gap. Scores are two-party margin points and are zero-sum within each race.</p><p>For 1994–2014, the fitted expectation is a backward application of the post-2016 Southern <code>decaying_lag</code> ridge model. It is explicitly a historical backcast. For 2018 and 2022, the map uses the exact published same-cycle Alabama WAR residual.</p><p>No pooled candidate effect, career average, fundraising, ideology, or committee identity enters WAR.</p></section>',
        rendered, count=1, flags=re.S,
    )
    rendered = rendered.replace(
        "The default view maps CMO in margin points. The raw comparison views show the legislative margin relative to the same district's governor result or previous presidential result. Those three views use a symmetric Â±30-point red-to-blue scale. Residual quality uses a separate Â±20-point gold-to-teal scale; tooltips show uncapped values.",
        "The default view maps race-residual WAR in margin points. Raw comparison views retain the governor and previous-presidential benchmarks for context. Colors are capped at ±30 points; tooltips and race details show uncapped values.",
    )
    # Match the legacy explorer note independently of its historically mangled
    # plus/minus glyph so the correction is deterministic across Windows codecs.
    rendered = re.sub(
        r'The default view maps CMO in margin points\..*?tooltips show uncapped values\.',
        'The default view maps race-residual WAR in margin points. Raw comparison views retain the governor and previous-presidential benchmarks for context. Colors are capped at ±30 points; tooltips and race details show uncapped values.',
        rendered,
        count=1,
    )
    rendered = rendered.replace('id="map-sub">CMO, observed margin points', 'id="map-sub">Alabama WAR, residual margin points')
    rendered = rendered.replace('data-map-mode="absolute" class="active">CMO</button>', 'data-map-mode="absolute" class="active">Alabama WAR</button>')
    rendered = re.sub(
        r'<section class="rankings"><h2>Candidate results</h2>.*?<div class="filters">',
        '<section class="rankings"><h2>Candidate-cycle WAR results</h2><div class="note">Each pair of candidate rows is one opposite-signed race residual. Historical backcasts and published modern residuals are labeled separately.</div><div class="filters">',
        rendered, count=1, flags=re.S,
    )
    rendered = re.sub(
        r'(<section class="rankings">.*?<table><thead>)<tr>.*?</tr>(</thead>)',
        r'\1<tr><th data-sort="cycle">Cycle</th><th data-sort="district">District</th><th data-sort="candidate">Candidate</th><th data-sort="war">Alabama WAR ↕</th><th data-sort="rawGap">Raw ticket gap</th><th data-sort="predictedStructuralGap">Structural expectation</th><th data-sort="lagComponent">Lag component</th><th data-sort="scoringScope">Scoring method</th><th data-sort="cycleTopTicket">Baseline margin</th><th data-sort="margin">Actual margin</th><th data-sort="votes">Votes</th></tr>\2',
        rendered, count=1, flags=re.S,
    )
    validation = '''<section class="validation" id="validation"><div class="section-head"><div><h2>Historical scoring boundary</h2><p>The model is not trained on the elections it backcasts.</p></div><span class="warning-chip">Extrapolation</span></div><div class="validation-grid"><div><h3>1994–2014</h3><p>The selected post-2016 Southern structural model is fit once on 3,658 strict modern races, then applied backward to 412 Alabama races. Negative years-since-2016 values make this an extrapolation outside the training era.</p></div><div><h3>2018–2022</h3><p>The 97 modern Alabama races exactly preserve the published same-cycle residual WAR values.</p></div></div><p class="validation-note">Historical WAR is descriptive. It cannot uniquely divide a race residual between candidate strength, opponent weakness, and omitted local conditions.</p></section>'''
    rendered = re.sub(r'<section class="validation".*?</section>', validation, rendered, count=1, flags=re.S)
    rendered = re.sub(r'<section class="attribution".*?</section>', '', rendered, count=1, flags=re.S)
    rendered = re.sub(
        r'<section class="downloads">.*?</section>',
        '<section class="downloads"><h2>Data and provenance</h2><p>Download the complete historical race residuals, candidate orientations, coverage, coefficients, and content-addressed manifest.</p><div class="download-links"><a href="data/alabama_historical_war_v1_candidate_cycle_war.csv">Candidate-cycle WAR</a><a href="data/alabama_historical_war_v1_race_war.csv">Race WAR</a><a href="data/alabama_historical_war_v1_coverage.csv">Coverage</a><a href="data/alabama_historical_war_v1_structural_coefficients.csv">Backcast coefficients</a><a href="data/alabama_historical_war_v1_manifest.json">Manifest</a><a href="cmo-methodology.html">Methodology</a></div></section>',
        rendered, count=1, flags=re.S,
    )
    rendered = re.sub(
        r'<section class="method">.*?</section></main>',
        '<section class="method"><h2>How to read historical WAR</h2><p>Positive WAR means the candidate performed better than the fitted structural expectation; negative WAR means worse. The Democratic candidate receives the race residual and the Republican receives its exact negative.</p><p>Candidate display names come from election records, with archived election pages used only as a spelling cross-check. Finance provider and committee names are prohibited.</p><p><a href="cmo-methodology.html">Read the full methodology</a> or <a href="index.html">view the 2026 forecast</a>.</p></section></main>',
        rendered, count=1, flags=re.S,
    )
    rendered = re.sub(
        r'const MODE_CONFIG=.*?;\nfunction modeConfig',
        "const MODE_CONFIG={absolute:{description:'Alabama WAR, residual margin points',headline:'Alabama WAR',title:'WAR',cap:30,low:'#d34b45',mid:'#f2f1ed',high:'#3d77a8',ticks:['R +30','R +15','Even','D +15','D +30']},governor:{description:'Raw overperformance vs. governor',headline:'Raw overperformance vs. governor',title:'overperformance vs. governor',cap:30,low:'#d34b45',mid:'#f2f1ed',high:'#3d77a8',ticks:['R +30','R +15','Even','D +15','D +30']},presidential:{description:'Raw overperformance vs. previous presidential margin',headline:'Raw overperformance vs. previous presidential margin',title:'overperformance vs. previous president',cap:30,low:'#d34b45',mid:'#f2f1ed',high:'#3d77a8',ticks:['R +30','R +15','Even','D +15','D +30']}};\nfunction modeConfig",
        rendered, count=1, flags=re.S,
    )
    rendered = rendered.replace(
        "function mapMetric(d,district){if(mapMode==='absolute')return d.demWar[district];if(mapMode==='quality')return d.demPair[district];if(mapMode==='governor')return d.rawVsGovernor[district];return d.rawVsPresidential[district]}",
        "function mapMetric(d,district){if(mapMode==='absolute')return d.demWar[district];if(mapMode==='governor')return d.rawVsGovernor[district];return d.rawVsPresidential[district]}",
    )
    rendered = re.sub(
        r'function mapValueText\(value\)\{.*?\}\nfunction mix',
        "function mapValueText(value){const side=value>=0?'Democratic':'Republican',amount=Math.abs(value).toFixed(1);return mapMode==='absolute'?`${side} WAR advantage: ${amount} points`:`${side} overperformance: ${amount} points`}\nfunction mix",
        rendered, count=1, flags=re.S,
    )
    detail_js = r'''function detail(x){const box=$('#detail');if(!x){box.innerHTML='<div class="detail-empty">Select a district or candidate row to inspect the race.</div>';return}const history=allCandidates().filter(c=>c.personId&&c.personId===x.personId).sort((a,b)=>a.cycle-b.cycle),scope=x.scoringScope==='post2016_southern_model_backcast'?'Modern-model backcast':'Published same-cycle residual',historyHtml=history.length>1?`<div class="decomp"><div class="decomp-title">Resolved election history</div>${history.map(c=>`<div class="stat"><span>${c.cycle} ${c.chamber} ${c.district}</span><b>WAR ${fmt(c.war)}</b></div>`).join('')}</div>`:'';box.innerHTML=`<div class="candidate-headline"><h3>${esc(x.candidate)}</h3><div class="party ${x.party}">${x.party==='D'?'Democratic':'Republican'} · District ${x.district}${x.incumbent?' · Incumbent':''}</div><div class="war-number">${fmt(x.war)}</div><div class="war-label">Alabama WAR · ${x.percentile.toFixed(0)}th percentile</div><div class="distribution"><i style="left:${x.percentile}%"></i><div class="distribution-label"><span>Lowest</span><span>Median</span><span>Highest</span></div></div></div>${raceBox(x)}<div class="decomp"><div class="decomp-title">Residual decomposition</div><div class="stat"><span>Raw legislative-minus-ticket gap</span><b>${fmt(x.rawGap)}</b></div><div class="stat"><span>Fitted structural expectation</span><b>${fmt(x.predictedStructuralGap)}</b></div><div class="stat"><span>Lag component</span><b>${fmt(x.lagComponent)}</b></div><div class="stat"><span>Scoring method</span><b>${scope}</b></div><div class="stat"><span>Lag context</span><b>${x.lagContextAvailable?'Observed':'Unavailable; zero-valued model encoding'}</b></div></div><div class="decomp"><div class="decomp-title">Source quality</div><div class="quality-grid"><div><span>Baseline method</span><b>${esc(x.baselineMethod||'Unavailable')}</b></div><div><span>Identity linkage</span><b>${esc(x.identityStatus)}</b></div><div><span>Previous president</span><b>${fmtMaybe(x.priorPres)}</b></div><div><span>Votes</span><b>${x.votes.toLocaleString()}</b></div></div></div>${historyHtml}<div class="explain">${x.war>=0?'This candidate finished ahead of':'This candidate finished behind'} the fitted structural expectation by <b>${Math.abs(x.war).toFixed(1)} margin points</b>. ${x.scoringScope==='post2016_southern_model_backcast'?'This is a backward application of a model trained only on post-2016 Southern races.':'This is the published modern same-cycle residual.'}</div>`}'''
    rendered = re.sub(r'function detail\(x\)\{.*?\}\nfunction renderMap', detail_js + '\nfunction renderMap', rendered, count=1, flags=re.S)
    rows_js = r'''function renderRows(){const d=DATA[active],scope=$('#scope-filter').value,q=$('#candidate-search').value.toLowerCase(),party=$('#party-filter').value,outcome=$('#outcome-filter').value,source=scope==='all'?allCandidates():d.candidates.map(x=>({...x,section:active,cycle:d.cycle,chamber:d.chamber})),rows=source.filter(x=>(party==='all'||x.party===party)&&(outcome==='all'||(outcome==='winner'&&x.winner)||(outcome==='incumbent'&&x.incumbent))&&(!q||x.candidate.toLowerCase().includes(q)||String(x.district)===q||String(x.cycle)===q||`${x.chamber} ${x.district}`.includes(q))).sort((a,b)=>{let A=a[sortKey],B=b[sortKey];return(typeof A==='string'?A.localeCompare(B):(A??-9999)-(B??-9999))*sortDir});$('#rows').innerHTML=rows.map(x=>`<tr tabindex="0" data-section="${x.section}" data-district="${x.district}" data-party="${x.party}"><td>${x.cycle} ${x.chamber==='house'?'H':'S'}</td><td>${x.district}</td><td class="cand"><i class="party-dot ${x.party}"></i>${esc(x.candidate)}${x.winner?' <small>✓</small>':''}</td><td class="num"><b>${fmt(x.war)}</b></td><td class="num">${fmt(x.rawGap)}</td><td class="num">${fmt(x.predictedStructuralGap)}</td><td class="num">${fmt(x.lagComponent)}</td><td>${x.scoringScope==='post2016_southern_model_backcast'?'Modern backcast':'Published modern'}</td><td class="num">${fmt(x.cycleTopTicket)}</td><td class="num">${fmt(x.margin)}</td><td class="num">${x.votes.toLocaleString()}</td></tr>`).join('');document.querySelectorAll('#rows tr').forEach(row=>{row.onclick=()=>selectCandidate(row.dataset.section,row.dataset.district,row.dataset.party);row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.onclick()}}})}'''
    rendered = re.sub(r'function renderRows\(\)\{.*?\}\nfunction render\(', rows_js + '\nfunction render(', rendered, count=1, flags=re.S)
    rendered = rendered.replace("<span>Median winner CMO</span>", "<span>Median winner WAR</span>")
    rendered = rendered.replace("<span>Top winner</span>", "<span>Top WAR winner</span>")
    rendered = rendered.replace(">CMO</a>", ">Alabama WAR</a>")
    rendered = rendered.replace(">CMO methodology</a>", ">WAR methodology</a>")
    return rendered


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
    rendered = modernize_historical_residual_war(build_page(load_data()))
    methodology_html = build_historical_residual_war_methodology()
    _hist_manifest = json.loads(HISTORICAL_MANIFEST.read_text(encoding="utf-8"))
    methodology_html = methodology_html.replace(
        "__BACKCAST_RACES__", str(_hist_manifest["diagnostics"]["backcast_races"])
    )
    methodology_html = methodology_html.replace(
        "Candidate display names come from election identity records, with archived election pages used only as a spelling cross-check.",
        "Candidate display names come from election identity records. Evidence-backed manual adjudications replace malformed identifier-shaped source labels, while archived election pages provide a spelling cross-check.",
    ).replace(
        "The public forecast evaluates generic candidates at zero expected WAR.",
        "The public forecast sets candidate-specific residual WAR to zero, while retaining the fitted WAR structure and incumbency effect.",
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
        ROOT / "project_docs/audits/ALABAMA_HISTORICAL_WAR_RELEASE_CARD_2026_09_11.md": "alabama_historical_war_release_card.md",
    }
    for source, name in sources.items():
        shutil.copy2(source, site_data / name)
    print(f"Wrote historical Alabama WAR map ({OUTPUT})")
