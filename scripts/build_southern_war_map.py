#!/usr/bin/env python3
"""Build the public 2016-2022 Southern legislative WAR explorer."""
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


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "data/processed/war/southern_historical_war_v1"
GEOGRAPHY = ROOT / "data/processed/source_audits/southern_legislative_geography_manifest.csv"
DOCS_DATA = ROOT / "docs/data"
PAYLOAD = DOCS_DATA / "southern_war_map_payload.json"
SITE = ROOT / "docs/southern-war.html"
METHOD = ROOT / "docs/southern-war-methodology.html"
ARTIFACT = ROOT / "artifacts/site/southern-war.html"
STATE_NAMES = {
    "AL": "Alabama", "AR": "Arkansas", "FL": "Florida", "GA": "Georgia",
    "KY": "Kentucky", "LA": "Louisiana", "MO": "Missouri", "MS": "Mississippi",
    "NC": "North Carolina", "OK": "Oklahoma", "SC": "South Carolina",
    "TN": "Tennessee", "TX": "Texas", "VA": "Virginia",
}


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


def path_for_geometry(geom, bounds, width=680, height=620, pad=14) -> str:
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


def build_payload() -> dict[str, object]:
    races = read_csv(MODEL / "race_war.csv")
    candidates = read_csv(MODEL / "candidate_cycle_war.csv")
    coverage = read_csv(MODEL / "coverage.csv")
    geometry_manifest = read_csv(GEOGRAPHY)
    model_manifest = json.loads((MODEL / "manifest.json").read_text(encoding="utf-8"))
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
    slices = {}
    total_features = 0
    for source in geometry_manifest:
        state, cycle, chamber = source["state_code"], int(source["cycle"]), source["chamber"]
        layer = "SLDLST" if chamber == "lower" else "SLDUST"
        path = ROOT / source["local_path"]
        frame = gpd.read_file(f"zip://{path.resolve()}")
        if layer not in frame.columns:
            raise ValueError(f"Missing {layer} in {path}")
        frame["district"] = frame[layer].map(normalized_district)
        frame = frame[frame.district.str.fullmatch(r"\d+")].copy()
        if frame.empty or frame.district.duplicated().any():
            raise ValueError(f"Census geometry district grain failed for {state}/{cycle}/{chamber}")
        frame = frame.to_crs(5070)
        frame["geometry"] = frame.geometry.simplify(1800, preserve_topology=True)
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
            public_races[district] = {
                "district": district,
                "demCandidate": dem["candidate_name"], "repCandidate": rep["candidate_name"],
                "demVotes": integer(row["dem_votes"]), "repVotes": integer(row["rep_votes"]),
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
    if len(slices) != 90:
        raise ValueError("Public Southern WAR payload must contain all 90 scheduled slices")
    if sum(len(value["races"]) for value in slices.values()) != len(races):
        raise ValueError("Public race payload lost a scored race")
    return {
        "runId": model_manifest["historical_war_run_id"],
        "generatedAt": model_manifest["generated_at_utc"],
        "publicationProvenance": {
            "builderSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "modelManifestSha256": hashlib.sha256((MODEL / "manifest.json").read_bytes()).hexdigest(),
            "geometryManifestSha256": hashlib.sha256(GEOGRAPHY.read_bytes()).hexdigest(),
            "configuration": "election-year Census geometry simplified at 1,800 meters in EPSG:5070",
        },
        "states": STATE_NAMES, "slices": slices,
        "diagnostics": {
            "scheduledSlices": len(slices), "geometryFeatures": total_features,
            "scoredRaces": len(races), "candidateRows": len(candidates),
            "financeCompleteRaces": model_manifest["diagnostics"]["finance_complete_races"],
        },
        "financeCoverageByState": model_manifest["finance_coverage_by_state"],
    }


def page_html() -> str:
    return r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Interactive WAR map for Southern state legislative elections, 2016 through 2022"><title>Southern legislative WAR map</title><style>
*{box-sizing:border-box}:root{--ink:#202a32;--muted:#60717d;--line:#aab9c2;--paper:#f4f8fa;--panel:#fff;--accent:#743b42;--dem:#3578a8;--rep:#a34850}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.5 Arial,sans-serif}header nav,main{width:min(1220px,calc(100% - 36px));margin:auto}header{background:#fff;border-bottom:1px solid var(--line)}header nav{display:flex;gap:18px;padding:17px 0}a{color:var(--accent);font-weight:700}.hero{padding:54px 0 32px;max-width:900px}.kicker{text-transform:uppercase;letter-spacing:.08em;color:var(--accent);font-weight:700}.hero h1{font:700 clamp(40px,6vw,68px)/.98 Arial,sans-serif;letter-spacing:-2px;margin:10px 0 18px}.hero p{max-width:760px;font:19px/1.55 Georgia,serif}.formula{border-left:4px solid var(--accent);padding:12px 17px;background:#e8f0f4}.controls{display:grid;grid-template-columns:repeat(3,minmax(150px,1fr));gap:12px;padding:18px;border:1px solid var(--line);background:var(--panel)}label{display:grid;gap:6px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}select{width:100%;padding:10px;border:1px solid var(--line);background:#fff;color:var(--ink)}.workspace{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(320px,.75fr);border:1px solid var(--line);border-top:0;background:var(--panel);min-height:690px}.map-panel{padding:24px;border-right:1px solid var(--line)}.map-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.map-head h2{margin:0}.map-head p{margin:5px 0;color:var(--muted)}.metric-tabs{display:flex;gap:5px;flex-wrap:wrap}.metric-tabs button{padding:8px 10px;border:1px solid var(--line);background:#fff;cursor:pointer}.metric-tabs button[aria-pressed=true]{background:var(--accent);color:#fff}.map-wrap{max-width:680px;margin:18px auto 0}.map-wrap svg{display:block;width:100%;height:auto}.district{stroke:#fff;stroke-width:1;vector-effect:non-scaling-stroke;cursor:pointer}.district:hover,.district:focus,.district.selected{stroke:#15191c;stroke-width:2.5}.legend{margin:10px auto;max-width:520px}.gradient{height:12px;background:linear-gradient(90deg,var(--rep),#edf1f3,var(--dem));border:1px solid var(--line)}.legend-row{display:flex;justify-content:space-between;color:var(--muted);font-size:12px}.missing-key{display:flex;gap:8px;align-items:center;margin-top:8px;color:var(--muted);font-size:12px}.missing-key i{width:16px;height:12px;background:#d5dce0;border:1px solid #b7c2c8}.detail{padding:26px;background:#f8fbfc}.detail h2{margin:0 0 3px}.detail .sub{color:var(--muted);margin-bottom:18px}.score{padding:18px 0;border-block:1px solid var(--line)}.score b{display:block;font-size:42px;line-height:1}.score span{color:var(--muted)}.math{display:grid;grid-template-columns:1fr auto;gap:8px;margin:20px 0}.math div{display:contents}.math b{text-align:right}.candidate{display:grid;grid-template-columns:12px 1fr auto;gap:10px;align-items:center;padding:10px 0;border-top:1px solid var(--line)}.candidate i{width:10px;height:28px}.candidate i.D{background:var(--dem)}.candidate i.R{background:var(--rep)}.candidate small{display:block;color:var(--muted)}.finance{margin-top:20px;padding:14px;background:#edf3f6}.warning{border-left:4px solid #a87928;background:#fff4d8;padding:12px 14px;margin:16px 0}.summary{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-top:0}.summary div{padding:18px;border-right:1px solid var(--line)}.summary div:last-child{border:0}.summary b{display:block;font-size:24px}.summary span{color:var(--muted)}.rankings,.method{padding:48px 0}.rankings h2,.method h2{font-size:30px}.table-wrap{overflow:auto;border-top:3px solid var(--accent)}table{border-collapse:collapse;width:100%;background:#fff}th,td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}th{background:#eef3f5;font-size:12px;text-transform:uppercase}td.num,th.num{text-align:right}.war.D{color:#245f89;font-weight:700}.war.R{color:#8d343d;font-weight:700}.method{border-top:1px solid var(--line);max-width:880px}.method p,.method li{font:16px/1.65 Georgia,serif}.loading{padding:40px;color:var(--muted)}@media(max-width:850px){.workspace{grid-template-columns:1fr}.map-panel{border-right:0;border-bottom:1px solid var(--line)}.summary{grid-template-columns:1fr 1fr}.summary div:nth-child(2){border-right:0}.controls{grid-template-columns:1fr}.map-head{display:block}.metric-tabs{margin-top:12px}}@media(max-width:520px){.hero{padding-top:35px}.summary{grid-template-columns:1fr}.summary div{border-right:0}.workspace{min-height:0}.map-panel,.detail{padding:18px}.candidate{grid-template-columns:10px 1fr}}
</style></head><body><header><nav><a href="index.html">Forecast</a><a href="cmo.html">Alabama WAR</a><a href="southern-war.html" aria-current="page">Southern WAR</a><a href="methods.html">Methods</a></nav></header><main><section class="hero"><div class="kicker">14 states · regular elections · 2016–2022</div><h1>Southern legislative WAR</h1><p>Race-level overperformance for state House and Senate contests, evaluated against the structural margin expected from the ticket, incumbency, chamber, state, and the model’s decaying down-ballot lag.</p><div class="formula"><b>WAR = actual legislative-minus-ticket gap − fitted structural expected gap.</b> Positive values favor the Democrat’s performance; negative values favor the Republican’s.</div></section><section class="controls" aria-label="Map filters"><label>State<select id="state"></select></label><label>Election<select id="cycle"></select></label><label>Chamber<select id="chamber"></select></label></section><section class="workspace"><div class="map-panel"><div class="map-head"><div><h2 id="mapTitle">Loading map…</h2><p id="mapSub"></p></div><div class="metric-tabs" aria-label="Mapped measure"><button data-metric="war" aria-pressed="true">WAR</button><button data-metric="rawGap" aria-pressed="false">Raw ticket gap</button><button data-metric="structuralGap" aria-pressed="false">Structural expectation</button></div></div><div class="map-wrap"><svg id="map" viewBox="0 0 680 620" role="group" aria-label="State legislative district map"></svg><div class="legend"><div class="gradient"></div><div class="legend-row"><span>R+20 or more</span><span>Even</span><span>D+20 or more</span></div><div class="missing-key"><i></i><span>No eligible D–R WAR score; missing is not zero</span></div></div></div></div><aside class="detail" id="detail"><div class="loading">Choose a colored district to inspect its race.</div></aside></section><section class="summary" id="summary"></section><section class="rankings"><h2>Scored races in this map</h2><div class="table-wrap"><table><thead><tr><th>District</th><th>Democrat</th><th>Republican</th><th class="num">Raw gap</th><th class="num">Expected gap</th><th class="num">WAR</th><th>Finance</th></tr></thead><tbody id="rows"></tbody></table></div></section><section class="method"><h2>What is—and is not—in the score</h2><p>Post-2016 races retain the published same-cycle Southern WAR residual. The 2016 map applies the selected post-2016 model backward without fitting on 2016 outcomes. The map includes every district outline, but only strict observed D–R contests receive a score.</p><p>Fundraising is shown when both major-party candidates have accepted source observations. It does not change WAR: the viability-gated finance specification failed its prespecified nested time-forward test. Missouri and Mississippi have the largest finance gaps in this warehouse run; missing amounts are shown as unavailable, never as zero.</p><p><a href="southern-war-methodology.html">Read the complete methodology and coverage notes</a> or <a href="data/southern_historical_war_v1_race_war.csv">download race WAR</a>.</p></section></main><script>
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];let DATA,active,metric='war',selected=null;const fmt=v=>v==null?'—':`${v>=0?'+':''}${Number(v).toFixed(1)}`,money=v=>v==null?'Unavailable':Number(v).toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0});function color(v){if(v==null)return'#d5dce0';const x=Math.max(-20,Math.min(20,v))/20;if(x<0){const t=1+x;return mix('#a34850','#edf1f3',t)}return mix('#edf1f3','#3578a8',x)}function mix(a,b,t){const A=a.match(/\w\w/g).map(x=>parseInt(x,16)),B=b.match(/\w\w/g).map(x=>parseInt(x,16));return'#'+A.map((x,i)=>Math.round(x+(B[i]-x)*t).toString(16).padStart(2,'0')).join('')}function options(select,values,label){select.innerHTML=values.map(v=>`<option value="${v}">${label(v)}</option>`).join('')}function available(state){return Object.values(DATA.slices).filter(x=>x.state===state)}function syncControls(initial=false){const state=$('#state').value||'AL',slices=available(state),cycles=[...new Set(slices.map(x=>x.cycle))].sort((a,b)=>a-b);options($('#cycle'),cycles,String);if(initial&&cycles.includes(2022))$('#cycle').value='2022';else if(!cycles.includes(Number($('#cycle').value)))$('#cycle').value=String(cycles.at(-1));const cycle=Number($('#cycle').value),chambers=slices.filter(x=>x.cycle===cycle).map(x=>x.chamber);options($('#chamber'),chambers,x=>x==='lower'?'House':'Senate');if(!chambers.includes($('#chamber').value))$('#chamber').value=chambers[0];active=DATA.slices[`${state}-${cycle}-${$('#chamber').value}`];selected=null;draw()}function raceValue(r){return r?r[metric]:null}function draw(){if(!active)return;$('#mapTitle').textContent=`${active.stateName} ${active.cycle} ${active.chamber==='lower'?'House':'Senate'}`;$('#mapSub').textContent=`${active.censusVintage} · ${active.districts} district outlines`;const svg=$('#map');svg.innerHTML=active.features.map(f=>{const r=active.races[f.district],v=raceValue(r),label=r?`District ${f.district}, ${metric==='war'?'WAR':metric==='rawGap'?'raw ticket gap':'structural expectation'} ${fmt(v)}`:`District ${f.district}, no eligible D-R WAR score`;return`<path class="district${selected===f.district?' selected':''}" data-district="${f.district}" d="${f.path}" fill="${color(v)}" tabindex="0" role="button" aria-label="${label}"><title>${label}</title></path>`}).join('');$$('.district').forEach(p=>{const open=()=>{selected=p.dataset.district;detail();draw()};p.addEventListener('click',open);p.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}})});summary();table();if(selected)detail();else{const top=Object.values(active.races).sort((a,b)=>Math.abs(b.war)-Math.abs(a.war))[0];if(top){selected=top.district;detail();$$('.district').find(p=>p.dataset.district===selected)?.classList.add('selected')}}}function summary(){const c=active.coverage,rate=c.scored?100*c.financeComplete/c.scored:0;$('#summary').innerHTML=`<div><b>${active.districts}</b><span>district outlines</span></div><div><b>${c.scored}</b><span>strict D–R race scores</span></div><div><b>${c.financeComplete}</b><span>finance-complete races (${rate.toFixed(0)}%)</span></div><div><b>${c.lagContext}</b><span>races with validated lag context</span></div>`}function detail(){const r=active.races[selected],el=$('#detail');if(!r){el.innerHTML=`<h2>District ${selected}</h2><div class="sub">${active.stateName} ${active.cycle} ${active.chamber==='lower'?'House':'Senate'}</div><div class="warning"><b>No eligible WAR score.</b><br>This district did not have a strict observed D–R contest with accepted baseline and incumbency context. Missing WAR is not zero.</div><p>Boundary source: <a href="${active.sourceUrl}">U.S. Census Bureau election-year cartographic boundary</a>.</p>`;return}const leader=r.war>=0?'Democratic':'Republican',scope=r.scope.includes('backcast')?'2016 post-2016-model backcast':'Published same-cycle residual',finance=r.financeComplete?`<b>Fundraising overlay</b><div class="candidate"><i class="D"></i><span>${r.demCandidate}</span><strong>${money(r.demFundraising)}</strong></div><div class="candidate"><i class="R"></i><span>${r.repCandidate}</span><strong>${money(r.repFundraising)}</strong></div><small>Descriptive only; fundraising does not enter WAR.</small>`:`<b>Fundraising unavailable</b><p>Both major-party observations and identities are not complete for this race. No missing amount is treated as zero.</p>`;el.innerHTML=`<h2>District ${r.district}</h2><div class="sub">${active.stateName} ${active.cycle} ${active.chamber==='lower'?'House':'Senate'} · ${scope}</div>${r.scope.includes('backcast')?'<div class="warning"><b>Backcast.</b> The structural relationship was fit only on races after 2016 and applied backward here.</div>':''}<div class="score"><b>${fmt(r.war)}</b><span>${leader} WAR, margin points</span></div><div class="math"><div><span>Actual legislative margin</span><b>${fmt(r.legislativeMargin)}</b></div><div><span>Ticket baseline</span><b>${fmt(r.ticketMargin)}</b></div><div><span>Raw legislative-ticket gap</span><b>${fmt(r.rawGap)}</b></div><div><span>Fitted structural gap</span><b>${fmt(r.structuralGap)}</b></div></div><div class="candidate"><i class="D"></i><span><b>${r.demCandidate}</b><small>${r.demIncumbent?'Incumbent · ':''}${r.demVotes.toLocaleString()} votes</small></span><strong>${fmt(r.war)}</strong></div><div class="candidate"><i class="R"></i><span><b>${r.repCandidate}</b><small>${r.repIncumbent?'Incumbent · ':''}${r.repVotes.toLocaleString()} votes</small></span><strong>${fmt(-r.war)}</strong></div><div class="finance">${finance}</div><p><small>Baseline: ${r.baselineOffice}. Warehouse plan label: ${r.warehousePlan}; ${r.warehouseGeography}. Display boundary: ${active.censusVintage}.</small></p>`}function table(){const races=Object.values(active.races).sort((a,b)=>Math.abs(b.war)-Math.abs(a.war));$('#rows').innerHTML=races.map(r=>`<tr data-district="${r.district}"><td><button class="row-link">${active.chamber==='lower'?'House':'Senate'} ${r.district}</button></td><td>${r.demCandidate}</td><td>${r.repCandidate}</td><td class="num">${fmt(r.rawGap)}</td><td class="num">${fmt(r.structuralGap)}</td><td class="num war ${r.war>=0?'D':'R'}">${fmt(r.war)}</td><td>${r.financeComplete?'Complete':'Unavailable'}</td></tr>`).join('');$$('.row-link').forEach(b=>b.addEventListener('click',()=>{selected=b.closest('tr').dataset.district;detail();draw();$('#detail').scrollIntoView({behavior:'smooth',block:'start'})}))}async function init(){const response=await fetch('data/southern_war_map_payload.json');if(!response.ok)throw new Error(`Payload HTTP ${response.status}`);DATA=await response.json();options($('#state'),Object.keys(DATA.states),x=>DATA.states[x]);$('#state').value='AL';$('#state').addEventListener('change',()=>syncControls(true));$('#cycle').addEventListener('change',()=>syncControls());$('#chamber').addEventListener('change',()=>syncControls());$$('[data-metric]').forEach(b=>b.addEventListener('click',()=>{metric=b.dataset.metric;$$('[data-metric]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));draw()}));syncControls(true)}init().catch(error=>{$('#mapTitle').textContent='Map failed to load';$('#detail').textContent=error.message});
</script></body></html>'''


def methodology_html(run_id: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Southern WAR methodology</title><style>body{{margin:0;background:#f4f8fa;color:#222;font:16px/1.65 Arial,sans-serif}}header nav,main{{width:min(900px,calc(100% - 36px));margin:auto}}header{{background:#fff;border-bottom:1px solid #aab9c2}}header nav{{display:flex;gap:18px;padding:17px 0}}a{{color:#743b42;font-weight:700}}h1{{font-size:52px;line-height:1;margin:58px 0 18px}}section{{padding:8px 0 24px;border-bottom:1px solid #aab9c2}}.formula,.warning{{padding:15px 18px;border-left:4px solid #743b42;background:#e7eff3}}.warning{{border-color:#a87928;background:#fff4d8}}table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #aab9c2;padding:9px;text-align:left}}</style></head><body><header><nav><a href="index.html">Forecast</a><a href="cmo.html">Alabama WAR</a><a href="southern-war.html" aria-current="page">Southern WAR</a><a href="methods.html">Methods</a></nav></header><main><h1>Southern WAR methodology</h1><p>Construction, coverage, geography, finance, and interpretation for the 2016–2022 Southern state-legislative WAR map.</p><section><h2>1. Estimand</h2><div class="formula">Raw gap = Democratic legislative margin − Democratic ticket margin<br>Race WAR = raw gap − fitted structural expected gap<br>Democratic WAR = race WAR; Republican WAR = −race WAR</div><p>The score is a race differential, not a pooled candidate-career effect. A residual cannot uniquely divide credit between candidate strength, opponent weakness, and omitted local conditions.</p></section><section><h2>2. Structural model</h2><p>The selected <code>decaying_lag</code> ridge specification (alpha 100) models the ordinary legislative-ticket gap using ticket margin and its square, state, chamber, baseline office family, election timing, symmetric incumbency, prior presidential margin, ticket change, and a ticket-change-by-years interaction. Specification selection used earlier-cycle forward validation.</p></section><section><h2>3. Historical scoring</h2><p>Races after 2016 preserve the published Southern WAR v3 same-cycle fitted residual. The 620 strict 2016 races are a backward application of the selected model fitted only on strict races after 2016.</p><div class="warning"><b>2016 extrapolation.</b> Those scores compare 2016 results with a modern post-2016 structural relationship. No 2016 outcome enters model fitting, but the result is descriptive rather than a contemporaneous fit.</div></section><section><h2>4. Coverage and missing races</h2><p>The explorer contains all 90 scheduled state/cycle/chamber map slices and every district outline in the exact election-year Census cartographic-boundary file. Only strict observed D–R regular contests receive WAR. Uncontested races, non-D/R races, research-only context, and missing outcomes remain unscored; gray never means WAR zero.</p><p>Louisiana, Mississippi, and Virginia retain their actual odd-year election schedules. South Carolina’s staggered Senate schedule is also retained.</p></section><section><h2>5. Fundraising</h2><p>Fundraising is displayed only when both major-party observations and both candidate identities are complete. The model tested viability gates at every $10,000 from $10,000 through $100,000, plus $250,000. Finance failed the prespecified nested time-forward promotion gate, so it does not enter headline WAR.</p><p>Missouri has no usable finance in the warehouse run underlying this map, and Mississippi has very limited electronic coverage. Other states have residual race-level gaps. Missing finance is unavailable, not zero.</p></section><section><h2>6. Geography</h2><p>Each slice uses the U.S. Census Bureau’s cartographic boundary released for that election year and chamber. A scored race must match one unique district feature in the exact state/year/chamber file. Census geometry is display evidence; it does not overwrite the warehouse’s provider-reported plan-vintage label.</p></section><section><h2>7. Downloads</h2><p><a href="data/southern_historical_war_v1_race_war.csv">Race WAR</a> · <a href="data/southern_historical_war_v1_candidate_cycle_war.csv">Candidate orientations</a> · <a href="data/southern_historical_war_v1_coverage.csv">Coverage</a> · <a href="data/southern_historical_war_v1_manifest.json">Run manifest</a> · <a href="data/southern_legislative_geography_manifest.csv">Geometry sources</a></p><p><small>Run {html.escape(run_id)}</small></p></section></main></body></html>'''


def main() -> None:
    payload = build_payload()
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    PAYLOAD.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    copies = {
        MODEL / "race_war.csv": DOCS_DATA / "southern_historical_war_v1_race_war.csv",
        MODEL / "candidate_cycle_war.csv": DOCS_DATA / "southern_historical_war_v1_candidate_cycle_war.csv",
        MODEL / "coverage.csv": DOCS_DATA / "southern_historical_war_v1_coverage.csv",
        MODEL / "manifest.json": DOCS_DATA / "southern_historical_war_v1_manifest.json",
        GEOGRAPHY: DOCS_DATA / "southern_legislative_geography_manifest.csv",
    }
    for source, target in copies.items():
        shutil.copy2(source, target)
    page = page_html()
    method = methodology_html(str(payload["runId"]))
    SITE.write_text(page, encoding="utf-8")
    METHOD.write_text(method, encoding="utf-8")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(page, encoding="utf-8")
    digest = hashlib.sha256(PAYLOAD.read_bytes()).hexdigest()
    print(f"Southern WAR map: slices=90 races={payload['diagnostics']['scoredRaces']:,} payload_sha256={digest}")


if __name__ == "__main__":
    main()
