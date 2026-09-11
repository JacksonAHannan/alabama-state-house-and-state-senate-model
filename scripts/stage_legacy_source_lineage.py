"""Stage literal source-cell provenance without changing the warehouse.

County cohorts must reconcile in full before any unique pair is eligible.
Repeated values retain all physical alternatives; no pairing by row order.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from zipfile import ZipFile

from build_election_database import _observations
from repair_sos_contest_offices import plain
from sos_precinct import YEAR_SOURCES, _workbook_sheets, load_sos_year
from warehouse import ROOT, database_path, file_sha256, utcnow
from load_alabama_2022_certified_source import digest_rows

CORE = ("year", "county", "county_key", "precinct", "precinct_key", "office",
        "district", "candidate", "candidate_key", "party", "party_norm", "votes",
        "source", "authority_rank")
FIELDS = ("source_file", "source_sheet", "source_row", "source_column", "source_file_id")


def records(cursor):
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor]


def key(row, office_labels=None):
    values = {field: plain(row[field]) for field in CORE}
    if office_labels:
        values["office"] = office_labels.get(values["office"], values["office"])
    return tuple(values[field] for field in CORE)


def compare_county(stored, parsed, source_id, office_labels=None):
    """Return an exact proposal or an explicit whole-cohort refusal."""
    old, new = defaultdict(list), defaultdict(list)
    for row in stored:
        old[key(row, office_labels)].append(row)
    for row in parsed:
        new[key(row, office_labels)].append(row)
    before = Counter({k: len(v) for k, v in old.items()})
    after = Counter({k: len(v) for k, v in new.items()})
    report = {"stored_rows": len(stored), "parsed_rows": len(parsed),
              "stored_only": sum((before-after).values()),
              "parsed_only": sum((after-before).values())}
    if before != after:
        return report | {"status": "substantive_mismatch", "changes": [],
                         "ambiguous": [], "conflicts": []}
    cells = set()
    for row in parsed:
        cell = tuple(plain(row.get(field)) for field in FIELDS[:4])
        if any(value is None or value == "" for value in cell) or cell in cells:
            raise ValueError("Missing or repeated physical source cell")
        for coordinate in cell[2:]:
            if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) or coordinate < 1 or int(coordinate) != coordinate:
                raise ValueError("Invalid one-based physical source coordinate")
        cells.add(cell)
    changes, ambiguous, conflicts = [], [], []
    for match_key, rows in old.items():
        candidates = new[match_key]
        if len(rows) != 1:
            ambiguous.append({"stored_rowids": [row["stored_rowid"] for row in rows],
                              "candidate_cells": [{field: plain(row.get(field)) for field in
                                                   (*FIELDS[:4], "printed_precinct", "printed_candidate")}
                                                  for row in candidates]})
            continue
        before_row, fresh = rows[0], candidates[0]
        proposed = {field: plain(fresh[field]) for field in FIELDS[:4]}
        # pandas can promote complete integral coordinates to floats when other
        # workbook rows are sparse. Match the warehouse INTEGER representation
        # before hashing the exact expected after-image.
        for field in ("source_row", "source_column"):
            proposed[field] = int(proposed[field])
        proposed["source_file_id"] = source_id
        # A filled field is evidence, never permission to silently overwrite it.
        disagreement = [field for field in FIELDS if before_row.get(field) is not None
                        and before_row[field] != proposed[field]]
        if disagreement:
            conflicts.append({"stored_rowid": before_row["stored_rowid"], "fields": disagreement})
            continue
        if any(before_row.get(field) is None for field in FIELDS):
            changes.append({"stored_rowid": before_row["stored_rowid"],
                            "before": {field: before_row.get(field) for field in FIELDS},
                            "after": proposed,
                            "source_key": list(key(before_row)),
                            "office_match": {"stored": before_row["office"], "parsed": fresh["office"]},
                            "printed_precinct": plain(fresh.get("printed_precinct")),
                            "printed_candidate": plain(fresh.get("printed_candidate"))})
    # A provenance conflict also refuses this entire county proposal.
    return report | {"status": "lineage_conflict" if conflicts else "reconciled",
                     "changes": [] if conflicts else changes,
                     "ambiguous": ambiguous, "conflicts": conflicts}


def verify_physical_cells(archive_path, parsed):
    """Reopen each immutable member and verify the proposed count-cell pointer."""
    with ZipFile(archive_path) as archive:
        members = Counter(archive.namelist())
        for member, frame in parsed.groupby("source_file", dropna=False):
            if members[member] != 1:
                raise ValueError("Missing or repeated raw archive member")
            sheets = _workbook_sheets(archive.read(member))
            for row in frame.itertuples(index=False):
                try:
                    cell = sheets[row.source_sheet][int(row.source_row)-1][int(row.source_column)-1]
                    matches = not isinstance(cell, bool) and float(cell) == row.votes
                except (KeyError, IndexError, ValueError, TypeError, OverflowError):
                    matches = False
                if not matches:
                    raise ValueError(f"Physical count cell disagrees: {member}, {row.source_sheet}, {row.source_row}, {row.source_column}")


def stage(database: Path, root: Path = ROOT, office_review: Path | None = None):
    office_labels_by_year = defaultdict(dict)
    review_evidence = None
    if office_review is not None:
        review_evidence = {"path": str(office_review.resolve()), "sha256": file_sha256(office_review)}
        review = json.loads(office_review.read_text(encoding="utf-8"))
        if review.get("status") != "approved_metadata_matching_only" or not review.get("reviewer") or not review.get("evidence"):
            raise ValueError("Office-label equivalence lacks reviewed evidence")
        for item in review["equivalences"]:
            office_labels = office_labels_by_year[item["year"]]
            if item["stored"] in office_labels:
                raise ValueError("Duplicate office-label equivalence")
            office_labels[item["stored"]] = item["parsed"]
    with closing(sqlite3.connect(database.resolve().as_uri()+"?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        latest = connection.execute("SELECT build_run_id FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone()[0]
        sources, cohorts, changes, ambiguities = [], [], [], []
        code_paths = [Path(__file__).resolve(), *[ROOT / "scripts" / name for name in
                      ("sos_precinct.py", "oe_normalize.py", "build_election_database.py", "warehouse.py", "repair_sos_contest_offices.py",
                       "repair_sos_cell_lineage.py", "load_alabama_2022_certified_source.py")]]
        code_hashes = {str(path): file_sha256(path) for path in code_paths}
        for year in (1998, 2004):
            office_labels = office_labels_by_year[year]
            path = root / "data/raw/alabama_elections_and_geography" / (YEAR_SOURCES[year]+".zip")
            digest = file_sha256(path)
            registered = records(connection.execute("SELECT source_file_id,local_path,sha256 FROM warehouse_source_file WHERE local_path=?",
                                 (path.relative_to(root).as_posix(),)))
            if len(registered) != 1 or registered[0]["sha256"] != digest:
                raise ValueError(f"Unregistered or changed raw archive: {path}")
            source_id = registered[0]["source_file_id"]
            sources.extend(registered)
            parsed = _observations(load_sos_year(root, year), "alabama_sos", 1)
            verify_physical_cells(path, parsed)
            old_rows = records(connection.execute("SELECT rowid AS stored_rowid,* FROM vote_observations WHERE source='alabama_sos' AND year=? ORDER BY rowid", (year,)))
            old_counties, new_counties = defaultdict(list), defaultdict(list)
            for row in old_rows:
                old_counties[row["county_key"]].append(row)
            for row in parsed.to_dict("records"):
                new_counties[row["county_key"]].append({k: plain(v) for k, v in row.items()})
            if set(old_counties) != set(new_counties):
                raise ValueError(f"County universe drift for {year}")
            for county in sorted(old_counties):
                comparison = compare_county(old_counties[county], new_counties[county], source_id, office_labels)
                changes.extend(comparison.pop("changes"))
                alternatives = comparison.pop("ambiguous")
                ambiguities.extend({"year": year, "county_key": county, **row} for row in alternatives)
                cohorts.append({"year": year, "county_key": county, **comparison,
                                "ambiguous_rows": sum(len(row["stored_rowids"]) for row in alternatives)})
            if file_sha256(path) != digest:
                raise ValueError("Raw source changed during staging")
        if any(file_sha256(Path(path)) != digest for path, digest in code_hashes.items()):
            raise ValueError("Parser code changed during staging")
        if review_evidence and file_sha256(office_review) != review_evidence["sha256"]:
            raise ValueError("Office review changed during staging")
        if review_evidence:
            expected_sources = {(item["source_file_id"], item["path"], item["sha256"]) for item in review["sources"]}
            actual_sources = {(item["source_file_id"], item["local_path"], item["sha256"]) for item in sources}
            if actual_sources != expected_sources:
                raise ValueError("Office review belongs to different source archives")
            reconciled = [item for item in cohorts if item["status"] == "reconciled"]
            if (len(reconciled) != review["expected_reconciled_cohorts"]
                    or sum(item["stored_rows"] for item in reconciled) != review["expected_reconciled_records"]
                    or {item["county_key"] for item in reconciled if item["year"] == 2004}
                    != set(review["eligible_2004_counties"])):
                raise ValueError("Reviewed county reconciliation scope changed")
        source_rows_sha256 = digest_rows(connection.execute(
            "SELECT rowid,* FROM vote_observations WHERE source='alabama_sos' AND year IN (1998,2004) ORDER BY rowid"))
        schema_sha256 = digest_rows(connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
        return {"schema_version": 1, "generated_at_utc": utcnow(), "warehouse_status": "unchanged",
                "latest_run": latest, "code_hashes": code_hashes, "sources": sources,
                "source_rows_sha256": source_rows_sha256, "schema_sha256": schema_sha256,
                "office_review": review_evidence,
                "comparison_fields": CORE, "cohorts": cohorts, "changes": changes,
                "ambiguities": ambiguities, "limitations": "Proposal only; no source-grain adjudication or database update."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=database_path())
    parser.add_argument("--output", type=Path, required=True, help="New proposal JSON path; never overwritten")
    parser.add_argument("--office-review", type=Path, help="Explicit reviewed label-equivalence evidence; source labels remain untouched")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = stage(args.database, office_review=args.office_review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    print(json.dumps({"proposal": str(args.output), "sha256": file_sha256(args.output),
                      "eligible_changes": len(report["changes"]),
                      "cohort_status": dict(Counter(row["status"] for row in report["cohorts"])),
                      "warehouse_status": "unchanged"}, indent=2))


if __name__ == "__main__":
    main()
