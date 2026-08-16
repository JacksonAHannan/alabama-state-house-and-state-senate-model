"""Build an atomic, standalone 1998-2026 roll-call research warehouse."""
from __future__ import annotations

from pathlib import Path
import os
import sqlite3

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"
DB = DATA / "alabama_legislative_rollcalls_1998_2026.sqlite"


def main() -> None:
    temp = DB.with_suffix(".sqlite.tmp")
    if temp.exists():
        temp.unlink()
    connection = sqlite3.connect(temp)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")

    historical_rollcalls = []
    for chamber in ("house", "senate"):
        frame = pd.read_csv(DATA / f"historical_{chamber}_journal_rollcalls.csv")
        frame = frame[frame.count_valid].copy()
        frame["canonical_rollcall_id"] = frame.rollcall_id
        frame["source_system"] = "adah_journal"
        frame["vote_date"] = None
        frame["vote_description"] = frame.motion_type
        frame["passed"] = None
        historical_rollcalls.append(frame[[
            "canonical_rollcall_id", "source_system", "session_year", "chamber", "vote_date",
            "bill_type", "bill_number", "vote_description", "motion_type", "yea_total", "nay_total",
            "abstain_total", "passed", "local_path", "page",
        ]])
    historical_rollcalls = pd.concat(historical_rollcalls, ignore_index=True)

    eligibility = pd.read_csv(DATA / "legiscan_rollcall_analysis_eligibility.csv")
    eligibility = eligibility[eligibility.reported_total_matches.eq(1)].copy()
    eligibility["canonical_rollcall_id"] = "LS-" + eligibility.roll_call_id.astype(str)
    eligibility["source_system"] = "legiscan"
    eligibility["motion_type"] = "legiscan_recorded_vote"
    eligibility["yea_total"] = eligibility.yea
    eligibility["nay_total"] = eligibility.nay
    eligibility["abstain_total"] = 0
    eligibility["local_path"] = eligibility.source_member
    eligibility["page"] = None
    legiscan_rollcalls = eligibility[[
        "canonical_rollcall_id", "source_system", "session_year", "chamber", "vote_date",
        "bill_type", "bill_number", "vote_description", "motion_type", "yea_total", "nay_total",
        "abstain_total", "passed", "local_path", "page",
    ]]
    rollcalls = pd.concat([historical_rollcalls, legiscan_rollcalls], ignore_index=True)
    rollcalls.to_sql("rollcall", connection, index=False, if_exists="replace")

    historical_votes = pd.read_csv(DATA / "historical_journal_member_votes_identified.csv")
    historical_votes = historical_votes[historical_votes.count_valid].copy()
    historical_votes["canonical_rollcall_id"] = historical_votes.rollcall_id
    historical_votes["source_system"] = "adah_journal"
    historical_votes["member_source_id"] = historical_votes.shor_u_id
    historical_votes["member_display_name"] = historical_votes.shor_name.fillna(historical_votes.member_name)
    historical_votes["identity_status"] = historical_votes.match_status
    historical_votes[[
        "canonical_rollcall_id", "source_system", "session_year", "chamber", "member_source_id",
        "member_display_name", "identity_status", "party", "district", "vote",
    ]].to_sql("member_vote", connection, index=False, if_exists="replace", chunksize=50000)

    eligible_ids = set(eligibility.roll_call_id.astype(int))
    legislators = pd.read_csv(DATA / "legiscan_alabama_legislators.csv")
    people = (legislators.sort_values("session_year").drop_duplicates("people_id", keep="last")
              [["people_id", "name", "party", "district"]])
    first = True
    for chunk in pd.read_csv(DATA / "legiscan_alabama_individual_votes.csv", chunksize=200000):
        chunk = chunk[chunk.roll_call_id.isin(eligible_ids)].merge(people, on="people_id", how="left", validate="many_to_one")
        chunk["canonical_rollcall_id"] = "LS-" + chunk.roll_call_id.astype(str)
        chunk["source_system"] = "legiscan"
        chunk["member_source_id"] = "LEGISCAN-" + chunk.people_id.astype(str)
        chunk["member_display_name"] = chunk.name
        chunk["identity_status"] = "legiscan_people_id"
        chunk[[
            "canonical_rollcall_id", "source_system", "session_year", "chamber", "member_source_id",
            "member_display_name", "identity_status", "party", "district", "vote",
        ]].to_sql("member_vote", connection, index=False, if_exists="append", chunksize=50000)
        first = False

    connection.executescript("""
    CREATE UNIQUE INDEX rollcall_pk ON rollcall(canonical_rollcall_id);
    CREATE INDEX rollcall_year_chamber ON rollcall(session_year, chamber);
    CREATE INDEX member_vote_rollcall ON member_vote(canonical_rollcall_id);
    CREATE INDEX member_vote_member ON member_vote(member_source_id, session_year);
    CREATE TABLE build_metadata AS
      SELECT datetime('now') AS built_utc, 1 AS schema_version,
             'ADAH journals 1998-2009 plus LegiScan 2010-2026' AS scope;
    """)
    coverage = pd.read_sql_query("""
      SELECT r.session_year, r.chamber, r.source_system,
             COUNT(DISTINCT r.canonical_rollcall_id) AS rollcalls,
             COUNT(v.canonical_rollcall_id) AS member_votes,
             SUM(CASE WHEN v.member_source_id IS NOT NULL THEN 1 ELSE 0 END) AS identified_member_votes
      FROM rollcall r LEFT JOIN member_vote v USING(canonical_rollcall_id)
      GROUP BY 1,2,3 ORDER BY 1,2,3
    """, connection)
    coverage.to_csv(DATA / "unified_legislative_rollcall_coverage.csv", index=False)
    connection.commit()
    connection.close()
    os.replace(temp, DB)
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
