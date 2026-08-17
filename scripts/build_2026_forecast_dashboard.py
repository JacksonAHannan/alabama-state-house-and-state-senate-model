"""Build the self-contained, accessible 2026 forecast dashboard."""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
ASSETS = ROOT / "dashboard"
OUTPUT = ROOT / "artifacts" / "site" / "alabama-2026-legislative-forecast.html"
SITE = ROOT / "docs"
MAPS = {
    "house": ROOT / "data" / "raw" / "alabama_elections_and_geography" / "tl_2025_01_sldl" / "tl_2025_01_sldl.shp",
    "senate": ROOT / "data" / "raw" / "alabama_elections_and_geography" / "tl_2025_01_sldu" / "tl_2025_01_sldu.shp",
}


def clean(value):
    if pd.isna(value): return None
    return value.item() if hasattr(value, "item") else value


def path_for_geometry(geom, bounds, width=650, height=710, pad=12):
    minx, miny, maxx, maxy = bounds
    scale = min((width - 2*pad)/(maxx-minx), (height - 2*pad)/(maxy-miny))
    ox, oy = (width-(maxx-minx)*scale)/2, (height-(maxy-miny)*scale)/2
    def ring(coords):
        pts=((ox+(x-minx)*scale, height-(oy+(y-miny)*scale)) for x,y in coords)
        return "M"+"L".join(f"{x:.1f},{y:.1f}" for x,y in pts)+"Z"
    polygons=[geom] if geom.geom_type=="Polygon" else list(geom.geoms)
    return "".join(ring(p.exterior.coords)+"".join(ring(h.coords) for h in p.interiors) for p in polygons)


def rating(p):
    if p is None: return "Not modeled"
    leader="D" if p>=.5 else "R"; q=max(p,1-p)
    band="Toss-up" if q<.55 else "Lean" if q<.70 else "Likely" if q<.90 else "Solid"
    return band if band=="Toss-up" else f"{band} {leader}"


def build_payload():
    forecast=pd.read_csv(WAR/"2026_prospective_features_and_forecast.csv")
    roster=pd.read_csv(WAR/"2026_final_candidate_roster.csv")
    incumbency=pd.read_csv(WAR/"2026_candidate_incumbency.csv")
    finance=pd.read_csv(WAR/"2026_state_candidate_finance_matches.csv")
    seats=pd.read_csv(WAR/"2026_correlated_seat_simulation.csv")
    polling=pd.read_csv(WAR/"2026_poll_adjusted_baseline.csv")
    roster=(roster.merge(incumbency[["chamber","district","party","candidate","incumbent"]],
                         on=["chamber","district","party","candidate"],how="left")
                  .merge(finance[["chamber","district","party","candidate","state_contributions","state_expenditures","finance_observation_status"]],
                         on=["chamber","district","party","candidate"],how="left"))
    fidx={(r.chamber,int(r.district)):r for r in forecast.itertuples()}
    poll_date=dt.date.fromisoformat(str(polling.poll_average_as_of.iloc[0]))
    build_date=dt.date.today()
    payload={"meta":{"pollAsOf":poll_date.isoformat(),"buildDate":build_date.isoformat(),
                     "financeAsOf":"2026-08-14","pollStalenessDays":(build_date-poll_date).days,
                     "model":"poll_adjusted_post2016_national_environment_ramp",
                     "version":"2026.08.16-national-environment-ramp"}}
    for chamber,map_path in MAPS.items():
        geo=gpd.read_file(map_path).to_crs(4326); field="SLDLST" if chamber=="house" else "SLDUST"
        geo["district"]=geo[field].astype(int); geo["geometry"]=geo.geometry.simplify(.004,preserve_topology=True)
        bounds=geo.total_bounds
        paths=[{"district":int(r.district),"path":path_for_geometry(r.geometry,bounds)} for _,r in geo.iterrows()]
        races=[]; total=105 if chamber=="house" else 35
        for district in range(1,total+1):
            sub=roster[(roster.chamber==chamber)&(roster.district==district)]
            candidates=[{"name":str(c.candidate),"party":str(c.party),"incumbent":bool(clean(c.incumbent) or False),
                         "raised":clean(c.state_contributions),"spent":clean(c.state_expenditures),
                         "financeStatus":clean(c.finance_observation_status)} for c in sub.itertuples()]
            major={c["party"] for c in candidates if c["party"] in {"D","R"}}; row=fidx.get((chamber,district))
            if row is not None:
                p=float(row.dem_win_probability); status="modeled"; margin=float(row.predicted_dem_margin)
                low80,high80=float(row.margin_80_low),float(row.margin_80_high)
                baseline=float(row.poll_adjusted_dem_margin); pres24=float(row.baseline_2024_pres_dem_margin)
                environment=float(row.environment_adjustment); finance_scenario=float(row.scenario_finance_scenario_margin)
                cmo_scenario=float(row.cmo_scenario_adjustment)
            elif major=={"D"}:
                p,status,margin=1.0,"unopposed-major-party",None
                low80=high80=baseline=pres24=environment=finance_scenario=cmo_scenario=None
            elif major=={"R"}:
                p,status,margin=0.0,"unopposed-major-party",None
                low80=high80=baseline=pres24=environment=finance_scenario=cmo_scenario=None
            else:
                p,status,margin=None,"unmodeled",None
                low80=high80=baseline=pres24=environment=finance_scenario=cmo_scenario=None
            races.append({"district":district,"candidates":candidates,"status":status,"demProbability":p,
                          "rating":rating(p) if status=="modeled" else "Not modeled","margin":margin,
                          "low80":low80,"high80":high80,"pollBaseline":baseline,"pres24":pres24,
                          "environmentAdjustment":environment,"financeScenario":finance_scenario,
                          "cmoScenarioAdjustment":cmo_scenario})
        sd=seats[seats.chamber.eq(chamber)][["dem_seats","probability"]].rename(columns={"dem_seats":"demSeats"})
        payload[chamber]={"paths":paths,"races":races,"seatDistribution":[{k:clean(v) for k,v in x.items()} for x in sd.to_dict("records")]}
    return payload


HTML="""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Jackson Hannan's 2026 Alabama State House and State Senate election forecast"><meta name="author" content="Jackson Hannan"><meta property="og:title" content="Alabama 2026 Legislative Forecast"><meta property="og:description" content="A district-by-district Alabama legislative forecast by Jackson Hannan."><meta property="og:type" content="website"><title>Alabama 2026 Legislative Forecast · Jackson Hannan</title><style>__CSS__</style></head><body>
<header class="mast"><div class="mast-inner"><div class="brand">Jackson Hannan<small>Alabama legislative forecast</small></div><nav class="social-nav" aria-label="Jackson Hannan online"><a href="https://github.com/JacksonAHannan" target="_blank" rel="me noopener">GitHub</a><a href="https://www.instagram.com/topsoilintraining/" target="_blank" rel="me noopener">Instagram</a><a href="https://substack.com/@jacksonhannan" target="_blank" rel="me noopener">Substack</a><a href="https://www.linkedin.com/in/jackson-hannan" target="_blank" rel="me noopener">LinkedIn</a></nav></div></header>
<section class="hero"><div class="kicker">The Alabama Legislature</div><h1>2026 Election Forecast</h1><div class="dek">A district-by-district forecast anchored to 2024 presidential performance and adjusted for the projected 2026 national environment using Alabama’s demographic composition.</div><div class="status-row"><span class="status-chip">Forecast built <b id="buildDate"></b></span><span class="status-chip">Polling through <b id="pollDate"></b></span><span class="status-chip" id="pollAge"></span><span class="status-chip">Finance through <b id="financeDate"></b></span></div>
<details class="quick-method"><summary>How the headline forecast works</summary><ol><li>Allocate the observed 2024 presidential vote into each 2026 legislative district.</li><li>Apply a district-specific 2026 demographic environment change derived from generic-ballot polling.</li><li>Simulate shared statewide, chamber, and district uncertainty. Candidate and finance adjustments remain separate experimental scenarios.</li></ol></details></section>
<main class="shell"><section class="overview-grid" id="overviewGrid" aria-label="House and Senate forecast summaries"></section>
<section class="workspace" id="workspace"><header class="workspace-head"><h2 id="chamberTitle"></h2><div class="segmented" aria-label="Select chamber"><button data-chamber="house" aria-pressed="true">State House</button><button data-chamber="senate" aria-pressed="false">State Senate</button></div></header>
<div class="chamber-strip"><div class="strip-stat"><b id="medianSeats"></b><span>Median Democratic seats</span></div><div class="strip-stat distribution-cell"><div class="distribution" id="distribution" aria-label="Simulated Democratic seat distribution"></div><div class="distribution-axis" id="distributionAxis"></div></div><div class="strip-stat"><b id="seatRange"></b><span>Democratic 80% seat range</span></div></div>
<div class="interactive"><section class="map-panel"><div class="map-head"><div><h3 id="mapTitle"></h3><p>Choose a district on the map or with the district finder.</p></div><div class="mode-tabs" aria-label="Map display"><button data-mode="probability" aria-pressed="true">Win chance</button><button data-mode="margin" aria-pressed="false">Margin</button><button data-mode="rating" aria-pressed="false">Rating</button></div></div><div class="map-tools"><label class="sr-only" for="districtSelect">Find a district</label><select id="districtSelect"></select><span class="section-note">Urban districts can also be selected from this list.</span></div><div class="map-wrap"><svg id="map" viewBox="0 0 650 710" role="group"></svg></div><div class="legend" id="legend" aria-label="Map legend"></div></section>
<aside class="detail" id="detail" aria-live="polite"><div class="detail-empty">Loading the closest race…</div></aside></div></section>
<section class="section"><h2>District forecast table</h2><p class="section-note"><span id="rowCount"></span>. Headline margins use the selected baseline. Candidate and fundraising scenarios are shown separately and do not change ratings.</p><div class="table-tools"><label class="sr-only" for="search">Search candidates or districts</label><input id="search" type="search" placeholder="Search candidate or district"><label class="sr-only" for="ratingFilter">Filter by rating</label><select id="ratingFilter"><option value="all">All ratings</option><option>Solid D</option><option>Likely D</option><option>Lean D</option><option>Toss-up</option><option>Lean R</option><option>Likely R</option><option>Solid R</option><option>Unopposed D</option><option>Unopposed R</option></select><label class="sr-only" for="scopeFilter">Filter races</label><select id="scopeFilter"><option value="all">All districts</option><option value="competitive">Competitive (35–65%)</option><option value="modeled">Modeled D–R races</option><option value="open">Open seats</option><option value="crosses">80% interval crosses even</option></select><button class="small-button" id="download">Download CSV</button></div><div class="table-hint">Swipe horizontally to see all columns; the district column remains fixed.</div><div class="table-wrap"><table><thead><tr><th><button data-sort="district">District<span></span></button></th><th>Candidates</th><th><button data-sort="rating">Rating<span></span></button></th><th><button data-sort="demProbability">Dem. chance<span></span></button></th><th><button data-sort="margin">Headline margin<span></span></button></th><th>80% interval</th><th>Finance scenario</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section class="section method"><div><h2>How to read this forecast</h2><p>The headline starts with each district’s observed 2024 presidential result and adds a district-specific demographic environment change derived from generic-ballot polling, Catalist history, YouGov cross-tabs, and Alabama ACS composition.</p><p>Incumbency, demographic-residual, finance, and prior-CMO layers were evaluated only as residual adjustments. None passed the rule requiring improvement in both average and latest-cycle forward MAE, so none changes the headline. The direct baseline’s mean forward MAE is 12.6 points.</p><div class="method-links"><a href="project_docs/methodology/FORECAST_METHODOLOGY.md">Full methodology</a><a href="data/processed/war/2026_forecast_decomposition.csv">District data</a><a href="data/processed/war/2026_residual_layer_backtest_summary.csv">Backtests</a></div></div><div class="caveat"><b>Experimental forecast.</b><p>Only two comparable forward cycles support the current uncertainty estimates. Probabilities use 50,000 simulations with shared statewide and chamber error plus district-specific error. Single-major-party districts are treated as fixed seats for chamber summaries even when an independent is present. Gray, dashed districts are unresolved or unmodeled rather than toss-ups.</p><p>Polling staleness is displayed at the top of the page. The environment component should be rebuilt when new polling becomes available.</p></div></section></main><footer class="site-footer"><div><b>Model and analysis by Jackson Hannan</b><span>Alabama 2026 Legislative Forecast</span></div><nav aria-label="Jackson Hannan profiles"><a href="https://github.com/JacksonAHannan" target="_blank" rel="me noopener">GitHub</a><a href="https://www.instagram.com/topsoilintraining/" target="_blank" rel="me noopener">Instagram</a><a href="https://substack.com/@jacksonhannan" target="_blank" rel="me noopener">Substack</a><a href="https://www.linkedin.com/in/jackson-hannan" target="_blank" rel="me noopener">LinkedIn</a></nav></footer><div class="tooltip" id="tooltip" role="tooltip"></div><script>const DATA=__PAYLOAD__;__JS__</script></body></html>"""


UNCERTAINTY_CAVEAT = """<div class="caveat"><b>Experimental uncertainty estimates.</b><p>District probabilities and seat ranges are calculated from 50,000 simulations around the poll-adjusted baseline. Each simulation includes an Alabama-wide error shared by every district, an additional House or Senate error shared within that chamber, and district-specific error.</p><p>The error scales use the full 1994–2022 archive and expanding-window holdouts from 1998 through 2022. The archive contains only eight distinct election environments, so estimated correlations and probabilities remain provisional rather than fully calibrated.</p><p>Districts with only one major-party nominee are treated as fixed Democratic or Republican seats in chamber summaries. Independent-only and otherwise unresolved districts remain unmodeled and are displayed in gray.</p><p>The national-environment projection uses polling through the date shown above and should be refreshed as new polling becomes available.</p></div>"""


METHODOLOGY = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Methodology for Jackson Hannan's Alabama 2026 legislative forecast"><title>Methodology · Alabama 2026 Legislative Forecast</title><style>__CSS__</style></head><body>
<header class="mast"><div class="mast-inner"><div class="brand">Jackson Hannan<small>Alabama legislative forecast</small></div><nav class="social-nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html">CMO</a><a href="methodology.html" aria-current="page">Forecast methodology</a><a href="cmo-methodology.html">CMO methodology</a><a href="https://github.com/JacksonAHannan" target="_blank" rel="me noopener">GitHub</a><a href="https://substack.com/@jacksonhannan" target="_blank" rel="me noopener">Substack</a></nav></div></header>
<main class="methodology-shell"><header class="methodology-hero"><div class="kicker">Model documentation</div><h1>Forecast methodology</h1><p class="dek">How the Alabama House and Senate forecast turns district geography, election results, demographic composition, and national polling into district probabilities and chamber simulations.</p><div class="status-row"><span class="status-chip">Model <b>baseline-first</b></span><span class="status-chip">Polling through <b>__POLL_DATE__</b></span><span class="status-chip">Updated <b>__BUILD_DATE__</b></span></div></header>
<div class="method-grid"><aside class="toc"><b>On this page</b><a href="#overview">Overview</a><a href="#baseline">District baseline</a><a href="#environment">National environment</a><a href="#poststratification">Alabama transfer</a><a href="#candidate">Candidate layers</a><a href="#validation">Validation</a><a href="#uncertainty">Uncertainty</a><a href="#limitations">Limitations</a><a href="#downloads">Downloads</a></aside>
<article class="method-copy"><section id="overview"><h2>Overview</h2><p>The forecast is deliberately baseline-first. It begins with the observed 2024 presidential vote allocated into the districts that will be used in 2026. It then applies a district-specific change derived from the current national generic-ballot environment and Alabama’s demographic composition.</p><div class="formula">2026 district margin = 2024 presidential margin + district demographic environment change + promoted residual adjustments</div><p>No candidate, incumbency, finance, or prior-CMO residual adjustment currently passes the promotion rule. Those quantities may appear as scenarios, but the headline forecast remains the poll-adjusted direct baseline.</p></section>
<section id="baseline"><h2>1. District baseline</h2><p>The structural baseline is each district’s two-party Democratic presidential margin in 2024. Precinct results are allocated to the 2026 legislative map using independently constructed Census geography rather than legislative turnout weights. This avoids allowing candidate strength in a legislative contest to influence its own geographic comparator.</p><p>The 2026 map is Alabama’s original 2021 legislature-drawn map, represented by the 2025 Census state-legislative shapefiles supplied for both chambers.</p></section>
<section id="environment"><h2>2. National political environment</h2><p>The current environment uses national generic-ballot polls from pollsters graded B+ or better in the supplied Nate Silver ratings file. Public releases are archived locally with retrieval timestamps and SHA-256 hashes.</p><p>The topline takes the newest eligible poll from each pollster in a rolling 60-day window. Likely-voter, registered-voter, and adult samples receive population weights, and older polls decay with a 21-day half-life. The current two-party national environment is <b>__NATIONAL_MARGIN__</b> across <b>__POLLSTERS__ pollsters</b>.</p><div class="callout"><b>Pollster quality is a gate, not a house effect.</b>The current model excludes lower-rated pollsters but does not yet estimate pollster-specific house effects. Polling should be rebuilt whenever new releases become available.</div></section>
<section id="poststratification"><h2>3. From national polling to Alabama districts</h2><p>Reviewed crosstabs estimate how racial and educational groups differ from each poll’s overall two-party result. Effects are measured on the logit scale, pooled across eligible pollsters, and applied to a Catalist 2024 national reference.</p><p>Historical Alabama offsets are estimated from election results and demographic ecological inference. ACS block-group race-by-education cells are allocated into each 2026 district and used to poststratify the projected group support and turnout. The model anchors the resulting change to the district’s observed 2024 presidential margin rather than trusting a fitted demographic level.</p></section>
<section id="candidate"><h2>4. Candidate, finance, and federal-realignment layers</h2><p>Incumbency, demographic residuals, finance, and prior candidate margin overperformance were tested only as adjustments to the strong baseline. The current finance scenario uses Alabama state campaign-finance receipts through August 14, 2026; unmatched filings remain unknown rather than being treated as zero. Finance is descriptive and potentially endogenous: strong candidates can raise more money, so it is not interpreted as a clean causal effect.</p><p>The national-environment scenario adds Catalist’s observed change in the national Democratic two-party margin from the preceding presidential election to the midterm U.S. House vote. A demographic variant tests whether that swing varies with district nonwhite and white-college composition. A separate federal-realignment scenario learns legislative residuals from same-cycle U.S. House and U.S. Senate results. Validation begins after the 2008 nationalization break, and post-2016 observations receive twice the weight of 2010-2014 observations.</p><p>The prospective anchor already incorporates the projected 2024-to-2026 national and demographic environment, so these comparisons test that construction without adding the same swing twice. Prior CMO uses only historical out-of-fold scores, exact normalized candidate-and-party matches, and shrinkage toward zero.</p></section>
<section id="validation"><h2>5. Forward validation and promotion</h2><p>Models train only on elections earlier than the cycle being predicted. The comparison now uses all eight cycles from 1994 through 2022, producing seven expanding-window holdouts. Promotion requires improvement in full-period mean MAE, post-2016 mean MAE, and the latest-cycle MAE.</p><table class="method-table"><thead><tr><th>Specification</th><th>Mean forward MAE</th><th>Latest MAE</th><th>Promoted</th></tr></thead><tbody>__BACKTEST_ROWS__</tbody></table><p>The post-2016 ramp reduces full-period mean MAE from 25.73 to 25.32, post-2016 mean MAE from 12.57 to 11.13, and 2022 MAE from 12.03 to 9.77. Applying the full national swing in every cycle performs substantially worse, especially before 2018. The demographic-response, finance, incumbency, and era-weighted federal variants fail the stricter three-part gate.</p><div class="callout"><b>Realignment is not a smooth early-series trend.</b>Official national vote changes and Alabama results imply a sharp 2006 anomaly, followed by little evidence that the national swing should be transferred directly in 2010 or 2014. This reflects Alabama’s delayed local partisan realignment and prevents the cadence from being estimated as a simple monotonic curve across all eight cycles.</div></section>
<section id="uncertainty"><h2>6. Probabilities and chamber simulations</h2><p>Fifty thousand deterministic-seed simulations add a shared Alabama-wide error, a shared chamber error, and district-specific error. Their scales are estimated from direct-baseline forward errors. District win probabilities, interval bounds, and chamber seat distributions are empirical simulation results.</p><p>Single-major-party districts are fixed for chamber summaries, even when an independent appears. Independent-only and unresolved districts remain unmodeled rather than being labeled toss-ups.</p></section>
<section id="limitations"><h2>7. Important limitations</h2><ul><li>Eight election environments support seven forward holdouts, but only two occur after the 2016 break.</li><li>National race and education crosstabs are not joint race-by-education samples; the model combines them with ACS and historical estimates.</li><li>Alabama polling is sparse, so national movements are transferred through demographic structure rather than measured directly in the state.</li><li>Polling house effects and mode effects are not yet estimated explicitly.</li><li>Candidate, incumbency, finance, federal-realignment, and CMO scenarios have not cleared the declared promotion gate.</li><li>Probabilities are provisional and should not be read as fully calibrated long-run frequencies.</li></ul></section>
<section id="downloads"><h2>Data and audit downloads</h2><p class="download-list"><a href="data/2026_forecast_decomposition.csv">District decomposition</a><a href="data/2026_residual_layer_backtest_summary.csv">Backtest summary</a><a href="data/polling_environment.csv">Polling environment</a><a href="data/poll_source_manifest.csv">Polling source manifest</a></p></section></article></div></main>
<footer class="site-footer"><div><b>Model and analysis by Jackson Hannan</b><span>Alabama 2026 Legislative Forecast</span></div><nav><a href="index.html">Forecast</a><a href="https://www.instagram.com/topsoilintraining/" target="_blank" rel="me noopener">Instagram</a><a href="https://www.linkedin.com/in/jackson-hannan" target="_blank" rel="me noopener">LinkedIn</a></nav></footer></body></html>"""


def build_methodology(css: str, payload: dict) -> str:
    summary = pd.read_csv(WAR / "2026_residual_layer_backtest_summary.csv")
    rows = "".join(
        f"<tr><td>{r.specification.replace('_', ' ').title()}</td><td>{r.mean_mae:.2f}</td>"
        f"<td>{r.latest_mae:.2f}</td><td>{'Yes' if r.promoted else 'No'}</td></tr>"
        for r in summary.itertuples()
    )
    environment = pd.read_csv(ROOT / "data" / "processed" / "polling" /
                              "votehub_silver_bplus_topline_environment.csv").iloc[0]
    return (METHODOLOGY.replace("__CSS__", css + (ASSETS / "methodology.css").read_text(encoding="utf-8"))
            .replace("__POLL_DATE__", str(environment.as_of))
            .replace("__BUILD_DATE__", payload["meta"]["buildDate"])
            .replace("__NATIONAL_MARGIN__", f"D+{float(environment.dem_two_party_margin):.2f}")
            .replace("__POLLSTERS__", str(int(environment.pollsters)))
            .replace("__BACKTEST_ROWS__", rows))


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    css=(ASSETS/"forecast_dashboard.css").read_text(encoding="utf-8")
    js=(ASSETS/"forecast_dashboard.js").read_text(encoding="utf-8")
    payload_data=build_payload()
    payload=json.dumps(payload_data,separators=(",",":"),ensure_ascii=False)
    page=HTML.replace("__CSS__",css).replace("__PAYLOAD__",payload).replace("__JS__",js)
    page=page.replace(
        "derived from generic-ballot polling, Catalist history, YouGov cross-tabs, and Alabama ACS composition.",
        "derived from quality-gated generic-ballot polling, reviewed demographic crosstabs, Catalist history, Alabama ecological inference, and ACS composition.")
    page=page.replace(
        "Incumbency, demographic-residual, finance, and prior-CMO layers were evaluated only as residual adjustments. None passed the rule requiring improvement in both average and latest-cycle forward MAE, so none changes the headline. The direct baseline’s mean forward MAE is 12.6 points.",
        "Incumbency, demographic-residual, current fundraising, federal-realignment, and prior-CMO layers were evaluated only as residual adjustments. The post-2016 national-environment ramp passed the full-history, recent-era, and latest-cycle comparison; other layers remain scenarios. Its seven-holdout mean forward MAE is 25.3 points.")
    page=page.replace('<a href="project_docs/methodology/FORECAST_METHODOLOGY.md">Full methodology</a>',
                      '<a href="methodology.html">Full methodology</a>')
    page=page.replace('href="data/processed/war/2026_forecast_decomposition.csv"',
                      'href="data/2026_forecast_decomposition.csv"')
    page=page.replace('href="data/processed/war/2026_residual_layer_backtest_summary.csv"',
                      'href="data/2026_residual_layer_backtest_summary.csv"')
    page=page.replace('<nav class="social-nav" aria-label="Jackson Hannan online">',
                      '<nav class="social-nav" aria-label="Site navigation"><a href="index.html" aria-current="page">Forecast</a><a href="cmo.html">CMO</a><a href="methodology.html">Forecast methodology</a><a href="cmo-methodology.html">CMO methodology</a>')
    page=page.replace('<a href="methodology.html">Full methodology</a>',
                      '<a href="methodology.html">Full methodology</a><a href="cmo.html">Historical CMO model</a>')
    page=re.sub(r'<div class="caveat">.*?</div></section></main>', UNCERTAINTY_CAVEAT+'</section></main>', page, count=1, flags=re.S)
    OUTPUT.write_text(page,encoding="utf-8")
    SITE.mkdir(parents=True,exist_ok=True)
    (SITE/"data").mkdir(exist_ok=True)
    (SITE/"index.html").write_text(page,encoding="utf-8")
    (SITE/"methodology.html").write_text(build_methodology(css,payload_data),encoding="utf-8")
    for source,name in [
        (WAR/"2026_forecast_decomposition.csv","2026_forecast_decomposition.csv"),
        (WAR/"2026_residual_layer_backtest_summary.csv","2026_residual_layer_backtest_summary.csv"),
        (ROOT/"data/processed/polling/votehub_silver_bplus_topline_environment.csv","polling_environment.csv"),
        (ROOT/"data/raw/polling/silver_recent/manifest.csv","poll_source_manifest.csv"),
    ]:
        shutil.copy2(source,SITE/"data"/name)
    print(f"Wrote {OUTPUT}, {SITE/'index.html'}, and {SITE/'methodology.html'}")


if __name__=="__main__": main()
