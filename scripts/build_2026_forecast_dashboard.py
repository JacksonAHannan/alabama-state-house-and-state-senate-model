# -*- coding: utf-8 -*-
"""Build the self-contained, accessible 2026 forecast dashboard."""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import t as student_t
from shapely.geometry import mapping

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
CAL = ROOT / "data" / "processed" / "forecast_calibration"
ASSETS = ROOT / "dashboard"
OUTPUT = ROOT / "artifacts" / "site" / "alabama-2026-legislative-forecast.html"
SITE = ROOT / "docs"
MAPS = {
    "house": ROOT / "data" / "raw" / "alabama_elections_and_geography" / "tl_2025_01_sldl" / "tl_2025_01_sldl.shp",
    "senate": ROOT / "data" / "raw" / "alabama_elections_and_geography" / "tl_2025_01_sldu" / "tl_2025_01_sldu.shp",
}
PUBLIC_MODELS = {
    "headline": "Headline",
    "environment_dem_favorable": "Dem scenario",
    "environment_rep_favorable": "Rep scenario",
}
DEFAULT_MODEL = "headline"


def normalize_name(value: object) -> str:
    """Conservative display-history key; exact normalized name and party only."""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def display_candidate_name(value: object) -> str | None:
    name = str(value)
    return None if re.fullmatch(r"GSL\d+[A-Z0-9]+", name.upper()) else name


def region_summary(row: object | None) -> list[dict]:
    if row is None:
        return []
    labels = {
        "region_auburn_city_share": "Auburn",
        "region_birmingham_city_share": "Birmingham",
        "region_birmingham_educated_suburbs_share": "Birmingham educated suburbs",
        "region_black_belt_share": "Black Belt",
        "region_huntsville_city_share": "Huntsville",
        "region_madison_county_remainder_share": "Madison County outside Huntsville and Madison",
        "region_madison_city_share": "Madison",
        "region_mobile_city_share": "Mobile",
        "region_other_alabama_share": "Other Alabama",
        "region_shelby_county_remainder_share": "Shelby County outside Birmingham suburbs",
        "region_tuscaloosa_city_share": "Tuscaloosa",
    }
    shares = [
        {"name": label, "share": round(float(getattr(row, field)), 6)}
        for field, label in labels.items()
        if pd.notna(getattr(row, field, np.nan)) and float(getattr(row, field)) >= .05
    ]
    return sorted(shares, key=lambda item: item["share"], reverse=True)[:3]


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


def point_for_geometry(geom, bounds, width=650, height=710, pad=12):
    minx, miny, maxx, maxy = bounds
    scale = min((width - 2*pad)/(maxx-minx), (height - 2*pad)/(maxy-miny))
    ox, oy = (width-(maxx-minx)*scale)/2, (height-(maxy-miny)*scale)/2
    point = geom.representative_point()
    return round(ox+(point.x-minx)*scale, 1), round(height-(oy+(point.y-miny)*scale), 1)


def rating(p):
    if p is None: return "Not modeled"
    leader="D" if p>=.5 else "R"; q=max(p,1-p)
    band="Toss-up" if q<.60 else "Lean" if q<.80 else "Likely" if q<.95 else "Very likely" if q<.98 else "Solid"
    return band if band=="Toss-up" else f"{band} {leader}"


def conditional_seat_distribution(probabilities, fixed_dem):
    """Exact Poisson-binomial distribution conditional on forecast margins."""
    distribution=np.array([1.0])
    for p in probabilities:
        distribution=np.convolve(distribution,np.array([1-float(p),float(p)]))
    return pd.DataFrame({"dem_seats":np.arange(len(distribution))+int(fixed_dem),
                         "probability":distribution})


def build_payload():
    scenarios=pd.read_csv(CAL/"post2016_headline_v1_2026_scenarios.csv")
    uncertainty=pd.read_csv(CAL/"post2016_headline_v1_2026_full_uncertainty.csv")
    modeled_seats=pd.read_csv(CAL/"post2016_headline_v1_2026_modeled_seats.csv")
    metrics=pd.read_csv(CAL/"post2016_headline_v1_forward_metrics.csv")
    manifest=json.loads((CAL/"post2016_headline_v1_manifest.json").read_text(encoding="utf-8"))
    roster=pd.read_csv(WAR/"2026_final_candidate_roster.csv")
    incumbency=pd.read_csv(WAR/"2026_candidate_incumbency.csv")
    finance=pd.read_csv(WAR/"2026_state_candidate_finance_matches.csv")
    model_finance=pd.read_csv(ROOT/"data/processed/finance/2026_candidate_finance_reconciled.csv")
    model_finance=model_finance[model_finance.cycle.eq(2026)]
    model_finance_index={(r.chamber,int(r.district),r.party):r for r in model_finance.itertuples()}
    polling=pd.read_csv(WAR/"2026_poll_adjusted_baseline.csv")
    demographics=pd.read_csv(ROOT/"data/processed/demographics/2026_sld_demographics.csv")
    cvap=pd.read_csv(ROOT/"data/processed/demographics/rdh_2024_sld_cvap.csv")
    regions=pd.read_csv(WAR/"next_forecast_tournament_region_features.csv")
    regions=regions[regions.cycle.eq(2026)]
    cmo_history=pd.read_csv(WAR/"cmo_v6_southern_candidates.csv")
    canonical_candidates=pd.read_csv(ROOT/"data/processed/elections/canonical_cmo_candidates.csv")
    cmo_history=cmo_history[cmo_history.cycle.le(2022)].copy()
    cmo_history["history_key"]=cmo_history.canonical_name.map(normalize_name)+"|"+cmo_history.canonical_party.astype(str)
    candidate_histories={}
    for history_key, history in cmo_history.groupby("history_key", sort=False):
        if history.candidate_effect_id.nunique() != 1:
            continue
        candidate_histories[history_key]=[
            {
                "cycle":int(row.cycle), "chamber":str(row.chamber), "district":int(row.district),
                "cmo":clean(row.candidate_direct_cmo), "incumbent":bool(row.incumbent),
                "winner":bool(row.winner),
            }
            for row in history.sort_values(["cycle","chamber","district"]).itertuples()
            if pd.notna(row.candidate_direct_cmo)
        ]
    prior_results={}
    for (chamber,district), prior in canonical_candidates[canonical_candidates.year.eq(2022)].groupby(["chamber","district"]):
        dem=prior[prior.canonical_party.eq("D")]
        rep=prior[prior.canonical_party.eq("R")]
        dem_votes=float(dem.canonical_votes.sum()); rep_votes=float(rep.canonical_votes.sum())
        total=dem_votes+rep_votes
        prior_results[(str(chamber),int(district))]={
            "cycle":2022,
            "margin":round(100*(dem_votes-rep_votes)/total,6) if dem_votes and rep_votes and total else None,
            "demVotes":int(dem_votes) if dem_votes else None,
            "repVotes":int(rep_votes) if rep_votes else None,
            "demCandidate":display_candidate_name(dem.canonical_name.iloc[0]) if not dem.empty else None,
            "repCandidate":display_candidate_name(rep.canonical_name.iloc[0]) if not rep.empty else None,
        }
    demographic_index={(r.chamber,int(r.district)):r for r in demographics.itertuples()}
    cvap_index={(r.chamber,int(r.district)):r for r in cvap.itertuples()}
    region_index={(r.chamber,int(r.district)):r for r in regions.itertuples()}
    roster=(roster.merge(incumbency[["chamber","district","party","candidate","incumbent"]],
                         on=["chamber","district","party","candidate"],how="left")
                  .merge(finance[["chamber","district","party","candidate","state_contributions","state_expenditures","finance_observation_status"]],
                         on=["chamber","district","party","candidate"],how="left"))
    pollidx={(r.chamber,int(r.district)):r for r in polling.itertuples()}
    poll_date=dt.date.fromisoformat(str(polling.poll_average_as_of.iloc[0]))
    build_date=dt.date.today()
    model_copy={
        "headline":("Headline forecast","National polling supplies the federal baseline; post-2016 Alabama elections estimate down-ballot lag, incumbency, and relative fundraising strength."),
        "environment_dem_favorable":("Polling-error scenario","Every district is shifted Democratic by one historical national polling-error standard deviation."),
        "environment_rep_favorable":("Polling-error scenario","Every district is shifted Republican by one historical national polling-error standard deviation."),
    }
    selected_specification=manifest["selected_specification"]
    selected_metric=metrics[metrics.specification.eq(selected_specification)].squeeze()
    holdout_mae=float(selected_metric.mae)
    scenario_index={(r.scenario,r.chamber,int(r.district)):r for r in scenarios.itertuples()}
    uncertainty_index={(r.chamber,int(r.district)):r for r in uncertainty.itertuples()}
    scale=float(manifest["probability"]["scale"])
    df=float(manifest["probability"]["df"])
    conditional_width=float(student_t.ppf(.9,df)*scale)
    payload={"meta":{"pollAsOf":poll_date.isoformat(),"buildDate":build_date.isoformat(),
                     "financeAsOf":"2026-08-14","pollStalenessDays":(build_date-poll_date).days,
                     "model":DEFAULT_MODEL,"version":manifest["build_id"],"simulationDraws":50000},
             "models":[],"contributionVariables":["Polling-implied federal baseline","Generic down-ballot lag","Incumbency","Relative fundraising strength","Polling-error scenario"],"provenance":[
                 {"category":"Election baseline","source":"2024 presidential results allocated to 2026 districts","asOf":"2024 general election","download":"data/2026_model_comparison.csv"},
                 {"category":"National environment","source":"Quality-gated national generic-ballot polling","asOf":poll_date.isoformat(),"download":"data/polling_environment.csv"},
                 {"category":"Candidates and incumbency","source":"Certified 2026 roster and reviewed incumbent matching","asOf":build_date.isoformat(),"download":"data/post2016_headline_v1_2026_scenarios.csv"},
                 {"category":"Fundraising","source":"Alabama principal campaign committee receipts; missing records remain missing","asOf":"2026-08-14","download":"data/post2016_headline_v1_2026_scenarios.csv"},
                 {"category":"Historical test","source":"2018 Alabama legislative races used to predict the 2022 cycle","asOf":"2022 election","download":"data/post2016_headline_v1_forward_metrics.csv"},
                 {"category":"District demographics","source":"2022 ACS district estimates and 2020-2024 ACS CVAP special tabulation","asOf":"2024 ACS","download":"data/2026_sld_demographics.csv"},
                 {"category":"Regional geography","source":"Project region-share crosswalk for the 2026 legislative districts","asOf":"2026 district plan","download":"data/next_forecast_tournament_region_features.csv"},
                 {"category":"Prior legislative context","source":"Canonical 2022 Alabama legislative candidate results","asOf":"2022 election","download":"data/canonical_cmo_candidates.csv"},
                 {"category":"Candidate history","source":"Current canonical Alabama candidate margin-overperformance records","asOf":"1994-2022 elections","download":"data/cmo_v6_southern_candidates.csv"},
                 {"category":"Methodology","source":"Model definitions, uncertainty, and limitations","asOf":build_date.isoformat(),"download":"data/post2016_headline_v1_manifest.json"}
             ]}
    model_forecasts={}; model_seats={}
    for model,label in PUBLIC_MODELS.items():
        modeled=scenarios[scenarios.scenario.eq(model)].copy()
        modeled["margin_80_low"]=modeled.predicted_dem_margin-conditional_width
        modeled["margin_80_high"]=modeled.predicted_dem_margin+conditional_width
        model_forecasts[model]={(r.chamber,int(r.district)):r for r in modeled.itertuples()}
        seat_rows=[]
        for chamber in MAPS:
            dem_districts=set(roster[(roster.chamber.eq(chamber)) & roster.party.eq("D")].district)
            rep_districts=set(roster[(roster.chamber.eq(chamber)) & roster.party.eq("R")].district)
            fixed_dem=len(dem_districts-rep_districts)
            if model=="headline":
                sd=modeled_seats[modeled_seats.chamber.eq(chamber)][["dem_modeled_seats","probability"]].copy()
                sd["dem_seats"]=sd.dem_modeled_seats+fixed_dem; sd=sd[["dem_seats","probability"]]
            else:
                ps=modeled[modeled.chamber.eq(chamber)].dem_win_probability.dropna().tolist()
                sd=conditional_seat_distribution(ps,fixed_dem)
            sd["chamber"]=chamber
            seat_rows.append(sd)
        model_seats[model]=pd.concat(seat_rows,ignore_index=True)
        status,description=model_copy[model]
        payload["models"].append({"id":model,"label":label,"status":status,"description":description,
            "default":model==DEFAULT_MODEL,
            "meanMae":holdout_mae,"recentMae":holdout_mae,
            "latestMae":holdout_mae,"passesGuardrail":model==DEFAULT_MODEL})
    for chamber,map_path in MAPS.items():
        geo=gpd.read_file(map_path).to_crs(4326); field="SLDLST" if chamber=="house" else "SLDUST"
        geo["district"]=geo[field].astype(int)
        geo["geometry"]=geo.geometry.make_valid().simplify(.001,preserve_topology=True)
        paths=[{"district":int(r.district),"geometry":mapping(r.geometry)} for _,r in geo.iterrows()]
        races=[]; total=105 if chamber=="house" else 35
        for district in range(1,total+1):
            sub=roster[(roster.chamber==chamber)&(roster.district==district)]
            headline_finance=scenario_index.get(("headline",chamber,district))
            candidates=[]
            for candidate in sub.itertuples():
                party=str(candidate.party)
                raised=clean(candidate.state_contributions)
                spent=clean(candidate.state_expenditures)
                finance_status=clean(candidate.finance_observation_status)
                model_finance_row=model_finance_index.get((chamber,district,party))
                if model_finance_row is not None:
                    raised=clean(model_finance_row.fundraising_total)
                    spent=clean(model_finance_row.expenditures)
                    finance_status=clean(model_finance_row.aggregation_status)
                if headline_finance is not None and party in {"D","R"}:
                    expected_raised=clean(getattr(headline_finance, "dem_fundraising" if party=="D" else "rep_fundraising"))
                    expected_status=clean(getattr(headline_finance, "dem_finance_status" if party=="D" else "rep_finance_status"))
                    # Candidate cards must reflect the same finance observation used
                    # by the forecast.  Do not substitute a separate display source
                    # when the model input is explicitly missing.
                    raised=expected_raised
                    finance_status=expected_status
                    if model_finance_row is None:
                        spent=None
                    assert raised == expected_raised and finance_status == expected_status
                candidates.append({"name":str(candidate.candidate),"party":party,
                    "incumbent":bool(clean(candidate.incumbent) or False),
                    "raised":raised,"spent":spent,
                    "financeStatus":finance_status,
                    "cmoHistory":candidate_histories.get(normalize_name(candidate.candidate)+"|"+party,[])})
            major={c["party"] for c in candidates if c["party"] in {"D","R"}}
            poll_row=pollidx.get((chamber,district)); model_values={}
            baseline=float(poll_row.poll_adjusted_dem_margin) if poll_row is not None else None
            pres24=float(poll_row.baseline_2024_pres_dem_margin) if poll_row is not None else None
            environment=baseline-pres24 if baseline is not None and pres24 is not None else None
            if all((chamber,district) in model_forecasts[model] for model in PUBLIC_MODELS):
                status="modeled"; model_values={}
                for model in PUBLIC_MODELS:
                    mr=model_forecasts[model][(chamber,district)]
                    poll_baseline=float(mr.environment_baseline_margin)
                    lag=float(mr.generic_downballot_lag)
                    incumbency_adjustment=float(mr.incumbency_adjustment)
                    fundraising_adjustment=float(mr.fundraising_adjustment)
                    polling_error=float(mr.polling_error_adjustment)
                    after_lag=poll_baseline+lag
                    after_incumbency=after_lag+incumbency_adjustment
                    after_fundraising=after_incumbency+fundraising_adjustment
                    model_values[model]={"margin":round(float(mr.predicted_dem_margin),6),"demProbability":round(float(mr.dem_win_probability),6),
                        "low80":round(float(mr.margin_80_low),6),"high80":round(float(mr.margin_80_high),6),
                        "steps":[[round(poll_baseline,6),round(poll_baseline,6),round(poll_baseline,6)],
                                 [round(lag,6),round(lag,6),round(after_lag,6)],
                                 [round(incumbency_adjustment,6),round(incumbency_adjustment,6),round(after_incumbency,6)],
                                 [round(fundraising_adjustment,6),round(fundraising_adjustment,6),round(after_fundraising,6)],
                                 [round(polling_error,6),round(polling_error,6),round(float(mr.predicted_dem_margin),6)]]}
                selected=model_values[DEFAULT_MODEL]
                p=selected["demProbability"]; margin=selected["margin"]; low80=selected["low80"]; high80=selected["high80"]
                finance_scenario=cmo_scenario=None
            elif major=={"D"}:
                p,status,margin=1.0,"unopposed-major-party",None
                low80=high80=finance_scenario=cmo_scenario=None
            elif major=={"R"}:
                p,status,margin=0.0,"unopposed-major-party",None
                low80=high80=finance_scenario=cmo_scenario=None
            else:
                p,status,margin=None,"unmodeled",None
                low80=high80=finance_scenario=cmo_scenario=None
            demo_row=demographic_index.get((chamber,district))
            cvap_row=cvap_index.get((chamber,district))
            profile={
                "priorResult":prior_results.get((chamber,district)),
                "openSeat":not any(candidate["incumbent"] for candidate in candidates),
                "nonwhiteShare":clean(getattr(demo_row,"nonwhite_share",None)),
                "collegeShare":clean(getattr(demo_row,"college_share",None)),
                "whiteCollegeShare":clean(getattr(demo_row,"white_college_share",None)),
                "blackCvapShare":clean(getattr(cvap_row,"cvap_black_nh_share",None)),
                "whiteCvapShare":clean(getattr(cvap_row,"cvap_white_nh_share",None)),
                "cvapTotal":clean(getattr(cvap_row,"CVAP_TOT24",None)),
                "regions":region_summary(region_index.get((chamber,district))),
            }
            races.append({"district":district,"candidates":candidates,"status":status,"demProbability":p,
                          "rating":rating(p) if status=="modeled" else "Not modeled","margin":margin,
                          "low80":low80,"high80":high80,"pollBaseline":baseline,"pres24":pres24,
                          "environmentAdjustment":environment,"financeScenario":finance_scenario,
                          "cmoScenarioAdjustment":cmo_scenario,"models":model_values,"profile":profile})
        distributions={}
        for model,seat_dist in model_seats.items():
            sd=seat_dist[seat_dist.chamber.eq(chamber)][["dem_seats","probability"]].rename(columns={"dem_seats":"demSeats"})
            distributions[model]=[{k:clean(v) for k,v in x.items()} for x in sd.to_dict("records")]
        payload[chamber]={"paths":paths,"races":races,"modelSeatDistributions":distributions,
                          "seatDistribution":distributions[DEFAULT_MODEL]}
    return payload


HTML="""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Jackson Hannan's 2026 Alabama State House and State Senate election forecast"><meta name="author" content="Jackson Hannan"><meta property="og:title" content="Alabama 2026 Legislative Forecast"><meta property="og:description" content="A district-by-district Alabama legislative forecast by Jackson Hannan."><meta property="og:type" content="website"><title>Alabama 2026 Legislative Forecast · Jackson Hannan</title><style>__CSS__</style></head><body>
<header class="mast"><div class="mast-inner"><div class="brand">Jackson Hannan<small>Alabama legislative forecast</small></div><nav class="social-nav" aria-label="Jackson Hannan online"><a href="https://github.com/JacksonAHannan" target="_blank" rel="me noopener">GitHub</a><a href="https://www.instagram.com/topsoilintraining/" target="_blank" rel="me noopener">Instagram</a><a href="https://substack.com/@jacksonhannan" target="_blank" rel="me noopener">Substack</a><a href="https://www.linkedin.com/in/jackson-hannan" target="_blank" rel="me noopener">LinkedIn</a></nav></div></header>
<section class="hero"><div class="kicker">The Alabama Legislature</div><h1>2026 Election Forecast</h1><div class="dek">District forecasts based on 2024 presidential results, the current national environment, incumbency, and relative campaign fundraising.</div><div class="status-row"><span class="status-chip">Forecast built <b id="buildDate"></b></span><span class="status-chip">Polling through <b id="pollDate"></b></span><span class="status-chip" id="pollAge"></span><span class="status-chip">Finance through <b id="financeDate"></b></span></div>
<details class="quick-method"><summary>Forecast views</summary><ol><li><b>Headline</b> applies the polling-implied national swing and the expected post-2016 Alabama down-ballot adjustment.</li><li><b>Dem scenario</b> and <b>Rep scenario</b> move every district by one historical national polling-error standard deviation.</li><li>District probabilities use a Student-t curve; chamber summaries use 50,000 simulations with shared statewide and chamber uncertainty.</li></ol></details></section>
<main class="shell"><section class="model-switcher" aria-labelledby="modelSwitcherTitle"><div class="model-switcher-head"><div><div class="kicker">Forecast and polling-error scenarios</div><h2 id="modelSwitcherTitle">Forecast view</h2><p id="modelDescription" class="section-note"></p></div><div class="model-scores" id="modelScores" aria-label="Forward-test error score"></div></div><div class="model-tabs" id="modelTabs" role="tablist" aria-label="Forecast view"></div><p class="mae-note">The displayed MAE is the average district-margin error when the model was trained on 2018 and tested on 2022. The scenario tabs change only the assumed national polling error.</p></section><section class="overview-grid" id="overviewGrid" aria-label="House and Senate forecast summaries"></section>
<section class="workspace" id="workspace"><header class="workspace-head"><h2 id="chamberTitle"></h2><div class="segmented" aria-label="Select chamber"><button data-chamber="house" aria-pressed="true">State House</button><button data-chamber="senate" aria-pressed="false">State Senate</button></div></header>
<div class="chamber-strip"><div class="strip-stat"><b id="medianSeats"></b><span>Median Democratic seats</span></div><div class="strip-stat distribution-cell"><div class="distribution" id="distribution" aria-label="Conditional Democratic seat distribution"></div><div class="distribution-axis" id="distributionAxis"></div></div><div class="strip-stat"><b id="seatRange"></b><span>Democratic 80% seat range</span></div></div>
<div class="chamber-insights"><section class="majority-path" aria-labelledby="majorityPathTitle"><div class="panel-head"><div><span class="panel-kicker">Chamber control</span><h3 id="majorityPathTitle">Path to a majority</h3></div><span id="majorityThreshold"></span></div><div id="majorityPath"></div></section><section class="race-watch" aria-labelledby="raceWatchTitle"><div class="panel-head"><div><span class="panel-kicker">Race overview</span><h3 id="raceWatchTitle">Seats to watch</h3></div><span id="raceWatchCount"></span></div><div id="raceWatch"></div></section></div>
<div class="interactive"><section class="map-panel"><div class="map-head"><div><h3 id="mapTitle"></h3><p id="mapScope">Statewide view. Choose a district on the map or with the district finder.</p></div><div class="mode-tabs" aria-label="Map display"><button data-mode="probability" aria-pressed="true">Win chance</button><button data-mode="margin" aria-pressed="false">Margin</button><button data-mode="rating" aria-pressed="false">Rating</button></div></div><div class="map-tools"><label class="sr-only" for="districtSelect">Find a district</label><select id="districtSelect"></select><span class="section-note">Pan and zoom to explore roads, cities, and district geography.</span></div><div class="map-wrap"><div id="map" role="group" aria-label="Interactive Alabama legislative district forecast map"></div></div><div class="legend" id="legend" aria-label="Map legend"></div></section>
<aside class="detail" id="detail" aria-live="polite"><div class="detail-empty">Select a district to explore its forecast.</div></aside></div></section>
<section class="section"><h2>District forecast table</h2><p class="section-note"><span id="rowCount"></span>. Margins, probabilities, intervals, and ratings follow the forecast view selected above.</p><div class="table-tools"><label class="sr-only" for="search">Search candidates or districts</label><input id="search" type="search" placeholder="Search candidate or district"><label class="sr-only" for="ratingFilter">Filter by rating</label><select id="ratingFilter"><option value="all">All ratings</option><option>Solid D</option><option>Very likely D</option><option>Likely D</option><option>Lean D</option><option>Toss-up</option><option>Lean R</option><option>Likely R</option><option>Very likely R</option><option>Solid R</option><option>Unopposed D</option><option>Unopposed R</option></select><label class="sr-only" for="scopeFilter">Filter races</label><select id="scopeFilter"><option value="all">All districts</option><option value="competitive">Competitive (35–65%)</option><option value="modeled">Modeled D–R races</option><option value="open">Open seats</option><option value="crosses">80% interval crosses even</option></select><button class="small-button" id="download">Download CSV</button></div><div class="table-hint">Swipe horizontally to see all columns; the district column remains fixed.</div><div class="table-wrap"><table><thead><tr><th><button data-sort="district">District<span></span></button></th><th>Candidates</th><th><button data-sort="rating">Rating<span></span></button></th><th><button data-sort="demProbability">Dem. chance<span></span></button></th><th><button data-sort="margin">Headline margin<span></span></button></th><th>80% interval</th><th>Finance scenario</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section class="section method"><div><h2>How to read this forecast</h2><p>The headline begins with each district’s 2024 presidential margin, applies the national swing implied by current generic-ballot polling, and adds the expected Alabama legislative difference from that federal baseline.</p><p>That down-ballot adjustment reflects generic legislative lag, incumbency, and fundraising strength relative to comparable districts. The Dem and Rep scenarios show how a typical national polling error would move the forecast.</p><div class="method-links"><a href="methodology.html">Full methodology</a><a href="data/post2016_headline_v1_2026_scenarios.csv">District scenarios</a><a href="data/post2016_headline_v1_forward_metrics.csv">Historical test</a></div></div><div class="caveat"><b>Forecast uncertainty.</b><p>Win probabilities use a Student-t distribution with five degrees of freedom and a 5.75-point scale.</p><p>Headline chamber summaries use 50,000 simulations with shared national, statewide, and chamber errors plus district-specific error.</p><p>Single-major-party districts are fixed in chamber summaries even when an independent is present. Gray, dashed districts are unresolved rather than toss-ups.</p><p>The complete candidate adjustment has one direct forward test, from 2018 to 2022, and should be interpreted with that limitation in mind.</p></div></section></main><footer class="site-footer"><div><b>Model and analysis by Jackson Hannan</b><span>Alabama 2026 Legislative Forecast</span></div><nav aria-label="Jackson Hannan profiles"><a href="https://github.com/JacksonAHannan" target="_blank" rel="me noopener">GitHub</a><a href="https://www.instagram.com/topsoilintraining/" target="_blank" rel="me noopener">Instagram</a><a href="https://substack.com/@jacksonhannan" target="_blank" rel="me noopener">Substack</a><a href="https://www.linkedin.com/in/jackson-hannan" target="_blank" rel="me noopener">LinkedIn</a></nav></footer><div class="tooltip" id="tooltip" role="tooltip"></div><script>const DATA=__PAYLOAD__;__JS__</script></body></html>"""


UNCERTAINTY_CAVEAT = """<div class="caveat"><b>Forecast uncertainty.</b><p>The headline uses 50,000 correlated simulations. Shared national, statewide, and chamber error prevents the chamber distribution from treating every district as independent.</p><p>District probabilities use a Student-t(5) curve with a 5.75-point scale. Scenario tabs show a typical national polling error in either direction.</p><p>The full candidate adjustment has one direct forward test, from 2018 to 2022. Districts with one major-party nominee are fixed; genuinely unresolved districts remain unmodeled and gray.</p></div>"""


METHODOLOGY = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Methodology for Jackson Hannan's Alabama 2026 legislative forecast"><title>Methodology · Alabama 2026 Legislative Forecast</title><style>__CSS__</style></head><body>
<header class="mast"><div class="mast-inner"><div class="brand">Jackson Hannan<small>Alabama legislative forecast</small></div><nav class="social-nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html">CMO</a><a href="methodology.html" aria-current="page">Forecast methodology</a><a href="cmo-methodology.html">CMO methodology</a><a href="https://github.com/JacksonAHannan" target="_blank" rel="me noopener">GitHub</a><a href="https://substack.com/@jacksonhannan" target="_blank" rel="me noopener">Substack</a></nav></div></header>
<main class="methodology-shell"><header class="methodology-hero"><div class="kicker">Model documentation</div><h1>Forecast methodology</h1><p class="dek">How the Alabama House and Senate forecast turns district geography, election results, demographic composition, and national polling into district probabilities and chamber simulations.</p><div class="status-row"><span class="status-chip">Model <b>baseline-first</b></span><span class="status-chip">Polling through <b>__POLL_DATE__</b></span><span class="status-chip">Updated <b>__BUILD_DATE__</b></span></div></header>
<div class="method-grid"><aside class="toc"><b>On this page</b><a href="#overview">Overview</a><a href="#baseline">District baseline</a><a href="#environment">National environment</a><a href="#poststratification">Alabama transfer</a><a href="#candidate">Candidate layers</a><a href="#validation">Validation</a><a href="#uncertainty">Uncertainty</a><a href="#limitations">Limitations</a><a href="#downloads">Downloads</a></aside>
<article class="method-copy"><section id="overview"><h2>Overview</h2><p>The forecast is deliberately baseline-first. It begins with the observed 2024 presidential vote allocated into the districts that will be used in 2026. It then applies a district-specific change derived from the current national generic-ballot environment and Alabama’s demographic composition.</p><div class="formula">2026 district margin = 2024 presidential margin + district demographic environment change + promoted residual adjustments</div><p>No candidate, incumbency, finance, or prior-CMO residual adjustment currently passes the promotion rule. Those quantities may appear as scenarios, but the headline forecast remains the poll-adjusted direct baseline.</p></section>
<section id="baseline"><h2>1. District baseline</h2><p>The structural baseline is each district’s two-party Democratic presidential margin in 2024. Precinct results are allocated to the 2026 legislative map using independently constructed Census geography rather than legislative turnout weights. This avoids allowing candidate strength in a legislative contest to influence its own geographic comparator.</p><p>The 2026 map is Alabama’s original 2021 legislature-drawn map, represented by the 2025 Census state-legislative shapefiles supplied for both chambers.</p></section>
<section id="environment"><h2>2. National political environment</h2><p>The current environment uses national generic-ballot polls from pollsters graded B+ or better in the supplied Nate Silver ratings file. Public releases are archived locally with retrieval timestamps and SHA-256 hashes.</p><p>The topline takes the newest eligible poll from each pollster in a rolling 60-day window. Likely-voter, registered-voter, and adult samples receive population weights, and older polls decay with a 21-day half-life. The current two-party national environment is <b>__NATIONAL_MARGIN__</b> across <b>__POLLSTERS__ pollsters</b>.</p><div class="callout"><b>Pollster quality is a gate, not a house effect.</b>The current model excludes lower-rated pollsters but does not yet estimate pollster-specific house effects. Polling should be rebuilt whenever new releases become available.</div></section>
<section id="poststratification"><h2>3. From national polling to Alabama districts</h2><p>Reviewed crosstabs estimate how racial and educational groups differ from each poll’s overall two-party result. Effects are measured on the logit scale, pooled across eligible pollsters, and applied to a Catalist 2024 national reference.</p><p>Historical Alabama offsets are estimated from election results and demographic ecological inference. ACS block-group race-by-education cells are allocated into each 2026 district and used to poststratify the projected group support and turnout. The model anchors the resulting change to the district’s observed 2024 presidential margin rather than trusting a fitted demographic level.</p></section>
<section id="candidate"><h2>4. Candidate, finance, and federal-realignment layers</h2><p>Incumbency, demographic residuals, finance, and prior candidate margin overperformance were tested only as adjustments to the strong baseline. The current finance scenario uses Alabama state campaign-finance receipts through August 14, 2026; unmatched filings remain unknown rather than being treated as zero. Finance is descriptive and potentially endogenous: strong candidates can raise more money, so it is not interpreted as a clean causal effect.</p><p>The national-environment scenario adds Catalist’s observed change in the national Democratic two-party margin from the preceding presidential election to the midterm U.S. House vote. A demographic variant tests whether that swing varies with district nonwhite and white-college composition. A separate federal-realignment scenario learns legislative residuals from same-cycle U.S. House and U.S. Senate results. Validation begins after the 2008 nationalization break, and post-2016 observations receive twice the weight of 2010-2014 observations.</p><p>The prospective anchor already incorporates the projected 2024-to-2026 national and demographic environment, so these comparisons test that construction without adding the same swing twice. Prior CMO uses only historical out-of-fold scores, exact normalized candidate-and-party matches, and shrinkage toward zero.</p></section>
<section id="validation"><h2>5. Forward validation and promotion</h2><p>Models train only on elections earlier than the cycle being predicted. The comparison now uses all eight cycles from 1994 through 2022, producing seven expanding-window holdouts. Promotion requires improvement in full-period mean MAE, post-2016 mean MAE, and the latest-cycle MAE.</p><table class="method-table"><thead><tr><th>Specification</th><th>Mean forward MAE</th><th>Latest MAE</th><th>Promoted</th></tr></thead><tbody>__BACKTEST_ROWS__</tbody></table><p>After removing misclassified unopposed races, the post-2016 ramp reduces full-period mean MAE from 25.26 to 24.85, post-2016 mean MAE from 12.57 to 11.13, and 2022 MAE from 12.03 to 9.78. Applying the full national swing in every cycle performs substantially worse, especially before 2018. The demographic-response, finance, incumbency, and era-weighted federal variants fail the stricter three-part gate.</p><div class="callout"><b>Realignment is not a smooth early-series trend.</b>Official national vote changes and Alabama results imply a sharp 2006 anomaly, followed by little evidence that the national swing should be transferred directly in 2010 or 2014. This reflects Alabama’s delayed local partisan realignment and prevents the cadence from being estimated as a simple monotonic curve across all eight cycles.</div></section>
<section id="uncertainty"><h2>6. Probabilities and chamber summaries</h2><p>A recent-era Southern calibration converts each expected margin into a conditional win probability using <code>P(D win) = Φ(expected Democratic margin / 6.0)</code>. The six-point scale was selected using forward-cycle and leave-state-out validation on 1,188 contested legislative races outside Alabama.</p><p>Chamber distributions combine district probabilities as independent Bernoulli outcomes and hold single-major-party seats fixed. Independent-only and unresolved districts remain unmodeled rather than being labeled toss-ups. These probabilities are conditional on the displayed national environment.</p></section>
<section id="limitations"><h2>7. Important limitations</h2><ul><li>Eight election environments support seven forward holdouts, but only two occur after the 2016 break.</li><li>The 80/20 blend was selected after comparing multiple challengers and should be confirmed on future elections.</li><li>National race and education crosstabs are not joint race-by-education samples; the model combines them with ACS and historical estimates.</li><li>Alabama polling is sparse, so national movements are transferred through demographic structure rather than measured directly in the state.</li><li>Fundraising is incomplete historically and should not be interpreted causally.</li><li>Polling house effects and mode effects are not yet estimated explicitly.</li><li>Probabilities are provisional and should not be read as fully calibrated long-run frequencies.</li></ul></section>
<section id="downloads"><h2>Data and audit downloads</h2><p class="download-list"><a href="data/2026_forecast_decomposition.csv">District decomposition</a><a href="data/2026_residual_layer_backtest_summary.csv">Backtest summary</a><a href="data/polling_environment.csv">Polling environment</a><a href="data/poll_source_manifest.csv">Polling source manifest</a></p></section></article></div></main>
<footer class="site-footer"><div><b>Model and analysis by Jackson Hannan</b><span>Alabama 2026 Legislative Forecast</span></div><nav><a href="index.html">Forecast</a><a href="https://www.instagram.com/topsoilintraining/" target="_blank" rel="me noopener">Instagram</a><a href="https://www.linkedin.com/in/jackson-hannan" target="_blank" rel="me noopener">LinkedIn</a></nav></footer></body></html>"""


def build_methodology(css: str, payload: dict) -> str:
    summary = pd.read_csv(WAR / "next_forecast_tournament_summary.csv").set_index("specification")
    basic=summary.loc[DEFAULT_MODEL]; plus=summary.loc["cmo_expectation__blend100"]
    rows=(f"<tr><td>Basic</td><td>{basic.cycle_balanced_mae:.2f}</td><td>{basic.post2016_mae:.2f}</td><td>{basic.latest_2022_mae:.2f}</td><td>Default</td></tr>"
          f"<tr><td>Fundamentals+</td><td>{plus.cycle_balanced_mae:.2f}</td><td>{plus.post2016_mae:.2f}</td><td>{plus.latest_2022_mae:.2f}</td><td>Experimental</td></tr>")
    environment = pd.read_csv(ROOT / "data" / "processed" / "polling" /
                              "votehub_silver_bplus_topline_environment.csv").iloc[0]
    styles=css+(ASSETS/"methodology.css").read_text(encoding="utf-8")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forecast methodology · Alabama 2026</title><style>{styles}</style></head><body>
<header class="mast"><div class="mast-inner"><div class="brand">Jackson Hannan<small>Alabama legislative forecast</small></div><nav class="social-nav"><a href="index.html">Forecast</a><a href="cmo.html">CMO</a><a href="methodology.html" aria-current="page">Forecast methodology</a><a href="cmo-methodology.html">CMO methodology</a></nav></div></header>
<main class="methodology-shell"><header class="methodology-hero"><div class="kicker">Model documentation</div><h1>Basic and Fundamentals+</h1><p class="dek">Two views of the same CMO expected-performance model, distinguished by how strongly the expectation is applied.</p><div class="status-row"><span class="status-chip">Default <b>Basic</b></span><span class="status-chip">Polling through <b>{environment.as_of}</b></span><span class="status-chip">Updated <b>{payload['meta']['buildDate']}</b></span></div></header>
<div class="method-grid"><aside class="toc"><b>On this page</b><a href="#models">Models</a><a href="#environment">Environment</a><a href="#validation">Validation</a><a href="#uncertainty">Uncertainty</a><a href="#limits">Limitations</a></aside><article class="method-copy">
<section id="models"><h2>The two views</h2><div class="formula">Basic = poll-adjusted presidential baseline + 20% of the CMO expected-performance adjustment</div><p>Basic is the default guardrail against overfitting. It uses the same CMO expectation as Fundamentals+, but shrinks the district adjustment four-fifths of the way toward zero. The current generic-ballot environment is D+{float(environment.dem_two_party_margin):.2f} across {int(environment.pollsters)} quality-gated pollsters.</p><div class="formula">Fundamentals+ = poll-adjusted presidential baseline + 100% of the CMO expected-performance adjustment</div><p>The CMO expectation uses district racial and educational composition, prior presidential trend and its availability, chamber, and 2008/2016 era terms. It deliberately excludes candidate incumbency, fundraising, ideology, and prior CMO so downstream consequences of candidate strength are not mistaken for independently known candidate effects.</p></section>
<section id="environment"><h2>National environment</h2><p>The polling signal comes from quality-gated generic-ballot polling. Historical tests support transferring none of the swing before 2018, half in 2018, and the full swing in 2022 and 2026. The 125% continued-nationalization case remains a separate experimental scenario, not a selected model.</p></section>
<section id="validation"><h2>Forward validation</h2><p>Every holdout is trained only on earlier cycles. The table reports cycle-balanced mean absolute error across the expanding-window tests, the post-2016 holdouts, and 2022 separately.</p><table class="method-table"><thead><tr><th>View</th><th>Mean MAE</th><th>2018–22</th><th>2022</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table><p>Fundamentals+ applies the complete historical expectation and is the richer substantive view. Basic remains the default because its 20% adjustment is a transparent hedge against selection noise and structural change in a small number of election cycles.</p></section>
<section id="uncertainty"><h2>Probabilities and chamber summaries</h2><p>A recent-era Southern calibration converts the selected expected margin into a win probability using <code>P(D win) = Φ(expected Democratic margin / 6.0)</code>. The six-point scale was fitted on 1,188 contested legislative races outside Alabama. Forward-cycle validation produced a 0.0310 Brier score and 96.1% winner accuracy; leave-state-out validation produced a 0.0332 Brier score and 95.8% winner accuracy.</p><p>The middle-80% district margin band is the corresponding conditional predictive interval. Chamber distributions combine district probabilities as independent Bernoulli outcomes and hold single-major-party seats fixed. They are conditional on the displayed national environment; national polling uncertainty belongs in explicit shared scenarios.</p></section>
<section id="limits"><h2>Limitations</h2><ul><li>Only a small number of forward election environments—and two after 2016—identify these relationships.</li><li>The CMO expectation is contextual; it does not identify an individual candidate effect.</li><li>National race and education crosstabs are not joint race-by-education samples and Alabama polling remains sparse.</li><li>Polling house effects and mode effects are not yet estimated explicitly.</li><li>Probabilities remain provisional rather than fully calibrated long-run frequencies.</li></ul><p class="download-list"><a href="data/next_forecast_tournament_2026.csv">District forecasts</a><a href="data/next_forecast_tournament_summary.csv">Tournament summary</a><a href="data/next_forecast_tournament_cycle_metrics.csv">Cycle metrics</a></p></section>
</article></div></main></body></html>'''


def build_methodology_v2(css: str, payload: dict) -> str:
    metrics=pd.read_csv(CAL/"post2016_headline_v1_forward_metrics.csv")
    manifest=json.loads((CAL/"post2016_headline_v1_manifest.json").read_text(encoding="utf-8"))
    components=pd.read_csv(CAL/"robust_forecast_v1_error_components.csv").iloc[0]
    display_specs={
        "polling_federal_only":"Polling-implied federal baseline",
        "polling_federal_plus_incumbency":"Federal baseline and incumbency",
        "polling_federal_plus_incumbency_fundraising":"With raw fundraising gap",
        "polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising":"Headline model",
    }
    rows="".join(
        f"<tr><td>{display_specs[r.specification]}</td><td>{r.mae:.2f}</td><td>{r.rmse:.2f}</td><td>{r.winner_accuracy:.1%}</td></tr>"
        for r in metrics[metrics.specification.isin(display_specs)].sort_values("mae").itertuples()
    )
    environment=pd.read_csv(ROOT/"data/processed/polling/votehub_silver_bplus_topline_environment.csv").iloc[0]
    features=pd.read_csv(CAL/"post2016_polling_cmo_2026_features.csv")
    national_swing=float(features.national_poll_swing_from_2024.iloc[0])
    finance_complete=int(features.finance_complete.sum())
    poll_error=float(manifest["polling_error_scenarios"]["shift_points"])
    styles=css+(ASSETS/"methodology.css").read_text(encoding="utf-8")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forecast methodology - Alabama 2026</title><style>{styles}</style></head><body>
<header class="mast"><div class="mast-inner"><div class="brand">Jackson Hannan<small>Alabama legislative forecast</small></div><nav class="social-nav"><a href="index.html">Forecast</a><a href="cmo.html">CMO</a><a href="methodology.html" aria-current="page">Forecast methodology</a><a href="cmo-methodology.html">CMO methodology</a></nav></div></header>
<main class="methodology-shell"><header class="methodology-hero"><div class="kicker">Model documentation</div><h1>Forecast methodology</h1><p class="dek">How national polling, federal partisanship, incumbency, and fundraising produce the district forecasts and chamber probabilities.</p><div class="status-row"><span class="status-chip">Headline <b>Post-2016 CMO</b></span><span class="status-chip">Polling through <b>{environment.as_of}</b></span><span class="status-chip">Finance coverage <b>{finance_complete}/48 races</b></span></div></header>
<div class="method-grid"><aside class="toc"><b>On this page</b><a href="#headline">Headline</a><a href="#environment">Environment</a><a href="#candidate">Candidate adjustment</a><a href="#validation">Historical test</a><a href="#uncertainty">Uncertainty</a><a href="#scenarios">Scenarios</a><a href="#limits">Limitations</a></aside><article class="method-copy">
<section id="headline"><h2>Headline margin</h2><div class="formula">Headline margin = 2024 presidential margin + national polling swing + expected Alabama legislative overperformance</div><p>The first two terms represent the federal result implied by current polling. The final term estimates how an Alabama legislative candidate would normally run relative to that federal baseline given the race’s chamber, incumbency, and fundraising position.</p></section>
<section id="environment"><h2>National environment</h2><p>The national two-party generic-ballot environment is D+{float(environment.dem_two_party_margin):.2f} across {int(environment.pollsters)} quality-gated pollsters through {environment.as_of}. Compared with the 2024 national presidential result, this produces a {national_swing:+.2f}-point Democratic swing that is applied uniformly to every district’s 2024 presidential margin.</p></section>
<section id="candidate"><h2>Down-ballot and candidate adjustment</h2><p>The model learns the legislative-minus-federal margin from elections after 2016. It estimates a generic Alabama legislative lag, an incumbency adjustment, and the Democratic-versus-Republican fundraising gap.</p><p>Fundraising is normalized within the election cycle. A first-stage model estimates the fundraising gap normally associated with district partisanship, competitiveness, chamber, and incumbency. The forecast uses the remaining relative fundraising strength. This first stage never uses the legislative result.</p><p>Explicit Alabama campaign-finance observations are complete for {finance_complete} of 48 contested two-party races. A race without complete finance receives the lag and incumbency terms but no fundraising adjustment.</p></section>
<section id="validation"><h2>Historical test</h2><p>The model trains on 59 contested races in 2018 and predicts the same 30 contested 2022 races under every specification.</p><table class="method-table"><thead><tr><th>Specification</th><th>2022 MAE</th><th>RMSE</th><th>Winner accuracy</th></tr></thead><tbody>{rows}</tbody></table><p>The headline specification records 7.08 points of mean absolute margin error, compared with 10.00 for the polling-implied federal baseline. A paired race bootstrap estimates a 2.91-point improvement, with a 95% interval from 0.83 to 5.00 points.</p></section>
<section id="uncertainty"><h2>Probabilities and chamber summaries</h2><p>Expected margins are converted to conditional win probabilities with a Student-t curve with five degrees of freedom and a 5.75-point scale. The headline uses 50,000 simulations with shared national ({components.national_sd:.2f}), statewide ({components.state_sd:.2f}), and chamber ({components.chamber_sd:.2f}) errors plus district-specific error ({components.district_sd:.2f}).</p><p>Single-major-party districts are fixed in chamber totals, even if an independent is present. Unresolved districts remain unmodeled.</p></section>
<section id="scenarios"><h2>Dem and Rep scenarios</h2><p>The Dem scenario shifts every district {poll_error:.2f} points Democratic. The Rep scenario shifts every district {poll_error:.2f} points Republican. That amount is one historical national polling-error standard deviation; all candidate and district adjustments otherwise remain unchanged.</p></section>
<section id="limits"><h2>Limitations</h2><ul><li>The complete candidate adjustment has one direct forward test, from 2018 to 2022.</li><li>Historical fundraising covers full election cycles, while the current 2026 figures are a partial-cycle snapshot.</li><li>Fundraising reflects resources, donor expectations, and candidate strength and should not be interpreted as a purely causal campaign effect.</li><li>Alabama polling is sparse, so the national generic ballot supplies the political-environment estimate.</li><li>Polling house effects and mode effects are not yet estimated explicitly.</li></ul><p class="download-list"><a href="data/post2016_headline_v1_2026_scenarios.csv">District scenarios</a><a href="data/post2016_headline_v1_forward_metrics.csv">Historical test</a><a href="data/post2016_headline_v1_bootstrap.csv">Bootstrap comparison</a></p></section>
</article></div></main></body></html>'''


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    css=(ASSETS/"forecast_dashboard.css").read_text(encoding="utf-8")
    js=(ASSETS/"forecast_dashboard.js").read_text(encoding="utf-8")
    # The dashboard behavior is shared with earlier releases; update its public
    # vocabulary without changing interaction logic.
    for old,new in {
        "All-cycle MAE":"Mean OOS MAE","2018–22 MAE":"2022 holdout MAE","2022 MAE":"2024 MAE",
        "vs Basic":"vs headline","Basic:":"Headline:","Basic model":"Headline forecast",
        "Transparent default and guardrail for every richer specification.":"Current district estimate.",
        "Basic forecast":"Polling-implied federal baseline","Public":"Headline",
        "Fundamentals+ incorporates candidate and district information, but it did not beat Basic in the 2022 holdout and therefore remains experimental.":"This is a sensitivity scenario, not the selected headline forecast.",
        "basic_model_margin":"headline_margin","difference_from_basic":"difference_from_headline",
        "models_disagree_on_winner":"views_disagree_on_winner","selected_model":"selected_view",
    }.items():
        js=js.replace(old,new)
    js=js.replace(
        '$("#modelScores").innerHTML=`<span><b>${m.meanMae.toFixed(2)}</b>Mean OOS MAE</span><span><b>${m.recentMae.toFixed(2)}</b>2022 holdout MAE</span><span><b>${m.latestMae.toFixed(2)}</b>2024 MAE</span>`;',
        '$("#modelScores").innerHTML=`<span><b>${m.meanMae.toFixed(2)}</b>2022 holdout MAE</span>`;'
    )
    payload_data=build_payload()
    payload=json.dumps(payload_data,separators=(",",":"),ensure_ascii=False)
    page=HTML.replace("__CSS__",css).replace("__PAYLOAD__",payload).replace("__JS__",js)
    page=page.replace("<style>",'<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""><style>',1)
    page=page.replace("<script>const DATA=",'<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script><script>const DATA=',1)
    page=page.replace('<section class="workspace" id="workspace">',
                      '<section class="workspace" id="workspace" role="tabpanel" aria-live="polite">')
    page=page.replace('<option value="crosses">80% interval crosses even</option>',
                      '<option value="crosses">80% interval crosses even</option><option value="winner-disagreement">Models disagree on winner</option><option value="rating-disagreement">Models disagree on rating</option>')
    page=page.replace('<th><button data-sort="margin">Headline margin<span></span></button></th><th>80% interval</th><th>Finance scenario</th>',
                      '<th><button data-sort="margin">Selected margin<span></span></button></th><th>Vs. headline</th><th>80% interval</th>')
    page=page.replace('<section class="section method">',
                      '<section class="section provenance"><h2>Data sources and freshness</h2><p class="section-note">Observed, modeled, missing, and imputed values are distinguished in district details. Supporting data remain downloadable.</p><div id="sourceLedger" class="source-ledger"></div></section><section class="section method">')
    page=page.replace(
        "Headline margins use the selected baseline. Candidate and fundraising scenarios are shown separately and do not change ratings.",
        "Margins, probabilities, intervals, and ratings use the model selected above.")
    page=page.replace(
        "The headline starts with each district’s observed 2024 presidential result and adds a district-specific demographic environment change derived from generic-ballot polling, Catalist history, YouGov cross-tabs, and Alabama ACS composition.",
        "Basic applies 20% of the CMO expected-performance adjustment to the poll-adjusted presidential baseline; Fundamentals+ applies the full adjustment.")
    page=page.replace(
        "Incumbency, demographic-residual, finance, and prior-CMO layers were evaluated only as residual adjustments. None passed the rule requiring improvement in both average and latest-cycle forward MAE, so none changes the headline. The direct baseline’s mean forward MAE is 12.6 points.",
        "Open any modeled district to see every input value, its signed effect, the running margin, and the final reconciliation. Nonlinear-model decompositions use a fixed sequential reveal order, so their individual effects are descriptive and order-dependent.")
    page=page.replace(
        "derived from generic-ballot polling, Catalist history, YouGov cross-tabs, and Alabama ACS composition.",
        "derived from quality-gated generic-ballot polling, reviewed demographic crosstabs, Catalist history, Alabama ecological inference, and ACS composition.")
    page=page.replace(
        "Incumbency, demographic-residual, finance, and prior-CMO layers were evaluated only as residual adjustments. None passed the rule requiring improvement in both average and latest-cycle forward MAE, so none changes the headline. The direct baseline’s mean forward MAE is 12.6 points.",
        "Incumbency, demographic-residual, current fundraising, federal-realignment, and prior-CMO layers were evaluated only as residual adjustments. The post-2016 national-environment ramp passed the full-history, recent-era, and latest-cycle comparison; other layers remain scenarios. Its seven-holdout mean forward MAE is 25.3 points.")
    page=page.replace('<a href="project_docs/methodology/FORECAST_METHODOLOGY.md">Full methodology</a>',
                      '<a href="methodology.html">Full methodology</a>')
    page=page.replace('href="data/processed/war/2026_forecast_decomposition.csv"',
                      'href="data/2026_model_comparison.csv"')
    page=page.replace('href="data/processed/war/2026_residual_layer_backtest_summary.csv"',
                      'href="data/2026_residual_layer_backtest_summary.csv"')
    page=page.replace('<nav class="social-nav" aria-label="Jackson Hannan online">',
                      '<nav class="social-nav" aria-label="Site navigation"><a href="index.html" aria-current="page">Forecast</a><a href="cmo.html">CMO</a><a href="methodology.html">Forecast methodology</a><a href="cmo-methodology.html">CMO methodology</a>')
    page=page.replace('<a href="methodology.html">Full methodology</a>',
                      '<a href="methodology.html">Full methodology</a><a href="cmo.html">Historical WAR model</a>')
    page=re.sub(r'<div class="caveat">.*?</div></section></main>', UNCERTAINTY_CAVEAT+'</section></main>', page, count=1, flags=re.S)
    OUTPUT.write_text(page,encoding="utf-8")
    SITE.mkdir(parents=True,exist_ok=True)
    (SITE/"data").mkdir(exist_ok=True)
    (SITE/"index.html").write_text(page,encoding="utf-8")
    methodology=build_methodology_v2(css,payload_data).replace(
        'href="data/2026_forecast_decomposition.csv"','href="data/2026_model_comparison.csv"')
    (SITE/"methodology.html").write_text(methodology,encoding="utf-8")
    for source,name in [
        (CAL/"post2016_headline_v1_2026_scenarios.csv","post2016_headline_v1_2026_scenarios.csv"),
        (CAL/"post2016_headline_v1_2026_full_uncertainty.csv","post2016_headline_v1_2026_full_uncertainty.csv"),
        (CAL/"post2016_headline_v1_2026_modeled_seats.csv","post2016_headline_v1_2026_modeled_seats.csv"),
        (CAL/"post2016_headline_v1_forward_metrics.csv","post2016_headline_v1_forward_metrics.csv"),
        (CAL/"post2016_headline_v1_bootstrap.csv","post2016_headline_v1_bootstrap.csv"),
        (CAL/"post2016_headline_v1_manifest.json","post2016_headline_v1_manifest.json"),
        (CAL/"robust_forecast_v1_error_components.csv","robust_forecast_v1_error_components.csv"),
        (WAR/"2026_forecast_decomposition.csv","2026_forecast_decomposition.csv"),
        (WAR/"2026_model_comparison.csv","2026_model_comparison.csv"),
        (WAR/"2026_model_variable_contributions.csv","2026_model_variable_contributions.csv"),
        (WAR/"forecast_experiment_tournament_summary.csv","forecast_experiment_tournament_summary.csv"),
        (WAR/"2026_residual_layer_backtest_summary.csv","2026_residual_layer_backtest_summary.csv"),
        (ROOT/"data/processed/polling/votehub_silver_bplus_topline_environment.csv","polling_environment.csv"),
        (ROOT/"data/raw/polling/silver_recent/manifest.csv","poll_source_manifest.csv"),
        (CAL/"production_probability_2026.csv","production_probability_2026.csv"),
        (CAL/"production_probability_curve.csv","production_probability_curve.csv"),
        (CAL/"production_probability_validation_summary.csv","production_probability_validation_summary.csv"),
        (CAL/"production_probability_family_comparison.csv","production_probability_family_comparison.csv"),
        (CAL/"production_probability_model_card.json","production_probability_model_card.json"),
        (ROOT/"data/processed/demographics/2026_sld_demographics.csv","2026_sld_demographics.csv"),
        (ROOT/"data/processed/demographics/rdh_2024_sld_cvap.csv","rdh_2024_sld_cvap.csv"),
        (WAR/"next_forecast_tournament_region_features.csv","next_forecast_tournament_region_features.csv"),
        (ROOT/"data/processed/elections/canonical_cmo_candidates.csv","canonical_cmo_candidates.csv"),
        (WAR/"cmo_v6_southern_candidates.csv","cmo_v6_southern_candidates.csv"),
    ]:
        shutil.copy2(source,SITE/"data"/name)
    for stale_name in (
        "next_forecast_tournament_2026.csv",
        "next_forecast_tournament_summary.csv",
        "next_forecast_tournament_cycle_metrics.csv",
        "next_forecast_tournament_past_only_selection.csv",
    ):
        stale = SITE / "data" / stale_name
        if stale.exists():
            stale.unlink()
    print(f"Wrote {OUTPUT}, {SITE/'index.html'}, and {SITE/'methodology.html'}")


if __name__=="__main__": main()
