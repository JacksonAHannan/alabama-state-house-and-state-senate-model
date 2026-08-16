"""Load existing checked source manifests into the central warehouse registry."""
from __future__ import annotations

import mimetypes
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from warehouse import ROOT, connect, initialize, source_file_id, utcnow

MANIFESTS = [
    ("census_acs", ROOT/"data/raw/acs/block_group_joint/source_manifest.csv", "local_path", "source_url", "retrieved_on"),
    ("internet_archive_adah", ROOT/"data/raw/alabama_legislature/acts/internet_archive/source_manifest.csv", "local_path", "source_url", "retrieved_at_utc"),
    ("alabama_legislature", ROOT/"data/raw/alabama_legislature/house_journals/manifest.csv", "local_path", "source_url", None),
    ("us_census", ROOT/"data/raw/census/source_manifest.csv", "filename", "url", "checked_utc"),
    ("pollster_document", ROOT/"data/raw/polling/silver_recent/manifest.csv", "filename", "source_url", "retrieved_utc"),
]


def resolve_path(manifest: Path, value: object) -> Path:
    path=Path(str(value))
    if path.is_absolute():return path
    from_root=ROOT/path
    return from_root if from_root.exists() else manifest.parent/path


def main() -> None:
    rows=[]
    with closing(connect()) as connection:
        initialize(connection)
        # Election source records predate the general registry.
        if connection.execute("select count(*) from sqlite_master where type='table' and name='source_manifest'").fetchone()[0]:
            for source_id,year,provider,path,digest,authoritative in connection.execute(
                    "select source_id,year,source,path,sha256,authoritative_votes from source_manifest"):
                rows.append((provider,ROOT/path,None,None,digest,
                             "normalized","official_vote_counts" if authoritative else "identity_enrichment"))
        for provider,manifest,path_col,url_col,time_col in MANIFESTS:
            if not manifest.exists():continue
            frame=pd.read_csv(manifest)
            for record in frame.to_dict("records"):
                digest=str(record.get("sha256","")).strip().lower()
                if len(digest)!=64:continue
                path=resolve_path(manifest,record.get(path_col,""))
                if not path.exists():continue
                status="normalized" if provider in {"census_acs","us_census"} else "registered"
                rows.append((provider,path,record.get(url_col),record.get(time_col) if time_col else None,
                             digest,status,None))
        for provider,path,url,retrieved,digest,status,scope in rows:
            relative=path.resolve().relative_to(ROOT).as_posix()
            connection.execute("""INSERT INTO warehouse_source_file
              (source_file_id,provider,local_path,original_url,retrieved_at_utc,sha256,media_type,
               license,extraction_status,authoritative_scope)
              VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_file_id) DO UPDATE SET
              original_url=excluded.original_url,retrieved_at_utc=coalesce(excluded.retrieved_at_utc,warehouse_source_file.retrieved_at_utc),
              sha256=excluded.sha256,media_type=excluded.media_type,
              extraction_status=excluded.extraction_status,authoritative_scope=coalesce(excluded.authoritative_scope,warehouse_source_file.authoritative_scope)""",
              (source_file_id(provider,relative),provider,relative,None if pd.isna(url) else url,
               utcnow() if retrieved is None or pd.isna(retrieved) else str(retrieved),digest,
               mimetypes.guess_type(path.name)[0],None,status,scope))
        connection.commit()
        print(pd.read_sql("select provider,count(*) files,sum(case when extraction_status='normalized' then 1 else 0 end) normalized from warehouse_source_file group by provider order by provider",connection).to_string(index=False))


if __name__=="__main__":main()
