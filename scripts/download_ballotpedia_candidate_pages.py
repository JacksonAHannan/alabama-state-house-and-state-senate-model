"""Acquire public Ballotpedia candidate pages without the paid data API.

Ballotpedia currently returns empty HTTP 202 responses to this environment's
ordinary HTTP client.  The downloader therefore uses Jina Reader only as a
read-only renderer of the same public page, while retaining both the original
Ballotpedia URL and renderer URL in the manifest.  Cached source documents are
immutable: an existing file is never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

import pandas as pd
import requests
from rapidfuzz.fuzz import WRatio

from oe_normalize import normalize_name


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ballotpedia"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
CANONICAL = ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv"
VOTESMART = IDEOLOGY / "votesmart_candidate_crosswalk_resolved.csv"
MANIFEST = IDEOLOGY / "ballotpedia_page_manifest.csv"
CROSSWALK = IDEOLOGY / "ballotpedia_candidate_crosswalk.csv"
READER = "https://r.jina.ai/https://ballotpedia.org/"
LINK = re.compile(r"(?<!!)\[([^\]]+)\]\((https://ballotpedia\.org/[^\s)#]+)(?:#[^)]+)?(?:\s+\"[^\"]*\")?\)")
ENCODED = re.compile(r"^GS[LU]\d+[DR]", re.I)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def candidate_target(url: str) -> Path:
    slug = unquote(urlsplit(url).path.lstrip("/"))
    safe_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", slug)[:100]
    return RAW / "candidate_pages" / f"{hashlib.sha1(url.encode()).hexdigest()[:12]}_{safe_slug}.md"


def district_url(chamber: str, district: object) -> str:
    title = "Alabama_House_of_Representatives_District" if chamber == "house" else "Alabama_State_Senate_District"
    return f"https://ballotpedia.org/{title}_{int(float(district))}"


def district_target(chamber: str, district: object) -> Path:
    return RAW / "district_pages" / f"{chamber}_{int(float(district)):03d}.md"


def clean_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(("https", "ballotpedia.org", parts.path, "", ""))


def candidate_links(markdown: str) -> dict[str, str]:
    links = {}
    excluded = ("Alabama_House_of_Representatives_", "Alabama_State_Senate_",
                "Democratic_Party", "Republican_Party", "Libertarian_Party")
    for label, url in LINK.findall(markdown):
        slug = unquote(urlsplit(url).path.lstrip("/"))
        if not slug or slug.startswith(excluded) or ":" in slug or slug in {"Main_Page"}:
            continue
        key = normalize_name(label)
        if key and len(key) > 2:
            links.setdefault(key, clean_url(url))
    return links


def fetch(session: requests.Session, source_url: str, target: Path, delay: float, timeout: float = 45) -> tuple[str, str]:
    if target.exists():
        text = target.read_text(encoding="utf-8")
        return text, "cached"
    renderer = READER + source_url.split("ballotpedia.org/", 1)[1]
    response = session.get(renderer, timeout=timeout)
    response.raise_for_status()
    text = response.text
    if not text.strip() or text.startswith("ERROR:"):
        raise RuntimeError(f"renderer returned no usable page for {source_url}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    time.sleep(delay)
    return text, "downloaded"


def effective_names(canonical: pd.DataFrame) -> pd.DataFrame:
    result = canonical.copy()
    result["effective_name"] = result.canonical_name
    if VOTESMART.exists():
        vs = pd.read_csv(VOTESMART, dtype=str).fillna("")
        vs = vs[vs.accepted.str.lower().eq("true")][["canonical_candidate_id", "votesmart_candidate"]]
        result = result.merge(vs, on="canonical_candidate_id", how="left", validate="one_to_one")
        encoded = result.canonical_name.str.match(ENCODED)
        surname_only = result.canonical_name.map(lambda value: len(normalize_name(value).split()) == 1)
        replace = (encoded | surname_only) & result.votesmart_candidate.ne("")
        result.loc[replace, "effective_name"] = result.votesmart_candidate
    result["name_key"] = result.effective_name.map(normalize_name)
    return result


def match_cycle(candidates: pd.DataFrame, links: dict[str, str], source: str = "election_index") -> list[dict[str, object]]:
    rows = []
    link_keys = list(links)
    for candidate in candidates.itertuples(index=False):
        url = links.get(candidate.name_key, "")
        method, score, margin = (f"exact_{source}_name", 100.0, 100.0) if url else ("unmatched", 0.0, 0.0)
        if not url and link_keys:
            scored = sorted(((WRatio(candidate.name_key, key), key) for key in link_keys), reverse=True)
            score = float(scored[0][0]); margin = score - (float(scored[1][0]) if len(scored) > 1 else 0.0)
            if score >= 94 and margin >= 8:
                url = links[scored[0][1]]; method = f"unique_fuzzy_{source}_name"
        rows.append({
            "canonical_candidate_id": candidate.canonical_candidate_id, "person_id": candidate.person_id,
            "election_year": candidate.year, "chamber": candidate.chamber, "district": candidate.district,
            "party": candidate.canonical_party, "canonical_name": candidate.canonical_name,
            "matched_name": candidate.effective_name, "ballotpedia_url": url, "match_method": method,
            "name_score": score, "score_margin": margin, "accepted": bool(url),
            "review_required": bool(not url and score >= 80),
        })
    return rows


def quarantine_page_cycle_collisions(crosswalk: pd.DataFrame, district_candidate_links: dict) -> pd.DataFrame:
    """Require one Ballotpedia person page per canonical candidate in a cycle."""
    result = crosswalk.copy()
    accepted = result.accepted & result.ballotpedia_url.ne("")
    collisions = result[accepted & result.duplicated(["election_year", "ballotpedia_url"], keep=False)]
    for _, group in collisions.groupby(["election_year", "ballotpedia_url"], sort=False):
        supported = []
        url_lower = group.ballotpedia_url.iloc[0].lower()
        for index, row in group.iterrows():
            chamber_hint = ("senate" not in url_lower or row.chamber == "senate") and (
                "house_of_representatives" not in url_lower or row.chamber == "house")
            links = district_candidate_links.get((row.chamber, str(int(float(row.district)))), {})
            district_support = links.get(normalize_name(row.matched_name), "") == row.ballotpedia_url
            if chamber_hint and district_support:
                supported.append(index)
        keep = supported if len(supported) == 1 else []
        reject = group.index.difference(keep)
        result.loc[reject, "accepted"] = False
        result.loc[reject, "review_required"] = True
        result.loc[reject, "match_method"] = "duplicate_page_cycle_identity_quarantined"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", nargs="+", type=int, default=[1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022])
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--indexes-only", action="store_true")
    parser.add_argument("--skip-indexes", action="store_true")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-district-pages", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    canonical = effective_names(pd.read_csv(CANONICAL, dtype=str).fillna(""))
    canonical["year"] = pd.to_numeric(canonical.year)
    session = requests.Session()
    session.headers["User-Agent"] = "AlabamaLegislativeCMOResearch/1.0 (public-source archival research)"
    manifest, matches, index_links = [], [], {}
    for cycle in args.cycles:
        cycle_links = {}
        if args.skip_indexes:
            for chamber in ("house", "senate"):
                cached_index = RAW / "election_indexes" / f"{cycle}_{chamber}.md"
                if cached_index.exists():
                    cycle_links.update(candidate_links(cached_index.read_text(encoding="utf-8")))
            index_links[cycle] = cycle_links
            continue
        for chamber, title in (("house", "Alabama_House_of_Representatives_elections"),
                               ("senate", "Alabama_State_Senate_elections")):
            source = f"https://ballotpedia.org/{title},_{cycle}"
            target = RAW / "election_indexes" / f"{cycle}_{chamber}.md"
            try:
                text, status = fetch(session, source, target, args.delay)
                cycle_links.update(candidate_links(text))
                manifest.append({"record_type":"election_index", "election_year":cycle,
                                 "canonical_candidate_id":"", "source_url":source,
                                 "renderer_url":READER + source.split("ballotpedia.org/",1)[1],
                                 "local_path":str(target.relative_to(ROOT)), "sha256":digest(text),
                                 "retrieved_date":str(date.today()), "status":status})
            except Exception as exc:
                manifest.append({"record_type":"election_index", "election_year":cycle,
                                 "canonical_candidate_id":"", "source_url":source, "renderer_url":"",
                                 "local_path":str(target.relative_to(ROOT)), "sha256":"",
                                 "retrieved_date":str(date.today()), "status":f"error:{type(exc).__name__}"})
        index_links[cycle] = cycle_links

    district_keys = list(canonical[canonical.year.isin(args.cycles)][["chamber", "district"]]
                         .drop_duplicates().itertuples(index=False, name=None))
    uncached = [(chamber, district) for chamber, district in district_keys
                if not district_target(chamber, district).exists()]
    if args.max_district_pages is not None:
        uncached = uncached[:args.max_district_pages]

    def acquire_district(key):
        chamber, district = key
        source = district_url(chamber, district); target = district_target(chamber, district)
        local_session = requests.Session()
        local_session.headers.update(session.headers)
        try:
            text, status = fetch(local_session, source, target, args.delay)
            return key, text, {"record_type":"district_page", "election_year":"",
                "canonical_candidate_id":"", "source_url":source,
                "renderer_url":READER + source.split("ballotpedia.org/",1)[1],
                "local_path":str(target.relative_to(ROOT)), "sha256":digest(text),
                "retrieved_date":str(date.today()), "status":status}
        except Exception as exc:
            return key, "", {"record_type":"district_page", "election_year":"",
                "canonical_candidate_id":"", "source_url":source, "renderer_url":"",
                "local_path":str(target.relative_to(ROOT)), "sha256":"",
                "retrieved_date":str(date.today()), "status":f"error:{type(exc).__name__}"}

    if uncached:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = [executor.submit(acquire_district, key) for key in uncached]
            for number, future in enumerate(as_completed(futures), 1):
                _, _, record = future.result(); manifest.append(record)
                print(f"District pages acquired {number:,}/{len(futures):,}", flush=True)

    district_candidate_links = {}
    for chamber, district in district_keys:
        target = district_target(chamber, district)
        if target.exists():
            text = target.read_text(encoding="utf-8")
            district_candidate_links[(chamber, str(int(float(district))))] = candidate_links(text)
            source = district_url(chamber, district)
            if not any(row["record_type"] == "district_page" and row["source_url"] == source for row in manifest):
                manifest.append({"record_type":"district_page", "election_year":"",
                    "canonical_candidate_id":"", "source_url":source,
                    "renderer_url":READER + source.split("ballotpedia.org/",1)[1],
                    "local_path":str(target.relative_to(ROOT)), "sha256":digest(text),
                    "retrieved_date":str(date.today()), "status":"cached"})

    for cycle in args.cycles:
        for (chamber, district), group in canonical[canonical.year.eq(cycle)].groupby(["chamber", "district"]):
            # District pages are the stronger identity boundary and include
            # historical election sections. Fall back to the statewide index
            # only when that district page could not be acquired.
            district_links = district_candidate_links.get((chamber, str(int(float(district)))), {})
            statewide_links = index_links.get(cycle, {})
            for _, candidate in group.iterrows():
                # Full names may safely use the statewide election index as a
                # fallback. Surname-only historical records stay constrained
                # to the district page to avoid namesake collisions.
                links = dict(district_links)
                source = "district_page"
                if len(str(candidate.name_key).split()) > 1:
                    links.update(statewide_links)
                    source = "district_or_election_index"
                matches.extend(match_cycle(candidate.to_frame().T, links, source))
    crosswalk = pd.DataFrame(matches)
    crosswalk = quarantine_page_cycle_collisions(crosswalk, district_candidate_links)
    CROSSWALK.parent.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(CROSSWALK, index=False)
    if not args.indexes_only:
        accepted = crosswalk[crosswalk.accepted].drop_duplicates("ballotpedia_url")
        if args.max_pages is not None:
            cached = accepted[accepted.ballotpedia_url.map(lambda url: candidate_target(url).exists())]
            uncached = accepted[~accepted.index.isin(cached.index)].head(args.max_pages)
            accepted = pd.concat([cached, uncached], ignore_index=True)
        for row in accepted.itertuples(index=False):
            target = candidate_target(row.ballotpedia_url)
            try:
                text, status = fetch(session, row.ballotpedia_url, target, args.delay)
                manifest.append({"record_type":"candidate_page", "election_year":"",
                                 "canonical_candidate_id":row.canonical_candidate_id,
                                 "source_url":row.ballotpedia_url,
                                 "renderer_url":READER + row.ballotpedia_url.split("ballotpedia.org/",1)[1],
                                 "local_path":str(target.relative_to(ROOT)), "sha256":digest(text),
                                 "retrieved_date":str(date.today()), "status":status})
            except Exception as exc:
                manifest.append({"record_type":"candidate_page", "election_year":"",
                                 "canonical_candidate_id":row.canonical_candidate_id,
                                 "source_url":row.ballotpedia_url, "renderer_url":"",
                                 "local_path":str(target.relative_to(ROOT)), "sha256":"",
                                 "retrieved_date":str(date.today()), "status":f"error:{type(exc).__name__}"})
    current_manifest = pd.DataFrame(manifest)
    if MANIFEST.exists():
        prior = pd.read_csv(MANIFEST, dtype=str).fillna("")
        current_manifest = pd.concat([prior, current_manifest], ignore_index=True).drop_duplicates(
            ["record_type", "source_url", "local_path"], keep="last")
    current_manifest.to_csv(MANIFEST, index=False)
    print(crosswalk.groupby("election_year").accepted.agg(["sum", "count"]).to_string())
    print(f"Manifest records: {len(manifest):,}; candidate pages cached: {sum(r['record_type']=='candidate_page' and not str(r['status']).startswith('error') for r in manifest):,}")


if __name__ == "__main__":
    main()
