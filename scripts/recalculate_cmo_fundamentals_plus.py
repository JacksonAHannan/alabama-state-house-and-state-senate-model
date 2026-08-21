"""Recalculate historical CMO with the full Fundamentals+ expectation.

The headline score is leave-one-cycle-out: each election cycle is scored by a
model trained on every other cycle. This is a retrospective descriptive CMO,
not a claim that 1994 could have been forecast with future election data.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, KFold

from run_forecast_experiment_tournament import cycle_balanced_weights, prepare_data
from run_next_forecast_tournaments import apply_canonical_historical_finance, feature_stages, pipeline

ROOT=Path(__file__).resolve().parents[1]
WAR=ROOT/"data"/"processed"/"war"
POLL=ROOT/"data"/"processed"/"polling"/"historical_silver_a_generic_ballot_cycles.csv"
SEED=20260817
SPEC="fundamentals_plus_cycle_holdout"


def panel() -> tuple[pd.DataFrame,list[str]]:
    data=apply_canonical_historical_finance(prepare_data().copy())
    polls=pd.read_csv(POLL)[["cycle","poll_implied_national_swing"]]
    data=data.merge(polls,on="cycle",how="left",validate="many_to_one")
    data["poll_transfer_weight"]=np.select(
        [data.cycle.ge(2022),data.cycle.ge(2018)],[1.0,.5],default=0.0)
    # Polling is not required before 2018 because the supported transfer is zero.
    data["poll_implied_national_swing"]=data.poll_implied_national_swing.fillna(0)
    statewide=pd.to_numeric(data.statewide_index_margin,errors="coerce")
    # Historical CMO measures performance relative to the same-cycle statewide
    # ticket.  The prospective forecast starts from presidential partisanship,
    # but importing that forecast baseline here double-counts district
    # partisanship and can manufacture enormous residuals in districts where
    # presidential and statewide candidates diverged.
    data["basic_baseline_source"]="same_cycle_statewide_index"
    data["basic_polling_baseline"]=statewide
    data["poll_swing_transferred"]=0.0
    data["poll_x_nonwhite"]=data.poll_swing_transferred*data.nonwhite_share
    data["poll_x_white_college"]=data.poll_swing_transferred*data.white_college_share
    data["chamber_house"]=data.chamber.eq("house").astype(int)

    regions=pd.read_csv(WAR/"next_forecast_tournament_region_features.csv")
    region_cols=sorted(c for c in regions if c.startswith("region_") and c.endswith("_share"))
    historical=regions[regions.cycle.ne(2026)]
    data=data.merge(historical,on=["cycle","chamber","district"],how="left",validate="one_to_one")
    data[region_cols]=data[region_cols].fillna(0)
    data["regional_features_available"]=data.regional_features_available.fillna(0)
    history=["dem_prior_recent","rep_prior_recent","dem_prior_winner","rep_prior_winner",
             "dem_prior_candidate_overperformance","rep_prior_candidate_overperformance"]
    data[history]=data[history].fillna(0)
    features=feature_stages(region_cols)["all_plus_candidate_history"]
    required=data[["legislative_dem_margin","basic_polling_baseline"]].notna().all(axis=1)
    if not required.all():
        missing=data.loc[~required,["cycle","chamber","district"]]
        raise ValueError(f"Fundamentals+ cannot score {len(missing)} races:\n{missing.to_string(index=False)}")
    return data.reset_index(drop=True),features


def predict_fold(data: pd.DataFrame,features: list[str],train_idx,test_idx) -> np.ndarray:
    train=data.iloc[train_idx]; test=data.iloc[test_idx]
    fit=pipeline(20.)
    target=train.legislative_dem_margin-train.basic_polling_baseline
    fit.fit(train[features],target,ridge__sample_weight=cycle_balanced_weights(train))
    adjustment=(.20*fit.predict(test[features])).clip(-4,4)
    return test.basic_polling_baseline.to_numpy()+adjustment


def cross_fitted(data: pd.DataFrame,features: list[str],folds) -> np.ndarray:
    result=np.full(len(data),np.nan)
    for train_idx,test_idx in folds:
        result[test_idx]=predict_fold(data,features,train_idx,test_idx)
    if np.isnan(result).any():
        raise ValueError("Cross-fitting left unscored races")
    return result


def score() -> tuple[pd.DataFrame,pd.DataFrame,float]:
    data,features=panel()
    cycles=data.cycle.to_numpy()
    cycle_folds=[(np.flatnonzero(cycles!=c),np.flatnonzero(cycles==c)) for c in sorted(set(cycles))]
    random_folds=KFold(10,shuffle=True,random_state=SEED).split(data)
    district_groups=data.chamber.astype(str)+"-"+data.district.astype(str)
    grouped_folds=GroupKFold(min(10,district_groups.nunique())).split(data,groups=district_groups)
    predictions={
        "cycle_holdout":cross_fitted(data,features,cycle_folds),
        "random_oof":cross_fitted(data,features,random_folds),
        "district_grouped":cross_fitted(data,features,grouped_folds),
    }
    all_idx=np.arange(len(data)); predictions["final"]=predict_fold(data,features,all_idx,all_idx)
    out=data[["cycle","chamber","district","legislative_dem_margin","statewide_index_margin",
              "basic_polling_baseline","basic_baseline_source","regional_features_available",
              "canonical_finance_complete","canonical_log_fundraising_ratio_d_to_r"]].copy()
    for method,pred in predictions.items():
        out[f"expected_legislative_dem_margin_{method}"]=pred
        out[f"cmo_{method}"]=out.legislative_dem_margin-pred
    instability=np.abs(out.cmo_cycle_holdout-out.cmo_random_oof)
    radius=float(np.quantile(instability,.95,method="higher"))
    out["cmo_stability_low"]=out.cmo_cycle_holdout-radius
    out["cmo_stability_high"]=out.cmo_cycle_holdout+radius
    diagnostics=(out.assign(absolute_error=lambda x:abs(x.legislative_dem_margin-x.expected_legislative_dem_margin_cycle_holdout))
                 .groupby(["cycle","chamber"],as_index=False)
                 .agg(races=("district","size"),mae=("absolute_error","mean"),
                      fallback_races=("basic_baseline_source",lambda x:(x=="same_cycle_statewide_fallback").sum()),
                      regional_coverage=("regional_features_available","mean")))
    return out,diagnostics,radius


def publish(scores: pd.DataFrame,radius: float) -> None:
    race_path=WAR/"preliminary_cmo_races.csv"; candidate_path=WAR/"preliminary_cmo_candidates.csv"
    races=pd.read_csv(race_path); candidates=pd.read_csv(candidate_path)
    keys=["cycle","chamber","district"]
    # This publisher is intentionally rerunnable.  Remove columns owned by the
    # Fundamentals+ scorer before merging so a prior run cannot shadow fresh
    # values with an unsuffixed, stale column.
    score_columns=[column for column in scores.columns if column not in keys]
    races=races.drop(columns=[column for column in score_columns if column in races.columns],errors="ignore")
    scored=races.merge(scores,on=keys,how="left",validate="one_to_one")
    if scored.cmo_cycle_holdout.isna().any():
        raise ValueError("Not every published CMO race received a Fundamentals+ score")
    scored["finance_complete"]=scored.canonical_finance_complete.fillna(0).astype(int)
    scored["ftm_finance_complete"]=scored.finance_complete
    scored["log_fundraising_ratio_d_to_r"]=scored.canonical_log_fundraising_ratio_d_to_r
    preserve=["cmo_total_oof","cmo_total_cycle_holdout","cmo_total_district_grouped","cmo_total_final",
              "expected_cmo_total_oof","expected_cmo_total_cycle_holdout","expected_cmo_total_district_grouped",
              "expected_cmo_total_final","cmo_total_stability_low","cmo_total_stability_high"]
    for column in preserve:
        legacy=f"legacy_{column}"
        if column in scored and legacy not in scored:
            scored[legacy]=scored[column]
    expected_raw={m:scored[f"expected_legislative_dem_margin_{m}"]-scored.statewide_index_margin
                  for m in ("cycle_holdout","random_oof","district_grouped","final")}
    # The generic OOF headline intentionally points to the stricter cycle holdout.
    scored["expected_cmo_total_oof"]=expected_raw["cycle_holdout"]
    scored["cmo_total_oof"]=scored.cmo_cycle_holdout
    scored["expected_cmo_total_cycle_holdout"]=expected_raw["cycle_holdout"]
    scored["cmo_total_cycle_holdout"]=scored.cmo_cycle_holdout
    scored["expected_cmo_total_district_grouped"]=expected_raw["district_grouped"]
    scored["cmo_total_district_grouped"]=scored.cmo_district_grouped
    scored["expected_cmo_total_final"]=expected_raw["final"]
    scored["cmo_total_final"]=scored.cmo_final
    scored["cmo_total_stability_low"]=scored.cmo_stability_low
    scored["cmo_total_stability_high"]=scored.cmo_stability_high
    scored["cmo_headline_specification"]=SPEC
    scored["expected_raw_overperformance_oof"]=scored.expected_cmo_total_oof
    scored["war_residual_oof"]=scored.cmo_total_oof
    scored["expected_raw_overperformance_loco"]=scored.expected_cmo_total_cycle_holdout
    scored["war_residual_loco"]=scored.cmo_total_cycle_holdout
    scored["expected_raw_overperformance_final"]=scored.expected_cmo_total_final
    scored["war_residual_final"]=scored.cmo_total_final

    candidate_keys=keys
    values=scored[candidate_keys+["cmo_total_oof","cmo_total_cycle_holdout","cmo_total_district_grouped",
                                   "cmo_total_final","cmo_total_stability_low","cmo_total_stability_high",
                                   "expected_cmo_total_oof","expected_cmo_total_cycle_holdout",
                                   "expected_cmo_total_district_grouped","expected_cmo_total_final"]]
    candidates=candidates.drop(columns=[c for c in values if c not in candidate_keys],errors="ignore").merge(
        values,on=candidate_keys,how="left",validate="many_to_one")
    sign=candidates.party.map({"D":1.0,"R":-1.0})
    for method in ("oof","cycle_holdout","district_grouped","final"):
        candidates[f"candidate_cmo_total_{method}"]=candidates[f"cmo_total_{method}"]*sign
    candidates["candidate_cmo_total_stability_low"]=np.where(
        sign.eq(1),candidates.cmo_total_stability_low,-candidates.cmo_total_stability_high)
    candidates["candidate_cmo_total_stability_high"]=np.where(
        sign.eq(1),candidates.cmo_total_stability_high,-candidates.cmo_total_stability_low)
    candidates["candidate_war_oof"]=candidates.candidate_cmo_total_oof
    candidates["candidate_war_final"]=candidates.candidate_cmo_total_final
    candidates["cmo_headline_specification"]=SPEC

    scored.to_csv(race_path,index=False); candidates.to_csv(candidate_path,index=False)
    scored.to_csv(WAR/"preliminary_war_races.csv",index=False)
    candidates.to_csv(WAR/"preliminary_war_candidates.csv",index=False)
    print(f"Published {len(scored)} races and {len(candidates)} candidate rows; stability radius {radius:.2f}")


def main() -> None:
    scores,diagnostics,radius=score()
    scores.to_csv(WAR/"fundamentals_plus_cmo_races.csv",index=False)
    diagnostics.to_csv(WAR/"fundamentals_plus_cmo_diagnostics.csv",index=False)
    publish(scores,radius)
    print(diagnostics.to_string(index=False))


if __name__=="__main__": main()
