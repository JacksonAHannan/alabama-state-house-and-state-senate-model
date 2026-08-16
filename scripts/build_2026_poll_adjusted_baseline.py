"""Adjust the direct 2024 presidential baseline for the live national environment."""
from pathlib import Path
import datetime as dt

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
POLLING = ROOT / "data" / "processed" / "polling"
OUT = ROOT / "data" / "processed" / "war"

# Official national two-party presidential margin, D minus R. This is the same
# national-environment anchor used by the VoteHub worked example (approximately R+1.5).
NATIONAL_2024_DEM_MARGIN = -1.48


def main() -> None:
    baseline = pd.read_csv(ROOT / "data" / "processed" / "presidential" /
                           "2026_district_presidential_features.csv")
    quality_environment = POLLING / "votehub_silver_bplus_topline_environment.csv"
    if quality_environment.exists():
        selected = pd.read_csv(quality_environment).iloc[0]
        poll_margin = float(selected.dem_two_party_margin)
        poll_as_of = str(selected.as_of)
        poll_staleness = (dt.date.today() - dt.date.fromisoformat(poll_as_of)).days
    else:
        selected = pd.read_csv(POLLING / "votehub_generic_ballot_snapshot.csv").iloc[0]
        poll_margin = float(selected.generic_ballot_dem_margin_two_party)
        poll_as_of = str(selected.poll_average_as_of)
        poll_staleness = int(selected.staleness_days)
    national_swing = poll_margin - NATIONAL_2024_DEM_MARGIN
    baseline["baseline_2024_pres_dem_margin"] = baseline.pres_2024_dem_margin
    baseline["national_2024_dem_margin"] = NATIONAL_2024_DEM_MARGIN
    baseline["votehub_2026_dem_margin"] = poll_margin
    baseline["national_dem_swing_2024_2026"] = national_swing
    baseline["geographic_elasticity"] = 1.0
    baseline["poll_adjusted_dem_margin"] = baseline.pres_2024_dem_margin + national_swing
    baseline["low_elasticity_075_margin"] = baseline.pres_2024_dem_margin + .75 * national_swing
    baseline["high_elasticity_125_margin"] = baseline.pres_2024_dem_margin + 1.25 * national_swing
    baseline["poll_average_as_of"] = poll_as_of
    baseline["poll_staleness_days_at_download"] = poll_staleness
    baseline["uniform_poll_adjusted_dem_margin"] = baseline["poll_adjusted_dem_margin"]
    demographic_path = OUT / "2026_demographic_poll_adjusted_baseline.csv"
    if demographic_path.exists():
        demographic = pd.read_csv(demographic_path)[[
            "chamber", "district", "demographic_swing_2024_2026", "demographic_poll_adjusted_margin"
        ]]
        baseline = baseline.merge(demographic, on=["chamber", "district"], validate="one_to_one")
        baseline["poll_adjusted_dem_margin"] = baseline.demographic_poll_adjusted_margin
        baseline["status"] = "catalist_yougov_demographic_transfer_selected"
    else:
        baseline["demographic_swing_2024_2026"] = pd.NA
        baseline["demographic_poll_adjusted_margin"] = pd.NA
        baseline["status"] = "uniform_swing_fallback_demographic_output_missing"
    columns = ["cycle", "chamber", "district", "baseline_2024_pres_dem_margin",
               "national_2024_dem_margin", "votehub_2026_dem_margin",
               "national_dem_swing_2024_2026", "geographic_elasticity",
               "poll_adjusted_dem_margin", "uniform_poll_adjusted_dem_margin",
               "demographic_swing_2024_2026", "demographic_poll_adjusted_margin", "low_elasticity_075_margin",
               "high_elasticity_125_margin", "poll_average_as_of",
               "poll_staleness_days_at_download", "status"]
    baseline[columns].to_csv(OUT / "2026_poll_adjusted_baseline.csv", index=False)
    print(baseline[columns].groupby("chamber").agg(
        districts=("district", "count"),
        mean_base=("baseline_2024_pres_dem_margin", "mean"),
        mean_adjusted=("poll_adjusted_dem_margin", "mean")).to_string())


if __name__ == "__main__":
    main()
