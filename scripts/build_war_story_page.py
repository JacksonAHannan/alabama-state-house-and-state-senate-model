"""Build a self-contained, Split Ticket-inspired Alabama legislative WAR page."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path

import geopandas as gpd
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
MAPS = ROOT / "Results and Shapefiles"
OUTPUT = ROOT / "Alabama Legislative Wins Above Replacement (WAR).html"

MAP_FILES = {
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
    with (WAR / "preliminary_war_candidates.csv").open(encoding="utf-8-sig", newline="") as f:
        candidates = list(csv.DictReader(f))
    with (WAR / "preliminary_war_races.csv").open(encoding="utf-8-sig", newline="") as f:
        races = list(csv.DictReader(f))
    with (WAR / "wikipedia_legislative_candidates.csv").open(encoding="utf-8-sig", newline="") as f:
        public_candidates = list(csv.DictReader(f))
    with (WAR / "2022_wikipedia_vote_validation.csv").open(encoding="utf-8-sig", newline="") as f:
        validated_2022_names = list(csv.DictReader(f))

    public_names = {
        (int(r["cycle"]), r["chamber"], int(r["district"]), r["party"], int(number(r["votes_wikipedia"], 0))): r["candidate"]
        for r in public_candidates
    }
    public_names.update({
        (int(r["cycle"]), r["chamber"], int(r["district"]), r["party"], int(number(r["votes_modeled"], 0))): r["candidate_modeled"]
        for r in validated_2022_names
    })
    race_index = {(int(r["cycle"]), r["chamber"], int(r["district"])): r for r in races}
    groups = {}
    for row in candidates:
        cycle, chamber, district = int(row["cycle"]), row["chamber"], int(row["district"])
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
            "war": round(number(row["candidate_war_final"], 0), 2),
            "low": round(number(row["candidate_war_final_ci_low"], 0), 2),
            "high": round(number(row["candidate_war_final_ci_high"], 0), 2),
            "raw": round((number(race["raw_overperformance"], 0) if row["party"] == "D" else -number(race["raw_overperformance"], 0)), 2),
            "expected": round((number(race["expected_raw_overperformance_final"], 0) if row["party"] == "D" else -number(race["expected_raw_overperformance_final"], 0)), 2),
            "margin": round((number(race["legislative_dem_margin"], 0) if row["party"] == "D" else -number(race["legislative_dem_margin"], 0)), 2),
            "cycleTopTicket": round((number(race["statewide_index_margin"], 0) if row["party"] == "D" else -number(race["statewide_index_margin"], 0)), 2),
            "priorPres": round((number(race["prior_pres_dem_margin"], 0) if row["party"] == "D" else -number(race["prior_pres_dem_margin"], 0)), 2),
            "expectedMargin": round((number(race["legislative_dem_margin"], 0) - number(race["war_residual_final"], 0) if row["party"] == "D" else -number(race["legislative_dem_margin"], 0) + number(race["war_residual_final"], 0)), 2),
            "winner": row["party"] == race["winner_party"],
            "incumbent": candidate_name == race["incumbent_candidate"],
        }
        groups.setdefault((cycle, chamber), []).append(item)

    payload = {}
    for (cycle, chamber), items in groups.items():
        frame = gpd.read_file(f"zip://{(MAPS / MAP_FILES[(cycle, chamber)]).resolve()}").to_crs(4326)
        frame["district"] = frame.apply(lambda r: district_id(r, cycle, chamber), axis=1)
        frame["geometry"] = frame.geometry.simplify(0.007, preserve_topology=True)
        bounds = frame.total_bounds
        paths = [{"district": int(r.district), "path": path_for_geometry(r.geometry, bounds)} for _, r in frame.iterrows()]
        winners = {x["district"]: x for x in items if x["winner"]}
        scored = [x["war"] for x in winners.values()]
        districts_in_race = sorted({x["district"] for x in items})
        dem_war = {
            d: round(number(race_index[(cycle, chamber, d)]["war_residual_final"], 0), 2)
            for d in districts_in_race
        }
        payload[f"{cycle}-{chamber}"] = {
            "cycle": cycle,
            "chamber": chamber,
            "mapVintage": "2012 enacted plan" if cycle == 2014 else "2017 enacted plan" if cycle == 2018 else "2021 enacted plan",
            "paths": paths,
            "candidates": sorted(items, key=lambda x: x["war"], reverse=True),
            "winners": winners,
            "demWar": dem_war,
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
<title>Alabama Legislative Wins Above Replacement (WAR)</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Libre+Franklin:wght@500;600;700;800&display=swap');
:root{--ink:#17191c;--muted:#666c73;--line:#d8dadd;--soft:#f4f4f2;--red:#d34b45;--blue:#3d77a8;--navy:#18263b}
*{box-sizing:border-box} body{margin:0;color:var(--ink);background:#fff;font-family:Inter,Arial,sans-serif;line-height:1.55}
header{border-bottom:1px solid var(--line);background:#fff}.mast{max-width:1180px;margin:auto;padding:26px 28px 22px;display:flex;align-items:end;justify-content:space-between;gap:24px}.brand{font:800 34px/1 'Libre Franklin',sans-serif;letter-spacing:-1.6px}.tag{font-size:12px;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);margin-top:8px}.nav{display:flex;gap:28px;font:600 13px 'Libre Franklin',sans-serif}.nav span:last-child{color:var(--red)}
main{max-width:1180px;margin:auto;padding:68px 28px 90px}.story-head{max-width:820px}.story-head h1{font:800 clamp(42px,6vw,78px)/.98 'Libre Franklin',sans-serif;letter-spacing:-3.2px;margin:0 0 28px}.dek{font:400 20px/1.5 Georgia,serif;color:#45484d;max-width:760px}.byline{border-top:1px solid var(--line);margin-top:34px;padding-top:18px;font:600 12px 'Libre Franklin';text-transform:uppercase;letter-spacing:1.2px}.byline b{color:var(--red)}
.intro{max-width:750px;margin:58px 0 54px;font:18px/1.75 Georgia,serif}.intro p{margin:0 0 18px}.intro strong{font-family:Inter,sans-serif;font-size:16px}
.explorer{border-top:4px solid var(--ink);padding-top:22px}.explorer-top{display:flex;justify-content:space-between;align-items:end;gap:24px;margin-bottom:20px}.explorer h2{font:800 30px 'Libre Franklin';margin:0}.note{font-size:12px;color:var(--muted)}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 28px}.controls button{border:1px solid #b7bbc0;background:#fff;padding:10px 16px;font:700 12px 'Libre Franklin';text-transform:uppercase;letter-spacing:.7px;cursor:pointer}.controls button:hover,.controls button:focus-visible{border-color:var(--ink)}.controls button.active{background:var(--navy);border-color:var(--navy);color:#fff}
.dashboard{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(330px,.85fr);border:1px solid var(--line);min-height:720px}.map-panel{padding:28px 30px;border-right:1px solid var(--line);position:relative}.map-title{font:700 20px 'Libre Franklin';margin:0}.map-sub{font-size:12px;color:var(--muted);margin:5px 0 4px}.map-wrap{max-width:610px;margin:12px auto 0}.map-wrap svg{width:100%;height:auto;display:block}.district{stroke:#fff;stroke-width:1.1;vector-effect:non-scaling-stroke;cursor:pointer;transition:filter .12s,stroke-width .12s}.district:hover,.district.selected{stroke:#17191c;stroke-width:2.3;filter:brightness(.96)}
.legend{max-width:430px;margin:10px auto 0}.gradient{height:10px;background:linear-gradient(90deg,#d34b45,#e8a19d,#f2f1ed,#9bbcd4,#3d77a8)}.ticks{display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-top:5px}
.detail{padding:30px 28px;display:flex;flex-direction:column}.detail-empty{margin:auto;color:var(--muted);font:16px Georgia,serif;text-align:center;max-width:260px}.detail h3{font:800 25px 'Libre Franklin';margin:0}.party{font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:1px;margin:6px 0 22px}.party.D{color:var(--blue)}.party.R{color:var(--red)}.war-number{font:800 62px/.9 'Libre Franklin';letter-spacing:-3px}.war-label{font-size:11px;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted);margin:9px 0 24px}.stat{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:11px 0;font-size:13px}.stat b{font-family:'Libre Franklin'}.explain{background:var(--soft);padding:15px 16px;margin-top:16px;font:13px/1.55 Georgia,serif}
.summary{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-top:0}.summary div{padding:17px 20px;border-right:1px solid var(--line)}.summary div:last-child{border:0}.summary b{display:block;font:800 21px 'Libre Franklin'}.summary span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.8px}
.rankings{margin-top:62px}.rankings h2{font:800 30px 'Libre Franklin';margin:0 0 8px}.table-wrap{overflow:auto;border-top:3px solid var(--ink);margin-top:18px;max-height:650px}table{width:100%;border-collapse:collapse;font-size:13px}thead{position:sticky;top:0;background:#fff;z-index:1}th{text-align:left;font:700 11px 'Libre Franklin';text-transform:uppercase;letter-spacing:.8px;border-bottom:1px solid var(--ink);padding:13px 10px;cursor:pointer}td{border-bottom:1px solid var(--line);padding:11px 10px}td.num{text-align:right;font-variant-numeric:tabular-nums}.cand{font-weight:700}.party-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px}.party-dot.D{background:var(--blue)}.party-dot.R{background:var(--red)}
.method{max-width:760px;margin:72px 0 0}.method h2{font:800 30px 'Libre Franklin';border-top:4px solid var(--ink);padding-top:18px}.method p{font:17px/1.75 Georgia,serif}.source{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:15px;margin-top:28px}
.tooltip{position:fixed;z-index:5;pointer-events:none;background:#15181c;color:#fff;padding:9px 11px;font-size:11px;box-shadow:0 4px 16px #0003;display:none}
@media(max-width:780px){.nav{display:none}.brand{font-size:27px}main{padding:44px 18px}.story-head h1{letter-spacing:-2px}.dashboard{grid-template-columns:1fr}.map-panel{border-right:0;border-bottom:1px solid var(--line);padding:22px 16px}.summary{grid-template-columns:1fr 1fr}.summary div:nth-child(2){border-right:0}.summary div:nth-child(-n+2){border-bottom:1px solid var(--line)}.explorer-top{display:block}.detail{min-height:390px}.controls button{flex:1 0 29%}}
</style></head><body>
<header><div class="mast"><div><div class="brand">Alabama Election Lab</div><div class="tag">Elections at your fingertips</div></div><nav class="nav"><span>Analysis</span><span>Data</span><span>WAR</span></nav></div></header>
<main><section class="story-head"><h1>Alabama Legislative Wins Above Replacement</h1><div class="dek">A district-by-district look at which state legislative candidates most exceeded—or fell short of—what the fundamentals predicted in 2014, 2018 and 2022.</div><div class="byline">Model and analysis by <b>Alabama Election Lab</b> &nbsp;•&nbsp; August 2026</div></section>
<section class="intro"><p>Winning a race is not the same thing as running a strong campaign. Alabama districts differ sharply in partisanship, incumbency, demographics and campaign resources. Our Wins Above Replacement model asks a narrower question: <em>how much better or worse did each candidate perform than a typical candidate would have under the same conditions?</em></p><p><strong>Positive WAR indicates outperformance; negative WAR indicates underperformance.</strong> Scores are measured in percentage points of two-party margin. Select a cycle and chamber, then hover or tap a district for detail.</p></section>
<section class="explorer"><div class="explorer-top"><div><h2>Explore the results</h2><div class="note">Map color shows which party's candidate ran ahead of the model's expectations, not who won the seat: blue means the Democratic candidate overperformed, red means the Republican candidate overperformed, and shading saturates at ±6 points so smaller differences remain visible. Gray districts had no model-eligible contested race.</div></div><div class="note" id="vintage"></div></div><div class="controls" id="controls"></div>
<div class="dashboard"><div class="map-panel"><h3 class="map-title" id="map-title"></h3><div class="map-sub">Direction of overperformance by district</div><div class="map-wrap"><svg id="map" viewBox="0 0 640 700" role="img"></svg><div class="legend"><div class="gradient"></div><div class="ticks"><span>R +6</span><span>R +3</span><span>Even</span><span>D +3</span><span>D +6</span></div></div></div></div><aside class="detail" id="detail"><div class="detail-empty">Select a colored district to inspect the race.</div></aside></div><div class="summary" id="summary"></div></section>
<section class="rankings"><h2>Candidate rankings</h2><div class="note">Click a column heading to sort. Margins are shown from each candidate party perspective. Same-cycle top-ticket margin is a same-year statewide index (e.g. Governor, Attorney General); prior presidential margin uses the 2012 presidential vote for 2014, 2016 for 2018, and 2020 for 2022 and is a model input, not the baseline WAR is measured against.</div><div class="table-wrap"><table><thead><tr><th data-sort="district">District</th><th data-sort="candidate">Candidate</th><th data-sort="war">WAR ↕</th><th data-sort="cycleTopTicket">Same-cycle top-ticket margin</th><th data-sort="priorPres">Prior presidential margin</th><th data-sort="expectedMargin">Expected margin</th><th data-sort="margin">Candidate margin</th><th data-sort="votes">Votes</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section class="method"><h2>How to read WAR</h2><p>The model begins with each Democratic candidate’s margin relative to a district baseline—a same-cycle statewide index built from same-year down-ballot statewide races such as Governor and Attorney General—and estimates the portion of the gap from that baseline expected from incumbency, prior presidential performance and trend, demographics, and the balance of campaign spending. The remaining residual is WAR. Republican candidate values are the sign-reversed district residual, so both parties share one intuitive scale: positive is better than expected.</p><p>Note that the same-cycle statewide index and the prior presidential margin are different numbers: the index is measured in the same year as the legislative race, while the presidential margin is from the most recent presidential election (2012, 2016, or 2020) and is used only as one input to the model’s expectation, not as the baseline itself. The two can diverge sharply when a state’s partisan lean shifts between a presidential year and the following midterm.</p><p>The page uses final-model residuals for description and displays model-based uncertainty intervals. Results are best used to compare candidates within this Alabama legislative dataset—not as a universal measure of candidate quality or a prediction of future performance.</p><div class="source">Sources: Alabama legislative general-election returns; Alabama Secretary of State campaign-finance records; U.S. Census Bureau ACS; presidential precinct returns and enacted legislative district files. Model output: <code>preliminary_war_candidates.csv</code>. Map vintages are matched to each election cycle.</div></section></main><div class="tooltip" id="tooltip"></div>
<script>const DATA=__PAYLOAD__;
let active='2022-house',sortKey='war',sortDir=-1,selected=null;
const $=s=>document.querySelector(s), fmt=n=>(n>0?'+':'')+Number(n).toFixed(1), esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function color(v){if(v==null)return '#deded9';const x=Math.max(-6,Math.min(6,v))/6;if(x<0)return mix('#f2f1ed','#d34b45',-x);return mix('#f2f1ed','#3d77a8',x)}
function mix(a,b,t){const A=a.match(/\w\w/g).map(x=>parseInt(x,16)),B=b.match(/\w\w/g).map(x=>parseInt(x,16));return '#'+A.map((x,i)=>Math.round(x+(B[i]-x)*t).toString(16).padStart(2,'0')).join('')}
function makeControls(){const box=$('#controls');box.innerHTML='';Object.keys(DATA).forEach(k=>{const d=DATA[k],b=document.createElement('button');b.textContent=d.cycle+' '+d.chamber;b.className=k===active?'active':'';b.onclick=()=>{active=k;selected=null;render()};box.appendChild(b)})}
function detail(x){const box=$('#detail');if(!x){box.innerHTML='<div class="detail-empty">Select a colored district to inspect the race.</div>';return}box.innerHTML=`<h3>${esc(x.candidate)}</h3><div class="party ${x.party}">${x.party==='D'?'Democratic':'Republican'} • District ${x.district}${x.incumbent?' • Incumbent':''}</div><div class="war-number">${fmt(x.war)}</div><div class="war-label">Wins above replacement</div><div class="stat"><span>Same-cycle top-ticket margin</span><b>${fmt(x.cycleTopTicket)}</b></div><div class="stat"><span>Prior presidential margin</span><b>${fmt(x.priorPres)}</b></div><div class="stat"><span>Expected margin</span><b>${fmt(x.expectedMargin)}</b></div><div class="stat"><span>Candidate margin</span><b>${fmt(x.margin)}</b></div><div class="stat"><span>Raw overperformance</span><b>${fmt(x.raw)}</b></div><div class="stat"><span>Expected overperformance</span><b>${fmt(x.expected)}</b></div><div class="stat"><span>Votes</span><b>${x.votes.toLocaleString()}</b></div><div class="explain">${x.war>=0?'This candidate ran ahead of':'This candidate ran behind'} the model’s expectation by about <b>${Math.abs(x.war).toFixed(1)} points</b> of two-party margin.</div>`}
function renderMap(){const d=DATA[active],map=$('#map'),tip=$('#tooltip');map.innerHTML='';map.setAttribute('aria-label',`${d.cycle} Alabama ${d.chamber} WAR map`);d.paths.forEach(p=>{const x=d.winners[p.district],dw=d.demWar[p.district],el=document.createElementNS('http://www.w3.org/2000/svg','path');el.setAttribute('d',p.path);el.setAttribute('fill',color(dw));el.setAttribute('class','district'+(selected===p.district?' selected':''));el.setAttribute('tabindex','0');el.setAttribute('aria-label',x?`District ${p.district}, ${dw>=0?'Democrat':'Republican'} overperformed by ${Math.abs(dw).toFixed(1)}, won by ${x.candidate}`:`District ${p.district}, no eligible race`);el.onmouseenter=e=>{tip.style.display='block';tip.innerHTML=x?`<b>District ${p.district}</b><br>${dw>=0?'Democrat':'Republican'} overperformed by ${Math.abs(dw).toFixed(1)}<br>Won by ${esc(x.candidate)} (${fmt(x.war)} WAR)`:`District ${p.district}<br>No eligible race`;moveTip(e)};el.onmousemove=moveTip;el.onmouseleave=()=>tip.style.display='none';el.onclick=()=>{selected=p.district;detail(x);renderMap()};el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();el.onclick()}};map.appendChild(el)});$('#map-title').textContent=`${d.cycle} Alabama ${d.chamber[0].toUpperCase()+d.chamber.slice(1)} WAR`;$('#vintage').textContent='Boundaries: '+d.mapVintage}
function moveTip(e){const t=$('#tooltip');t.style.left=(e.clientX+14)+'px';t.style.top=(e.clientY+14)+'px'}
function renderRows(){const d=DATA[active],rows=[...d.candidates].sort((a,b)=>{let A=a[sortKey],B=b[sortKey];return(typeof A==='string'?A.localeCompare(B):A-B)*sortDir});$('#rows').innerHTML=rows.map(x=>`<tr><td>${x.district}</td><td class="cand"><i class="party-dot ${x.party}"></i>${esc(x.candidate)}${x.winner?' <small>✓</small>':''}</td><td class="num"><b>${fmt(x.war)}</b></td><td class="num">${fmt(x.cycleTopTicket)}</td><td class="num">${fmt(x.priorPres)}</td><td class="num">${fmt(x.expectedMargin)}</td><td class="num">${fmt(x.margin)}</td><td class="num">${x.votes.toLocaleString()}</td></tr>`).join('')}
function render(){makeControls();const d=DATA[active];renderMap();detail(d.winners[selected]);renderRows();$('#summary').innerHTML=`<div><b>${d.summary.races}</b><span>Contested districts</span></div><div><b>${d.summary.candidates}</b><span>Candidates scored</span></div><div><b>${fmt(d.summary.median)}</b><span>Median winner WAR</span></div><div><b>${esc(d.summary.top)}</b><span>Top winner</span></div>`}
document.querySelectorAll('th[data-sort]').forEach(th=>th.onclick=()=>{const k=th.dataset.sort;sortDir=sortKey===k?-sortDir:(k==='candidate'?1:-1);sortKey=k;renderRows()});render();</script></body></html>'''
    return template.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    data = load_data()
    OUTPUT.write_text(build_page(data), encoding="utf-8")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
