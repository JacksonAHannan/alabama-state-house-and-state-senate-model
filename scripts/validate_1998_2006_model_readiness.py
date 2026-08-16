"""Validation gates for the experimental 1998, 2002, and 2006 CMO extension."""
from __future__ import annotations
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import geopandas as gpd

from build_1998_2006_context_features import DB, ELECT, PRES, WAR, PRIOR, legislative_weights, county_population_district_weights
from build_presidential_district_features import _prepare_weights, allocate_to_districts

ROOT=Path(__file__).resolve().parents[1];CYCLES=(1998,2002,2006);CORE=('Governor','Attorney General')
OUT=ELECT/'validation';OUT.mkdir(parents=True,exist_ok=True)

def source_statewide()->pd.DataFrame:
    with sqlite3.connect(DB) as c:
        return pd.read_sql_query("""select year cycle,county_key,precinct_key,office,party_norm,sum(votes) votes
          from vote_observations where source='alabama_sos' and year in (1998,2002,2006)
          and office in ('Governor','Attorney General') and party_norm in ('D','R')
          group by year,county_key,precinct_key,office,party_norm""",c)

def baseline_audit(votes:pd.DataFrame):
    allocation=[];district_rows=[];fallback_district_rows=[];weight_rows=[]
    for cycle in CYCLES:
      source=votes[votes.cycle.eq(cycle)]
      for chamber in ('house','senate'):
        weights=legislative_weights(cycle);weights=weights[weights.chamber.eq(chamber)].copy()
        sums=weights.groupby(['county_key','precinct_key']).allocation_weight.sum()
        weight_rows.append({'cycle':cycle,'chamber':chamber,'weight_groups':len(sums),
          'max_weight_sum_error':float((sums-1).abs().max()),'split_precinct_groups':int(weights.groupby(['county_key','precinct_key']).district.size().gt(1).sum())})
        merged=source.merge(weights,on=['cycle','county_key','precinct_key'],how='left',indicator=True)
        matched=merged[merged._merge.eq('both')].copy();matched['allocated_votes']=matched.votes*matched.allocation_weight
        missing=merged[merged._merge.eq('left_only')][source.columns].copy().merge(county_population_district_weights(cycle,chamber),on='county_key',how='left')
        missing['allocated_votes']=missing.votes*missing.allocation_weight;augmented=pd.concat([matched,missing],ignore_index=True,sort=False)
        source_tot=source.groupby(['office','party_norm']).votes.sum();alloc_tot=matched.groupby(['office','party_norm']).allocated_votes.sum()
        augmented_tot=augmented.groupby(['office','party_norm']).allocated_votes.sum()
        for key,total in source_tot.items():
          allocated=float(alloc_tot.get(key,0));hybrid=float(augmented_tot.get(key,0));allocation.append({'cycle':cycle,'chamber':chamber,'office':key[0],'party':key[1],
            'source_votes':total,'allocated_votes':allocated,'unallocated_votes':total-allocated,'coverage':allocated/total if total else np.nan,
            'hybrid_allocated_votes':hybrid,'hybrid_unallocated_votes':total-hybrid,
            'hybrid_coverage':hybrid/total if total else np.nan})
        part=(matched.groupby(['district','office','party_norm']).allocated_votes.sum().unstack(fill_value=0).reset_index())
        for party in ('D','R'):
          if party not in part:part[party]=0
        part['office_margin']=100*(part.D-part.R)/(part.D+part.R).where((part.D+part.R).gt(0));part['cycle']=cycle;part['chamber']=chamber
        district_rows.append(part)
        alt=(augmented.groupby(['district','office','party_norm']).allocated_votes.sum().unstack(fill_value=0).reset_index())
        for party in ('D','R'):
          if party not in alt:alt[party]=0
        alt['office_margin']=100*(alt.D-alt.R)/(alt.D+alt.R).where((alt.D+alt.R).gt(0));alt['cycle']=cycle;alt['chamber']=chamber
        fallback_district_rows.append(alt)
    return pd.DataFrame(allocation),pd.concat(district_rows,ignore_index=True),pd.DataFrame(weight_rows),pd.concat(fallback_district_rows,ignore_index=True)

def unmatched_baseline_detail(votes:pd.DataFrame)->pd.DataFrame:
    rows=[]
    for cycle in CYCLES:
      source=votes[votes.cycle.eq(cycle)]
      for chamber in ('house','senate'):
        keys=legislative_weights(cycle);keys=keys[keys.chamber.eq(chamber)][['county_key','precinct_key']].drop_duplicates()
        missing=source.merge(keys,on=['county_key','precinct_key'],how='left',indicator=True);missing=missing[missing._merge.eq('left_only')]
        grouped=missing.groupby(['county_key','office','party_norm'],as_index=False).votes.sum();grouped['cycle']=cycle;grouped['chamber']=chamber;rows.append(grouped)
    return pd.concat(rows,ignore_index=True)

def presidential_audit(raw:pd.DataFrame,features:pd.DataFrame,matches:pd.DataFrame)->pd.DataFrame:
    rows=[]
    for cycle in CYCLES:
      year=PRIOR[cycle];source=raw[raw.cycle.eq(year)];district=features[features.cycle.eq(cycle)]
      current=matches[matches.target_cycle.eq(cycle)]
      for chamber in ('house','senate'):
        d=district[district.chamber.eq(chamber)];rows.append({'cycle':cycle,'source_year':year,'chamber':chamber,
          'source_counties':source.county_key.nunique(),'source_two_party_votes':float((source.dem_votes+source.rep_votes).sum()),
          'allocated_two_party_votes':float(d.two_party_votes.sum()),'districts_with_margin':int(d.dem_margin.notna().sum()),
          'districts_source_complete':int(d.source_complete.fillna(False).sum()),'median_fallback_share':float(d.fallback_share.median()),
          'p90_fallback_share':float(d.fallback_share.quantile(.9)),'exact_or_fuzzy_match_share':float(current.match_method.isin(['exact','fuzzy']).mean())})
    return pd.DataFrame(rows)

def candidate_audits(races:pd.DataFrame,inc:pd.DataFrame,fin:pd.DataFrame):
    eligible=races[races.war_eligible].copy();keys=['cycle','chamber','district']
    i=inc.merge(eligible[keys],on=keys,how='inner');f=fin.merge(eligible[keys],on=keys,how='inner')
    rows=[]
    for cycle in CYCLES:
      rr=eligible[eligible.cycle.eq(cycle)];ii=i[i.cycle.eq(cycle)];ff=f[f.cycle.eq(cycle)]
      rows.append({'cycle':cycle,'eligible_races':len(rr),'candidate_rows':len(ii),'supported_incumbents':int(ii.incumbent.sum()),
        'incumbency_unknown_candidates':int(ii.review_status.eq('unknown').sum()),'finance_observed_candidates':int(ff.total_resources_raised.notna().sum()),
        'finance_complete_races':int(rr.finance_complete.fillna(False).sum()),'duplicate_candidate_ids':int(ii.canonical_candidate_id.duplicated().sum()),
        'negative_finance_values':int(ff.total_resources_raised.dropna().lt(0).sum())})
    return pd.DataFrame(rows),i,f

def sensitivity(races:pd.DataFrame,office:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    eligible=races[races.war_eligible][['cycle','chamber','district','legislative_dem_margin','raw_overperformance']]
    wide=office.pivot_table(index=['cycle','chamber','district'],columns='office',values='office_margin').reset_index()
    x=eligible.merge(wide,on=['cycle','chamber','district'],how='left');x['overperformance_governor']=x.legislative_dem_margin-x.Governor
    x['overperformance_attorney_general']=x.legislative_dem_margin-x['Attorney General']
    rows=[]
    for (cycle,chamber),g in x.groupby(['cycle','chamber']):
      rows.append({'cycle':cycle,'chamber':chamber,'races':len(g),'governor_vs_core_rank_correlation':g.overperformance_governor.corr(g.raw_overperformance,method='spearman'),
        'ag_vs_core_rank_correlation':g.overperformance_attorney_general.corr(g.raw_overperformance,method='spearman'),
        'mean_governor_core_abs_difference':float((g.overperformance_governor-g.raw_overperformance).abs().mean()),
        'mean_ag_core_abs_difference':float((g.overperformance_attorney_general-g.raw_overperformance).abs().mean())})
    return pd.DataFrame(rows),x

def fallback_sensitivity(races:pd.DataFrame,current:pd.DataFrame,fallback:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    keys=['cycle','chamber','district'];eligible=races[races.cycle.isin(CYCLES)&races.war_eligible][keys+['legislative_dem_margin']]
    def core(frame,name):return frame.groupby(keys,as_index=False).office_margin.mean().rename(columns={'office_margin':name})
    x=eligible.merge(core(current,'current_baseline'),on=keys).merge(core(fallback,'fallback_baseline'),on=keys)
    x['current_overperformance']=x.legislative_dem_margin-x.current_baseline;x['fallback_overperformance']=x.legislative_dem_margin-x.fallback_baseline
    rows=[]
    for (cycle,chamber),g in x.groupby(['cycle','chamber']):rows.append({'cycle':cycle,'chamber':chamber,'races':len(g),
      'rank_correlation':g.current_overperformance.corr(g.fallback_overperformance,method='spearman'),
      'mean_abs_baseline_change':(g.current_baseline-g.fallback_baseline).abs().mean(),
      'max_abs_baseline_change':(g.current_baseline-g.fallback_baseline).abs().max()})
    x['baseline_change']=x.fallback_baseline-x.current_baseline
    return pd.DataFrame(rows),x

def readiness(allocation,weights,pres,candidates,sensitivity)->pd.DataFrame:
    rows=[]
    for cycle in CYCLES:
      a=allocation[allocation.cycle.eq(cycle)];w=weights[weights.cycle.eq(cycle)];p=pres[pres.cycle.eq(cycle)];c=candidates[candidates.cycle.eq(cycle)];s=sensitivity[sensitivity.cycle.eq(cycle)]
      checks={
        'weight_conservation':w.max_weight_sum_error.max()<1e-9,
        'hybrid_baseline_vote_coverage_99pct':a.hybrid_coverage.min()>=.99,
        'presidential_complete_80pct':p.districts_source_complete.sum()/p.districts_with_margin.sum()>=.80,
        'presidential_fallback_median_below_50pct':p.median_fallback_share.max()<.50,
        'candidate_ids_unique':c.duplicate_candidate_ids.sum()==0,
        'finance_nonnegative':c.negative_finance_values.sum()==0,
        'baseline_rank_sensitivity_090':min(s.governor_vs_core_rank_correlation.min(),s.ag_vs_core_rank_correlation.min())>=.90}
      rows.extend({'cycle':cycle,'gate':gate,'passed':bool(value)} for gate,value in checks.items())
    return pd.DataFrame(rows)

def main():
    votes=source_statewide();allocation,office,weights,fallback_office=baseline_audit(votes)
    raw=pd.read_csv(PRES/'1996_2004_historical_president_precinct.csv');features=pd.read_csv(PRES/'1998_2006_district_presidential_features.csv');matches=pd.read_csv(PRES/'1998_2006_presidential_precinct_matches.csv')
    pres=presidential_audit(raw,features,matches);races=pd.read_csv(ELECT/'canonical_cmo_features.csv');inc=pd.read_csv(ELECT/'1998_2006_candidate_incumbency.csv');fin=pd.read_csv(WAR/'1998_2006_candidate_finance_coverage.csv')
    candidates,eligible_inc,eligible_fin=candidate_audits(races,inc,fin);sens,detail=sensitivity(races,office)
    fallback_sens,fallback_detail=fallback_sensitivity(races,office,fallback_office);gates=readiness(allocation,weights,pres,candidates,sens)
    outputs={'historical_baseline_allocation_validation.csv':allocation,'historical_baseline_weight_validation.csv':weights,
      'historical_baseline_unmatched_county_detail.csv':unmatched_baseline_detail(votes),
      'historical_presidential_validation.csv':pres,'historical_candidate_context_validation.csv':candidates,
      'historical_baseline_sensitivity.csv':sens,'historical_baseline_sensitivity_detail.csv':detail,
      'historical_county_population_fallback_sensitivity.csv':fallback_sens,
      'historical_county_population_fallback_detail.csv':fallback_detail,
      'historical_cmo_readiness_gates.csv':gates}
    for name,frame in outputs.items():frame.to_csv(OUT/name,index=False)
    print(gates.groupby('cycle').passed.agg(['sum','count']).to_string());print('\nFailed gates:\n',gates[~gates.passed].to_string(index=False))

if __name__=='__main__':main()
