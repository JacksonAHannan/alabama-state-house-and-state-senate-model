"""Run retrospective and forecast-eligible top-of-ticket experiments.

Same-cycle gubernatorial returns are explicitly labeled retrospective because
they are unavailable when a forecast is published.  The Jones/Tuberville
geographic scenarios use their 2020 head-to-head residual as a candidate-pair
prior and therefore remain sensitivity tests, not fitted forecasts.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fit_2026_prospective_model import historical

ELECT = ROOT / "data" / "processed" / "elections"
OUT = ELECT / "validation"


def governor_experiments() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    h = historical()
    b = pd.read_csv(ELECT / "canonical_cmo_district_office_baselines.csv")
    g = b[b.office.eq("Governor")][["cycle", "chamber", "district", "D", "R", "office_margin"]].copy()
    g["district"] = g.district.astype(int)
    x = h.merge(g, on=["cycle", "chamber", "district"], how="inner")
    x = x[x.cycle.isin([2014, 2018, 2022]) & x.D.gt(0) & x.R.gt(0)].copy()
    x["governor_residual"] = x.office_margin - x.prior_pres_dem_margin
    x["legislative_residual"] = x.legislative_dem_margin - x.national_environment_ramp_baseline
    x = x.dropna(subset=["governor_residual", "legislative_residual",
                         "legislative_dem_margin", "national_environment_ramp_baseline"]).copy()
    x["dem_retention"] = x.dem_votes / x.D
    x["rep_retention"] = x.rep_votes / x.R
    x["open_seat"] = ((x.dem_incumbent_i == 0) & (x.rep_incumbent_i == 0)).astype(int)

    desc = (x.groupby(["cycle", "open_seat"], as_index=False)
            .agg(races=("district", "size"), governor_residual=("governor_residual", "mean"),
                 legislative_residual=("legislative_residual", "mean"),
                 dem_retention=("dem_retention", "median"), rep_retention=("rep_retention", "median")))

    rows = []
    feature_sets = {
        "ramp": [], "ramp_plus_governor": ["governor_residual"],
        "governor_demographics": ["governor_residual", "gov_x_nonwhite", "gov_x_college"],
        "governor_candidate_context": ["governor_residual", "gov_x_open", "gov_x_dem_inc", "gov_x_rep_inc"],
        "governor_all_interactions": ["governor_residual", "gov_x_nonwhite", "gov_x_college",
                                      "gov_x_open", "gov_x_dem_inc", "gov_x_rep_inc"],
    }
    x["gov_x_nonwhite"] = x.governor_residual * x.nonwhite_share
    x["gov_x_college"] = x.governor_residual * x.white_college_share
    x["gov_x_open"] = x.governor_residual * x.open_seat
    x["gov_x_dem_inc"] = x.governor_residual * x.dem_incumbent_i
    x["gov_x_rep_inc"] = x.governor_residual * x.rep_incumbent_i
    model_columns = sorted({column for columns in feature_sets.values() for column in columns})
    for column in model_columns:
        x[column] = x[column].fillna(x[column].median())
    for cycle in [2018, 2022]:
        train, test = x[x.cycle < cycle], x[x.cycle == cycle]
        for name, features in feature_sets.items():
            pred = test.national_environment_ramp_baseline.to_numpy()
            if features:
                counts = train.cycle.value_counts()
                weights = train.cycle.map(lambda z: 1 / counts.loc[z])
                model = Ridge(alpha=20).fit(train[features], train.legislative_residual, sample_weight=weights)
                pred = pred + model.predict(test[features])
            rows.append({"test_cycle": cycle, "specification": name, "races": len(test),
                         "mae": mean_absolute_error(test.legislative_dem_margin, pred)})
    validation = pd.DataFrame(rows)
    validation["mean_mae"] = validation.groupby("specification").mae.transform("mean")

    effects = []
    for subset, part in [("all", x), ("open", x[x.open_seat.eq(1)]), ("incumbent_present", x[x.open_seat.eq(0)])]:
        if len(part) < 5:
            continue
        slope = np.polyfit(part.governor_residual, part.legislative_residual, 1)[0]
        effects.append({"subset": subset, "races": len(part), "transfer_slope": slope,
                        "correlation": part.governor_residual.corr(part.legislative_residual)})
    return x, desc, validation.merge(pd.DataFrame(effects), how="cross")


def jones_tuberville_scenarios() -> tuple[pd.DataFrame, pd.DataFrame]:
    db = sqlite3.connect(ELECT / "alabama_elections.sqlite")
    q = """select county_key,precinct_key,office,candidate,party_norm,sum(votes) votes
           from vote_observations where year=2020 and source='alabama_sos'
           and ((office='President' and candidate like 'Joseph R. Biden%')
             or (office='President' and candidate like 'Donald J. Trump%')
             or (office='UNITED STATES SENATOR' and trim(candidate) in ('Doug Jones','Tommy Tuberville')))
           group by county_key,precinct_key,office,candidate,party_norm"""
    v = pd.read_sql_query(q, db)
    v["race"] = np.where(v.office.eq("President"), "president", "senate")
    p = v.pivot_table(index=["county_key", "precinct_key"], columns=["race", "party_norm"],
                      values="votes", aggfunc="sum", fill_value=0)
    p.columns = [f"{a}_{b}" for a, b in p.columns]
    p = p.reset_index()
    for race in ["president", "senate"]:
        total = p[f"{race}_D"] + p[f"{race}_R"]
        p[f"{race}_margin"] = 100 * (p[f"{race}_D"] - p[f"{race}_R"]) / total.replace(0, np.nan)
    p["pair_residual"] = p.senate_margin - p.president_margin
    p["pair_votes"] = p.senate_D + p.senate_R

    w = pd.read_csv(ROOT / "data" / "processed" / "war" / "2026_geographic_precinct_district_weights.csv")
    for col in ["county_key", "precinct_key"]:
        w[col] = w[col].astype(str).str.upper().str.strip()
        p[col] = p[col].astype(str).str.upper().str.strip()
    m = w.merge(p, on=["county_key", "precinct_key"], how="inner")
    m["mass"] = m.allocation_weight * m.pair_votes
    d = (m.groupby(["chamber", "district"])
         .apply(lambda z: np.average(z.pair_residual, weights=z.mass), include_groups=False)
         .rename("local_pair_residual").reset_index())
    state = np.average(p.pair_residual.dropna(), weights=p.loc[p.pair_residual.notna(), "pair_votes"])
    d["statewide_pair_residual"] = state
    d["centered_geographic_residual"] = d.local_pair_residual - state

    forecast_path = ROOT / "data" / "processed" / "war" / "2026_prospective_features_and_forecast_legacy_core_20260815.csv"
    f = pd.read_csv(forecast_path)[["chamber", "district", "predicted_dem_margin"]]
    scenarios = f.merge(d, on=["chamber", "district"], how="left")
    for rate in [0.20, 0.42, 0.60]:
        tag = str(rate).replace(".", "_")
        scenarios[f"pair_effect_{tag}"] = rate * scenarios.local_pair_residual
        scenarios[f"scenario_margin_{tag}"] = scenarios.predicted_dem_margin + scenarios[f"pair_effect_{tag}"]
        scenarios[f"winner_change_{tag}"] = ((scenarios.predicted_dem_margin >= 0) != (scenarios[f"scenario_margin_{tag}"] >= 0))
    summary = pd.DataFrame([{
        "transfer_rate": rate,
        "mean_dem_margin_change": scenarios[f"pair_effect_{str(rate).replace('.', '_')}"] .mean(),
        "max_abs_district_change": scenarios[f"pair_effect_{str(rate).replace('.', '_')}"] .abs().max(),
        "winner_changes": int(scenarios[f"winner_change_{str(rate).replace('.', '_')}"] .sum()),
    } for rate in [0.20, 0.42, 0.60]])
    return scenarios, summary


def main() -> None:
    detail, desc, validation = governor_experiments()
    scenarios, summary = jones_tuberville_scenarios()
    detail.to_csv(OUT / "governor_coattail_detail.csv", index=False)
    desc.to_csv(OUT / "governor_turnout_retention_summary.csv", index=False)
    validation.to_csv(OUT / "governor_coattail_forward_validation.csv", index=False)
    scenarios.to_csv(OUT / "2026_jones_tuberville_geographic_scenarios.csv", index=False)
    summary.to_csv(OUT / "2026_jones_tuberville_scenario_summary.csv", index=False)
    print("Governor validation\n", validation[["test_cycle", "specification", "mae", "mean_mae"]].drop_duplicates().to_string(index=False))
    transfer_columns = [column for column in ["subset", "races_y", "transfer_slope", "correlation"] if column in validation]
    print("\nTransfer diagnostics\n", validation[transfer_columns].drop_duplicates().to_string(index=False))
    print("\nJones/Tuberville scenarios\n", summary.to_string(index=False))


if __name__ == "__main__":
    main()
