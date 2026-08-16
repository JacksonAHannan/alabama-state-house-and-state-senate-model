"""Produce first descriptive comparisons for the experimental 1998-2006 CMO extension."""
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];ELECT=ROOT/'data'/'processed'/'elections'

def main()->None:
    races=pd.read_csv(ELECT/'canonical_cmo_features.csv')
    races=races[races.cycle.isin([1998,2002,2006])&races.war_eligible].copy()
    context=pd.read_csv(ELECT/'1998_2006_cmo_context_features.csv')
    extras=['cycle','chamber','district',*[column for column in ['prior_pres_dem_margin','prior_pres_source_complete',
      'census_vintage','readiness_status'] if column not in races]]
    races=races.merge(context[extras],on=['cycle','chamber','district'],how='left',validate='one_to_one')
    summary=(races.groupby(['cycle','chamber'],as_index=False).agg(
      races=('district','size'),mean_raw_overperformance=('raw_overperformance','mean'),
      median_raw_overperformance=('raw_overperformance','median'),sd_raw_overperformance=('raw_overperformance','std'),
      mean_abs_overperformance=('raw_overperformance',lambda x:x.abs().mean()),
      prior_pres_complete=('prior_pres_source_complete','sum'),finance_complete=('finance_complete','sum')))
    rows=[]
    for (cycle,chamber),group in races.groupby(['cycle','chamber']):
        complete=group[group.prior_pres_source_complete.astype(bool)]
        rows.append({'cycle':cycle,'chamber':chamber,'comparison':'raw_overperformance_vs_prior_pres_margin',
          'n':len(complete),'pearson_r':complete.raw_overperformance.corr(complete.prior_pres_dem_margin)})
    correlations=pd.DataFrame(rows)
    ranked=pd.concat([group.assign(abs_raw_overperformance=group.raw_overperformance.abs()).nlargest(10,'abs_raw_overperformance')
                      for _,group in races.groupby('cycle')],ignore_index=True)
    summary.to_csv(ELECT/'1998_2006_performance_summary.csv',index=False)
    correlations.to_csv(ELECT/'1998_2006_performance_correlations.csv',index=False)
    ranked.to_csv(ELECT/'1998_2006_largest_raw_overperformances.csv',index=False)
    print(summary.to_string(index=False));print('\n',correlations.to_string(index=False))

if __name__=='__main__':main()
