import numpy as np
import pandas as pd

from analyze_social_conservatism_national_baselines import hc3_ols


def test_hc3_recovers_positive_social_relationship():
    x = np.linspace(-1, 1, 30)
    frame = pd.DataFrame({"cycle": [2002] * 30, "social_score": x, "outcome": 4 * x + 2})
    result = hc3_ols(frame, "outcome", [], "test")
    assert abs(result["social_coefficient_full_unit"] - 4) < 1e-8


def test_hc3_does_not_fill_missing_ideology():
    frame = pd.DataFrame({"cycle": [2002] * 8, "social_score": [np.nan, -1, -.5, 0, .2, .4, .8, 1],
                          "outcome": range(8)})
    result = hc3_ols(frame, "outcome", [], "test")
    assert result["n"] == 7
