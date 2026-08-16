"""Normalize YouGov's congressional-ballot tracker and create election snapshots."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "polling" / "yougov_congressional_ballot_tracker.xlsx"
OUT = ROOT / "data" / "processed" / "polling"
ELECTION_DATES = {2018: "2018-11-06", 2020: "2020-11-03", 2022: "2022-11-08", 2024: "2024-11-05"}
DIMENSIONS = {
    "US Registered Voters": ("overall", "all"),
    "Under 30": ("age", "under_30"), "30-44": ("age", "30_44"),
    "45-64": ("age", "45_64"), "65+": ("age", "65_plus"),
    "Male": ("gender", "male"), "Female": ("gender", "female"),
    "White": ("race", "white"), "Black": ("race", "black"),
    "Hispanic": ("race", "hispanic"), "Other": ("race", "other"),
    "HS or less": ("education", "hs_or_less"),
    "Some college": ("education", "some_college"),
    "College grad": ("education", "college_grad"),
    "Postgrad": ("education", "postgrad"),
}


def parse_sheet(frame: pd.DataFrame, sheet: str) -> pd.DataFrame:
    dates = pd.to_datetime(frame.iloc[0, 1:], errors="coerce")
    labels = frame.iloc[:, 0].astype(str).str.strip()
    dem_rows = frame.index[labels.eq("The Democratic Party candidate")]
    rep_rows = frame.index[labels.eq("The Republican Party candidate")]
    base_rows = frame.index[labels.eq("Unweighted base")]
    if len(dem_rows) != 1 or len(rep_rows) != 1:
        raise ValueError(f"Unexpected answer rows in YouGov sheet {sheet}")
    dem = pd.to_numeric(frame.iloc[dem_rows[0], 1:], errors="coerce")
    rep = pd.to_numeric(frame.iloc[rep_rows[0], 1:], errors="coerce")
    base = pd.to_numeric(frame.iloc[base_rows[0], 1:], errors="coerce") if len(base_rows) else np.nan
    dimension, group = DIMENSIONS[sheet]
    result = pd.DataFrame({"date": dates, "dem_raw_share": dem, "rep_raw_share": rep,
                           "unweighted_base": base})
    result = result.dropna(subset=["date", "dem_raw_share", "rep_raw_share"])
    result["dem_two_party_share"] = result.dem_raw_share / (result.dem_raw_share + result.rep_raw_share)
    result["dem_margin_two_party"] = 100 * (result.dem_raw_share - result.rep_raw_share) / (result.dem_raw_share + result.rep_raw_share)
    result.insert(0, "group", group); result.insert(0, "dimension", dimension)
    return result


def election_snapshots(long: pd.DataFrame, waves: int = 4) -> pd.DataFrame:
    targets = {**ELECTION_DATES, 2026: long.date.max().date().isoformat()}
    rows = []
    for year, target in targets.items():
        eligible = long[long.date.le(pd.Timestamp(target))]
        for (dimension, group), part in eligible.groupby(["dimension", "group"]):
            sample = part.nlargest(waves, "date")
            rows.append({"cycle": year, "target_date": target, "dimension": dimension, "group": group,
                         "waves": len(sample), "first_wave": sample.date.min().date().isoformat(),
                         "last_wave": sample.date.max().date().isoformat(),
                         "dem_margin_two_party": sample.dem_margin_two_party.mean(),
                         "dem_two_party_share": sample.dem_two_party_share.mean(),
                         "mean_unweighted_base": sample.unweighted_base.mean(),
                         "source": "YouGov Congressional Ballot Voting Intention tracker"})
    return pd.DataFrame(rows)


def main() -> None:
    workbook = pd.ExcelFile(SOURCE)
    missing = set(DIMENSIONS) - set(workbook.sheet_names)
    if missing:
        raise RuntimeError(f"Missing expected YouGov sheets: {sorted(missing)}")
    long = pd.concat([parse_sheet(pd.read_excel(SOURCE, sheet_name=sheet, header=None), sheet)
                      for sheet in DIMENSIONS], ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    long.to_csv(OUT / "yougov_generic_ballot_demographics_long.csv", index=False)
    snapshots = election_snapshots(long)
    snapshots.to_csv(OUT / "yougov_generic_ballot_election_snapshots.csv", index=False)
    print(snapshots[snapshots.cycle.eq(2026)][["dimension", "group", "dem_margin_two_party",
          "waves", "last_wave"]].to_string(index=False))


if __name__ == "__main__":
    main()
