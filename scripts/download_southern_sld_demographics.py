"""Download election-vintage ACS demographics for Southern SLD calibration."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "forecast_calibration"
STATES = {"AR": "05", "GA": "13", "LA": "22", "MS": "28", "TN": "47", "TX": "48"}
COLLEGE = ["B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]
VARIABLES = ["NAME", "B03002_001E", "B03002_003E", "B15003_001E", *COLLEGE,
             "C15002H_001E", "C15002H_006E", "C15002H_011E"]


def api_key() -> str:
    for name in (".env", "token.env"):
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("CENSUS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("CENSUS_API_KEY", "")


def pull(year: int, state: str, chamber: str) -> pd.DataFrame:
    geography = ("state legislative district (upper chamber)" if chamber == "upper"
                 else "state legislative district (lower chamber)")
    params = {"get": ",".join(VARIABLES), "for": f"{geography}:*", "in": f"state:{STATES[state]}"}
    if api_key():
        params["key"] = api_key()
    response = requests.get(f"https://api.census.gov/data/{year}/acs/acs5", params=params, timeout=90)
    response.raise_for_status()
    payload = response.json()
    frame = pd.DataFrame(payload[1:], columns=payload[0])
    frame["district"] = pd.to_numeric(frame[geography], errors="coerce")
    for variable in VARIABLES[1:]:
        frame[variable] = pd.to_numeric(frame[variable], errors="coerce")
    frame["nonwhite_share"] = 1 - frame.B03002_003E / frame.B03002_001E
    frame["college_share"] = frame[COLLEGE].sum(axis=1) / frame.B15003_001E
    frame["white_college_share"] = (frame.C15002H_006E + frame.C15002H_011E) / frame.C15002H_001E
    frame["state"], frame["year"], frame["chamber"] = state, year, chamber
    frame["acs_vintage"] = year
    frame["demographics_source"] = f"ACS {year} 5-year direct SLD tabulation"
    return frame[["state", "year", "chamber", "district", "nonwhite_share", "college_share",
                  "white_college_share", "acs_vintage", "demographics_source"]]


def main() -> None:
    frames = []
    for year in (2018, 2019, 2020, 2022, 2024):
        for state in STATES:
            for chamber in ("lower", "upper"):
                try:
                    frames.append(pull(year, state, chamber))
                    print(year, state, chamber, len(frames[-1]))
                except requests.HTTPError as error:
                    print("SKIP", year, state, chamber, error)
    data = pd.concat(frames, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUT / "southern_sld_acs_demographics.csv", index=False)
    print(data.groupby(["year", "state", "chamber"]).size().to_string())


if __name__ == "__main__":
    main()
