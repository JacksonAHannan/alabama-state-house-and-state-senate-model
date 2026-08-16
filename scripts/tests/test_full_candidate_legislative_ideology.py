import pandas as pd
from build_full_candidate_legislative_ideology import match_candidate, member_name_parts


def test_historical_comma_name_is_reordered_and_keeps_surname():
    assert member_name_parts('Lindsey, Richard') == ('RICHARD LINDSEY','LINDSEY')


def test_match_requires_unique_supported_identity():
    scores=pd.DataFrame([
        {'cycle':2002,'chamber':'house','normalized_name':'JOHN SMITH','surname':'SMITH','party':'D','district':1},
        {'cycle':2002,'chamber':'house','normalized_name':'JANE SMITH','surname':'SMITH','party':'D','district':2},
    ])
    candidate=pd.Series({'year':2002,'chamber':'house','canonical_name':'Smith','canonical_party':'D',
                         'incumbent':False,'district_candidate':1})
    assert match_candidate(candidate,scores)==(None,'unmatched_no_verified_legislative_identity')


def test_exact_name_precedes_surname_matching():
    scores=pd.DataFrame([
        {'cycle':2002,'chamber':'house','normalized_name':'JOHN SMITH','surname':'SMITH','party':'D','district':1},
        {'cycle':2002,'chamber':'house','normalized_name':'JANE SMITH','surname':'SMITH','party':'D','district':2},
    ])
    candidate=pd.Series({'year':2002,'chamber':'house','canonical_name':'John Smith','canonical_party':'D',
                         'incumbent':False,'district_candidate':1})
    match,method=match_candidate(candidate,scores)
    assert method=='exact_name_window'
    assert match.normalized_name=='JOHN SMITH'
