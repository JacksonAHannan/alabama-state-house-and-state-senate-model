"""Download the official Census 2000 Alabama VTD layer from TIGERweb."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from warehouse import ROOT

LAYER = "https://tigerweb.geo.census.gov/arcgis/rest/services/Census2020/tigerWMS_Census2000/MapServer/58"
OUT = ROOT / "data/raw/census/vtd2000/alabama_vtd2000.geojson"
MANIFEST = ROOT / "data/raw/census/vtd2000/source_manifest.json"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Alabama historical election geography research"
    query = f"{LAYER}/query"
    ids_response = session.get(query, params={"where": "GEOID LIKE '01%'",
        "returnIdsOnly": "true", "f": "json"}, timeout=60)
    ids_response.raise_for_status()
    object_ids = ids_response.json()["objectIds"]
    frames = []
    for start in range(0, len(object_ids), 50):
        response = session.get(query, params={"objectIds": ",".join(map(str, object_ids[start:start + 50])),
            "outFields": "GEOID,STATE,COUNTY,VTD,NAME,BASENAME,POP100",
            "returnGeometry": "true", "outSR": "4326", "f": "geojson"}, timeout=180)
        response.raise_for_status()
        frames.append(gpd.GeoDataFrame.from_features(response.json()["features"], crs=4326))
        print(f"Downloaded {min(start + 50, len(object_ids))}/{len(object_ids)}", flush=True)
    data = pd.concat(frames, ignore_index=True)
    data = gpd.GeoDataFrame(data, geometry="geometry", crs=4326)
    if len(data) != len(object_ids) or data.GEOID.duplicated().any():
        raise ValueError("Census 2000 VTD download failed completeness/uniqueness validation")
    data.to_file(OUT, driver="GeoJSON")
    MANIFEST.write_text(json.dumps({"provider": "US Census Bureau TIGERweb",
        "layer_url": LAYER, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "feature_count": len(data), "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "temporal_vintage": "2000-01-01", "state_fips": "01"}, indent=2), encoding="utf-8")
    print(OUT, len(data))


if __name__ == "__main__":
    main()
