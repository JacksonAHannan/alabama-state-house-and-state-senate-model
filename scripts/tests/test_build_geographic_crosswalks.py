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
    assert set(weights.allocation_method) == {"vtd_population", "county_population_fallback"}
