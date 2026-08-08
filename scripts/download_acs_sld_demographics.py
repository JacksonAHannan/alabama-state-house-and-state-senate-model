"""Download ACS five-year Alabama legislative-district demographics."""

from pathlib import Path
import os
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "demographics"
COLLEGE_VARS = ["B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]
# White-alone, not-Hispanic-or-Latino sex-by-educational-attainment (collapsed
# categories), used for a direct white_college_share instead of assuming
# college attainment is independent of race within a district.
WHITE_COLLEGE_VARS = ["C15002H_001E", "C15002H_006E", "C15002H_011E"]
BASE_VARS = ["NAME", "B03002_001E", "B03002_003E", "B15003_001E",
             *COLLEGE_VARS, *WHITE_COLLEGE_VARS]


def api_key() -> str:
    for line in (ROOT / "token.env").read_text(encoding="utf-8").splitlines():
        if line.startswith("CENSUS_API_KEY="):
            return line.split("=", 1)[1].strip()
    return os.environ.get("CENSUS_API_KEY", "")


def pull(year: int, chamber: str, geography: str) -> pd.DataFrame:
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    variables = BASE_VARS
    params = {"get": ",".join(variables), "for": f"{geography}:*", "in": "state:01",
              "key": api_key()}
    response = requests.get(url, params=params, timeout=60)
    if not response.ok:
        raise RuntimeError(f"Census API {response.status_code}: {response.text[:500]}")
    payload = response.json()
    data = pd.DataFrame(payload[1:], columns=payload[0])
    district_col = geography
    data["district"] = pd.to_numeric(data[district_col], errors="coerce").astype("Int64")
    for var in variables[1:]:
        data[var] = pd.to_numeric(data[var], errors="coerce")
    data["nonwhite_share"] = 1 - data.B03002_003E / data.B03002_001E
    data["college_share"] = data[COLLEGE_VARS].sum(axis=1) / data.B15003_001E
    data["white_college_share"] = (
        (data.C15002H_006E + data.C15002H_011E) / data.C15002H_001E)
    data["cycle"] = year
    data["acs_vintage"] = year
    data["chamber"] = chamber
    return data[["cycle", "acs_vintage", "chamber", "district", "NAME",
                 "B03002_001E", "B15003_001E", "nonwhite_share",
                 "college_share", "white_college_share", "C15002H_001E"]]


def main() -> None:
    frames = []
    for year in (2014, 2018, 2022):
        frames.append(pull(year, "house", "state legislative district (lower chamber)"))
        frames.append(pull(year, "senate", "state legislative district (upper chamber)"))
    data = pd.concat(frames, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUT / "acs_direct_sld_demographics.csv", index=False)
    print(data.groupby(["cycle", "chamber"]).agg(
        rows=("district", "size"), min_district=("district", "min"),
        max_district=("district", "max"), null_nonwhite=("nonwhite_share", lambda x: x.isna().sum()),
        null_white_college=("white_college_share", lambda x: x.isna().sum())).to_string())


if __name__ == "__main__":
    main()
