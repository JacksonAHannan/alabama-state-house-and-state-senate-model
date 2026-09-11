#!/usr/bin/env python3
"""Acquire immutable presidential-context sources for Southern WAR v4.

The 2016 Redistricting Data Hub files are disaggregated to 2020 Census
blocks, so they can be joined exactly to the national 2022 state-legislative
block assignment file already in the repository.  Daily Kos's public source
index is snapshotted as provenance for its older-plan district tables.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import re
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/presidential/southern_war_v4"
MANIFEST = ROOT / "data/processed/source_audits/southern_war_v4_presidential_manifest.csv"
DAILY_KOS_INDEX_URL = (
    "https://www.dailykos.com/stories/2021/3/23/1220127/"
    "-Daily-Kos-Elections-statewide-election-results-by-congressional-and-legislative-districts"
)
RDH_DOWNLOADS = {
    "AL": (37232, "al_2016_gen_2020_blocks.zip"),
    "AR": (37210, "ar_2016_gen_2020_blocks.zip"),
    "FL": (37216, "fl_2016_gen_2020_blocks.zip"),
    "GA": (37196, "ga_2016_gen_2020_blocks.zip"),
    "KY": (37226, "ky_2016_gen_2020_blocks.zip"),
    "LA": (37229, "la_2016_gen_2020_blocks.zip"),
    "MS": (37231, "ms_2016_gen_2020_blocks.zip"),
    "MO": (37217, "mo_2016_gen_2020_blocks.zip"),
    "NC": (37198, "nc_2016_gen_2020_blocks.zip"),
    "OK": (37235, "ok_2016_gen_2020_blocks.zip"),
    "SC": (37240, "sc_2016_gen_2020_blocks.zip"),
    "TN": (37228, "tn_2016_gen_2020_blocks.zip"),
    "TX": (37204, "tx_2016_gen_2020_blocks.zip"),
    "VA": (37208, "va_2016_gen_2020_blocks.zip"),
}
SUPPLEMENTAL_2012 = (
    {
        "source_file_id": "OPENELECTIONS-2012-GA-PRECINCT",
        "provider": "OpenElections",
        "source_url": (
            "https://raw.githubusercontent.com/openelections/openelections-data-ga/"
            "86bf341e68775bae06a54538dae0311fb6201872/2012/20121106__ga__general.csv"
        ),
        "state_code": "GA",
        "license_or_terms": "OpenElections public repository; underlying Georgia SOS/Clarity results",
        "filename": "20121106__ga__general.csv",
        "local_path": "data/raw/openelections_historical_gaps/GA/2012/20121106__ga__general.csv",
        "retrieved_at": "2026-08-22T16:26:29+00:00",
    },
    {
        "source_file_id": "OPENELECTIONS-2012-MS-PRECINCT",
        "provider": "OpenElections",
        "source_url": (
            "https://raw.githubusercontent.com/openelections/openelections-data-ms/"
            "ed58cb2d2480744f02aac7a285b47d10676ff14d/2012/"
            "20121106__ms__general__precinct.csv"
        ),
        "state_code": "MS",
        "license_or_terms": "OpenElections public repository; converted Mississippi county results",
        "filename": "20121106__ms__general__precinct.csv",
        "local_path": (
            "data/raw/openelections_historical_gaps/MS/2012/"
            "20121106__ms__general__precinct.csv"
        ),
        "retrieved_at": "2026-09-03T23:16:01+00:00",
    },
    {
        "source_file_id": "NCSBE-2012-NC-GENERAL-PRECINCT",
        "provider": "North Carolina State Board of Elections",
        "source_url": "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2012_11_06/results_pct_20121106.zip",
        "state_code": "NC",
        "license_or_terms": "official public election-result download",
        "filename": "results_pct_20121106.zip",
        "local_path": "data/raw/southern_sos_elections/NC/2012/results_pct_20121106.zip",
        "retrieved_at": "2026-08-22T05:49:55+00:00",
    },
    {
        "source_file_id": "VAELECTIONS-2012-VA-PRESIDENT-PRECINCT",
        "provider": "Virginia Department of Elections historical database",
        "source_url": "https://va2.elstats.civera.com/api/download_contest/44930_table.csv?split_party=false",
        "state_code": "VA",
        "license_or_terms": "official public historical election-result export",
        "filename": "2012_president_contest_44930.csv",
        "local_path": "data/raw/southern_sos_elections/VA/2012/2012_president_contest_44930.csv",
    },
    {
        "source_file_id": "FLDOS-2012-FL-GENERAL-PRECINCT",
        "provider": "Florida Department of State Division of Elections",
        "source_url": "https://files.floridados.gov/media/697204/precinctlevelelectionresults2012gen.zip",
        "state_code": "FL",
        "license_or_terms": "official public precinct-level election-result download",
        "filename": "precinctlevelelectionresults2012gen.zip",
        "local_path": (
            "data/raw/southern_sos_elections/FL/2012/"
            "precinctlevelelectionresults2012gen.zip"
        ),
        "retrieved_at": "2026-08-22T05:48:00+00:00",
    },
)

NATIONAL_CONTEXT = (
    {
        "source_file_id": "RDH-NATIONAL-2020-PRES-BLOCKS",
        "provider": "Redistricting Data Hub",
        "source_url": (
            "https://redistrictingdatahub.org/dataset/"
            "2020-presidential-democratic-republican-vote-share-on-nationwide-2020-census-blocks/"
        ),
        "state_code": "MULTI",
        "election_cycle": "2020",
        "geography_vintage": "2020 Census blocks",
        "authoritative_scope": (
            "VEST presidential precinct returns disaggregated by RDH to 2020 Census blocks"
        ),
        "media_type": "application/zip",
        "license_or_terms": "Redistricting Data Hub public download; preserve README and attribution",
        "filename": "national_block_2020_pres_results.zip",
        "local_path": (
            "data/raw/historical_statewide_elections/national_block_2020_pres_results.zip"
        ),
        "retrieved_at": "2023-04-26",
    },
    {
        "source_file_id": "NYT-NATIONAL-2024-PRES-PRECINCT-RESULTS",
        "provider": "The New York Times",
        "source_url": (
            "https://int.nyt.com/newsgraphics/elections/map-data/2024/national/"
            "precincts-with-results.csv.gz"
        ),
        "state_code": "MULTI",
        "election_cycle": "2024",
        "geography_vintage": "provider-collected 2024 precincts",
        "authoritative_scope": "standardized 2024 presidential precinct returns",
        "media_type": "application/gzip",
        "license_or_terms": (
            "New York Times 2024 precinct-data license; attribution and license review required"
        ),
        "filename": "precincts-with-results.csv.gz",
        "local_path": (
            "data/raw/presidential/southern_war_v4/precincts-with-results.csv.gz"
        ),
    },
    {
        "source_file_id": "NYT-NATIONAL-2024-PRES-PRECINCT-GEOMETRY",
        "provider": "The New York Times",
        "source_url": (
            "https://int.nyt.com/newsgraphics/elections/map-data/2024/national/"
            "precincts-with-results.topojson.gz"
        ),
        "state_code": "MULTI",
        "election_cycle": "2024",
        "geography_vintage": "provider-collected 2024 precincts",
        "authoritative_scope": "2024 presidential precinct geometries and joined returns",
        "media_type": "application/gzip",
        "license_or_terms": (
            "New York Times 2024 precinct-data license; attribution and license review required"
        ),
        "filename": "precincts-with-results.topojson.gz",
        "local_path": (
            "data/raw/historical_statewide_elections/precincts-with-results.topojson.gz"
        ),
    },
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path, require_zip: bool = False) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Alabama-WAR-research/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response:
        if response.status != 200:
            raise RuntimeError(f"Download failed with HTTP {response.status}: {url}")
        with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent, suffix=".part") as tmp:
            while chunk := response.read(1024 * 1024):
                tmp.write(chunk)
            temporary = Path(tmp.name)
    try:
        if require_zip and not zipfile.is_zipfile(temporary):
            raise ValueError(f"Downloaded RDH artifact is not a ZIP: {url}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def rdh_url(dataset_id: int, filename: str) -> str:
    document = f"%2Fweb_ready_stage%2Fdisag_votes_block%2F{filename}"
    return f"https://redistrictingdatahub.org/download/?datasetid={dataset_id}&document={document}"


def prior_manifest() -> dict[str, dict[str, str]]:
    if not MANIFEST.exists():
        return {}
    frame = pd.read_csv(MANIFEST, dtype=str).fillna("")
    if frame.source_file_id.duplicated().any():
        raise ValueError("Southern WAR v4 presidential manifest contains duplicate source IDs")
    return frame.set_index("source_file_id").to_dict("index")


def assets() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [{
        "source_file_id": "DAILYKOS-SLD-PRESIDENTIAL-INDEX-2021",
        "provider": "Daily Kos Elections",
        "source_url": DAILY_KOS_INDEX_URL,
        "state_code": "MULTI",
        "election_cycle": "2012;2016;2020",
        "geography_vintage": "state-specific 2011-2021 legislative plans documented in source index",
        "authoritative_scope": "public index and provenance links for presidential results by legislative district",
        "media_type": "text/html",
        "license_or_terms": "publicly accessible Daily Kos Elections research page; attribution required",
        "filename": "daily_kos_statewide_results_by_district_index.html",
    }]
    for state, (dataset_id, filename) in RDH_DOWNLOADS.items():
        rows.append({
            "source_file_id": f"RDH-2016-{state}-2020-BLOCKS",
            "provider": "Redistricting Data Hub",
            "source_url": rdh_url(dataset_id, filename),
            "state_code": state,
            "election_cycle": "2016",
            "geography_vintage": "2020 Census blocks",
            "authoritative_scope": "2016 general-election results disaggregated to 2020 Census blocks",
            "media_type": "application/zip",
            "license_or_terms": "Redistricting Data Hub public download; preserve provider README and attribution",
            "filename": filename,
        })
    for source in SUPPLEMENTAL_2012:
        rows.append({
            **source,
            "election_cycle": "2012",
            "geography_vintage": "provider-reported 2012 precincts",
            "authoritative_scope": "2012 presidential general-election precinct returns",
            "media_type": "application/zip" if str(source["filename"]).endswith(".zip") else "text/csv",
        })
    rows.extend(NATIONAL_CONTEXT)
    for row in rows:
        if "local_path" not in row:
            row["local_path"] = str((RAW / str(row["filename"])).relative_to(ROOT)).replace("\\", "/")
    return rows


def acquire_one(
    row: dict[str, object], old: dict[str, str], offline: bool, include_rdh_downloads: bool,
) -> dict[str, object]:
    path = ROOT / str(row["local_path"])
    if path.exists():
        digest = sha256(path)
        if old.get("sha256") and old["sha256"] != digest:
            raise ValueError(f"Immutable presidential source changed on disk: {path}")
        retrieved_at = (
            old.get("retrieved_at") or str(row.get("retrieved_at") or "")
            or dt.datetime.now(dt.timezone.utc).isoformat()
        )
    else:
        if str(row["provider"]) == "Redistricting Data Hub" and not include_rdh_downloads:
            return {
                **row, "retrieved_at": "", "sha256": "",
                "ingest_status": "requires_authenticated_download",
            }
        if offline:
            raise FileNotFoundError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        download(str(row["source_url"]), path, require_zip=str(row["media_type"]) == "application/zip")
        digest = sha256(path)
        retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    return {**row, "retrieved_at": retrieved_at, "sha256": digest, "ingest_status": "acquired"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--include-rdh-downloads", action="store_true",
        help="attempt RDH downloads; the provider may require an authenticated account",
    )
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    old = prior_manifest()
    requested = assets()
    output: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                acquire_one, row, old.get(str(row["source_file_id"]), {}),
                args.offline, args.include_rdh_downloads,
            ): row
            for row in requested
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            output.append(result)
            print(f"{result['ingest_status']} {result['source_file_id']}: {result['filename']}", flush=True)
    frame = pd.DataFrame(output).sort_values(["provider", "state_code"]).reset_index(drop=True)
    if len(frame) != 23 or frame.source_file_id.duplicated().any():
        raise ValueError(
            "Expected one Daily Kos index, fourteen RDH 2016 files, five 2012 supplements, "
            "and three national 2020/2024 context files"
        )
    columns = [
        "source_file_id", "provider", "source_url", "retrieved_at", "sha256", "media_type",
        "license_or_terms", "state_code", "election_cycle", "geography_vintage",
        "authoritative_scope", "ingest_status", "filename", "local_path",
    ]
    frame[columns].to_csv(MANIFEST, index=False)
    print(f"Presidential context sources: {len(frame)}; manifest={MANIFEST}")


if __name__ == "__main__":
    main()
