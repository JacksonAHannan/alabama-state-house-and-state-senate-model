"""Normalize Alabama's county-level 2012 presidential precinct workbooks."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Results and Shapefiles" / "2012General-PrecinctLevel.zip"
OUTPUT = ROOT / "data" / "processed" / "presidential"
UNAVAILABLE = {"Bullock", "Butler", "Hale", "Wilcox"}


def county_name(filename: str) -> str:
    name = re.sub(r"\.xls(?:\.xls)?$|\.xlsx$", "", Path(filename).name, flags=re.I)
    return "Randolph" if name == "Radolph" else name


def tidy(rows: list[dict[str, object]], county: str, source_format: str) -> pd.DataFrame:
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["county"] = county
    out["source_format"] = source_format
    out["precinct"] = out["precinct"].astype(str).str.strip()
    for col in ("dem_votes", "rep_votes"):
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)
    out = out[~out.precinct.str.contains(r"^Totals?:?\s*$", case=False, na=False)].copy()
    out["two_party_votes"] = out.dem_votes + out.rep_votes
    out["pres_dem_margin"] = (100 * (out.dem_votes - out.rep_votes) /
                              out.two_party_votes.where(out.two_party_votes > 0))
    return out[["county", "precinct", "dem_votes", "rep_votes", "two_party_votes",
                "pres_dem_margin", "source_format"]]


def standard_xlsx(data: bytes, county: str) -> pd.DataFrame:
    xf = pd.ExcelFile(BytesIO(data))
    target = next((s for s in xf.sheet_names if "PRESIDENT AND VICE-PRESIDENT" in
                   pd.read_excel(xf, s, header=None, nrows=1).astype(str).to_string()), None)
    if target is None:
        raise ValueError("presidential sheet not found")
    raw = pd.read_excel(xf, target, header=None)
    rows = []
    for values in raw.iloc[3:].itertuples(index=False, name=None):
        if len(values) < 6 or pd.isna(values[0]):
            continue
        rows.append({"precinct": values[0], "dem_votes": values[3], "rep_votes": values[5]})
    return tidy(rows, county, "standard_xlsx")


def montgomery_xlsx(data: bytes) -> pd.DataFrame:
    raw = pd.read_excel(BytesIO(data), sheet_name="Precinct Results")
    pres = raw[raw["Contest Title"].astype(str).str.contains(
        "PRESIDENT AND VICE-PRESIDENT", case=False, na=False)]
    dem = pres[pres.Party.eq("DEM")].iloc[0]
    rep = pres[pres.Party.eq("REP")].iloc[0]
    metadata = {"Contest Title", "Party", "Candidate"}
    rows = [{"precinct": col, "dem_votes": dem[col], "rep_votes": rep[col]}
            for col in raw.columns if col not in metadata]
    return tidy(rows, "Montgomery", "transposed_xlsx")


def xml_rows(data: bytes, county: str) -> pd.DataFrame:
    ns = {"s": "urn:schemas-microsoft-com:office:spreadsheet"}
    root = ET.fromstring(data.decode("utf-8-sig").encode())
    sheet = next(ws for ws in root.findall("s:Worksheet", ns)
                 if ws.attrib.get("{urn:schemas-microsoft-com:office:spreadsheet}Name") == "2")
    parsed = []
    for row in sheet.findall(".//s:Row", ns):
        values = [d.text for d in row.findall(".//s:Data", ns)]
        parsed.append(values)
    rows = []
    for values in parsed[3:]:
        if len(values) < 6 or not values[0]:
            continue
        rows.append({"precinct": values[0], "dem_votes": values[3], "rep_votes": values[5]})
    return tidy(rows, county, "spreadsheetml")


def main() -> None:
    frames = []
    qa = []
    with ZipFile(SOURCE) as archive:
        for filename in archive.namelist():
            county = county_name(filename)
            data = archive.read(filename)
            if county in UNAVAILABLE:
                qa.append({"county": county, "status": "precinct_results_unavailable",
                           "precincts": 0, "dem_votes": 0, "rep_votes": 0})
                continue
            try:
                if county == "Montgomery":
                    frame = montgomery_xlsx(data)
                elif filename.lower().endswith(".xls.xls"):
                    frame = xml_rows(data, county)
                else:
                    frame = standard_xlsx(data, county)
                frames.append(frame)
                qa.append({"county": county, "status": "parsed", "precincts": len(frame),
                           "dem_votes": frame.dem_votes.sum(), "rep_votes": frame.rep_votes.sum()})
            except Exception as exc:
                qa.append({"county": county, "status": f"parse_error: {exc}",
                           "precincts": 0, "dem_votes": 0, "rep_votes": 0})

    results = pd.concat(frames, ignore_index=True)
    quality = pd.DataFrame(qa).sort_values("county")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT / "2012_president_precinct.csv", index=False)
    quality.to_csv(OUTPUT / "2012_president_county_qa.csv", index=False)
    print(f"Parsed counties: {(quality.status == 'parsed').sum()}/67")
    print(f"Precinct rows: {len(results):,}")
    print(f"Obama votes represented: {results.dem_votes.sum():,}")
    print(f"Romney votes represented: {results.rep_votes.sum():,}")
    print(quality[quality.status.ne("parsed")].to_string(index=False))


if __name__ == "__main__":
    main()
