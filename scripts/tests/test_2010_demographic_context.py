import pandas as pd
from build_2010_demographic_context import RAW, build, parse_acs_2010

def test_2010_context_reuses_same_plan_2006_rows_with_explicit_age():
    rows=[]
    for chamber,count in [('house',105),('senate',35)]:
        rows.extend({'cycle':2006,'chamber':chamber,'district':i+1,
                     'nonwhite_share':.2,'white_college_share':.3,
                     'allocation_method':'old'} for i in range(count))
    got=build(pd.DataFrame(rows))
    assert set(got.cycle)=={2010}
    assert set(got.demographic_age_years)=={10}
    assert set(got.allocation_method)=={'2000_sf3_same_2002_2010_plan_provisional'}

def test_downloaded_2010_acs_has_complete_direct_sld_coverage():
    got=parse_acs_2010(RAW)
    assert got.groupby('chamber').district.nunique().to_dict()=={'house':105,'senate':35}
    assert got.nonwhite_share.between(0,1).all()
    assert got.white_college_share.between(0,1).all()
    assert set(got.allocation_method)=={'2006_2010_acs5_direct_sld'}
