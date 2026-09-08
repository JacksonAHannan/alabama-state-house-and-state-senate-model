"""Read immutable Alabama 2022 SOS cells; keep RDH allocation data separate.

No downloads, output writes or warehouse mutations. Blank source cells remain
unknown. Totals sum observed precinct cells, not source summaries or over/under
ballots; they do not establish that an unprinted value was zero.
"""

from __future__ import annotations

import hashlib
import io
import math
import re
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from oe_normalize import normalize_name
from sos_precinct import _office, _workbook_sheets, norm_party


ARCHIVE = Path("data/raw/alabama_elections_and_geography/2022 General Precinct Level Results.zip")
README = Path("data/raw/alabama_elections_and_geography/al_gen_22_prec/README.txt")
KEY = ["chamber", "district", "party", "candidate_norm"]


def _category(label: str) -> str:
    normalized = normalize_name(label)
    if normalized in {"WRITE IN", "WRITE INS"}:
        return "write_in"
    if normalized in {"OVER VOTE", "OVER VOTES", "OVERVOTES"}:
        return "overvote"
    if normalized in {"UNDER VOTE", "UNDER VOTES", "UNDERVOTES"}:
        return "undervote"
    if normalized in {"TOTAL", "TOTALS", "TOTAL VOTES", "CONTEST TOTAL"}:
        return "summary"
    if not normalized:
        raise ValueError("Missing legislative candidate/category label")
    return "named_candidate"


def parse_workbook(content: bytes, member: str, county: str) -> pd.DataFrame:
    """One row per physical legislative result cell, including explicit blanks."""
    sheets = _workbook_sheets(content)
    if set(sheets) != {"Precinct Results"}:
        raise ValueError(f"Unexpected workbook sheets: {member}: {list(sheets)}")
    rows = sheets["Precinct Results"]
    if not rows or rows[0][:3] != ["Contest Title", "Party", "Candidate"]:
        raise ValueError(f"Unrecognized metadata header: {member}")
    headers = [str(v).strip() for v in rows[0]]
    if len(headers) < 4 or any(not h for h in headers[3:]) or len({h.upper() for h in headers[3:]}) != len(headers[3:]):
        raise ValueError(f"Missing or ambiguous precinct headers: {member}")
    records = []
    for row_number, row in enumerate(rows[1:], 2):
        if len(row) > len(headers) and any(str(v).strip() for v in row[len(headers):]):
            raise ValueError(f"Values outside header: {member}:{row_number}")
        values = list(row) + [""] * max(0, len(headers) - len(row))
        title, printed_party, candidate = [str(v).strip() for v in values[:3]]
        office, district = _office(title)
        if office not in {"State House", "State Senate"}:
            continue
        chamber = "house" if office == "State House" else "senate"
        if district is None or not district.is_integer() or not 1 <= district <= (105 if chamber == "house" else 35):
            raise ValueError(f"Invalid legislative district: {member}:{row_number}:{title}")
        category = _category(candidate)
        if category == "named_candidate" and printed_party.upper() not in {"DEM", "REP", "LIB", "IND", "NON"}:
            raise ValueError(f"Unknown named-candidate party: {member}:{row_number}:{printed_party}")
        for column, header in enumerate(headers[3:], 4):
            value = values[column - 1]
            votes = None
            if str(value).strip():
                try:
                    votes = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Malformed vote: {member}:{row_number}:{column}:{value!r}") from exc
                if isinstance(value, bool) or not math.isfinite(votes) or votes < 0 or not votes.is_integer():
                    raise ValueError(f"Invalid vote: {member}:{row_number}:{column}:{value!r}")
                votes = int(votes)
            summary = bool(re.fullmatch(r"(?:COUNTY |CONTEST |GRAND )?TOTAL(?:S| VOTES)?|TOTAL OF REGISTERED VOTERS", header, re.I))
            records.append({
                "source_member": member, "source_sheet": "Precinct Results",
                "source_row": row_number, "source_column": column,
                "county": county, "precinct": header, "printed_precinct": str(rows[0][column - 1]),
                "printed_office": str(values[0]), "printed_party": str(values[1]),
                "printed_candidate": str(values[2]),
                "chamber": chamber, "district": int(district), "party": norm_party(printed_party),
                "candidate_norm": normalize_name(candidate), "category": category,
                "cell_kind": "summary" if summary else "precinct",
                "votes": votes, "value_status": "unknown" if votes is None else "observed",
            })
    if not records:
        raise ValueError(f"No legislative cells: {member}")
    frame = pd.DataFrame(records)
    frame["votes"] = pd.array(frame.votes, dtype="Int64")
    row_keys = frame.drop_duplicates("source_row")
    if row_keys.duplicated(KEY + ["category"]).any():
        raise ValueError(f"Ambiguous repeated candidate/category rows: {member}")
    return frame


def load_official_cells(root: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    """Require all 67 unique county workbooks in the ZIP; never use extraction."""
    path = root / ARCHIVE
    content = path.read_bytes()
    parts, county_names, members = [], set(), []
    with ZipFile(io.BytesIO(content)) as archive:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive members / physical cells")
        if len(names) != 67:
            raise ValueError(f"Expected 67 county workbooks, found {len(names)}")
        for member in sorted(names):
            match = re.fullmatch(r"2022-General-([A-Za-z]+)\.xls", member)
            if not match or match[1].upper() in county_names:
                raise ValueError(f"Unexpected or duplicate county member: {member}")
            county_names.add(match[1].upper())
            workbook = archive.read(member)
            parts.append(parse_workbook(workbook, member, match[1]))
            members.append({"member": member, "sha256": hashlib.sha256(workbook).hexdigest()})
    cells = pd.concat(parts, ignore_index=True)
    if cells.duplicated(["source_member", "source_sheet", "source_row", "source_column"]).any():
        raise ValueError("Duplicate physical source cells")
    return cells, {"source_path": ARCHIVE.as_posix(), "sha256": hashlib.sha256(content).hexdigest(),
                   "cycle": 2022, "state_code": "AL", "stage": "general", "county_count": 67,
                   "members": members, "unknown_cells": int(cells.votes.isna().sum())}


def candidate_totals(cells: pd.DataFrame) -> pd.DataFrame:
    """Observed named-candidate totals; blank cells retained in the source frame."""
    selected = cells[cells.category.eq("named_candidate") & cells.cell_kind.eq("precinct")]
    groups = selected.groupby(KEY, dropna=False).votes
    totals = groups.sum(min_count=1).reset_index()
    counts = groups.agg(observed_cells="count", source_cells="size").reset_index()
    totals = totals.merge(counts, on=KEY, validate="one_to_one")
    totals["unknown_cells"] = totals.source_cells - totals.observed_cells
    totals["aggregation_status"] = "observed_cell_subtotal"
    if totals.empty or totals.votes.isna().any():
        raise ValueError("Missing candidate totals")
    return totals


def read_rdh_candidate_names(text: str) -> pd.DataFrame:
    """One compatibility code per printed contest/party/name; no fuzzy aliases."""
    records = []
    for line in text.splitlines():
        match = re.match(r"^(G(?:SL\d{3}|SU\d{2})[A-Z][A-Z0-9]+)\s+(.+)$", line.strip())
        if not match:
            continue
        code, description = match.groups()
        fields = description.strip().split("-:-")
        if len(fields) != 3:
            raise ValueError(f"Malformed RDH field description: {line}")
        title, candidate, printed_party = map(str.strip, fields)
        office, district = _office(title)
        chamber = "house" if code.startswith("GSL") else "senate"
        encoded = int(code[3:6] if chamber == "house" else code[3:5])
        party = code[6] if chamber == "house" else code[5]
        if party not in {"D", "R"}:
            continue
        if office != ("State House" if chamber == "house" else "State Senate") or district != encoded or norm_party(printed_party) != party:
            raise ValueError(f"RDH code/name scope disagreement: {line}")
        if party in {"D", "R"}:
            records.append({"candidate_code": code, "chamber": chamber, "district": encoded,
                            "party": party, "candidate_norm": normalize_name(candidate),
                            "printed_candidate": candidate})
    result = pd.DataFrame(records)
    if result.empty or result.duplicated("candidate_code").any() or result.duplicated(KEY).any():
        raise ValueError("Missing or ambiguous RDH candidate descriptions")
    return result


def match_code_totals(cells: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """Diagnostic 1:1 name join retaining unknown counts and subtotal status.

    This is not a certified producer input. Name parity cannot establish vote
    completeness; callers must retain the aggregation evidence for review.
    """
    totals = candidate_totals(cells)
    totals = totals[totals.party.isin(["D", "R"])]
    if totals.duplicated(["chamber", "district", "party"]).any():
        raise ValueError("Ambiguous official candidate identity")
    merged = names.merge(totals, on=KEY, how="outer", validate="one_to_one", indicator=True)
    if not merged._merge.eq("both").all():
        bad = merged.loc[merged._merge.ne("both"), KEY + ["candidate_code", "_merge"]]
        raise ValueError(f"Unmatched official/RDH candidate names: {bad.to_dict('records')}")
    return merged.drop(columns="_merge")


def parse_canvass_page(spans: list[dict], page_number: int) -> list[dict]:
    """Parse a legislative total row by its positioned headers, never text order.

    Merged PDF text spans retain their shared bounding box and token index; each
    numeric total has its own box and column index. Page numbers are one-based
    physical PDF pages, not the differently numbered printed footer.
    """
    contests = sorted(
        [s for s in spans if re.fullmatch(r"State (?:Senator|Representative), District \d+", s["text"])],
        key=lambda s: s["bbox"][0],
    )
    totals = [s for s in spans if s["text"] == "Total" and s["bbox"][0] < 100]
    if not contests or not totals:
        return []
    if len(totals) != 1 or len({s["text"] for s in contests}) != len(contests):
        raise ValueError(f"Ambiguous canvass contest/total headers: page {page_number}")
    texts = {s["text"] for s in spans}
    if "November 08, 2022" not in texts or "Certified by the State Canvassing Board" not in texts:
        raise ValueError(f"Wrong or unverified canvass election scope: page {page_number}")
    total_y = totals[0]["bbox"][1]
    heading_y = max(s["bbox"][1] for s in contests)
    header_spans = sorted(
        [s for s in spans if heading_y + 10 < s["bbox"][1] < total_y
         and ("Write-In" in s["text"] or re.search(r"\([DRLI]\)", s["text"]))],
        key=lambda s: s["bbox"][0],
    )
    headers = []
    for span in header_spans:
        tokens = re.findall(r"(?:.*?\([DRLI]\)|Write-In)", span["text"])
        if "".join(tokens).replace(" ", "") != span["text"].replace(" ", ""):
            raise ValueError(f"Unparsed canvass candidate header: page {page_number}: {span['text']}")
        headers.extend((token.strip(), span, token_index) for token_index, token in enumerate(tokens))
    values = sorted(
        [s for s in spans if abs(s["bbox"][1] - total_y) < 1 and s["bbox"][0] >= 100],
        key=lambda s: s["bbox"][0],
    )
    number_pattern = r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)"
    if any(not re.fullmatch(number_pattern, s["text"]) for s in values):
        raise ValueError(f"Malformed canvass total: page {page_number}")
    if (len(headers) != len(values) or not headers
            or sum(text == "Write-In" for text, _, _ in headers) != len(contests)
            or len({tuple(s["bbox"]) for s in values}) != len(values)):
        raise ValueError(f"Ambiguous canvass header/value columns: page {page_number}")
    records, contest_index = [], 0
    for column, ((text, header, token_index), value) in enumerate(zip(headers, values), 1):
        if contest_index >= len(contests):
            raise ValueError(f"Candidate after final write-in column: page {page_number}")
        contest = contests[contest_index]
        write_in = text == "Write-In"
        match = None if write_in else re.fullmatch(r"(.+) \(([DRLI])\)", text)
        if not write_in and match is None:
            raise ValueError(f"Malformed canvass candidate: page {page_number}: {text}")
        chamber = "house" if "Representative" in contest["text"] else "senate"
        district = int(contest["text"].split()[-1])
        if not 1 <= district <= (105 if chamber == "house" else 35):
            raise ValueError(f"Invalid canvass district: page {page_number}")
        candidate = "Write-In" if write_in else match[1]
        records.append({
            "chamber": chamber, "district": district,
            "party": "O" if write_in else match[2],
            "candidate_norm": normalize_name(candidate),
            "category": "write_in" if write_in else "named_candidate",
            "certified_votes": int(value["text"].replace(",", "")),
            "canvass_printed_candidate": candidate,
            "canvass_printed_party": None if write_in else match[2],
            "canvass_page": page_number, "canvass_column": column,
            "canvass_header_text": header["text"], "canvass_header_token": token_index,
            "canvass_header_bbox": list(header["bbox"]),
            "canvass_value_bbox": list(value["bbox"]),
            "canvass_district_bbox": list(contest["bbox"]),
            "canvass_total_label_bbox": list(totals[0]["bbox"]),
        })
        if write_in:
            contest_index += 1
    if records[-1]["category"] != "write_in":
        raise ValueError(f"Unclosed canvass contest columns: page {page_number}")
    if pd.DataFrame(records).duplicated(KEY + ["category"]).any():
        raise ValueError(f"Ambiguous canvass candidate headers: page {page_number}")
    return records


def load_certified_canvass(path: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    """Read certified legislative totals with full 105-House/35-Senate coverage."""
    import fitz

    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    records = []
    with fitz.open(stream=content, filetype="pdf") as document:
        page_count = len(document)
        for page_number, page in enumerate(document, 1):
            spans = [s for b in page.get_text("dict")["blocks"]
                     for line in b.get("lines", []) for s in line["spans"]]
            records.extend(parse_canvass_page(spans, page_number))
    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError("No certified legislative totals")
    expected = {(chamber, district) for chamber, count in [("house", 105), ("senate", 35)]
                for district in range(1, count + 1)}
    if set(zip(frame.chamber, frame.district)) != expected:
        raise ValueError("Certified canvass does not cover the exact 140 legislative districts")
    if frame.duplicated(KEY + ["category"]).any():
        raise ValueError("Duplicate certified candidate/contest totals")
    if frame[frame.category.eq("write_in")].groupby(["chamber", "district"]).size().to_dict() != dict.fromkeys(expected, 1):
        raise ValueError("Missing or ambiguous certified write-in columns")
    frame["canvass_sha256"] = digest
    return frame, {"source_path": str(path), "sha256": digest, "page_count": page_count,
                   "legislative_contests": 140, "total_pages": int(frame.canvass_page.nunique()),
                   "state_code": "AL", "cycle": 2022, "stage": "general"}


def reconcile_canvass(cells: pd.DataFrame, canvass: pd.DataFrame) -> pd.DataFrame:
    """Review every exact all-party/name/category key, retaining all missingness.

    A matched certified contest total does not turn unprinted precinct values
    into observed zeroes or certify any geographic allocation.
    """
    selected = cells[cells.category.isin(["named_candidate", "write_in"])
                     & cells.cell_kind.eq("precinct")].copy()
    # Unlike the older compatibility norm_party interface, this evidence join
    # must distinguish the provider's explicit Libertarian/Independent labels.
    selected["party"] = selected.printed_party.str.strip().str.upper().map(
        {"DEM": "D", "REP": "R", "LIB": "L", "IND": "I", "NON": "O"})
    selected.loc[selected.category.eq("write_in"), "party"] = "O"
    keys = KEY + ["category"]
    groups = selected.groupby(keys, dropna=False)
    observed = groups.votes.sum(min_count=1).rename("observed_votes").reset_index()
    counts = groups.votes.agg(observed_cells="count", source_cells="size").reset_index()
    observed = observed.merge(counts, on=keys, validate="one_to_one")
    observed["unknown_cells"] = observed.source_cells - observed.observed_cells
    observed["aggregation_status"] = "observed_cell_subtotal"
    certified = canvass.copy()
    certified["ambiguous_certified_key"] = certified.duplicated(keys, keep=False)
    result = observed.merge(certified, on=keys, how="outer", indicator=True, validate="one_to_many")
    result["reconciliation_status"] = "review"
    result["reconciliation_reason"] = "vote_mismatch"
    both = result._merge.eq("both")
    matched = both & result.observed_votes.notna() & result.observed_votes.eq(result.certified_votes)
    result.loc[matched, "reconciliation_status"] = "matched_certified_total"
    result.loc[matched, "reconciliation_reason"] = "exact_name_party_contest_category_and_votes"
    result.loc[result._merge.eq("left_only"), "reconciliation_reason"] = "missing_certified_candidate"
    result.loc[result._merge.eq("right_only"), "reconciliation_reason"] = "missing_precinct_candidate"
    unknown = both & (result.observed_votes.isna() | result.certified_votes.isna())
    result.loc[unknown, "reconciliation_reason"] = "unknown_vote_total"
    ambiguous = result.ambiguous_certified_key.eq(True)
    result.loc[ambiguous, "reconciliation_status"] = "review"
    result.loc[ambiguous, "reconciliation_reason"] = "ambiguous_certified_key"
    return result.drop(columns="_merge")
