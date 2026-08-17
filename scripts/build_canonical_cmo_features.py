"""Assemble four-cycle CMO features from the canonical election database."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
from build_1998_2006_context_features import county_population_district_weights

ROOT=Path(__file__).resolve().parents[1]; DB=ROOT/"data"/"processed"/"elections"/"alabama_elections.sqlite"
ELECT=ROOT/"data"/"processed"/"elections"; WAR=ROOT/"data"/"processed"/"war"
CYCLES=(1994,1998,2002,2006,2010,2014,2018,2022); PUBLISHED_MODEL_CYCLES=(2010,2014,2018,2022); CORE=("Governor","Attorney General")
PARTY_2010={"RON SPARKS":"D","ROBERT BENTLEY":"R","JAMES H ANDERSON":"D","LUTHER STRANGE":"R"}
PARTY_1994={"EVANS":"D","SESSIONS":"R"}

def nullable_bool(series: pd.Series) -> pd.Series:
    """Parse mixed CSV booleans without treating the string False as true."""
    numeric=pd.to_numeric(series,errors="coerce")
    text=series.astype("string").str.strip().str.lower().map(
        {"true":1.0,"false":0.0,"yes":1.0,"no":0.0})
    return numeric.fillna(text).map({1.0:True,0.0:False}).astype("boolean")

def main():
    with sqlite3.connect(DB) as c:
        candidates=pd.read_sql("select * from canonical_candidates",c)
        observations=pd.read_sql("""select year,county_key,precinct_key,office,candidate_key,party_norm,votes
          from vote_observations where source='alabama_sos' and office in ('Governor','Attorney General')""",c)
        legislative=pd.read_sql("""select year,county_key,precinct_key,office,district,votes
          from vote_observations where source='alabama_sos' and office in ('State House','State Senate')
          and district is not null""",c)
        nodes=pd.read_sql("select node_id,year,county_key,precinct_key from precinct_nodes where source='alabama_sos'",c)
    candidates=candidates[candidates.year.isin(CYCLES)&candidates.canonical_party.isin(["D","R"])]
    result=(candidates.groupby(["year","chamber","district","canonical_party"],as_index=False).canonical_votes.sum()
            .pivot(index=["year","chamber","district"],columns="canonical_party",values="canonical_votes").fillna(0).reset_index())
    for party in ("D","R"):
        if party not in result: result[party]=0
    result=result.rename(columns={"year":"cycle","D":"dem_votes","R":"rep_votes"})
    result["two_party_votes"]=result.dem_votes+result.rep_votes
    result["legislative_dem_margin"]=100*(result.dem_votes-result.rep_votes)/result.two_party_votes.where(result.two_party_votes.gt(0))
    result["war_eligible"]=result.dem_votes.gt(0)&result.rep_votes.gt(0)
    result["contest_status"]=np.select(
        [result.dem_votes.gt(0)&result.rep_votes.eq(0),
         result.rep_votes.gt(0)&result.dem_votes.eq(0),
         result.war_eligible],
        ["unopposed_democrat","unopposed_republican","contested_two_party"],
        default="no_major_party_votes")
    inc=(candidates[candidates.incumbent.astype(bool)].groupby(["year","chamber","district","canonical_party"]).size()
         .unstack(fill_value=0).reset_index())
    inc=inc.rename(columns={"year":"cycle","D":"dem_incumbent","R":"rep_incumbent"})
    for col in ("dem_incumbent","rep_incumbent"):
        if col not in inc: inc[col]=0
    result=result.merge(inc[["cycle","chamber","district","dem_incumbent","rep_incumbent"]],how="left")
    result[["dem_incumbent","rep_incumbent"]]=result[["dem_incumbent","rep_incumbent"]].fillna(0).astype(bool)

    observations=observations.merge(nodes,on=["year","county_key","precinct_key"],validate="many_to_one")
    is_1994_ag=observations.year.eq(1994)&observations.office.eq("Attorney General")
    observations.loc[is_1994_ag,"party_norm"]=observations.loc[is_1994_ag,"candidate_key"].map(PARTY_1994).fillna(
        observations.loc[is_1994_ag,"party_norm"])
    observations.loc[observations.year.eq(2010),"party_norm"]=observations.loc[observations.year.eq(2010),"candidate_key"].map(PARTY_2010).fillna("O")
    observations=observations[observations.party_norm.isin(["D","R"])]
    weights=pd.read_csv(ELECT/"canonical_precinct_district_weights.csv")
    allocated=observations.merge(weights,left_on=["year","node_id"],right_on=["cycle","node_id"],validate="many_to_many")
    allocated["allocated_votes"]=allocated.votes*allocated.allocation_weight
    allocated["baseline_allocation_method"]="census_vtd_population"
    # Before 2010, no accepted precinct-to-VTD identity crosswalk has yet been
    # built. Preserve those official races in the CMO database using explicit,
    # provisional legislative-activity shares; never label them geographic.
    historical=legislative[legislative.year.isin(set(CYCLES)-set(PUBLISHED_MODEL_CYCLES))].copy()
    historical["chamber"]=historical.office.map({"State House":"house","State Senate":"senate"})
    activity=(historical.groupby(["year","chamber","county_key","precinct_key","district"],as_index=False).votes.sum()
              .rename(columns={"votes":"district_activity"}))
    activity["precinct_activity"]=activity.groupby(["year","chamber","county_key","precinct_key"]).district_activity.transform("sum")
    activity=activity[activity.precinct_activity.gt(0)]
    activity["allocation_weight"]=activity.district_activity/activity.precinct_activity
    historical_allocations=[]
    for cycle in (1998,2002,2006):
        cycle_obs=observations[observations.year.eq(cycle)]
        for chamber in ("house","senate"):
            chamber_activity=activity[(activity.year.eq(cycle))&(activity.chamber.eq(chamber))]
            joined=cycle_obs.merge(
                chamber_activity,on=["year","county_key","precinct_key"],how="left",
                indicator=True,validate="many_to_many")
            direct=joined[joined._merge.eq("both")].copy()
            direct["cycle"]=cycle
            direct["allocated_votes"]=direct.votes*direct.allocation_weight
            direct["baseline_allocation_method"]="legislative_activity_provisional"
            historical_allocations.append(direct)
            missing=joined[joined._merge.eq("left_only")][cycle_obs.columns].copy()
            fallback=missing.merge(
                county_population_district_weights(cycle,chamber),on="county_key",how="left",
                validate="many_to_many")
            fallback["cycle"]=cycle; fallback["chamber"]=chamber
            fallback["allocated_votes"]=fallback.votes*fallback.allocation_weight
            fallback["baseline_allocation_method"]="county_population_fallback"
            historical_allocations.append(fallback[fallback.allocation_weight.notna()])
    # Keep the separately validated 1994 implementation unchanged.
    oldobs_1994=observations[observations.year.eq(1994)]
    oldactivity_1994=activity[activity.year.eq(1994)]
    if not oldobs_1994.empty and not oldactivity_1994.empty:
        oldalloc=oldobs_1994.merge(oldactivity_1994,on=["year","county_key","precinct_key"],how="inner",validate="many_to_many")
        oldalloc["cycle"]=oldalloc.year; oldalloc["allocated_votes"]=oldalloc.votes*oldalloc.allocation_weight
        oldalloc["baseline_allocation_method"]="legislative_activity_provisional"
        historical_allocations.append(oldalloc)
    allocated=pd.concat([allocated,*historical_allocations],ignore_index=True,sort=False)
    office_baseline=(allocated.groupby(["cycle","chamber","district","office","party_norm"],as_index=False).allocated_votes.sum()
              .pivot(index=["cycle","chamber","district","office"],columns="party_norm",values="allocated_votes").fillna(0).reset_index())
    office_baseline["office_margin"]=100*(office_baseline.D-office_baseline.R)/(office_baseline.D+office_baseline.R).where((office_baseline.D+office_baseline.R).gt(0))
    method=(allocated.groupby(["cycle","chamber","district","office"],as_index=False)
            .baseline_allocation_method.agg(lambda x:
                "county_population_fallback" if (x=="county_population_fallback").any()
                else "legislative_activity_provisional" if (x=="legislative_activity_provisional").any()
                else "census_vtd_population"))
    office_baseline=office_baseline.merge(method,on=["cycle","chamber","district","office"],how="left",validate="one_to_one")
    allocated["fallback_allocated_votes"]=np.where(
        allocated.baseline_allocation_method.eq("county_population_fallback"),
        allocated.allocated_votes,0.0)
    fallback_share=(allocated.groupby(["cycle","chamber","district","office"],as_index=False)
        .agg(all_allocated_votes=("allocated_votes","sum"),fallback_allocated_votes=("fallback_allocated_votes","sum")))
    fallback_share["baseline_fallback_share"]=fallback_share.fallback_allocated_votes/fallback_share.all_allocated_votes.where(
        fallback_share.all_allocated_votes.gt(0))
    office_baseline=office_baseline.merge(
        fallback_share[["cycle","chamber","district","office","baseline_fallback_share"]],
        on=["cycle","chamber","district","office"],how="left",validate="one_to_one")
    office_baseline["baseline_source"]="alabama_sos_canonical"
    legacy=pd.read_csv(WAR/"district_baseline_office.csv")
    legacy=legacy[legacy.office.isin(CORE)][["cycle","chamber","district","office","office_dem_margin"]].rename(columns={"office_dem_margin":"office_margin"})
    legacy["baseline_source"]="openelections_geographic_fallback"
    have=set(map(tuple,office_baseline[["cycle","chamber","district","office"]].values))
    legacy=legacy[[tuple(x) not in have for x in legacy[["cycle","chamber","district","office"]].values]]
    office_baseline=pd.concat([office_baseline,legacy],ignore_index=True,sort=False)
    # Preserve the office-level inputs used by the model for downstream displays.
    # The separate baseline-scenario audit starts in 2010, which previously left
    # the 1994-2006 story entries without their Governor and Attorney General tabs.
    office_baseline.to_csv(ELECT/"canonical_cmo_district_office_baselines.csv",index=False)
    baseline=(office_baseline.groupby(["cycle","chamber","district"],as_index=False)
              .agg(core_index_margin=("office_margin","mean"),core_index_offices=("office","nunique"),
                   baseline_fallback_share=("baseline_fallback_share","max"),
                   baseline_allocation_method=("baseline_allocation_method",lambda x:
                       "county_population_fallback" if (x=="county_population_fallback").any()
                       else "legislative_activity_provisional" if (x=="legislative_activity_provisional").any()
                       else "census_vtd_population")))
    baseline["core_index_complete"]=baseline.core_index_offices.eq(2)
    result=result.merge(baseline,on=["cycle","chamber","district"],how="left")
    result["statewide_index_margin"]=result.core_index_margin
    result["raw_overperformance"]=result.legislative_dem_margin-result.core_index_margin
    result["historical_extension"]=~result.cycle.isin(PUBLISHED_MODEL_CYCLES)
    result["model_tier"]=np.where(result.cycle.eq(1994),"sensitivity_1994","core_1998_2022")
    result["model_eligible"]=result.cycle.isin(CYCLES)

    demographics=pd.read_csv(ROOT/"data"/"processed"/"demographics"/"acs_direct_sld_demographics.csv")
    result=result.merge(demographics[["cycle","chamber","district","nonwhite_share","white_college_share"]],
                        on=["cycle","chamber","district"],how="left")
    context_2010_path=ROOT/"data"/"processed"/"demographics"/"2010_district_demographics.csv"
    if context_2010_path.exists():
        context_2010=pd.read_csv(context_2010_path)[
            ["cycle","chamber","district","nonwhite_share","white_college_share",
             "allocation_method","demographic_reference_year","demographic_age_years"]]
        result=result.merge(context_2010,on=["cycle","chamber","district"],how="left",
                            suffixes=("","_2010"),validate="one_to_one")
        mask_2010=result.cycle.eq(2010)&result.nonwhite_share_2010.notna()
        for column in ("nonwhite_share","white_college_share"):
            result.loc[mask_2010,column]=result.loc[mask_2010,f"{column}_2010"]
            result=result.drop(columns=f"{column}_2010")
        result.loc[mask_2010,"demographics_method"]=result.loc[mask_2010,"allocation_method"]
        result=result.drop(columns="allocation_method")
    finance=pd.read_csv(WAR/"race_finance_features.csv")
    result=result.merge(finance[["cycle","chamber","district","log_spending_ratio_d_to_r","finance_complete"]],
                        on=["cycle","chamber","district"],how="left")
    ftm_path=WAR/"ftm_race_finance_features.csv"
    if ftm_path.exists():
        ftm=pd.read_csv(ftm_path)
        result=result.merge(ftm[["cycle","chamber","district","log_fundraising_ratio_d_to_r","ftm_finance_complete"]],
                            on=["cycle","chamber","district"],how="left")
    pres=[]
    for cycle in (2014,2018,2022):
        p=pd.read_csv(ROOT/"data"/"processed"/"presidential"/f"{cycle}_district_presidential_features.csv").drop(columns="office",errors="ignore")
        pres.append(p)
    result=result.merge(pd.concat(pres,ignore_index=True,sort=False),on=["cycle","chamber","district"],how="left")
    result["finance_complete"]=result.finance_complete.fillna(False)
    if "ftm_finance_complete" not in result: result["ftm_finance_complete"]=False
    result["ftm_finance_complete"]=result.ftm_finance_complete.fillna(False)
    historical_context_path=ELECT/"1994_cmo_context_features.csv"
    if historical_context_path.exists():
        context=pd.read_csv(historical_context_path)
        context_columns=["cycle","chamber","district","nonwhite_share","college_share",
          "white_college_share","demographics_method","dem_incumbent","rep_incumbent",
          "pres_1992_dem_margin","pres_1992_fallback_share","pres_1992_source_complete"]
        result=result.merge(context[context_columns],on=["cycle","chamber","district"],how="left",
                            suffixes=("","_historical"),validate="one_to_one")
        for column in ("nonwhite_share","white_college_share"):
            result[column]=result[column].fillna(result.pop(f"{column}_historical"))
        historical_mask=result.cycle.eq(1994)&result.demographics_method.notna()
        result.loc[historical_mask,"dem_incumbent"]=nullable_bool(result.loc[historical_mask,"dem_incumbent_historical"]).fillna(False)
        result.loc[historical_mask,"rep_incumbent"]=nullable_bool(result.loc[historical_mask,"rep_incumbent_historical"]).fillna(False)
        result=result.drop(columns=["dem_incumbent_historical","rep_incumbent_historical"])
    extended_context_path=ELECT/"1998_2006_cmo_context_features.csv"
    if extended_context_path.exists():
        extended=pd.read_csv(extended_context_path)
        columns=["cycle","chamber","district","nonwhite_share","college_share","white_college_share",
                 "demographics_method","dem_incumbent","rep_incumbent","incumbency_complete","finance_complete",
                 "log_resource_ratio_d_to_r","prior_presidential_year","prior_pres_dem_margin",
                 "prior_pres_fallback_share","prior_pres_source_complete","readiness_status"]
        result=result.merge(extended[columns],on=["cycle","chamber","district"],how="left",
                            suffixes=("","_extended"),validate="one_to_one")
        method_source="demographics_method_extended" if "demographics_method_extended" in result else "demographics_method"
        extended_mask=result.cycle.isin([1998,2002,2006])&result[method_source].notna()
        if method_source!="demographics_method":
            result.loc[extended_mask,"demographics_method"]=result.loc[extended_mask,method_source]
            result=result.drop(columns=method_source)
        for column in ["nonwhite_share","white_college_share","finance_complete","log_resource_ratio_d_to_r"]:
            source=f"{column}_extended" if f"{column}_extended" in result else column
            if source!=column:
                result.loc[extended_mask,column]=result.loc[extended_mask,source]
                result=result.drop(columns=source)
        result.loc[extended_mask,"dem_incumbent"]=nullable_bool(result.loc[extended_mask,"dem_incumbent_extended"]).fillna(False)
        result.loc[extended_mask,"rep_incumbent"]=nullable_bool(result.loc[extended_mask,"rep_incumbent_extended"]).fillna(False)
        result=result.drop(columns=["dem_incumbent_extended","rep_incumbent_extended"])
    result.to_csv(ELECT/"canonical_cmo_features.csv",index=False)
    candidates.to_csv(ELECT/"canonical_cmo_candidates.csv",index=False)
    historical_races=result[result.historical_extension & result.war_eligible].copy()
    historical_candidates=candidates.merge(
        historical_races[["cycle","chamber","district","legislative_dem_margin","core_index_margin",
                          "raw_overperformance","baseline_allocation_method"]],
        left_on=["year","chamber","district"],right_on=["cycle","chamber","district"],
        how="inner",validate="many_to_one")
    historical_candidates["candidate_margin_overperformance"]=historical_candidates.raw_overperformance*np.where(
        historical_candidates.canonical_party.eq("D"),1,-1)
    historical_candidates["score_status"]=np.where(
        historical_candidates.cycle.eq(1994),"fitted_cmo_sensitivity_tier",
        "fitted_cmo_core_historical_tier")
    historical_candidates.to_csv(ELECT/"historical_cmo_extension.csv",index=False)
    print(result.groupby(["cycle","chamber"]).agg(races=("district","size"),eligible=("war_eligible","sum"),
          baseline_complete=("core_index_complete","sum"),nonwhite_available=("nonwhite_share",lambda x:x.notna().sum())).to_string())

if __name__=="__main__":main()
