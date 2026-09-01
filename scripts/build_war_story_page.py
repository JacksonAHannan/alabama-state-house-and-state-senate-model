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


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
MAPS = ROOT / "data" / "raw" / "alabama_elections_and_geography"
OUTPUT = ROOT / "artifacts" / "site" / "alabama-legislative-cmo.html"
LEGACY_OUTPUT = ROOT / "artifacts" / "site" / "alabama-legislative-war-legacy.html"
SITE_OUTPUT = ROOT / "docs" / "cmo.html"
SITE_METHODOLOGY_OUTPUT = ROOT / "docs" / "cmo-methodology.html"

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


def load_data():
    """Build the public payload from the validated CMO v6 historical product."""
    with (WAR / "cmo_v6_southern_candidates.csv").open(encoding="utf-8-sig", newline="") as f:
        candidates = list(csv.DictReader(f))
    with (WAR / "cmo_v6_southern_races.csv").open(encoding="utf-8-sig", newline="") as f:
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
            "candidate": public_name_index.get((cycle, chamber, district, party, int(number(row["canonical_votes"], 0))), row["canonical_name"]),
            "personId": row["candidate_effect_id"],
            "party": party, "votes": int(number(row["canonical_votes"], 0)),
            "war": round(number(row["candidate_direct_cmo"], 0), 2),
            "within": round(number(row.get("candidate_state_ticket_cmo")), 2) if number(row.get("candidate_state_ticket_cmo")) is not None else None,
            "raw": round(number(row.get("candidate_federal_ticket_cmo")), 2) if number(row.get("candidate_federal_ticket_cmo")) is not None else None,
            "predictiveResidual": round(number(row.get("candidate_presidential_ticket_cmo")), 2) if number(row.get("candidate_presidential_ticket_cmo")) is not None else None,
            "partialPooled": round(number(row.get("southern_candidate_quality_index"), 0), 2),
            "qualityLow": round(number(row.get("southern_candidate_quality_low"), 0), 2),
            "qualityHigh": round(number(row.get("southern_candidate_quality_high"), 0), 2),
            "qualityStatus": row.get("southern_quality_status", "uncertain"),
            "qualityResidual": round(number(row.get("candidate_quality_residual"), 0), 2),
            "southernExpectedGap": round(number(row.get("candidate_southern_expected_gap"), 0), 2),
            "genericIncumbency": round(number(row.get("candidate_generic_incumbency_component"), 0), 2),
            "totalElectoralValue": round(number(row.get("candidate_total_electoral_value"), 0), 2),
            "replacementLevel": round(number(row.get("candidate_replacement_level"), 0), 2),
            "structuralAdjustment": round(number(row.get("candidate_structural_adjustment"), 0), 2),
            "appearances": int(number(row.get("southern_quality_appearances"), 1)),
            "identityStatus": row.get("identity_status", ""), "contestTier": row.get("contest_tier", ""),
            "low": round(number(row.get("candidate_direct_baseline_low"), 0), 2),
            "high": round(number(row.get("candidate_direct_baseline_high"), 0), 2),
            "specificationRange": round(abs(number(row.get("candidate_direct_baseline_high"), 0) - number(row.get("candidate_direct_baseline_low"), 0)), 2),
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
        dem_context = {d: round(number(race_index[(cycle, chamber, d)]["direct_cmo"], 0), 2) for d in districts}
        dem_within = {d: round(number(race_index[(cycle, chamber, d)].get("state_ticket_cmo")), 2) if number(race_index[(cycle, chamber, d)].get("state_ticket_cmo")) is not None else None for d in districts}
        dem_raw = {d: round(number(race_index[(cycle, chamber, d)].get("federal_ticket_cmo")), 2) if number(race_index[(cycle, chamber, d)].get("federal_ticket_cmo")) is not None else None for d in districts}
        dem_pair = {d: round(number(race_index[(cycle, chamber, d)].get("pooled_quality_differential"), 0), 2) for d in districts}
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


def build_validation_panel():
    tournament = list(csv.DictReader((WAR / "cmo_v5_model_tournament.csv").open(encoding="utf-8-sig", newline="")))
    validity = [r for r in tournament if r.get("stage") == "construct"]
    quality = [r for r in tournament if r.get("stage") == "quality" and r.get("specification") == "seen_candidate"]
    construct_rows = "".join(
        f"<tr><td>{html.escape(r['specification'].replace('_', ' ').title())}</td><td>{r.get('pairs', '')}</td>"
        f"<td>{number(r.get('pearson'), 0):.3f}</td><td>{number(r.get('spearman'), 0):.3f}</td></tr>"
        for r in validity)
    quality_rows = "".join(
        f"<tr><td>{html.escape(str(r.get('parameter', '')))}</td><td>{r.get('races', '')}</td>"
        f"<td>{number(r.get('mae'), 0):.2f}</td><td>{number(r.get('zero_baseline_mae'), 0):.2f}</td></tr>"
        for r in quality)
    return f'''<section class="validation" id="validation"><div class="section-head"><div><h2>Diagnostics</h2><p>Observed CMO and estimated Candidate Quality answer different questions. Repeat-candidate tests choose the structural centering and ridge shrinkage used for the quality estimate.</p></div><span class="warning-chip">Retrospective—not causal</span></div><div class="validation-grid"><div><h3>Repeat-candidate construct check</h3><div class="table-wrap compact"><table><thead><tr><th>Measure</th><th>Pairs</th><th>Pearson</th><th>Spearman</th></tr></thead><tbody>{construct_rows}</tbody></table></div></div><div><h3>Candidate-quality penalty</h3><div class="table-wrap compact"><table><thead><tr><th>Penalty</th><th>Races</th><th>Prior-CQI MAE</th><th>Zero MAE</th></tr></thead><tbody>{quality_rows}</tbody></table></div></div></div><p class="validation-note">Direct CMO is descriptive and auditable. Candidate Quality is partially pooled, uncertainty-labeled, and should not be read as a precise causal division of credit between opponents.</p></section>'''
    # Legacy body below is intentionally unreachable and retained temporarily
    # to keep this focused migration reviewable.
    rows = "".join(
        f"<tr><td>{html.escape(r['specification'].replace('_', ' ').title())}</td><td>{r.get('alpha', '')}</td>"
        f"<td>{number(r.get('mean_cycle_mae'), 0):.1f}</td><td>{number(r.get('mean_cycle_rmse'), 0):.1f}</td></tr>" for r in tournament)
    validity_rows = "".join(
        f"<tr><td>{html.escape(r['design'].replace('_', ' ').title())}: {html.escape(r['outcome'].replace('_', ' '))}</td><td>{r.get('n', '')}</td>"
        f"<td>{number(r.get('pearson'), 0):.3f}</td></tr>" for r in validity)
    return f'''<section class="validation" id="validation"><div class="section-head"><div><h2>Diagnostics</h2><p>The structural model is selected with election-cycle holdouts. These diagnostics test the construction; they do not turn a retrospective residual into a forecast.</p></div><span class="warning-chip">Retrospective—not causal</span></div><div class="validation-grid"><div><h3>Cycle-held-out tournament</h3><div class="table-wrap compact"><table><thead><tr><th>Model</th><th>Ridge alpha</th><th>MAE</th><th>RMSE</th></tr></thead><tbody>{rows}</tbody></table></div></div><div><h3>Construct checks</h3><div class="table-wrap compact"><table><thead><tr><th>Check</th><th>N</th><th>Value</th></tr></thead><tbody>{validity_rows}</tbody></table></div></div></div><p class="validation-note">The score has little repeat-candidate persistence in the present sample. Read it as a candidate-cycle structural residual, not a durable or causal measure of candidate quality.</p></section>'''


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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Libre+Franklin:wght@500;600;700;800&display=swap');
:root{--ink:#101828;--muted:#667085;--line:#e4e7ec;--soft:#f8fafc;--red:#c93f49;--blue:#2878b5;--navy:#14253d}
*{box-sizing:border-box} body{margin:0;color:var(--ink);background:#fff;font-family:Inter,Arial,sans-serif;line-height:1.55}
header{border-bottom:1px solid #263b57;background:var(--navy);color:#fff}.mast{max-width:1280px;margin:auto;padding:20px 28px;display:flex;align-items:center;justify-content:space-between;gap:24px}.brand{font:800 27px/1 'Libre Franklin',sans-serif;letter-spacing:-1px}.tag{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:#b9c5d4;margin-top:7px}.nav{display:flex;gap:24px;font:600 12px 'Libre Franklin',sans-serif}.nav a{color:#cbd5e1;text-decoration:none}.nav a[aria-current="page"],.nav a:hover{color:#fff}
main{max-width:1280px;margin:auto;padding:44px 28px 90px}.story-head{max-width:980px}.story-head h1{font:800 clamp(38px,5vw,66px)/1 'Libre Franklin',sans-serif;letter-spacing:-2.8px;margin:0 0 20px}.dek{font:400 19px/1.5 Georgia,serif;color:#475467;max-width:850px}.byline{margin-top:22px;font:600 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:1.1px;color:var(--muted)}.byline b{color:var(--ink)}
.model-status{display:grid;grid-template-columns:1.5fr repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:34px 0 44px}.status-card{background:#fff;padding:20px}.status-card.feature{background:var(--navy);color:#fff}.status-card b{display:block;font:800 23px 'Libre Franklin';margin-bottom:3px}.status-card span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.7px}.status-card.feature span{color:#b9c5d4}.status-card.feature p{font:13px/1.45 Inter;margin:8px 0 0;color:#e4eaf1}
.intro{max-width:750px;margin:58px 0 54px;font:18px/1.75 Georgia,serif}.intro p{margin:0 0 18px}.intro strong{font-family:Inter,sans-serif;font-size:16px}
.explorer{border-top:4px solid var(--ink);padding-top:22px}.explorer-top{display:flex;justify-content:space-between;align-items:end;gap:24px;margin-bottom:20px}.explorer h2{font:800 30px 'Libre Franklin';margin:0}.note{font-size:12px;color:var(--muted)}
.controls{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:18px 0 20px;max-width:900px}.cycle-group{padding:9px;background:var(--soft);border:1px solid var(--line)}.cycle-group-label{display:block;margin:0 5px 7px;font:700 9px 'Libre Franklin';color:var(--muted);text-transform:uppercase;letter-spacing:1px}.cycle-buttons{display:flex;gap:5px;flex-wrap:wrap}.controls button{border:0;background:transparent;border-radius:3px;padding:9px 11px;font:700 10px 'Libre Franklin';text-transform:uppercase;letter-spacing:.45px;cursor:pointer}.controls button:hover,.controls button:focus-visible{background:#e8edf3}.controls button.active{background:var(--navy);color:#fff;box-shadow:0 1px 3px #0002}
.dashboard{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(330px,.85fr);border:1px solid var(--line);min-height:720px}.map-panel{padding:28px 30px;border-right:1px solid var(--line);position:relative}.map-title{font:700 20px 'Libre Franklin';margin:0}.map-sub{font-size:12px;color:var(--muted);margin:5px 0 4px}.map-wrap{max-width:610px;margin:12px auto 0}.map-wrap svg{width:100%;height:auto;display:block}.district{stroke:#fff;stroke-width:1.1;vector-effect:non-scaling-stroke;cursor:pointer;transition:filter .12s,stroke-width .12s}.district:hover,.district.selected{stroke:#17191c;stroke-width:2.3;filter:brightness(.96)}
.legend{max-width:430px;margin:10px auto 0}.gradient{height:10px;background:linear-gradient(90deg,#d34b45,#e8a19d,#f2f1ed,#9bbcd4,#3d77a8)}.ticks{display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-top:5px}
.map-modes{display:flex;flex-wrap:wrap;gap:4px;margin-top:12px}.map-modes button{border:1px solid var(--line);background:#fff;padding:7px 10px;font:700 10px 'Libre Franklin';text-transform:uppercase;cursor:pointer}.map-modes button.active{background:var(--ink);color:#fff}
.detail{padding:30px 28px;display:flex;flex-direction:column}.detail-empty{margin:auto;color:var(--muted);font:16px Georgia,serif;text-align:center;max-width:260px}.detail h3{font:800 25px 'Libre Franklin';margin:0}.party{font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:1px;margin:6px 0 14px}.party.D{color:var(--blue)}.party.R{color:var(--red)}.badges{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:20px}.badge{background:#eef2f6;border-radius:20px;padding:4px 8px;font:700 9px 'Libre Franklin';letter-spacing:.4px;text-transform:uppercase}.badge.warn{background:#fff1d6;color:#7a4d00}.war-number{font:800 62px/.9 'Libre Franklin';letter-spacing:-3px}.war-number.unavailable{font-size:28px;letter-spacing:-1px}.war-label{font-size:11px;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted);margin:9px 0 12px}.distribution{position:relative;height:8px;background:linear-gradient(90deg,var(--red),#eee 50%,var(--blue));margin:9px 8px 38px;border-radius:5px}.distribution>i{position:absolute;top:-5px;width:3px;height:18px;background:var(--ink);box-shadow:0 0 0 2px #fff;transform:translateX(-50%)}.distribution-label{position:absolute;top:17px;left:0;right:0;display:flex;justify-content:space-between;font-size:9px;line-height:1;color:var(--muted)}.distribution-label span:first-child{transform:translateX(-2px)}.distribution-label span:last-child{transform:translateX(2px)}.stat{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:10px 0;font-size:13px}.stat b{font-family:'Libre Franklin'}.decomp{margin-top:12px;border:1px solid var(--line);padding:12px 14px}.decomp-title{font:700 10px 'Libre Franklin';text-transform:uppercase;letter-spacing:.7px;margin-bottom:5px}.explain{background:var(--soft);padding:15px 16px;margin-top:16px;font:13px/1.55 Georgia,serif}
.racebox{border:1px solid #aeb7c2;margin:20px 0 4px;background:#fff}.racebox-head{background:var(--navy);color:#fff;text-align:center;padding:9px 12px;font:700 13px 'Libre Franklin'}.racebox-sub{text-align:center;background:#edf1f5;border-bottom:1px solid #aeb7c2;padding:5px;font:600 10px 'Libre Franklin';text-transform:uppercase;letter-spacing:.5px}.racebox table{font-size:12px}.racebox th{cursor:default;background:#f8fafc;border-bottom:1px solid #cdd3da;padding:7px 8px;font-size:9px}.racebox td{padding:8px;border-bottom:1px solid #e4e7ec}.racebox tr:last-child td{border-bottom:0}.racebox .winner-row{font-weight:700}.racebox .party-cell{width:8px;padding:0}.racebox .party-cell.D{background:var(--blue)}.racebox .party-cell.R{background:var(--red)}.racebox-total{display:grid;grid-template-columns:1fr 1fr;background:#f8fafc;border-top:1px solid #cdd3da}.racebox-total div{padding:7px 9px;font-size:10px}.racebox-total div:last-child{text-align:right}.check{color:#157347;margin-left:4px}
.detail>.racebox{margin:0 0 22px}.racebox .group-head{text-align:center;background:#e8edf3}.racebox .candidate-col{min-width:115px}.racebox .expected{background:#f7f9fb}.racebox-comparison{background:#f8fafc;border-top:1px solid #cdd3da;padding:7px 9px}.racebox-comparison div{display:flex;justify-content:space-between;gap:12px;font-size:10px;padding:2px 0}.racebox-comparison b{text-align:right}
.baseline-context{border-top:3px solid var(--navy);margin-top:10px;padding:10px 9px;background:#fff}.baseline-title{font:700 10px 'Libre Franklin';text-transform:uppercase;letter-spacing:.6px;margin-bottom:7px}.baseline-tabs{display:flex;flex-wrap:wrap;gap:4px}.baseline-tabs button{border:1px solid #cdd3da;background:#f8fafc;padding:5px 7px;font:600 9px Inter;cursor:pointer}.baseline-tabs button.active{background:var(--navy);border-color:var(--navy);color:#fff}.baseline-wikibox{border:1px solid #aeb7c2;margin-top:9px}.baseline-wikibox-head{background:#dce5ee;text-align:center;padding:6px 8px;font:700 11px 'Libre Franklin'}.baseline-wikibox-sub{background:#f4f6f8;text-align:center;border-top:1px solid #cdd3da;border-bottom:1px solid #cdd3da;padding:3px 6px;font-size:9px;color:var(--muted)}.baseline-wikibox table{font-size:10px}.baseline-wikibox th{padding:5px 7px;font-size:8px;background:#f8fafc}.baseline-wikibox td{padding:6px 7px}.baseline-wikibox .leader{font-weight:700}.baseline-wikibox-foot{display:grid;grid-template-columns:1fr 1fr;background:#f8fafc;border-top:1px solid #cdd3da}.baseline-wikibox-foot div{padding:5px 7px;font-size:9px}.baseline-wikibox-foot div:last-child{text-align:right}.baseline-wikibox-note{border-top:1px solid #e4e7ec;padding:5px 7px;font-size:8px;color:var(--muted)}
.summary{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-top:0}.summary div{padding:17px 20px;border-right:1px solid var(--line)}.summary div:last-child{border:0}.summary b{display:block;font:800 21px 'Libre Franklin'}.summary span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.8px}
.rankings{margin-top:62px}.rankings h2{font:800 30px 'Libre Franklin';margin:0 0 8px}.filters{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.filters input,.filters select{border:1px solid var(--line);background:#fff;padding:9px 11px;font:12px Inter}.filters input{min-width:230px}.table-wrap{overflow:auto;border-top:3px solid var(--ink);margin-top:12px;max-height:650px}table{width:100%;border-collapse:collapse;font-size:13px}thead{position:sticky;top:0;background:#fff;z-index:1}th{text-align:left;font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:.8px;border-bottom:1px solid var(--ink);padding:13px 10px;cursor:pointer}td{border-bottom:1px solid var(--line);padding:11px 10px}td.num{text-align:right;font-variant-numeric:tabular-nums}.cand{font-weight:700}.party-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px}.party-dot.D{background:var(--blue)}.party-dot.R{background:var(--red)}
.rankings tbody tr{cursor:pointer}.rankings tbody tr:hover,.rankings tbody tr:focus{background:#f2f6fa;outline:2px solid var(--blue);outline-offset:-2px}.tier-badge{display:inline-block;margin-left:6px;padding:3px 5px;border:1px solid #aeb7c2;background:#f8fafc;font:700 8px 'Libre Franklin';text-transform:uppercase;letter-spacing:.4px}.tier-badge.sensitivity{background:#fff4dd;border-color:#e2b85b;color:#714b00}.quality-grid,.context-grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);margin-top:12px}.quality-grid div,.context-grid div{background:#fff;padding:8px}.quality-grid span,.context-grid span{display:block;color:var(--muted);font-size:8px;text-transform:uppercase;letter-spacing:.5px}.quality-grid b,.context-grid b{display:block;margin-top:3px;font-size:10px}.validation,.attribution,.downloads{margin-top:62px;border-top:4px solid var(--ink);padding-top:20px}.validation h2,.attribution h2,.downloads h2{font:800 30px 'Libre Franklin';margin:0 0 7px}.section-head{display:flex;justify-content:space-between;gap:20px;align-items:start}.section-head p,.downloads p{color:var(--muted);font-size:12px;max-width:720px}.warning-chip{padding:7px 9px;background:#fff0f0;border:1px solid #e5aaaa;color:#8b1f1f;font:700 9px 'Libre Franklin';text-transform:uppercase}.validation-grid{display:grid;grid-template-columns:1.6fr .8fr;gap:24px;margin-top:20px}.validation h3{font:700 14px 'Libre Franklin'}.table-wrap.compact{max-height:none;margin-top:8px}.compact th,.compact td{padding:8px;font-size:10px}.risk-row{background:#fff0f0}.validation details{margin-top:20px}.validation summary{cursor:pointer;font-weight:700}.benchmark{max-width:430px}.validation-note{padding:12px 14px;border-left:4px solid #b42318;background:#fff7f6;font-size:12px}.source-ledger{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-top:20px}.source-ledger article{background:#fff;padding:16px}.source-ledger span{font:700 8px 'Libre Franklin';text-transform:uppercase;letter-spacing:.7px;color:var(--muted)}.source-ledger h3{font:700 13px/1.3 'Libre Franklin';margin:6px 0}.source-ledger h3 a{color:var(--ink)}.source-ledger p{font-size:10px;line-height:1.5;color:var(--muted);margin:0}.attribution-note{background:var(--soft);border-left:4px solid var(--blue);padding:12px 14px;font-size:11px;line-height:1.55}.source-credit{font-size:8px;color:var(--muted);line-height:1.4;margin-top:7px}.download-links{display:flex;flex-wrap:wrap;gap:7px}.download-links a{border:1px solid var(--line);padding:9px 11px;color:var(--ink);font:700 10px 'Libre Franklin';text-decoration:none;text-transform:uppercase}.download-links a:hover{background:var(--soft)}
.method{max-width:760px;margin:72px 0 0}.method h2{font:800 30px 'Libre Franklin';border-top:4px solid var(--ink);padding-top:18px}.method p{font:17px/1.75 Georgia,serif}.source{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:15px;margin-top:28px}
.tooltip{position:fixed;z-index:5;pointer-events:none;background:#15181c;color:#fff;padding:9px 11px;font-size:11px;box-shadow:0 4px 16px #0003;display:none}
@media(max-width:780px){.nav{display:none}.brand{font-size:27px}main{padding:44px 18px}.story-head h1{letter-spacing:-2px}.dashboard{grid-template-columns:1fr}.map-panel{border-right:0;border-bottom:1px solid var(--line);padding:22px 16px}.summary{grid-template-columns:1fr 1fr}.summary div:nth-child(2){border-right:0}.summary div:nth-child(-n+2){border-bottom:1px solid var(--line)}.explorer-top{display:block}.detail{min-height:390px}.controls{grid-template-columns:1fr}.controls button{flex:1 0 29%}.validation-grid,.quality-grid,.context-grid,.source-ledger{grid-template-columns:1fr}.section-head{display:block}}
@media(max-width:480px){.dashboard,.dashboard>*,.map-panel,.detail{min-width:0;max-width:100%}.racebox,.baseline-context,.baseline-wikibox,.decomp{min-width:0;max-width:100%}.racebox>table{width:100%;table-layout:fixed}.racebox>table th,.racebox>table td{min-width:0;white-space:normal;overflow-wrap:anywhere}.racebox>table th:first-child,.racebox>table td:first-child{width:5%}.racebox>table th:nth-child(2),.racebox>table td:nth-child(2){width:34%}.racebox .candidate-col{min-width:0}.stat span,.stat b{min-width:0;overflow-wrap:anywhere}}
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
    return (template.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
            .replace("__ELIGIBLE_RACES__", str(eligible_races))
            .replace("__CYCLE_COUNT__", str(cycle_count))
            .replace("__VALIDATION_PANEL__", build_validation_panel_v6())
            .replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
            .replace("background:linear-gradient(90deg,#d34b45,#e8a19d,#f2f1ed,#9bbcd4,#3d77a8)",
                     "background:linear-gradient(90deg,#d34b45 0%,#f2f1ed 50%,#3d77a8 100%)")
            .replace("Build updated August 16, 2026", "Build updated August 17, 2026")
            .replace("Spending ${x.financeComplete?'complete':'incomplete'} · FTM ${x.ftmFinanceComplete?'complete':'incomplete'}",
                     "Canonical fundraising ${x.ftmFinanceComplete?'complete':'incomplete'} · DIME/FCPA source priority"))


def build_methodology_page(eligible_races):
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Methodology for Jackson Hannan's Alabama Candidate Margin Overperformance model"><title>CMO methodology · Jackson Hannan</title><style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Libre+Franklin:wght@600;700;800&display=swap');
:root{--ink:#101828;--muted:#667085;--line:#e4e7ec;--soft:#f8fafc;--blue:#2878b5;--navy:#14253d}*{box-sizing:border-box}body{margin:0;color:var(--ink);font-family:Inter,Arial,sans-serif}header{background:var(--navy);color:#fff}.mast{max-width:1180px;margin:auto;padding:20px 28px;display:flex;align-items:center;justify-content:space-between;gap:22px}.brand{font:800 27px/1 'Libre Franklin';letter-spacing:-1px}.tag{margin-top:7px;color:#b9c5d4;font-size:10px;text-transform:uppercase;letter-spacing:1.5px}.nav{display:flex;flex-wrap:wrap;gap:20px}.nav a{color:#cbd5e1;text-decoration:none;font:600 12px 'Libre Franklin'}.nav a[aria-current=page],.nav a:hover{color:#fff}.shell{max-width:1040px;margin:auto;padding:52px 28px 90px}.hero{max-width:850px;margin-bottom:44px}.kicker{font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:1.3px;color:var(--blue)}h1{font:800 clamp(42px,7vw,76px)/.98 'Libre Franklin';letter-spacing:-3px;margin:10px 0 18px}.dek{font:21px/1.55 Georgia,serif;color:#344054}.chips{display:flex;flex-wrap:wrap;gap:8px}.chip{background:var(--soft);border:1px solid var(--line);padding:8px 11px;font-size:11px}.grid{display:grid;grid-template-columns:220px minmax(0,1fr);gap:50px;align-items:start}.toc{position:sticky;top:24px;border-top:3px solid var(--ink);padding-top:13px}.toc b{display:block;margin-bottom:9px;font-size:11px;text-transform:uppercase;letter-spacing:1px}.toc a{display:block;color:var(--muted);text-decoration:none;padding:5px 0;font-size:13px}.copy section{border-top:1px solid var(--line);padding:28px 0}.copy section:first-child{border-top:3px solid var(--ink)}h2{font:800 25px 'Libre Franklin';margin:0 0 13px}.copy p,.copy li{font:17px/1.72 Georgia,serif}.copy li+li{margin-top:7px}.formula{padding:16px 18px;border-left:4px solid var(--blue);background:var(--soft);font:14px/1.6 Consolas,monospace;margin:18px 0}.callout{background:var(--soft);border:1px solid var(--line);padding:17px 19px;margin:18px 0}.callout b{display:block;margin-bottom:5px}.links{display:flex;flex-wrap:wrap;gap:8px}.links a{border:1px solid var(--line);padding:9px 11px;color:var(--ink);font:700 10px 'Libre Franklin';text-decoration:none;text-transform:uppercase;letter-spacing:.5px}.links a:hover{background:var(--soft)}.source-ledger{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line)}.source-ledger article{background:#fff;padding:14px}.source-ledger span{font:700 8px 'Libre Franklin';text-transform:uppercase;color:var(--muted)}.source-ledger h3{font:700 13px 'Libre Franklin';margin:5px 0}.source-ledger h3 a{color:var(--ink)}.source-ledger p{font:12px/1.5 Inter,sans-serif;margin:0;color:var(--muted)}.attribution-note{background:var(--soft);border-left:4px solid var(--blue);padding:12px 14px;font:12px/1.5 Inter,sans-serif}footer{background:var(--navy);color:#fff;padding:28px max(28px,calc((100vw - 984px)/2));font-size:12px}footer a{color:#cbd5e1}@media(max-width:760px){.mast{align-items:flex-start;flex-direction:column;padding:20px 18px}.shell{padding:38px 18px 65px}.grid,.source-ledger{grid-template-columns:1fr}.toc{position:static}h1{letter-spacing:-2px}.nav{gap:12px}}
</style></head><body><header><div class="mast"><div><div class="brand">Jackson Hannan</div><div class="tag">Alabama legislative models</div></div><nav class="nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html">CMO</a><a href="ideology-performance.html">Issues & caucuses</a><a href="methodology.html">Forecast methodology</a><a href="cmo-methodology.html" aria-current="page">CMO methodology</a><a href="https://github.com/JacksonAHannan">GitHub</a></nav></div></header>
<main class="shell"><div class="hero"><div class="kicker">Model documentation</div><h1>Candidate Margin Overperformance</h1><p class="dek">A retrospective index of how far an Alabama legislative candidate ran ahead of or behind a cross-fitted expectation for the district and election.</p><div class="chips"><span class="chip"><b>8 cycles:</b> 1994–2022</span><span class="chip"><b>__ELIGIBLE_RACES__</b> contested D–R races</span><span class="chip"><b>Unit:</b> margin percentage points</span></div></div>
<div class="grid"><aside class="toc"><b>On this page</b><a href="#estimand">What CMO measures</a><a href="#data">Data and eligibility</a><a href="#baseline">Expected baseline</a><a href="#crossfit">Cross-fitting</a><a href="#versions">Three specifications</a><a href="#validation">Validation</a><a href="#limits">Limitations</a><a href="#forecast">Forecast use</a><a href="#sources">Sources and credit</a></aside><article class="copy">
<section id="estimand"><h2>1. What CMO measures</h2><p>CMO is candidate margin overperformance, not literal wins above replacement and not a causal estimate of candidate quality. It compares the candidate’s observed two-party margin with a statistical expectation based on the political and demographic context of the race.</p><div class="formula">Democratic CMO = observed Democratic two-party margin − cross-fitted expected Democratic margin<br>Republican CMO = − Democratic CMO</div><p>A Democratic candidate who was expected to lose by 20 points but lost by 10 has a CMO of +10. The Republican in that race receives −10. Scores are therefore zero-sum within a race and cannot separately identify both candidates’ contributions.</p></section>
<section id="data"><h2>2. Data and eligibility</h2><p>The index covers all eight Alabama legislative general-election cycles from 1994 through 2022. The 1998–2022 series is the core historical tier; 1994 is retained and visibly flagged as a sensitivity tier because its presidential and split-precinct allocations rely more heavily on fallbacks. A race is scored only when both major parties received votes.</p><ul><li>Official and reconciled election returns provide candidates, parties, and votes.</li><li>Same-cycle statewide offices and preceding presidential returns provide political context.</li><li>Decennial Census and ACS sources provide era-appropriate demographics.</li><li>Incumbency uses positive evidence; ambiguous dual matches are neutralized and flagged.</li><li>Finance is an optional sensitivity layer rather than a requirement for headline CMO.</li></ul></section>
<section id="baseline"><h2>3. The expected baseline</h2><p>The headline historical Fundamentals+ expectation begins with the same-cycle statewide ticket margin measured inside each legislative district. It then applies 20% of a ridge adjustment, capped at four points, using demographics, regional context where available, finance and its availability, incumbency and open-seat status, chamber, presidential context, and available prior-candidate indicators. This avoids counting district partisanship twice when statewide and presidential voting diverge.</p><div class="callout"><b>Why a regularized model?</b> Ridge regression and the 20% shrinkage limit unstable adjustments in a small, correlated dataset. This retrospective CMO baseline is distinct from the prospective 2026 forecast, which begins with presidential partisanship and a projected environment.</div></section>
<section id="crossfit"><h2>4. Cycle-held-out scoring</h2><p>The published headline score withholds the candidate's entire election cycle. Every race is therefore predicted by a model that did not train on any result from that election year.</p><p>This is retrospective validation rather than a historical forecast: the 1994 model, for example, may train on later cycles. The displayed stability band measures disagreement between cycle-held-out and ordinary random-fold scores; it is not a confidence interval.</p></section>
<section id="versions"><h2>5. Three CMO specifications</h2><p><b>Total CMO</b>, the headline measure, uses Fundamentals+ and therefore conditions partly on observed finance. <b>Resource-adjusted CMO</b> and <b>Fundraising-adjusted CMO</b> remain legacy sensitivity specifications for comparison.</p><p>None supports a causal claim. Fundraising is endogenous, finance coverage is incomplete, and money raised is not the same as money efficiently deployed. Numerical prior-CMO values are unavailable in the current historical training panel, so only prior-appearance and prior-winner indicators contribute candidate-history information.</p></section>
<section id="validation"><h2>6. Validation and interpretation</h2><p>Validation emphasizes forward and grouped tests rather than random folds alone. The model reports random out-of-fold error, leave-one-cycle-out error, source coverage, exact vote-total checks, score symmetry, and sensitivity to specifications. Historical era shifts—especially 2014—make cycle holdouts materially harder than within-era prediction.</p><p>Large positive scores mean “far ahead of this model’s expectation,” not “personally caused this many points.” Rankings are most useful alongside the district result, expected baseline, top-of-ticket context, stability band, and source notes.</p></section>
<section id="limits"><h2>7. Important limitations</h2><ul><li>The index contains eight cycles and __ELIGIBLE_RACES__ eligible races, but only a small number of independent election environments.</li><li>Scores are conditional on contested Democratic-versus-Republican races and do not represent all candidates or legislators.</li><li>The zero-sum construction attributes a race residual symmetrically to the two candidates.</li><li>Election eras, district boundaries, turnout, and source quality change across cycles; 1994 is a sensitivity tier.</li><li>Same-cycle context makes the historical index descriptive; it cannot be used unchanged before Election Day.</li><li>The stability band is a model-sensitivity diagnostic, not calibrated predictive uncertainty.</li></ul></section>
<section id="forecast"><h2>8. Relationship to the 2026 forecast</h2><p>The forecast and CMO are separate products. CMO describes historical overperformance. CMO v4 is not inserted directly into the headline forecast because repeat-candidate persistence is weak in the current sample.</p><div class="links"><a href="cmo.html">Explore CMO</a><a href="index.html">View forecast</a><a href="methodology.html#candidate">Forecast candidate layer</a><a href="data/cmo_v4_candidates.csv">Candidate data</a></div></section>
__ATTRIBUTION_PANEL__
</article></div></main><footer>Model and analysis by Jackson Hannan · <a href="https://github.com/JacksonAHannan">GitHub</a> · <a href="https://substack.com/@jacksonhannan">Substack</a></footer></body></html>'''
    return (page.replace("__ELIGIBLE_RACES__", str(eligible_races))
            .replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
            .replace("Finance is an optional sensitivity layer rather than a requirement for headline CMO.",
                     "Headline Fundamentals+ uses canonical fundraising where available plus an explicit availability flag. Coverage is 352 of 509 races (69.2%); missing records remain unknown."))


def modernize_v4_copy(rendered):
    replacements = {
        "Direct ticket comparison": "WAR-style residual",
        "Direct ticket CMO": "WAR-style CMO",
        "Direct CMO": "WAR-style CMO",
        "direct-CMO": "WAR-style CMO",
        "State-ticket CMO": "Raw ticket gap",
        "Federal CMO": "Lag adjustment",
        "Presidential CMO": "Incumbency adjustment",
        "State ticket": "Raw ticket gap",
        "Federal ticket": "Lag adjustment",
        "Band width": "Structural gap",
        "Build updated August 21, 2026 from CMO methodology v3.": "Build updated August 21, 2026 from CMO methodology v4.",
    }
    for old, new in replacements.items():
        rendered = rendered.replace(old, new)
    rendered = rendered.replace(
        "The headline score is the legislative margin minus a source-aware same-district ticket baseline. Demographics, incumbency, finance, ideology, and candidate history do not alter the election-level score.",
        "The headline score is the observed legislative-versus-ticket gap minus the gap predicted from incumbency, downballot lag, demographics, and campaign effort.")
    rendered = rendered.replace(
        "Candidate Margin Overperformance compares a legislative result with same-district political conditions measured from the ticket. The main score is directly auditable from the actual legislative margin and selected baseline.",
        "This model applies Split Ticket's WAR structure to Alabama legislative elections: measure the raw legislative-versus-ticket gap, predict its structural portion, and score the residual.")
    rendered = rendered.replace(
        "Positive values indicate performance ahead of the source-aware ticket baseline.",
        "Positive values indicate performance ahead of the model's structural expectation.")
    rendered = rendered.replace("<b>4</b><span>Comparison views</span>", "<b>5</b><span>Model components</span>")
    rendered = rendered.replace(
        "WAR-style CMO is the headline comparison. Federal, presidential, and career-pooled columns are labeled alternatives rather than replacements for the observed score.",
        "The table separates the observed ticket gap, modeled structural expectation, and remaining WAR-style residual.")
    rendered = rendered.replace(
        "The source-aware baseline combines same-cycle Governor and Attorney General returns by vote weight. From 2018 onward, usable same-cycle federal results receive a declared 30 percent weight; previous presidential results remain a fallback.",
        "The preferred baseline is the same-cycle federal ticket inside the district. When it is unavailable, the model uses the documented same-cycle state-ticket fallback.")
    rendered = rendered.replace(
        "WAR-style CMO is simply the candidate-oriented legislative margin minus that baseline. Regression expectations are audit-only because out-of-era extrapolation can absorb or reverse the performance the measure is intended to describe. The displayed band reflects disagreement among ticket baselines and source quality; it is not a 95 percent confidence interval.",
        "The structural model uses symmetric incumbency, era-specific downballot lag, limited demographics, and capped campaign effort. WAR-style CMO is the observed ticket gap minus that prediction; ideology is excluded so it can be tested afterward.")
    rendered = rendered.replace("Overperformance versus the state ticket", "Observed legislative-versus-ticket gap")
    rendered = rendered.replace("Overperformance versus the same-cycle federal ticket", "Modeled downballot-lag adjustment")
    rendered = rendered.replace("Baseline/data-quality band", "WAR-style CMO")
    rendered = rendered.replace("Federal-ticket CMO", "Lagged-partisanship adjustment")
    rendered = rendered.replace("Presidential-baseline CMO", "Incumbency adjustment")
    rendered = rendered.replace("actual versus ticket baseline", "actual versus structural expectation")
    rendered = rendered.replace('<th colspan="2" class="group-head">Ticket baseline</th>', '<th colspan="2" class="group-head">Structural expectation</th>')
    rendered = rendered.replace('<span>Ticket baseline margin</span>', '<span>Structural expected margin</span>')
    rendered = rendered.replace('<span class="badge ${stable?\'\':\'warn\'}">${stable?\'Narrower band\':\'Wider band\'}</span>', '')
    rendered = rendered.replace('<span class="badge ${x.signConsistent?\'\':\'warn\'}">${x.signConsistent?\'Ticket alternatives agree\':\'Ticket direction differs\'}</span>', '')
    rendered = rendered.replace('<div class="stat"><span>WAR-style CMO</span><b>${fmt(x.low)} to ${fmt(x.high)}</b></div>', '')
    rendered = rendered.replace("Direct comparison", "WAR decomposition")
    rendered = rendered.replace("Source-aware baseline margin", "Expected legislative margin")
    rendered = rendered.replace(
        "the source-aware same-district ticket baseline by about <b>${Math.abs(x.war).toFixed(1)} points</b>. Regression context expectations are not used in this score.",
        "the model's structural expectation by about <b>${Math.abs(x.war).toFixed(1)} points</b>. The raw ticket gap is ${fmt(x.within)} and the predicted structural gap is ${fmt(x.predictedStructuralGap)}.")
    return rendered


def modernize_methodology_v4(rendered):
    body = '''<article class="copy">
<section id="estimand"><h2>1. What CMO measures</h2><p>CMO is a state-legislative analogue to Split Ticket's WAR. It begins with the observed two-party margin gap between a legislative race and the same district's ticket baseline, predicts the portion normally associated with structural conditions, and treats the remainder as candidate margin overperformance.</p><div class="formula">Raw ticket gap = legislative margin − ticket margin<br>WAR-style CMO = raw ticket gap − predicted structural gap</div><p>Republican values reverse the Democratic race residual, so every race is zero-sum. The residual is retrospective and is not a causal estimate of either candidate's personal contribution.</p></section>
<section id="data"><h2>2. Data and eligibility</h2><p>The model covers contested Democratic-versus-Republican Alabama House and Senate races from 1994 through 2022. Official and reconciled returns provide legislative, federal, statewide, and presidential results. Census and ACS sources supply era-appropriate demographics; finance enters only through a capped campaign-effort term.</p></section>
<section id="baseline"><h2>3. Ticket baseline</h2><p>The preferred comparison is the same-cycle U.S. House and U.S. Senate result measured within the legislative district. It captures the national political environment facing the legislative candidates. Eighty-one races without a usable federal comparison use a documented same-cycle state-ticket fallback; 428 use the federal-primary baseline.</p></section>
<section id="models"><h2>4. Structural expectation</h2><p>A regularized ridge model predicts the normal legislative-ticket gap. Major terms are symmetric party-oriented incumbency and era-specific downballot lag—the difference between same-cycle federal voting and preceding presidential voting. Prior presidential margin and available presidential swing provide additional political context.</p><p>Nonwhite share and white-college share are minor demographic terms capped at ±3 points. Campaign effort uses spending, fundraising, or resource ratios according to availability and is capped at ±2 points. Ideology and cycle fixed effects are excluded: ideology is an outcome to test afterward, while cycle indicators would absorb statewide Conservadem overperformance.</p></section>
<section id="validation"><h2>5. Model selection and checks</h2><p>Ridge strength is selected with leave-one-cycle-out testing. Published checks cover vote arithmetic, ticket-source selection, component reconciliation, caps, party symmetry, candidate orientation, and exact zero-sum scores.</p></section>
<section id="identity"><h2>6. Candidate and career summaries</h2><p>Election-level CMO is the primary product. Candidate histories use normalized full-name identities; unresolved surname-only records remain race-specific. A separately labeled partial-pooled career summary shrinks repeat candidates toward zero and never replaces the candidate-cycle result.</p></section>
<section id="limits"><h2>7. Limitations</h2><ul><li>Eight cycles provide many races but few independent statewide environments.</li><li>The effort cap reaches its ±2-point bound often, signaling that finance measurement remains coarse.</li><li>Repeat-candidate WAR persistence is near zero in the current sample, so CMO should not be treated as a durable talent rating or forecast signal.</li><li>Fallback ticket sources and historical geographic allocation add uncertainty that is documented row by row.</li><li>Zero-sum residuals cannot separately identify the contributions of opposing candidates.</li></ul></section>
<section id="reproducibility"><h2>8. Reproducibility</h2><p>The versioned build publishes race rows, candidate rows, component decomposition, coefficients, cycle diagnostics, construct checks, and a provenance manifest.</p><div class="links"><a href="cmo.html">Explore CMO</a><a href="data/cmo_v4_candidates.csv">Candidate data</a><a href="data/cmo_v4_races.csv">Race data</a><a href="data/cmo_v4_components.csv">Components</a><a href="data/cmo_v4_provenance.csv">Run manifest</a></div></section>
__ATTRIBUTION_PANEL__
</article>'''.replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
    start = rendered.index('<article class="copy">')
    end = rendered.index('</article></div></main>')
    rendered = rendered[:start] + body + rendered[end + len('</article>'):]
    rendered = rendered.replace("A retrospective index of how far an Alabama legislative candidate ran ahead of or behind a cross-fitted expectation for the district and election.", "A retrospective WAR-style residual for Alabama legislative candidates, measured against same-district ticket voting and a regularized structural expectation.")
    return rendered


def modernize_v5_copy(rendered):
    """Replace legacy residual language with the validated dual-estimand contract."""
    rendered = rendered.replace(
        "How far Alabama legislative candidates ran ahead of or behind the model’s district-level expectation from 1994 through 2022.",
        "Observed ticket overperformance and partial-pooled candidate quality in Alabama legislative elections, 1994–2022.")
    rendered = rendered.replace("<b>3</b><span>Map views</span>", "<b>4</b><span>Map views</span>")
    rendered = rendered.replace(
        "Candidate Margin Overperformance compares a legislative result with same-district political conditions measured from the ticket. The main score is directly auditable from the actual legislative margin and selected baseline.",
        "CMO is the observed candidate-oriented difference between the legislative margin and a source-aware same-district ticket margin. Candidate Quality is a separate partial-pooled estimate of the component that persists across appearances.")
    rendered = rendered.replace(
        "<strong>Direct ticket CMO is the headline measure.</strong> Positive values indicate performance ahead of the source-aware ticket baseline. Scores are two-party margin percentage points, are zero-sum within a race, and are not causal estimates of individual candidate quality.",
        "<strong>CMO is the headline descriptive measure.</strong> It is not adjusted away for incumbency, fundraising, or demographics. Candidate Quality is labeled separately with uncertainty and does not convert a one-off race into a confident personal rating.")
    rendered = rendered.replace(
        '<button data-map-mode="absolute" class="active">CMO</button>',
        '<button data-map-mode="absolute" class="active">CMO</button><button data-map-mode="quality">Candidate quality differential</button>')
    rendered = rendered.replace(
        "Direct CMO is the headline comparison. Federal, presidential, and career-pooled columns are labeled alternatives rather than replacements for the observed score.",
        "CMO is the observed ticket comparison. Candidate Quality is a separate, shrinkage-based estimate; its interval and evidence status are shown rather than hidden.")
    old_head = '<th data-sort="war">Direct CMO ↕</th><th data-sort="within">State-ticket CMO</th><th data-sort="raw">Federal CMO</th><th data-sort="predictiveResidual">Presidential CMO</th><th data-sort="partialPooled">Career pooled</th><th data-sort="specificationRange">Band width</th>'
    new_head = '<th data-sort="war">CMO ↕</th><th data-sort="partialPooled">Candidate quality</th><th data-sort="qualityLow">Quality interval</th><th data-sort="within">Vs. state ticket</th><th data-sort="raw">Vs. federal ticket</th><th data-sort="predictiveResidual">Vs. previous president</th>'
    rendered = rendered.replace(old_head, new_head)
    detail_js = r'''function detail(x){const box=$('#detail');if(!x){box.innerHTML='<div class="detail-empty">Select a district or candidate row to inspect the race.</div>';return}const history=allCandidates().filter(c=>c.personId&&c.personId===x.personId).sort((a,b)=>a.cycle-b.cycle),historyHtml=history.length>1?`<div class="decomp"><div class="decomp-title">Resolved candidate history</div>${history.map(c=>`<div class="stat"><span>${c.cycle} ${c.chamber} ${c.district}</span><b>CMO ${fmt(c.war)}</b></div>`).join('')}</div>`:'';box.innerHTML=`<div class="candidate-headline"><h3>${esc(x.candidate)}</h3><div class="party ${x.party}">${x.party==='D'?'Democratic':'Republican'} • District ${x.district}${x.incumbent?' • Incumbent':''}</div><div class="war-number">${fmt(x.war)}</div><div class="war-label">CMO • ${x.percentile.toFixed(0)}th percentile</div><div class="distribution"><i style="left:${x.percentile}%"></i><div class="distribution-label"><span>Lowest</span><span>Median</span><span>Highest</span></div></div></div>${raceBox(x)}<div class="decomp"><div class="decomp-title">Candidate Quality Index</div><div class="stat"><span>Partial-pooled estimate</span><b>${fmt(x.partialPooled)}</b></div><div class="stat"><span>Uncertainty interval</span><b>${fmt(x.qualityLow)} to ${fmt(x.qualityHigh)}</b></div><div class="stat"><span>Evidence status</span><b>${esc(x.qualityStatus)} · ${(100*x.attributionReliability).toFixed(0)}% reliability · ${x.appearances} appearance${x.appearances===1?'':'s'}</b></div><div class="stat"><span>Intrinsic sensitivity</span><b>${fmt(x.intrinsicQuality)}</b></div><div class="stat"><span>Pre-election estimate</span><b>${fmtMaybe(x.preElectionQuality)} · ${x.preElectionAppearances} prior appearance${x.preElectionAppearances===1?'':'s'}</b></div></div><div class="decomp"><div class="decomp-title">Alternative observed comparisons</div><div class="stat"><span>State ticket</span><b>${fmtMaybe(x.within)}</b></div><div class="stat"><span>Same-cycle federal ticket</span><b>${fmtMaybe(x.raw)}</b></div><div class="stat"><span>Previous presidential ticket</span><b>${fmtMaybe(x.predictiveResidual)}</b></div></div><div class="decomp"><div class="decomp-title">Source quality</div><div class="quality-grid"><div><span>Selected baseline</span><b>${esc(x.baselineMethod||'Unavailable')}</b></div><div><span>Identity linkage</span><b>${esc(x.identityStatus)}</b></div><div><span>Demographics</span><b>${esc(x.demographicsMethod||'Unavailable')}${x.demographicReferenceYear?' · '+Math.round(x.demographicReferenceYear):''}</b></div><div><span>Previous president</span><b>${fmtMaybe(x.priorPres)}</b></div><div><span>Votes</span><b>${x.votes.toLocaleString()}</b></div></div></div>${historyHtml}<div class="explain">${x.war>=0?'This candidate ran ahead of':'This candidate ran behind'} the selected same-district ticket by about <b>${Math.abs(x.war).toFixed(1)} margin points</b>. Candidate Quality is a separate estimate and is <b>${esc(x.qualityStatus)}</b> given the available repeat and opponent network.</div>`}'''
    rendered = re.sub(r"function detail\(x\)\{.*?\}\nfunction renderMap", detail_js + "\nfunction renderMap", rendered, count=1, flags=re.S)
    rows_js = r'''function renderRows(){const d=DATA[active],scope=$('#scope-filter').value,q=$('#candidate-search').value.toLowerCase(),party=$('#party-filter').value,outcome=$('#outcome-filter').value,source=scope==='all'?allCandidates():d.candidates.map(x=>({...x,section:active,cycle:d.cycle,chamber:d.chamber})),rows=source.filter(x=>(party==='all'||x.party===party)&&(outcome==='all'||(outcome==='winner'&&x.winner)||(outcome==='incumbent'&&x.incumbent))&&(!q||x.candidate.toLowerCase().includes(q)||String(x.district)===q||String(x.cycle)===q||`${x.chamber} ${x.district}`.includes(q))).sort((a,b)=>{let A=a[sortKey],B=b[sortKey];return(typeof A==='string'?A.localeCompare(B):(A??-9999)-(B??-9999))*sortDir});$('#rows').innerHTML=rows.map(x=>`<tr tabindex="0" data-section="${x.section}" data-district="${x.district}" data-party="${x.party}"><td>${x.cycle} ${x.chamber==='house'?'H':'S'}</td><td>${x.district}</td><td class="cand"><i class="party-dot ${x.party}"></i>${esc(x.candidate)}${x.winner?' <small>✓</small>':''}${x.contestTier==='nominal'?' <span class="tier-badge sensitivity">Nominal</span>':''}</td><td class="num"><b>${fmt(x.war)}</b></td><td class="num">${fmt(x.partialPooled)}<br><small>${esc(x.qualityStatus)}</small></td><td class="num">${fmt(x.qualityLow)} to ${fmt(x.qualityHigh)}</td><td class="num">${fmtMaybe(x.within)}</td><td class="num">${fmtMaybe(x.raw)}</td><td class="num">${fmtMaybe(x.predictiveResidual)}</td><td class="num">${fmt(x.cycleTopTicket)}</td><td class="num">${fmt(x.margin)}</td><td class="num">${x.votes.toLocaleString()}</td></tr>`).join('');document.querySelectorAll('#rows tr').forEach(row=>{row.onclick=()=>selectCandidate(row.dataset.section,row.dataset.district,row.dataset.party);row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.onclick()}}})}'''
    rendered = re.sub(r"function renderRows\(\)\{.*?\}\nfunction render\(\)", rows_js + "\nfunction render()", rendered, count=1, flags=re.S)
    if "function clearSelection()" not in rendered:
        rendered = rendered.replace(
            "document.querySelectorAll('th[data-sort]')",
            "function clearSelection(){selected=null;selectedParty=null;detail(null);renderMap()}\n"
            "document.querySelectorAll('th[data-sort]')", 1)
    rendered = rendered.replace(
        "function render(){",
        "function clearSelection(){selected=null;selectedParty=null;detail(null);renderMap()}\nfunction render(){", 1)
    rendered = re.sub(r'<section class="downloads">.*?</section>', '<section class="downloads"><h2>Data and provenance</h2><p>CMO methodology v5 publishes observed race and candidate scores, candidate-quality estimates, validation tournaments, named cases, and provenance.</p><div class="download-links"><a href="data/cmo_v5_candidates.csv">Candidate output</a><a href="data/cmo_v5_races.csv">Race output</a><a href="data/cmo_v5_candidate_effects.csv">Candidate quality</a><a href="data/cmo_v5_model_tournament.csv">Model tournament</a><a href="data/cmo_v5_case_studies.csv">Case studies</a><a href="data/cmo_v5_provenance.csv">Run manifest</a><a href="cmo-methodology.html">Methodology</a></div></section>', rendered, count=1, flags=re.S)
    rendered = re.sub(r'<section class="method">.*?</section></main>', '<section class="method"><h2>How to read the measures</h2><p>CMO reports what happened relative to the selected same-district ticket. It deliberately gives Mike Curtis credit for his observed ticket overperformance rather than subtracting that performance as an expected structural effect.</p><p>Candidate Quality asks a narrower second question: how much of cycle-centered CMO appears repeatable across a candidate’s observed race and opponent network? It is shrunk toward zero and must be read with its interval and evidence status.</p><p><a href="cmo-methodology.html">Read the full CMO methodology</a> or <a href="index.html">view the 2026 forecast</a>.</p><div class="source">Model outputs: <code>cmo_v5_candidates.csv</code> and <code>cmo_v5_races.csv</code>.</div></section></main>', rendered, count=1, flags=re.S)
    return rendered


def modernize_methodology_v5(rendered):
    body = '''<article class="copy">
<section id="estimand"><h2>1. Two measures</h2><p><b>Candidate Margin Overperformance (CMO)</b> is the observed candidate-oriented legislative margin minus the selected same-district ticket margin.</p><div class="formula">Democratic race CMO = legislative Democratic margin − selected ticket Democratic margin<br>Candidate CMO = Democratic race CMO for D; its negative for R</div><p>CMO is the headline descriptive measure. It is not residualized for incumbency, fundraising, demographics, or candidate history.</p><p><b>Candidate Quality Index (CQI)</b> is separate. It estimates a repeatable candidate component after centering CMO within cycle, chamber, and ticket-source groups, then partially pooling candidate effects across the candidate-opponent network.</p></section>
<section id="data"><h2>2. Coverage</h2><p>The model covers 509 contested Democratic–Republican Alabama House and Senate races from 1994 through 2022. It publishes 1,018 candidate-cycle rows. Nominal contests remain visible but are excluded from replacement-level fitting.</p></section>
<section id="baseline"><h2>3. Ticket selection</h2><p>The preferred baseline is the same-cycle federal ticket measured inside the legislative district. When that comparison is unavailable, the model uses a documented same-cycle state-ticket fallback. State, federal, and previous-presidential comparisons are published separately so baseline sensitivity remains visible.</p></section>
<section id="quality"><h2>4. Candidate Quality estimation</h2><p>Replacement levels are estimated separately by cycle, chamber, and ticket source. The structural tournament compares cycle centering with models using only predetermined presidential history and demographics. Current same-cycle federal margin is never reused as a lag predictor.</p><p>The selected race residual is modeled as <code>q(D candidate) − q(R candidate)</code> with ridge partial pooling. The penalty is chosen using forward-cycle tests among races containing at least one previously observed candidate. Full-panel CQI is retrospective. A separately labeled pre-election estimate uses prior cycles only.</p></section>
<section id="incumbency"><h2>5. Incumbency and mediation</h2><p>Total CQI retains officeholding as part of a candidate’s observed electoral value. An intrinsic sensitivity subtracts a prespecified three-point generic incumbency effect before fitting. Fundraising is not subtracted: it may be a mechanism through which candidate strength operates, and current coverage is not sufficient to identify a universal causal adjustment.</p></section>
<section id="uncertainty"><h2>6. Identification and uncertainty</h2><p>CQI includes a ridge uncertainty interval, appearances, reliability, and an evidence status. A disconnected race containing two one-time candidates identifies only their difference. Those candidates are always labeled <b>uncertain</b> and marked <code>pair_differential_only</code>; the model does not pretend to know which candidate supplied the advantage.</p><p>An interval crossing zero means uncertain evidence, not average candidate quality.</p></section>
<section id="validation"><h2>7. Validation</h2><p>Validation requires exact direct-score arithmetic, zero-sum candidate orientation, deterministic replacement levels, no same-cycle leakage in lag terms, forward-only pre-election estimates, repeat-candidate model selection, party-symmetry checks, conservative singleton labeling, and hashed operative inputs.</p></section>
<section id="limits"><h2>8. Limitations</h2><ul><li>Many candidates appear once, so CQI is usually uncertain.</li><li>A candidate effect can still combine personal strength, opponent weakness, and unmeasured local conditions.</li><li>Only eight election cycles are observed, and Alabama’s party system changed substantially over the period.</li><li>Fallback ticket sources and historical geographic allocation create row-specific comparability limits.</li><li>CMO describes observed elections; it is not itself a pre-election win probability.</li></ul></section>
<section id="reproducibility"><h2>9. Reproducibility</h2><p>The build publishes race rows, candidate rows, candidate effects, tournaments, case studies, transition and symmetry diagnostics, and a provenance manifest.</p><div class="links"><a href="cmo.html">Explore CMO</a><a href="data/cmo_v5_candidates.csv">Candidate data</a><a href="data/cmo_v5_races.csv">Race data</a><a href="data/cmo_v5_candidate_effects.csv">Candidate quality</a><a href="data/cmo_v5_provenance.csv">Run manifest</a></div></section>
__ATTRIBUTION_PANEL__
</article>'''.replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
    start = rendered.index('<article class="copy">')
    end = rendered.index('</article></div></main>')
    rendered = rendered[:start] + body + rendered[end + len('</article>'):]
    rendered = re.sub(r'<aside class="toc">.*?</aside>', '<aside class="toc"><b>On this page</b><a href="#estimand">Two measures</a><a href="#data">Coverage</a><a href="#baseline">Ticket selection</a><a href="#quality">Candidate Quality</a><a href="#incumbency">Incumbency</a><a href="#uncertainty">Identification</a><a href="#validation">Validation</a><a href="#limits">Limitations</a><a href="#reproducibility">Reproducibility</a><a href="#sources">Sources</a></aside>', rendered, count=1, flags=re.S)
    rendered = rendered.replace("A retrospective index of how far an Alabama legislative candidate ran ahead of or behind a cross-fitted expectation for the district and election.", "Documentation for observed CMO and partial-pooled Candidate Quality in Alabama legislative elections.")
    rendered = rendered.replace("Documentation for the WAR-style ticket residual, structural model, diagnostics, and reproducible CMO v4 build.", "Documentation for observed CMO and partial-pooled Candidate Quality in Alabama legislative elections.")
    return rendered


def modernize_v6_copy(rendered):
    """Promote v6 labels and fields without changing the Direct CMO estimand."""
    rendered = modernize_v5_copy(rendered)
    rendered = rendered.replace(
        '<input id="candidate-search"',
        '<input id="candidate-search" aria-label="Search candidates or districts"',
        1,
    )
    rendered = rendered.replace(
        '<select id="scope-filter">',
        '<select id="scope-filter" aria-label="Candidate result scope">',
        1,
    )
    rendered = rendered.replace(
        '<select id="party-filter">',
        '<select id="party-filter" aria-label="Candidate party">',
        1,
    )
    rendered = rendered.replace(
        '<select id="outcome-filter">',
        '<select id="outcome-filter" aria-label="Candidate outcome">',
        1,
    )
    rendered = re.sub(
        r'<div class="dek">.*?</div>',
        '<div class="dek">Observed ticket overperformance and a Southern-prior decomposition of structural lag, generic incumbency, and residual candidate quality in Alabama legislative elections, 1994–2022.</div>',
        rendered, count=1, flags=re.S)
    rendered = re.sub(
        r'<section class="intro">.*?</section>',
        '<section class="intro"><p>CMO measures how far a legislative candidate ran ahead of or behind the selected statewide or federal ticket within the same district.</p><p>The accompanying estimates use comparable Southern elections to describe how much of that result resembles ordinary down-ballot voting, incumbency, or a candidate-versus-opponent advantage. Those estimates are historical and carry explicit uncertainty.</p></section>',
        rendered, count=1, flags=re.S)
    rendered = rendered.replace(
        '<section class="explorer">',
        '<section class="measure-guide" aria-labelledby="measureGuideTitle"><h2 id="measureGuideTitle">Measures used on this page</h2><div><article><b>CMO</b><p>Observed candidate margin minus the selected same-district ticket margin.</p></article><article><b>Residual quality</b><p>CMO after the Southern historical model accounts for ordinary down-ballot structure.</p></article><article><b>Total value</b><p>Partial-pooled residual quality plus the candidate-oriented generic incumbency component.</p></article></div></section><section class="explorer">', 1)
    rendered = rendered.replace('Candidate quality differential</button>', 'Residual quality differential</button>')
    rendered = re.sub(
        r'<th data-sort="war">CMO.*?</th><th data-sort="partialPooled">.*?</th><th data-sort="qualityLow">.*?</th>',
        '<th data-sort="war">CMO ↕</th><th data-sort="partialPooled">Residual quality</th><th data-sort="totalElectoralValue">Total value</th>',
        rendered, count=1, flags=re.S)
    detail_js = r'''function detail(x){const box=$('#detail');if(!x){box.innerHTML='<div class="detail-empty">Select a district or candidate row to inspect the race.</div>';return}const history=allCandidates().filter(c=>c.personId&&c.personId===x.personId).sort((a,b)=>a.cycle-b.cycle),historyHtml=history.length>1?`<div class="decomp"><div class="decomp-title">Resolved candidate history</div>${history.map(c=>`<div class="stat"><span>${c.cycle} ${c.chamber} ${c.district}</span><b>CMO ${fmt(c.war)}</b></div>`).join('')}</div>`:'';box.innerHTML=`<div class="candidate-headline"><h3>${esc(x.candidate)}</h3><div class="party ${x.party}">${x.party==='D'?'Democratic':'Republican'} &middot; District ${x.district}${x.incumbent?' &middot; Incumbent':''}</div><div class="war-number">${fmt(x.war)}</div><div class="war-label">CMO &middot; ${x.percentile.toFixed(0)}th percentile</div><div class="distribution"><i style="left:${x.percentile}%"></i><div class="distribution-label"><span>Lowest</span><span>Median</span><span>Highest</span></div></div></div>${raceBox(x)}<div class="decomp"><div class="decomp-title">Southern-prior decomposition</div><div class="stat"><span>Historical structural expectation</span><b>${fmt(x.southernExpectedGap)}</b></div><div class="stat"><span>Race-level residual quality</span><b>${fmt(x.qualityResidual)}</b></div><div class="stat"><span>Partial-pooled residual quality</span><b>${fmt(x.partialPooled)}</b></div><div class="stat"><span>Uncertainty interval</span><b>${fmt(x.qualityLow)} to ${fmt(x.qualityHigh)}</b></div><div class="stat"><span>Evidence status</span><b>${esc(x.qualityStatus)} &middot; ${x.appearances} appearance${x.appearances===1?'':'s'}</b></div><div class="stat"><span>Generic incumbency component</span><b>${fmt(x.genericIncumbency)}</b></div><div class="stat"><span>Total electoral value</span><b>${fmt(x.totalElectoralValue)}</b></div></div><div class="decomp"><div class="decomp-title">Alternative observed comparisons</div><div class="stat"><span>State ticket</span><b>${fmtMaybe(x.within)}</b></div><div class="stat"><span>Same-cycle federal ticket</span><b>${fmtMaybe(x.raw)}</b></div><div class="stat"><span>Previous presidential ticket</span><b>${fmtMaybe(x.predictiveResidual)}</b></div></div><div class="decomp"><div class="decomp-title">Source quality</div><div class="quality-grid"><div><span>Selected baseline</span><b>${esc(x.baselineMethod||'Unavailable')}</b></div><div><span>Identity linkage</span><b>${esc(x.identityStatus)}</b></div><div><span>Demographics</span><b>${esc(x.demographicsMethod||'Unavailable')}${x.demographicReferenceYear?' &middot; '+Math.round(x.demographicReferenceYear):''}</b></div><div><span>Previous president</span><b>${fmtMaybe(x.priorPres)}</b></div><div><span>Votes</span><b>${x.votes.toLocaleString()}</b></div></div></div>${historyHtml}<div class="explain">${x.war>=0?'This candidate ran ahead of':'This candidate ran behind'} the selected same-district ticket by about <b>${Math.abs(x.war).toFixed(1)} margin points</b>. The Southern-prior fields are a historical decomposition, not a direct 2026 forecast adjustment.</div>`}'''
    detail_js = detail_js.replace("if(!x){box.innerHTML=", "if(!x){box.classList.add('is-empty');box.innerHTML=")
    detail_js = detail_js.replace(";return}const history=", ";return}box.classList.remove('is-empty');const history=")
    detail_js = detail_js.replace(
        '<div class="candidate-headline">',
        '<button class="close-detail" type="button" aria-label="Close candidate details" onclick="clearSelection()">&times;</button><div class="candidate-headline">', 1)
    detail_js = detail_js.replace(
        "historyHtml=history.length>1?`<div class=\"decomp\"><div class=\"decomp-title\">Resolved candidate history</div>${history.map(c=>`<div class=\"stat\"><span>${c.cycle} ${c.chamber} ${c.district}</span><b>CMO ${fmt(c.war)}</b></div>`).join('')}</div>`:'';box.innerHTML=",
        "historyMax=Math.max(5,...history.map(c=>Math.abs(c.war))),historyHtml=history.length>1?`<div class=\"decomp career-history\"><div class=\"decomp-title\">Candidate CMO timeline</div><p>CMO is signed to the Democratic margin. Select a race to open it.</p>${history.map(c=>`<button class=\"career-observation\" onclick=\"selectCandidate('${c.section}',${c.district},'${c.party}')\"><span>${c.cycle}<small>${c.chamber==='house'?'HD':'SD'}-${c.district}${c.incumbent?' &middot; incumbent':''}</small></span><i><i class=\"zero\"></i><i class=\"bar ${c.war>=0?'D':'R'}\" style=\"left:${c.war>=0?50:50-45*Math.abs(c.war)/historyMax}%;width:${45*Math.abs(c.war)/historyMax}%\"></i></i><b>${fmt(c.war)}</b></button>`).join('')}</div>`:'';box.innerHTML="
    )
    rendered = re.sub(r"function detail\(x\)\{.*?\}\nfunction renderMap", detail_js + "\nfunction renderMap", rendered, count=1, flags=re.S)
    static_headline = ('<div class="war-number">${fmt(x.war)}</div>'
                       '<div class="war-label">CMO &middot; ${x.percentile.toFixed(0)}th percentile</div>'
                       '<div class="distribution"><i style="left:${x.percentile}%"></i>'
                       '<div class="distribution-label"><span>Lowest</span><span>Median</span><span>Highest</span></div></div>')
    rendered = rendered.replace(static_headline, '${candidateHeadline(x)}', 1)
    career_css = r'''.measure-guide{margin:0 0 52px;border-top:4px solid var(--ink);padding-top:18px}.measure-guide h2{font:800 24px 'Libre Franklin';margin:0 0 12px}.measure-guide>div{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line)}.measure-guide article{background:#fff;padding:15px}.measure-guide b{font:700 12px 'Libre Franklin'}.measure-guide p{margin:5px 0 0;font-size:11px;line-height:1.45;color:var(--muted)}.detail{position:relative}.close-detail{position:absolute;right:14px;top:14px;width:34px;height:34px;border:1px solid var(--line);border-radius:50%;background:#fff;color:var(--ink);font:24px/1 Arial;cursor:pointer}.close-detail:hover,.close-detail:focus-visible{background:var(--soft)}.career-history>p{margin:0 0 8px;font-size:9px;color:var(--muted)}.career-observation{width:100%;display:grid;grid-template-columns:72px minmax(90px,1fr) 58px;gap:8px;align-items:center;border:0;border-top:1px solid var(--line);background:#fff;padding:7px 0;text-align:left;color:var(--ink)}.career-observation:hover,.career-observation:focus-visible{background:var(--soft)}.career-observation>span{font:700 10px 'Libre Franklin'}.career-observation small{display:block;font:400 8px Inter;color:var(--muted)}.career-observation>i{position:relative;height:8px;background:var(--soft)}.career-observation .zero{position:absolute;left:50%;top:-2px;bottom:-2px;border-left:1px solid var(--ink)}.career-observation .bar{position:absolute;top:2px;height:4px}.career-observation .bar.D{background:var(--blue)}.career-observation .bar.R{background:var(--red)}.career-observation>b{text-align:right;font:700 9px 'Libre Franklin'}@media(max-width:780px){.measure-guide>div{grid-template-columns:1fr}.map-modes{display:grid;grid-template-columns:1fr 1fr}.map-modes button{white-space:normal;min-height:44px}.detail.is-empty{display:none}.rankings .table-wrap{max-height:none}.rankings table{font-size:11px}.rankings th,.rankings td{padding:9px 7px}}@media(max-width:480px){.map-modes{grid-template-columns:1fr}}'''
    rendered = rendered.replace("</style>", career_css + "</style>", 1)
    rendered = rendered.replace(
        "</style>",
        "@media(max-width:780px){.rankings table th:nth-child(n+5),.rankings table td:nth-child(n+5){display:none}}</style>", 1)
    rows_js = r'''function renderRows(){const d=DATA[active],scope=$('#scope-filter').value,q=$('#candidate-search').value.toLowerCase(),party=$('#party-filter').value,outcome=$('#outcome-filter').value,source=scope==='all'?allCandidates():d.candidates.map(x=>({...x,section:active,cycle:d.cycle,chamber:d.chamber})),rows=source.filter(x=>(party==='all'||x.party===party)&&(outcome==='all'||(outcome==='winner'&&x.winner)||(outcome==='incumbent'&&x.incumbent))&&(!q||x.candidate.toLowerCase().includes(q)||String(x.district)===q||String(x.cycle)===q||`${x.chamber} ${x.district}`.includes(q))).sort((a,b)=>{let A=a[sortKey],B=b[sortKey];return(typeof A==='string'?A.localeCompare(B):(A??-9999)-(B??-9999))*sortDir});$('#rows').innerHTML=rows.map(x=>`<tr tabindex="0" data-section="${x.section}" data-district="${x.district}" data-party="${x.party}"><td>${x.cycle} ${x.chamber==='house'?'H':'S'}</td><td>${x.district}</td><td class="cand"><i class="party-dot ${x.party}"></i>${esc(x.candidate)}${x.winner?' <small>✓</small>':''}${x.contestTier==='nominal'?' <span class="tier-badge sensitivity">Nominal</span>':''}</td><td class="num"><b>${fmt(x.war)}</b></td><td class="num">${fmt(x.partialPooled)}<br><small>${esc(x.qualityStatus)}</small></td><td class="num">${fmt(x.totalElectoralValue)}</td><td class="num">${fmtMaybe(x.within)}</td><td class="num">${fmtMaybe(x.raw)}</td><td class="num">${fmtMaybe(x.predictiveResidual)}</td><td class="num">${fmt(x.cycleTopTicket)}</td><td class="num">${fmt(x.margin)}</td><td class="num">${x.votes.toLocaleString()}</td></tr>`).join('');document.querySelectorAll('#rows tr').forEach(row=>{row.onclick=()=>selectCandidate(row.dataset.section,row.dataset.district,row.dataset.party);row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.onclick()}}})}'''
    rendered = re.sub(r"function renderRows\(\)\{.*?\}\nfunction render\(\)", rows_js + "\nfunction render()", rendered, count=1, flags=re.S)
    rendered = rendered.replace(
        '<tr tabindex="0" data-section="${x.section}"',
        '<tr tabindex="0" role="button" aria-label="Open ${x.candidate}, ${x.cycle} ${x.chamber===\'house\'?\'House\':\'Senate\'} District ${x.district}, CMO ${fmt(x.war)}" data-section="${x.section}"',
        1,
    )
    if "function clearSelection()" not in rendered:
        rendered = rendered.replace(
            "document.querySelectorAll('th[data-sort]')",
            "function clearSelection(){selected=null;selectedParty=null;detail(null);renderMap()}\n"
            "document.querySelectorAll('th[data-sort]')",
            1,
        )
    rendered = re.sub(
        r'<section class="downloads">.*?</section>',
        '<section class="downloads"><h2>Data and sources</h2><p>Download the candidate scores, race comparisons, uncertainty estimates, historical checks, and case studies used on this page.</p><div class="download-links"><a href="data/cmo_v6_southern_candidates.csv">Candidate scores</a><a href="data/cmo_v6_southern_races.csv">Race comparisons</a><a href="data/cmo_v6_southern_quality.csv">Quality estimates</a><a href="data/cmo_v6_southern_validation.csv">Historical checks</a><a href="data/cmo_v6_southern_case_studies.csv">Case studies</a><a href="cmo-methodology.html">Methodology</a></div></section>',
        rendered, count=1, flags=re.S)
    rendered = re.sub(
        r'<section class="method">.*?</section></main>',
        '<section class="method"><h2>How to read the measures</h2><p>CMO reports the observed margin difference from the selected same-district ticket.</p><p>Residual quality estimates compare that gap with historical Southern down-ballot voting and generic incumbency. They help describe past elections but are not inserted directly into the 2026 forecast.</p><p><a href="cmo-methodology.html">Read the full CMO methodology</a> or <a href="index.html">view the 2026 forecast</a>.</p></section></main>',
        rendered, count=1, flags=re.S)
    rendered = rendered.replace("CMO methodology v5", "CMO methodology v6")
    return rendered


def modernize_war_headline(rendered):
    """Make candidate WAR the public product while retaining CMO as evidence."""
    rendered = re.sub(
        r"<title>.*?</title>",
        "<title>Alabama Legislative Wins Above Replacement (WAR)</title>",
        rendered, count=1, flags=re.S,
    )
    rendered = re.sub(
        r'<section class="story-head"><h1>.*?</h1><div class="dek">.*?</div>',
        '<section class="story-head"><h1>Alabama Legislative WAR</h1><div class="dek">Candidate-level Wins Above Replacement estimates, observed ticket overperformance, and historical district context for Alabama legislative elections, 1994&ndash;2022.</div>',
        rendered, count=1, flags=re.S,
    )
    rendered = re.sub(
        r'<section class="model-status">.*?</section>',
        '<section class="model-status"><div class="status-card feature"><span>Historical WAR architecture</span><b>Partially pooled candidate quality</b><p>WAR estimates the candidate-versus-opponent component remaining after the Southern historical model accounts for ordinary down-ballot structure. CMO remains a separate observed ticket comparison.</p></div><div class="status-card"><b>8</b><span>Historical cycles</span></div><div class="status-card"><b>509</b><span>Contested D vs. R races</span></div><div class="status-card"><b>4</b><span>Map views</span></div></section>',
        rendered, count=1, flags=re.S,
    )
    rendered = re.sub(
        r'<section class="intro">.*?</section>',
        '<section class="intro"><p><strong>WAR is the headline candidate-quality estimate.</strong> It partially pools each candidate&rsquo;s residual across the candidate-opponent network after accounting for the historical Southern down-ballot expectation. Scores are margin points and retain uncertainty.</p><p>CMO remains the directly observed difference between a legislative candidate&rsquo;s margin and the selected same-district ticket. Governor, federal, and previous-presidential comparisons remain visible as separate evidence.</p></section>',
        rendered, count=1, flags=re.S,
    )
    rendered = re.sub(
        r'<section class="measure-guide".*?</section><section class="explorer">',
        '<section class="measure-guide" aria-labelledby="measureGuideTitle"><h2 id="measureGuideTitle">Measures used on this page</h2><div><article><b>WAR</b><p>Partial-pooled candidate quality after the Southern historical model accounts for ordinary down-ballot structure.</p></article><article><b>CMO</b><p>Observed candidate margin minus the selected same-district ticket margin.</p></article><article><b>Total electoral value</b><p>WAR plus the candidate-oriented generic incumbency component.</p></article></div></section><section class="explorer">',
        rendered, count=1, flags=re.S,
    )
    rendered = rendered.replace(
        "The default view maps CMO in margin points. The raw comparison views show the legislative margin relative to the same district's governor result or previous presidential result. Those three views use a symmetric ±30-point red-to-blue scale. Residual quality uses a separate ±20-point gold-to-teal scale; tooltips show uncapped values.",
        "The default view maps the Democratic-versus-Republican WAR differential on its own gold-to-teal scale. CMO and the governor and previous-presidential comparisons use a separate red-to-blue margin scale; tooltips show uncapped values.",
    )
    rendered = rendered.replace(
        '<button data-map-mode="absolute" class="active">CMO</button><button data-map-mode="quality">Residual quality differential</button>',
        '<button data-map-mode="quality" class="active">WAR</button><button data-map-mode="absolute">CMO</button>',
    )
    rendered = rendered.replace(
        "let active='2010-house',sortKey='war',sortDir=-1,selected=null,selectedParty=null,mapMode='absolute',baselineChoices={};",
        "let active='2010-house',sortKey='partialPooled',sortDir=-1,selected=null,selectedParty=null,mapMode='quality',baselineChoices={};",
    )
    rendered = rendered.replace(
        "quality:{description:'Pooled residual-quality differential, D minus R',headline:'Residual quality differential vs. opponent',title:'residual quality',cap:20",
        "quality:{description:'WAR differential, Democratic candidate minus Republican candidate',headline:'Candidate WAR',title:'WAR',cap:20",
    )
    rendered = rendered.replace(
        "function candidateMetric(x){if(!x)return null;if(mapMode==='absolute')return x.war;const value=mapMetric(DATA[active],x.district);return value==null?null:(x.party==='D'?Number(value):-Number(value))}",
        "function candidateMetric(x){if(!x)return null;if(mapMode==='quality')return Number(x.partialPooled);if(mapMode==='absolute')return x.war;const value=mapMetric(DATA[active],x.district);return value==null?null:(x.party==='D'?Number(value):-Number(value))}",
    )
    rendered = rendered.replace(
        "return mapMode==='quality'?`${side} residual-quality advantage: ${amount} points`:`${side} overperformance: ${amount} points`",
        "return mapMode==='quality'?`${side} WAR advantage: ${amount} points`:`${side} overperformance: ${amount} points`",
    )
    rendered = re.sub(
        r'<th data-sort="war">CMO.*?</th><th data-sort="partialPooled">.*?</th><th data-sort="totalElectoralValue">.*?</th>',
        '<th data-sort="partialPooled">WAR &harr;</th><th data-sort="war">CMO</th><th data-sort="totalElectoralValue">Total value</th>',
        rendered, count=1, flags=re.S,
    )
    rendered = rendered.replace(
        '<td class="num"><b>${fmt(x.war)}</b></td><td class="num">${fmt(x.partialPooled)}<br><small>${esc(x.qualityStatus)}</small></td><td class="num">${fmt(x.totalElectoralValue)}</td>',
        '<td class="num"><b>${fmt(x.partialPooled)}</b><br><small>${esc(x.qualityStatus)}</small></td><td class="num">${fmt(x.war)}</td><td class="num">${fmt(x.totalElectoralValue)}</td>',
    )
    rendered = rendered.replace(
        ", CMO ${fmt(x.war)}\" data-section=",
        ", WAR ${fmt(x.partialPooled)}\" data-section=",
    )
    rendered = rendered.replace("Candidate CMO timeline", "Candidate WAR timeline")
    rendered = rendered.replace("CMO is signed to the Democratic margin. Select a race to open it.", "WAR is candidate-oriented. Select a race to open it.")
    rendered = rendered.replace('<b>CMO ${fmt(c.war)}</b>', '<b>WAR ${fmt(c.partialPooled)}</b>')
    rendered = rendered.replace("Math.abs(c.war)", "Math.abs(c.partialPooled)")
    rendered = rendered.replace("c.war>=0", "c.partialPooled>=0")
    rendered = rendered.replace("${fmt(c.war)}", "${fmt(c.partialPooled)}")
    rendered = rendered.replace("Southern-prior decomposition", "WAR decomposition")
    rendered = rendered.replace("Race-level residual quality", "Unpooled quality residual")
    rendered = rendered.replace("Partial-pooled residual quality", "WAR")
    rendered = rendered.replace("Residual quality differential", "WAR differential")
    rendered = rendered.replace("residual candidate quality", "WAR")
    rendered = rendered.replace("Residual candidate quality", "WAR")
    rendered = rendered.replace("Candidate Quality Index", "WAR")
    rendered = rendered.replace("Candidate Quality", "WAR")
    rendered = rendered.replace(
        "CMO is the observed ticket comparison. WAR is a separate, shrinkage-based estimate; its interval and evidence status are shown rather than hidden.",
        "WAR is the headline partial-pooled estimate. CMO remains the observed ticket comparison; both are shown with distinct labels.",
    )
    rendered = rendered.replace(
        "<div><b>${fmt(d.summary.median)}</b><span>Median winner CMO</span></div><div><b>${esc(d.summary.top)}</b><span>Top winner</span></div>",
        "<div><b>${fmt(d.summary.warMedian)}</b><span>Median winner WAR</span></div><div><b>${esc(d.summary.warTop)}</b><span>Highest winner WAR</span></div>",
    )
    rendered = re.sub(
        r'<section class="method">.*?</section></main>',
        '<section class="method"><h2>How to read WAR</h2><p>WAR is a retrospective, partial-pooled estimate of candidate quality in margin points. It is not a win probability and does not uniquely separate candidate strength from opponent weakness in isolated one-time races.</p><p>CMO and the raw governor, federal, and previous-presidential comparisons show what happened before the historical structural adjustment. They remain available because the decomposition is uncertain.</p><p>The WAR name credits <a href="https://split-ticket.org/2025/08/15/deconstructing-war/" target="_blank" rel="noopener">Split Ticket&rsquo;s candidate-quality framework</a>; this project&rsquo;s Alabama construction and estimates are independent.</p><p><a href="cmo-methodology.html">Read the full WAR methodology</a> or <a href="index.html">view the 2026 forecast</a>.</p></section></main>',
        rendered, count=1, flags=re.S,
    )
    return rendered


def modernize_methodology_v6(rendered):
    rendered = modernize_methodology_v5(rendered)
    body = '''<article class="copy">
<section id="estimand"><h2>1. Direct CMO</h2><p><b>Candidate Margin Overperformance (CMO)</b> is the observed candidate-oriented legislative margin minus the selected same-district ticket margin.</p><div class="formula">Democratic race CMO = legislative Democratic margin − selected ticket Democratic margin<br>Candidate CMO = Democratic race CMO for D; its negative for R</div><p>Incumbency, fundraising, demographics, ideology, and candidate history do not alter the observed CMO score.</p></section>
<section id="data"><h2>2. Coverage</h2><p>The model covers 509 contested Democratic–Republican Alabama House and Senate races from 1994 through 2022 and publishes 1,018 candidate-cycle rows.</p></section>
<section id="baseline"><h2>3. Ticket selection</h2><p>The preferred baseline is the same-cycle federal ticket measured inside the legislative district. A documented same-cycle state-ticket result is used when federal context is unavailable. State, federal, and previous-presidential comparisons remain separate.</p></section>
<section id="prior"><h2>4. Southern comparison</h2><p>The historical comparison uses 2,350 legislative contests from ten Southern states, excluding Alabama. It estimates the ordinary down-ballot gap for a race with similar timing, chamber, federal baseline, and incumbency, then compares that expectation with the observed Alabama result.</p><div class="formula">Residual candidate quality = Direct CMO − Southern structural expectation<br>Generic incumbency gap = inclusive expectation − incumbent-neutral expectation</div><p>Federal ticket baselines can combine U.S. House and Senate results, so the model averages predictions under both office categories and retains their range.</p></section>
<section id="quality"><h2>5. Residual candidate quality</h2><p>The candidate-versus-opponent residual is partial-pooled across the identity and opponent network with ridge penalty 3, selected in forward tests among previously observed candidates. Total electoral value adds the candidate-oriented half-share of generic incumbency to the pooled residual effect.</p></section>
<section id="validation"><h2>6. Validation and regime change</h2><p>The Southern expectation lowers cycle-balanced historical MAE from 21.33 to 17.29 points, with gains concentrated in 1994–2014. It fails the modern gate: 2018–2022 MAE rises from 6.54 for the ticket baseline to 13.66. Therefore it is useful for historical decomposition but rejected as a direct 2026 forecast adjustment.</p></section>
<section id="uncertainty"><h2>7. Identification and uncertainty</h2><p>Residual quality remains a zero-sum candidate-versus-opponent differential. A one-time race cannot uniquely distinguish candidate strength from opponent weakness or omitted local conditions; isolated one-time candidates retain the <code>pair_differential_only</code> identification label. Partial-pooled estimates retain intervals, appearances, and an evidence status; an interval crossing zero means uncertain evidence.</p></section>
<section id="limits"><h2>8. Limitations</h2><ul><li>Many candidates appear once and most personal estimates remain uncertain.</li><li>The Southern historical panel ends in 2016 and cannot be extrapolated through the post-2016 regime without modern validation.</li><li>Fallback ticket sources and historical geographic allocation create row-specific comparability limits.</li><li>CMO is descriptive and is not itself a pre-election win probability.</li></ul></section>
<section id="reproducibility"><h2>9. Downloads</h2><p>Candidate scores, race comparisons, quality estimates, and historical validation results are available for review.</p><div class="links"><a href="cmo.html">Explore CMO</a><a href="data/cmo_v6_southern_candidates.csv">Candidate scores</a><a href="data/cmo_v6_southern_races.csv">Race comparisons</a><a href="data/cmo_v6_southern_quality.csv">Quality estimates</a><a href="data/cmo_v6_southern_validation.csv">Historical checks</a></div></section>
__ATTRIBUTION_PANEL__
</article>'''.replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
    start = rendered.index('<article class="copy">')
    end = rendered.index('</article></div></main>')
    rendered = rendered[:start] + body + rendered[end + len('</article>'):]
    rendered = re.sub(r'<aside class="toc">.*?</aside>', '<aside class="toc"><b>On this page</b><a href="#estimand">Direct CMO</a><a href="#data">Coverage</a><a href="#baseline">Ticket selection</a><a href="#prior">Southern comparison</a><a href="#quality">Residual quality</a><a href="#validation">Validation</a><a href="#uncertainty">Identification</a><a href="#limits">Limitations</a><a href="#reproducibility">Downloads</a><a href="#sources">Sources</a></aside>', rendered, count=1, flags=re.S)
    rendered = rendered.replace("Documentation for observed CMO and partial-pooled Candidate Quality in Alabama legislative elections.", "Documentation for Direct CMO and the Southern-prior historical decomposition in Alabama legislative elections.")
    return rendered


def modernize_war_methodology(rendered):
    """Present the v6 decomposition as WAR with CMO kept as an input measure."""
    rendered = re.sub(r"<title>.*?</title>", "<title>Alabama Legislative WAR Methodology</title>", rendered, count=1, flags=re.S)
    rendered = re.sub(r"<h1>.*?</h1>", "<h1>WAR methodology</h1>", rendered, count=1, flags=re.S)
    rendered = re.sub(
        r'<(?P<tag>div|p) class="dek">.*?</(?P=tag)>',
        '<p class="dek">Definitions, inputs, partial pooling, validation, and limitations for Alabama legislative Wins Above Replacement.</p>',
        rendered, count=1, flags=re.S,
    )
    body = '''<article class="copy">
<section id="estimand"><h2>1. What WAR estimates</h2><p><b>Wins Above Replacement (WAR)</b> is the partial-pooled candidate effect remaining after the historical Southern model estimates ordinary down-ballot structure for the race.</p><div class="formula">Race quality residual = observed CMO &minus; Southern structural expectation<br>Candidate WAR values are fitted so q(D candidate) &minus; q(R candidate) explains that residual</div><p>WAR is expressed in two-party margin points. It is retrospective, uncertain, and distinct from a win probability.</p></section>
<section id="cmo"><h2>2. CMO as the observed input</h2><p><b>Candidate Margin Overperformance (CMO)</b> is the candidate-oriented legislative margin minus the selected same-district ticket margin. Incumbency, fundraising, demographics, ideology, and candidate history do not alter CMO.</p><p>CMO remains published alongside WAR because it is directly auditable and shows the performance being decomposed.</p></section>
<section id="data"><h2>3. Coverage</h2><p>The model covers 509 contested Democratic&ndash;Republican Alabama House and Senate races from 1994 through 2022 and publishes 1,018 candidate-cycle rows.</p></section>
<section id="baseline"><h2>4. Ticket and geographic inputs</h2><p>The preferred CMO baseline is the same-cycle federal ticket measured inside the legislative district, with a documented same-cycle state-ticket fallback. Governor, federal, and previous-presidential comparisons remain separate.</p><p>Precinct-to-district allocation now gives official legislative ballot evidence priority over shared Census VTD geometry. One reported district receives the entire named precinct; a precinct reporting multiple districts is divided by its observed legislative activity; spatial and county fallbacks apply only when ballot evidence is unavailable.</p></section>
<section id="prior"><h2>5. Southern structural expectation</h2><p>The comparison uses 2,350 legislative contests from ten Southern states, excluding Alabama. It estimates ordinary down-ballot performance for a race with similar timing, chamber, federal baseline, and incumbency. The residual becomes the input to candidate partial pooling.</p></section>
<section id="quality"><h2>6. Partial pooling and incumbency</h2><p>The candidate-versus-opponent residual is partial-pooled across the identity and opponent network with the forward-selected ridge penalty. Generic incumbency is reported separately; total electoral value adds the candidate-oriented generic incumbency component to WAR.</p></section>
<section id="validation"><h2>7. Validation and regime change</h2><p>The Southern expectation improves historical fit across 1994&ndash;2022 but fails the modern 2018&ndash;2022 forecast gate. WAR is therefore used for historical candidate analysis and not inserted directly into the 2026 forecast as a deterministic adjustment.</p></section>
<section id="uncertainty"><h2>8. Identification and uncertainty</h2><p>A one-time race identifies only the candidate-versus-opponent differential. It cannot uniquely distinguish candidate strength, opponent weakness, and omitted local conditions. Isolated one-time candidates retain an uncertain, pair-differential-only label. Intervals crossing zero indicate uncertain evidence.</p></section>
<section id="limits"><h2>9. Limitations</h2><ul><li>Most candidates appear only once.</li><li>The Southern calibration panel ends in 2016 and does not validate a modern forecast adjustment.</li><li>Historical geography and fallback ticket sources add row-specific uncertainty.</li><li>WAR is a margin-point estimate, not literal seat wins or a causal division of credit.</li></ul></section>
<section id="reproducibility"><h2>10. Downloads and credit</h2><p>The WAR name credits <a href="https://split-ticket.org/2025/08/15/deconstructing-war/" target="_blank" rel="noopener">Split Ticket&rsquo;s candidate-quality framework</a>. This project&rsquo;s Alabama data, allocation hierarchy, Southern model, and estimates are independent.</p><div class="links"><a href="cmo.html">Explore WAR</a><a href="data/cmo_v6_southern_candidates.csv">Candidate data</a><a href="data/cmo_v6_southern_races.csv">Race data</a><a href="data/cmo_v6_southern_quality.csv">WAR estimates</a><a href="data/cmo_v6_southern_validation.csv">Historical checks</a></div></section>
__ATTRIBUTION_PANEL__
</article>'''.replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
    start = rendered.index('<article class="copy">')
    end = rendered.index('</article></div></main>')
    rendered = rendered[:start] + body + rendered[end + len('</article>'):]
    rendered = re.sub(
        r'<aside class="toc">.*?</aside>',
        '<aside class="toc"><b>On this page</b><a href="#estimand">WAR</a><a href="#cmo">CMO</a><a href="#data">Coverage</a><a href="#baseline">Inputs</a><a href="#prior">Southern expectation</a><a href="#quality">Partial pooling</a><a href="#validation">Validation</a><a href="#uncertainty">Identification</a><a href="#limits">Limitations</a><a href="#reproducibility">Downloads and credit</a><a href="#sources">Sources</a></aside>',
        rendered, count=1, flags=re.S,
    )
    return rendered


if False and __name__ == "__main__":  # superseded by the residual-WAR publisher below
    data = load_data()
    rendered = modernize_war_headline(modernize_v6_copy(build_page(data)))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    LEGACY_OUTPUT.write_text(rendered, encoding="utf-8")
    SITE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SITE_OUTPUT.write_text(rendered, encoding="utf-8")
    eligible_races = sum(section["summary"]["races"] for section in data.values())
    methodology = (ROOT / "project_docs" / "model" / "CMO_MODEL_CARD.md").read_text(encoding="utf-8")
    methodology_html = build_methodology_page(eligible_races)
    # Replace legacy prose wholesale while retaining the shared navigation and page shell.
    start = methodology_html.index('<article class="copy">')
    end = methodology_html.index('</article></div></main>')
    sections = '''<article class="copy">
<section id="estimand"><h2>1. Four separate measures</h2><p><b>Raw ticket overperformance</b> is the legislative Democratic margin minus the source-aware ticket baseline. <b>Context CMO</b>, the headline, is the legislative margin minus a candidate-variable-free regularized expectation. <b>Within-cycle CMO</b> centers context CMO on the median within each cycle and chamber. <b>Predictive residual</b> comes from a separate prediction model that may use incumbency, finance, and candidate history.</p><div class="formula">Candidate context CMO = party-oriented (legislative Democratic margin − expected context margin)</div><p>These are different estimands, not interchangeable robustness versions. Republican values reverse the Democratic race residual, so each race remains zero-sum.</p></section>
<section id="data"><h2>2. Coverage and contest tiers</h2><p>The data cover 1994 through 2022 for both Alabama legislative chambers. Races are classified as meaningful, marginal, or nominal according to the losing major-party vote share. Nominal contests remain visible but are excluded from fitting. The 1994 cycle remains a sensitivity tier because more of its context depends on historical allocation and fallback sources.</p></section>
<section id="baseline"><h2>3. Source-aware political baseline</h2><p>Governor and Attorney General results are combined by votes cast rather than by a simple office average. Starting in 2018, usable same-cycle U.S. House and U.S. Senate results receive a declared 30 percent federal weight, leaving 70 percent on the state ticket. Previous presidential margin is a documented fallback rather than a universal substitute.</p></section>
<section id="models"><h2>4. Alternative comparisons and uncertainty</h2><p>State-ticket, federal-ticket, and previous-presidential residuals are published alongside the headline. The band reflects disagreement among available ticket baselines plus source-quality and contest-quality penalties; it is not a 95 percent confidence interval.</p><p>The former context regression is retained only in a pathology audit. It is not used to calculate CMO because out-of-era covariate extrapolation can double-adjust district partisanship and reverse directly observed overperformance.</p></section>
<section id="identity"><h2>5. Candidate identity and career summaries</h2><p>Candidate histories link on normalized full names. Surname-only source records are treated as unresolved and race-specific, and same-cycle collisions are split by chamber and district. Career CMO is a separately labeled partial-pooled summary. It never replaces the election-level score.</p></section>
<section id="validation"><h2>6. Validation</h2><p>Every score is arithmetically reproducible from the published legislative and baseline margins. Validation checks vote-margin arithmetic, source selection, candidate orientation, zero-sum symmetry, uncertainty construction, and the baseline tournament.</p></section>
<section id="limits"><h2>7. Limitations</h2><ul><li>Eight election cycles provide many races but few independent statewide environments.</li><li>The index covers contested Democratic-versus-Republican races and not every legislative candidate.</li><li>Zero-sum race residuals cannot identify both candidates' contributions without stronger assumptions.</li><li>District plans, source quality, turnout, and party coalitions change over time.</li><li>Same-cycle election context makes historical CMO descriptive and unsuitable as a direct pre-election forecast input.</li></ul></section>
<section id="reproducibility"><h2>8. Reproducibility</h2><p>Each build records input hashes, code hash, configuration, run identifier, and output hashes in a deterministic manifest. Human identity adjudications remain separate from machine-generated evidence.</p><div class="links"><a href="cmo.html">Explore CMO</a><a href="data/cmo_v4_candidates.csv">Candidate data</a><a href="data/cmo_v4_races.csv">Race data</a><a href="data/cmo_v4_provenance.csv">Run manifest</a><a href="data/cmo_v4_components.csv">Components</a></div></section>
__ATTRIBUTION_PANEL__
</article>'''.replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
    sections = re.sub(
        r'<section id="estimand">.*?</section>',
        '<section id="estimand"><h2>1. Direct CMO</h2><p>The headline score is the candidate-oriented difference between the legislative margin and a source-aware same-district ticket baseline. It is an observed comparison, not a second-stage regression residual.</p><div class="formula">Candidate CMO = party-oriented (legislative margin minus source-aware ticket margin)</div><p>Republican values reverse the Democratic race residual, so each race remains zero-sum. Demographics, finance, incumbency, ideology, and candidate history do not alter an election-level score.</p></section>',
        sections, count=1, flags=re.S)
    methodology_html = methodology_html[:start] + sections + methodology_html[end + len('</article>'):]
    methodology_html = methodology_html.replace("A retrospective index of how far an Alabama legislative candidate ran ahead of or behind a cross-fitted expectation for the district and election.", "Documentation for the WAR-style ticket residual, structural model, diagnostics, and reproducible CMO v4 build.")
    old_toc = '<aside class="toc"><b>On this page</b><a href="#estimand">What CMO measures</a><a href="#data">Data and eligibility</a><a href="#baseline">Expected baseline</a><a href="#crossfit">Cross-fitting</a><a href="#versions">Three specifications</a><a href="#validation">Validation</a><a href="#limits">Limitations</a><a href="#forecast">Forecast use</a><a href="#sources">Sources and credit</a></aside>'
    new_toc = '<aside class="toc"><b>On this page</b><a href="#estimand">Four measures</a><a href="#data">Coverage and contest tiers</a><a href="#baseline">Political baseline</a><a href="#models">Estimation</a><a href="#identity">Identity and partial pooling</a><a href="#validation">Validation</a><a href="#limits">Limitations</a><a href="#reproducibility">Reproducibility</a><a href="#sources">Sources and credit</a></aside>'
    methodology_html = methodology_html.replace(old_toc, new_toc)
    methodology_html = modernize_war_methodology(
        modernize_methodology_v6(methodology_html)
    )
    SITE_METHODOLOGY_OUTPUT.write_text(methodology_html, encoding="utf-8")
    site_data = SITE_OUTPUT.parent / "data"
    site_data.mkdir(parents=True, exist_ok=True)
    for pattern in ("cmo_v2_*", "cmo_v3_*", "preliminary_cmo_*"):
        for stale in site_data.glob(pattern):
            if stale.is_file():
                stale.unlink()
    for source in WAR.glob("cmo_v6_southern_*"):
        if source.is_file():
            shutil.copy2(source, site_data / source.name)
    shutil.copy2(ROOT / "project_docs" / "model" / "CMO_METHODOLOGY_V6_SOUTHERN_PRIOR.md", site_data / "cmo_methodology_v6.md")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")


def build_residual_war_page():
    """Build the corrected post-2016 Alabama race-residual WAR explorer."""
    source = WAR / "alabama_war_v1"
    with (source / "candidate_cycle_war.csv").open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for record in records:
        orientation = 1.0 if record["canonical_party"] == "D" else -1.0
        rows.append({
            "cycle": int(record["cycle"]),
            "chamber": "House" if record["chamber"] == "lower" else "Senate",
            "district": int(float(record["district"])),
            "party": record["canonical_party"],
            "candidate": record["candidate_name"],
            "incumbent": record["incumbent"] in {"1", "True", "true"},
            "rawGap": orientation * float(record["raw_gap"]),
            "structuralGap": orientation * float(record["fitted_structural_expected_gap"]),
            "war": float(record["candidate_cycle_war"]),
            "result": record["candidate_cycle_result"],
        })
    rows.sort(key=lambda row: (row["cycle"], row["chamber"], row["district"], row["party"]))
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    run_id = html.escape(manifest["alabama_war_run_id"])
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Post-2016 Alabama legislative race-residual WAR ratings"><title>Alabama WAR · Jackson Hannan</title><style>
*{box-sizing:border-box}body{margin:0;background:#f6f7f5;color:#201c1d;font:15px/1.5 Arial,sans-serif}header{background:#fff;border-bottom:1px solid #ccd4d5}header nav{width:min(1180px,calc(100% - 32px));margin:auto;display:flex;gap:22px;padding:18px 0}header a{color:#4e2630;text-decoration:none;font-weight:700}.hero,.shell{width:min(1180px,calc(100% - 32px));margin:auto}.hero{padding:58px 0 34px}.kicker{text-transform:uppercase;letter-spacing:.13em;color:#743b42;font-size:12px;font-weight:800}.hero h1{font:700 clamp(42px,7vw,78px)/.98 Georgia,serif;margin:8px 0 18px}.dek{max-width:780px;font:20px/1.55 Georgia,serif;color:#48565b}.formula{background:#e9eef0;border-left:4px solid #743b42;padding:18px 20px;margin-top:22px;font:17px/1.6 Georgia,serif}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#aebbbf;border:1px solid #aebbbf;margin:28px 0}.stat{background:#fff;padding:20px}.stat b{display:block;font:700 30px Georgia,serif}.stat span{color:#5a686d}.tools{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}.tools input,.tools select{background:#fff;border:1px solid #aab5b8;padding:11px 12px;font:inherit;min-width:170px}.tools input{flex:1;min-width:230px}.table-wrap{overflow:auto;border:1px solid #bbc5c7;background:#fff}table{width:100%;border-collapse:collapse;min-width:850px}th,td{text-align:left;padding:12px 14px;border-bottom:1px solid #e0e5e6}th{position:sticky;top:0;background:#e9eef0;font-size:12px;text-transform:uppercase;letter-spacing:.07em}td.num{text-align:right;font-variant-numeric:tabular-nums}.party{display:inline-grid;place-items:center;width:25px;height:25px;border-radius:50%;color:#fff;font-weight:800}.party.D{background:#326da8}.party.R{background:#a54245}.war.pos{color:#225f46;font-weight:800}.war.neg{color:#8a3037;font-weight:800}.note{margin:26px 0 70px;padding:22px;border-top:3px solid #743b42;font:16px/1.65 Georgia,serif}.note a{color:#743b42;font-weight:700}@media(max-width:700px){.stats{grid-template-columns:1fr}.hero{padding-top:36px}}
</style></head><body><header><nav><a href="index.html">Forecast</a><a href="cmo.html" aria-current="page">Alabama WAR</a><a href="ideology-performance.html">Ideology &amp; caucuses</a><a href="methods.html">Methods</a></nav></header><main><section class="hero"><div class="kicker">Alabama legislative elections · 2018–2022</div><h1>Alabama WAR</h1><p class="dek">How far each Democratic–Republican legislative result finished above or below the structural margin expected for that race. These are race residuals, not pooled career effects.</p><div class="formula"><b>WAR = actual legislative-minus-ticket gap − fitted structural expected gap.</b><br>The Democratic candidate receives the race residual; the Republican receives its exact negative.</div><div class="stats"><div class="stat"><b>97</b><span>contested races</span></div><div class="stat"><b>194</b><span>candidate-cycle ratings</span></div><div class="stat"><b>2018–22</b><span>strict post-2016 coverage</span></div></div></section><section class="shell"><div class="tools"><input id="search" type="search" placeholder="Search candidate or district" aria-label="Search candidate or district"><select id="cycle" aria-label="Filter cycle"><option value="all">All cycles</option><option>2018</option><option>2022</option></select><select id="chamber" aria-label="Filter chamber"><option value="all">Both chambers</option><option>House</option><option>Senate</option></select></div><div class="table-wrap"><table><thead><tr><th>Candidate</th><th>Party</th><th>Cycle</th><th>District</th><th>Raw ticket gap</th><th>Structural gap</th><th>Alabama WAR</th></tr></thead><tbody id="rows"></tbody></table></div><p id="count"></p><div class="note"><b>Interpretation.</b> Positive WAR means the candidate performed better than the structural expectation; negative WAR means worse. A one-race residual does not uniquely divide credit between candidate strength, opponent weakness, and omitted local conditions. WAR is retrospective and is not a win probability. <a href="cmo-methodology.html">Read the methodology</a> or <a href="data/alabama_war_v1_candidate_cycle_war.csv">download candidate ratings</a>.<br><small>Run __RUN_ID__</small></div></section></main><script>const DATA=__PAYLOAD__;const body=document.getElementById("rows"),search=document.getElementById("search"),cycle=document.getElementById("cycle"),chamber=document.getElementById("chamber"),count=document.getElementById("count");const fmt=v=>(v>=0?"+":"")+v.toFixed(2);function draw(){const q=search.value.toLowerCase().trim();const filtered=DATA.filter(r=>(cycle.value==="all"||String(r.cycle)===cycle.value)&&(chamber.value==="all"||r.chamber===chamber.value)&&(!q||`${r.candidate} ${r.chamber} ${r.district} ${r.party}`.toLowerCase().includes(q)));body.innerHTML=filtered.map(r=>`<tr><td><b>${r.candidate}</b>${r.incumbent?" <small>incumbent</small>":""}</td><td><span class="party ${r.party}">${r.party}</span></td><td>${r.cycle}</td><td>${r.chamber} ${r.district}</td><td class="num">${fmt(r.rawGap)}</td><td class="num">${fmt(r.structuralGap)}</td><td class="num war ${r.war>=0?"pos":"neg"}">${fmt(r.war)}</td></tr>`).join("");count.textContent=`Showing ${filtered.length} of ${DATA.length} candidate-cycle ratings.`}search.addEventListener("input",draw);cycle.addEventListener("change",draw);chamber.addEventListener("change",draw);draw();</script></body></html>'''
    return page.replace("__PAYLOAD__", payload).replace("__RUN_ID__", run_id)


def build_residual_war_methodology():
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Alabama WAR methodology</title><style>body{margin:0;font:16px/1.65 Arial,sans-serif;color:#211d1e;background:#f6f7f5}header nav,main{width:min(900px,calc(100% - 36px));margin:auto}header{background:#fff;border-bottom:1px solid #ccd4d5}header nav{display:flex;gap:20px;padding:18px 0}a{color:#743b42;font-weight:700}h1,h2{font-family:Georgia,serif}h1{font-size:52px;line-height:1;margin:60px 0 18px}section{padding:10px 0 22px;border-bottom:1px solid #ccd4d5}.formula{background:#e9eef0;border-left:4px solid #743b42;padding:18px 20px;font-family:Georgia,serif}.links{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:70px}</style></head><body><header><nav><a href="index.html">Forecast</a><a href="cmo.html">Alabama WAR</a><a href="methods.html">Methods</a></nav></header><main><h1>Alabama WAR methodology</h1><p>Definitions, construction, validation, and limitations for the post-2016 Alabama legislative race residual.</p><section><h2>1. Estimand</h2><p>WAR is the actual legislative-minus-ticket gap minus the same-cycle fitted structural gap.</p><div class="formula">Race WAR = raw gap − fitted structural expected gap<br>Democratic candidate WAR = race WAR<br>Republican candidate WAR = −race WAR</div><p>No pooled individual candidate effect, career average, fundraising term, or ideology measure is called WAR.</p></section><section><h2>2. Structural expectation</h2><p>The source model is trained on strict post-2016 Southern Democratic-versus-Republican general elections. It estimates ordinary down-ballot structure from ticket partisanship, era, chamber, state, reviewed incumbency, and a lag term whose ticket-change effect decays over time. Finance was tested separately and rejected from headline WAR.</p></section><section><h2>3. Alabama coverage</h2><p>The Alabama publication filters the validated Southern run without refitting or changing scores: 64 races in 2018 and 33 in 2022, producing 194 opposite-signed candidate-cycle views. Uncontested, non-D–R, and non-strict rows are not silently scored.</p></section><section><h2>4. Forecast use</h2><p>A generic candidate has expected residual WAR of zero. The 2026 forecast therefore does not add prior WAR, CMO, candidate identity, repeat-candidate history, ideology, or fundraising. A candidate-independent structural adjustment was tested from 2018 into 2022 but failed its margin-error promotion gate, so it remains an audit diagnostic and is zero in the public headline.</p></section><section><h2>5. Limitations</h2><ul><li>WAR is retrospective and is not a win probability.</li><li>A race residual cannot uniquely separate candidate strength from opponent weakness or omitted local conditions.</li><li>Only two Alabama cycles are available after 2016, yielding one direct forward holdout.</li><li>Same-cycle ticket selection and historical district geography remain sources of uncertainty.</li></ul></section><section><h2>6. Downloads and credit</h2><p>The residual definition follows Split Ticket’s published framing of WAR as actual candidate performance minus structurally predicted performance. This Alabama implementation, data, and estimates are independent.</p><div class="links"><a href="data/alabama_war_v1_candidate_cycle_war.csv">Candidate ratings</a><a href="data/alabama_war_v1_race_war.csv">Race ratings</a><a href="data/alabama_war_v1_manifest.json">Manifest</a><a href="data/alabama_war_forecast_v1_forward_metrics.csv">Forecast test</a></div></section></main></body></html>'''


if __name__ == "__main__":
    rendered = build_residual_war_page()
    methodology_html = build_residual_war_methodology()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SITE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    LEGACY_OUTPUT.write_text(rendered, encoding="utf-8")
    SITE_OUTPUT.write_text(rendered, encoding="utf-8")
    SITE_METHODOLOGY_OUTPUT.write_text(methodology_html, encoding="utf-8")
    site_data = SITE_OUTPUT.parent / "data"
    site_data.mkdir(parents=True, exist_ok=True)
    sources = {
        WAR / "alabama_war_v1" / "candidate_cycle_war.csv": "alabama_war_v1_candidate_cycle_war.csv",
        WAR / "alabama_war_v1" / "race_war.csv": "alabama_war_v1_race_war.csv",
        WAR / "alabama_war_v1" / "coverage.csv": "alabama_war_v1_coverage.csv",
        WAR / "alabama_war_v1" / "manifest.json": "alabama_war_v1_manifest.json",
        ROOT / "data/processed/forecast_calibration/alabama_war_forecast_v1_forward_metrics.csv": "alabama_war_forecast_v1_forward_metrics.csv",
    }
    for source, name in sources.items():
        shutil.copy2(source, site_data / name)
    print(f"Wrote corrected Alabama WAR page with 194 candidate-cycle ratings ({OUTPUT})")
