#!/usr/bin/env python3
"""Acquire the official Alabama historical presidential county workbook."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
URL = (
    "https://www.sos.alabama.gov/sites/default/files/election-data/2017-06/"
    "eapresidentgeneral1976-2012_0.xls"
)
RAW = ROOT / "data/raw/alabama_elections_and_geography/eapresidentgeneral1976-2012_0.xls"
MANIFEST = ROOT / "data/processed/source_audits/alabama_presidential_county_archive_manifest.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def acquire() -> dict[str, object]:
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    last_modified = ""
    if not RAW.exists():
        request = urllib.request.Request(URL, headers={"User-Agent": "alabama-war-research/1.0"})
        with urllib.request.urlopen(request) as response:
            payload = response.read()
            last_modified = response.headers.get("Last-Modified", "")
        if not payload.startswith(bytes.fromhex("D0CF11E0")):
            raise ValueError("Alabama SOS archive is not an OLE Excel workbook")
        RAW.parent.mkdir(parents=True, exist_ok=True)
        RAW.write_bytes(payload)
    row: dict[str, object] = {
        "source_file_id": "ALSOS-PRESIDENT-GENERAL-COUNTY-1976-2012",
        "provider": "Alabama Secretary of State",
        "source_url": URL,
        "retrieved_at": retrieved_at,
        "source_last_modified": last_modified,
        "sha256": sha256(RAW),
        "size_bytes": RAW.stat().st_size,
        "media_type": "application/vnd.ms-excel",
        "license_or_terms": "Official public election download; no separate license statement located",
        "state_code": "AL",
        "cycle": 2012,
        "geography_vintage": "2012 county reporting units",
        "authoritative_scope": "Official county-level presidential general-election results, 1976-2012",
        "ingest_status": "acquired",
        "local_path": str(RAW.relative_to(ROOT)).replace("\\", "/"),
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return row


if __name__ == "__main__":
    print(acquire())
