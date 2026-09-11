#!/usr/bin/env python3
"""Acquire official historical Southern election-result files and audit coverage.

The downloader is deliberately conservative: it saves official archive pages,
follows only configured government domains, downloads tabular/archive files, and
queues dynamic or ambiguous links for review. It never overwrites raw evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/southern_sos_elections"
AUDIT = ROOT / "data/processed/source_audits"
TARGET_EVEN = tuple(range(1994, 2017, 2))
TARGET_ODD = tuple(range(1995, 2016, 2))
TARGET_ODD_QUAD = tuple(range(1995, 2016, 4))
TARGET_LA_ODD_QUAD = tuple(range(1995, 2024, 4))
TIMEOUT = 45
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36 Alabama-legislative-model-research"


@dataclass(frozen=True)
class StateSource:
    state: str
    archive_url: str
    domains: tuple[str, ...]
    years: tuple[int, ...] = TARGET_EVEN


SOURCES = (
    StateSource("AR", "https://www.sos.arkansas.gov/elections/research/election-results", ("sos.arkansas.gov", "www.sos.arkansas.gov")),
    StateSource("FL", "https://dos.fl.gov/elections/data-statistics/elections-data/precinct-level-election-results", ("results.elections.myflorida.com", "dos.fl.gov")),
    StateSource("GA", "https://sos.ga.gov/page/historical-elections-results", ("sos.ga.gov", "results.enr.clarityelections.com")),
    StateSource("KY", "https://elect.ky.gov/results/Pages/default.aspx", ("elect.ky.gov", "www.sos.ky.gov", "secure.kentucky.gov")),
    StateSource("LA", "https://www.sos.la.gov/elections-voting/post-election-statistic-files", ("sos.la.gov", "www.sos.la.gov", "voterportal.sos.la.gov"), TARGET_LA_ODD_QUAD),
    StateSource("MS", "https://www.sos.ms.gov/elections-voting/election-results", ("sos.ms.gov", "www.sos.ms.gov", "sos.state.ms.us", "www.sos.state.ms.us"), TARGET_ODD_QUAD),
    StateSource("MO", "https://www.sos.mo.gov/elections/s_default", ("sos.mo.gov", "www.sos.mo.gov")),
    StateSource("NC", "https://www.ncsbe.gov/results-data/election-results/historical-election-results-data", ("ncsbe.gov", "www.ncsbe.gov", "s3.amazonaws.com")),
    StateSource("OK", "https://oklahoma.gov/elections/elections-results/election-results.html", ("oklahoma.gov", "www.ok.gov", "ok.gov")),
    StateSource("SC", "https://scvotes.gov/elections-statistics/election-results/", ("scvotes.gov", "www.scvotes.gov", "www.enr-scvotes.org")),
    StateSource("TN", "https://sos.tn.gov/elections/results", ("sos.tn.gov", "sos-prod.tnsosgovfiles.com",
        "sos-tn-gov-files.tnsosfiles.com", "tnelections.tnsosfiles.com", "sos-tn-gov-files.s3.amazonaws.com")),
    # Texas is intentionally omitted: the project already holds the relevant
    # Texas results in the companion Texas repository and copied-source staging.
    StateSource("VA", "https://www.elections.virginia.gov/resultsreports/election-results/", ("elections.virginia.gov", "www.elections.virginia.gov"), TARGET_ODD),
)

FILE_EXTENSIONS = {".csv", ".tsv", ".txt", ".zip", ".xls", ".xlsx", ".json", ".xml", ".dbf"}
RESULT_WORDS = re.compile(r"precinct|results?|general|returns?|statement of vote|recap", re.I)
PRECINCT_WORDS = re.compile(r"precinct|(?:^|[_\W])pct(?:[_\W]|$)|ward|polling", re.I)
SKIP_WORDS = re.compile(r"primary|runoff|registration|turnout|candidate list|qualif", re.I)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")

# Mississippi's current archive is bot-protected, while its still-official
# legacy county-recap pages are directly accessible. The SOS explicitly labels
# these as precinct-level county recapitulation reports.
MS_PRECINCT_PAGES = {
    2003: "https://sos.ms.gov/elections/electionresults_aspx/elections_results_2003_county.aspx",
    2007: "https://www.sos.state.ms.us/elections/2007/General%20Election/General.asp",
    2011: "https://sos.ms.gov/elections/electionresults_aspx/elections_results_2011_county.aspx",
    2015: "https://sos.ms.gov/elections/electionresults_aspx/elections_results_2015_countyG.aspx",
}

OK_GENERAL_DATES = {
    2012: "20121106",
    2014: "20141104",
    2016: "20161108",
}
OK_2010_PRECINCT_ZIP = "https://oklahoma.gov/content/dam/ok/en/elections/documents/110210.zip"

TN_GENERAL_SPREADSHEETS = {
    2008: "https://sos-prod.tnsosgovfiles.com/s3fs-public/document/November2008.xlsx",
    2010: "https://sos-prod.tnsosgovfiles.com/s3fs-public/document/November2010.xls",
    2012: "https://sos-prod.tnsosgovfiles.com/s3fs-public/document/November2012.xlsx",
    2014: "https://sos-tn-gov-files.s3.amazonaws.com/20141104_PrecinctTotals.xlsx",
    2016: "https://sos-tn-gov-files.s3.amazonaws.com/StateGeneralbyPrecinctNov2016.xlsx",
}

LA_2000_2011_COMBINED = (
    "https://redist.legis.la.gov/2011_Files/doj/08%20Data%20CD%20DVDs/"
    "Voter%20Registration%20Election%20Results%20and%20Candidate%20information/"
    "Combined%20Data%20Text%20Files/Combined%20Data%20TextFiles.zip"
)

LA_LEGISLATIVE_ELECTION_DATES = {
    1995: {"first_round": "19951021", "runoff": "19951118"},
    1999: {"first_round": "19991023", "runoff": "19991120"},
    2003: {"first_round": "20031004", "runoff": "20031115"},
    2007: {"first_round": "20071020", "runoff": "20071117"},
    2011: {"first_round": "20111022", "runoff": "20111119"},
    2015: {"first_round": "20151024", "runoff": "20151121"},
    2019: {"first_round": "20191012", "runoff": "20191116"},
    2023: {"first_round": "20231014", "runoff": "20231118"},
}

SC_ELECTION_REPORTS = {
    1994: "https://scvotes.gov/wp-content/uploads/2022/08/Election_Report_1994-1995.pdf",
    1996: "https://scvotes.gov/wp-content/uploads/2022/08/Election_Report_1995-1996.pdf",
    1998: "https://scvotes.gov/wp-content/uploads/2022/08/Election_Report_1997-1998.pdf",
    2000: "https://scvotes.gov/wp-content/uploads/2022/08/Election_Report_2000.pdf",
    2002: "https://scvotes.gov/wp-content/uploads/2022/08/Election_Report_2002.pdf",
    2004: "https://scvotes.gov/wp-content/uploads/2022/08/Election_Report_2004.pdf",
    2006: "https://scvotes.gov/wp-content/uploads/2022/08/Election_Report_2006.pdf",
}

AR_STATIC_GENERAL_FILES = {
    1994: ("https://www.sos.arkansas.gov/uploads/elections/94general_election_results.xls", "precinct"),
    2002: ("https://www.sos.arkansas.gov/uploads/elections/2002_General.pdf", "published_report"),
    2004: ("https://www.sos.arkansas.gov/uploads/elections/2004_General_Election_and_Non-Partisan_Judicial_Runoff_Certification_Report.pdf", "published_report"),
    2006: ("https://www.sos.arkansas.gov/uploads/elections/20070308_ARSOS_2006_Elections_Publication_Final__Revised.xls", "unknown"),
    2010: ("https://www.sos.arkansas.gov/uploads/elections/2010_General_Election_Results_-_Fed%2C_State_-_by_Polling_Location.xlsx", "precinct"),
}

# Arkansas's current official election-results application exposes its full
# election data as public JSON. These files include precinct result records and
# are the authoritative bulk exports behind the SOS results interface.
AR_TALLY_GENERAL_FILES = {
    2012: "https://results.tally-enr.com/results/arkansas/1832/FullDataFile.json",
    2014: "https://results.tally-enr.com/results/arkansas/1834/FullDataFile.json",
    2016: "https://results.tally-enr.com/results/arkansas/1836/FullDataFile.json",
}

# Human-action routes retained separately from machine acquisition. A row is
# not evidence that data exist at precinct level; ``access_status`` explains
# whether the link is a direct browser download, a purchase/request page, or an
# archive where the desired granularity is not publicly exposed.
MANUAL_ACCESS = [
    {"state": "GA", "cycles": "2012", "access_status": "manual_browser_download",
     "url": "https://sos.ga.gov/sites/default/files/2026-04/november_6_2012_-_general_election.zip",
     "save_under": "data/raw/southern_sos_elections/GA/2012/",
     "reason": "Official ZIP is exposed by the SOS index but automated requests receive Cloudflare 403."},
    {"state": "GA", "cycles": "2014", "access_status": "manual_browser_download",
     "url": "https://sos.ga.gov/sites/default/files/2026-04/november_4_2014_-_general_election.zip",
     "save_under": "data/raw/southern_sos_elections/GA/2014/",
     "reason": "Official ZIP is exposed by the SOS index but automated requests receive Cloudflare 403."},
    {"state": "GA", "cycles": "2016", "access_status": "manual_browser_download",
     "url": "https://sos.ga.gov/sites/default/files/2026-04/november_8_2016_-_general_election.zip",
     "save_under": "data/raw/southern_sos_elections/GA/2016/",
     "reason": "Official ZIP is exposed by the SOS index but automated requests receive Cloudflare 403."},
    {"state": "MO", "cycles": "1996-2016", "access_status": "purchase_or_records_request",
     "url": "https://www.sos.mo.gov/elections/s_default.asp?id=calendar",
     "save_under": "data/raw/southern_sos_elections/MO/{year}/",
     "reason": "Missouri says precinct-level general-election data from 1996 onward are available for purchase from its Elections Division."},
    {"state": "AR", "cycles": "2008", "access_status": "official_archive_contact",
     "url": "https://www.sos.arkansas.gov/elections/research/election-results",
     "save_under": "data/raw/southern_sos_elections/AR/2008/",
     "reason": "No downloadable 2008 precinct export was exposed; the SOS page directs users to Elections staff for temporarily unavailable data."},
    {"state": "FL", "cycles": "1994-2010", "access_status": "official_archive_no_public_file",
     "url": "https://dos.fl.gov/elections/data-statistics/elections-data/precinct-level-election-results/",
     "save_under": "data/raw/southern_sos_elections/FL/{year}/",
     "reason": "The official precinct-download collection begins with 2012."},
    {"state": "GA", "cycles": "1994-2010", "access_status": "official_archive_no_public_file",
     "url": "https://sos.ga.gov/page/historical-elections-results",
     "save_under": "data/raw/southern_sos_elections/GA/{year}/",
     "reason": "The official page exposes precinct/summary ZIPs only for later elections."},
    {"state": "NC", "cycles": "1994-1998", "access_status": "official_archive_no_public_file",
     "url": "https://www.ncsbe.gov/results-data/election-results/historical-election-results-data",
     "save_under": "data/raw/southern_sos_elections/NC/{year}/",
     "reason": "The current official bulk collection exposes precinct results beginning in 2000."},
    {"state": "MS", "cycles": "1995,1999", "access_status": "official_archive_or_records_request",
     "url": "https://www.sos.ms.gov/elections-voting/election-results",
     "save_under": "data/raw/southern_sos_elections/MS/{year}/",
     "reason": "The accessible official county-recap archive begins with the 2003 state cycle."},
    {"state": "OK", "cycles": "1994-2008", "access_status": "official_library_archive_no_precinct_export",
     "url": "https://digitalprairie.ok.gov/digital/collection/stgovpub/id/16640/",
     "save_under": "data/raw/southern_sos_elections/OK/{year}/",
     "reason": "Official election publications are archived, but no machine-readable precinct export was exposed for these cycles."},
    {"state": "SC", "cycles": "1994-2006", "access_status": "official_reports_no_current_precinct_export",
     "url": "https://scvotes.gov/elections-statistics/election-results/",
     "save_under": "data/raw/southern_sos_elections/SC/{year}/",
     "reason": "Official reports were downloaded; their historical precinct-return link is retired and the current election database begins in 2008."},
    {"state": "TN", "cycles": "1994,1996", "access_status": "official_archive_no_general_precinct_file",
     "url": "https://sos.tn.gov/elections/results",
     "save_under": "data/raw/southern_sos_elections/TN/{year}/",
     "reason": "The current archive exposes later general precinct files but no 1994 or 1996 general precinct download."},
    {"state": "KY", "cycles": "1994-2000", "access_status": "official_archive_no_vote_precinct_file",
     "url": "https://elect.ky.gov/results/Pages/default.aspx",
     "save_under": "data/raw/southern_sos_elections/KY/{year}/",
     "reason": "Older files exposed by the archive are county/district totals or precinct registration statistics, not precinct vote returns."},
    {"state": "VA", "cycles": "1995-2003", "access_status": "official_database_locality_only",
     "url": "https://historical.elections.virginia.gov/",
     "save_under": "data/raw/southern_sos_elections/VA/{year}/",
     "reason": "Contest CSVs are downloadable, but inspection shows locality rather than precinct detail for these cycles."},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def official(url: str, domains: tuple[str, ...]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def safe_name(url: str, fallback: str) -> str:
    name = Path(unquote(urlparse(url).path)).name or fallback
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name[:180] or fallback


def write_once(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError(f"Refusing to overwrite changed raw evidence: {path}")
        return
    path.write_bytes(content)


def write_snapshot(path: Path, content: bytes) -> Path:
    """Write a source snapshot without overwriting a prior, changed response."""
    if path.exists() and path.read_bytes() != content:
        digest = hashlib.sha256(content).hexdigest()[:12]
        path = path.with_name(f"{path.stem}_{digest}{path.suffix}")
    write_once(path, content)
    return path


def fetch(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response


def extract_links(html: bytes, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[tuple[str, str]] = []
    for a in soup.select("a[href]"):
        href = urljoin(base_url, a.get("href", "").strip())
        text = " ".join(a.stripped_strings)
        if href.startswith(("http://", "https://")):
            found.append((text, href))
    return found


def infer_year(text: str, url: str, allowed: tuple[int, ...]) -> int | None:
    # A file path is stronger evidence than surrounding navigation text. This
    # matters on archive pages whose accordion/link labels retain another year.
    url_years = [int(x) for x in YEAR_RE.findall(unquote(url))]
    text_years = [int(x) for x in YEAR_RE.findall(text)]
    # Archive paths commonly contain a decade label before the actual year
    # (for example /2010-2019/.../2014/). The right-most URL year is therefore
    # the most specific; visible link text remains the fallback.
    return next((y for y in list(reversed(url_years)) + text_years if y in allowed), None)


def coverage_hint(text: str, url: str) -> str:
    combined = f"{text} {unquote(url)}"
    if re.search(r"registration|regstat|voterstats?", combined, re.I):
        return "registration"
    if PRECINCT_WORDS.search(combined):
        return "precinct"
    if re.search(r"county", combined, re.I):
        return "county"
    if re.search(r"district|legislative", combined, re.I):
        return "district"
    return "unknown"


def refine_coverage(hint: str, content: bytes) -> str:
    """Correct link-based granularity when the downloaded source is explicit."""
    sample = content[:8192].decode("latin-1", errors="ignore")
    if re.search(r"VOTER\s+REGISTRATION\s+STATISTICS|TOTAL\s+REG(?:ISTRATION)?", sample, re.I):
        return "registration"
    return hint


def csv_write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def acquire_mississippi_precinct_recaps(session: requests.Session, manifest: list[dict],
                                         unresolved: list[dict], discovered: dict,
                                         byte_hashes: dict[str, str], audit_only: bool) -> None:
    domains = next(s.domains for s in SOURCES if s.state == "MS")
    original_ua = session.headers.get("User-Agent")
    session.headers["User-Agent"] = "Mozilla/5.0"
    for year, page_url in MS_PRECINCT_PAGES.items():
        try:
            page = fetch(session, page_url)
            page_path = write_snapshot(RAW / "MS" / "archive_pages" / f"{year}_county_precinct_recaps.html", page.content)
            digest = hashlib.sha256(page.content).hexdigest()
            rel = page_path.relative_to(ROOT).as_posix()
            manifest.append({"state": "MS", "election_year": year, "election_date": "",
                "official_url": page.url, "retrieved_at": now_iso(), "local_path": rel,
                "media_type": page.headers.get("content-type", "text/html").split(";")[0],
                "size_bytes": len(page.content), "sha256": digest,
                "duplicate_of": byte_hashes.get(digest, ""), "coverage": "election_page"})
            byte_hashes.setdefault(digest, rel)
            pdf_links = [(text, url) for text, url in extract_links(page.content, page.url)
                         if official(url, domains) and Path(urlparse(url).path).suffix.lower() == ".pdf"]
            discovered.setdefault(("MS", year), []).extend("precinct" for _ in pdf_links)
            for text, url in pdf_links:
                if audit_only:
                    unresolved.append({"state": "MS", "election_year": year, "url": url,
                        "link_text": text, "reason": "discovered_not_downloaded_audit_mode"})
                    continue
                try:
                    result = fetch(session, url)
                    path = write_snapshot(RAW / "MS" / str(year) / safe_name(result.url, f"{year}_county_recap.pdf"), result.content)
                    rdigest = hashlib.sha256(result.content).hexdigest()
                    rrel = path.relative_to(ROOT).as_posix()
                    manifest.append({"state": "MS", "election_year": year, "election_date": "",
                        "official_url": result.url, "retrieved_at": now_iso(), "local_path": rrel,
                        "media_type": result.headers.get("content-type", "application/pdf").split(";")[0],
                        "size_bytes": len(result.content), "sha256": rdigest,
                        "duplicate_of": byte_hashes.get(rdigest, ""), "coverage": "precinct"})
                    byte_hashes.setdefault(rdigest, rrel)
                except Exception as exc:
                    unresolved.append({"state": "MS", "election_year": year, "url": url,
                        "link_text": text, "reason": f"download_failed: {exc}"})
        except Exception as exc:
            unresolved.append({"state": "MS", "election_year": year, "url": page_url,
                "link_text": "county precinct recap index", "reason": f"provider_page_failed: {exc}"})
    if original_ua:
        session.headers["User-Agent"] = original_ua


def append_download(manifest: list[dict], byte_hashes: dict[str, str], *, state: str,
                    year: int, url: str, response: requests.Response, path: Path,
                    coverage: str, election_date: str = "", election_stage: str = "") -> None:
    path = write_snapshot(path, response.content)
    digest = hashlib.sha256(response.content).hexdigest()
    rel = path.relative_to(ROOT).as_posix()
    manifest.append({"state": state, "election_year": year, "election_date": election_date,
        "election_stage": election_stage,
        "official_url": response.url, "retrieved_at": now_iso(), "local_path": rel,
        "media_type": response.headers.get("content-type", "application/octet-stream").split(";")[0],
        "size_bytes": len(response.content), "sha256": digest,
        "duplicate_of": byte_hashes.get(digest, ""), "coverage": coverage})
    byte_hashes.setdefault(digest, rel)


def acquire_south_carolina_county_precincts(session: requests.Session, manifest: list[dict],
                                             unresolved: list[dict], discovered: dict,
                                             byte_hashes: dict[str, str], audit_only: bool) -> None:
    """Recover precinct ZIPs from each county's official legacy ENR instance."""
    archive_url = next(s.archive_url for s in SOURCES if s.state == "SC")
    try:
        archive = fetch(session, archive_url)
    except Exception as exc:
        unresolved.append({"state": "SC", "election_year": "", "url": archive_url,
            "link_text": "SC election archive", "reason": f"provider_page_failed: {exc}"})
        return
    elections: dict[int, str] = {}
    for text, url in extract_links(archive.content, archive.url):
        year = infer_year(text, url, TARGET_EVEN)
        if year in {2008, 2010, 2012, 2014, 2016} and re.search(r"general election", text, re.I) and not re.search(r"recount|runoff", text, re.I):
            parsed = urlparse(url)
            elections[year] = f"https://results.enr.clarityelections.com{parsed.path}"
    for year, summary_url in sorted(elections.items()):
        try:
            summary = fetch(session, summary_url)
            state_base = summary.url.rsplit("/en/", 1)[0]
            county_select = fetch(session, state_base + "/en/select-county.html")
            append_download(manifest, byte_hashes, state="SC", year=year, url=county_select.url,
                response=county_select, path=RAW / "SC" / "archive_pages" / f"{year}_county_index.html",
                coverage="election_page")
            soup = BeautifulSoup(county_select.content, "html.parser")
            county_values = [(a.get_text(" ", strip=True), a.get("value", ""))
                             for a in soup.select("a[value]") if a.get("value", "").endswith("index.html")]
            discovered.setdefault(("SC", year), []).extend("precinct" for _ in county_values)
            for county, value in county_values:
                county_index_url = "https://results.enr.clarityelections.com/SC" + value
                if audit_only:
                    unresolved.append({"state": "SC", "election_year": year, "url": county_index_url,
                        "link_text": county, "reason": "discovered_not_downloaded_audit_mode"})
                    continue
                try:
                    county_index = fetch(session, county_index_url)
                    match = re.search(rb"\./(\d+)/js/version\.js", county_index.content)
                    if not match:
                        # Older ENR generations expose the result version via
                        # an immediate meta refresh instead of version.js.
                        match = re.search(rb"URL=\./(\d+)/en/summary\.html", county_index.content, re.I)
                    if not match:
                        raise RuntimeError("county result-version id not found")
                    result_id = match.group(1).decode()
                    county_root = county_index.url.rsplit("/index.html", 1)[0]
                    detail_url = f"{county_root}/{result_id}/reports/detailtxt.zip"
                    detail = fetch(session, detail_url)
                    filename = re.sub(r"[^A-Za-z0-9_-]+", "_", county).strip("_") + "_detailtxt.zip"
                    append_download(manifest, byte_hashes, state="SC", year=year, url=detail_url,
                        response=detail, path=RAW / "SC" / str(year) / filename, coverage="precinct")
                except Exception as exc:
                    unresolved.append({"state": "SC", "election_year": year, "url": county_index_url,
                        "link_text": county, "reason": f"county_precinct_download_failed: {exc}"})
        except Exception as exc:
            unresolved.append({"state": "SC", "election_year": year, "url": summary_url,
                "link_text": f"{year} General Election", "reason": f"provider_page_failed: {exc}"})


def acquire_oklahoma_precinct_extracts(session: requests.Session, manifest: list[dict],
                                        unresolved: list[dict], discovered: dict,
                                        byte_hashes: dict[str, str], audit_only: bool) -> None:
    """Use the public OK election-results application's precinct CSV export."""
    application_url = "http://results.okelections.us/OKER/?elecDate=20161108"
    api = "https://results.okelections.gov/OKERS/enrapi/"
    try:
        fetch(session, application_url)
        login = session.put(api + "login/", json={
            "Username": "appuser", "Password": "X098de!22k098Mgfd",
        }, timeout=TIMEOUT)
        login.raise_for_status()
        # The public Angular client removes the service's leading sentinel.
        token = json.loads(login.text)[1:]
    except Exception as exc:
        unresolved.append({"state": "OK", "election_year": "", "url": application_url,
            "link_text": "public election results export", "reason": f"provider_login_failed: {exc}"})
        return
    for year, election_date in OK_GENERAL_DATES.items():
        url = f"{api}GetExtract/PLCSV/{election_date}"
        discovered.setdefault(("OK", year), []).append("precinct")
        if audit_only:
            unresolved.append({"state": "OK", "election_year": year, "url": url,
                "link_text": "Precinct Level Results - CSV (Zipped)",
                "reason": "discovered_not_downloaded_audit_mode"})
            continue
        try:
            result = session.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "*/*"},
                                 timeout=TIMEOUT)
            result.raise_for_status()
            if not result.content.startswith(b"PK"):
                raise RuntimeError("official export was not a ZIP archive")
            append_download(manifest, byte_hashes, state="OK", year=year, url=url,
                response=result, path=RAW / "OK" / str(year) / f"{election_date}_PrecinctResults_csv.zip",
                coverage="precinct")
        except Exception as exc:
            unresolved.append({"state": "OK", "election_year": year, "url": url,
                "link_text": "Precinct Level Results - CSV (Zipped)",
                "reason": f"provider_extract_failed: {exc}"})
    discovered.setdefault(("OK", 2010), []).append("precinct")
    if audit_only:
        unresolved.append({"state": "OK", "election_year": 2010, "url": OK_2010_PRECINCT_ZIP,
            "link_text": "General Election — November 2, 2010",
            "reason": "discovered_not_downloaded_audit_mode"})
    else:
        try:
            result = fetch(session, OK_2010_PRECINCT_ZIP)
            if not result.content.startswith(b"PK"):
                raise RuntimeError("official 2010 response was not a ZIP archive")
            append_download(manifest, byte_hashes, state="OK", year=2010, url=OK_2010_PRECINCT_ZIP,
                response=result, path=RAW / "OK" / "2010" / "110210.zip", coverage="precinct")
        except Exception as exc:
            unresolved.append({"state": "OK", "election_year": 2010, "url": OK_2010_PRECINCT_ZIP,
                "link_text": "General Election — November 2, 2010",
                "reason": f"provider_download_failed: {exc}"})


def acquire_virginia_bulk_csvs(session: requests.Session, manifest: list[dict],
                               unresolved: list[dict], discovered: dict,
                               byte_hashes: dict[str, str], audit_only: bool) -> None:
    """Download official precinct-level Virginia general-election CSVs."""
    landing = "https://www.elections.virginia.gov/resultsreports/election-results/"
    base = "https://apps.elections.virginia.gov/SBE_CSV/ELECTIONS/ELECTIONRESULTS/"
    try:
        fetch(session, landing)  # Establish the browser-like path expected by the file host.
    except Exception as exc:
        unresolved.append({"state": "VA", "election_year": "", "url": landing,
            "link_text": "Virginia election results", "reason": f"provider_page_failed: {exc}"})
        return
    for year in (2005, 2007, 2009, 2011, 2013, 2015):
        directory_url = f"{base}{year}/"
        try:
            directory = fetch(session, directory_url)
            links = [(text, url) for text, url in extract_links(directory.content, directory.url)
                     if re.search(r"(?:november|11-8).*general", f"{text} {url}", re.I)
                     and Path(urlparse(url).path).suffix.lower() == ".csv"]
            if len(links) != 1:
                raise RuntimeError(f"expected one November general CSV, found {len(links)}")
            text, url = links[0]
            discovered.setdefault(("VA", year), []).append("precinct")
            if audit_only:
                unresolved.append({"state": "VA", "election_year": year, "url": url,
                    "link_text": text, "reason": "discovered_not_downloaded_audit_mode"})
                continue
            result = fetch(session, url)
            if b"PrecinctUid" not in result.content[:1000] or b"PrecinctName" not in result.content[:1000]:
                raise RuntimeError("CSV lacks expected precinct fields")
            append_download(manifest, byte_hashes, state="VA", year=year, url=url,
                response=result, path=RAW / "VA" / str(year) / f"{year}_November_General.csv",
                coverage="precinct")
        except Exception as exc:
            unresolved.append({"state": "VA", "election_year": year, "url": directory_url,
                "link_text": f"{year} November General", "reason": f"provider_download_failed: {exc}"})


def acquire_tennessee_precinct_results(session: requests.Session, manifest: list[dict],
                                       unresolved: list[dict], discovered: dict,
                                       byte_hashes: dict[str, str], audit_only: bool) -> None:
    """Acquire TN general-election spreadsheets and legacy precinct PDFs."""
    for year, url in TN_GENERAL_SPREADSHEETS.items():
        discovered.setdefault(("TN", year), []).append("precinct")
        if audit_only:
            unresolved.append({"state": "TN", "election_year": year, "url": url,
                "link_text": f"{year} general precinct spreadsheet",
                "reason": "discovered_not_downloaded_audit_mode"})
            continue
        try:
            result = fetch(session, url)
            append_download(manifest, byte_hashes, state="TN", year=year, url=url,
                response=result, path=RAW / "TN" / str(year) / safe_name(result.url, f"{year}_precinct_results.xlsx"),
                coverage="precinct")
        except Exception as exc:
            unresolved.append({"state": "TN", "election_year": year, "url": url,
                "link_text": f"{year} general precinct spreadsheet",
                "reason": f"provider_download_failed: {exc}"})

    archive = next((p for p in (RAW / "TN" / "archive_pages").glob("index*.html")), None)
    if not archive:
        return
    domains = next(s.domains for s in SOURCES if s.state == "TN")
    for text, url in extract_links(archive.read_bytes(), "https://sos.tn.gov/elections/results"):
        match = re.search(r"/results/(1998|2000|2002|2004|2006)-11/", url)
        if not match or not official(url, domains):
            continue
        year = int(match.group(1))
        combined = f"{text} {url}"
        if not re.search(r"precinct|pct|prec|(?:^|[-_])p\.pdf", combined, re.I):
            continue
        discovered.setdefault(("TN", year), []).append("precinct")
        if audit_only:
            unresolved.append({"state": "TN", "election_year": year, "url": url,
                "link_text": text, "reason": "discovered_not_downloaded_audit_mode"})
            continue
        try:
            result = fetch(session, url)
            append_download(manifest, byte_hashes, state="TN", year=year, url=url,
                response=result, path=RAW / "TN" / str(year) / safe_name(result.url, f"{year}_precinct.pdf"),
                coverage="precinct")
        except Exception as exc:
            unresolved.append({"state": "TN", "election_year": year, "url": url,
                "link_text": text, "reason": f"provider_download_failed: {exc}"})


def acquire_louisiana_redistricting_archive(session: requests.Session, manifest: list[dict],
                                             unresolved: list[dict], discovered: dict,
                                             byte_hashes: dict[str, str], audit_only: bool) -> None:
    """Acquire the SOS-derived 2000-2011 precinct panel archived by the LA Legislature."""
    for year in (2003, 2007):
        discovered.setdefault(("LA", year), []).append("precinct")
    if audit_only:
        unresolved.append({"state": "LA", "election_year": "2003;2007", "url": LA_2000_2011_COMBINED,
            "link_text": "SOS combined election and candidate data, 2000-2011",
            "reason": "discovered_not_downloaded_audit_mode"})
        return
    try:
        result = fetch(session, LA_2000_2011_COMBINED)
        if not result.content.startswith(b"PK"):
            raise RuntimeError("official combined data response was not a ZIP archive")
        path = RAW / "LA" / "2000_2011" / "Combined_Data_TextFiles.zip"
        append_download(manifest, byte_hashes, state="LA", year=2003, url=LA_2000_2011_COMBINED,
            response=result, path=path, coverage="precinct")
        # One immutable archive covers both target cycles; repeat the manifest
        # association rather than duplicating the source bytes.
        digest = hashlib.sha256(result.content).hexdigest()
        rel = path.relative_to(ROOT).as_posix()
        manifest.append({"state": "LA", "election_year": 2007, "election_date": "",
            "official_url": LA_2000_2011_COMBINED, "retrieved_at": now_iso(), "local_path": rel,
            "media_type": result.headers.get("content-type", "application/zip").split(";")[0],
            "size_bytes": len(result.content), "sha256": digest, "duplicate_of": rel,
            "coverage": "precinct"})
    except Exception as exc:
        unresolved.append({"state": "LA", "election_year": "2003;2007", "url": LA_2000_2011_COMBINED,
            "link_text": "SOS combined election and candidate data, 2000-2011",
            "reason": f"provider_download_failed: {exc}"})


def acquire_louisiana_precinct_csvs(session: requests.Session, manifest: list[dict],
                                    unresolved: list[dict], discovered: dict,
                                    byte_hashes: dict[str, str], audit_only: bool) -> None:
    """Download every listed regular legislative contest from both election stages."""
    endpoint = "https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob="
    for year, stages in LA_LEGISLATIVE_ELECTION_DATES.items():
        for stage, date in stages.items():
            index_url = f"{endpoint}{date}/ElectionRaces.htm"
            try:
                index_response = fetch(session, index_url)
                races = index_response.json().get("Races", {}).get("Race", [])
                if isinstance(races, dict):
                    races = [races]
                if not audit_only:
                    append_download(
                        manifest, byte_hashes, state="LA", year=year, url=index_url,
                        response=index_response,
                        path=RAW / "LA" / str(year) / f"ElectionRaces_{date}.htm",
                        coverage="race_index", election_date=date, election_stage=stage,
                    )
            except Exception as exc:
                unresolved.append({"state": "LA", "election_year": year, "url": index_url,
                    "link_text": f"{year} {stage} election race index",
                    "reason": f"provider_index_failed: {exc}"})
                continue
            legislative = [r for r in races if re.search(
                r"State (?:Representative|Senator)\b", r.get("OfficeTitleAndDesc", ""), re.I)]
            discovered.setdefault(("LA", year), []).extend("precinct" for _ in legislative)
            for race in legislative:
                race_id = str(race.get("RaceID", "")).strip()
                url = f"{endpoint}{date}/csv/ByPrecinct_{race_id}.csv"
                if audit_only:
                    unresolved.append({"state": "LA", "election_year": year, "url": url,
                        "link_text": f"{stage}: {race.get('OfficeTitleAndDesc', race_id)}",
                        "reason": "discovered_not_downloaded_audit_mode"})
                    continue
                try:
                    result = fetch(session, url)
                    if not result.content.startswith(b"Office,Parish,Ward,Precinct"):
                        raise RuntimeError("CSV lacks the expected Office, Parish, Ward, Precinct columns")
                    append_download(manifest, byte_hashes, state="LA", year=year, url=url,
                        response=result, path=RAW / "LA" / str(year) / f"ByPrecinct_{race_id}.csv",
                        coverage="precinct", election_date=date, election_stage=stage)
                except Exception as exc:
                    unresolved.append({"state": "LA", "election_year": year, "url": url,
                        "link_text": f"{stage}: {race.get('OfficeTitleAndDesc', race_id)}",
                        "reason": f"provider_download_failed: {exc}"})


def acquire_kentucky_county_recaps(session: requests.Session, manifest: list[dict],
                                   unresolved: list[dict], discovered: dict,
                                   byte_hashes: dict[str, str], audit_only: bool,
                                   years: set[int] | None = None) -> None:
    """Acquire county recap files whose rows contain Kentucky precinct results."""
    pages = {
        2002: "https://elect.ky.gov/results/2000-2009/Pages/2002primaryandgeneralelectionresults.aspx",
        2004: "https://elect.ky.gov/results/2000-2009/Pages/2004primaryandgeneralelectionresults.aspx",
        2006: "https://elect.ky.gov/results/2000-2009/Pages/2006primaryandgeneralelectionresults.aspx",
        2008: "https://elect.ky.gov/results/2000-2009/Pages/2008primaryandgeneralelectionresults.aspx",
        2010: "https://elect.ky.gov/Pages/2010-Recap-Sheets.aspx",
        2012: "https://elect.ky.gov/Pages/2012-Recap-Sheets.aspx",
        2014: "https://elect.ky.gov/Pages/2014-Recap-Sheets.aspx",
        2016: "https://elect.ky.gov/Pages/2016recap-sheets.aspx",
    }
    for year, page_url in pages.items():
        if years is not None and year not in years:
            continue
        try:
            page = fetch(session, page_url)
            soup = BeautifulSoup(page.content, "html.parser")
            candidates: list[tuple[str, str]] = []
            if year <= 2008:
                for a in soup.select("a[href]"):
                    url = urljoin(page.url, a.get("href", ""))
                    path = unquote(urlparse(url).path)
                    general_tail = path.split("/General Election/", 1)[-1]
                    county_subdirectory = "/General Election/" in path and "/" in general_tail
                    if "/General Election/" in path and (
                        re.search(r"/(?:res_|[A-Z]+ gen )", path, re.I) or county_subdirectory
                    ) and not re.search(r"reg(?:istration)?stat", path, re.I):
                        candidates.append((a.get_text(" ", strip=True), url))
            else:
                section = ""
                for tag in soup.find_all(["h1", "h2", "h3", "h4", "strong", "a"]):
                    if tag.name != "a":
                        label = " ".join(tag.stripped_strings)
                        if label:
                            section = label
                        continue
                    url = urljoin(page.url, tag.get("href", ""))
                    if Path(urlparse(url).path).suffix.lower() != ".pdf":
                        continue
                    if year == 2010:
                        is_general = bool(re.search(r"gen2010\.pdf$", unquote(url), re.I))
                    else:
                        is_general = section.strip().lower() == "general"
                    if is_general:
                        candidates.append((tag.get_text(" ", strip=True), url))
            candidates = list(dict.fromkeys(candidates))
            discovered.setdefault(("KY", year), []).extend("precinct" for _ in candidates)
            for label, url in candidates:
                if audit_only:
                    unresolved.append({"state": "KY", "election_year": year, "url": url,
                        "link_text": label, "reason": "discovered_not_downloaded_audit_mode"})
                    continue
                try:
                    result = fetch(session, url)
                    append_download(manifest, byte_hashes, state="KY", year=year, url=url,
                        response=result, path=RAW / "KY" / str(year) / "county_recaps" /
                        safe_name(result.url, f"{label}_{year}.dat"), coverage="precinct")
                except Exception as exc:
                    unresolved.append({"state": "KY", "election_year": year, "url": url,
                        "link_text": label, "reason": f"county_recap_download_failed: {exc}"})
        except Exception as exc:
            unresolved.append({"state": "KY", "election_year": year, "url": page_url,
                "link_text": f"{year} county recap index", "reason": f"provider_page_failed: {exc}"})


def acquire_south_carolina_election_reports(session: requests.Session, manifest: list[dict],
                                             unresolved: list[dict], byte_hashes: dict[str, str],
                                             audit_only: bool) -> None:
    """Preserve official pre-ENR election reports without calling them precinct data."""
    for year, url in SC_ELECTION_REPORTS.items():
        if audit_only:
            unresolved.append({"state": "SC", "election_year": year, "url": url,
                "link_text": f"{year} election report", "reason": "discovered_not_downloaded_audit_mode"})
            continue
        try:
            result = fetch(session, url)
            if not result.content.startswith(b"%PDF"):
                raise RuntimeError("official election report response was not a PDF")
            append_download(manifest, byte_hashes, state="SC", year=year, url=url,
                response=result, path=RAW / "SC" / str(year) / f"Election_Report_{year}.pdf",
                coverage="published_report")
        except Exception as exc:
            unresolved.append({"state": "SC", "election_year": year, "url": url,
                "link_text": f"{year} election report", "reason": f"provider_download_failed: {exc}"})


def acquire_arkansas_static_results(session: requests.Session, manifest: list[dict],
                                    unresolved: list[dict], discovered: dict,
                                    byte_hashes: dict[str, str], audit_only: bool) -> None:
    for year, (url, coverage) in AR_STATIC_GENERAL_FILES.items():
        discovered.setdefault(("AR", year), []).append(coverage)
        if audit_only:
            unresolved.append({"state": "AR", "election_year": year, "url": url,
                "link_text": f"{year} general election results", "reason": "discovered_not_downloaded_audit_mode"})
            continue
        try:
            result = fetch(session, url)
            append_download(manifest, byte_hashes, state="AR", year=year, url=url,
                response=result, path=RAW / "AR" / str(year) / safe_name(result.url, f"{year}_general_results.dat"),
                coverage=coverage)
        except Exception as exc:
            unresolved.append({"state": "AR", "election_year": year, "url": url,
                "link_text": f"{year} general election results", "reason": f"provider_download_failed: {exc}"})

    for year, url in AR_TALLY_GENERAL_FILES.items():
        discovered.setdefault(("AR", year), []).append("precinct")
        if audit_only:
            unresolved.append({"state": "AR", "election_year": year, "url": url,
                "link_text": f"{year} full election data", "reason": "discovered_not_downloaded_audit_mode"})
            continue
        try:
            result = fetch(session, url)
            append_download(manifest, byte_hashes, state="AR", year=year, url=url,
                response=result, path=RAW / "AR" / str(year) / f"{year}_FullDataFile.json",
                coverage="precinct")
        except Exception as exc:
            unresolved.append({"state": "AR", "election_year": year, "url": url,
                "link_text": f"{year} full election data", "reason": f"provider_download_failed: {exc}"})


def run(audit_only: bool = False) -> tuple[list[dict], list[dict], list[dict]]:
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    manifest: list[dict] = []
    unresolved: list[dict] = []
    discovered: dict[tuple[str, int], list[str]] = {}
    byte_hashes: dict[str, str] = {}

    for source in SOURCES:
        archive_path = RAW / source.state / "archive_pages" / "index.html"
        try:
            response = fetch(session, source.archive_url)
            archive_path = write_snapshot(archive_path, response.content)
            digest = hashlib.sha256(response.content).hexdigest()
            manifest.append({
                "state": source.state, "election_year": "", "election_date": "",
                "official_url": response.url, "retrieved_at": now_iso(),
                "local_path": archive_path.relative_to(ROOT).as_posix(),
                "media_type": response.headers.get("content-type", "text/html").split(";")[0],
                "size_bytes": len(response.content), "sha256": digest,
                "duplicate_of": byte_hashes.get(digest, ""), "coverage": "archive_page",
            })
            byte_hashes.setdefault(digest, archive_path.relative_to(ROOT).as_posix())
        except Exception as exc:
            unresolved.append({"state": source.state, "election_year": "", "url": source.archive_url,
                               "link_text": "archive page", "reason": f"archive_fetch_failed: {exc}"})
            continue

        queue = [(text, url, 0) for text, url in extract_links(response.content, response.url)]
        seen_pages: set[str] = {response.url}
        candidates: list[tuple[str, str, int, str]] = []
        for text, url, depth in queue:
            if not official(url, source.domains):
                continue
            year = infer_year(text, url, source.years)
            ext = Path(urlparse(url).path).suffix.lower()
            combined = f"{text} {unquote(url)}"
            excluded = SKIP_WORDS.search(combined) and not re.search(r"general election", combined, re.I)
            if year and ext in FILE_EXTENSIONS and RESULT_WORDS.search(combined) and not excluded:
                candidates.append((text, url, year, coverage_hint(text, url)))
                continue
            # Follow one level of year-specific result pages; this handles state
            # archives whose downloads live on an election detail page.
            if depth == 0 and year and RESULT_WORDS.search(combined) and url not in seen_pages:
                seen_pages.add(url)
                try:
                    page = fetch(session, url)
                    page_path = RAW / source.state / "archive_pages" / f"{year}_{safe_name(page.url, 'results.html')}"
                    if page_path.suffix.lower() not in {".html", ".htm"}:
                        page_path = page_path.with_suffix(page_path.suffix + ".html")
                    page_path = write_snapshot(page_path, page.content)
                    pdigest = hashlib.sha256(page.content).hexdigest()
                    manifest.append({"state": source.state, "election_year": year, "election_date": "",
                        "official_url": page.url, "retrieved_at": now_iso(),
                        "local_path": page_path.relative_to(ROOT).as_posix(),
                        "media_type": page.headers.get("content-type", "text/html").split(";")[0],
                        "size_bytes": len(page.content), "sha256": pdigest,
                        "duplicate_of": byte_hashes.get(pdigest, ""), "coverage": "election_page"})
                    byte_hashes.setdefault(pdigest, page_path.relative_to(ROOT).as_posix())
                    queue.extend((t, u, 1) for t, u in extract_links(page.content, page.url))
                except Exception as exc:
                    unresolved.append({"state": source.state, "election_year": year, "url": url,
                                       "link_text": text, "reason": f"detail_fetch_failed: {exc}"})

        for text, url, year, hint in dict.fromkeys(candidates):
            discovered.setdefault((source.state, year), []).append(hint)
            if audit_only:
                unresolved.append({"state": source.state, "election_year": year, "url": url,
                                   "link_text": text, "reason": "discovered_not_downloaded_audit_mode"})
                continue
            try:
                result = fetch(session, url)
                filename = safe_name(result.url, f"{source.state}_{year}_results.dat")
                path = RAW / source.state / str(year) / filename
                path = write_snapshot(path, result.content)
                digest = hashlib.sha256(result.content).hexdigest()
                rel = path.relative_to(ROOT).as_posix()
                hint = refine_coverage(hint, result.content)
                manifest.append({"state": source.state, "election_year": year, "election_date": "",
                    "official_url": result.url, "retrieved_at": now_iso(), "local_path": rel,
                    "media_type": result.headers.get("content-type", mimetypes.guess_type(filename)[0] or "application/octet-stream").split(";")[0],
                    "size_bytes": len(result.content), "sha256": digest,
                    "duplicate_of": byte_hashes.get(digest, ""), "coverage": hint})
                byte_hashes.setdefault(digest, rel)
            except Exception as exc:
                unresolved.append({"state": source.state, "election_year": year, "url": url,
                                   "link_text": text, "reason": f"download_failed: {exc}"})

    acquire_mississippi_precinct_recaps(session, manifest, unresolved, discovered, byte_hashes, audit_only)
    acquire_south_carolina_county_precincts(session, manifest, unresolved, discovered, byte_hashes, audit_only)
    acquire_oklahoma_precinct_extracts(session, manifest, unresolved, discovered, byte_hashes, audit_only)
    acquire_virginia_bulk_csvs(session, manifest, unresolved, discovered, byte_hashes, audit_only)
    acquire_tennessee_precinct_results(session, manifest, unresolved, discovered, byte_hashes, audit_only)
    acquire_louisiana_redistricting_archive(session, manifest, unresolved, discovered, byte_hashes, audit_only)
    acquire_louisiana_precinct_csvs(session, manifest, unresolved, discovered, byte_hashes, audit_only)
    acquire_kentucky_county_recaps(session, manifest, unresolved, discovered, byte_hashes, audit_only)
    acquire_south_carolina_election_reports(session, manifest, unresolved, byte_hashes, audit_only)
    acquire_arkansas_static_results(session, manifest, unresolved, discovered, byte_hashes, audit_only)

    inventory: list[dict] = []
    for source in SOURCES:
        for year in source.years:
            files = [m for m in manifest if m["state"] == source.state and m["election_year"] == year and m["coverage"] not in {"election_page"}]
            hints = discovered.get((source.state, year), [])
            if any(m["coverage"] == "precinct" for m in files):
                status = "downloaded_precinct"
            elif files:
                status = "downloaded_unknown_granularity"
            elif "precinct" in hints:
                status = "linked_precinct"
            elif hints:
                status = "linked_unknown_granularity"
            else:
                status = "not_found_on_archive"
            inventory.append({"state": source.state, "election_year": year, "status": status,
                              "download_count": len(files), "discovered_link_count": len(hints),
                              "archive_url": source.archive_url})

    csv_write(AUDIT / "southern_sos_download_manifest.csv", manifest,
              ["state", "election_year", "election_date", "election_stage", "official_url", "retrieved_at", "local_path", "media_type", "size_bytes", "sha256", "duplicate_of", "coverage"])
    csv_write(AUDIT / "southern_sos_precinct_inventory.csv", inventory,
              ["state", "election_year", "status", "download_count", "discovered_link_count", "archive_url"])
    csv_write(AUDIT / "southern_sos_unresolved_links.csv", unresolved,
              ["state", "election_year", "url", "link_text", "reason"])
    csv_write(AUDIT / "southern_sos_manual_access.csv", MANUAL_ACCESS,
              ["state", "cycles", "access_status", "url", "save_under", "reason"])
    return manifest, inventory, unresolved


def run_louisiana_legislative(audit_only: bool = False) -> tuple[list[dict], list[dict], list[dict]]:
    """Run the official Louisiana two-stage acquisition without touching other providers."""
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    manifest: list[dict] = []
    unresolved: list[dict] = []
    discovered: dict[tuple[str, int], list[str]] = {}
    byte_hashes: dict[str, str] = {}
    acquire_louisiana_precinct_csvs(
        session, manifest, unresolved, discovered, byte_hashes, audit_only
    )

    coverage: list[dict] = []
    for year, stages in LA_LEGISLATIVE_ELECTION_DATES.items():
        for stage, date in stages.items():
            date_rows = [row for row in manifest if row.get("election_date") == date]
            failures = [row for row in unresolved if f"blob={date}/" in row.get("url", "")]
            index_count = sum(row.get("coverage") == "race_index" for row in date_rows)
            contest_count = sum(row.get("coverage") == "precinct" for row in date_rows)
            coverage.append({
                "election_year": year,
                "election_date": date,
                "election_stage": stage,
                "race_index_downloaded": index_count,
                "legislative_contest_files": contest_count,
                "failed_downloads": len(failures),
                "status": "complete" if not audit_only and index_count == 1 and not failures else
                          "audit_only" if audit_only else "incomplete",
            })

    csv_write(AUDIT / "louisiana_legislative_results_manifest.csv", manifest,
              ["state", "election_year", "election_date", "election_stage", "official_url", "retrieved_at", "local_path", "media_type", "size_bytes", "sha256", "duplicate_of", "coverage"])
    csv_write(AUDIT / "louisiana_legislative_results_coverage.csv", coverage,
              ["election_year", "election_date", "election_stage", "race_index_downloaded", "legislative_contest_files", "failed_downloads", "status"])
    csv_write(AUDIT / "louisiana_legislative_results_unresolved.csv", unresolved,
              ["state", "election_year", "url", "link_text", "reason"])
    return manifest, coverage, unresolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true", help="inventory links without downloading result files")
    parser.add_argument("--louisiana-legislative-only", action="store_true",
                        help="acquire both stages of Louisiana regular legislative elections only")
    args = parser.parse_args()
    if args.louisiana_legislative_only:
        manifest, inventory, unresolved = run_louisiana_legislative(args.audit)
    else:
        manifest, inventory, unresolved = run(args.audit)
    print(f"manifest_rows={len(manifest)} inventory_rows={len(inventory)} unresolved_rows={len(unresolved)}")
    print("coverage=" + ", ".join(f"{k}:{sum(r['status'] == k for r in inventory)}" for k in sorted({r['status'] for r in inventory})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
