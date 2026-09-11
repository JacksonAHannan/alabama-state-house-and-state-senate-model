#!/usr/bin/env python3
"""Acquire exact-vintage 2012 precinct geometry for the remaining WAR states."""
from __future__ import annotations

import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from warehouse import ROOT


RAW = ROOT / "data/raw/presidential/southern_war_v4/precinct_geography_2012"
MANIFEST = ROOT / "data/processed/source_audits/southern_2012_precinct_geography_manifest.csv"
ELECTION_GEODATA_COMMIT = "eea3da5dbc7b02a282cd968dbd83c45674c01489"
VIRGINIA_COMMIT = "fc0095ac6fae5a58d315eb6029c4bb9fa73244d5"

SPECS = {
    "FL": {
        "filename": "fl_2012.zip",
        "url": "https://dataverse.harvard.edu/api/access/datafile/12070337",
        "expected_bytes": 21_245_980,
        "provider": "Voting and Election Science Team",
        "license_or_terms": "CC BY 4.0; preserve VEST citation and validation report",
        "geography_vintage": "2012 general-election precincts",
        "authoritative_scope": "VEST harmonized 2012 Florida precinct polygons and election results",
        "shapefile_hint": "fl_2012.shp",
    },
    "GA": {
        "filename": "ga-VTD2012.zip",
        "url": f"https://raw.githubusercontent.com/nvkelso/election-geodata/{ELECTION_GEODATA_COMMIT}/data/13-georgia/statewide/2012/ga-VTD2012.zip",
        "expected_bytes": 17_690_191,
        "provider": "Georgia Legislative and Congressional Reapportionment Office via Election Geodata",
        "license_or_terms": "Election Geodata permits reuse without permission; credit requested",
        "geography_vintage": "Georgia VTD 2012",
        "authoritative_scope": "2012 Georgia voting-district polygons archived from the state reapportionment office",
        "shapefile_hint": ".shp",
    },
    "MS": {
        "filename": "precincts_2012.zip",
        "url": f"https://raw.githubusercontent.com/nvkelso/election-geodata/{ELECTION_GEODATA_COMMIT}/data/28-mississippi/statewide/2012/precincts_2012.zip",
        "expected_bytes": 17_619_459,
        "provider": "Mississippi Automated Resource Information System via Election Geodata",
        "license_or_terms": "MARIS metadata states no access/use limitations; Election Geodata credit requested",
        "geography_vintage": "Mississippi voting precincts, 2012-03-30",
        "authoritative_scope": "State GIS 2012 Mississippi precinct polygons",
        "shapefile_hint": ".shp",
    },
    "NC": {
        "filename": "SBE_PRECINCTS_20120901.zip",
        "url": "https://s3.amazonaws.com/dl.ncsbe.gov/ShapeFiles/Precinct/SBE_PRECINCTS_20120901.zip",
        "expected_bytes": 19_398_769,
        "provider": "North Carolina State Board of Elections",
        "license_or_terms": "Official NCSBE public download; reuse terms not separately stated",
        "geography_vintage": "NCSBE precincts as of 2012-09-01",
        "authoritative_scope": "Official precinct polygons immediately preceding the 2012 general election",
        "shapefile_hint": ".shp",
    },
    "VA": {
        "filename": f"virginia-voting-precincts-{VIRGINIA_COMMIT}.zip",
        "url": f"https://github.com/erikalopresti/virginia-voting-precincts/archive/{VIRGINIA_COMMIT}.zip",
        "expected_bytes": None,
        "provider": "Virginia Voting Precincts project",
        "license_or_terms": "GPL-3.0; compiled from Virginia official and local GIS evidence",
        "geography_vintage": "Virginia November 2012 general-election precincts",
        "authoritative_scope": "Research reconstruction of 2012 Virginia precinct polygons",
        "shapefile_hint": "va_precincts_2012_nov_general.shp",
    },
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def acquire(state: str, spec: dict, offline: bool) -> dict:
    path = RAW / state / spec["filename"]
    path.parent.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    last_modified = ""
    if not path.exists():
        if offline:
            raise FileNotFoundError(path)
        with requests.get(
            spec["url"], headers={"User-Agent": "southern-war-research/1.0"},
            stream=True, timeout=180,
        ) as response:
            response.raise_for_status()
            temporary = path.with_suffix(path.suffix + ".part")
            with temporary.open("wb") as stream:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        stream.write(chunk)
            temporary.replace(path)
            last_modified = response.headers.get("last-modified", "")
    expected = spec["expected_bytes"]
    if expected is not None and path.stat().st_size != expected:
        raise ValueError(f"Unexpected byte count for {path}: {path.stat().st_size} != {expected}")
    return {
        "source_file_id": f"PRECINCT-GEOMETRY-2012-{state}",
        "provider": spec["provider"],
        "source_url": spec["url"],
        "retrieved_at": retrieved_at,
        "source_last_modified": last_modified,
        "sha256": digest(path),
        "size_bytes": path.stat().st_size,
        "media_type": "application/zip",
        "license_or_terms": spec["license_or_terms"],
        "state_code": state,
        "cycle": 2012,
        "geography_vintage": spec["geography_vintage"],
        "authoritative_scope": spec["authoritative_scope"],
        "shapefile_hint": spec["shapefile_hint"],
        "ingest_status": "acquired",
        "local_path": path.relative_to(ROOT).as_posix(),
    }


def build_manifest(offline: bool = False) -> pd.DataFrame:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows = list(pool.map(lambda item: acquire(item[0], item[1], offline), SPECS.items()))
    frame = pd.DataFrame(rows).sort_values("state_code")
    if len(frame) != len(SPECS) or frame.source_file_id.duplicated().any():
        raise ValueError("2012 precinct-geometry manifest is incomplete or duplicated")
    MANIFEST.write_text(frame.to_csv(index=False), encoding="utf-8")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    frame = build_manifest(args.offline)
    print(f"2012 precinct geography: {len(frame)} files, {int(frame.size_bytes.sum()):,} bytes")


if __name__ == "__main__":
    main()
