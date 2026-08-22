"""Build a Split Ticket-style WAR analogue for Alabama legislative races.

The modeled outcome is legislative margin minus the same-cycle federal margin.
CMO is the remaining residual after structural incumbency and down-ballot-lag
effects, with tightly constrained demographic and campaign-effort controls.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import rebuild_cmo_methodology_v2 as v2

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
REPORT = ROOT / "project_docs" / "model" / "CMO_METHODOLOGY_V4.md"
KEYS = ["cycle", "chamber", "district"]
ALPHAS = [3.0, 10.0, 30.0, 100.0]


def prepare() -> tuple[pd.DataFrame, pd.DataFrame]:
    races, candidates = v2.load_panel()
    data = v2.prepare_features(v2.attach_candidate_history(v2.build_source_aware_baseline(races), candidates))
    data["federal_primary"] = data.federal_available_v2.eq(1) & data.federal_index_margin.notna()
    data["war_baseline_margin"] = data.federal_index_margin.where(
        data.federal_primary, data.baseline_state_margin_v2)
    data["war_baseline_source"] = np.where(
        data.federal_primary, "same_cycle_federal", "same_cycle_state_fallback")
    data["raw_ticket_gap"] = data.legislative_dem_margin - data.war_baseline_margin
    data["downballot_lag"] = data.federal_index_margin - data.prior_pres_dem_margin_v2
    data.loc[~data.federal_primary, "downballot_lag"] = np.nan
    data["prior_pres_margin"] = data.prior_pres_dem_margin_v2

    data["presidential_swing"] = np.select(
        [data.cycle.eq(2014), data.cycle.eq(2018), data.cycle.eq(2022)],
        [data.pres_2012_dem_margin - data.pres_2008_dem_margin,
         data.pres_2016_dem_margin - data.pres_2012_dem_margin,
         data.pres_2020_dem_margin - data.pres_2016_dem_margin], default=np.nan)
    data["campaign_effort_ratio"] = (
        pd.to_numeric(data.log_spending_ratio_d_to_r, errors="coerce")
        .fillna(pd.to_numeric(data.log_fundraising_ratio_d_to_r, errors="coerce"))
        .fillna(pd.to_numeric(data.log_resource_ratio_d_to_r, errors="coerce")))
    data["campaign_effort_available"] = data.campaign_effort_ratio.notna().astype(int)
    data["campaign_effort_ratio"] = data.campaign_effort_ratio.clip(-3, 3)

    data["era"] = np.select(
        [data.cycle.le(2006), data.cycle.le(2014)],
        ["pre_2008", "2008_2014"], default="post_2016")
    for era in ["pre_2008", "2008_2014", "post_2016"]:
        flag = data.era.eq(era).astype(float)
        # A single party-oriented incumbency effect prevents the model from
        # rebranding the selected strength of surviving Democratic incumbents
        # as a uniquely Democratic incumbency entitlement.
        data[f"inc_adv_{era}"] = (data.dem_incumbent_i - data.rep_incumbent_i) * flag
        data[f"lag_{era}"] = data.downballot_lag * flag
    return data, candidates


MAIN = [
    "inc_adv_pre_2008", "inc_adv_2008_2014", "inc_adv_post_2016",
    "prior_pres_margin", "presidential_swing",
    "lag_pre_2008", "lag_2008_2014", "lag_post_2016",
]
MINOR = ["nonwhite_share", "white_college_share", "campaign_effort_ratio",
         "campaign_effort_available"]
# A free cycle fixed effect would absorb the statewide prevalence of unusually
# strong Alabama Democrats and then subtract it from every candidate. Split
# Ticket's national cycle model does not grant an Alabama-specific cycle mean;
# structural overperformance must instead be explained by the declared Jain
# factors. Chamber is retained, while era variation enters through explicit
# incumbency and lag interactions above.
CATEGORICAL = ["chamber"]


def pipeline(alpha: float, include_minor: bool) -> Pipeline:
    numeric = MAIN + (MINOR if include_minor else [])
    prep = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                           ("scale", StandardScaler())]), numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), CATEGORICAL),
    ])
    return Pipeline([("prep", prep), ("ridge", Ridge(alpha=alpha))])


def tournament(data: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    fit_data = data[data.federal_primary & data.headline_fit_eligible].copy()
    rows = []
    for include_minor in [False, True]:
        for alpha in ALPHAS:
            fold = []
            for cycle in sorted(fit_data.cycle.unique()):
                train, test = fit_data[fit_data.cycle.ne(cycle)], fit_data[fit_data.cycle.eq(cycle)]
                model = pipeline(alpha, include_minor)
                features = MAIN + (MINOR if include_minor else []) + CATEGORICAL
                model.fit(train[features], train.raw_ticket_gap)
                pred = model.predict(test[features])
                fold.append({"test_cycle": cycle, "races": len(test),
                             "mae": mean_absolute_error(test.raw_ticket_gap, pred),
                             "rmse": mean_squared_error(test.raw_ticket_gap, pred) ** .5})
            frame = pd.DataFrame(fold)
            rows.append({"specification": "full" if include_minor else "barebones",
                         "alpha": alpha, "cycles": len(frame), "races": int(frame.races.sum()),
                         "mean_cycle_mae": frame.mae.mean(), "mean_cycle_rmse": frame.rmse.mean(),
                         "latest_cycle_mae": frame.loc[frame.test_cycle.eq(frame.test_cycle.max()), "mae"].iloc[0]})
    results = pd.DataFrame(rows)
    # Select regularization on the barebones structural model. Minor controls
    # are added later under explicit contribution caps rather than promoted for
    # a marginal in-sample gain.
    bare = results[results.specification.eq("barebones")]
    alpha = float(bare.sort_values(["mean_cycle_mae", "latest_cycle_mae"]).iloc[0].alpha)
    return results, alpha


def fit_components(data: pd.DataFrame, alpha: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    fit_data = data[data.federal_primary & data.headline_fit_eligible].copy()
    # Fit the primary structural model.
    main_model = pipeline(alpha, False)
    main_features = MAIN + CATEGORICAL
    main_model.fit(fit_data[main_features], fit_data.raw_ticket_gap)
    main_pred = main_model.predict(data[main_features])
    inc_cols = [c for c in MAIN if c.startswith("inc_adv_")]
    lag_cols = [c for c in MAIN if c.startswith("lag_") or c in {"prior_pres_margin", "presidential_swing"}]
    neutral_inc = data[main_features].copy()
    neutral_inc[inc_cols] = 0.0
    neutral_lag = data[main_features].copy()
    for col in lag_cols:
        neutral_lag[col] = pd.to_numeric(fit_data[col], errors="coerce").median()
    incumbency_component = main_pred - main_model.predict(neutral_inc)
    lag_component = main_pred - main_model.predict(neutral_lag)

    # Minor controls explain only remaining training residual and are strongly
    # regularized. Demographic and effort contributions are capped to match the
    # deliberately small role described in Split Ticket's methodology.
    fit_residual = fit_data.raw_ticket_gap - main_model.predict(fit_data[main_features])
    minor_prep = ColumnTransformer([
        ("demo", Pipeline([("impute", SimpleImputer(strategy="median")),
                            ("scale", StandardScaler())]), ["nonwhite_share", "white_college_share"]),
        ("effort", Pipeline([("impute", SimpleImputer(strategy="constant", fill_value=0)),
                              ("scale", StandardScaler())]), ["campaign_effort_ratio", "campaign_effort_available"]),
    ])
    transformed = minor_prep.fit_transform(fit_data[MINOR])
    minor_fit = Ridge(alpha=max(100.0, alpha * 10)).fit(transformed, fit_residual)
    all_transformed = minor_prep.transform(data[MINOR])
    demo_raw = minor_fit.intercept_ + all_transformed[:, :2] @ minor_fit.coef_[:2]
    effort_raw = all_transformed[:, 2:] @ minor_fit.coef_[2:]
    data = data.copy()
    data["structural_expected_gap"] = main_pred
    data["incumbency_adjustment"] = incumbency_component
    data["lagged_partisanship_adjustment"] = lag_component
    data["structural_base_adjustment"] = main_pred - incumbency_component - lag_component
    data["demographic_adjustment"] = np.clip(demo_raw, -3, 3)
    data["campaign_effort_adjustment"] = np.clip(effort_raw, -2, 2)
    data["predicted_structural_gap"] = (
        data.structural_expected_gap + data.demographic_adjustment + data.campaign_effort_adjustment)
    data["war_cmo"] = data.raw_ticket_gap - data.predicted_structural_gap
    names = main_model.named_steps["prep"].get_feature_names_out()
    coefficients = pd.DataFrame({"feature": names,
                                 "coefficient": main_model.named_steps["ridge"].coef_})
    coefficients = pd.concat([pd.DataFrame([{"feature": "intercept",
                                              "coefficient": main_model.named_steps["ridge"].intercept_}]),
                              coefficients], ignore_index=True)
    return data, coefficients


def candidate_output(data: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    cols = KEYS + ["raw_ticket_gap", "predicted_structural_gap", "structural_expected_gap",
                   "structural_base_adjustment", "incumbency_adjustment", "lagged_partisanship_adjustment",
                   "demographic_adjustment", "campaign_effort_adjustment", "war_cmo",
                   "war_baseline_margin", "war_baseline_source", "federal_primary", "contest_tier"]
    out = candidates.merge(data[cols], on=KEYS, how="inner", validate="many_to_one")
    sign = out.canonical_party.map({"D": 1.0, "R": -1.0})
    for col in ["raw_ticket_gap", "predicted_structural_gap", "structural_expected_gap",
                "structural_base_adjustment", "incumbency_adjustment", "lagged_partisanship_adjustment",
                "demographic_adjustment", "campaign_effort_adjustment", "war_cmo",
                "war_baseline_margin"]:
        out[f"candidate_{col}"] = out[col] * sign
    career = (out.groupby("candidate_effect_id").candidate_war_cmo
              .agg([("career_war_mean", "mean"), ("appearances", "size")]).reset_index())
    career["career_reliability"] = career.appearances / (career.appearances + 2)
    career["career_war_partial_pooled"] = career.career_war_mean * career.career_reliability
    return out.merge(career, on="candidate_effect_id", how="left", validate="many_to_one")


def build() -> None:
    data, candidates = prepare()
    results, alpha = tournament(data)
    scored, coefficients = fit_components(data, alpha)
    candidate = candidate_output(scored, candidates)

    race_cols = KEYS + ["dem_votes", "rep_votes", "two_party_votes", "legislative_dem_margin",
        "war_baseline_margin", "war_baseline_source", "federal_primary", "raw_ticket_gap",
        "structural_expected_gap", "structural_base_adjustment", "incumbency_adjustment",
        "lagged_partisanship_adjustment", "demographic_adjustment", "campaign_effort_adjustment",
        "predicted_structural_gap", "war_cmo", "dem_incumbent_i", "rep_incumbent_i",
        "prior_pres_margin", "downballot_lag", "presidential_swing", "nonwhite_share",
        "white_college_share", "campaign_effort_ratio", "campaign_effort_available", "era", "contest_tier"]
    races = scored[race_cols].copy()
    components = races[KEYS + ["raw_ticket_gap", "structural_base_adjustment",
        "incumbency_adjustment", "lagged_partisanship_adjustment", "structural_expected_gap",
        "demographic_adjustment", "campaign_effort_adjustment", "predicted_structural_gap", "war_cmo"]]

    races.to_csv(WAR / "cmo_v4_races.csv", index=False)
    candidate.to_csv(WAR / "cmo_v4_candidates.csv", index=False)
    components.to_csv(WAR / "cmo_v4_components.csv", index=False)
    results.to_csv(WAR / "cmo_v4_model_tournament.csv", index=False)
    coefficients.to_csv(WAR / "cmo_v4_coefficients.csv", index=False)

    longitudinal = candidate[
        candidate.identity_status.ne("surname_only_unresolved_race_specific")
    ].sort_values(["candidate_effect_id", "cycle"]).copy()
    grouped = longitudinal.groupby("candidate_effect_id", sort=False)
    longitudinal["prior_cycle"] = grouped.cycle.shift(1)
    longitudinal["prior_candidate_war"] = grouped.candidate_war_cmo.shift(1)
    repeat = longitudinal[longitudinal.prior_cycle.eq(longitudinal.cycle - 4)]
    validity_rows = []
    for outcome in ["candidate_war_cmo", "candidate_raw_ticket_gap"]:
        stat = v2.safe_correlation(repeat.prior_candidate_war, repeat[outcome])
        validity_rows.append({"design": "repeat_candidate_next_cycle", "outcome": outcome, **stat})
    validity = pd.DataFrame(validity_rows)
    validity.to_csv(WAR / "cmo_v4_construct_validity.csv", index=False)

    cycle = (races.groupby("cycle", as_index=False).agg(
        races=("district", "size"), federal_primary=("federal_primary", "sum"),
        mean_raw_gap=("raw_ticket_gap", "mean"), mean_war=("war_cmo", "mean"),
        mae_war=("war_cmo", lambda x: x.abs().mean())))
    cycle.to_csv(WAR / "cmo_v4_cycle_diagnostics.csv", index=False)

    files = [v2.ELECTIONS / "canonical_cmo_features.csv", v2.ELECTIONS / "canonical_cmo_candidates.csv",
             v2.ELECTIONS / "historical_federal_district_baselines.csv", Path(__file__)]
    manifest = pd.DataFrame([{"record_type": "input" if p != Path(__file__) else "code",
                              "name": str(p.relative_to(ROOT)),
                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files])
    manifest = pd.concat([manifest, pd.DataFrame([{"record_type": "config", "name": "selected_alpha", "sha256": str(alpha)},
                                                  {"record_type": "config", "name": "demographic_cap", "sha256": "3.0"},
                                                  {"record_type": "config", "name": "campaign_effort_cap", "sha256": "2.0"}])], ignore_index=True)
    manifest.to_csv(WAR / "cmo_v4_provenance.csv", index=False)

    morrow = races[(races.cycle.eq(1998)) & races.chamber.eq("house") & races.district.eq(18)].iloc[0]
    REPORT.write_text(
        "# CMO methodology v4: Alabama WAR analogue\n\n"
        "CMO is the residual of a model predicting the legislative-minus-same-cycle-federal "
        "margin gap. Incumbency and down-ballot lag are the principal structural controls. "
        "Demographics are capped at three margin points and campaign effort at two. Ideology "
        "never enters the model.\n\n"
        "## Formula\n\n"
        "`CMO = raw legislative-ticket gap - predicted structural gap`\n\n"
        "Federal-unavailable races use the same-cycle state ticket and are labeled sensitivity "
        "fallbacks. The model is trained only on races with usable federal baselines.\n\n"
        f"Selected ridge alpha: {alpha:g}.\n\n"
        "## Morrow, 1998 HD-18\n\n"
        f"- Raw legislative-federal gap: {morrow.raw_ticket_gap:.3f}\n"
        f"- Predicted structural gap: {morrow.predicted_structural_gap:.3f}\n"
        f"- WAR-style CMO: {morrow.war_cmo:.3f}\n\n"
        "## Tournament\n\n" + v2.markdown_table(results) + "\n\n"
        "## Cycle diagnostics\n\n" + v2.markdown_table(cycle) + "\n\n"
        "## Construct validity\n\n" + v2.markdown_table(validity) + "\n",
        encoding="utf-8")
    print(f"races={len(races)} candidates={len(candidate)} primary={int(races.federal_primary.sum())} alpha={alpha:g}")


if __name__ == "__main__":
    build()
