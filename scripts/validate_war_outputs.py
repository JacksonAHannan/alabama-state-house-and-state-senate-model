"""Validate final WAR artifacts and create a compact model-readiness audit."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"


def add(rows, section, check, value, passed, note=""):
    rows.append({
        "section": section,
        "check": check,
        "value": value,
        "passed": bool(passed),
        "note": note,
    })


def main() -> None:
    features = pd.read_csv(WAR / "war_model_features.csv")
    source_races = pd.read_csv(WAR / "race_results.csv")
    races = pd.read_csv(WAR / "preliminary_war_races.csv")
    candidates = pd.read_csv(WAR / "preliminary_war_candidates.csv")
    diagnostics = pd.read_csv(WAR / "preliminary_war_diagnostics.csv")
    specs = pd.read_csv(WAR / "war_specification_comparison.csv")
    rows = []

    key = ["cycle", "chamber", "district"]
    add(rows, "features", "unique_cycle_chamber_district", int(features.duplicated(key).sum()),
        not features.duplicated(key).any(), "Duplicate count; must equal zero.")
    expected = {(2014, "house"): 105, (2014, "senate"): 35,
                (2018, "house"): 105, (2018, "senate"): 35,
                (2022, "house"): 105, (2022, "senate"): 35}
    counts = features.groupby(["cycle", "chamber"]).size().to_dict()
    add(rows, "features", "all_420_district_cycles_present", len(features),
        len(features) == 420 and counts == expected,
        "Expected 105 House and 35 Senate districts in each of three cycles.")

    eligible = races[races["war_eligible"].astype(bool)].copy()
    expected_eligible = int(source_races.war_eligible.astype(bool).sum())
    add(rows, "eligibility", "eligible_race_count", len(eligible),
        len(eligible) == expected_eligible,
        f"Contested D-R races only; expected dynamically from race_results ({expected_eligible}).")
    add(rows, "eligibility", "scores_only_on_eligible_races", int(races.war_residual_final.notna().sum()),
        races.loc[~races.war_eligible.astype(bool), "war_residual_final"].isna().all())

    required = ["raw_overperformance", "war_residual_oof", "war_residual_final",
                "war_model_se", "war_final_ci_low", "war_final_ci_high"]
    missing = int(eligible[required].isna().sum().sum())
    add(rows, "scores", "eligible_score_fields_complete", missing, missing == 0,
        "Missing cells across score and uncertainty fields.")
    ordered = (eligible.war_final_ci_low <= eligible.war_residual_final) & \
              (eligible.war_residual_final <= eligible.war_final_ci_high) & \
              (eligible.war_model_se >= 0)
    add(rows, "scores", "confidence_intervals_ordered", int((~ordered).sum()), ordered.all(),
        "Violation count; must equal zero.")

    c = candidates[candidates.candidate_war_final.notna()].copy()
    pairs = c.pivot_table(index=key, columns="party", values="candidate_war_final", aggfunc="first")
    pair_error = (pairs.get("D") + pairs.get("R")).abs()
    add(rows, "scores", "candidate_scores_are_zero_sum", float(pair_error.max()),
        bool(pair_error.fillna(np.inf).le(1e-9).all()), "Maximum absolute D+R score.")

    interval_sign_ok = np.where(
        c.party.eq("D"),
        np.isclose(c.candidate_war_final_ci_low, c.war_final_ci_low) &
        np.isclose(c.candidate_war_final_ci_high, c.war_final_ci_high),
        np.isclose(c.candidate_war_final_ci_low, -c.war_final_ci_high) &
        np.isclose(c.candidate_war_final_ci_high, -c.war_final_ci_low),
    )
    add(rows, "scores", "candidate_interval_sign_conversion", int((~interval_sign_ok).sum()),
        bool(interval_sign_ok.all()), "Republican intervals must reverse endpoints and signs.")

    add(rows, "coverage", "core_baseline_complete_eligible",
        int(eligible.core_index_complete.fillna(False).sum()),
        eligible.core_index_complete.fillna(False).mean() >= .98,
        f"{eligible.core_index_complete.fillna(False).mean():.1%} complete.")
    add(rows, "coverage", "finance_complete_eligible",
        int(eligible.finance_complete.fillna(False).sum()),
        eligible.finance_complete.fillna(False).mean() >= .80,
        f"{eligible.finance_complete.fillna(False).mean():.1%} complete; model includes missingness flag.")

    official_2018_path = WAR / "2018_official_vote_validation_summary.csv"
    if official_2018_path.exists():
        official_2018 = pd.read_csv(official_2018_path).iloc[0]
        official_ok = (official_2018.mismatches == 0 and official_2018.modeled_only == 0 and
                       official_2018.official_only == 0 and
                       official_2018.exact_vote_matches == official_2018.modeled_candidates)
        add(rows, "source_validation", "2018_candidate_totals_match_official_workbooks",
            int(official_2018.exact_vote_matches), official_ok,
            "Exact candidate vote matches out of 204 modeled candidates.")
    else:
        add(rows, "source_validation", "2018_candidate_totals_match_official_workbooks",
            "missing", False, "Run validate_2018_official_legislative_totals.py.")

    metric = diagnostics.iloc[0]
    add(rows, "validation", "random_fold_oof_r2_positive", float(metric["r2_oof"]),
        metric["r2_oof"] > 0)
    add(rows, "validation", "leave_cycle_out_r2_nonnegative", float(metric["r2_leave_cycle_out"]),
        metric["r2_leave_cycle_out"] >= 0,
        "A failure means the model should not be described as validated across unseen eras.")
    comparable = specs[specs.races.eq(len(eligible))]
    best = comparable.loc[comparable.cycle_holdout_rmse.idxmin()]
    add(rows, "validation", "best_cycle_holdout_specification", best.specification, True,
        f"RMSE {best.cycle_holdout_rmse:.3f}; comparison, not an absolute acceptance test.")

    qa = pd.DataFrame(rows)
    qa.to_csv(WAR / "model_readiness_qa.csv", index=False)

    # Audit the largest candidate-level scores with every major input alongside them.
    extreme = c.loc[c.candidate_war_oof.abs().ge(25)].copy()
    feature_cols = key + [
        "legislative_dem_margin", "statewide_index_margin",
        "incumbency_status", "incumbent_party", "prior_pres_dem_margin",
        "prior_pres_swing", "pres_2012_fallback_share", "core_index_complete",
        "baseline_quality", "dem_candidate_spending", "rep_candidate_spending",
        "finance_complete", "nonwhite_share", "white_college_share",
    ]
    extreme = extreme.merge(eligible[feature_cols], on=key, how="left", validate="many_to_one")
    extreme["source_outcome_validation"] = np.where(
        extreme.cycle.eq(2014), "matches archived Wikipedia district table",
        "processed election-source result; certified canvass comparison pending")
    extreme["review_priority"] = np.select(
        [~extreme.core_index_complete.fillna(False),
         extreme.pres_2012_fallback_share.fillna(0).ge(.50),
         ~extreme.finance_complete.fillna(False).astype(bool)],
        ["high: incomplete core baseline", "high: majority 2012 county fallback",
         "medium: finance incomplete"], default="standard extreme-score review")
    extreme = extreme.sort_values("candidate_war_oof", key=lambda s: s.abs(), ascending=False)
    extreme.to_csv(WAR / "extreme_war_validation.csv", index=False)

    print(qa.to_string(index=False))
    print(f"\nExtreme candidate scores written: {len(extreme)}")
    failed = qa[~qa.passed]
    print(f"Failed readiness checks: {len(failed)}")


if __name__ == "__main__":
    main()
