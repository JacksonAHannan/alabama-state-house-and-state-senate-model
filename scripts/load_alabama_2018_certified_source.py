"""Stage or append reviewed Alabama 2018 source observations, never promote them.

Default execution is read-only. Application needs an explicit snapshot and new
backup path. The certified canvass is registered in ``warehouse_source_file``
inside the same guarded transaction only when it is absent. Unlike the 2022
cohort, 30 reviewed rows whose precinct subtotals fall below the certified total
are retained as review evidence; blank precinct cells stay unknown, never zero.
JSON is emitted to stdout for the coordinator to retain; this tool does not
write exports or rebuild canonical/model tables. ``--write-evidence`` only
regenerates the row-level evidence pin and never opens the warehouse.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3

import pandas as pd

import alabama_2018_official_results as adapter
from warehouse import ROOT, begin_run, database_path, file_sha256, finish_run, source_file_id, utcnow

AUDIT = Path("project_docs/audits/ALABAMA_2018_CERTIFIED_SOURCE_RECONCILIATION.json")
EVIDENCE = Path("project_docs/audits/ALABAMA_2018_CERTIFIED_SOURCE_ROWS.json")
MANIFEST = Path("data/raw/alabama_elections_and_geography/2018_general_certified_canvass.manifest.json")
AUDIT_SHA256 = "8c1b0bb6037ba3a944bba771028592f8db0b62417d453070a5df709dc53dbdd1"
EVIDENCE_SHA256 = "14f62727cbe9658c42c6c6bd223c15e507a9d5cf9c6046e506b67bd53ab74664"
AUDIT_STATUS = "review_required_precinct_subtotals_below_certified_canvass"
FAMILY = "alabama_sos_certified_canvass"
PARSER = "alabama_2018_official_results.certified_canvass"
CYCLE = 2018
ELECTION_DATE = "2018-11-06"
SETS = "source_southern_legislative_observation_set"
CANDIDATES = "source_southern_legislative_candidate_result"
QA = "qa_southern_legislative_source_reconciliation"
BUILD = "warehouse_build_run"
REPAIR = "qa_warehouse_source_repair"
REGISTRY = "warehouse_source_file"
OWNED = {SETS, CANDIDATES, QA, BUILD, REPAIR}
SNAPSHOT_TABLES = sorted(OWNED | {REGISTRY})
KEY = ["chamber", "district", "party", "candidate_norm", "category"]
EXPECTED_STATUS = {"matched_certified_total": 322, "review": 30}
EXPECTED_REVIEW_REASONS = {"vote_mismatch": 29, "missing_precinct_candidate": 1}
EXPECTED_ALIGNMENT = {"unique_exact_contest_party_category": 351, "precinct_candidate_scope_absent": 1}
MATCHED_REASON = "exact_name_party_contest_category_and_votes"
ABSENT = "precinct_candidate_scope_absent"
EVIDENCE_COLUMNS = KEY + [
    "observed_votes", "certified_votes", "observed_cells", "unknown_cells", "source_cells",
    "aggregation_status", "reconciliation_status", "reconciliation_reason", "candidate_alignment_method",
    "canvass_candidate_norm", "ambiguous_certified_key", "canvass_printed_candidate", "canvass_printed_party",
    "canvass_page", "canvass_column", "canvass_header_text", "canvass_header_token", "canvass_header_bbox",
    "canvass_value_bbox", "canvass_district_bbox", "canvass_total_label_bbox", "canvass_sha256"]
PARTY_FAMILY = {"D": "democratic", "R": "republican", "L": "other", "I": "independent"}
PRINTED_PARTY = {"DEM": "D", "REP": "R", "LIB": "L", "IND": "I", "NON": "O"}
REGISTRY_COLUMNS = ["source_file_id", "provider", "local_path", "original_url", "retrieved_at_utc", "sha256",
                    "media_type", "license", "extraction_status", "authoritative_scope"]
MANIFEST_AUDIT_FIELDS = ("source_file_id", "provider", "local_path", "source_url", "source_index_url", "sha256",
                         "size_bytes", "certified_date", "license_or_terms")


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def identifier(prefix: str, *parts) -> str:
    return prefix + "-" + hashlib.sha256(encode(parts).encode()).hexdigest()[:24].upper()


def digest_rows(rows) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(encode(tuple(row)).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def snapshot(connection) -> dict:
    return {table: digest_rows(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid'))
            for table in SNAPSHOT_TABLES} | {
        "schema": digest_rows(connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))}


def malformed(value) -> bool:
    return (pd.isna(value) or isinstance(value, bool) or not math.isfinite(float(value))
            or float(value) < 0 or not float(value).is_integer())


def registry_row(manifest: dict) -> dict:
    """The ten registry columns exactly as the 2022 registration replay wrote them."""
    return dict(zip(REGISTRY_COLUMNS, (
        manifest["source_file_id"], manifest["provider"], manifest["local_path"], manifest["source_url"],
        manifest["retrieved_at"], manifest["sha256"], manifest["media_type"], manifest["license_or_terms"],
        "registered", manifest["authoritative_scope"])))


def summarize(reconciled: pd.DataFrame) -> dict:
    """Literal counts of the staged frame; unknown cells are counted, never summed as zero."""
    named = reconciled.category.eq("named_candidate")
    write_in = reconciled.category.eq("write_in")
    review = reconciled[reconciled.reconciliation_status.eq("review")].copy()
    review["signed_delta"] = review.observed_votes - review.certified_votes
    by_category_party = {}
    for (category, party), group in review.groupby(["category", "party"], sort=True):
        known = group.signed_delta.dropna()
        by_category_party[f"{category}_{party}"] = {"rows": len(group), "signed_delta": int(known.sum()),
                                                    "absolute_delta": int(known.abs().sum())}
    known = review.signed_delta.dropna()
    return {
        "contests": len(reconciled[["chamber", "district"]].drop_duplicates()),
        "certified_rows": len(reconciled),
        "named_candidate_rows": int(named.sum()), "write_in_rows": int(write_in.sum()),
        "certified_votes": {"named_candidate": int(reconciled.loc[named, "certified_votes"].sum()),
                            "write_in": int(reconciled.loc[write_in, "certified_votes"].sum())},
        "observed_precinct_subtotal_votes": {
            "named_candidate": int(reconciled.loc[named, "observed_votes"].dropna().sum()),
            "write_in": int(reconciled.loc[write_in, "observed_votes"].dropna().sum())},
        "precinct_source_cells": int(reconciled.source_cells.dropna().sum()),
        "observed_precinct_cells": int(reconciled.observed_cells.dropna().sum()),
        "unknown_precinct_cells_retained": int(reconciled.unknown_cells.dropna().sum()),
        "reconciliation_status_counts": {k: int(v) for k, v in reconciled.reconciliation_status.value_counts().items()},
        "candidate_alignment": {k: int(v) for k, v in reconciled.candidate_alignment_method.value_counts().items()},
        "precinct_subtotal_review": {
            "rows": len(review),
            "review_reason_counts": {k: int(v) for k, v in review.reconciliation_reason.value_counts().items()},
            "signed_observed_minus_certified_delta": int(known.sum()),
            "absolute_vote_delta": int(known.abs().sum()),
            "by_category_party": by_category_party},
    }


def fresh_reconciliation(root: Path = ROOT):
    """Recompute the adapter reconciliation and require every accepted audit fact."""
    audit_path, manifest_path = root / AUDIT, root / MANIFEST
    if file_sha256(audit_path) != AUDIT_SHA256:
        raise ValueError("Reviewed reconciliation audit hash mismatch")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    canvass = audit["canvass_source"]
    if (audit["status"] != AUDIT_STATUS
            or any(canvass[field] != manifest[field] for field in MANIFEST_AUDIT_FIELDS)
            or canvass["retrieved_at_utc"] != manifest["retrieved_at"]
            or (manifest["state_code"], manifest["cycle"], manifest["election_date"], manifest["election_stage"])
            != ("AL", CYCLE, ELECTION_DATE, "general")
            or source_file_id(manifest["provider"], manifest["local_path"]) != manifest["source_file_id"]):
        raise ValueError("Canvass manifest/audit disagreement")
    for path, digest in audit["code_sha256"].items():
        if file_sha256(root / path) != digest:
            raise ValueError(f"Audited adapter code changed: {path}")
    source_path = root / manifest["local_path"]
    if file_sha256(source_path) != manifest["sha256"] or source_path.stat().st_size != manifest["size_bytes"]:
        raise ValueError("Canvass source hash/size mismatch")
    reconciled, sources = adapter.reconcile_sources(root)
    cells, precinct = adapter.load_official_cells(root)
    registration = audit["precinct_source"]
    if (sources["precinct_source"] != precinct or sources["canvass_source"]["sha256"] != manifest["sha256"]
            or precinct["source_path"] != registration["local_path"] or precinct["sha256"] != registration["sha256"]
            or precinct["county_count"] != registration["county_workbooks"]
            or source_file_id(registration["provider"], registration["local_path"]) != registration["source_file_id"]
            or sources["canvass_source"]["page_count"] != audit["coverage"]["canvass_pages"]
            or sources["canvass_source"]["total_pages"] != audit["coverage"]["legislative_total_pages"]):
        raise ValueError("Precinct/canvass source evidence changed")
    if reconciled.duplicated(KEY).any():
        raise ValueError("Duplicate reviewed source keys")
    matched = reconciled.reconciliation_status.eq("matched_certified_total")
    if not reconciled.loc[matched, "reconciliation_reason"].eq(MATCHED_REASON).all():
        raise ValueError("Matched rows carry an unexpected reconciliation reason")
    summary = summarize(reconciled)
    coverage, reconciliation = audit["coverage"], audit["reconciliation"]
    accepted = {
        "contests": coverage["house_districts"] + coverage["senate_districts"],
        "certified_rows": coverage["certified_rows"],
        "named_candidate_rows": coverage["named_candidate_rows"], "write_in_rows": coverage["write_in_rows"],
        "certified_votes": reconciliation["certified_votes"],
        "observed_precinct_subtotal_votes": reconciliation["observed_precinct_subtotal_votes"],
        "precinct_source_cells": coverage["precinct_source_cells"],
        "observed_precinct_cells": coverage["observed_precinct_cells"],
        "unknown_precinct_cells_retained": coverage["unknown_precinct_cells_retained"],
        "reconciliation_status_counts": {"matched_certified_total": reconciliation["matched_certified_total_rows"],
                                         "review": reconciliation["review_rows"]},
        "candidate_alignment": {k: audit["candidate_alignment"][k] for k in EXPECTED_ALIGNMENT},
        "precinct_subtotal_review": {
            "rows": reconciliation["review_rows"], "review_reason_counts": reconciliation["review_reasons"],
            "signed_observed_minus_certified_delta": reconciliation["review_signed_observed_minus_certified_delta"],
            "absolute_vote_delta": reconciliation["review_absolute_vote_delta"],
            "by_category_party": reconciliation["review_by_category_party"]},
    }
    if (summary != accepted or summary["reconciliation_status_counts"] != EXPECTED_STATUS
            or summary["precinct_subtotal_review"]["review_reason_counts"] != EXPECTED_REVIEW_REASONS
            or summary["candidate_alignment"] != EXPECTED_ALIGNMENT
            or summary["contests"] != 140 or summary["certified_rows"] != 352):
        raise ValueError("Reviewed cohort coverage mismatch")
    return reconciled, cells, manifest, audit, precinct, summary


def evidence_document(reconciled: pd.DataFrame, manifest: dict, audit: dict, precinct: dict, summary: dict) -> dict:
    ordered = reconciled.sort_values(["canvass_page", "canvass_column"])
    return {
        "schema_version": 1, "generated_at_utc": utcnow(),
        "scope": "row-level pin of the accepted Alabama 2018 certified canvass/precinct reconciliation for the "
                 "source-only warehouse append; no canonical promotion or analytical certification",
        "reconciliation_audit": {"path": AUDIT.as_posix(), "sha256": AUDIT_SHA256, "status": audit["status"]},
        "code_sha256": audit["code_sha256"],
        "canvass_source": manifest, "precinct_source": precinct, "precinct_registration": audit["precinct_source"],
        "summary": summary, "columns": EVIDENCE_COLUMNS,
        # pandas' ten-decimal float serialization, the same path verified_evidence replays.
        "rows": json.loads(ordered[EVIDENCE_COLUMNS].to_json(orient="values")),
        "limitations": ["Unknown precinct cells are not observed zeros.",
                        "Thirty precinct subtotals below the certified total remain review rows.",
                        "Certified totals do not certify geographic allocations or canonical identity.",
                        "Explicit redistribution terms remain review."],
    }


def write_evidence(root: Path = ROOT) -> dict:
    """Regenerate the row-level evidence pin from the accepted sources; no database access."""
    reconciled, _, manifest, audit, precinct, summary = fresh_reconciliation(root)
    document = evidence_document(reconciled, manifest, audit, precinct, summary)
    path = root / EVIDENCE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    digest = file_sha256(path)
    return {"path": EVIDENCE.as_posix(), "sha256": digest, "rows": len(document["rows"]),
            "pinned_constant_matches": digest == EVIDENCE_SHA256, "summary": summary}


def verified_evidence(root: Path = ROOT):
    """Reconcile fresh source parsing row by row against the exact pinned evidence."""
    evidence_path = root / EVIDENCE
    if not evidence_path.is_file() or file_sha256(evidence_path) != EVIDENCE_SHA256:
        raise ValueError("Reviewed source evidence hash mismatch")
    pinned = json.loads(evidence_path.read_text(encoding="utf-8"))
    reconciled, cells, manifest, audit, precinct, summary = fresh_reconciliation(root)
    if (pinned["columns"] != EVIDENCE_COLUMNS or pinned["canvass_source"] != manifest
            or pinned["precinct_source"] != precinct or pinned["precinct_registration"] != audit["precinct_source"]
            or pinned["code_sha256"] != audit["code_sha256"] or pinned["summary"] != summary
            or pinned["reconciliation_audit"] != {"path": AUDIT.as_posix(), "sha256": AUDIT_SHA256, "status": audit["status"]}):
        raise ValueError("Pinned source evidence disagrees with fresh reconciliation")
    fresh = json.loads(reconciled[EVIDENCE_COLUMNS].to_json(orient="values"))
    key_columns = [EVIDENCE_COLUMNS.index(key) for key in KEY]
    def keyed(rows):
        result = {tuple(row[i] for i in key_columns): row for row in rows}
        if len(result) != len(rows):
            raise ValueError("Duplicate reviewed source keys")
        return result
    if keyed(fresh) != keyed(pinned["rows"]) or len(fresh) != 352:
        raise ValueError("Fresh source rows differ from pinned evidence")
    return reconciled, cells, manifest, {
        "audit_sha256": AUDIT_SHA256, "evidence_sha256": EVIDENCE_SHA256, "manifest_sha256": file_sha256(root / MANIFEST),
        "adapter_code_sha256": audit["code_sha256"], "precinct_source": precinct,
        "precinct_registration": audit["precinct_source"], "canvass_source": manifest, "summary": summary,
    }


def registered_sources(connection, evidence: dict, root: Path = ROOT) -> tuple[dict, bool]:
    """The precinct ZIP must be registered; the canvass may await its one registry insert."""
    result, register = {}, False
    for metadata, required in [(evidence["precinct_registration"], True), (evidence["canvass_source"], False)]:
        path, identity, digest = metadata["local_path"], metadata["source_file_id"], metadata["sha256"]
        if file_sha256(root / path) != digest:
            raise ValueError(f"Source file on disk differs from reviewed evidence: {path}")
        rows = connection.execute(f"SELECT source_file_id,local_path,sha256 FROM {REGISTRY} WHERE local_path=? OR source_file_id=?",
                                  (path, identity)).fetchall()
        if not rows:
            if required:
                raise ValueError(f"Missing registered source: {path}")
            register = True
            result[identity] = {"local_path": path, "sha256": digest, "registration": "insert_pending"}
            continue
        if len(rows) != 1 or tuple(rows[0]) != (identity, path, digest):
            raise ValueError(f"Missing or inconsistent registered source: {path}")
        result[identity] = {"local_path": path, "sha256": digest, "registration": "present"}
    return result, register


def cohort(reconciled: pd.DataFrame, cells: pd.DataFrame, manifest: dict, evidence: dict,
           run: str, timestamp: str) -> dict[str, list[dict]]:
    """Construct source rows with stable artifact/physical-cell identifiers.

    Review rows are retained with their reconciliation evidence; the certified
    total is the observed vote value for every row. The single scope-absent
    row has no precinct cells at all, so its cell counts are zero and its
    precinct subtotal is null.
    """
    if reconciled.duplicated(KEY).any():
        raise ValueError("Duplicate staged source keys")
    statuses = {k: int(v) for k, v in reconciled.reconciliation_status.value_counts().items()}
    if statuses != EXPECTED_STATUS:
        raise ValueError(f"Unexpected staged reconciliation statuses: {statuses}")
    if any(malformed(value) for value in reconciled.certified_votes):
        raise ValueError("Malformed certified vote value")
    expected = {(chamber, district) for chamber, n in [("house", 105), ("senate", 35)] for district in range(1, n + 1)}
    if set(zip(reconciled.chamber, reconciled.district)) != expected or len(reconciled) != 352:
        raise ValueError("Staged cohort is not the complete reviewed 140/352 source")
    selected = cells[cells.category.isin(["named_candidate", "write_in"]) & cells.cell_kind.eq("precinct")].copy()
    selected["party"] = selected.printed_party.str.strip().str.upper().map(PRINTED_PARTY)
    selected.loc[selected.category.eq("write_in"), "party"] = "O"
    source_id = manifest["source_file_id"]
    result = {SETS: [], CANDIDATES: [], QA: []}
    for (source_chamber, district), group in reconciled.groupby(["chamber", "district"], sort=True):
        chamber = "lower" if source_chamber == "house" else "upper"
        set_id = identifier("AL18SET", source_id, manifest["sha256"], chamber, int(district))
        denominator = int(group.certified_votes.sum())
        if denominator <= 0 or int(group.category.eq("write_in").sum()) != 1:
            raise ValueError("Invalid certified contest denominator/write-in coverage")
        row_evidence = []
        for row in group.sort_values(["canvass_page", "canvass_column"]).to_dict("records"):
            box = [round(float(v), 10) for v in row["canvass_value_bbox"]]
            physical = {"source_file_id": source_id, "sha256": manifest["sha256"],
                        "page": int(row["canvass_page"]), "value_bbox": box}
            candidate_id = identifier("AL18CELL", physical)
            writein = row["category"] == "write_in"
            status, reason = row["reconciliation_status"], row["reconciliation_reason"]
            absent = row["candidate_alignment_method"] == ABSENT
            if status == "review" and reason not in EXPECTED_REVIEW_REASONS:
                raise ValueError(f"Unexpected review reason: {reason}")
            if absent != (reason == "missing_precinct_candidate"):
                raise ValueError("Precinct-scope alignment disagrees with reconciliation reason")
            if not writein and row["party"] not in PARTY_FAMILY:
                raise ValueError(f"Unmapped named-candidate party: {row['party']}")
            source_cells = selected[selected.chamber.eq(source_chamber) & selected.district.eq(district)
                                    & selected.category.eq(row["category"]) & selected.party.eq(row["party"])
                                    & selected.candidate_norm.eq(row["candidate_norm"])]
            counts = {"observed_cells": int(source_cells.votes.notna().sum()),
                      "unknown_cells": int(source_cells.votes.isna().sum()), "source_cells": len(source_cells)}
            for field, actual in counts.items():
                staged = row[field]
                if pd.isna(staged):
                    if not absent:
                        raise ValueError(f"Missing precinct cell count: {field}")
                    staged = 0
                if int(staged) != actual:
                    raise ValueError("Physical precinct evidence/missingness mismatch")
            observed = None if pd.isna(row["observed_votes"]) else int(row["observed_votes"])
            if observed != (int(source_cells.votes.dropna().sum()) if counts["observed_cells"] else None):
                raise ValueError("Observed precinct subtotal disagrees with physical cells")
            if (status == "matched_certified_total") != (observed is not None and observed == int(row["certified_votes"])):
                raise ValueError("Reconciliation status disagrees with certified/observed votes")
            locators = json.loads(source_cells[["source_member", "source_sheet", "source_row", "source_column",
                "county", "precinct", "printed_party", "printed_candidate", "votes", "value_status"]].to_json(orient="records"))
            result[CANDIDATES].append({
                "source_candidate_result_id": candidate_id, "observation_set_id": set_id,
                "candidate_source_id": encode(physical), "candidate_name": row["canvass_printed_candidate"],
                "candidate_name_original": row["canvass_printed_candidate"],
                "party_family": "unknown" if writein else PARTY_FAMILY[row["party"]],
                "party_original": None if writein else row["canvass_printed_party"],
                "votes": int(row["certified_votes"]), "vote_share": None,
                "vote_value_status": "observed", "writein_status": "true" if writein else "false",
                "incumbent_status": None, "winner_status": None,
                "validation_status": "passed" if status == "matched_certified_total" else "review", "as_of_utc": timestamp,
            })
            row_evidence.append({"source_candidate_result_id": candidate_id, "physical_canvass_cell": physical,
                "header_text": row["canvass_header_text"], "header_bbox": row["canvass_header_bbox"],
                "header_token": int(row["canvass_header_token"]), "category": row["category"],
                "canvass_candidate_norm": row["canvass_candidate_norm"], "aligned_candidate_norm": row["candidate_norm"],
                "candidate_alignment_method": row["candidate_alignment_method"],
                "certified_votes": int(row["certified_votes"]), "observed_votes": observed, **counts,
                "aggregation_status": None if pd.isna(row["aggregation_status"]) else row["aggregation_status"],
                "reconciliation_status": status, "reconciliation_reason": reason,
                "precinct_cells": sorted(locators, key=encode)})
        review = [item["reconciliation_reason"] for item in row_evidence if item["reconciliation_status"] == "review"]
        quality = {"promotion_status": "pending_canonical_adoption", "audit_sha256": evidence["audit_sha256"],
            "evidence_sha256": evidence["evidence_sha256"],
            "source_hashes": {"canvass": manifest["sha256"], "precinct": evidence["precinct_source"]["sha256"]},
            "vote_share_denominator": denominator, "denominator_categories": ["named_candidate", "write_in"],
            "unknown_precinct_cells_are_zero": False, "precinct_subtotal_review_rows": len(review),
            "review_reason_counts": {reason: review.count(reason) for reason in sorted(set(review))},
            "candidate_evidence": row_evidence}
        result[SETS].append({
            "observation_set_id": set_id, "build_run_id": run, "source_file_id": source_id,
            "source_member": None, "provider": manifest["provider"], "source_family": FAMILY, "authority_rank": 10,
            "state_code": "AL", "cycle": CYCLE, "election_date": ELECTION_DATE, "election_date_status": "observed",
            "election_stage": "general", "election_stage_original": "General Election",
            "office_code": "SLDL" if chamber == "lower" else "SLDU", "chamber": chamber,
            "district_plan_id": f"AL-{CYCLE}-{chamber}-reported-unknown-vintage",
            "geography_vintage": manifest["geography_vintage"], "district": str(district), "district_original": str(district),
            "source_coverage": "certified_all_candidate_and_write_in_totals", "contest_status": "unknown",
            "parser_name": PARSER, "quality_flags_json": encode(quality), "validation_status": "review", "as_of_utc": timestamp,
        })
    ids = [row["source_candidate_result_id"] for row in result[CANDIDATES]]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate physical certified cells")
    labels = {(row["observation_set_id"], row["candidate_name"], row["party_family"], row["party_original"]) for row in result[CANDIDATES]}
    if len(labels) != len(ids):
        raise ValueError("Duplicate printed candidate label within a contest")
    total = sum(row["votes"] for row in result[CANDIDATES])
    summary = summarize(reconciled)
    result[QA] = [{"reconciliation_id": identifier("AL18QA", source_id, manifest["sha256"]),
        "build_run_id": run, "source_file_id": source_id, "source_member": None, "state_code": "AL", "cycle": CYCLE,
        "parser_name": PARSER, "input_rows": len(reconciled), "output_candidate_rows": len(ids),
        "input_votes": total, "output_votes": total, "vote_delta": 0, "unknown_vote_rows": 0,
        "reconciliation_status": "exact", "note": encode({"audit_sha256": evidence["audit_sha256"],
            "evidence_sha256": evidence["evidence_sha256"],
            "unknown_precinct_cells_retained": summary["unknown_precinct_cells_retained"],
            "precinct_subtotal_review": summary["precinct_subtotal_review"],
            "canonical_adoption": "pending", "counts": summary})}]
    return result


def existing_cohort(connection, expected: dict) -> bool:
    """Replay is a no-op only for an exact cohort, never a partial overwrite.

    The source family is shared with the 2022 canvass cohort, so the scope is
    the 2018 cycle or this artifact, never the whole family.
    """
    source_id = expected[SETS][0]["source_file_id"]
    scope = "((source_family=? AND state_code='AL' AND cycle=?) OR source_file_id=?)"
    queries = {SETS: (f"SELECT * FROM {SETS} WHERE {scope}", (FAMILY, CYCLE, source_id)),
               CANDIDATES: (f"SELECT c.* FROM {CANDIDATES} c JOIN {SETS} USING(observation_set_id) WHERE {scope}", (FAMILY, CYCLE, source_id)),
               QA: (f"SELECT * FROM {QA} WHERE parser_name=? OR source_file_id=?", (PARSER, source_id))}
    actual = {}
    for table, (query, args) in queries.items():
        cursor = connection.execute(query, args)
        columns = [d[0] for d in cursor.description]
        actual[table] = [dict(zip(columns, row)) for row in cursor]
    if not any(actual.values()):
        return False
    def stable(rows):
        return sorted(encode({k: v for k, v in row.items() if k not in {"build_run_id", "as_of_utc"}}) for row in rows)
    if any(stable(actual[table]) != stable(expected[table]) for table in expected):
        raise ValueError("Existing source cohort conflicts with reviewed append; no overwrite allowed")
    return True


def authorizer(register: bool):
    """Owned inserts plus, only when the canvass is unregistered, its one registry insert."""
    def authorize(action, table, column, database, trigger):
        if action == sqlite3.SQLITE_INSERT:
            allowed = table in OWNED or (register and table == REGISTRY)
            return sqlite3.SQLITE_OK if allowed and trigger is None else sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_UPDATE:
            return sqlite3.SQLITE_OK if table == BUILD and trigger is None else sqlite3.SQLITE_DENY
        if action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
                      sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
                      sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_CREATE_INDEX,
                      sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    return authorize


def append_source(database: Path, *, apply: bool = False, expected_run: str | None = None,
                  backup: Path | None = None, root: Path = ROOT) -> dict:
    database = database.resolve()
    if apply and (not expected_run or backup is None):
        raise ValueError("Application requires --expected-run and --backup")
    if not database.is_file():
        raise FileNotFoundError(database)
    if apply:
        backup = backup.resolve()
        if backup == database or backup.exists():
            raise FileExistsError("Backup must be a new separate path")
    reconciled, cells, manifest, evidence = verified_evidence(root)
    staged = cohort(reconciled, cells, manifest, evidence, "staged", "staged")
    mode = "rw" if apply else "ro"
    with closing(sqlite3.connect(database.as_uri() + f"?mode={mode}", uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if not apply:
            connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        try:
            sources, register = registered_sources(connection, evidence, root)
            latest = connection.execute(f"SELECT build_run_id FROM {BUILD} ORDER BY rowid DESC LIMIT 1").fetchone()
            latest = latest[0] if latest else None
            if expected_run is not None and expected_run != latest:
                raise ValueError(f"Warehouse snapshot changed: expected {expected_run}, found {latest}")
            present = existing_cohort(connection, staged)
            report = {"warehouse_status": "unchanged" if present else "dry_run", "latest_run": latest,
                      "canvass_registration": "insert_pending" if register else "present",
                      "source_files": sources, "evidence": evidence,
                      "staged_counts": {table: len(rows) for table, rows in staged.items()}}
            if present or not apply:
                connection.rollback()
                return report
            if any(row[0] in OWNED | {REGISTRY} for row in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Owned-table triggers require separate review")
            before = snapshot(connection)
            before_counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                             for table in SNAPSHOT_TABLES}
            code_paths = [Path(__file__), Path(__file__).with_name("warehouse.py"),
                          Path(__file__).with_name("load_southern_legislative_history_warehouse.py")]
            application_code = {str(path): file_sha256(path) for path in code_paths}
            connection.set_authorizer(authorizer(register))
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(backup)) as destination:
                source.execute("PRAGMA query_only=ON")
                source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)] or snapshot(destination) != before:
                    raise ValueError("Separate backup validation failed")
            # Sources can change on disk independently of the database lock.
            if registered_sources(connection, evidence, root) != (sources, register):
                raise ValueError("Source registration changed during application")
            for path, digest in evidence["adapter_code_sha256"].items():
                if file_sha256(root / path) != digest:
                    raise ValueError("Adapter changed during source application")
            if any(file_sha256(Path(path)) != digest for path, digest in application_code.items()):
                raise ValueError("Application code changed during source application")
            if (file_sha256(root / AUDIT) != evidence["audit_sha256"] or file_sha256(root / MANIFEST) != evidence["manifest_sha256"]
                    or file_sha256(root / EVIDENCE) != evidence["evidence_sha256"]):
                raise ValueError("Reviewed evidence changed during application")
            config = {"backup": str(backup), "expected_run": expected_run, "before_snapshot": before,
                      "before_counts": before_counts, "canvass_registration": report["canvass_registration"],
                      "source_files": sources, "evidence": evidence,
                      "application_code_sha256": application_code}
            run = begin_run(connection, "alabama_2018_certified_source_append", config)
            timestamp = utcnow()
            if register:
                registration = registry_row(manifest)
                connection.execute(f"INSERT INTO {REGISTRY} ({','.join(REGISTRY_COLUMNS)}) VALUES ({','.join('?' for _ in REGISTRY_COLUMNS)})",
                                   tuple(registration[column] for column in REGISTRY_COLUMNS))
            for table, rows in staged.items():
                columns = list(rows[0])
                values = [tuple(run if column == "build_run_id" else timestamp if column == "as_of_utc" else row[column]
                                for column in columns) for row in rows]
                connection.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", values)
            if not existing_cohort(connection, staged):
                raise ValueError("Appended source cohort not found")
            registered, pending = registered_sources(connection, evidence, root)
            if pending or any(item["registration"] != "present" for item in registered.values()):
                raise ValueError("Canvass registration not found after application")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Foreign key violation")
            details = {"source_counts": report["staged_counts"], "source_reconciliation": evidence["summary"],
                       "canvass_registration": "inserted" if register else "present",
                       "canonical_adoption": "pending", "source_set_status": "review",
                       "precinct_subtotal_review_rows_retained": evidence["summary"]["precinct_subtotal_review"]["rows"],
                       "unchanged": ["canonical identities/results", "outcomes", "allocations", "model outputs", "publications",
                                     "Alabama 2022 certified source cohort"],
                       "backup": str(backup)}
            connection.execute(f"INSERT INTO {REPAIR} VALUES (?,?,?,?,?,?,?)",
                (identifier("AL18LOAD", run), run, SETS, "Alabama 2018 certified source append only",
                 "source_loaded_pending_adoption", encode(details), timestamp))
            finish_run(connection, run, details)
            deltas = {SETS: len(staged[SETS]), CANDIDATES: len(staged[CANDIDATES]), QA: len(staged[QA]), BUILD: 1, REPAIR: 1,
                      REGISTRY: 1 if register else 0}
            for table, count in before_counts.items():
                # UPDATE permission for the new run must not mask modification
                # of prior runs. All before-image rows must survive identically.
                preserved = digest_rows(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid LIMIT ?', (count,)))
                actual_count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                if preserved != before[table] or actual_count != count + deltas.get(table, 0):
                    raise ValueError(f"Append changed prior rows or unexpected counts: {table}")
            connection.commit()
            return report | {"warehouse_status": "committed", "build_run_id": run,
                             "configuration": config, "validation": details}
        except BaseException:
            connection.rollback()
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=database_path())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-run")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--write-evidence", action="store_true",
                        help="regenerate the row-level evidence pin from the accepted sources; never touches the warehouse")
    args = parser.parse_args(argv)
    if args.write_evidence:
        if args.apply or args.expected_run or args.backup:
            raise ValueError("--write-evidence is a source-only step and cannot be combined with application")
        print(json.dumps(write_evidence(), indent=2))
        return 0
    print(json.dumps(append_source(args.database, apply=args.apply, expected_run=args.expected_run,
                                  backup=args.backup), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
