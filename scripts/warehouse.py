"""Shared lifecycle and contract helpers for the project SQLite warehouse."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite"
SCHEMA = Path(__file__).with_name("warehouse_schema.sql")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def database_path() -> Path:
    override = os.environ.get("ALABAMA_WAREHOUSE_PATH")
    return Path(override).resolve() if override else DEFAULT_DB


def connect(path: Path | None = None, readonly: bool = False) -> sqlite3.Connection:
    target = (path or database_path()).resolve()
    if readonly:
        connection = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(target)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_file_id(provider: str, relative_path: str) -> str:
    token = hashlib.sha256(f"{provider}:{relative_path}".encode()).hexdigest()[:20]
    return f"SRC-{token.upper()}"


def register_source_file(connection: sqlite3.Connection, *, provider: str, path: Path,
                         original_url: str | None = None, media_type: str | None = None,
                         license_name: str | None = None, extraction_status: str = "registered",
                         authoritative_scope: str | None = None,
                         project_root: Path = ROOT) -> str:
    relative = path.resolve().relative_to(project_root.resolve()).as_posix()
    identifier = source_file_id(provider, relative)
    connection.execute("""
      INSERT INTO warehouse_source_file
      (source_file_id,provider,local_path,original_url,retrieved_at_utc,sha256,media_type,
       license,extraction_status,authoritative_scope)
      VALUES (?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(source_file_id) DO UPDATE SET
        original_url=excluded.original_url, sha256=excluded.sha256,
        media_type=excluded.media_type, license=excluded.license,
        extraction_status=excluded.extraction_status,
        authoritative_scope=excluded.authoritative_scope
    """, (identifier, provider, relative, original_url, utcnow(), file_sha256(path), media_type,
          license_name, extraction_status, authoritative_scope))
    return identifier


def register_table(connection: sqlite3.Connection, name: str, layer: str, owner: str,
                   key: str | None, authority: str | None, lifecycle: str,
                   description: str) -> None:
    connection.execute("""
      INSERT INTO warehouse_table_registry
      (table_name,layer,owner_script,primary_key_description,authority_policy,lifecycle,description)
      VALUES (?,?,?,?,?,?,?)
      ON CONFLICT(table_name) DO UPDATE SET layer=excluded.layer,
        owner_script=excluded.owner_script, primary_key_description=excluded.primary_key_description,
        authority_policy=excluded.authority_policy, lifecycle=excluded.lifecycle,
        description=excluded.description
    """, (name, layer, owner, key, authority, lifecycle, description))


def begin_run(connection: sqlite3.Connection, target: str, configuration: dict) -> str:
    run_id = f"RUN-{uuid.uuid4().hex.upper()}"
    connection.execute("INSERT INTO warehouse_build_run VALUES (?,?,?,?,?,?,?,?)",
                       (run_id, target, utcnow(), None, "running", git_commit(),
                        json.dumps(configuration, sort_keys=True), None))
    return run_id


def finish_run(connection: sqlite3.Connection, run_id: str, validation: dict) -> None:
    connection.execute("""UPDATE warehouse_build_run SET completed_at_utc=?,status='validated',
                       validation_json=? WHERE build_run_id=?""",
                       (utcnow(), json.dumps(validation, sort_keys=True), run_id))


def install_identity_contracts(connection: sqlite3.Connection) -> None:
    """Add constrained canonical identity access paths after identity tables exist."""
    connection.executescript("""
      CREATE UNIQUE INDEX IF NOT EXISTS canonical_candidate_id_pk
        ON canonical_candidates(canonical_candidate_id);
      CREATE UNIQUE INDEX IF NOT EXISTS canonical_candidate_election_uk
        ON canonical_candidates(year,chamber,district,canonical_party);
      CREATE UNIQUE INDEX IF NOT EXISTS candidate_party_affiliation_uk
        ON candidate_party_affiliations(person_id,canonical_candidate_id,year,chamber,district,canonical_party);
      DROP VIEW IF EXISTS dim_person;
      CREATE VIEW dim_person AS
      WITH ranked AS (
        SELECT person_id,canonical_name,year,
               row_number() OVER (PARTITION BY person_id ORDER BY year DESC,canonical_name) AS rank
        FROM canonical_candidates
      )
      SELECT person_id,canonical_name AS preferred_name,
             (SELECT min(c.year) FROM canonical_candidates c WHERE c.person_id=ranked.person_id) AS first_election_year,
             (SELECT max(c.year) FROM canonical_candidates c WHERE c.person_id=ranked.person_id) AS last_election_year
      FROM ranked WHERE rank=1;
      DROP VIEW IF EXISTS fact_candidate_election;
      CREATE VIEW fact_candidate_election AS
      SELECT canonical_candidate_id,person_id,year,chamber,district,canonical_party AS party,
             canonical_name AS ballot_name,canonical_votes AS votes,incumbent,winner,canonical_source
      FROM canonical_candidates;
      DROP VIEW IF EXISTS bridge_person_alias;
      CREATE VIEW bridge_person_alias AS
      SELECT DISTINCT c.person_id,a.canonical_candidate_id,a.source,a.year,a.ballot_name,a.candidate_key,
             a.match_status,a.composite_score
      FROM candidate_aliases a JOIN canonical_candidates c USING(canonical_candidate_id);
    """)


def git_commit() -> str | None:
    head = ROOT / ".git" / "HEAD"
    if not head.exists(): return None
    value = head.read_text(encoding="utf-8").strip()
    if value.startswith("ref: "):
        ref = ROOT / ".git" / value[5:]
        return ref.read_text(encoding="utf-8").strip() if ref.exists() else None
    return value


@contextmanager
def atomic_database(target: Path) -> Iterator[Path]:
    """Yield a temporary database path and atomically publish it on success."""
    target = target.resolve()
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.building")
    try:
        yield temporary
        with closing(connect(temporary, readonly=True)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("SQLite integrity check failed")
        os.replace(temporary, target)
    finally:
        if temporary.exists(): temporary.unlink()
