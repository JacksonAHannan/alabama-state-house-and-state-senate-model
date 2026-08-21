"""Pilot Alabama FCPA surname searches for candidates missing state finance matches."""
from __future__ import annotations

import argparse
import base64
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from rapidfuzz.fuzz import WRatio

from oe_normalize import normalize_name

ROOT=Path(__file__).resolve().parents[1]
SEARCH="https://fcpa.alabamavotes.gov/page.request.do"
REFERER=("https://fcpa.alabamavotes.gov/page.request.do?"
         "page=page.acfPublicPrincipalCampaignCommitteeSearch")
FINANCIAL_SUMMARY_MARKER="let financialSummaryData = "


def surname(name: object) -> str:
    tokens=normalize_name(name).split()
    while tokens and tokens[-1] in {"JR","SR","II","III","IV"}:tokens.pop()
    return tokens[-1] if tokens else ""


def search(last_name: str) -> tuple[list[dict],str]:
    criteria=[
      {"field_key":"candidateLastName","comparison_type":"like","comparison_value_1":last_name},
      {"field_key":"committeeType","comparison_type":"equalTo","comparison_value_1":"1"},
    ]
    params={"page":"com.acf.common.page.committeesearchresults","pageNumber":1,"pageSize":100,
            "sortDirection":"ASC","sortBy":"candidateLastName",
            "criteria":json.dumps(criteria,separators=(",",":"))}
    url=SEARCH+"?"+urllib.parse.urlencode(params)
    request=urllib.request.Request(url,headers={"User-Agent":"JacksonHannan-AlabamaElectionResearch/1.0",
                                                "Accept":"application/json","Referer":REFERER})
    with urllib.request.urlopen(request,timeout=60) as response:
        payload=json.load(response)
    if not payload.get("success"):raise RuntimeError(f"FCPA search failed for {last_name}")
    return payload["data"]["list"],url


def all_financial_summaries(record_id: object) -> tuple[dict, str]:
    """Return every official calendar-year summary displayed for a committee."""
    encoded=base64.b64encode(str(int(float(record_id))).encode()).decode()
    detail_url=(SEARCH+"?"+urllib.parse.urlencode({"page":"page.acfPublicCommitteeDetails",
                                                   "type":base64.b64encode(b"pcc").decode(),
                                                   "id":encoded}))
    request=urllib.request.Request(detail_url,headers={"User-Agent":"JacksonHannan-AlabamaElectionResearch/1.0",
                                                       "Referer":REFERER})
    with urllib.request.urlopen(request,timeout=60) as response:
        detail=response.read().decode("utf-8",errors="replace")
    committee_id=re.search(r'"committeeId"\s*:\s*"([^"]+)"',detail)
    if not committee_id:
        return {},detail_url
    summary_url=SEARCH+"?"+urllib.parse.urlencode({"page":"page.acfPublicCommitteeFinancialSummary",
                                                   "committeeIdStr":str(int(float(record_id)))})
    request=urllib.request.Request(summary_url,headers={"User-Agent":"JacksonHannan-AlabamaElectionResearch/1.0",
                                                         "Referer":detail_url})
    with urllib.request.urlopen(request,timeout=60) as response:
        html=response.read().decode("utf-8",errors="replace")
    match=re.search(re.escape(FINANCIAL_SUMMARY_MARKER)+r"(\{.*?\});",html,re.DOTALL)
    if not match:
        return {},summary_url
    return json.loads(match.group(1)),summary_url


def annual_financial_summary(record_id: object, cycle: int) -> tuple[dict, str]:
    """Return one calendar year from the official committee summary."""
    payload,url=all_financial_summaries(record_id)
    return payload.get(str(int(cycle)),{}),url


def expected_office(chamber: str) -> str:
    return "STATE REPRESENTATIVE" if chamber=="house" else "STATE SENATOR"


def select_candidates(limit_per_cycle: int) -> pd.DataFrame:
    source=pd.read_csv(ROOT/"data/processed/war/candidate_finance_matches.csv")
    missing=source[source.finance_name.isna()].copy()
    missing["surname"]=missing.candidate.map(surname)
    return (missing[missing.surname.ne("")].sort_values(["cycle","chamber","district","party"])
            .groupby("cycle",group_keys=False).head(limit_per_cycle).reset_index(drop=True))


def run(limit_per_cycle: int=10,delay: float=.2) -> pd.DataFrame:
    candidates=select_candidates(limit_per_cycle); retrieved=datetime.now(timezone.utc).isoformat()
    cache={}; rows=[]
    for candidate in candidates.itertuples(index=False):
        if candidate.surname not in cache:
            cache[candidate.surname]=search(candidate.surname)
            time.sleep(delay)
        results,url=cache[candidate.surname]
        if not results:
            rows.append({"cycle":candidate.cycle,"chamber":candidate.chamber,"district":candidate.district,
                         "party":candidate.party,"candidate":candidate.candidate,"surname":candidate.surname,
                         "search_results":0,"committee_match_status":"no_surname_result","search_url":url,
                         "retrieved_at_utc":retrieved})
            continue
        for item in results:
            found=" ".join(filter(None,[item.get("candidateFirstName"),item.get("candidateMiddleName"),item.get("candidateLastName")]))
            score=float(WRatio(normalize_name(candidate.candidate),normalize_name(found)))
            office_ok=expected_office(candidate.chamber) in str(item.get("office","")).upper()
            jurisdiction_number=re.search(r"(\d+)",str(item.get("jurisdiction","")))
            district_ok=bool(jurisdiction_number and int(jurisdiction_number.group(1))==int(candidate.district))
            status=("strong_name_office_district" if score>=88 and office_ok and district_ok else
                    "name_office_candidate" if score>=88 and office_ok else
                    "surname_result_not_candidate")
            rows.append({"cycle":candidate.cycle,"chamber":candidate.chamber,"district":candidate.district,
                "party":candidate.party,"candidate":candidate.candidate,"surname":candidate.surname,
                "search_results":len(results),"committee_match_status":status,"name_score":score,
                "office_compatible":office_ok,"district_compatible":district_ok,
                "fcpa_record_id":item.get("id"),"committee_id":item.get("committeeId"),
                "fcpa_candidate_name":found,"fcpa_party":item.get("party"),"fcpa_office":item.get("office"),
                "fcpa_jurisdiction":item.get("jurisdiction"),"fcpa_place":item.get("place"),
                "committee_status":item.get("committeeStatus"),"registered_date":item.get("registeredDate"),
                "search_url":url,"retrieved_at_utc":retrieved})
    result=pd.DataFrame(rows)
    output=ROOT/"data/processed/war/fcpa_surname_search_pilot.csv"
    result.to_csv(output,index=False)
    return result


def retrieve_pilot_summaries(delay: float=.2) -> pd.DataFrame:
    """Fetch election-year summaries for the pilot's strong committee matches."""
    matches=pd.read_csv(ROOT/"data/processed/war/fcpa_surname_search_pilot.csv")
    strong=matches[matches.committee_match_status.eq("strong_name_office_district")].copy()
    finance=pd.read_csv(ROOT/"data/processed/war/candidate_finance_matches.csv")
    rows=[]
    for item in strong.itertuples(index=False):
        annual,url=annual_financial_summary(item.fcpa_record_id,int(item.cycle))
        current=finance[(finance.cycle.eq(item.cycle)) & (finance.chamber.eq(item.chamber)) &
                        (finance.district.eq(item.district)) & (finance.party.eq(item.party)) &
                        (finance.candidate.eq(item.candidate))]
        rows.append({
            "cycle":item.cycle,"chamber":item.chamber,"district":item.district,"party":item.party,
            "candidate":item.candidate,"committee_id":item.committee_id,
            "registered_date":item.registered_date,"annual_summary_available":bool(annual),
            "cash_contributions":annual.get("cashContributions"),
            "other_receipts":annual.get("otherReceipts"),
            "in_kind_contributions":annual.get("inKindContributions"),
            "expenditures":annual.get("expenditures"),
            "beginning_balance":annual.get("beginningBalance"),"ending_balance":annual.get("endingBalance"),
            "current_candidate_expenditures":None if current.empty else current.iloc[0].candidate_expenditures,
            "financial_summary_url":url,
        })
        time.sleep(delay)
    result=pd.DataFrame(rows)
    result.to_csv(ROOT/"data/processed/war/fcpa_surname_financial_summary_pilot.csv",index=False)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--limit-per-cycle",type=int,default=10)
    parser.add_argument("--delay",type=float,default=.2)
    parser.add_argument("--fetch-summaries",action="store_true"); args=parser.parse_args()
    frame=run(args.limit_per_cycle,args.delay)
    candidates=frame[["cycle","chamber","district","party","candidate"]].drop_duplicates()
    strong=frame[frame.committee_match_status.eq("strong_name_office_district")]
    print(f"Searched {len(candidates)} unmatched candidates; found strong district-specific committees for "
          f"{strong[['cycle','chamber','district','party','candidate']].drop_duplicates().shape[0]}.")
    if args.fetch_summaries:
        summaries=retrieve_pilot_summaries(args.delay)
        print(f"Retrieved {summaries.annual_summary_available.sum()} election-year financial summaries "
              f"for {len(summaries)} strong committee matches.")
