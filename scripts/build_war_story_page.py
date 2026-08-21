"""Build a self-contained Alabama candidate margin-overperformance page."""

from __future__ import annotations

import csv
import html
import json
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
    with (WAR / "preliminary_cmo_candidates.csv").open(encoding="utf-8-sig", newline="") as f:
        candidates = list(csv.DictReader(f))
    with (WAR / "preliminary_cmo_races.csv").open(encoding="utf-8-sig", newline="") as f:
        races = list(csv.DictReader(f))
    with (WAR / "wikipedia_legislative_candidates.csv").open(encoding="utf-8-sig", newline="") as f:
        public_candidates = list(csv.DictReader(f))
    with (WAR / "2022_wikipedia_vote_validation.csv").open(encoding="utf-8-sig", newline="") as f:
        validated_2022_names = list(csv.DictReader(f))
    with (ROOT / "data" / "processed" / "elections" / "canonical_cmo_district_office_baselines.csv").open(encoding="utf-8-sig", newline="") as f:
        office_baselines = list(csv.DictReader(f))
    with (ROOT / "data" / "processed" / "elections" / "canonical_cmo_features.csv").open(encoding="utf-8-sig", newline="") as f:
        all_races = list(csv.DictReader(f))

    public_names = {
        (int(r["cycle"]), r["chamber"], int(r["district"]), r["party"], int(number(r["votes_wikipedia"], 0))): r["candidate"]
        for r in public_candidates
    }
    public_names.update({
        (int(r["cycle"]), r["chamber"], int(r["district"]), r["party"], int(number(r["votes_modeled"], 0))): r["candidate_modeled"]
        for r in validated_2022_names
    })
    race_index = {(int(r["cycle"]), r["chamber"], int(r["district"])): r for r in races}
    name_db = sqlite3.connect(ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite")
    observed_names = name_db.execute("""
        SELECT year, office, party_norm, TRIM(candidate), COUNT(*) AS records, SUM(votes) AS votes
        FROM vote_observations
        WHERE authority_rank = 1 AND party_norm IN ('D','R')
        GROUP BY year, office, party_norm, TRIM(candidate)
        ORDER BY year, office, party_norm, records DESC, votes DESC
    """).fetchall()
    name_db.close()
    office_names = {}
    for year, office, party, candidate, records, votes in observed_names:
        office_names.setdefault((int(year), office, party), candidate)
    office_names.update({
        (2010, "Governor", "D"): "Ron Sparks", (2010, "Governor", "R"): "Robert Bentley",
        (2010, "Attorney General", "D"): "James H. Anderson", (2010, "Attorney General", "R"): "Luther Strange",
    })
    office_index = {}
    for row in office_baselines:
        margin = number(row.get("office_margin"))
        if margin is None:
            continue
        key = (int(row["cycle"]), row["chamber"], int(float(row["district"])))
        office_index.setdefault(key, []).append({
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
        candidate_name = public_names.get(
            (cycle, chamber, district, row["party"], int(number(row["votes"], 0))),
            row["candidate"],
        )
        item = {
            "district": district,
            "candidate": candidate_name,
            "personId": row.get("person_id", ""),
            "party": row["party"],
            "votes": int(number(row["votes"], 0)),
            "war": round(number(row["candidate_cmo_total_oof"], 0), 2),
            "adjusted": round(number(row["candidate_cmo_resource_adjusted_oof"], 0), 2),
            "fundraisingAdjusted": round(number(row.get("candidate_cmo_fundraising_adjusted_oof"), 0), 2),
            "specificationRange": round(number(row.get("candidate_cmo_specification_range"), 0), 2),
            "signConsistent": str(row.get("candidate_cmo_sign_consistent", "")).lower() in {"true", "1"},
            "low": round(number(row["candidate_cmo_total_stability_low"], 0), 2),
            "high": round(number(row["candidate_cmo_total_stability_high"], 0), 2),
            "raw": round((number(race["raw_overperformance"], 0) if row["party"] == "D" else -number(race["raw_overperformance"], 0)), 2),
            "expected": round((number(race["expected_cmo_total_oof"], 0) if row["party"] == "D" else -number(race["expected_cmo_total_oof"], 0)), 2),
            "margin": round((number(race["legislative_dem_margin"], 0) if row["party"] == "D" else -number(race["legislative_dem_margin"], 0)), 2),
            "cycleTopTicket": round((number(race["statewide_index_margin"], 0) if row["party"] == "D" else -number(race["statewide_index_margin"], 0)), 2),
            "priorPres": (round(number(race["prior_pres_dem_margin"]), 2) if row["party"] == "D" and number(race["prior_pres_dem_margin"]) is not None
                          else round(-number(race["prior_pres_dem_margin"]), 2) if number(race["prior_pres_dem_margin"]) is not None else None),
            "expectedMargin": round((number(race["legislative_dem_margin"], 0) - number(race["cmo_total_oof"], 0) if row["party"] == "D" else -number(race["legislative_dem_margin"], 0) + number(race["cmo_total_oof"], 0)), 2),
            "winner": ((row["party"] == "D" and number(race["dem_votes"], 0) > number(race["rep_votes"], 0)) or
                       (row["party"] == "R" and number(race["rep_votes"], 0) > number(race["dem_votes"], 0))),
            "incumbent": ((row["party"] == "D" and str(race.get("dem_incumbent", "")).lower() in {"true", "1"}) or
                          (row["party"] == "R" and str(race.get("rep_incumbent", "")).lower() in {"true", "1"})),
            "quality": "; ".join(filter(None, [
                "1994 sensitivity tier" if cycle == 1994 else "",
                "historical geography/context" if cycle < 2010 else "",
                "incumbency match conflict excluded" if str(race.get("incumbency_conflict", "0")) in {"1", "1.0", "True", "true"} else "",
                "finance incomplete" if str(race.get("finance_complete", "")).lower() not in {"true", "1"} else "",
                "core baseline incomplete" if str(race.get("core_index_complete", "")).lower() not in {"true", "1"} else "",
                "2014 structural-break risk" if cycle == 2014 else "",
            ])) or "standard source checks passed",
            "modelTier": race.get("model_tier", ""),
            "baselineMethod": race.get("baseline_allocation_method", ""),
            "baselineFallbackShare": number(race.get("baseline_fallback_share")),
            "priorPresYear": number(race.get("prior_presidential_year")),
            "priorPresFallbackShare": number(race.get("prior_pres_fallback_share")),
            "priorPresComplete": str(race.get("prior_pres_source_complete", "")).lower() in {"true", "1"},
            "priorPresSwing": number(race.get("prior_pres_swing")),
            "presTrendAvailable": str(race.get("pres_trend_available", "")).lower() in {"true", "1"},
            "demographicsMethod": race.get("demographics_method", "") or race.get("demographics_method_historical", ""),
            "demographicReferenceYear": number(race.get("demographic_reference_year")),
            "nonwhiteShare": number(race.get("nonwhite_share")),
            "whiteCollegeShare": number(race.get("white_college_share")),
            "incumbencyComplete": str(race.get("incumbency_evidence_complete", "")).lower() in {"true", "1"},
            "incumbencyConflict": str(race.get("incumbency_conflict", "")).lower() in {"true", "1"},
            "financeComplete": str(race.get("finance_complete", "")).lower() in {"true", "1"},
            "ftmFinanceComplete": str(race.get("ftm_finance_complete", "")).lower() in {"true", "1"},
            "readinessStatus": race.get("readiness_status", ""),
        }
        groups.setdefault((cycle, chamber), []).append(item)

    payload = {}
    for (cycle, chamber), items in groups.items():
        ordered_scores = sorted(x["war"] for x in items)
        for item in items:
            below = sum(v < item["war"] for v in ordered_scores)
            equal = sum(v == item["war"] for v in ordered_scores)
            item["percentile"] = round(100 * (below + 0.5 * equal) / len(ordered_scores), 1)
        frame = gpd.read_file(f"zip://{(MAPS / MAP_FILES[(cycle, chamber)]).resolve()}").to_crs(4326)
        frame["district"] = frame.apply(lambda r: district_id(r, cycle, chamber), axis=1)
        frame["geometry"] = frame.geometry.simplify(0.007, preserve_topology=True)
        bounds = frame.total_bounds
        paths = [{"district": int(r.district), "path": path_for_geometry(r.geometry, bounds)} for _, r in frame.iterrows()]
        winners = {x["district"]: x for x in items if x["winner"]}
        scored = [x["war"] for x in winners.values()]
        districts_in_race = sorted({x["district"] for x in items})
        cycle_races = [r for r in all_races if int(r["cycle"]) == cycle and r["chamber"] == chamber]
        district_status = {}
        for row in cycle_races:
            district = int(float(row["district"]))
            if str(row.get("war_eligible", "")).lower() in {"true", "1"}:
                status = "Eligible contested D–R race"
            elif number(row.get("dem_votes"), 0) <= 0 or number(row.get("rep_votes"), 0) <= 0:
                status = "Uncontested or missing a Democratic/Republican nominee"
            elif str(row.get("core_index_complete", "")).lower() not in {"true", "1"}:
                status = "Statewide baseline incomplete"
            else:
                status = "Not eligible for a published CMO score"
            district_status[str(district)] = status
        dem_war = {
            d: round(number(race_index[(cycle, chamber, d)]["cmo_total_oof"], 0), 2)
            for d in districts_in_race
        }
        ordered_dem = sorted(dem_war.values())
        dem_percentile = {
            d: round(2 * ((sum(v < score for v in ordered_dem) +
                           0.5 * sum(v == score for v in ordered_dem)) / len(ordered_dem)) - 1, 4)
            for d, score in dem_war.items()
        }
        governor_margin = {
            d: next((o["demMargin"] for o in office_index.get((cycle, chamber, d), [])
                     if o["label"] == "Governor"), None)
            for d in districts_in_race
        }
        raw_vs_governor = {
            d: (round(number(race_index[(cycle, chamber, d)]["legislative_dem_margin"], 0) - governor_margin[d], 2)
                if governor_margin[d] is not None else None)
            for d in districts_in_race
        }
        raw_vs_presidential = {
            d: (round(number(race_index[(cycle, chamber, d)]["legislative_dem_margin"], 0) - prior, 2)
                if (prior := number(race_index[(cycle, chamber, d)].get("prior_pres_dem_margin"))) is not None else None)
            for d in districts_in_race
        }
        payload[f"{cycle}-{chamber}"] = {
            "cycle": cycle,
            "chamber": chamber,
            "mapVintage": "1992 enacted plan" if cycle <= 1998 else "2001 enacted plan" if cycle <= 2010 else "2012 enacted plan" if cycle == 2014 else "2017 enacted plan" if cycle == 2018 else "2021 enacted plan",
            "paths": paths,
            "candidates": sorted(items, key=lambda x: x["war"], reverse=True),
            "winners": winners,
            "demWar": dem_war,
            "demPercentile": dem_percentile,
            "rawVsGovernor": raw_vs_governor,
            "rawVsPresidential": raw_vs_presidential,
            "districtStatus": district_status,
            "baselines": {
                str(d): ([{"label": "Same-cycle composite", "demMargin": round(number(race_index[(cycle, chamber, d)].get("statewide_index_margin"), 0), 2), "kind": "composite", "demName": "Democratic ticket average", "repName": "Republican ticket average"},
                          {"label": "Previous presidential", "demMargin": round(number(race_index[(cycle, chamber, d)].get("prior_pres_dem_margin"), 0), 2), "kind": "presidential",
                           "available": number(race_index[(cycle, chamber, d)].get("prior_pres_dem_margin")) is not None,
                           "demName": {1994:"Bill Clinton",1998:"Bill Clinton",2002:"Al Gore",2006:"John Kerry",2014: "Barack Obama", 2018: "Hillary Clinton", 2022: "Joe Biden"}.get(cycle, "Democratic presidential nominee"),
                           "repName": {1994:"George H. W. Bush",1998:"Bob Dole",2002:"George W. Bush",2006:"George W. Bush",2014: "Mitt Romney", 2018: "Donald Trump", 2022: "Donald Trump"}.get(cycle, "Republican presidential nominee")}] +
                         office_index.get((cycle, chamber, d), []))
                for d in districts_in_race
            },
            "summary": {
                "races": len(winners),
                "candidates": len(items),
                "median": round(float(np.median(scored)), 1),
                "top": max(winners.values(), key=lambda x: x["war"])["candidate"],
            },
        }
    return payload


def load_data_v2():
    """Build the public payload from the versioned CMO v2 data product."""
    with (WAR / "cmo_v2_candidates.csv").open(encoding="utf-8-sig", newline="") as f:
        candidates = list(csv.DictReader(f))
    with (WAR / "cmo_v2_races.csv").open(encoding="utf-8-sig", newline="") as f:
        races = list(csv.DictReader(f))
    with (WAR / "cmo_v2_candidate_pair_attribution.csv").open(encoding="utf-8-sig", newline="") as f:
        pairs = list(csv.DictReader(f))
    with (WAR / "preliminary_cmo_candidates.csv").open(encoding="utf-8-sig", newline="") as f:
        legacy_names = list(csv.DictReader(f))
    with (WAR / "wikipedia_legislative_candidates.csv").open(encoding="utf-8-sig", newline="") as f:
        public_candidates = list(csv.DictReader(f))
    with (WAR / "2022_wikipedia_vote_validation.csv").open(encoding="utf-8-sig", newline="") as f:
        validated_2022_names = list(csv.DictReader(f))
    with (ROOT / "data" / "processed" / "elections" / "canonical_cmo_district_office_baselines.csv").open(encoding="utf-8-sig", newline="") as f:
        office_baselines = list(csv.DictReader(f))

    race_index = {(int(r["cycle"]), r["chamber"], int(float(r["district"]))): r for r in races}
    pair_index = {(int(r["cycle"]), r["chamber"], int(float(r["district"]))): r for r in pairs}
    public_name_index = {
        (int(r["cycle"]), r["chamber"], int(float(r["district"])), r["party"], int(number(r["votes"], 0))): r["candidate"]
        for r in legacy_names
    }
    public_name_index.update({
        (int(r["cycle"]), r["chamber"], int(r["district"]), r["party"], int(number(r["votes_wikipedia"], 0))): r["candidate"]
        for r in public_candidates
    })
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
        party = row["canonical_party"]
        orient = 1 if party == "D" else -1
        width = number(row.get("candidate_context_cmo_high"), 0) - number(row.get("candidate_context_cmo_low"), 0)
        item = {
            "district": district,
            "candidate": public_name_index.get((cycle, chamber, district, party, int(number(row["canonical_votes"], 0))), row["canonical_name"]),
            "personId": row["candidate_effect_id"],
            "party": party, "votes": int(number(row["canonical_votes"], 0)),
            "war": round(number(row["candidate_context_cmo"], 0), 2),
            "within": round(number(row["candidate_within_cycle_cmo"], 0), 2),
            "raw": round(number(row["candidate_raw_ticket_overperformance"], 0), 2),
            "predictiveResidual": round(number(row["candidate_predictive_residual"], 0), 2),
            "partialPooled": round(number(row["candidate_partial_pooled_effect"], 0), 2),
            "appearances": int(number(row.get("appearances"), 1)),
            "attributionReliability": number(row.get("attribution_reliability"), 0),
            "identityStatus": row.get("identity_status", ""), "contestTier": row.get("contest_tier", ""),
            "low": round(number(row["candidate_context_cmo_low"], 0), 2),
            "high": round(number(row["candidate_context_cmo_high"], 0), 2),
            "specificationRange": round(width, 2),
            "signConsistent": bool(np.sign(number(race.get("context_cmo_huber"), 0)) == np.sign(number(race.get("context_cmo_logit"), 0))),
            "expectedMargin": round(orient * number(race["expected_margin_context"], 0), 2),
            "margin": round(orient * number(race["legislative_dem_margin"], 0), 2),
            "cycleTopTicket": round(orient * number(race["baseline_ensemble_margin"], 0), 2),
            "priorPres": (round(orient * number(race.get("prior_pres_dem_margin_v2")), 2)
                          if number(race.get("prior_pres_dem_margin_v2")) is not None else None),
            "priorPresYear": number(race.get("prior_presidential_year")),
            "winner": str(row.get("winner", "")).lower() in {"true", "1"},
            "incumbent": str(row.get("incumbent", "")).lower() in {"true", "1"},
            "quality": "; ".join(filter(None, [
                "nominal contest; excluded from fitting" if row.get("contest_tier") == "nominal" else "",
                "1994 sensitivity tier" if cycle == 1994 else "",
                "race-specific unresolved identity" if row.get("identity_status") == "surname_only_unresolved_race_specific" else "",
                "statewide baseline fallback" if number(race.get("baseline_fallback_share"), 0) > 0 else "",
            ])) or "standard source checks passed",
            "modelTier": race.get("model_tier", ""), "baselineMethod": race.get("baseline_source_v2", ""),
            "baselineFallbackShare": number(race.get("baseline_fallback_share")),
            "priorPresFallbackShare": number(race.get("prior_pres_fallback_share")),
            "priorPresComplete": str(race.get("prior_pres_source_complete", "")).lower() in {"true", "1"},
            "demographicsMethod": race.get("demographics_method", "") or race.get("demographics_method_historical", ""),
            "demographicReferenceYear": number(race.get("demographic_reference_year")),
            "nonwhiteShare": number(race.get("nonwhite_share")), "whiteCollegeShare": number(race.get("white_college_share")),
            "readinessStatus": race.get("readiness_status", ""),
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
        dem_context = {d: round(number(race_index[(cycle, chamber, d)]["context_cmo"], 0), 2) for d in districts}
        dem_within = {d: round(number(race_index[(cycle, chamber, d)]["within_cycle_cmo"], 0), 2) for d in districts}
        dem_raw = {d: round(number(race_index[(cycle, chamber, d)]["raw_ticket_overperformance"], 0), 2) for d in districts}
        dem_pair = {d: round(number(pair_index[(cycle, chamber, d)]["candidate_pair_component"], 0), 2) for d in districts}
        ordered_dem = sorted(dem_context.values())
        percentiles = {d: round(2 * ((sum(v < s for v in ordered_dem) + .5 * sum(v == s for v in ordered_dem)) / len(ordered_dem)) - 1, 4) for d, s in dem_context.items()}
        gov = {d: next((o["demMargin"] for o in office_index.get((cycle, chamber, d), []) if o["label"] == "Governor"), None) for d in districts}
        raw_gov = {d: round(number(race_index[(cycle, chamber, d)]["legislative_dem_margin"], 0) - gov[d], 2) if gov[d] is not None else None for d in districts}
        raw_pres = {d: round(number(race_index[(cycle, chamber, d)]["legislative_dem_margin"], 0) - number(race_index[(cycle, chamber, d)]["prior_pres_dem_margin_v2"]), 2) if number(race_index[(cycle, chamber, d)].get("prior_pres_dem_margin_v2")) is not None else None for d in districts}
        payload[f"{cycle}-{chamber}"] = {
            "cycle": cycle, "chamber": chamber,
            "mapVintage": "1992 enacted plan" if cycle <= 1998 else "2001 enacted plan" if cycle <= 2010 else "2012 enacted plan" if cycle == 2014 else "2017 enacted plan" if cycle == 2018 else "2021 enacted plan",
            "paths": paths, "candidates": sorted(items, key=lambda x: x["war"], reverse=True), "winners": winners,
            "demWar": dem_context, "demWithin": dem_within, "demRawTicket": dem_raw, "demPair": dem_pair,
            "demPercentile": percentiles, "rawVsGovernor": raw_gov, "rawVsPresidential": raw_pres,
            "districtStatus": {str(d): f"{race_index[(cycle, chamber, d)]['contest_tier'].title()} contested D–R race" for d in districts},
            "baselines": {str(d): ([{"label": "Source-aware ensemble", "demMargin": round(number(race_index[(cycle, chamber, d)]["baseline_ensemble_margin"], 0), 2), "kind": "composite", "demName": "Democratic baseline", "repName": "Republican baseline"}, {"label": "Previous presidential", "demMargin": round(number(race_index[(cycle, chamber, d)].get("prior_pres_dem_margin_v2"), 0), 2), "kind": "presidential", "available": number(race_index[(cycle, chamber, d)].get("prior_pres_dem_margin_v2")) is not None, "demName": "Democratic nominee", "repName": "Republican nominee"}] + office_index.get((cycle, chamber, d), [])) for d in districts},
            "summary": {"races": len(winners), "candidates": len(items), "median": round(float(np.median([x["war"] for x in winners.values()])), 1), "top": max(winners.values(), key=lambda x: x["war"])["candidate"]},
        }
    return payload


def build_validation_panel():
    diagnostics = list(csv.DictReader((WAR / "cmo_diagnostics.csv").open(encoding="utf-8-sig", newline="")))
    benchmarks = list(csv.DictReader((WAR / "cmo_benchmark_diagnostics.csv").open(encoding="utf-8-sig", newline="")))
    forward = list(csv.DictReader((WAR / "cmo_forward_validation.csv").open(encoding="utf-8-sig", newline="")))
    labels = {"total": "Total", "resource_adjusted": "Resource-adjusted", "fundraising_adjusted": "Fundraising-adjusted"}
    rows = "".join(
        f"<tr><td>{labels.get(r['specification'], html.escape(r['specification']))}</td>"
        f"<td>{number(r['random_mae']):.1f}</td><td>{number(r['random_r2']):.3f}</td>"
        f"<td>{number(r['district_grouped_mae']):.1f}</td><td>{number(r['district_grouped_r2']):.3f}</td>"
        f"<td>{number(r['cycle_holdout_mae']):.1f}</td><td>{number(r['cycle_holdout_r2']):.3f}</td></tr>"
        for r in diagnostics
    )
    benchmark_rows = "".join(
        f"<tr><td>{html.escape(r['benchmark'].replace('_', ' ').title())}</td><td>{number(r['mae']):.1f}</td><td>{number(r['r2']):.3f}</td></tr>"
        for r in benchmarks
    )
    total_forward = [r for r in forward if r["specification"] == "total"]
    forward_rows = "".join(
        f"<tr class=\"{'risk-row' if number(r['r2']) < 0 else ''}\"><td>{r['test_cycle']}</td><td>{r['test_races']}</td>"
        f"<td>{number(r['mae']):.1f}</td><td>{number(r['r2']):.3f}</td></tr>" for r in total_forward
    )
    return f'''<section class="validation" id="validation"><div class="section-head"><div><h2>Model validation</h2><p>Out-of-sample error in margin percentage points. Negative R² means the model transferred worse than predicting the test set mean.</p></div><span class="warning-chip">Retrospective—not a forecast</span></div><div class="validation-grid"><div><h3>Cross-validation by specification</h3><div class="table-wrap compact"><table><thead><tr><th>Specification</th><th>Random MAE</th><th>Random R²</th><th>District MAE</th><th>District R²</th><th>Cycle MAE</th><th>Cycle R²</th></tr></thead><tbody>{rows}</tbody></table></div></div><div><h3>Total CMO forward tests</h3><div class="table-wrap compact"><table><thead><tr><th>Test cycle</th><th>Races</th><th>MAE</th><th>R²</th></tr></thead><tbody>{forward_rows}</tbody></table></div></div></div><details><summary>Simple benchmark comparison</summary><div class="table-wrap compact benchmark"><table><thead><tr><th>Benchmark</th><th>MAE</th><th>R²</th></tr></thead><tbody>{benchmark_rows}</tbody></table></div></details><p class="validation-note">Forward performance varies materially by election era, including negative R² in several cycles. CMO is suitable for retrospective comparison, not uniform claims about unseen elections.</p></section>'''


def build_validation_panel_v2():
    diagnostics = list(csv.DictReader((WAR / "cmo_v2_diagnostics.csv").open(encoding="utf-8-sig", newline="")))
    validity = list(csv.DictReader((WAR / "cmo_v2_construct_validity.csv").open(encoding="utf-8-sig", newline="")))
    labels = {
        "baseline_ensemble_margin": "Source-aware baseline", "context_ridge": "Context CMO (ridge)",
        "context_huber": "Robust alternative", "context_bounded_logit": "Bounded-logit alternative",
        "nested_forward_selected": "Nested-forward specification", "predictive_full": "Predictive residual",
    }
    rows = []
    for spec in labels:
        values = [r for r in diagnostics if r["specification"] == spec]
        if values:
            rows.append(f"<tr><td>{labels[spec]}</td><td>{sum(number(r['races'], 0) for r in values):.0f}</td><td>{np.mean([number(r['mae'], 0) for r in values]):.1f}</td><td>{np.mean([number(r['rmse'], 0) for r in values]):.1f}</td></tr>")
    validity_rows = "".join(
        f"<tr><td>{html.escape(r['design'].replace('_', ' ').title())}</td><td>{html.escape(r['outcome'].replace('candidate_', '').replace('_', ' ').title())}</td><td>{r['n']}</td><td>{number(r['spearman']):.3f}</td><td>{number(r['spearman_p']):.3f}</td></tr>"
        for r in validity
    )
    return f'''<section class="validation" id="validation"><div class="section-head"><div><h2>Diagnostics</h2><p>Errors are calculated by cycle. The displayed averages weight election cycles equally, so a large cycle does not dominate the result.</p></div><span class="warning-chip">Retrospective—not causal</span></div><div class="validation-grid"><div><h3>Cycle-balanced error</h3><div class="table-wrap compact"><table><thead><tr><th>Specification</th><th>Race predictions</th><th>Mean cycle MAE</th><th>Mean cycle RMSE</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></div><div><h3>Construct-validity checks</h3><div class="table-wrap compact"><table><thead><tr><th>Design</th><th>Measure</th><th>N</th><th>Spearman</th><th>p</th></tr></thead><tbody>{validity_rows}</tbody></table></div></div></div><p class="validation-note">Context CMO is the public comparison measure. Predictive residual is shown separately because it conditions on candidate-linked variables. The partial-pooled candidate-pair estimate is descriptive attribution, not a causal individual effect.</p></section>'''


def build_attribution_panel(tag="section"):
    sources = [
        ("Election returns", "Alabama Secretary of State", "Official legislative, statewide-office, and presidential returns; the authoritative election source.", "https://www.sos.alabama.gov/alabama-votes/voter/election-information"),
        ("Election reconciliation", "OpenElections", "Standardized secondary election files used for comparison, normalization, and documented fallback—not a replacement for official returns.", "https://github.com/openelections/openelections-data-al"),
        ("Population and demographics", "U.S. Census Bureau", "1990/2000 decennial Census SF3, American Community Survey estimates, Census blocks and VTD geography.", "https://data.census.gov/"),
        ("District boundaries", "U.S. Census Bureau TIGER/Line and archived Alabama enacted-plan shapefiles", "Legislative boundary geometry used to render maps and allocate geographic features; the page identifies the plan vintage.", "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html"),
        ("Precinct geography and presidential returns", "Voting and Election Science Team (VEST)", "Election-specific precinct files used in the modern presidential/geographic pipeline where documented.", "https://dataverse.harvard.edu/dataverse/electionscience"),
        ("Historical campaign finance", "Database on Ideology, Money in Politics, and Elections (DIME), Adam Bonica", "Recipient-level contribution totals used for pre-electronic-era resource coverage; missing records remain unknown.", "https://data.stanford.edu/dime"),
        ("State campaign finance", "Alabama Secretary of State FCPA", "Principal-campaign-committee summaries provide the preferred 2014-2022 fundraising observations; identified committees with no cycle activity are observed zeros, while unmatched candidates remain unknown.", "https://fcpa.alabamavotes.gov/"),
        ("Finance cross-check", "FollowTheMoney / National Institute on Money in Politics", "Candidate fundraising totals remain a secondary comparison source rather than the canonical modern finance input.", "https://www.followthemoney.org/"),
        ("Historical roster evidence", "Shor–McCarty state legislative data", "Serving-legislator roster and party evidence used in historical incumbency review.", "https://americanlegislatures.com/"),
        ("Independent validation", "Wikipedia election pages", "Archived pages used only to cross-check candidate names and vote totals; discrepancies do not overwrite official returns.", "https://en.wikipedia.org/wiki/Alabama_Legislature"),
    ]
    cards = "".join(
        f'<article><span>{html.escape(role)}</span><h3><a href="{url}" target="_blank" rel="noopener">{html.escape(name)} ↗</a></h3><p>{html.escape(use)}</p></article>'
        for role, name, use, url in sources
    )
    return f'<{tag} class="attribution" id="sources"><div class="section-head"><div><h2>Data sources and attribution</h2><p>Credits describe how each source is used in CMO. Derived scores, allocations, matches, and errors are this project’s calculations and should not be attributed to the source organizations.</p></div></div><div class="source-ledger">{cards}</div><p class="attribution-note"><b>Attribution boundary:</b> Source organizations provide underlying records or geography; none endorses this model. Alabama Secretary of State returns remain authoritative. OpenElections and Wikipedia are secondary checks. Finance missingness is never interpreted as zero.</p></{tag}>'


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
.detail{padding:30px 28px;display:flex;flex-direction:column}.detail-empty{margin:auto;color:var(--muted);font:16px Georgia,serif;text-align:center;max-width:260px}.detail h3{font:800 25px 'Libre Franklin';margin:0}.party{font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:1px;margin:6px 0 14px}.party.D{color:var(--blue)}.party.R{color:var(--red)}.badges{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:20px}.badge{background:#eef2f6;border-radius:20px;padding:4px 8px;font:700 9px 'Libre Franklin';letter-spacing:.4px;text-transform:uppercase}.badge.warn{background:#fff1d6;color:#7a4d00}.war-number{font:800 62px/.9 'Libre Franklin';letter-spacing:-3px}.war-label{font-size:11px;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted);margin:9px 0 12px}.distribution{position:relative;height:8px;background:linear-gradient(90deg,var(--red),#eee 50%,var(--blue));margin:9px 4px 25px;border-radius:5px}.distribution i{position:absolute;top:-5px;width:3px;height:18px;background:var(--ink);box-shadow:0 0 0 2px #fff;transform:translateX(-50%)}.distribution-label{display:flex;justify-content:space-between;font-size:9px;color:var(--muted);margin-top:6px}.stat{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:10px 0;font-size:13px}.stat b{font-family:'Libre Franklin'}.decomp{margin-top:12px;border:1px solid var(--line);padding:12px 14px}.decomp-title{font:700 10px 'Libre Franklin';text-transform:uppercase;letter-spacing:.7px;margin-bottom:5px}.explain{background:var(--soft);padding:15px 16px;margin-top:16px;font:13px/1.55 Georgia,serif}
.racebox{border:1px solid #aeb7c2;margin:20px 0 4px;background:#fff}.racebox-head{background:var(--navy);color:#fff;text-align:center;padding:9px 12px;font:700 13px 'Libre Franklin'}.racebox-sub{text-align:center;background:#edf1f5;border-bottom:1px solid #aeb7c2;padding:5px;font:600 10px 'Libre Franklin';text-transform:uppercase;letter-spacing:.5px}.racebox table{font-size:12px}.racebox th{cursor:default;background:#f8fafc;border-bottom:1px solid #cdd3da;padding:7px 8px;font-size:9px}.racebox td{padding:8px;border-bottom:1px solid #e4e7ec}.racebox tr:last-child td{border-bottom:0}.racebox .winner-row{font-weight:700}.racebox .party-cell{width:8px;padding:0}.racebox .party-cell.D{background:var(--blue)}.racebox .party-cell.R{background:var(--red)}.racebox-total{display:grid;grid-template-columns:1fr 1fr;background:#f8fafc;border-top:1px solid #cdd3da}.racebox-total div{padding:7px 9px;font-size:10px}.racebox-total div:last-child{text-align:right}.check{color:#157347;margin-left:4px}
.detail>.racebox{margin:0 0 22px}.racebox .group-head{text-align:center;background:#e8edf3}.racebox .candidate-col{min-width:115px}.racebox .expected{background:#f7f9fb}.racebox-comparison{background:#f8fafc;border-top:1px solid #cdd3da;padding:7px 9px}.racebox-comparison div{display:flex;justify-content:space-between;gap:12px;font-size:10px;padding:2px 0}.racebox-comparison b{text-align:right}
.baseline-context{border-top:3px solid var(--navy);margin-top:10px;padding:10px 9px;background:#fff}.baseline-title{font:700 10px 'Libre Franklin';text-transform:uppercase;letter-spacing:.6px;margin-bottom:7px}.baseline-tabs{display:flex;flex-wrap:wrap;gap:4px}.baseline-tabs button{border:1px solid #cdd3da;background:#f8fafc;padding:5px 7px;font:600 9px Inter;cursor:pointer}.baseline-tabs button.active{background:var(--navy);border-color:var(--navy);color:#fff}.baseline-wikibox{border:1px solid #aeb7c2;margin-top:9px}.baseline-wikibox-head{background:#dce5ee;text-align:center;padding:6px 8px;font:700 11px 'Libre Franklin'}.baseline-wikibox-sub{background:#f4f6f8;text-align:center;border-top:1px solid #cdd3da;border-bottom:1px solid #cdd3da;padding:3px 6px;font-size:9px;color:var(--muted)}.baseline-wikibox table{font-size:10px}.baseline-wikibox th{padding:5px 7px;font-size:8px;background:#f8fafc}.baseline-wikibox td{padding:6px 7px}.baseline-wikibox .leader{font-weight:700}.baseline-wikibox-foot{display:grid;grid-template-columns:1fr 1fr;background:#f8fafc;border-top:1px solid #cdd3da}.baseline-wikibox-foot div{padding:5px 7px;font-size:9px}.baseline-wikibox-foot div:last-child{text-align:right}.baseline-wikibox-note{border-top:1px solid #e4e7ec;padding:5px 7px;font-size:8px;color:var(--muted)}
.summary{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-top:0}.summary div{padding:17px 20px;border-right:1px solid var(--line)}.summary div:last-child{border:0}.summary b{display:block;font:800 21px 'Libre Franklin'}.summary span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.8px}
.rankings{margin-top:62px}.rankings h2{font:800 30px 'Libre Franklin';margin:0 0 8px}.filters{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.filters input,.filters select{border:1px solid var(--line);background:#fff;padding:9px 11px;font:12px Inter}.filters input{min-width:230px}.table-wrap{overflow:auto;border-top:3px solid var(--ink);margin-top:12px;max-height:650px}table{width:100%;border-collapse:collapse;font-size:13px}thead{position:sticky;top:0;background:#fff;z-index:1}th{text-align:left;font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:.8px;border-bottom:1px solid var(--ink);padding:13px 10px;cursor:pointer}td{border-bottom:1px solid var(--line);padding:11px 10px}td.num{text-align:right;font-variant-numeric:tabular-nums}.cand{font-weight:700}.party-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px}.party-dot.D{background:var(--blue)}.party-dot.R{background:var(--red)}
.rankings tbody tr{cursor:pointer}.rankings tbody tr:hover,.rankings tbody tr:focus{background:#f2f6fa;outline:2px solid var(--blue);outline-offset:-2px}.tier-badge{display:inline-block;margin-left:6px;padding:3px 5px;border:1px solid #aeb7c2;background:#f8fafc;font:700 8px 'Libre Franklin';text-transform:uppercase;letter-spacing:.4px}.tier-badge.sensitivity{background:#fff4dd;border-color:#e2b85b;color:#714b00}.quality-grid,.context-grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);margin-top:12px}.quality-grid div,.context-grid div{background:#fff;padding:8px}.quality-grid span,.context-grid span{display:block;color:var(--muted);font-size:8px;text-transform:uppercase;letter-spacing:.5px}.quality-grid b,.context-grid b{display:block;margin-top:3px;font-size:10px}.validation,.attribution,.downloads{margin-top:62px;border-top:4px solid var(--ink);padding-top:20px}.validation h2,.attribution h2,.downloads h2{font:800 30px 'Libre Franklin';margin:0 0 7px}.section-head{display:flex;justify-content:space-between;gap:20px;align-items:start}.section-head p,.downloads p{color:var(--muted);font-size:12px;max-width:720px}.warning-chip{padding:7px 9px;background:#fff0f0;border:1px solid #e5aaaa;color:#8b1f1f;font:700 9px 'Libre Franklin';text-transform:uppercase}.validation-grid{display:grid;grid-template-columns:1.6fr .8fr;gap:24px;margin-top:20px}.validation h3{font:700 14px 'Libre Franklin'}.table-wrap.compact{max-height:none;margin-top:8px}.compact th,.compact td{padding:8px;font-size:10px}.risk-row{background:#fff0f0}.validation details{margin-top:20px}.validation summary{cursor:pointer;font-weight:700}.benchmark{max-width:430px}.validation-note{padding:12px 14px;border-left:4px solid #b42318;background:#fff7f6;font-size:12px}.source-ledger{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-top:20px}.source-ledger article{background:#fff;padding:16px}.source-ledger span{font:700 8px 'Libre Franklin';text-transform:uppercase;letter-spacing:.7px;color:var(--muted)}.source-ledger h3{font:700 13px/1.3 'Libre Franklin';margin:6px 0}.source-ledger h3 a{color:var(--ink)}.source-ledger p{font-size:10px;line-height:1.5;color:var(--muted);margin:0}.attribution-note{background:var(--soft);border-left:4px solid var(--blue);padding:12px 14px;font-size:11px;line-height:1.55}.source-credit{font-size:8px;color:var(--muted);line-height:1.4;margin-top:7px}.download-links{display:flex;flex-wrap:wrap;gap:7px}.download-links a{border:1px solid var(--line);padding:9px 11px;color:var(--ink);font:700 10px 'Libre Franklin';text-decoration:none;text-transform:uppercase}.download-links a:hover{background:var(--soft)}
.method{max-width:760px;margin:72px 0 0}.method h2{font:800 30px 'Libre Franklin';border-top:4px solid var(--ink);padding-top:18px}.method p{font:17px/1.75 Georgia,serif}.source{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:15px;margin-top:28px}
.tooltip{position:fixed;z-index:5;pointer-events:none;background:#15181c;color:#fff;padding:9px 11px;font-size:11px;box-shadow:0 4px 16px #0003;display:none}
@media(max-width:780px){.nav{display:none}.brand{font-size:27px}main{padding:44px 18px}.story-head h1{letter-spacing:-2px}.dashboard{grid-template-columns:1fr}.map-panel{border-right:0;border-bottom:1px solid var(--line);padding:22px 16px}.summary{grid-template-columns:1fr 1fr}.summary div:nth-child(2){border-right:0}.summary div:nth-child(-n+2){border-bottom:1px solid var(--line)}.explorer-top{display:block}.detail{min-height:390px}.controls{grid-template-columns:1fr}.controls button{flex:1 0 29%}.validation-grid,.quality-grid,.context-grid,.source-ledger{grid-template-columns:1fr}.section-head{display:block}}
</style></head><body>
<header><div class="mast"><div><div class="brand">Jackson Hannan</div><div class="tag">Alabama legislative models</div></div><nav class="nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html" aria-current="page">CMO</a><a href="ideology-performance.html">Issues & caucuses</a><a href="methodology.html">Forecast methodology</a><a href="cmo-methodology.html">CMO methodology</a><a href="https://github.com/JacksonAHannan" target="_blank" rel="me noopener">GitHub</a></nav></div></header>
<main><section class="story-head"><h1>Alabama Candidate Margin Overperformance</h1><div class="dek">How far Alabama legislative candidates ran ahead of or behind the model’s district-level expectation from 1994 through 2022.</div><div class="byline">Model and analysis by <b>Jackson Hannan</b> &nbsp;•&nbsp; August 2026</div></section>
<section class="model-status"><div class="status-card feature"><span>Historical CMO architecture</span><b>Candidate-variable-free context</b><p>The headline comparison uses district political context, demographics, chamber, and cycle information. Candidate history, incumbency, and finance are excluded so the expectation does not absorb the performance CMO is intended to describe.</p></div><div class="status-card"><b>__CYCLE_COUNT__</b><span>Historical cycles</span></div><div class="status-card"><b>__ELIGIBLE_RACES__</b><span>Contested D vs. R races</span></div><div class="status-card"><b>4</b><span>Distinct estimands</span></div></section>
<section class="intro"><p>Candidate Margin Overperformance compares a legislative result with political conditions in the district. The page keeps four different questions separate: raw ticket overperformance, context-adjusted CMO, within-cycle CMO, and a predictive residual that may condition on candidate-linked information.</p><p><strong>Context CMO is the headline measure.</strong> Positive values indicate performance ahead of the candidate-variable-free expectation. Scores are two-party margin percentage points, are zero-sum within a race, and are not causal estimates of individual candidate quality.</p></section>
<section class="explorer"><div class="explorer-top"><div><h2>Explore the results</h2><div class="note">The default relative view uses context-CMO percentiles within the selected cycle and chamber so exceptional results do not flatten the rest of the map. Absolute views use a symmetric square-root scale capped visually at ±30 points. Tooltips always show the uncapped score.</div></div><div class="note" id="vintage"></div></div><div class="controls" id="controls"></div>
<div class="dashboard"><div class="map-panel"><h3 class="map-title" id="map-title"></h3><div class="map-sub" id="map-sub">Context CMO within cycle and chamber</div><div class="map-modes"><button data-map-mode="relative" class="active">Relative context</button><button data-map-mode="absolute">Context CMO</button><button data-map-mode="within">Within-cycle</button><button data-map-mode="rawticket">Raw ticket</button><button data-map-mode="pair">Partial-pooled pair</button><button data-map-mode="governor">Raw vs. Governor</button><button data-map-mode="presidential">Raw vs. president</button></div><div class="map-wrap"><svg id="map" viewBox="0 0 640 700" role="img"></svg><div class="legend"><div class="gradient"></div><div class="ticks" id="legend-ticks"></div></div></div></div><aside class="detail" id="detail"><div class="detail-empty">Select a colored district to inspect the race.</div></aside></div><div class="summary" id="summary"></div></section>
<section class="rankings"><h2>Candidate results</h2><div class="note">Context CMO is the headline comparison. The other columns answer different questions and are not interchangeable specifications of one score.</div><div class="filters"><input id="candidate-search" type="search" placeholder="Search candidate or district"><select id="scope-filter"><option value="active">Selected cycle and chamber</option><option value="all">All cycles and chambers</option></select><select id="party-filter"><option value="all">All parties</option><option value="D">Democratic</option><option value="R">Republican</option></select><select id="outcome-filter"><option value="all">All candidates</option><option value="winner">Winners</option><option value="incumbent">Incumbents</option></select></div><div class="table-wrap"><table><thead><tr><th data-sort="cycle">Cycle</th><th data-sort="district">District</th><th data-sort="candidate">Candidate</th><th data-sort="war">Context CMO ↕</th><th data-sort="within">Within-cycle</th><th data-sort="raw">Raw ticket</th><th data-sort="predictiveResidual">Predictive residual</th><th data-sort="partialPooled">Partial-pooled</th><th data-sort="specificationRange">Band width</th><th data-sort="cycleTopTicket">Baseline margin</th><th data-sort="expectedMargin">Expected margin</th><th data-sort="margin">Actual margin</th><th data-sort="votes">Votes</th></tr></thead><tbody id="rows"></tbody></table></div></section>
__VALIDATION_PANEL__
__ATTRIBUTION_PANEL__
<section class="downloads"><h2>Data and provenance</h2><p>Build updated August 21, 2026 from CMO methodology v2. Download the versioned rows, diagnostics, identity audit, and reproducibility manifest.</p><div class="download-links"><a href="data/cmo_v2_candidates.csv">Candidate output</a><a href="data/cmo_v2_races.csv">Race output</a><a href="data/cmo_v2_diagnostics.csv">Diagnostics</a><a href="data/cmo_v2_construct_validity.csv">Construct validity</a><a href="data/cmo_v2_run_manifest.csv">Run manifest</a><a href="data/cmo_model_card.md">Model card</a><a href="cmo-methodology.html">Methodology</a></div></section>
<section class="method"><h2>How to read CMO</h2><p>The source-aware baseline combines same-cycle Governor and Attorney General returns by vote weight. From 2018 onward, usable same-cycle federal results receive a declared 30 percent weight; previous presidential results remain a fallback. Context CMO then compares the legislative margin with a candidate-variable-free, regularized expectation.</p><p>Within-cycle CMO removes each cycle and chamber median. Raw ticket overperformance is the legislative margin minus the source-aware ticket baseline. Predictive residual conditions on candidate-linked variables and is therefore reported separately. The displayed band reflects model-specification disagreement and source quality; it is not a 95 percent confidence interval.</p><p><a href="cmo-methodology.html">Read the full CMO methodology</a>, <a href="index.html">view the 2026 forecast</a>, or read the <a href="methodology.html#models">forecast methodology</a>.</p><div class="source">Model output: <code>cmo_v2_candidates.csv</code>. Scores cover contested Democratic-versus-Republican races; nominal contests are displayed but excluded from model fitting.</div></section></main><div class="tooltip" id="tooltip"></div>
<script>const DATA=__PAYLOAD__;
let active='2010-house',sortKey='war',sortDir=-1,selected=null,mapMode='relative',baselineChoices={};
const $=s=>document.querySelector(s), fmt=n=>(n>0?'+':'')+Number(n).toFixed(1), fmtMaybe=n=>n==null?'Unavailable':fmt(n), pct=n=>n==null?'Unavailable':(100*Number(n)).toFixed(1)+'%', esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const allCandidates=()=>Object.entries(DATA).flatMap(([section,d])=>d.candidates.map(x=>({...x,section,cycle:d.cycle,chamber:d.chamber})));
function color(v){if(v==null)return '#deded9';let x=mapMode==='relative'?v:Math.sign(v)*Math.sqrt(Math.min(30,Math.abs(v))/30);if(x<0)return mix('#f2f1ed','#d34b45',-x);return mix('#f2f1ed','#3d77a8',x)}
function mapMetric(d,district){if(mapMode==='relative')return d.demPercentile[district];if(mapMode==='absolute')return d.demWar[district];if(mapMode==='within')return d.demWithin[district];if(mapMode==='rawticket')return d.demRawTicket[district];if(mapMode==='pair')return d.demPair[district];if(mapMode==='governor')return d.rawVsGovernor[district];return d.rawVsPresidential[district]}
function mapRawValue(d,district){return mapMode==='relative'?d.demWar[district]:mapMetric(d,district)}
function mapDescription(){return {relative:'Context CMO percentile within cycle and chamber',absolute:'Context CMO, square-root color scale',within:'Within-cycle CMO',rawticket:'Raw overperformance versus source-aware ticket baseline',pair:'Partial-pooled candidate-pair component',governor:'Raw legislative overperformance versus Governor',presidential:'Raw legislative overperformance versus previous presidential margin'}[mapMode]}
function mix(a,b,t){const A=a.match(/\w\w/g).map(x=>parseInt(x,16)),B=b.match(/\w\w/g).map(x=>parseInt(x,16));return '#'+A.map((x,i)=>Math.round(x+(B[i]-x)*t).toString(16).padStart(2,'0')).join('')}
function makeControls(){const box=$('#controls');box.innerHTML='';[['Early historical · 1994–2006',y=>y<=2006],['Modern series · 2010–2022',y=>y>=2010]].forEach(([label,include])=>{const group=document.createElement('div');group.className='cycle-group';const heading=document.createElement('span');heading.className='cycle-group-label';heading.textContent=label;const buttons=document.createElement('div');buttons.className='cycle-buttons';Object.keys(DATA).filter(k=>include(DATA[k].cycle)).forEach(k=>{const d=DATA[k],b=document.createElement('button');b.textContent=d.cycle+' '+(d.chamber==='house'?'House':'Senate');b.className=k===active?'active':'';b.setAttribute('aria-pressed',k===active?'true':'false');b.onclick=()=>{active=k;selected=null;render()};buttons.appendChild(b)});group.append(heading,buttons);box.appendChild(group)})}
function baselineOptions(x){const raw=DATA[active].baselines[String(x.district)]||[];return raw.filter(o=>o.available!==false).sort((a,b)=>{const rank=o=>o.label==='Governor'?0:o.kind==='office'?1:o.kind==='composite'?2:3;return rank(a)-rank(b)||a.label.localeCompare(b.label)})}
function setBaseline(district,index){baselineChoices[active+'-'+district]=index;detail(DATA[active].winners[district])}
function baselineContext(x,total){const options=baselineOptions(x);if(!options.length)return '';const key=active+'-'+x.district,index=Math.min(baselineChoices[key]??0,options.length-1),o=options[index],margin=o.demMargin,leader=margin>=0?'D':'R',demShare=(100+margin)/2,repShare=100-demShare,isObserved=o.kind==='office',boxTotal=isObserved?Number(o.demVotes)+Number(o.repVotes):total,demVotes=isObserved?Number(o.demVotes):Math.round(boxTotal*demShare/100),repVotes=isObserved?Number(o.repVotes):Math.round(boxTotal*repShare/100),gap=Math.abs(Math.round(demVotes-repVotes)),tabs=options.map((v,i)=>`<button class="${i===index?'active':''}" onclick="setBaseline(${x.district},${i})">${esc(v.label)}</button>`).join(''),subtitle=isObserved?'District-level two-party office result':'Margin normalized to legislative two-party turnout',note=isObserved?'Votes are the allocated district result for this statewide office.':'Vote totals are implied from the selected margin at the legislative race’s observed turnout.';return `<div class="baseline-context"><div class="baseline-title">District top-of-ticket context</div><div class="baseline-tabs">${tabs}</div><div class="baseline-wikibox"><div class="baseline-wikibox-head">${esc(o.label)}</div><div class="baseline-wikibox-sub">${subtitle}</div><table><thead><tr><th></th><th>Candidate</th><th>Party</th><th class="num">Votes</th><th class="num">Share</th></tr></thead><tbody><tr class="${leader==='D'?'leader':''}"><td class="party-cell D"></td><td>${esc(o.demName)}</td><td>D${leader==='D'?' <span class="check">✓</span>':''}</td><td class="num">${Math.round(demVotes).toLocaleString()}</td><td class="num">${demShare.toFixed(1)}%</td></tr><tr class="${leader==='R'?'leader':''}"><td class="party-cell R"></td><td>${esc(o.repName)}</td><td>R${leader==='R'?' <span class="check">✓</span>':''}</td><td class="num">${Math.round(repVotes).toLocaleString()}</td><td class="num">${repShare.toFixed(1)}%</td></tr></tbody></table><div class="baseline-wikibox-foot"><div><b>${Math.round(boxTotal).toLocaleString()}</b> two-party votes</div><div>Margin: <b>${leader}+${Math.abs(margin).toFixed(1)}</b> · ${gap.toLocaleString()} votes</div></div><div class="baseline-wikibox-note">${note}</div></div><div class="source-credit">Source: Alabama Secretary of State official returns; district allocation and composite calculations by this project.</div></div>`}
function raceBox(x){const d=DATA[active],race=d.candidates.filter(c=>c.district===x.district).sort((a,b)=>b.votes-a.votes),total=race.reduce((s,c)=>s+c.votes,0),actualGap=race.length>1?race[0].votes-race[1].votes:total,actualMargin=100*actualGap/total,dem=race.find(c=>c.party==='D'),expectedDem=dem?dem.expectedMargin:0,expectedLeader=expectedDem>=0?'Democratic':'Republican',expectedGap=Math.round(total*Math.abs(expectedDem)/100),rows=race.map(c=>{const expectedShare=(100+c.expectedMargin)/2,expectedVotes=Math.round(total*expectedShare/100);return `<tr class="${c.winner?'winner-row':''}"><td class="party-cell ${c.party}"></td><td class="candidate-col">${esc(c.candidate)} ${c.party}${c.incumbent?' <small>(inc.)</small>':''}${c.winner?' <span class="check">✓</span>':''}</td><td class="num">${c.votes.toLocaleString()}</td><td class="num">${(100*c.votes/total).toFixed(1)}%</td><td class="num expected">${expectedVotes.toLocaleString()}</td><td class="num expected">${expectedShare.toFixed(1)}%</td></tr>`}).join('');return `<div class="racebox"><div class="racebox-head">${d.cycle} Alabama ${d.chamber==='house'?'House':'Senate'} District ${x.district}</div><div class="racebox-sub">General election · actual versus model baseline</div><table><thead><tr><th rowspan="2"></th><th rowspan="2">Candidate</th><th colspan="2" class="group-head">Actual</th><th colspan="2" class="group-head">Expected baseline</th></tr><tr><th class="num">Votes</th><th class="num">Share</th><th class="num">Votes</th><th class="num">Share</th></tr></thead><tbody>${rows}</tbody></table><div class="racebox-comparison"><div><span>Actual margin</span><b>${race[0].party==='D'?'Democratic':'Republican'} +${actualMargin.toFixed(1)} pts · ${actualGap.toLocaleString()} votes</b></div><div><span>Expected baseline margin</span><b>${expectedLeader} +${Math.abs(expectedDem).toFixed(1)} pts · ${expectedGap.toLocaleString()} votes</b></div><div><span>Two-party turnout</span><b>${total.toLocaleString()} votes</b></div></div><div class="source-credit">Actual votes: Alabama Secretary of State. Candidate-name display may use archived Wikipedia pages only as a secondary cross-check; official totals control.</div>${baselineContext(x,total)}</div>`}
function detail(x){const box=$('#detail');if(!x){box.innerHTML='<div class="detail-empty">Select a district or candidate row to inspect the race.</div>';return}const width=x.high-x.low,stable=width<=15,quality=x.quality==='standard source checks passed',tier=x.modelTier==='sensitivity_1994'?'1994 sensitivity':'Historical',history=allCandidates().filter(c=>c.personId&&c.personId===x.personId).sort((a,b)=>a.cycle-b.cycle),historyHtml=history.length>1?`<div class="decomp"><div class="decomp-title">Resolved candidate history</div>${history.map(c=>`<div class="stat"><span>${c.cycle} ${c.chamber} ${c.district}</span><b>${fmt(c.war)}</b></div>`).join('')}</div>`:'';box.innerHTML=`${raceBox(x)}<h3>${esc(x.candidate)} <span class="tier-badge ${x.modelTier==='sensitivity_1994'?'sensitivity':''}">${tier}</span></h3><div class="party ${x.party}">${x.party==='D'?'Democratic':'Republican'} • District ${x.district}${x.incumbent?' • Incumbent':''}</div><div class="badges"><span class="badge">${esc(x.contestTier)} contest</span><span class="badge ${stable?'':'warn'}">${stable?'Narrower band':'Wider band'}</span><span class="badge ${x.signConsistent?'':'warn'}">${x.signConsistent?'Alternatives agree':'Alternative direction differs'}</span><span class="badge ${quality?'':'warn'}">${quality?'Standard sources':'Source caution'}</span></div><div class="war-number">${fmt(x.war)}</div><div class="war-label">Context CMO points • ${x.percentile.toFixed(0)}th percentile</div><div class="distribution"><i style="left:${x.percentile}%"></i><div class="distribution-label"><span>Lowest</span><span>Median</span><span>Highest</span></div></div><div class="stat"><span>Specification/data-quality band</span><b>${fmt(x.low)} to ${fmt(x.high)}</b></div><div class="stat"><span>Within-cycle CMO</span><b>${fmt(x.within)}</b></div><div class="stat"><span>Raw ticket overperformance</span><b>${fmt(x.raw)}</b></div><div class="stat"><span>Predictive residual</span><b>${fmt(x.predictiveResidual)}</b></div><div class="stat"><span>Partial-pooled candidate effect</span><b>${fmt(x.partialPooled)}</b></div><div class="stat"><span>Attribution reliability</span><b>${(100*x.attributionReliability).toFixed(0)}% · ${x.appearances} appearance${x.appearances===1?'':'s'}</b></div><div class="decomp"><div class="decomp-title">Context comparison</div><div class="stat"><span>Candidate-variable-free expected margin</span><b>${fmt(x.expectedMargin)}</b></div><div class="stat"><span>Candidate's actual margin</span><b>${fmt(x.margin)}</b></div><div class="stat"><span>Context CMO</span><b>${fmt(x.war)}</b></div><div class="stat"><span>Source-aware baseline margin</span><b>${fmt(x.cycleTopTicket)}</b></div></div><div class="decomp"><div class="decomp-title">Source quality</div><div class="quality-grid"><div><span>Baseline method</span><b>${esc(x.baselineMethod||'Unavailable')}</b></div><div><span>Baseline fallback</span><b>${pct(x.baselineFallbackShare)}</b></div><div><span>Identity linkage</span><b>${esc(x.identityStatus)}</b></div><div><span>Demographics</span><b>${esc(x.demographicsMethod||'Unavailable')}${x.demographicReferenceYear?' · '+Math.round(x.demographicReferenceYear):''}</b></div><div><span>Previous president</span><b>${fmtMaybe(x.priorPres)}</b></div><div><span>Votes</span><b>${x.votes.toLocaleString()}</b></div></div></div>${historyHtml}<div class="explain">${x.war>=0?'This candidate ran ahead of':'This candidate ran behind'} the candidate-variable-free context expectation by about <b>${Math.abs(x.war).toFixed(1)} points</b>. The predictive residual is separate because it conditions on candidate-linked variables.<br><br><b>Data note:</b> ${esc(x.quality)}</div>`}
function renderMap(){const d=DATA[active],map=$('#map'),tip=$('#tooltip');map.innerHTML='';map.setAttribute('aria-label',`${d.cycle} Alabama ${d.chamber} overperformance map`);d.paths.forEach(p=>{const x=d.winners[p.district],display=mapMetric(d,p.district),raw=mapRawValue(d,p.district),status=d.districtStatus[String(p.district)]||'No election record available',el=document.createElementNS('http://www.w3.org/2000/svg','path');el.setAttribute('d',p.path);el.setAttribute('fill',color(display));el.setAttribute('class','district'+(selected===p.district?' selected':''));el.setAttribute('tabindex','0');el.setAttribute('aria-label',x&&raw!=null?`District ${p.district}, ${raw>=0?'Democrat':'Republican'} overperformed by ${Math.abs(raw).toFixed(1)}, won by ${x.candidate}`:`District ${p.district}, ${status}`);el.onmouseenter=e=>{tip.style.display='block';tip.innerHTML=x&&raw!=null?`<b>District ${p.district}</b><br>${mapDescription()}<br>${raw>=0?'Democrat':'Republican'} +${Math.abs(raw).toFixed(1)} points${mapMode==='relative'?`<br>${x.percentile.toFixed(0)}th candidate percentile`:''}<br>Won by ${esc(x.candidate)}`:`<b>District ${p.district}</b><br>${esc(x?'Selected benchmark unavailable':status)}`;moveTip(e)};el.onmousemove=moveTip;el.onmouseleave=()=>tip.style.display='none';el.onclick=()=>{selected=p.district;detail(x);renderMap()};el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();el.onclick()}};map.appendChild(el)});$('#map-title').textContent=`${d.cycle} Alabama ${d.chamber[0].toUpperCase()+d.chamber.slice(1)} overperformance`;$('#vintage').textContent='Boundaries: '+d.mapVintage;$('#map-sub').textContent=mapDescription();$('#legend-ticks').innerHTML=mapMode==='relative'?'<span>Strongest R</span><span>R-leaning</span><span>Median</span><span>D-leaning</span><span>Strongest D</span>':'<span>R +30</span><span>R +10</span><span>Even</span><span>D +10</span><span>D +30</span>'}
function moveTip(e){const t=$('#tooltip');t.style.left=(e.clientX+14)+'px';t.style.top=(e.clientY+14)+'px'}
function selectCandidate(section,district,party){active=section;selected=Number(district);const x=DATA[active].candidates.find(c=>c.district===selected&&c.party===party);render();detail(x);$('#detail').scrollIntoView({behavior:'smooth',block:'start'})}
function renderRows(){const d=DATA[active],scope=$('#scope-filter').value,q=$('#candidate-search').value.toLowerCase(),party=$('#party-filter').value,outcome=$('#outcome-filter').value,source=scope==='all'?allCandidates():d.candidates.map(x=>({...x,section:active,cycle:d.cycle,chamber:d.chamber})),rows=source.filter(x=>(party==='all'||x.party===party)&&(outcome==='all'||(outcome==='winner'&&x.winner)||(outcome==='incumbent'&&x.incumbent))&&(!q||x.candidate.toLowerCase().includes(q)||String(x.district)===q||String(x.cycle)===q||`${x.chamber} ${x.district}`.includes(q))).sort((a,b)=>{let A=a[sortKey],B=b[sortKey];return(typeof A==='string'?A.localeCompare(B):A-B)*sortDir});$('#rows').innerHTML=rows.map(x=>`<tr tabindex="0" data-section="${x.section}" data-district="${x.district}" data-party="${x.party}"><td>${x.cycle} ${x.chamber==='house'?'H':'S'}</td><td>${x.district}</td><td class="cand"><i class="party-dot ${x.party}"></i>${esc(x.candidate)}${x.winner?' <small>✓</small>':''}${x.contestTier==='nominal'?' <span class="tier-badge sensitivity">Nominal</span>':''}</td><td class="num"><b>${fmt(x.war)}</b></td><td class="num">${fmt(x.within)}</td><td class="num">${fmt(x.raw)}</td><td class="num">${fmt(x.predictiveResidual)}</td><td class="num">${fmt(x.partialPooled)}</td><td class="num">${x.specificationRange.toFixed(1)}</td><td class="num">${fmt(x.cycleTopTicket)}</td><td class="num">${fmt(x.expectedMargin)}</td><td class="num">${fmt(x.margin)}</td><td class="num">${x.votes.toLocaleString()}</td></tr>`).join('');document.querySelectorAll('#rows tr').forEach(row=>{row.onclick=()=>selectCandidate(row.dataset.section,row.dataset.district,row.dataset.party);row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.onclick()}}})}
function render(){makeControls();const d=DATA[active];renderMap();detail(d.winners[selected]);renderRows();$('#summary').innerHTML=`<div><b>${d.summary.races}</b><span>Contested districts</span></div><div><b>${d.summary.candidates}</b><span>Candidates scored</span></div><div><b>${fmt(d.summary.median)}</b><span>Median winner CMO</span></div><div><b>${esc(d.summary.top)}</b><span>Top winner</span></div>`}
document.querySelectorAll('th[data-sort]').forEach(th=>th.onclick=()=>{const k=th.dataset.sort;sortDir=sortKey===k?-sortDir:(k==='candidate'?1:-1);sortKey=k;renderRows()});['candidate-search','scope-filter','party-filter','outcome-filter'].forEach(id=>$('#'+id).oninput=renderRows);document.querySelectorAll('[data-map-mode]').forEach(button=>button.onclick=()=>{mapMode=button.dataset.mapMode;document.querySelectorAll('[data-map-mode]').forEach(b=>b.classList.toggle('active',b===button));renderMap()});render();</script></body></html>'''
    eligible_races = sum(section["summary"]["races"] for section in payload.values())
    cycle_count = len({section["cycle"] for section in payload.values()})
    return (template.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
            .replace("__ELIGIBLE_RACES__", str(eligible_races))
            .replace("__CYCLE_COUNT__", str(cycle_count))
            .replace("__VALIDATION_PANEL__", build_validation_panel_v2())
            .replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
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
<section id="forecast"><h2>8. Relationship to the 2026 forecast</h2><p>The forecast and CMO are separate products. CMO describes historical overperformance. For 2026, prior CMO was tested as a shrinkage-adjusted candidate layer using exact candidate-and-party matches. It did not improve both the average and latest forward-cycle error under the declared promotion rule, so it does not alter the headline forecast and remains a scenario layer.</p><div class="links"><a href="cmo.html">Explore CMO</a><a href="index.html">View forecast</a><a href="methodology.html#candidate">Forecast candidate layer</a><a href="data/preliminary_cmo_candidates.csv">Candidate data</a></div></section>
__ATTRIBUTION_PANEL__
</article></div></main><footer>Model and analysis by Jackson Hannan · <a href="https://github.com/JacksonAHannan">GitHub</a> · <a href="https://substack.com/@jacksonhannan">Substack</a></footer></body></html>'''
    return (page.replace("__ELIGIBLE_RACES__", str(eligible_races))
            .replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
            .replace("Finance is an optional sensitivity layer rather than a requirement for headline CMO.",
                     "Headline Fundamentals+ uses canonical fundraising where available plus an explicit availability flag. Coverage is 352 of 509 races (69.2%); missing records remain unknown."))


if __name__ == "__main__":
    data = load_data_v2()
    rendered = build_page(data)
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
<section id="baseline"><h2>3. Source-aware political baseline</h2><p>Governor and Attorney General results are combined by votes cast rather than by a simple office average. Starting in 2018, usable same-cycle U.S. House and U.S. Senate results receive a declared 30 percent federal weight, leaving 70 percent on the state ticket. Previous presidential margin is a documented fallback rather than a universal substitute.</p><p>The expected context model uses political baseline, demographics, chamber, and cycle structure. It excludes candidate identity, incumbency, finance, prior performance, and winner status.</p></section>
<section id="models"><h2>4. Estimation and robustness</h2><p>Ridge regression is the headline context estimator. Huber regression and a bounded-logit margin model provide alternatives. A nested forward-selection exercise chooses specifications using only cycles earlier than the cycle being evaluated. Public uncertainty bands expand with model disagreement and source-quality penalties; they are not 95 percent confidence intervals.</p></section>
<section id="identity"><h2>5. Candidate identity and partial pooling</h2><p>Candidate histories link on normalized full names. Surname-only source records are treated as unresolved and race-specific, and same-cycle collisions are split by chamber and district. A crossed candidate/opponent ridge model produces a partial-pooled candidate-pair component. That component is descriptive attribution and is kept separate from headline context CMO.</p></section>
<section id="validation"><h2>6. Validation</h2><p>Diagnostics report errors by cycle and summarize them with equal weight for each election cycle. Construct-validity checks examine repeat-candidate persistence, next-election wins, resolved different-candidate successors, and incumbent-departure successors. These tests do not turn CMO into a causal candidate effect.</p></section>
<section id="limits"><h2>7. Limitations</h2><ul><li>Eight election cycles provide many races but few independent statewide environments.</li><li>The index covers contested Democratic-versus-Republican races and not every legislative candidate.</li><li>Zero-sum race residuals cannot identify both candidates' contributions without stronger assumptions.</li><li>District plans, source quality, turnout, and party coalitions change over time.</li><li>Same-cycle election context makes historical CMO descriptive and unsuitable as a direct pre-election forecast input.</li></ul></section>
<section id="reproducibility"><h2>8. Reproducibility</h2><p>Each build records input hashes, code hash, configuration, run identifier, and output hashes in a deterministic manifest. Human identity adjudications remain separate from machine-generated evidence.</p><div class="links"><a href="cmo.html">Explore CMO</a><a href="data/cmo_v2_candidates.csv">Candidate data</a><a href="data/cmo_v2_races.csv">Race data</a><a href="data/cmo_v2_run_manifest.csv">Run manifest</a><a href="data/cmo_model_card.md">Model card</a></div></section>
__ATTRIBUTION_PANEL__
</article>'''.replace("__ATTRIBUTION_PANEL__", build_attribution_panel())
    methodology_html = methodology_html[:start] + sections + methodology_html[end + len('</article>'):]
    methodology_html = methodology_html.replace("A retrospective index of how far an Alabama legislative candidate ran ahead of or behind a cross-fitted expectation for the district and election.", "Documentation for the source-aware baseline, four published estimands, contest tiers, identity rules, diagnostics, and reproducible CMO v2 build.")
    old_toc = '<aside class="toc"><b>On this page</b><a href="#estimand">What CMO measures</a><a href="#data">Data and eligibility</a><a href="#baseline">Expected baseline</a><a href="#crossfit">Cross-fitting</a><a href="#versions">Three specifications</a><a href="#validation">Validation</a><a href="#limits">Limitations</a><a href="#forecast">Forecast use</a><a href="#sources">Sources and credit</a></aside>'
    new_toc = '<aside class="toc"><b>On this page</b><a href="#estimand">Four measures</a><a href="#data">Coverage and contest tiers</a><a href="#baseline">Political baseline</a><a href="#models">Estimation</a><a href="#identity">Identity and partial pooling</a><a href="#validation">Validation</a><a href="#limits">Limitations</a><a href="#reproducibility">Reproducibility</a><a href="#sources">Sources and credit</a></aside>'
    methodology_html = methodology_html.replace(old_toc, new_toc)
    SITE_METHODOLOGY_OUTPUT.write_text(methodology_html, encoding="utf-8")
    site_data = SITE_OUTPUT.parent / "data"
    site_data.mkdir(parents=True, exist_ok=True)
    for source in WAR.glob("cmo_v2_*"):
        if source.is_file():
            shutil.copy2(source, site_data / source.name)
    shutil.copy2(ROOT / "project_docs" / "model" / "CMO_MODEL_CARD.md", site_data / "cmo_model_card.md")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
