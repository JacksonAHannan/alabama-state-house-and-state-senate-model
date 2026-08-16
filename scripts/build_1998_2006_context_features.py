"""Build auditable demographics, incumbency, finance, and presidential context for 1998-2006."""
from __future__ import annotations

from contextlib import closing
from io import BytesIO
from pathlib import Path
import csv as csv_module
import re, sqlite3, zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from build_1994_context_features import tract_demographics as tract_demographics_1990
from build_candidate_finance_features import canonical_person
from build_presidential_district_features import _prepare_weights, allocate_to_districts
from sos_precinct import _workbook_sheets
from oe_normalize import normalize_name
from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_source_file, register_table

ELECT=ROOT/'data'/'processed'/'elections'; PRES=ROOT/'data'/'processed'/'presidential'
DEM=ROOT/'data'/'processed'/'demographics'; WAR=ROOT/'data'/'processed'/'war'
RAW=ROOT/'data'/'raw'/'alabama_elections_and_geography'; CENSUS=ROOT/'data'/'raw'/'census'/'2000_sf3_alabama'
DB=ELECT/'alabama_elections.sqlite'; SHOR=ROOT/'data'/'raw'/'ideology'/'shor_mccarty_individual_legislators_1993_2018.tsv'
SCHEMA=Path(__file__).with_name('warehouse_1998_2006_context_schema.sql')
CYCLES=(1998,2002,2006); PRIOR={1998:1996,2002:2000,2006:2004}
PLANS={
  1998:{'house':(RAW/'al_lower_1992_2000'/'al_lower_1992_2000.shp','DISTRICT'),
        'senate':(RAW/'al_upper_1992_2000'/'al_upper_1992_2000.shp','SLDUST00')},
  2002:{'house':(RAW/'al_lower_2002_2010'/'al_lower_2002_2010.shp','DISTRICT'),
        'senate':(RAW/'al_upper_2002_2010'/'al_upper_2002_2010.shp','DISTRICT')},
  2006:{'house':(RAW/'al_lower_2002_2010'/'al_lower_2002_2010.shp','DISTRICT'),
        'senate':(RAW/'al_upper_2002_2010'/'al_upper_2002_2010.shp','DISTRICT')},
}
TRACT_URL='https://www2.census.gov/geo/tiger/PREVGENZ/tr/tr00shp/tr01_d00_shp.zip'
SF3_URL='https://api.census.gov/data/2000/dec/sf3'

def county_population_district_weights(cycle:int,chamber:str)->pd.DataFrame:
    """Return independently constructed county-to-district population shares.

    These weights are a conservative fallback for statewide-result precincts
    that cannot be joined to legislative precinct activity.  They never use
    votes from the modeled legislative contest.
    """
    tracts=(tract_demographics_1990() if cycle==1998 else tract_demographics_2000()).to_crs(5070)
    tracts['county_fips']=tracts.tract_key.str.split('|').str[0]
    tract_areas=tracts.set_index('tract_key').geometry.area
    path,column=PLANS[cycle][chamber]
    districts=gpd.read_file(path)[[column,'geometry']].rename(columns={column:'district'}).to_crs(5070)
    districts['district']=pd.to_numeric(districts.district).astype(int)
    pieces=gpd.overlay(
        tracts[['tract_key','county_fips','total_population','geometry']],
        districts,how='intersection',keep_geom_type=False)
    pieces['population']=pieces.total_population*pieces.geometry.area/pieces.tract_key.map(tract_areas)
    weights=pieces.groupby(['county_fips','district'],as_index=False).population.sum()
    weights['allocation_weight']=weights.population/weights.groupby('county_fips').population.transform('sum')
    county_shape=RAW/'al_gen_22_prec'/'al_gen_22_st_prec.shp'
    counties=gpd.read_file(county_shape,ignore_geometry=True)[['County','COUNTYFP']].drop_duplicates()
    counties['county_key']=counties.County.map(normalize_name)
    return weights.merge(
        counties[['county_key','COUNTYFP']],left_on='county_fips',right_on='COUNTYFP',
        validate='many_to_one')[['county_key','district','allocation_weight']]

def census_api_key()->str:
    token=ROOT/'token.env'
    if token.exists():
        for line in token.read_text(encoding='utf-8').splitlines():
            if line.startswith('CENSUS_API_KEY='):return line.split('=',1)[1].strip()
    return ''

def ensure_2000_sources() -> tuple[Path,Path]:
    CENSUS.mkdir(parents=True,exist_ok=True); csv=CENSUS/'alabama_tract_sf3.csv'; shp=CENSUS/'tracts'/'tr01_d00.shp'
    if not csv.exists():
        bulk=CENSUS/'all_Alabama2f32000'
        if (bulk/'algeo_uf3.zip').exists():
            parse_2000_sf3_bulk(bulk).to_csv(csv,index=False)
        else:
            variables=['NAME','P001001','P007003','P037001','P037015','P037016','P037017','P037018',
                       'P037032','P037033','P037034','P037035','P148A001','P148A008','P148A009','P148A016','P148A017']
            frames=[]
            for start in range(1,len(variables),2):
                requested=['NAME',*variables[start:start+2]];params={'get':','.join(requested),'for':'tract:*','in':'state:01 county:*'}
                if census_api_key():params['key']=census_api_key()
                response=requests.get(SF3_URL,params=params,timeout=120);response.raise_for_status()
                rows=response.json();frame=pd.DataFrame(rows[1:],columns=rows[0]);frames.append(frame)
            data=frames[0]
            for frame in frames[1:]:data=data.merge(frame.drop(columns='NAME'),on=['state','county','tract'],validate='one_to_one')
            data.to_csv(csv,index=False)
    if not shp.exists():
        response=requests.get(TRACT_URL,timeout=120);response.raise_for_status();shp.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(BytesIO(response.content)) as archive: archive.extractall(shp.parent)
    return csv,shp

def _zip_rows(path:Path):
    with zipfile.ZipFile(path) as archive:
        name=archive.namelist()[0]
        with archive.open(name) as stream:
            for raw in stream:yield next(csv_module.reader([raw.decode('latin1')]))

def parse_2000_sf3_bulk(bulk:Path)->pd.DataFrame:
    """Read only the three SF3 sequences needed for the tract feature mart."""
    geography=[]
    with zipfile.ZipFile(bulk/'algeo_uf3.zip') as archive:
        with archive.open(archive.namelist()[0]) as stream:
            for raw in stream:
                line=raw.decode('latin1')
                if line[8:11]=='140' and line[29:31]=='01':
                    geography.append({'LOGRECNO':line[18:25],'NAME':line[192:282].strip(),
                                      'state':line[29:31],'county':line[31:34],'tract':line[55:61]})
    geo=pd.DataFrame(geography)
    selections={
      1:{'P001001':5,'P007003':26},
      3:{'P037001':211,'P037015':225,'P037016':226,'P037017':227,'P037018':228,
         'P037032':242,'P037033':243,'P037034':244,'P037035':245},
      13:{'P148A001':5,'P148A008':12,'P148A009':13,'P148A016':20,'P148A017':21}}
    result=geo
    for sequence,columns in selections.items():
        records=[]
        for row in _zip_rows(bulk/f'al{sequence:05d}_uf3.zip'):
            records.append({'LOGRECNO':row[4],**{name:row[position] for name,position in columns.items()}})
        result=result.merge(pd.DataFrame(records),on='LOGRECNO',how='left',validate='one_to_one')
    if result[list(sum((list(value) for value in selections.values()),[]))].isna().any().any():
        raise ValueError('SF3 bulk sequences did not cover every Alabama tract geography record')
    return result

def tract_demographics_2000() -> gpd.GeoDataFrame:
    csv,shp=ensure_2000_sources();d=pd.read_csv(csv,dtype={'state':str,'county':str,'tract':str})
    numeric=[c for c in d if c.startswith('P')]
    d[numeric]=d[numeric].apply(pd.to_numeric,errors='coerce')
    d['total_population']=d.P001001;d['white_population']=d.P007003;d['age25_population']=d.P037001
    d['college_population']=d[['P037015','P037016','P037017','P037018','P037032','P037033','P037034','P037035']].sum(axis=1)
    d['white_age25_population']=d.P148A001
    d['white_college_population']=d[['P148A008','P148A009','P148A016','P148A017']].sum(axis=1)
    d['tract_key']=d.county.str.zfill(3)+'|'+d.tract.str.zfill(6)
    g=gpd.read_file(shp)
    if g.crs is None:g=g.set_crs(4269)
    county_col=next(c for c in ['COUNTY','COUNTYFP00','CO'] if c in g)
    tract_col=next(c for c in ['TRACT','TRACTCE00','TRACTBASE'] if c in g)
    # The legacy TIGER shapefile suppresses the implied two-decimal tract
    # suffix for whole-number tracts (``0113`` means Census code ``011300``).
    tract_code=g[tract_col].astype(str).str.replace('.0','',regex=False).str.strip().str.ljust(6,'0')
    g['tract_key']=g[county_col].astype(str).str.zfill(3)+'|'+tract_code
    cols=['tract_key','total_population','white_population','age25_population','college_population','white_age25_population','white_college_population']
    return g[['tract_key','geometry']].dissolve('tract_key',as_index=False).merge(d[cols],on='tract_key',validate='one_to_one')

def allocate_demographics(tracts:gpd.GeoDataFrame,cycle:int,vintage:int)->pd.DataFrame:
    tracts=tracts.to_crs(5070);source=float(tracts.total_population.sum());frames=[]
    for chamber,(path,column) in PLANS[cycle].items():
        districts=gpd.read_file(path)[[column,'geometry']].rename(columns={column:'district'}).to_crs(5070)
        districts['district']=pd.to_numeric(districts.district).astype(int)
        x=gpd.overlay(tracts,districts,how='intersection',keep_geom_type=False)
        areas=tracts.set_index('tract_key').geometry.area;x['share']=x.geometry.area/x.tract_key.map(areas)
        counts=['total_population','white_population','age25_population','college_population','white_age25_population','white_college_population']
        for col in counts:x[col]*=x.share
        out=x.groupby('district',as_index=False)[counts].sum();out['nonwhite_share']=1-out.white_population/out.total_population
        out['college_share']=out.college_population/out.age25_population;out['white_college_share']=out.white_college_population/out.white_age25_population
        out['source_population_coverage']=out.total_population.sum()/source;out['allocation_method']=f'{vintage}_sf3_tract_area_interpolation_provisional'
        out['census_vintage']=vintage;out['cycle']=cycle;out['chamber']=chamber;frames.append(out)
    return pd.concat(frames,ignore_index=True)

def legislative_weights(cycle:int)->pd.DataFrame:
    with sqlite3.connect(DB) as c:
        d=pd.read_sql_query("""select year as cycle,county_key,precinct_key,office,district,sum(votes) activity
          from vote_observations where source='alabama_sos' and year=? and office in ('State House','State Senate')
          and district is not null group by year,county_key,precinct_key,office,district""",c,params=(cycle,))
    d['chamber']=d.office.map({'State House':'house','State Senate':'senate'});d['total']=d.groupby(['county_key','precinct_key','chamber']).activity.transform('sum')
    d=d[d.total.gt(0)].copy();d['allocation_weight']=d.activity/d.total;d['allocation_method']='legislative_activity_provisional'
    return d[['cycle','chamber','county_key','precinct_key','district','allocation_weight','allocation_method']]

def _pres1996()->pd.DataFrame:
    path=RAW/'96g-prec'/'96g-prec'/'1996 Compiled Results.xls';rows=[]
    for county,data in _workbook_sheets(path.read_bytes()).items():
        if county.startswith('Summary') or len(data)<3:continue
        header=[str(x).upper() for x in data[1]]
        try: dem=next(i for i,x in enumerate(header) if 'BILL CLINTON' in x);rep=next(i for i,x in enumerate(header) if 'BOB DOLE' in x)
        except StopIteration:continue
        for row in data[2:]:
            if len(row)<=max(dem,rep):continue
            dv=pd.to_numeric(row[dem],errors='coerce');rv=pd.to_numeric(row[rep],errors='coerce');name=str(row[3]).strip() if len(row)>3 else ''
            if name and not (pd.isna(dv) and pd.isna(rv)) and 'TOTAL' not in name.upper():
                rows.append([1996,county.upper(),name.upper(),'Bill Clinton','Bob Dole',
                             0 if pd.isna(dv) else dv,0 if pd.isna(rv) else rv,path.name])
    return pd.DataFrame(rows,columns=['cycle','county_key','precinct_key','dem_candidate','rep_candidate','dem_votes','rep_votes','source_file'])

def _pres2000()->pd.DataFrame:
    candidates=[]
    for path in RAW.glob('2000gen*/**/*.xls'):
        for _,data in _workbook_sheets(path.read_bytes()).items():
            if len(data)<3:continue
            found={}
            for header_row,row in enumerate(data[:20]):
                for column,value in enumerate(row):
                    label=str(value).upper()
                    if ('GORE' in label or 'LIEBERMAN' in label) and 'dem' not in found:found['dem']=(header_row,column)
                    if ('BUSH' in label or 'CHENEY' in label) and 'rep' not in found:found['rep']=(header_row,column)
            if set(found)!={'dem','rep'}:continue
            dem=found['dem'][1];rep=found['rep'][1];rows=[]
            for row in data[max(found['dem'][0],found['rep'][0])+1:]:
                if len(row)<=max(dem,rep):continue
                dv=pd.to_numeric(row[dem],errors='coerce');rv=pd.to_numeric(row[rep],errors='coerce');name=str(row[0]).strip()
                if (name and not (pd.isna(dv) and pd.isna(rv)) and
                    not re.search(r'TOTAL|CALCULATED|REPORTED',name,re.I)):
                    rows.append((name.upper(),0 if pd.isna(dv) else dv,0 if pd.isna(rv) else rv))
            if rows:
                county=re.sub(r'[-_ ]?2000GENP.*$','',path.stem,flags=re.I).upper();candidates.append((county,sum(x[1]+x[2] for x in rows),path,rows))
    selected={}
    for item in candidates:
        if item[0] not in selected or item[1]>selected[item[0]][1]:selected[item[0]]=item
    output=[]
    for county,(_,_,path,rows) in selected.items():
        for name,dv,rv in rows:output.append([2000,county,name,'Al Gore','George W. Bush',dv,rv,str(path.relative_to(ROOT))])
    return pd.DataFrame(output,columns=['cycle','county_key','precinct_key','dem_candidate','rep_candidate','dem_votes','rep_votes','source_file'])

def _pres2004()->pd.DataFrame:
    with sqlite3.connect(DB) as c:
        d=pd.read_sql_query("""select county_key,precinct_key,party_norm,sum(votes) votes from vote_observations
          where source='alabama_sos' and year=2004 and office='President' and party_norm in ('D','R')
          group by county_key,precinct_key,party_norm""",c)
    d=d.pivot_table(index=['county_key','precinct_key'],columns='party_norm',values='votes',fill_value=0).reset_index()
    d=d.rename(columns={'D':'dem_votes','R':'rep_votes'});d['county_key']=d.county_key.str.replace(r'\s*-\s*GEN04$','',regex=True,case=False)
    d['cycle']=2004;d['dem_candidate']='John Kerry';d['rep_candidate']='George W. Bush';d['source_file']='warehouse:alabama_sos_2004'
    return d[['cycle','county_key','precinct_key','dem_candidate','rep_candidate','dem_votes','rep_votes','source_file']]

def presidential(cycle:int,raw:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    weights=_prepare_weights(legislative_weights(cycle),cycle);out,matches=allocate_to_districts(raw,weights,PRIOR[cycle])
    rename={f'pres_{PRIOR[cycle]}_dem_votes':'dem_votes',f'pres_{PRIOR[cycle]}_rep_votes':'rep_votes',f'pres_{PRIOR[cycle]}_two_party_votes':'two_party_votes',f'pres_{PRIOR[cycle]}_dem_margin':'dem_margin',f'pres_{PRIOR[cycle]}_fallback_share':'fallback_share',f'pres_{PRIOR[cycle]}_source_complete':'source_complete'}
    out=out.rename(columns=rename);out['cycle']=cycle;out['source_year']=PRIOR[cycle];out['allocation_method']='precinct_match_then_legislative_activity_fallback'
    return out,matches

def candidates()->pd.DataFrame:
    with sqlite3.connect(DB) as c:return pd.read_sql_query("""select canonical_candidate_id,year cycle,chamber,district,canonical_party party,canonical_name candidate
      from canonical_candidates where year in (1998,2002,2006) and canonical_party in ('D','R')""",c)

def incumbency(cand:pd.DataFrame)->pd.DataFrame:
    def surname(value:str)->str:
        text=str(value);return canonical_person(text.split(',',1)[0] if ',' in text else text).split()[-1]
    shor=pd.read_csv(SHOR,sep='\t');shor=shor[shor.st.eq('AL')].copy();shor['surname']=shor.name.map(surname)
    rows=[]
    for row in cand.itertuples(index=False):
        year=row.cycle-1;flag=f'{row.chamber}{year}';district_col=('h' if row.chamber=='house' else 's')+f'district{year}'
        candidate_surname=surname(row.candidate)
        pool=shor[shor[flag].notna()&shor.surname.eq(candidate_surname)] if flag in shor else shor.iloc[0:0]
        exact=pool[pd.to_numeric(pool[district_col],errors='coerce').eq(row.district)] if district_col in pool else pool.iloc[0:0]
        hit=exact if len(exact)==1 else pool if len(pool)==1 else pool.iloc[0:0]
        supported=len(hit)==1;party_ok=(not supported) or hit.iloc[0].party==row.party
        rows.append({**row._asdict(),'incumbent':int(supported and party_ok),'prior_candidate_name':hit.iloc[0]['name'] if supported else None,'prior_party':hit.iloc[0].party if supported else None,
          'match_method':'shor_pre_election_roster_district_or_unique_surname','match_confidence':'high' if len(exact)==1 and party_ok else 'medium' if supported and party_ok else 'low','review_status':'supported' if supported and party_ok else 'unknown'})
    return pd.DataFrame(rows)

def finance(cand:pd.DataFrame)->pd.DataFrame:
    source=pd.read_csv(WAR/'candidate_resource_harmonized.csv');cols=['canonical_candidate_id','total_resources_raised','resource_observation_status','source_name']
    out=cand.merge(source[cols],on='canonical_candidate_id',how='left',validate='one_to_one').rename(columns={'resource_observation_status':'observation_status'})
    out['coverage_note']='DIME recipient totals; missing is unknown, never assumed zero';return out

def context(dem,pres,inc,fin):
    base=dem[['cycle','chamber','district','census_vintage','nonwhite_share','college_share','white_college_share','allocation_method']].rename(columns={'allocation_method':'demographics_method'})
    ri=inc.pivot_table(index=['cycle','chamber','district'],columns='party',values='incumbent',aggfunc='max',fill_value=0).reset_index().rename(columns={'D':'dem_incumbent','R':'rep_incumbent'})
    known=inc.assign(known=inc.review_status.eq('supported')).groupby(['cycle','chamber','district']).known.all().reset_index(name='incumbency_complete')
    rf=pd.read_csv(WAR/'race_resource_features_harmonized.csv')[['cycle','chamber','district','finance_complete','log_resource_ratio_d_to_r']]
    p=pres[['cycle','chamber','district','source_year','dem_margin','fallback_share','source_complete']].rename(columns={'source_year':'prior_presidential_year','dem_margin':'prior_pres_dem_margin','fallback_share':'prior_pres_fallback_share','source_complete':'prior_pres_source_complete'})
    out=base.merge(ri,on=['cycle','chamber','district'],how='left').merge(known,on=['cycle','chamber','district'],how='left').merge(rf,on=['cycle','chamber','district'],how='left').merge(p,on=['cycle','chamber','district'],how='left')
    out['prior_presidential_year']=out.apply(lambda row: PRIOR[int(row.cycle)] if pd.isna(row.prior_presidential_year) else int(row.prior_presidential_year),axis=1)
    out[['dem_incumbent','rep_incumbent','incumbency_complete','finance_complete','prior_pres_source_complete']]=out[['dem_incumbent','rep_incumbent','incumbency_complete','finance_complete','prior_pres_source_complete']].fillna(False)
    out['readiness_status']=np.where(out.prior_pres_source_complete&out.nonwhite_share.notna(),'experimental_complete_context','experimental_source_gap')
    return out

def main():
    d1990=tract_demographics_1990()
    try:
        d2000=tract_demographics_2000();vintage=2000
    except Exception as error:
        print(f'WARNING: 2000 SF3 unavailable ({error}); using explicitly provisional 1990 SF3 interpolation')
        d2000=d1990;vintage=1990
    dem=pd.concat([allocate_demographics(d1990,1998,1990),allocate_demographics(d2000,2002,vintage),allocate_demographics(d2000,2006,vintage)],ignore_index=True)
    raw=pd.concat([_pres1996(),_pres2000(),_pres2004()],ignore_index=True);pres=[];matches=[]
    for cycle in CYCLES:
        p,m=presidential(cycle,raw[raw.cycle.eq(PRIOR[cycle])]);pres.append(p);m['target_cycle']=cycle;matches.append(m)
    pres=pd.concat(pres,ignore_index=True);cand=candidates();inc=incumbency(cand);fin=finance(cand);ctx=context(dem,pres,inc,fin)
    DEM.mkdir(parents=True,exist_ok=True);PRES.mkdir(parents=True,exist_ok=True)
    dem.to_csv(DEM/'1998_2006_district_demographics.csv',index=False);raw.to_csv(PRES/'1996_2004_historical_president_precinct.csv',index=False);pres.to_csv(PRES/'1998_2006_district_presidential_features.csv',index=False);pd.concat(matches).to_csv(PRES/'1998_2006_presidential_precinct_matches.csv',index=False)
    inc.to_csv(ELECT/'1998_2006_candidate_incumbency.csv',index=False);fin.to_csv(WAR/'1998_2006_candidate_finance_coverage.csv',index=False);ctx.to_csv(ELECT/'1998_2006_cmo_context_features.csv',index=False)
    with closing(connect()) as con:
        initialize(con);con.executescript(SCHEMA.read_text());run=begin_run(con,'historical_1998_2006_context',{'cycles':CYCLES})
        con.execute('delete from mart_historical_cmo_context_feature_v2 where cycle in (1998,2002,2006)');w=ctx.copy()
        for col in ['dem_incumbent','rep_incumbent','incumbency_complete','finance_complete','prior_pres_source_complete']:w[col]=w[col].astype(int)
        w.to_sql('mart_historical_cmo_context_feature_v2',con,if_exists='append',index=False);register_table(con,'mart_historical_cmo_context_feature_v2','mart','scripts/build_1998_2006_context_features.py','cycle/chamber/district','Census SF3; official election returns; Shor-McCarty; DIME','replace','Historical context for experimental CMO cycles')
        finish_run(con,run,{'rows':len(ctx),'pres_complete':int(ctx.prior_pres_source_complete.sum()),'incumbency_supported':int(inc.incumbent.sum()),'finance_observed':int(fin.total_resources_raised.notna().sum())});con.commit()
    print(ctx.groupby(['cycle','chamber']).agg(districts=('district','size'),pres_complete=('prior_pres_source_complete','sum'),incumbents=('dem_incumbent','sum'),finance_complete=('finance_complete','sum')).to_string())

if __name__=='__main__':main()
