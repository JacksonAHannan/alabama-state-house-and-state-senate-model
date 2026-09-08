"""Read and reconcile immutable Alabama 2018 SOS legislative results.

This adapter is read-only.  It preserves blank precinct workbook cells as
unknown and treats the certified canvass totals as separate source evidence.
"""
from __future__ import annotations

import hashlib
import io
import math
import re
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

import alabama_2022_official_results as shared
from oe_normalize import normalize_name


ARCHIVE = Path(
    "data/raw/alabama_elections_and_geography/2018-Official-General-Precinct-Results.zip"
)
CANVASS = Path(
    "data/raw/alabama_elections_and_geography/2018_general_certified_canvass.pdf"
)
KEY = shared.KEY
DATE_LABEL = "November 6, 2018"
CERTIFICATION_LABEL = "Certified by the State Canvassing Board"
HYPHENS = re.compile("[\u2010\u2011\u2012\u2013\u2014]")


def clean_text(value: object) -> str:
    """Normalize PDF spacing and typographic hyphens without changing names."""
    return HYPHENS.sub("-", re.sub(r"\s+", " ", str(value)).strip())


def parse_canvass_page(spans: list[dict], page_number: int) -> list[dict]:
    """Parse one rotated 2018 legislative canvass total row by positioned columns."""
    spans = [dict(span, text=clean_text(span["text"])) for span in spans]
    spans = [span for span in spans if span["text"]]
    texts = {span["text"] for span in spans}
    if "Alabama Senate - General Election Results" in texts:
        chamber, district_count = "senate", 35
    elif "Alabama House of Representatives - General Election Results" in texts:
        chamber, district_count = "house", 105
    else:
        return []

    # Every contest spans a two-page county table.  Only the first page has the
    # certified Total row; continuation pages deliberately produce no records.
    totals = [span for span in spans if span["text"] == "Total"]
    if not totals:
        return []
    contests = sorted(
        [span for span in spans if re.fullmatch(r"District \d+", span["text"])],
        key=lambda span: span["bbox"][1],
        reverse=True,
    )
    if len(totals) != 1 or not contests:
        raise ValueError(f"Ambiguous canvass contest/total headers: page {page_number}")
    if DATE_LABEL not in texts or CERTIFICATION_LABEL not in texts:
        raise ValueError(f"Wrong or unverified canvass election scope: page {page_number}")

    total = totals[0]
    contest_x = max(span["bbox"][0] for span in contests)
    header_spans = sorted(
        [
            span
            for span in spans
            if contest_x + 5 < span["bbox"][0] < total["bbox"][0] - 1
            and ("Write-In" in span["text"] or re.search(r"\([DRLI]\)", span["text"]))
        ],
        key=lambda span: span["bbox"][1],
        reverse=True,
    )
    headers: list[tuple[str, dict, int]] = []
    for span in header_spans:
        tokens = re.findall(r"(?:.*?\([DRLI]\)|Write-In)", span["text"])
        if "".join(tokens).replace(" ", "") != span["text"].replace(" ", ""):
            raise ValueError(
                f"Unparsed canvass candidate header: page {page_number}: {span['text']}"
            )
        headers.extend(
            (token.strip(), span, token_index)
            for token_index, token in enumerate(tokens)
        )

    values = sorted(
        [
            span
            for span in spans
            if abs(span["bbox"][0] - total["bbox"][0]) < 1
            and span["bbox"][1] < total["bbox"][1] - 1
        ],
        key=lambda span: span["bbox"][1],
        reverse=True,
    )
    number_pattern = r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)"
    if any(not re.fullmatch(number_pattern, span["text"]) for span in values):
        raise ValueError(f"Malformed canvass total: page {page_number}")
    if (
        len(headers) != len(values)
        or not headers
        or sum(text == "Write-In" for text, _, _ in headers) != len(contests)
        or len({tuple(span["bbox"]) for span in values}) != len(values)
    ):
        raise ValueError(f"Ambiguous canvass header/value columns: page {page_number}")

    records: list[dict] = []
    contest_index = 0
    for column, ((text, header, token_index), value) in enumerate(
        zip(headers, values), 1
    ):
        if contest_index >= len(contests):
            raise ValueError(f"Candidate after final write-in column: page {page_number}")
        contest = contests[contest_index]
        district = int(contest["text"].split()[-1])
        if not 1 <= district <= district_count:
            raise ValueError(f"Invalid canvass district: page {page_number}")
        write_in = text == "Write-In"
        match = None if write_in else re.fullmatch(r"(.+) \(([DRLI])\)", text)
        if not write_in and match is None:
            raise ValueError(f"Malformed canvass candidate: page {page_number}: {text}")
        candidate = "Write-In" if write_in else match[1]
        records.append(
            {
                "chamber": chamber,
                "district": district,
                "party": "O" if write_in else match[2],
                "candidate_norm": normalize_name(candidate),
                "category": "write_in" if write_in else "named_candidate",
                "certified_votes": int(value["text"].replace(",", "")),
                "canvass_printed_candidate": candidate,
                "canvass_printed_party": None if write_in else match[2],
                "canvass_page": page_number,
                "canvass_column": column,
                "canvass_header_text": header["text"],
                "canvass_header_token": token_index,
                "canvass_header_bbox": list(header["bbox"]),
                "canvass_value_bbox": list(value["bbox"]),
                "canvass_district_bbox": list(contest["bbox"]),
                "canvass_total_label_bbox": list(total["bbox"]),
            }
        )
        if write_in:
            contest_index += 1
    if contest_index != len(contests):
        raise ValueError(f"Unclosed canvass contest columns: page {page_number}")
    if pd.DataFrame(records).duplicated(KEY + ["category"]).any():
        raise ValueError(f"Ambiguous canvass candidate headers: page {page_number}")
    return records


def load_certified_canvass(root: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    """Read certified totals with exact 105-House/35-Senate coverage."""
    import fitz

    path = root / CANVASS
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    records: list[dict] = []
    with fitz.open(stream=content, filetype="pdf") as document:
        page_count = len(document)
        for page_number, page in enumerate(document, 1):
            spans = [
                span
                for block in page.get_text("dict")["blocks"]
                for line in block.get("lines", [])
                for span in line["spans"]
            ]
            records.extend(parse_canvass_page(spans, page_number))
    frame = pd.DataFrame(records)
    expected = {
        (chamber, district)
        for chamber, count in (("house", 105), ("senate", 35))
        for district in range(1, count + 1)
    }
    if frame.empty or set(zip(frame.chamber, frame.district)) != expected:
        raise ValueError("Certified canvass does not cover the exact 140 districts")
    if frame.duplicated(KEY + ["category"]).any():
        raise ValueError("Duplicate certified candidate/contest totals")
    write_ins = frame[frame.category.eq("write_in")].groupby(
        ["chamber", "district"]
    ).size()
    if write_ins.to_dict() != dict.fromkeys(expected, 1):
        raise ValueError("Missing or ambiguous certified write-in columns")
    if any(
        isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < 0
        or not float(value).is_integer()
        for value in frame.certified_votes
    ):
        raise ValueError("Invalid certified vote value")
    frame["canvass_sha256"] = digest
    metadata = {
        "source_path": CANVASS.as_posix(),
        "sha256": digest,
        "page_count": page_count,
        "legislative_contests": len(expected),
        "total_pages": int(frame.canvass_page.nunique()),
        "state_code": "AL",
        "cycle": 2018,
        "stage": "general",
    }
    return frame, metadata


def load_official_cells(root: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    """Read every physical legislative cell from all 67 county workbooks."""
    path = root / ARCHIVE
    content = path.read_bytes()
    parts: list[pd.DataFrame] = []
    county_names: set[str] = set()
    members: list[dict[str, str]] = []
    with ZipFile(io.BytesIO(content)) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if len(names) != len(set(names)) or len(names) != 67:
            raise ValueError("Expected 67 unique county workbooks")
        for member in sorted(names):
            match = re.fullmatch(r"2018-General-([A-Za-z]+)\.xls", member)
            if match is None or match[1].upper() in county_names:
                raise ValueError(f"Unexpected or duplicate county member: {member}")
            county_names.add(match[1].upper())
            workbook = archive.read(member)
            parts.append(shared.parse_workbook(workbook, member, match[1]))
            members.append(
                {"member": member, "sha256": hashlib.sha256(workbook).hexdigest()}
            )
    cells = pd.concat(parts, ignore_index=True)
    physical = ["source_member", "source_sheet", "source_row", "source_column"]
    if cells.duplicated(physical).any():
        raise ValueError("Duplicate physical source cells")
    metadata = {
        "source_path": ARCHIVE.as_posix(),
        "sha256": hashlib.sha256(content).hexdigest(),
        "cycle": 2018,
        "state_code": "AL",
        "stage": "general",
        "county_count": len(county_names),
        "members": members,
        "unknown_cells": int(cells.votes.isna().sum()),
    }
    return cells, metadata


def align_certified_candidate_keys(
    cells: pd.DataFrame, canvass: pd.DataFrame
) -> pd.DataFrame:
    """Bridge canvass surnames to unique precinct names at exact contest/party grain."""
    selected = cells[
        cells.category.isin(["named_candidate", "write_in"])
        & cells.cell_kind.eq("precinct")
    ].copy()
    selected["party"] = selected.printed_party.str.strip().str.upper().map(
        {"DEM": "D", "REP": "R", "LIB": "L", "IND": "I", "NON": "O"}
    )
    selected.loc[selected.category.eq("write_in"), "party"] = "O"
    scope = ["chamber", "district", "party", "category"]
    identities = selected[scope + ["candidate_norm"]].drop_duplicates()
    if identities.duplicated(scope).any() or canvass.duplicated(scope).any():
        raise ValueError("Candidate identity is not unique at exact contest/party grain")
    identities = identities.rename(columns={"candidate_norm": "precinct_candidate_norm"})
    aligned = canvass.merge(identities, on=scope, how="left", validate="one_to_one")
    aligned["canvass_candidate_norm"] = aligned.candidate_norm
    available = aligned.precinct_candidate_norm.notna()
    aligned.loc[available, "candidate_norm"] = aligned.loc[
        available, "precinct_candidate_norm"
    ]
    aligned["candidate_alignment_method"] = available.map(
        {
            True: "unique_exact_contest_party_category",
            False: "precinct_candidate_scope_absent",
        }
    )
    return aligned.drop(columns="precinct_candidate_norm")


def reconcile_sources(root: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    """Return exact source reconciliation; never convert unknown cells to zero."""
    cells, precinct = load_official_cells(root)
    canvass, certified = load_certified_canvass(root)
    canvass = align_certified_candidate_keys(cells, canvass)
    reconciliation = shared.reconcile_canvass(cells, canvass)
    return reconciliation, {"precinct_source": precinct, "canvass_source": certified}
