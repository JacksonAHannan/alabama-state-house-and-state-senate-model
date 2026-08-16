import numpy as np

from build_1994_context_features import (KNOWN_1992_PRESIDENTIAL_GAPS, candidates,
    combined_context, district_demographics, finance_coverage, incumbency,
    presidential_features, presidential_precincts)


def test_1994_demographics_cover_both_plans_and_reconcile_population():
    result= district_demographics()
    assert result.groupby("chamber").district.nunique().to_dict()=={"house":105,"senate":35}
    population=result.groupby("chamber").total_population.sum()
    assert abs(population.house-population.senate)/population.house<1e-8
    assert result.source_population_coverage.min()>0.999
    assert result.nonwhite_share.between(0,1).all()
    assert result.white_college_share.between(0,1).all()
    assert result.allocation_method.eq("1990_sf3_tract_area_interpolation_provisional").all()


def test_1992_presidential_archive_has_only_documented_gaps():
    precincts=presidential_precincts()
    assert precincts.county_key.nunique()==64
    assert not KNOWN_1992_PRESIDENTIAL_GAPS.intersection(set(precincts.county_key))
    district,matches=presidential_features(precincts)
    assert district.groupby("chamber").district.nunique().to_dict()=={"house":105,"senate":35}
    assert district.dem_margin.notna().sum()>=120
    assert not district.loc[district.dem_margin.isna(),"source_complete"].any()
    assert district.fallback_share.dropna().between(0,1+1e-12).all()
    assert {"exact","fuzzy","unmatched","county_level_ballot"}.issuperset(set(matches.match_method))


def test_1994_incumbency_is_positive_evidence_and_finance_unknown_not_zero():
    candidate=candidates();inc=incumbency(candidate);finance=finance_coverage(candidate)
    assert int(inc.incumbent.sum())==75
    assert inc.loc[inc.incumbent.eq(0),"review_status"].eq("unknown").all()
    assert finance.total_resources_raised.isna().all()
    assert finance.observation_status.eq("not_observed_unknown_not_zero").all()
    sanderford=inc[(inc.chamber.eq("house"))&(inc.district.eq(20))].iloc[0]
    assert sanderford.party=="R"


def test_1994_context_has_no_fabricated_finance_ratio():
    demographics=district_demographics();precincts=presidential_precincts()
    president,_=presidential_features(precincts);candidate=candidates()
    context=combined_context(demographics,president,incumbency(candidate),finance_coverage(candidate))
    assert len(context)==140
    assert not context.finance_complete.any()
    assert context.log_resource_ratio_d_to_r.isna().all()
