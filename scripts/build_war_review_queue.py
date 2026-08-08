"""Create a prioritized review queue for preliminary WAR scores."""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"


def main() -> None:
    races = pd.read_csv(WAR / "preliminary_war_races.csv")
    races["high_absolute_war"] = races.war_residual_oof.abs().ge(25)
    races["high_2012_fallback"] = (races.cycle.eq(2014) &
                                    races.pres_2012_fallback_share.fillna(0).ge(0.50))
    races["finance_incomplete"] = ~races.finance_complete.fillna(False).astype(bool)
    races["baseline_incomplete"] = ~races.core_index_complete.fillna(False).astype(bool)
    races["cycle_shift_risk"] = races.cycle.eq(2014)
    flag_cols = ["high_absolute_war", "high_2012_fallback", "finance_incomplete",
                 "baseline_incomplete", "cycle_shift_risk"]
    races["review_flag_count"] = races[flag_cols].sum(axis=1)
    races["review_reasons"] = races.apply(
        lambda row: " | ".join(col for col in flag_cols if bool(row[col])), axis=1)
    queue = races[races.review_flag_count.gt(0)].sort_values(
        ["high_absolute_war", "review_flag_count", "war_residual_oof"],
        ascending=[False, False, False])
    queue.to_csv(WAR / "preliminary_war_review_queue.csv", index=False)
    summary = pd.DataFrame([{"flag": col, "races": int(races[col].sum())} for col in flag_cols])
    summary.to_csv(WAR / "preliminary_war_review_summary.csv", index=False)
    print(summary.to_string(index=False))
    print("\nHighest-priority races:")
    print(queue.head(15)[["cycle", "chamber", "district", "war_residual_oof",
                          "review_reasons"]].to_string(index=False))


if __name__ == "__main__":
    main()
