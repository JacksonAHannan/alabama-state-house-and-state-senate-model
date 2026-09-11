#!/usr/bin/env python3
"""Acquire official candidate/report summaries for Southern legislative races.

This is the preferred finance acquisition layer.  It targets the modeled
candidate-cycle universe and stores report summaries rather than transaction
ledgers.  Transaction data remains a reconciliation fallback only.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import html
import json
import os
import re
import tempfile
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from itertools import combinations, permutations
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pilot_fcpa_surname_search import all_financial_summaries, search as fcpa_search


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data/processed/war/southern_war_panel_v1/southern_war_panel.csv"
FINAL_CANDIDATES = (
    ROOT / "data/processed/elections/southern_legislative_final_candidate_history.csv.gz"
)
RAW = ROOT / "data/raw/finance/southern_summaries"
AUDIT = ROOT / "data/processed/source_audits"
MANIFEST = AUDIT / "southern_finance_summary_manifest.csv"
MATCH_AUDIT = AUDIT / "southern_finance_summary_candidate_matches.csv"
COVERAGE = AUDIT / "southern_finance_summary_coverage.csv"
FINANCE_IDENTITY_ADJUDICATIONS = (
    ROOT / "data/manual/finance/southern_finance_identity_adjudications.csv"
)
TARGET_MIN_YEAR = 2016
TARGET_MAX_YEAR = 2024
SC_DETAIL_SELECTION_VERSION = "v4"
SC_REPORT_LIST_URL = (
    "https://ethicsfiling.sc.gov/api/Candidate/Report/Public/Campaign/Get/Reports"
)
SC_REPORT_DETAIL_URL = (
    "https://ethicsfiling.sc.gov/api/Ethics/Get/Public/Candidate/Report/Details/{report_id}"
)
AR_CANDIDATE_SUMMARY_URL = (
    "https://api-ethics-disclosures.sos.arkansas.gov/api/"
    "PublicFilerDetails/GetCandidateCommitteDetails"
)
AR_LEGACY_REPORT_INDEX_URL = (
    "https://api-ethics-disclosures.sos.arkansas.gov/api/"
    "PublicLegacyFiledReport/GetPublicLegacyFiledReport"
)
AR_LEGACY_REPORT_DOWNLOAD_URL = (
    "https://api-ethics-disclosures.sos.arkansas.gov/api/"
    "PublicFiledReportAndDownload/LegacyDownloadDocument"
)
AR_ARCHIVE_SEARCH_URL = (
    "https://www.ark.org/sos-filing_search/index.php/filing/search/new"
)
AR_FOLLOWTHEMONEY_CANDIDATE_URL = (
    "https://www.followthemoney.org/aaengine/aafetch.php"
)
FL_CONTRIBUTION_SUMMARY_URL = (
    "https://dos.elections.myflorida.com/cgi-bin/contrib.exe"
)
FL_ELECTION_CODES = {
    2016: "20161108-GEN", 2018: "20181106-GEN", 2020: "20201103-GEN",
    2022: "20221108-GEN", 2024: "20241105-GEN",
}
FL_SPECIAL_ELECTION_CODES = {
    2018: [("20181106-S01", "senate")],
    2020: [("20201103-S01", "senate")],
    2024: [("20241105-S01", "senate"), ("20240116-S01", "house")],
}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/139.0.0.0 Safari/537.36"
)
KY_BASE = "https://secure.kentucky.gov/kref/publicsearch/"
KY_ELECTION_DATES = {
    2016: "11/8/2016", 2018: "11/6/2018", 2020: "11/3/2020",
    2022: "11/8/2022", 2024: "11/5/2024",
}
MS_SERVICE = (
    "https://cfportal.sos.ms.gov/online/Services/MS/"
    "CampaignFinanceServices.asmx"
)
MS_DETAIL = (
    "https://cfportal.sos.ms.gov/online/ViewXSLTFileByName.aspx?"
    "providerName=CF_CandidateDetails&EntityId={entity_id}"
)
MS_FILING = (
    "https://cfportal.sos.ms.gov/online/ExecuteWorkflow.aspx?"
    "WorkflowId=g729911d7-f399-46d6-a1ca-f15c1294f82d&FilingId={filing_id}"
)
MO_ELECTION_SEARCH = (
    "https://www.mec.mo.gov/MEC/Campaign_Finance/CF12_SearchElection.aspx"
)
VA_BASE = "https://cfreports.elections.virginia.gov/"
NC_BASE = "https://cf.ncsbe.gov/CFTxnLkup/"
TN_BASE = "https://apps.tn.gov/tncamp/"
TN_ELECTION_IDS = {2016: "213", 2018: "214", 2020: "221", 2022: "225", 2024: "230"}
GA_RECORDSEARCH_CANDIDATE_URL = (
    "https://api-recordsearch.ethics.ga.gov/api/"
    "PublicFilerDetails/GetCandidateDetails"
)
GA_LEGACY_CANDIDATE_SEARCH_URL = (
    "https://media.ethics.ga.gov/search/Campaign/"
    "Campaign_Namesearchresults.aspx"
)
GA_GIVEN_NAME_SEARCH_ALIASES = {
    "BEN": ("BENJAMIN",), "BETH": ("ELIZABETH",),
    "BETTY": ("ELIZABETH",), "BILL": ("WILLIAM",),
    "BOB": ("ROBERT",), "CHUCK": ("CHARLES",),
    "DOUG": ("DOUGLAS", "WILLIAM"), "EDDIE": ("EDWARD", "JAMES"),
    "GENE": ("EUGENE",), "GINNY": ("VIRGINIA",),
    "JEFF": ("JEFFERY", "JEFFREY"), "MARTY": ("MARTIN", "MAURICE"),
    "MIKE": ("MICHAEL",), "PAT": ("PATRICIA", "PATRICK"),
    "RANDY": ("RANDALL",), "RICK": ("RICHARD",),
    "RON": ("RONALD", "JAMES"), "SAM": ("SAMUEL",),
    "STEVE": ("STEVEN", "STEPHEN"), "TREY": ("WILLIAM", "ROBERT"),
}


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


def session_with_retries() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(
        total=4, connect=4, read=4, status=3, backoff_factor=0.75,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}), raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def write_immutable_bytes(path: Path, content: bytes) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".part", dir=path.parent
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        temp_path = Path(temp_name)
        if temp_path.stat().st_size == 0:
            raise RuntimeError(f"refusing to store empty artifact: {path}")
        if path.exists():
            raise RuntimeError(f"refusing to overwrite raw evidence: {path}")
        temp_path.replace(path)
    finally:
        if Path(temp_name).exists():
            Path(temp_name).unlink()


def strip_marks(value: object) -> str:
    # Some official result files preserve combining accents as HTML numeric
    # entities (for example ``JOSE&#769;``). Decode those entities before
    # Unicode normalization so the finance identity join sees the real name.
    text = unicodedata.normalize("NFKD", html.unescape(str(value or "")))
    return "".join(char for char in text if not unicodedata.combining(char))


def normalized_tokens(value: object) -> list[str]:
    text = strip_marks(value)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = text.upper()
    tokens = re.findall(r"[A-Z0-9]+", text)
    tokens = [
        token for token in tokens
        if token not in {"JR", "SR", "II", "III", "IV", "MR", "MRS", "MS", "DR"}
    ]
    # Camel-case normalization is useful for concatenated provider names, but
    # it also splits ordinary Mc/Mac surnames. Rejoin those surname prefixes.
    normalized = []
    index = 0
    while index < len(tokens):
        if tokens[index] in {"MC", "MAC"} and index + 1 < len(tokens):
            normalized.append(tokens[index] + tokens[index + 1])
            index += 2
        else:
            normalized.append(tokens[index])
            index += 1
    return normalized


def person_parts(value: object) -> tuple[str, str, str]:
    raw = strip_marks(value).strip()
    tokens = normalized_tokens(raw)
    if not tokens:
        return "", "", ""
    if "," in raw:
        left, right = raw.split(",", 1)
        # Election sources use both ``LAST, FIRST`` and natural-order names
        # followed by a suffix.  Treat the latter as natural order; otherwise
        # ``James A. Thomas, Jr.`` loses its given name and suppresses exact
        # committee discovery queries.
        right_raw_tokens = re.findall(r"[A-Z0-9]+", right.upper())
        suffix_only = bool(right_raw_tokens) and all(
            token in {"JR", "SR", "II", "III", "IV"}
            for token in right_raw_tokens
        )
        if suffix_only:
            ordered = normalized_tokens(left)
            first = ordered[0] if ordered else ""
            last = ordered[-1] if ordered else ""
        else:
            last_tokens = normalized_tokens(left)
            first_tokens = normalized_tokens(right)
            first = first_tokens[0] if first_tokens else ""
            last = last_tokens[-1] if last_tokens else ""
            ordered = first_tokens + last_tokens
    else:
        first, last, ordered = tokens[0], tokens[-1], tokens
    return first, last, " ".join(ordered)


def candidate_score(target: object, provider_name: object) -> float:
    target_first, target_last, target_ordered = person_parts(target)
    source_first, source_last, source_ordered = person_parts(provider_name)
    if not target_ordered or not source_ordered:
        return 0.0
    scores = [
        float(fuzz.token_set_ratio(target_ordered, source_ordered)),
        float(fuzz.ratio(target_ordered.replace(" ", ""), source_ordered.replace(" ", ""))),
    ]
    if target_last == source_last and target_last:
        scores.append(80.0 + 0.2 * fuzz.ratio(target_first, source_first))
    elif (
        len(target_last) >= 4 and len(source_last) >= 4
        and (target_last in source_last or source_last in target_last)
    ):
        scores.append(75.0 + 0.2 * fuzz.ratio(target_first, source_first))
    return min(100.0, max(scores))


IDENTITY_CONTEXT_STOPWORDS = {
    "CAMPAIGN", "CANDIDATE", "CITIZENS", "COMMITTEE", "COMM", "CMTE",
    "DISTRICT", "ELECT", "ELECTING", "ELECTION", "FOR", "FRIENDS", "FUND", "HOUSE", "IN",
    "NC", "NORTH", "OF", "REELECT", "REELECTING", "SENATE", "STATE",
    "THE", "TO", "VIRGINIA", "VA",
}

COMMON_GIVEN_NAME_GROUPS = (
    {"BEN", "BENJAMIN"}, {"BETH", "BETTY", "BETSY", "ELIZABETH"},
    {"BILL", "BILLY", "WILL", "WILLIAM"}, {"BOB", "BOBBY", "ROB", "ROBERT"},
    {"CHARLES", "CHUCK"}, {"CHRIS", "CHRISTOPHER"},
    {"CINDY", "CYNTHIA"},
    {"CLIFF", "CLIFTON"}, {"DOUG", "DOUGLAS"},
    {"ED", "EDDIE", "EDWARD"}, {"GENE", "EUGENE"},
    {"GINNY", "VIRGINIA"}, {"JEFF", "JEFFERY", "JEFFREY"},
    {"JOE", "JOSEPH"}, {"JIM", "JIMMY", "JAMES"},
    {"KEN", "KENNY", "KENNETH"},
    {"KATHY", "KATHERINE", "CATHERINE"}, {"MATT", "MATTHEW"},
    {"MELISSA", "MISSY"}, {"MIKE", "MICHAEL"},
    {"PAT", "PATRICIA"}, {"RANDALL", "RANDY"},
    {"RICH", "RICHARD", "RICK"}, {"RON", "RONALD"}, {"SAM", "SAMUEL"},
    {"STEVE", "STEVEN", "STEPHEN"}, {"TIM", "TIMOTHY"},
    {"TOM", "TOMMY", "THOMAS"}, {"DAVE", "DAVID"},
    {"BRITT", "BRITTANY", "BRITTNEY"},
)
COMMON_GIVEN_NAME_EQUIVALENTS = {
    name: group for group in COMMON_GIVEN_NAME_GROUPS for name in group
}


def plausible_concatenated_surname_fragments(value: object) -> set[str]:
    """Return conservative discovery fragments for a collapsed family name.

    Four-character minimum fragments are only used to retrieve official search
    candidates. Acceptance still requires the independent person-name score,
    legislative committee scope, and the normal 94-point threshold.
    """
    last = person_parts(value)[1]
    if len(last) < 7:
        return set()
    return {
        last[:index] for index in range(4, len(last) - 3)
    } | {
        last[index:] for index in range(3, len(last) - 3)
    }


def candidate_identity_score(
    target: object, provider_name: object, identity_context: object = "",
) -> float:
    """Score person-name evidence without treating committee boilerplate as a name.

    Election files commonly collapse a compound surname (``Carroll Foy`` to
    ``carrollfoy``), while committee names add phrases such as ``Friends of``
    or ``for NC House``.  This score rewards a compatible compound surname and
    independently observed given-name evidence.  A surname alone deliberately
    tops out at 90 so callers must add reciprocal/uniqueness evidence before
    accepting it.
    """
    raw_target = strip_marks(target).strip()
    target_tokens = normalized_tokens(raw_target)
    provider_tokens = normalized_tokens(provider_name)
    context_tokens = [
        token for token in normalized_tokens(identity_context)
        if token not in IDENTITY_CONTEXT_STOPWORDS and not token.isdigit()
    ]
    if not target_tokens or not provider_tokens:
        return 0.0

    if "," in raw_target:
        left, right = raw_target.split(",", 1)
        right_tokens = normalized_tokens(right)
        right_raw_tokens = re.findall(r"[A-Z0-9]+", right.upper())
        suffix_only = bool(right_raw_tokens) and all(
            token in {"JR", "SR", "II", "III", "IV"}
            for token in right_raw_tokens
        )
        if suffix_only:
            left_tokens = normalized_tokens(left)
            target_last = left_tokens[-1] if left_tokens else ""
            target_given = left_tokens[:-1]
        else:
            target_last = "".join(normalized_tokens(left))
            target_given = right_tokens
    else:
        target_last = target_tokens[-1]
        target_given = target_tokens[:-1]
    if not target_last:
        return 0.0

    source_tokens = [
        token for token in provider_tokens
        if token not in {"DELEGATE", "HONORABLE", "SENATOR"}
    ]
    combined_tokens = source_tokens + context_tokens
    surname_matches: list[tuple[tuple[int, ...], float]] = []
    indices = range(len(combined_tokens))
    for width in range(1, min(3, len(combined_tokens)) + 1):
        for selected_indices in combinations(indices, width):
            for ordered_indices in permutations(selected_indices):
                candidate_last = "".join(combined_tokens[index] for index in ordered_indices)
                ratio = float(fuzz.ratio(target_last, candidate_last))
                if ratio >= 92.0:
                    surname_matches.append((tuple(selected_indices), ratio))
    if not surname_matches:
        return 0.0
    surname_indices, surname_score = max(
        surname_matches, key=lambda item: (item[1], len(item[0]), -sum(item[0]))
    )

    source_given = [
        token for index, token in enumerate(combined_tokens)
        if index not in surname_indices
        and not (len(token) > 1 and token in target_last)
    ]
    target_words = {token for token in target_given if len(token) > 1}
    source_words = {token for token in source_given if len(token) > 1}
    context_words = {token for token in context_tokens if len(token) > 1}
    compound_given = any(
        target_word in {left + right, right + left}
        for target_word in target_words
        for left, right in combinations(source_words, 2)
    ) or any(
        source_word in {left + right, right + left}
        for source_word in source_words
        for left, right in combinations(target_words, 2)
    )
    exact_given = bool(target_words & source_words) or compound_given
    nickname_given = any(
        source_word in COMMON_GIVEN_NAME_EQUIVALENTS.get(target_word, set())
        for target_word in target_words
        for source_word in (source_words | context_words)
    )
    # Initial evidence must be positional and at least one side must actually
    # be an initial.  Merely sharing the first letter of two different full
    # names (Bob/Benjamin, Josh/John, Robert/Richard) is not person evidence.
    initial_evidence = any(
        target_token[0] == source_token[0]
        and (len(target_token) == 1 or len(source_token) == 1)
        for target_token, source_token in zip(target_given, source_given)
        if target_token and source_token
    )

    target_first = target_given[0] if target_given else ""
    provider_given = [
        token for index, token in enumerate(source_tokens)
        if index not in surname_indices
        and not (len(token) > 1 and token in target_last)
    ]
    provider_first = provider_given[0] if provider_given else ""
    first_exact = bool(
        target_first and provider_first and target_first == provider_first
    )
    middle_conflict = False
    if first_exact and len(target_given) > 1 and len(provider_given) > 1:
        target_middle = target_given[1]
        provider_middle = provider_given[1]
        middle_conflict = bool(
            target_middle and provider_middle
            and target_middle[0] != provider_middle[0]
        )
    nickname_or_other_given = bool(target_words & context_words)

    if surname_score >= 99.0 and first_exact:
        return 96.0 if middle_conflict else 100.0
    if surname_score >= 99.0 and (
        exact_given or nickname_given or nickname_or_other_given
    ):
        return 100.0
    if surname_score >= 99.0 and initial_evidence:
        return 96.0
    if surname_score >= 92.0 and exact_given:
        return 94.0
    if surname_score >= 99.0:
        return 90.0
    return 0.0


def candidate_universe(
    state: str | None = None, *, prefer_final_names: bool = False,
) -> pd.DataFrame:
    panel = pd.read_csv(PANEL, low_memory=False)
    panel = panel[pd.to_numeric(panel.year, errors="coerce").between(
        TARGET_MIN_YEAR, TARGET_MAX_YEAR
    )].copy()
    if state:
        panel = panel[panel.state.eq(state)]
    rows = []
    for row in panel.itertuples(index=False):
        for party, column in (("D", "dem_candidate"), ("R", "rep_candidate")):
            candidate = getattr(row, column)
            if pd.isna(candidate) or not str(candidate).strip():
                continue
            rows.append({
                "state": row.state, "cycle": int(row.year),
                "chamber": str(row.chamber).lower(), "district": int(row.district),
                "party": party, "candidate": str(candidate).strip(),
            })
    frame = pd.DataFrame(rows).drop_duplicates(
        ["state", "cycle", "chamber", "district", "party"]
    )
    if prefer_final_names and FINAL_CANDIDATES.exists() and not frame.empty:
        final = pd.read_csv(
            FINAL_CANDIDATES,
            compression="gzip",
            usecols=[
                "state_code", "cycle", "chamber", "district",
                "party_family", "candidate_name",
            ],
            low_memory=False,
        )
        final = final[
            final.cycle.between(TARGET_MIN_YEAR, TARGET_MAX_YEAR)
            & final.party_family.isin(["democratic", "republican"])
        ].copy()
        if state:
            final = final[final.state_code.eq(state)]
        final["state"] = final.state_code
        final["chamber"] = final.chamber.map({"lower": "house", "upper": "senate"})
        final["party"] = final.party_family.map(
            {"democratic": "D", "republican": "R"}
        )
        key = ["state", "cycle", "chamber", "district", "party"]
        unique = final.drop_duplicates(key, keep=False)[key + ["candidate_name"]]
        frame = frame.merge(unique, on=key, how="left", validate="one_to_one")
        frame["candidate"] = frame.candidate_name.fillna(frame.candidate)
        frame = frame.drop(columns="candidate_name")
    return frame.sort_values(
        ["state", "cycle", "chamber", "district", "party"]
    ).reset_index(drop=True)


def sc_office_parts(value: object) -> tuple[str | None, int | None]:
    match = re.match(
        r"^SC (House of Representatives District|Senate District)\s+(\d+)$",
        str(value or "").strip(), flags=re.I,
    )
    if not match:
        return None, None
    chamber = "house" if match.group(1).lower().startswith("house") else "senate"
    return chamber, int(match.group(2))


def sc_report_index(session: requests.Session, cycle: int, timeout: int) -> tuple[Path, list[dict]]:
    path = RAW / "SC" / f"{cycle}_campaign_report_index.json"
    if path.exists():
        return path, json.loads(path.read_text(encoding="utf-8-sig"))
    payload = {
        "candidate": "", "office": "", "reportType": "Any",
        "electionyear": cycle, "electionType": "Any",
    }
    response = session.post(SC_REPORT_LIST_URL, json=payload, timeout=timeout)
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise RuntimeError("South Carolina report index was not a JSON array")
    write_immutable_bytes(
        path, json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return path, rows


def match_sc_candidates(
    targets: pd.DataFrame, index_rows: list[dict], cycle: int,
) -> tuple[pd.DataFrame, dict[str, list[dict]]]:
    index = pd.DataFrame(index_rows)
    if index.empty:
        return pd.DataFrame(), {}
    parts = index.office.map(sc_office_parts)
    index["chamber"] = parts.map(lambda pair: pair[0])
    index["district"] = parts.map(lambda pair: pair[1])
    index = index[index.chamber.notna()].copy()
    # One person can have multiple campaign IDs, and in a few cases multiple
    # filer IDs, for the same legislative office.  Scoring those rows
    # separately creates a false zero margin between duplicate exact names.
    # Collapse only exact normalized provider identities within office/district;
    # genuinely different names remain separate candidates for review.
    index["provider_identity_name"] = index.candidateName.map(
        lambda value: " ".join(normalized_tokens(value))
    )
    index["provider_identity"] = index.apply(
        lambda row: (
            f"{row['chamber']}|{int(row['district'])}|"
            f"{row['provider_identity_name']}"
        ),
        axis=1,
    )
    campaigns: dict[str, list[dict]] = {
        str(identity): group.to_dict("records")
        for identity, group in index.groupby("provider_identity", dropna=False)
    }
    candidate_rows = index[[
        "provider_identity", "candidateName", "chamber", "district"
    ]].drop_duplicates("provider_identity")
    matches = []
    for target in targets[targets.cycle.eq(cycle)].itertuples(index=False):
        pool = candidate_rows[
            candidate_rows.chamber.eq(target.chamber)
            & candidate_rows.district.eq(target.district)
        ].copy()
        scored = []
        for source in pool.itertuples(index=False):
            identity_reports = campaigns[str(source.provider_identity)]
            filer_ids = sorted({
                int(row["candidateFilerId"]) for row in identity_reports
                if pd.notna(row.get("candidateFilerId"))
            })
            campaign_ids = sorted({
                str(row["campaignId"]) for row in identity_reports
                if pd.notna(row.get("campaignId"))
            })
            scored.append((
                candidate_score(target.candidate, source.candidateName),
                str(source.provider_identity), filer_ids, campaign_ids,
                str(source.candidateName).strip(),
            ))
        scored.sort(reverse=True)
        best = scored[0] if scored else (0.0, "", [], [], "")
        second = scored[1][0] if len(scored) > 1 else 0.0
        margin = float(best[0] - second)
        # The report index is already scoped to the exact election cycle,
        # legislative chamber, and district.  A score of 80 with a ten-point
        # margin safely accommodates legal-name/nickname pairs (Chip/Colonel,
        # Luke/William, etc.) while still rejecting competing filers.
        accepted = bool(
            best[1] and (
                (best[0] >= 80.0 and margin >= 10.0)
                or (best[0] == 100.0 and margin >= 4.0)
            )
        )
        matches.append({
            "state": "SC", "cycle": cycle, "chamber": target.chamber,
            "district": target.district, "party": target.party,
            "candidate": target.candidate,
            "provider_candidate": best[4] if best[1] else "",
            "provider_identity": best[1],
            "candidate_filer_id": "|".join(map(str, best[2])),
            "campaign_id": "|".join(best[3]),
            "match_score": best[0], "match_margin": margin,
            "candidates_considered": len(scored),
            "match_status": "accepted_automatic" if accepted else "review_required",
        })
    return pd.DataFrame(matches), campaigns


def report_name_years(value: object) -> set[int]:
    return {int(year) for year in re.findall(r"\b20\d{2}\b", str(value or ""))}


def select_sc_reports(
    matches: pd.DataFrame, campaigns: dict[str, list[dict]], cycle: int,
) -> list[dict]:
    selected = []
    start_year = cycle - 1
    for match in matches[matches.match_status.eq("accepted_automatic")].to_dict("records"):
        for report in campaigns.get(str(match["provider_identity"]), []):
            years = report_name_years(report.get("reportName"))
            updated_year = pd.to_datetime(
                report.get("lastUpdated"), errors="coerce"
            ).year
            in_named_window = bool(years & {start_year, cycle})
            generic_in_window = not years and start_year <= updated_year <= cycle + 1
            if not (in_named_window or generic_in_window):
                continue
            selected.append({**match, **report})
    unique = {}
    for row in selected:
        unique[int(row["reportId"])] = row
    return list(unique.values())


def acquire_sc_details(
    selected: list[dict], cycle: int, timeout: int, workers: int,
) -> tuple[Path, list[dict]]:
    path = RAW / "SC" / (
        f"{cycle}_matched_report_details_{SC_DETAIL_SELECTION_VERSION}.jsonl"
    )
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            return path, [json.loads(line) for line in handle if line.strip()]

    prior_by_report: dict[int, dict] = {}
    for prior_path in sorted((RAW / "SC").glob(
        f"{cycle}_matched_report_details_v*.jsonl"
    )):
        if prior_path == path:
            continue
        with prior_path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    item = json.loads(line)
                    prior_by_report[int(item["index"]["reportId"])] = item

    def fetch(row: dict) -> dict:
        report_id = int(row["reportId"])
        if report_id in prior_by_report:
            cached = prior_by_report[report_id]
            return {**cached, "index": row}
        session = session_with_retries()
        try:
            url = SC_REPORT_DETAIL_URL.format(report_id=int(row["reportId"]))
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            detail = response.json()
            if not isinstance(detail, dict) or "overview" not in detail:
                raise RuntimeError(f"invalid report detail {row['reportId']}")
            return {"source_url": url, "index": row, "detail": detail}
        finally:
            session.close()

    details = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, row): row for row in selected}
        for future in as_completed(futures):
            details.append(future.result())
    details.sort(key=lambda item: int(item["index"]["reportId"]))
    content = "".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
        for item in details
    ).encode("utf-8")
    write_immutable_bytes(path, content)
    return path, details


def manifest_row(
    path: Path, cycle: int, kind: str, source_url: str, record_count: int,
    request_parameters: dict,
) -> dict[str, object]:
    return {
        "source_file_id": f"finance-summary:sc:{cycle}:{kind}:{sha256(path)[:12]}",
        "state": "SC", "cycle": cycle, "data_kind": kind,
        "provider": "South Carolina State Ethics Commission",
        "source_url": source_url, "retrieved_at": datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        ).replace(microsecond=0).isoformat(),
        "sha256": sha256(path), "size_bytes": path.stat().st_size,
        "record_count": record_count, "local_path": relative(path),
        "request_parameters": json.dumps(
            request_parameters, sort_keys=True, separators=(",", ":")
        ),
        "authoritative_scope": (
            "official candidate campaign-report index" if kind == "report_index"
            else "official selected candidate campaign-report details and summary totals"
        ),
        "ingest_status": "acquired_unparsed",
        "license_or_terms": "official public records; reuse terms not stated",
    }


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def upsert_state_csv(path: Path, frame: pd.DataFrame, state: str) -> None:
    if path.exists():
        existing = pd.read_csv(path)
        if "state" in existing:
            existing = existing[~existing.state.eq(state)]
        frame = pd.concat([existing, frame], ignore_index=True, sort=False)
    if path == MANIFEST and not frame.empty:
        frame["state_code"] = frame.get("state_code", pd.Series(index=frame.index, dtype=object)).fillna(
            frame.get("state", "")
        )
        media_by_suffix = {
            ".html": "text/html", ".json": "application/json",
            ".jsonl": "application/x-ndjson", ".xml": "application/xml",
            ".pdf": "application/pdf", ".csv": "text/csv",
        }
        inferred_media = frame.get("local_path", pd.Series(index=frame.index, dtype=object)).map(
            lambda value: media_by_suffix.get(Path(str(value or "")).suffix.lower(), "application/octet-stream")
        )
        frame["media_type"] = frame.get("media_type", pd.Series(index=frame.index, dtype=object)).fillna(inferred_media)
        frame["geography_vintage"] = frame.get(
            "geography_vintage", pd.Series(index=frame.index, dtype=object)
        ).fillna("not_applicable_candidate_finance")
        frame = frame.drop_duplicates("source_file_id", keep="last")
    write_csv(path, frame)


def acquire_sc(timeout: int, workers: int) -> None:
    targets = candidate_universe("SC")
    session = session_with_retries()
    manifests = []
    match_frames = []
    coverage_rows = []
    try:
        for cycle in sorted(targets.cycle.unique()):
            index_path, index_rows = sc_report_index(session, int(cycle), timeout)
            matches, campaigns = match_sc_candidates(targets, index_rows, int(cycle))
            selected = select_sc_reports(matches, campaigns, int(cycle))
            details_path, details = acquire_sc_details(
                selected, int(cycle), timeout, workers
            )
            match_frames.append(matches)
            manifests.extend([
                manifest_row(
                    index_path, int(cycle), "report_index", SC_REPORT_LIST_URL,
                    len(index_rows), {
                        "candidate": "", "office": "", "reportType": "Any",
                        "electionyear": int(cycle), "electionType": "Any",
                    },
                ),
                manifest_row(
                    details_path, int(cycle), "matched_report_details",
                    SC_REPORT_DETAIL_URL, len(details),
                    {"selection": "accepted modeled candidate campaigns and cycle-window reports"},
                ),
            ])
            accepted = int(matches.match_status.eq("accepted_automatic").sum())
            coverage_rows.append({
                "state": "SC", "cycle": int(cycle), "target_candidates": len(matches),
                "matched_candidates": accepted,
                "match_coverage": accepted / len(matches) if len(matches) else 0.0,
                "selected_report_details": len(details),
                "acquisition_status": (
                    "complete_candidate_match" if accepted == len(matches)
                    else "candidate_match_review_required"
                ),
            })
            print(
                f"SC {cycle}: {accepted}/{len(matches)} candidates; "
                f"{len(details)} report summaries",
                flush=True,
            )
    finally:
        session.close()
    upsert_state_csv(MANIFEST, pd.DataFrame(manifests), "SC")
    upsert_state_csv(MATCH_AUDIT, pd.concat(match_frames, ignore_index=True), "SC")
    upsert_state_csv(COVERAGE, pd.DataFrame(coverage_rows), "SC")


def ar_candidate_summary_index(
    session: requests.Session, cycle: int, timeout: int,
) -> tuple[Path, list[dict], dict]:
    path = RAW / "AR" / f"{cycle}_candidate_financial_summary_index.json"
    payload = {
        "pageNumber": 1, "pageSize": 1000, "filerTypeCode": "CAN",
        "filerName": "", "politicalPartyCode": "", "OfficeSought": "",
        "totalRaisedMax": None, "totalRaisedMin": None,
        "totalSpentMax": None, "totalSpentMin": None,
        "balanceFundsMax": None, "balanceFundsMin": None,
        "accountStatus": "", "election": str(cycle),
        "transactionSourceTypeCode": None, "jurisdictionType": "",
        "jurisdiction": "",
    }
    if path.exists():
        envelope = json.loads(path.read_text(encoding="utf-8-sig"))
        return path, envelope["response"]["data"]["items"], envelope["request"]
    response = session.post(AR_CANDIDATE_SUMMARY_URL, json=payload, timeout=timeout)
    response.raise_for_status()
    body = response.json()
    if not body.get("succeeded") or not isinstance(body.get("data", {}).get("items"), list):
        raise RuntimeError("Arkansas candidate summary index had an unexpected response")
    envelope = {"request": payload, "response": body}
    write_immutable_bytes(
        path, json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return path, body["data"]["items"], payload


def ar_party(value: object) -> str | None:
    text = str(value or "").lower()
    if "democratic" in text:
        return "D"
    if "republican" in text:
        return "R"
    return None


def ar_provider_identity(row: pd.Series) -> str:
    first, last, _ = person_parts(row.get("filerName"))
    district = int(row["district"]) if pd.notna(row.get("district")) else ""
    return f"{row.get('chamber', '')}|{district}|{first} {last}|{row.get('party') or ''}"


def match_ar_candidates(
    targets: pd.DataFrame, index_rows: list[dict], cycle: int,
) -> pd.DataFrame:
    source = pd.DataFrame(index_rows)
    if source.empty:
        return pd.DataFrame()
    source = source[source.office.isin(["State Representative", "State Senate"])].copy()
    source["chamber"] = source.office.map(
        {"State Representative": "house", "State Senate": "senate"}
    )
    source["district"] = pd.to_numeric(source.officeDistrictName, errors="coerce")
    source["party"] = source.politicalParty.map(ar_party)
    source["provider_identity"] = source.apply(ar_provider_identity, axis=1)
    identities = source.drop_duplicates("provider_identity")
    matches = []
    for target in targets[targets.cycle.eq(cycle)].itertuples(index=False):
        pool = identities[
            identities.chamber.eq(target.chamber)
            & identities.district.eq(target.district)
            & identities.party.eq(target.party)
        ]
        scored = sorted(
            [
                (
                    candidate_score(target.candidate, row.filerName),
                    str(row.provider_identity), str(row.filerName).strip(),
                    str(row.filerEntityID), str(row.guid),
                )
                for row in pool.itertuples(index=False)
            ],
            reverse=True,
        )
        best = scored[0] if scored else (0.0, "", "", "", "")
        second = scored[1][0] if len(scored) > 1 else 0.0
        margin = float(best[0] - second)
        accepted = bool(best[1] and best[0] >= 88.0 and margin >= 4.0)
        matches.append({
            "state": "AR", "cycle": cycle, "chamber": target.chamber,
            "district": target.district, "party": target.party,
            "candidate": target.candidate, "provider_candidate": best[2],
            "provider_identity": best[1], "candidate_filer_id": best[3],
            "campaign_id": best[4], "match_score": best[0],
            "match_margin": margin, "candidates_considered": len(scored),
            "match_status": "accepted_automatic" if accepted else "review_required",
        })
    return pd.DataFrame(matches)


def ar_legacy_report_index(
    session: requests.Session, timeout: int,
) -> tuple[Path, list[dict], dict]:
    """Acquire the portal's complete public candidate legacy-report index."""
    path = RAW / "AR" / "legacy_candidate_report_index_v1.json"
    payload = {
        "pageNumber": 1, "pageSize": 50000, "sortBy": None, "sortType": None,
        "filerName": None, "filerTypeCode": "CAN", "filingEntityId": None,
        "reportType": None, "fileName": None, "officeType": None,
        "reportStatus": None, "filedDateFromDate": None,
        "filedDateToDate": None, "filedDate": None, "electionID": None,
        "registrationYear": None, "moduleName": "CF",
    }
    if path.exists():
        envelope = json.loads(path.read_text(encoding="utf-8-sig"))
        return path, envelope["response"]["data"]["items"], envelope["request"]
    response = session.post(AR_LEGACY_REPORT_INDEX_URL, json=payload, timeout=timeout)
    response.raise_for_status()
    body = response.json()
    items = body.get("data", {}).get("items")
    if not body.get("succeeded") or not isinstance(items, list):
        raise RuntimeError("Arkansas legacy report index had an unexpected response")
    if len(items) != body["data"].get("totalItems"):
        raise RuntimeError("Arkansas legacy report index was unexpectedly paginated")
    write_immutable_bytes(
        path, json.dumps(
            {"request": payload, "response": body}, ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
    )
    return path, items, payload


def ar_legacy_name_key(value: object) -> str:
    return " ".join(normalized_tokens(value))


def match_ar_legacy_candidates(
    targets: pd.DataFrame, index_rows: list[dict], cycles: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Match modeled candidates to unique legacy person identities.

    The portal commonly has multiple registrations for one person.  Scoring
    registrations independently creates false zero-margin ties, so candidates
    are compared with unique normalized person names first and the selected
    identity is then linked back to its latest usable report.
    """
    source = pd.DataFrame(index_rows)
    source["report_end"] = pd.to_datetime(source.reportEndDate, errors="coerce")
    source["filed_date"] = pd.to_datetime(source.filedDate, errors="coerce")
    source["cycle"] = source.report_end.dt.year
    source["chamber"] = source.officeType.map(
        {"State Representative": "house", "State Senate": "senate"}
    )
    source["provider_identity"] = source.filerName.map(ar_legacy_name_key)
    source = source[
        source.cycle.isin(cycles) & source.chamber.notna()
        & source.provider_identity.ne("")
    ].copy()
    identities = source.drop_duplicates(
        ["cycle", "chamber", "provider_identity"]
    )
    matches = []
    selections = []
    for target in targets[targets.cycle.isin(cycles)].itertuples(index=False):
        pool = identities[
            identities.cycle.eq(target.cycle)
            & identities.chamber.eq(target.chamber)
        ]
        scored = sorted(
            [
                (
                    candidate_identity_score(target.candidate, row.filerName),
                    str(row.provider_identity), str(row.filerName).strip(),
                )
                for row in pool.itertuples(index=False)
            ],
            reverse=True,
        )
        best = scored[0] if scored else (0.0, "", "")
        best_person = person_parts(best[2])[:2]
        second = next(
            (score for score, _, name in scored[1:]
             if person_parts(name)[:2] != best_person),
            0.0,
        )
        margin = float(best[0] - second)
        accepted = bool(
            best[1] and best[0] >= 94.0 and (margin >= 4.0 or best[0] >= 98.0)
        )
        match = {
            "state": "AR", "cycle": int(target.cycle),
            "chamber": target.chamber, "district": int(target.district),
            "party": target.party, "candidate": target.candidate,
            "provider_candidate": best[2], "provider_identity": best[1],
            "candidate_filer_id": "", "campaign_id": "",
            "match_score": best[0], "match_margin": margin,
            "candidates_considered": len(scored),
            "match_status": "accepted_automatic" if accepted else "review_required",
        }
        if accepted:
            reports = source[
                source.cycle.eq(target.cycle)
                & source.chamber.eq(target.chamber)
                & source.provider_identity.eq(best[1])
            ].copy()
            reports = reports[
                ~reports.fileName.fillna("").str.contains("carryover", case=False)
            ].copy()
            reports["final_rank"] = reports.fileName.fillna("").str.contains(
                "final", case=False
            ).astype(int)
            reports = reports.sort_values(
                ["report_end", "final_rank", "filed_date", "id"],
                ascending=[False, False, False, False],
            )
            if not reports.empty:
                selected = reports.iloc[0]
                match["candidate_filer_id"] = str(
                    int(selected.legacyFilerRegistrationID)
                )
                match["campaign_id"] = str(selected.filerReportGuid)
                selections.append({
                    **{key: match[key] for key in (
                        "state", "cycle", "chamber", "district", "party",
                        "candidate", "provider_candidate", "provider_identity",
                        "candidate_filer_id", "match_score", "match_margin",
                        "match_status",
                    )},
                    "source_system": "ethics_disclosures_legacy_api",
                    "report_id": str(selected.filerReportGuid),
                    "report_name": str(selected.fileName),
                    "report_type": str(selected.reportType),
                    "report_start": selected.reportStartDate,
                    "report_end": selected.reportEndDate,
                    "filed_date": selected.filedDate,
                })
        matches.append(match)
    return pd.DataFrame(matches), pd.DataFrame(selections)


def parse_ar_archive_search(content: bytes) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    rows = []
    for tr in soup.select("tr"):
        cells = tr.select("td")
        link = tr.select_one('a[href*="/filing/save_pdf/"]')
        if len(cells) < 5 or link is None:
            continue
        url = urljoin(AR_ARCHIVE_SEARCH_URL, link.get("href"))
        rows.append({
            "filer_name": cells[0].get_text(" ", strip=True),
            "cycle": cells[1].get_text(" ", strip=True),
            "filed_date": cells[2].get_text(" ", strip=True),
            "report_name": cells[3].get_text(" ", strip=True),
            "election_type": cells[4].get_text(" ", strip=True),
            "download_url": url,
            "report_id": url.rstrip("/").rsplit("/", 1)[-1],
        })
    return rows


def ar_archive_2016_selections(
    targets: pd.DataFrame, timeout: int, workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame, list[Path]]:
    """Search the predecessor archive for 2016 candidate reports."""
    targets = targets[targets.cycle.eq(2016)].copy()

    def search_target(target: dict) -> tuple[dict, Path, list[dict]]:
        _, last, _ = person_parts(target["candidate"])
        query = last.title()
        key = re.sub(r"[^a-z0-9]+", "_", (
            f"{target['chamber']}_{target['district']}_{target['party']}_"
            f"{target['candidate']}"
        ).lower()).strip("_")
        path = RAW / "AR" / "archive_2016_searches_v1" / f"{key}.html"
        if not path.exists():
            response = requests.post(
                AR_ARCHIVE_SEARCH_URL,
                data={"ccne": "ccne", "candidate_name": query,
                      "year": "2016", "search": "Search"},
                headers={"User-Agent": USER_AGENT}, timeout=timeout,
            )
            response.raise_for_status()
            write_immutable_bytes(path, response.content)
        return target, path, parse_ar_archive_search(path.read_bytes())

    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(search_target, target)
            for target in targets.to_dict("records")
        ]
        for future in as_completed(futures):
            results.append(future.result())

    matches = []
    selections = []
    search_paths = []
    for target, path, rows in results:
        search_paths.append(path)
        cycle_rows = [row for row in rows if str(row["cycle"]) == "2016"]
        identities = sorted({row["filer_name"] for row in cycle_rows})
        scored = sorted(
            [(candidate_identity_score(target["candidate"], name), name)
             for name in identities],
            reverse=True,
        )
        best = scored[0] if scored else (0.0, "")
        second = scored[1][0] if len(scored) > 1 else 0.0
        margin = float(best[0] - second)
        accepted = bool(
            best[1] and best[0] >= 94.0 and (margin >= 4.0 or best[0] >= 98.0)
        )
        candidate_rows = [row for row in cycle_rows if row["filer_name"] == best[1]]
        usable = [
            row for row in candidate_rows
            if "carryover" not in row["report_name"].lower()
            and pd.to_datetime(row["filed_date"], errors="coerce")
            <= pd.Timestamp("2016-12-31")
        ]
        for row in usable:
            row["date_value"] = pd.to_datetime(row["filed_date"], errors="coerce")
            row["general_rank"] = int(row["election_type"].lower() == "general")
            row["final_rank"] = int("final" in row["report_name"].lower())
        usable.sort(
            key=lambda row: (
                row["general_rank"], row["date_value"], row["final_rank"],
                int(row["report_id"]),
            ),
            reverse=True,
        )
        selected = usable[0] if accepted and usable else None
        match = {
            "state": "AR", "cycle": 2016, "chamber": target["chamber"],
            "district": int(target["district"]), "party": target["party"],
            "candidate": target["candidate"], "provider_candidate": best[1],
            "provider_identity": ar_legacy_name_key(best[1]),
            "candidate_filer_id": "",
            "campaign_id": selected["report_id"] if selected else "",
            "match_score": best[0], "match_margin": margin,
            "candidates_considered": len(scored),
            "match_status": "accepted_automatic" if selected else "review_required",
        }
        matches.append(match)
        if selected:
            selections.append({
                **{key: match[key] for key in (
                    "state", "cycle", "chamber", "district", "party",
                    "candidate", "provider_candidate", "provider_identity",
                    "candidate_filer_id", "match_score", "match_margin",
                    "match_status",
                )},
                "source_system": "ark_org_predecessor_archive",
                "report_id": selected["report_id"],
                "report_name": selected["report_name"],
                "report_type": selected["election_type"],
                "report_start": "", "report_end": "",
                "filed_date": selected["filed_date"],
                "download_url": selected["download_url"],
                "search_path": relative(path),
            })
    return pd.DataFrame(matches), pd.DataFrame(selections), search_paths


def acquire_ar_legacy_reports(
    targets: pd.DataFrame, timeout: int, workers: int,
) -> tuple[list[dict], pd.DataFrame, pd.DataFrame, list[dict]]:
    session = session_with_retries()
    try:
        index_path, index_rows, payload = ar_legacy_report_index(session, timeout)
    finally:
        session.close()
    api_matches, api_selections = match_ar_legacy_candidates(
        targets, index_rows, [2018, 2020, 2022]
    )
    archive_matches, archive_selections, search_paths = ar_archive_2016_selections(
        targets, timeout, workers
    )
    selections = pd.concat(
        [archive_selections, api_selections], ignore_index=True, sort=False
    )

    def download_report(item: dict) -> tuple[str, Path, str, str]:
        report_id = str(item["report_id"])
        path = RAW / "AR" / "selected_legacy_reports_v1" / f"{report_id}.pdf"
        invalid_path = path.with_suffix(".invalid_response")
        if not path.exists() and invalid_path.exists():
            download_url = item.get("download_url")
            return report_id, invalid_path, (
                str(download_url)
                if pd.notna(download_url) and str(download_url)
                else AR_LEGACY_REPORT_DOWNLOAD_URL
            ), "invalid_report_response_preserved"
        if not path.exists():
            if item["source_system"] == "ark_org_predecessor_archive":
                # The predecessor archive requires the search-session cookie
                # when resolving a displayed PDF link.
                archive_session = requests.Session()
                archive_session.headers.update({"User-Agent": USER_AGENT})
                archive_session.post(
                    AR_ARCHIVE_SEARCH_URL,
                    data={"ccne": "ccne",
                          "candidate_name": item["provider_candidate"],
                          "year": "2016", "search": "Search"},
                    timeout=timeout,
                ).raise_for_status()
                response = archive_session.get(item["download_url"], timeout=timeout)
                archive_session.close()
            else:
                response = requests.post(
                    AR_LEGACY_REPORT_DOWNLOAD_URL,
                    json={"filerReportGuid": report_id,
                          "fileName": item["report_name"],
                          "openInNewTab": False},
                    headers={"User-Agent": USER_AGENT}, timeout=timeout,
                )
            if response.status_code >= 400 or not response.content.startswith(b"%PDF"):
                evidence = response.content or json.dumps({
                    "http_status": response.status_code,
                    "report_id": report_id,
                }, separators=(",", ":")).encode("utf-8")
                write_immutable_bytes(invalid_path, evidence)
                download_url = item.get("download_url")
                return report_id, invalid_path, (
                    str(download_url)
                    if pd.notna(download_url) and str(download_url)
                    else AR_LEGACY_REPORT_DOWNLOAD_URL
                ), f"invalid_report_response_http_{response.status_code}"
            write_immutable_bytes(path, response.content)
        download_url = item.get("download_url")
        return report_id, path, (
            str(download_url) if pd.notna(download_url) and str(download_url)
            else AR_LEGACY_REPORT_DOWNLOAD_URL
        ), "downloaded_pdf"

    downloaded = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(download_report, item)
            for item in selections.to_dict("records")
        ]
        for future in as_completed(futures):
            report_id, path, url, status = future.result()
            downloaded[report_id] = (path, url, status)
    selections["local_path"] = selections.report_id.map(
        lambda report_id: relative(downloaded[str(report_id)][0])
    )
    selections["download_status"] = selections.report_id.map(
        lambda report_id: downloaded[str(report_id)][2]
    )
    selection_path = RAW / "AR" / "matched_legacy_candidate_reports_v2.jsonl"
    if not selection_path.exists():
        content = "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in selections.fillna("").to_dict("records")
        ).encode("utf-8")
        write_immutable_bytes(selection_path, content)

    manifests = [{
        "source_file_id": f"finance-summary:ar:legacy-index:{sha256(index_path)[:12]}",
        "state": "AR", "cycle": "2018-2022",
        "data_kind": "legacy_candidate_report_index",
        "provider": "Arkansas Secretary of State Financial Disclosure",
        "source_url": AR_LEGACY_REPORT_INDEX_URL,
        "retrieved_at": datetime.fromtimestamp(
            index_path.stat().st_mtime, timezone.utc
        ).replace(microsecond=0).isoformat(),
        "sha256": sha256(index_path), "size_bytes": index_path.stat().st_size,
        "record_count": len(index_rows), "local_path": relative(index_path),
        "request_parameters": json.dumps(payload, sort_keys=True, separators=(",", ":")),
        "authoritative_scope": "official public index of legacy candidate-filed reports",
        "ingest_status": "acquired_parsed",
        "license_or_terms": "official public records; reuse terms not stated",
    }]
    for path in search_paths:
        manifests.append({
            "source_file_id": f"finance-summary:ar:2016-search:{sha256(path)[:12]}",
            "state": "AR", "cycle": 2016,
            "data_kind": "legacy_candidate_report_search",
            "provider": "Arkansas Secretary of State predecessor filing archive",
            "source_url": AR_ARCHIVE_SEARCH_URL,
            "retrieved_at": datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc
            ).replace(microsecond=0).isoformat(),
            "sha256": sha256(path), "size_bytes": path.stat().st_size,
            "record_count": len(parse_ar_archive_search(path.read_bytes())),
            "local_path": relative(path), "request_parameters": "targeted surname search; year=2016",
            "authoritative_scope": "official predecessor archive candidate filing search",
            "ingest_status": "acquired_parsed",
            "license_or_terms": "official public records; reuse terms not stated",
        })
    for report_id, (path, url, status) in downloaded.items():
        manifests.append({
            "source_file_id": f"finance-summary:ar:report:{report_id}:{sha256(path)[:12]}",
            "state": "AR", "cycle": int(
                selections.loc[selections.report_id.astype(str).eq(report_id), "cycle"].iloc[0]
            ),
            "data_kind": (
                "selected_candidate_finance_report_pdf"
                if status == "downloaded_pdf" else "invalid_report_download_response"
            ),
            "provider": "Arkansas Secretary of State",
            "source_url": url,
            "retrieved_at": datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc
            ).replace(microsecond=0).isoformat(),
            "sha256": sha256(path), "size_bytes": path.stat().st_size,
            "record_count": 1, "local_path": relative(path),
            "request_parameters": f"report_id={report_id}",
            "authoritative_scope": "official candidate campaign-finance report selected for cumulative cycle totals",
            "ingest_status": (
                "acquired_unparsed" if status == "downloaded_pdf"
                else "acquired_review_required"
            ),
            "license_or_terms": "official public records; reuse terms not stated",
        })
    return manifests, pd.concat(
        [archive_matches, api_matches], ignore_index=True, sort=False
    ), selections, index_rows


def parse_ar_followthemoney_candidates(content: bytes) -> list[dict]:
    """Parse the public candidate-cycle totals table from FollowTheMoney."""
    soup = BeautifulSoup(content, "html.parser")
    rows = []
    for tr in soup.select("tbody tr"):
        cells = tr.select("td")
        if len(cells) < 13:
            continue
        token = lambda name: tr.select_one(f'td[token="{name}"]')
        candidate_cell = token("c-t-id")
        party_cell = token("c-t-p")
        office_cell = token("c-r-osid")
        year_cell = token("y")
        if not all((candidate_cell, party_cell, office_cell, year_cell)):
            continue
        total_text = cells[-1].get_text(" ", strip=True)
        total_match = re.search(r"-?\$?([\d,]+(?:\.\d{2})?)", total_text)
        candidate_link = candidate_cell.select_one('[token="c-t-eid"]')
        rows.append({
            "candidate": candidate_cell.get_text(" ", strip=True),
            "candidate_id": candidate_cell.get("tokenvalue", ""),
            "entity_id": candidate_link.get("tokenvalue", "") if candidate_link else "",
            "party": party_cell.get_text(" ", strip=True),
            "office": office_cell.get_text(" ", strip=True),
            "cycle": int(year_cell.get_text(" ", strip=True)),
            "record_count": int(cells[-2].get_text(" ", strip=True).replace(",", "")),
            "total_contributions": (
                float(total_match.group(1).replace(",", ""))
                if total_match else None
            ),
        })
    return rows


def acquire_ar_followthemoney(
    targets: pd.DataFrame, timeout: int,
) -> tuple[list[dict], pd.DataFrame]:
    """Acquire public historical totals used only when an official row is unusable."""
    manifests = []
    source_rows = []
    for cycle in sorted(targets.cycle.unique()):
        page = 0
        while True:
            path = RAW / "AR" / "followthemoney_candidate_totals_v1" / (
                f"{int(cycle)}_page_{page}.html"
            )
            params = {
                "dt": "1", "s": "AR", "y": str(int(cycle)), "c-exi": "1",
                "gro": "c-t-id", "p": str(page),
            }
            if not path.exists():
                response = requests.get(
                    AR_FOLLOWTHEMONEY_CANDIDATE_URL, params=params,
                    headers={"User-Agent": USER_AGENT}, timeout=timeout,
                )
                response.raise_for_status()
                write_immutable_bytes(path, response.content)
            rows = parse_ar_followthemoney_candidates(path.read_bytes())
            source_rows.extend(rows)
            manifests.append({
                "source_file_id": (
                    f"finance-summary:ar:followthemoney:{cycle}:{page}:"
                    f"{sha256(path)[:12]}"
                ),
                "state": "AR", "cycle": int(cycle),
                "data_kind": "candidate_cycle_contribution_totals_secondary",
                "provider": "FollowTheMoney.org",
                "source_url": AR_FOLLOWTHEMONEY_CANDIDATE_URL,
                "retrieved_at": datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc
                ).replace(microsecond=0).isoformat(),
                "sha256": sha256(path), "size_bytes": path.stat().st_size,
                "record_count": len(rows), "local_path": relative(path),
                "request_parameters": json.dumps(params, sort_keys=True, separators=(",", ":")),
                "authoritative_scope": (
                    "secondary aggregation of campaign-finance reports filed with the state; "
                    "fallback only when the official Arkansas report is unavailable or unusable"
                ),
                "ingest_status": "acquired_parsed",
                "license_or_terms": "Institute data attribution required; public research table",
            })
            if len(rows) < 100:
                break
            page += 1
            if page > 20:
                raise RuntimeError("FollowTheMoney Arkansas candidate table did not terminate")

    source = pd.DataFrame(source_rows)
    office = source.office.str.extract(
        r"^(HOUSE|SENATE) DISTRICT\s+0*(\d+)$", flags=re.I
    )
    source["chamber"] = office[0].str.lower().map(
        {"house": "house", "senate": "senate"}
    )
    source["district"] = pd.to_numeric(office[1], errors="coerce")
    source["party_normalized"] = source.party.str.upper().map(
        {"DEMOCRATIC": "D", "REPUBLICAN": "R"}
    )
    source = source[
        source.chamber.notna() & source.district.notna()
        & source.party_normalized.notna()
    ].copy()
    matches = []
    for target in targets.itertuples(index=False):
        pool = source[
            source.cycle.eq(target.cycle)
            & source.chamber.eq(target.chamber)
            & source.district.eq(target.district)
            & source.party_normalized.eq(target.party)
        ]
        scored = sorted(
            [(candidate_identity_score(target.candidate, row.candidate), row)
             for row in pool.itertuples(index=False)],
            key=lambda item: item[0], reverse=True,
        )
        best_score, best = scored[0] if scored else (0.0, None)
        second = scored[1][0] if len(scored) > 1 else 0.0
        margin = float(best_score - second)
        accepted = bool(
            best is not None and best_score >= 94.0
            and (margin >= 4.0 or best_score >= 98.0)
            and pd.notna(best.total_contributions)
        )
        matches.append({
            "state": "AR", "cycle": int(target.cycle),
            "chamber": target.chamber, "district": int(target.district),
            "party": target.party, "candidate": target.candidate,
            "provider_candidate": best.candidate if best is not None else "",
            "provider_identity": (
                f"followthemoney:{best.candidate_id}" if best is not None else ""
            ),
            "candidate_filer_id": best.candidate_id if best is not None else "",
            "campaign_id": best.entity_id if best is not None else "",
            "match_score": best_score, "match_margin": margin,
            "candidates_considered": len(scored),
            "match_status": (
                "accepted_secondary_fallback" if accepted else "review_required"
            ),
            "record_count": int(best.record_count) if accepted else None,
            "total_contributions": float(best.total_contributions) if accepted else None,
        })
    match_path = RAW / "AR" / "followthemoney_candidate_matches_v1.jsonl"
    if not match_path.exists():
        write_immutable_bytes(
            match_path,
            "".join(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                for row in matches
            ).encode("utf-8"),
        )
    return manifests, pd.DataFrame(matches)


def acquire_ar(timeout: int, workers: int) -> None:
    targets = candidate_universe("AR")
    # Current candidate summaries cover 2024; public legacy report indexes and
    # cumulative candidate PDFs supply the preceding modeled cycles.
    cycles = [cycle for cycle in sorted(targets.cycle.unique()) if cycle >= 2024]
    coverage_rows = []
    legacy_manifests, legacy_matches, legacy_selections, _ = acquire_ar_legacy_reports(
        targets, timeout, workers
    )
    fallback_manifests, fallback_matches = acquire_ar_followthemoney(targets, timeout)
    manifests = legacy_manifests + fallback_manifests
    matches_all = [legacy_matches, fallback_matches]
    for cycle, group in legacy_matches.groupby("cycle"):
        accepted = int(group.match_status.eq("accepted_automatic").sum())
        coverage_rows.append({
            "state": "AR", "cycle": int(cycle),
            "target_candidates": len(group), "matched_candidates": accepted,
            "match_coverage": accepted / len(group) if len(group) else 0.0,
            "selected_report_details": int(legacy_selections.cycle.eq(cycle).sum()),
            "acquisition_status": (
                "complete_candidate_match" if accepted == len(group)
                else "candidate_match_review_required"
            ),
        })
        print(f"AR {cycle}: {accepted}/{len(group)} legacy candidates", flush=True)
    session = session_with_retries()
    try:
        for cycle in cycles:
            path, rows, payload = ar_candidate_summary_index(session, int(cycle), timeout)
            matches = match_ar_candidates(targets, rows, int(cycle))
            matches_all.append(matches)
            accepted = int(matches.match_status.eq("accepted_automatic").sum())
            manifests.append({
                "source_file_id": f"finance-summary:ar:{cycle}:candidate-index:{sha256(path)[:12]}",
                "state": "AR", "cycle": int(cycle),
                "data_kind": "candidate_financial_summary_index",
                "provider": "Arkansas Secretary of State Financial Disclosure",
                "source_url": AR_CANDIDATE_SUMMARY_URL,
                "retrieved_at": datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc
                ).replace(microsecond=0).isoformat(),
                "sha256": sha256(path), "size_bytes": path.stat().st_size,
                "record_count": len(rows), "local_path": relative(path),
                "request_parameters": json.dumps(payload, sort_keys=True, separators=(",", ":")),
                "authoritative_scope": "official candidate-level total raised, spent, and balance for the selected election year",
                "ingest_status": "acquired_parsed",
                "license_or_terms": "official public records; reuse terms not stated",
            })
            coverage_rows.append({
                "state": "AR", "cycle": int(cycle),
                "target_candidates": len(matches), "matched_candidates": accepted,
                "match_coverage": accepted / len(matches) if len(matches) else 0.0,
                "selected_report_details": 0,
                "acquisition_status": (
                    "complete_candidate_match" if accepted == len(matches)
                    else "candidate_match_review_required"
                ),
            })
            print(f"AR {cycle}: {accepted}/{len(matches)} candidates", flush=True)
    finally:
        session.close()
    if matches_all:
        upsert_state_csv(MANIFEST, pd.DataFrame(manifests), "AR")
        upsert_state_csv(MATCH_AUDIT, pd.concat(matches_all, ignore_index=True), "AR")
        upsert_state_csv(COVERAGE, pd.DataFrame(coverage_rows), "AR")


def parse_fl_candidate_summary(content: bytes) -> list[dict]:
    text = BeautifulSoup(content, "html.parser").get_text("\n")
    rows = []
    pattern = re.compile(
        r"^(?P<candidate>.*?)\s+(?P<party>[A-Z]{3})\s+"
        r"(?P<office>STR|STS)\s+(?P<district>\d{3})\s+"
        r"(?:(?P<group>\d+)\s+)?(?P<amount>-?[\d,]+\.\d{2})\s*$"
    )
    for line in text.splitlines():
        match = pattern.match(line.rstrip())
        if not match:
            continue
        row = match.groupdict()
        row["district"] = int(row["district"])
        row["total_amount"] = float(row.pop("amount").replace(",", ""))
        rows.append(row)
    return rows


def fl_candidate_summary(
    session: requests.Session, cycle: int, chamber: str, timeout: int,
    election_code: str | None = None,
) -> tuple[Path, list[dict], dict]:
    office = "STR" if chamber == "house" else "STS"
    election_code = election_code or FL_ELECTION_CODES[cycle]
    suffix = "general" if election_code == FL_ELECTION_CODES[cycle] else election_code.lower()
    path = RAW / "FL" / f"{cycle}_{chamber}_candidate_contribution_summary_{suffix}.html"
    legacy_path = RAW / "FL" / f"{cycle}_{chamber}_candidate_contribution_summary.html"
    if suffix == "general" and legacy_path.exists():
        path = legacy_path
    payload = {
        "election": election_code, "CanFName": "", "CanLName": "",
        "CanNameSrch": "2", "office": office, "cdistrict": "", "cgroup": "",
        "party": "All", "search_on": "3", "ComName": "", "ComNameSrch": "2",
        "committee": "All", "cfname": "", "clname": "", "namesearch": "2",
        "ccity": "", "cstate": "", "czipcode": "", "coccupation": "",
        "cdollar_minimum": "", "cdollar_maximum": "", "rowlimit": "500",
        "csort1": "NAM", "csort2": "CAN", "cdatefrom": "", "cdateto": "",
        "queryformat": "1", "Submit": "Submit",
    }
    if not path.exists():
        response = session.post(
            FL_CONTRIBUTION_SUMMARY_URL, data=payload, timeout=timeout,
            headers={
                "Referer": "https://dos.elections.myflorida.com/campaign-finance/contributions/"
            },
        )
        response.raise_for_status()
        if b"Summary of Candidates" not in response.content:
            raise RuntimeError(f"Florida {cycle} {chamber} response was not a candidate summary")
        write_immutable_bytes(path, response.content)
    rows = parse_fl_candidate_summary(path.read_bytes())
    if not rows:
        raise RuntimeError(f"Florida {cycle} {chamber} summary parsed no rows")
    return path, rows, payload


def match_fl_candidates(
    targets: pd.DataFrame, source_rows: list[dict], cycle: int,
) -> pd.DataFrame:
    source = pd.DataFrame(source_rows)
    source["chamber"] = source.office.map({"STR": "house", "STS": "senate"})
    source["party_normalized"] = source.party.map({"DEM": "D", "REP": "R"})
    source["provider_identity"] = source.apply(
        lambda row: (
            f"{row['chamber']}|{int(row['district'])}|"
            f"{' '.join(normalized_tokens(row['candidate']))}|{row['party_normalized'] or ''}"
        ), axis=1,
    )
    identities = source.drop_duplicates("provider_identity")
    matches = []
    for target in targets[targets.cycle.eq(cycle)].itertuples(index=False):
        pool = identities[
            identities.chamber.eq(target.chamber)
            & identities.district.eq(target.district)
            & identities.party_normalized.eq(target.party)
        ]
        scored = sorted([
            (
                candidate_score(target.candidate, row.candidate),
                str(row.provider_identity), str(row.candidate).strip(),
            ) for row in pool.itertuples(index=False)
        ], reverse=True)
        best = scored[0] if scored else (0.0, "", "")
        second = scored[1][0] if len(scored) > 1 else 0.0
        margin = float(best[0] - second)
        accepted = bool(best[1] and best[0] >= 88.0 and margin >= 4.0)
        matches.append({
            "state": "FL", "cycle": cycle, "chamber": target.chamber,
            "district": target.district, "party": target.party,
            "candidate": target.candidate, "provider_candidate": best[2],
            "provider_identity": best[1], "candidate_filer_id": "",
            "campaign_id": "", "match_score": best[0], "match_margin": margin,
            "candidates_considered": len(scored),
            "match_status": "accepted_automatic" if accepted else "review_required",
        })
    return pd.DataFrame(matches)


def acquire_fl(timeout: int) -> None:
    targets = candidate_universe("FL")
    session = session_with_retries()
    manifests = []
    match_frames = []
    coverage_rows = []
    try:
        for cycle in sorted(targets.cycle.unique()):
            all_rows = []
            election_chambers = [
                (FL_ELECTION_CODES[int(cycle)], "house"),
                (FL_ELECTION_CODES[int(cycle)], "senate"),
            ] + FL_SPECIAL_ELECTION_CODES.get(int(cycle), [])
            for election_code, chamber in election_chambers:
                path, rows, payload = fl_candidate_summary(
                    session, int(cycle), chamber, timeout, election_code
                )
                all_rows.extend({**row, "election_code": election_code} for row in rows)
                manifests.append({
                    "source_file_id": f"finance-summary:fl:{cycle}:{chamber}:{election_code}:{sha256(path)[:12]}",
                    "state": "FL", "cycle": int(cycle),
                    "data_kind": "candidate_contribution_summary",
                    "provider": "Florida Division of Elections",
                    "source_url": FL_CONTRIBUTION_SUMMARY_URL,
                    "retrieved_at": datetime.fromtimestamp(
                        path.stat().st_mtime, timezone.utc
                    ).replace(microsecond=0).isoformat(),
                    "sha256": sha256(path), "size_bytes": path.stat().st_size,
                    "record_count": len(rows), "local_path": relative(path),
                    "request_parameters": json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    "authoritative_scope": "official candidate contribution-total summary for the selected election, office, and all parties",
                    "ingest_status": "acquired_parsed_measure_review",
                    "license_or_terms": "official public records; reuse terms not stated",
                })
            matches = match_fl_candidates(targets, all_rows, int(cycle))
            match_frames.append(matches)
            accepted = int(matches.match_status.eq("accepted_automatic").sum())
            coverage_rows.append({
                "state": "FL", "cycle": int(cycle),
                "target_candidates": len(matches), "matched_candidates": accepted,
                "match_coverage": accepted / len(matches) if len(matches) else 0.0,
                "selected_report_details": 0,
                "acquisition_status": "source_measure_includes_in_kind_and_loan_records",
            })
            print(f"FL {cycle}: {accepted}/{len(matches)} candidates", flush=True)
    finally:
        session.close()
    upsert_state_csv(MANIFEST, pd.DataFrame(manifests), "FL")
    upsert_state_csv(MATCH_AUDIT, pd.concat(match_frames, ignore_index=True), "FL")
    upsert_state_csv(COVERAGE, pd.DataFrame(coverage_rows), "FL")


def money(value: object) -> float | None:
    text = str(value or "").strip().replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text.replace("(", "-").replace(")", ""))
    except ValueError:
        return None


def tn_candidate_search_payload(cycle: int) -> list[tuple[str, str]]:
    return [
        ("searchType", "candidate"), ("name", ""),
        ("officeSelection", ""), ("districtSelection", ""),
        ("electionYearSelection", TN_ELECTION_IDS[cycle]), ("partySelection", ""),
        ("nameField", "true"), ("contactField", "true"),
        ("partyField", "true"), ("officeField", "true"),
        ("districtField", "true"), ("primaryField", "true"),
        ("generalField", "true"), ("electionYearField", "true"),
        ("committeeField", "true"), ("createdField", "true"),
        ("closedField", "true"), ("_continue", "Search"),
    ]


def parse_tn_candidate_page(content: bytes) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    rows = []
    party_map = {"Democrat": "D", "Republican": "R"}
    for tr in soup.select("table tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        link = tr.select_one("a[href*='/public/replist.htm']")
        if len(cells) < 8 or link is None:
            continue
        identity = re.search(r"[?&]id=(\d+)", link.get("href", ""))
        district = pd.to_numeric(cells[4], errors="coerce")
        chamber = (
            "house" if "House" in cells[3]
            else "senate" if "Senate" in cells[3] else None
        )
        if identity is None or pd.isna(district) or chamber is None:
            continue
        rows.append({
            "candidate": cells[0], "party": party_map.get(cells[2]),
            "chamber": chamber, "district": int(district),
            "general_election": bool(str(cells[6]).strip()),
            "provider_id": identity.group(1), "committee_id": identity.group(1),
            "report_list_url": urljoin(TN_BASE, link["href"]),
        })
    return rows


def parse_tn_report_page(content: bytes) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    rows = []
    for tr in soup.select("table tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        link = tr.select_one("a[href*='report_full.htm?reportId=']")
        if len(cells) < 4 or link is None:
            continue
        report_id = re.search(r"reportId=(\d+)", link.get("href", ""))
        report_year = re.search(r"(20\d{2})\s*$", cells[1])
        if report_id is None or report_year is None:
            continue
        rows.append({
            "election": int(cells[0]), "report_name": cells[1],
            "is_amendment": cells[2].upper() == "Y",
            "submitted_on": cells[3], "report_year": int(report_year.group(1)),
            "report_id": report_id.group(1),
            "report_url": urljoin(TN_BASE, link["href"]),
        })
    return rows


def acquire_tn(timeout: int, workers: int) -> None:
    """Acquire candidate-partitioned Tennessee report summaries.

    The portal's statewide transaction export exposes only the current result
    batch.  Candidate report lists are complete, amendment-aware, and much
    smaller, so the modeled-candidate/report partition is the authoritative
    acquisition path for cycle fundraising.
    """
    targets = candidate_universe("TN")
    manifests, match_frames, coverage_rows, report_index = [], [], [], []
    session = session_with_retries()
    search_url = urljoin(TN_BASE, "public/cpsearch.htm")
    try:
        for cycle in sorted(targets.cycle.unique()):
            cycle = int(cycle)
            cycle_root = RAW / "TN" / str(cycle)
            first_path = cycle_root / "candidate_index_page_1.html"
            page_contents: list[bytes] = []
            if first_path.exists():
                page_paths = sorted(cycle_root.glob("candidate_index_page_*.html"))
                page_contents = [path.read_bytes() for path in page_paths]
            else:
                session.get(search_url, timeout=timeout).raise_for_status()
                response = session.post(
                    search_url, data=tn_candidate_search_payload(cycle), timeout=timeout
                )
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                page_links = [1]
                for node in soup.select("a[href*='d-1341904-p=']"):
                    match = re.search(r"d-1341904-p=(\d+)", node.get("href", ""))
                    if match:
                        page_links.append(int(match.group(1)))
                last_page = max(page_links)
                for page in range(1, last_page + 1):
                    content = response.content if page == 1 else session.get(
                        urljoin(response.url, f"?d-1341904-p={page}"), timeout=timeout
                    ).content
                    path = cycle_root / f"candidate_index_page_{page}.html"
                    write_immutable_bytes(path, content)
                    page_contents.append(content)
            source_rows = []
            for content in page_contents:
                source_rows.extend(parse_tn_candidate_page(content))
            source = pd.DataFrame(source_rows).drop_duplicates("provider_id")
            general_source = source[source.general_election].copy()
            matches = match_simple_candidates(
                targets, general_source, cycle, "TN", require_party=True
            )
            scoped_variant = (
                pd.to_numeric(matches.match_score, errors="coerce").ge(80.0)
                & pd.to_numeric(matches.match_margin, errors="coerce").ge(10.0)
            )
            matches.loc[scoped_variant, "match_status"] = "accepted_automatic"
            match_frames.append(matches)
            accepted = matches[matches.match_status.eq("accepted_automatic")]

            # Re-establish public-search context when immutable candidate pages
            # were reused; report-list URLs otherwise redirect to the login page.
            session.get(search_url, timeout=timeout).raise_for_status()
            session.post(
                search_url, data=tn_candidate_search_payload(cycle), timeout=timeout
            ).raise_for_status()
            for match in accepted.to_dict("records"):
                provider_id = str(match["provider_identity"])
                source_row = source[source.provider_id.eq(provider_id)].iloc[0]
                page_one = cycle_root / "report_lists" / f"{provider_id}_page_1.html"
                if page_one.exists():
                    list_paths = sorted(page_one.parent.glob(f"{provider_id}_page_*.html"))
                    list_contents = [path.read_bytes() for path in list_paths]
                else:
                    response = session.get(source_row.report_list_url, timeout=timeout)
                    response.raise_for_status()
                    if "/public/replist.htm" not in response.url:
                        raise RuntimeError(f"TN report list redirected for {provider_id}")
                    soup = BeautifulSoup(response.content, "html.parser")
                    pages = [1]
                    for node in soup.select("a[href*='d-1341904-p=']"):
                        found = re.search(r"d-1341904-p=(\d+)", node.get("href", ""))
                        if found:
                            pages.append(int(found.group(1)))
                    list_contents = []
                    for page in range(1, max(pages) + 1):
                        # Reconstruct the paging query while preserving owner/id.
                        content = response.content if page == 1 else session.get(
                            source_row.report_list_url + f"&d-1341904-p={page}",
                            timeout=timeout,
                        ).content
                        path = cycle_root / "report_lists" / f"{provider_id}_page_{page}.html"
                        write_immutable_bytes(path, content)
                        list_contents.append(content)
                reports = []
                for content in list_contents:
                    reports.extend(parse_tn_report_page(content))
                reports = [
                    row for row in reports
                    if row["election"] == cycle and row["report_year"] in {cycle - 1, cycle}
                ]
                for row in {item["report_id"]: item for item in reports}.values():
                    report_index.append({**match, **row})

            index_path = cycle_root / "matched_candidate_report_index_v2.jsonl"
            lines = "".join(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                for row in report_index if int(row["cycle"]) == cycle
            )
            write_immutable_bytes(index_path, lines.encode("utf-8"))
            manifests.append(source_manifest_row(
                index_path, state="TN", cycle=cycle, kind="matched_candidate_report_index",
                provider="Tennessee Registry of Election Finance", source_url=search_url,
                record_count=sum(int(row["cycle"]) == cycle for row in report_index),
                request_parameters={"election_id": TN_ELECTION_IDS[cycle]},
                authoritative_scope="official modeled-candidate current report list",
            ))
            accepted_count = len(accepted)
            coverage_rows.append({
                "state": "TN", "cycle": cycle, "target_candidates": len(matches),
                "matched_candidates": accepted_count,
                "match_coverage": accepted_count / len(matches) if len(matches) else 0.0,
                "selected_report_details": sum(int(row["cycle"]) == cycle for row in report_index),
                "acquisition_status": "candidate_report_lists_acquired",
            })
            print(f"TN {cycle}: {accepted_count}/{len(matches)} candidates indexed", flush=True)
    finally:
        session.close()

    def fetch_report(row: dict) -> tuple[dict, Path]:
        path = RAW / "TN" / "reports" / f"{row['report_id']}.html"
        if not path.exists():
            local = session_with_retries()
            try:
                local.get(urljoin(TN_BASE, "public/search.htm"), timeout=timeout).raise_for_status()
                response = local.get(row["report_url"], timeout=timeout)
                response.raise_for_status()
                if response.url.endswith("login.htm"):
                    raise RuntimeError(f"TN report {row['report_id']} redirected to login")
                write_immutable_bytes(path, response.content)
            finally:
                local.close()
        return row, path

    unique_reports = list({row["report_id"]: row for row in report_index}.values())
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = [pool.submit(fetch_report, row) for row in unique_reports]
        for future in as_completed(futures):
            row, path = future.result()
            manifests.append(source_manifest_row(
                path, state="TN", cycle=int(row["cycle"]), kind="report_summary_html",
                provider="Tennessee Registry of Election Finance",
                source_url=row["report_url"], record_count=1,
                request_parameters={"report_id": row["report_id"]},
                authoritative_scope="official current campaign-finance report summary",
            ))
    upsert_state_csv(MANIFEST, pd.DataFrame(manifests), "TN")
    upsert_state_csv(MATCH_AUDIT, pd.concat(match_frames, ignore_index=True), "TN")
    upsert_state_csv(COVERAGE, pd.DataFrame(coverage_rows), "TN")
    print(f"TN: acquired {len(unique_reports)} unique report summaries", flush=True)


def acquire_al_adjudicated_completion() -> None:
    """Acquire official FCPA summaries for approved candidate-level gaps."""
    if not FINANCE_IDENTITY_ADJUDICATIONS.exists():
        raise RuntimeError("Finance identity adjudication file is missing")
    decisions = pd.read_csv(FINANCE_IDENTITY_ADJUDICATIONS, dtype=str)
    decisions = decisions[
        decisions.state_code.eq("AL") & decisions.review_status.eq("approved")
    ].copy()
    if decisions.empty:
        print("AL: no approved candidate-completion decisions", flush=True)
        return
    for column in ("cycle_start", "cycle_end", "district"):
        decisions[column] = pd.to_numeric(decisions[column], errors="raise").astype(int)

    manifests: list[dict[str, object]] = []
    index_rows: list[dict[str, object]] = []
    summary_cache: dict[str, tuple[dict, str, Path]] = {}
    for decision in decisions.itertuples(index=False):
        record_ids = [
            value.strip() for value in str(decision.provider_identity).split("|")
            if value.strip()
        ]
        alias = str(decision.provider_candidate_name).split("|", 1)[0]
        tokens = normalized_tokens(alias)
        if not tokens:
            raise RuntimeError(f"AL adjudication lacks a searchable name: {decision.adjudication_id}")
        query_first_name = tokens[0] if len(tokens) > 1 else None
        results, search_url = fcpa_search(tokens[-1])
        result_ids = {str(item.get("id")) for item in results}
        missing_ids = sorted(set(record_ids) - result_ids)
        search_mode = "surname"
        # The public result set is capped at 100.  Retry common surnames with
        # the approved provider first name so exact records beyond that cap
        # remain discoverable and the saved evidence reflects the query used.
        if missing_ids and query_first_name:
            exact_results, exact_search_url = fcpa_search(
                tokens[-1], first_name=query_first_name
            )
            exact_ids = {str(item.get("id")) for item in exact_results}
            if set(record_ids).issubset(exact_ids):
                results, search_url = exact_results, exact_search_url
                result_ids = exact_ids
                missing_ids = []
                search_mode = "first_and_surname"
        if missing_ids:
            raise RuntimeError(
                f"AL adjudication provider IDs are absent from official search "
                f"for {decision.adjudication_id}: {missing_ids}"
            )
        search_path = (
            RAW / "AL" / "adjudicated_committee_searches_v2"
            / f"{decision.adjudication_id}.json"
        )
        search_content = json.dumps({
            "adjudication_id": decision.adjudication_id,
            "query_surname": tokens[-1],
            "query_first_name": query_first_name if search_mode == "first_and_surname" else None,
            "search_mode": search_mode,
            "source_url": search_url,
            "results": results,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        write_immutable_bytes(search_path, search_content)
        manifests.append(source_manifest_row(
            search_path, state="AL", cycle=decision.cycle_start,
            kind="adjudicated_candidate_committee_search",
            provider="Alabama Secretary of State FCPA",
            source_url=search_url, record_count=len(results),
            request_parameters={
                "surname": tokens[-1],
                "first_name": query_first_name if search_mode == "first_and_surname" else None,
                "search_mode": search_mode,
                "adjudication_id": decision.adjudication_id,
            },
            authoritative_scope=(
                "official principal-campaign-committee search evidence for an "
                "approved modeled-candidate identity"
            ),
        ))
        summary_paths = []
        summary_urls = []
        for record_id in record_ids:
            if record_id not in summary_cache:
                payload, summary_url = all_financial_summaries(record_id)
                summary_path = (
                    RAW / "AL" / "adjudicated_financial_summaries_v1"
                    / f"{record_id}.json"
                )
                content = json.dumps({
                    "fcpa_record_id": record_id,
                    "source_url": summary_url,
                    "financial_summary": payload,
                }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                write_immutable_bytes(summary_path, content)
                summary_cache[record_id] = (payload, summary_url, summary_path)
                manifests.append(source_manifest_row(
                    summary_path, state="AL", cycle=decision.cycle_start,
                    kind="adjudicated_candidate_financial_summary",
                    provider="Alabama Secretary of State FCPA",
                    source_url=summary_url, record_count=len(payload),
                    request_parameters={"fcpa_record_id": record_id},
                    authoritative_scope=(
                        "official calendar-year committee financial summaries for an "
                        "approved modeled-candidate identity"
                    ),
                ))
            _, summary_url, summary_path = summary_cache[record_id]
            summary_paths.append(summary_path.relative_to(ROOT).as_posix())
            summary_urls.append(summary_url)
        for cycle in range(decision.cycle_start, decision.cycle_end + 1, 2):
            index_rows.append({
                "state": "AL", "cycle": cycle, "chamber": decision.chamber,
                "district": decision.district, "party": decision.party,
                "candidate": decision.candidate_name,
                "provider_candidate": decision.provider_candidate_name,
                "provider_identity": decision.provider_identity,
                "search_path": search_path.relative_to(ROOT).as_posix(),
                "summary_paths": summary_paths, "summary_urls": summary_urls,
                "adjudication_id": decision.adjudication_id,
            })

    index_rows.sort(key=lambda row: (
        row["cycle"], row["chamber"], row["district"], row["party"]
    ))
    index_path = RAW / "AL" / "adjudicated_candidate_financial_summary_index_v3.jsonl"
    index_content = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in index_rows
    ).encode("utf-8")
    write_immutable_bytes(index_path, index_content)
    manifests.append(source_manifest_row(
        index_path, state="AL", cycle=0,
        kind="adjudicated_candidate_financial_summary_index",
        provider="Alabama Secretary of State FCPA",
        source_url="https://fcpa.alabamavotes.gov/", record_count=len(index_rows),
        request_parameters={"selection": "approved candidate-completion adjudications"},
        authoritative_scope=(
            "official FCPA record IDs joined to exact modeled candidates by approved evidence"
        ),
    ))
    existing_al = pd.DataFrame()
    if MANIFEST.exists():
        existing = pd.read_csv(MANIFEST)
        existing_al = existing[existing.state.eq("AL")].copy()
    combined = pd.concat([existing_al, pd.DataFrame(manifests)], ignore_index=True, sort=False)
    combined = combined.drop_duplicates("source_file_id", keep="last")
    upsert_state_csv(MANIFEST, combined, "AL")
    print(
        f"AL: acquired {len(summary_cache)} summaries for {len(index_rows)} "
        "adjudicated candidate-cycles", flush=True,
    )


def acquire_tn_adjudicated_completion(timeout: int) -> None:
    """Acquire only reports authorized by approved TN identity decisions.

    This path closes a small historical candidate-index gap without replacing
    the immutable statewide acquisition. Each supplemental index cites a
    stable, evidence-bearing adjudication and retains the official report IDs.
    """
    if not FINANCE_IDENTITY_ADJUDICATIONS.exists():
        raise RuntimeError("Finance identity adjudication file is missing")
    decisions = pd.read_csv(FINANCE_IDENTITY_ADJUDICATIONS, dtype=str)
    decisions = decisions[
        decisions.state_code.eq("TN") & decisions.review_status.eq("approved")
    ].copy()
    if decisions.empty:
        print("TN: no approved candidate-completion decisions", flush=True)
        return
    for column in ("cycle_start", "cycle_end", "district"):
        decisions[column] = pd.to_numeric(decisions[column], errors="raise").astype(int)

    manifests: list[dict[str, object]] = []
    index_rows: dict[int, list[dict[str, object]]] = {}
    session = session_with_retries()
    search_url = urljoin(TN_BASE, "public/cpsearch.htm")
    try:
        for decision in decisions.itertuples(index=False):
            source_path = ROOT / decision.evidence_source_path
            official_report_list_evidence = str(decision.evidence_source_url).startswith(
                "https://apps.tn.gov/tncamp/public/replist.htm"
            )
            if not source_path.exists() and not official_report_list_evidence:
                raise RuntimeError(
                    f"TN adjudication evidence is missing: {decision.evidence_source_path}"
                )
            context_cycle = decision.cycle_start
            if source_path.exists():
                context_cycle = next(
                    int(part) for part in source_path.parts
                    if part.isdigit() and int(part) in TN_ELECTION_IDS
                )
            session.get(search_url, timeout=timeout).raise_for_status()
            session.post(
                search_url, data=tn_candidate_search_payload(context_cycle), timeout=timeout
            ).raise_for_status()
            response = session.get(
                urljoin(TN_BASE, "public/replist.htm"),
                params={
                    "id": decision.provider_identity,
                    "owner": decision.provider_candidate_name,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            if "/public/replist.htm" not in response.url:
                raise RuntimeError(
                    f"TN adjudicated report list redirected for {decision.provider_identity}"
                )
            soup = BeautifulSoup(response.content, "html.parser")
            pages = [1]
            for node in soup.select("a[href*='d-1341904-p=']"):
                found = re.search(r"d-1341904-p=(\d+)", node.get("href", ""))
                if found:
                    pages.append(int(found.group(1)))
            list_contents: list[bytes] = []
            for page in range(1, max(pages) + 1):
                content = response.content if page == 1 else session.get(
                    response.url + f"&d-1341904-p={page}", timeout=timeout
                ).content
                list_path = (
                    RAW / "TN" / str(decision.cycle_start) / "adjudicated_report_lists_v2"
                    / f"{decision.provider_identity}_page_{page}.html"
                )
                write_immutable_bytes(list_path, content)
                list_contents.append(content)
                manifests.append(source_manifest_row(
                    list_path, state="TN", cycle=decision.cycle_start,
                    kind="adjudicated_candidate_report_list",
                    provider="Tennessee Registry of Election Finance",
                    source_url=response.url, record_count=1,
                    request_parameters={
                        "provider_identity": decision.provider_identity,
                        "page": page,
                        "adjudication_id": decision.adjudication_id,
                    },
                    authoritative_scope=(
                        "official report list for an approved modeled-candidate identity"
                    ),
                ))
            reports: list[dict[str, object]] = []
            for content in list_contents:
                reports.extend(parse_tn_report_page(content))
            reports = list({row["report_id"]: row for row in reports}.values())

            for cycle in range(decision.cycle_start, decision.cycle_end + 1, 2):
                target = candidate_universe("TN")
                target = target[
                    target.cycle.eq(cycle) & target.chamber.eq(decision.chamber)
                    & target.district.eq(decision.district)
                    & target.party.eq(decision.party)
                ]
                if len(target) != 1:
                    raise RuntimeError(
                        f"TN adjudication does not resolve one modeled candidate: "
                        f"{decision.adjudication_id}"
                    )
                selected = [
                    row for row in reports
                    if row["election"] == cycle
                    and row["report_year"] in {cycle - 1, cycle}
                ]
                if not selected:
                    raise RuntimeError(
                        f"TN adjudicated filer has no reports for cycle {cycle}: "
                        f"{decision.provider_identity}"
                    )
                for row in selected:
                    index_entry = {
                        "state": "TN", "cycle": cycle,
                        "chamber": decision.chamber, "district": decision.district,
                        "party": decision.party, "candidate": target.iloc[0].candidate,
                        "provider_candidate": decision.provider_candidate_name,
                        "provider_identity": decision.provider_identity,
                        "candidate_filer_id": decision.provider_identity,
                        "campaign_id": decision.provider_identity,
                        "match_status": "accepted_manual_adjudication",
                        "adjudication_id": decision.adjudication_id,
                        **row,
                    }
                    report_path = RAW / "TN" / "reports" / f"{row['report_id']}.html"
                    if not report_path.exists():
                        report_response = session.get(row["report_url"], timeout=timeout)
                        report_response.raise_for_status()
                        if report_response.url.endswith("login.htm"):
                            raise RuntimeError(
                                f"TN report {row['report_id']} redirected to login"
                            )
                        write_immutable_bytes(report_path, report_response.content)
                    report_text = BeautifulSoup(
                        report_path.read_bytes(), "html.parser"
                    ).get_text(" ", strip=True)
                    if "TOTAL CONTRIBUTIONS" not in report_text.upper():
                        # The public summary endpoint occasionally errors for a valid
                        # report while its official full-report workbook remains
                        # available in the same session. Preserve the error page and
                        # acquire the workbook as a separate immutable source.
                        session.get(row["report_url"], timeout=timeout).raise_for_status()
                        workbook_response = session.get(
                            urljoin(
                                TN_BASE,
                                "search/pub/fullReportExcelExportPublic.htm",
                            ),
                            params={"generateLists": "true"}, timeout=timeout,
                        )
                        workbook_response.raise_for_status()
                        if not workbook_response.content.startswith(b"\xd0\xcf\x11\xe0"):
                            raise RuntimeError(
                                f"TN report {row['report_id']} workbook is not an XLS file"
                            )
                        workbook_path = (
                            RAW / "TN" / "report_workbooks"
                            / f"{row['report_id']}.xls"
                        )
                        write_immutable_bytes(workbook_path, workbook_response.content)
                        index_entry["report_workbook_path"] = (
                            workbook_path.relative_to(ROOT).as_posix()
                        )
                        manifests.append(source_manifest_row(
                            workbook_path, state="TN", cycle=cycle,
                            kind="adjudicated_full_report_workbook",
                            provider="Tennessee Registry of Election Finance",
                            source_url=workbook_response.url, record_count=1,
                            request_parameters={
                                "report_id": row["report_id"],
                                "adjudication_id": decision.adjudication_id,
                                "fallback_reason": "public summary endpoint error",
                            },
                            authoritative_scope=(
                                "official full-report workbook for a report whose "
                                "public summary endpoint is unreadable"
                            ),
                        ))
                    index_rows.setdefault(cycle, []).append(index_entry)
                    manifests.append(source_manifest_row(
                        report_path, state="TN", cycle=cycle,
                        kind="adjudicated_report_summary_html",
                        provider="Tennessee Registry of Election Finance",
                        source_url=row["report_url"], record_count=1,
                        request_parameters={
                            "report_id": row["report_id"],
                            "adjudication_id": decision.adjudication_id,
                        },
                        authoritative_scope=(
                            "official current campaign-finance report summary for an "
                            "approved modeled-candidate identity"
                        ),
                    ))
    finally:
        session.close()

    for cycle, rows in index_rows.items():
        rows.sort(key=lambda row: (row["district"], row["party"], int(row["report_id"])))
        index_path = RAW / "TN" / str(cycle) / "adjudicated_candidate_report_index_v2.jsonl"
        content = "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ).encode("utf-8")
        write_immutable_bytes(index_path, content)
        manifests.append(source_manifest_row(
            index_path, state="TN", cycle=cycle,
            kind="adjudicated_candidate_report_index",
            provider="Tennessee Registry of Election Finance",
            source_url=search_url, record_count=len(rows),
            request_parameters={
                "selection": "approved candidate-completion adjudications",
            },
            authoritative_scope=(
                "official report IDs joined to exact modeled candidates by approved evidence"
            ),
        ))

    existing_tn = pd.DataFrame()
    if MANIFEST.exists():
        existing = pd.read_csv(MANIFEST)
        existing_tn = existing[existing.state.eq("TN")].copy()
    combined = pd.concat([existing_tn, pd.DataFrame(manifests)], ignore_index=True, sort=False)
    combined = combined.drop_duplicates("source_file_id", keep="last")
    upsert_state_csv(MANIFEST, combined, "TN")
    print(
        f"TN: acquired {sum(len(rows) for rows in index_rows.values())} "
        "adjudicated candidate-report summaries",
        flush=True,
    )


def source_manifest_row(
    path: Path, *, state: str, cycle: int, kind: str, provider: str,
    source_url: str, record_count: int, request_parameters: dict,
    authoritative_scope: str, ingest_status: str = "acquired_parsed",
) -> dict[str, object]:
    return {
        "source_file_id": (
            f"finance-summary:{state.lower()}:{cycle}:{kind}:{sha256(path)[:12]}"
        ),
        "state": state, "cycle": cycle, "data_kind": kind,
        "provider": provider, "source_url": source_url,
        "retrieved_at": datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        ).replace(microsecond=0).isoformat(),
        "sha256": sha256(path), "size_bytes": path.stat().st_size,
        "record_count": record_count, "local_path": relative(path),
        "request_parameters": json.dumps(
            request_parameters, sort_keys=True, separators=(",", ":")
        ),
        "authoritative_scope": authoritative_scope,
        "ingest_status": ingest_status,
        "license_or_terms": "official public records; reuse terms not stated",
    }


def ga_recordsearch_candidate_payload(query: str) -> dict[str, object]:
    """Build the public candidate-search request used by Record Search."""
    return {
        "pageNumber": 1, "pageSize": 100, "sortBy": None, "sortType": None,
        "filerTypeCode": "CAN", "filerName": query,
        "filingEntityId": None, "politicalPartyCode": None,
        "OfficeSought": None, "totalRaisedMax": None, "totalRaisedMin": None,
        "totalSpentMax": None, "totalSpentMin": None,
        "balanceFundsMax": None, "balanceFundsMin": None,
        "accountStatus": None, "election": None, "electionCycle": None,
        "transactionSourceTypeCode": None, "treasurerName": None,
        "jurisdictionId": None, "campaignName": None, "cityDistrictId": None,
        "districtTypeId": None, "jurisdictionIsStateOrIsCounty": None,
        "districtTypeDesc": None, "isProfile": False,
    }


def parse_ga_legacy_candidate_search(content: bytes) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    rows = []
    for link in soup.select("a[href*='__doPostBack'][id*='lnkViewID']"):
        event = re.search(r"__doPostBack\('([^']+)'", link.get("href", ""))
        tr = link.find_parent("tr")
        name = tr.select_one("span[id*='Label1']") if tr else None
        if event is None or name is None:
            continue
        rows.append({
            "provider_candidate": name.get_text(" ", strip=True),
            "event_target": event.group(1),
        })
    return rows


def parse_ga_legacy_candidate_detail(content: bytes) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    name_node = soup.select_one("span[id$='_NameInfo1_lblName']")
    provider_candidate = name_node.get_text(" ", strip=True) if name_node else ""
    table = soup.select_one("table[id$='_NameInfo1_dlDOIs']")
    rows = []
    if table is None:
        return rows
    for tr in table.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        if len(cells) < 4 or not re.fullmatch(r"C\d+", cells[0], re.I):
            continue
        office = cells[1]
        chamber = (
            "house" if re.search(r"State (?:Representative|House)", office, re.I)
            else "senate" if re.search(r"State Senat(?:e|or)", office, re.I) else None
        )
        district_match = re.search(r"District\s*:\s*(\d+)", office, re.I)
        if chamber is None or district_match is None:
            continue
        rows.append({
            "provider_candidate": provider_candidate,
            "provider_identity": "legacy:" + cells[0].upper(),
            "chamber": chamber, "district": int(district_match.group(1)),
            "registration_status": cells[3],
            "no_reports_filed": "No Reports Filed" in soup.get_text(" ", strip=True),
        })
    return rows


def match_ga_legacy_registrations(
    targets: pd.DataFrame, registrations: list[dict],
) -> pd.DataFrame:
    source = pd.DataFrame(registrations)
    matches = []
    for target in targets.itertuples(index=False):
        if source.empty:
            pool = source
        else:
            pool = source[
                source.chamber.eq(target.chamber)
                & source.district.eq(int(target.district))
            ]
        def score_pool(candidate_pool: pd.DataFrame) -> list[tuple]:
            grouped = []
            for provider_candidate, group in candidate_pool.groupby("provider_candidate"):
                score = candidate_score(target.candidate, provider_candidate)
                grouped.append((
                    score, str(provider_candidate),
                    sorted(set(group.provider_identity.astype(str))),
                    sorted(set(group.source_path.astype(str))),
                ))
            return grouped

        grouped = score_pool(pool) if not pool.empty else []
        grouped.sort(reverse=True)
        best = grouped[0] if grouped else (0.0, "", [], [])
        second = grouped[1][0] if len(grouped) > 1 else 0.0
        margin = float(best[0] - second)
        accepted = bool(best[2] and best[0] >= 75.0 and margin >= 4.0)
        match_scope = "exact_office_district"
        if not accepted and not source.empty:
            # The filer ID follows the person/committee when a candidate
            # changes district or legislative chamber.  Never borrow a
            # registration created after the target election.
            continuity = source.copy()
            continuity["registration_year"] = pd.to_numeric(
                continuity.provider_identity.astype(str).str.extract(
                    r"legacy:C(\d{4})", expand=False
                ), errors="coerce",
            )
            continuity = continuity[
                continuity.registration_year.le(int(target.cycle))
            ]
            fallback = score_pool(continuity)
            fallback.sort(reverse=True)
            fallback_best = fallback[0] if fallback else (0.0, "", [], [])
            fallback_second = fallback[1][0] if len(fallback) > 1 else 0.0
            fallback_margin = float(fallback_best[0] - fallback_second)
            if (
                fallback_best[2] and fallback_best[0] >= 94.0
                and fallback_margin >= 4.0
            ):
                best = fallback_best
                margin = fallback_margin
                grouped = fallback
                accepted = True
                match_scope = "predating_filer_name_identity_continuity"
        matches.append({
            "state": "GA", "cycle": int(target.cycle),
            "chamber": target.chamber, "district": int(target.district),
            "party": target.party, "candidate": target.candidate,
            "provider_candidate": best[1],
            "provider_identity": "|".join(best[2]),
            "candidate_filer_id": "|".join(
                identity.removeprefix("legacy:") for identity in best[2]
            ),
            "campaign_id": "", "committee_name": "",
            "source_path": ";".join(best[3]), "match_score": float(best[0]),
            "match_margin": margin, "candidates_considered": len(grouped),
            "match_scope": match_scope,
            "match_status": "accepted_automatic" if accepted else "review_required",
        })
    return pd.DataFrame(matches)


def acquire_ga_legacy_registrations(
    targets: pd.DataFrame, timeout: int, workers: int,
) -> tuple[list[dict], list[dict]]:
    """Acquire exact legacy name-search and registration-detail evidence."""
    if targets.empty:
        return [], []
    target_names = sorted(set(targets.candidate.astype(str)))

    def fetch(candidate: str) -> tuple[list[tuple[Path, str, dict]], Path | None]:
        first, last, _ = person_parts(candidate)
        given_names = [first, *GA_GIVEN_NAME_SEARCH_ALIASES.get(first, ())]
        queries = [
            (given_name, last) for given_name in given_names
        ] + [
            (given_name, "") for given_name in given_names
        ]
        local = session_with_retries()
        artifacts = []
        selected_response = None
        selected_event = ""
        best_score = 0.0
        try:
            for first_query, last_query in queries:
                params = {
                    "CommitteeName": "", "FirstName": first_query.title(),
                    "LastName": last_query.title(), "Method": "0",
                }
                response = local.get(
                    GA_LEGACY_CANDIDATE_SEARCH_URL, params=params, timeout=timeout
                )
                response.raise_for_status()
                query_key = json.dumps(params, sort_keys=True, separators=(",", ":"))
                query_hash = hashlib.sha256(query_key.encode("utf-8")).hexdigest()[:16]
                path = RAW / "GA" / "legacy_candidate_search_v1" / f"{query_hash}.html"
                write_immutable_bytes(path, response.content)
                artifacts.append((path, response.url, params))
                rows = parse_ga_legacy_candidate_search(response.content)
                scored = sorted(
                    [
                        candidate_score(candidate, row["provider_candidate"]),
                        row["event_target"],
                    ]
                    for row in rows
                )
                scored.sort(reverse=True)
                if scored and scored[0][0] > best_score:
                    best_score, selected_event = scored[0]
                    selected_response = response
                if best_score >= 95.0:
                    break
            if selected_response is None or best_score < 75.0:
                return artifacts, None
            data = webform_hidden(selected_response.content)
            data.update({"__EVENTTARGET": selected_event, "__EVENTARGUMENT": ""})
            detail = local.post(
                selected_response.url, data=data, timeout=timeout,
                allow_redirects=True,
            )
            detail.raise_for_status()
            detail_hash = hashlib.sha256(detail.url.encode("utf-8")).hexdigest()[:16]
            detail_path = (
                RAW / "GA" / "legacy_candidate_details_v1" / f"{detail_hash}.html"
            )
            write_immutable_bytes(detail_path, detail.content)
            return artifacts, detail_path
        finally:
            local.close()

    all_artifacts, detail_paths = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, candidate): candidate for candidate in target_names}
        for future in as_completed(futures):
            artifacts, detail_path = future.result()
            all_artifacts.extend(artifacts)
            if detail_path is not None:
                detail_paths.append(detail_path)
    manifests = []
    for path, url, params in all_artifacts:
        manifests.append(source_manifest_row(
            path, state="GA", cycle=0, kind="legacy_candidate_name_search",
            provider="Georgia Government Transparency and Campaign Finance Commission",
            source_url=url, record_count=len(
                parse_ga_legacy_candidate_search(path.read_bytes())
            ), request_parameters=params,
            authoritative_scope="official legacy candidate-name search results",
        ))
    registrations = []
    for path in sorted(set(detail_paths)):
        parsed = parse_ga_legacy_candidate_detail(path.read_bytes())
        for row in parsed:
            registrations.append({**row, "source_path": relative(path)})
        manifests.append(source_manifest_row(
            path, state="GA", cycle=0, kind="legacy_candidate_registration_detail",
            provider="Georgia Government Transparency and Campaign Finance Commission",
            source_url="https://media.ethics.ga.gov/search/Campaign/Campaign_Name.aspx",
            record_count=len(parsed), request_parameters={"selection": "name-search postback"},
            authoritative_scope=(
                "official legacy filer ID, candidate name, legislative office, "
                "district, registration status, and report-list status"
            ),
        ))
    return manifests, registrations


def parse_ga_recordsearch_candidate_response(content: bytes) -> list[dict]:
    payload = json.loads(content.decode("utf-8-sig"))
    if payload.get("succeeded") is not True:
        raise RuntimeError("Georgia Record Search candidate query did not succeed")
    data = payload.get("data") or {}
    items = data.get("items") or []
    if not isinstance(items, list):
        raise RuntimeError("Georgia Record Search candidate items were not a list")
    return items


def ga_recordsearch_registration_scope(row: dict) -> tuple[int | None, str | None, int | None, str | None]:
    cycle_match = re.search(
        r"\b(20\d{2})\b",
        str(row.get("electionCycleName") or row.get("filingCycleName") or ""),
    )
    cycle = int(cycle_match.group(1)) if cycle_match else None
    office = str(row.get("office") or "").strip().lower()
    chamber = (
        "house" if office == "state representative"
        else "senate" if office == "state senator" else None
    )
    district_match = re.search(r"\d+", str(row.get("districtName") or ""))
    district = int(district_match.group()) if district_match else None
    party = {
        "DEM": "D", "DEMOCRAT": "D", "DEMOCRATIC": "D",
        "REP": "R", "REPUBLICAN": "R",
    }.get(str(row.get("politicalPartyCode") or row.get("politicalParty") or "").upper())
    return cycle, chamber, district, party


def match_ga_recordsearch_registrations(
    targets: pd.DataFrame, registrations: list[dict],
) -> pd.DataFrame:
    """Match official registrations at exact cycle/office/district/party scope."""
    scoped_rows = []
    for row in registrations:
        cycle, chamber, district, party = ga_recordsearch_registration_scope(row)
        filer_id = str(row.get("filerEntityId") or "").strip()
        if None in {cycle, chamber, district, party} or not filer_id:
            continue
        provider_candidate = str(row.get("filerName") or "").strip()
        if not provider_candidate:
            provider_candidate = " ".join(
                str(row.get(field) or "").strip()
                for field in ("candidateFirstName", "candidateMiddleName", "candidateLastName")
            ).strip()
        scoped_rows.append({
            "cycle": cycle, "chamber": chamber, "district": district,
            "party": party, "provider_candidate": provider_candidate,
            "provider_identity": f"recordsearch:{filer_id}",
            "committee_name": str(row.get("committeeName") or "").strip(),
            "source_reported_total": pd.to_numeric(
                row.get("totalContributions"), errors="coerce"
            ),
            "source_path": str(row.get("_source_path") or ""),
        })
    source = pd.DataFrame(scoped_rows)
    matches = []
    for target in targets.itertuples(index=False):
        if source.empty:
            pool = source
        else:
            pool = source[
                source.cycle.between(max(2016, int(target.cycle) - 2), int(target.cycle))
                & source.chamber.eq(target.chamber)
                & source.district.eq(int(target.district))
                & source.party.eq(target.party)
            ].sort_values("cycle", ascending=False).drop_duplicates("provider_identity")
        def score_pool(candidate_pool: pd.DataFrame) -> list[tuple]:
            scored = []
            for row in candidate_pool.itertuples(index=False):
                score = max(
                    candidate_score(target.candidate, row.provider_candidate),
                    candidate_identity_score(
                        target.candidate, row.provider_candidate, row.committee_name
                    ),
                )
                scored.append((
                    score, row.provider_identity, row.provider_candidate,
                    row.committee_name, row.source_path, int(row.cycle),
                    row.source_reported_total,
                ))
            return scored

        scored = score_pool(pool)
        scored.sort(reverse=True)
        best = scored[0] if scored else (0.0, "", "", "", "", 0, pd.NA)
        second = scored[1][0] if len(scored) > 1 else 0.0
        margin = float(best[0] - second)
        accepted = bool(best[1] and best[0] >= 75.0 and margin >= 4.0)
        match_scope = "exact_cycle_office_district_party"
        if not accepted and not source.empty:
            # A Record Search filer ID remains attached to the person even
            # after redistricting or an office change.  Same-party identity
            # continuity may look backward two years, never forward.
            continuity = source[
                source.cycle.between(
                    max(2016, int(target.cycle) - 2), int(target.cycle)
                )
                & source.party.eq(target.party)
            ].sort_values("cycle", ascending=False).drop_duplicates(
                "provider_identity"
            )
            fallback = score_pool(continuity)
            fallback.sort(reverse=True)
            fallback_best = (
                fallback[0] if fallback
                else (0.0, "", "", "", "", 0, pd.NA)
            )
            fallback_second = fallback[1][0] if len(fallback) > 1 else 0.0
            fallback_margin = float(fallback_best[0] - fallback_second)
            if (
                fallback_best[1] and fallback_best[0] >= 94.0
                and fallback_margin >= 4.0
            ):
                best = fallback_best
                margin = fallback_margin
                scored = fallback
                accepted = True
                match_scope = "prior_or_current_cycle_name_party_identity_continuity"
        matches.append({
            "state": "GA", "cycle": int(target.cycle),
            "chamber": target.chamber, "district": int(target.district),
            "party": target.party, "candidate": target.candidate,
            "provider_candidate": best[2], "provider_identity": best[1],
            "candidate_filer_id": best[1].removeprefix("recordsearch:"),
            "campaign_id": "", "committee_name": best[3],
            "source_path": best[4], "match_score": float(best[0]),
            "registration_cycle": best[5], "source_reported_total": best[6],
            "match_margin": margin, "candidates_considered": len(scored),
            "match_scope": match_scope,
            "match_status": "accepted_automatic" if accepted else "review_required",
        })
    return pd.DataFrame(matches)


def acquire_ga(timeout: int, workers: int, completion_only: bool) -> None:
    """Acquire targeted official current and legacy candidate registrations."""
    targets = candidate_universe("GA", prefer_final_names=True)
    if completion_only:
        review_path = ROOT / "data/processed/finance/southern_candidate_cycle_finance_review.csv"
        if review_path.exists():
            review = pd.read_csv(review_path, low_memory=False)
            review = review[
                review.state.eq("GA")
                & review.finance_observation_status.eq(
                    "unknown_candidate_transaction_identity_unresolved"
                )
            ][["state", "cycle", "chamber", "district", "party"]]
            targets = targets.merge(
                review, on=["state", "cycle", "chamber", "district", "party"],
                how="inner", validate="one_to_one",
            )
    modern_targets = targets.copy()
    legacy_targets = targets[targets.cycle.lt(2022)].copy()
    query_terms = sorted({
        token
        for candidate in modern_targets.candidate
        for token in person_parts(candidate)[:2]
        if len(token) >= 3
    })
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://recordsearch.ethics.ga.gov",
        "Referer": "https://recordsearch.ethics.ga.gov/",
    }

    def fetch(query: str) -> tuple[str, Path, bytes, bool]:
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
        path = RAW / "GA" / "recordsearch_candidate_search_v1" / f"{query_hash}.json"
        if path.exists():
            return query, path, path.read_bytes(), True
        local = session_with_retries()
        try:
            response = local.post(
                GA_RECORDSEARCH_CANDIDATE_URL,
                json=ga_recordsearch_candidate_payload(query),
                headers=headers, timeout=timeout,
            )
            if not response.ok:
                error_path = (
                    RAW / "GA" / "recordsearch_candidate_search_v1" / "errors"
                    / f"{query_hash}.json"
                )
                write_immutable_bytes(error_path, response.content)
                return query, error_path, response.content, False
            parse_ga_recordsearch_candidate_response(response.content)
            write_immutable_bytes(path, response.content)
            return query, path, response.content, True
        finally:
            local.close()

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, query): query for query in query_terms}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item[0])

    registrations, manifests = [], []
    for query, path, content, succeeded in results:
        items = parse_ga_recordsearch_candidate_response(content) if succeeded else []
        for item in items:
            registrations.append({**item, "_source_path": relative(path)})
        manifests.append(source_manifest_row(
            path, state="GA", cycle=0, kind="recordsearch_candidate_query",
            provider="Georgia Government Transparency and Campaign Finance Commission",
            source_url=GA_RECORDSEARCH_CANDIDATE_URL, record_count=len(items),
            request_parameters=ga_recordsearch_candidate_payload(query),
            authoritative_scope=(
                "official candidate filer identity, election cycle, legislative "
                "office, district, party, and committee"
            ),
            ingest_status="acquired_parsed" if succeeded else "rejected_provider_response",
        ))
    modern_matches = match_ga_recordsearch_registrations(
        modern_targets, registrations
    )
    legacy_manifests, legacy_registrations = acquire_ga_legacy_registrations(
        legacy_targets, timeout, workers
    )
    manifests.extend(legacy_manifests)
    legacy_matches = match_ga_legacy_registrations(
        legacy_targets, legacy_registrations
    )
    matches = pd.concat(
        [modern_matches, legacy_matches], ignore_index=True, sort=False
    )
    coverage_rows = []
    for cycle, group in matches.groupby("cycle", sort=True):
        accepted = int(group.match_status.eq("accepted_automatic").sum())
        coverage_rows.append({
            "state": "GA", "cycle": int(cycle),
            "target_candidates": len(group), "matched_candidates": accepted,
            "match_coverage": accepted / len(group) if len(group) else 0.0,
            "selected_report_details": 0,
            "acquisition_status": (
                "targeted_recordsearch_candidate_registration"
                if int(cycle) >= 2022 else
                "targeted_legacy_candidate_registration"
            ),
        })

    existing_manifest = pd.DataFrame()
    if MANIFEST.exists():
        current = pd.read_csv(MANIFEST, low_memory=False)
        existing_manifest = current[current.state.eq("GA")].copy()
    combined_manifest = pd.concat(
        [existing_manifest, pd.DataFrame(manifests)], ignore_index=True, sort=False
    ).drop_duplicates("source_file_id", keep="last")
    upsert_state_csv(MANIFEST, combined_manifest, "GA")
    upsert_state_csv(MATCH_AUDIT, matches, "GA")
    upsert_state_csv(COVERAGE, pd.DataFrame(coverage_rows), "GA")
    print(
        f"GA: {int(matches.match_status.eq('accepted_automatic').sum())}/"
        f"{len(matches)} targeted registrations accepted from "
        f"{len(results)} current-system queries and "
        f"{len(legacy_registrations)} legacy registration rows",
        flush=True,
    )


def parse_ky_candidate_index(content: bytes, chamber: str) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    rows = []
    for tr in soup.select("table tbody tr, table tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        link = tr.select_one("a[href*='/CandidateSearch/CandidateReports/']")
        if len(cells) < 10 or link is None:
            continue
        district_match = re.search(r"(\d+)\s*(?:st|nd|rd|th)?\s+District", cells[3], re.I)
        candidate_id = re.search(r"/CandidateReports/(\d+)", link.get("href", ""))
        if district_match is None or candidate_id is None:
            continue
        rows.append({
            "candidate": link.get_text(" ", strip=True), "chamber": chamber,
            "district": int(district_match.group(1)), "office": cells[1],
            "committee_status": cells[2], "election_date": cells[4],
            "election_type": cells[5], "total_receipts": money(cells[6]),
            "total_expenses": money(cells[7]), "signature_date": cells[8],
            "approval_date": cells[9], "candidate_id": candidate_id.group(1),
            "candidate_report_url": urljoin(KY_BASE, link["href"]),
        })
    return rows


def match_simple_candidates(
    targets: pd.DataFrame, source: pd.DataFrame, cycle: int, state: str,
    *, require_party: bool = False,
) -> pd.DataFrame:
    matches = []
    cycle_targets = targets[targets.cycle.eq(cycle)]
    for target in cycle_targets.itertuples(index=False):
        pool = source[
            source.chamber.eq(target.chamber)
            & source.district.eq(target.district)
        ]
        if require_party and "party" in pool:
            pool = pool[pool.party.eq(target.party)]
        scored = sorted([
            (
                candidate_score(target.candidate, row.candidate),
                str(row.candidate), str(getattr(row, "provider_id", "")),
                str(getattr(row, "committee_id", "")),
            ) for row in pool.itertuples(index=False)
        ], reverse=True)
        best = scored[0] if scored else (0.0, "", "", "")
        second = scored[1][0] if len(scored) > 1 else 0.0
        margin = float(best[0] - second)
        accepted = bool(best[1] and best[0] >= 88.0 and margin >= 4.0)
        matches.append({
            "state": state, "cycle": cycle, "chamber": target.chamber,
            "district": target.district, "party": target.party,
            "candidate": target.candidate, "provider_candidate": best[1],
            "provider_identity": best[2], "candidate_filer_id": best[2],
            "campaign_id": best[3], "match_score": best[0],
            "match_margin": margin, "candidates_considered": len(scored),
            "match_status": "accepted_automatic" if accepted else "review_required",
        })
    return pd.DataFrame(matches)


def match_ky_candidate_registrations(
    targets: pd.DataFrame, source: pd.DataFrame, cycle: int,
) -> pd.DataFrame:
    """Match KREF registrations after collapsing duplicate rows by person.

    KREF can expose both a legacy and a migrated registration for one person.
    Treating those IDs as competing people creates a false zero-point margin.
    The displayed first/last identity is therefore the ambiguity unit, while
    the selected registration remains a single auditable provider ID.
    """
    matches = []
    cycle_targets = targets[targets.cycle.eq(cycle)]
    for target in cycle_targets.itertuples(index=False):
        pool = source[
            source.chamber.eq(target.chamber)
            & source.district.eq(target.district)
            & source.cycle.eq(cycle)
        ].copy()
        people: list[tuple[float, float, pd.Series]] = []
        if not pool.empty:
            pool["person_key"] = pool.candidate.map(
                lambda value: "|".join(person_parts(value)[:2])
            )
            for _, registrations in pool.groupby("person_key", dropna=False):
                ranked = []
                for _, registration in registrations.iterrows():
                    identity_score = max(
                        candidate_score(target.candidate, registration.candidate),
                        candidate_identity_score(
                            target.candidate, registration.candidate
                        ),
                    )
                    full_name_score = float(fuzz.ratio(
                        " ".join(normalized_tokens(target.candidate)),
                        " ".join(normalized_tokens(registration.candidate)),
                    ))
                    is_general = str(registration.election_type).lower() == "general"
                    ranked.append((
                        int(is_general), full_name_score, identity_score,
                        int(pd.notna(registration.total_receipts)), registration,
                    ))
                selected = max(ranked, key=lambda item: item[:4])
                people.append((selected[2], selected[1], selected[4]))
        people.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best = people[0] if people else (0.0, 0.0, None)
        second_score = people[1][0] if len(people) > 1 else 0.0
        margin = float(best[0] - second_score)
        registration = best[2]
        accepted = bool(
            registration is not None and best[0] >= 94.0 and margin >= 4.0
        )
        provider_candidate = (
            str(registration.candidate) if registration is not None else ""
        )
        provider_id = (
            str(registration.candidate_id) if registration is not None else ""
        )
        matches.append({
            "state": "KY", "cycle": cycle, "chamber": target.chamber,
            "district": target.district, "party": target.party,
            "candidate": target.candidate,
            "provider_candidate": provider_candidate,
            "provider_identity": provider_id, "candidate_filer_id": provider_id,
            "campaign_id": provider_id, "match_score": best[0],
            "match_margin": margin, "candidates_considered": len(people),
            "match_status": "accepted_automatic" if accepted else "review_required",
            "match_method": (
                "same_cycle_general_registration" if registration is not None
                and str(registration.election_type).lower() == "general"
                else "same_cycle_primary_registration" if registration is not None
                else "no_compatible_registration"
            ),
            "adjudication_id": "",
        })
    return pd.DataFrame(matches)


def apply_ky_identity_adjudications(
    matches: pd.DataFrame, source: pd.DataFrame,
) -> pd.DataFrame:
    if not FINANCE_IDENTITY_ADJUDICATIONS.exists():
        return matches
    decisions = pd.read_csv(FINANCE_IDENTITY_ADJUDICATIONS, dtype=str).fillna("")
    decisions = decisions[
        decisions.state_code.eq("KY") & decisions.review_status.eq("approved")
    ].copy()
    if decisions.empty:
        return matches
    required_evidence = [
        "adjudication_id", "provider_identity", "evidence_source_path",
        "evidence_source_url", "evidence_quote", "rationale", "reviewer",
    ]
    for decision in decisions.itertuples(index=False):
        if any(not str(getattr(decision, column, "")).strip() for column in required_evidence):
            raise RuntimeError(
                f"KY adjudication lacks required evidence: {decision.adjudication_id}"
            )
        cycle_start = int(decision.cycle_start)
        cycle_end = int(decision.cycle_end)
        scoped_cycles = sorted(
            cycle for cycle in matches.cycle.astype(int).unique()
            if cycle_start <= cycle <= cycle_end
        )
        if not scoped_cycles:
            continue
        target_mask = (
            matches.cycle.between(cycle_start, cycle_end)
            & matches.chamber.eq(decision.chamber)
            & matches.district.astype(int).eq(int(decision.district))
            & matches.party.eq(decision.party)
        )
        target_indexes = matches.index[target_mask]
        if len(target_indexes) != len(scoped_cycles):
            raise RuntimeError(
                f"KY adjudication scope drift: {decision.adjudication_id}"
            )
        for index in target_indexes:
            target = matches.loc[index]
            if max(
                candidate_score(target.candidate, decision.candidate_name),
                candidate_identity_score(target.candidate, decision.candidate_name),
            ) < 94.0:
                raise RuntimeError(
                    f"KY adjudication candidate drift: {decision.adjudication_id}"
                )
            provider = source[
                source.cycle.eq(int(target.cycle))
                & source.chamber.eq(target.chamber)
                & source.district.eq(int(target.district))
                & source.candidate_id.astype(str).eq(str(decision.provider_identity))
            ]
            if len(provider) != 1:
                raise RuntimeError(
                    f"KY adjudication provider identity is not unique in scope: "
                    f"{decision.adjudication_id}"
                )
            row = provider.iloc[0]
            if (
                target.match_status == "accepted_automatic"
                and str(target.provider_identity) != str(decision.provider_identity)
            ):
                raise RuntimeError(
                    f"KY adjudication conflicts with automatic match: "
                    f"{decision.adjudication_id}"
                )
            matches.loc[index, [
                "provider_candidate", "provider_identity", "candidate_filer_id",
                "campaign_id", "match_status", "match_method", "adjudication_id",
            ]] = [
                row.candidate, str(row.candidate_id), str(row.candidate_id),
                str(row.candidate_id), "accepted_manual_adjudication",
                "approved_identity_adjudication", decision.adjudication_id,
            ]
    return matches


def acquire_ky(timeout: int, workers: int) -> None:
    targets = candidate_universe("KY", prefer_final_names=True)
    session = session_with_retries()
    manifests, matches_all, coverage_rows = [], [], []
    try:
        for cycle in sorted(targets.cycle.unique()):
            source_rows = []
            date_value = KY_ELECTION_DATES[int(cycle)] + " 12:00:00 AM"
            office_map = {
                "house": "STATE REPRESENTATIVE",
                "senate": "STATE SENATOR (ODD)" if cycle % 4 == 0 else "STATE SENATOR (EVEN)",
            }
            for chamber, office in office_map.items():
                params = {
                    "ElectionDate": date_value, "ElectionType": "GENERAL",
                    "OfficeSought": office, "ExemptionStatus": "All",
                    "pageIndex": 0, "pageSize": 1000, "totalRecord": 1000,
                }
                path = RAW / "KY" / f"{cycle}_{chamber}_candidate_finance_index.html"
                if not path.exists():
                    response = session.get(
                        urljoin(KY_BASE, "CandidateSearch"), params=params, timeout=timeout
                    )
                    response.raise_for_status()
                    write_immutable_bytes(path, response.content)
                parsed = parse_ky_candidate_index(path.read_bytes(), chamber)
                source_rows.extend({
                    **row, "cycle": int(cycle),
                    "source_path": relative(path),
                } for row in parsed)
                manifests.append(source_manifest_row(
                    path, state="KY", cycle=int(cycle), kind=f"{chamber}_candidate_index",
                    provider="Kentucky Registry of Election Finance",
                    source_url=urljoin(KY_BASE, "CandidateSearch"),
                    record_count=len(parsed), request_parameters=params,
                    authoritative_scope=(
                        "official candidate election registration and total campaign "
                        "receipts and expenses"
                    ),
                ))
            source = pd.DataFrame(source_rows)
            source["provider_id"] = source.candidate_id
            source["committee_id"] = source.candidate_id
            preliminary = match_ky_candidate_registrations(
                targets, source, int(cycle)
            )
            unresolved = preliminary[
                ~preliminary.match_status.eq("accepted_automatic")
            ]
            search_path = (
                RAW / "KY" / f"{cycle}_unresolved_candidate_name_searches_v1.jsonl"
            )
            if search_path.exists():
                search_items = [
                    json.loads(line) for line in search_path.read_text(
                        encoding="utf-8"
                    ).splitlines() if line.strip()
                ]
            else:
                query_specs = []
                for target in unresolved.itertuples(index=False):
                    first, last, _ = person_parts(target.candidate)
                    variants = {(first, last)} | {
                        (first, fragment) for fragment in
                        plausible_concatenated_surname_fragments(target.candidate)
                    }
                    for query_first, query_last in sorted(variants):
                        if query_first and query_last:
                            query_specs.append({
                                "target": {
                                    "cycle": int(cycle), "chamber": target.chamber,
                                    "district": int(target.district),
                                    "party": target.party,
                                    "candidate": target.candidate,
                                },
                                "params": {
                                    "FirstName": query_first,
                                    "LastName": query_last, "pageIndex": 0,
                                    "pageSize": 1000, "totalRecord": 1000,
                                },
                            })

                def fetch_name_search(spec: dict) -> dict:
                    local_session = session_with_retries()
                    try:
                        response = local_session.get(
                            urljoin(KY_BASE, "CandidateSearch"),
                            params=spec["params"], timeout=timeout,
                        )
                        response.raise_for_status()
                        return {
                            **spec, "source_url": response.url,
                            "retrieved_at_utc": datetime.now(timezone.utc).replace(
                                microsecond=0
                            ).isoformat(),
                            "content_base64": base64.b64encode(
                                response.content
                            ).decode("ascii"),
                        }
                    finally:
                        local_session.close()

                search_items = []
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [pool.submit(fetch_name_search, spec) for spec in query_specs]
                    for future in as_completed(futures):
                        search_items.append(future.result())
                search_items.sort(key=lambda item: (
                    item["target"]["chamber"], item["target"]["district"],
                    item["target"]["party"], item["params"]["FirstName"],
                    item["params"]["LastName"],
                ))
                content = "".join(
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
                    for item in search_items
                ).encode("utf-8")
                write_immutable_bytes(search_path, content)

            fallback_rows = []
            for item in search_items:
                chamber = item["target"]["chamber"]
                for row in parse_ky_candidate_index(
                    base64.b64decode(item["content_base64"]), chamber
                ):
                    election_year = pd.to_datetime(
                        row["election_date"], errors="coerce"
                    ).year
                    if election_year == int(cycle):
                        fallback_rows.append({
                            **row, "cycle": int(cycle),
                            "source_path": relative(search_path),
                        })
            if fallback_rows:
                source = pd.concat(
                    [source, pd.DataFrame(fallback_rows)], ignore_index=True,
                    sort=False,
                ).drop_duplicates(
                    ["cycle", "chamber", "district", "candidate_id"],
                    keep="first",
                )
            manifests.append(source_manifest_row(
                search_path, state="KY", cycle=int(cycle),
                kind="targeted_candidate_name_searches",
                provider="Kentucky Registry of Election Finance",
                source_url=urljoin(KY_BASE, "CandidateSearch"),
                record_count=len(search_items),
                request_parameters={
                    "selection": "unresolved modeled candidates; exact name and "
                    "conservative compound-surname discovery fragments"
                },
                authoritative_scope=(
                    "official candidate registrations used only within the exact "
                    "modeled cycle, legislative chamber, and district"
                ),
            ))
            matches = match_ky_candidate_registrations(targets, source, int(cycle))
            matches = apply_ky_identity_adjudications(matches, source)
            matches_all.append(matches)
            accepted = int(matches.match_status.str.startswith("accepted_").sum())
            coverage_rows.append({
                "state": "KY", "cycle": int(cycle),
                "target_candidates": len(matches), "matched_candidates": accepted,
                "match_coverage": accepted / len(matches) if len(matches) else 0.0,
                "selected_report_details": 0,
                "acquisition_status": "candidate_election_totals_acquired",
            })
            print(f"KY {cycle}: {accepted}/{len(matches)} candidates", flush=True)
    finally:
        session.close()
    upsert_state_csv(MANIFEST, pd.DataFrame(manifests), "KY")
    upsert_state_csv(MATCH_AUDIT, pd.concat(matches_all, ignore_index=True), "KY")
    upsert_state_csv(COVERAGE, pd.DataFrame(coverage_rows), "KY")


def parse_ms_candidate_details(content: bytes) -> dict:
    soup = BeautifulSoup(content, "html.parser")
    office_rows, filings = [], []
    tables = soup.select("table")
    for table in tables:
        caption = table.select_one("caption")
        title = caption.get_text(" ", strip=True).upper() if caption else ""
        if "OFFICE HISTORY" in title:
            for tr in table.select("tbody tr"):
                cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
                if len(cells) >= 4:
                    office_rows.append({
                        "party": cells[0], "office_type": cells[1],
                        "office_name": cells[2], "election_year": cells[3],
                    })
        if "FILING HISTORY" in title:
            for tr in table.select("tbody tr"):
                cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
                link = tr.select_one("a[data-val]")
                if len(cells) >= 3 and link is not None:
                    filings.append({
                        "date_filed": cells[0], "report_name": cells[1],
                        "status": cells[2], "filing_id": link.get("data-val"),
                    })
    heading = soup.select_one("#theCandidTemplate1, h1, h2")
    return {
        "provider_candidate": heading.get_text(" ", strip=True) if heading else "",
        "office_history": office_rows, "filings": filings,
    }


def select_ms_cycle_filings(filings: list[dict], cycle: int) -> list[dict]:
    frame = pd.DataFrame(filings)
    if frame.empty:
        return []
    frame["filed"] = pd.to_datetime(frame.date_filed, errors="coerce")
    frame["name_lower"] = frame.report_name.str.lower()
    frame = frame[~frame.name_lower.str.contains("48 hour", na=False)].copy()
    selected = []
    for report_year in (cycle - 1, cycle):
        start = pd.Timestamp(report_year, 10, 1)
        end = pd.Timestamp(report_year + 1, 2, 15)
        pool = frame[frame.filed.between(start, end)].copy()
        if pool.empty:
            # January filings generally summarize the prior calendar year;
            # never reuse one as the current year's fallback.
            pool = frame[frame.filed.between(
                pd.Timestamp(report_year, 3, 1), pd.Timestamp(report_year, 12, 31)
            )].copy()
        if pool.empty:
            continue
        pool["amended"] = pool.name_lower.str.contains("amend", na=False)
        chosen = pool.sort_values(["filed", "amended"]).iloc[-1].to_dict()
        chosen["summary_year"] = report_year
        selected.append(chosen)
    return selected


def acquire_ms(timeout: int, workers: int) -> None:
    targets = candidate_universe("MS")
    if targets.empty:
        return
    # The first acquisition predated the 2023 election rows in the warehouse.
    # Acquire the newest not-yet-indexed cycle and retain prior-cycle evidence
    # in the state-level audit tables below.
    cycle = int(targets.cycle.max())
    targets = targets[targets.cycle.eq(cycle)].copy()
    session = session_with_retries()
    manifests, source_rows = [], []
    try:
        for chamber, office in (("house", "House"), ("senate", "Senate")):
            payload = {
                "DistrictType": "Legislative", "DistrictName": office,
                "ElectionYear": str(cycle), "DistrictNumber": "",
            }
            path = RAW / "MS" / f"{cycle}_{chamber}_candidate_index.json"
            if not path.exists():
                response = session.post(
                    MS_SERVICE + "/DistrictSearch", json=payload,
                    headers={
                        "Referer": (
                            "https://cfportal.sos.ms.gov/online/portal/cf/"
                            "page/cf-search/Portal.aspx"
                        )
                    }, timeout=timeout
                )
                response.raise_for_status()
                write_immutable_bytes(path, response.content)
            body = json.loads(path.read_text(encoding="utf-8-sig"))
            rows = json.loads(body["d"]).get("Table") or []
            for row in rows:
                if row.get("OrganizationType") != "Candidate":
                    continue
                source_rows.append({
                    "candidate": row["EntityName"], "chamber": chamber,
                    "district": 0, "provider_id": row["EntityId"],
                    "committee_id": row["EntityId"],
                })
            manifests.append(source_manifest_row(
                path, state="MS", cycle=cycle, kind=f"{chamber}_candidate_index",
                provider="Mississippi Secretary of State",
                source_url=MS_SERVICE + "/DistrictSearch", record_count=len(rows),
                request_parameters=payload,
                authoritative_scope="official electronic campaign-finance candidate index",
            ))
    finally:
        session.close()
    source = pd.DataFrame(source_rows)
    # The service omits district from its result rows.  Match within chamber by
    # name, then retain the district supplied by the official election panel.
    matches = []
    for target in targets.itertuples(index=False):
        pool = source[source.chamber.eq(target.chamber)]
        scored = sorted([
            (candidate_score(target.candidate, row.candidate), row.candidate, row.provider_id)
            for row in pool.itertuples(index=False)
        ], reverse=True)
        best = scored[0] if scored else (0.0, "", "")
        second = scored[1][0] if len(scored) > 1 else 0.0
        margin = float(best[0] - second)
        accepted = bool(best[2] and best[0] >= 92.0 and margin >= 5.0)
        matches.append({
            "state": "MS", "cycle": cycle, "chamber": target.chamber,
            "district": target.district, "party": target.party,
            "candidate": target.candidate, "provider_candidate": best[1],
            "provider_identity": best[2], "candidate_filer_id": best[2],
            "campaign_id": best[2], "match_score": best[0],
            "match_margin": margin, "candidates_considered": len(scored),
            "match_status": "accepted_automatic" if accepted else "review_required",
        })
    match_frame = pd.DataFrame(matches)
    accepted_ids = sorted(set(
        match_frame.loc[
            match_frame.match_status.eq("accepted_automatic"), "provider_identity"
        ]
    ))

    def fetch_detail(entity_id: str) -> tuple[str, Path, dict]:
        path = RAW / "MS" / "candidate_details" / f"{entity_id}.html"
        if not path.exists():
            local = session_with_retries()
            local.headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            try:
                response = local.get(
                    MS_DETAIL.format(entity_id=entity_id),
                    headers={
                        "Referer": (
                            "https://cfportal.sos.ms.gov/online/portal/cf/"
                            "page/cf-search/Portal.aspx"
                        )
                    }, timeout=timeout,
                )
                response.raise_for_status()
                write_immutable_bytes(path, response.content)
            finally:
                local.close()
        return entity_id, path, parse_ms_candidate_details(path.read_bytes())

    details = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as pool:
        futures = [pool.submit(fetch_detail, entity_id) for entity_id in accepted_ids]
        for future in as_completed(futures):
            entity_id, path, parsed = future.result()
            details[entity_id] = {"path": path, **parsed}

    selected = []
    for entity_id, detail in details.items():
        for filing in select_ms_cycle_filings(detail["filings"], cycle):
            selected.append({"entity_id": entity_id, **filing})

    def fetch_filing(row: dict) -> tuple[dict, Path, str]:
        filing_id = row["filing_id"]
        path = RAW / "MS" / "selected_filings" / f"{filing_id}.pdf"
        url = MS_FILING.format(filing_id=filing_id)
        if not path.exists():
            local = session_with_retries()
            local.headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            detail_url = MS_DETAIL.format(entity_id=row["entity_id"])
            try:
                local.get(detail_url, timeout=timeout)
                response = local.get(
                    url, headers={"Referer": detail_url}, timeout=timeout
                )
                response.raise_for_status()
                if not response.content.startswith(b"%PDF"):
                    raise RuntimeError(f"Mississippi filing {filing_id} was not a PDF")
                write_immutable_bytes(path, response.content)
            finally:
                local.close()
        return row, path, url

    filing_results = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as pool:
        futures = [pool.submit(fetch_filing, row) for row in selected]
        for future in as_completed(futures):
            filing_results.append(future.result())
    index_path = RAW / "MS" / f"{cycle}_matched_candidate_filing_index_v2.jsonl"
    lines = []
    for entity_id in sorted(details):
        item = details[entity_id]
        lines.append(json.dumps({
            "entity_id": entity_id, "candidate_detail_path": relative(item["path"]),
            "provider_candidate": item["provider_candidate"],
            "office_history": item["office_history"], "filings": item["filings"],
        }, ensure_ascii=False, separators=(",", ":")))
    write_immutable_bytes(index_path, ("\n".join(lines) + "\n").encode("utf-8"))
    manifests.append(source_manifest_row(
        index_path, state="MS", cycle=cycle, kind="matched_candidate_filing_index",
        provider="Mississippi Secretary of State", source_url=MS_DETAIL,
        record_count=len(details), request_parameters={"selection": "accepted modeled candidates"},
        authoritative_scope="official candidate office and filing history",
    ))
    for row, path, url in filing_results:
        manifests.append(source_manifest_row(
            path, state="MS", cycle=cycle, kind="selected_filing_pdf",
            provider="Mississippi Secretary of State", source_url=url,
            record_count=1, request_parameters={
                "entity_id": row["entity_id"], "summary_year": row["summary_year"],
                "report_name": row["report_name"],
            },
            authoritative_scope="official selected campaign-finance disclosure filing",
            ingest_status="acquired_pdf_parse_pending",
        ))
    accepted = int(match_frame.match_status.eq("accepted_automatic").sum())
    manifest_frame = pd.DataFrame(manifests)
    coverage_frame = pd.DataFrame([{
        "state": "MS", "cycle": cycle, "target_candidates": len(match_frame),
        "matched_candidates": accepted,
        "match_coverage": accepted / len(match_frame) if len(match_frame) else 0.0,
        "selected_report_details": len(filing_results),
        "acquisition_status": "selected_electronic_and_scanned_filing_pdfs_acquired",
    }])
    # upsert_state_csv intentionally replaces a whole state's rows.  Merge
    # prior Mississippi cycles explicitly so adding 2023 cannot discard the
    # already acquired 2019 audit trail.
    for path, frame in (
        (MANIFEST, manifest_frame), (MATCH_AUDIT, match_frame),
        (COVERAGE, coverage_frame),
    ):
        if path.exists():
            prior = pd.read_csv(path, dtype=str)
            prior_cycle = pd.to_numeric(prior.get("cycle"), errors="coerce")
            keep = prior[prior.state.eq("MS") & prior_cycle.ne(cycle)]
            frame = pd.concat([keep, frame], ignore_index=True, sort=False)
        upsert_state_csv(path, frame, "MS")
    print(f"MS {cycle}: {accepted}/{len(match_frame)} candidates; {len(filing_results)} filings", flush=True)


def parse_va_committee_search(content: bytes) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    rows = []
    for tr in soup.select("table tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        link = tr.select_one("a[href*='/Committee/Index/']")
        if len(cells) < 3 or link is None:
            continue
        guid = re.search(r"/Committee/Index/([^/?#]+)", link.get("href", ""))
        if guid:
            rows.append({
                "committee_name": cells[0], "candidate": cells[1],
                "committee_type": cells[2], "committee_id": guid.group(1),
                "committee_url": urljoin(VA_BASE, link["href"]),
            })
    return rows


def parse_nc_committee_identity(value: object) -> tuple[str, str]:
    """Split NC's ``COMMITTEE NAME (LAST, GIVEN)`` search display."""
    text = str(value or "").strip()
    match = re.search(r"\(([^()]*,[^()]*)\)\s*$", text)
    if not match:
        return text, text
    return text[:match.start()].strip(), match.group(1).strip()


def nc_committee_is_legislative_compatible(value: object) -> bool:
    """Exclude an explicit nonlegislative campaign returned by name search."""
    text = str(value or "").lower()
    nonlegislative = (
        "congress", " for judge", " for justice", "district attorney",
        " for da", "sheriff", "mayor", "city council", "county commissioner",
        "school board", "superior court", "court of appeals",
    )
    return not any(label in text for label in nonlegislative)


def nc_committee_identity_name(value: object) -> str:
    return "".join(
        token for token in normalized_tokens(value)
        if token not in IDENTITY_CONTEXT_STOPWORDS and not token.isdigit()
    )


def nc_targeted_search_payload(
    start: str, end: str, committee_ids: list[str], committee_names: list[str], token: str,
) -> list[tuple[str, str]]:
    return [
        ("Filter.ReceiptAll", "true"), ("Filter.ReceiptAll", "false"),
        ("Filter.ExpenditureAll", "true"), ("Filter.ExpenditureAll", "false"),
        ("Filter.CommitteeAll", "true"), ("Filter.CommitteeAll", "false"),
        ("Filter.PartyAll", "true"), ("Filter.PartyAll", "false"),
        ("Filter.OfficeAll", "true"), ("Filter.OfficeAll", "false"),
        ("Filter.CommitteeIDs", ",".join(committee_ids)),
        ("Filter.CommitteeNames", "|".join(committee_names)),
        ("Filter.CountyList", ""), ("Filter.StartDate", start),
        ("Filter.EndDate", end), ("Filter.AmountFrom", ""),
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


def acquire_nc(timeout: int, workers: int) -> None:
    """Acquire exact modeled-committee transaction batches for North Carolina."""
    targets = candidate_universe("NC", prefer_final_names=True)
    surname_frequency = (
        targets.assign(surname=targets.candidate.map(lambda value: person_parts(value)[1]))
        .groupby(["cycle", "surname"]).size().to_dict()
    )
    query_by_candidate: dict[str, set[str]] = {}
    for candidate in sorted(set(targets.candidate)):
        first, last, _ = person_parts(candidate)
        raw = strip_marks(candidate)
        right = raw.split(",", 1)[1] if "," in raw else raw
        given = next((token for token in normalized_tokens(right) if len(token) >= 3), "")
        query_by_candidate[candidate] = {query for query in (last, first, given) if query}
    query_names = sorted(set().union(*query_by_candidate.values()))

    search_path = RAW / "NC" / "modeled_candidate_committee_searches_v2.jsonl"
    search_envelopes = []
    if search_path.exists():
        for line in search_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                item["content"] = base64.b64decode(item.pop("content_base64"))
                search_envelopes.append(item)
    else:
        def fetch_search(query: str) -> tuple[str, bytes]:
            local = session_with_retries()
            try:
                response = local.get(
                    NC_BASE + "CommitteeSearch", params={
                        "handler": "Search", "name": query,
                        "useOrg": "true", "useCand": "true",
                        "useInhouse": "false", "useAcronym": "false",
                        "validateName": "true", "page": 1, "pageSize": 1000,
                    }, timeout=timeout,
                )
                response.raise_for_status()
                payload = response.json()
                if int(payload.get("Total", 0)) > len(payload.get("Data", [])):
                    raise RuntimeError(f"NC committee search truncated for {query}")
                return query, response.content
            finally:
                local.close()

        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(fetch_search, query) for query in query_names]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item[0])
        serial = []
        for query, content in results:
            serial.append(json.dumps({
                "query_name": query, "source_url": NC_BASE + "CommitteeSearch?handler=Search",
                "request_parameters": {
                    "name": query, "useOrg": True, "useCand": True, "pageSize": 1000,
                },
                "content_base64": base64.b64encode(content).decode("ascii"),
            }, ensure_ascii=False, separators=(",", ":")))
            search_envelopes.append({"query_name": query, "content": content})
        write_immutable_bytes(search_path, ("\n".join(serial) + "\n").encode("utf-8"))

    by_query = {
        item["query_name"]: json.loads(item["content"]).get("Data", [])
        for item in search_envelopes
    }
    matches = []
    for target in targets.itertuples(index=False):
        candidates = {}
        for query in query_by_candidate[target.candidate]:
            for row in by_query.get(query, []):
                candidates[str(row["OrgGroupID"])] = row
        scored = []
        for committee_id, row in candidates.items():
            committee_name, provider_candidate = parse_nc_committee_identity(row["OrgName"])
            if not nc_committee_is_legislative_compatible(committee_name):
                continue
            score = max(
                candidate_score(target.candidate, provider_candidate),
                candidate_identity_score(target.candidate, provider_candidate, committee_name),
            )
            target_surname = person_parts(target.candidate)[1]
            safe_unique_surname_committee = (
                score >= 90.0
                and surname_frequency.get((int(target.cycle), target_surname), 0) == 1
                and nc_committee_identity_name(committee_name) == target_surname
            )
            if score >= 94.0 or safe_unique_surname_committee:
                scored.append((score, committee_id, row["OrgName"], provider_candidate))
        scored.sort(reverse=True)
        top_score = scored[0][0] if scored else 0.0
        selected = [row for row in scored if row[0] >= top_score - 2.0]
        matches.append({
            "state": "NC", "cycle": int(target.cycle), "chamber": target.chamber,
            "district": int(target.district), "party": target.party,
            "candidate": target.candidate,
            "provider_candidate": "|".join(sorted({row[3] for row in selected})),
            "committee_names": "|".join(sorted({row[2] for row in selected})),
            "provider_identity": "|".join(sorted({row[1] for row in selected})),
            "candidate_filer_id": "|".join(sorted({row[1] for row in selected})),
            "campaign_id": "|".join(sorted({row[1] for row in selected})),
            "match_score": top_score, "match_margin": top_score,
            "candidates_considered": len(scored),
            "match_status": "accepted_automatic" if selected else "review_required",
        })
    match_frame = pd.DataFrame(matches)

    committee_names = {}
    for rows in by_query.values():
        for row in rows:
            committee_names[str(row["OrgGroupID"])] = str(row["OrgName"])
    batch_specs = []
    for cycle, group in match_frame[match_frame.match_status.eq("accepted_automatic")].groupby("cycle"):
        committee_ids = sorted(set(
            group.provider_identity.str.split("|").explode().dropna()
        ) - {""})
        for batch_number, offset in enumerate(range(0, len(committee_ids), 40), start=1):
            ids = committee_ids[offset:offset + 40]
            batch_specs.append({
                "cycle": int(cycle), "batch": batch_number, "committee_ids": ids,
                "committee_names": [committee_names[item] for item in ids],
            })

    def fetch_batch(spec: dict) -> tuple[dict, Path, int]:
        path = RAW / "NC" / "targeted_transactions_v3" / str(spec["cycle"]) / f"batch_{spec['batch']:03d}.csv"
        if path.exists():
            with path.open(encoding="utf-8-sig", errors="replace") as handle:
                return spec, path, max(0, sum(1 for _ in handle) - 1)
        local = session_with_retries()
        try:
            page = local.get(NC_BASE + "AdvancedSearch/", timeout=timeout)
            page.raise_for_status()
            soup = BeautifulSoup(page.text, "html.parser")
            token = soup.select_one('input[name="__RequestVerificationToken"]')
            if token is None:
                raise RuntimeError("NC search page omitted antiforgery token")
            start, end = f"01/01/{spec['cycle'] - 1}", f"12/31/{spec['cycle']}"
            result = local.post(
                NC_BASE + "AdvancedSearch",
                data=nc_targeted_search_payload(
                    start, end, spec["committee_ids"], spec["committee_names"], token["value"]
                ), timeout=timeout,
            )
            result.raise_for_status()
            result_soup = BeautifulSoup(result.text, "html.parser")
            grid, form = result_soup.select_one("#divGrid"), result_soup.select_one("#frmExport")
            export_token = form.select_one('input[name="__RequestVerificationToken"]') if form else None
            if grid is None or export_token is None:
                raise RuntimeError("NC targeted result omitted export parameters")
            exported = local.post(
                NC_BASE + "Export", data={
                    "searchParamsJson": grid.get("data-search-params", ""),
                    "__RequestVerificationToken": export_token["value"],
                }, timeout=timeout,
            )
            exported.raise_for_status()
            if not exported.content.startswith(b"Name,Street Line 1"):
                raise RuntimeError("NC targeted export returned an unexpected header")
            write_immutable_bytes(path, exported.content)
            return spec, path, max(0, exported.content.count(b"\n") - 1)
        finally:
            local.close()

    batch_results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_batch, spec) for spec in batch_specs]
        for future in as_completed(futures):
            batch_results.append(future.result())
    batch_results.sort(key=lambda item: (item[0]["cycle"], item[0]["batch"]))

    index_path = RAW / "NC" / "targeted_transaction_batches_v3.jsonl"
    write_immutable_bytes(index_path, ("".join(
        json.dumps({
            **spec, "local_path": relative(path), "record_count": count,
            "source_url": NC_BASE + "Export",
        }, ensure_ascii=False, separators=(",", ":")) + "\n"
        for spec, path, count in batch_results
    )).encode("utf-8"))

    manifests = [
        source_manifest_row(
            search_path, state="NC", cycle=0, kind="modeled_candidate_committee_search_collection",
            provider="North Carolina State Board of Elections",
            source_url=NC_BASE + "CommitteeSearch?handler=Search",
            record_count=len(search_envelopes),
            request_parameters={"selection": "modeled candidate surname and given-name queries"},
            authoritative_scope="official committee identifiers and candidate/committee display names",
        ),
        source_manifest_row(
            index_path, state="NC", cycle=0, kind="targeted_transaction_batch_index",
            provider="North Carolina State Board of Elections", source_url=NC_BASE + "Export",
            record_count=len(batch_results),
            request_parameters={"batch_size": 40},
            authoritative_scope="query lineage for exact modeled candidate committee transaction exports",
        ),
    ]
    for spec, path, count in batch_results:
        manifests.append(source_manifest_row(
            path, state="NC", cycle=spec["cycle"], kind="targeted_candidate_transactions",
            provider="North Carolina State Board of Elections", source_url=NC_BASE + "Export",
            record_count=count,
            request_parameters={
                "committee_ids": spec["committee_ids"],
                "start": f"01/01/{spec['cycle'] - 1}", "end": f"12/31/{spec['cycle']}",
            },
            authoritative_scope="all official reported receipts and expenditures for exact modeled committees and cycle window",
        ))
    coverage = []
    for cycle, group in match_frame.groupby("cycle"):
        accepted = int(group.match_status.eq("accepted_automatic").sum())
        coverage.append({
            "state": "NC", "cycle": int(cycle), "target_candidates": len(group),
            "matched_candidates": accepted, "match_coverage": accepted / len(group),
            "selected_report_details": sum(
                count for spec, _, count in batch_results if spec["cycle"] == cycle
            ),
            "acquisition_status": "exact_candidate_committee_cycle_transaction_batches_acquired",
        })
    upsert_state_csv(MANIFEST, pd.DataFrame(manifests), "NC")
    upsert_state_csv(MATCH_AUDIT, match_frame, "NC")
    upsert_state_csv(COVERAGE, pd.DataFrame(coverage), "NC")
    print(
        f"NC: {int(match_frame.match_status.eq('accepted_automatic').sum())}/"
        f"{len(match_frame)} candidates; {len(batch_results)} exact transaction batches",
        flush=True,
    )


def va_committee_chamber(name: object) -> str | None:
    text = str(name or "").lower()
    if any(word in text for word in ("delegate", "house of delegates", " for house")):
        return "house"
    if "senate" in text:
        return "senate"
    return None


def va_committee_is_compatible(name: object, chamber: str) -> bool:
    """Reject committees that explicitly identify another office."""
    text = str(name or "").lower()
    nonlegislative = (
        "governor", "lieutenant governor", "attorney general", "congress",
        "city council", "school board", "board of supervisors", "mayor",
        "sheriff", "commonwealth attorney", "county treasurer",
    )
    if any(label in text for label in nonlegislative):
        return False
    observed_chamber = va_committee_chamber(name)
    return observed_chamber is None or observed_chamber == chamber


def va_standard_committee_discovery_queries(
    candidate: object, chamber: str,
) -> set[str]:
    """Build common legal committee-title searches for an unresolved person."""
    first, last, _ = person_parts(candidate)
    if not last:
        return set()
    office = "Delegate" if chamber == "house" else "Senate"
    queries = {
        f"{last} for {office}",
        f"{last} for Virginia",
    }
    if first:
        queries.update({
            f"Friends of {first} {last}",
            f"{first} {last} for {office}",
        })
    return queries


def parse_va_committee_reports(content: bytes) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    table = soup.select_one("table")
    if table is None:
        return []
    rows = []
    for tr in table.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        link = tr.select_one("a[href*='/Report/Index/']")
        if len(cells) < 5 or link is None:
            continue
        dates = re.findall(r"\d{2}/\d{2}/\d{4}", cells[0])
        report_id = re.search(r"/Report/Index/(\d+)", link.get("href", ""))
        if len(dates) != 2 or report_id is None:
            continue
        rows.append({
            "period_start": dates[0], "period_end": dates[1],
            "amendment": cells[1], "filed": cells[2],
            "contributions_received": money(cells[3]),
            "ending_balance": money(cells[4]), "report_id": report_id.group(1),
            "report_url": urljoin(VA_BASE, link["href"]),
            "xml_url": urljoin(VA_BASE, f"Report/ReportXML/{report_id.group(1)}"),
        })
    return rows


def acquire_va(timeout: int, workers: int) -> None:
    targets = candidate_universe("VA", prefer_final_names=True)
    target_queries = {
        candidate: person_parts(candidate)[1]
        for candidate in sorted(set(targets.candidate))
    }
    query_names = sorted(set(target_queries.values()))

    def fetch_search(name: str) -> tuple[str, bytes]:
        local = session_with_retries()
        try:
            response = local.get(VA_BASE, params={
                "CommitteeName": name,
                "CommitteeType": "Candidate Campaign Committee",
            }, timeout=timeout)
            response.raise_for_status()
            return name, response.content
        finally:
            local.close()

    # v5 refreshes the immutable search collection after the 2023 Virginia
    # election rows entered the canonical candidate universe.  Reusing v4
    # silently omitted every newly loaded candidate.
    search_path = RAW / "VA" / "modeled_candidate_committee_searches_v5.jsonl"
    search_envelopes = []
    if search_path.exists():
        for line in search_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                item["content"] = base64.b64decode(item.pop("content_base64"))
                search_envelopes.append(item)
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(fetch_search, name) for name in query_names]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item[0])
        serial = []
        for name, content in results:
            serial.append(json.dumps({
                "query_name": name,
                "source_url": VA_BASE,
                "request_parameters": {
                    "CommitteeName": name,
                    "CommitteeType": "Candidate Campaign Committee",
                },
                "content_base64": base64.b64encode(content).decode("ascii"),
            }, ensure_ascii=False, separators=(",", ":")))
            search_envelopes.append({"query_name": name, "content": content})
        write_immutable_bytes(search_path, ("\n".join(serial) + "\n").encode("utf-8"))

    by_query = {
        item["query_name"]: parse_va_committee_search(item["content"])
        for item in search_envelopes
    }
    first_last_queries = {
        candidate: " ".join(part for part in person_parts(candidate)[:2] if part)
        for candidate in target_queries
    }
    first_last_results: dict[str, list[dict]] = {}
    prior_search_path = RAW / "VA" / "modeled_candidate_committee_searches_v3.jsonl"
    if prior_search_path.exists():
        prior_by_query = {}
        for line in prior_search_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                prior_by_query[item["query_name"]] = parse_va_committee_search(
                    base64.b64decode(item["content_base64"])
                )
        first_last_results = {
            candidate: prior_by_query.get(query, [])
            for candidate, query in first_last_queries.items()
        }

    # A surname-only query misses provider names whose spaced or hyphenated
    # surname was collapsed by an election source (for example Carroll Foy ->
    # carrollfoy).  Preserve a second immutable discovery collection keyed by
    # a substantive given-name token, then match reciprocally over the union.
    given_name_queries = {}
    for candidate in target_queries:
        raw = strip_marks(candidate)
        right = raw.split(",", 1)[1] if "," in raw else raw
        tokens = normalized_tokens(right)
        given_name_queries[candidate] = next(
            (token for token in tokens if len(token) >= 3), ""
        )
    discovery_queries = sorted(set(given_name_queries.values()) - {""})
    discovery_path = RAW / "VA" / "modeled_candidate_committee_searches_v6.jsonl"
    discovery_envelopes = []
    if discovery_path.exists():
        for line in discovery_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                item["content"] = base64.b64decode(item.pop("content_base64"))
                discovery_envelopes.append(item)
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(fetch_search, name) for name in discovery_queries]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item[0])
        serial = []
        for name, content in results:
            serial.append(json.dumps({
                "query_name": name, "query_kind": "given_name_discovery",
                "source_url": VA_BASE,
                "request_parameters": {
                    "CommitteeName": name,
                    "CommitteeType": "Candidate Campaign Committee",
                },
                "content_base64": base64.b64encode(content).decode("ascii"),
            }, ensure_ascii=False, separators=(",", ":")))
            discovery_envelopes.append({"query_name": name, "content": content})
        write_immutable_bytes(
            discovery_path, ("\n".join(serial) + "\n").encode("utf-8")
        )

    # The portal caps broad surname/given-name searches.  Querying the exact
    # parsed first/last pair gives candidates beyond the first result page a
    # deterministic discovery path while retaining the broad searches as
    # independent evidence.
    exact_queries = sorted(set(first_last_queries.values()) - {""})
    # v12 is keyed by the final election-warehouse display name.  Earlier
    # collections inherited concatenated VPAP aliases such as SCOTTGARRETT,
    # which suppressed otherwise exact committee discovery.
    exact_path = RAW / "VA" / "modeled_candidate_committee_searches_v12.jsonl"
    exact_envelopes = []
    if exact_path.exists():
        for line in exact_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                item["content"] = base64.b64decode(item.pop("content_base64"))
                exact_envelopes.append(item)
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(fetch_search, name) for name in exact_queries]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item[0])
        serial = []
        for name, content in results:
            serial.append(json.dumps({
                "query_name": name, "query_kind": "exact_first_last_discovery",
                "source_url": VA_BASE,
                "request_parameters": {
                    "CommitteeName": name,
                    "CommitteeType": "Candidate Campaign Committee",
                },
                "content_base64": base64.b64encode(content).decode("ascii"),
            }, ensure_ascii=False, separators=(",", ":")))
            exact_envelopes.append({"query_name": name, "content": content})
        write_immutable_bytes(
            exact_path, ("\n".join(serial) + "\n").encode("utf-8")
        )

    # Older Virginia election inputs concatenate compound or prior surnames
    # (for example BEVANSRANSONE and SCOTTGARRETT).  For unresolved candidates
    # only, query plausible prefix/suffix decompositions.  These strings are
    # discovery aids; the normal reciprocal person-name threshold still gates
    # every committee assignment.
    unresolved_targets = targets
    if MATCH_AUDIT.exists():
        prior_matches = pd.read_csv(MATCH_AUDIT, dtype=str, low_memory=False)
        prior_matches = prior_matches[
            prior_matches.state.eq("VA")
            & prior_matches.match_status.ne("accepted_automatic")
        ].copy()
        if not prior_matches.empty:
            prior_matches["cycle"] = pd.to_numeric(
                prior_matches.cycle, errors="coerce"
            )
            prior_matches["district"] = pd.to_numeric(
                prior_matches.district, errors="coerce"
            )
            unresolved_targets = targets.merge(
                prior_matches[["cycle", "chamber", "district", "party"]],
                on=["cycle", "chamber", "district", "party"],
                how="inner", validate="one_to_one",
            )
    split_queries = set()
    for candidate in sorted(set(unresolved_targets.candidate.astype(str))):
        first, last, _ = person_parts(candidate)
        for fragment in plausible_concatenated_surname_fragments(candidate):
            split_queries.add(fragment)
            if first:
                split_queries.add(f"{first} {fragment}")
    split_path = RAW / "VA" / "modeled_candidate_committee_searches_v13.jsonl"
    split_envelopes = []
    if split_path.exists():
        for line in split_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                item["content"] = base64.b64decode(item.pop("content_base64"))
                split_envelopes.append(item)
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(fetch_search, name) for name in sorted(split_queries)]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item[0])
        serial = []
        for name, content in results:
            serial.append(json.dumps({
                "query_name": name,
                "query_kind": "concatenated_surname_decomposition",
                "source_url": VA_BASE,
                "request_parameters": {
                    "CommitteeName": name,
                    "CommitteeType": "Candidate Campaign Committee",
                },
                "content_base64": base64.b64encode(content).decode("ascii"),
            }, ensure_ascii=False, separators=(",", ":")))
            split_envelopes.append({"query_name": name, "content": content})
        write_immutable_bytes(
            split_path, ("\n".join(serial) + "\n").encode("utf-8")
        )

    # Expand discovery only for candidates still unresolved after v13. This
    # captures common filing-name aliases and shorter components of collapsed
    # surnames without repeating the statewide search workload.
    expanded_queries = set()
    for candidate in sorted(set(unresolved_targets.candidate.astype(str))):
        first, last, _ = person_parts(candidate)
        for fragment in plausible_concatenated_surname_fragments(candidate):
            expanded_queries.add(fragment)
            if first:
                expanded_queries.add(f"{first} {fragment}")
        for alias in COMMON_GIVEN_NAME_EQUIVALENTS.get(first, set()) - {first}:
            expanded_queries.add(f"{alias} {last}")
            for fragment in plausible_concatenated_surname_fragments(candidate):
                expanded_queries.add(f"{alias} {fragment}")
    expanded_path = RAW / "VA" / "modeled_candidate_committee_searches_v14.jsonl"
    expanded_envelopes = []
    if expanded_path.exists():
        for line in expanded_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                item["content"] = base64.b64decode(item.pop("content_base64"))
                expanded_envelopes.append(item)
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(fetch_search, name)
                for name in sorted(expanded_queries)
            ]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item[0])
        serial = []
        for name, content in results:
            serial.append(json.dumps({
                "query_name": name,
                "query_kind": "unresolved_alias_or_surname_component",
                "source_url": VA_BASE,
                "request_parameters": {
                    "CommitteeName": name,
                    "CommitteeType": "Candidate Campaign Committee",
                },
                "content_base64": base64.b64encode(content).decode("ascii"),
            }, ensure_ascii=False, separators=(",", ":")))
            expanded_envelopes.append({"query_name": name, "content": content})
        write_immutable_bytes(
            expanded_path, ("\n".join(serial) + "\n").encode("utf-8")
        )

    # The portal's CommitteeName parameter searches legal committee titles,
    # not merely its displayed candidate-person column. Query common Virginia
    # title forms for the small unresolved set so historical committees such
    # as "Stuart for Senate" and "Wolf for Delegate" remain discoverable.
    committee_title_queries = set()
    for target in unresolved_targets.itertuples(index=False):
        committee_title_queries.update(
            va_standard_committee_discovery_queries(
                target.candidate, target.chamber
            )
        )
    title_path = RAW / "VA" / "modeled_candidate_committee_searches_v15.jsonl"
    title_envelopes = []
    if title_path.exists():
        for line in title_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                item["content"] = base64.b64decode(item.pop("content_base64"))
                title_envelopes.append(item)
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(fetch_search, name)
                for name in sorted(committee_title_queries)
            ]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item[0])
        serial = []
        for name, content in results:
            serial.append(json.dumps({
                "query_name": name,
                "query_kind": "unresolved_standard_committee_title",
                "source_url": VA_BASE,
                "request_parameters": {
                    "CommitteeName": name,
                    "CommitteeType": "Candidate Campaign Committee",
                },
                "content_base64": base64.b64encode(content).decode("ascii"),
            }, ensure_ascii=False, separators=(",", ":")))
            title_envelopes.append({"query_name": name, "content": content})
        write_immutable_bytes(
            title_path, ("\n".join(serial) + "\n").encode("utf-8")
        )

    global_candidates: list[dict] = []
    for envelope in (
        search_envelopes + discovery_envelopes + exact_envelopes
        + split_envelopes + expanded_envelopes + title_envelopes
    ):
        global_candidates.extend(parse_va_committee_search(envelope["content"]))
    for rows in first_last_results.values():
        global_candidates.extend(rows)
    global_candidates = list({
        (
            row["committee_id"], row["candidate"], row["committee_name"]
        ): row for row in global_candidates
    }.values())
    candidate_surname_index: dict[str, set[int]] = {}
    for row_index, row in enumerate(global_candidates):
        context_tokens = [
            token for token in normalized_tokens(row["committee_name"])
            if token not in IDENTITY_CONTEXT_STOPWORDS and not token.isdigit()
        ]
        tokens = normalized_tokens(row["candidate"]) + context_tokens
        for width in range(1, min(3, len(tokens)) + 1):
            for selected_tokens in combinations(tokens, width):
                for ordered_tokens in permutations(selected_tokens):
                    candidate_surname_index.setdefault(
                        "".join(ordered_tokens), set()
                    ).add(row_index)
    matches = []
    committee_targets: dict[str, list[dict]] = {}
    for target in targets.itertuples(index=False):
        scored_candidates = []
        target_last = person_parts(target.candidate)[1]
        candidate_indices = set(candidate_surname_index.get(target_last, set()))
        for fragment in plausible_concatenated_surname_fragments(target.candidate):
            candidate_indices.update(candidate_surname_index.get(fragment, set()))
        candidate_rows = (
            global_candidates[row_index]
            for row_index in candidate_indices
        )
        for row in candidate_rows:
            if not va_committee_is_compatible(row["committee_name"], target.chamber):
                continue
            score = max(
                candidate_identity_score(
                    target.candidate, row["candidate"], row["committee_name"]
                ),
                candidate_score(target.candidate, row["candidate"]),
            )
            if score >= 94.0:
                scored_candidates.append((score, row))
        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        if scored_candidates:
            top_score = scored_candidates[0][0]
            selected = [row for score, row in scored_candidates if score >= top_score - 2]
            provider_names = sorted(set(row["candidate"] for row in selected))
            committee_ids = sorted(set(row["committee_id"] for row in selected))
            for row in selected:
                committee_targets.setdefault(row["committee_id"], []).append({
                    "cycle": int(target.cycle), "chamber": target.chamber,
                    "district": int(target.district), "party": target.party,
                    "candidate": target.candidate,
                })
            status = "accepted_automatic"
        else:
            top_score, provider_names, committee_ids, status = 0.0, [], [], "review_required"
        matches.append({
            "state": "VA", "cycle": int(target.cycle), "chamber": target.chamber,
            "district": int(target.district), "party": target.party,
            "candidate": target.candidate,
            "provider_candidate": "|".join(provider_names),
            "provider_identity": "|".join(committee_ids),
            "candidate_filer_id": "|".join(committee_ids),
            "campaign_id": "|".join(committee_ids), "match_score": top_score,
            "match_margin": top_score,
            "candidates_considered": len(scored_candidates), "match_status": status,
        })
    match_frame = pd.DataFrame(matches)
    accepted_keys = set(
        match_frame.loc[match_frame.match_status.eq("accepted_automatic")]
        .provider_identity.str.split("|").explode().dropna()
    ) - {""}

    def fetch_committee(committee_id: str) -> tuple[str, bytes]:
        local = session_with_retries()
        try:
            url = urljoin(VA_BASE, f"Committee/Index/{committee_id}")
            response = local.get(url, timeout=timeout)
            response.raise_for_status()
            return committee_id, response.content
        finally:
            local.close()

    committee_path = RAW / "VA" / "matched_candidate_committee_report_indexes_v18.jsonl"
    committee_envelopes = []
    if committee_path.exists():
        for line in committee_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                item["content"] = base64.b64decode(item.pop("content_base64"))
                committee_envelopes.append(item)
    else:
        # Seed the new immutable collection from v11, then fetch only committee
        # IDs newly exposed by final-name matching.
        prior_committee_path = (
            RAW / "VA" / "matched_candidate_committee_report_indexes_v17.jsonl"
        )
        if prior_committee_path.exists():
            for line in prior_committee_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    item = json.loads(line)
                    item["content"] = base64.b64decode(item.pop("content_base64"))
                    committee_envelopes.append(item)
        existing_committee_ids = {
            item["committee_id"] for item in committee_envelopes
        }
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(fetch_committee, key)
                for key in sorted(accepted_keys - existing_committee_ids)
            ]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item[0])
        for committee_id, content in results:
            committee_envelopes.append({
                "committee_id": committee_id,
                "source_url": urljoin(VA_BASE, f"Committee/Index/{committee_id}"),
                "content": content,
            })
        committee_envelopes.sort(key=lambda item: item["committee_id"])
        serial = [json.dumps({
            "committee_id": item["committee_id"],
            "source_url": item.get(
                "source_url",
                urljoin(VA_BASE, f"Committee/Index/{item['committee_id']}"),
            ),
            "content_base64": base64.b64encode(item["content"]).decode("ascii"),
        }, separators=(",", ":")) for item in committee_envelopes]
        write_immutable_bytes(committee_path, ("\n".join(serial) + "\n").encode("utf-8"))

    selected_reports: dict[str, dict] = {}
    for envelope in committee_envelopes:
        committee_id = envelope["committee_id"]
        reports = parse_va_committee_reports(envelope["content"])
        for target in committee_targets.get(committee_id, []):
            start = pd.Timestamp(target["cycle"] - 1, 1, 1)
            end = pd.Timestamp(target["cycle"], 12, 31)
            for report in reports:
                report_start = pd.to_datetime(report["period_start"], errors="coerce")
                report_end = pd.to_datetime(report["period_end"], errors="coerce")
                if pd.notna(report_start) and pd.notna(report_end) and report_end >= start and report_start <= end:
                    selected_reports[report["report_id"]] = report

    def fetch_xml(report: dict) -> tuple[dict, Path]:
        path = RAW / "VA" / "selected_report_xml" / f"{report['report_id']}.xml"
        if not path.exists():
            local = session_with_retries()
            try:
                response = local.get(report["xml_url"], timeout=timeout)
                response.raise_for_status()
                if b"<?xml" not in response.content[:16]:
                    raise RuntimeError(f"Virginia report {report['report_id']} was not XML")
                write_immutable_bytes(path, response.content)
            finally:
                local.close()
        return report, path

    xml_results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_xml, report) for report in selected_reports.values()]
        for future in as_completed(futures):
            xml_results.append(future.result())
    manifests = [
        source_manifest_row(
            search_path, state="VA", cycle=0, kind="candidate_committee_search_collection",
            provider="Virginia Department of Elections", source_url=VA_BASE,
            record_count=len(search_envelopes),
            request_parameters={"selection": "modeled candidate names"},
            authoritative_scope="official candidate campaign committee search results",
        ),
        source_manifest_row(
            discovery_path, state="VA", cycle=0,
            kind="candidate_committee_given_name_search_collection",
            provider="Virginia Department of Elections", source_url=VA_BASE,
            record_count=len(discovery_envelopes),
            request_parameters={"selection": "modeled candidate substantive given names"},
            authoritative_scope="official candidate campaign committee search results",
        ),
        source_manifest_row(
            exact_path, state="VA", cycle=0,
            kind="candidate_committee_exact_name_search_collection",
            provider="Virginia Department of Elections", source_url=VA_BASE,
            record_count=len(exact_envelopes),
            request_parameters={"selection": "modeled candidate exact first and last names"},
            authoritative_scope="official candidate campaign committee search results",
        ),
        source_manifest_row(
            split_path, state="VA", cycle=0,
            kind="candidate_committee_concatenated_surname_search_collection",
            provider="Virginia Department of Elections", source_url=VA_BASE,
            record_count=len(split_envelopes),
            request_parameters={
                "selection": "unresolved modeled candidate surname decompositions"
            },
            authoritative_scope="official candidate campaign committee search results",
        ),
        source_manifest_row(
            expanded_path, state="VA", cycle=0,
            kind="candidate_committee_unresolved_alias_search_collection",
            provider="Virginia Department of Elections", source_url=VA_BASE,
            record_count=len(expanded_envelopes),
            request_parameters={
                "selection": "unresolved modeled candidate aliases and surname components"
            },
            authoritative_scope="official candidate campaign committee search results",
        ),
        source_manifest_row(
            title_path, state="VA", cycle=0,
            kind="candidate_committee_standard_title_search_collection",
            provider="Virginia Department of Elections", source_url=VA_BASE,
            record_count=len(title_envelopes),
            request_parameters={
                "selection": "unresolved modeled candidate standard legal committee titles"
            },
            authoritative_scope="official candidate campaign committee search results",
        ),
        source_manifest_row(
            committee_path, state="VA", cycle=0, kind="committee_report_index_collection",
            provider="Virginia Department of Elections", source_url=VA_BASE + "Committee/Index/{id}",
            record_count=len(committee_envelopes),
            request_parameters={"selection": "automatically matched candidate committees"},
            authoritative_scope="official scheduled-report periods, amendments, contributions, and balances",
        ),
    ]
    for report, path in xml_results:
        report_end = pd.to_datetime(report["period_end"], errors="coerce")
        report_cycle = int(report_end.year) if pd.notna(report_end) else 0
        manifests.append(source_manifest_row(
            path, state="VA", cycle=report_cycle, kind="selected_report_xml",
            provider="Virginia Department of Elections", source_url=report["xml_url"],
            record_count=1, request_parameters={"report_id": report["report_id"]},
            authoritative_scope="official structured scheduled campaign-finance report",
        ))
    coverage_rows = []
    for cycle, group in match_frame.groupby("cycle"):
        accepted = int(group.match_status.eq("accepted_automatic").sum())
        coverage_rows.append({
            "state": "VA", "cycle": int(cycle), "target_candidates": len(group),
            "matched_candidates": accepted,
            "match_coverage": accepted / len(group) if len(group) else 0.0,
            "selected_report_details": sum(
                1 for report in selected_reports.values()
                if pd.to_datetime(report["period_end"]).year in {cycle - 1, cycle}
            ),
            "acquisition_status": "scheduled_report_indexes_and_selected_xml_acquired",
        })
    upsert_state_csv(MANIFEST, pd.DataFrame(manifests), "VA")
    upsert_state_csv(MATCH_AUDIT, match_frame, "VA")
    upsert_state_csv(COVERAGE, pd.DataFrame(coverage_rows), "VA")
    print(
        f"VA: {int(match_frame.match_status.eq('accepted_automatic').sum())}/"
        f"{len(match_frame)} candidates; {len(xml_results)} report XML files",
        flush=True,
    )


def webform_hidden(content: bytes) -> dict[str, str]:
    soup = BeautifulSoup(content, "html.parser")
    return {
        element.get("name"): element.get("value", "")
        for element in soup.select("input[type=hidden][name]")
    }


def mo_election_search(
    session: requests.Session, cycle: int, chamber: str, timeout: int,
) -> tuple[bytes, dict[str, str]]:
    year_name = "ctl00$ctl00$ContentPlaceHolder$ContentPlaceHolder1$ddElectionYear"
    date_name = "ctl00$ctl00$ContentPlaceHolder$ContentPlaceHolder1$ddElectionDate"
    office_name = "ctl00$ctl00$ContentPlaceHolder$ContentPlaceHolder1$ddPoliticalOffice"
    district_name = "ctl00$ctl00$ContentPlaceHolder$ContentPlaceHolder1$ddPoliticalDistrict"
    status_name = "ctl00$ctl00$ContentPlaceHolder$ContentPlaceHolder1$ddStatus"
    search_name = "ctl00$ctl00$ContentPlaceHolder$ContentPlaceHolder1$btnSearch"

    def postback(content: bytes, target: str, values: dict[str, str]) -> bytes:
        data = webform_hidden(content)
        data.update(values)
        data.update({"__EVENTTARGET": target, "__EVENTARGUMENT": ""})
        response = session.post(MO_ELECTION_SEARCH, data=data, timeout=timeout)
        response.raise_for_status()
        return response.content

    response = session.get(MO_ELECTION_SEARCH, timeout=timeout)
    response.raise_for_status()
    content = postback(response.content, year_name, {year_name: str(cycle)})
    soup = BeautifulSoup(content, "html.parser")
    dates = [
        option.get("value") for option in soup.select(
            "#ContentPlaceHolder_ContentPlaceHolder1_ddElectionDate option"
        ) if option.get("value") not in {None, "0"}
    ]
    november = [value for value in dates if value.startswith("11/")]
    if not november:
        raise RuntimeError(f"Missouri {cycle} general-election date unavailable")
    election_date = november[0]
    values = {year_name: str(cycle), date_name: election_date}
    content = postback(content, date_name, values)
    office = "State Representative" if chamber == "house" else "State Senator"
    values[office_name] = office
    content = postback(content, office_name, values)
    values.update({district_name: "0", status_name: "All", search_name: "Search"})
    data = webform_hidden(content)
    data.update(values)
    data.pop("__EVENTTARGET", None)
    data.pop("__EVENTARGUMENT", None)
    response = session.post(MO_ELECTION_SEARCH, data=data, timeout=timeout)
    response.raise_for_status()
    return response.content, values


def parse_mo_candidate_index(content: bytes, chamber: str) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    table = soup.select_one("#ContentPlaceHolder_ContentPlaceHolder1_grvElection")
    if table is None:
        return []
    rows = []
    for tr in table.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        link = tr.select_one("a[id*='_lbtnComm_']")
        if len(cells) < 6 or link is None:
            continue
        district_match = re.search(r"Distr(?:ic|tic)t\s+(\d+)", cells[4], re.I)
        event = re.search(r"__doPostBack\('([^']+)'", link.get("href", ""))
        if district_match is None or event is None:
            continue
        rows.append({
            "candidate": cells[2], "committee_name": cells[1],
            "party": cells[3], "chamber": chamber,
            "district": int(district_match.group(1)), "office": cells[4],
            "committee_status": cells[5], "event_target": event.group(1),
            "provider_id": event.group(1), "committee_id": "",
        })
    return rows


def acquire_mo(timeout: int, workers: int) -> None:
    targets = candidate_universe("MO")
    manifests, matches_all, coverage_rows, id_rows = [], [], [], []
    for cycle in sorted(targets.cycle.unique()):
        if cycle < 2020:
            unavailable = targets[targets.cycle.eq(cycle)].copy()
            unavailable["provider_candidate"] = ""
            unavailable["provider_identity"] = ""
            unavailable["candidate_filer_id"] = ""
            unavailable["campaign_id"] = ""
            unavailable["match_score"] = 0.0
            unavailable["match_margin"] = 0.0
            unavailable["candidates_considered"] = 0
            unavailable["match_status"] = "legacy_election_index_unavailable"
            matches_all.append(unavailable)
            coverage_rows.append({
                "state": "MO", "cycle": int(cycle),
                "target_candidates": len(unavailable), "matched_candidates": 0,
                "match_coverage": 0.0, "selected_report_details": 0,
                "acquisition_status": "legacy_election_index_unavailable_in_current_portal",
            })
            print(f"MO {cycle}: current portal has no legacy election index", flush=True)
            continue
        cycle_matches = []
        for chamber in ("house", "senate"):
            session = session_with_retries()
            try:
                live_content, values = mo_election_search(
                    session, int(cycle), chamber, timeout
                )
                path = RAW / "MO" / f"{cycle}_{chamber}_candidate_election_index.html"
                write_immutable_bytes(path, live_content)
                source_rows = parse_mo_candidate_index(path.read_bytes(), chamber)
                source = pd.DataFrame(source_rows)
                chamber_targets = targets[
                    targets.cycle.eq(cycle) & targets.chamber.eq(chamber)
                ]
                matches = match_simple_candidates(
                    chamber_targets, source, int(cycle), "MO", require_party=True
                )
                event_map = source.set_index("provider_id").event_target.to_dict()
                matches["event_target"] = matches.provider_identity.map(event_map)
                cycle_matches.append(matches)
                manifests.append(source_manifest_row(
                    path, state="MO", cycle=int(cycle),
                    kind=f"{chamber}_candidate_election_index",
                    provider="Missouri Ethics Commission",
                    source_url=MO_ELECTION_SEARCH, record_count=len(source_rows),
                    request_parameters={
                        "election_year": int(cycle), "chamber": chamber,
                        "election_date": values.get(
                            "ctl00$ctl00$ContentPlaceHolder$ContentPlaceHolder1$ddElectionDate"
                        ),
                    },
                    authoritative_scope=(
                        "official candidate committee, candidate, party, office, "
                        "district, and committee status by election"
                    ),
                ))

                base_hidden = webform_hidden(live_content)
                accepted = matches[matches.match_status.eq("accepted_automatic")]

                def resolve_mecid(row: dict) -> dict:
                    local = session_with_retries()
                    try:
                        local.cookies.update(session.cookies)
                        data = dict(base_hidden)
                        data.update(values)
                        data.update({
                            "__EVENTTARGET": row["event_target"],
                            "__EVENTARGUMENT": "",
                        })
                        response = local.post(
                            MO_ELECTION_SEARCH, data=data, timeout=timeout
                        )
                        response.raise_for_status()
                        found = re.search(r"CommInfo\.aspx\?mecid=([A-Z]\d+)", response.text, re.I)
                        return {
                            "cycle": int(cycle), "chamber": chamber,
                            "district": int(float(row["district"])),
                            "party": row["party"], "candidate": row["candidate"],
                            "provider_candidate": row["provider_candidate"],
                            "committee_name": source.loc[
                                source.provider_id.eq(row["provider_identity"]),
                                "committee_name",
                            ].iloc[0],
                            "mec_id": found.group(1).upper() if found else "",
                            "event_target": row["event_target"],
                            "response_sha256": hashlib.sha256(response.content).hexdigest(),
                        }
                    finally:
                        local.close()

                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [
                        pool.submit(resolve_mecid, row)
                        for row in accepted.to_dict("records")
                    ]
                    for future in as_completed(futures):
                        id_rows.append(future.result())
            finally:
                session.close()
        combined = pd.concat(cycle_matches, ignore_index=True)
        matches_all.append(combined)
        accepted_count = int(combined.match_status.eq("accepted_automatic").sum())
        coverage_rows.append({
            "state": "MO", "cycle": int(cycle),
            "target_candidates": len(combined), "matched_candidates": accepted_count,
            "match_coverage": accepted_count / len(combined) if len(combined) else 0.0,
            "selected_report_details": 0,
            "acquisition_status": (
                "candidate_committees_acquired_report_download_blocked_by_recaptcha"
            ),
        })
        print(f"MO {cycle}: {accepted_count}/{len(combined)} candidates", flush=True)
    id_path = RAW / "MO" / "modeled_candidate_mec_ids.jsonl"
    id_rows.sort(key=lambda row: (
        row["cycle"], row["chamber"], row["district"], row["party"]
    ))
    write_immutable_bytes(id_path, ("".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in id_rows
    )).encode("utf-8"))
    manifests.append(source_manifest_row(
        id_path, state="MO", cycle=0, kind="modeled_candidate_committee_ids",
        provider="Missouri Ethics Commission", source_url=MO_ELECTION_SEARCH,
        record_count=len(id_rows),
        request_parameters={"selection": "accepted modeled candidate rows"},
        authoritative_scope="official committee MEC identifiers resolved from election results",
        ingest_status="acquired_report_summary_blocked_by_recaptcha",
    ))
    upsert_state_csv(MANIFEST, pd.DataFrame(manifests), "MO")
    upsert_state_csv(MATCH_AUDIT, pd.concat(matches_all, ignore_index=True), "MO")
    upsert_state_csv(COVERAGE, pd.DataFrame(coverage_rows), "MO")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--states", nargs="*", default=["AR", "FL", "GA", "KY", "MS", "MO", "NC", "SC", "TN", "VA"]
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--completion-only", action="store_true",
        help="Acquire only approved candidate-level completion targets",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requested = {state.upper() for state in args.states}
    unsupported = requested - {"AL", "AR", "FL", "GA", "KY", "MS", "MO", "NC", "SC", "TN", "VA"}
    if unsupported:
        raise SystemExit(
            "Summary adapter not yet configured for: " + ", ".join(sorted(unsupported))
        )
    if "AL" in requested:
        if not args.completion_only:
            raise SystemExit("AL is configured only for --completion-only acquisition")
        acquire_al_adjudicated_completion()
    if "SC" in requested:
        acquire_sc(args.timeout, args.workers)
    if "AR" in requested:
        acquire_ar(args.timeout, args.workers)
    if "FL" in requested:
        acquire_fl(args.timeout)
    if "GA" in requested:
        acquire_ga(args.timeout, args.workers, args.completion_only)
    if "KY" in requested:
        acquire_ky(args.timeout, args.workers)
    if "MS" in requested:
        acquire_ms(args.timeout, args.workers)
    if "MO" in requested:
        acquire_mo(args.timeout, args.workers)
    if "TN" in requested:
        if args.completion_only:
            acquire_tn_adjudicated_completion(args.timeout)
        else:
            acquire_tn(args.timeout, args.workers)
    if "NC" in requested:
        acquire_nc(args.timeout, args.workers)
    if "VA" in requested:
        acquire_va(args.timeout, args.workers)


if __name__ == "__main__":
    main()
