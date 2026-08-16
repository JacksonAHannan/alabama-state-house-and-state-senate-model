"""Normalize official Alabama SOS county precinct workbooks and ZIPs."""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from oe_normalize import is_pseudocandidate, norm_party, normalize_name

SS = "urn:schemas-microsoft-com:office:spreadsheet"
YEAR_SOURCES = {
    1994: "94g-prec",
    1998: "98g-prec",
    2002: "2002-GeneralElection-PrecinctLevel_0.xls",
    2004: "2004-GeneralElection-PrecinctLevel",
    2006: "2006GeneralElection-PrecinctLevel",
    2008: "2008GeneralElectionPrecinctLevelResults.xls",
    2010: "2010-general-precinctLevel",
    2012: "2012General-PrecinctLevel",
    2014: "2014General-precinctLevel",
    2016: "2016-General-PrecinctLevel",
    2018: "2018-Official-General-Precinct-Results",
    2020: "2020 General Precinct Results",
    2022: "2022 General Precinct Level Results",
    2024: "2024-General Precinct Level Results",
}
LEGISLATIVE_DISTRICT_OVERRIDES = {
    (2002, "State Senate", "PREUITT JIM"): 11.0,
    (2006, "State Senate", "BARRON"): 8.0,
    (2006, "State Senate", "STOUT"): 8.0,
    (2006, "State Senate", "LINDSEY"): 22.0,
    (2006, "State Senate", "MCMILLAN"): 22.0,
    (2006, "State Senate", "SANDERS"): 23.0,
    (2006, "State Senate", "DUKE"): 23.0,
    (2006, "State Senate", "SINGLETON"): 24.0,
    (2006, "State Senate", "PENN"): 28.0,
}


def _xml_sheets(content: bytes) -> dict[str, list[list[object]]]:
    root = ET.fromstring(content.lstrip(b"\xef\xbb\xbf"))
    ns = {"s": SS}
    name_key, index_key, merge_key = f"{{{SS}}}Name", f"{{{SS}}}Index", f"{{{SS}}}MergeAcross"
    sheets = {}
    for ws in root.findall(".//s:Worksheet", ns):
        rows = []
        for row in ws.findall("s:Table/s:Row", ns):
            values, position = [], 1
            for cell in row.findall("s:Cell", ns):
                requested = cell.get(index_key)
                if requested:
                    while position < int(requested):
                        values.append(""); position += 1
                datum = cell.find("s:Data", ns)
                value: object = "" if datum is None else "".join(datum.itertext())
                if datum is not None and datum.get(f"{{{SS}}}Type") == "Number":
                    value = float(value) if "." in str(value) else int(value)
                values.append(value); position += 1
                for _ in range(int(cell.get(merge_key, "0"))):
                    values.append(""); position += 1
            rows.append(values)
        sheets[ws.get(name_key, "Sheet")] = rows
    return sheets


def _workbook_sheets(content: bytes) -> dict[str, list[list[object]]]:
    if b"<?xml" in content[:100]:
        return _xml_sheets(content)
    book = pd.ExcelFile(io.BytesIO(content))
    return {s: pd.read_excel(book, sheet_name=s, header=None).fillna("").values.tolist()
            for s in book.sheet_names}


def _office(title: object) -> tuple[str, float | None]:
    text = re.sub(r"\s+", " ", str(title)).strip().upper()
    match = re.search(r"DIST(?:RICT)?\.?(?: NO\.)?\s*(\d+)", text)
    district = float(match.group(1)) if match else None
    if "PRESIDENT" in text: return "President", district
    if district is None:
        embedded = re.search(r"STATE HOUSE\s*,?\s*(\d+)$", text)
        if embedded: district = float(embedded.group(1))
    if re.search(r"STATE (?:(?:HOUSE OF )?REP(?:RESENTATIVE)?|HOUSE(?:\s*,?\s*(?:DISTRICT\s*)?\d+)?)", text):
        return "State House", district
    if re.search(r"STATE SEN(?:ATOR|ATE)?", text) or (
            re.search(r"\bSENATOR\b", text) and
            not re.search(r"\b(?:US|U\.S\.|UNITED STATES)\b", text)):
        return "State Senate", district
    mappings = {
        "LIEUTENANT GOVERNOR": "Lieutenant Governor", "ATTORNEY GEN": "Attorney General",
        "SECRETARY OF STATE": "Secretary of State", "STATE AUDITOR": "State Auditor",
        "STATE TREASURER": "State Treasurer", "COMMISSIONER OF AGRICULTURE": "Commissioner of Agriculture and Industries",
        "GOVERNOR": "Governor",
    }
    for needle, canonical in mappings.items():
        if needle in text: return canonical, district
    return str(title).strip(), district


def _repair_legislative_metadata(data: pd.DataFrame) -> pd.DataFrame:
    """Fill omitted legacy districts from unique same-election candidate links."""
    result = data.copy(); result["candidate_norm"] = result.candidate.map(normalize_name)
    for office in ("State House", "State Senate"):
        known = result[result.office.eq(office) & result.district.notna()]
        choices = known.groupby("candidate_norm").district.agg(lambda values: sorted(set(values)))
        mapping = {name: values[0] for name, values in choices.items() if len(values) == 1}
        missing = result.office.eq(office) & result.district.isna()
        result.loc[missing, "district"] = result.loc[missing, "candidate_norm"].map(mapping)
    for (year, office, candidate), district in LEGISLATIVE_DISTRICT_OVERRIDES.items():
        mask=result.year.eq(year)&result.office.eq(office)&result.candidate_norm.eq(candidate)&result.district.isna()
        result.loc[mask,"district"]=district
    return result.drop(columns="candidate_norm")


def _wide_sheet(rows: list[list[object]], county: str) -> pd.DataFrame:
    if not rows: return pd.DataFrame()
    width = max(map(len, rows)); padded = [r + [""] * (width - len(r)) for r in rows]
    header, records = [str(x).strip() for x in padded[0]], []
    for row in padded[1:]:
        title, party, candidate = row[:3]
        if not str(title).strip() or is_pseudocandidate(candidate): continue
        office, district = _office(title)
        for precinct, votes in zip(header[3:], row[3:]):
            number = pd.to_numeric(votes, errors="coerce")
            if not precinct or pd.isna(number): continue
            records.append({"county": county, "precinct": precinct, "office": office,
                            "district": district, "party": party, "candidate": candidate,
                            "votes": float(number)})
    return pd.DataFrame(records)


def _county_matrix_sheets(sheets: dict[str, list[list[object]]], county: str) -> pd.DataFrame:
    """Read county-designed matrices with offices in row 1 and candidates in row 2."""
    records = []
    for rows in sheets.values():
        if len(rows) < 3: continue
        width = max(map(len, rows)); padded = [r + [""] * (width-len(r)) for r in rows]
        offices, candidates = padded[0], padded[1]
        carried = ""; office_at = []
        for value in offices:
            if str(value).strip(): carried = str(value).strip()
            office_at.append(carried)
        for row in padded[2:]:
            precinct = str(row[0]).strip()
            if not precinct or re.search(r"\bTOTALS?\b", precinct, re.I): continue
            for col in range(1, width):
                candidate = str(candidates[col]).strip()
                party_match = re.search(r"\(([DR])\s*\)", candidate, re.I)
                number = pd.to_numeric(row[col], errors="coerce")
                if not candidate or is_pseudocandidate(candidate) or pd.isna(number): continue
                office, district = _office(office_at[col])
                records.append({"county": county, "precinct": precinct, "office": office,
                                "district": district, "party": party_match.group(1) if party_match else "",
                                "candidate": re.sub(r"\s*\([DR]\s*\)\s*$", "", candidate, flags=re.I),
                                "votes": float(number)})
    return pd.DataFrame(records)


def _legacy_1994(rows: list[list[object]], county: str) -> pd.DataFrame:
    """Read the four-header-row 1994 county matrices.

    Alabama's export encodes the Democratic/Republican ballot columns as A/B
    or first/second variants rather than printing a party field.  The general
    election ballot order was Democratic then Republican; the code is retained
    as supporting evidence and the inferred party is explicitly flagged later.
    """
    if len(rows) < 5: return pd.DataFrame()
    width=max(map(len,rows)); padded=[r+[""]*(width-len(r)) for r in rows]
    offices, districts, candidates, codes=padded[:4]
    carried=""; carried_district=""; office_at=[]; district_at=[]
    for value,district_value in zip(offices,districts):
        if str(value).strip():
            carried=str(value).strip(); carried_district=""
        if str(district_value).strip(): carried_district=str(district_value).strip()
        office_at.append(carried); district_at.append(carried_district)
    groups={}
    for col in range(3,width):
        title=office_at[col]
        d=district_at[col]
        if d: title=f"{title}, {d}"
        groups.setdefault(title,[]).append(col)
    party_at={}
    for title,cols in groups.items():
        named=[c for c in cols if str(candidates[c]).strip() and not is_pseudocandidate(candidates[c])]
        for rank,col in enumerate(named):
            code=str(codes[col]).strip().upper()
            if code.startswith("A") or code.endswith("1") or rank==0: party_at[col]="D"
            elif code.startswith("B") or code.endswith("2") or rank==1: party_at[col]="R"
            else: party_at[col]=""
    records=[]
    for row in padded[4:]:
        precinct=str(row[1]).strip() or str(row[2]).strip()
        if not precinct or re.search(r"\bTOTALS?\b",precinct,re.I): continue
        for col in range(3,width):
            candidate=str(candidates[col]).strip(); number=pd.to_numeric(row[col],errors="coerce")
            if not candidate or is_pseudocandidate(candidate) or pd.isna(number): continue
            title=office_at[col]; d=district_at[col]
            if d: title=f"{title}, {d}"
            office,district=_office(title)
            records.append({"county":county,"precinct":precinct,"office":office,"district":district,
                            "party":party_at.get(col,""),"candidate":candidate,"votes":float(number),
                            "party_method":"ballot_order_with_export_code"})
    return pd.DataFrame(records)


def _legacy_1998(rows: list[list[object]], county: str) -> pd.DataFrame:
    """Read 1998 office/candidate column matrices."""
    if len(rows)<3:return pd.DataFrame()
    width=max(map(len,rows)); padded=[r+[""]*(width-len(r)) for r in rows]
    offices,candidates=padded[:2]; carried=""; office_at=[]
    for value in offices:
        if str(value).strip():carried=str(value).strip()
        office_at.append(carried)
    groups={}
    for col in range(1,width): groups.setdefault(office_at[col],[]).append(col)
    party_at={}
    for title,cols in groups.items():
        named=[c for c in cols if str(candidates[c]).strip() and not is_pseudocandidate(candidates[c])]
        # Only infer major parties when both major-party ballot positions exist.
        if len(named)>=2: party_at[named[0]]="D"; party_at[named[1]]="R"
    records=[]
    only_summary = len([r for r in padded[2:] if any(str(v).strip() for v in r)]) == 1
    for row in padded[2:]:
        precinct=str(row[0]).strip()
        if not precinct or (re.search(r"\bTOTALS?\b",precinct,re.I) and not only_summary):continue
        if only_summary and re.search(r"\bTOTALS?\b",precinct,re.I): precinct="COUNTY REPORTING TOTAL"
        for col in range(1,width):
            candidate=str(candidates[col]).strip(); number=pd.to_numeric(row[col],errors="coerce")
            if not candidate or is_pseudocandidate(candidate) or pd.isna(number):continue
            office,district=_office(office_at[col])
            records.append({"county":county,"precinct":precinct,"office":office,"district":district,
                            "party":party_at.get(col,""),"candidate":candidate,"votes":float(number),
                            "party_method":"ballot_order" if col in party_at else "unresolved"})
    return pd.DataFrame(records)


def _legacy_2002(rows: list[list[object]], county: str) -> pd.DataFrame:
    if len(rows)<4:return pd.DataFrame()
    width=max(map(len,rows)); padded=[r+[""]*(width-len(r)) for r in rows]
    header_row=next((i for i,r in enumerate(padded[:8]) if "Contest Title" in map(str,r)),None)
    if header_row is None:
        # Jefferson is transposed: contests are columns and precincts rows.
        labels={str(r[0]).strip().upper():i for i,r in enumerate(padded[:12]) if r}
        if not {"RACE","PARTY CODE","CANDIDATE","PRECINCT NAME"}.issubset(labels):return pd.DataFrame()
        office_row,party_row,candidate_row,start=(labels[x] for x in ("RACE","PARTY CODE","CANDIDATE","PRECINCT NAME"))
        records=[]
        for row in padded[start+1:]:
            precinct=str(row[0]).strip()
            if not precinct:continue
            for col in range(1,width):
                candidate=padded[candidate_row][col]; number=pd.to_numeric(row[col],errors="coerce")
                if not str(candidate).strip() or is_pseudocandidate(candidate) or pd.isna(number):continue
                office,district=_office(padded[office_row][col])
                records.append({"county":county,"precinct":precinct,"office":office,"district":district,
                                "party":padded[party_row][col],"candidate":candidate,"votes":float(number),
                                "party_method":"printed"})
        return pd.DataFrame(records)
    precincts=padded[header_row-1][5:]
    records=[]
    for row in padded[header_row+1:]:
        title,party,candidate=row[2:5]
        if not str(title).strip() or is_pseudocandidate(candidate):continue
        office,district=_office(title)
        for precinct,votes in zip(precincts[1:],row[6:]):
            number=pd.to_numeric(votes,errors="coerce")
            if not str(precinct).strip() or pd.isna(number):continue
            records.append({"county":county,"precinct":str(precinct).strip(),"office":office,
                            "district":district,"party":party,"candidate":candidate,"votes":float(number),
                            "party_method":"printed"})
    return pd.DataFrame(records)


def _legacy_2004(rows: list[list[object]], county: str) -> pd.DataFrame:
    if not rows:return pd.DataFrame()
    width=max(map(len,rows)); padded=[r+[""]*(width-len(r)) for r in rows]
    header=padded[0]; records=[]
    president_party={"GEORGE W BUSH":"R","JOHN F KERRY":"D"}
    from oe_normalize import normalize_name
    for row in padded[1:]:
        title,candidate=row[:2]
        if not str(title).strip() or is_pseudocandidate(candidate):continue
        office,district=_office(title); party=president_party.get(normalize_name(candidate),"")
        for precinct,votes in zip(header[3:],row[3:]):
            number=pd.to_numeric(votes,errors="coerce")
            if not str(precinct).strip() or pd.isna(number):continue
            records.append({"county":county,"precinct":str(precinct).strip(),"office":office,
                            "district":district,"party":party,"candidate":candidate,"votes":float(number),
                            "party_method":"candidate_dictionary" if party else "unresolved"})
    return pd.DataFrame(records)


def _legacy_candidate_header_matrix(sheets: dict[str,list[list[object]]],county: str) -> pd.DataFrame:
    """Read county-designed sheets whose header embeds ``Name - D/R``."""
    records=[]
    for rows in sheets.values():
        if len(rows)<3:continue
        width=max(map(len,rows)); padded=[r+[""]*(width-len(r)) for r in rows]
        header_row=next((i for i,r in enumerate(padded[:10]) if any(str(v).strip().upper()=="PRECINCT" for v in r)),None)
        if header_row is None:continue
        precinct_col=next(i for i,v in enumerate(padded[header_row]) if str(v).strip().upper()=="PRECINCT")
        candidates=padded[header_row]; offices=padded[max(0,header_row-1)]
        carried=""; office_at=[]
        for value in offices:
            if str(value).strip():carried=str(value).strip()
            office_at.append(carried)
        for row in padded[header_row+1:]:
            precinct=str(row[precinct_col]).strip()
            if not precinct or re.search(r"\bTOTALS?\b",precinct,re.I):continue
            for col in range(precinct_col+1,width):
                label=str(candidates[col]).strip(); number=pd.to_numeric(row[col],errors="coerce")
                match=re.search(r"\s+-\s+([DR])\s*$",label,re.I)
                if not label or is_pseudocandidate(label) or pd.isna(number):continue
                office,district=_office(office_at[col]); candidate=re.sub(r"\s+-\s+[A-Z]+\s*$","",label,flags=re.I)
                records.append({"county":county,"precinct":precinct,"office":office,"district":district,
                                "party":match.group(1) if match else "","candidate":candidate,"votes":float(number),
                                "party_method":"printed" if match else "unresolved"})
    return pd.DataFrame(records)


def _legacy_2008(sheets: dict[str,list[list[object]]],county: str) -> pd.DataFrame:
    records=[]
    for rows in sheets.values():
        if len(rows)<3:continue
        width=max(map(len,rows)); padded=[r+[""]*(width-len(r)) for r in rows]
        candidate_row=next((i for i,r in enumerate(padded[:8]) if
                            sum(bool(re.search(r"\((?:DEM|REP|D|R)\)",str(v),re.I)) for v in r)>=2
                            or ({"BARACK OBAMA","JOHN MCCAIN"} <= {re.sub(r"[^A-Z ]","",str(v).upper()).strip() for v in r})),None)
        if candidate_row is None:continue
        office_row=max(0,candidate_row-1); offices=padded[office_row]; candidates=padded[candidate_row]
        carried=""; office_at=[]
        for value in offices:
            if str(value).strip() and str(value).strip().upper() not in {"PRECINCT","GENERAL 2008"}:carried=str(value).strip()
            office_at.append(carried)
        for row in padded[candidate_row+1:]:
            precinct=str(row[0]).strip()
            if not precinct or re.search(r"\bTOTALS?\b",precinct,re.I):continue
            for col in range(1,width):
                label=str(candidates[col]).strip(); match=re.search(r"\((DEM|REP|D|R)\)\s*$",label,re.I)
                number=pd.to_numeric(row[col],errors="coerce")
                if not label or is_pseudocandidate(label) or pd.isna(number):continue
                office,district=_office(office_at[col]); party=match.group(1) if match else ""
                candidate=re.sub(r"\s*\((?:DEM|REP|D|R)\)\s*$","",label,flags=re.I)
                if not party:
                    key=re.sub(r"[^A-Z ]","",candidate.upper()).strip()
                    party={"BARACK OBAMA":"D","JOHN MCCAIN":"R"}.get(key,"")
                records.append({"county":county,"precinct":precinct,"office":office,"district":district,
                                "party":party,"candidate":candidate,"votes":float(number),
                                "party_method":"printed" if party else "unresolved"})
    return pd.DataFrame(records)


def _contest_sheets(sheets: dict[str, list[list[object]]], county: str) -> pd.DataFrame:
    """Read 2010/2012 contest sheets; party is blank pending reviewed mapping."""
    records = []
    for name, rows in sheets.items():
        if name in {"Table of Contents", "Registered Voters"} or len(rows) < 4: continue
        office, district = _office(rows[0][0] if rows[0] else "")
        candidates, headers = rows[1], rows[2]
        # Candidate labels occupy the first cell of a merged Polling/Total
        # pair. Spreadsheet readers expose the second cell as blank.
        carried = ""
        candidate_at = []
        for value in candidates:
            if str(value).strip(): carried = str(value).strip()
            candidate_at.append(carried)
        candidate_at.extend([carried] * (len(headers) - len(candidate_at)))
        columns = [(i, candidate_at[i]) for i, h in enumerate(headers)
                   if str(h).strip().upper() == "TOTAL VOTES" and i < len(candidate_at)
                   and candidate_at[i]]
        for row in rows[3:]:
            if not row or not str(row[0]).strip() or re.search(r"\bTOTALS?\b", str(row[0]), re.I): continue
            for col, candidate in columns:
                number = pd.to_numeric(row[col] if col < len(row) else None, errors="coerce")
                if pd.isna(number): continue
                records.append({"county": county, "precinct": str(row[0]).strip(), "office": office,
                                "district": district, "party": "", "candidate": candidate,
                                "votes": float(number)})
    return pd.DataFrame(records)


def normalize_workbook(content: bytes, county: str, year: int) -> pd.DataFrame:
    sheets = _workbook_sheets(content)
    if year == 1994:
        data = pd.concat([_legacy_1994(rows, county) for rows in sheets.values()], ignore_index=True)
    elif year == 1998:
        data = pd.concat([_legacy_1998(rows, county) for rows in sheets.values()], ignore_index=True)
    elif year == 2002:
        data = pd.concat([_legacy_2002(rows, county) for rows in sheets.values()], ignore_index=True)
    elif year == 2004:
        data = pd.concat([_legacy_2004(rows, county) for rows in sheets.values()], ignore_index=True)
        if data.empty: data = _legacy_candidate_header_matrix(sheets, county)
    elif year == 2008:
        data = _legacy_2008(sheets, county)
    else:
        data = pd.DataFrame()
    wide_name = next((name for name, rows in sheets.items() if rows and len(rows[0]) >= 3
                      and str(rows[0][0]).strip() in {"Contest Title", "Office"}), None)
    if data.empty and wide_name:
        rows = sheets[wide_name]
        # Normalize Jefferson's harmless header spelling difference.
        rows[0][1:3] = ["Party", "Candidate"]
        data = _wide_sheet(rows, county)
    elif data.empty and "Precinct Results" in sheets:
        data = _wide_sheet(sheets["Precinct Results"], county)
    elif data.empty:
        data = _contest_sheets(sheets, county)
        if data.empty:
            data = _county_matrix_sheets(sheets, county)
        if data.empty and year in (2004, 2006):
            data = _legacy_candidate_header_matrix(sheets, county)
    if data.empty: return data
    data["year"] = year; data["party_norm"] = data["party"].map(norm_party)
    data["county_key"] = data["county"].str.upper().str.strip()
    data["precinct_key"] = data["precinct"].str.upper().str.strip()
    return data


def normalize_csv(content: bytes, county: str, year: int) -> pd.DataFrame:
    """Normalize the two 2014 county CSV exports.

    The vendor reused the ``Registered Voters`` heading for its numeric result
    field; inspection of contest/candidate rows confirms it contains votes.
    """
    raw = pd.read_csv(io.BytesIO(content), dtype=str).fillna("")
    records = []
    for _, row in raw.iterrows():
        title = row["Contest Title"]
        candidate = row["Candidate Name"]
        if is_pseudocandidate(candidate): continue
        number = pd.to_numeric(row["Registered Voters"], errors="coerce")
        if pd.isna(number): continue
        office, district = _office(title)
        records.append({"county": county, "precinct": row["Precinct Name"].strip(),
                        "office": office, "district": district, "party": row["Party Code"],
                        "candidate": candidate.strip(), "votes": float(number)})
    data = pd.DataFrame(records)
    if data.empty: return data
    data["year"] = year; data["party_norm"] = data.party.map(norm_party)
    data["county_key"] = data.county.str.upper().str.strip(); data["precinct_key"] = data.precinct.str.upper().str.strip()
    return data


def _county_from_filename(name: str, year: int) -> str:
    stem = Path(name).stem
    stem = re.sub(rf"^{year}[-_ ]*GENERAL[-_ ]*", "", stem, flags=re.I)
    stem = re.sub(rf"\s+{year}\s+GENERAL\s+PRECINCT.*$", "", stem, flags=re.I)
    stem = re.sub(r"\s+GENERAL\s+PRECINCT.*$", "", stem, flags=re.I)
    return stem.replace("_", " ").strip()


def load_sos_year(root: Path, year: int) -> pd.DataFrame:
    base, source = root / "data" / "raw" / "alabama_elections_and_geography", YEAR_SOURCES[year]
    if source.lower().endswith((".xls", ".xlsx")):
        path=base/source
        sheets=_workbook_sheets(path.read_bytes()); parts=[]
        for county,rows in sheets.items():
            content_sheets={county:rows}
            data = (_legacy_2002(rows, county) if year==2002 else _legacy_2008(content_sheets, county))
            if not data.empty:
                data["year"]=year; data["party_norm"]=data.party.map(norm_party)
                data["county_key"]=data.county.str.upper().str.strip(); data["precinct_key"]=data.precinct.str.upper().str.strip()
                data["source_file"]=f"{source}::{county}"; parts.append(data)
        if len(sheets)!=67: raise AssertionError(f"SOS {year}: expected 67 county sheets, found {len(sheets)}")
        return _repair_legislative_metadata(pd.concat(parts,ignore_index=True))
    directory, archive, parts = base / source, base / f"{source}.zip", []
    # Prefer the immutable official ZIP. Extracted directories are convenient
    # but may be partial or manually modified.
    files_seen = 0
    if archive.exists():
        with ZipFile(archive) as zipped:
            for name in sorted(zipped.namelist()):
                if Path(name).suffix.lower() in {".xls", ".xlsx", ".csv"}:
                    if Path(name).stem.upper() == "PRINT1":
                        continue
                    files_seen += 1
                    content = zipped.read(name)
                    part = (normalize_csv(content, _county_from_filename(name, year), year)
                            if Path(name).suffix.lower() == ".csv" else
                            normalize_workbook(content, _county_from_filename(name, year), year))
                    if not part.empty:
                        part["source_file"] = name
                        parts.append(part)
    elif directory.exists():
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() in {".xls", ".xlsx"}:
                files_seen += 1
                part = normalize_workbook(path.read_bytes(), _county_from_filename(path.name, year), year)
                if not part.empty:
                    part["source_file"] = path.name
                    parts.append(part)
    else: raise FileNotFoundError(f"No SOS source for {year}: {source}")
    if files_seen != 67:
        raise AssertionError(f"SOS {year}: expected 67 county workbooks, found {files_seen}")
    result = pd.concat(parts, ignore_index=True)
    return _repair_legislative_metadata(result)
