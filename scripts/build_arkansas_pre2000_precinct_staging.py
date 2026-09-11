#!/usr/bin/env python3
"""Normalize official Arkansas 1994-1998 county-sheet precinct workbooks."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/processed/precinct_history/arkansas_pre2000"
KLARNER = ROOT / "data/raw/historical_statewide_elections/dataverse_files.zip"
SOURCES = {
    1994: ROOT / "data/raw/southern_sos_elections/AR/1994/94general_election_results.xls",
    1996: ROOT / "data/raw/southern_sos_elections/AR/1996/precinct.xls",
    1998: ROOT / "data/raw/southern_sos_elections/AR/1998/Gen98Ver5.zip",
}

PARTIES = {
    "DEMOCRAT": "DEM", "DEMOCRATIC": "DEM", "REPUBLICAN": "REP",
    "INDEPENDENT": "IND", "REFORM": "OTH", "GREEN PARTY OF ARKANSAS": "OTH",
    "LIBERTARIAN": "OTH", "LIBERTARIAN PARTY": "OTH",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workbook(path: Path) -> pd.ExcelFile:
    if path.suffix.lower() != ".zip":
        return pd.ExcelFile(path)
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith((".xls", ".xlsx"))]
        if len(names) != 1:
            raise ValueError(f"Expected one workbook in {path}, found {names}")
        return pd.ExcelFile(io.BytesIO(archive.read(names[0])))


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_party(value: object) -> str | None:
    text = clean(value).upper()
    if not text or text == "NAN":
        return None
    if text in {"PARTY", "PARTY AFFILIATION", "AFFILIATION"}:
        return None
    for label, code in PARTIES.items():
        if label in text:
            return code
    return "OTH" if "PARTY" in text else None


def classify_contest(label: object) -> tuple[str, int | None] | None:
    text = clean(label).upper().replace("REPRESENTATVIE", "REPRESENTATIVE").replace("REPRESENTAVE", "REPRESENTATIVE")
    if "STATE REPRESENTATIVE" in text:
        office = "SLDL"
    elif "STATE SENAT" in text and not re.search(r"U\.?S\.?\s+SENAT|UNITED STATES SENAT", text):
        office = "SLDU"
    elif "PRESIDENT" in text:
        return "USP", None
    elif re.search(r"U\.?S\.?\s+SENAT|UNITED STATES SENAT", text):
        return "USS", None
    elif text == "GOVERNOR" or text.startswith("FOR GOVERNOR"):
        return "GOV", None
    elif "CONGRESS" in text and not any(word in text for word in ("CONGRESSMAN ", "104TH CONGRESS -")):
        office = "USH"
    else:
        return None
    numbers = re.findall(r"(?<!\d)(\d{1,3})(?:ST|ND|RD|TH)?(?!\d)", text)
    if office in {"SLDL", "SLDU"}:
        district = int(numbers[-1]) if numbers else None
        if office == "SLDL" and district and not 1 <= district <= 100:
            return None
        if office == "SLDU" and district and not 1 <= district <= 35:
            return None
        return office, district
    if office == "USH":
        # The first number can be the Congress number; the final one is the district.
        return office, int(numbers[-1]) if numbers else None
    return office, None


def parse_sheet(frame: pd.DataFrame, year: int, county: str, source: Path) -> list[dict]:
    if frame.shape[1] < 3:
        return []
    precincts = [clean(value) for value in frame.iloc[0, 2:].tolist()]
    terminal_total = next(
        (index for index, label in enumerate(precincts) if label.upper() in {"TOTAL", "TOTALS", "GRAND TOTAL"}),
        len(precincts),
    )
    active: tuple[str, int | None] | None = None
    rows: list[dict] = []
    for row_number in range(1, len(frame)):
        first = frame.iat[row_number, 0]
        contest = classify_contest(first)
        if contest:
            active = contest
            continue
        party = normalize_party(frame.iat[row_number, 1] if frame.shape[1] > 1 else None)
        candidate = clean(first)
        # Any labeled non-candidate row ends the prior block. Without this reset,
        # later statewide offices can be incorrectly inherited as governor, etc.
        if candidate and candidate.upper() != "NAN" and party is None:
            active = None
            continue
        if active is None or party is None or not candidate or candidate.upper() == "NAN":
            continue
        office, district = active
        if office in {"SLDL", "SLDU", "USH"} and district is None:
            continue
        for position, precinct in enumerate(precincts):
            if position >= terminal_total:
                break
            offset = position + 2
            if not precinct or precinct.upper() == "NAN" or precinct.upper() in {"SUBTOTAL", "SUBTOTALS"}:
                continue
            vote = pd.to_numeric(frame.iat[row_number, offset], errors="coerce")
            if pd.isna(vote):
                continue
            if vote < 0 or float(vote) != int(vote):
                raise ValueError(f"Invalid vote {vote} in {year} {county} row {row_number + 1}")
            rows.append({
                "state": "AR", "year": year, "county": county.upper(),
                "precinct": precinct.upper(), "office": office, "district": district,
                "candidate": candidate.upper(), "party": party, "votes": int(vote),
                "source_file": source.relative_to(ROOT).as_posix(), "source_sheet": county,
                "source_row": row_number + 1,
            })
    return rows


def build(output: Path = DEFAULT_OUTPUT) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    source_meta = []
    for year, path in SOURCES.items():
        book = workbook(path)
        source_meta.append({"year": year, "path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)})
        for sheet in book.sheet_names:
            sheet_label = clean(sheet).upper()
            if "SUMMARY" in sheet_label or "TOTAL" in sheet_label:
                continue
            frame = pd.read_excel(book, sheet_name=sheet, header=None, dtype=object)
            all_rows.extend(parse_sheet(frame, year, clean(sheet), path))

    observations = pd.DataFrame(all_rows)
    key = ["state", "year", "county", "precinct", "office", "district", "candidate", "party"]
    observations["duplicate_source_rows"] = observations.groupby(key, dropna=False)["votes"].transform("size")
    # Repeated report blocks contain identical returns. Keep one observation and expose multiplicity.
    observations = observations.sort_values(key + ["source_row"]).drop_duplicates(key, keep="first")
    observations = observations.sort_values(key).reset_index(drop=True)

    district = (observations.groupby(["state", "year", "office", "district", "candidate", "party"],
                                     dropna=False, as_index=False)
                .agg(votes=("votes", "sum"), precinct_rows=("precinct", "size"),
                     counties=("county", "nunique")))
    coverage = (observations.groupby(["year", "office"], as_index=False)
                .agg(observation_rows=("votes", "size"), votes=("votes", "sum"),
                     counties=("county", "nunique"), candidates=("candidate", "nunique"),
                     districts=("district", "nunique")))

    # Reconcile the parsed legislative totals to the independent Klarner archive.
    # Klarner remains the outcome source; the precinct rows supply allocation weights.
    from build_historical_southern_legislative_panel import klarner_metadata
    outcomes = klarner_metadata(KLARNER)
    outcomes = outcomes.loc[outcomes["state"].eq("AR") & outcomes["year"].isin(SOURCES)]
    legislative = district.loc[district["office"].isin(["SLDL", "SLDU"]) & district["party"].isin(["DEM", "REP"])]
    parsed = (legislative.pivot_table(index=["state", "year", "office", "district"],
                                      columns="party", values="votes", aggfunc="sum", fill_value=0)
              .reset_index().rename(columns={"DEM": "sos_dem_votes", "REP": "sos_rep_votes"}))
    parsed["chamber"] = parsed["office"].map({"SLDL": "house", "SLDU": "senate"})
    reconciliation = outcomes.merge(
        parsed.drop(columns="office"), on=["state", "year", "chamber", "district"], how="outer", indicator=True
    )
    for column in ["klarner_dem_votes", "klarner_rep_votes", "sos_dem_votes", "sos_rep_votes"]:
        reconciliation[column] = pd.to_numeric(reconciliation[column], errors="coerce")
    reconciliation["dem_vote_delta"] = reconciliation["sos_dem_votes"] - reconciliation["klarner_dem_votes"]
    reconciliation["rep_vote_delta"] = reconciliation["sos_rep_votes"] - reconciliation["klarner_rep_votes"]
    reconciliation["total_absolute_delta"] = reconciliation[["dem_vote_delta", "rep_vote_delta"]].abs().sum(axis=1, min_count=2)
    reconciliation["klarner_major_votes"] = reconciliation[["klarner_dem_votes", "klarner_rep_votes"]].sum(axis=1, min_count=2)
    tolerance = reconciliation["klarner_major_votes"].mul(0.01).clip(lower=10)
    reconciliation["reconciliation_status"] = "missing_one_source"
    complete_votes = reconciliation[["klarner_dem_votes", "klarner_rep_votes", "sos_dem_votes", "sos_rep_votes"]].notna().all(axis=1)
    both = reconciliation["_merge"].eq("both") & complete_votes
    exact = both & reconciliation["total_absolute_delta"].eq(0)
    close = both & ~exact & reconciliation["total_absolute_delta"].le(tolerance)
    reconciliation.loc[exact, "reconciliation_status"] = "exact"
    reconciliation.loc[close, "reconciliation_status"] = "within_one_percent"
    reconciliation.loc[both & ~exact & ~close, "reconciliation_status"] = "material_mismatch"
    reconciliation["model_eligible"] = reconciliation["reconciliation_status"].isin(["exact", "within_one_percent"])
    reconciliation = reconciliation.sort_values(["year", "chamber", "district"]).reset_index(drop=True)

    paths = {
        "observations": output / "arkansas_pre2000_precinct_observations.csv",
        "districts": output / "arkansas_pre2000_district_candidates.csv",
        "coverage": output / "arkansas_pre2000_coverage.csv",
        "reconciliation": output / "arkansas_pre2000_legislative_reconciliation.csv",
    }
    observations.to_csv(paths["observations"], index=False)
    district.to_csv(paths["districts"], index=False)
    coverage.to_csv(paths["coverage"], index=False)
    reconciliation.to_csv(paths["reconciliation"], index=False)
    outputs = [{"name": name, "path": path.relative_to(ROOT).as_posix(), "rows": len(obj),
                "bytes": path.stat().st_size, "sha256": sha256(path)}
               for (name, path), obj in zip(paths.items(), [observations, district, coverage, reconciliation])]
    manifest = {
        "schema_version": 1,
        "pipeline": "scripts/build_arkansas_pre2000_precinct_staging.py",
        "sources": source_meta,
        "row_counts": {"observations": len(observations), "district_candidates": len(district),
                       "coverage": len(coverage), "reconciliation": len(reconciliation),
                       "model_eligible": int(reconciliation["model_eligible"].sum())},
        "outputs": outputs,
    }
    manifest["build_id"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:20]
    (output / "arkansas_pre2000_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.output)
    print(f"Arkansas pre-2000 staging: {result['row_counts']}, build={result['build_id']}")


if __name__ == "__main__":
    main()
