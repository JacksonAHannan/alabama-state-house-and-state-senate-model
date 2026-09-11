"""Apply a hash-pinned September precinct-identity stage, never downstream analyses."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

try:
    import stage_precinct_identity_repair as staging
    from warehouse import begin_run, finish_run, file_sha256, utcnow
except ModuleNotFoundError:
    from scripts import stage_precinct_identity_repair as staging
    from scripts.warehouse import begin_run, finish_run, file_sha256, utcnow


IDENTITY = ("precinct_nodes", "precinct_vote_fingerprints", "precinct_match_candidates", "precinct_source_links")
GEOGRAPHY = ("precinct_geography_match_candidates", "precinct_geography_links",
             "canonical_geography_evidence", "canonical_precinct_geography_links", "precinct_geography_conflicts")
EXPORTS = ("precinct_link_review.csv", "precinct_geography_review.csv")
TARGET = "precinct_identity_source_repair_2026_09_05"
STALE = ["canonical_precinct_district_weights.csv", "precinct_geography_conflict_impact.csv",
         "historical weights and baselines", "dependent analytical and publication outputs"]
SOURCE_LIMITATIONS = (
    "Source-key collisions and the fractional Morgan observation remain unresolved in "
    "vote_observations, qa_vote_observation_quality and the original WQA source-repair evidence. "
    "This application neither rekeys ambiguous provider observations nor certifies geography."
)


def read_table(connection, name):
    return pd.read_sql_query(f'SELECT * FROM "{name}" ORDER BY rowid', connection)


def csv_hash(frame):
    return hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()


def verified_stage(connection, directory, expected_hash, expected_run=None):
    manifest_path = directory / "manifest.json"
    if file_sha256(manifest_path) != expected_hash:
        raise ValueError("Accepted stage manifest hash changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = manifest.get("profile", staging.DEFAULT_PROFILE)
    query = staging.source_query(profile)
    if manifest.get("source_scope") != staging.PROFILES[profile] or manifest.get("source_query") != query or manifest.get("status") != "staged_review_only":
        raise ValueError("Stage is not the scoped September source repair")
    staged_run = manifest.get("expected_run")
    if profile == staging.OFFICE_PROFILE and (not staged_run or staged_run != manifest.get("warehouse_latest_run")):
        raise ValueError("Office-label stage has no verified warehouse run")
    if expected_run is not None and staged_run != expected_run:
        raise ValueError("Requested run differs from accepted stage")
    if staged_run is not None:
        latest = connection.execute("SELECT build_run_id FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone()
        if latest is None or latest[0] != staged_run:
            raise ValueError("Warehouse run changed since staging")
    for name in ("stage_precinct_identity_repair.py", "build_precinct_identity.py", "source_vote_quality.py"):
        if file_sha256(Path(__file__).with_name(name)) != manifest.get("code_sha256", {}).get(name):
            raise ValueError(f"Stage code changed: {name}")
    names = {f"{prefix}{name}.csv" for name in IDENTITY for prefix in ("", "before_")}
    if set(manifest["outputs"]) != names:
        raise ValueError("Unexpected staged output set")
    for name in names:
        if file_sha256(directory / name) != manifest["outputs"][name]["sha256"]:
            raise ValueError(f"Stage output changed: {name}")
    staging.require_reported_vote_quality(connection, staging.PROFILES[profile])
    votes = pd.read_sql_query(query, connection)
    if staging.digest(votes) != manifest["source_fingerprint_input_sha256"]:
        raise ValueError("Source snapshot changed since staging")
    old = {name: read_table(connection, name) for name in IDENTITY}
    for name, frame in old.items():
        if staging.digest(frame) != manifest["input_tables"][name]["sha256"]:
            raise ValueError(f"Identity input changed since staging: {name}")
    frames, evidence = staging.prepare(votes, *(old[name] for name in IDENTITY), profile=profile)
    for name, frame in frames.items():
        if csv_hash(frame) != manifest["outputs"][f"{name}.csv"]["sha256"]:
            raise ValueError(f"Stage does not replay exactly: {name}")
    return old, frames, evidence


def reconcile_geography(old_identity, new_identity, geography, evidence, proven_2010=()):
    retired = set(evidence["retired_ids"])
    changed = set(evidence["changed_fingerprint_or_identity_ids"]) - retired
    old_nodes = old_identity["precinct_nodes"].set_index("node_id")
    new_nodes = new_identity["precinct_nodes"].set_index("node_id")
    metadata = ["year", "source", "county_key", "precinct_key", "name_norm", "precinct_code", "county_level_ballot"]
    referenced = set().union(*(set(frame.source_node_id) for frame in geography.values()))
    preserved_direct = sorted(changed & referenced)
    for node_id in preserved_direct:
        if node_id not in old_nodes.index or (old_nodes.loc[node_id, "year"] != 2014 and node_id not in proven_2010):
            raise ValueError(f"Changed geography reference needs separate review: {node_id}")
        pd.testing.assert_series_equal(old_nodes.loc[node_id, metadata], new_nodes.loc[node_id, metadata], check_names=False)
    old_links = old_identity["precinct_source_links"]
    new_links = new_identity["precinct_source_links"]
    accepted = set(map(tuple, new_links[new_links.accepted.eq(1)][["left_node_id", "right_node_id"]].values))
    revoked = {int(row.left_node_id) for row in old_links[old_links.accepted.eq(1)].itertuples()
               if (row.left_node_id, row.right_node_id) not in accepted}
    affected = retired | revoked
    result = {name: frame[~frame.source_node_id.isin(retired)].copy() for name, frame in geography.items()}
    raw = result["canonical_geography_evidence"]
    raw = raw[~(raw.source_node_id.isin(revoked) & raw.evidence.eq("source_transfer"))].copy()
    result["canonical_geography_evidence"] = raw
    scoped = raw[raw.source_node_id.isin(affected)]
    counts = scoped.groupby("source_node_id").vtd.nunique()
    canonical = scoped[scoped.source_node_id.map(counts).eq(1)].copy()
    canonical = canonical.groupby(["source_node_id", "vtd"], as_index=False).agg(
        evidence=("evidence", lambda values: "consensus" if values.nunique() > 1 else values.iloc[0]))
    conflicts = scoped[scoped.source_node_id.map(counts).gt(1)].copy()
    for name, replacement in (("canonical_precinct_geography_links", canonical), ("precinct_geography_conflicts", conflicts)):
        result[name] = pd.concat([result[name][~result[name].source_node_id.isin(affected)], replacement], ignore_index=True)
    for name, frame in result.items():
        pd.testing.assert_frame_equal(frame[~frame.source_node_id.isin(affected)].reset_index(drop=True),
                                      geography[name][~geography[name].source_node_id.isin(affected)].reset_index(drop=True))
    return result, {"retired_reference_ids": sorted(retired), "revoked_source_transfer_ids": sorted(revoked),
                    "surviving_2014_metadata_proven_unchanged": [n for n in preserved_direct if n not in proven_2010],
                    "surviving_2010_name_code_parity_proven": sorted(proven_2010),
                    "before_hashes": {name: staging.digest(frame) for name, frame in geography.items()},
                    "after_hashes": {name: staging.digest(frame) for name, frame in result.items()}}


def replace_rows(connection, name, frame):
    columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')]
    if set(columns) != set(frame.columns):
        raise ValueError(f"Unexpected table columns: {name}")
    connection.execute(f'DELETE FROM "{name}"')
    fields = ",".join(f'"{column}"' for column in columns)
    connection.executemany(f'INSERT INTO "{name}" ({fields}) VALUES ({",".join("?" for _ in columns)})',
        (tuple(None if pd.isna(value) else value for value in row)
         for row in frame[columns].itertuples(index=False, name=None)))


def validate(connection, expected, old_identity, profile=staging.DEFAULT_PROFILE):
    for name, frame in expected.items():
        pd.testing.assert_frame_equal(read_table(connection, name), frame.reset_index(drop=True), check_dtype=False)
    nodes = expected["precinct_nodes"]
    if nodes.node_id.duplicated().any() or nodes.duplicated(staging.KEYS).any():
        raise ValueError("Duplicate identity IDs or keys")
    ids = set(nodes.node_id)
    geography_ids = connection.execute("SELECT geo_node_id FROM geographic_precinct_nodes").fetchall()
    geo_ids = {row[0] for row in geography_ids}
    if len(geo_ids) != len(geography_ids):
        raise ValueError("Duplicate geographic node IDs")
    for name in GEOGRAPHY:
        if not set(expected[name].source_node_id).issubset(ids):
            raise ValueError(f"Orphan geography reference: {name}")
        if "geo_node_id" in expected[name] and not set(expected[name].geo_node_id).issubset(geo_ids):
            raise ValueError(f"Orphan geographic node: {name}")
    for name in ("precinct_match_candidates", "precinct_source_links"):
        if not set(expected[name].left_node_id).issubset(ids) or not set(expected[name].right_node_id).issubset(ids):
            raise ValueError(f"Orphan source reference: {name}")
    if not set(expected["precinct_vote_fingerprints"].node_id).issubset(ids):
        raise ValueError("Orphan fingerprint")
    for name, keys in (("precinct_vote_fingerprints", ["node_id", "office"]),
                       ("precinct_match_candidates", ["left_node_id", "right_node_id"]),
                       ("precinct_geography_match_candidates", ["source_node_id", "geo_node_id"]),
                       ("precinct_source_links", ["left_node_id"]),
                       ("canonical_precinct_geography_links", ["source_node_id"]),
                       ("precinct_geography_links", ["source_node_id"])):
        if expected[name].duplicated(keys).any():
            raise ValueError(f"Duplicate reference grain: {name}")
    old_nodes = old_identity["precinct_nodes"]
    outside = old_nodes[~staging.repair_scope(old_nodes, profile)]
    pd.testing.assert_frame_equal(nodes[nodes.node_id.isin(outside.node_id)].reset_index(drop=True), outside.reset_index(drop=True))
    old_fp = old_identity["precinct_vote_fingerprints"]
    pd.testing.assert_frame_equal(expected["precinct_vote_fingerprints"][expected["precinct_vote_fingerprints"].node_id.isin(outside.node_id)].reset_index(drop=True),
                                  old_fp[old_fp.node_id.isin(outside.node_id)].reset_index(drop=True))
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Foreign key violation")


def review_exports(connection):
    nodes = read_table(connection, "precinct_nodes")
    links = read_table(connection, "precinct_source_links")
    left = nodes.add_prefix("left_")[["left_node_id", "left_year", "left_county_key", "left_precinct_key", "left_name_norm", "left_precinct_code"]]
    right = nodes.add_prefix("right_")[["right_node_id", "right_precinct_key", "right_name_norm", "right_precinct_code"]]
    source = links.merge(left, on="left_node_id", how="left", validate="many_to_one").merge(right, on="right_node_id", how="left", validate="many_to_one")
    source = source.sort_values(["left_year", "left_county_key", "accepted", "composite_score"], ascending=[True, True, True, False])
    geographic = read_table(connection, "precinct_geography_links").merge(nodes[["node_id", "year", "county_key", "precinct_key"]], left_on="source_node_id", right_on="node_id", validate="many_to_one")
    geographic = geographic.merge(read_table(connection, "geographic_precinct_nodes")[["geo_node_id", "vtd", "geography_name", "geography_source"]], on="geo_node_id", validate="many_to_one")
    return dict(zip(EXPORTS, (source, geographic)))


def prove_office_geography(connection, old, new, geography, evidence):
    """Permit only Geneva2010 references proven independent of office totals."""
    if evidence.get("profile") != staging.OFFICE_PROFILE:
        return []
    try:
        from build_precinct_geography_links import match
    except ModuleNotFoundError:
        from scripts.build_precinct_geography_links import match
    before = old["precinct_nodes"]
    after = new["precinct_nodes"]
    scoped = staging.repair_scope(before, staging.OFFICE_PROFILE)
    columns = list(before.columns)
    pd.testing.assert_frame_equal(before[scoped].sort_values("node_id").reset_index(drop=True),
                                  after[after.node_id.isin(before.loc[scoped, "node_id"])][columns].sort_values("node_id").reset_index(drop=True))
    changed = set(evidence["changed_fingerprint_or_identity_ids"])
    referenced = set().union(*(set(frame.source_node_id) for frame in geography.values())) & changed
    eligible = before[before.node_id.isin(referenced)]
    if not (eligible.year.eq(2010) & eligible.county_key.eq("GENEVA") & eligible.source.eq("alabama_sos")).all():
        raise ValueError("Only unchanged Geneva2010 name/code references may be retained")
    if not referenced:
        return []
    geo = read_table(connection, "geographic_precinct_nodes")
    geo_fp = read_table(connection, "geographic_vote_fingerprints")
    old_result = match(eligible, old["precinct_vote_fingerprints"], geo, geo_fp)
    new_result = match(eligible, new["precinct_vote_fingerprints"], geo, geo_fp)
    for table, prior, fresh in zip(GEOGRAPHY[:2], old_result, new_result):
        keys = ["source_node_id", "geo_node_id"]
        def ordered(frame): return frame.sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(ordered(prior), ordered(fresh))
        stored = geography[table][geography[table].source_node_id.isin(referenced)]
        pd.testing.assert_frame_equal(ordered(stored), ordered(fresh), check_dtype=False)
        if not fresh.vote_score.eq(0).all() or not fresh.shared_offices.eq(0).all():
            raise ValueError("Geneva2010 matcher unexpectedly uses vote evidence")
    accepted = new_result[1][new_result[1].accepted.eq(1)].merge(geo[["geo_node_id", "vtd"]], on="geo_node_id", validate="many_to_one")
    pairs = set(zip(accepted.source_node_id, accepted.vtd))
    raw = geography["canonical_geography_evidence"]
    raw = raw[raw.source_node_id.isin(referenced)]
    if not raw.evidence.eq("direct_geography").all() or not set(zip(raw.source_node_id, raw.vtd)).issubset(pairs):
        raise ValueError("Unproven Geneva2010 canonical geography evidence")
    return sorted(referenced)


def apply(database: Path, stage: Path, backup: Path, manifest_sha256: str, expected_run=None):
    database, stage, backup = database.resolve(), stage.resolve(), backup.resolve()
    report_path = backup.with_name(backup.name + ".application.json")
    csv_backups = {name: backup.with_name(backup.name + "." + name) for name in EXPORTS}
    if database == backup or any(path.exists() for path in (backup, report_path, *csv_backups.values())):
        raise FileExistsError("Backup and application evidence must use new separate paths")
    if not database.is_file():
        raise FileNotFoundError(database)
    export_paths = {name: database.parent / name for name in EXPORTS}
    if any(path.resolve().parent != database.parent for path in export_paths.values()):
        raise ValueError("Refusing redirected review exports")
    # Use mode=rw so a mistaken source path can never create an empty database.
    with closing(sqlite3.connect(database.as_uri() + "?mode=rw", uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            old, frames, identity_evidence = verified_stage(connection, stage, manifest_sha256, expected_run)
            profile = identity_evidence.get("profile", staging.DEFAULT_PROFILE)
            geo_before = {name: read_table(connection, name) for name in GEOGRAPHY}
            proven_2010 = prove_office_geography(connection, old, frames, geo_before, identity_evidence)
            geo_after, geo_evidence = reconcile_geography(old, frames, geo_before, identity_evidence, proven_2010)
            expected = {**frames, **geo_after}
            # Prevent triggers or cascades from widening the owned write scope.
            allowed = set(expected) | {"warehouse_build_run", "qa_warehouse_source_repair"}
            triggers = connection.execute("SELECT name,tbl_name FROM sqlite_master WHERE type='trigger'").fetchall()
            if any(table in allowed for _, table in triggers):
                raise ValueError("Triggers on owned tables require separate scope review")
            def authorize(action, arg1, arg2, db_name, trigger):
                if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) and arg1 not in allowed:
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            connection.set_authorizer(authorize)
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(backup)) as destination:
                source.execute("PRAGMA query_only=ON")
                source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup quick_check failed")
                for name, before in {**old, **geo_before}.items():
                    pd.testing.assert_frame_equal(read_table(destination, name), before)
                if staging.digest(pd.read_sql_query(staging.source_query(profile), destination)) != json.loads((stage / "manifest.json").read_text(encoding="utf-8"))["source_fingerprint_input_sha256"]:
                    raise ValueError("Backup source snapshot differs")
            prior_exports = {}
            for name, path in export_paths.items():
                if path.exists():
                    with path.open("rb") as source, csv_backups[name].open("xb") as destination:
                        shutil.copyfileobj(source, destination)
                    if file_sha256(path) != file_sha256(csv_backups[name]):
                        raise ValueError(f"Review export changed during backup: {name}")
                    prior_exports[name] = {"backup": str(csv_backups[name]), "sha256": file_sha256(csv_backups[name])}
            configuration = {"stage": str(stage), "accepted_manifest_sha256": manifest_sha256,
                "backup": str(backup), "backup_verified": "quick_check and source/owned-table parity under writer reservation",
                "source_scope": staging.PROFILES[profile], "profile": profile, "prior_exports": prior_exports,
                "application_code_sha256": file_sha256(Path(__file__)),
                "geography_matcher_code_sha256": file_sha256(Path(__file__).with_name("build_precinct_geography_links.py"))}
            run = begin_run(connection, TARGET, configuration)
            connection.execute("PRAGMA defer_foreign_keys=ON")
            for name, frame in expected.items():
                replace_rows(connection, name, frame)
            validate(connection, expected, old, profile)
            exports = review_exports(connection)
            details = {"identity": identity_evidence, "geography": geo_evidence,
                       "backup": str(backup), "not_rebuilt": STALE, "exports": "pending",
                       "unresolved_source_quality": SOURCE_LIMITATIONS}
            connection.execute("INSERT INTO qa_warehouse_source_repair VALUES (?,?,?,?,?,?,?)",
                ("WQA-IDENTITY-" + run, run, "precinct identity and geography references", staging.PROFILES[profile],
                 "repaired_with_review", json.dumps(details, sort_keys=True), utcnow()))
            finish_run(connection, run, details)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        report = {"build_run_id": run, "warehouse_status": "committed", "exports_status": "pending",
                  "configuration": configuration, "validation": details}
        try:
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            report["outputs"] = {}
            for name, frame in exports.items():
                frame.to_csv(export_paths[name], index=False)
                report["outputs"][name] = {"rows": len(frame), "sha256": file_sha256(export_paths[name])}
            report["exports_status"] = "complete"
        except Exception as exc:
            report["exports_status"] = "failed_after_commit"
            report["export_error"] = f"{type(exc).__name__}: {exc}"
        details["exports"] = report["exports_status"]
        connection.execute("UPDATE warehouse_build_run SET validation_json=? WHERE build_run_id=?", (json.dumps(details, sort_keys=True), run))
        connection.commit()
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=staging.DB)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--stage-manifest-sha256", required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--expected-run")
    args = parser.parse_args()
    result = apply(args.database, args.stage, args.backup, args.stage_manifest_sha256, args.expected_run)
    print(json.dumps(result, indent=2))
    if result["exports_status"] != "complete":
        raise SystemExit(1)
