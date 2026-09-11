#!/usr/bin/env python3
"""Acquire and audit official Southern state campaign-finance source files.

This is a raw-source acquisition layer. It deliberately does not match
committees to candidates, reconcile amendments, or create model features.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import mimetypes
import os
import string
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/finance/southern"
AUDIT = ROOT / "data/processed/source_audits"
MANIFEST_PATH = AUDIT / "southern_campaign_finance_manifest.csv"
COVERAGE_PATH = AUDIT / "southern_campaign_finance_coverage.csv"
UNRESOLVED_PATH = AUDIT / "southern_campaign_finance_unresolved.csv"
PANEL_PATH = ROOT / "data/processed/war/southern_war_panel_v1/southern_war_panel.csv"
TARGET_YEARS = tuple(range(2016, 2025))
# A two-calendar-year campaign-cycle total for the 2016 elections requires
# 2015 transactions.  Keep the modeled target years distinct from the source
# acquisition years so coverage reporting still describes 2016-2024.
SOURCE_YEARS = tuple(range(2015, 2025))
FLORIDA_ELECTIONS = {
    2016: "20161108-GEN",
    2018: "20181106-GEN",
    2020: "20201103-GEN",
    2022: "20221108-GEN",
    2024: "20241105-GEN",
}
FLORIDA_OFFICES = ("STS", "STR")
FLORIDA_ROW_LIMIT = 9999
FLORIDA_DATABASE_START_YEAR = 1996
TIMEOUT = 120
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/125 Safari/537.36 "
    "Alabama-legislative-model-campaign-finance-research"
)

MANIFEST_FIELDS = [
    "source_file_id", "provider", "source_url", "retrieved_at", "sha256",
    "media_type", "size_bytes", "license_or_terms", "state_code", "cycle",
    "geography_vintage", "authoritative_scope", "ingest_status",
    "acquisition_method", "data_kind", "local_path", "request_parameters",
    "query_scope", "record_count", "response_limit", "notes",
]


@dataclass(frozen=True)
class StateSource:
    state: str
    provider: str
    portal_url: str
    access_class: str
    data_categories: str
    limitation: str = ""


SOURCES = (
    StateSource("AL", "Alabama Secretary of State FCPA", "https://fcpa.alabamavotes.gov/page.request.do?page=page.acfPublicDownloadData", "existing_upstream", "contributions|in_kind|other_receipts|expenditures"),
    StateSource("AR", "Arkansas Secretary of State", "https://ethics-disclosures.sos.arkansas.gov/public/cf/downloads", "partial_bulk_api", "contributions_and_loans|expenditures", "Structured statewide CSV exports begin in filing year 2022; 2016-2021 legacy filings are PDF-only in the current portal."),
    StateSource("DE", "Delaware Department of Elections", "https://elections.delaware.gov/candidates/campaignfinance/index.html", "query_report_export", "committees|reports|contributions|expenditures", "No statewide bulk transaction dump is exposed."),
    StateSource("FL", "Florida Department of State Division of Elections", "https://dos.elections.myflorida.com/campaign-finance/contributions/", "partitioned_query_export", "candidate_contributions|candidate_expenditures", "State-legislative candidate exports must be partitioned because each form response is capped at the requested row limit."),
    StateSource("GA", "Georgia Government Transparency and Campaign Finance Commission", "https://ethics.ga.gov/records-search-all/", "hybrid_query_export", "candidate_contributions|candidate_expenditures", "Official records are split between the 2005-2021 legacy system and the 2022-2025 Record Search system; the latter is exported in monthly candidate partitions because its bulk endpoint currently returns HTTP 406 and annual transaction exports time out."),
    StateSource("KY", "Kentucky Registry of Election Finance", "https://secure.kentucky.gov/kref/publicsearch/CandidateSearch/", "query_export", "candidate_receipts|candidate_expenses|contributions", "Candidate and transaction exports require election/office queries."),
    StateSource("LA", "Louisiana Board of Ethics", "https://ethics.la.gov/CampaignFinanceSearch/ShowPremadereports.aspx", "direct_bulk", "contributions|loans|expenditures"),
    StateSource("MD", "Maryland State Board of Elections MD CRIS", "https://elections.maryland.gov/campaign_finance/", "query_export", "committees|reports|contributions|expenditures", "MD CRIS does not expose an obvious statewide bulk archive."),
    StateSource("MS", "Mississippi Secretary of State", "https://cfportal.sos.ms.gov/online/portal/cf/page/cf-search/Portal.aspx", "query_export_partial", "committees|reports|contributions|expenditures", "Only electronically filed reports are fully transaction-searchable; paper filings remain documents."),
    StateSource("MO", "unconfigured", "", "unconfigured", "", "Missouri is in the Southern model universe but was absent from the supplied source list."),
    StateSource("NC", "North Carolina State Board of Elections", "https://cf.ncsbe.gov/CFTxnLkup/AdvancedSearch/", "form_query_export", "candidate_receipts|candidate_expenditures", "Official CSV exports are assembled by calendar year and N.C. House/Senate office code."),
    StateSource("OK", "Oklahoma Ethics Commission Guardian", "https://guardian.ok.gov/PublicSite/DataDownload.aspx", "direct_bulk", "contributions_and_loans|expenditures"),
    StateSource("SC", "South Carolina State Ethics Commission", "https://ethicsfiling.sc.gov/public/campaign-reports/contributions", "annual_query_api", "contributions|expenditures|reports", "Official statewide public transaction searches are captured as annual JSON responses; downstream adapters must restrict offices and resolve amendments."),
    StateSource("TN", "Tennessee Registry of Election Finance", "https://apps.tn.gov/tncamp/public/cesearch.htm", "form_query_export", "candidate_contributions|candidate_expenditures", "Official candidate transaction CSVs are generated by report-year form queries."),
    StateSource("TX", "Texas Ethics Commission", "https://www.ethics.state.tx.us/search/cf/", "existing_upstream", "campaign_finance_csv_database|annual_totals"),
    StateSource("VA", "Virginia Department of Elections", "https://cfreports.elections.virginia.gov/", "query_report_export", "committees|reports|xml", "Structured reports are committee-scoped; no statewide CSV dump is exposed."),
    StateSource("WV", "West Virginia Secretary of State", "https://apps.sos.wv.gov/elections/candidate-search/previous.aspx", "candidate_report_export", "candidates|reports|raw_data", "Historical finance is candidate/report scoped."),
)


def louisiana_files() -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    blocks = ((2016, 2019), (2020, 2023), (2024, 2027))
    kinds = {
        "contributions": ("ContributionReports", "Contributions"),
        "loans": ("LoanReports", "Loans"),
        "expenditures": ("ExpenditureReports", "Expenditures"),
    }
    root = "https://www.ethics.la.gov/Pub/CampFinan/DataDownload"
    for start, end in blocks:
        for kind, (folder, stem) in kinds.items():
            name = f"{stem}_{start}_to_{end}.csv"
            files.append({
                "state": "LA", "provider": "Louisiana Board of Ethics",
                "url": f"{root}/{folder}/{name}", "name": name,
                "data_kind": kind, "cycle": f"{start}-{end}",
                "authoritative_scope": f"reported campaign-finance {kind} in filing years {start}-{end}",
            })
    return files


def arkansas_files() -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    endpoint = (
        "https://api-ethics-disclosures.sos.arkansas.gov/api/"
        "ExportData/GetExportPublicDownloadData"
    )
    kinds = {
        "contributions_and_loans": "TCON",
        "expenditures": "TEXP",
    }
    for year in range(2022, 2025):
        for kind, transaction_type in kinds.items():
            payload = {
                "transactionTypeCode": transaction_type,
                "type": "CSV",
                "filingYear": str(year),
            }
            files.append({
                "state": "AR", "provider": "Arkansas Secretary of State",
                "url": endpoint, "name": f"{year}_{kind}.csv",
                "data_kind": kind, "cycle": str(year),
                "authoritative_scope": (
                    f"reported campaign-finance {kind} filed in {year}; "
                    "statewide current-system export"
                ),
                "method": "POST",
                "json": payload,
                "request_parameters": json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                ),
                "acquisition_method": "official_public_api_export",
            })
    return files


def oklahoma_files() -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    root = "https://guardian.ok.gov/PublicSite/Docs/BulkDataDownloads"
    kinds = {
        "contributions_and_loans": "ContributionLoanExtract",
        "expenditures": "ExpenditureExtract",
    }
    for year in TARGET_YEARS:
        for kind, stem in kinds.items():
            name = f"{year}_{stem}.csv.zip"
            files.append({
                "state": "OK", "provider": "Oklahoma Ethics Commission Guardian",
                "url": f"{root}/{name}", "name": name, "data_kind": kind,
                "cycle": str(year),
                "authoritative_scope": f"reported campaign-finance {kind} in filing year {year}",
            })
    return files


def south_carolina_files() -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    queries = {
        "contributions": (
            "https://ethicsfiling.sc.gov/api/Candidate/Contribution/Search/",
            {
                "amountMin": 0, "officeRun": "", "candidate": "",
                "contributorName": "", "contributorOccupation": "",
                "contributionDescription": "",
            },
            "contributionYear",
        ),
        "expenditures": (
            "https://ethicsfiling.sc.gov/api/Candidate/Expenditure/Public/"
            "Get/All/Campaign/Expenditures",
            {
                "candidate": "", "office": "", "vendorName": "",
                "vendorLoc": "Any", "amount": 0, "expDesc": "",
            },
            "expenditureYear",
        ),
    }
    for year in TARGET_YEARS:
        for kind, (url, base_payload, year_field) in queries.items():
            payload = {**base_payload, year_field: year}
            files.append({
                "state": "SC", "provider": "South Carolina State Ethics Commission",
                "url": url, "name": f"{year}_{kind}.json",
                "data_kind": kind, "cycle": str(year), "method": "POST",
                "json": payload,
                "request_parameters": json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                ),
                "query_scope": f"year={year};kind={kind}",
                "authoritative_scope": (
                    f"statewide public {kind} search results for reporting year {year}"
                ),
                "acquisition_method": "official_public_json_query",
                "count_json_records": True,
                "notes": (
                    "Raw statewide public-search response; includes non-legislative "
                    "offices and requires a downstream office/candidate adapter."
                ),
            })
    return files


DIRECT_FILES = tuple(
    arkansas_files() + louisiana_files() + oklahoma_files()
    + south_carolina_files()
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def read_existing_manifest() -> dict[str, dict[str, str]]:
    if not MANIFEST_PATH.exists():
        return {}
    with MANIFEST_PATH.open(encoding="utf-8-sig", newline="") as handle:
        return {row["local_path"]: row for row in csv.DictReader(handle)}


def media_type(path: Path, response_type: str = "") -> str:
    if response_type:
        return response_type.split(";", 1)[0].strip()
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def manifest_row(spec: dict[str, object], path: Path, retrieved_at: str,
                 response_type: str = "") -> dict[str, object]:
    digest = sha256(path)
    state = str(spec["state"])
    kind = str(spec["data_kind"])
    cycle = str(spec["cycle"])
    request_parameters = str(spec.get("request_parameters", ""))
    request_token = (
        f":{hashlib.sha256(request_parameters.encode('utf-8')).hexdigest()[:10]}"
        if request_parameters else ""
    )
    return {
        "source_file_id": f"finance:{state.lower()}:{kind}:{cycle}{request_token}:{digest[:12]}",
        "provider": spec["provider"], "source_url": spec["url"],
        "retrieved_at": retrieved_at, "sha256": digest,
        "media_type": media_type(path, response_type), "size_bytes": path.stat().st_size,
        "license_or_terms": "official public records; reuse terms not stated on download page",
        "state_code": state, "cycle": cycle, "geography_vintage": "not_applicable",
        "authoritative_scope": spec["authoritative_scope"],
        "ingest_status": spec.get("ingest_status", "acquired_unparsed"),
        "acquisition_method": spec.get("acquisition_method", "official_direct_bulk_download"),
        "data_kind": kind,
        "local_path": relative(path),
        "request_parameters": spec.get("request_parameters", ""),
        "query_scope": spec.get("query_scope", ""),
        "record_count": spec.get("record_count", ""),
        "response_limit": spec.get("response_limit", ""),
        "notes": spec.get("notes", "Raw provider artifact; may include non-legislative filers."),
    }


def acquire_file(session: requests.Session, spec: dict[str, object], existing: dict[str, dict[str, str]],
                 timeout: int) -> dict[str, object]:
    destination = RAW / str(spec["state"]) / str(spec["name"])
    rel = relative(destination)
    if destination.exists():
        if spec.get("count_delimited_records"):
            spec["record_count"] = count_delimited_records(destination)
        if spec.get("count_json_records"):
            spec["record_count"] = count_json_records(destination)
        prior = existing.get(rel, {})
        retrieved_at = prior.get("retrieved_at") or datetime.fromtimestamp(
            destination.stat().st_mtime, timezone.utc
        ).replace(microsecond=0).isoformat()
        return manifest_row(spec, destination, retrieved_at, prior.get("media_type", ""))

    destination.parent.mkdir(parents=True, exist_ok=True)
    method = str(spec.get("method", "GET")).upper()
    if method == "POST":
        post_args = {"json": spec["json"]} if "json" in spec else {"data": spec.get("data", {})}
        response = session.post(str(spec["url"]), **post_args, timeout=timeout,
                                stream=True, allow_redirects=True)
    else:
        response = session.get(
            str(spec["url"]), timeout=timeout, stream=True, allow_redirects=True,
        )
    response.raise_for_status()
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".part", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            for block in response.iter_content(1024 * 1024):
                if block:
                    handle.write(block)
        temp_path = Path(temp_name)
        if temp_path.stat().st_size == 0:
            raise RuntimeError("provider returned an empty artifact")
        expected_header = spec.get("expected_header")
        if expected_header:
            with temp_path.open("rb") as check:
                first_line = check.readline().decode("utf-8-sig", errors="replace").strip()
            if not first_line.startswith(str(expected_header)):
                raise RuntimeError(f"unexpected provider response header: {first_line[:160]}")
        if spec.get("count_delimited_records"):
            spec["record_count"] = count_delimited_records(temp_path)
        if spec.get("count_json_records"):
            spec["record_count"] = count_json_records(temp_path)
        if destination.exists():
            raise RuntimeError(f"refusing to overwrite raw evidence: {destination}")
        temp_path.replace(destination)
    finally:
        if Path(temp_name).exists():
            Path(temp_name).unlink()
    return manifest_row(spec, destination, utc_now(), response.headers.get("content-type", ""))


def count_delimited_records(path: Path) -> int:
    with path.open("rb") as handle:
        line_count = sum(1 for _ in handle)
    return max(0, line_count - 1)


def count_json_records(path: Path) -> int:
    with path.open(encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise RuntimeError("provider JSON response is not a record array")
    return len(payload)


def florida_form_payload(
    kind: str, year: int, office: str, prefix: str,
    date_from: date | None = None, date_to: date | None = None,
) -> dict[str, str]:
    payload = {
        "election": FLORIDA_ELECTIONS[year], "search_on": "1",
        "CanFName": "", "CanLName": prefix, "CanNameSrch": "2",
        "office": office, "cdistrict": "", "cgroup": "", "party": "All",
        "ComName": "", "ComNameSrch": "2", "committee": "All",
        "cfname": "", "clname": "", "namesearch": "2", "ccity": "",
        "cstate": "", "czipcode": "", "cdollar_minimum": "",
        "cdollar_maximum": "", "rowlimit": str(FLORIDA_ROW_LIMIT),
        "csort1": "NAM", "csort2": "CAN",
        "cdatefrom": date_from.strftime("%m/%d/%Y") if date_from else "",
        "cdateto": date_to.strftime("%m/%d/%Y") if date_to else "",
        "queryformat": "2", "Submit": "Submit",
    }
    payload["coccupation" if kind == "contributions" else "cpurpose"] = ""
    return payload


def florida_query_spec(
    kind: str, year: int, office: str, prefix: str,
    date_from: date | None = None, date_to: date | None = None,
    date_partition: str = "",
) -> dict[str, object]:
    endpoint_name = "contrib.exe" if kind == "contributions" else "expend.exe"
    payload = florida_form_payload(kind, year, office, prefix, date_from, date_to)
    parameters = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    partition_name = f"/{date_partition}" if date_partition else ""
    date_scope = (
        f";date_from={date_from.isoformat()};date_to={date_to.isoformat()}"
        f";date_partition={date_partition}"
        if date_from and date_to else ""
    )
    return {
        "state": "FL", "provider": "Florida Department of State Division of Elections",
        "url": f"https://dos.elections.myflorida.com/cgi-bin/{endpoint_name}",
        "name": f"{kind}/{year}/{office}/{prefix}{partition_name}.tsv", "data_kind": kind,
        "cycle": str(year), "method": "POST", "data": payload,
        "authoritative_scope": (
            f"reported {kind} for Florida {office} candidates assigned to the {year} "
            f"general-election record, candidate surname beginning {prefix}"
        ),
        "acquisition_method": "official_partitioned_form_export",
        "request_parameters": parameters,
        "query_scope": f"year={year};office={office};surname_prefix={prefix}{date_scope}",
        "response_limit": FLORIDA_ROW_LIMIT,
        "count_delimited_records": True,
        "expected_header": (
            "Candidate/Committee\tDate\tAmount\tTyp"
            if kind == "contributions"
            else "Candidate/Committee\tDate\tAmount\tPayee Name"
        ),
        "notes": "Raw tab-delimited form export; candidate query partition retained verbatim.",
    }


def bootstrap_florida_session(session: requests.Session) -> None:
    """Acquire the browser cookies currently required by Florida's public form."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    try:
        driver.get("https://dos.elections.myflorida.com/campaign-finance/contributions/")
        time.sleep(2)
        session.headers["User-Agent"] = driver.execute_script("return navigator.userAgent")
        for cookie in driver.get_cookies():
            session.cookies.set(
                cookie["name"], cookie["value"], domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )
    finally:
        driver.quit()


def acquire_florida(
    session: requests.Session, existing: dict[str, dict[str, str]], timeout: int,
    years: set[int], audit_only: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    manifest: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    def acquire_prefix(kind: str, year: int, office: str, prefix: str) -> None:
        spec = florida_query_spec(kind, year, office, prefix)
        destination = RAW / "FL" / str(spec["name"])
        if audit_only and not destination.exists():
            return
        try:
            row = acquire_file(session, spec, existing, timeout)
            count = int(row["record_count"])
            if count >= FLORIDA_ROW_LIMIT:
                row["ingest_status"] = "acquired_truncated"
            manifest.append(row)
            print(f"FL {kind} {year} {office} {prefix}: {count} rows", flush=True)
            if count >= FLORIDA_ROW_LIMIT:
                if len(prefix) < 3:
                    for suffix in string.ascii_uppercase:
                        acquire_prefix(kind, year, office, prefix + suffix)
                else:
                    for calendar_year in range(
                        FLORIDA_DATABASE_START_YEAR, datetime.now().year + 1
                    ):
                        acquire_date_range(
                            kind, year, office, prefix,
                            date(calendar_year, 1, 1), date(calendar_year, 12, 31),
                            f"year_{calendar_year}", "year",
                        )
        except Exception as exc:
            failures.append({
                "state": "FL", "data_kind": kind, "source_url": spec["url"],
                "access_class": "partitioned_query_export",
                "reason": f"query_failed ({year} {office} {prefix}): {exc}",
                "next_action": "retry_or_review_provider_response",
            })
            print(
                f"FAILED FL {kind} {year} {office} {prefix}: {exc}",
                flush=True,
            )

    def acquire_date_range(
        kind: str, year: int, office: str, prefix: str,
        date_from: date, date_to: date, partition_name: str, granularity: str,
    ) -> None:
        spec = florida_query_spec(
            kind, year, office, prefix, date_from, date_to, partition_name,
        )
        destination = RAW / "FL" / str(spec["name"])
        if audit_only and not destination.exists():
            return
        try:
            row = acquire_file(session, spec, existing, timeout)
            count = int(row["record_count"])
            if count >= FLORIDA_ROW_LIMIT:
                row["ingest_status"] = "acquired_truncated"
            manifest.append(row)
            print(
                f"FL {kind} {year} {office} {prefix} {partition_name}: {count} rows",
                flush=True,
            )
            if count < FLORIDA_ROW_LIMIT:
                return
            if granularity == "year":
                for month in range(1, 13):
                    last_day = calendar.monthrange(date_from.year, month)[1]
                    acquire_date_range(
                        kind, year, office, prefix,
                        date(date_from.year, month, 1), date(date_from.year, month, last_day),
                        f"month_{date_from.year}_{month:02d}", "month",
                    )
            elif granularity == "month":
                for day in range(1, date_to.day + 1):
                    one_day = date(date_from.year, date_from.month, day)
                    acquire_date_range(
                        kind, year, office, prefix, one_day, one_day,
                        f"day_{one_day.isoformat()}", "day",
                    )
            else:
                failures.append({
                    "state": "FL", "data_kind": kind, "source_url": spec["url"],
                    "access_class": "partitioned_query_export",
                    "reason": f"single-day query remained capped ({partition_name})",
                    "next_action": "add_an_amount_partition_dimension",
                })
        except Exception as exc:
            failures.append({
                "state": "FL", "data_kind": kind, "source_url": spec["url"],
                "access_class": "partitioned_query_export",
                "reason": f"date_query_failed ({year} {office} {prefix} {partition_name}): {exc}",
                "next_action": "retry_or_review_provider_response",
            })
            print(
                f"FAILED FL {kind} {year} {office} {prefix} {partition_name}: {exc}",
                flush=True,
            )

    for year in sorted(years & set(FLORIDA_ELECTIONS)):
        for office in FLORIDA_OFFICES:
            for kind in ("contributions", "expenditures"):
                for prefix in string.ascii_uppercase:
                    acquire_prefix(kind, year, office, prefix)
    return manifest, failures


def north_carolina_search_payload(year: int, office: str, token: str) -> list[tuple[str, str]]:
    return [
        ("Filter.ReceiptAll", "true"), ("Filter.ReceiptAll", "false"),
        ("Filter.ExpenditureAll", "true"), ("Filter.ExpenditureAll", "false"),
        ("Filter.CommitteeAll", "false"),
        ("Filter.SelectedCommitteeTypes", "CNC"),
        ("Filter.SelectedCommitteeTypes", "JNT"),
        ("Filter.PartyAll", "true"), ("Filter.PartyAll", "false"),
        ("Filter.OfficeAll", "false"), ("Filter.SelectedOfficeTypes", office),
        ("Filter.CommitteeIDs", ""), ("Filter.CommitteeNames", ""),
        ("Filter.CountyList", ""), ("Filter.StartDate", f"01/01/{year}"),
        ("Filter.EndDate", f"12/31/{year}"), ("Filter.AmountFrom", ""),
        ("Filter.AmountTo", ""), ("Filter.CityList", ""),
        ("Filter.IsOrg", "false"), ("Filter.FirstName", ""),
        ("Filter.OrgName", ""), ("Filter.LastName", ""),
        ("Filter.NameSoundsLike", "false"), ("Filter.SelectedState", ""),
        ("Filter.Purpose", ""), ("Filter.Profession", ""),
        ("Filter.ProfessionSoundsLike", "false"), ("Filter.ZipCodeList", ""),
        ("Filter.PaymentMethodSelected", ""), ("Filter.EmployerName", ""),
        ("Filter.EmployerSoundsLike", "false"),
        ("__RequestVerificationToken", token),
    ]


def north_carolina_spec(year: int, office: str) -> dict[str, object]:
    scope = {"calendar_year": year, "office_code": office, "transaction_types": "all"}
    return {
        "state": "NC", "provider": "North Carolina State Board of Elections",
        "url": "https://cf.ncsbe.gov/CFTxnLkup/Export",
        "name": f"transactions_v2/{year}/{office}.csv",
        "data_kind": "receipts_and_expenditures", "cycle": str(year),
        "authoritative_scope": (
            f"reported transactions dated in {year} for committees associated with "
            f"North Carolina office code {office}"
        ),
        "acquisition_method": "official_antiforgery_form_csv_export",
        "request_parameters": json.dumps(scope, sort_keys=True, separators=(",", ":")),
        "query_scope": f"year={year};office={office};committee_types=CNC,JNT",
        "expected_header": "Name,Street Line 1,Street Line 2,City,State,Zip Code",
        "notes": (
            "Raw official CSV export containing receipts and expenditures for "
            "candidate and joint-candidate committees only. Version 2 corrects "
            "the original form payload, which selected all committee types."
        ),
    }


def acquire_north_carolina(
    session: requests.Session, existing: dict[str, dict[str, str]], timeout: int,
    years: set[int], audit_only: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    manifest: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    search_url = "https://cf.ncsbe.gov/CFTxnLkup/AdvancedSearch/"
    search_post_url = "https://cf.ncsbe.gov/CFTxnLkup/AdvancedSearch"

    for year in sorted(years & set(SOURCE_YEARS)):
        for office in ("NCSN", "NSHS"):
            spec = north_carolina_spec(year, office)
            destination = RAW / "NC" / str(spec["name"])
            rel = relative(destination)
            if destination.exists():
                spec["record_count"] = count_delimited_records(destination)
                prior = existing.get(rel, {})
                retrieved_at = prior.get("retrieved_at") or datetime.fromtimestamp(
                    destination.stat().st_mtime, timezone.utc
                ).replace(microsecond=0).isoformat()
                manifest.append(
                    manifest_row(spec, destination, retrieved_at, prior.get("media_type", ""))
                )
                print(f"NC {year} {office}: {spec['record_count']} rows", flush=True)
                continue
            if audit_only:
                continue
            try:
                search_page = session.get(search_url, timeout=timeout)
                search_page.raise_for_status()
                soup = BeautifulSoup(search_page.text, "html.parser")
                token_node = soup.select_one('input[name="__RequestVerificationToken"]')
                if token_node is None:
                    raise RuntimeError("search page did not contain an antiforgery token")
                search_response = session.post(
                    search_post_url,
                    data=north_carolina_search_payload(year, office, token_node["value"]),
                    timeout=timeout,
                )
                search_response.raise_for_status()
                result_soup = BeautifulSoup(search_response.text, "html.parser")
                grid = result_soup.select_one("#divGrid")
                export_form = result_soup.select_one("#frmExport")
                export_token = (
                    export_form.select_one('input[name="__RequestVerificationToken"]')
                    if export_form else None
                )
                if grid is None or export_token is None:
                    raise RuntimeError("result page did not expose export parameters")
                export_response = session.post(
                    str(spec["url"]),
                    data={
                        "searchParamsJson": grid.get("data-search-params", ""),
                        "__RequestVerificationToken": export_token["value"],
                    },
                    timeout=timeout, stream=True,
                )
                export_response.raise_for_status()
                destination.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(
                    prefix=f".{destination.name}.", suffix=".part", dir=destination.parent
                )
                try:
                    with os.fdopen(fd, "wb") as handle:
                        for block in export_response.iter_content(1024 * 1024):
                            if block:
                                handle.write(block)
                    temp_path = Path(temp_name)
                    with temp_path.open("rb") as check:
                        first_line = check.readline().decode("utf-8-sig", errors="replace").strip()
                    if not first_line.startswith(str(spec["expected_header"])):
                        raise RuntimeError(f"unexpected CSV header: {first_line[:160]}")
                    spec["record_count"] = count_delimited_records(temp_path)
                    if destination.exists():
                        raise RuntimeError(f"refusing to overwrite raw evidence: {destination}")
                    temp_path.replace(destination)
                finally:
                    if Path(temp_name).exists():
                        Path(temp_name).unlink()
                manifest.append(
                    manifest_row(
                        spec, destination, utc_now(),
                        export_response.headers.get("content-type", ""),
                    )
                )
                print(f"NC {year} {office}: {spec['record_count']} rows", flush=True)
            except Exception as exc:
                failures.append({
                    "state": "NC", "data_kind": spec["data_kind"],
                    "source_url": spec["url"], "access_class": "form_query_export",
                    "reason": f"query_failed ({year} {office}): {exc}",
                    "next_action": "retry_or_review_provider_response",
                })
                print(f"FAILED NC {year} {office}: {exc}", flush=True)
    return manifest, failures


def tennessee_search_payload(kind: str, year: int) -> list[tuple[str, str]]:
    common = [
        ("searchType", kind), ("toType", "candidate"),
        ("electionYearSelection", ""), ("yearSelection", str(year)),
        ("typeOf", "all"), ("amountSelection", "equal"),
        ("amountDollars", ""), ("amountCents", ""),
        ("typeField", "true"), ("adjustmentField", "true"),
        ("amountField", "true"), ("dateField", "true"),
        ("electionYearField", "true"), ("reportNameField", "true"),
    ]
    if kind == "contributions":
        common.extend([
            ("fromCandidate", "true"), ("fromPAC", "true"),
            ("fromIndividual", "true"), ("fromOrganization", "true"),
            ("recipientName", ""), ("contributorName", ""), ("employer", ""),
            ("occupation", ""), ("zipCode", ""),
            ("recipientNameField", "true"), ("contributorNameField", "true"),
            ("contributorAddressField", "true"),
            ("contributorOccupationField", "true"),
            ("contributorEmployerField", "true"), ("descriptionField", "true"),
        ])
    else:
        common.extend([
            ("toCandidate", "true"), ("toPac", "true"), ("toOther", "true"),
            ("candName", ""), ("vendorName", ""), ("vendorZipCode", ""),
            ("purpose", ""), ("candidatePACNameField", "true"),
            ("vendorNameField", "true"), ("vendorAddressField", "true"),
            ("purposeField", "true"), ("candidateForField", "true"),
            ("soField", "true"),
        ])
    common.append(("_continue", "Search"))
    return common


def tennessee_spec(kind: str, year: int) -> dict[str, object]:
    scope = {"report_year": year, "filer_type": "candidate", "transaction_type": kind}
    return {
        "state": "TN", "provider": "Tennessee Registry of Election Finance",
        "url": "https://apps.tn.gov/tncamp/public/cesearch.htm",
        "name": f"{kind}/{year}.csv", "data_kind": kind, "cycle": str(year),
        "authoritative_scope": f"reported candidate {kind} in report year {year}",
        "acquisition_method": "official_session_form_csv_export",
        "request_parameters": json.dumps(scope, sort_keys=True, separators=(",", ":")),
        "query_scope": f"year={year};kind={kind}",
        "expected_header": (
            "Type,Adj,Amount,Date,Election Year,Report Name,Recipient Name"
            if kind == "contributions"
            else "Type,Adj,Amount,Date,Election Year,Report Name,Candidate/PAC Name"
        ),
        "notes": "Raw official candidate transaction CSV export; ISO-8859-1 response.",
    }


def acquire_tennessee(
    session: requests.Session, existing: dict[str, dict[str, str]], timeout: int,
    years: set[int], audit_only: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    from urllib.parse import urljoin

    manifest: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    search_url = "https://apps.tn.gov/tncamp/public/cesearch.htm"
    for year in sorted(years & set(SOURCE_YEARS)):
        for kind in ("contributions", "expenditures"):
            spec = tennessee_spec(kind, year)
            destination = RAW / "TN" / str(spec["name"])
            rel = relative(destination)
            if destination.exists():
                spec["record_count"] = count_delimited_records(destination)
                prior = existing.get(rel, {})
                retrieved_at = prior.get("retrieved_at") or datetime.fromtimestamp(
                    destination.stat().st_mtime, timezone.utc
                ).replace(microsecond=0).isoformat()
                manifest.append(
                    manifest_row(spec, destination, retrieved_at, prior.get("media_type", ""))
                )
                print(f"TN {kind} {year}: {spec['record_count']} rows", flush=True)
                continue
            if audit_only:
                continue
            try:
                landing = session.get(search_url, timeout=timeout)
                landing.raise_for_status()
                results = session.post(
                    search_url, data=tennessee_search_payload(kind, year), timeout=timeout
                )
                results.raise_for_status()
                soup = BeautifulSoup(results.text, "html.parser")
                csv_link = next(
                    (
                        node.get("href") for node in soup.find_all("a", href=True)
                        if node.get_text(" ", strip=True) == "CSV"
                    ),
                    None,
                )
                if not csv_link:
                    raise RuntimeError("results page did not expose a CSV export link")
                export_response = session.get(
                    urljoin(results.url, csv_link), timeout=timeout, stream=True
                )
                export_response.raise_for_status()
                destination.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(
                    prefix=f".{destination.name}.", suffix=".part", dir=destination.parent
                )
                try:
                    with os.fdopen(fd, "wb") as handle:
                        for block in export_response.iter_content(1024 * 1024):
                            if block:
                                handle.write(block)
                    temp_path = Path(temp_name)
                    with temp_path.open("rb") as check:
                        first_line = check.readline().decode("iso-8859-1", errors="replace").strip()
                    if not first_line.startswith(str(spec["expected_header"])):
                        raise RuntimeError(f"unexpected CSV header: {first_line[:160]}")
                    spec["record_count"] = count_delimited_records(temp_path)
                    if destination.exists():
                        raise RuntimeError(f"refusing to overwrite raw evidence: {destination}")
                    temp_path.replace(destination)
                finally:
                    if Path(temp_name).exists():
                        Path(temp_name).unlink()
                manifest.append(
                    manifest_row(
                        spec, destination, utc_now(),
                        export_response.headers.get("content-type", ""),
                    )
                )
                print(f"TN {kind} {year}: {spec['record_count']} rows", flush=True)
            except Exception as exc:
                failures.append({
                    "state": "TN", "data_kind": kind, "source_url": spec["url"],
                    "access_class": "form_query_export",
                    "reason": f"query_failed ({year} {kind}): {exc}",
                    "next_action": "retry_or_review_provider_response",
                })
                print(f"FAILED TN {kind} {year}: {exc}", flush=True)
    return manifest, failures


def georgia_spec(kind: str, year: int) -> dict[str, object]:
    if kind == "contributions":
        path = "Campaign_ByContributionsearchresults.aspx"
        params = {
            "Contributor": "", "Zip": "", "City": "", "ContTypeID": "0",
            "PAC": "", "Employer": "", "Occupation": "",
            "From": f"01/01/{year}", "To": f"12/31/{year}",
            "Cash": "", "InK": "", "Filer": "", "Candidate": "", "Committee": "",
        }
        extension = "csv"
        expected_header = "FilerID,Type,LastName,FirstName,Address,City,State,Zip"
    else:
        path = "campaign_ByExpendituresearchresults.aspx"
        params = {
            "Name": "", "ExpTypeID": "0", "OccEmp": "", "Purpose": "",
            "From": f"01/01/{year}", "To": f"12/31/{year}",
            "Item": "", "Paid": "", "Filer": "", "Candidate": "", "Committee": "",
        }
        extension = "xls"
        expected_header = "<table"
    url = f"https://media.ethics.ga.gov/search/Campaign/{path}?{urlencode(params)}"
    scope = {"calendar_year": year, "transaction_type": kind, "filer_scope": "statewide"}
    return {
        "state": "GA",
        "provider": "Georgia Government Transparency and Campaign Finance Commission",
        "url": url, "name": f"{kind}/{year}.{extension}", "data_kind": kind,
        "cycle": str(year),
        "authoritative_scope": f"reported statewide campaign-finance {kind} dated in {year}",
        "acquisition_method": "official_webforms_export",
        "request_parameters": json.dumps(scope, sort_keys=True, separators=(",", ":")),
        "query_scope": f"system=legacy;year={year};kind={kind}",
        "expected_header": expected_header,
        "notes": (
            "Raw official CSV export."
            if kind == "contributions"
            else "Raw official HTML-table XLS export; no format conversion applied."
        ),
    }


def acquire_georgia(
    session: requests.Session, existing: dict[str, dict[str, str]], timeout: int,
    years: set[int], audit_only: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    manifest: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for year in sorted(years & set(SOURCE_YEARS)):
        for kind in ("contributions", "expenditures"):
            spec = georgia_spec(kind, year)
            destination = RAW / "GA" / str(spec["name"])
            rel = relative(destination)
            if destination.exists():
                spec["record_count"] = (
                    count_delimited_records(destination)
                    if kind == "contributions"
                    else max(0, destination.read_bytes().lower().count(b"<tr") - 1)
                )
                prior = existing.get(rel, {})
                retrieved_at = prior.get("retrieved_at") or datetime.fromtimestamp(
                    destination.stat().st_mtime, timezone.utc
                ).replace(microsecond=0).isoformat()
                manifest.append(
                    manifest_row(spec, destination, retrieved_at, prior.get("media_type", ""))
                )
                print(f"GA {kind} {year}: {spec['record_count']} rows", flush=True)
                continue
            if audit_only:
                continue
            try:
                results = session.get(str(spec["url"]), timeout=timeout)
                results.raise_for_status()
                soup = BeautifulSoup(results.text, "html.parser")
                export_node = soup.select_one("#ctl00_ContentPlaceHolder1_Export")
                if export_node is None:
                    raise RuntimeError("results page did not expose an export control")
                payload = {
                    node.get("name"): node.get("value", "")
                    for node in soup.select('input[type="hidden"][name]')
                }
                payload["ctl00$ContentPlaceHolder1$Export.x"] = "1"
                payload["ctl00$ContentPlaceHolder1$Export.y"] = "1"
                export_response = session.post(
                    results.url, data=payload, timeout=timeout, stream=True
                )
                export_response.raise_for_status()
                destination.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(
                    prefix=f".{destination.name}.", suffix=".part", dir=destination.parent
                )
                try:
                    with os.fdopen(fd, "wb") as handle:
                        for block in export_response.iter_content(1024 * 1024):
                            if block:
                                handle.write(block)
                    temp_path = Path(temp_name)
                    with temp_path.open("rb") as check:
                        start = check.read(512).decode("utf-8-sig", errors="replace").lstrip()
                    if not start.startswith(str(spec["expected_header"])):
                        raise RuntimeError(f"unexpected export header: {start[:160]}")
                    spec["record_count"] = (
                        count_delimited_records(temp_path)
                        if kind == "contributions"
                        else max(0, temp_path.read_bytes().lower().count(b"<tr") - 1)
                    )
                    if destination.exists():
                        raise RuntimeError(f"refusing to overwrite raw evidence: {destination}")
                    temp_path.replace(destination)
                finally:
                    if Path(temp_name).exists():
                        Path(temp_name).unlink()
                manifest.append(
                    manifest_row(
                        spec, destination, utc_now(),
                        export_response.headers.get("content-type", ""),
                    )
                )
                print(f"GA {kind} {year}: {spec['record_count']} rows", flush=True)
            except Exception as exc:
                failures.append({
                    "state": "GA", "data_kind": kind, "source_url": spec["url"],
                    "access_class": "webforms_query_export",
                    "reason": f"query_failed ({year} {kind}): {exc}",
                    "next_action": "retry_or_review_provider_response",
                })
                print(f"FAILED GA {kind} {year}: {exc}", flush=True)
    return manifest, failures


def georgia_modern_filter(
    kind: str, year: int, month: int, day: int | None = None,
) -> dict[str, object]:
    last_day = calendar.monthrange(year, month)[1]
    date_from = f"{month:02d}/{day:02d}/{year}" if day else f"{month:02d}/01/{year}"
    date_to = f"{month:02d}/{day:02d}/{year}" if day else f"{month:02d}/{last_day:02d}/{year}"
    common: dict[str, object] = {
        "pageNumber": 1, "pageSize": 10, "sortBy": "Transaction Date",
        "sortType": "desc", "transactionTypeCode": "TCON" if kind == "contributions" else "TEXP",
        "committeeType": "CAN", "toDate": date_to, "fromDate": date_from,
    }
    if kind == "contributions":
        common.update({
            "filerName": "", "sourceName": "", "transactionAmountMax": None,
            "transactionAmountMin": None, "sourceTypeCode": "",
            "transactionSubTypeCode": "", "electionID": "", "reportName": "",
            "byState": "", "electionType": "", "electionYear": "",
            "filerRegistrationGuid": None,
        })
    else:
        common.update({
            "electionYear": "", "electionType": None,
            "searchedTransactionTypeCode": None, "filerName": "", "candidateName": "",
            "measure": "", "officeSought": "", "district": "",
            "transactionAmountMax": None, "sourceTypeCode": None,
            "electionID": None, "sourceName": "", "sourceAddress": "",
            "reportName": "", "purpose": None, "city": "", "state": "",
            "stance": "", "address": "", "transactionCategory": "",
        })
    return common


def georgia_modern_spec(
    kind: str, year: int, month: int, day: int | None = None,
) -> dict[str, object]:
    transaction_filter = georgia_modern_filter(kind, year, month, day)
    partition = f"{month:02d}_{day:02d}" if day else f"{month:02d}"
    path = f"{month:02d}/{day:02d}.csv" if day else f"{month:02d}.csv"
    payload = {
        "publicGridName": (
            "ContributionsPublicGrid" if kind == "contributions" else "ExpendituresPublicGrid"
        ),
        "transactionDetailsSearchFilter": transaction_filter,
        "fileName": f"{kind}_{year}_{partition}", "type": "CSV",
        "openInNewTab": False,
    }
    collection = "recordsearch_v2" if year == 2024 else "recordsearch"
    return {
        "state": "GA",
        "provider": "Georgia Government Transparency and Campaign Finance Commission",
        "url": (
            "https://api-recordsearch.ethics.ga.gov/api/"
            "PublicGridDownload/DownloadPublicGridData"
        ),
        "name": f"{collection}/{kind}/{year}/{path}",
        "data_kind": kind, "cycle": str(year),
        "authoritative_scope": (
            f"reported candidate {kind} dated in {year}-{month:02d} in the "
            "official 2022-2025 Record Search system"
        ),
        "acquisition_method": "official_partitioned_public_grid_export",
        "request_parameters": json.dumps(payload, sort_keys=True, separators=(",", ":")),
        "query_scope": (
            f"system=recordsearch;year={year};month={month:02d};"
            f"day={day:02d};kind={kind}" if day else
            f"system=recordsearch;year={year};month={month:02d};kind={kind}"
        ),
        "payload": payload,
        "expected_title": (
            "Contribution Download as of" if kind == "contributions"
            else "Expenditure Download as of"
        ),
        "expected_header": (
            "Filing Entity Id,Candidate Last Name,Candidate First Name"
            if kind == "contributions"
            else "Transaction Id,Filing Entity Id,Candidate Last Name"
        ),
        "notes": (
            "Raw official candidate CSV export partitioned by transaction month. "
            "The version-2 collection preserves a refreshed replacement for the "
            "provider's defective first 2024 response set."
        ),
    }


def acquire_georgia_modern(
    session: requests.Session, existing: dict[str, dict[str, str]], timeout: int,
    years: set[int], audit_only: bool, kinds: tuple[str, ...] = ("contributions", "expenditures"),
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    manifest: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://recordsearch.ethics.ga.gov",
        "Referer": "https://recordsearch.ethics.ga.gov/",
    }

    def acquire_days(kind: str, year: int, month: int) -> None:
        child_days = range(1, calendar.monthrange(year, month)[1] + 1)
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(
                lambda child_day: acquire_period(kind, year, month, child_day),
                child_days,
            ))

    def acquire_period(kind: str, year: int, month: int, day: int | None = None) -> None:
        spec = georgia_modern_spec(kind, year, month, day)
        destination = RAW / "GA" / str(spec["name"])
        rel = relative(destination)
        label = f"{year}-{month:02d}" + (f"-{day:02d}" if day else "")
        if destination.exists():
            spec["record_count"] = max(0, count_delimited_records(destination) - 1)
            prior = existing.get(rel, {})
            retrieved_at = prior.get("retrieved_at") or datetime.fromtimestamp(
                destination.stat().st_mtime, timezone.utc
            ).replace(microsecond=0).isoformat()
            manifest.append(
                manifest_row(spec, destination, retrieved_at, prior.get("media_type", ""))
            )
            print(f"GA recordsearch {kind} {label}: {spec['record_count']} rows", flush=True)
            return
        if audit_only:
            return
        try:
            response = session.post(
                str(spec["url"]), json=spec["payload"], headers=headers,
                timeout=timeout, stream=True,
            )
            response.raise_for_status()
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".part", dir=destination.parent
            )
            try:
                with os.fdopen(fd, "wb") as handle:
                    for block in response.iter_content(1024 * 1024):
                        if block:
                            handle.write(block)
                temp_path = Path(temp_name)
                with temp_path.open("r", encoding="utf-8-sig", errors="replace") as check:
                    title = check.readline().strip()
                    header = check.readline().strip()
                if not title.startswith(str(spec["expected_title"])):
                    raise RuntimeError(f"unexpected export title: {title[:160]}")
                if not header.startswith(str(spec["expected_header"])):
                    raise RuntimeError(f"unexpected CSV header: {header[:160]}")
                spec["record_count"] = max(0, count_delimited_records(temp_path) - 1)
                if destination.exists():
                    raise RuntimeError(f"refusing to overwrite raw evidence: {destination}")
                temp_path.replace(destination)
            finally:
                if Path(temp_name).exists():
                    Path(temp_name).unlink()
            manifest.append(
                manifest_row(
                    spec, destination, utc_now(), response.headers.get("content-type", ""),
                )
            )
            print(f"GA recordsearch {kind} {label}: {spec['record_count']} rows", flush=True)
        except requests.HTTPError as exc:
            if day is None and exc.response is not None and exc.response.status_code == 504:
                print(f"GA recordsearch {kind} {label}: splitting gateway-limited month", flush=True)
                acquire_days(kind, year, month)
                return
            failures.append({
                "state": "GA", "data_kind": kind, "source_url": spec["url"],
                "access_class": "hybrid_query_export",
                "reason": f"recordsearch_query_failed ({label} {kind}): {exc}",
                "next_action": "retry_or_review_provider_response",
            })
            print(f"FAILED GA recordsearch {kind} {label}: {exc}", flush=True)
        except Exception as exc:
            failures.append({
                "state": "GA", "data_kind": kind, "source_url": spec["url"],
                "access_class": "hybrid_query_export",
                "reason": f"recordsearch_query_failed ({label} {kind}): {exc}",
                "next_action": "retry_or_review_provider_response",
            })
            print(f"FAILED GA recordsearch {kind} {label}: {exc}", flush=True)

    for year in sorted(years & {2022, 2023, 2024}):
        for kind in kinds:
            for month in range(1, 13):
                month_path = RAW / "GA" / str(
                    georgia_modern_spec(kind, year, month)["name"]
                )
                days = range(1, calendar.monthrange(year, month)[1] + 1)
                daily_paths = [
                    RAW / "GA" / str(
                        georgia_modern_spec(kind, year, month, day)["name"]
                    )
                    for day in days
                ]
                if not month_path.exists() and all(path.exists() for path in daily_paths):
                    for day in days:
                        acquire_period(kind, year, month, day)
                else:
                    acquire_period(kind, year, month)
    return manifest, failures


def candidate_universe_counts() -> dict[str, int]:
    if not PANEL_PATH.exists():
        return {}
    panel = pd.read_csv(PANEL_PATH, usecols=["state", "year", "dem_candidate", "rep_candidate"], low_memory=False)
    panel = panel[pd.to_numeric(panel.year, errors="coerce").between(2016, 2024)]
    counts: dict[str, int] = {}
    for state, group in panel.groupby("state"):
        names = pd.concat([group.dem_candidate, group.rep_candidate], ignore_index=True).dropna()
        counts[str(state)] = int(names.astype(str).str.strip().replace("", pd.NA).dropna().nunique())
    return counts


def florida_query_coverage(manifest: list[dict[str, object]]) -> tuple[int, int]:
    rows: dict[tuple[str, str, str, str], str] = {}
    date_rows: dict[tuple[str, str, str, str, str], str] = {}
    for row in manifest:
        if row.get("state_code") != "FL" or not row.get("query_scope"):
            continue
        scope = dict(
            item.split("=", 1) for item in str(row["query_scope"]).split(";") if "=" in item
        )
        key = (
            str(scope.get("year", "")), str(scope.get("office", "")),
            str(row.get("data_kind", "")), str(scope.get("surname_prefix", "")),
        )
        date_partition = str(scope.get("date_partition", ""))
        if date_partition:
            date_rows[key + (date_partition,)] = str(row.get("ingest_status", ""))
        else:
            rows[key] = str(row.get("ingest_status", ""))

    def date_partition_complete(
        year: int, office: str, kind: str, prefix: str, calendar_year: int,
    ) -> bool:
        base = (str(year), office, kind, prefix)
        year_status = date_rows.get(base + (f"year_{calendar_year}",), "")
        if year_status == "acquired_unparsed":
            return True
        if year_status != "acquired_truncated":
            return False
        for month in range(1, 13):
            month_status = date_rows.get(
                base + (f"month_{calendar_year}_{month:02d}",), ""
            )
            if month_status == "acquired_unparsed":
                continue
            if month_status != "acquired_truncated":
                return False
            last_day = calendar.monthrange(calendar_year, month)[1]
            if not all(
                date_rows.get(
                    base + (f"day_{date(calendar_year, month, day).isoformat()}",), ""
                ) == "acquired_unparsed"
                for day in range(1, last_day + 1)
            ):
                return False
        return True

    def prefix_complete(year: int, office: str, kind: str, prefix: str) -> bool:
        status = rows.get((str(year), office, kind, prefix), "")
        if status == "acquired_unparsed":
            return True
        if status != "acquired_truncated":
            return False
        if len(prefix) < 3:
            return all(
                prefix_complete(year, office, kind, prefix + suffix)
                for suffix in string.ascii_uppercase
            )
        return all(
            date_partition_complete(year, office, kind, prefix, calendar_year)
            for calendar_year in range(
                FLORIDA_DATABASE_START_YEAR, datetime.now().year + 1
            )
        )

    expected_dimensions = len(FLORIDA_ELECTIONS) * len(FLORIDA_OFFICES) * 2
    complete_dimensions = sum(
        all(prefix_complete(year, office, kind, prefix) for prefix in string.ascii_uppercase)
        for year in FLORIDA_ELECTIONS
        for office in FLORIDA_OFFICES
        for kind in ("contributions", "expenditures")
    )
    return complete_dimensions, expected_dimensions


def north_carolina_query_coverage(manifest: list[dict[str, object]]) -> tuple[int, int]:
    scopes = {
        str(row.get("query_scope", ""))
        for row in manifest
        if row.get("state_code") == "NC" and row.get("ingest_status") == "acquired_unparsed"
    }
    expected = {
        f"year={year};office={office};committee_types=CNC,JNT"
        for year in TARGET_YEARS
        for office in ("NCSN", "NSHS")
    }
    return len(scopes & expected), len(expected)


def tennessee_query_coverage(manifest: list[dict[str, object]]) -> tuple[int, int]:
    scopes = {
        str(row.get("query_scope", ""))
        for row in manifest
        if row.get("state_code") == "TN" and row.get("ingest_status") == "acquired_unparsed"
    }
    expected = {
        f"year={year};kind={kind}"
        for year in TARGET_YEARS
        for kind in ("contributions", "expenditures")
    }
    return len(scopes & expected), len(expected)


def georgia_query_coverage(manifest: list[dict[str, object]]) -> tuple[int, int]:
    scopes = {
        str(row.get("query_scope", ""))
        for row in manifest
        if row.get("state_code") == "GA" and row.get("ingest_status") == "acquired_unparsed"
    }
    legacy_expected = {
        f"system=legacy;year={year};kind={kind}"
        for year in range(2016, 2022)
        for kind in ("contributions", "expenditures")
    }
    complete = len(scopes & legacy_expected)
    modern_expected = 3 * 12 * 2
    for year in (2022, 2023, 2024):
        for month in range(1, 13):
            for kind in ("contributions", "expenditures"):
                month_scope = (
                    f"system=recordsearch;year={year};month={month:02d};kind={kind}"
                )
                if month_scope in scopes:
                    complete += 1
                    continue
                if all(
                    (
                        f"system=recordsearch;year={year};month={month:02d};"
                        f"day={day:02d};kind={kind}"
                    ) in scopes
                    for day in range(1, calendar.monthrange(year, month)[1] + 1)
                ):
                    complete += 1
    return complete, len(legacy_expected) + modern_expected


def georgia_recordsearch_anomalies(
    manifest: list[dict[str, object]],
) -> list[str]:
    """Flag implausibly empty statewide election-year responses for review."""
    nonempty_months = {kind: set() for kind in ("contributions", "expenditures")}
    for row in manifest:
        if row.get("state_code") != "GA":
            continue
        scope = {
            key: value
            for key, value in (
                item.split("=", 1)
                for item in str(row.get("query_scope", "")).split(";")
                if "=" in item
            )
        }
        if scope.get("system") != "recordsearch" or scope.get("year") != "2024":
            continue
        kind = str(scope.get("kind", ""))
        try:
            record_count = int(float(str(row.get("record_count", "0") or "0")))
        except ValueError:
            record_count = 0
        if kind in nonempty_months and record_count > 0:
            nonempty_months[kind].add(str(scope.get("month", "")))
    anomalies = []
    for kind, months in nonempty_months.items():
        if len(months) < 2:
            anomalies.append(
                f"Georgia Record Search 2024 {kind} responses are nonempty in "
                f"only {len(months)} month(s); do not treat retrieval coverage "
                "as transaction completeness"
            )
    return anomalies


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_coverage(manifest: list[dict[str, object]], failures: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    counts = candidate_universe_counts()
    coverage: list[dict[str, object]] = []
    unresolved = list(failures)
    direct_by_state = {
        state: [spec for spec in DIRECT_FILES if spec["state"] == state]
        for state in {str(spec["state"]) for spec in DIRECT_FILES}
    }
    manifest_by_state = {
        state: [row for row in manifest if row["state_code"] == state]
        for state in {source.state for source in SOURCES}
    }
    florida_complete_dimensions, florida_expected_dimensions = florida_query_coverage(manifest)
    nc_complete_dimensions, nc_expected_dimensions = north_carolina_query_coverage(manifest)
    tn_complete_dimensions, tn_expected_dimensions = tennessee_query_coverage(manifest)
    ga_complete_dimensions, ga_expected_dimensions = georgia_query_coverage(manifest)
    ga_anomalies = georgia_recordsearch_anomalies(manifest)
    for source in SOURCES:
        expected = len(direct_by_state.get(source.state, []))
        acquired = len(manifest_by_state.get(source.state, []))
        if source.access_class == "existing_upstream":
            status = "existing_not_reacquired"
        elif source.access_class == "direct_bulk":
            status = "complete_raw_bulk" if acquired == expected and expected else "direct_bulk_incomplete"
        elif source.access_class == "partial_bulk_api":
            status = "partial_raw_bulk" if acquired == expected and expected else "partial_bulk_incomplete"
        elif source.access_class == "partitioned_query_export":
            status = (
                "complete_raw_candidate_queries"
                if florida_complete_dimensions == florida_expected_dimensions
                else "partitioned_query_incomplete"
            )
        elif source.access_class == "form_query_export":
            complete_dimensions, expected_dimensions = (
                (nc_complete_dimensions, nc_expected_dimensions)
                if source.state == "NC"
                else (tn_complete_dimensions, tn_expected_dimensions)
            )
            status = (
                "complete_raw_candidate_queries"
                if complete_dimensions == expected_dimensions
                else "form_query_incomplete"
            )
        elif source.access_class == "hybrid_query_export":
            status = (
                "complete_raw_candidate_queries"
                if ga_complete_dimensions == ga_expected_dimensions and not ga_anomalies
                else "hybrid_query_provider_anomaly"
                if ga_complete_dimensions == ga_expected_dimensions
                else "hybrid_query_incomplete"
            )
        elif source.access_class == "annual_query_api":
            status = (
                "complete_raw_statewide_queries"
                if acquired == expected and expected else "annual_query_incomplete"
            )
        elif source.access_class == "unconfigured":
            status = "unconfigured"
        else:
            status = "adapter_required"
        coverage.append({
            "state": source.state, "provider": source.provider, "portal_url": source.portal_url,
            "target_cycles": "2016-2024", "access_class": source.access_class,
            "data_categories": source.data_categories, "expected_direct_files": expected,
            "acquired_files": acquired,
            "acquired_bytes": sum(int(row["size_bytes"]) for row in manifest_by_state.get(source.state, [])),
            "acquisition_status": status, "candidate_universe_names": counts.get(source.state, 0),
            "candidate_universe_available": int(counts.get(source.state, 0) > 0),
            "limitation": source.limitation,
        })
        if status in {
            "adapter_required", "unconfigured", "partial_raw_bulk",
            "partial_bulk_incomplete", "partitioned_query_incomplete",
            "form_query_incomplete", "hybrid_query_incomplete",
            "hybrid_query_provider_anomaly", "annual_query_incomplete",
        }:
            provider_anomaly = (
                source.state == "GA" and status == "hybrid_query_provider_anomaly"
            )
            unresolved.append({
                "state": source.state, "data_kind": source.data_categories or "all",
                "source_url": source.portal_url, "access_class": source.access_class,
                "reason": (
                    "; ".join(ga_anomalies)
                    if provider_anomaly else
                    source.limitation or "state adapter not configured"
                ),
                "next_action": (
                    "reconcile_official_recordsearch_2024_or_acquire_report_exports"
                    if provider_anomaly else
                    "extract_and_validate_legacy_report_documents"
                    if source.access_class == "partial_bulk_api"
                    else "implement_and_validate_state_portal_adapter"
                    if source.portal_url else "identify_official_source"
                ),
            })
    return coverage, unresolved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", nargs="*", default=["AR", "FL", "GA", "LA", "NC", "OK", "SC", "TN"], help="Configured state codes to acquire")
    parser.add_argument(
        "--years", nargs="*", type=int, default=list(TARGET_YEARS),
        help="Calendar/election years for configured query adapters",
    )
    parser.add_argument("--audit-only", action="store_true", help="Write coverage without downloading files")
    parser.add_argument("--timeout", type=int, default=TIMEOUT)
    parser.add_argument(
        "--ga-kinds", nargs="*", choices=["contributions", "expenditures"],
        default=["contributions", "expenditures"],
        help="Georgia Record Search transaction classes to acquire",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requested = {state.upper() for state in args.states}
    unsupported = requested - {"AR", "FL", "GA", "LA", "NC", "OK", "SC", "TN"}
    if unsupported:
        raise SystemExit(f"No direct-bulk adapter for: {', '.join(sorted(unsupported))}")
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(
        total=4, connect=4, read=4, status=2, backoff_factor=0.75,
        status_forcelist=(429, 500, 502, 503),
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    existing = read_existing_manifest()
    manifest: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for spec in DIRECT_FILES:
        if spec["state"] not in requested:
            continue
        destination = RAW / str(spec["state"]) / str(spec["name"])
        if args.audit_only and not destination.exists():
            continue
        try:
            manifest.append(acquire_file(session, spec, existing, args.timeout))
            print(f"{spec['state']} {spec['data_kind']} {spec['cycle']}: {destination.name}", flush=True)
        except Exception as exc:
            failures.append({
                "state": spec["state"], "data_kind": spec["data_kind"], "source_url": spec["url"],
                "access_class": "direct_bulk", "reason": f"download_failed: {exc}",
                "next_action": "retry_or_review_provider_response",
            })
            print(f"FAILED {spec['state']} {spec['data_kind']} {spec['cycle']}: {exc}", flush=True)

    if "FL" in requested:
        if not args.audit_only:
            bootstrap_florida_session(session)
        florida_manifest, florida_failures = acquire_florida(
            session, existing, args.timeout, set(args.years), args.audit_only,
        )
        manifest.extend(florida_manifest)
        failures.extend(florida_failures)

    if "GA" in requested:
        ga_manifest, ga_failures = acquire_georgia(
            session, existing, args.timeout,
            set(args.years) & set(range(2015, 2022)), args.audit_only,
        )
        manifest.extend(ga_manifest)
        failures.extend(ga_failures)
        ga_modern_manifest, ga_modern_failures = acquire_georgia_modern(
            session, existing, args.timeout,
            set(args.years) & {2022, 2023, 2024}, args.audit_only,
            tuple(args.ga_kinds),
        )
        manifest.extend(ga_modern_manifest)
        failures.extend(ga_modern_failures)

    if "NC" in requested:
        nc_manifest, nc_failures = acquire_north_carolina(
            session, existing, args.timeout, set(args.years), args.audit_only,
        )
        manifest.extend(nc_manifest)
        failures.extend(nc_failures)

    if "TN" in requested:
        tn_manifest, tn_failures = acquire_tennessee(
            session, existing, args.timeout, set(args.years), args.audit_only,
        )
        manifest.extend(tn_manifest)
        failures.extend(tn_failures)

    # Preserve rows for already acquired direct files even when only one state
    # is requested on a subsequent run.
    for spec in DIRECT_FILES:
        destination = RAW / str(spec["state"]) / str(spec["name"])
        if destination.exists() and not any(row["local_path"] == relative(destination) for row in manifest):
            manifest.append(acquire_file(session, spec, existing, args.timeout))

    # Preserve previously acquired query artifacts when a later run targets a
    # different state. Their hashes and retrieval times remain unchanged.
    present = {str(row["local_path"]) for row in manifest}
    for local_path, row in existing.items():
        if local_path in present:
            continue
        if (ROOT / local_path).is_file():
            manifest.append(row)

    manifest.sort(key=lambda row: (str(row["state_code"]), str(row["cycle"]), str(row["data_kind"])))
    coverage, unresolved = build_coverage(manifest, failures)
    write_csv(MANIFEST_PATH, manifest, MANIFEST_FIELDS)
    write_csv(COVERAGE_PATH, coverage, [
        "state", "provider", "portal_url", "target_cycles", "access_class", "data_categories",
        "expected_direct_files", "acquired_files", "acquired_bytes", "acquisition_status",
        "candidate_universe_names", "candidate_universe_available", "limitation",
    ])
    write_csv(UNRESOLVED_PATH, unresolved, [
        "state", "data_kind", "source_url", "access_class", "reason", "next_action",
    ])
    print(f"Manifest files: {len(manifest)}; unresolved state/file rows: {len(unresolved)}")


if __name__ == "__main__":
    main()
