import pandas as pd
from scripts.build_precinct_identity import precinct_code, vote_similarity

def test_precinct_code_normalizes_leading_zeroes():
    assert precinct_code("0040 - East Memorial") == "40"
    assert precinct_code("East Memorial") == ""

def test_vote_fingerprint_uses_shared_offices():
    left = pd.DataFrame({"office":["President","Governor"],"votes":[100,80]})
    right = pd.DataFrame({"office":["President","Governor"],"votes":[100,72]})
    score, shared = vote_similarity(left,right)
    assert shared == 2
    assert round(score,1) == 95.0
