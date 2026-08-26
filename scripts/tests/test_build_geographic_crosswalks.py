import numpy as np
import pandas as pd

from build_geographic_crosswalks import hierarchical_precinct_weights, precinct_norm


def test_precinct_norm_removes_jefferson_precinct_prefix():
    assert precinct_norm("PREC 1020 - TOM BRADFORD PARK") == "TOM BRADFORD PARK"
    assert precinct_norm("0040 E_MEMORIAL CHRISTIAN") == "E MEMORIAL CHRISTIAN"


def test_generated_geographic_weights_cover_every_precinct():
    weights = pd.read_csv("data/processed/war/geographic_precinct_district_weights.csv")
    sums = weights.groupby(["cycle", "chamber", "county_key", "precinct_key"]).allocation_weight.sum()
    assert np.allclose(sums, 1)
    allowed = {
        "reported_single_district", "split_precinct_block_population",
        "split_legislative_activity_fallback", "split_county_population_fallback",
        "spatial_no_reported_district",
        "county_population_no_reported_district_fallback", "county_level_ballot",
    }
    assert set(weights.allocation_method).issubset(allowed)
    assert {"reported_single_district", "split_legislative_activity_fallback"}.issubset(
        set(weights.allocation_method))
    assert not weights.loc[weights.cycle.eq(2022), "allocation_method"].eq(
        "split_county_population_fallback"
    ).any()


def test_2022_hd32_governor_matches_spatial_benchmark():
    offices = pd.read_csv("data/processed/war/district_baseline_office.csv")
    row = offices[
        offices.cycle.eq(2022) & offices.chamber.eq("house") &
        offices.district.eq(32) & offices.office.eq("Governor")
    ].squeeze()
    assert np.isclose(row.office_dem_margin, 1.549149, atol=1e-6)
    assert row.allocation_method == "reported_district_with_population_splits"
    assert np.isclose(row.baseline_fallback_share, 0)


def test_shared_vtd_does_not_split_distinct_single_district_precincts():
    activity = pd.DataFrame([
        {"cycle": 2010, "chamber": "house", "county_key": "CALHOUN",
         "precinct_key": "ANNISTON CARVER CENTER", "district": 32,
         "district_activity": 400, "precinct_activity": 400, "allocation_weight": 1.0},
        {"cycle": 2010, "chamber": "house", "county_key": "CALHOUN",
         "precinct_key": "ANNISTON GOLDEN SPRINGS", "district": 36,
         "district_activity": 900, "precinct_activity": 900, "allocation_weight": 1.0},
    ])
    matches = pd.DataFrame([
        {"cycle": 2010, "county_key": "CALHOUN", "precinct_key": precinct,
         "county_fips": "015", "geometry_id": "015000015", "vtd": "015000015",
         "match_method": "exact", "match_score": 100.0, "score_margin": 100.0}
        for precinct in ("ANNISTON CARVER CENTER", "ANNISTON GOLDEN SPRINGS")
    ])
    spatial = pd.DataFrame([
        {"county_fips": "015", "geometry_id": "015000015", "district": 32,
         "allocation_weight": 0.70},
        {"county_fips": "015", "geometry_id": "015000015", "district": 36,
         "allocation_weight": 0.30},
    ])
    blocks = pd.DataFrame([
        {"county_fips": "015", "district": 32, "population": 700},
        {"county_fips": "015", "district": 36, "population": 300},
    ])

    result = hierarchical_precinct_weights(activity, matches, spatial, blocks)

    carver = result[result.precinct_key.eq("ANNISTON CARVER CENTER")]
    golden = result[result.precinct_key.eq("ANNISTON GOLDEN SPRINGS")]
    assert carver[["district", "allocation_weight"]].values.tolist() == [[32, 1.0]]
    assert golden[["district", "allocation_weight"]].values.tolist() == [[36, 1.0]]
    assert set(result.allocation_method) == {"reported_single_district"}


def test_reported_multidistrict_precinct_uses_ballot_activity_share():
    activity = pd.DataFrame([
        {"cycle": 2010, "chamber": "house", "county_key": "TALLADEGA",
         "precinct_key": "EASTABOGA CLUB HOUSE", "district": 32,
         "district_activity": 300, "precinct_activity": 500, "allocation_weight": 0.6},
        {"cycle": 2010, "chamber": "house", "county_key": "TALLADEGA",
         "precinct_key": "EASTABOGA CLUB HOUSE", "district": 35,
         "district_activity": 200, "precinct_activity": 500, "allocation_weight": 0.4},
    ])
    matches = pd.DataFrame([
        {"cycle": 2010, "county_key": "TALLADEGA", "precinct_key": "EASTABOGA CLUB HOUSE",
         "county_fips": "121", "geometry_id": "121000005", "vtd": "121000005",
         "match_method": "exact", "match_score": 100.0, "score_margin": 100.0}
    ])
    spatial = pd.DataFrame([
        {"county_fips": "121", "geometry_id": "121000005", "district": 32,
         "allocation_weight": 0.2},
        {"county_fips": "121", "geometry_id": "121000005", "district": 35,
         "allocation_weight": 0.8},
    ])
    blocks = pd.DataFrame([
        {"county_fips": "121", "district": 32, "population": 200},
        {"county_fips": "121", "district": 35, "population": 800},
    ])

    result = hierarchical_precinct_weights(activity, matches, spatial, blocks).sort_values("district")

    assert result.district.tolist() == [32, 35]
    assert np.allclose(result.allocation_weight, [0.6, 0.4])
    assert set(result.allocation_method) == {"split_legislative_activity_fallback"}
