"""Stage precinct identity repairs; never mutate the input warehouse or promote links."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from build_precinct_identity import DB, build_nodes, match_sources
    from source_vote_quality import require_reported_vote_quality
except ModuleNotFoundError:
    from scripts.build_precinct_identity import DB, build_nodes, match_sources
    from scripts.source_vote_quality import require_reported_vote_quality


KEYS = ["year", "source", "county_key", "precinct_key"]
GROUPS = ["year", "county_key"]
DEFAULT_PROFILE = "september-source-repair"
OFFICE_PROFILE = "sos-office-labels"
SOURCE_SCOPE = "source='alabama_sos' AND (year=1994 OR (year=2002 AND county_key='MARSHALL') OR (year=2014 AND county_key='JEFFERSON'))"
PROFILES = {DEFAULT_PROFILE: SOURCE_SCOPE,
            OFFICE_PROFILE: "source='alabama_sos' AND ((year=2010 AND county_key='GENEVA') OR (year=2012 AND county_key='MORGAN'))"}
VOTE_QUERY = f"""SELECT year,source,county_key,precinct_key,office,SUM(votes) votes
FROM vote_observations WHERE {SOURCE_SCOPE}
GROUP BY year,source,county_key,precinct_key,office
ORDER BY year,source,county_key,precinct_key,office"""


def source_query(profile=DEFAULT_PROFILE):
    if profile not in PROFILES:
        raise ValueError(f"Unknown precinct repair profile: {profile}")
    return VOTE_QUERY.replace(SOURCE_SCOPE, PROFILES[profile])


def digest(frame):
    return hashlib.sha256(frame.to_csv(index=False, lineterminator="\n").encode()).hexdigest()


def repair_scope(frame, profile=DEFAULT_PROFILE):
    if profile == OFFICE_PROFILE:
        return frame.source.eq("alabama_sos") & ((frame.year.eq(2010) & frame.county_key.eq("GENEVA")) |
                                               (frame.year.eq(2012) & frame.county_key.eq("MORGAN")))
    if profile != DEFAULT_PROFILE:
        raise ValueError(f"Unknown precinct repair profile: {profile}")
    return frame.source.eq("alabama_sos") & (frame.year.eq(1994) |
        (frame.year.eq(2002) & frame.county_key.eq("MARSHALL")) |
        (frame.year.eq(2014) & frame.county_key.eq("JEFFERSON")))


def prepare(votes, old_nodes, old_fingerprints, old_candidates, old_links, profile=DEFAULT_PROFILE):
    votes = votes[repair_scope(votes, profile)].copy()
    if votes[KEYS + ["office", "votes"]].isna().any().any():
        raise ValueError("Missing precinct key, office or fingerprint votes")
    scoped_nodes, scoped_fingerprints = build_nodes(votes, existing=old_nodes)
    untouched_nodes = old_nodes[~repair_scope(old_nodes, profile)].copy()
    untouched_fingerprints = old_fingerprints[old_fingerprints.node_id.isin(untouched_nodes.node_id)].copy()
    nodes = pd.concat([untouched_nodes, scoped_nodes], ignore_index=True)
    fingerprints = pd.concat([untouched_fingerprints, scoped_fingerprints], ignore_index=True)
    if profile == OFFICE_PROFILE:
        if set(nodes.node_id) != set(old_nodes.node_id):
            raise ValueError("Office-label profile must preserve every existing node ID")
        pd.testing.assert_frame_equal(nodes[old_nodes.columns].sort_values("node_id").reset_index(drop=True),
                                      old_nodes.sort_values("node_id").reset_index(drop=True))
    before = old_fingerprints.sort_values(["node_id", "office"])
    after = fingerprints.sort_values(["node_id", "office"])
    if before.duplicated(["node_id", "office"]).any():
        raise ValueError("Duplicate existing fingerprint grain")
    compare = before.merge(after, on=["node_id", "office"], how="outer", suffixes=("_old", "_new"), indicator=True, validate="one_to_one")
    changed = set(compare.loc[compare._merge.ne("both") | compare.votes_old.ne(compare.votes_new), "node_id"])
    changed |= set(old_nodes.node_id) ^ set(nodes.node_id)
    metadata = ["name_norm", "precinct_code", "county_level_ballot"]
    shared = old_nodes.merge(nodes, on="node_id", suffixes=("_old", "_new"), validate="one_to_one")
    for field in metadata:
        changed.update(shared.loc[shared[f"{field}_old"].ne(shared[f"{field}_new"]), "node_id"])
    changed_nodes = pd.concat([old_nodes, nodes], ignore_index=True)
    groups = set(map(tuple, changed_nodes[changed_nodes.node_id.isin(changed)][GROUPS].values))
    # This repair changes SOS left nodes only; preserve every other source and sibling.
    affected = nodes.node_id.isin(changed) & repair_scope(nodes, profile)
    affected_ids = set(nodes.loc[affected, "node_id"])
    retired = set(old_nodes.node_id) - set(nodes.node_id)
    affected_old = old_nodes.node_id.isin(changed) & repair_scope(old_nodes, profile)
    affected_old_ids = set(old_nodes.loc[affected_old, "node_id"])
    for frame in (old_candidates, old_links):
        if not set(frame.left_node_id).issubset(set(old_nodes.node_id)) or not set(frame.right_node_id).issubset(set(old_nodes.node_id)):
            raise ValueError("Existing source-link table has orphan IDs")
    pool = nodes[affected | nodes.source.eq("openelections")]
    proposals, links = match_sources(pool, fingerprints, "alabama_sos", "openelections") if affected_ids else (pd.DataFrame(), pd.DataFrame())
    if proposals.empty:
        proposals = old_candidates.iloc[:0].copy()
    elif set(proposals.columns) != set(old_candidates.columns):
        raise ValueError("Unrecognized candidate columns; preserve external evidence for review")
    proposals = proposals[old_candidates.columns]
    if links.empty:
        links = old_links.iloc[:0].copy()
    else:
        # Changed inputs yield review suggestions, never inherited acceptance.
        links["accepted"] = 0
        links["match_method"] = "review"
        links["relationship"] = "unresolved"
        if set(links.columns) != set(old_links.columns):
            raise ValueError("Unrecognized source-link columns; preserve external adjudications for review")
        links = links[old_links.columns]
    def retained(frame):
        return frame[~frame.left_node_id.isin(affected_old_ids | retired) & ~frame.right_node_id.isin(retired)].copy()
    kept_links = retained(old_links)
    candidates = pd.concat([retained(old_candidates), proposals], ignore_index=True)
    links = pd.concat([kept_links, links], ignore_index=True)
    # Removing an accepted left node may change a surviving sibling's cardinality,
    # but not its acceptance or identity evidence.
    counts = links[links.accepted.eq(1)].groupby("right_node_id").size()
    removed_accepted = old_links[old_links.accepted.eq(1) & old_links.left_node_id.isin(affected_old_ids | retired)]
    relationship_changes = []
    for index, row in links[links.accepted.eq(1) & links.right_node_id.isin(removed_accepted.right_node_id)].iterrows():
        expected = "many_sos_to_one_oe" if counts[row.right_node_id] > 1 else "one_to_one"
        if row.relationship != expected:
            relationship_changes.append({"left_node_id": int(row.left_node_id), "before": row.relationship, "after": expected})
            links.at[index, "relationship"] = expected
    for frame in (candidates, links):
        if not set(frame.left_node_id).issubset(set(nodes.node_id)) or not set(frame.right_node_id).issubset(set(nodes.node_id)):
            raise ValueError("Staged source-link table has orphan IDs")
    if links.left_node_id.duplicated().any():
        raise ValueError("Staged source links are not one per left node")
    evidence = {
        "profile": profile,
        "old_nodes": len(old_nodes), "staged_nodes": len(nodes),
        "retained_ids": len(set(nodes.node_id) & set(old_nodes.node_id)),
        "new_ids": sorted(set(nodes.node_id) - set(old_nodes.node_id)),
        "retired_ids": sorted(retired), "changed_fingerprint_or_identity_ids": sorted(changed),
        "affected_county_years": sorted([list(g) for g in groups]),
        "outside_scope_nodes_sha256": digest(untouched_nodes),
        "outside_scope_fingerprints_sha256": digest(untouched_fingerprints),
        "preserved_link_rows": len(kept_links) - len(relationship_changes),
        "retained_links_before_relationship_updates_sha256": digest(kept_links),
        "relationship_only_changes": relationship_changes,
        "changed_links_requiring_review": int(links.left_node_id.isin(affected_ids).sum()),
        "affected_nodes_without_suggestion": sorted(affected_ids - set(links.left_node_id)),
    }
    return {"precinct_nodes": nodes, "precinct_vote_fingerprints": fingerprints,
            "precinct_match_candidates": candidates, "precinct_source_links": links}, evidence


def stage(database: Path, output: Path, profile=DEFAULT_PROFILE, expected_run=None):
    query = source_query(profile)
    if profile == OFFICE_PROFILE and not expected_run:
        raise ValueError("Office-label staging requires an explicit expected run")
    database, output = database.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError(f"Staging output must be new: {output}")
    tables = ["precinct_nodes", "precinct_vote_fingerprints", "precinct_match_candidates", "precinct_source_links"]
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        latest = connection.execute("SELECT build_run_id FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone() if "warehouse_build_run" in available else None
        latest = latest[0] if latest else None
        if expected_run is not None and latest != expected_run:
            raise ValueError("Warehouse run changed before staging")
        require_reported_vote_quality(connection, PROFILES[profile])
        votes = pd.read_sql_query(query, connection)
        old = {name: pd.read_sql_query(f'SELECT * FROM "{name}" ORDER BY rowid', connection) for name in tables}
        available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        runs = pd.read_sql_query("SELECT * FROM warehouse_build_run ORDER BY build_run_id", connection) if "warehouse_build_run" in available else pd.DataFrame()
        repairs = pd.read_sql_query("SELECT * FROM qa_warehouse_source_repair ORDER BY issue_id", connection) if "qa_warehouse_source_repair" in available else pd.DataFrame()
    frames, evidence = prepare(votes, *(old[name] for name in tables), profile=profile)
    output.mkdir(parents=True, exist_ok=False)
    outputs = {}
    # An interrupted directory has no manifest and is never an accepted stage; retain it for inspection.
    for name, frame in {**frames, **{f"before_{name}": frame for name, frame in old.items()}}.items():
        path = output / f"{name}.csv"
        frame.to_csv(path, index=False, mode="x")
        outputs[path.name] = {"rows": len(frame), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {
        "status": "staged_review_only", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(database), "read_mode": "mode=ro; PRAGMA query_only=ON; BEGIN snapshot",
        "profile": profile, "expected_run": expected_run, "warehouse_latest_run": latest,
        "source_scope": PROFILES[profile],
        "source_query": query, "source_fingerprint_input_sha256": digest(votes),
        "input_tables": {name: {"rows": len(frame), "sha256": digest(frame)} for name, frame in old.items()},
        "warehouse_runs": json.loads(runs.to_json(orient="records")),
        "repair_evidence": json.loads(repairs.to_json(orient="records")),
        "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), Path(__file__).with_name("build_precinct_identity.py"), Path(__file__).with_name("source_vote_quality.py"))},
        "validation": evidence, "outputs": outputs,
        "not_rebuilt": ["geography links", "manual adjudications", "allocation weights", "baselines", "models", "publications"],
        "promotion": "Not authorized by this command. Review changed links, reconcile dependent IDs and compare a fresh source snapshot before any transactional application.",
    }
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DB)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES, default=DEFAULT_PROFILE)
    parser.add_argument("--expected-run")
    args = parser.parse_args()
    report = stage(args.database, args.output, args.profile, args.expected_run)
    print(json.dumps({"status": report["status"], "output": str(args.output), "validation": report["validation"]}, indent=2))
