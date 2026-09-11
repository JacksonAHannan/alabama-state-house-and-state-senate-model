#!/usr/bin/env python3
"""Build auditable Southern legislative incumbency evidence, 2016-2024.

Ballotpedia election-page wikitext is the primary web roster source;
Wikipedia is acquired as an independent cross-check when a matching article
exists. Positive provider flags and exact prior-winner/candidate continuity
are preserved. Absence is never treated as an open seat: open seats require an
explicit retirement/primary-defeat source row or an approved adjudication.
"""
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
try:
    from build_incumbency_features import read_candidate_code_names
except ModuleNotFoundError:  # Imported as scripts.build_southern_incumbents.
    from scripts.build_incumbency_features import read_candidate_code_names


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data/processed/elections/alabama_elections.sqlite"
RAW = ROOT / "data/raw/candidates/incumbency_web"
OUT_DIR = ROOT / "data/processed/incumbency"
AUDIT_DIR = ROOT / "data/processed/source_audits"
MANUAL = ROOT / "data/manual/incumbency/southern_incumbency_adjudications_2016_2024.csv"
ALABAMA_ROSTER = ROOT / "data/processed/war/incumbency_roster.csv"
ALABAMA_2022_CODE_SOURCE = (
    ROOT / "data/raw/alabama_elections_and_geography/al_gen_22_prec/README.txt"
)
GENERATED_EVIDENCE = "data/processed/incumbency/southern_incumbency_evidence_2016_2024.csv"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/128 Safari/537.36"
)
TARGET_STATES = {
    "AL": ("Alabama", "House of Representatives", "State Senate"),
    "AR": ("Arkansas", "House of Representatives", "State Senate"),
    "FL": ("Florida", "House of Representatives", "State Senate"),
    "GA": ("Georgia", "House of Representatives", "State Senate"),
    "KY": ("Kentucky", "House of Representatives", "State Senate"),
    "LA": ("Louisiana", "House of Representatives", "State Senate"),
    "MO": ("Missouri", "House of Representatives", "State Senate"),
    "MS": ("Mississippi", "House of Representatives", "State Senate"),
    "NC": ("North Carolina", "House of Representatives", "State Senate"),
    "OK": ("Oklahoma", "House of Representatives", "State Senate"),
    "SC": ("South Carolina", "House of Representatives", "State Senate"),
    "TN": ("Tennessee", "House of Representatives", "State Senate"),
    "TX": ("Texas", "House of Representatives", "State Senate"),
    "VA": ("Virginia", "House of Delegates", "State Senate"),
}
EVEN = (2016, 2018, 2020, 2022, 2024)
SCHEDULE = {
    **{state: {"lower": EVEN, "upper": EVEN} for state in ("AR", "FL", "GA", "KY", "MO", "NC", "OK", "TN", "TX")},
    "AL": {"lower": (2018, 2022), "upper": (2018, 2022)},
    "LA": {"lower": (2019, 2023), "upper": (2019, 2023)},
    "MS": {"lower": (2019, 2023), "upper": (2019, 2023)},
    "SC": {"lower": EVEN, "upper": (2016, 2020, 2024)},
    "VA": {"lower": (2017, 2019, 2021, 2023), "upper": (2019, 2023)},
}
PARTY = {"blue": "democratic", "red": "republican"}
DISTRICT_RE = re.compile(
    r"(?:House|Senate|Assembly|Delegate(?:s)?|Legislative)?\s*District\s*(?:No\.?\s*)?(\d+)", re.I
)
HEADING_RE = re.compile(r"^(={2,5})\s*(.*?)\s*\1\s*$", re.M)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", "" if pd.isna(value) else str(value))
    text = text.encode("ascii", "ignore").decode().upper()
    text = re.sub(r"\b(JR|SR|II|III|IV)\b", " ", text)
    tokens = re.findall(r"[A-Z0-9]+", text)
    return "|".join(sorted(tokens))


def clean_wiki(value: str) -> str:
    text = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", value, flags=re.I | re.S)
    text = re.sub(r"\{\{[^{}]*\}\}", " ", text)
    text = re.sub(r"\[\[[^]|]+\|([^]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^]]+)\]\]", r"\1", text)
    text = re.sub(r"'{2,}", "", text)
    return re.sub(r"\s+", " ", text).strip(" |-*\n\r\t")


def page_specs() -> Iterable[dict]:
    for state, chambers in SCHEDULE.items():
        state_name, lower, upper = TARGET_STATES[state]
        for chamber, years in chambers.items():
            office = lower if chamber == "lower" else upper
            for cycle in years:
                title = f"{state_name} {office} elections, {cycle}"
                yield {"state_code": state, "state_name": state_name, "chamber": chamber,
                       "cycle": cycle, "office": office, "ballotpedia_title": title}


def api_get(session: requests.Session, base: str, params: dict) -> tuple[bytes, str]:
    response = session.get(base, params=params, timeout=60)
    response.raise_for_status()
    return response.content, response.url


def store_raw(provider: str, spec: dict, content: bytes) -> tuple[Path, str]:
    digest = sha256_bytes(content)
    folder = RAW / provider / spec["state_code"] / str(spec["cycle"]) / spec["chamber"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest[:16]}.json"
    if path.exists() and sha256_file(path) != digest:
        raise ValueError(f"Immutable raw file changed: {path}")
    if not path.exists():
        path.write_bytes(content)
    return path, digest


def wikipedia_title(session: requests.Session, spec: dict) -> str | None:
    chamber_term = "House" if spec["chamber"] == "lower" else "Senate"
    query = f'intitle:"{spec["cycle"]}" intitle:"{spec["state_name"]}" {chamber_term} election'
    content, _ = api_get(
        session, "https://en.wikipedia.org/w/api.php",
        {"action": "query", "list": "search", "srsearch": query, "srlimit": 10, "format": "json"},
    )
    results = json.loads(content).get("query", {}).get("search", [])
    tokens = {str(spec["cycle"]), spec["state_name"].lower(), chamber_term.lower()}
    for result in results:
        title = result["title"]
        lower = title.lower()
        if all(token.lower() in lower for token in tokens):
            return title
    return None


def acquire_pages() -> tuple[pd.DataFrame, Path]:
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "manifests").mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).isoformat()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    rows = []
    for spec in page_specs():
        sources = [("ballotpedia", "https://ballotpedia.org/wiki/api.php", spec["ballotpedia_title"])]
        try:
            wiki_title = wikipedia_title(session, spec)
        except requests.RequestException:
            wiki_title = None
        if wiki_title:
            sources.append(("wikipedia", "https://en.wikipedia.org/w/api.php", wiki_title))
        for provider, base, title in sources:
            status, error, resolved_url = "acquired", None, None
            try:
                content, resolved_url = api_get(
                    session, base,
                    {"action": "parse", "page": title, "prop": "wikitext", "format": "json"},
                )
                payload = json.loads(content)
                if "error" in payload:
                    raise ValueError(payload["error"].get("info", "MediaWiki parse error"))
                path, digest = store_raw(provider, spec, content)
            except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
                status, error, path, digest = "unavailable", str(exc), None, None
            rows.append(
                {
                    **spec, "provider": provider, "page_title": title,
                    "source_url": resolved_url or base, "retrieved_at_utc": retrieved,
                    "sha256": digest,
                    "local_path": str(path.relative_to(ROOT)).replace("\\", "/") if path else None,
                    "license_or_terms": (
                        "https://ballotpedia.org/Ballotpedia:Copyrights" if provider == "ballotpedia"
                        else "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use"
                    ),
                    "geographic_vintage": f"district labels reported for the {spec['cycle']} election",
                    "election_cycle": spec["cycle"],
                    "authoritative_scope": "incumbent retirement, defeat, and election-page roster statements",
                    "acquisition_status": status, "error": error,
                }
            )
    manifest_rows = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    manifest = RAW / "manifests" / f"acquisition_{stamp}.csv"
    manifest_rows.to_csv(manifest, index=False)
    return manifest_rows, manifest


def wikitext(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["parse"]["wikitext"]["*"]


def section_text(text: str, heading_predicate) -> list[tuple[str, str]]:
    headings = list(HEADING_RE.finditer(text))
    output = []
    for index, match in enumerate(headings):
        title = clean_wiki(match.group(2))
        if not heading_predicate(title.lower()):
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        output.append((title, text[match.end():end]))
    return output


def table_records(body: str) -> list[dict]:
    records = []
    for table in re.findall(r"\{\|.*?\n\|\}", body, flags=re.S):
        for raw_row in re.split(r"\n\|-\s*\n", table)[1:]:
            cells = [cell.strip() for cell in re.split(r"\s*\|\|\s*", raw_row)]
            if len(cells) < 3:
                continue
            district = DISTRICT_RE.search(clean_wiki(" ".join(cells)))
            if not district:
                continue
            name = clean_wiki(re.sub(r"^\|\s*", "", cells[0]))
            party_cell = cells[1].lower()
            if "democrat" in party_cell or "blue" in party_cell:
                party = "democratic"
            elif "republican" in party_cell or "red" in party_cell:
                party = "republican"
            else:
                party = "unknown"
            if name and name.lower() != "name":
                records.append({"incumbent_name": name, "party_family": party,
                                "district": str(int(district.group(1)))})
    return records


def parse_web_lists(manifest: pd.DataFrame, provider: str) -> pd.DataFrame:
    rows = []
    available = manifest[(manifest.provider == provider) & (manifest.acquisition_status == "acquired")]
    for source in available.to_dict("records"):
        text = wikitext(ROOT / source["local_path"])
        predicates = {
            "retiring": lambda title: "retir" in title,
            "primary_defeat": lambda title: "incumbent" in title and "defeat" in title and "primary" in title,
            "general_defeat": lambda title: "incumbent" in title and "defeat" in title and "general" in title,
        }
        for status, predicate in predicates.items():
            for heading, body in section_text(text, predicate):
                for record in table_records(body):
                    rows.append(
                        {
                            "state_code": source["state_code"], "cycle": int(source["cycle"]),
                            "chamber": source["chamber"], **record, "web_status": status,
                            "provider": provider, "source_url": source["source_url"],
                            "source_local_path": source["local_path"], "source_sha256": source["sha256"],
                            "source_heading": heading,
                        }
                    )
    return pd.DataFrame(rows)


def parse_wikipedia_candidate_incumbents(manifest: pd.DataFrame) -> pd.DataFrame:
    """Extract only table rows explicitly labeling a candidate incumbent."""
    rows = []
    available = manifest[(manifest.provider == "wikipedia") & (manifest.acquisition_status == "acquired")]
    for source in available.to_dict("records"):
        text = wikitext(ROOT / source["local_path"])
        headings = list(HEADING_RE.finditer(text))
        for index, heading in enumerate(headings):
            district = DISTRICT_RE.search(clean_wiki(heading.group(2)))
            if not district:
                continue
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            body = text[heading.end():end]
            for table in re.findall(r"\{\|.*?\n\|\}", body, flags=re.S):
                for raw_row in re.split(r"\n\|-\s*\n", table)[1:]:
                    if "incumbent" not in raw_row.lower():
                        continue
                    cells = [clean_wiki(cell) for cell in re.split(r"\s*\|\|\s*", raw_row)]
                    candidate_cells = [cell for cell in cells if "incumbent" in cell.lower()]
                    if not candidate_cells:
                        continue
                    name = re.sub(r"\([^)]*incumbent[^)]*\)", "", candidate_cells[0], flags=re.I).strip(" |*")
                    joined = " ".join(cells).lower()
                    party = "democratic" if "democrat" in joined else (
                        "republican" if "republican" in joined else "unknown"
                    )
                    if not name:
                        continue
                    rows.append({
                        "state_code": source["state_code"], "cycle": int(source["cycle"]),
                        "chamber": source["chamber"], "district": str(int(district.group(1))),
                        "incumbent_name": name, "party_family": party,
                        "web_status": "candidate_incumbent", "provider": "wikipedia",
                        "source_url": source["source_url"], "source_local_path": source["local_path"],
                        "source_sha256": source["sha256"],
                        "source_heading": clean_wiki(heading.group(2)),
                    })
    return pd.DataFrame(rows)


def warehouse_races(connection: sqlite3.Connection) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """SELECT state_code,cycle,chamber,district,dem_candidate_name,rep_candidate_name,
                  dem_votes,rep_votes
           FROM mart_southern_war_outcome WHERE cycle BETWEEN 2016 AND 2024""",
        connection,
    )
    frame["district"] = frame.district.astype(str).str.replace(r"\.0$", "", regex=True)
    aliases = read_candidate_code_names()
    alabama_2022 = frame.state_code.eq("AL") & frame.cycle.eq(2022)
    for column in ("dem_candidate_name", "rep_candidate_name"):
        decoded = frame.loc[alabama_2022, column].map(aliases)
        frame.loc[alabama_2022, column] = decoded.fillna(frame.loc[alabama_2022, column])
    return frame


def provider_incumbents(connection: sqlite3.Connection) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """SELECT DISTINCT e.state_code,e.cycle,e.chamber,e.district,
                  e.incumbent_name,e.party_family,e.method,e.source_file_id,
                  s.local_path AS source_local_path,s.sha256 AS source_sha256,
                  s.provider AS source_provider
           FROM source_southern_incumbency_evidence e
           LEFT JOIN warehouse_source_file s USING(source_file_id)
           WHERE e.cycle BETWEEN 2016 AND 2024 AND e.incumbent_ran=1""",
        connection,
    )
    normalized_path = frame.source_local_path.fillna("").astype(str).str.replace("\\", "/")
    # The warehouse retains the previous generated evidence export for
    # downstream consumers. It is not an upstream source for its own rebuild.
    return frame[normalized_path.ne(GENERATED_EVIDENCE)].copy()


def alabama_incumbents() -> pd.DataFrame:
    """Load the evidence-backed Alabama roster at exact race-party grain."""
    roster = pd.read_csv(ALABAMA_ROSTER, dtype={"district": str})
    roster = roster[roster.cycle.between(2016, 2024)].copy()
    roster["state_code"] = "AL"
    roster["chamber"] = roster.chamber.map({"house": "lower", "senate": "upper"})
    if roster.chamber.isna().any() or not roster.incumbent_party.isin(["D", "R"]).all():
        raise ValueError("Alabama incumbency roster contains an invalid chamber or party")
    roster["party_family"] = roster.incumbent_party.map(
        {"D": "democratic", "R": "republican"}
    )
    roster["method"] = "canonical_alabama_incumbency_roster"
    roster["source_file_id"] = None
    roster["source_local_path"] = str(ALABAMA_ROSTER.relative_to(ROOT)).replace("\\", "/")
    roster["source_sha256"] = sha256_file(ALABAMA_ROSTER)
    roster["source_provider"] = "Alabama dedicated incumbency pipeline"
    return roster.rename(columns={"incumbent_candidate": "incumbent_name"})[[
        "state_code", "cycle", "chamber", "district", "incumbent_name",
        "party_family", "method", "source_file_id", "source_local_path",
        "source_sha256", "source_provider",
    ]]


def scoped_provider_records(
    source_positive: pd.DataFrame,
    candidate_by_party: dict[str, str],
    explicit_open: pd.DataFrame | None = None,
) -> list[dict]:
    """Attach positive evidence to the sole candidate in its exact race-party.

    Major-party scope constrains the identity but does not establish it by
    itself. A normalized name/surname or independently decoded Alabama roster
    must also agree. Unknown-party evidence requires a full normalized name.
    """
    def surname_keys(value: object) -> set[str]:
        text = unicodedata.normalize("NFKD", "" if pd.isna(value) else str(value))
        text = text.encode("ascii", "ignore").decode().upper()
        text = re.sub(r"\b(JR|SR|II|III|IV)\b", " ", text)
        text = re.sub(
            r"\b(STATE|HOUSE|REPRESENTATIVE|REP|SENATOR|SEN|DELEGATE|INCUMBENT)\b",
            " ",
            text,
        )
        tokens = re.findall(r"[A-Z]+", text)
        if not tokens:
            return set()
        if "," in str(value):
            before_comma = re.findall(r"[A-Z]+", text.split(",", 1)[0])
            return {"".join(before_comma)} if before_comma else set()
        return {tokens[-1], "".join(tokens[-2:])} if len(tokens) > 1 else {tokens[-1]}

    def surnames_related(left: set[str], right: set[str]) -> bool:
        for source_name in left:
            for candidate_name in right:
                if source_name == candidate_name:
                    return True
                shorter, longer = sorted((source_name, candidate_name), key=len)
                if len(shorter) >= 5 and (
                    longer.startswith(shorter) or longer.endswith(shorter)
                ):
                    return True
                if min(len(source_name), len(candidate_name)) >= 7 and SequenceMatcher(
                    None, source_name, candidate_name
                ).ratio() >= 0.9:
                    return True
        return False

    open_rows = explicit_open if explicit_open is not None else pd.DataFrame()
    records: list[dict] = []
    for item in source_positive.to_dict("records"):
        family = item.get("party_family")
        matched_family = family if family in candidate_by_party else next(
            (
                party for party, candidate in candidate_by_party.items()
                if normalized_name(item.get("incumbent_name")) == normalized_name(candidate)
            ),
            None,
        )
        if matched_family is None:
            continue
        candidate = candidate_by_party[matched_family]
        exact_name = normalized_name(item.get("incumbent_name")) == normalized_name(candidate)
        source_surnames = surname_keys(item.get("incumbent_name"))
        candidate_surnames = surname_keys(candidate)
        surname_match = surnames_related(source_surnames, candidate_surnames)
        resolved_alabama = item.get("method") == "canonical_alabama_incumbency_roster"
        if family not in candidate_by_party and not exact_name:
            continue
        conflicting_open = False
        if not open_rows.empty and source_surnames:
            same_party_open = open_rows[
                open_rows.party_family.isin([matched_family, "unknown"])
            ]
            conflicting_open = any(
                surnames_related(source_surnames, surname_keys(name))
                for name in same_party_open.incumbent_name
            )
        if conflicting_open and not exact_name and not resolved_alabama:
            continue
        if exact_name:
            identity_method = "exact_race_party_and_name"
        elif resolved_alabama:
            identity_method = "exact_race_party_alabama_decoded_roster"
        elif surname_match:
            identity_method = "exact_race_party_and_surname"
        else:
            continue
        records.append({
            **item,
            "party_family": matched_family,
            "incumbent_ran": 1,
            "open_seat": 0,
            "election_status": "incumbent_observed_in_general",
            "won_general": None,
            "coverage_status": f"source_reported_{identity_method}",
            "roster_source_url": None,
            "ballotpedia_url": None,
            "wikipedia_url": None,
            "notes": (
                f"{item.get('method')}; identity={identity_method}; "
                f"modeled_candidate={candidate}"
            ),
        })
    return records


def prior_winners(connection: sqlite3.Connection) -> pd.DataFrame:
    candidates = pd.read_sql_query(
        """SELECT state_code,cycle,chamber,district,candidate_name,party_family,votes
           FROM fact_southern_legislative_final_candidate_election
           WHERE cycle BETWEEN 2014 AND 2024 AND party_family IN ('democratic','republican')""",
        connection,
    )
    winners = []
    for _, group in candidates.groupby(["state_code", "cycle", "chamber", "district"], sort=False):
        observed = group[pd.to_numeric(group.votes, errors="coerce").fillna(0).gt(0)]
        if not observed.empty:
            selected = observed.loc[pd.to_numeric(observed.votes, errors="coerce").idxmax()]
        elif len(group) == 1:
            # Klarner retains an uncontested winner with an unreported vote.
            # A sole final-stage major-party candidate is positive winner
            # evidence; this does not turn a missing current incumbent into an
            # open seat.
            selected = group.iloc[0]
        else:
            continue
        winners.append(selected.to_dict())
    return pd.DataFrame(winners).rename(
        columns={"candidate_name": "incumbent_name", "cycle": "prior_cycle"}
    )


def build_rosters(manifest: pd.DataFrame, connection: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    races = warehouse_races(connection)
    positives = pd.concat(
        [provider_incumbents(connection), alabama_incumbents()],
        ignore_index=True,
        sort=False,
    )
    positives["district"] = positives.district.astype(str).str.replace(r"\.0$", "", regex=True)
    winners = prior_winners(connection)
    web = pd.concat(
        [parse_web_lists(manifest, "ballotpedia"), parse_web_lists(manifest, "wikipedia"),
         parse_wikipedia_candidate_incumbents(manifest)],
        ignore_index=True, sort=False,
    )
    manual = pd.read_csv(MANUAL)
    manual["district"] = manual.district.astype(str).str.replace(r"\.0$", "", regex=True)
    evidence_rows, race_rows = [], []
    for race in races.to_dict("records"):
        key = (race["state_code"], int(race["cycle"]), race["chamber"], race["district"])
        candidate_by_party = {
            "democratic": race["dem_candidate_name"], "republican": race["rep_candidate_name"]
        }
        selected = manual[
            manual.state_code.eq(key[0]) & manual.cycle.eq(key[1])
            & manual.chamber.eq(key[2]) & manual.district.eq(key[3])
            & manual.review_status.eq("approved")
        ]
        method = None
        if not selected.empty:
            records = selected.to_dict("records")
            method = "approved_manual_adjudication"
        else:
            records = []
            source_positive = positives[
                positives.state_code.eq(key[0]) & positives.cycle.eq(key[1])
                & positives.chamber.eq(key[2]) & positives.district.eq(key[3])
            ]
            bp = web[
                web.state_code.eq(key[0]) & web.cycle.eq(key[1])
                & web.chamber.eq(key[2]) & web.district.eq(key[3])
            ]
            open_bp = bp[bp.web_status.isin(["retiring", "primary_defeat"])]
            records = scoped_provider_records(source_positive, candidate_by_party, open_bp)
            if records:
                method = "provider_reported_incumbent"
            else:
                if not open_bp.empty:
                    item = open_bp.iloc[0].to_dict()
                    records = [{**item, "incumbent_ran": 0, "open_seat": 1,
                                "election_status": item["web_status"], "won_general": 0,
                                "coverage_status": f"explicit_{item['provider']}_open_seat",
                                "roster_source_url": item["source_url"],
                                "ballotpedia_url": item["source_url"] if item["provider"] == "ballotpedia" else None,
                                "wikipedia_url": item["source_url"] if item["provider"] == "wikipedia" else None,
                                "notes": f"{item['provider'].title()} section: {item['source_heading']}"}]
                    method = f"{item['provider']}_explicit_open_seat"
                else:
                    prior_cycles = sorted(
                        winners[(winners.state_code == key[0]) & (winners.chamber == key[2])
                                & (winners.prior_cycle < key[1])].prior_cycle.unique()
                    )
                    prior_cycle = prior_cycles[-1] if prior_cycles else None
                    prior = winners[
                        winners.state_code.eq(key[0]) & winners.chamber.eq(key[2])
                        & winners.prior_cycle.eq(prior_cycle)
                    ] if prior_cycle else winners.iloc[0:0]
                    for item in prior.to_dict("records"):
                        for family, candidate in candidate_by_party.items():
                            if normalized_name(item["incumbent_name"]) == normalized_name(candidate):
                                records.append({**item, "district": key[3], "party_family": family,
                                                "incumbent_ran": 1, "open_seat": 0,
                                                "election_status": "exact_prior_winner_in_general",
                                                "won_general": None, "coverage_status": "continuity_observed",
                                                "roster_source_url": None, "ballotpedia_url": None,
                                                "wikipedia_url": None,
                                                "notes": f"Exact candidate-name continuity from {prior_cycle} winner."})
                    if records:
                        method = "exact_prior_winner_candidate_continuity"
                    else:
                        general = bp[bp.web_status.isin(["general_defeat", "candidate_incumbent"])]
                        for item in general.to_dict("records"):
                            if any(normalized_name(item["incumbent_name"]) == normalized_name(name)
                                   for name in candidate_by_party.values()):
                                records.append({**item, "incumbent_ran": 1, "open_seat": 0,
                                                "election_status": item["web_status"],
                                                "won_general": 0 if item["web_status"] == "general_defeat" else None,
                                                "coverage_status": f"explicit_{item['provider']}_incumbent",
                                                "roster_source_url": item["source_url"],
                                                "ballotpedia_url": item["source_url"] if item["provider"] == "ballotpedia" else None,
                                                "wikipedia_url": item["source_url"] if item["provider"] == "wikipedia" else None,
                                                "notes": f"{item['provider'].title()} section: {item['source_heading']}"})
                        if records:
                            method = "explicit_web_incumbent"
        dem_inc = int(any(row.get("incumbent_ran") == 1 and row.get("party_family") == "democratic" for row in records))
        rep_inc = int(any(row.get("incumbent_ran") == 1 and row.get("party_family") == "republican" for row in records))
        complete = bool(records) and not (dem_inc and rep_inc and any(row.get("open_seat") == 1 for row in records))
        race_rows.append(
            {"state_code": key[0], "cycle": key[1], "chamber": key[2], "district": key[3],
             "dem_incumbent": dem_inc if complete else None, "rep_incumbent": rep_inc if complete else None,
             "incumbency_balance": dem_inc - rep_inc if complete else None,
             "open_seat": int(any(row.get("open_seat") == 1 for row in records)) if complete else None,
             "incumbency_method": method, "incumbency_quality": "source_validated" if complete else "missing",
             "strict_incumbency_eligible": int(complete),
             "evidence_count": len(records), "review_status": "approved" if complete else "review"}
        )
        for record in records:
            evidence_rows.append(
                {"cycle": key[1], "state_code": key[0], "chamber": key[2], "district": key[3],
                 "incumbent_name": record["incumbent_name"], "party_family": record.get("party_family", "unknown"),
                 "incumbent_ran": record.get("incumbent_ran"), "open_seat": record.get("open_seat"),
                 "election_status": record.get("election_status"), "won_general": record.get("won_general"),
                 "method": method, "roster_source_url": record.get("roster_source_url"),
                 "ballotpedia_url": record.get("ballotpedia_url"), "wikipedia_url": record.get("wikipedia_url"),
                 "coverage_status": record.get("coverage_status", "source_validated"),
                 "notes": record.get("notes"), "adjudication_id": record.get("adjudication_id"),
                 "source_local_path": record.get("source_local_path"),
                 "source_sha256": record.get("source_sha256")}
            )
    evidence = pd.DataFrame(evidence_rows).drop_duplicates(
        ["cycle", "state_code", "chamber", "district", "incumbent_name", "method"]
    )
    roster = pd.DataFrame(race_rows)
    if roster.duplicated(["state_code", "cycle", "chamber", "district"]).any():
        raise ValueError("Incumbency roster violates race-key uniqueness")
    return evidence, roster


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DATABASE)
    parser.add_argument("--reuse-manifest", type=Path)
    args = parser.parse_args()
    if args.reuse_manifest:
        manifest_path = args.reuse_manifest.resolve()
        manifest = pd.read_csv(manifest_path)
    else:
        manifest, manifest_path = acquire_pages()
    database_path = args.database.resolve()
    with sqlite3.connect(database_path) as connection:
        evidence, roster = build_rosters(manifest, connection)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    evidence_path = OUT_DIR / "southern_incumbency_evidence_2016_2024.csv"
    roster_path = OUT_DIR / "southern_incumbency_race_roster_2016_2024.csv"
    review_path = OUT_DIR / "southern_incumbency_review_queue_2016_2024.csv"
    evidence.to_csv(evidence_path, index=False)
    roster.to_csv(roster_path, index=False)
    roster[roster.review_status.eq("review")].to_csv(review_path, index=False)
    audit = {
        "contract_version": 1, "pipeline": "scripts/build_southern_incumbents.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "states": sorted(TARGET_STATES), "cycles": [2016, 2024],
        "source_manifest": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
        "source_manifest_sha256": sha256_file(manifest_path),
        "manual_adjudications": str(MANUAL.relative_to(ROOT)).replace("\\", "/"),
        "manual_adjudications_sha256": sha256_file(MANUAL),
        "database": str(database_path.relative_to(ROOT)).replace("\\", "/"),
        "database_sha256": sha256_file(database_path),
        "alabama_incumbency_roster": str(ALABAMA_ROSTER.relative_to(ROOT)).replace("\\", "/"),
        "alabama_incumbency_roster_sha256": sha256_file(ALABAMA_ROSTER),
        "alabama_2022_candidate_code_source": str(
            ALABAMA_2022_CODE_SOURCE.relative_to(ROOT)
        ).replace("\\", "/"),
        "alabama_2022_candidate_code_source_sha256": sha256_file(ALABAMA_2022_CODE_SOURCE),
        "race_rows": len(roster), "strict_ready": int(roster.strict_incumbency_eligible.sum()),
        "review_rows": int(roster.review_status.eq("review").sum()), "evidence_rows": len(evidence),
        "missing_value_policy": "Absence is unknown, never open and never zero.",
        "outputs": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
            for path in (evidence_path, roster_path, review_path)
        },
    }
    (AUDIT_DIR / "southern_incumbency_2016_2024_manifest.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
