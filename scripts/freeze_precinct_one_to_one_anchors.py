"""Persist immutable one-to-one anchors from the last validated GeoPackages."""
from __future__ import annotations

import hashlib
from pathlib import Path

import geopandas as gpd
import pandas as pd

from warehouse import ROOT

SOURCE = ROOT / "data/processed/precinct_history"
OUT = ROOT / "data/manual/precinct_history/frozen_one_to_one_anchors.csv"
EXPECTED_HASH = "ccec4ff703e69491563f0e8e1e2e99290f64c10b11d9612d11c319dfcb440a7b"
COLUMNS = ["cycle", "county_key", "precinct_key", "donor_vtd_id", "donor_name",
           "donor_vintage", "name_match_method", "name_match_score", "name_match_margin"]


def mapping_hash(data: pd.DataFrame) -> str:
    ordered = data.sort_values(["cycle", "county_key", "precinct_key"])
    payload = "\n".join(ordered.cycle.astype(str) + "|" + ordered.county_key + "|"
                        + ordered.precinct_key + "|" + ordered.donor_vtd_id)
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    frames = []
    for path in SOURCE.glob("approximate_*_precincts.gpkg"):
        data = gpd.read_file(path, ignore_geometry=True)
        frozen = data[data.frozen_one_to_one.astype(str).str.lower().isin(["true", "1"])]
        frames.append(frozen[COLUMNS])
    result = pd.concat(frames).drop_duplicates(["cycle", "county_key", "precinct_key"])
    digest = mapping_hash(result)
    if len(result) != 832 or digest != EXPECTED_HASH:
        raise ValueError(f"anchor recovery failed: rows={len(result)}, hash={digest}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.sort_values(["cycle", "county_key", "precinct_key"]).to_csv(OUT, index=False)
    print(f"Wrote {len(result)} frozen anchors to {OUT}; hash={digest}")


if __name__ == "__main__":
    main()
