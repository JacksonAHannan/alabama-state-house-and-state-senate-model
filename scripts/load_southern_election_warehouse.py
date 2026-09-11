#!/usr/bin/env python3
"""Stage official Southern returns and load candidate-election facts into SQLite.

The adapters intentionally stop at provider-reported contest geography.  They
do not claim a redistricting vintage that the acquisition manifest did not
record, infer uncontested status, or turn missing files/candidates into zeroes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd

from warehouse import (ROOT, begin_run, connect, finish_run, initialize, register_table,
                       source_file_id)


RAW = ROOT / "data/raw/southern_sos_elections"
AUDIT = ROOT / "data/processed/source_audits"
OUT = ROOT / "data/processed/elections"
SCHEMA = Path(__file__).with_name("warehouse_southern_elections_schema.sql")
SOUTHERN_STATES = ("AL", "AR", "FL", "GA", "KY", "LA", "MS", "MO", "NC", "OK", "SC", "TN", "TX", "VA")
DISTRICT_LIMITS = {
    "AR": {"SLDL": 100, "SLDU": 35}, "FL": {"SLDL": 120, "SLDU": 40},
    "KY": {"SLDL": 100, "SLDU": 38}, "LA": {"SLDL": 105, "SLDU": 39},
    "NC": {"SLDL": 120, "SLDU": 50}, "OK": {"SLDL": 101, "SLDU": 48},
    "SC": {"SLDL": 124, "SLDU": 46}, "TN": {"SLDL": 99, "SLDU": 33},
    "VA": {"SLDL": 100, "SLDU": 40},
}
PROVIDERS = {
    "AR": "Arkansas Secretary of State", "FL": "Florida Division of Elections",
    "GA": "Georgia Secretary of State", "KY": "Kentucky State Board of Elections",
    "LA": "Louisiana Secretary of State", "MS": "Mississippi Secretary of State",
    "MO": "Missouri Secretary of State", "NC": "North Carolina State Board of Elections",
    "OK": "Oklahoma State Election Board", "SC": "South Carolina Election Commission",
    "TN": "Tennessee Secretary of State", "VA": "Virginia Department of Elections",
}
LICENSE = "official public record; reuse terms not recorded in acquisition manifest; review required"


def stable_id(prefix: str, *values: object) -> str:
    token = "|".join("" if value is None else str(value) for value in values)
    return f"{prefix}-{hashlib.sha256(token.encode()).hexdigest()[:20].upper()}"


def clean(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\ufeff", "").strip())


@lru_cache(maxsize=100_000)
def canonical_name(value: object) -> str:
    text = clean(value)
    text = re.sub(r"^\.\s*", "", text)
    text = re.sub(r"\s*(?:-\s*)?\((?:D|R|I|DEM|REP|IND|DEMOCRATIC|REPUBLICAN|INDEPENDENT)\)\s*$", "", text, flags=re.I)
    text = re.sub(r"\s+-\s+(?:D|R|I|DEM|REP|IND)\s*$", "", text, flags=re.I)
    return text.upper()


@lru_cache(maxsize=10_000)
def party_family(value: object) -> str:
    text = clean(value).upper().replace("PARTY", "").strip(" .()-")
    if text in {"D", "DEM", "DEMOCRAT", "DEMOCRATIC"}: return "democratic"
    if text in {"R", "REP", "REPUBLICAN"}: return "republican"
    if text in {"I", "IND", "NPA", "INDEPENDENT", "NO AFFILIATION"}: return "independent"
    if not text: return "unknown"
    return "other"


@lru_cache(maxsize=100_000)
def candidate_and_party(candidate: object, explicit_party: object = None) -> tuple[str, str]:
    name, party = clean(candidate), clean(explicit_party)
    if not party:
        match = re.search(r"\s*(?:-\s*)?\((D|R|I|DEM|REP|IND|DEMOCRATIC|REPUBLICAN|INDEPENDENT)\)\s*$", name, re.I)
        if not match:
            match = re.search(r"\s+-\s+(D|R|I|DEM|REP|IND)\s*$", name, re.I)
        if match:
            party = match.group(1)
    return canonical_name(name), party


def general_election_date(year: int) -> str:
    current = date(year, 11, 2)
    while current.weekday() != 1:
        current += timedelta(days=1)
    return current.isoformat()


@lru_cache(maxsize=10_000)
def normalize_date(value: object, year: int) -> tuple[str, str]:
    text = clean(value)
    if text:
        parsed = pd.to_datetime(text, errors="coerce")
        if not pd.isna(parsed): return parsed.date().isoformat(), "observed"
        if re.fullmatch(r"\d{8}", text):
            return datetime.strptime(text, "%Y%m%d").date().isoformat(), "observed"
    return general_election_date(year), "derived"


@lru_cache(maxsize=10_000)
def normalize_stage(value: object, office: str = "") -> tuple[str, str]:
    original = clean(value) or "general"
    text = original.lower().replace("_", " ")
    if "special" in text and "runoff" in text: return "special_runoff", original
    if "special" in text: return "special", original
    if "primary" in text and "runoff" in text: return "primary_runoff", original
    if "primary" in text: return "primary", original
    if "runoff" in text: return "other", original
    # Louisiana's first round is the regular general election under its open-primary system.
    if "first round" in text or "first_round" in clean(value).lower(): return "general", original
    return "general", original


@lru_cache(maxsize=100_000)
def classify_office(label: object, district_value: object = None) -> tuple[str, str | None, str | None] | None:
    original = clean(label)
    text = original.upper().replace("U. S.", "U.S.")
    reported_district = clean(district_value)
    numeric_district = re.fullmatch(r"0*(\d+)(?:\.0+)?", reported_district)
    district = str(int(numeric_district.group(1))) if numeric_district else None
    if text in {"USP", "USS", "GOV"}: return text, None, None
    if text == "USH": return text, None, district
    if text == "SLDL": return text, "lower", district
    if text == "SLDU": return text, "upper", district
    if district is None:
        matches = re.findall(r"DIST(?:RICT|\.)?\s*[,#:;-]?\s*(\d{1,3})|\b(\d{1,3})(?:ST|ND|RD|TH)\s+DIS", text)
        numbers = [left or right for left, right in matches]
        district = str(int(numbers[-1])) if numbers else None
    if district is None:
        fallback_patterns = (
            r"\b(\d{1,3})(?:ST|ND|RD|TH)?\s+(?:SENATORIAL|REPRESENTATIVE)\s+DISTRICT\b",
            r"\b(?:STATE SENATOR|STATE REPRESENTATIVE|NC HOUSE|NC SENATE)\s*\(?\s*(\d{1,3})\s*\)?\s*$",
            r"\b(?:NC HOUSE|NC SENATE)\s*\(\s*(\d{1,3})\s*\)\s*$",
            r"\b(\d{1,3})(?:ST|ND|RD|TH)?\s+DI(?:S)?\s*$",
        )
        for pattern in fallback_patterns:
            match = re.search(pattern, text)
            if match:
                district = str(int(match.group(1))); break
    if re.search(r"PRESIDENT", text): return "USP", None, None
    if re.search(r"\bU\.?S\.?\s+SENAT|UNITED STATES SENAT", text): return "USS", None, None
    if re.search(r"\bU\.?S\.?\s+HOUSE|UNITED STATES HOUSE|\bU\.?S\.?\s+REPRESENTATIVE|CONGRESS", text):
        return "USH", None, district
    if (re.search(r"STATE HOUSE|STATE REPRESENTATIVE|KY REPRESENTATIVE|HOUSE OF DELEGATES|TENNESSEE HOUSE|NC HOUSE", text)
            and not re.search(r"\bU\.?S\.?\b|UNITED STATES", text)):
        return "SLDL", "lower", district
    if (re.search(r"STATE SENAT|STATE SENATOR|KY SENATOR|TENNESSEE SENATE|NC SENATE", text)
            and not re.search(r"\bU\.?S\.?\b|UNITED STATES", text)):
        return "SLDU", "upper", district
    if text.startswith("GOVERNOR") or text.startswith("FOR GOVERNOR"):
        return "GOV", None, None
    return None


def manifest_rows(root: Path = ROOT) -> list[dict]:
    paths = [root / "data/processed/source_audits/southern_sos_download_manifest.csv",
             root / "data/processed/source_audits/louisiana_legislative_results_manifest.csv"]
    by_path: dict[str, dict] = {}
    for manifest in paths:
        if not manifest.exists(): continue
        for record in pd.read_csv(manifest, dtype=str).fillna("").to_dict("records"):
            local = str(record.get("local_path", "")).replace("\\", "/")
            if not local or not (root / local).exists(): continue
            current = by_path.get(local, {})
            # Prefer the stage-aware Louisiana manifest when it supplies richer metadata.
            by_path[local] = {**current, **{key: value for key, value in record.items() if value != ""}}
    return [dict(record, local_path=path) for path, record in sorted(by_path.items())]


def add_result(rows: list[dict], *, state: str, year: int, election_date: object, stage: object,
               office: object, candidate: object, party: object, votes: object, source_path: str,
               district: object = None, units: int = 1, coverage: str = "official_result") -> bool:
    classification = classify_office(office, district)
    numeric = pd.to_numeric(votes, errors="coerce")
    if classification is None or pd.isna(numeric) or numeric < 0 or float(numeric) != int(numeric): return False
    name, original_party = candidate_and_party(candidate, party)
    if not name: return False
    office_code, chamber, normalized_district = classification
    observed_date, date_status = normalize_date(election_date, year)
    normalized_stage, stage_original = normalize_stage(stage, clean(office))
    rows.append({
        "state_code": state, "cycle": int(year), "election_date": observed_date,
        "election_date_status": date_status, "election_stage": normalized_stage,
        "election_stage_original": stage_original, "office_code": office_code,
        "office_original": clean(office), "chamber": chamber, "district": normalized_district,
        "district_original": clean(district) or normalized_district, "candidate_name": name,
        "candidate_original": clean(candidate), "party_original": original_party or None,
        "party_family": party_family(original_party), "votes": int(numeric),
        "reported_geography_count": max(1, int(units)), "source_coverage": coverage,
        "source_path": source_path,
    })
    return True


def collapse_file(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    keys = ("state_code", "cycle", "election_date", "election_date_status", "election_stage",
            "election_stage_original", "office_code", "office_original", "chamber", "district",
            "district_original", "candidate_name", "party_family", "party_original", "source_coverage",
            "source_path")
    for row in rows:
        key = tuple(row.get(column) for column in keys)
        if key not in grouped:
            grouped[key] = {column: row.get(column) for column in keys}
            grouped[key].update(votes=0, reported_geography_count=0, candidate_originals=set())
        grouped[key]["votes"] += row["votes"]
        grouped[key]["reported_geography_count"] += row["reported_geography_count"]
        grouped[key]["candidate_originals"].add(row["candidate_original"])
    return list(grouped.values())


def reconciliation(path: str, parser: str, raw_rows: int, raw_votes: int | None,
                   output: list[dict], note: str | None = None) -> dict:
    output_votes = sum(row["votes"] for row in output)
    status = "exact" if raw_votes is not None and raw_votes == output_votes else "not_available"
    return {"source_path": path, "parser_name": parser, "input_candidate_rows": raw_rows,
            "output_candidate_rows": len(output), "input_votes": raw_votes,
            "output_votes": output_votes, "vote_delta": None if raw_votes is None else output_votes - raw_votes,
            "reconciliation_status": status, "note": note}


def parse_arkansas_json(path: Path, meta: dict) -> tuple[list[dict], dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    info = payload["ElectionInfo"]; year = int(pd.to_datetime(info["ElectionDate"]).year)
    rows, raw_rows, raw_votes = [], 0, 0
    for contest in payload["ContestData"]:
        if classify_office(contest.get("ContestName")) is None: continue
        for candidate in contest.get("Candidates", []):
            votes = candidate.get("TotalVotes")
            if add_result(rows, state="AR", year=year, election_date=info.get("ElectionDate"),
                          stage=info.get("ElectionName"), office=contest.get("ContestName"),
                          candidate=candidate.get("Name"), party=candidate.get("PartyName"), votes=votes,
                          source_path=meta["local_path"], units=contest.get("TotalPrecincts") or 1,
                          coverage="official_state_or_district_total"):
                raw_rows += 1; raw_votes += int(votes)
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "arkansas_tally_json", raw_rows, raw_votes, output)


def parse_arkansas_pipe_zip(path: Path, meta: dict) -> tuple[list[dict], dict]:
    rows, raw_rows, raw_votes = [], 0, 0
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.lower().endswith(".txt"): continue
            content = archive.read(member).decode("utf-8-sig", errors="replace").replace("\x00", "")
            lines = content.splitlines()
            header_index = next((i for i, line in enumerate(lines) if line.startswith("Office|")), None)
            if header_index is None: continue
            header = next(csv.reader([lines[header_index]], delimiter="|"))
            for fields in csv.reader(lines[header_index + 1:], delimiter="|"):
                if len(fields) < 4: continue
                votes = [pd.to_numeric(value, errors="coerce") for value in fields[3:len(header)]]
                numeric = [int(value) for value in votes if not pd.isna(value)]
                total = sum(numeric)
                if add_result(rows, state="AR", year=int(meta["election_year"]), election_date=meta.get("election_date"),
                              stage="general", office=fields[0], candidate=fields[1], party=fields[2], votes=total,
                              source_path=meta["local_path"], units=max(1, len(numeric)),
                              coverage="official_precinct_aggregate"):
                    raw_rows += len(numeric); raw_votes += total
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "arkansas_pipe_precinct_zip", raw_rows, raw_votes, output)


def parse_arkansas_workbook(path: Path, meta: dict) -> tuple[list[dict], dict]:
    rows, raw_rows, raw_votes = [], 0, 0
    for sheet in pd.ExcelFile(path).sheet_names:
        frame = pd.read_excel(path, sheet_name=sheet, dtype=object)
        columns = {clean(column).lower(): column for column in frame.columns}
        if not {"race", "candidate", "votes"}.issubset(columns): continue
        for record in frame.to_dict("records"):
            votes = record.get(columns["votes"])
            if add_result(rows, state="AR", year=int(meta["election_year"]), election_date=meta.get("election_date"),
                          stage="general", office=record.get(columns["race"]), candidate=record.get(columns["candidate"]),
                          party=record.get(columns.get("party")) if columns.get("party") else None, votes=votes,
                          source_path=meta["local_path"], units=1, coverage="official_precinct_aggregate"):
                raw_rows += 1; raw_votes += int(votes)
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "arkansas_precinct_workbook", raw_rows, raw_votes, output)


def parse_florida_zip(path: Path, meta: dict) -> tuple[list[dict], dict]:
    rows, raw_rows, raw_votes = [], 0, 0
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if member.endswith("/") or not member.lower().endswith(".txt"): continue
            payload = archive.read(member)
            encoding = "utf-16" if b"\x00" in payload[:2000] and payload[:2] in {b"\xff\xfe", b"\xfe\xff"} else "utf-8-sig"
            content = payload.decode(encoding, errors="replace").replace("\x00", "")
            for fields in csv.reader(io.StringIO(content), delimiter="\t"):
                if len(fields) < 19: continue
                if add_result(rows, state="FL", year=int(meta["election_year"]), election_date=fields[3],
                              stage=fields[4], office=f"{fields[11]} {fields[12]}", candidate=fields[14],
                              party=fields[15], votes=fields[18], source_path=meta["local_path"],
                              units=1, coverage="official_precinct_aggregate"):
                    raw_rows += 1; raw_votes += int(fields[18])
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "florida_precinct_zip", raw_rows, raw_votes, output)


def parse_louisiana_csv(path: Path, meta: dict) -> tuple[list[dict], dict]:
    frame = pd.read_csv(path, dtype=str).fillna("")
    if len(frame.columns) <= 4: raise ValueError("Louisiana result has no candidate columns")
    rows, raw_rows, raw_votes = [], 0, 0
    units = len(frame)
    for candidate_column in frame.columns[4:]:
        name, party = candidate_and_party(candidate_column)
        votes = pd.to_numeric(frame[candidate_column], errors="coerce")
        total = int(votes.dropna().sum())
        if add_result(rows, state="LA", year=int(meta["election_year"]), election_date=meta.get("election_date"),
                      stage=meta.get("election_stage", "first_round"), office=frame.iloc[0, 0],
                      candidate=name, party=party, votes=total, source_path=meta["local_path"], units=units,
                      coverage="official_precinct_aggregate"):
            raw_rows += int(votes.notna().sum()); raw_votes += total
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "louisiana_by_precinct_csv", raw_rows, raw_votes, output)


def parse_north_carolina_zip(path: Path, meta: dict) -> tuple[list[dict], dict]:
    rows, raw_rows, raw_votes = [], 0, 0
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if member.endswith("/"): continue
            payload = archive.read(member)
            encoding = "utf-16" if b"\x00" in payload[:2000] and payload[:2] in {b"\xff\xfe", b"\xfe\xff"} else "utf-8-sig"
            content = payload.decode(encoding, errors="replace").replace("\x00", "")
            if content.strip().lower().startswith("data unavailable"): continue
            first_line = content.splitlines()[0] if content.splitlines() else ""
            delimiter = "\t" if first_line.count("\t") > first_line.count(",") else ","
            first_fields = next(csv.reader([first_line], delimiter=delimiter), [])
            if not first_fields or clean(first_fields[0]).lower() != "county":
                for fields in csv.reader(io.StringIO(content), delimiter=delimiter):
                    if len(fields) < 8: continue
                    parsed_date = pd.to_datetime(fields[1], errors="coerce")
                    stage = "primary" if not pd.isna(parsed_date) and parsed_date.month in {3, 4, 5, 6, 7, 8, 9} else "general"
                    if add_result(rows, state="NC", year=int(meta["election_year"]), election_date=fields[1], stage=stage,
                                  office=fields[4], candidate=fields[5], party=fields[6], votes=fields[7],
                                  source_path=meta["local_path"], units=1, coverage="official_precinct_aggregate"):
                        raw_rows += 1; raw_votes += int(float(fields[7]))
                continue
            reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
            filename_date = re.search(r"(20\d{6})", path.name)
            fallback_date = filename_date.group(1) if filename_date else None
            for raw_record in reader:
                record = {clean(key).lower(): value for key, value in raw_record.items() if key is not None}
                election_date = record.get("election date") or record.get("election_dt") or fallback_date
                parsed_date = pd.to_datetime(election_date, errors="coerce")
                stage = "primary" if not pd.isna(parsed_date) and parsed_date.month in {3, 4, 5, 6, 7, 8, 9} else "general"
                office = record.get("contest name") or record.get("contest_name") or record.get("contest")
                candidate = record.get("choice") or record.get("name_on_ballot")
                party = record.get("choice party") or record.get("party") or record.get("party_cd")
                votes = record.get("total votes") or record.get("ballot_count")
                if add_result(rows, state="NC", year=int(meta["election_year"]), election_date=election_date, stage=stage,
                              office=office, district=record.get("district"), candidate=candidate, party=party, votes=votes,
                              source_path=meta["local_path"], units=1, coverage="official_precinct_aggregate"):
                    raw_rows += 1; raw_votes += int(float(votes))
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "north_carolina_precinct_zip", raw_rows, raw_votes, output)


def parse_oklahoma_zip(path: Path, meta: dict) -> tuple[list[dict], dict]:
    rows, raw_rows, raw_votes = [], 0, 0
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not members: raise ValueError("No CSV in Oklahoma ZIP")
        with archive.open(members[0]) as binary, io.TextIOWrapper(binary, encoding="utf-8-sig", errors="replace", newline="") as stream:
            for record in csv.DictReader(stream):
                votes = record.get("cand_tot_votes")
                if add_result(rows, state="OK", year=int(meta["election_year"]), election_date=record.get("elec_date"),
                              stage="general", office=record.get("race_description"), candidate=record.get("cand_name"),
                              party=record.get("cand_party"), votes=votes, source_path=meta["local_path"], units=1,
                              coverage="official_precinct_aggregate"):
                    raw_rows += 1; raw_votes += int(votes)
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "oklahoma_precinct_zip", raw_rows, raw_votes, output)


def parse_virginia_csv(path: Path, meta: dict) -> tuple[list[dict], dict]:
    rows, raw_rows, raw_votes = [], 0, 0
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as stream:
        for record in csv.DictReader(stream):
            office = record.get("OfficeTitle", "")
            district = record.get("DistrictName") if record.get("DistrictType") in {"House of Delegates", "State Senate", "Congressional"} else None
            candidate = " ".join(filter(None, [record.get("FirstName"), record.get("MiddleName"), record.get("LastName"), record.get("Suffix")]))
            if not candidate.strip(): candidate = record.get("LastName", "")
            votes = record.get("TOTAL_VOTES")
            if add_result(rows, state="VA", year=int(meta["election_year"]), election_date=record.get("ElectionDate"),
                          stage=record.get("ElectionType"), office=office, district=district, candidate=candidate,
                          party=record.get("Party"), votes=votes, source_path=meta["local_path"], units=1,
                          coverage="official_precinct_aggregate"):
                raw_rows += 1; raw_votes += int(votes)
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "virginia_precinct_csv", raw_rows, raw_votes, output)


def parse_tennessee_workbook(path: Path, meta: dict) -> tuple[list[dict], dict]:
    frame = pd.read_excel(path, sheet_name=0, dtype=object)
    columns = {clean(column).upper(): column for column in frame.columns}
    county_col = columns.get("COUNTY"); precinct_col = columns.get("PRECINCT") or columns.get("PRECINCT NAME")
    office_col = columns.get("OFFICENAME"); date_col = columns.get("ELECTDATE"); stage_col = columns.get("ELECTTYPE")
    district_col = columns.get("DISTRICT") or columns.get("JURISID")
    rows, raw_rows, raw_votes = [], 0, 0
    for record in frame.to_dict("records"):
        office = record.get(office_col) if office_col else None
        if classify_office(office, record.get(district_col) if district_col else None) is None: continue
        for number in range(1, 11):
            name_col = columns.get(f"BNAME{number}") or columns.get(f"RNAME{number}")
            vote_col = columns.get(f"TALLY{number}") or columns.get(f"PVTALLY{number}")
            party_col = columns.get(f"PARTY{number}")
            if not name_col or not vote_col: continue
            if add_result(rows, state="TN", year=int(meta["election_year"]),
                          election_date=record.get(date_col) if date_col else None,
                          stage=record.get(stage_col) if stage_col else "general", office=office,
                          district=record.get(district_col) if district_col else None, candidate=record.get(name_col),
                          party=record.get(party_col) if party_col else None, votes=record.get(vote_col),
                          source_path=meta["local_path"], units=1, coverage="official_precinct_aggregate"):
                raw_rows += 1; raw_votes += int(record[vote_col])
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "tennessee_precinct_workbook", raw_rows, raw_votes, output)


def parse_south_carolina_zip(path: Path, meta: dict) -> tuple[list[dict], dict]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        text = archive.read(members[0]).decode("utf-8-sig", errors="replace")
    lines = text.splitlines(); rows, raw_rows, raw_votes = [], 0, 0
    index = 0
    while index < len(lines):
        office_line = clean(lines[index])
        if "(Vote For" not in office_line or classify_office(office_line) is None:
            index += 1; continue
        candidate_index = index + 1
        while candidate_index < len(lines) and not clean(lines[candidate_index]): candidate_index += 1
        header_index = candidate_index + 1
        while header_index < len(lines) and not clean(lines[header_index]).startswith("Precinct"): header_index += 1
        candidate_line = lines[candidate_index] if candidate_index < len(lines) else ""
        candidates = [clean(candidate_line[start:start + 60]) for start in range(60, len(candidate_line), 60)]
        candidates = [candidate for candidate in candidates if candidate]
        total_index = header_index + 1
        while total_index < len(lines) and not clean(lines[total_index]).startswith("Totals:"): total_index += 1
        if candidates and total_index < len(lines):
            cells = [clean(lines[total_index][start:start + 30]) for start in range(0, len(lines[total_index]), 30)]
            for position, candidate in enumerate(candidates):
                vote_index = 3 + 2 * position
                votes = cells[vote_index] if vote_index < len(cells) else ""
                if add_result(rows, state="SC", year=int(meta["election_year"]), election_date=meta.get("election_date"),
                              stage="general", office=office_line, candidate=candidate, party=None, votes=votes,
                              source_path=meta["local_path"], units=1, coverage="official_county_total_component"):
                    raw_rows += 1; raw_votes += int(votes)
        index = max(index + 1, total_index + 1)
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "south_carolina_detail_zip", raw_rows, raw_votes, output,
                                  "Fixed-width county totals; party labels are absent from the provider export")


def parse_kentucky_summary(path: Path, meta: dict) -> tuple[list[dict], dict]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    rows, raw_rows, raw_votes, active = [], 0, 0, None
    for line in text.splitlines():
        if "OFF/DST/DIV:" in line:
            label = re.sub(r"^.*?OFF/DST/DIV:\s*\S+\s*", "", line)
            label = re.split(r"PRECINCTS REP:", label)[0].strip()
            active = label if classify_office(label) else None
            continue
        if active is None: continue
        match = re.match(r"^\s{4}(\S+)\s{7}(.+?)\s{2,}([\d,]+)\s+\d+(?:\.\d+)?%", line)
        if not match: continue
        party, candidate, votes = match.groups(); numeric = int(votes.replace(",", ""))
        if add_result(rows, state="KY", year=int(meta["election_year"]), election_date=meta.get("election_date"),
                      stage="general", office=active, candidate=candidate, party=party, votes=numeric,
                      source_path=meta["local_path"], units=1, coverage="official_state_or_district_total"):
            raw_rows += 1; raw_votes += numeric
    output = collapse_file(rows)
    return output, reconciliation(meta["local_path"], "kentucky_state_summary", raw_rows, raw_votes, output)


KY_SUMMARIES = {
    "data/raw/southern_sos_elections/KY/2000/00Gen_Statewidebyoffice.txt",
    "data/raw/southern_sos_elections/KY/2002/2002statebyoffice.txt",
    "data/raw/southern_sos_elections/KY/2004/2004statebyoffice.txt",
    "data/raw/southern_sos_elections/KY/2006/STATEwidebyoffice.txt",
    "data/raw/southern_sos_elections/KY/2008/STATEwide_by_office_gen_08.txt",
}


def adapter_for(meta: dict):
    path, state = Path(meta["local_path"]), meta.get("state", "")
    suffix = path.suffix.lower()
    if state == "AR" and suffix == ".json" and "FullDataFile" in path.name: return parse_arkansas_json
    if state == "AR" and path.name.lower() == "general2000p.zip": return parse_arkansas_pipe_zip
    if state == "AR" and suffix == ".xlsx" and "2010_General_Election_Results" in path.name: return parse_arkansas_workbook
    if state == "FL" and suffix == ".zip" and "gen" in path.name.lower(): return parse_florida_zip
    if state == "LA" and suffix == ".csv" and path.name.startswith("ByPrecinct_"): return parse_louisiana_csv
    if state == "NC" and suffix == ".zip": return parse_north_carolina_zip
    if state == "OK" and suffix == ".zip" and "PrecinctResults" in path.name: return parse_oklahoma_zip
    if state == "SC" and suffix == ".zip" and "detailtxt" in path.name.lower(): return parse_south_carolina_zip
    if state == "TN" and suffix in {".xls", ".xlsx"}: return parse_tennessee_workbook
    if state == "VA" and suffix == ".csv" and "General" in path.name: return parse_virginia_csv
    if meta["local_path"] in KY_SUMMARIES: return parse_kentucky_summary
    return None


def load_arkansas_pre2000(root: Path = ROOT) -> tuple[list[dict], list[str], list[dict]]:
    source = root / "data/processed/precinct_history/arkansas_pre2000/arkansas_pre2000_district_candidates.csv"
    if not source.exists(): return [], [], []
    frame = pd.read_csv(source)
    rows, paths = [], []
    source_paths = {
        1994: "data/raw/southern_sos_elections/AR/1994/94general_election_results.xls",
        1996: "data/raw/southern_sos_elections/AR/1996/precinct.xls",
        1998: "data/raw/southern_sos_elections/AR/1998/Gen98Ver5.zip",
    }
    for record in frame.to_dict("records"):
        path = source_paths[int(record["year"])]
        if add_result(rows, state="AR", year=int(record["year"]), election_date=None, stage="general",
                      office=record["office"], district=record.get("district"), candidate=record["candidate"],
                      party=record["party"], votes=record["votes"], source_path=path,
                      units=record.get("precinct_rows", 1), coverage="official_precinct_aggregate"):
            paths.append(path)
    output = collapse_file(rows)
    audits = []
    for relative in sorted(set(paths)):
        year = int(Path(relative).parts[-2])
        input_rows = int(frame.year.eq(year).sum())
        input_votes = int(frame.loc[frame.year.eq(year), "votes"].sum())
        file_output = [row for row in output if row["source_path"] == relative]
        audits.append(reconciliation(relative, "arkansas_pre2000_validated_staging", input_rows,
                                     input_votes, file_output,
                                     "Imported from the independently validated Arkansas pre-2000 staging build"))
    return output, sorted(set(paths)), audits


def combine_results(rows: Iterable[dict]) -> list[dict]:
    """Combine non-overlapping county/file components at candidate-contest grain."""
    grouped: dict[tuple, dict] = {}
    keys = ("state_code", "cycle", "election_date", "election_stage", "office_code", "chamber",
            "district", "candidate_name", "party_family")
    for row in rows:
        key = tuple(row.get(column) for column in keys)
        if key not in grouped:
            grouped[key] = {column: row.get(column) for column in keys}
            grouped[key].update(votes=0, reported_geography_count=0, candidate_originals=set(),
                                office_originals=set(), district_originals=set(), party_originals=set(),
                                stage_originals=set(), date_statuses=set(), source_paths=set(), coverages=set())
        current = grouped[key]
        current["votes"] += int(row["votes"])
        current["reported_geography_count"] += int(row["reported_geography_count"])
        current["candidate_originals"].update(row.get("candidate_originals", {row.get("candidate_original", "")}))
        current["office_originals"].add(row["office_original"])
        current["district_originals"].add(row.get("district_original"))
        current["party_originals"].add(row.get("party_original"))
        current["stage_originals"].add(row.get("election_stage_original"))
        current["date_statuses"].add(row.get("election_date_status"))
        current["source_paths"].add(row["source_path"])
        current["coverages"].add(row["source_coverage"])
    results = list(grouped.values())
    for row in results:
        row["district_original"] = "|".join(sorted(clean(value) for value in row["district_originals"] if clean(value))) or None
        row["party_original"] = "|".join(sorted(clean(value) for value in row["party_originals"] if clean(value))) or None
        row["election_stage_original"] = "|".join(sorted(clean(value) for value in row["stage_originals"] if clean(value)))
        row["election_date_status"] = "observed" if "observed" in row["date_statuses"] else "derived"
    contest_groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in results:
        contest_key = (row["state_code"], row["election_date"], row["election_stage"], row["office_code"], row["district"])
        contest_groups[contest_key].append(row)
    for contest_key, candidates in contest_groups.items():
        total = sum(row["votes"] for row in candidates)
        contest_id = stable_id("CONTEST", *contest_key)
        election_id = stable_id("ELECTION", contest_key[0], contest_key[1], contest_key[2])
        for row in candidates:
            row["contest_id"], row["election_id"] = contest_id, election_id
            row["candidate_election_id"] = stable_id("CE", contest_id, row["candidate_name"], row["party_family"])
            row["vote_share"] = row["votes"] / total if total else None
            row["observed_candidate_count"] = len(candidates)
    return sorted(results, key=lambda row: (row["state_code"], row["election_date"], row["office_code"], row["district"] or "", row["candidate_name"]))


def result_validation_status(row: dict) -> str:
    if row["office_code"] not in {"SLDL", "SLDU"}: return "passed"
    if row.get("district") is None: return "review"
    try: district = int(row["district"])
    except (TypeError, ValueError): return "review"
    limit = DISTRICT_LIMITS.get(row["state_code"], {}).get(row["office_code"])
    return "passed" if limit is not None and 1 <= district <= limit else "review"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def media_type(path: Path) -> str | None:
    return {".csv": "text/csv", ".txt": "text/plain", ".json": "application/json",
            ".html": "text/html", ".htm": "text/html", ".pdf": "application/pdf",
            ".zip": "application/zip", ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}.get(path.suffix.lower())


def upsert_source(connection: sqlite3.Connection, root: Path, meta: dict, parsed_paths: set[str],
                  rejected: dict[str, str]) -> str:
    relative = meta["local_path"].replace("\\", "/"); path = root / relative
    state = meta.get("state", ""); provider = PROVIDERS.get(state, f"{state} election authority")
    existing = connection.execute("SELECT source_file_id FROM warehouse_source_file WHERE local_path=?", (relative,)).fetchone()
    identifier = existing[0] if existing else source_file_id(provider, relative)
    parsed = relative in parsed_paths
    extraction = "failed" if relative in rejected else ("normalized" if parsed else "registered")
    scope = "official_reported_election_results" if meta.get("coverage") in {"precinct", "county", "district", "statewide"} else "archive_discovery_or_report"
    connection.execute("""INSERT INTO warehouse_source_file
      (source_file_id,provider,local_path,original_url,retrieved_at_utc,sha256,media_type,license,extraction_status,authoritative_scope)
      VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_file_id) DO UPDATE SET
      original_url=excluded.original_url,retrieved_at_utc=excluded.retrieved_at_utc,sha256=excluded.sha256,
      media_type=excluded.media_type,license=excluded.license,extraction_status=excluded.extraction_status,
      authoritative_scope=excluded.authoritative_scope""",
      (identifier, provider, relative, meta.get("official_url"), meta.get("retrieved_at") or datetime.now(timezone.utc).isoformat(),
       meta.get("sha256") or sha256(path), meta.get("media_type") or media_type(path), LICENSE, extraction, scope))
    ingest = "rejected" if relative in rejected else ("superseded" if meta.get("duplicate_of") else ("parsed" if parsed else "acquired"))
    cycle = int(meta["election_year"]) if clean(meta.get("election_year")) else None
    election_date = normalize_date(meta.get("election_date"), cycle)[0] if cycle and clean(meta.get("election_date")) else None
    connection.execute("""INSERT INTO source_southern_election_file VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(source_file_id) DO UPDATE SET cycle=excluded.cycle,election_date=excluded.election_date,
      election_stage_original=excluded.election_stage_original,ingest_status=excluded.ingest_status,
      coverage_original=excluded.coverage_original,parser_name=excluded.parser_name,parser_message=excluded.parser_message""",
      (identifier, state, cycle, election_date, meta.get("election_stage"),
       "provider-reported election geography; plan vintage not independently verified", LICENSE, scope, ingest,
       meta.get("coverage"), adapter_for(meta).__name__ if adapter_for(meta) else None, rejected.get(relative)))
    return identifier


def coverage_rows(manifest: list[dict], results: list[dict], rejected: dict[str, str], run_id: str) -> list[dict]:
    result_counts = defaultdict(int)
    for row in results: result_counts[(row["state_code"], row["cycle"])] += 1
    file_counts = defaultdict(int); acquisition = {}
    for meta in manifest:
        state = meta.get("state", ""); year = int(meta["election_year"]) if clean(meta.get("election_year")) else None
        if state and year:
            file_counts[(state, year)] += 1
            acquisition[(state, year)] = "downloaded"
    inventory_path = AUDIT / "southern_sos_precinct_inventory.csv"
    if inventory_path.exists():
        for record in pd.read_csv(inventory_path, dtype=str).fillna("").to_dict("records"):
            key = (record["state"], int(record["election_year"]))
            acquisition.setdefault(key, record["status"])
    keys = set(acquisition) | set(result_counts)
    for state in SOUTHERN_STATES:
        if not any(key[0] == state for key in keys): keys.add((state, None))
    rows = []
    for state, year in sorted(keys, key=lambda item: (item[0], item[1] or 0)):
        count = result_counts[(state, year)]
        if count: status, limitation = "parsed", None
        elif state == "AL": status, limitation = "existing_canonical", "Alabama remains in fact_candidate_election and was not reacquired"
        elif state == "TX": status, limitation = "external_repository", "Texas results remain in the companion Texas repository"
        elif state in {"GA", "MO"}: status, limitation = "not_acquired", "Official bulk results were unavailable to automated acquisition"
        elif state == "MS": status, limitation = "review_queue", "Downloaded county recaps are PDF-only and require a validated extraction adapter"
        else: status, limitation = "registered_unparsed", "No validated adapter for the acquired artifact format"
        rows.append({"state_code": state, "cycle": year, "acquisition_status": acquisition.get((state, year), "external_or_missing"),
                     "normalization_status": status, "source_files": file_counts[(state, year)],
                     "candidate_results": count, "limitation": limitation, "build_run_id": run_id})
    return rows


def export_loaded(database: Path | None = None, run_id: str | None = None) -> dict:
    with closing(connect(database, readonly=True)) as connection:
        if run_id is None:
            latest = connection.execute("""SELECT build_run_id FROM warehouse_build_run
              WHERE target='southern_official_election_results' AND status='validated'
              ORDER BY completed_at_utc DESC LIMIT 1""").fetchone()
            if latest is None: raise ValueError("No validated Southern election warehouse run exists")
            run_id = latest[0]
        run = connection.execute("SELECT code_commit,validation_json FROM warehouse_build_run WHERE build_run_id=?", (run_id,)).fetchone()
        if run is None: raise ValueError(f"Unknown build run: {run_id}")
        export = pd.read_sql_query("SELECT * FROM source_southern_candidate_election WHERE build_run_id=? ORDER BY state_code,election_date,office_code,district,candidate_name",
                                   connection, params=(run_id,))
        coverage = pd.read_sql_query("SELECT * FROM qa_southern_election_coverage WHERE build_run_id=? ORDER BY state_code,cycle",
                                     connection, params=(run_id,))
        audits = pd.read_sql_query("""SELECT r.* FROM qa_southern_election_reconciliation r
          JOIN source_southern_election_file f USING(source_file_id) ORDER BY f.state_code,f.cycle,r.source_file_id""", connection)
    OUT.mkdir(parents=True, exist_ok=True); AUDIT.mkdir(parents=True, exist_ok=True)
    export.to_csv(OUT / "southern_state_candidate_results.csv.gz", index=False,
                  compression={"method": "gzip", "mtime": 0})
    coverage.to_csv(AUDIT / "southern_sos_normalization_coverage.csv", index=False)
    audits.to_csv(AUDIT / "southern_sos_normalization_reconciliation.csv", index=False)
    validation = json.loads(run[1])
    build_manifest = {"contract_version": 1, "pipeline": "scripts/load_southern_election_warehouse.py",
                      "build_run_id": run_id, "validation": validation,
                      "outputs": ["data/processed/elections/southern_state_candidate_results.csv.gz",
                                  "data/processed/source_audits/southern_sos_normalization_coverage.csv",
                                  "data/processed/source_audits/southern_sos_normalization_reconciliation.csv"],
                      "code_version": run[0]}
    (AUDIT / "southern_sos_normalization_manifest.json").write_text(json.dumps(build_manifest, indent=2) + "\n", encoding="utf-8")
    return build_manifest


def build(root: Path = ROOT, database: Path | None = None) -> dict:
    manifest = manifest_rows(root)
    parsed_rows, audits, parsed_paths, rejected = [], [], set(), {}
    for meta in manifest:
        adapter = adapter_for(meta)
        if adapter is None: continue
        path = root / meta["local_path"]
        try:
            rows, audit = adapter(path, meta)
            if rows:
                parsed_rows.extend(rows); audits.append(audit); parsed_paths.add(meta["local_path"])
        except (ValueError, KeyError, zipfile.BadZipFile, pd.errors.ParserError, csv.Error) as error:
            rejected[meta["local_path"]] = f"{type(error).__name__}: {error}"
            audits.append({"source_path": meta["local_path"], "parser_name": adapter.__name__,
                           "input_candidate_rows": 0, "output_candidate_rows": 0, "input_votes": None,
                           "output_votes": None, "vote_delta": None, "reconciliation_status": "rejected",
                           "note": rejected[meta["local_path"]]})
    historical, historical_paths, historical_audits = load_arkansas_pre2000(root)
    parsed_rows.extend(historical); parsed_paths.update(historical_paths); audits.extend(historical_audits)
    results = combine_results(parsed_rows)

    with closing(connect(database)) as connection:
        initialize(connection); connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run_id = begin_run(connection, "southern_official_election_results", {
            "contract_version": 1, "states": list(SOUTHERN_STATES), "manifest_files": len(manifest)})
        connection.commit(); connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM bridge_southern_candidate_result_source")
        connection.execute("DELETE FROM source_southern_candidate_election")
        connection.execute("DELETE FROM qa_southern_election_reconciliation")
        connection.execute("DELETE FROM qa_southern_election_coverage")
        source_ids = {meta["local_path"]: upsert_source(connection, root, meta, parsed_paths, rejected) for meta in manifest}
        # Derived Arkansas staging still points only to immutable raw source files.
        for relative in historical_paths:
            if relative not in source_ids:
                state, year = "AR", int(Path(relative).parts[-2])
                synthetic = {"state": state, "election_year": str(year), "local_path": relative,
                             "coverage": "precinct", "official_url": None, "retrieved_at": None,
                             "sha256": sha256(root / relative)}
                source_ids[relative] = upsert_source(connection, root, synthetic, parsed_paths, rejected)
            connection.execute("""UPDATE source_southern_election_file
              SET parser_name='arkansas_pre2000_validated_staging',
                  parser_message='Imported from independently validated Arkansas pre-2000 staging'
              WHERE source_file_id=?""", (source_ids[relative],))
        as_of = max((clean(meta.get("retrieved_at")) for meta in manifest if clean(meta.get("retrieved_at"))), default=datetime.now(timezone.utc).isoformat())
        result_columns = [
            "candidate_election_id", "election_id", "contest_id", "contract_version", "build_run_id",
            "state_code", "cycle", "election_date", "election_date_status", "election_stage",
            "election_stage_original", "office_code", "office_original", "chamber", "district_plan_id",
            "geography_vintage", "district", "district_original", "candidate_name",
            "candidate_name_originals_json", "party_family", "party_original", "votes", "vote_share",
            "vote_value_status", "contest_status", "observed_candidate_count", "reported_geography_count",
            "source_coverage", "validation_status", "as_of_utc"]
        insert_sql = f"INSERT INTO source_southern_candidate_election ({','.join(result_columns)}) VALUES ({','.join('?' for _ in result_columns)})"
        for row in results:
            office_original = sorted(row["office_originals"])[0]
            plan_id = (f"{row['state_code']}-{row['cycle']}-{row['chamber']}-reported-unknown-vintage"
                       if row["chamber"] else None)
            record = {
                **row, "contract_version": 1, "build_run_id": run_id, "office_original": office_original,
                "district_plan_id": plan_id, "geography_vintage": "provider-reported; plan vintage unverified",
                "candidate_name_originals_json": json.dumps(sorted(name for name in row["candidate_originals"] if name)),
                "vote_value_status": "observed", "contest_status": "unknown",
                "source_coverage": "+".join(sorted(row["coverages"])),
                "validation_status": result_validation_status(row),
                "as_of_utc": as_of,
            }
            connection.execute(insert_sql, tuple(record.get(column) for column in result_columns))
            role = "component" if len(row["source_paths"]) > 1 else "reports"
            for relative in row["source_paths"]:
                connection.execute("INSERT INTO bridge_southern_candidate_result_source VALUES (?,?,?)",
                                   (row["candidate_election_id"], source_ids[relative], role))
        for audit in audits:
            identifier = source_ids.get(audit["source_path"])
            if identifier:
                connection.execute("INSERT INTO qa_southern_election_reconciliation VALUES (?,?,?,?,?,?,?,?,?)",
                                   (identifier, audit["parser_name"], audit["input_candidate_rows"],
                                    audit["output_candidate_rows"], audit["input_votes"], audit["output_votes"],
                                    audit["vote_delta"], audit["reconciliation_status"], audit["note"]))
        coverage = coverage_rows(manifest, results, rejected, run_id)
        for row in coverage:
            connection.execute("INSERT INTO qa_southern_election_coverage VALUES (?,?,?,?,?,?,?,?)", tuple(row.values()))
        duplicate = connection.execute("""SELECT COUNT(*) FROM (
          SELECT state_code,election_date,election_stage,office_code,coalesce(district,''),candidate_name,
                 party_family,coalesce(party_original,''),count(*) n
          FROM source_southern_candidate_election GROUP BY 1,2,3,4,5,6,7,8 HAVING n>1)""").fetchone()[0]
        bad_share = connection.execute("SELECT COUNT(*) FROM source_southern_candidate_election WHERE vote_share<0 OR vote_share>1").fetchone()[0]
        bad_fk = connection.execute("PRAGMA foreign_key_check").fetchall()
        nonexact = connection.execute("SELECT COUNT(*) FROM qa_southern_election_reconciliation WHERE reconciliation_status NOT IN ('exact','rejected')").fetchone()[0]
        if duplicate or bad_share or bad_fk:
            raise ValueError(f"Southern election validation failed: duplicates={duplicate}, shares={bad_share}, foreign_keys={bad_fk[:5]}")
        validation = {"candidate_results": len(results), "source_files": len(manifest),
                      "validated_candidate_results": sum(result_validation_status(row) == "passed" for row in results),
                      "review_candidate_results": sum(result_validation_status(row) == "review" for row in results),
                      "parsed_source_files": len(parsed_paths), "rejected_source_files": len(rejected),
                      "exact_source_reconciliations": sum(a["reconciliation_status"] == "exact" for a in audits),
                      "nonexact_source_reconciliations": nonexact, "states_with_results": len({r["state_code"] for r in results})}
        register_table(connection, "source_southern_election_file", "source", "scripts/load_southern_election_warehouse.py",
                       "source_file_id", "Official provider artifacts; unknown terms and vintages remain explicit", "replace",
                       "Extended source contract for acquired Southern election artifacts")
        register_table(connection, "source_southern_candidate_election", "source", "scripts/load_southern_election_warehouse.py",
                       "candidate_election_id", "Official provider totals only; no cross-source overwrite", "replace",
                       "Normalized candidate-party-contest observations at reported contest geography")
        register_table(connection, "fact_southern_candidate_election", "canonical", "scripts/load_southern_election_warehouse.py",
                       "candidate_election_id", "Validated official normalized observations", "view",
                       "Cross-state candidate-election fact interface")
        register_table(connection, "qa_southern_election_coverage", "qa", "scripts/load_southern_election_warehouse.py",
                       "state_code + cycle", "Explicit acquired, parsed, external, and review-queue states", "replace",
                       "Southern result acquisition and normalization coverage")
        finish_run(connection, run_id, validation); connection.commit()

    return export_loaded(database, run_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()
    result = export_loaded(args.database) if args.export_only else build(database=args.database)
    print(json.dumps(result["validation"], indent=2))


if __name__ == "__main__": main()
