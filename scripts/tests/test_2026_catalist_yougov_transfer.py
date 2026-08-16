import numpy as np
from scripts.build_2026_catalist_yougov_transfer import expit, logit


def test_logit_transfer_round_trip():
    values=np.array([.05,.5,.95])
    assert np.allclose(expit(logit(values)),values)
