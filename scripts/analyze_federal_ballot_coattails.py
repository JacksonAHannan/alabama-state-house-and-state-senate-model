"""Test partisan federal-ballot coattails in Alabama legislative elections.

The estimand is the change in Democratic legislative margin, relative to the
post-2016 national-environment ramp, associated with exposure to a U.S. House
race containing only a Democrat or only a Republican. Contested D-R House
races are the reference. Same-cycle ballot status is known before Election Day,
so the feature is forecast-eligible; federal vote margins are not used.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from build_historical_federal_baselines import (CYCLES,ELECT,allocate_cycle,
                                                  load_observations)
from fit_2026_prospective_model import historical

OUT=ELECT/"validation"


def house_ballot_exposure()->pd.DataFrame:
    source=load_observations()
    totals=(source.groupby(["year","contest","party_norm"],as_index=False).votes.sum()
            .pivot(index=["year","contest"],columns="party_norm",values="votes")
            .fillna(0).reset_index())
    for party in ("D","R"):
        if party not in totals: totals[party]=0
    totals["ballot_status"]=np.select(
        [totals.D.gt(0)&totals.R.gt(0),totals.D.gt(0)&totals.R.eq(0),
         totals.R.gt(0)&totals.D.eq(0)],
        ["contested","democratic_only","republican_only"],default="other")
    modern=pd.read_csv(ELECT/"canonical_precinct_district_weights.csv")
    parts=[]
    for cycle in CYCLES:
        for chamber in ("house","senate"):
            allocated=allocate_cycle(source,cycle,chamber,modern)
            allocated=allocated[allocated.federal_office.eq("us_house")].copy()
            if allocated.empty: continue
            allocated["cycle"]=cycle;allocated["chamber"]=chamber
            allocated["allocated_votes"]=allocated.votes*allocated.allocation_weight
            allocated=allocated.merge(totals[["year","contest","ballot_status"]],
                                      on=["year","contest"],validate="many_to_one")
            grouped=(allocated.groupby(["cycle","chamber","district","ballot_status"],as_index=False)
                     .allocated_votes.sum().pivot(index=["cycle","chamber","district"],
                     columns="ballot_status",values="allocated_votes").fillna(0).reset_index())
            for column in ("contested","democratic_only","republican_only"):
                if column not in grouped: grouped[column]=0.0
            grouped["house_ballot_votes"]=grouped[
                ["contested","democratic_only","republican_only"]].sum(axis=1)
            grouped["house_contested_exposure"]=grouped.contested/grouped.house_ballot_votes
            grouped["house_democratic_only_exposure"]=grouped.democratic_only/grouped.house_ballot_votes
            grouped["house_republican_only_exposure"]=grouped.republican_only/grouped.house_ballot_votes
            parts.append(grouped)
    return pd.concat(parts,ignore_index=True)


def design(frame:pd.DataFrame,adjusted:bool)->tuple[np.ndarray,list[str]]:
    pieces=[pd.Series(1.0,index=frame.index,name="intercept"),
            frame.house_democratic_only_exposure,
            frame.house_republican_only_exposure,
            pd.get_dummies(frame.cycle,prefix="cycle",drop_first=True,dtype=float),
            frame.chamber.eq("senate").astype(float).rename("senate")]
    if adjusted:
        for column in ("prior_pres_dem_margin","nonwhite_share","white_college_share",
                       "dem_incumbent_i","rep_incumbent_i"):
            values=pd.to_numeric(frame[column],errors="coerce")
            pieces.append(values.fillna(values.median()).rename(column))
    matrix=pd.concat(pieces,axis=1)
    return matrix.to_numpy(float),matrix.columns.tolist()


def clustered_ols(frame:pd.DataFrame,adjusted:bool)->pd.DataFrame:
    x,names=design(frame,adjusted);y=frame.coattail_outcome.to_numpy(float)
    inverse=np.linalg.pinv(x.T@x);beta=inverse@x.T@y;residual=y-x@beta
    meat=np.zeros((x.shape[1],x.shape[1]))
    for cycle in frame.cycle.unique():
        use=frame.cycle.eq(cycle).to_numpy();score=x[use].T@residual[use]
        meat+=np.outer(score,score)
    clusters=frame.cycle.nunique();n=len(frame);k=x.shape[1]
    correction=(clusters/(clusters-1))*((n-1)/(n-k))
    se=np.sqrt(np.diag(correction*inverse@meat@inverse))
    rows=[]
    for variable in ("house_democratic_only_exposure","house_republican_only_exposure"):
        idx=names.index(variable);estimate=beta[idx];stderr=se[idx]
        rows.append({"model":"adjusted" if adjusted else "cycle_chamber_fixed_effects",
          "variable":variable,"party_benefited":"D" if "democratic" in variable else "R",
          "dem_margin_effect":estimate,"party_margin_benefit":estimate if "democratic" in variable else -estimate,
          "clustered_standard_error":stderr,"ci95_low":estimate-1.96*stderr,
          "ci95_high":estimate+1.96*stderr,"cycles":clusters,"races":n})
    return pd.DataFrame(rows)


def forward_validation(frame:pd.DataFrame)->pd.DataFrame:
    rows=[];features=["house_democratic_only_exposure","house_republican_only_exposure"]
    for cycle in sorted(frame.cycle.unique())[1:]:
        train=frame[frame.cycle.lt(cycle)].copy();test=frame[frame.cycle.eq(cycle)].copy()
        counts=train.cycle.value_counts();weights=train.cycle.map(lambda x:1/counts.loc[x]).to_numpy()
        predictions={"post2016_ramp":test.national_environment_ramp_baseline.to_numpy()}
        xtrain=pd.concat([train[features],train.chamber.eq("senate").astype(float).rename("senate")],axis=1)
        xtest=pd.concat([test[features],test.chamber.eq("senate").astype(float).rename("senate")],axis=1)
        model=Ridge(alpha=20.0).fit(xtrain,train.coattail_outcome,sample_weight=weights)
        predictions["ramp_plus_partisan_house_coattails"]=(
            test.national_environment_ramp_baseline.to_numpy()+model.predict(xtest))
        for name,prediction in predictions.items():
            rows.append({"test_cycle":cycle,"specification":name,"races":len(test),
                         "mae":mean_absolute_error(test.legislative_dem_margin,prediction)})
    result=pd.DataFrame(rows)
    means=result.groupby("specification",as_index=False).mae.mean().rename(columns={"mae":"cycle_balanced_mean_mae"})
    return result.merge(means,on="specification",how="left")


def main()->None:
    exposure=house_ballot_exposure()
    data=(historical().merge(exposure,on=["cycle","chamber","district"],how="inner",validate="one_to_one")
          .dropna(subset=["house_democratic_only_exposure","house_republican_only_exposure",
                         "national_environment_ramp_baseline","legislative_dem_margin"])
          .reset_index(drop=True))
    data["coattail_outcome"]=data.legislative_dem_margin-data.national_environment_ramp_baseline
    estimates=pd.concat([clustered_ols(data,False),clustered_ols(data,True)],ignore_index=True)
    forward=forward_validation(data)
    exposure.to_csv(OUT/"federal_house_ballot_coattail_exposure.csv",index=False)
    estimates.to_csv(OUT/"federal_house_ballot_coattail_estimates.csv",index=False)
    forward.to_csv(OUT/"federal_house_ballot_coattail_forward_validation.csv",index=False)
    print(estimates.to_string(index=False))
    print("\nForward validation")
    print(forward.pivot(index="test_cycle",columns="specification",values="mae").to_string())
    print("\nCycle-balanced means")
    print(forward[["specification","cycle_balanced_mean_mae"]].drop_duplicates().to_string(index=False))


if __name__=="__main__":main()
