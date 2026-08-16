"""Allocate same-cycle federal elections into Alabama legislative districts.

Only contested D-R federal contests contribute to the margin.  Uncontested
House races remain in the denominator of ``federal_contested_coverage`` so the
result never silently treats a one-party ballot as a 100-point baseline.
"""
from __future__ import annotations
from pathlib import Path
from contextlib import closing
import re,sqlite3
import numpy as np
import pandas as pd

from build_1998_2006_context_features import legislative_weights,county_population_district_weights
from warehouse import connect,initialize,begin_run,finish_run,register_table

ROOT=Path(__file__).resolve().parents[1];ELECT=ROOT/'data'/'processed'/'elections'
DB=ELECT/'alabama_elections.sqlite';CYCLES=(1994,1998,2002,2006,2010,2014,2018,2022)
SCHEMA=Path(__file__).with_name('warehouse_federal_baseline_schema.sql')
PARTY_OVERRIDES_2010={
 'JO BONNER':'R','DAVID WALTER':'D','MARTHA ROBY':'R','BOBBY BRIGHT':'D',
 'MIKE ROGERS':'R','STEVE SEGREST':'D','ROBERT ADERHOLT':'R','MO BROOKS':'R',
 'STEVE RABY':'D','SPENCER BACHUS':'R','TERRI A SEWELL':'D','DON CHAMBERLAIN':'R',
 'RICHARD C SHELBY':'R','WILLIAM G BARNES':'D'}

def federal_office(title:object,district:object=None)->tuple[str|None,int|None]:
    text=re.sub(r'\s+',' ',str(title)).strip().upper()
    if re.search(r'\b(?:U\.?S\.?|UNITED STATES)\s+SENAT',text):return 'us_senate',None
    is_house=(re.search(r'\b(?:U\.?S\.?|UNITED STATES)\b.*\b(?:REPRESENTATIVE|REP\.?|HOUSE|CONGRESS)',text)
              or re.search(r'\bUS\s+REP',text))
    if not is_house:return None,None
    value=pd.to_numeric(district,errors='coerce')
    if pd.isna(value):
        patterns=(r'(?:DIST(?:RICT)?\.?|#|\bD)\s*(\d+)',r'(\d+)(?:ST|ND|RD|TH)\s+CONGRESSIONAL')
        match=next((m for pattern in patterns if (m:=re.search(pattern,text))),None)
        value=float(match.group(1)) if match else np.nan
    return 'us_house',(None if pd.isna(value) else int(value))

def load_observations()->pd.DataFrame:
    with sqlite3.connect(DB) as connection:
        data=pd.read_sql_query("""select year,county_key,precinct_key,office,district,candidate_key,
          party_norm,votes from vote_observations where source='alabama_sos'
          and year in (1994,1998,2002,2006,2010,2014,2018,2022)""",connection)
        nodes=pd.read_sql_query("""select node_id,year,county_key,precinct_key from precinct_nodes
          where source='alabama_sos'""",connection)
    parsed=[federal_office(row.office,row.district) for row in data.itertuples()]
    data['federal_office']=[x[0] for x in parsed];data['federal_district']=[x[1] for x in parsed]
    data=data.rename(columns={'district':'source_district'})
    data=data[data.federal_office.notna()].copy()
    # Repair blank county exports from a unique same-cycle/candidate party seen
    # elsewhere, then apply a documented 2010 ballot override (that workbook
    # omitted party labels for every federal contest).
    known=(data[data.party_norm.isin(['D','R'])].groupby(['year','candidate_key']).party_norm
           .agg(lambda x:sorted(set(x))))
    mapping={key:values[0] for key,values in known.items() if len(values)==1}
    missing=~data.party_norm.isin(['D','R'])
    data.loc[missing,'party_norm']=[mapping.get((row.year,row.candidate_key),'O') for row in data[missing].itertuples()]
    mask_2010=data.year.eq(2010)&data.candidate_key.isin(PARTY_OVERRIDES_2010)
    data.loc[mask_2010,'party_norm']=data.loc[mask_2010,'candidate_key'].map(PARTY_OVERRIDES_2010)
    data=data[data.party_norm.isin(['D','R'])].copy()
    data['contest']=np.where(data.federal_office.eq('us_senate'),'us_senate',
                             'us_house_'+data.federal_district.fillna(-1).astype(int).astype(str))
    return data.merge(nodes,on=['year','county_key','precinct_key'],how='left',validate='many_to_one')

def historical_weights(cycle:int,chamber:str)->pd.DataFrame:
    if cycle==1994:
        path=ELECT/'1994_precinct_district_ballot_weights.csv';weights=pd.read_csv(path)
        return weights[weights.chamber.eq(chamber)][['county_key','precinct_key','district','allocation_weight']]
    return legislative_weights(cycle).query('chamber == @chamber')[
        ['county_key','precinct_key','district','allocation_weight']]

def allocate_cycle(source:pd.DataFrame,cycle:int,chamber:str,modern:pd.DataFrame)->pd.DataFrame:
    current=source[source.year.eq(cycle)].copy()
    if cycle>=2010:
        weights=modern[(modern.cycle.eq(cycle))&(modern.chamber.eq(chamber))]
        out=current.merge(weights[['node_id','district','allocation_weight']],on='node_id',how='inner',validate='many_to_many')
        out['allocation_method']='canonical_geographic_weight'
        return out
    weights=historical_weights(cycle,chamber)
    merged=current.merge(weights,on=['county_key','precinct_key'],how='left',indicator=True,validate='many_to_many')
    direct=merged[merged._merge.eq('both')].copy();direct['allocation_method']='legislative_activity_provisional'
    if cycle==1994:return direct
    missing=merged[merged._merge.eq('left_only')][current.columns].merge(
        county_population_district_weights(cycle,chamber),on='county_key',how='left',validate='many_to_many')
    missing['allocation_method']='county_population_fallback'
    return pd.concat([direct,missing[missing.allocation_weight.notna()]],ignore_index=True,sort=False)

def build(source:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    modern=pd.read_csv(ELECT/'canonical_precinct_district_weights.csv');parts=[]
    for cycle in CYCLES:
        for chamber in ('house','senate'):
            allocated=allocate_cycle(source,cycle,chamber,modern)
            allocated['cycle']=cycle;allocated['chamber']=chamber
            allocated['allocated_votes']=allocated.votes*allocated.allocation_weight
            parts.append(allocated)
    allocated=pd.concat(parts,ignore_index=True,sort=False)
    statewide=(source.groupby(['year','contest','party_norm'],as_index=False).votes.sum()
        .pivot(index=['year','contest'],columns='party_norm',values='votes').fillna(0).reset_index())
    for party in ('D','R'):
        if party not in statewide:statewide[party]=0
    statewide['contested']=statewide.D.gt(0)&statewide.R.gt(0)
    allocated=allocated.merge(statewide[['year','contest','contested']],on=['year','contest'],validate='many_to_one')
    totals=(allocated.groupby(['cycle','chamber','district'],as_index=False).allocated_votes.sum()
            .rename(columns={'allocated_votes':'all_federal_major_votes'}))
    valid=allocated[allocated.contested].copy()
    contest=(valid.groupby(['cycle','chamber','district','federal_office','contest','party_norm'],as_index=False).allocated_votes.sum()
        .pivot(index=['cycle','chamber','district','federal_office','contest'],columns='party_norm',values='allocated_votes').fillna(0).reset_index())
    for party in ('D','R'):
        if party not in contest:contest[party]=0
    contest['two_party_votes']=contest.D+contest.R
    contest['dem_margin']=100*(contest.D-contest.R)/contest.two_party_votes.where(contest.two_party_votes.gt(0))
    components=(contest.groupby(['cycle','chamber','district','federal_office'],as_index=False)
        .agg(dem_votes=('D','sum'),rep_votes=('R','sum'),two_party_votes=('two_party_votes','sum')))
    components['dem_margin']=100*(components.dem_votes-components.rep_votes)/components.two_party_votes
    wide=components.pivot(index=['cycle','chamber','district'],columns='federal_office',values=['dem_margin','two_party_votes'])
    wide.columns=['_'.join(reversed(x)) for x in wide.columns];wide=wide.reset_index()
    for column in ('us_house_dem_margin','us_senate_dem_margin','us_house_two_party_votes','us_senate_two_party_votes'):
        if column not in wide:wide[column]=np.nan
    wide['federal_index_margin']=wide[['us_house_dem_margin','us_senate_dem_margin']].mean(axis=1)
    wide['federal_components']=wide[['us_house_dem_margin','us_senate_dem_margin']].notna().sum(axis=1)
    contested_votes=contest.groupby(['cycle','chamber','district'],as_index=False).two_party_votes.sum().rename(columns={'two_party_votes':'contested_federal_votes'})
    wide=wide.merge(contested_votes,on=['cycle','chamber','district']).merge(totals,on=['cycle','chamber','district'])
    wide['federal_contested_coverage']=wide.contested_federal_votes/wide.all_federal_major_votes
    method=(allocated.groupby(['cycle','chamber','district']).allocation_method.agg(
        lambda x:'county_population_fallback' if (x=='county_population_fallback').any() else
        'legislative_activity_provisional' if (x=='legislative_activity_provisional').any() else
        'canonical_geographic_weight').reset_index(name='federal_allocation_method'))
    return wide.merge(method,on=['cycle','chamber','district']),contest

def main()->None:
    source=load_observations();features,contest=build(source)
    features.to_csv(ELECT/'historical_federal_district_baselines.csv',index=False)
    contest.to_csv(ELECT/'historical_federal_contest_components.csv',index=False)
    audit=(features.groupby(['cycle','chamber'],as_index=False).agg(districts=('district','size'),
      federal_available=('federal_index_margin',lambda x:x.notna().sum()),median_contested_coverage=('federal_contested_coverage','median'),
      house_available=('us_house_dem_margin',lambda x:x.notna().sum()),senate_available=('us_senate_dem_margin',lambda x:x.notna().sum())))
    audit.to_csv(ELECT/'validation'/'historical_federal_baseline_coverage.csv',index=False);print(audit.to_string(index=False))
    with closing(connect()) as connection:
        initialize(connection);connection.executescript(SCHEMA.read_text(encoding='utf-8'))
        run=begin_run(connection,'historical_federal_district_baseline',{'cycles':list(CYCLES),'contested_only':True})
        connection.execute('delete from mart_historical_federal_district_baseline')
        features.to_sql('mart_historical_federal_district_baseline',connection,if_exists='append',index=False)
        register_table(connection,'mart_historical_federal_district_baseline','mart',
          'scripts/build_historical_federal_baselines.py','cycle/chamber/district',
          'Alabama SOS major-party federal returns; uncontested contests excluded from margin and retained in coverage',
          'replace','Same-cycle federal House/Senate baseline allocated to legislative districts')
        finish_run(connection,run,{'rows':len(features),'minimum_contested_coverage':float(features.federal_contested_coverage.min())})
        connection.commit()

if __name__=='__main__':main()
