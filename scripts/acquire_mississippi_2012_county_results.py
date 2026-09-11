#!/usr/bin/env python3
"""Acquire the pinned OpenElections Mississippi 2012 county reconciliation file."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
URL = (
    "https://raw.githubusercontent.com/openelections/openelections-data-ms/"
    "ed58cb2d2480744f02aac7a285b47d10676ff14d/2012/20121106__ms__general.csv"
)
RAW = ROOT / "data/raw/openelections_historical_gaps/MS/2012/20121106__ms__general.csv"
MANIFEST = ROOT / "data/processed/source_audits/mississippi_2012_county_results_manifest.csv"


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
        request = urllib.request.Request(URL, headers={"User-Agent": "southern-war-research/1.0"})
        with urllib.request.urlopen(request) as response:
            payload = response.read()
            last_modified = response.headers.get("Last-Modified", "")
        if not payload.startswith(b"county,office,district,party,candidate,votes"):
            raise ValueError("Unexpected Mississippi county result schema")
        RAW.parent.mkdir(parents=True, exist_ok=True)
        RAW.write_bytes(payload)
    row: dict[str, object] = {
        "source_file_id": "OPENELECTIONS-2012-MS-COUNTY",
        "provider": "OpenElections conversion of Mississippi Secretary of State",
        "source_url": URL,
        "retrieved_at": retrieved_at,
        "source_last_modified": last_modified,
        "sha256": sha256(RAW),
        "size_bytes": RAW.stat().st_size,
        "media_type": "text/csv",
        "license_or_terms": "OpenElections public repository; converted official Mississippi county results",
        "state_code": "MS",
        "cycle": 2012,
        "geography_vintage": "2012 county reporting units",
        "authoritative_scope": "County-level reconciliation for 2012 Mississippi general-election returns",
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
