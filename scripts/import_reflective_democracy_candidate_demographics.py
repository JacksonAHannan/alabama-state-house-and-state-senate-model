"""Match Reflective Democracy candidate race records to canonical candidates."""

from __future__ import annotations

import re
import unicodedata
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "raw" / "candidate_demographics" / "RD-Candidate-Analysis-2012-8.zip"
CANDIDATES = ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv"
OUT = ROOT / "data" / "processed" / "elections" / "validation" / "reflective_democracy_candidate_matches.csv"
CATALOG = "https://dss.princeton.edu/catalog/resource6303"


def name_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    text = re.sub(r"\b(JR|SR|II|III|IV)\b", " ", text)
    return re.sub(r"[^A-Z0-9]+", "", text)


def parse_office(value: str) -> tuple[str, int] | tuple[None, None]:
    match = re.search(r"State (House|Representative|Senate|Senator) District\s+(\d+)", str(value), re.I)
    if not match:
        return None, None
    chamber = "senate" if match.group(1).lower() in {"senate", "senator"} else "house"
    return chamber, int(match.group(2))


def main() -> None:
    with ZipFile(ARCHIVE) as archive:
        workbook = archive.read("RD-Candidate-Analysis-2012-8.xlsx")
    rows = []
    for year in (2014, 2018):
        source = pd.read_excel(BytesIO(workbook), sheet_name=str(year))
        source = source[(source.State.eq("AL")) & source["Office Level"].eq("State Legislature")].copy()
        parsed = source["Office Name"].map(parse_office)
        source["chamber"] = parsed.map(lambda value: value[0])
        source["district"] = parsed.map(lambda value: value[1])
        source["name_key"] = source["Candidate Name"].map(name_key)
        source["year"] = year
        rows.append(source)
    source = pd.concat(rows, ignore_index=True)

    candidates = pd.read_csv(CANDIDATES)
    candidates = candidates[candidates.year.isin([2014, 2018])].copy()
    candidates["name_key"] = candidates.canonical_name.map(name_key)
    match = candidates.merge(
        source[["year", "chamber", "district", "name_key", "Candidate Name",
                "Candidate Party", "White/Non-White", "Race"]],
        on=["year", "chamber", "district", "name_key"], how="left", validate="one_to_one",
    )
    match["race_ethnicity"] = match.Race.map({
        "Black or African American": "black",
        "White": "non_black",
    }).fillna("")
    match["black_candidate"] = match.race_ethnicity.map({"black": 1, "non_black": 0})
    match["review_status"] = match.race_ethnicity.map(
        lambda value: "approved_external_dataset" if value else "external_unknown")
    match["evidence_url"] = CATALOG
    match["evidence_quote"] = match.apply(
        lambda row: f"Reflective Democracy Race={row['Race']}" if pd.notna(row.Race) else "", axis=1)
    match["evidence_date"] = match.year.astype(str)
    match["reviewer"] = "Reflective Democracy Campaign"
    match["notes"] = (
        "External research coding; candidate-level source provenance is not included in the workbook. "
        "Use as a sensitivity source and prefer a reviewed primary/biographical source when available."
    )
    columns = [
        "canonical_candidate_id", "person_id", "year", "chamber", "district",
        "canonical_party", "canonical_name", "Candidate Name", "race_ethnicity",
        "black_candidate", "evidence_url", "evidence_quote", "evidence_date",
        "review_status", "reviewer", "notes",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    match[columns].to_csv(OUT, index=False)
    print(match.groupby(["year", "review_status"]).size().to_string())


if __name__ == "__main__":
    main()
