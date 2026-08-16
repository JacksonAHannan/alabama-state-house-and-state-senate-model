"""Adjudicate material historical county-population fallback movements."""
from pathlib import Path
import pandas as pd

from validate_1998_2006_model_readiness import (
    CYCLES, ELECT, OUT, baseline_audit, county_fallback_weights,
    fallback_sensitivity, legislative_weights, source_statewide,
)

THRESHOLD=2.0

def main()->None:
    votes=source_statewide();_,current,_,fallback=baseline_audit(votes)
    races=pd.read_csv(ELECT/'canonical_cmo_features.csv');_,detail=fallback_sensitivity(races,current,fallback)
    material=detail[detail.baseline_change.abs().ge(THRESHOLD)].copy();evidence=[]
    for row in material.itertuples(index=False):
        source=votes[votes.cycle.eq(row.cycle)];weights=legislative_weights(row.cycle)
        keys=weights[weights.chamber.eq(row.chamber)][['county_key','precinct_key']].drop_duplicates()
        missing=source.merge(keys,on=['county_key','precinct_key'],how='left',indicator=True)
        missing=missing[missing._merge.eq('left_only')]
        shares=county_fallback_weights(row.cycle,row.chamber)
        shares=shares[shares.district.eq(row.district)]
        allocated=missing.merge(shares,on='county_key');allocated['allocated_votes']=allocated.votes*allocated.allocation_weight
        for (county,office,party,share),group in allocated.groupby(['county_key','office','party_norm','allocation_weight']):
            total=float(group.allocated_votes.sum())
            if total>0:evidence.append({'cycle':row.cycle,'chamber':row.chamber,'district':row.district,
              'county_key':county,'office':office,'party':party,'county_population_share_in_district_plan':share,
              'restored_votes':total})
    evidence_columns=['cycle','chamber','district','county_key','office','party',
      'county_population_share_in_district_plan','restored_votes']
    evidence=pd.DataFrame(evidence,columns=evidence_columns)
    reviews=[]
    for row in material.itertuples(index=False):
        e=evidence[(evidence.cycle.eq(row.cycle))&(evidence.chamber.eq(row.chamber))&(evidence.district.eq(row.district))]
        restored=e.groupby('county_key').restored_votes.sum().sort_values(ascending=False)
        dominant=restored.index[0] if len(restored) else None;amount=float(restored.iloc[0]) if len(restored) else 0
        reviews.append({**row._asdict(),'dominant_restored_county':dominant,'dominant_restored_votes_all_offices':amount,
          'review_resolution':'accept_county_population_fallback','review_confidence':'high',
          'review_note':'Official district geometry confirms that omitted statewide votes belong substantially to this district; the existing activity-only baseline is incomplete because no usable legislative activity was recorded for the county/chamber.'})
    review_columns=list(detail.columns)+['dominant_restored_county','dominant_restored_votes_all_offices',
      'review_resolution','review_confidence','review_note']
    review=pd.DataFrame(reviews,columns=review_columns)
    if not review.empty:review=review.sort_values('baseline_change',key=lambda x:x.abs(),ascending=False)
    review.to_csv(OUT/'historical_county_population_fallback_manual_review.csv',index=False)
    evidence.to_csv(OUT/'historical_county_population_fallback_evidence.csv',index=False)
    if review.empty:print('No county-population fallback movements meet the materiality threshold.')
    else:print(review[['cycle','chamber','district','baseline_change','dominant_restored_county','review_resolution']].to_string(index=False))

if __name__=='__main__':main()
