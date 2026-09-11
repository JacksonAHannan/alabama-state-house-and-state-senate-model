#!/usr/bin/env python3
"""Acquire immutable 2020 TIGER/Line block geometry for Southern states."""
from __future__ import annotations

import argparse
import hashlib
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/census"
MANIFEST = ROOT / "data/processed/source_audits/southern_2020_census_block_manifest.csv"
BASE = "https://www2.census.gov/geo/tiger/TIGER2020PL/STATE"
TERMS = "U.S. Census Bureau public data; TIGER/Line attribution required"
ASSETS = (
    ("AL", "01", "ALABAMA", 148_096_873),
    ("AR", "05", "ARKANSAS", 130_482_845),
    ("FL", "12", "FLORIDA", 189_739_232),
    ("GA", "13", "GEORGIA", 170_298_208),
    ("KY", "21", "KENTUCKY", 158_088_398),
    ("LA", "22", "LOUISIANA", 112_549_772),
    ("MO", "29", "MISSOURI", 197_345_691),
    ("MS", "28", "MISSISSIPPI", 118_217_432),
    ("NC", "37", "NORTH_CAROLINA", 202_604_850),
    ("OK", "40", "OKLAHOMA", 110_227_879),
    ("SC", "45", "SOUTH_CAROLINA", 113_142_059),
    ("TN", "47", "TENNESSEE", 184_921_842),
    ("TX", "48", "TEXAS", 420_908_467),
    ("VA", "51", "VIRGINIA", 184_650_567),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def acquire_one(asset: tuple[str, str, str, int], prior: dict[str, dict[str, str]],
                offline: bool) -> dict[str, object]:
    state, fips, census_name, expected_size = asset
    filename = f"tl_2020_{fips}_tabblock20.zip"
    url = f"{BASE}/{fips}_{census_name}/{fips}/{filename}"
    target = RAW / filename
    source_file_id = f"CENSUS-2020-{state}-TABBLOCK20"
    old = prior.get(source_file_id, {})
    retrieved_at = old.get("retrieved_at", "")
    last_modified = old.get("source_last_modified", "")
    if target.exists():
        if target.stat().st_size != expected_size:
            raise ValueError(f"Unexpected existing Census archive size: {target}")
        current_hash = sha256(target)
        if old.get("sha256") and old["sha256"].lower() != current_hash:
            raise ValueError(f"Immutable Census archive changed locally: {target}")
        if not retrieved_at:
            retrieved_at = datetime.fromtimestamp(target.stat().st_mtime, timezone.utc).isoformat()
    elif offline:
        raise FileNotFoundError(f"Offline acquisition is missing {target}")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        if temporary.exists():
            temporary.unlink()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "southern-war-warehouse/1.0"})
            with urllib.request.urlopen(request, timeout=300) as response, temporary.open("xb") as output:
                header_date = response.headers.get("Last-Modified")
                if header_date:
                    last_modified = parsedate_to_datetime(header_date).astimezone(timezone.utc).isoformat()
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if temporary.stat().st_size != expected_size:
                raise ValueError(
                    f"Unexpected byte count for {state}: {temporary.stat().st_size} != {expected_size}"
                )
            os.replace(temporary, target)
            retrieved_at = datetime.now(timezone.utc).isoformat()
        finally:
            if temporary.exists():
                temporary.unlink()
        current_hash = sha256(target)
    return {
        "source_file_id": source_file_id,
        "provider": "U.S. Census Bureau",
        "source_url": url,
        "retrieved_at": retrieved_at,
        "source_last_modified": last_modified,
        "sha256": current_hash,
        "size_bytes": target.stat().st_size,
        "media_type": "application/zip",
        "license_or_terms": TERMS,
        "state_code": state,
        "cycle": 2020,
        "geography_vintage": "2020 Census tabulation blocks",
        "authoritative_scope": "statewide TIGER/Line 2020 Census block polygons",
        "ingest_status": "acquired",
        "local_path": target.relative_to(ROOT).as_posix(),
    }


def build_manifest(*, offline: bool = False, workers: int = 4) -> pd.DataFrame:
    prior: dict[str, dict[str, str]] = {}
    if MANIFEST.exists():
        old = pd.read_csv(MANIFEST, dtype=str).fillna("")
        prior = old.set_index("source_file_id").to_dict("index")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        rows = list(executor.map(lambda asset: acquire_one(asset, prior, offline), ASSETS))
    frame = pd.DataFrame(rows).sort_values("state_code", kind="stable")
    if len(frame) != 14 or frame.state_code.duplicated().any():
        raise ValueError("Expected one unique Census block archive for each Southern state")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    frame = build_manifest(offline=args.offline, workers=args.workers)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(MANIFEST, index=False)
    print(
        f"Southern Census block archives: {len(frame)} acquired, "
        f"{int(frame.size_bytes.astype(int).sum()):,} bytes; manifest={MANIFEST}"
    )


if __name__ == "__main__":
    main()
