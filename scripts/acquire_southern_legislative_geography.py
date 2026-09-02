#!/usr/bin/env python3
"""Acquire election-year Census cartographic boundaries for Southern WAR maps."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from southern_war_map_contract import STATE_FIPS, scheduled_keys_2016_2022


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/census/southern_legislative_boundaries_2016_2022"
MANIFEST = ROOT / "data/processed/source_audits/southern_legislative_geography_manifest.csv"
BASE_URL = "https://www2.census.gov/geo/tiger/GENZ{cycle}/shp/{filename}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def requested_assets() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for state, cycle, chamber in sorted(scheduled_keys_2016_2022()):
        layer = "sldl" if chamber == "lower" else "sldu"
        filename = f"cb_{cycle}_{STATE_FIPS[state]}_{layer}_500k.zip"
        rows.append({
            "source_file_id": f"CENSUS-CB-{cycle}-{state}-{layer.upper()}-500K",
            "provider": "U.S. Census Bureau",
            "source_url": BASE_URL.format(cycle=cycle, filename=filename),
            "state_code": state,
            "cycle": cycle,
            "chamber": chamber,
            "filename": filename,
            "local_path": str((RAW / filename).relative_to(ROOT)).replace("\\", "/"),
            "media_type": "application/zip",
            "license_or_terms": "U.S. Census Bureau public data; no copyright restriction",
            "geography_vintage": f"Census {cycle} cartographic boundary, 1:500,000",
            "authoritative_scope": "display geometry for state legislative districts represented in the election-year Census boundary release",
        })
    return rows


def existing_manifest() -> dict[str, dict[str, str]]:
    if not MANIFEST.exists():
        return {}
    frame = pd.read_csv(MANIFEST, dtype=str).fillna("")
    if frame.source_file_id.duplicated().any():
        raise ValueError("Southern legislative geography manifest has duplicate source IDs")
    return frame.set_index("source_file_id").to_dict("index")


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Alabama-WAR-research/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 200:
            raise RuntimeError(f"Census download failed with HTTP {response.status}: {url}")
        with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent, suffix=".part") as tmp:
            while chunk := response.read(1024 * 1024):
                tmp.write(chunk)
            temporary = Path(tmp.name)
    try:
        if not zipfile.is_zipfile(temporary):
            raise ValueError(f"Downloaded Census artifact is not a ZIP: {url}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="validate local immutable files without downloading")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    prior = existing_manifest()
    generated = dt.datetime.now(dt.timezone.utc).isoformat()
    output = []
    for row in requested_assets():
        path = ROOT / str(row["local_path"])
        old = prior.get(str(row["source_file_id"]), {})
        if path.exists():
            current_hash = sha256(path)
            if old.get("sha256") and old["sha256"] != current_hash:
                raise ValueError(f"Immutable Census source changed on disk: {path}")
        else:
            if args.offline:
                raise FileNotFoundError(path)
            download(str(row["source_url"]), path)
            current_hash = sha256(path)
        output.append({
            **row,
            "retrieved_at": old.get("retrieved_at") or generated,
            "sha256": current_hash,
            "ingest_status": "acquired",
        })
    frame = pd.DataFrame(output)
    if frame.duplicated(["state_code", "cycle", "chamber"]).any() or len(frame) != 90:
        raise ValueError("Election-year Southern geometry schedule must contain 90 unique slices")
    columns = [
        "source_file_id", "provider", "source_url", "retrieved_at", "sha256",
        "media_type", "license_or_terms", "state_code", "cycle", "chamber",
        "geography_vintage", "authoritative_scope", "ingest_status", "filename", "local_path",
    ]
    frame[columns].to_csv(MANIFEST, index=False)
    print(f"Southern legislative geometry: {len(frame)} immutable Census ZIPs; manifest={MANIFEST}")


if __name__ == "__main__":
    main()
