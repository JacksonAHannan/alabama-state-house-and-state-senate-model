#!/usr/bin/env python3
"""Acquire full-resolution Census 2020 SLD geometry for review-plan supplements."""
from __future__ import annotations

import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from warehouse import ROOT


RAW = ROOT / "data/raw/census/southern_2020_detailed_plan_supplements"
MANIFEST = ROOT / "data/processed/source_audits/southern_2020_detailed_plan_supplement_manifest.csv"
SPECS = {
    ("FL", "12", "lower", "sldl"): 2_248_463,
    ("FL", "12", "upper", "sldu"): 1_525_280,
    ("NC", "37", "lower", "sldl"): 5_437_404,
    ("NC", "37", "upper", "sldu"): 3_349_222,
    ("TX", "48", "lower", "sldl"): 6_430_099,
    ("TX", "48", "upper", "sldu"): 3_276_671,
}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def acquire(spec: tuple[str, str, str, str], expected: int, offline: bool) -> dict:
    state, fips, chamber, code = spec
    filename = f"tl_2020_{fips}_{code}.zip"
    url = f"https://www2.census.gov/geo/tiger/TIGER2020/{code.upper()}/{filename}"
    path = RAW / filename
    retrieved_at = datetime.now(timezone.utc).isoformat()
    last_modified = ""
    if path.exists():
        if path.stat().st_size != expected:
            raise ValueError(f"Existing source has unexpected size: {path}")
    elif offline:
        raise FileNotFoundError(path)
    else:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        if len(response.content) != expected:
            raise ValueError(f"Unexpected byte count for {url}: {len(response.content)} != {expected}")
        temporary = path.with_suffix(path.suffix + ".part")
        temporary.write_bytes(response.content)
        temporary.replace(path)
        last_modified = response.headers.get("last-modified", "")
    return {
        "source_file_id": f"CENSUS-TIGER-2020-{state}-{code.upper()}-DETAILED",
        "provider": "U.S. Census Bureau",
        "source_url": url,
        "retrieved_at": retrieved_at,
        "source_last_modified": last_modified,
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
        "media_type": "application/zip",
        "license_or_terms": "U.S. Census Bureau public data; TIGER/Line attribution required",
        "state_code": state,
        "cycle": 2020,
        "chamber": chamber,
        "geography_vintage": "TIGER/Line 2020 full-resolution state legislative district",
        "authoritative_scope": "Detailed geometry supplement; usable only after same-plan overlay validation",
        "ingest_status": "acquired",
        "local_path": path.relative_to(ROOT).as_posix(),
    }


def build_manifest(offline: bool = False) -> pd.DataFrame:
    RAW.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(lambda item: acquire(item[0], item[1], offline), SPECS.items()))
    frame = pd.DataFrame(rows).sort_values(["state_code", "chamber"])
    if len(frame) != 6 or frame.source_file_id.duplicated().any():
        raise ValueError("Detailed-plan supplement manifest is incomplete or duplicated")
    frame.to_csv(MANIFEST, index=False)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    frame = build_manifest(args.offline)
    print(f"Detailed 2020 plan supplements: {len(frame)} files, {int(frame.size_bytes.sum()):,} bytes")


if __name__ == "__main__":
    main()
