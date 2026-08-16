"""Normalize Catalist's public national demographic election estimates."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "polling"
OUT = ROOT / "data" / "processed" / "polling"
WORKBOOK = RAW / "Catalist_What_Happened_2024_Public_National_Crosstabs_2025_05_19.xlsx"
WORKBOOK_SOURCE = "https://catalist.us/whathappened2024/"
HISTORICAL_SOURCE = "https://catalist.us/revisiting-what-happened-2018/"

# Values transcribed from Catalist's published historical table image. Only
# years absent from the newer workbook are used, preventing vintage mixing in
# overlapping years.
HISTORICAL_MARGINS = {
    2008: {"Total": 8, "White Non-College": -10, "White College": -4,
           "Black": 90, "Latinx": 27, "Asian/Other": 26},
    2010: {"Total": -5, "White Non-College": -23, "White College": -11,
           "Black": 80, "Latinx": 21, "Asian/Other": 19},
}


def normalize_header(value: object) -> tuple[str, int] | None:
    text = " ".join(str(value).split())
    match = re.match(r"^(Pres|CD)\s*(20\d{2})$", text)
    if not match:
        return None
    return ({"Pres": "president", "CD": "us_house"}[match.group(1)], int(match.group(2)))


def group_dimension(group: str) -> str:
    if group == "Total":
        return "overall"
    if group in {"White", "Black", "Latino", "AAPI", "Other"}:
        return "race"
    if group in {"18-29", "30-44", "45-64", "65+"}:
        return "age"
    if group in {"Women", "Men"}:
        return "gender"
    if "College" in group and group in {"Non-College", "College"}:
        return "education"
    if any(token in group for token in ["White", "Black", "Latino", "AAPI", "Other"]):
        return "intersectional"
    return "other"


def parse_workbook(path: Path = WORKBOOK) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Catalist What Happened 2024", header=None)
    headers = raw.iloc[5]
    rows: list[dict] = []
    for row_index in range(6, len(raw)):
        group_value = raw.iat[row_index, 0]
        if pd.isna(group_value):
            continue
        group = str(group_value).strip()
        for column in range(2, 10):
            if pd.isna(raw.iat[row_index, column]):
                continue
            year = int(float(headers.iloc[column]))
            rows.append({
                "year": year, "election_type": "electorate", "dimension": group_dimension(group),
                "group": group, "metric": "electorate_composition_pct",
                "value": float(raw.iat[row_index, column]), "source_vintage": "2024_workbook",
                "source_url": WORKBOOK_SOURCE,
            })
        for column in range(10, 21):
            parsed = normalize_header(headers.iloc[column])
            if not parsed or pd.isna(raw.iat[row_index, column]):
                continue
            election_type, year = parsed
            rows.append({
                "year": year, "election_type": election_type, "dimension": group_dimension(group),
                "group": group, "metric": "dem_two_party_share_pct",
                "value": float(raw.iat[row_index, column]), "source_vintage": "2024_workbook",
                "source_url": WORKBOOK_SOURCE,
            })
    return pd.DataFrame(rows)


def add_historical_rows(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, groups in HISTORICAL_MARGINS.items():
        election_type = "president" if year % 4 == 0 else "us_house"
        for group, margin in groups.items():
            rows.append({
                "year": year, "election_type": election_type,
                "dimension": group_dimension(group), "group": group,
                "metric": "dem_two_party_share_pct", "value": 50 + margin / 2,
                "source_vintage": "2018_historical_chart",
                "source_url": HISTORICAL_SOURCE,
            })
    return pd.concat([frame, pd.DataFrame(rows)], ignore_index=True)


def main() -> None:
    frame = add_historical_rows(parse_workbook())
    duplicates = frame.duplicated(["year", "election_type", "group", "metric"])
    if duplicates.any():
        raise RuntimeError("Catalist master contains duplicate election/group metrics")
    frame = frame.sort_values(["metric", "year", "election_type", "dimension", "group"])
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "catalist_national_demographic_master.csv"
    frame.to_csv(path, index=False)
    core = frame[(frame.metric == "dem_two_party_share_pct") & frame.group.isin(
        ["Total", "White Non-College", "White College", "Black", "Latino", "Latinx"]
    )]
    print(core.to_string(index=False))
    print(f"Wrote {len(frame):,} Catalist estimates to {path}")


if __name__ == "__main__":
    main()
