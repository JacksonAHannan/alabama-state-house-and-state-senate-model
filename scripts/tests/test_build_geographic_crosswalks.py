import numpy as np
import pandas as pd

from build_geographic_crosswalks import precinct_norm


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
    assert {"reported_single_district", "split_precinct_block_population"}.issubset(
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
