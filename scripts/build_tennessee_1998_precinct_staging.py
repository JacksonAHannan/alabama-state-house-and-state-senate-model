#!/usr/bin/env python3
"""OCR official Tennessee 1998 precinct reports into experimental staging."""

from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import hashlib
import json
import re
import subprocess
from pathlib import Path
from zipfile import ZipFile

import fitz
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/southern_sos_elections/TN/1998"
OUTPUT = ROOT / "data/processed/precinct_history/tennessee_1998"
KLARNER = ROOT / "data/raw/historical_statewide_elections/dataverse_files.zip"
FILES = {"house": RAW / "house-p.pdf", "senate": RAW / "senate-p.pdf", "governor": RAW / "gov-p.pdf"}
TN_COUNTIES = """Anderson Bedford Benton Bledsoe Blount Bradley Campbell Cannon Carroll Carter Cheatham Chester
Claiborne Clay Cocke Coffee Crockett Cumberland Davidson Decatur DeKalb Dickson Dyer Fayette Fentress Franklin
Gibson Giles Grainger Greene Grundy Hamblen Hamilton Hancock Hardeman Hardin Hawkins Haywood Henderson Henry Hickman
Houston Humphreys Jackson Jefferson Johnson Knox Lake Lauderdale Lawrence Lewis Lincoln Loudon Macon Madison Marion
Marshall Maury McMinn McNairy Meigs Monroe Montgomery Moore Morgan Obion Overton Perry Pickett Polk Putnam Rhea Roane
Robertson Rutherford Scott Sequatchie Sevier Shelby Smith Stewart Sullivan Sumner Tipton Trousdale Unicoi Union Van Buren
Warren Washington Wayne Weakley White Williamson Wilson""".upper().split()
# Restore the only two-word county after whitespace tokenization.
TN_COUNTIES = [name for name in TN_COUNTIES if name not in {"VAN", "BUREN"}] + ["VAN BUREN"]
SENATE_PAGE_DISTRICT = {1: 1, 2: 3, 4: 5, 5: 7, 6: 8, 7: 9, 9: 11, 10: 13, 13: 15,
                        16: 17, 18: 19, 19: 21, 20: 23, 21: 25, 24: 27, 26: 29, 27: 31, 28: 33}
DISTRICT_INITIAL_COUNTY = {("senate", 33): "SHELBY"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _ocr_chunk(payload: tuple[str, str, list[int], float]) -> list[dict]:
    report, path_text, pages, zoom = payload
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    document = fitz.open(path_text)
    output: list[dict] = []
    for page_number in pages:
        pixmap = document[page_number].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
        result, _ = engine(image)
        for box, text, confidence in result or []:
            xs = [point[0] for point in box]
            ys = [point[1] for point in box]
            output.append({"report": report, "page": page_number + 1, "x0": min(xs), "y0": min(ys),
                           "x1": max(xs), "y1": max(ys), "text": str(text), "confidence": float(confidence)})
    return output


def run_ocr(output: Path, workers: int, zoom: float, force: bool) -> pd.DataFrame:
    cache = output / "tennessee_1998_ocr_tokens.csv.gz"
    metadata_path = output / "tennessee_1998_ocr_metadata.json"
    source_hashes = {name: sha256(path) for name, path in FILES.items()}
    if cache.exists() and metadata_path.exists() and not force:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("source_hashes") == source_hashes and metadata.get("zoom") == zoom:
            return pd.read_csv(cache)

    jobs = []
    for report, path in FILES.items():
        pages = list(range(len(fitz.open(path))))
        chunks = [pages[index::workers] for index in range(workers)]
        jobs.extend((report, str(path), chunk, zoom) for chunk in chunks if chunk)
    token_rows: list[dict] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        for rows in executor.map(_ocr_chunk, jobs):
            token_rows.extend(rows)
    tokens = pd.DataFrame(token_rows).sort_values(["report", "page", "y0", "x0"]).reset_index(drop=True)
    tokens.to_csv(cache, index=False, compression={"method": "gzip", "mtime": 0})
    metadata = {"source_hashes": source_hashes, "zoom": zoom, "workers": workers,
                "pages": {name: len(fitz.open(path)) for name, path in FILES.items()}, "tokens": len(tokens)}
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return tokens


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def canonical_county(value: object) -> tuple[str, float]:
    raw = re.sub(r"[^A-Z ]", "", normalize_text(value).upper())
    raw = re.sub(r"\s+", " ", raw).strip()
    aliases = {"NOINN": "UNION", "HLINS": "SMITH", "LIHM": "WHITE", "NOSNHOF": "JOHNSON"}
    if raw in aliases:
        return aliases[raw], 0.9
    if raw in TN_COUNTIES:
        return raw, 1.0
    ranked = sorted(((difflib.SequenceMatcher(None, raw, county).ratio(), county) for county in TN_COUNTIES), reverse=True)
    if ranked and ranked[0][0] >= 0.75 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.08):
        return ranked[0][1], ranked[0][0]
    return f"UNRESOLVED::{raw}", ranked[0][0] if ranked else 0.0


def has_total_marker(value: object) -> bool:
    words = re.findall(r"[A-Z]+", normalize_text(value).upper())
    return any(word.endswith("TOTAL") or (len(word) == 5 and difflib.SequenceMatcher(None, word, "TOTAL").ratio() >= 0.8)
               for word in words)


def district_number(value: object, maximum: int) -> int | None:
    text = normalize_text(value).upper()
    if "TOTAL" in text:
        return None
    match = re.search(r"\bDISTRICT\b\s*[:#]?\s*([0-9](?:[.\s]*[0-9])?)", text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    number = int(digits) if digits else 0
    return number if 1 <= number <= maximum else None


def integer_token(value: object) -> int | None:
    text = normalize_text(value).replace(",", "").replace("。", "0")
    if text in {"O", "o"}:
        text = "0"
    if not re.fullmatch(r"\d+", text):
        return None
    return int(text)


def cell_integer(items: list[dict]) -> tuple[int | None, float | None]:
    if not items:
        return None, None
    text = "".join(normalize_text(item["text"]) for item in sorted(items, key=lambda row: row["x0"]))
    translations = str.maketrans({"O": "0", "o": "0", "。": "0", "I": "1", "l": "1",
                                  "B": "8", "b": "8", "E": "8", "e": "8", "G": "6", "S": "5"})
    text = text.translate(translations)
    text = re.sub(r"[,.:;'`\s]", "", text)
    if not re.fullmatch(r"\d+", text):
        return None, min(float(item["confidence"]) for item in items)
    return int(text), min(float(item["confidence"]) for item in items)


def numeric_cells(line: list[dict], start: float = 325, gap: float = 55) -> tuple[list[tuple[int, float]], bool]:
    items = [item for item in line if item["x0"] >= start]
    if not items:
        return [], False
    groups: list[list[dict]] = []
    for item in sorted(items, key=lambda row: row["x0"]):
        if not groups or item["x0"] - max(part["x1"] for part in groups[-1]) > gap:
            groups.append([item])
        else:
            groups[-1].append(item)
    cells: list[tuple[int, float]] = []
    ambiguous = False
    for group in groups:
        value, confidence = cell_integer(group)
        if value is None:
            ambiguous = True
        else:
            cells.append((value, float(confidence)))
    return cells, ambiguous


def page_lines(tokens: pd.DataFrame, tolerance: float = 7.0) -> list[list[dict]]:
    records = tokens.to_dict("records")
    records.sort(key=lambda row: ((row["y0"] + row["y1"]) / 2, row["x0"]))
    lines: list[list[dict]] = []
    centers: list[float] = []
    for row in records:
        center = (row["y0"] + row["y1"]) / 2
        if not lines or abs(center - centers[-1]) > tolerance:
            lines.append([row])
            centers.append(center)
        else:
            lines[-1].append(row)
            centers[-1] = sum((item["y0"] + item["y1"]) / 2 for item in lines[-1]) / len(lines[-1])
    for line in lines:
        line.sort(key=lambda row: row["x0"])
    return lines


def line_text(line: list[dict]) -> str:
    return " ".join(normalize_text(item["text"]) for item in line).strip()


def left_label(line: list[dict]) -> str:
    return " ".join(normalize_text(item["text"]) for item in line if item["x0"] < 325).strip()


def parse_legislative(tokens: pd.DataFrame, report: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    district = None
    county = None
    rows: list[dict] = []
    totals: list[dict] = []
    header_audit: list[dict] = []
    expected_districts = list(range(1, 100)) if report == "house" else sorted([8] + list(range(1, 34, 2)))
    header_index = 0
    for page, page_frame in tokens.loc[tokens["report"].eq(report)].groupby("page", sort=True):
        for line in page_lines(page_frame):
            text = line_text(line)
            upper = text.upper()
            if upper.strip().startswith("DISTRICT") and not has_total_marker(upper):
                if report == "house" and header_index >= len(expected_districts):
                    raise ValueError(f"Too many {report} district headers; page {page}: {text}")
                observed = district_number(upper, 99 if report == "house" else 33)
                if report == "house":
                    district = expected_districts[header_index]
                else:
                    if int(page) not in SENATE_PAGE_DISTRICT:
                        raise ValueError(f"Unadjudicated Senate district header on page {page}: {text}")
                    district = SENATE_PAGE_DISTRICT[int(page)]
                header_audit.append({"report": report, "source_page": int(page), "header_index": header_index + 1,
                                     "assigned_district": district, "ocr_district": observed,
                                     "ocr_header": text, "sequence_override": observed != district})
                header_index += 1
                county = DISTRICT_INITIAL_COUNTY.get((report, district))
                county_raw = county
                county_confidence = 1.0 if county else None
                continue
            county_match = re.search(r"\bCOUNTY\s*:\s*(.+)", upper)
            if county_match:
                county_raw = re.sub(r"[^A-Z .'-]", "", county_match.group(1)).strip()
                county, county_confidence = canonical_county(county_raw)
                continue
            label = left_label(line)
            if not label or district is None or county is None:
                continue
            label_compact = re.sub(r"[^A-Z]", "", label.upper())
            numeric, ambiguous_numeric = numeric_cells(line)
            if "DISTRICT" in upper and has_total_marker(label):
                totals.append({"state": "TN", "year": 1998, "chamber": report, "district": district,
                               "ocr_district_total": sum(value for value, _ in numeric), "source_page": int(page)})
                continue
            if has_total_marker(label) or any(term in upper for term in ["CANDIDATES", "WRITE-", "PAGE "]):
                continue
            if not numeric or ambiguous_numeric:
                continue
            row_confidence = min(confidence for _, confidence in numeric)
            if row_confidence < 0.45:
                continue
            rows.append({"state": "TN", "year": 1998, "county": county, "precinct": label.upper(),
                         "county_raw": county_raw, "county_match_confidence": county_confidence,
                         "chamber": report, "district": district,
                         "legislative_turnout": sum(value for value, _ in numeric),
                         "numeric_columns": len(numeric), "ocr_min_numeric_confidence": row_confidence,
                         "source_page": int(page), "source_line": text})
    assigned = [row["assigned_district"] for row in header_audit]
    if report == "house" and assigned != expected_districts:
        raise ValueError(f"Expected ordered House districts 1-99, found {assigned}")
    if report == "senate" and sorted(set(assigned)) != expected_districts:
        raise ValueError(f"Expected regular odd Senate districts plus special district 8, found {assigned}")
    frame = pd.DataFrame(rows)
    total_frame = pd.DataFrame(totals)
    return frame, total_frame, pd.DataFrame(header_audit)


def parse_governor(tokens: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    county = None
    rows: list[dict] = []
    review: list[dict] = []
    totals: list[dict] = []
    for page, page_frame in tokens.loc[tokens["report"].eq("governor")].groupby("page", sort=True):
        for line in page_lines(page_frame):
            text = line_text(line)
            upper = text.upper()
            county_match = re.search(r"\bCOUNTY\s*:\s*(.+)", upper)
            if county_match:
                county_raw = re.sub(r"[^A-Z .'-]", "", county_match.group(1)).strip()
                county, county_confidence = canonical_county(county_raw)
                continue
            label = left_label(line)
            label_compact = re.sub(r"[^A-Z]", "", label.upper())
            if not label or county is None or any(
                term in upper for term in ["CANDIDATES", "WRITE-", "PAGE "]
            ):
                continue
            dem_group = [item for item in line if 325 <= item["x0"] < 425]
            rep_group = [item for item in line if 425 <= item["x0"] < 525]
            dem_vote, dem_confidence = cell_integer(dem_group)
            rep_vote, rep_confidence = cell_integer(rep_group)
            if has_total_marker(label):
                if "COUNTY" in label_compact and dem_vote is not None and rep_vote is not None:
                    totals.append({"state": "TN", "year": 1998, "county": county, "county_raw": county_raw,
                                   "dem_total": dem_vote, "rep_total": rep_vote, "source_page": int(page)})
                continue
            if dem_vote is None or rep_vote is None:
                if dem_group or rep_group:
                    review.append({"county": county, "precinct": label.upper(), "source_page": int(page),
                                   "source_line": text, "reason": "missing_or_multiple_major_party_cells"})
                continue
            confidence = min(float(dem_confidence), float(rep_confidence))
            if confidence < 0.45:
                review.append({"county": county, "precinct": label.upper(), "source_page": int(page),
                               "source_line": text, "reason": "low_numeric_confidence"})
                continue
            rows.append({"state": "TN", "year": 1998, "county": county, "precinct": label.upper(),
                         "county_raw": county_raw, "county_match_confidence": county_confidence,
                         "dem_votes": dem_vote, "rep_votes": rep_vote, "ocr_min_numeric_confidence": confidence,
                         "source_page": int(page), "source_line": text})
    return pd.DataFrame(rows), pd.DataFrame(review), pd.DataFrame(totals)


def klarner_tennessee() -> pd.DataFrame:
    with ZipFile(KLARNER) as archive:
        contests = pd.read_csv(archive.open("202slers_uoa_contest20230810.csv"), low_memory=False)
    contests = contests.loc[contests["state"].eq("Tennessee") & contests["year"].eq(1998)].copy()
    contests["state"] = "TN"
    contests["chamber"] = contests["sen"].map({0: "house", 1: "senate"})
    contests["district"] = pd.to_numeric(contests["dno"], errors="coerce")
    for column in ["dvote", "rvote", "ovote"]:
        contests[column] = pd.to_numeric(contests[column], errors="coerce")
    contests["klarner_total_votes"] = contests[["dvote", "rvote", "ovote"]].sum(axis=1, min_count=3)
    return contests[["state", "year", "chamber", "district", "dvote", "rvote", "ovote", "klarner_total_votes",
                     "dinc", "rinc", "uncont", "dontuse", "bigthird"]].drop_duplicates(["state", "year", "chamber", "district"])


def build(output: Path, workers: int, zoom: float, force_ocr: bool) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    tokens = run_ocr(output, workers, zoom, force_ocr)
    house, house_totals, house_headers = parse_legislative(tokens, "house")
    senate, senate_totals, senate_headers = parse_legislative(tokens, "senate")
    legislative = pd.concat([house, senate], ignore_index=True)
    keys = ["state", "year", "county", "precinct", "chamber", "district"]
    duplicate_counts = legislative.groupby(keys, dropna=False)["legislative_turnout"].transform("size")
    legislative["duplicate_ocr_rows"] = duplicate_counts
    legislative = legislative.sort_values(keys + ["source_page"]).drop_duplicates(keys, keep="first").reset_index(drop=True)
    governor, governor_review, governor_totals = parse_governor(tokens)
    gov_keys = ["state", "year", "county", "precinct"]
    governor["duplicate_ocr_rows"] = governor.groupby(gov_keys, dropna=False)["dem_votes"].transform("size")
    governor = governor.sort_values(gov_keys + ["source_page"]).drop_duplicates(gov_keys, keep="first").reset_index(drop=True)
    parsed_governor = governor.groupby(["state", "year", "county"], as_index=False)[["dem_votes", "rep_votes"]].sum()
    governor_coverage = governor_totals.merge(parsed_governor, on=["state", "year", "county"], how="outer", validate="one_to_one")
    governor_coverage["dem_coverage"] = governor_coverage["dem_votes"] / governor_coverage["dem_total"].where(governor_coverage["dem_total"] > 0)
    governor_coverage["rep_coverage"] = governor_coverage["rep_votes"] / governor_coverage["rep_total"].where(governor_coverage["rep_total"] > 0)

    parsed_totals = legislative.groupby(["state", "year", "chamber", "district"], as_index=False)["legislative_turnout"].sum()
    outcomes = klarner_tennessee()
    reconciliation = outcomes.merge(parsed_totals, on=["state", "year", "chamber", "district"], how="outer", indicator=True)
    reconciliation["vote_delta"] = reconciliation["legislative_turnout"] - reconciliation["klarner_total_votes"]
    tolerance = reconciliation["klarner_total_votes"].mul(0.01).clip(lower=10)
    complete = reconciliation[["legislative_turnout", "klarner_total_votes"]].notna().all(axis=1)
    reconciliation["reconciliation_status"] = "missing_one_source"
    reconciliation.loc[complete & reconciliation["vote_delta"].eq(0), "reconciliation_status"] = "exact"
    reconciliation.loc[complete & reconciliation["vote_delta"].ne(0) & reconciliation["vote_delta"].abs().le(tolerance),
                       "reconciliation_status"] = "within_one_percent"
    reconciliation.loc[complete & reconciliation["vote_delta"].abs().gt(tolerance),
                       "reconciliation_status"] = "material_mismatch"
    reconciliation["model_eligible"] = reconciliation["reconciliation_status"].isin(["exact", "within_one_percent"])
    reconciliation = reconciliation.sort_values(["chamber", "district"]).reset_index(drop=True)

    district_totals = pd.concat([house_totals, senate_totals], ignore_index=True)
    district_headers = pd.concat([house_headers, senate_headers], ignore_index=True)
    paths = {
        "tokens": output / "tennessee_1998_ocr_tokens.csv.gz",
        "legislative": output / "tennessee_1998_legislative_precinct_turnout.csv",
        "governor": output / "tennessee_1998_governor_precinct.csv",
        "governor_review": output / "tennessee_1998_governor_review.csv",
        "governor_coverage": output / "tennessee_1998_governor_coverage.csv",
        "ocr_district_totals": output / "tennessee_1998_ocr_district_totals.csv",
        "district_headers": output / "tennessee_1998_district_header_audit.csv",
        "reconciliation": output / "tennessee_1998_legislative_reconciliation.csv",
    }
    legislative.to_csv(paths["legislative"], index=False)
    governor.to_csv(paths["governor"], index=False)
    governor_review.to_csv(paths["governor_review"], index=False)
    governor_coverage.to_csv(paths["governor_coverage"], index=False)
    district_totals.to_csv(paths["ocr_district_totals"], index=False)
    district_headers.to_csv(paths["district_headers"], index=False)
    reconciliation.to_csv(paths["reconciliation"], index=False)
    source_meta = [{"report": name, "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                    "sha256": sha256(path), "pages": len(fitz.open(path))} for name, path in FILES.items()]
    manifest = {"schema_version": 1, "pipeline": Path(__file__).resolve().relative_to(ROOT).as_posix(),
                "code_commit": git_commit(), "configuration": {"ocr_engine": "rapidocr_onnxruntime", "zoom": zoom,
                "minimum_numeric_confidence": 0.45, "reconciliation_tolerance": "max(10 votes, 1 percent)"},
                "sources": source_meta, "klarner_sha256": sha256(KLARNER),
                "row_counts": {"ocr_tokens": len(tokens), "legislative": len(legislative), "governor": len(governor),
                               "governor_review": len(governor_review), "reconciliation": len(reconciliation),
                               "governor_county_totals": len(governor_totals),
                               "district_headers": len(district_headers),
                               "model_eligible": int(reconciliation["model_eligible"].sum())}}
    manifest["outputs"] = [{"name": name, "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                            "sha256": sha256(path)} for name, path in paths.items()]
    manifest["build_id"] = hashlib.sha256(
        (":".join(item["sha256"] for item in source_meta) + ":" + sha256(Path(__file__).resolve())).encode()
    ).hexdigest()[:20]
    (output / "tennessee_1998_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--zoom", type=float, default=2.0)
    parser.add_argument("--force-ocr", action="store_true")
    args = parser.parse_args()
    manifest = build(args.output, args.workers, args.zoom, args.force_ocr)
    print("Tennessee 1998 staging:", manifest["row_counts"], "build", manifest["build_id"])


if __name__ == "__main__":
    main()
