import geopandas as gpd
from shapely.geometry import box

from scripts.audit_historical_precinct_geography import (
    canonical_vtd_code, county_match_key, decoded_county_vtd_code,
    non_geographic_record, normalize_split_base, partition_shared_vtds,
)


def test_county_match_key_reconciles_historical_abbreviations():
    assert county_match_key("STCLAIR") == county_match_key("St. Clair")
    assert county_match_key("COVINGTN") == county_match_key("Covington")


def test_split_suffixes_reduce_to_parent_polling_place():
    assert normalize_split_base("B.N. Mabra Center 2") == normalize_split_base("B.N. Mabra Center 1")
    assert normalize_split_base("0381 Lower Peachtree #2") == "LOWER PEACHTREE"


def test_county_specific_vtd_decoders():
    assignments = {("senate", 34), ("house", 102)}
    assert decoded_county_vtd_code("Mobile", "34-102-09", assignments) == (
        "102-9", "mobile_senate_house_box_code")
    assert decoded_county_vtd_code("Mobile", "34-102-09", {("house", 102)}) == ("", "")
    assert decoded_county_vtd_code("Lee", "BEAT 06/BOX 4") == ("60", "lee_beat_box_code")
    assert decoded_county_vtd_code("Morgan", "15-001") == ("15-1", "morgan_segmented_code")
    assert canonical_vtd_code("015-001") == "15-1"


def test_non_geographic_records():
    assert non_geographic_record("CALCULATED NUMBER OF VOTES")
    assert non_geographic_record("CHALLENGED VOTES")
    assert not non_geographic_record("Providence Church of God")


def test_shared_vtd_is_partitioned_without_overlap():
    data = gpd.GeoDataFrame([
        {"cycle": 1994, "chamber": "house", "district": 1, "donor_vtd_id": "VTD-X",
         "county_key": "TEST", "precinct_key": "PLACE 1", "geometry_confidence": "low",
         "geometry": box(0, 0, 10, 10)},
        {"cycle": 1994, "chamber": "house", "district": 1, "donor_vtd_id": "VTD-X",
         "county_key": "TEST", "precinct_key": "PLACE 2", "geometry_confidence": "low",
         "geometry": box(0, 0, 10, 10)},
    ], geometry="geometry", crs=5070)
    got = partition_shared_vtds(data)
    assert got.vtd_occupancy_count.tolist() == [2, 2]
    assert got.geometry.iloc[0].intersection(got.geometry.iloc[1]).area < 1e-8
    assert abs(got.geometry.area.sum() - 100) < 1e-8
