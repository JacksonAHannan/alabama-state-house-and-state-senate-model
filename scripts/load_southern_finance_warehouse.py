#!/usr/bin/env python3
"""Load canonical Southern candidate-cycle finance into the SQLite warehouse.

The loader preserves every source finance row, records raw-file lineage where
the acquisition manifests resolve it, and only promotes an identity to the
candidate mart after an exact state/cycle/chamber/district/party match plus a
conservative name match. Incumbency is positive matching evidence only; its
absence never implies challenger status and never creates a zero finance row.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from acquire_southern_candidate_finance_summaries import (
    candidate_score,
    normalized_tokens,
)
from load_southern_election_warehouse import canonical_name, party_family, stable_id
from warehouse import (
    ROOT,
    begin_run,
    connect,
    finish_run,
    initialize,
    register_table,
)


SCHEMA = Path(__file__).with_name("warehouse_southern_finance_schema.sql")
FINANCE = ROOT / "data/processed/finance/southern_candidate_cycle_finance.csv"
SUMMARY_MANIFEST = ROOT / "data/processed/source_audits/southern_finance_summary_manifest.csv"
TRANSACTION_MANIFEST = ROOT / "data/processed/source_audits/southern_campaign_finance_manifest.csv"
INCUMBENCY = ROOT / "data/raw/candidates/southern_state_legislative_incumbents_2016_2026.xlsx"
GENERATED_INCUMBENCY = ROOT / "data/processed/incumbency/southern_incumbency_evidence_2016_2024.csv"
FINANCE_IDENTITY_ADJUDICATIONS = (
    ROOT / "data/manual/finance/southern_finance_identity_adjudications.csv"
)
OUT = ROOT / "data/processed/finance"
AUDIT = ROOT / "data/processed/source_audits"
OBSERVED_STATUSES = {"observed_positive", "observed_zero"}
SMOOTHING_DOLLARS = 1_000.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def normalized_district(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return clean(value)
    return str(int(number)) if float(number).is_integer() else clean(value)


def chamber(value: object) -> str:
    text = clean(value).lower()
    mapping = {"house": "lower", "senate": "upper", "lower": "lower", "upper": "upper"}
    if text not in mapping:
        raise ValueError(f"Unsupported chamber: {value!r}")
    return mapping[text]


def nullable_float(value: object) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else float(number)


def nullable_int(value: object) -> int | None:
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else int(number)


def yes_no(value: object) -> int | None:
    text = clean(value).lower()
    if text in {"yes", "y", "true", "1"}:
        return 1
    if text in {"no", "n", "false", "0"}:
        return 0
    return None


def local_locator(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def upsert_registry_file(
    connection: sqlite3.Connection,
    *,
    preferred_id: str,
    provider: str,
    path: Path,
    source_url: str | None,
    retrieved_at: str | None,
    digest: str,
    media_type: str | None,
    license_or_terms: str | None,
    extraction_status: str,
    authoritative_scope: str,
) -> str:
    """Register a file without changing an existing ID for the same path."""
    locator = local_locator(path)
    existing = connection.execute(
        "SELECT source_file_id FROM warehouse_source_file WHERE local_path=?", (locator,)
    ).fetchone()
    if existing:
        identifier = existing[0]
        connection.execute(
            """UPDATE warehouse_source_file SET provider=?,original_url=?,retrieved_at_utc=?,
               sha256=?,media_type=?,license=?,extraction_status=?,authoritative_scope=?
               WHERE source_file_id=?""",
            (provider, source_url or None, retrieved_at or None, digest, media_type or None,
             license_or_terms or None, extraction_status, authoritative_scope, identifier),
        )
        return identifier
    collision = connection.execute(
        "SELECT local_path FROM warehouse_source_file WHERE source_file_id=?", (preferred_id,)
    ).fetchone()
    identifier = (
        stable_id("FSRC", preferred_id, locator) if collision else preferred_id
    )
    connection.execute(
        """INSERT INTO warehouse_source_file
           (source_file_id,provider,local_path,original_url,retrieved_at_utc,sha256,
            media_type,license,extraction_status,authoritative_scope)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (identifier, provider, locator, source_url or None, retrieved_at or None, digest,
         media_type or None, license_or_terms or None, extraction_status, authoritative_scope),
    )
    return identifier


def read_manifests(paths: list[Path]) -> list[dict]:
    records: list[dict] = []
    required = {
        "source_file_id", "provider", "source_url", "retrieved_at", "sha256",
        "media_type", "license_or_terms", "state_code", "cycle",
        "geography_vintage", "authoritative_scope", "ingest_status", "local_path",
    }
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(path)
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False)
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{path.name} is missing manifest fields: {missing}")
        for row in frame.to_dict("records"):
            if any(not clean(row[field]) for field in required):
                raise ValueError(f"{path.name} contains an incomplete manifest row")
            local = Path(row["local_path"])
            local = local if local.is_absolute() else ROOT / local
            if not local.exists():
                raise FileNotFoundError(local)
            if len(row["sha256"]) != 64:
                raise ValueError(f"Invalid manifest SHA-256 for {local}")
            records.append({**row, "manifest_name": path.name, "path": local})
    return records


def register_manifest_sources(
    connection: sqlite3.Connection, records: list[dict]
) -> tuple[dict[str, list[tuple[str, str]]], int]:
    path_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    inserted = 0
    for row in records:
        status = "normalized" if any(
            token in row["ingest_status"].lower() for token in ("parsed", "normalized")
        ) else "registered"
        warehouse_id = upsert_registry_file(
            connection,
            preferred_id=row["source_file_id"],
            provider=row["provider"], path=row["path"], source_url=row["source_url"],
            retrieved_at=row["retrieved_at"], digest=row["sha256"],
            media_type=row["media_type"], license_or_terms=row["license_or_terms"],
            extraction_status=status, authoritative_scope=row["authoritative_scope"],
        )
        registration_id = stable_id(
            "FREG", row["manifest_name"], row["source_file_id"]
        )
        state = clean(row["state_code"]).upper() or None
        data_kind = clean(row.get("data_kind")) or "unspecified"
        connection.execute(
            """INSERT INTO source_southern_finance_file
               (finance_source_registration_id,warehouse_source_file_id,manifest_name,
                manifest_source_file_id,state_code,cycle,data_kind,geography_vintage,
                authoritative_scope,ingest_status)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (registration_id, warehouse_id, row["manifest_name"], row["source_file_id"],
             state, clean(row["cycle"]), data_kind, row["geography_vintage"],
             row["authoritative_scope"], row["ingest_status"]),
        )
        path_map[local_locator(row["path"])].append(
            (registration_id, "raw_evidence")
        )
        inserted += 1
    return path_map, inserted


def register_derived_input(
    connection: sqlite3.Connection,
    path: Path,
    *,
    provider: str,
    data_kind: str,
    scope: str,
    manifest_name: str,
) -> tuple[str, str]:
    digest = sha256(path)
    registry_id = upsert_registry_file(
        connection, preferred_id=stable_id("SRC", provider, local_locator(path)),
        provider=provider, path=path, source_url=None,
        retrieved_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        digest=digest,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if path.suffix.lower() == ".xlsx" else "text/csv"
        ),
        license_or_terms="project-derived or supplied research input; upstream terms retained separately",
        extraction_status="normalized", authoritative_scope=scope,
    )
    registration_id = stable_id("FREG", manifest_name, registry_id)
    connection.execute(
        """INSERT INTO source_southern_finance_file
           (finance_source_registration_id,warehouse_source_file_id,manifest_name,
            manifest_source_file_id,state_code,cycle,data_kind,geography_vintage,
            authoritative_scope,ingest_status)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (registration_id, registry_id, manifest_name, registry_id, None, "2016-2026",
         data_kind, "provider-reported legislative district", scope, "normalized"),
    )
    return registry_id, registration_id


def resolve_provider_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidates = (ROOT / path, ROOT.parent / path)
    return next((candidate for candidate in candidates if candidate.exists()), candidates[0])


def register_supplemental_upstreams(
    connection: sqlite3.Connection,
    finance: list[dict],
    path_map: dict[str, list[tuple[str, str]]],
) -> int:
    """Register known local upstreams not represented in the two manifests."""
    metadata = {
        "AL": {
            "provider": "Alabama Secretary of State FCPA",
            "source_url": "https://fcpa.alabamavotes.gov/page.request.do?page=page.acfPublicDownloadData",
            "terms": "official public records; reuse terms not stated on download page",
            "kind": "candidate_cycle_summary",
            "scope": "processed Alabama candidate-cycle FCPA monetary contribution summary",
            "role": "canonical_input",
        },
        "TX": {
            "provider": "Texas Ethics Commission",
            "source_url": "https://prd.tecprd.ethicsefile.com/public/cf/public/TEC_CF_CSV.zip",
            "terms": "official public records; reuse terms not stated on download page",
            "kind": "campaign_finance_csv_database",
            "scope": "Texas Ethics Commission campaign-finance CSV database",
            "role": "raw_evidence",
        },
    }
    added = 0
    seen: set[tuple[str, str]] = set()
    for row in finance:
        state = row["state_code"]
        if state not in metadata:
            continue
        for value in (row["provider_source_path"] or "").split(";"):
            value = value.strip()
            if not value:
                continue
            path = resolve_provider_path(value)
            locator = local_locator(path)
            if path_map.get(locator) or (state, locator) in seen or not path.exists():
                continue
            seen.add((state, locator))
            meta = metadata[state]
            digest = sha256(path)
            warehouse_id = upsert_registry_file(
                connection,
                preferred_id=stable_id("SRC", meta["provider"], locator),
                provider=meta["provider"], path=path, source_url=meta["source_url"],
                retrieved_at=datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc
                ).isoformat(),
                digest=digest,
                media_type="application/zip" if path.suffix.lower() == ".zip" else "text/csv",
                license_or_terms=meta["terms"], extraction_status="normalized",
                authoritative_scope=meta["scope"],
            )
            registration_id = stable_id("FREG", "supplemental_upstream", warehouse_id)
            connection.execute(
                """INSERT INTO source_southern_finance_file
                   (finance_source_registration_id,warehouse_source_file_id,manifest_name,
                    manifest_source_file_id,state_code,cycle,data_kind,geography_vintage,
                    authoritative_scope,ingest_status)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (registration_id, warehouse_id, "supplemental_upstream", warehouse_id,
                 state, "2016-2024", meta["kind"],
                 "not_applicable_candidate_finance", meta["scope"], "normalized"),
            )
            path_map[locator].append((registration_id, meta["role"]))
            added += 1
    return added


def incumbency_records(path: Path, run_id: str, source_id: str) -> list[dict]:
    frame = pd.read_excel(path, sheet_name="Incumbents")
    required = {
        "Year", "State", "Chamber", "District", "Incumbent", "Party",
        "Incumbent_Ran", "Open_Seat", "Election_Status", "Won_General",
        "Method", "Roster_Source_URL", "Ballotpedia_URL", "Wikipedia_URL",
        "Coverage_Status", "Notes",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Incumbency workbook is missing columns: {missing}")
    rows = []
    for row in frame.to_dict("records"):
        state = clean(row["State"]).upper()
        year = int(row["Year"])
        house = chamber(row["Chamber"])
        district = normalized_district(row["District"])
        name = clean(row["Incumbent"])
        rows.append({
            "incumbency_evidence_id": stable_id(
                "INCEV", source_id, year, state, house, district, name
            ),
            "source_file_id": source_id, "contract_version": 1,
            "build_run_id": run_id, "cycle": year, "state_code": state,
            "chamber": house, "district": district, "incumbent_name": name,
            "party_family": party_family(row["Party"]),
            "incumbent_ran": yes_no(row["Incumbent_Ran"]),
            "open_seat": yes_no(row["Open_Seat"]),
            "election_status": clean(row["Election_Status"]) or None,
            "won_general": yes_no(row["Won_General"]),
            "method": clean(row["Method"]),
            "roster_source_url": clean(row["Roster_Source_URL"]) or None,
            "ballotpedia_url": clean(row["Ballotpedia_URL"]) or None,
            "wikipedia_url": clean(row["Wikipedia_URL"]) or None,
            "coverage_status": clean(row["Coverage_Status"]),
            "notes": clean(row["Notes"]) or None,
        })
    key = ["cycle", "state_code", "chamber", "district", "incumbent_name"]
    if pd.DataFrame(rows).duplicated(key).any():
        raise ValueError("Incumbency workbook is not unique at its declared grain")
    return rows


def warehouse_incumbency_records(
    connection: sqlite3.Connection, run_id: str
) -> list[dict]:
    """Load positive provider-reported incumbent flags already in the warehouse."""
    required = {"source_southern_legislative_candidate_result", "source_southern_legislative_observation_set"}
    available = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if not required.issubset(available):
        return []
    frame = pd.read_sql_query(
        """SELECT s.source_file_id,s.provider,s.source_family,s.state_code,s.cycle,
                  s.chamber,s.district,c.candidate_name,c.party_family
           FROM source_southern_legislative_candidate_result c
           JOIN source_southern_legislative_observation_set s USING(observation_set_id)
           WHERE c.incumbent_status=1 AND c.validation_status='passed'
             AND s.validation_status='passed' AND s.election_stage='general'
             AND s.cycle BETWEEN 2016 AND 2024""",
        connection,
    )
    rows = []
    for row in frame.drop_duplicates().to_dict("records"):
        district = normalized_district(row["district"])
        name = clean(row["candidate_name"])
        rows.append({
            "incumbency_evidence_id": stable_id(
                "INCEV", row["source_file_id"], row["cycle"], row["state_code"],
                row["chamber"], district, name, row["source_family"],
            ),
            "source_file_id": row["source_file_id"], "contract_version": 1,
            "build_run_id": run_id, "cycle": int(row["cycle"]),
            "state_code": row["state_code"], "chamber": row["chamber"],
            "district": district, "incumbent_name": name,
            "party_family": row["party_family"], "incumbent_ran": 1,
            "open_seat": 0,
            "election_status": "candidate_observed_in_general_election",
            "won_general": None,
            "method": (
                f"provider-reported incumbent_status from {row['provider']} "
                f"({row['source_family']})"
            ),
            "roster_source_url": None, "ballotpedia_url": None,
            "wikipedia_url": None, "coverage_status": "source_reported",
            "notes": (
                "Positive incumbent evidence inherited from the provider observation; "
                "absence is not negative evidence."
            ),
        })
    return rows


def generated_incumbency_records(path: Path, run_id: str, source_id: str) -> list[dict]:
    """Load reviewed/generated web and continuity evidence at candidate grain."""
    frame = pd.read_csv(path, low_memory=False)
    required = {
        "cycle", "state_code", "chamber", "district", "incumbent_name",
        "party_family", "incumbent_ran", "open_seat", "election_status",
        "won_general", "method", "roster_source_url", "ballotpedia_url",
        "wikipedia_url", "coverage_status", "notes",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Generated incumbency evidence is missing columns: {missing}")
    rows = []
    for row in frame.to_dict("records"):
        year = int(row["cycle"])
        state = clean(row["state_code"]).upper()
        house = chamber(row["chamber"])
        district = normalized_district(row["district"])
        name = clean(row["incumbent_name"])
        family = clean(row["party_family"]).lower() or "unknown"
        if family not in {"democratic", "republican", "independent", "other", "unknown"}:
            family = party_family(family)
        rows.append({
            "incumbency_evidence_id": stable_id(
                "INCEV", source_id, year, state, house, district, name, clean(row["method"])
            ),
            "source_file_id": source_id, "contract_version": 1,
            "build_run_id": run_id, "cycle": year, "state_code": state,
            "chamber": house, "district": district, "incumbent_name": name,
            "party_family": family, "incumbent_ran": nullable_int(row["incumbent_ran"]),
            "open_seat": nullable_int(row["open_seat"]),
            "election_status": clean(row["election_status"]) or None,
            "won_general": nullable_int(row["won_general"]),
            "method": clean(row["method"]),
            "roster_source_url": clean(row["roster_source_url"]) or None,
            "ballotpedia_url": clean(row["ballotpedia_url"]) or None,
            "wikipedia_url": clean(row["wikipedia_url"]) or None,
            "coverage_status": clean(row["coverage_status"]),
            "notes": clean(row["notes"]) or None,
        })
    key = ["cycle", "state_code", "chamber", "district", "incumbent_name", "method"]
    if pd.DataFrame(rows).duplicated(key).any():
        raise ValueError("Generated incumbency evidence is not unique at its declared grain")
    return rows


def finance_records(path: Path, run_id: str, source_id: str) -> list[dict]:
    frame = pd.read_csv(path, low_memory=False)
    required = {
        "state", "cycle", "chamber", "district", "party", "candidate",
        "total_fundraising", "finance_observation_status", "aggregation_status",
        "source_name", "source_measure", "source_path",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Finance panel is missing columns: {missing}")
    key = ["state", "cycle", "chamber", "district", "party"]
    if frame.duplicated(key).any():
        raise ValueError("Finance panel is not unique on state/cycle/chamber/district/party")
    rows = []
    for row in frame.to_dict("records"):
        state = clean(row["state"]).upper()
        year = int(row["cycle"])
        house = chamber(row["chamber"])
        district = normalized_district(row["district"])
        family = party_family(row["party"])
        original = clean(row["candidate"])
        status = clean(row["finance_observation_status"])
        observed = int(status in OBSERVED_STATUSES)
        total = nullable_float(row.get("total_fundraising"))
        if observed and total is None:
            raise ValueError(f"Observed finance row has no total: {state} {year} {original}")
        rows.append({
            "finance_candidate_cycle_id": stable_id(
                "FIN", state, year, house, district, family, original
            ),
            "contract_version": 1, "build_run_id": run_id,
            "source_file_id": source_id, "state_code": state, "cycle": year,
            "chamber": house, "district": district, "party_family": family,
            "candidate_name": canonical_name(original),
            "candidate_name_original": original,
            "provider_candidate_name": clean(row.get("provider_candidate")) or None,
            "committee_id": clean(row.get("committee_id")) or None,
            "total_fundraising": total,
            "cash_contributions": nullable_float(row.get("cash_contributions")),
            "other_receipts": nullable_float(row.get("other_receipts")),
            "in_kind_contributions": nullable_float(row.get("in_kind_contributions")),
            "loans_received": nullable_float(row.get("loans_received")),
            "expenditures": nullable_float(row.get("expenditures")),
            "ending_cash": nullable_float(row.get("ending_cash")),
            "report_count": nullable_int(row.get("report_count")),
            "period_start": clean(row.get("period_start")) or None,
            "period_end": clean(row.get("period_end")) or None,
            "finance_observation_status": status, "finance_observed": observed,
            "aggregation_status": clean(row["aggregation_status"]),
            "source_name": clean(row["source_name"]),
            "source_measure": clean(row["source_measure"]),
            "provider_source_path": clean(row.get("source_path")) or None,
            "source_reported_total": nullable_float(row.get("source_reported_total")),
            "upstream_data_run_id": clean(row.get("data_run_id")) or None,
            "upstream_generated_at_utc": clean(row.get("generated_at_utc")) or None,
            "upstream_code_sha256": clean(row.get("build_code_sha256")) or None,
            "upstream_config_id": clean(row.get("build_config_id")) or None,
        })
    return rows


def name_key(value: object) -> tuple[str, ...]:
    return tuple(sorted(normalized_tokens(value)))


def approved_identity_bridge_decisions() -> dict[tuple[str, int, str, str, str], dict]:
    """Index approved provider identities at canonical warehouse scope."""
    if not FINANCE_IDENTITY_ADJUDICATIONS.exists():
        return {}
    frame = pd.read_csv(FINANCE_IDENTITY_ADJUDICATIONS, dtype=str)
    frame = frame[
        frame.state_code.notna()
        & frame.review_status.str.lower().eq("approved")
    ].copy()
    chamber_map = {"house": "lower", "senate": "upper", "lower": "lower", "upper": "upper"}
    party_map = {"D": "democratic", "R": "republican"}
    decisions: dict[tuple[str, int, str, str, str], dict] = {}
    for decision in frame.to_dict("records"):
        start = int(decision["cycle_start"])
        end = int(decision["cycle_end"])
        chamber = chamber_map.get(str(decision["chamber"]).lower())
        party = party_map.get(str(decision["party"]).upper())
        if chamber is None or party is None:
            raise ValueError(
                f"Unsupported finance identity adjudication scope: {decision['adjudication_id']}"
            )
        for cycle in range(start, end + 1, 2):
            key = (
                decision["state_code"], cycle, chamber,
                str(int(float(decision["district"]))), party,
            )
            if key in decisions:
                raise ValueError(f"Overlapping approved finance identity decisions: {key}")
            decisions[key] = decision
    return decisions


def provider_identity_tokens(value: object) -> set[str]:
    """Normalize pipe-delimited source IDs and adapter prefixes."""
    return {
        token.split(":")[-1].strip()
        for token in str(value or "").split("|")
        if token.strip()
    }


def match_finance_candidates(
    finance: list[dict], candidates: pd.DataFrame, incumbency: list[dict]
) -> list[dict]:
    """Return at most one scoped candidate proposal per finance row."""
    approved_decisions = approved_identity_bridge_decisions()
    candidate_groups = {
        key: group.to_dict("records")
        for key, group in candidates.groupby(
            ["state_code", "cycle", "chamber", "district", "party_family"],
            dropna=False,
        )
    }
    incumbent_groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in incumbency:
        incumbent_groups[
            (row["state_code"], row["cycle"], row["chamber"], row["district"])
        ].append(row)
    matches = []
    for row in finance:
        scope = (
            row["state_code"], row["cycle"], row["chamber"], row["district"],
            row["party_family"],
        )
        options = candidate_groups.get(scope, [])
        party_scope = "exact"
        if not options:
            options = candidate_groups.get((*scope[:4], "unknown"), [])
            party_scope = "warehouse_party_unknown"
        if not options:
            continue
        finance_names = [row["candidate_name_original"]]
        if row.get("provider_candidate_name"):
            finance_names.append(row["provider_candidate_name"])
        incumbent_evidence = None
        for evidence in incumbent_groups.get(scope[:4], []):
            if evidence["incumbent_ran"] != 1:
                continue
            if max(
                candidate_score(name, evidence["incumbent_name"])
                for name in finance_names
            ) >= 92:
                incumbent_evidence = evidence
                break
        scored = []
        for option in options:
            candidate_names = option.get("candidate_match_names")
            if not isinstance(candidate_names, list):
                candidate_names = [option["candidate_name"]]
            score, finance_match_name, candidate_match_name = max(
                (
                    candidate_score(finance_name, candidate_name),
                    finance_name,
                    candidate_name,
                )
                for finance_name in finance_names for candidate_name in candidate_names
            )
            support = bool(
                incumbent_evidence
                and max(
                    candidate_score(name, incumbent_evidence["incumbent_name"])
                    for name in candidate_names
                ) >= 92
            )
            scored.append((
                score + (3.0 if support else 0.0), score, support, option,
                finance_match_name, candidate_match_name,
            ))
        scored.sort(key=lambda item: (item[0], item[1], item[3]["candidate_result_id"]), reverse=True)
        best_effective, best_score, support, best, finance_match_name, candidate_match_name = scored[0]
        second_effective = scored[1][0] if len(scored) > 1 else 0.0
        margin = best_effective - second_effective
        exact = name_key(finance_match_name) == name_key(candidate_match_name)
        approved = approved_decisions.get(scope)
        approved_provider_ids = (
            provider_identity_tokens(approved["provider_identity"])
            if approved is not None else set()
        )
        source_provider_ids = provider_identity_tokens(row.get("committee_id"))
        approved_identity = bool(
            approved is not None
            and approved_provider_ids
            and approved_provider_ids.issubset(source_provider_ids)
            and candidate_score(
                approved["candidate_name"], candidate_match_name
            ) >= 75.0
        )
        if approved_identity:
            review = "accepted"
            method = "approved_identity_adjudication:" + approved["adjudication_id"]
            best_score = max(best_score, candidate_score(
                approved["candidate_name"], candidate_match_name
            ))
        elif party_scope == "warehouse_party_unknown" and exact and best_score >= 99 and margin >= 5:
            review, method = "accepted", "exact_name_with_warehouse_party_unknown"
        elif party_scope == "warehouse_party_unknown" and best_score >= 92 and margin >= 5:
            review, method = "accepted", "strong_name_with_warehouse_party_unknown"
        elif party_scope == "warehouse_party_unknown":
            review, method = "review", "warehouse_party_unknown_and_name_not_conclusive"
        elif exact and best_score >= 99 and margin >= 5:
            review, method = "accepted", "exact_scope_and_normalized_name"
        elif best_score >= 92 and margin >= 5:
            review, method = "accepted", "fuzzy_name_with_exact_election_scope"
        elif support and best_score >= 88 and margin >= 3:
            review, method = "accepted", "incumbency_supported_fuzzy_name"
        elif len(options) == 1 and best_score >= 88 and margin >= 20:
            review, method = "accepted", "unique_scope_candidate_with_strong_name"
        else:
            review, method = "review", "ambiguous_or_low_score_scoped_name"
        rationale = (
            f"exact state/cycle/chamber/district scope; party_scope={party_scope}; "
            f"finance_name={finance_match_name!r}; candidate_name={candidate_match_name!r}; "
            f"name_score={best_score:.1f}; effective_margin={margin:.1f}; "
            f"incumbency_support={int(support)}"
        )
        matches.append({
            "finance_candidate_cycle_id": row["finance_candidate_cycle_id"],
            "candidate_result_id": best["candidate_result_id"],
            "incumbency_evidence_id": (
                incumbent_evidence["incumbency_evidence_id"] if support else None
            ),
            "match_method": method, "name_score": best_score,
            "match_margin": margin, "incumbency_support": int(support),
            "review_status": review, "rationale": rationale,
        })
    # Review proposals do not own a candidate identity. The bridge contract is
    # one-to-one, so retain only the strongest proposal for any election
    # candidate and leave competing finance rows unmatched for audit.
    ranked = sorted(
        matches,
        key=lambda row: (
            row["candidate_result_id"],
            row["review_status"] == "accepted",
            row["name_score"], row["match_margin"],
            row["finance_candidate_cycle_id"],
        ),
        reverse=True,
    )
    deduplicated = []
    claimed: set[str] = set()
    for match in ranked:
        if match["candidate_result_id"] in claimed:
            continue
        claimed.add(match["candidate_result_id"])
        deduplicated.append(match)
    return sorted(deduplicated, key=lambda row: row["finance_candidate_cycle_id"])


def raw_lineage(
    finance: list[dict], panel_registration_id: str,
    path_map: dict[str, list[tuple[str, str]]],
    identity_adjudication_registration_id: str | None = None,
) -> tuple[list[tuple[str, str, str]], int]:
    rows: set[tuple[str, str, str]] = set()
    unresolved = 0
    for record in finance:
        identifier = record["finance_candidate_cycle_id"]
        rows.add((identifier, panel_registration_id, "canonical_input"))
        if (
            identity_adjudication_registration_id
            and "approved_identity_adjudication:" in record["aggregation_status"]
        ):
            rows.add((
                identifier,
                identity_adjudication_registration_id,
                "raw_evidence",
            ))
        paths = [part.strip() for part in (record["provider_source_path"] or "").split(";") if part.strip()]
        for path_text in paths:
            path = resolve_provider_path(path_text)
            registrations = path_map.get(local_locator(path), [])
            if not registrations:
                unresolved += 1
            for registration_id, role in registrations:
                rows.add((identifier, registration_id, role))
    return sorted(rows), unresolved


def mart_candidate_rows(
    finance: list[dict], matches: list[dict], run_id: str
) -> list[dict]:
    finance_map = {row["finance_candidate_cycle_id"]: row for row in finance}
    rows = []
    for match in matches:
        if match["review_status"] != "accepted":
            continue
        source = finance_map[match["finance_candidate_cycle_id"]]
        rows.append({
            "candidate_result_id": match["candidate_result_id"],
            "finance_candidate_cycle_id": source["finance_candidate_cycle_id"],
            "build_run_id": run_id, "state_code": source["state_code"],
            "cycle": source["cycle"], "chamber": source["chamber"],
            "district": source["district"], "party_family": source["party_family"],
            "candidate_name": source["candidate_name_original"],
            "total_fundraising": source["total_fundraising"],
            "cash_contributions": source["cash_contributions"],
            "other_receipts": source["other_receipts"],
            "in_kind_contributions": source["in_kind_contributions"],
            "loans_received": source["loans_received"],
            "expenditures": source["expenditures"], "ending_cash": source["ending_cash"],
            "finance_observation_status": source["finance_observation_status"],
            "finance_observed": source["finance_observed"],
            "source_name": source["source_name"], "source_measure": source["source_measure"],
            "match_method": match["match_method"], "match_score": match["name_score"],
            "incumbency_support": match["incumbency_support"],
        })
    return rows


def race_rows(finance: list[dict], matches: list[dict], run_id: str) -> list[dict]:
    accepted = {
        row["finance_candidate_cycle_id"]: row["candidate_result_id"]
        for row in matches if row["review_status"] == "accepted"
    }
    grouped: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for row in finance:
        grouped[(row["state_code"], row["cycle"], row["chamber"], row["district"])][
            row["party_family"]
        ] = row
    output = []
    for key, parties in sorted(grouped.items()):
        state, cycle, house, district = key
        dem, rep = parties.get("democratic"), parties.get("republican")
        dem_id = accepted.get(dem["finance_candidate_cycle_id"]) if dem else None
        rep_id = accepted.get(rep["finance_candidate_cycle_id"]) if rep else None
        complete = bool(
            dem and rep and dem["finance_observed"] and rep["finance_observed"]
            and dem_id and rep_id
        )
        if not dem or not rep:
            status = "not_democratic_republican_contest"
        elif not dem["finance_observed"] or not rep["finance_observed"]:
            status = "incomplete_finance_observation"
        elif not dem_id or not rep_id:
            status = "incomplete_candidate_identity"
        else:
            status = "complete"
        ratio = (
            math.log(
                (dem["total_fundraising"] + SMOOTHING_DOLLARS)
                / (rep["total_fundraising"] + SMOOTHING_DOLLARS)
            ) if complete else None
        )
        output.append({
            "state_code": state, "cycle": cycle, "chamber": house,
            "district": district, "build_run_id": run_id,
            "democratic_candidate_result_id": dem_id,
            "republican_candidate_result_id": rep_id,
            "democratic_finance_candidate_cycle_id": dem["finance_candidate_cycle_id"] if dem else None,
            "republican_finance_candidate_cycle_id": rep["finance_candidate_cycle_id"] if rep else None,
            "democratic_fundraising": dem["total_fundraising"] if dem else None,
            "republican_fundraising": rep["total_fundraising"] if rep else None,
            "democratic_finance_status": dem["finance_observation_status"] if dem else None,
            "republican_finance_status": rep["finance_observation_status"] if rep else None,
            "finance_complete": int(complete),
            "log_fundraising_ratio_d_to_r": ratio,
            "smoothing_constant": SMOOTHING_DOLLARS,
            "race_finance_status": status,
        })
    return output


def coverage_rows(
    finance: list[dict], matches: list[dict], races: list[dict], run_id: str
) -> list[dict]:
    match_map = {row["finance_candidate_cycle_id"]: row for row in matches}
    groups: dict[tuple, list[dict]] = defaultdict(list)
    race_groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in finance:
        groups[(row["state_code"], row["cycle"])].append(row)
    for row in races:
        race_groups[(row["state_code"], row["cycle"])].append(row)
    rows = []
    for key, source_rows in sorted(groups.items()):
        state, cycle = key
        accepted = sum(
            match_map.get(row["finance_candidate_cycle_id"], {}).get("review_status") == "accepted"
            for row in source_rows
        )
        review = sum(
            match_map.get(row["finance_candidate_cycle_id"], {}).get("review_status") == "review"
            for row in source_rows
        )
        observed = sum(row["finance_observed"] for row in source_rows)
        observed_matched = sum(
            row["finance_observed"]
            and match_map.get(row["finance_candidate_cycle_id"], {}).get("review_status") == "accepted"
            for row in source_rows
        )
        state_races = race_groups[key]
        dr = sum(
            row["democratic_finance_candidate_cycle_id"] is not None
            and row["republican_finance_candidate_cycle_id"] is not None
            for row in state_races
        )
        complete = sum(row["finance_complete"] for row in state_races)
        total = len(source_rows)
        rows.append({
            "state_code": state, "cycle": cycle, "build_run_id": run_id,
            "source_candidate_rows": total, "observed_candidate_rows": observed,
            "accepted_identity_matches": accepted, "review_identity_matches": review,
            "unmatched_identity_rows": total - accepted - review,
            "observed_accepted_matches": observed_matched,
            "candidate_finance_coverage": observed / total,
            "identity_match_coverage": accepted / total,
            "warehouse_observed_coverage": observed_matched / total,
            "democratic_republican_races": dr, "finance_complete_races": complete,
            "race_finance_coverage": complete / dr if dr else None,
        })
    return rows


def insert_dicts(connection: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    connection.executemany(
        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
        [tuple(row.get(column) for column in columns) for row in rows],
    )


def export_loaded(database: Path | None, run_id: str, validation: dict) -> None:
    with closing(connect(database, readonly=True)) as connection:
        candidate = pd.read_sql_query(
            "SELECT * FROM fact_southern_candidate_cycle_finance ORDER BY state_code,cycle,chamber,district,party_family",
            connection,
        )
        races = pd.read_sql_query(
            "SELECT * FROM fact_southern_race_finance ORDER BY state_code,cycle,chamber,district",
            connection,
        )
        coverage = pd.read_sql_query(
            "SELECT * FROM qa_southern_finance_coverage ORDER BY state_code,cycle", connection
        )
        review = pd.read_sql_query(
            """SELECT f.*,b.candidate_result_id,b.match_method,b.name_score,b.match_margin,
                      b.incumbency_support,b.review_status,b.rationale
               FROM source_southern_candidate_cycle_finance f
               LEFT JOIN bridge_southern_finance_candidate_identity b
                 USING(finance_candidate_cycle_id)
               WHERE b.review_status IS NULL OR b.review_status<>'accepted'
               ORDER BY f.state_code,f.cycle,f.chamber,f.district,f.party_family""",
            connection,
        )
    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(OUT / "southern_warehouse_candidate_finance.csv", index=False)
    races.to_csv(OUT / "southern_warehouse_race_finance.csv", index=False)
    coverage.to_csv(AUDIT / "southern_finance_warehouse_coverage.csv", index=False)
    review.to_csv(AUDIT / "southern_finance_warehouse_identity_review.csv", index=False)
    manifest = {
        "contract_version": 1,
        "pipeline": "scripts/load_southern_finance_warehouse.py",
        "build_run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_sha256": sha256(Path(__file__)),
        "configuration": {
            "cycle_window": "2016-2024",
            "smoothing_dollars": SMOOTHING_DOLLARS,
            "incumbency_role": "positive_identity_evidence_only",
            "finance_identity_adjudications": local_locator(
                FINANCE_IDENTITY_ADJUDICATIONS
            ),
        },
        "validation": validation,
        "outputs": [
            "data/processed/finance/southern_warehouse_candidate_finance.csv",
            "data/processed/finance/southern_warehouse_race_finance.csv",
            "data/processed/source_audits/southern_finance_warehouse_coverage.csv",
            "data/processed/source_audits/southern_finance_warehouse_identity_review.csv",
        ],
    }
    (AUDIT / "southern_finance_warehouse_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def build(
    database: Path | None = None,
    *,
    finance_path: Path = FINANCE,
    incumbency_path: Path = INCUMBENCY,
    generated_incumbency_path: Path = GENERATED_INCUMBENCY,
    identity_adjudications_path: Path = FINANCE_IDENTITY_ADJUDICATIONS,
    manifest_paths: list[Path] | None = None,
    export: bool = True,
) -> dict:
    manifest_paths = (
        [SUMMARY_MANIFEST, TRANSACTION_MANIFEST]
        if manifest_paths is None else manifest_paths
    )
    manifest_records = read_manifests(manifest_paths) if manifest_paths else []
    with closing(connect(database)) as connection:
        initialize(connection)
        canonical_exists = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name='canonical_southern_legislative_candidate_election'"
        ).fetchone()[0]
        final_exists = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='view' "
            "AND name='fact_southern_legislative_final_candidate_election'"
        ).fetchone()[0]
        if not canonical_exists or not final_exists:
            raise RuntimeError(
                "Southern legislative history warehouse must be loaded before finance"
            )
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run_id = begin_run(connection, "southern_candidate_cycle_finance", {
            "contract_version": 1, "cycles": "2016-2024",
            "finance_input": local_locator(finance_path),
            "incumbency_input": local_locator(incumbency_path),
            "generated_incumbency_input": local_locator(generated_incumbency_path),
            "finance_identity_adjudications_input": local_locator(
                identity_adjudications_path
            ),
            "manifest_files": [local_locator(path) for path in manifest_paths],
            "incumbency_role": "positive_identity_evidence_only",
        })
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        for table in (
            "mart_southern_race_finance", "mart_southern_candidate_cycle_finance",
            "bridge_southern_finance_candidate_identity",
            "bridge_southern_finance_record_source",
            "source_southern_candidate_cycle_finance",
            "qa_southern_finance_coverage",
            "source_southern_finance_file",
        ):
            connection.execute(f"DELETE FROM {table}")
        # The downstream 2026 Alabama preparation mart holds FKs to workbook
        # evidence. Preserve those stable source rows and refresh only the
        # historical evidence owned by this build.
        connection.execute(
            "DELETE FROM source_southern_incumbency_evidence "
            "WHERE cycle BETWEEN 2016 AND 2024"
        )

        path_map, registered_manifest_files = register_manifest_sources(
            connection, manifest_records
        )
        finance_source_id, panel_registration_id = register_derived_input(
            connection, finance_path,
            provider="Southern candidate-cycle finance canonical builder",
            data_kind="canonical_candidate_cycle_finance",
            scope="canonical candidate-cycle finance observations for modeled Southern legislative candidates",
            manifest_name="southern_candidate_cycle_finance.csv",
        )
        incumbency_source_id, _ = register_derived_input(
            connection, incumbency_path,
            provider="Southern state legislative incumbency research workbook",
            data_kind="incumbency_evidence",
            scope="sitting incumbent and open-seat evidence by district-election where populated",
            manifest_name="southern_state_legislative_incumbents_2016_2026.xlsx",
        )
        generated_incumbency_source_id, _ = register_derived_input(
            connection, generated_incumbency_path,
            provider="Southern incumbency web roster and reviewed continuity builder",
            data_kind="incumbency_evidence",
            scope="candidate and open-seat incumbency evidence for Southern WAR races, 2016-2024",
            manifest_name="southern_incumbency_evidence_2016_2024.csv",
        )
        _, identity_adjudication_registration_id = register_derived_input(
            connection, identity_adjudications_path,
            provider="Reviewed Southern campaign-finance identity adjudications",
            data_kind="candidate_finance_identity_adjudication",
            scope=(
                "evidence-bearing reviewed provider identities restricted to exact "
                "state/cycle/chamber/district/party candidate scopes"
            ),
            manifest_name="southern_finance_identity_adjudications.csv",
        )
        workbook_incumbency = incumbency_records(
            incumbency_path, run_id, incumbency_source_id
        )
        historical_incumbency = warehouse_incumbency_records(connection, run_id)
        generated_incumbency = generated_incumbency_records(
            generated_incumbency_path, run_id, generated_incumbency_source_id
        )
        incumbency = workbook_incumbency + historical_incumbency + generated_incumbency
        finance = finance_records(finance_path, run_id, finance_source_id)
        existing_incumbency_ids = {
            row[0] for row in connection.execute(
                "SELECT incumbency_evidence_id FROM source_southern_incumbency_evidence"
            )
        }
        insert_dicts(
            connection, "source_southern_incumbency_evidence",
            [row for row in incumbency if row["incumbency_evidence_id"] not in existing_incumbency_ids],
        )
        insert_dicts(connection, "source_southern_candidate_cycle_finance", finance)
        supplemental_sources = register_supplemental_upstreams(
            connection, finance, path_map
        )
        lineage, unresolved_lineage_paths = raw_lineage(
            finance, panel_registration_id, path_map,
            identity_adjudication_registration_id,
        )
        connection.executemany(
            "INSERT INTO bridge_southern_finance_record_source VALUES (?,?,?)", lineage
        )

        candidates = pd.read_sql_query(
            """SELECT candidate_result_id,state_code,cycle,chamber,district,
                      candidate_name,party_family
               FROM fact_southern_legislative_final_candidate_election
               WHERE cycle BETWEEN 2016 AND 2024""",
            connection,
        )
        candidates["cycle"] = pd.to_numeric(candidates.cycle, errors="raise").astype(int)
        candidates["district"] = candidates.district.map(normalized_district)
        aliases = (
            pd.read_sql_query(
                """SELECT canonical_candidate_id AS candidate_result_id,ballot_name
                   FROM candidate_aliases
                   WHERE match_status='accepted' AND year BETWEEN 2016 AND 2024""",
                connection,
            )
            if connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='candidate_aliases'"
            ).fetchone()[0]
            else pd.DataFrame(columns=["candidate_result_id", "ballot_name"])
        )
        alias_map = aliases.groupby("candidate_result_id").ballot_name.apply(
            lambda values: [clean(value) for value in values if clean(value)]
        ).to_dict()
        candidates["candidate_match_names"] = candidates.apply(
            lambda row: list(dict.fromkeys([
                row.candidate_name, *alias_map.get(row.candidate_result_id, [])
            ])),
            axis=1,
        )
        matches = match_finance_candidates(finance, candidates, incumbency)
        insert_dicts(connection, "bridge_southern_finance_candidate_identity", matches)
        candidate_mart = mart_candidate_rows(finance, matches, run_id)
        races = race_rows(finance, matches, run_id)
        coverage = coverage_rows(finance, matches, races, run_id)
        insert_dicts(connection, "mart_southern_candidate_cycle_finance", candidate_mart)
        insert_dicts(connection, "mart_southern_race_finance", races)
        insert_dicts(connection, "qa_southern_finance_coverage", coverage)

        accepted = sum(row["review_status"] == "accepted" for row in matches)
        review = sum(row["review_status"] == "review" for row in matches)
        observed_input = sum(row["finance_observed"] for row in finance)
        observed_mart = sum(row["finance_observed"] for row in candidate_mart)
        complete_races = sum(row["finance_complete"] for row in races)
        historical_incumbency_count = sum(
            2016 <= row["cycle"] <= 2024 for row in incumbency
        )
        incumbency_supported = sum(row["incumbency_support"] for row in matches)
        bad_scope = connection.execute(
            """SELECT COUNT(*) FROM bridge_southern_finance_candidate_identity b
               JOIN source_southern_candidate_cycle_finance f USING(finance_candidate_cycle_id)
               JOIN canonical_southern_legislative_candidate_election c USING(candidate_result_id)
               WHERE f.state_code<>c.state_code OR f.cycle<>c.cycle OR f.chamber<>c.chamber
                  OR f.district<>c.district
                  OR (f.party_family<>c.party_family AND c.party_family<>'unknown')"""
        ).fetchone()[0]
        bad_observed = connection.execute(
            """SELECT COUNT(*) FROM source_southern_candidate_cycle_finance
               WHERE finance_observed=1 AND total_fundraising IS NULL"""
        ).fetchone()[0]
        bad_complete_race = connection.execute(
            """SELECT COUNT(*) FROM mart_southern_race_finance
               WHERE finance_complete=1 AND
                 (democratic_fundraising IS NULL OR republican_fundraising IS NULL
                  OR democratic_candidate_result_id IS NULL
                  OR republican_candidate_result_id IS NULL)"""
        ).fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if bad_scope or bad_observed or bad_complete_race or foreign_keys:
            raise ValueError(
                "Southern finance warehouse validation failed: "
                f"scope={bad_scope}, observed_missing={bad_observed}, "
                f"complete_race_missing={bad_complete_race}, foreign_keys={foreign_keys[:3]}"
            )
        validation = {
            "manifest_source_files": registered_manifest_files,
            "supplemental_upstream_files": supplemental_sources,
            "source_candidate_rows": len(finance),
            "observed_source_candidates": observed_input,
            "accepted_identity_matches": accepted,
            "review_identity_matches": review,
            "unmatched_identity_rows": len(finance) - accepted - review,
            "candidate_mart_rows": len(candidate_mart),
            "observed_candidate_mart_rows": observed_mart,
            "race_mart_rows": len(races),
            "finance_complete_races": complete_races,
            "incumbency_evidence_rows": len(incumbency),
            "workbook_incumbency_evidence_rows": len(workbook_incumbency),
            "warehouse_historical_incumbency_evidence_rows": len(historical_incumbency),
            "generated_incumbency_evidence_rows": len(generated_incumbency),
            "incumbency_evidence_2016_2024": historical_incumbency_count,
            "incumbency_supported_matches": incumbency_supported,
            "unresolved_provider_lineage_paths": unresolved_lineage_paths,
            "scope_mismatch_rows": 0,
            "observed_rows_missing_total": 0,
            "complete_races_missing_required_values": 0,
            "foreign_key_violations": 0,
        }
        owner = "scripts/load_southern_finance_warehouse.py"
        for args in (
            ("source_southern_finance_file", "source", "finance_source_registration_id",
             "Manifest observations coexist; warehouse registry IDs remain stable", "replace",
             "Acquisition-manifest registrations for Southern finance artifacts"),
            ("source_southern_incumbency_evidence", "source", "incumbency_evidence_id",
             "Positive evidence only; missing rows do not imply non-incumbency", "replace",
             "District-cycle incumbency evidence from the supplied workbook"),
            ("source_southern_candidate_cycle_finance", "source", "finance_candidate_cycle_id",
             "All canonical input observations retained including unknowns", "replace",
             "One finance observation per modeled candidate and cycle"),
            ("bridge_southern_finance_candidate_identity", "canonical", "finance_candidate_cycle_id",
             "Exact election scope plus reviewed name evidence; incumbency is positive support", "replace",
             "Evidence-bearing finance-to-election candidate identity bridge"),
            ("mart_southern_candidate_cycle_finance", "mart", "candidate_result_id",
             "Only accepted candidate identity links; unknown finance remains null", "replace",
             "Warehouse-linked candidate-cycle fundraising and separate finance categories"),
            ("mart_southern_race_finance", "mart", "state/cycle/chamber/district",
             "D/R ratio only when both finance observations and identities are complete", "replace",
             "Race-level Democratic and Republican fundraising features"),
            ("qa_southern_finance_coverage", "qa", "state_code/cycle",
             "Separates source observation, identity match, and complete-race coverage", "replace",
             "Southern finance coverage by state and election cycle"),
            ("fact_southern_candidate_cycle_finance", "mart", "candidate_result_id",
             "Validated candidate finance mart interface", "view",
             "Candidate-cycle finance fact interface"),
            ("fact_southern_race_finance", "mart", "state/cycle/chamber/district",
             "Validated complete/incomplete race finance interface", "view",
             "Race finance fact interface"),
        ):
            register_table(connection, args[0], args[1], owner, args[2], args[3], args[4], args[5])
        finish_run(connection, run_id, validation)
        connection.commit()
    if export:
        export_loaded(database, run_id, validation)
    return {"build_run_id": run_id, "validation": validation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    result = build(args.database)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
