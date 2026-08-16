"""Create a prioritized review queue for preliminary WAR scores."""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"

# Presidential source years feeding each cycle's features, mirroring
# build_presidential_district_features.TARGET_SOURCES. A race is fallback-heavy
# if ANY of its cycle's presidential inputs leaned mostly on county-level
# redistribution rather than direct precinct matches.
CYCLE_PRESIDENTIAL_SOURCES = {2010: [], 2014: [2012], 2018: [2012, 2016], 2022: [2016, 2020]}


def max_presidential_fallback_share(races: pd.DataFrame) -> pd.Series:
    """Largest fallback share among the presidential inputs used by each cycle.

    This flag used to be hardcoded to `cycle == 2014` and to the 2012 column,
    which silently skipped every 2018 race once 2012 data started feeding the
    2018 cycle as well -- 14 contested 2018 races carried
    pres_2012_fallback_share >= 0.5 and were never queued for review.
    validate_war_outputs.py's equivalent check is cycle-agnostic; this matches it.
    """
    share = pd.Series(0.0, index=races.index)
    for cycle, source_years in CYCLE_PRESIDENTIAL_SOURCES.items():
        rows = races.cycle.eq(cycle)
        columns = [f"pres_{year}_fallback_share" for year in source_years
                   if f"pres_{year}_fallback_share" in races]
        if not columns or not rows.any():
            continue
        share.loc[rows] = races.loc[rows, columns].fillna(0).max(axis=1)
    return share


def main() -> None:
    races = pd.read_csv(WAR / "preliminary_war_races.csv")
    races["high_absolute_war"] = races.war_residual_oof.abs().ge(25)
    races["max_pres_fallback_share"] = max_presidential_fallback_share(races)
    races["high_pres_fallback"] = races.max_pres_fallback_share.ge(0.50)
    races["finance_incomplete"] = ~races.finance_complete.fillna(False).astype(bool)
    races["ftm_finance_incomplete"] = ~races.ftm_finance_complete.fillna(False).astype(bool)
    races["baseline_incomplete"] = ~races.core_index_complete.fillna(False).astype(bool)
    races["cycle_shift_risk"] = races.cycle.eq(2014)
    uncertainty_path = ROOT / "data" / "processed" / "elections" / "canonical_baseline_uncertainty.csv"
    if uncertainty_path.exists():
        uncertainty = pd.read_csv(uncertainty_path)[["cycle","chamber","district","baseline_range"]]
        races = races.merge(uncertainty, on=["cycle","chamber","district"], how="left", validate="one_to_one")
    else:
        races["baseline_range"] = 0.0
    races["baseline_geography_sensitive"] = races.baseline_range.fillna(0).ge(1.0)
    flag_cols = ["high_absolute_war", "high_pres_fallback", "finance_incomplete",
                 "ftm_finance_incomplete", "baseline_incomplete", "cycle_shift_risk",
                 "baseline_geography_sensitive"]
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
