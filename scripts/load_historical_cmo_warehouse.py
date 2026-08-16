"""Warehouse official pre-precinct CMO inputs and publish a cycle gap contract."""
from __future__ import annotations

import hashlib
import re
from contextlib import closing
from pathlib import Path

import pandas as pd

from build_candidate_finance_features import canonical_person
from warehouse import (ROOT,begin_run,connect,finish_run,initialize,register_source_file,
                       register_table)

RAW=ROOT/"data"/"raw"/"alabama_elections_and_geography"
STATEWIDE=ROOT/"data"/"raw"/"historical_statewide_elections"
OUT=ROOT/"data"/"processed"/"elections"
SCHEMA=Path(__file__).with_name("warehouse_historical_cmo_schema.sql")
LEGISLATIVE={
    1986:(RAW/"eastateleg86.xls",{"senate":"Sen.86gen.","house":"Hse.86gen."}),
    1990:(RAW/"eastateleg90.xls",{"senate":"Sen.90Gen.","house":"Hse.90Gen."}),
}
STATEWIDE_1990={
    "Governor":("eagovernor1946-2010.xls","Gen.90"),
    "Lieutenant Governor":("ealtgovernor1986-2010.xls","Gen.90"),
    "Attorney General":("eaattorneygeneral1986-2010.xls","Gen.90"),
    "Secretary of State":("easecretaryofstate1986-2010_0.xls","Gen.90"),
    "State Treasurer":("eatreasurer1986-2010.xls","Gen.90"),
    "Commissioner of Agriculture and Industries":("eacommissionerag-and-ind1986-2010.xls","Gen.90"),
}
# The official 1986/1990 returns remain archived, but 1994 is the first CMO-
# eligible cycle because the 1983 House plan has no recoverable authoritative
# geometry in the current source collection.
CYCLES=list(range(1994,2023,4))


def stable_id(prefix: str,*values: object) -> str:
    return prefix+"-"+hashlib.sha256("|".join(map(str,values)).encode()).hexdigest()[:20].upper()


def parse_legislative(path: Path,year: int,sheets: dict[str,str]) -> pd.DataFrame:
    records=[]; district_pattern=r"\s*Dist(?:rict|ict)\s+(\d+)\s*"
    for chamber,sheet in sheets.items():
        data=pd.read_excel(path,sheet_name=sheet,header=None).fillna("")
        for row_number in range(len(data)):
            for column in range(len(data.columns)):
                district_match=re.fullmatch(district_pattern,str(data.iat[row_number,column]),re.I)
                if not district_match: continue
                district=int(district_match.group(1)); block_end=min(column+5,len(data.columns))
                same_row=any(re.search(r"\(([DR])\)",str(data.iat[row_number,k]),re.I)
                             for k in range(column+1,block_end))
                header=row_number if same_row else row_number+1
                county_column=column if same_row else max(0,column-1)
                candidates=[]
                for candidate_column in range(county_column+1,block_end):
                    label=str(data.iat[header,candidate_column]).strip()
                    party_match=re.search(r"\(([DR])\)",label,re.I)
                    if party_match:
                        name=re.sub(r"\s*\([DR]\)\s*","",label,flags=re.I).strip()
                        candidates.append((candidate_column,name,party_match.group(1).upper()))
                for result_row in range(header+1,len(data)):
                    if any(re.fullmatch(district_pattern,str(data.iat[result_row,k]),re.I)
                           for k in range(column,block_end)): break
                    county=str(data.iat[result_row,county_column]).strip()
                    if not county: continue
                    for candidate_column,name,party in candidates:
                        votes=pd.to_numeric(data.iat[result_row,candidate_column],errors="coerce")
                        if pd.isna(votes): continue
                        records.append({"result_id":stable_id("HLR",year,chamber,district,county,name,party),
                            "year":year,"chamber":chamber,"district":district,"county":county,
                            "candidate_name":name,"normalized_name":canonical_person(name),"party":party,
                            "votes":float(votes),"source_sheet":sheet})
    result=pd.DataFrame(records)
    conflicts=result.groupby("result_id").votes.nunique()
    if (conflicts>1).any(): raise ValueError("Conflicting duplicate historical legislative results")
    result=result.drop_duplicates("result_id")
    if year==1990:
        counts=result.groupby("chamber").district.nunique().to_dict()
        if counts!={"house":105,"senate":35}: raise ValueError(f"Incomplete 1990 district parse: {counts}")
    return result


def parse_1990_statewide(path: Path,office: str,sheet: str="Gen.90") -> pd.DataFrame:
    data=pd.read_excel(path,sheet_name=sheet,header=None)
    headers=data.iloc[0].tolist(); records=[]
    candidates=[]
    for column,label in enumerate(headers[1:],start=1):
        match=re.search(r"\(([DR])\)",str(label),re.I)
        if match:
            candidates.append((column,re.sub(r"\s*\([DR]\)\s*","",str(label),flags=re.I).strip(),match.group(1)))
    for row in range(1,len(data)):
        county=str(data.iat[row,0]).strip()
        if county in {"","Calculated","Reported","nan"}: continue
        for column,name,party in candidates:
            votes=pd.to_numeric(data.iat[row,column],errors="coerce")
            if pd.isna(votes): continue
            records.append({"result_id":stable_id("HSR",1990,office,county,name,party),"year":1990,
                "office":office,"county":county,"candidate_name":name,
                "normalized_name":canonical_person(name),"party":party,"votes":float(votes),
                "source_sheet":sheet})
    result=pd.DataFrame(records)
    if result.county.nunique()!=67: raise ValueError(f"Expected 67 counties in 1990 governor; found {result.county.nunique()}")
    return result


def parse_1990_governor(path: Path) -> pd.DataFrame:
    return parse_1990_statewide(path,"Governor","Gen.90")


def candidate_results(legislative: pd.DataFrame) -> pd.DataFrame:
    result=(legislative.groupby(["year","chamber","district","party","candidate_name","normalized_name"],as_index=False)
            .agg(votes=("votes","sum"),counties_reported=("county","nunique")))
    result["winner"]=(result.votes==result.groupby(["year","chamber","district"]).votes.transform("max")).astype(int)
    result["historical_candidate_id"]=[stable_id("HC",*x) for x in result[["year","chamber","district","party","normalized_name"]].itertuples(index=False,name=None)]
    result["source_name"]="Alabama SOS historical legislative archive"
    return result[["historical_candidate_id","year","chamber","district","party","candidate_name",
                   "normalized_name","votes","winner","counties_reported","source_name"]]


def incumbency_evidence(candidates: pd.DataFrame) -> pd.DataFrame:
    prior=candidates[(candidates.year.eq(1986))&candidates.winner.eq(1)]
    current=candidates[candidates.year.eq(1990)]; rows=[]
    for candidate in current.itertuples(index=False):
        matches=prior[(prior.chamber.eq(candidate.chamber))&(prior.district.eq(candidate.district))&
                      (prior.normalized_name.eq(candidate.normalized_name))]
        supported=len(matches)==1
        rows.append({"historical_candidate_id":candidate.historical_candidate_id,
            "incumbent_status":"supported_prior_winner" if supported else "unknown",
            "prior_year":1986 if supported else None,
            "prior_candidate_name":matches.iloc[0].candidate_name if supported else None,
            "match_method":"same_district_exact_normalized_name" if supported else None,
            "evidence_note":("Exact match to a recorded 1986 general-election winner" if supported else
                "The 1986 archive omits many uncontested districts; absence is not evidence of non-incumbency")})
    return pd.DataFrame(rows)


def coverage() -> pd.DataFrame:
    rows=[]
    for cycle in CYCLES:
        facts={
          "legislative_results":("available",
            "data/raw/alabama_elections_and_geography/eastateleg90.xls" if cycle==1990 else "warehouse:canonical_vote_observations",
            "source_historical_legislative_county_result" if cycle==1990 else "canonical_vote_observations",None),
          "same_cycle_statewide_baseline":("available" if cycle>=2014 else "partial",
            "warehouse:canonical_vote_observations",
            "mart_historical_district_office_baseline" if cycle==1994 else "canonical_vote_observations",
            None if cycle>=2014 else ("Built for 1994; split precincts use provisional legislative ballot-activity shares"
                                      if cycle==1994 else "A plan-specific district allocation has not been built")),
          "district_plan_geometry":("missing" if cycle==1990 else "available",
            None if cycle==1990 else "data/raw/alabama_elections_and_geography/",None,
            "The available 1992-2000 plan is not the plan used in the 1990 election" if cycle==1990 else None),
          "precinct_or_block_crosswalk":("available" if cycle>=2014 else ("partial" if cycle==1994 else "missing"),
            "warehouse:mart_historical_precinct_district_weight" if cycle==1994 else None,
            "mart_historical_precinct_district_weight" if cycle==1994 else
              ("geographic_precinct_district_weights" if cycle>=2014 else None),
            None if cycle>=2014 else ("Official ballot district labels are exact for single-district precincts; split shares are provisional"
                                      if cycle==1994 else "No validated plan-specific crosswalk has been built for this cycle")),
          "incumbency":("partial" if cycle==1994 else "available",
            "warehouse:mart_historical_candidate_incumbency" if cycle==1994 else "warehouse:canonical_candidates",
            "mart_historical_candidate_incumbency" if cycle==1994 else "canonical_candidates",
            "Positive matches to unique 1990 winning surnames; unmatched candidates remain unknown" if cycle==1994 else None),
          "candidate_finance":("available" if cycle>=1998 else "missing",
            "warehouse:mart_candidate_resources" if cycle>=1998 else None,
            "mart_candidate_resources" if cycle>=1998 else None,
            None if cycle>=1998 else "DIME Alabama state legislative receipts begin in 1998"),
          "district_demographics":("available" if cycle>=2014 else ("partial" if cycle==1994 else "missing"),
            "data/processed/demographics/1994_district_demographics.csv" if cycle==1994 else
              ("data/processed/demographics/acs_direct_sld_demographics.csv" if cycle>=2014 else None),
            "mart_historical_district_demographic_feature" if cycle==1994 else None,
            "1990 SF3 tract-area interpolation; not block-level allocation" if cycle==1994 else
              (None if cycle>=2014 else "No plan-specific historical demographic feature table is currently built")),
          "previous_presidential_context":("available" if cycle>=2014 else ("partial" if cycle==1994 else "missing"),
            "data/processed/presidential/1994_district_presidential_features.csv" if cycle==1994 else
              ("data/processed/presidential/" if cycle>=2014 else None),
            "mart_historical_district_presidential_feature" if cycle==1994 else None,
            "Official 1992 precinct returns; Montgomery and Talladega presidential columns are blank and Wilcox is absent; unmatched precincts use fallback allocation" if cycle==1994 else
              (None if cycle>=2014 else "Prior presidential results have not been allocated to this legislative plan")),
        }
        for domain,(status,locator,obj,limitation) in facts.items():
            rows.append({"cycle":cycle,"input_domain":domain,"status":status,"source_locator":locator,
                         "warehouse_object":obj,"limitation":limitation,
                         "required_for_specification":"core" if domain in {"legislative_results","same_cycle_statewide_baseline","incumbency"} else "extended"})
    return pd.DataFrame(rows)


def main() -> None:
    frames=[]; source_ids={}
    with closing(connect()) as connection:
        initialize(connection); connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run=begin_run(connection,"historical_cmo_inputs",{"target_start":1994,"target_end":2022,
            "archival_support_years":[1986,1990],"excluded_cycle_reason":
            "No authoritative 1983 Alabama House plan geometry"})
        for year,(path,sheets) in LEGISLATIVE.items():
            frame=parse_legislative(path,year,sheets); frames.append(frame)
            source_ids[year]=register_source_file(connection,provider="alabama_sos",path=path,
                original_url=f"https://www.sos.alabama.gov/sites/default/files/election-data/2017-06/{path.name}",
                media_type="application/vnd.ms-excel",extraction_status="normalized",
                authoritative_scope="official_historical_legislative_county_totals")
            frame.insert(1,"source_file_id",source_ids[year])
        legislative=pd.concat(frames,ignore_index=True); candidates=candidate_results(legislative)
        incumbency=incumbency_evidence(candidates)
        statewide_parts=[]
        for office,(filename,sheet) in STATEWIDE_1990.items():
            source_path=STATEWIDE/filename; part=parse_1990_statewide(source_path,office,sheet)
            source_id=register_source_file(connection,provider="alabama_sos",path=source_path,
                original_url=f"https://www.sos.alabama.gov/sites/default/files/election-data/2017-06/{filename}",
                media_type="application/vnd.ms-excel",extraction_status="normalized",
                authoritative_scope="official_historical_statewide_county_totals")
            part.insert(1,"source_file_id",source_id); statewide_parts.append(part)
        statewide=pd.concat(statewide_parts,ignore_index=True); availability=coverage()
        tables=[("source_historical_legislative_county_result",legislative),
                ("source_historical_statewide_county_result",statewide),
                ("mart_historical_candidate_result",candidates),
                ("mart_historical_incumbency_evidence",incumbency),
                ("mart_cmo_cycle_input_coverage",availability)]
        # Delete children first so repeatable replacement respects foreign keys.
        for table in ["mart_historical_incumbency_evidence","mart_historical_candidate_result",
                      "source_historical_legislative_county_result","source_historical_statewide_county_result",
                      "mart_cmo_cycle_input_coverage"]:
            connection.execute(f"DELETE FROM {table}")
        for table,frame in tables:
            frame.to_sql(table,connection,if_exists="append",index=False)
        definitions=[
          ("source_historical_legislative_county_result","source","result_id","Official county/district legislative totals"),
          ("source_historical_statewide_county_result","source","result_id","Official historical statewide county totals"),
          ("mart_historical_candidate_result","mart","historical_candidate_id","Aggregated pre-precinct legislative candidate results"),
          ("mart_historical_incumbency_evidence","mart","historical_candidate_id","Conservative prior-winner incumbency evidence"),
          ("mart_cmo_cycle_input_coverage","qa","cycle/input_domain","Explicit CMO source readiness and gaps")]
        for table,layer,key,description in definitions:
            register_table(connection,table,layer,"scripts/load_historical_cmo_warehouse.py",key,
                           "Alabama SOS; unknown remains unknown","replace",description)
        finish_run(connection,run,{"legislative_county_rows":len(legislative),"candidate_rows":len(candidates),
            "statewide_county_rows":len(statewide),"1990_incumbents_supported":int((incumbency.incumbent_status=='supported_prior_winner').sum()),
            "first_cmo_eligible_cycle":1994})
        connection.commit()
    OUT.mkdir(parents=True,exist_ok=True)
    legislative.to_csv(OUT/"historical_legislative_county_results.csv",index=False)
    candidates.to_csv(OUT/"historical_candidate_results.csv",index=False)
    statewide.to_csv(OUT/"historical_statewide_county_results.csv",index=False)
    incumbency.to_csv(OUT/"historical_incumbency_evidence.csv",index=False)
    availability.to_csv(OUT/"cmo_cycle_input_coverage.csv",index=False)
    print(candidates.groupby(["year","chamber"]).agg(candidates=("historical_candidate_id","size"),districts=("district","nunique")).to_string())
    print("\nCMO eligibility begins in 1994; 1986 and 1990 remain archival support data.")


if __name__=="__main__": main()
