"""Cache and warehouse every public DOJ Section 5 notice entry for Alabama."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from warehouse import (ROOT, begin_run, connect, finish_run, initialize,
                       register_source_file, register_table, utcnow)

INDEX_URL = "https://www.justice.gov/crt/archive-notices-section-5-submission-activity"
RAW = ROOT / "data" / "raw" / "doj" / "section5_notices"
OUT = ROOT / "data" / "processed" / "precinct_history"
SCHEMA = Path(__file__).with_name("warehouse_precinct_history_schema.sql")
USER_AGENT = "alabama-legislative-cmo-research/1.0 (historical GIS research)"
PRECINCT_PATTERN = re.compile(
    r"\b(?:voting\s+)?precincts?\b|\bpolling[- ]places?\b|\bvoting\s+(?:district|box)(?:es)?\b|"
    r"\brealign(?:ment|ed)?\b|\bdeconsolidat(?:e|ion)\b|\bconsolidat(?:e|ion)\b|"
    r"\brenumber(?:ed|ing)?\b|\bredesignat(?:e|ed|ion)\b|\bboundar(?:y|ies)\b|"
    r"\b(?:divide|division|split)\b", re.I)
ACTIVITY_PATTERNS = (
    "Additional information received", "Related submission received", "Submission received",
    "Withdrawal received", "Notice of withdrawal", "Request for reconsideration",
    "Objection interposed", "Declaratory judgment action", "Expedited Consideration Requested",
)


def stable_id(prefix: str, *parts: object) -> str:
    token = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:20].upper()
    return f"{prefix}-{token}"


def notice_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    xls_by_stem = {}
    for anchor in soup.select("a[href]"):
        url = urljoin(INDEX_URL, anchor["href"])
        if url.lower().endswith((".xls", ".xlsx")):
            xls_by_stem[Path(url).stem.lower()] = url
    notices = []
    for anchor in soup.select("a[href]"):
        label = " ".join(anchor.stripped_strings)
        match = re.fullmatch(r"Notice of (.+)", label, re.I)
        if not match:
            continue
        notice_date = pd.to_datetime(match.group(1), errors="coerce")
        if pd.isna(notice_date):
            continue
        notice_url = urljoin(INDEX_URL, anchor["href"])
        stem = Path(notice_url).stem.lower()
        # The DOJ index currently labels its March 11, 2013 notice as 2023.
        # Prefer the encoded MMDDYY filename when the label falls outside the
        # public Section 5 notice period.
        encoded = re.search(r"(\d{6})$", stem)
        if notice_date.year > 2013 and encoded:
            notice_date = pd.to_datetime(encoded.group(1), format="%m%d%y", errors="coerce")
        source_url = xls_by_stem.get(stem, notice_url)
        fmt = "xls" if source_url.lower().endswith((".xls", ".xlsx")) else "html"
        notices.append({"notice_date": notice_date.date().isoformat(), "source_url": source_url,
                        "source_format": fmt, "notice_id": stable_id("DOJNOTICE", notice_date.date())})
    return list({row["notice_id"]: row for row in notices}.values())


def fetch_one(item: dict, refresh: bool = False) -> dict:
    suffix = ".xls" if item["source_format"] == "xls" else ".html"
    path = RAW / f'{item["notice_date"]}{suffix}'
    if refresh or not path.exists():
        response = None
        for attempt in range(4):
            response = requests.get(item["source_url"], headers={"User-Agent": USER_AGENT}, timeout=60)
            if response.ok: break
            if response.status_code not in {403, 429, 500, 502, 503, 504}: response.raise_for_status()
            time.sleep(1.5 * (attempt + 1))
        assert response is not None
        response.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
    return {**item, "local_path": path}


def _clean(value: object) -> str | None:
    if value is None or pd.isna(value): return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def parse_xls(item: dict) -> list[dict]:
    frame = pd.read_excel(item["local_path"], header=None)
    rows = []
    for order, row in frame.iterrows():
        state = _clean(row.iloc[0] if len(row) > 0 else None)
        submission = _clean(row.iloc[10] if len(row) > 10 else None)
        if not state or not submission or not re.fullmatch(r"\d{4}-\d+", submission):
            continue
        raw = " | ".join(_clean(value) for value in row if _clean(value))
        rows.append({"row_order": int(order), "activity_date": _date(row.iloc[14]),
                     "submission_number": submission, "state": state.upper(),
                     "county": _clean(row.iloc[3]), "subjurisdiction": _clean(row.iloc[6]),
                     "activity": _clean(row.iloc[17]), "change_description": _clean(row.iloc[24]),
                     "raw_text": raw})
    return rows


def _date(value: object) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date().isoformat()


def parse_html(item: dict) -> list[dict]:
    payload = item["local_path"].read_bytes()
    if payload.lstrip().startswith(b"%PDF"):
        return parse_pdf(item)
    soup = BeautifulSoup(payload, "html.parser")
    table = soup.select_one("table")
    if table is None: return []
    rows, pending = [], None
    for order, tr in enumerate(table.select("tr")):
        text = re.sub(r"\s+", " ", tr.get_text(" ", strip=True)).strip()
        header = re.search(r"(\d{2}/\d{2}/\d{2,4})\s*-\s*(\d{2,4}-\d+)", text)
        if header:
            pending = (_date(header.group(1)), header.group(2), order)
            continue
        if pending is None or "State" not in text:
            continue
        lines = [re.sub(r"^:\s*", "", line.strip())
                 for line in tr.get_text("\n", strip=True).splitlines() if line.strip()]
        fields, remainder, index = {}, [], 0
        while index < len(lines):
            if lines[index] in {"State", "County", "Parish", "Subjurisdiction"} and index + 1 < len(lines):
                key = "County" if lines[index] == "Parish" else lines[index]
                fields[key] = lines[index + 1]; index += 2
            else:
                remainder.append(lines[index]); index += 1
        activities = [line for line in remainder if any(term.lower() in line.lower() for term in ACTIVITY_PATTERNS)]
        descriptions = [line for line in remainder if line not in activities]
        rows.append({"row_order": pending[2], "activity_date": pending[0],
                     "submission_number": pending[1], "state": fields.get("State", "").upper(),
                     "county": fields.get("County"), "subjurisdiction": fields.get("Subjurisdiction"),
                     "activity": "; ".join(activities) or None,
                     "change_description": "; ".join(descriptions) or None,
                     "raw_text": text})
        pending = None
    return rows


def parse_pdf(item: dict) -> list[dict]:
    from pypdf import PdfReader

    text = "\n".join(page.extract_text() or "" for page in PdfReader(item["local_path"]).pages)
    matches = list(re.finditer(r"Submission Number:\s*(\d{4}-\d+)", text, flags=re.I))
    rows = []
    previous_end = 0
    for order, match in enumerate(matches):
        block = text[previous_end:match.end()]
        previous_end = match.end()
        state_hits = list(re.finditer(
            r"(?m)^\s*([A-Z][A-Z ]+?)\s+(?=(?:Subjurisdiction|County|Parish|Action Date):)", block))
        if not state_hits:
            continue
        state_match = state_hits[-1]
        block = block[state_match.start():]
        def field(name: str) -> str | None:
            found = re.search(rf"\b{name}:\s*([^\n]+)", block, flags=re.I)
            return _clean(found.group(1)) if found else None
        activity_date = field("Action Date")
        activity = next((line.strip() for line in block.splitlines()
                         if any(term.lower() in line.lower() for term in ACTIVITY_PATTERNS)), None)
        after_date = re.split(r"Action Date:\s*[^\n]+\n", block, maxsplit=1, flags=re.I)
        body_lines = [line.strip() for line in (after_date[1] if len(after_date) == 2 else "").splitlines()
                      if line.strip() and not line.lower().startswith("submission number:")]
        description = next((line for line in body_lines if line != activity), None)
        rows.append({"row_order": order, "activity_date": _date(activity_date),
                     "submission_number": match.group(1), "state": state_match.group(1).strip(),
                     "county": field("County") or field("Parish"),
                     "subjurisdiction": field("Subjurisdiction"), "activity": activity,
                     "change_description": description, "raw_text": re.sub(r"\s+", " ", block).strip()})
    return rows


def parse_notice(item: dict) -> list[dict]:
    rows = parse_xls(item) if item["source_format"] == "xls" else parse_html(item)
    for row in rows:
        row["notice_id"] = item["notice_id"]
        row["entry_id"] = stable_id("DOJENTRY", item["notice_id"], row["row_order"], row["submission_number"])
    return rows


def aggregate_submissions(alabama: pd.DataFrame) -> pd.DataFrame:
    records = []
    for submission, group in alabama.groupby("submission_number", dropna=False):
        descriptions = sorted(set(group.change_description.dropna().astype(str)))
        activities = sorted(set(group.activity.dropna().astype(str)))
        terms = sorted(set(match.group(0).lower() for value in descriptions
                           for match in PRECINCT_PATTERN.finditer(value)))
        activity_text = " | ".join(activities).lower()
        records.append({"submission_number": submission, "state": "ALABAMA",
            "county": " | ".join(sorted(set(group.county.dropna().astype(str)))) or None,
            "subjurisdiction": " | ".join(sorted(set(group.subjurisdiction.dropna().astype(str)))) or None,
            "first_activity_date": group.activity_date.dropna().min() if group.activity_date.notna().any() else None,
            "last_activity_date": group.activity_date.dropna().max() if group.activity_date.notna().any() else None,
            "first_notice_date": group.notice_date.min(), "last_notice_date": group.notice_date.max(),
            "descriptions": " | ".join(descriptions), "activities": " | ".join(activities),
            "notice_count": group.notice_id.nunique(), "entry_count": len(group),
            "withdrawn": int("withdraw" in activity_text), "objected": int("objection" in activity_text),
            "precinct_candidate": int(bool(terms)), "precinct_terms": " | ".join(terms),
            "classification_status": "keyword_candidate" if terms else "retained_non_candidate"})
    return pd.DataFrame(records)


def event_types(description: str) -> list[str]:
    text = description.lower()
    types = []
    tests = [
        ("split", (" split", "division", "divide")),
        ("consolidate", ("consolidat", "merge")),
        ("countywide_realignment", ("countywide", "county-wide")),
        ("boundary_adjustment", ("boundar", "realign")),
        ("rename", ("rename", "name change")),
        ("renumber", ("renumber", "number change")),
        ("redesignate", ("redesignat", "designation")),
        ("polling_place_change", ("polling place", "polling-place", "voting place")),
        ("create", ("creation", "create", "establish")),
        ("abolish", ("abolish", "eliminat", "discontinu")),
    ]
    for change_type, terms in tests:
        if any(term in text for term in terms):
            types.append(change_type)
    return types or ["unknown"]


def provisional_events(submissions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    events, relationships = [], []
    for row in submissions[submissions.precinct_candidate.eq(1)].itertuples(index=False):
        types = event_types(row.descriptions or "")
        event_id = f"DOJ-{row.submission_number}"
        geometry_types = {"create", "abolish", "split", "consolidate", "boundary_adjustment", "countywide_realignment"}
        designation_types = {"rename", "renumber", "redesignate"}
        events.append({
            "event_id": event_id, "county_fips": None, "county_name": row.county,
            "resolution_number": None, "adoption_date": None, "effective_date": None,
            "change_type": types[0], "geometry_changed": int(bool(set(types) & geometry_types)),
            "designation_changed": int(bool(set(types) & designation_types)),
            "polling_place_changed": int("polling_place_change" in types),
            "description": row.descriptions, "doj_submission_number": row.submission_number,
            "doj_status": row.activities, "source_file_id": None, "confidence": "medium",
            "verification_status": "documentary_candidate",
        })
        relationships.extend({"event_id": event_id, "change_type": item} for item in types)
    return pd.DataFrame(events), pd.DataFrame(relationships)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--cached-only", action="store_true"); args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    index_path = RAW / "archive_index.html"
    if args.refresh or not index_path.exists():
        response = requests.get(INDEX_URL, headers={"User-Agent": USER_AGENT}, timeout=60); response.raise_for_status()
        index_path.write_bytes(response.content)
    inventory = notice_inventory(index_path.read_text(encoding="utf-8", errors="replace"))
    fetched, failures = [], []
    if args.cached_only:
        for item in inventory:
            suffix = ".xls" if item["source_format"] == "xls" else ".html"
            path = RAW / f'{item["notice_date"]}{suffix}'
            if path.exists(): fetched.append({**item,"local_path":path})
            else: failures.append({**item,"error":"not_cached"})
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(fetch_one, item, args.refresh): item for item in inventory}
            for number, future in enumerate(as_completed(futures), 1):
                try:
                    fetched.append(future.result())
                except Exception as error:
                    failures.append({**futures[future], "error": repr(error)})
                if number % 100 == 0: print(f"Cached {number}/{len(futures)} notices", flush=True)
    (OUT / "doj_notice_download_failures.json").write_text(
        json.dumps(failures, indent=2, default=str), encoding="utf-8")
    if failures:
        print(f"WARNING: {len(failures)} notice downloads failed; see failure manifest", flush=True)
    all_entries = []
    for item in sorted(fetched, key=lambda row: row["notice_date"]):
        all_entries.extend(parse_notice(item))
    entries = pd.DataFrame(all_entries)
    if entries.empty: raise RuntimeError("No DOJ notice entries parsed")
    notices = pd.DataFrame([{k: item[k] for k in ("notice_id","notice_date","source_url","source_format")}
                            for item in fetched])
    entries = entries.merge(notices[["notice_id","notice_date"]], on="notice_id", validate="many_to_one")
    alabama = entries[entries.state.str.upper().eq("ALABAMA")].copy()
    submissions = aggregate_submissions(alabama)
    events, event_type_rows = provisional_events(submissions)
    alabama.to_csv(OUT / "doj_all_alabama_submission_entries.csv", index=False)
    submissions.to_csv(OUT / "doj_alabama_submission_history.csv", index=False)
    submissions[submissions.precinct_candidate.eq(1)].to_csv(OUT / "doj_precinct_candidate_submissions.csv", index=False)
    (OUT / "doj_ingest_summary.json").write_text(json.dumps({"notices":len(notices),
      "inventory_notices":len(inventory),"download_failures":len(failures),
      "all_entries":len(entries),"alabama_entries":len(alabama),"alabama_submissions":len(submissions),
      "precinct_candidates":int(submissions.precinct_candidate.sum())},indent=2),encoding="utf-8")

    with connect() as connection:
        initialize(connection); connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run = begin_run(connection,"doj_section5_precinct_history",{"index_url":INDEX_URL,"notices":len(notices)})
        source_ids = {}
        for item in fetched:
            source_ids[item["notice_id"]] = register_source_file(connection,provider="usdoj_crt_section5",
              path=item["local_path"],original_url=item["source_url"],
              media_type="application/vnd.ms-excel" if item["source_format"]=="xls" else "text/html",
              extraction_status="normalized",authoritative_scope="section5_submission_notice")
        notice_rows = notices.copy(); notice_rows["source_file_id"] = notice_rows.notice_id.map(source_ids)
        notice_rows["parsed_at_utc"] = utcnow()
        connection.execute("DELETE FROM precinct_change_event_type WHERE event_id LIKE 'DOJ-%'")
        connection.execute("DELETE FROM precinct_change_event WHERE event_id LIKE 'DOJ-%'")
        connection.execute("DELETE FROM canonical_doj_section5_submission")
        connection.execute("DELETE FROM source_doj_section5_entry")
        connection.execute("DELETE FROM source_doj_section5_notice")
        notice_rows[["notice_id","notice_date","source_file_id","source_url","source_format","parsed_at_utc"]].to_sql(
            "source_doj_section5_notice",connection,index=False,if_exists="append")
        entries.drop(columns="notice_date").to_sql("source_doj_section5_entry",connection,index=False,if_exists="append")
        submissions.to_sql("canonical_doj_section5_submission",connection,index=False,if_exists="append")
        if not events.empty:
            events.to_sql("precinct_change_event",connection,index=False,if_exists="append")
            event_type_rows.to_sql("precinct_change_event_type",connection,index=False,if_exists="append")
        for name,layer,key,description in [
          ("source_doj_section5_notice","source","notice_id","Cached DOJ weekly notice files"),
          ("source_doj_section5_entry","source","entry_id","Every parsed Section 5 notice entry"),
          ("canonical_doj_section5_submission","canonical","submission_number","Alabama submission lifecycle aggregation")]:
            register_table(connection,name,layer,"scripts/ingest_doj_section5_precinct_history.py",key,
                           "DOJ notice retained verbatim; classification stored separately","replace",description)
        register_table(connection,"precinct_change_event","canonical","scripts/ingest_doj_section5_precinct_history.py",
          "event_id","DOJ keyword hits are documentary candidates, never confirmed events","replace",
          "Source-backed precinct change events and candidates")
        finish_run(connection,run,{"notices":len(notices),"entries":len(entries),"alabama_entries":len(alabama),
                                  "submissions":len(submissions),"precinct_candidates":int(submissions.precinct_candidate.sum())})
        connection.commit()
    print((OUT / "doj_ingest_summary.json").read_text())


if __name__ == "__main__": main()
