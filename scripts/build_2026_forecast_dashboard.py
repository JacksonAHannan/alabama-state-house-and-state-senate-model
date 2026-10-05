# -*- coding: utf-8 -*-
"""Build the self-contained, accessible 2026 forecast dashboard."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import t as student_t

import site_geography
from southern_war_release_gate import ReleaseGateError, sha256

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
MAP_SIMPLIFY_METERS = 90
FORECAST_MANIFEST = CAL / "alabama_war_forecast_v1_manifest.json"
SEATS = ROOT / "data" / "processed" / "elections" / "alabama_seats_by_cycle_v1"
PLAN_EQUIVALENCE = ROOT / "data" / "processed" / "elections" / "alabama_2022_2026_plan_equivalence_v1"


def forecast_graphics(roster: pd.DataFrame) -> dict:
    """The environment-versus-seats joint and the polling replay, in chamber seat totals.

    Both summarize the published run: the joint is a declared forecast output, and the
    replay must name the same forecast build. A stale replay refuses the build.
    """
    manifest = json.loads(FORECAST_MANIFEST.read_text(encoding="utf-8"))
    joint_path = CAL / "alabama_war_forecast_v1_2026_environment_seat_joint.csv"
    if not joint_path.exists():
        raise ReleaseGateError("Missing the environment-seat joint export; rerun the forecast")
    fixed = {}
    for chamber in MAPS:
        part = roster[roster.chamber.eq(chamber)]
        fixed[chamber] = len(set(part[part.party.eq("D")].district) - set(part[part.party.eq("R")].district))
    joint = pd.read_csv(joint_path)
    draws = int(joint.draws.iloc[0])
    if joint.groupby("chamber").draw_count.sum().ne(draws).any():
        raise ReleaseGateError("Environment-seat joint does not account for every draw")
    graphics = {"environmentJoint": {
        "draws": draws,
        "binWidth": float((joint.environment_shift_high - joint.environment_shift_low).iloc[0]),
        "chambers": {chamber: [[float(r.environment_shift_low), int(r.dem_modeled_seats) + fixed[chamber], int(r.draw_count)]
                               for r in part.itertuples()]
                     for chamber, part in joint.groupby("chamber")},
    }}
    replay_path = CAL / "alabama_war_forecast_v1_polling_replay.csv"
    replay_manifest_path = CAL / "alabama_war_forecast_v1_polling_replay_manifest.json"
    if replay_path.exists():
        replay_manifest = json.loads(replay_manifest_path.read_text(encoding="utf-8"))
        if replay_manifest["forecast_build_id"] != manifest["build_id"] or replay_manifest["output"]["sha256"] != sha256(replay_path):
            raise ReleaseGateError("Polling replay does not describe the current forecast run; rerun build_forecast_polling_replay.py")
        replay = pd.read_csv(replay_path)
        graphics["pollingReplay"] = {
            "limitations": replay_manifest["limitations"],
            "rows": [{"asOf": as_of, "genericBallot": round(float(part.generic_ballot_margin.iloc[0]), 4),
                      "chambers": {r.chamber: {"median": int(r.dem_seats_median), "low": int(r.dem_seats_p10),
                                               "high": int(r.dem_seats_p90), "mean": round(float(r.dem_seats_mean), 3),
                                               "control": round(float(r.prob_dem_majority), 5)}
                                   for r in part.itertuples()}}
                     for as_of, part in replay.groupby("as_of", sort=True)],
        }
    return graphics


def plan_equivalence() -> dict[tuple[str, int], dict]:
    """Per-district evidence that the 2026 district is the 2022 district, for the 2022-result map.

    The audit must describe the geometry this page draws; a stale or missing audit refuses
    the build rather than letting a 2022 result stand in for a different plan.
    """
    manifest_path = PLAN_EQUIVALENCE / "manifest.json"
    if not manifest_path.exists():
        raise ReleaseGateError("Missing 2022-2026 plan-equivalence audit; run scripts/audit_2022_2026_plan_equivalence.py")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = {item["path"]: item["sha256"] for item in manifest["inputs"] if "path" in item}
    for path in MAPS.values():
        relative = path.relative_to(ROOT).as_posix()
        if declared.get(relative) != sha256(path):
            raise ReleaseGateError(f"Plan-equivalence audit does not describe the current map geometry: {relative}")
    table = pd.read_csv(PLAN_EQUIVALENCE / "district_equivalence.csv").fillna({"condition": ""})
    if table.duplicated(["chamber", "district"]).any() or len(table) != 140:
        raise ReleaseGateError("Plan-equivalence audit must have one row per 2026 district")
    return {(r.chamber, int(r.district)): {"samePlan": bool(r.equivalent), "planNote": r.condition or None}
            for r in table.itertuples()}


def seat_history() -> dict | None:
    """Seats won at each regular general election, with unknown seats kept explicit."""
    if not (SEATS / "seats_by_cycle.csv").exists():
        return None
    manifest = json.loads((SEATS / "manifest.json").read_text(encoding="utf-8"))
    seats = pd.read_csv(SEATS / "seats_by_cycle.csv")
    checks = pd.read_csv(SEATS / "reconciliation.csv")
    chambers = {}
    for chamber, part in seats.groupby("chamber"):
        rows = []
        for cycle, cell in part.groupby("cycle"):
            counts = dict(zip(cell.party, cell.seats.astype(int)))
            statuses = set(checks[checks.cycle.eq(cycle) & checks.chamber.eq(chamber)].status)
            # Reconciled when any independent reference matches exactly (a snapshot of
            # composition that disagrees is queued in the reconciliation file, not hidden).
            status = ("match" if "match" in statuses
                      else "consistent_with_unknowns" if "consistent_with_unknowns" in statuses
                      else "mismatch" if "mismatch" in statuses else "unreconciled")
            rows.append({"cycle": int(cycle), "D": counts.get("democratic", 0), "R": counts.get("republican", 0),
                         "other": counts.get("other", 0), "unknown": counts.get("unknown", 0),
                         "seats": int(cell.chamber_size.iloc[0]), "reconciliation": status})
        chambers[str(chamber)] = rows
    return {"runId": manifest["run_id"], "chambers": chambers,
            "download": "data/alabama_seats_by_cycle_v1_seats_by_cycle.csv",
            "reconciliation": "data/alabama_seats_by_cycle_v1_reconciliation.csv"}


def normalize_name(value: object) -> str:
    """Conservative display-history key; exact normalized name and party only."""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def display_candidate_name(value: object) -> str | None:
    name = str(value)
    return None if re.fullmatch(r"GS[LU]\d+[A-Z0-9]+", name.upper()) else name


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
    scenarios=pd.read_csv(CAL/"alabama_war_forecast_v1_2026_scenarios.csv")
    uncertainty=pd.read_csv(CAL/"alabama_war_forecast_v1_2026_full_uncertainty.csv")
    modeled_seats=pd.read_csv(CAL/"alabama_war_forecast_v1_2026_modeled_seats.csv")
    metrics=pd.read_csv(CAL/"alabama_war_forecast_v1_forward_metrics.csv")
    manifest=json.loads((CAL/"alabama_war_forecast_v1_manifest.json").read_text(encoding="utf-8"))
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
    war_history=pd.read_csv(WAR/"alabama_war_v1/candidate_cycle_war.csv")
    canonical_candidates=pd.read_csv(ROOT/"data/processed/elections/canonical_cmo_candidates.csv")
    war_history["history_key"]=war_history.normalized_candidate_name.map(normalize_name)+"|"+war_history.canonical_party.astype(str)
    candidate_histories={}
    for history_key, history in war_history.groupby("history_key", sort=False):
        if history.candidate_effect_id.nunique() != 1:
            continue
        candidate_histories[history_key]=[
            {
                "cycle":int(row.cycle), "chamber":{"lower":"house","upper":"senate"}[str(row.chamber)], "district":int(row.district),
                "war":clean(row.candidate_cycle_war), "incumbent":bool(row.incumbent),
            }
            for row in history.sort_values(["cycle","chamber","district"]).itertuples()
            if pd.notna(row.candidate_cycle_war)
        ]
    prior_results={}
    equivalence=plan_equivalence()
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
            "winner":"D" if dem_votes>rep_votes else "R" if rep_votes>dem_votes else None,
            **equivalence[(str(chamber),int(district))],
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
        "headline":("Headline forecast","The generic ballot shifts each district's 2024 presidential margin, the post-2016 WAR model adds its structural expectation, and nominees with a matched prior Alabama race carry part of their own WAR forward."),
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
                     "model":DEFAULT_MODEL,"version":manifest["build_id"],"simulationDraws":50000,
                     # 100 equally likely outcomes for any district: margin plus these offsets.
                     "outcomeOffsets":[round(float(student_t.ppf((i+.5)/100,df)*scale),4) for i in range(100)],
                     "probability":{"family":"student_t","df":df,"scale":scale}},
             "models":[],"contributionVariables":["Generic-ballot district baseline","Generic WAR structure","WAR incumbency effect","Carried-forward candidate WAR","Polling-error scenario"],"provenance":[
                 {"category":"Election baseline","source":"2024 presidential results allocated to 2026 districts","asOf":"2024 general election","download":"data/alabama_war_forecast_v1_2026_scenarios.csv"},
                 {"category":"National environment","source":"Silver Bulletin generic congressional ballot average (two-party margin)","asOf":poll_date.isoformat(),"download":"data/polling_environment.csv"},
                 {"category":"Candidates","source":"Certified 2026 roster; matched prior Alabama races supply the carried-forward candidate WAR","asOf":build_date.isoformat(),"download":"data/alabama_war_forecast_v1_2026_scenarios.csv"},
                 {"category":"Historical test","source":"Post-2016 Southern WAR races before 2022 used to test Alabama's 2022 generic structural forecast","asOf":"2022 election","download":"data/alabama_war_forecast_v1_forward_metrics.csv"},
                 {"category":"District demographics","source":"2022 ACS district estimates and 2020-2024 ACS CVAP special tabulation","asOf":"2024 ACS","download":"data/2026_sld_demographics.csv"},
                 {"category":"Regional geography","source":"Project region-share crosswalk for the 2026 legislative districts","asOf":"2026 district plan","download":"data/next_forecast_tournament_region_features.csv"},
                 {"category":"Prior legislative context","source":"Canonical 2022 Alabama legislative candidate results","asOf":"2022 election","download":"data/canonical_cmo_candidates.csv"},
                 {"category":"2022-to-2026 district match","source":"Block-assignment and boundary audit showing which 2026 districts are the 2022 districts","asOf":"2021 enacted plan","download":"data/alabama_2022_2026_plan_equivalence.csv"},
                 {"category":"Candidate history","source":"Alabama race-residual WAR carried forward for matched nominees at the persistence estimated on Southern repeat candidates","asOf":"2018-2022 elections","download":"data/alabama_war_v1_candidate_cycle_war.csv"},
                 {"category":"Methodology","source":"Generic-ballot environment, WAR structure and candidate-history forecast definitions","asOf":build_date.isoformat(),"download":"data/alabama_war_forecast_v1_manifest.json"}
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
    payload["seatHistory"]=seat_history()
    payload.update(forecast_graphics(roster))
    map_frame=site_geography.alabama_frame()
    payload["context"]=site_geography.alabama_context(map_frame)
    for chamber,map_path in MAPS.items():
        geo=gpd.read_file(map_path); field="SLDLST" if chamber=="house" else "SLDUST"
        geo["district"]=geo[field].astype(int)
        geometry=site_geography.district_geometry(geo,"district",simplify=MAP_SIMPLIFY_METERS,
                                                  frame=map_frame,metros=True)
        races=[]; total=105 if chamber=="house" else 35
        for district in range(1,total+1):
            sub=roster[(roster.chamber==chamber)&(roster.district==district)]
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
                candidates.append({"name":str(candidate.candidate),"party":party,
                    "incumbent":bool(clean(candidate.incumbent) or False),
                    "raised":raised,"spent":spent,
                    "financeStatus":finance_status,
                    "warHistory":candidate_histories.get(normalize_name(candidate.candidate)+"|"+party,[])})
            major={c["party"] for c in candidates if c["party"] in {"D","R"}}
            poll_row=pollidx.get((chamber,district)); model_values={}
            baseline=float(poll_row.uniform_poll_adjusted_dem_margin) if poll_row is not None else None
            pres24=float(poll_row.baseline_2024_pres_dem_margin) if poll_row is not None else None
            environment=baseline-pres24 if baseline is not None and pres24 is not None else None
            if all((chamber,district) in model_forecasts[model] for model in PUBLIC_MODELS):
                status="modeled"; model_values={}
                for model in PUBLIC_MODELS:
                    mr=model_forecasts[model][(chamber,district)]
                    poll_baseline=float(mr.environment_baseline_margin)
                    lag=float(mr.generic_downballot_lag)
                    incumbency_adjustment=float(mr.incumbency_adjustment)
                    candidate_war_adjustment=float(mr.candidate_war_adjustment)
                    polling_error=float(mr.polling_error_adjustment)
                    after_lag=poll_baseline+lag
                    after_incumbency=after_lag+incumbency_adjustment
                    after_candidate_war=after_incumbency+candidate_war_adjustment
                    model_values[model]={"margin":round(float(mr.predicted_dem_margin),6),"demProbability":round(float(mr.dem_win_probability),6),
                        "low80":round(float(mr.margin_80_low),6),"high80":round(float(mr.margin_80_high),6),
                        "steps":[[round(poll_baseline,6),round(poll_baseline,6),round(poll_baseline,6)],
                                 [round(lag,6),round(lag,6),round(after_lag,6)],
                                 [round(incumbency_adjustment,6),round(incumbency_adjustment,6),round(after_incumbency,6)],
                                 [round(candidate_war_adjustment,6),round(candidate_war_adjustment,6),round(after_candidate_war,6)],
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
        payload[chamber]={"geometry":geometry,"races":races,"modelSeatDistributions":distributions,
                          "seatDistribution":distributions[DEFAULT_MODEL]}
    return payload


HTML="""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Jackson Hannan's 2026 Alabama State House and State Senate election forecast"><meta name="author" content="Jackson Hannan"><meta property="og:title" content="Alabama 2026 Legislative Forecast"><meta property="og:description" content="A district-by-district Alabama legislative forecast by Jackson Hannan."><meta property="og:type" content="website"><title>Alabama 2026 Legislative Forecast · Jackson Hannan</title><style>__CSS__</style></head><body>
<header class="mast"><div class="mast-inner"><div class="brand">Jackson Hannan<small>Alabama legislative forecast</small></div><nav class="social-nav" aria-label="Site navigation"><a href="index.html" aria-current="page">Forecast</a><a href="cmo.html">Alabama WAR</a><a href="methodology.html">Forecast methodology</a></nav></div></header>
<main class="forecast-main"><section class="hero"><div class="kicker">The Alabama Legislature</div><h1>2026 Election Forecast</h1><p class="dek">District forecasts based on 2024 presidential results, the current national generic ballot, and each nominee’s own demonstrated WAR where they have run before. Fundraising is not a forecast input.</p><div class="status-row"><span class="status-chip">Forecast built <b id="buildDate"></b></span><span class="status-chip">Polling through <b id="pollDate"></b></span><span class="status-chip" id="pollAge"></span><span class="status-chip">Build <b id="buildId"></b></span></div></section>
<div class="shell"><section class="model-switcher" aria-labelledby="modelSwitcherTitle"><h2 id="modelSwitcherTitle" class="sr-only">Forecast view</h2><div><span class="seg-label">Forecast view</span><div class="model-tabs" id="modelTabs" role="tablist" aria-label="Forecast view"></div></div><p id="modelDescription"></p></section>
<section class="topline" id="topline" aria-label="House and Senate forecast summaries"></section>
<section class="workspace" id="workspace" role="tabpanel"><header class="workspace-head"><div><div class="kicker">District explorer</div><h2 id="chamberTitle"></h2></div><div class="seg" role="group" aria-label="Select chamber"><button data-chamber="house" aria-pressed="true">State House</button><button data-chamber="senate" aria-pressed="false">State Senate</button></div></header>
<div class="explorer"><section class="map-card" aria-labelledby="mapTitle"><h3 id="mapTitle" class="sr-only"></h3><div class="map-toolbar"><div><span class="seg-label" id="viewLabel">View</span><div class="seg" role="group" aria-labelledby="viewLabel"><button data-view="map" aria-pressed="true">Map</button><button data-view="tiles" aria-pressed="false">Tiles</button></div></div><div><span class="seg-label" id="modeLabel">Color by</span><div class="seg" role="group" aria-labelledby="modeLabel"><button data-mode="probability" aria-pressed="true">Win chance</button><button data-mode="margin" aria-pressed="false">Margin</button><button data-mode="result2022" aria-pressed="false">2022 result</button></div></div><div><label class="seg-label" for="highlight">Highlight</label><select id="highlight" class="highlight-select"><option value="all">All districts</option><option value="competitive">Competitive (35–65%)</option><option value="close">Within 10 points</option><option value="open">Open seats</option><option value="trails">Incumbent's party trails</option></select></div><div class="finder"><label class="seg-label" for="districtSearch">Find a district, candidate or city</label><input id="districtSearch" type="search" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="districtOptions" autocomplete="off" placeholder="HD-25, a name, or a city"><ul id="districtOptions" role="listbox" aria-label="Matching districts" hidden></ul></div></div><div class="presets" id="presets" role="group" aria-label="Zoom to an area"></div><div id="map"></div><p class="map-caption" id="mapScope"></p><div id="legend" class="legend" role="group" aria-label="Map legend"></div></section><aside class="detail" id="detail" aria-live="polite"></aside></div></section>
<section class="section" id="closest" aria-labelledby="closestTitle"><div class="kicker">Competitive seats</div><h2 id="closestTitle">Where the competitive seats sit</h2><p class="section-note" id="closestNote"></p><div class="section-panel chart beeswarm" id="beeswarm"></div></section>
<section class="section" id="trend" aria-labelledby="trendTitle" hidden></section>
<section class="section" id="environment" aria-labelledby="environmentTitle" hidden></section>
<section class="section" id="history" aria-labelledby="historyTitle" hidden></section>
<section class="section" aria-labelledby="tableTitle"><div class="kicker">Every district</div><h2 id="tableTitle">District forecast table</h2><p class="section-note"><span id="rowCount"></span>. Margins, probabilities, intervals, and ratings use the forecast view selected above. Margin strips run from R+40 to D+40; larger margins sit at the edge.</p><div class="table-tools"><label class="sr-only" for="search">Search candidates or districts</label><input id="search" type="search" placeholder="Search candidate or district"><label class="sr-only" for="ratingFilter">Filter by rating</label><select id="ratingFilter"><option value="all">All ratings</option><option>Solid D</option><option>Very likely D</option><option>Likely D</option><option>Lean D</option><option>Toss-up</option><option>Lean R</option><option>Likely R</option><option>Very likely R</option><option>Solid R</option><option>Unopposed D</option><option>Unopposed R</option></select><label class="sr-only" for="scopeFilter">Filter races</label><select id="scopeFilter"><option value="all">All districts</option><option value="competitive">Competitive (35–65%)</option><option value="modeled">Modeled D–R races</option><option value="open">Open seats</option><option value="crosses">80% interval crosses even</option><option value="trails">Incumbent's party trails</option><option value="winner-disagreement">Models disagree on winner</option><option value="rating-disagreement">Models disagree on rating</option></select><button class="small-button" id="download">Download CSV</button></div><p class="table-hint">Swipe sideways for every column.</p><div class="table-wrap"><table><thead><tr><th><button data-sort="district">District<span></span></button></th><th>Candidates</th><th><button data-sort="rating">Rating<span></span></button></th><th><button data-sort="demProbability">Dem. chance<span></span></button></th><th><button data-sort="margin">Margin and 80% interval<span></span></button></th><th class="delta-col">Vs. headline</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section class="section provenance" aria-labelledby="sourcesTitle"><h2 id="sourcesTitle">Data sources and freshness</h2><p class="section-note">Observed, modeled, missing, and imputed values are distinguished in district details. Supporting data remain downloadable.</p><div id="sourceLedger" class="source-ledger"></div></section>
<section class="section method"><div><h2>How to read this forecast</h2><p>The headline begins with each district’s 2024 presidential margin and applies the national swing implied by current generic-ballot polling.</p><p>Nominees with a matched prior Alabama race carry a share of their own WAR forward; everyone else is evaluated generically. Ideology and fundraising are excluded. The headline includes the owner-selected structural adjustment, including its symmetric incumbency effect. On the sole direct Alabama forward holdout it still trails the generic-ballot-only benchmark, while carrying candidate history improves on the structural model alone; that comparison is published as an advisory limitation, not as evidence that the structural term is zero.</p><p class="mae-note">__MAE_NOTE__ The scenario tabs change only the assumed national polling error.</p><div class="method-links"><a href="methodology.html">Full methodology</a><a href="cmo.html">Historical WAR model</a><a href="data/alabama_war_forecast_v1_2026_scenarios.csv">District scenarios</a><a href="data/alabama_war_forecast_v1_forward_metrics.csv">Historical test</a></div></div>__CAVEAT__</section></div></main><footer class="site-footer"><div><b>Model and analysis by Jackson Hannan</b><span>Alabama 2026 Legislative Forecast</span></div><nav aria-label="Jackson Hannan profiles"><a href="https://github.com/JacksonAHannan" target="_blank" rel="me noopener">GitHub</a><a href="https://www.instagram.com/topsoilintraining/" target="_blank" rel="me noopener">Instagram</a><a href="https://substack.com/@jacksonhannan" target="_blank" rel="me noopener">Substack</a><a href="https://www.linkedin.com/in/jackson-hannan" target="_blank" rel="me noopener">LinkedIn</a></nav></footer><script>__MAPJS__</script><script>const DATA=__PAYLOAD__;__JS__</script></body></html>"""


UNCERTAINTY_CAVEAT = """<div class="caveat"><b>Forecast uncertainty.</b><p>The headline uses 50,000 simulations. Shared national, statewide, and chamber error prevents the chamber distribution from treating every district as independent.</p><p>District probabilities use a Student-t(5) curve calibrated on the 2022 holdout. Scenario tabs show a typical national polling error in either direction.</p><p>Carried-forward candidate WAR applies only where a prior Alabama race is matched. Districts with one major-party nominee are fixed; genuinely unresolved districts remain unmodeled and gray.</p></div>"""











def pipeline_figure() -> str:
    """The forecast's stages, left to right; HTML so the boxes wrap on narrow screens."""
    steps = [("2024 presidential", "district margin"), ("+ national swing", "generic ballot"),
             ("+ WAR structure", "incl. incumbency"), ("+ candidate WAR", "matched nominees"),
             ("District margin", "Student-t probability"), ("50,000 simulations", "seat distribution")]
    items = "".join(
        f'<li style="flex:1 1 128px;min-width:118px;padding:8px 10px;border:1px solid #9db4c1;'
        f'background:{"#211b1b" if i >= 4 else "#f8fbfc"};color:{"#fff" if i >= 4 else "#211b1b"}!important">'
        f'<b style="display:block;font:700 13px/1.3 Arial,Helvetica,sans-serif;color:{"#fff" if i >= 4 else "#211b1b"}!important">{a}</b>'
        f'<span style="font:12px/1.3 Arial,Helvetica,sans-serif;color:{"#dfe5e9" if i >= 4 else "#586772"}!important">{b}</span></li>'
        + ('' if i == len(steps) - 1 else '<li aria-hidden="true" style="align-self:center;font:700 16px Arial;color:#211b1b">→</li>')
        for i, (a, b) in enumerate(steps))
    return ('<figure class="method-figure" style="margin:18px 0"><ol aria-label="Forecast stages" '
            'style="display:flex;flex-wrap:wrap;gap:6px;margin:0;padding:0;list-style:none">' + items + '</ol></figure>')


def holdout_figure(selected_mae: float) -> str:
    """Predicted against actual Democratic margin for the 2022 Alabama forward holdout."""
    pred = pd.read_csv(CAL / "alabama_war_forecast_v1_forward_predictions.csv")
    mae = float((pred.legislative_dem_margin - pred.predicted_dem_margin).abs().mean())
    if abs(mae - selected_mae) > 1e-6:
        raise ReleaseGateError(f"Holdout figure MAE {mae:.4f} disagrees with the manifest {selected_mae:.4f}")
    lim = float(np.ceil(max(60.0, pred[["legislative_dem_margin", "predicted_dem_margin"]].abs().max().max()) / 10) * 10)
    size, pad = 420, 46
    scale = (size - 2 * pad) / (2 * lim)
    sx = lambda v: pad + (v + lim) * scale
    sy = lambda v: size - pad - (v + lim) * scale
    ticks = "".join(
        f'<line x1="{sx(v):.1f}" x2="{sx(v):.1f}" y1="{pad}" y2="{size - pad}" stroke="{"#586772" if v == 0 else "#dbe4ea"}"/>'
        f'<line x1="{pad}" x2="{size - pad}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="{"#586772" if v == 0 else "#dbe4ea"}"/>'
        f'<text x="{sx(v):.1f}" y="{size - pad + 16}" text-anchor="middle" font-size="12" fill="#586772">{"Even" if v == 0 else ("D+" if v > 0 else "R+") + str(int(abs(v)))}</text>'
        f'<text x="{pad - 6}" y="{sy(v) + 3:.1f}" text-anchor="end" font-size="12" fill="#586772">{"Even" if v == 0 else ("D+" if v > 0 else "R+") + str(int(abs(v)))}</text>'
        for v in np.arange(-lim, lim + 1, 20))
    band = (f'<path d="M{sx(-lim):.1f},{sy(-lim + mae):.1f}L{sx(lim - mae):.1f},{sy(lim):.1f}L{sx(lim):.1f},{sy(lim):.1f}'
            f'L{sx(lim):.1f},{sy(lim - mae):.1f}L{sx(-lim + mae):.1f},{sy(-lim):.1f}L{sx(-lim):.1f},{sy(-lim):.1f}Z" fill="#eef5f8"/>')
    dots = []
    for row in pred.itertuples():
        hit = np.sign(row.legislative_dem_margin) == np.sign(row.predicted_dem_margin)
        style = 'fill="#211b1b"' if hit else 'fill="#fff" stroke="#743b42" stroke-width="2"'
        dots.append(f'<circle cx="{sx(row.predicted_dem_margin):.1f}" cy="{sy(row.legislative_dem_margin):.1f}" r="4" {style}>'
                    f'<title>{row.chamber} {row.district}: predicted {row.predicted_dem_margin:+.1f}, actual {row.legislative_dem_margin:+.1f}</title></circle>')
    misses = int((np.sign(pred.legislative_dem_margin) != np.sign(pred.predicted_dem_margin)).sum())
    return (f'<figure class="method-figure" style="margin:18px 0;max-width:460px;overflow-x:auto"><svg viewBox="0 0 {size} {size}" role="img" '
            f'aria-label="2022 holdout: {len(pred)} races, mean absolute error {mae:.2f} points, {misses} wrong winners" '
            'style="display:block;width:100%;min-width:420px;height:auto;font-family:Arial,Helvetica,sans-serif">'
            f'{band}{ticks}<line x1="{sx(-lim):.1f}" y1="{sy(-lim):.1f}" x2="{sx(lim):.1f}" y2="{sy(lim):.1f}" stroke="#211b1b" stroke-dasharray="4 3"/>'
            + "".join(dots) +
            f'<text x="{size / 2}" y="{size - 8}" text-anchor="middle" font-size="13" fill="#211b1b">Predicted Democratic margin</text>'
            f'<text transform="translate(12,{size / 2}) rotate(-90)" text-anchor="middle" font-size="13" fill="#211b1b">Actual Democratic margin</text></svg>'
            f'<figcaption style="font-size:13px;color:#394b58">Each dot is one of the {len(pred)} Alabama 2022 holdout races under the published '
            f'specification. The dashed line is a perfect forecast and the shaded band is within the {mae:.2f}-point mean absolute error. '
            f'Hollow dots ({misses}) called the wrong winner.</figcaption></figure>')


def build_methodology_v3(css: str, payload: dict) -> str:
    """Document the generic-ballot, environment-adjusted WAR forecast."""
    metrics = pd.read_csv(CAL / "alabama_war_forecast_v1_forward_metrics.csv").set_index("specification")
    manifest = json.loads((CAL / "alabama_war_forecast_v1_manifest.json").read_text(encoding="utf-8"))
    components = pd.read_csv(CAL / "robust_forecast_v1_error_components.csv").iloc[0]
    baseline = metrics.loc["generic_ballot_baseline"]
    structural = metrics.loc["generic_war_structural"]
    candidate = metrics.loc["war_structural_plus_candidate_history"]
    history = json.loads(
        (CAL / "alabama_forecast_candidate_history_manifest.json").read_text(encoding="utf-8")
    )
    persistence = float(history["fit"]["persistence"])
    history_pairs = int(history["fit"]["pairs"])
    carry_limit = int(history["coverage"]["carry_limit_years"])
    history_races = int(manifest["diagnostics"]["headline_races_with_candidate_history"])
    history_mean = float(manifest["diagnostics"]["headline_mean_abs_candidate_adjustment"])
    history_holdout_races = int(candidate.races_with_candidate_history)
    holdout_assessment = (
        "improved on" if candidate.mae < baseline.mae else "still trails"
    )
    scale = float(manifest["probability"]["scale"])
    coverage80 = float(manifest["probability"]["holdout_coverage_80"])
    styles = css + (ASSETS / "methodology.css").read_text(encoding="utf-8")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forecast methodology · Alabama 2026</title><style>{styles}</style></head><body>
<header class="mast"><div class="mast-inner"><div class="brand">Jackson Hannan<small>Alabama legislative forecast</small></div><nav class="social-nav" aria-label="Site navigation"><a href="index.html">Forecast</a><a href="cmo.html">Alabama WAR</a><a href="methodology.html" aria-current="page">Forecast methodology</a><a href="cmo-methodology.html">WAR methodology</a></nav></div></header>
<main class="methodology-shell"><header class="methodology-hero"><div class="kicker">Model documentation</div><h1>Forecast methodology</h1><p class="dek">A WAR forecast anchored to the national generic ballot, carrying each nominee&rsquo;s own demonstrated WAR forward where a prior Alabama race is matched.</p><div class="status-row"><span class="status-chip">Headline <b>generic ballot + WAR structure + candidate history</b></span><span class="status-chip">Polling through <b>{payload['meta']['pollAsOf']}</b></span><span class="status-chip">Build <b>{manifest['build_id']}</b></span></div></header>
<div class="method-grid"><aside class="toc"><b>On this page</b><a href="#identity">Forecast identity</a><a href="#environment">Environment</a><a href="#generic">Candidate history</a><a href="#validation">Forward test</a><a href="#uncertainty">Uncertainty</a><a href="#limits">Limitations</a><a href="#downloads">Downloads</a></aside><article class="method-copy">
<section id="identity"><h2>1. Forecast identity</h2><div class="formula">2026 Democratic margin = 2024 district presidential margin + national generic-ballot swing + WAR structure + WAR incumbency effect + carried-forward candidate WAR</div>{pipeline_figure()}<p>The selected post-2016 Southern WAR model supplies the structural expected gap, including its symmetric incumbency effect. A nominee with a matched prior Alabama race adds {persistence:.2f} of that race&rsquo;s residual WAR, oriented to the Democratic margin; a rematch is counted once rather than twice.</p></section>
<section id="environment"><h2>2. National environment</h2><p>The Silver Bulletin generic congressional ballot average (weighted by pollster rating, sample size and recency, with house-effect adjustment), converted to a two-party margin, is used as a stand-in for the election environment because Alabama-specific polling is sparse. Its change from the 2024 national presidential margin is applied uniformly to every district's 2024 presidential margin. The uniform national-to-Alabama transfer is an owner-selected model assumption; the validation audit does not establish its Alabama-specific validity beyond the single 2022 forward holdout. The Dem and Rep scenario tabs add or subtract one historical national polling-error standard deviation.</p></section>
<section id="generic"><h2>3. Candidate history</h2><p>A nominee with a matched prior Alabama race carries {persistence:.2f} of that race’s WAR into this forecast; the rest are evaluated generically. Persistence is estimated on {history_pairs:,} repeat-candidate pairs in the Southern v3 panel with candidate-clustered standard errors, and the years-elapsed interaction is not statistically supported, so no decay is applied. Matching is verified-crosswalk first, then exact unique name; ambiguous names and results older than {carry_limit} years are left unmatched and enter as zero. {history_races} of the modeled races carry a candidate adjustment, averaging {history_mean:.1f} margin points. Ideology and fundraising remain excluded: the payload records <code>finance_used=false</code> for every modeled race.</p></section>
<section id="validation"><h2>4. Post-2016-to-2022 forward test</h2><p>The direct Alabama forward test fits the selected WAR design on {int(structural.train_races)} eligible Southern races after 2016 and before 2022, then evaluates 33 Alabama races in 2022, including the WAR model's incumbency term. The generic-ballot district baseline records {baseline.mae:.2f} points of MAE and {baseline.winner_accuracy:.1%} winner accuracy. The WAR structural specification alone records {structural.mae:.2f} points, and adding carried-forward candidate WAR records {candidate.mae:.2f} points across the {history_holdout_races} holdout races that had a matched prior result. The published model is the WAR specification with candidate history: it is the owner-selected estimand, it improves on the structural model, and it still trails the generic-ballot benchmark on this single holdout. That comparison is published rather than hidden.</p><table class="method-table"><thead><tr><th>Specification</th><th>2022 MAE</th><th>RMSE</th><th>Winner accuracy</th><th>Status</th></tr></thead><tbody><tr><td>Generic-ballot baseline</td><td>{baseline.mae:.2f}</td><td>{baseline.rmse:.2f}</td><td>{baseline.winner_accuracy:.1%}</td><td>Diagnostic benchmark</td></tr><tr><td>WAR structural expected gap</td><td>{structural.mae:.2f}</td><td>{structural.rmse:.2f}</td><td>{structural.winner_accuracy:.1%}</td><td>Comparison</td></tr><tr><td>WAR structural plus candidate history</td><td>{candidate.mae:.2f}</td><td>{candidate.rmse:.2f}</td><td>{candidate.winner_accuracy:.1%}</td><td>Published specification</td></tr></tbody></table>{holdout_figure(float(manifest["diagnostics"]["selected_forward_mae"]))}</section>
<section id="uncertainty"><h2>5. Probabilities and chamber summaries</h2><p>Expected margins are converted to conditional probabilities with a Student-t distribution with five degrees of freedom and a {scale:.2f}-point scale, the maximum-likelihood scale of the 2022 holdout margin residuals (its nominal 80% interval covers {coverage80:.0%} of them). The scale is tuned and evaluated on the same 33 races, so the probability layer has no independent evaluation. Headline chamber summaries use 50,000 correlated simulations with national ({components.national_sd:.2f}), statewide ({components.state_sd:.2f}), chamber ({components.chamber_sd:.2f}), and district ({components.district_sd:.2f}) error components read from <code>robust_forecast_v1_error_components.csv</code>, the live uncertainty input for this build. Single-major-party seats are fixed in chamber totals.</p></section>
<section id="limits"><h2>6. Limitations</h2><ul><li>Only one direct post-2016 Alabama forward holdout is available; the selected structural specification {holdout_assessment} the generic-ballot-only benchmark on it.</li><li>The national generic ballot is an imperfect proxy for Alabama's state-legislative environment.</li><li>The probability scale is sample-limited and should not be read as long-run calibration evidence.</li><li>Candidate history is only available for {history_races} of the modeled races; everyone else is evaluated generically, so the adjustment is uneven across districts.</li><li>Persistence is measured over two-to-six-year gaps and applied up to {carry_limit} years, so 2018 results reach 2026 as a one-cycle extrapolation; older results are not carried at all.</li><li>Roster and polling evidence can change before Election Day.</li></ul></section>
<section id="downloads"><h2>7. Data and audit downloads</h2><p class="download-list"><a href="data/alabama_war_forecast_v1_2026_scenarios.csv">District scenarios</a><a href="data/alabama_war_forecast_v1_forward_predictions.csv">Forward predictions</a><a href="data/alabama_war_forecast_v1_forward_metrics.csv">Forward metrics</a><a href="data/alabama_war_forecast_v1_manifest.json">Manifest</a><a href="data/robust_forecast_v1_error_components.csv">Uncertainty components</a><a href="data/alabama_war_v1_candidate_cycle_war.csv">Alabama WAR ratings</a></p></section>
</article></div></main></body></html>'''


def require_fresh_inputs() -> dict:
    """Refuse to render when a declared forecast input or output no longer matches disk."""
    manifest = json.loads(FORECAST_MANIFEST.read_text(encoding="utf-8"))
    try:
        declarations = [
            (entry["path"], entry["sha256"])
            for section in ("inputs", "outputs")
            for entry in manifest.get(section, [])
        ]
    except (AttributeError, KeyError, TypeError) as error:
        raise ReleaseGateError("Malformed forecast file declarations") from error
    root = ROOT.resolve()
    for relative, expected in declarations:
        if (not isinstance(relative, str) or not relative
                or not isinstance(expected, str) or len(expected) != 64
                or any(char not in "0123456789abcdef" for char in expected)):
            raise ReleaseGateError(f"Malformed forecast file declaration: {relative!r}")
        path = (root / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(root):
            raise ReleaseGateError(f"Forecast file outside repository: {relative}")
        try:
            actual = sha256(path)
        except OSError as error:
            raise ReleaseGateError(
                f"Declared forecast input unavailable: {relative}"
            ) from error
        if actual != expected:
            raise ReleaseGateError(f"Declared forecast input changed: {relative}")
    return manifest


def main(*, publish: bool = True):
    forecast_manifest = require_fresh_inputs()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    css=((ASSETS/"site_components.css").read_text(encoding="utf-8")
         +(ASSETS/"forecast_dashboard.css").read_text(encoding="utf-8"))
    js=(ASSETS/"forecast_dashboard.js").read_text(encoding="utf-8")
    map_js=(ASSETS/"site_map.js").read_text(encoding="utf-8")
    payload_data=build_payload()
    payload=json.dumps(payload_data,separators=(",",":"),ensure_ascii=False)
    forward_metrics=pd.read_csv(CAL/"alabama_war_forecast_v1_forward_metrics.csv").set_index("specification")
    train_races=int(forward_metrics.loc[forecast_manifest["selected_specification"],"train_races"])
    mae_note=("The 2022 holdout MAE is the average Alabama district-margin error after training on "
              f"eligible post-2016 Southern races before 2022 ({train_races:,} training races).")
    page=(HTML.replace("__CSS__",css).replace("__MAPJS__",map_js).replace("__CAVEAT__",UNCERTAINTY_CAVEAT)
          .replace("__MAE_NOTE__",mae_note).replace("__PAYLOAD__",payload).replace("__JS__",js))
    OUTPUT.write_text(page,encoding="utf-8")
    methodology=build_methodology_v3(css,payload_data)
    methodology_artifact=OUTPUT.parent/"forecast-methodology.html"
    methodology_artifact.write_text(methodology,encoding="utf-8")
    if not publish:
        # New downloads the candidate links to, so a local preview resolves them.
        preview_data=OUTPUT.parent/"data"; preview_data.mkdir(exist_ok=True)
        for name in ("seats_by_cycle","district_winners","reconciliation","manifest"):
            source=SEATS/(f"{name}.json" if name=="manifest" else f"{name}.csv")
            if source.exists(): shutil.copy2(source,preview_data/f"alabama_seats_by_cycle_v1_{source.name}")
        shutil.copy2(PLAN_EQUIVALENCE/"district_equivalence.csv",preview_data/"alabama_2022_2026_plan_equivalence.csv")
        print(f"Wrote {OUTPUT} and {methodology_artifact} (artifact only)")
        return
    SITE.mkdir(parents=True,exist_ok=True)
    (SITE/"data").mkdir(exist_ok=True)
    (SITE/"index.html").write_text(page,encoding="utf-8")
    (SITE/"methodology.html").write_text(methodology,encoding="utf-8")
    for source,name in [
        (CAL/"alabama_war_forecast_v1_2026_scenarios.csv","alabama_war_forecast_v1_2026_scenarios.csv"),
        (CAL/"alabama_war_forecast_v1_2026_full_uncertainty.csv","alabama_war_forecast_v1_2026_full_uncertainty.csv"),
        (CAL/"alabama_war_forecast_v1_2026_modeled_seats.csv","alabama_war_forecast_v1_2026_modeled_seats.csv"),
        (CAL/"alabama_war_forecast_v1_forward_predictions.csv","alabama_war_forecast_v1_forward_predictions.csv"),
        (CAL/"alabama_war_forecast_v1_forward_metrics.csv","alabama_war_forecast_v1_forward_metrics.csv"),
        (CAL/"alabama_war_forecast_v1_probability_families.csv","alabama_war_forecast_v1_probability_families.csv"),
        (CAL/"alabama_war_forecast_v1_manifest.json","alabama_war_forecast_v1_manifest.json"),
        (CAL/"robust_forecast_v1_error_components.csv","robust_forecast_v1_error_components.csv"),
        (ROOT/"data/processed/polling/silver_bulletin_generic_ballot_environment.csv","polling_environment.csv"),
        (ROOT/"data/raw/polling/silver_recent/manifest.csv","poll_source_manifest.csv"),
        (ROOT/"data/processed/demographics/2026_sld_demographics.csv","2026_sld_demographics.csv"),
        (WAR/"next_forecast_tournament_region_features.csv","next_forecast_tournament_region_features.csv"),
        (ROOT/"data/processed/elections/canonical_cmo_candidates.csv","canonical_cmo_candidates.csv"),
        (WAR/"alabama_war_v1/candidate_cycle_war.csv","alabama_war_v1_candidate_cycle_war.csv"),
        (WAR/"alabama_war_v1/race_war.csv","alabama_war_v1_race_war.csv"),
        (WAR/"alabama_war_v1/manifest.json","alabama_war_v1_manifest.json"),
        (SEATS/"seats_by_cycle.csv","alabama_seats_by_cycle_v1_seats_by_cycle.csv"),
        (SEATS/"district_winners.csv","alabama_seats_by_cycle_v1_district_winners.csv"),
        (SEATS/"reconciliation.csv","alabama_seats_by_cycle_v1_reconciliation.csv"),
        (SEATS/"manifest.json","alabama_seats_by_cycle_v1_manifest.json"),
        (PLAN_EQUIVALENCE/"district_equivalence.csv","alabama_2022_2026_plan_equivalence.csv"),
    ]:
        shutil.copy2(source,SITE/"data"/name)
    for stale_name in (
        "next_forecast_tournament_2026.csv",
        "next_forecast_tournament_summary.csv",
        "next_forecast_tournament_cycle_metrics.csv",
        "next_forecast_tournament_past_only_selection.csv",
        # Superseded legacy bundles that no active page links. The live
        # uncertainty input robust_forecast_v1_error_components.csv is kept.
        "2026_model_variable_contributions.csv",
        "2026_forecast_decomposition.csv",
        "2026_model_comparison.csv",
        "forecast_experiment_tournament_summary.csv",
        "2026_residual_layer_backtest_summary.csv",
        "production_probability_2026.csv",
        "production_probability_curve.csv",
        "production_probability_validation_summary.csv",
        "production_probability_family_comparison.csv",
        "production_probability_model_card.json",
        "post2016_headline_v1_manifest.json",
        "post2016_headline_v1_bootstrap.csv",
        "post2016_headline_v1_forward_metrics.csv",
        "post2016_headline_v1_2026_scenarios.csv",
        "post2016_headline_v1_2026_full_uncertainty.csv",
        "post2016_headline_v1_2026_modeled_seats.csv",
        "robust_forecast_v1_manifest.json",
        "robust_forecast_v1_metrics.csv",
        "robust_forecast_v1_ranking.csv",
        "robust_forecast_v1_2026_scenarios.csv",
        "robust_forecast_v1_2026_full_uncertainty.csv",
        "robust_forecast_v1_2026_modeled_seats.csv",
        "robust_forecast_v1_probability_families.csv",
        "robust_forecast_v1_subgroup_audit.csv",
    ):
        stale = SITE / "data" / stale_name
        if stale.exists():
            stale.unlink()
    print(f"Wrote {OUTPUT}, {SITE/'index.html'}, and {SITE/'methodology.html'}")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-only",
        action="store_true",
        help="Build local release-candidate HTML without writing publication files under docs/.",
    )
    args=parser.parse_args()
    main(publish=not args.artifact_only)
