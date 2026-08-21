"""Discover candidate campaign URLs and inventory their archived availability.

Vote Smart profile links are a discovery aid, not cycle-specific evidence: the
public profile can change after an election.  This script therefore preserves
the retrieval date and keeps archive captures tied to the election cycle.
All network responses are cached and failures are recorded so runs resume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ideology" / "campaign_websites"
OUT = ROOT / "data" / "processed" / "ideology"
XWALK = OUT / "votesmart_candidate_crosswalk_resolved.csv"
HOST = "https://j.futurefacts.votesmart.io"
USER_AGENT = "alabama-legislative-cmo-research/1.0 (historical academic research)"
SOCIAL_HOSTS = {"facebook.com", "www.facebook.com", "twitter.com", "x.com", "instagram.com", "www.instagram.com", "youtube.com", "www.youtube.com"}


def clean_url(href: str) -> str:
    href = unquote((href or "").strip())
    parsed = urlparse(href)
    if parsed.path.startswith("/redirect"):
        values = parse_qs(parsed.query)
        href = (values.get("url") or values.get("target") or [href])[0]
    return href


def parse_campaign_links(html: str, profile_url: str) -> list[dict[str, str]]:
    """Extract explicitly labelled campaign websites from a public profile."""
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        href = clean_url(anchor["href"])
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        host = parsed.netloc.lower()
        if "votesmart" in host or host in SOCIAL_HOSTS:
            continue
        text = " ".join(anchor.get_text(" ", strip=True).split())
        container = anchor.find_parent(["div", "li", "tr", "td", "p"])
        context = " ".join((container.get_text(" ", strip=True) if container else text).split())
        marker = f"{text} {context}".lower()
        if not any(term in marker for term in ("campaign website", "campaign site", "campaign web site")):
            continue
        found[href] = {
            "campaign_url": href,
            "link_label": text,
            "link_context": context[:500],
            "discovery_source_url": profile_url,
        }
    return list(found.values())


def parse_biography_links(payload: object, profile_url: str) -> list[dict[str, str]]:
    """Parse the campaign-contact collection used by Vote Smart's public UI."""
    if not isinstance(payload, dict):
        return []
    values = payload.get("electionWebAddresses") or []
    found = []
    for item in values if isinstance(values, list) else []:
        href = clean_url(item.get("webaddress", "") if isinstance(item, dict) else "")
        if urlparse(href).scheme in {"http", "https"}:
            found.append({"campaign_url": href, "link_label": "Campaign website", "link_context": "Vote Smart campaign contact", "discovery_source_url": profile_url})
    return found


def select_nearest_capture(captures: list[dict[str, str]], election_year: int) -> dict[str, str] | None:
    """Choose the successful HTML capture nearest the general election date."""
    target = int(f"{election_year}1101")
    eligible = [c for c in captures if c.get("timestamp", "")[:8].isdigit()]
    return min(eligible, key=lambda c: abs(int(c["timestamp"][:8]) - target)) if eligible else None


def request_cached(session: requests.Session, url: str, path: Path, timeout: int) -> tuple[int, str]:
    if path.exists():
        return 200, path.read_text(encoding="utf-8", errors="replace")
    response = session.get(url, timeout=timeout)
    if response.status_code == 200:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
    return response.status_code, response.text


def cdx_captures(session: requests.Session, campaign_url: str, cache: Path, timeout: int) -> tuple[list[dict[str, str]], str]:
    if cache.exists():
        payload = json.loads(cache.read_text(encoding="utf-8"))
    else:
        response = session.get(
            "https://web.archive.org/cdx/search/cdx",
            params={"url": campaign_url, "output": "json", "fl": "timestamp,original,statuscode,mimetype,digest", "filter": ["statuscode:200", "mimetype:text/html"], "collapse": "digest"},
            timeout=timeout,
        )
        if response.status_code != 200:
            return [], f"http_{response.status_code}"
        payload = response.json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if not payload or len(payload) < 2:
        return [], "no_captures"
    headers = payload[0]
    return [dict(zip(headers, row)) for row in payload[1:]], "ok"


def accepted_crosswalk() -> pd.DataFrame:
    frame = pd.read_csv(XWALK, dtype=str).fillna("")
    frame = frame[frame.accepted.str.lower().eq("true")].copy()
    frame["votesmart_candidate_id"] = frame.votesmart_candidate_id.str.replace(r"\.0$", "", regex=True)
    frame = frame[frame.votesmart_candidate_id.ne("")]
    return frame


def universe(frame: pd.DataFrame, limit: int | None) -> pd.DataFrame:
    # One profile fetch per stable Vote Smart ID; expand back to cycles after discovery.
    profiles = frame.sort_values("election_year").drop_duplicates("votesmart_candidate_id", keep="last")
    return profiles.head(limit) if limit else profiles


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Pilot with the first N unique Vote Smart candidates")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--wayback", action="store_true", help="Query CDX for discovered URLs")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    crosswalk = accepted_crosswalk()
    candidates = universe(crosswalk, args.limit)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    rows: list[dict[str, object]] = []
    status_rows: list[dict[str, object]] = []
    retrieved = datetime.now(timezone.utc).isoformat()
    for _, candidate in candidates.iterrows():
        cid = candidate.votesmart_candidate_id
        profile_url = f"{HOST}/candidate/{cid}"
        cache = RAW / "votesmart_profiles" / f"{cid}.html"
        if args.refresh and cache.exists():
            cache.unlink()
        try:
            code, html = request_cached(session, profile_url, cache, args.timeout)
            links = parse_campaign_links(html, profile_url) if code == 200 else []
            if not links:
                biography_url = f"https://justfacts.votesmart.org/nextfactsAPI/candidate/biography/{cid}/"
                try:
                    biography = session.get(biography_url, timeout=args.timeout)
                    if biography.status_code == 200:
                        links = parse_biography_links(biography.json(), biography_url)
                except (requests.RequestException, ValueError):
                    pass
            error = "" if code == 200 else f"http_{code}"
        except requests.RequestException as exc:
            code, links, error = 0, [], type(exc).__name__
        status_rows.append({"votesmart_candidate_id": cid, "profile_url": profile_url, "http_status": code, "campaign_links_found": len(links), "error": error, "retrieved_at_utc": retrieved})
        for link in links:
            url_hash = hashlib.sha256(link["campaign_url"].encode()).hexdigest()[:16]
            captures: list[dict[str, str]] = []
            cdx_status = "not_requested"
            if args.wayback:
                try:
                    captures, cdx_status = cdx_captures(session, link["campaign_url"], RAW / "wayback_cdx" / f"{url_hash}.json", args.timeout)
                except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
                    cdx_status = type(exc).__name__
            cycles = crosswalk[crosswalk.votesmart_candidate_id.eq(cid)]
            for _, cycle in cycles.iterrows():
                nearest = select_nearest_capture(captures, int(cycle.election_year))
                rows.append({**cycle.to_dict(), **link, "url_temporal_status": "current_profile_link_as_of_retrieval", "retrieved_at_utc": retrieved, "wayback_capture_count": len(captures), "wayback_status": cdx_status, "nearest_cycle_capture_timestamp": (nearest or {}).get("timestamp", ""), "nearest_cycle_capture_url": (f"https://web.archive.org/web/{nearest['timestamp']}id_/{nearest['original']}" if nearest else "")})
        time.sleep(max(0, args.delay))

    website_columns = list(candidates.columns) + [
        "campaign_url", "link_label", "link_context", "discovery_source_url",
        "url_temporal_status", "retrieved_at_utc", "wayback_capture_count",
        "wayback_status", "nearest_cycle_capture_timestamp", "nearest_cycle_capture_url",
    ]
    pd.DataFrame(rows, columns=website_columns).to_csv(OUT / "candidate_campaign_websites.csv", index=False)
    pd.DataFrame(status_rows).to_csv(OUT / "candidate_campaign_website_discovery_status.csv", index=False)
    print(f"Profiles attempted: {len(status_rows)}; campaign URLs: {len(rows)}")


if __name__ == "__main__":
    main()
