#!/usr/bin/env python3
"""Register the existing RDH/VEST Mississippi 2019 precinct archive.

The archive is not re-downloaded here.  It is an immutable input already in
the repository workspace, and its embedded README supplies the upstream
lineage used below.  The 2012 readiness workflow uses only its precinct names
and VTD codes as aliases; it does not substitute 2019 votes for 2012 votes.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/historical_statewide_elections/ms_gen_19_prec.zip"
MANIFEST = ROOT / "data/processed/source_audits/mississippi_2019_precinct_alias_manifest.csv"
SOURCE_URL = "https://dataverse.harvard.edu/file.xhtml?fileId=5706485&version=5.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register() -> dict[str, object]:
    if not RAW.exists():
        raise FileNotFoundError(
            f"Required immutable alias source is absent: {RAW}. "
            "Recover it from the pinned Dataverse file before continuing."
        )
    with zipfile.ZipFile(RAW) as archive:
        members = set(archive.namelist())
        required = {"README.txt", "ms_gen_19_sldl_prec.shp", "ms_gen_19_sldu_prec.shp"}
        if not required.issubset(members):
            raise ValueError(f"Unexpected Mississippi 2019 archive members: {required - members}")
        readme = archive.read("README.txt").decode("utf-8-sig", errors="replace")
    required_readme_text = (
        "2019 MS General Precinct Boundary and Election Results",
        "fileId=5706485&version=5.0",
        "RDH Date Retrieval\r\n10/27/2022",
    )
    if not all(text in readme for text in required_readme_text):
        raise ValueError("Mississippi 2019 archive README does not match the registered source")

    local_timestamp = dt.datetime.fromtimestamp(RAW.stat().st_mtime, dt.timezone.utc).isoformat()
    row: dict[str, object] = {
        "source_file_id": "RDH-VEST-2019-MS-PRECINCT",
        "provider": "Redistricting Data Hub redistribution of VEST",
        "source_url": SOURCE_URL,
        "retrieved_at": local_timestamp,
        "retrieval_timestamp_basis": "local immutable archive modification time",
        "upstream_rdh_retrieved_at": "2022-10-27",
        "sha256": sha256(RAW),
        "size_bytes": RAW.stat().st_size,
        "media_type": "application/zip",
        "license_or_terms": "CC BY 4.0; preserve VEST and RDH attribution and embedded README",
        "state_code": "MS",
        "cycle": 2019,
        "geography_vintage": "2019 Mississippi precincts split to the legislative plan used in 2019",
        "authoritative_scope": (
            "RDH/VEST precinct names and VTD codes used only as corroborating aliases for the "
            "Mississippi 2012 precinct-name crosswalk"
        ),
        "ingest_status": "registered_existing_immutable_archive",
        "local_path": RAW.relative_to(ROOT).as_posix(),
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return row


if __name__ == "__main__":
    print(register())
