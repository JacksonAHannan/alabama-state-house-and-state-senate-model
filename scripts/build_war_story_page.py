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
MAPS = ROOT / "Results and Shapefiles"
OUTPUT = ROOT / "Alabama Legislative Candidate Margin Overperformance (CMO).html"
LEGACY_OUTPUT = ROOT / "Alabama Legislative Wins Above Replacement (WAR).html"
SITE_OUTPUT = ROOT / "docs" / "cmo.html"
SITE_METHODOLOGY_OUTPUT = ROOT / "docs" / "cmo-methodology.html"

MAP_FILES = {
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
        return float(value)
    except (TypeError, ValueError):
        return default


def district_id(row, cycle, chamber):
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
    with (ROOT / "data" / "processed" / "elections" / "canonical_district_baseline_office_scenarios.csv").open(encoding="utf-8-sig", newline="") as f:
        office_baselines = list(csv.DictReader(f))

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
        if margin is None or row.get("scenario") != "prefer_direct":
            continue
        key = (int(row["cycle"]), row["chamber"], int(float(row["district"])))
        office_index.setdefault(key, []).append({
            "label": row["office"], "demMargin": round(margin, 2),
            "demVotes": round(number(row.get("D"), 0)),
            "repVotes": round(number(row.get("R"), 0)), "kind": "office",
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
            "party": row["party"],
            "votes": int(number(row["votes"], 0)),
            "war": round(number(row["candidate_cmo_total_oof"], 0), 2),
            "adjusted": round(number(row["candidate_cmo_resource_adjusted_oof"], 0), 2),
            "low": round(number(row["candidate_cmo_total_stability_low"], 0), 2),
            "high": round(number(row["candidate_cmo_total_stability_high"], 0), 2),
            "raw": round((number(race["raw_overperformance"], 0) if row["party"] == "D" else -number(race["raw_overperformance"], 0)), 2),
            "expected": round((number(race["expected_cmo_total_oof"], 0) if row["party"] == "D" else -number(race["expected_cmo_total_oof"], 0)), 2),
            "margin": round((number(race["legislative_dem_margin"], 0) if row["party"] == "D" else -number(race["legislative_dem_margin"], 0)), 2),
            "cycleTopTicket": round((number(race["statewide_index_margin"], 0) if row["party"] == "D" else -number(race["statewide_index_margin"], 0)), 2),
            "priorPres": round((number(race["prior_pres_dem_margin"], 0) if row["party"] == "D" else -number(race["prior_pres_dem_margin"], 0)), 2),
            "expectedMargin": round((number(race["legislative_dem_margin"], 0) - number(race["cmo_total_oof"], 0) if row["party"] == "D" else -number(race["legislative_dem_margin"], 0) + number(race["cmo_total_oof"], 0)), 2),
            "winner": ((row["party"] == "D" and number(race["dem_votes"], 0) > number(race["rep_votes"], 0)) or
                       (row["party"] == "R" and number(race["rep_votes"], 0) > number(race["dem_votes"], 0))),
            "incumbent": ((row["party"] == "D" and str(race.get("dem_incumbent", "")).lower() in {"true", "1"}) or
                          (row["party"] == "R" and str(race.get("rep_incumbent", "")).lower() in {"true", "1"})),
            "quality": "; ".join(filter(None, [
                "finance incomplete" if str(race.get("finance_complete", "")).lower() not in {"true", "1"} else "",
                "core baseline incomplete" if str(race.get("core_index_complete", "")).lower() not in {"true", "1"} else "",
                "2014 structural-break risk" if cycle == 2014 else "",
            ])) or "standard source checks passed",
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
            "mapVintage": "2001 enacted plan" if cycle == 2010 else "2012 enacted plan" if cycle == 2014 else "2017 enacted plan" if cycle == 2018 else "2021 enacted plan",
            "paths": paths,
            "candidates": sorted(items, key=lambda x: x["war"], reverse=True),
            "winners": winners,
            "demWar": dem_war,
            "demPercentile": dem_percentile,
            "rawVsGovernor": raw_vs_governor,
            "rawVsPresidential": raw_vs_presidential,
            "baselines": {
                str(d): ([{"label": "Same-cycle composite", "demMargin": round(number(race_index[(cycle, chamber, d)].get("statewide_index_margin"), 0), 2), "kind": "composite", "demName": "Democratic ticket average", "repName": "Republican ticket average"},
                          {"label": "Previous presidential", "demMargin": round(number(race_index[(cycle, chamber, d)].get("prior_pres_dem_margin"), 0), 2), "kind": "presidential",
                           "available": number(race_index[(cycle, chamber, d)].get("prior_pres_dem_margin")) is not None,
                           "demName": {2014: "Barack Obama", 2018: "Hillary Clinton", 2022: "Joe Biden"}.get(cycle, "Democratic presidential nominee"),
                           "repName": {2014: "Mitt Romney", 2018: "Donald Trump", 2022: "Donald Trump"}.get(cycle, "Republican presidential nominee")}] +
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
.controls{display:flex;gap:6px;flex-wrap:wrap;margin:18px 0 20px;padding:5px;background:var(--soft);border:1px solid var(--line);width:max-content;max-width:100%}.controls button{border:0;background:transparent;border-radius:3px;padding:9px 14px;font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:.6px;cursor:pointer}.controls button:hover,.controls button:focus-visible{background:#e8edf3}.controls button.active{background:var(--navy);color:#fff;box-shadow:0 1px 3px #0002}
.dashboard{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(330px,.85fr);border:1px solid var(--line);min-height:720px}.map-panel{padding:28px 30px;border-right:1px solid var(--line);position:relative}.map-title{font:700 20px 'Libre Franklin';margin:0}.map-sub{font-size:12px;color:var(--muted);margin:5px 0 4px}.map-wrap{max-width:610px;margin:12px auto 0}.map-wrap svg{width:100%;height:auto;display:block}.district{stroke:#fff;stroke-width:1.1;vector-effect:non-scaling-stroke;cursor:pointer;transition:filter .12s,stroke-width .12s}.district:hover,.district.selected{stroke:#17191c;stroke-width:2.3;filter:brightness(.96)}
.legend{max-width:430px;margin:10px auto 0}.gradient{height:10px;background:linear-gradient(90deg,#d34b45,#e8a19d,#f2f1ed,#9bbcd4,#3d77a8)}.ticks{display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-top:5px}
.map-modes{display:flex;gap:4px;margin-top:12px}.map-modes button{border:1px solid var(--line);background:#fff;padding:7px 10px;font:700 10px 'Libre Franklin';text-transform:uppercase;cursor:pointer}.map-modes button.active{background:var(--ink);color:#fff}
.detail{padding:30px 28px;display:flex;flex-direction:column}.detail-empty{margin:auto;color:var(--muted);font:16px Georgia,serif;text-align:center;max-width:260px}.detail h3{font:800 25px 'Libre Franklin';margin:0}.party{font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:1px;margin:6px 0 14px}.party.D{color:var(--blue)}.party.R{color:var(--red)}.badges{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:20px}.badge{background:#eef2f6;border-radius:20px;padding:4px 8px;font:700 9px 'Libre Franklin';letter-spacing:.4px;text-transform:uppercase}.badge.warn{background:#fff1d6;color:#7a4d00}.war-number{font:800 62px/.9 'Libre Franklin';letter-spacing:-3px}.war-label{font-size:11px;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted);margin:9px 0 12px}.distribution{position:relative;height:8px;background:linear-gradient(90deg,var(--red),#eee 50%,var(--blue));margin:9px 4px 25px;border-radius:5px}.distribution i{position:absolute;top:-5px;width:3px;height:18px;background:var(--ink);box-shadow:0 0 0 2px #fff;transform:translateX(-50%)}.distribution-label{display:flex;justify-content:space-between;font-size:9px;color:var(--muted);margin-top:6px}.stat{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:10px 0;font-size:13px}.stat b{font-family:'Libre Franklin'}.decomp{margin-top:12px;border:1px solid var(--line);padding:12px 14px}.decomp-title{font:700 10px 'Libre Franklin';text-transform:uppercase;letter-spacing:.7px;margin-bottom:5px}.explain{background:var(--soft);padding:15px 16px;margin-top:16px;font:13px/1.55 Georgia,serif}
.racebox{border:1px solid #aeb7c2;margin:20px 0 4px;background:#fff}.racebox-head{background:var(--navy);color:#fff;text-align:center;padding:9px 12px;font:700 13px 'Libre Franklin'}.racebox-sub{text-align:center;background:#edf1f5;border-bottom:1px solid #aeb7c2;padding:5px;font:600 10px 'Libre Franklin';text-transform:uppercase;letter-spacing:.5px}.racebox table{font-size:12px}.racebox th{cursor:default;background:#f8fafc;border-bottom:1px solid #cdd3da;padding:7px 8px;font-size:9px}.racebox td{padding:8px;border-bottom:1px solid #e4e7ec}.racebox tr:last-child td{border-bottom:0}.racebox .winner-row{font-weight:700}.racebox .party-cell{width:8px;padding:0}.racebox .party-cell.D{background:var(--blue)}.racebox .party-cell.R{background:var(--red)}.racebox-total{display:grid;grid-template-columns:1fr 1fr;background:#f8fafc;border-top:1px solid #cdd3da}.racebox-total div{padding:7px 9px;font-size:10px}.racebox-total div:last-child{text-align:right}.check{color:#157347;margin-left:4px}
.detail>.racebox{margin:0 0 22px}.racebox .group-head{text-align:center;background:#e8edf3}.racebox .candidate-col{min-width:115px}.racebox .expected{background:#f7f9fb}.racebox-comparison{background:#f8fafc;border-top:1px solid #cdd3da;padding:7px 9px}.racebox-comparison div{display:flex;justify-content:space-between;gap:12px;font-size:10px;padding:2px 0}.racebox-comparison b{text-align:right}
.baseline-context{border-top:3px solid var(--navy);margin-top:10px;padding:10px 9px;background:#fff}.baseline-title{font:700 10px 'Libre Franklin';text-transform:uppercase;letter-spacing:.6px;margin-bottom:7px}.baseline-tabs{display:flex;flex-wrap:wrap;gap:4px}.baseline-tabs button{border:1px solid #cdd3da;background:#f8fafc;padding:5px 7px;font:600 9px Inter;cursor:pointer}.baseline-tabs button.active{background:var(--navy);border-color:var(--navy);color:#fff}.baseline-wikibox{border:1px solid #aeb7c2;margin-top:9px}.baseline-wikibox-head{background:#dce5ee;text-align:center;padding:6px 8px;font:700 11px 'Libre Franklin'}.baseline-wikibox-sub{background:#f4f6f8;text-align:center;border-top:1px solid #cdd3da;border-bottom:1px solid #cdd3da;padding:3px 6px;font-size:9px;color:var(--muted)}.baseline-wikibox table{font-size:10px}.baseline-wikibox th{padding:5px 7px;font-size:8px;background:#f8fafc}.baseline-wikibox td{padding:6px 7px}.baseline-wikibox .leader{font-weight:700}.baseline-wikibox-foot{display:grid;grid-template-columns:1fr 1fr;background:#f8fafc;border-top:1px solid #cdd3da}.baseline-wikibox-foot div{padding:5px 7px;font-size:9px}.baseline-wikibox-foot div:last-child{text-align:right}.baseline-wikibox-note{border-top:1px solid #e4e7ec;padding:5px 7px;font-size:8px;color:var(--muted)}
.summary{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-top:0}.summary div{padding:17px 20px;border-right:1px solid var(--line)}.summary div:last-child{border:0}.summary b{display:block;font:800 21px 'Libre Franklin'}.summary span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.8px}
.rankings{margin-top:62px}.rankings h2{font:800 30px 'Libre Franklin';margin:0 0 8px}.filters{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.filters input,.filters select{border:1px solid var(--line);background:#fff;padding:9px 11px;font:12px Inter}.filters input{min-width:230px}.table-wrap{overflow:auto;border-top:3px solid var(--ink);margin-top:12px;max-height:650px}table{width:100%;border-collapse:collapse;font-size:13px}thead{position:sticky;top:0;background:#fff;z-index:1}th{text-align:left;font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:.8px;border-bottom:1px solid var(--ink);padding:13px 10px;cursor:pointer}td{border-bottom:1px solid var(--line);padding:11px 10px}td.num{text-align:right;font-variant-numeric:tabular-nums}.cand{font-weight:700}.party-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px}.party-dot.D{background:var(--blue)}.party-dot.R{background:var(--red)}
.method{max-width:760px;margin:72px 0 0}.method h2{font:800 30px 'Libre Franklin';border-top:4px solid var(--ink);padding-top:18px}.method p{font:17px/1.75 Georgia,serif}.source{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:15px;margin-top:28px}
.tooltip{position:fixed;z-index:5;pointer-events:none;background:#15181c;color:#fff;padding:9px 11px;font-size:11px;box-shadow:0 4px 16px #0003;display:none}
@media(max-width:780px){.nav{display:none}.brand{font-size:27px}main{padding:44px 18px}.story-head h1{letter-spacing:-2px}.dashboard{grid-template-columns:1fr}.map-panel{border-right:0;border-bottom:1px solid var(--line);padding:22px 16px}.summary{grid-template-columns:1fr 1fr}.summary div:nth-child(2){border-right:0}.summary div:nth-child(-n+2){border-bottom:1px solid var(--line)}.explorer-top{display:block}.detail{min-height:390px}.controls button{flex:1 0 29%}}
</style></head><body>
<header><div class="mast"><div><div class="brand">Jackson Hannan</div><div class="tag">Alabama legislative models</div></div><nav class="nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html" aria-current="page">CMO</a><a href="methodology.html">Forecast methodology</a><a href="cmo-methodology.html">CMO methodology</a><a href="https://github.com/JacksonAHannan" target="_blank" rel="me noopener">GitHub</a></nav></div></header>
<main><section class="story-head"><h1>Alabama Candidate Margin Overperformance</h1><div class="dek">How far Alabama legislative candidates ran ahead of or behind the model’s district-level expectation in 2010, 2014, 2018, and 2022.</div><div class="byline">Model and analysis by <b>Jackson Hannan</b> &nbsp;•&nbsp; August 2026</div></section>
<section class="model-status"><div class="status-card feature"><span>2026 forecast architecture</span><b>Direct presidential baseline</b><p>The forecast starts from projected 2024 presidential results. Polling, incumbency, finance, and candidate CMO remain explicit downstream adjustments.</p></div><div class="status-card"><b>4</b><span>Historical cycles</span></div><div class="status-card"><b>218</b><span>Eligible D vs. R races</span></div><div class="status-card"><b>12.57</b><span>Forward baseline MAE</span></div></section>
<section class="intro"><p>Winning a race is not the same thing as running a strong campaign. Candidate Margin Overperformance asks: <em>how much better or worse was a candidate's two-party margin than the model expected in that race?</em></p><p><strong>Positive CMO indicates outperformance; negative CMO indicates underperformance.</strong> Headline Total CMO excludes campaign spending and uses out-of-fold predictions. Scores are margin percentage points—not wins or an independently identified candidate effect.</p></section>
<section class="explorer"><div class="explorer-top"><div><h2>Explore the results</h2><div class="note">The default relative view uses within-cycle percentiles so exceptional results do not flatten the rest of the map. The absolute view uses a symmetric square-root scale capped visually at ±30 CMO points. Tooltips always show the uncapped raw score.</div></div><div class="note" id="vintage"></div></div><div class="controls" id="controls"></div>
<div class="dashboard"><div class="map-panel"><h3 class="map-title" id="map-title"></h3><div class="map-sub" id="map-sub">Relative overperformance within cycle and chamber</div><div class="map-modes"><button data-map-mode="relative" class="active">Relative CMO</button><button data-map-mode="absolute">Absolute CMO</button><button data-map-mode="governor">Raw vs. Governor</button><button data-map-mode="presidential">Raw vs. previous president</button></div><div class="map-wrap"><svg id="map" viewBox="0 0 640 700" role="img"></svg><div class="legend"><div class="gradient"></div><div class="ticks" id="legend-ticks"></div></div></div></div><aside class="detail" id="detail"><div class="detail-empty">Select a colored district to inspect the race.</div></aside></div><div class="summary" id="summary"></div></section>
<section class="rankings"><h2>Candidate rankings</h2><div class="note">Total CMO excludes spending; resource-adjusted CMO accounts for campaign resources. Both are out-of-fold historical scores.</div><div class="filters"><input id="candidate-search" type="search" placeholder="Search candidate or district"><select id="party-filter"><option value="all">All parties</option><option value="D">Democratic</option><option value="R">Republican</option></select><select id="outcome-filter"><option value="all">All candidates</option><option value="winner">Winners</option><option value="incumbent">Incumbents</option></select></div><div class="table-wrap"><table><thead><tr><th data-sort="district">District</th><th data-sort="candidate">Candidate</th><th data-sort="war">Total CMO ↕</th><th data-sort="percentile">Percentile</th><th data-sort="adjusted">Resource-adjusted CMO</th><th data-sort="cycleTopTicket">Same-cycle top-ticket margin</th><th data-sort="expectedMargin">Expected margin</th><th data-sort="margin">Candidate margin</th><th data-sort="votes">Votes</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section class="method"><h2>How to read CMO</h2><p>The model cross-fits expected Democratic margin overperformance using incumbency, prior presidential performance and trend, demographics, cycle, and chamber. Total CMO is the remaining residual. Resource-adjusted CMO additionally accounts for campaign spending. Republican values are sign-reversed district residuals, making the index zero-sum within each race by construction.</p><p>The displayed band measures sensitivity to withholding an entire election cycle; it is not a 95% confidence interval. Results apply only to contested Democratic-versus-Republican Alabama legislative races and should not be interpreted as a forecast or universal candidate-quality measure.</p><p><a href="cmo-methodology.html">Read the full CMO methodology</a>, <a href="index.html">view the 2026 forecast</a>, or read the <a href="methodology.html#candidate">forecast candidate-layer methodology</a>.</p><div class="source">Model output: <code>preliminary_cmo_candidates.csv</code>. Sources include Alabama election returns and campaign-finance records, Census ACS, presidential precinct returns, and enacted legislative district files.</div></section></main><div class="tooltip" id="tooltip"></div>
<script>const DATA=__PAYLOAD__;
let active='2010-house',sortKey='war',sortDir=-1,selected=null,mapMode='relative',baselineChoices={};
const $=s=>document.querySelector(s), fmt=n=>(n>0?'+':'')+Number(n).toFixed(1), esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function color(v){if(v==null)return '#deded9';let x=mapMode==='relative'?v:Math.sign(v)*Math.sqrt(Math.min(30,Math.abs(v))/30);if(x<0)return mix('#f2f1ed','#d34b45',-x);return mix('#f2f1ed','#3d77a8',x)}
function mapMetric(d,district){if(mapMode==='relative')return d.demPercentile[district];if(mapMode==='absolute')return d.demWar[district];if(mapMode==='governor')return d.rawVsGovernor[district];return d.rawVsPresidential[district]}
function mapRawValue(d,district){return mapMode==='relative'||mapMode==='absolute'?d.demWar[district]:mapMetric(d,district)}
function mapDescription(){return {relative:'CMO percentile within cycle and chamber',absolute:'Absolute CMO, square-root color scale',governor:'Raw legislative overperformance versus Governor',presidential:'Raw legislative overperformance versus previous presidential margin'}[mapMode]}
function mix(a,b,t){const A=a.match(/\w\w/g).map(x=>parseInt(x,16)),B=b.match(/\w\w/g).map(x=>parseInt(x,16));return '#'+A.map((x,i)=>Math.round(x+(B[i]-x)*t).toString(16).padStart(2,'0')).join('')}
function makeControls(){const box=$('#controls');box.innerHTML='';Object.keys(DATA).forEach(k=>{const d=DATA[k],b=document.createElement('button');b.textContent=d.cycle+' '+d.chamber;b.className=k===active?'active':'';b.onclick=()=>{active=k;selected=null;render()};box.appendChild(b)})}
function baselineOptions(x){const raw=DATA[active].baselines[String(x.district)]||[];return raw.filter(o=>o.available!==false).sort((a,b)=>{const rank=o=>o.label==='Governor'?0:o.kind==='office'?1:o.kind==='composite'?2:3;return rank(a)-rank(b)||a.label.localeCompare(b.label)})}
function setBaseline(district,index){baselineChoices[active+'-'+district]=index;detail(DATA[active].winners[district])}
function baselineContext(x,total){const options=baselineOptions(x);if(!options.length)return '';const key=active+'-'+x.district,index=Math.min(baselineChoices[key]??0,options.length-1),o=options[index],margin=o.demMargin,leader=margin>=0?'D':'R',demShare=(100+margin)/2,repShare=100-demShare,isObserved=o.kind==='office',boxTotal=isObserved?Number(o.demVotes)+Number(o.repVotes):total,demVotes=isObserved?Number(o.demVotes):Math.round(boxTotal*demShare/100),repVotes=isObserved?Number(o.repVotes):Math.round(boxTotal*repShare/100),gap=Math.abs(Math.round(demVotes-repVotes)),tabs=options.map((v,i)=>`<button class="${i===index?'active':''}" onclick="setBaseline(${x.district},${i})">${esc(v.label)}</button>`).join(''),subtitle=isObserved?'District-level two-party office result':'Margin normalized to legislative two-party turnout',note=isObserved?'Votes are the allocated district result for this statewide office.':'Vote totals are implied from the selected margin at the legislative race’s observed turnout.';return `<div class="baseline-context"><div class="baseline-title">District top-of-ticket context</div><div class="baseline-tabs">${tabs}</div><div class="baseline-wikibox"><div class="baseline-wikibox-head">${esc(o.label)}</div><div class="baseline-wikibox-sub">${subtitle}</div><table><thead><tr><th></th><th>Candidate</th><th>Party</th><th class="num">Votes</th><th class="num">Share</th></tr></thead><tbody><tr class="${leader==='D'?'leader':''}"><td class="party-cell D"></td><td>${esc(o.demName)}</td><td>D${leader==='D'?' <span class="check">✓</span>':''}</td><td class="num">${Math.round(demVotes).toLocaleString()}</td><td class="num">${demShare.toFixed(1)}%</td></tr><tr class="${leader==='R'?'leader':''}"><td class="party-cell R"></td><td>${esc(o.repName)}</td><td>R${leader==='R'?' <span class="check">✓</span>':''}</td><td class="num">${Math.round(repVotes).toLocaleString()}</td><td class="num">${repShare.toFixed(1)}%</td></tr></tbody></table><div class="baseline-wikibox-foot"><div><b>${Math.round(boxTotal).toLocaleString()}</b> two-party votes</div><div>Margin: <b>${leader}+${Math.abs(margin).toFixed(1)}</b> · ${gap.toLocaleString()} votes</div></div><div class="baseline-wikibox-note">${note}</div></div></div>`}
function raceBox(x){const d=DATA[active],race=d.candidates.filter(c=>c.district===x.district).sort((a,b)=>b.votes-a.votes),total=race.reduce((s,c)=>s+c.votes,0),actualGap=race.length>1?race[0].votes-race[1].votes:total,actualMargin=100*actualGap/total,dem=race.find(c=>c.party==='D'),expectedDem=dem?dem.expectedMargin:0,expectedLeader=expectedDem>=0?'Democratic':'Republican',expectedGap=Math.round(total*Math.abs(expectedDem)/100),rows=race.map(c=>{const expectedShare=(100+c.expectedMargin)/2,expectedVotes=Math.round(total*expectedShare/100);return `<tr class="${c.winner?'winner-row':''}"><td class="party-cell ${c.party}"></td><td class="candidate-col">${esc(c.candidate)} ${c.party}${c.incumbent?' <small>(inc.)</small>':''}${c.winner?' <span class="check">✓</span>':''}</td><td class="num">${c.votes.toLocaleString()}</td><td class="num">${(100*c.votes/total).toFixed(1)}%</td><td class="num expected">${expectedVotes.toLocaleString()}</td><td class="num expected">${expectedShare.toFixed(1)}%</td></tr>`}).join('');return `<div class="racebox"><div class="racebox-head">${d.cycle} Alabama ${d.chamber==='house'?'House':'Senate'} District ${x.district}</div><div class="racebox-sub">General election · actual versus model baseline</div><table><thead><tr><th rowspan="2"></th><th rowspan="2">Candidate</th><th colspan="2" class="group-head">Actual</th><th colspan="2" class="group-head">Expected baseline</th></tr><tr><th class="num">Votes</th><th class="num">Share</th><th class="num">Votes</th><th class="num">Share</th></tr></thead><tbody>${rows}</tbody></table><div class="racebox-comparison"><div><span>Actual margin</span><b>${race[0].party==='D'?'Democratic':'Republican'} +${actualMargin.toFixed(1)} pts · ${actualGap.toLocaleString()} votes</b></div><div><span>Expected baseline margin</span><b>${expectedLeader} +${Math.abs(expectedDem).toFixed(1)} pts · ${expectedGap.toLocaleString()} votes</b></div><div><span>Two-party turnout</span><b>${total.toLocaleString()} votes</b></div></div>${baselineContext(x,total)}</div>`}
function detail(x){const box=$('#detail');if(!x){box.innerHTML='<div class="detail-empty">Select a colored district to inspect the race.</div>';return}const width=x.high-x.low,stable=width<=15,quality=x.quality==='standard source checks passed';box.innerHTML=`${raceBox(x)}<h3>${esc(x.candidate)}</h3><div class="party ${x.party}">${x.party==='D'?'Democratic':'Republican'} • District ${x.district}${x.incumbent?' • Incumbent':''}</div><div class="badges"><span class="badge">${x.percentile>=90?'Exceptional':x.percentile>=70?'Above average':x.percentile<=10?'Exceptional underperformance':'Typical range'}</span><span class="badge ${stable?'':'warn'}">${stable?'More stable':'High sensitivity'}</span><span class="badge ${quality?'':'warn'}">${quality?'Standard sources':'Source caution'}</span></div><div class="war-number">${fmt(x.war)}</div><div class="war-label">CMO points • ${x.percentile.toFixed(0)}th percentile</div><div class="distribution"><i style="left:${x.percentile}%"></i><div class="distribution-label"><span>Lowest</span><span>Median</span><span>Highest</span></div></div><div class="stat"><span>Cross-cycle stability band</span><b>${fmt(x.low)} to ${fmt(x.high)}</b></div><div class="stat"><span>Resource-adjusted CMO</span><b>${fmt(x.adjusted)}</b></div><div class="stat"><span>Same-cycle top-ticket margin</span><b>${fmt(x.cycleTopTicket)}</b></div><div class="decomp"><div class="decomp-title">Margin decomposition</div><div class="stat"><span>Model-expected candidate margin</span><b>${fmt(x.expectedMargin)}</b></div><div class="stat"><span>Candidate's actual margin</span><b>${fmt(x.margin)}</b></div><div class="stat"><span>Difference (CMO)</span><b>${fmt(x.war)}</b></div></div><div class="stat"><span>Votes</span><b>${x.votes.toLocaleString()}</b></div><div class="explain">${x.war>=0?'This candidate ran ahead of':'This candidate ran behind'} the cross-fitted model expectation by about <b>${Math.abs(x.war).toFixed(1)} points</b>.<br><br><b>Data note:</b> ${esc(x.quality)}</div>`}
function renderMap(){const d=DATA[active],map=$('#map'),tip=$('#tooltip');map.innerHTML='';map.setAttribute('aria-label',`${d.cycle} Alabama ${d.chamber} overperformance map`);d.paths.forEach(p=>{const x=d.winners[p.district],display=mapMetric(d,p.district),raw=mapRawValue(d,p.district),el=document.createElementNS('http://www.w3.org/2000/svg','path');el.setAttribute('d',p.path);el.setAttribute('fill',color(display));el.setAttribute('class','district'+(selected===p.district?' selected':''));el.setAttribute('tabindex','0');el.setAttribute('aria-label',x&&raw!=null?`District ${p.district}, ${raw>=0?'Democrat':'Republican'} overperformed by ${Math.abs(raw).toFixed(1)}, won by ${x.candidate}`:`District ${p.district}, benchmark unavailable`);el.onmouseenter=e=>{tip.style.display='block';tip.innerHTML=x&&raw!=null?`<b>District ${p.district}</b><br>${mapDescription()}<br>${raw>=0?'Democrat':'Republican'} +${Math.abs(raw).toFixed(1)} points${mapMode==='relative'?`<br>${x.percentile.toFixed(0)}th candidate percentile`:''}<br>Won by ${esc(x.candidate)}`:`District ${p.district}<br>${x?'Selected benchmark unavailable':'No eligible race'}`;moveTip(e)};el.onmousemove=moveTip;el.onmouseleave=()=>tip.style.display='none';el.onclick=()=>{selected=p.district;detail(x);renderMap()};el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();el.onclick()}};map.appendChild(el)});$('#map-title').textContent=`${d.cycle} Alabama ${d.chamber[0].toUpperCase()+d.chamber.slice(1)} overperformance`;$('#vintage').textContent='Boundaries: '+d.mapVintage;$('#map-sub').textContent=mapDescription();$('#legend-ticks').innerHTML=mapMode==='relative'?'<span>Strongest R</span><span>R-leaning</span><span>Median</span><span>D-leaning</span><span>Strongest D</span>':'<span>R +30</span><span>R +10</span><span>Even</span><span>D +10</span><span>D +30</span>'}
function moveTip(e){const t=$('#tooltip');t.style.left=(e.clientX+14)+'px';t.style.top=(e.clientY+14)+'px'}
function renderRows(){const d=DATA[active],q=$('#candidate-search').value.toLowerCase(),party=$('#party-filter').value,outcome=$('#outcome-filter').value,rows=[...d.candidates].filter(x=>(party==='all'||x.party===party)&&(outcome==='all'||(outcome==='winner'&&x.winner)||(outcome==='incumbent'&&x.incumbent))&&(!q||x.candidate.toLowerCase().includes(q)||String(x.district)===q)).sort((a,b)=>{let A=a[sortKey],B=b[sortKey];return(typeof A==='string'?A.localeCompare(B):A-B)*sortDir});$('#rows').innerHTML=rows.map(x=>`<tr><td>${x.district}</td><td class="cand"><i class="party-dot ${x.party}"></i>${esc(x.candidate)}${x.winner?' <small>✓</small>':''}</td><td class="num"><b>${fmt(x.war)}</b></td><td class="num">${x.percentile.toFixed(0)}th</td><td class="num">${fmt(x.adjusted)}</td><td class="num">${fmt(x.cycleTopTicket)}</td><td class="num">${fmt(x.expectedMargin)}</td><td class="num">${fmt(x.margin)}</td><td class="num">${x.votes.toLocaleString()}</td></tr>`).join('')}
function render(){makeControls();const d=DATA[active];renderMap();detail(d.winners[selected]);renderRows();$('#summary').innerHTML=`<div><b>${d.summary.races}</b><span>Contested districts</span></div><div><b>${d.summary.candidates}</b><span>Candidates scored</span></div><div><b>${fmt(d.summary.median)}</b><span>Median winner CMO</span></div><div><b>${esc(d.summary.top)}</b><span>Top winner</span></div>`}
document.querySelectorAll('th[data-sort]').forEach(th=>th.onclick=()=>{const k=th.dataset.sort;sortDir=sortKey===k?-sortDir:(k==='candidate'?1:-1);sortKey=k;renderRows()});['candidate-search','party-filter','outcome-filter'].forEach(id=>$('#'+id).oninput=renderRows);document.querySelectorAll('[data-map-mode]').forEach(button=>button.onclick=()=>{mapMode=button.dataset.mapMode;document.querySelectorAll('[data-map-mode]').forEach(b=>b.classList.toggle('active',b===button));renderMap()});render();</script></body></html>'''
    return template.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))


def build_methodology_page():
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Methodology for Jackson Hannan's Alabama Candidate Margin Overperformance model"><title>CMO methodology · Jackson Hannan</title><style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Libre+Franklin:wght@600;700;800&display=swap');
:root{--ink:#101828;--muted:#667085;--line:#e4e7ec;--soft:#f8fafc;--blue:#2878b5;--navy:#14253d}*{box-sizing:border-box}body{margin:0;color:var(--ink);font-family:Inter,Arial,sans-serif}header{background:var(--navy);color:#fff}.mast{max-width:1180px;margin:auto;padding:20px 28px;display:flex;align-items:center;justify-content:space-between;gap:22px}.brand{font:800 27px/1 'Libre Franklin';letter-spacing:-1px}.tag{margin-top:7px;color:#b9c5d4;font-size:10px;text-transform:uppercase;letter-spacing:1.5px}.nav{display:flex;flex-wrap:wrap;gap:20px}.nav a{color:#cbd5e1;text-decoration:none;font:600 12px 'Libre Franklin'}.nav a[aria-current=page],.nav a:hover{color:#fff}.shell{max-width:1040px;margin:auto;padding:52px 28px 90px}.hero{max-width:850px;margin-bottom:44px}.kicker{font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:1.3px;color:var(--blue)}h1{font:800 clamp(42px,7vw,76px)/.98 'Libre Franklin';letter-spacing:-3px;margin:10px 0 18px}.dek{font:21px/1.55 Georgia,serif;color:#344054}.chips{display:flex;flex-wrap:wrap;gap:8px}.chip{background:var(--soft);border:1px solid var(--line);padding:8px 11px;font-size:11px}.grid{display:grid;grid-template-columns:220px minmax(0,1fr);gap:50px;align-items:start}.toc{position:sticky;top:24px;border-top:3px solid var(--ink);padding-top:13px}.toc b{display:block;margin-bottom:9px;font-size:11px;text-transform:uppercase;letter-spacing:1px}.toc a{display:block;color:var(--muted);text-decoration:none;padding:5px 0;font-size:13px}.copy section{border-top:1px solid var(--line);padding:28px 0}.copy section:first-child{border-top:3px solid var(--ink)}h2{font:800 25px 'Libre Franklin';margin:0 0 13px}.copy p,.copy li{font:17px/1.72 Georgia,serif}.copy li+li{margin-top:7px}.formula{padding:16px 18px;border-left:4px solid var(--blue);background:var(--soft);font:14px/1.6 Consolas,monospace;margin:18px 0}.callout{background:var(--soft);border:1px solid var(--line);padding:17px 19px;margin:18px 0}.callout b{display:block;margin-bottom:5px}.links{display:flex;flex-wrap:wrap;gap:8px}.links a{border:1px solid var(--line);padding:9px 11px;color:var(--ink);font:700 10px 'Libre Franklin';text-decoration:none;text-transform:uppercase;letter-spacing:.5px}.links a:hover{background:var(--soft)}footer{background:var(--navy);color:#fff;padding:28px max(28px,calc((100vw - 984px)/2));font-size:12px}footer a{color:#cbd5e1}@media(max-width:760px){.mast{align-items:flex-start;flex-direction:column;padding:20px 18px}.shell{padding:38px 18px 65px}.grid{grid-template-columns:1fr}.toc{position:static}h1{letter-spacing:-2px}.nav{gap:12px}}
</style></head><body><header><div class="mast"><div><div class="brand">Jackson Hannan</div><div class="tag">Alabama legislative models</div></div><nav class="nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html">CMO</a><a href="methodology.html">Forecast methodology</a><a href="cmo-methodology.html" aria-current="page">CMO methodology</a><a href="https://github.com/JacksonAHannan">GitHub</a></nav></div></header>
<main class="shell"><div class="hero"><div class="kicker">Model documentation</div><h1>Candidate Margin Overperformance</h1><p class="dek">A retrospective index of how far an Alabama legislative candidate ran ahead of or behind a cross-fitted expectation for the district and election.</p><div class="chips"><span class="chip"><b>4 cycles:</b> 2010–2022</span><span class="chip"><b>218</b> contested D–R races</span><span class="chip"><b>Unit:</b> margin percentage points</span></div></div>
<div class="grid"><aside class="toc"><b>On this page</b><a href="#estimand">What CMO measures</a><a href="#data">Data and eligibility</a><a href="#baseline">Expected baseline</a><a href="#crossfit">Cross-fitting</a><a href="#versions">Two versions</a><a href="#validation">Validation</a><a href="#limits">Limitations</a><a href="#forecast">Forecast use</a></aside><article class="copy">
<section id="estimand"><h2>1. What CMO measures</h2><p>CMO is candidate margin overperformance, not literal wins above replacement and not a causal estimate of candidate quality. It compares the candidate’s observed two-party margin with a statistical expectation based on the political and demographic context of the race.</p><div class="formula">Democratic CMO = observed Democratic two-party margin − cross-fitted expected Democratic margin<br>Republican CMO = − Democratic CMO</div><p>A Democratic candidate who was expected to lose by 20 points but lost by 10 has a CMO of +10. The Republican in that race receives −10. Scores are therefore zero-sum within a race and cannot separately identify both candidates’ contributions.</p></section>
<section id="data"><h2>2. Data and eligibility</h2><p>The current historical model covers the 2010, 2014, 2018, and 2022 Alabama legislative general elections. A race is eligible only when both a Democratic and Republican candidate received votes. Uncontested races and races without both major parties remain in the source database but are not scored.</p><ul><li>Official and reconciled Alabama election returns provide candidates, parties, and votes.</li><li>Statewide-office and presidential precinct results provide district political context.</li><li>Census ACS data provide district demographics.</li><li>Candidate rosters and historical officeholding provide incumbency.</li><li>Alabama campaign-finance and FollowTheMoney records provide the optional resource layer.</li></ul><p>Precinct results are allocated to legislative districts with geography-based Census block/VTD crosswalks, independently of legislative contest turnout wherever authoritative geography permits.</p></section>
<section id="baseline"><h2>3. The expected baseline</h2><p>The model predicts Democratic legislative overperformance relative to a same-cycle statewide-office index. Predictors describe the district and election rather than simply restating the legislative outcome: party-specific incumbency, prior presidential performance and trend, demographics, chamber, cycle, and source-availability indicators. Numeric missing values are imputed within the modeling pipeline and explicit availability flags preserve missingness information.</p><div class="callout"><b>Why a regularized model?</b> Ridge regression shrinks unstable coefficients in a small, correlated dataset. It is intentionally modest: CMO is the unexplained remainder after the model establishes a reasonable contextual expectation.</div></section>
<section id="crossfit"><h2>4. Out-of-fold scoring</h2><p>The published headline score is out-of-fold. Each race is predicted by a model that did not train on that observation, and regularization is selected inside the training data. This avoids ranking candidates by an expectation fitted directly to their own result.</p><p>The model also withholds whole election cycles. Those leave-one-cycle-out results test how sensitive a score is to historical era changes. The displayed stability band summarizes this cross-cycle sensitivity; it is not labeled or interpreted as a 95% confidence interval.</p></section>
<section id="versions"><h2>5. Total and resource-adjusted CMO</h2><p><b>Total CMO</b>, the headline measure, excludes spending. It is closer to total campaign overperformance because fundraising may itself reflect candidate strength. <b>Resource-adjusted CMO</b> includes relative campaign spending and a finance-availability flag, asking how a candidate performed after accounting for observed resources.</p><p>Neither version supports a causal claim. Fundraising is endogenous, finance coverage is incomplete, and money raised is not the same as money efficiently deployed.</p></section>
<section id="validation"><h2>6. Validation and interpretation</h2><p>Validation emphasizes forward and grouped tests rather than random folds alone. The model reports random out-of-fold error, leave-one-cycle-out error, source coverage, exact vote-total checks, score symmetry, and sensitivity to specifications. Historical era shifts—especially 2014—make cycle holdouts materially harder than within-era prediction.</p><p>Large positive scores mean “far ahead of this model’s expectation,” not “personally caused this many points.” Rankings are most useful alongside the district result, expected baseline, top-of-ticket context, stability band, and source notes.</p></section>
<section id="limits"><h2>7. Important limitations</h2><ul><li>The effective sample is small: four cycles and 218 eligible races.</li><li>Scores are conditional on contested Democratic-versus-Republican races and do not represent all candidates or legislators.</li><li>The zero-sum construction attributes a race residual symmetrically to the two candidates.</li><li>Election eras, district boundaries, turnout, and source quality change across cycles.</li><li>Same-cycle context makes the historical index descriptive; it cannot be used unchanged before Election Day.</li><li>The stability band is a model-sensitivity diagnostic, not calibrated predictive uncertainty.</li></ul></section>
<section id="forecast"><h2>8. Relationship to the 2026 forecast</h2><p>The forecast and CMO are separate products. CMO describes historical overperformance. For 2026, prior CMO was tested as a shrinkage-adjusted candidate layer using exact candidate-and-party matches. It did not improve both the average and latest forward-cycle error under the declared promotion rule, so it does not alter the headline forecast and remains a scenario layer.</p><div class="links"><a href="cmo.html">Explore CMO</a><a href="index.html">View forecast</a><a href="methodology.html#candidate">Forecast candidate layer</a><a href="data/preliminary_cmo_candidates.csv">Candidate data</a></div></section>
</article></div></main><footer>Model and analysis by Jackson Hannan · <a href="https://github.com/JacksonAHannan">GitHub</a> · <a href="https://substack.com/@jacksonhannan">Substack</a></footer></body></html>'''


if __name__ == "__main__":
    data = load_data()
    rendered = build_page(data)
    OUTPUT.write_text(rendered, encoding="utf-8")
    LEGACY_OUTPUT.write_text(rendered, encoding="utf-8")
    SITE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SITE_OUTPUT.write_text(rendered, encoding="utf-8")
    SITE_METHODOLOGY_OUTPUT.write_text(build_methodology_page(), encoding="utf-8")
    site_data = SITE_OUTPUT.parent / "data"
    site_data.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WAR / "preliminary_cmo_candidates.csv", site_data / "preliminary_cmo_candidates.csv")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
