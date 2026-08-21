"""Catalog currently available Alabama precinct/VTD geometry snapshots."""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from warehouse import (ROOT, begin_run, connect, finish_run, initialize,
                       register_source_file, register_table)

# Explicit inventory: a filename match is not enough to establish temporal validity.
SNAPSHOTS = [
  {"path":"data/raw/alabama_elections_and_geography/tl_2012_01_vtd10.zip",
   "snapshot_date":"2010-04-01","election_date":None,"source_type":"census_vtd",
   "coverage":"statewide","apparent_valid_from":None,"apparent_valid_to":None,
   "notes":"2010 Census VTD geography distributed in the 2012 TIGER/Line release; not assumed valid for a decade."},
  {"path":"data/raw/alabama_elections_and_geography/al_vest_16.zip",
   "snapshot_date":"2016-11-08","election_date":"2016-11-08","source_type":"vest_election_precinct",
   "coverage":"statewide","apparent_valid_from":"2016-11-08","apparent_valid_to":"2016-11-08",
   "notes":"VEST election-specific precinct geometry."},
  {"path":"data/raw/alabama_elections_and_geography/al_vest_18.zip",
   "snapshot_date":"2018-11-06","election_date":"2018-11-06","source_type":"vest_election_precinct",
   "coverage":"statewide","apparent_valid_from":"2018-11-06","apparent_valid_to":"2018-11-06",
   "notes":"VEST election-specific precinct geometry."},
  {"path":"data/raw/alabama_elections_and_geography/al_vest_20.zip",
   "snapshot_date":"2020-11-03","election_date":"2020-11-03","source_type":"vest_election_precinct",
   "coverage":"statewide","apparent_valid_from":"2020-11-03","apparent_valid_to":"2020-11-03",
   "notes":"VEST election-specific precinct geometry."},
]


def snapshot_id(path: str, date: str | None) -> str:
    import hashlib
    return "SNAP-" + hashlib.sha256(f"{path}|{date}".encode()).hexdigest()[:20].upper()


def main() -> None:
    rows=[]
    for spec in SNAPSHOTS:
        path=ROOT/spec["path"]
        row={**spec,"available":path.exists(),"bytes":path.stat().st_size if path.exists() else None,
             "feature_count":None,"crs":None,"geometry_types":None}
        if path.exists():
            geography=gpd.read_file(path)
            row.update(feature_count=len(geography),crs=str(geography.crs),
                       geometry_types=json.dumps(geography.geometry.geom_type.value_counts().to_dict(),sort_keys=True))
        row["snapshot_id"]=snapshot_id(spec["path"],spec["snapshot_date"]);rows.append(row)
    result=pd.DataFrame(rows)
    out=ROOT/"data/processed/precinct_history/geometry_snapshot_inventory.csv";out.parent.mkdir(parents=True,exist_ok=True)
    result.to_csv(out,index=False)
    with connect() as connection:
        initialize(connection);connection.executescript(
            Path(__file__).with_name("warehouse_precinct_history_schema.sql").read_text(encoding="utf-8"))
        run=begin_run(connection,"precinct_geometry_snapshot_catalog",{"configured_snapshots":len(result)})
        connection.execute("DELETE FROM precinct_snapshot")
        for row in rows:
            if not row["available"]:continue
            path=ROOT/row["path"]
            source_id=register_source_file(connection,provider=row["source_type"],path=path,
              media_type="application/zip",extraction_status="normalized",
              authoritative_scope="observed_precinct_geometry_snapshot")
            connection.execute("""INSERT INTO precinct_snapshot
              (snapshot_id,snapshot_date,election_date,source_file_id,source_type,coverage,
               apparent_valid_from,apparent_valid_to,notes) VALUES (?,?,?,?,?,?,?,?,?)""",
              (row["snapshot_id"],row["snapshot_date"],row["election_date"],source_id,row["source_type"],
               row["coverage"],row["apparent_valid_from"],row["apparent_valid_to"],row["notes"]))
        register_table(connection,"precinct_snapshot","canonical","scripts/catalog_precinct_geometry_snapshots.py",
          "snapshot_id","Explicit source/date metadata; never extrapolate across a decade","replace",
          "Observed precinct and VTD geometry snapshots")
        finish_run(connection,run,{"available":int(result.available.sum()),"missing":int((~result.available).sum())})
        connection.commit()
    print(result[["snapshot_date","source_type","available","feature_count","crs"]].to_string(index=False))


if __name__=="__main__":main()
