import pandas as pd
from build_full_candidate_legislative_ideology import (
    match_candidate, member_name_parts, remove_duplicate_member_assignments,
)


def test_historical_comma_name_is_reordered_and_keeps_surname():
    assert member_name_parts('Lindsey, Richard') == ('RICHARD LINDSEY','LINDSEY')


def test_surname_match_can_be_resolved_by_unique_district():
    scores=pd.DataFrame([
        {'cycle':2002,'chamber':'house','normalized_name':'JOHN SMITH','surname':'SMITH','party':'D','district':1},
        {'cycle':2002,'chamber':'house','normalized_name':'JANE SMITH','surname':'SMITH','party':'D','district':2},
    ])
    candidate=pd.Series({'year':2002,'chamber':'house','canonical_name':'Smith','canonical_party':'D',
                         'incumbent':False,'district_candidate':1})
    match, method = match_candidate(candidate,scores)
    assert method == 'surname_party_district_window'
    assert match.normalized_name == 'JOHN SMITH'


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


def test_surname_only_match_requires_district_when_available():
    scores=pd.DataFrame([{
        'cycle':1998,'chamber':'house','normalized_name':'JOHN THOMAS','surname':'THOMAS',
        'party':'R','district':49,'member_source_id':'M49',
    }])
    wrong=pd.Series({'year':1998,'chamber':'house','canonical_name':'Thomas','canonical_party':'R',
                     'incumbent':False,'district_candidate':27})
    right=wrong.copy(); right['district_candidate']=49
    assert match_candidate(wrong,scores)==(None,'unmatched_no_verified_legislative_identity')
    assert match_candidate(right,scores)[1]=='surname_party_district_window'


def test_duplicate_member_assignment_keeps_only_unique_district_match():
    rows=pd.DataFrame([
        {'year':1998,'member_source_id':'M49','district_candidate':27,'district':49,
         'behavioral_ideology':.4,'legislative_ideology_available':True,
         'coverage_status':'scored','identity_match_method':'exact_name_window'},
        {'year':1998,'member_source_id':'M49','district_candidate':49,'district':49,
         'behavioral_ideology':.4,'legislative_ideology_available':True,
         'coverage_status':'scored','identity_match_method':'exact_name_window'},
    ])
    result=remove_duplicate_member_assignments(rows,['member_source_id','district','behavioral_ideology'])
    assert result.loc[0,'member_source_id'] != result.loc[0,'member_source_id']  # NaN
    assert not result.loc[0,'legislative_ideology_available']
    assert result.loc[1,'member_source_id']=='M49'
