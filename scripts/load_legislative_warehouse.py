"""Load normalized LegiScan compatibility CSVs into constrained warehouse tables."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd

from warehouse import (ROOT, begin_run, connect, finish_run, initialize, register_source_file,
                       register_table, source_file_id)

LEG=ROOT/"data"/"processed"/"legislative"
RAW=ROOT/"data"/"raw"/"legiscan"/"alabama"
SCHEMA=Path(__file__).with_name("warehouse_legislative_schema.sql")

FILES={
 "source_legiscan_bill":"legiscan_alabama_bills.csv",
 "source_legiscan_roll_call":"legiscan_alabama_rollcalls.csv",
 "source_legiscan_legislator_session":"legiscan_alabama_legislators.csv",
 "source_legiscan_member_vote":"legiscan_alabama_individual_votes.csv",
 "source_legiscan_bill_sponsor":"legiscan_bill_sponsors.csv",
 "source_legiscan_bill_history":"legiscan_bill_history.csv",
 "source_legiscan_bill_subject":"legiscan_bill_subjects.csv",
 "source_legiscan_amendment":"legiscan_bill_amendments.csv",
 "source_legiscan_bill_document":"legiscan_bill_text_manifest.csv",
}

LOAD_ORDER=["source_legiscan_bill","source_legiscan_legislator_session",
            "source_legiscan_roll_call","source_legiscan_member_vote",
            "source_legiscan_bill_sponsor","source_legiscan_bill_history",
            "source_legiscan_bill_subject","source_legiscan_amendment",
            "source_legiscan_bill_document"]


def clean(value):
    if value is None or (isinstance(value,float) and np.isnan(value)):return None
    if isinstance(value,np.generic):return value.item()
    return value


def insert_frame(connection: sqlite3.Connection,table: str,frame: pd.DataFrame,
                 chunk_size: int=50000) -> None:
    columns=list(frame.columns); placeholders=",".join("?" for _ in columns)
    sql=f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
    for start in range(0,len(frame),chunk_size):
        rows=([clean(v) for v in row] for row in frame.iloc[start:start+chunk_size].itertuples(index=False,name=None))
        connection.executemany(sql,rows)


def archive_registry(connection: sqlite3.Connection) -> dict[str,str]:
    manifest=pd.read_csv(LEG/"legiscan_source_manifest.csv")
    result={}
    for row in manifest.itertuples(index=False):
        path=RAW/row.source_archive
        if not path.exists():continue
        identifier=register_source_file(connection,provider="legiscan",path=path,
            original_url=row.source_url,license_name=row.license,extraction_status="normalized",
            authoritative_scope="structured_legislative_records")
        result[row.source_archive]=identifier
    return result


def sessions(bills: pd.DataFrame) -> pd.DataFrame:
    frame=bills[["session_id","session_year","session_name"]].dropna(subset=["session_id"]).drop_duplicates()
    frame["session_id"]=frame.session_id.astype(int)
    if frame.session_id.duplicated().any():raise ValueError("Conflicting LegiScan session metadata")
    return frame


def people_table(legislators: pd.DataFrame,votes_path: Path,sponsors: pd.DataFrame) -> pd.DataFrame:
    roster=(legislators.sort_values("session_year").drop_duplicates("people_id",keep="last")
            [["people_id","name","normalized_name"]].rename(columns={"name":"preferred_name"}))
    ids=set(roster.people_id.astype(int)); extras=set(sponsors.people_id.dropna().astype(int))
    for chunk in pd.read_csv(votes_path,usecols=["people_id"],chunksize=250000):
        extras.update(chunk.people_id.dropna().astype(int))
    stubs=pd.DataFrame({"people_id":sorted(extras-ids),"preferred_name":None,"normalized_name":None})
    roster["record_status"]="roster"; stubs["record_status"]="vote_only_stub"
    return pd.concat([roster,stubs],ignore_index=True)


def identity_matches() -> pd.DataFrame:
    proposed=pd.read_csv(LEG/"legiscan_candidate_identity_matches.csv")
    proposed=proposed[proposed.match_status.eq("exact_name_candidate") & proposed.person_id.notna()]
    proposed=(proposed[["people_id","person_id"]].drop_duplicates()
              .assign(match_method="exact_name_candidate",review_status="proposed",
                      evidence_locator="data/processed/legislative/legiscan_candidate_identity_matches.csv",
                      review_note=None))
    reviewed_path=ROOT/"research"/"cmo_ideology"/"focal_legislator_identity_crosswalk.csv"
    reviewed=pd.read_csv(reviewed_path)
    reviewed=reviewed[reviewed.review_status.eq("reviewed") & reviewed.legiscan_people_id.notna()]
    approved=pd.DataFrame({"people_id":reviewed.legiscan_people_id.astype(int),"person_id":reviewed.person_id,
        "match_method":reviewed.match_method,"review_status":"approved",
        "evidence_locator":"research/cmo_ideology/focal_legislator_identity_crosswalk.csv",
        "review_note":reviewed.review_note})
    return pd.concat([proposed,approved],ignore_index=True).drop_duplicates(
        ["people_id","person_id","match_method"],keep="last")


def load() -> dict[str,int]:
    frames={name:pd.read_csv(LEG/file) for name,file in FILES.items() if name!="source_legiscan_member_vote"}
    votes_path=LEG/FILES["source_legiscan_member_vote"]
    expected={name:(sum(len(c) for c in pd.read_csv(votes_path,chunksize=250000)) if name=="source_legiscan_member_vote" else len(frame))
              for name,frame in {**frames,"source_legiscan_member_vote":pd.DataFrame()}.items()}
    with closing(connect()) as connection:
        initialize(connection); connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        archive_ids=archive_registry(connection)
        run_id=begin_run(connection,"legislative_source_and_identity",{"compatibility_files":FILES})
        connection.commit()
        connection.execute("PRAGMA defer_foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        for table in reversed(LOAD_ORDER):connection.execute(f"DELETE FROM {table}")
        connection.execute("DELETE FROM canonical_legislator_person_match")
        connection.execute("DELETE FROM source_legiscan_person")
        connection.execute("DELETE FROM source_legiscan_session")
        insert_frame(connection,"source_legiscan_session",sessions(frames["source_legiscan_bill"]))
        people=people_table(frames["source_legiscan_legislator_session"],votes_path,frames["source_legiscan_bill_sponsor"])
        insert_frame(connection,"source_legiscan_person",people)
        for table in LOAD_ORDER:
            if table=="source_legiscan_member_vote":
                for frame in pd.read_csv(votes_path,chunksize=100000):
                    frame["source_file_id"]=frame.source_archive.map(archive_ids)
                    insert_frame(connection,table,frame)
            else:
                frame=frames[table].copy()
                if "source_archive" in frame:
                    frame["source_file_id"]=frame.source_archive.map(archive_ids)
                insert_frame(connection,table,frame)
        matches=identity_matches(); insert_frame(connection,"canonical_legislator_person_match",matches)
        fk=connection.execute("PRAGMA foreign_key_check").fetchall()
        if fk:raise ValueError(f"Legislative foreign-key failures: {fk[:10]}")
        actual={table:connection.execute(f"select count(*) from {table}").fetchone()[0] for table in LOAD_ORDER}
        if actual!=expected:raise ValueError(f"CSV parity failure: expected={expected}, actual={actual}")
        connection.commit()
        for table,key,description in [
            ("source_legiscan_bill","bill_id","Normalized LegiScan bills"),
            ("source_legiscan_roll_call","roll_call_id","Recorded legislative roll calls"),
            ("source_legiscan_member_vote","roll_call_id + people_id","Individual recorded member votes"),
            ("source_legiscan_bill_sponsor","bill_id + people_id + sponsor_order","Bill sponsorship observations"),
            ("canonical_legislator_identity","people_id + person_id","Human-approved legislator/person links"),
        ]:
            register_table(connection,table,"canonical" if table.startswith("canonical") else "source",
                "scripts/load_legislative_warehouse.py",key,
                "LegiScan structured source; ALISON verification; reviewed links only for canonical identity",
                "view" if table.startswith("canonical") else "replace",description)
        finish_run(connection,run_id,{**actual,"people":len(people),"approved_identity_links":int((matches.review_status=="approved").sum())})
        connection.commit()
    return actual


if __name__=="__main__":
    result=load()
    print("\n".join(f"{table}: {rows:,}" for table,rows in result.items()))
