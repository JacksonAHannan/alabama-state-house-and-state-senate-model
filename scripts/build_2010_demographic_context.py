"""Build a provisional demographic layer for the 2010 election.

The election used the same enacted 2002-2010 districts represented in the
validated 2006 SF3 context.  Until the 2006-2010 ACS SLD archive can be pulled,
we reuse the locally warehoused 2000 SF3 district estimates and label their age
and construction method explicitly.
"""
from pathlib import Path
import csv
import re
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data'/'processed'/'demographics'/'1998_2006_district_demographics.csv'
OUT=ROOT/'data'/'processed'/'demographics'/'2010_district_demographics.csv'
RAW=ROOT/'data'/'raw'/'census'/'Alabama_All_Geographies_Not_Tracts_Block_Groups'

def parse_acs_2010(raw:Path)->pd.DataFrame:
    """Parse the three required detailed tables from sequence files 13/40."""
    geography=[]
    with (raw/'g20105al.txt').open(encoding='latin1') as stream:
        for line in stream:
            summary_level=line[8:11]
            if summary_level not in {'610','620'}:continue
            match=re.search(r'District\s+(\d+)',line[218:318])
            if not match:continue
            geography.append({'LOGRECNO':line[13:20],
                'chamber':'senate' if summary_level=='610' else 'house',
                'district':int(match.group(1)),'NAME':line[218:318].strip()})
    geo=pd.DataFrame(geography)
    selections={
        13:{'total_population':37,'white_nonhispanic_population':39},
        40:{'age25_population':89,
            'college_population':list(range(103,107))+list(range(120,124)),
            'white_age25_population':201,
            'white_college_population':[206,211]}}
    result=geo
    for sequence,fields in selections.items():
        rows=[]
        path=raw/f'e20105al{sequence:04d}000.txt'
        with path.open(encoding='latin1',newline='') as stream:
            for values in csv.reader(stream):
                row={'LOGRECNO':values[5]}
                for name,index in fields.items():
                    indexes=index if isinstance(index,list) else [index]
                    row[name]=sum(float(values[i]) if values[i] not in ('','.') else 0 for i in indexes)
                rows.append(row)
        result=result.merge(pd.DataFrame(rows),on='LOGRECNO',how='left',validate='one_to_one')
    result['nonwhite_share']=1-result.white_nonhispanic_population/result.total_population
    result['college_share']=result.college_population/result.age25_population
    result['white_college_share']=result.white_college_population/result.white_age25_population
    result['cycle']=2010;result['census_vintage']=2010
    result['demographic_reference_year']=2010;result['demographic_age_years']=0
    result['source_population_coverage']=1.0
    result['allocation_method']='2006_2010_acs5_direct_sld'
    expected={'house':105,'senate':35};actual=result.groupby('chamber').district.nunique().to_dict()
    if actual!=expected:raise ValueError(f'Unexpected 2010 ACS district coverage: {actual}')
    if result[['nonwhite_share','college_share','white_college_share']].isna().any().any():
        raise ValueError('Missing 2010 ACS demographic estimates')
    return result

def build(source:pd.DataFrame)->pd.DataFrame:
    result=source[source.cycle.eq(2006)].copy()
    result['cycle']=2010
    result['demographic_reference_year']=2000
    result['demographic_age_years']=10
    result['allocation_method']='2000_sf3_same_2002_2010_plan_provisional'
    if result.duplicated(['cycle','chamber','district']).any():
        raise ValueError('Duplicate 2010 district demographic rows')
    expected={'house':105,'senate':35}
    actual=result.groupby('chamber').district.nunique().to_dict()
    if actual!=expected:raise ValueError(f'Unexpected 2010 district coverage: {actual}')
    return result

def main()->None:
    result=parse_acs_2010(RAW) if (RAW/'g20105al.txt').exists() else build(pd.read_csv(SOURCE))
    result.to_csv(OUT,index=False)
    print(result.groupby('chamber').agg(rows=('district','size'),min_nonwhite=('nonwhite_share','min'),
          max_nonwhite=('nonwhite_share','max'),min_white_college=('white_college_share','min'),
          max_white_college=('white_college_share','max')).to_string())

if __name__=='__main__':main()
