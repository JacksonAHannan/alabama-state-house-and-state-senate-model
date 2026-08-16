"""Discover historical Alabama legislative candidate IDs from public election pages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scrape_votesmart_public import HOST, OUT, RAW, USER_AGENT, clean


YEARS = (1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022)


def parse_candidates(html: str, year: int, source_url: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: dict[int, dict[str, object]] = {}
    for link in soup.find_all("a", href=re.compile(r"^/candidate/\d+/")):
        match = re.match(r"^/candidate/(\d+)/([^/?#]+)", link.get("href", ""))
        if not match:
            continue
        candidate_id = int(match.group(1))
        name = clean(link.get_text(" ", strip=True))
        if not name:
            continue
        candidate_col = link.find_parent("div", id="electionsDetailsResultsCol")
        contest = candidate_col.find_previous_sibling("div", class_="col-md-12") if candidate_col else None
        contest_text = clean(contest.get_text(" ", strip=True)) if contest else ""
        office = re.search(r"State (House|Senate)", contest_text, flags=re.I)
        district = re.search(r"District\s+(\d+)", contest_text, flags=re.I)
        media = link.find_parent("div", class_="media")
        details = media.find_all("h5", class_="title") if media else []
        outcome = clean(details[0].get_text(" ", strip=True)).strip("()") if details else ""
        party = clean(details[1].get_text(" ", strip=True)) if len(details) > 1 else ""
        rows[candidate_id] = {
            "election_year": year,
            "votesmart_candidate_id": candidate_id,
            "candidate": name,
            "chamber": office.group(1).lower() if office else "",
            "district": int(district.group(1)) if district else None,
            "party": party,
            "outcome": outcome,
            "profile_slug": match.group(2),
            "profile_url": urljoin(HOST, link["href"]),
            "source_url": source_url,
        }
    return list(rows.values())


def last_page(html: str) -> int:
    pages = [int(value) for value in re.findall(r"[?&]p=(\d+)", html)]
    return max(pages, default=1)


def discover(delay: float = 1.0, refresh: bool = False) -> list[dict[str, object]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html"})
    records: list[dict[str, object]] = []
    manifest: list[dict[str, object]] = []
    RAW.mkdir(parents=True, exist_ok=True)
    for year in YEARS:
        base = f"{HOST}/election/{year}/L/AL/{year}-state-legislative-election"
        page = 1
        total_pages = 1
        while page <= total_pages:
            target = RAW / f"election_{year}_general_page_{page}.html"
            url = f"{base}?stageId=G&p={page}"
            if target.exists() and not refresh:
                html = target.read_text(encoding="utf-8")
            else:
                response = session.get(base, params={"stageId": "G", "p": page}, timeout=45)
                response.raise_for_status()
                html = response.text
                target.write_text(html, encoding="utf-8")
                time.sleep(max(delay, 0.25))
            total_pages = max(total_pages, last_page(html))
            page_rows = parse_candidates(html, year, url)
            records.extend(page_rows)
            content = html.encode("utf-8")
            manifest.append(
                {
                    "year": year,
                    "page": page,
                    "source_url": url,
                    "candidate_count": len(page_rows),
                    "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
            page += 1
        print(f"Discovered {sum(row['election_year'] == year for row in records):,} candidates for {year}")
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / "votesmart_public_candidate_roster.csv"
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    (RAW / "manifest_election_pages.json").write_text(
        json.dumps(
            {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "files": manifest},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(records):,} candidate-election rows ({len({r['votesmart_candidate_id'] for r in records}):,} unique people)")
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    discover(args.delay, args.refresh)


if __name__ == "__main__":
    main()
