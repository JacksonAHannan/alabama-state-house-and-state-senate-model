"""Build final-cycle generic-ballot signals from currently Silver A-rated pollsters."""
from __future__ import annotations

from pathlib import Path
import difflib
import json
import re

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"/"polling"
OUT=ROOT/"data"/"processed"/"polling"
POLL_WINDOW_DAYS=21
POP_WEIGHT={"lv":1.0,"rv":.8,"a":.55,"v":.9}
PRIOR_PRES_MARGIN={1998:9.45,2002:.52,2006:-2.46,2010:7.27,2014:3.85,2018:2.23,2022:4.54}


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower().replace("the", ""))


def match_ratings(pollsters: pd.Series, ratings: pd.DataFrame) -> pd.DataFrame:
    rating_names={norm(x):x for x in ratings.Pollster}
    rows=[]
    for pollster in sorted(pollsters.dropna().unique()):
        key=norm(pollster); candidates=difflib.get_close_matches(key,rating_names,1,.72)
        if not candidates: continue
        matched=rating_names[candidates[0]]
        score=difflib.SequenceMatcher(None,key,candidates[0]).ratio()
        # The branded ABC/Washington Post series is a Washington Post poll.
        if pollster=="ABC News/The Washington Post": matched="The Washington Post"; score=1.0
        if score < .78: continue
        row=ratings[ratings.Pollster.eq(matched)].iloc[0]
        rows.append({"pollster":pollster,"silver_pollster":matched,"match_score":score,
                     "silver_grade":row.grade_clean,"predictive_plus_minus":row["Predictive Plus-Minus"]})
    return pd.DataFrame(rows)


def main() -> None:
    polls=pd.read_csv(RAW/"fivethirtyeight_raw_polls.csv",low_memory=False)
    ratings=pd.read_csv(RAW/"nate_silver_pollster_ratings.csv")
    ratings["grade_clean"]=ratings.Grade.astype(str).str.split("@@").str[0]
    ratings=ratings[ratings.grade_clean.isin(["A+","A","A-"])].copy()
    polls=polls[(polls.type_simple.eq("House-G-US")) & polls.cycle.isin(PRIOR_PRES_MARGIN)].copy()
    polls["polldate"]=pd.to_datetime(polls.polldate); polls["electiondate"]=pd.to_datetime(polls.electiondate)
    polls=polls[polls.partisan.isna()]
    crosswalk=match_ratings(polls.pollster,ratings)
    selected=polls.merge(crosswalk,on="pollster",how="inner",validate="many_to_one")
    selected["days_before_election"]=(selected.electiondate-selected.polldate).dt.days
    selected=selected[selected.days_before_election.between(0,POLL_WINDOW_DAYS)]
    selected["dem_two_party_margin"]=100*(selected.cand1_pct-selected.cand2_pct)/(selected.cand1_pct+selected.cand2_pct)
    # One final observation per pollster and cycle avoids trackers dominating.
    selected=selected.sort_values(["cycle","pollster","polldate","samplesize"]).drop_duplicates(
        ["cycle","pollster"],keep="last")
    selected["weight"]=selected.get("population",pd.Series("rv",index=selected.index)).astype(str).str.lower().map(POP_WEIGHT).fillna(.7)
    rows=[]
    for cycle,g in selected.groupby("cycle"):
        margin=np.average(g.dem_two_party_margin,weights=g.weight)
        actual=float(g.margin_actual.dropna().median())
        rows.append({"cycle":int(cycle),"a_rated_pollsters":g.pollster.nunique(),"final_poll_margin":margin,
                     "earliest_final_poll":g.polldate.min().date(),"latest_final_poll":g.polldate.max().date(),
                     "actual_house_margin":actual,"poll_error":margin-actual,
                     "prior_presidential_margin":PRIOR_PRES_MARGIN[int(cycle)],
                     "poll_implied_national_swing":margin-PRIOR_PRES_MARGIN[int(cycle)],
                     "actual_national_swing":actual-PRIOR_PRES_MARGIN[int(cycle)],
                     "rating_policy":"current_2026_silver_A_plus_A_A_minus_survivorship_screen",
                     "poll_policy":f"latest_nonpartisan_poll_per_pollster_within_{POLL_WINDOW_DAYS}_days"})
    summary=pd.DataFrame(rows).sort_values("cycle")
    OUT.mkdir(parents=True,exist_ok=True)
    selected.to_csv(OUT/"historical_silver_a_generic_ballot_polls.csv",index=False)
    crosswalk.to_csv(OUT/"historical_silver_a_pollster_crosswalk.csv",index=False)
    summary.to_csv(OUT/"historical_silver_a_generic_ballot_cycles.csv",index=False)
    catalog=pd.DataFrame(json.loads((RAW/"votehub_generic_ballot_catalog.json").read_text(encoding="utf-8")))
    current_crosswalk=match_ratings(catalog.pollster,ratings)
    current=catalog.merge(current_crosswalk,on="pollster",how="inner",validate="many_to_one")
    current["end_date"]=pd.to_datetime(current.end_date)
    current["dem_two_party_margin"]=current.answers.map(lambda answers: (
        lambda a: 100*(a.get("dem",np.nan)-a.get("rep",np.nan))/(a.get("dem",0)+a.get("rep",0))
    )({str(x["choice"]).lower():float(x["pct"]) for x in answers}))
    as_of=current.end_date.max(); current=current[current.end_date.ge(as_of-pd.Timedelta(days=60))]
    current=current.sort_values("end_date").drop_duplicates("pollster",keep="last")
    current.to_csv(OUT/"historical_silver_a_current_2026.csv",index=False)
    print(summary.to_string(index=False))
    print(f"\n2026 A-rated snapshot through {as_of.date()}: D{current.dem_two_party_margin.mean():+.2f} across {len(current)} pollsters")


if __name__=="__main__": main()
