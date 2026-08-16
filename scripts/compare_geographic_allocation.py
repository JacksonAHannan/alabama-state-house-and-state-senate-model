"""Compare current geographic allocation with the repository's prior baseline."""

from io import StringIO
from pathlib import Path
import subprocess

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"


def main() -> None:
    old_text = subprocess.check_output(
        ["git", "show", "HEAD:data/processed/war/war_model_features.csv"],
        cwd=ROOT, text=True)
    old = pd.read_csv(StringIO(old_text))
    new = pd.read_csv(WAR / "war_model_features.csv")
    key = ["cycle", "chamber", "district"]
    columns = key + ["statewide_index_margin", "raw_overperformance"]
    comparison = old[columns].merge(new[columns], on=key, suffixes=("_activity", "_geographic"),
                                    validate="one_to_one")
    for field in ("statewide_index_margin", "raw_overperformance"):
        comparison[f"{field}_change"] = (comparison[f"{field}_geographic"] -
                                          comparison[f"{field}_activity"])
    comparison.to_csv(WAR / "geographic_allocation_feature_comparison.csv", index=False)
    summary = (comparison.groupby(["cycle", "chamber"], as_index=False)
               .agg(mean_abs_baseline_change=("statewide_index_margin_change", lambda x: x.abs().mean()),
                    max_abs_baseline_change=("statewide_index_margin_change", lambda x: x.abs().max()),
                    mean_abs_target_change=("raw_overperformance_change", lambda x: x.abs().mean()),
                    max_abs_target_change=("raw_overperformance_change", lambda x: x.abs().max())))
    summary.to_csv(WAR / "geographic_allocation_comparison_summary.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
