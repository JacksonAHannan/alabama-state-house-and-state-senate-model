"""Build district-constrained FTM fundraising and 2026 state-summary features."""
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from build_candidate_finance_features import norm, canonical_person

ROOT=Path(__file__).resolve().parents[1]; FIN=ROOT/"data"/"raw"/"finance"/"alabama"
WAR=ROOT/"data"/"processed"/"war"; DB=ROOT/"data"/"processed"/"elections"/"alabama_elections.sqlite"
PARTY={"DEMOCRATIC":"D","REPUBLICAN":"R"}

def token_key(value): return " ".join(sorted(canonical_person(value).split()))

def choose(candidate,pool,name_col):
    if pool.empty: return None,0.0,0.0,"not_observed"
    target=token_key(candidate); scored=[]
    for idx,name in pool[name_col].items():
        score=float(fuzz.ratio(target,token_key(name)))
        scored.append((score,idx))
    scored.sort(reverse=True); score,idx=scored[0]; second=scored[1][0] if len(scored)>1 else 0.0
    margin=score-second
    exact=target==token_key(pool.loc[idx,name_col])
    if exact or (score>=94 and margin>=5): return idx,score,margin,"exact_tokens" if exact else "fuzzy_review"
    return None,score,margin,"unmatched"

def candidates():
    with sqlite3.connect(DB) as connection:
        old=pd.read_sql("""select year as cycle,chamber,district,canonical_party as party,
            canonical_name as candidate from canonical_candidates where canonical_party in ('D','R')""",connection)
    final=WAR/"2026_final_candidate_roster.csv"; certified=WAR/"2026_certified_candidate_roster.csv"
    roster=final if final.exists() else certified if certified.exists() else WAR/"2026_candidate_roster_provisional.csv"
    current=pd.read_csv(roster)[["cycle","chamber","district","party","candidate"]]
    return pd.concat([old,current],ignore_index=True)

def ftm(cands):
    raw=pd.read_excel(FIN/"Alabama_FTM_State_Legislative_Finance_2010_2022.xlsx",sheet_name="All Candidates")
    raw=raw.rename(columns={"Election Year":"cycle","Chamber":"chamber","District":"district",
                            "General Party":"party_name","Total $":"fundraising_total","Candidate":"ftm_candidate"})
    raw["chamber"]=raw.chamber.str.lower(); raw["party"]=raw.party_name.map(PARTY)
    raw=raw[raw.cycle.isin([2010,2014,2018,2022])&raw.party.notna()].copy()
    records=[]
    for row in cands[cands.cycle.lt(2026)].itertuples(index=False):
        pool=raw[(raw.cycle.eq(row.cycle))&(raw.chamber.eq(row.chamber))&
                 (raw.district.eq(row.district))&(raw.party.eq(row.party))]
        idx,score,margin,status=choose(row.candidate,pool,"ftm_candidate")
        hit=pool.loc[idx] if idx is not None else None
        records.append({"cycle":row.cycle,"chamber":row.chamber,"district":row.district,"party":row.party,
            "candidate":row.candidate,"ftm_candidate":hit.ftm_candidate if hit is not None else None,
            "fundraising_total":hit.fundraising_total if hit is not None else np.nan,
            "ftm_records":hit["# of Records"] if hit is not None else np.nan,
            "ftm_election_status":hit["Election Status"] if hit is not None else None,
            "finance_observation_status":"observed" if hit is not None else "not_observed_unknown_not_zero",
            "match_method":status,"match_score":score,"match_margin":margin,
            "source":"FollowTheMoney candidate summary"})
    matched=pd.DataFrame(records); matched.to_csv(WAR/"ftm_candidate_finance_matches.csv",index=False)
    race=(matched.pivot(index=["cycle","chamber","district"],columns="party",values="fundraising_total").reset_index())
    for p in ("D","R"):
        if p not in race: race[p]=np.nan
    race=race.rename(columns={"D":"dem_fundraising","R":"rep_fundraising"})
    race["ftm_finance_complete"]=race.dem_fundraising.notna()&race.rep_fundraising.notna()
    race["log_fundraising_ratio_d_to_r"]=np.log((race.dem_fundraising+500)/(race.rep_fundraising+500))
    # Explicit sensitivity only; this is never the primary feature.
    race["log_fundraising_ratio_zero_assumption"]=np.log(
        (race.dem_fundraising.fillna(0)+500)/(race.rep_fundraising.fillna(0)+500))
    race.to_csv(WAR/"ftm_race_finance_features.csv",index=False)
    return matched,race

def state_2026(cands):
    parts=[]
    for chamber,label in [("house","House"),("senate","Senate")]:
        frame=pd.read_csv(FIN/f"State {label} Fundraising 2026 Cycle.csv")
        frame["chamber"]=chamber; parts.append(frame)
    raw=pd.concat(parts,ignore_index=True).rename(columns={"Candidate":"state_candidate",
        "Monetary Contributions":"state_contributions","Monetary Expenditures":"state_expenditures",
        "Beginning Funds on Hand":"state_beginning_cash","Ending Funds on Hand":"state_ending_cash",
        "Candidate Status":"state_candidate_status"})
    # Product rule: use one main fundraising committee row per candidate. Prefer
    # an active committee, then the row with the largest monetary contributions.
    raw["candidate_key"]=raw.state_candidate.map(token_key)
    raw["active_priority"]=raw.state_candidate_status.astype(str).str.upper().eq("ACTIVE").astype(int)
    raw["candidate_source_rows"]=raw.groupby(["chamber","candidate_key"]).state_candidate.transform("size")
    grouped=(raw.sort_values(["active_priority","state_contributions"],ascending=False)
             .drop_duplicates(["chamber","candidate_key"])
             .rename(columns={"candidate_source_rows":"state_rows"}))
    grouped.to_csv(WAR/"2026_state_main_committee_source.csv",index=False)
    records=[]
    for row in cands[cands.cycle.eq(2026)].itertuples(index=False):
        pool=grouped[grouped.chamber.eq(row.chamber)]
        idx,score,margin,status=choose(row.candidate,pool,"state_candidate")
        hit=pool.loc[idx] if idx is not None else None
        records.append({"cycle":2026,"chamber":row.chamber,"district":row.district,"party":row.party,"candidate":row.candidate,
            "state_candidate":hit.state_candidate if hit is not None else None,
            "state_contributions":hit.state_contributions if hit is not None else np.nan,
            "state_expenditures":hit.state_expenditures if hit is not None else np.nan,
            "state_rows":hit.state_rows if hit is not None else 0,
            "finance_observation_status":"observed" if hit is not None else "no_state_entry_zero_assumption_sensitivity_only",
            "match_method":status,"match_score":score,"match_margin":margin})
    result=pd.DataFrame(records); result.to_csv(WAR/"2026_state_candidate_finance_matches.csv",index=False)
    result[~result.match_method.eq("exact_tokens")].to_csv(WAR/"2026_state_finance_review.csv",index=False)
    return result

def main():
    cands=candidates(); historical,races=ftm(cands); current=state_2026(cands)
    transaction_path=WAR/"candidate_finance_matches.csv"
    if transaction_path.exists():
        transaction=pd.read_csv(transaction_path)
        transaction=transaction[transaction.cycle.eq(2026)][["cycle","chamber","district","party","candidate",
            "candidate_expenditures","finance_match_method"]]
        reconciliation=current.merge(transaction,on=["cycle","chamber","district","party","candidate"],how="left")
        reconciliation["state_missing_transaction_positive"]=(
            reconciliation.state_expenditures.isna()&reconciliation.candidate_expenditures.fillna(0).gt(0))
        reconciliation["zero_assumption_status"]=np.select([
            reconciliation.state_expenditures.notna(),
            reconciliation.state_missing_transaction_positive,
            reconciliation.finance_match_method.fillna("unmatched").ne("unmatched")],
            ["state_summary_observed","invalid_zero_assumption_transactions_positive",
             "transaction_match_zero_expenditures"],default="unknown_no_matched_filing")
        reconciliation.to_csv(WAR/"2026_state_vs_transaction_finance_reconciliation.csv",index=False)
    coverage=pd.concat([
        historical.assign(observed=historical.finance_observation_status.eq("observed")).groupby(["cycle","party"])["observed"].agg(["size","sum"]).reset_index().assign(source="FTM"),
        current.assign(observed=current.finance_observation_status.eq("observed")).groupby(["cycle","party"])["observed"].agg(["size","sum"]).reset_index().assign(source="state_website")])
    coverage=coverage.rename(columns={"size":"candidates","sum":"observed"}); coverage["coverage"]=coverage.observed/coverage.candidates
    coverage.to_csv(WAR/"multisource_finance_coverage.csv",index=False)
    print(coverage.to_string(index=False))
    print(f"FTM complete D/R races: {races.ftm_finance_complete.sum()}/{len(races)}")
    if transaction_path.exists():
        print("\n2026 zero-assumption audit:\n"+reconciliation.zero_assumption_status.value_counts().to_string())

if __name__=="__main__": main()
