"""Inventory and optionally archive crosstab documents linked by VoteHub polls.

VoteHub exposes poll toplines, not crosstabs. This script treats the API as a
catalog, visits each poll's source page, discovers likely tabulation files, and
records an auditable manifest. It deliberately does not infer crosstabs from
prose or charts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.votehub.com/polls"
RAW = ROOT / "data" / "raw" / "polling" / "votehub_crosstabs"
OUT = ROOT / "data" / "processed" / "polling"
ASSET_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv"}
LINK_HINT = re.compile(r"cross.?tab|tabulation|topline|full.?result|questionnaire|data", re.I)
CROSSTAB_HINT = re.compile(r"cross.?tab|tab.?report|tabulation|banner|full.?result", re.I)
TOPLINE_HINT = re.compile(r"topline|methodology|questionnaire", re.I)


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")[:120] or "source"


def discover_assets(page_url: str, content: bytes, content_type: str) -> list[dict]:
    suffix = Path(urlparse(page_url).path).suffix.lower()
    if suffix in ASSET_EXTENSIONS or any(x in content_type.lower() for x in ("pdf", "spreadsheet", "csv")):
        return [{"asset_url": page_url, "link_text": "direct source", "asset_kind": suffix.lstrip(".") or "document"}]
    if "html" not in content_type.lower():
        return []
    soup = BeautifulSoup(content, "html.parser")
    found: dict[str, dict] = {}
    for anchor in soup.find_all("a", href=True):
        href = urljoin(page_url, anchor["href"])
        text = " ".join(anchor.get_text(" ", strip=True).split())
        ext = Path(urlparse(href).path).suffix.lower()
        if ext in ASSET_EXTENSIONS or LINK_HINT.search(f"{text} {href}"):
            found[href] = {"asset_url": href, "link_text": text[:250],
                           "asset_kind": ext.lstrip(".") or "linked_page"}
    return list(found.values())


def inspect_poll(poll: dict, headers: dict[str, str], download: bool = False) -> list[dict]:
    rows: list[dict] = []
    session = requests.Session()
    session.headers.update(headers)
    base = {k: poll.get(k) for k in ("id", "pollster", "start_date", "end_date", "population",
                                     "sample_size", "internal", "partisan", "url")}
    url = poll.get("url")
    if not url:
        return [{**base, "status": "missing_source_url"}]
    try:
        response = session.get(url, timeout=12)
        response.raise_for_status()
        ctype = response.headers.get("content-type", "")
        assets = discover_assets(response.url, response.content, ctype)
        if not assets:
            return [{**base, "resolved_url": response.url, "status": "no_document_discovered"}]
        for asset in assets:
            row = {**base, "resolved_url": response.url, **asset, "status": "document_discovered"}
            if download and asset["asset_kind"] in {"pdf", "xlsx", "xls", "csv"}:
                try:
                    doc = session.get(asset["asset_url"], timeout=30)
                    doc.raise_for_status()
                    digest = hashlib.sha256(doc.content).hexdigest()
                    ext = Path(urlparse(doc.url).path).suffix.lower()
                    if ext not in ASSET_EXTENSIONS:
                        ext = {"application/pdf": ".pdf", "text/csv": ".csv"}.get(
                            doc.headers.get("content-type", "").split(";")[0], ".bin")
                    target = RAW / f"{safe_name(str(poll.get('id')))}_{digest[:12]}{ext}"
                    target.write_bytes(doc.content)
                    row.update(status="archived", local_path=str(target.relative_to(ROOT)),
                               sha256=digest, bytes=len(doc.content), retrieved_on=date.today().isoformat())
                except requests.RequestException as exc:
                    row.update(status="asset_download_error", error=str(exc)[:500])
            rows.append(row)
    except requests.RequestException as exc:
        rows.append({**base, "status": "source_request_error", "error": str(exc)[:500]})
    return rows


def inventory(polls: list[dict], session: requests.Session, download: bool = False,
              workers: int = 8) -> pd.DataFrame:
    rows = []
    if download:
        RAW.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(inspect_poll, poll, dict(session.headers), download) for poll in polls]
        for future in as_completed(futures):
            rows.extend(future.result())
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", default="2026-01-01")
    parser.add_argument("--to-date")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    params = {"poll_type": "generic-ballot", "from_date": args.from_date}
    if args.to_date:
        params["to_date"] = args.to_date
    session = requests.Session()
    session.headers["User-Agent"] = "Jackson-Hannan-Alabama-forecast/1.0 crosstab research"
    response = session.get(API, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    polls = payload["polls"] if isinstance(payload, dict) else payload
    OUT.mkdir(parents=True, exist_ok=True)
    (RAW.parent / "votehub_generic_ballot_catalog.json").write_text(json.dumps(polls, indent=2), encoding="utf-8")
    result = inventory(polls, session, args.download, args.workers)
    result.to_csv(OUT / "votehub_crosstab_source_manifest.csv", index=False)
    documents = result[result.asset_kind.isin({"pdf", "xlsx", "xls", "csv"})].copy()
    hint_text = (documents.link_text.fillna("") + " " + documents.asset_url.fillna(""))
    documents["review_priority"] = np.select(
        [documents.asset_kind.isin({"xlsx", "xls", "csv"}) | hint_text.str.contains(CROSSTAB_HINT),
         hint_text.str.contains(TOPLINE_HINT)],
        ["high_likely_crosstabs", "low_likely_topline_or_methodology"],
        default="medium_document_requires_review")
    documents = documents.sort_values(["review_priority", "end_date", "pollster"], ascending=[True, False, True])
    documents.to_csv(OUT / "votehub_crosstab_document_review_queue.csv", index=False)
    summary = result.groupby("status", dropna=False).size().rename("rows").reset_index()
    summary.to_csv(OUT / "votehub_crosstab_source_coverage.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
