"""Create experimental 2026 Alabama demographic polling projections.

The output is diagnostic until the historical transfer gate passes. It must
not be poststratified by independently adding age, education, gender, and race
effects because those dimensions overlap.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from backtest_ces_polling_transfer import (
    fit_pooled_beta,
    inv_logit,
    logit,
    prepare_inputs,
)

ROOT = Path(__file__).resolve().parents[1]
POLLING = ROOT / "data" / "processed" / "polling"


def main() -> None:
    ces = pd.read_csv(POLLING / "ces_house_vote_demographics.csv")
    polls = pd.read_csv(POLLING / "yougov_generic_ballot_election_snapshots.csv")
    inputs = prepare_inputs(ces, polls)
    backtest = pd.read_csv(POLLING / "ces_yougov_transfer_backtest.csv")
    history = backtest[backtest.method == "carry_forward"].copy()
    history["actual_change_logit"] = history.apply(
        lambda row: logit(row.actual_dem_share) - logit(row.forecast_dem_share), axis=1
    )
    beta = fit_pooled_beta(history)

    prior = inputs[inputs.year == 2024].set_index(["dimension", "group"])
    current = polls[polls.cycle == 2026].rename(
        columns={"dem_two_party_share": "poll_share"}
    ).set_index(["dimension", "group"])
    rows = []
    for dimension, group in prior.index.intersection(current.index):
        old = prior.loc[(dimension, group)]
        now = current.loc[(dimension, group)]
        if pd.isna(now.poll_share):
            continue
        signal = logit(now.poll_share) - logit(old.national_share)
        projected = inv_logit(logit(old.al_share) + beta * signal)
        rows.append({
            "cycle": 2026, "dimension": dimension, "group": group,
            "ces_2024_alabama_dem_share": old.al_share,
            "ces_2024_rest_us_dem_share": old.national_share,
            "yougov_2026_dem_share": now.poll_share,
            "pooled_transfer_beta": beta,
            "projected_2026_alabama_dem_share": projected,
            "projected_alabama_swing_points": 100 * (projected - old.al_share),
            "status": "experimental_validation_gate_failed",
        })
    projection = pd.DataFrame(rows).sort_values(["dimension", "group"])
    projection.to_csv(POLLING / "2026_ces_yougov_demographic_projection_experimental.csv", index=False)

    summary = pd.read_csv(POLLING / "ces_yougov_transfer_backtest_summary.csv")
    yearly = summary[summary.target_year.astype(str) != "all"].copy()
    pivot = yearly.pivot(index="target_year", columns="method", values="weighted_mae_points")
    wins = int((pivot.demographic_pooled_transfer < pivot.carry_forward).sum())
    overall = summary[summary.target_year.astype(str) == "all"].set_index("method")
    improvement = float(
        overall.loc["carry_forward", "weighted_mae_points"]
        - overall.loc["demographic_pooled_transfer", "weighted_mae_points"]
    )
    gate = pd.DataFrame([{
        "historical_cycles": len(pivot), "cycles_beating_carry_forward": wins,
        "required_cycle_wins": 3, "pooled_mae_improvement_points": improvement,
        "pooled_transfer_beta": beta,
        "gate_passed": wins >= 3 and improvement > 0,
        "production_action": "withhold_demographic_transfer" if wins < 3 else "eligible_for_review",
    }])
    gate.to_csv(POLLING / "ces_yougov_transfer_release_gate.csv", index=False)
    print(gate.to_string(index=False))
    print(projection[["dimension", "group", "projected_alabama_swing_points"]].to_string(index=False))


if __name__ == "__main__":
    main()
