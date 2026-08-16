import pandas as pd

def test_material_fallback_reviews_are_resolved_with_geometry_evidence():
    reviews=pd.read_csv('data/processed/elections/validation/historical_county_population_fallback_manual_review.csv')
    evidence=pd.read_csv('data/processed/elections/validation/historical_county_population_fallback_evidence.csv')
    assert reviews.empty or reviews.baseline_change.abs().ge(2).all()
    assert reviews.empty or reviews.review_resolution.eq('accept_county_population_fallback').all()
    assert evidence.empty or evidence.restored_votes.gt(0).all()
    assert set(map(tuple,reviews[['cycle','chamber','district']].values)).issubset(
        set(map(tuple,evidence[['cycle','chamber','district']].drop_duplicates().values)))
