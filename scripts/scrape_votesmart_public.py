"""Cache and parse public Vote Smart candidate ideology pages.

This collector uses only ordinary public HTML returned with HTTP 200. It does
not authenticate, evade blocks, or render hidden endpoints. Cached pages make
the run resumable and avoid repeatedly requesting the same source.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ideology" / "votesmart_public"
OUT = ROOT / "data" / "processed" / "ideology"
HOST = "https://j.futurefacts.votesmart.io"
USER_AGENT = "alabama-legislative-cmo-research/1.0 (historical academic research)"
PILOT_IDS = (5646, 5704, 5635, 15216, 15991, 60390, 9357, 14648, 5666, 16033)


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_years(value: str) -> tuple[int | None, int | None]:
    years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", value)]
    if not years:
        return None, None
    return min(years), max(years)


def candidate_name(soup: BeautifulSoup) -> str:
    title = soup.find("h2", class_="card-title")
    text = clean(title.get_text(" ", strip=True)) if title else ""
    return re.sub(r"'(?:s)? (?:Issue Positions.*|Ratings and Endorsements.*)$", "", text)


def parse_pct(html: str, candidate_id: int, source_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    name = candidate_name(soup)
    election = soup.find("h3", class_="text-left")
    election_text = clean(election.get_text(" ", strip=True)) if election else ""
    year_start, _ = extract_years(election_text)
    records: list[dict[str, Any]] = []
    for header in soup.find_all("h5", class_="returned-PCT-header"):
        card = header.find_parent("div", class_="card")
        if not card:
            continue
        body = card.find("div", class_="card-body")
        if not body:
            continue
        prompt = body.find("p", class_="text-left")
        prompt_text = clean(prompt.get_text(" ", strip=True)) if prompt else ""
        rows = body.find_all("tr", id="issueTextTypesNpatoptionText")
        for option_number, row in enumerate(rows, start=1):
            cells = row.find_all("td")
            if not cells:
                continue
            raw_answer = clean(cells[0].get_text(" ", strip=True))
            option_text = clean(cells[-1].get_text(" ", strip=True))
            selected_icon = row.select_one("i.fas.fa-circle") is not None
            records.append(
                {
                    "votesmart_candidate_id": candidate_id,
                    "candidate": name,
                    "election_year": year_start,
                    "election_description": election_text,
                    "section": clean(header.get_text(" ", strip=True)),
                    "question": prompt_text,
                    "option_number": option_number,
                    "option_text": option_text,
                    "raw_answer": raw_answer,
                    "selected": bool(raw_answer or selected_icon),
                    "source_type": "candidate_supplied_pct_response",
                    "source_url": source_url,
                }
            )
    return records


def category_for_table(table: Tag) -> str:
    collapse = table.find_parent("div", id=re.compile(r"^collapse\d+$"))
    if not collapse:
        return ""
    number = re.search(r"\d+", collapse.get("id", ""))
    if not number:
        return ""
    container = collapse.parent
    header = container.find(id=f"heading{number.group()}") if container else None
    return clean(header.get_text(" ", strip=True)) if header else ""


def parse_evaluations(
    html: str, candidate_id: int, source_url: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    soup = BeautifulSoup(html, "html.parser")
    name = candidate_name(soup)
    ratings: list[dict[str, Any]] = []
    seen_ratings: set[tuple[str, str, str]] = set()
    for table in soup.find_all("table", class_="evaluations-table"):
        category = category_for_table(table)
        for row in table.select("div.row.mb-2"):
            link = row.find("a", href=re.compile(r"/interest-group/\d+/rating/\d+"))
            values = row.find_all("div", class_="evaluations-item-primary")
            if not link or len(values) < 2:
                continue
            organization = clean(link.get_text(" ", strip=True))
            rating = clean(values[0].get_text(" ", strip=True))
            timespan = clean(values[1].get_text(" ", strip=True))
            key = (link.get("href", ""), rating, timespan)
            if key in seen_ratings:
                continue
            seen_ratings.add(key)
            start, end = extract_years(timespan)
            ids = re.search(r"/interest-group/(\d+)/rating/(\d+)", link.get("href", ""))
            ratings.append(
                {
                    "votesmart_candidate_id": candidate_id,
                    "candidate": name,
                    "issue_category": category,
                    "organization": organization,
                    "interest_group_id": int(ids.group(1)) if ids else None,
                    "scorecard_id": int(ids.group(2)) if ids else None,
                    "rating": rating,
                    "rating_period": timespan,
                    "rating_year_start": start,
                    "rating_year_end": end,
                    "source_type": "interest_group_rating",
                    "source_url": link.get("href") or source_url,
                    "candidate_page_url": source_url,
                }
            )

    endorsements: list[dict[str, Any]] = []
    endorsement_header = soup.find(class_="evaluations-endorsement-header")
    if endorsement_header:
        year_start, _ = extract_years(endorsement_header.get_text(" ", strip=True))
        card = endorsement_header.find_parent("div", class_="card")
        if card:
            for item in card.find_all(class_="evaluations-candidate-endorsement-item"):
                link = item.find("a")
                if not link:
                    continue
                group_id = re.search(r"/interest-group/(\d+)", link.get("href", ""))
                endorsements.append(
                    {
                        "votesmart_candidate_id": candidate_id,
                        "candidate": name,
                        "endorsement_year": year_start,
                        "organization": clean(link.get_text(" ", strip=True)),
                        "interest_group_id": int(group_id.group(1)) if group_id else None,
                        "source_type": "interest_group_endorsement",
                        "source_url": link.get("href") or source_url,
                        "candidate_page_url": source_url,
                    }
                )
    return ratings, endorsements


class PublicPageCollector:
    def __init__(self, delay: float = 1.0, session: requests.Session | None = None):
        self.delay = delay
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html"})
        self.last_request = 0.0

    def fetch(self, candidate_id: int, page_type: str, refresh: bool = False) -> tuple[str, str]:
        target = RAW / f"candidate_{candidate_id}_{page_type}.html"
        if target.exists() and not refresh:
            return target.read_text(encoding="utf-8"), self.url(candidate_id, page_type)
        elapsed = time.monotonic() - self.last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        url = self.url(candidate_id, page_type)
        response = self.session.get(url, timeout=45)
        self.last_request = time.monotonic()
        response.raise_for_status()
        if urlparse(response.url).hostname not in {
            "j.futurefacts.votesmart.io", "justfacts.votesmart.org"
        }:
            raise RuntimeError(f"Unexpected redirect host: {response.url}")
        if len(response.content) < 10_000:
            raise RuntimeError(f"Unexpectedly small Vote Smart page: {len(response.content)} bytes")
        RAW.mkdir(parents=True, exist_ok=True)
        target.write_text(response.text, encoding="utf-8")
        return response.text, response.url

    @staticmethod
    def url(candidate_id: int, page_type: str) -> str:
        if page_type == "pct":
            return f"{HOST}/candidate/political-courage-test/{candidate_id}"
        if page_type == "evaluations":
            return f"{HOST}/candidate/evaluations/{candidate_id}"
        raise ValueError(page_type)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_ids(value: str) -> tuple[int, ...]:
    return tuple(dict.fromkeys(int(item.strip()) for item in value.split(",") if item.strip()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-ids", type=parse_ids, default=PILOT_IDS)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--label", default="pilot")
    args = parser.parse_args()
    collector = PublicPageCollector(max(args.delay, 0.25))
    pct_rows: list[dict[str, Any]] = []
    ratings: list[dict[str, Any]] = []
    endorsements: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for candidate_id in args.candidate_ids:
        for page_type in ("pct", "evaluations"):
            html, url = collector.fetch(candidate_id, page_type, args.refresh)
            manifest.append(
                {
                    "candidate_id": candidate_id,
                    "page_type": page_type,
                    "source_url": url,
                    "bytes": len(html.encode("utf-8")),
                    "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
                }
            )
            if page_type == "pct":
                pct_rows.extend(parse_pct(html, candidate_id, url))
            else:
                candidate_ratings, candidate_endorsements = parse_evaluations(
                    html, candidate_id, url
                )
                ratings.extend(candidate_ratings)
                endorsements.extend(candidate_endorsements)
    write_csv(OUT / f"votesmart_{args.label}_pct_options.csv", pct_rows)
    write_csv(OUT / f"votesmart_{args.label}_ratings.csv", ratings)
    write_csv(OUT / f"votesmart_{args.label}_endorsements.csv", endorsements)
    manifest_payload = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_ids": list(args.candidate_ids),
        "request_delay_seconds": collector.delay,
        "files": manifest,
    }
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"manifest_{args.label}.json").write_text(
        json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Parsed {len(pct_rows):,} PCT options, {len(ratings):,} ratings, "
        f"and {len(endorsements):,} endorsements for {len(args.candidate_ids):,} candidates"
    )


if __name__ == "__main__":
    main()
