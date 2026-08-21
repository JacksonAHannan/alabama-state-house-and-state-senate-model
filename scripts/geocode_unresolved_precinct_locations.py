"""Last-resort geocoding for unresolved named historical polling places."""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from rapidfuzz import fuzz
from shapely.geometry import Point

from audit_historical_precinct_geography import OUT, county_match_key, donor_vtds, normalize_split_base

QUEUE = OUT / "historical_precinct_geometry_review_queue.csv"
AUDIT = OUT / "historical_precinct_geometry_audit.csv"
CACHE = OUT / "historical_precinct_geocode_cache.json"
RESULTS = OUT / "historical_precinct_geocode_resolutions.csv"
ENDPOINT = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
GENERIC = re.compile(r"ABSENT|CHALLENG|DISPUT|PROVISION|FAILSAFE|WRITE.?IN|BEAT\s*\d|BOX\s*\d", re.I)
VARIANT_VERSION = 1


def expanded_place_name(value: str) -> str:
    text = f" {value.upper()} "
    replacements = {
        r"\bE S\b|\bES\b": "ELEMENTARY SCHOOL", r"\bM S\b|\bMS\b": "MIDDLE SCHOOL",
        r"\bH S\b|\bHS\b": "HIGH SCHOOL", r"\bCC\b": "COMMUNITY CENTER",
        r"\bCTR\b": "CENTER", r"\bCOMM\b": "COMMUNITY", r"\bSCH\b": "SCHOOL",
        r"\bFD\b": "FIRE DEPARTMENT", r"\bNATL\b": "NATIONAL",
        r"\bBAPT\b": "BAPTIST", r"\bCH\b": "CHURCH", r"\bELEM\b": "ELEMENTARY",
        r"\bREC\b": "RECREATION", r"\bMT\b": "MOUNT",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    return re.sub(r"\s+", " ", text).strip()


def query_variants(place_key: str, county_key: str) -> list[str]:
    names = [place_key, expanded_place_name(place_key)]
    names += [re.sub(r"\s+(?:DISTRICT|PRECINCT)\s*\d+$", "", name).strip() for name in names]
    return list(dict.fromkeys(
        f"{name}, {county_key} County, Alabama" for name in names if name))


def eligible(name: str) -> bool:
    return bool(re.search(r"[A-Z]{3}", name, re.I)) and not GENERIC.search(name)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--delay", type=float, default=0.15); args = parser.parse_args()
    queue = pd.read_csv(QUEUE)
    if "vtd_inventory_relation" in queue:
        queue = queue[queue.vtd_inventory_relation.eq("overflow")].copy()
    ranked_path = OUT / "historical_precinct_adjudication_queue.csv"
    if ranked_path.exists():
        ranked = pd.read_csv(ranked_path)[["cycle", "county_key", "precinct_key", "priority_rank"]]
        queue = queue.merge(ranked, on=["cycle", "county_key", "precinct_key"], how="left")
    else:
        queue["priority_rank"] = range(1, len(queue) + 1)
    resolution_universe = queue.copy()
    if AUDIT.exists():
        audit = pd.read_csv(AUDIT)
        prior_geocoded = audit[audit.name_match_method.eq("named_place_geocode_to_containing_vtd")]
        if "vtd_inventory_relation" in prior_geocoded:
            prior_geocoded = prior_geocoded[prior_geocoded.vtd_inventory_relation.eq("overflow")]
        keep = [column for column in queue.columns if column in prior_geocoded.columns]
        resolution_universe = pd.concat([queue, prior_geocoded[keep]], ignore_index=True)
        resolution_universe = resolution_universe.drop_duplicates(
            ["cycle", "county_key", "precinct_key"])
    queue["place_key"] = queue.precinct_key.map(normalize_split_base)
    places = (queue[queue.precinct_key.map(eligible)]
              .sort_values(["priority_rank", "is_split_precinct", "cycle"])
              .drop_duplicates(["county_key", "place_key"]))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    session = requests.Session(); session.headers["User-Agent"] = "Alabama historical election geography research"
    requested = 0
    for row in places.itertuples(index=False):
        key = f"{county_match_key(row.county_key)}|{row.place_key}"
        if requested >= args.limit: break
        item = cache.setdefault(key, {"query": "", "candidates": []})
        if item.get("variant_version") == VARIANT_VERSION:
            continue
        existing = {candidate.get("address") for candidate in item.get("candidates", [])}
        queries = query_variants(row.place_key, row.county_key)
        for query in queries:
            if requested >= args.limit: break
            response = session.get(ENDPOINT, params={"SingleLine": query, "f": "json", "outFields": "*",
                "maxLocations": 5, "countryCode": "USA"}, timeout=45)
            response.raise_for_status(); payload = response.json()
            if not item.get("query"): item["query"] = query
            for candidate in payload.get("candidates", []):
                identity = candidate.get("address")
                if identity not in existing:
                    item.setdefault("candidates", []).append(candidate); existing.add(identity)
            requested += 1
            time.sleep(args.delay)
        item["queries"] = queries
        item["variant_version"] = VARIANT_VERSION
        if requested % 50 == 0:
            CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
            print(f"Geocoded {requested}", flush=True)
    CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    donors = donor_vtds().to_crs(4326)
    donors["county_match_key"] = donors.county_key.map(county_match_key)
    county_shapes = donors.dissolve("county_match_key").geometry
    rows = []
    for row in resolution_universe.itertuples(index=False):
        place_key = normalize_split_base(row.precinct_key); county_key = county_match_key(row.county_key)
        item = cache.get(f"{county_key}|{place_key}")
        if not item: continue
        accepted = None
        place_variants = [place_key, expanded_place_name(place_key)]
        for candidate in item["candidates"]:
            attributes = candidate.get("attributes", {})
            region = str(attributes.get("RegionAbbr") or attributes.get("Region") or "").upper()
            address_type = str(attributes.get("Addr_type") or "")
            short_label = str(attributes.get("ShortLabel") or attributes.get("PlaceName") or candidate.get("address") or "")
            name_similarity = max(float(fuzz.WRatio(variant, normalize_split_base(short_label)))
                                  for variant in place_variants)
            location = candidate.get("location") or {}
            if float(candidate.get("score", 0)) < 85 or region not in {"AL", "ALABAMA"}:
                continue
            if address_type == "POI":
                named_location_ok = name_similarity >= 80
            elif address_type == "Locality":
                named_location_ok = name_similarity >= 90 and "COUNTY" not in short_label.upper()
            else:
                named_location_ok = name_similarity >= 90
            if not named_location_ok:
                continue
            point = Point(float(location["x"]), float(location["y"]))
            county_shape = county_shapes.get(county_key)
            if county_shape is None or not county_shape.covers(point):
                continue
            vintage = 2010 if int(row.cycle) >= 2006 else 2000
            pool = donors[(donors.county_match_key.eq(county_key)) & donors.donor_vintage.eq(vintage)]
            containing = pool[pool.geometry.covers(point)]
            if len(containing) != 1: continue
            accepted = (candidate, point, containing.iloc[0]); break
        if accepted is None: continue
        candidate, point, donor = accepted
        rows.append({"cycle": int(row.cycle), "county_key": row.county_key,
            "precinct_key": row.precinct_key, "place_key": place_key,
            "donor_vtd_id": donor.donor_vtd_id, "donor_name": donor.donor_name,
            "donor_vintage": int(donor.donor_vintage), "longitude": point.x, "latitude": point.y,
            "geocoder_score": float(candidate["score"]), "matched_address": candidate.get("address"),
            "geocoder_name_similarity": name_similarity, "geocoder_address_type": address_type,
            "match_method": "named_place_geocode_to_containing_vtd", "confidence": "low",
            "verification_status": "approximate_geocoded_polling_place"})
    pd.DataFrame(rows).drop_duplicates(["cycle", "county_key", "precinct_key"]).to_csv(RESULTS, index=False)
    print({"new_requests": requested, "cache_entries": len(cache), "accepted_precincts": len(rows)})


if __name__ == "__main__":
    main()
