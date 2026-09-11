"""Read-only LegiScan eligibility boundary; SQL owns reconciliation policy."""
from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3

import pandas as pd

from warehouse import connect


@contextmanager
def source_snapshot():
    with closing(connect(readonly=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        yield connection


def read_member_votes():
    """Return canonical observations, never votes copied from a stale CSV."""
    with source_snapshot() as connection:
        return pd.read_sql_query("SELECT * FROM canonical_legiscan_member_vote", connection)


def read_roll_calls():
    with source_snapshot() as connection:
        return pd.read_sql_query("SELECT * FROM canonical_legiscan_roll_call", connection)


def _fingerprint(rows):
    digest = hashlib.sha256()
    for row in rows:
        # SQLite may expose integral counts as REAL in concatenated exports.
        values = [int(v) if isinstance(v, float) and v.is_integer() else v for v in row]
        digest.update(json.dumps(values, ensure_ascii=True, separators=(',', ':')).encode())
        digest.update(b'\n')
    return digest.digest()


@contextmanager
def checked_standalone(path: Path):
    """Hold a read snapshot after checking exact LegiScan content parity.

    Journal rows are outside this provider check. Missing/rejected/changed
    LegiScan rows fail closed; timestamps and matching IDs alone are not proof.
    Only relevant ordered rows are hashed, never the whole central database.
    """
    with source_snapshot() as source, closing(sqlite3.connect(
        Path(path).resolve().as_uri() + '?mode=ro', uri=True
    )) as local:
        local.execute('PRAGMA query_only=ON')
        local.execute('BEGIN')
        pairs = [
            ("""SELECT 'LS-'||r.roll_call_id, r.session_year, r.chamber, r.vote_date,
                       r.vote_description, r.yea, r.nay, b.bill_number
                FROM canonical_legiscan_roll_call r
                JOIN source_legiscan_bill b USING(bill_id) ORDER BY 1""",
             """SELECT canonical_rollcall_id,session_year,chamber,vote_date,
                       vote_description,yea_total,nay_total,bill_number
                FROM rollcall WHERE canonical_rollcall_id LIKE 'LS-%' ORDER BY 1"""),
            ("""SELECT 'LS-'||roll_call_id,session_year,chamber,
                       'LEGISCAN-'||people_id,vote
                FROM canonical_legiscan_member_vote ORDER BY 1,4,2,3,5""",
             """SELECT canonical_rollcall_id,session_year,chamber,member_source_id,vote
                FROM member_vote WHERE canonical_rollcall_id LIKE 'LS-%'
                ORDER BY 1,4,2,3,5"""),
        ]
        for expected, observed in pairs:
            if _fingerprint(source.execute(expected)) != _fingerprint(local.execute(observed)):
                raise ValueError('LegiScan standalone snapshot differs from canonical source; '
                                 'review dependencies before a scoped rebuild')
        yield local
