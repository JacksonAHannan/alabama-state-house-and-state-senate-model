"""Fit regularized race x education turnout/preference ecological models."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar

from build_alabama_race_ei import vest_statewide_returns

ROOT = Path(__file__).resolve().parents[1]
POLLING = ROOT / "data" / "processed" / "polling"
CELLS = [f"{race}_{education}" for race in ["white_nh", "black", "other"]
         for education in ["noncollege", "college"]]
CATALIST_GROUPS = {
    "white_nh_noncollege": "White Non-College", "white_nh_college": "White College",
    "black_noncollege": "Black Non-College", "black_college": "Black College",
    "other_noncollege": "Other Non-College", "other_college": "Other College",
}


def expit(values: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-values))


def logit(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, 1e-6, 1-1e-6)
    return np.log(values / (1-values))


def catalist_prior(cycle: int, population: np.ndarray, observed_dem_share: float) -> np.ndarray:
    election = "us_house" if cycle == 2018 else "president"
    master = pd.read_csv(POLLING / "catalist_national_demographic_master.csv")
    selected = master[(master.year == cycle) & (master.election_type == election)
                      & (master.metric == "dem_two_party_share_pct")]
    lookup = selected.set_index("group").value.to_dict()
    national = np.array([lookup[CATALIST_GROUPS[cell]] / 100 for cell in CELLS])
    shares = population.sum(axis=0); shares /= shares.sum()
    target = float(observed_dem_share)
    objective = lambda shift: abs(float(shares @ expit(logit(national) + shift)) - target)
    shift = minimize_scalar(objective, bounds=(-3, 3), method="bounded").x
    return expit(logit(national) + shift)


def fit_model(frame: pd.DataFrame, support_prior: np.ndarray, prior_strength: float) -> dict:
    population = frame[CELLS].to_numpy(float)
    dem = frame.dem_votes.to_numpy(float); rep = frame.rep_votes.to_numpy(float)
    statewide_turnout = np.clip((dem.sum()+rep.sum()) / population.sum(), .05, .95)

    def objective(parameters: np.ndarray) -> float:
        turnout, support = expit(parameters[:6]), expit(parameters[6:])
        expected_dem = np.clip(population @ (turnout*support), 1e-9, None)
        expected_rep = np.clip(population @ (turnout*(1-support)), 1e-9, None)
        nll = np.sum(expected_dem-dem*np.log(expected_dem) + expected_rep-rep*np.log(expected_rep))
        support_penalty = -prior_strength*np.sum(
            support_prior*np.log(support) + (1-support_prior)*np.log(1-support))
        # Aggregate returns weakly identify twelve separate turnout/preference
        # parameters. Strong hierarchical pooling prevents a small group from
        # being assigned near-zero turnout merely to reconcile precinct totals.
        turnout_center = logit(np.array([statewide_turnout]))[0]
        turnout_penalty = 5000/2*np.sum((parameters[:6]-turnout_center)**2)
        return float(nll + support_penalty + turnout_penalty)

    initial = np.r_[np.repeat(logit(np.array([statewide_turnout]))[0], 6), logit(support_prior)]
    result = minimize(objective, initial, method="L-BFGS-B", options={"maxiter": 2000})
    turnout, support = expit(result.x[:6]), expit(result.x[6:])
    expected_dem = population @ (turnout*support); expected_rep = population @ (turnout*(1-support))
    valid = (dem+rep)>0
    actual_share = dem[valid]/(dem[valid]+rep[valid])
    predicted_share = expected_dem[valid]/(expected_dem[valid]+expected_rep[valid])
    return {"turnout": turnout, "support": support, "success": result.success,
            "precinct_mae": float(np.average(abs(predicted_share-actual_share), weights=(dem+rep)[valid])),
            "state_dem_error": float((expected_dem.sum()/(expected_dem.sum()+expected_rep.sum()))
                                     - dem.sum()/(dem.sum()+rep.sum())),
            "vote_total_error_pct": float((expected_dem.sum()+expected_rep.sum()-dem.sum()-rep.sum())
                                          /(dem.sum()+rep.sum()))}


def main() -> None:
    demographics = pd.read_csv(POLLING / "vest_precinct_joint_race_education.csv")
    votes = vest_statewide_returns()
    rows=[]
    for cycle in [2018,2020]:
        demo = demographics[(demographics.cycle==cycle)&(demographics.acs_vintage==2022)].sort_values("precinct_id")
        election = votes[votes.cycle==cycle].reset_index(drop=True).reset_index(names="precinct_id")
        frame=election.merge(demo[["precinct_id",*CELLS]],on="precinct_id",validate="one_to_one")
        observed=frame.dem_votes.sum()/(frame.dem_votes.sum()+frame.rep_votes.sum())
        prior=catalist_prior(cycle,frame[CELLS].to_numpy(float),observed)
        for strength in [25.,100.,400.,1600.]:
            fit=fit_model(frame,prior,strength)
            for i,cell in enumerate(CELLS):
                rows.append({"cycle":cycle,"acs_vintage":2022,"cell":cell,"prior_strength":strength,
                             "catalist_shifted_prior":prior[i],"estimated_dem_support":fit['support'][i],
                             "estimated_turnout":fit['turnout'][i],"optimizer_success":fit['success'],
                             "precinct_weighted_mae":fit['precinct_mae'],"state_dem_share_error":fit['state_dem_error'],
                             "vote_total_error_pct":fit['vote_total_error_pct']})
    result=pd.DataFrame(rows)
    stability=result.groupby(["cycle","cell"]).estimated_dem_support.agg(["min","max"]).reset_index()
    stability["prior_sensitivity_range"]=stability["max"]-stability["min"]
    result=result.merge(stability[["cycle","cell","prior_sensitivity_range"]],on=["cycle","cell"])
    result["boundary_solution"]=(result.estimated_dem_support<.02)|(result.estimated_dem_support>.98)
    result["release_eligible"]=(~result.boundary_solution)&(result.prior_sensitivity_range<.10)
    result.to_csv(POLLING / "alabama_joint_race_education_ei_sensitivity.csv",index=False)
    preferred=result[result.prior_strength==400].copy()
    preferred.to_csv(POLLING / "alabama_joint_race_education_ei_estimates.csv",index=False)
    print(preferred[["cycle","cell","estimated_dem_support","estimated_turnout",
                     "prior_sensitivity_range","boundary_solution","precinct_weighted_mae"]].to_string(index=False))


if __name__ == "__main__": main()
