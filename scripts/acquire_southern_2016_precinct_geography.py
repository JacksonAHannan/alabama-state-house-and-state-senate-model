#!/usr/bin/env python3
"""Acquire immutable VEST 2016 Southern precinct result/geography archives."""
from __future__ import annotations

import argparse
import hashlib
import os
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/presidential/southern_war_v4/vest_2016"
MANIFEST = ROOT / "data/processed/source_audits/southern_2016_vest_manifest.csv"
DATASET_DOI = "doi:10.7910/DVN/NH5S2I"
DATASET_VERSION = "97.0"
TERMS = "CC BY 4.0; preserve VEST citation and state validation report"

# File IDs, labels, sizes, and MD5 values come from the Harvard Dataverse
# version-97.0 API response. Keeping them in code makes acquisition
# deterministic and ensures that a changed upstream byte stream is rejected.
ASSETS = (
    ("AL", 4751068, "al_2016.zip", 18_831_548, "61124d011e9eee5a6d4396be11731273"),
    ("AR", 4931773, "ar_2016.zip", 12_794_157, "a9e9e80bc18d5ea366a13b036f777f43"),
    ("FL", 12070343, "fl.zip", 23_348_064, "896676b031405d9531ab53d2959236da"),
    ("GA", 11070010, "ga_2016.zip", 18_264_976, "bd2270587959e3bb7e2cc7138b3cd08c"),
    ("KY", 6429540, "ky_2016.zip", 20_010_143, "1023bb7a5f0589df64d39cbdd5ed9777"),
    ("LA", 3644961, "la_2016.zip", 15_127_906, "78e1804ddac30600da0cb12978235273"),
    ("MO", 5007730, "mo_2016.zip", 13_698_929, "f1b26737d21feacdf6d36781a46daca9"),
    ("MS", 5706481, "ms_2016.zip", 13_773_285, "9e3f4ffeb6db4b0328526c902b5bdb38"),
    ("NC", 11595840, "nc_2016.zip", 19_618_569, "4e70d8d798ae7df6987052d151bd1528"),
    ("OK", 3613878, "ok_2016.zip", 11_546_071, "3f5839157df6ebbdc8c59f36564f56b4"),
    ("SC", 11070011, "sc_2016.zip", 11_170_086, "330db11eb23e2c92380c8f77d5c10484"),
    ("TN", 11070008, "tn_2016.zip", 24_615_303, "3ba06a046b56194c0bcdbe38059471ac"),
    ("TX", 12070340, "tx.zip", 45_666_869, "221094f45e24eead73a4d45a3db8780e"),
    ("VA", 6550194, "va_2016.zip", 22_414_870, "2a50e5e9efcf03f1f716616738467710"),
)


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def retrieve(url: str, target: Path, expected_size: int, expected_md5: str) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    if temporary.exists():
        temporary.unlink()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "southern-war-warehouse/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("xb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temporary.stat().st_size != expected_size:
            raise ValueError(
                f"Unexpected byte count for {url}: {temporary.stat().st_size} != {expected_size}"
            )
        if digest(temporary, "md5") != expected_md5:
            raise ValueError(f"Dataverse MD5 mismatch for {url}")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return datetime.now(timezone.utc).isoformat()


def build_manifest(*, offline: bool = False) -> pd.DataFrame:
    prior: dict[str, str] = {}
    if MANIFEST.exists():
        old = pd.read_csv(MANIFEST, dtype=str).fillna("")
        prior = dict(zip(old.source_file_id, old.retrieved_at))
    rows = []
    for state, file_id, upstream_label, expected_size, expected_md5 in ASSETS:
        source_file_id = f"VEST-2016-{state}-PRECINCT"
        url = f"https://dataverse.harvard.edu/api/access/datafile/{file_id}"
        target = RAW / state / f"{state.lower()}_2016.zip"
        retrieved_at = prior.get(source_file_id, "")
        if target.exists():
            if target.stat().st_size != expected_size or digest(target, "md5") != expected_md5:
                raise ValueError(f"Immutable local source differs from Dataverse metadata: {target}")
            if not retrieved_at:
                retrieved_at = datetime.fromtimestamp(
                    target.stat().st_mtime, timezone.utc
                ).isoformat()
        elif offline:
            raise FileNotFoundError(f"Offline acquisition is missing {target}")
        else:
            retrieved_at = retrieve(url, target, expected_size, expected_md5)
        with zipfile.ZipFile(target) as archive:
            shapefiles = sorted(name for name in archive.namelist() if name.lower().endswith(".shp"))
            if len(shapefiles) != 1:
                raise ValueError(f"Expected one precinct shapefile in {target}, found {shapefiles}")
            members = len(archive.infolist())
        rows.append({
            "source_file_id": source_file_id,
            "provider": "Voting and Election Science Team",
            "dataset_doi": DATASET_DOI,
            "dataset_version": DATASET_VERSION,
            "dataverse_file_id": file_id,
            "upstream_label": upstream_label,
            "source_url": url,
            "retrieved_at": retrieved_at,
            "sha256": digest(target, "sha256"),
            "upstream_md5": expected_md5,
            "size_bytes": target.stat().st_size,
            "media_type": "application/zip",
            "license_or_terms": TERMS,
            "state_code": state,
            "election_cycle": 2016,
            "geography_vintage": "2016 general-election precincts",
            "authoritative_scope": "VEST harmonized precinct polygons and statewide election results",
            "shapefile_member": shapefiles[0],
            "archive_members": members,
            "ingest_status": "acquired",
            "local_path": target.relative_to(ROOT).as_posix(),
        })
    frame = pd.DataFrame(rows)
    if len(frame) != 14 or frame.source_file_id.duplicated().any():
        raise ValueError("Expected one unique VEST 2016 source for each of 14 states")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    frame = build_manifest(offline=args.offline)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(MANIFEST, index=False)
    print(f"VEST 2016 Southern precinct archives: {len(frame)} acquired; manifest={MANIFEST}")


if __name__ == "__main__":
    main()
