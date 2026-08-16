"""Normalize DIME state finance records and build provenance-aware resource features."""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from build_candidate_finance_features import canonical_person
from warehouse import (ROOT, begin_run, connect, finish_run, initialize, register_source_file,
                       register_table)

WAR=ROOT/"data"/"processed"/"war"
RAW=ROOT/"data"/"raw"/"finance"/"dime_recipients_1979_2024.csv"
SCHEMA=Path(__file__).with_name("warehouse_finance_schema.sql")
PARTY={"100":"D","200":"R"}
SMOOTHING_CONSTANT=500.0


def source_path() -> Path:
    """Handle the downloaded archive directory that repeats the CSV filename."""
    if RAW.is_file(): return RAW
    files=sorted(RAW.glob("*.csv")) if RAW.is_dir() else []
    if len(files)!=1: raise FileNotFoundError(f"Expected one DIME recipient CSV under {RAW}; found {files}")
    return files[0]


def token_key(value: object) -> str:
    return " ".join(sorted(canonical_person(value).split()))


def district_number(value: object) -> float:
    match=re.search(r"(\d+)",str(value))
    return float(match.group(1)) if match else np.nan


def load_dime(path: Path | None=None) -> pd.DataFrame:
    path=path or source_path(); parts=[]
    columns=["cycle","bonica.rid","bonica.cid","name","lname","party","state","seat","district",
             "total.receipts","total.disbursements","total.indiv.contribs","total.unitemized",
             "total.pac.contribs","total.party.contribs","total.contribs.from.candidate",
             "num.givers","recipient.cfscore"]
    for chunk in pd.read_csv(path,usecols=columns,chunksize=100000,low_memory=False):
        parts.append(chunk[chunk.state.astype(str).str.upper().eq("AL") &
                           chunk.seat.isin(["state:lower","state:upper"])].copy())
    frame=pd.concat(parts,ignore_index=True)
    frame["chamber"]=frame.seat.map({"state:lower":"house","state:upper":"senate"})
    frame["district_num"]=frame.district.map(district_number)
    frame["party_letter"]=frame.party.astype(str).str.strip().map(PARTY)
    frame["normalized_name"]=frame.name.map(canonical_person)
    frame=frame.dropna(subset=["cycle","district_num"]).copy()
    frame["cycle"]=frame.cycle.astype(int); frame["district_num"]=frame.district_num.astype(int)
    # Stable even when Bonica IDs are absent or reused across cycles.
    frame["dime_recipient_cycle_id"]=["DIME-"+hashlib.sha256(
        f"{y}|{c}|{d}|{p}|{n}|{rid}".encode()).hexdigest()[:20].upper()
        for y,c,d,p,n,rid in zip(frame.cycle,frame.chamber,frame.district_num,
                                 frame.party_letter.fillna(""),frame.normalized_name,
                                 frame["bonica.rid"].fillna(""))]
    if frame.dime_recipient_cycle_id.duplicated().any():
        raise ValueError("DIME normalized recipient-cycle IDs are not unique")
    return frame


def canonical_candidates(connection: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql("""SELECT canonical_candidate_id,year,chamber,district,
      canonical_party AS party,canonical_name AS candidate
      FROM canonical_candidates WHERE canonical_party IN ('D','R')""",connection)


def match_candidates(candidates: pd.DataFrame,dime: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for candidate in candidates[candidates.year.isin(dime.cycle.unique())].itertuples(index=False):
        pool=dime[(dime.cycle.eq(candidate.year))&(dime.chamber.eq(candidate.chamber))&
                  (dime.district_num.eq(candidate.district))&(dime.party_letter.eq(candidate.party))]
        scores=sorted([(float(fuzz.ratio(token_key(candidate.candidate),token_key(row.name))),row)
                       for row in pool.itertuples(index=False)],key=lambda x:x[0],reverse=True)
        if not scores:
            rows.append({"canonical_candidate_id":candidate.canonical_candidate_id,"year":candidate.year,
                "chamber":candidate.chamber,"district":candidate.district,"party":candidate.party,
                "candidate":candidate.candidate,"review_status":"review","match_method":"no_candidate",
                "match_score":0.0,"match_margin":0.0})
            continue
        score,hit=scores[0]; second=scores[1][0] if len(scores)>1 else 0.0; margin=score-second
        exact=token_key(candidate.candidate)==token_key(hit.name)
        candidate_surname=canonical_person(candidate.candidate).split()[-1]
        surname_hits=pool[pool.lname.map(canonical_person).eq(candidate_surname)]
        unique_surname=len(surname_hits)==1 and hit.dime_recipient_cycle_id==surname_hits.iloc[0].dime_recipient_cycle_id
        accepted=exact or unique_surname or (score>=94 and margin>=5)
        rows.append({"canonical_candidate_id":candidate.canonical_candidate_id,"year":candidate.year,
            "chamber":candidate.chamber,"district":candidate.district,"party":candidate.party,
            "candidate":candidate.candidate,"dime_recipient_cycle_id":hit.dime_recipient_cycle_id,
            "dime_name":hit.name,"total_receipts":hit._asdict().get("_8",np.nan),
            "match_method":"exact_tokens" if exact else "district_party_surname" if unique_surname else "fuzzy" if accepted else "candidate_review",
            "match_score":score,"match_margin":margin,"review_status":"accepted" if accepted else "review"})
    result=pd.DataFrame(rows)
    # itertuples renames dotted source columns unpredictably; merge the monetary value by stable ID.
    result=result.drop(columns=["total_receipts"],errors="ignore").merge(
        dime[["dime_recipient_cycle_id","total.receipts"]].rename(columns={"total.receipts":"total_receipts"}),
        on="dime_recipient_cycle_id",how="left",validate="many_to_one")
    return result


def harmonized_resources(candidates: pd.DataFrame,dime_matches: pd.DataFrame) -> pd.DataFrame:
    base=candidates.rename(columns={"year":"cycle"}).copy()
    dime=(dime_matches[dime_matches.review_status.eq("accepted")]
          [["canonical_candidate_id","dime_name","total_receipts","match_method"]]
          .rename(columns={"dime_name":"source_candidate_name"}))
    base=base.merge(dime,on="canonical_candidate_id",how="left",validate="one_to_one")
    base["total_resources_raised"]=np.where(base.cycle.le(2010),base.total_receipts,np.nan)
    base["source_name"]=np.where(base.cycle.le(2010)&base.total_receipts.notna(),"DIME",None)
    base["source_measure"]=np.where(base.source_name.eq("DIME"),"total.receipts",None)

    ftm_path=WAR/"ftm_candidate_finance_matches.csv"
    if ftm_path.exists():
        ftm=pd.read_csv(ftm_path)
        accepted=ftm.finance_observation_status.eq("observed")
        ftm=ftm[accepted][["cycle","chamber","district","party","candidate","ftm_candidate",
                           "fundraising_total","match_method"]]
        ftm["candidate_key"]=ftm.candidate.map(token_key)
        base["candidate_key"]=base.candidate.map(token_key)
        base=base.merge(ftm.drop(columns="candidate"),on=["cycle","chamber","district","party","candidate_key"],
                        how="left",suffixes=("","_ftm"),validate="one_to_one")
        use=base.cycle.between(2014,2022)&base.fundraising_total.notna()
        base.loc[use,"total_resources_raised"]=base.loc[use,"fundraising_total"]
        base.loc[use,"source_name"]="FollowTheMoney"
        base.loc[use,"source_measure"]="fundraising_total"
        base.loc[use,"source_candidate_name"]=base.loc[use,"ftm_candidate"]
        base.loc[use,"match_method"]=base.loc[use,"match_method_ftm"]

    state_path=WAR/"2026_state_candidate_finance_matches.csv"
    if state_path.exists():
        state=pd.read_csv(state_path); state["candidate_key"]=state.candidate.map(token_key)
        state=state[state.finance_observation_status.eq("observed")]
        state=state[["cycle","chamber","district","party","candidate_key","state_candidate",
                     "state_contributions","match_method"]]
        base=base.merge(state,on=["cycle","chamber","district","party","candidate_key"],how="left",
                        suffixes=("","_state"),validate="one_to_one")
        use=base.cycle.eq(2026)&base.state_contributions.notna()
        base.loc[use,"total_resources_raised"]=base.loc[use,"state_contributions"]
        base.loc[use,"source_name"]="Alabama FCPA state summary"
        base.loc[use,"source_measure"]="monetary_contributions_as_of_download"
        base.loc[use,"source_candidate_name"]=base.loc[use,"state_candidate"]
        base.loc[use,"match_method"]=base.loc[use,"match_method_state"]

    base["resource_observation_status"]=np.where(base.total_resources_raised.notna(),"observed",
                                                  "not_observed_unknown_not_zero")
    base["source_authority_rule"]="DIME through 2010; FollowTheMoney 2014-2022; Alabama FCPA 2026"
    return base[["canonical_candidate_id","cycle","chamber","district","party","candidate",
                 "total_resources_raised","resource_observation_status","source_name","source_measure",
                 "source_candidate_name","match_method","source_authority_rule"]]


def race_features(candidate: pd.DataFrame) -> pd.DataFrame:
    values=candidate.pivot(index=["cycle","chamber","district"],columns="party",
                           values="total_resources_raised").reset_index()
    sources=candidate.pivot(index=["cycle","chamber","district"],columns="party",
                            values="source_name").reset_index()
    for party in ("D","R"):
        if party not in values: values[party]=np.nan
        if party not in sources: sources[party]=None
    result=values.rename(columns={"D":"dem_resources","R":"rep_resources"}).merge(
        sources.rename(columns={"D":"dem_source","R":"rep_source"}),
        on=["cycle","chamber","district"],validate="one_to_one")
    result["finance_complete"]=result.dem_resources.notna()&result.rep_resources.notna()
    result["log_resource_ratio_d_to_r"]=np.log((result.dem_resources+SMOOTHING_CONSTANT)/
                                                (result.rep_resources+SMOOTHING_CONSTANT))
    result.loc[~result.finance_complete,"log_resource_ratio_d_to_r"]=np.nan
    result["smoothing_constant"]=SMOOTHING_CONSTANT
    return result


def load_warehouse(dime: pd.DataFrame,matches: pd.DataFrame,candidate: pd.DataFrame,races: pd.DataFrame,
                   path: Path) -> None:
    with closing(connect()) as connection:
        initialize(connection); connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run=begin_run(connection,"finance",{"dime_path":str(path.relative_to(ROOT))})
        source_id=register_source_file(connection,provider="DIME",path=path,media_type="text/csv",
            extraction_status="normalized",authoritative_scope="historical_candidate_receipts_and_identity")
        normalized=dime.rename(columns={"cycle":"cycle","bonica.rid":"bonica_recipient_id",
            "bonica.cid":"bonica_candidate_id","name":"recipient_name","party":"party_code",
            "party_letter":"party","district_num":"district","total.receipts":"total_receipts",
            "total.disbursements":"total_disbursements","total.indiv.contribs":"individual_contributions",
            "total.unitemized":"unitemized_contributions","total.pac.contribs":"pac_contributions",
            "total.party.contribs":"party_contributions","total.contribs.from.candidate":"candidate_contributions",
            "num.givers":"number_givers","recipient.cfscore":"recipient_cfscore"})
        cols=["dime_recipient_cycle_id","cycle","bonica_recipient_id","bonica_candidate_id","recipient_name",
              "normalized_name","party_code","party","state","chamber","district","total_receipts",
              "total_disbursements","individual_contributions","unitemized_contributions","pac_contributions",
              "party_contributions","candidate_contributions","number_givers","recipient_cfscore"]
        normalized=normalized[cols]; normalized.insert(1,"source_file_id",source_id)
        connection.execute("DELETE FROM canonical_candidate_finance_match WHERE source_name='DIME'")
        connection.execute("DELETE FROM source_dime_recipient")
        normalized.to_sql("source_dime_recipient",connection,if_exists="append",index=False)
        accepted=matches[matches.review_status.eq("accepted")][["dime_recipient_cycle_id",
            "canonical_candidate_id","match_method","match_score","match_margin","review_status"]].copy()
        accepted.insert(0,"source_name","DIME")
        accepted.to_sql("canonical_candidate_finance_match",connection,if_exists="append",index=False)
        connection.execute("DELETE FROM mart_candidate_resources"); connection.execute("DELETE FROM mart_race_resource_features")
        candidate.rename(columns={"cycle":"year","candidate":"candidate_name"}).to_sql(
            "mart_candidate_resources",connection,if_exists="append",index=False)
        races.rename(columns={"cycle":"year"}).assign(finance_complete=lambda x:x.finance_complete.astype(int)).to_sql(
            "mart_race_resource_features",connection,if_exists="append",index=False)
        for table,layer,key,description in [
            ("source_dime_recipient","source","dime_recipient_cycle_id","Normalized DIME Alabama legislative recipients"),
            ("canonical_candidate_finance_match","canonical","source/recipient/candidate","Accepted finance identity links"),
            ("mart_candidate_resources","mart","canonical_candidate_id","Authority-selected candidate fundraising resources"),
            ("mart_race_resource_features","mart","year/chamber/district","Complete-case D/R fundraising ratios")]:
            register_table(connection,table,layer,"scripts/build_dime_finance_features.py",key,
                           "DIME<=2010; FTM 2014-2022; Alabama FCPA 2026","replace",description)
        finish_run(connection,run,{"dime_rows":len(dime),"accepted_matches":len(accepted),
                                   "candidate_rows":len(candidate),"complete_races":int(races.finance_complete.sum())})
        connection.commit()


def main(skip_warehouse: bool=False) -> None:
    path=source_path(); dime=load_dime(path)
    with closing(connect(readonly=True)) as connection: candidates=canonical_candidates(connection)
    matches=match_candidates(candidates,dime)
    candidate=harmonized_resources(candidates,matches); races=race_features(candidate)
    WAR.mkdir(parents=True,exist_ok=True)
    dime.to_csv(WAR/"dime_alabama_legislative_recipients.csv",index=False)
    matches.to_csv(WAR/"dime_candidate_finance_matches.csv",index=False)
    matches[~matches.review_status.eq("accepted")].to_csv(WAR/"dime_candidate_finance_review.csv",index=False)
    candidate.to_csv(WAR/"candidate_resource_harmonized.csv",index=False)
    races.to_csv(WAR/"race_resource_features_harmonized.csv",index=False)
    coverage=(candidate.assign(observed=candidate.resource_observation_status.eq("observed"))
              .groupby(["cycle","source_name"],dropna=False).agg(candidates=("candidate","size"),
                   observed=("observed","sum"),resources=("total_resources_raised","sum")).reset_index())
    coverage.to_csv(WAR/"harmonized_finance_coverage.csv",index=False)
    if not skip_warehouse: load_warehouse(dime,matches,candidate,races,path)
    print(coverage.to_string(index=False)); print(f"DIME review rows: {(matches.review_status=='review').sum()}")


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--skip-warehouse",action="store_true")
    args=parser.parse_args(); main(args.skip_warehouse)
