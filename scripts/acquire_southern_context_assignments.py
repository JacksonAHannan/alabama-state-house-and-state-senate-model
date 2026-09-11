#!/usr/bin/env python3
"""Register immutable national state-legislative block assignment archives."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/historical_statewide_elections"
MANIFEST = ROOT / "data/processed/source_audits/southern_context_assignment_manifest.csv"
SOURCE_URL = "https://redistrictingdatahub.org/state/national/"
ASSETS = (
    (2022, "national_2022_elections_st_leg_boundaries.zip", "2026-08-19T06:56:55.1516657Z"),
    (2024, "national_2024_elections_st_leg_boundaries.zip", "2026-08-19T06:57:02.7174392Z"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest() -> pd.DataFrame:
    rows = []
    for cycle, filename, retrieved_at in ASSETS:
        path = RAW / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Registered RDH block-assignment archive is missing; reacquire from {SOURCE_URL}: {path}"
            )
        rows.append({
            "source_file_id": f"RDH-NATIONAL-{cycle}-SLD-BAF",
            "provider": "Redistricting Data Hub",
            "source_url": SOURCE_URL,
            "retrieved_at": retrieved_at,
            "sha256": sha256(path),
            "media_type": "application/zip",
            "license_or_terms": "Redistricting Data Hub public download; preserve README and attribution",
            "state_code": "MULTI",
            "cycle": cycle,
            "geography_vintage": "2020 Census blocks assigned to election-year state legislative plans",
            "authoritative_scope": f"national {cycle} election state-legislative block assignments and boundaries",
            "ingest_status": "acquired",
            "filename": filename,
            "local_path": path.relative_to(ROOT).as_posix(),
        })
    frame = pd.DataFrame(rows)
    if len(frame) != 2 or frame.source_file_id.duplicated().any():
        raise ValueError("Expected unique 2022 and 2024 national assignment sources")
    return frame


def main() -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    frame = build_manifest()
    if MANIFEST.exists():
        old = pd.read_csv(MANIFEST, dtype=str).fillna("").set_index("source_file_id")
        for row in frame.itertuples(index=False):
            if row.source_file_id in old.index and old.loc[row.source_file_id, "sha256"] not in {"", row.sha256}:
                raise ValueError(f"Immutable assignment source changed: {row.source_file_id}")
    frame.to_csv(MANIFEST, index=False)
    print(f"Southern context assignments: {len(frame)} acquired archives; manifest={MANIFEST}")


if __name__ == "__main__":
    main()
