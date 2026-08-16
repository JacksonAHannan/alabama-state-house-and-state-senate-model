"""Compare retired legislative-activity and Census geographic weights."""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"


def main() -> None:
    key = ["cycle", "chamber", "county_key", "precinct_key", "district"]
    activity = pd.read_csv(WAR / "precinct_district_allocation_weights.csv")[
        key + ["allocation_weight"]].rename(columns={"allocation_weight": "activity_weight"})
    geographic = pd.read_csv(WAR / "geographic_precinct_district_weights.csv")[
        key + ["allocation_weight", "allocation_method"]].rename(
            columns={"allocation_weight": "geographic_weight"})
    detail = activity.merge(geographic, on=key, how="outer")
    detail[["activity_weight", "geographic_weight"]] = detail[
        ["activity_weight", "geographic_weight"]].fillna(0)
    detail["weight_change"] = detail.geographic_weight - detail.activity_weight
    detail["absolute_weight_change"] = detail.weight_change.abs()
    detail.to_csv(WAR / "allocation_weight_sensitivity_detail.csv", index=False)
    summary = (detail.groupby(["cycle", "chamber", "district"], as_index=False)
               .agg(precinct_district_rows=("precinct_key", "size"),
                    max_absolute_weight_change=("absolute_weight_change", "max"),
                    mean_absolute_weight_change=("absolute_weight_change", "mean"),
                    county_fallback_rows=("allocation_method",
                                          lambda x: x.eq("county_population_fallback").sum())))
    summary["allocation_sensitivity_flag"] = summary.max_absolute_weight_change.ge(.10)
    summary.sort_values(["allocation_sensitivity_flag", "max_absolute_weight_change"],
                        ascending=False).to_csv(
                            WAR / "allocation_weight_sensitivity_by_district.csv", index=False)
    print(summary.sort_values("max_absolute_weight_change", ascending=False).head(25).to_string(index=False))


if __name__ == "__main__":
    main()
