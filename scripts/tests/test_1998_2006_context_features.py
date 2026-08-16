import pandas as pd
from build_1998_2006_context_features import CENSUS, PRIOR, _pres1996, _pres2000, _pres2004, candidates, incumbency, parse_2000_sf3_bulk

def test_bulk_sf3_parser_recovers_full_alabama_tract_population():
    result=parse_2000_sf3_bulk(CENSUS/'all_Alabama2f32000')
    assert len(result)==1081
    assert pd.to_numeric(result.P001001).sum()==4_447_100
    assert result[['P007003','P037001','P148A001']].notna().all().all()

def test_historical_presidential_sources_have_broad_county_coverage():
    assert _pres1996().county_key.nunique() >= 65
    assert _pres2000().county_key.nunique() >= 60
    assert _pres2004().county_key.nunique() >= 65

def test_2000_presidential_parser_excludes_duplicate_county_summaries():
    result=_pres2000()
    assert not result.precinct_key.isin(['CALCULATED','REPORTED']).any()
    assert 1_200_000 < (result.dem_votes+result.rep_votes).sum() < 1_400_000

def test_incumbency_is_positive_evidence_not_blanket_zero():
    result=incumbency(candidates())
    assert set(result.cycle)==set(PRIOR)
    assert result.groupby('cycle').incumbent.sum().min() >= 40
    assert set(result.review_status)<= {'supported','unknown'}

def test_context_export_has_full_district_universe_and_no_missing_as_zero_contract():
    result=pd.read_csv('data/processed/elections/1998_2006_cmo_context_features.csv')
    assert len(result)==3*(105+35)
    assert result.groupby(['cycle','chamber']).district.nunique().min()==35
    assert result.prior_presidential_year.notna().all()
    assert result.readiness_status.str.startswith('experimental_').all()
