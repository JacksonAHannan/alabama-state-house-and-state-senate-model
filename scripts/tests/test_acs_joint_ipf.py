import numpy as np
from scripts.build_acs_block_group_joint_race_education import ipf


def test_ipf_satisfies_row_and_column_constraints():
    result=ipf(np.array([[4.,1.],[1.,4.]]),np.array([10.,20.]),np.array([12.,18.]))
    assert np.allclose(result.sum(axis=1),[10,20],atol=1e-6)
    assert np.allclose(result.sum(axis=0),[12,18],atol=1e-6)
