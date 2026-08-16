"""Build independent CES validation estimates for Alabama joint cells."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/ces/dataverse_files/cumulative_2006-2025.dta'
OUT=ROOT/'data/processed/polling'

def main():
    columns=['year','state','weight','voted_rep_party','race_h','educ']
    frame=pd.read_stata(RAW,columns=columns,convert_categoricals=True)
    frame=frame[(frame.year.isin([2018,2020]))&(frame.state=='Alabama')
                &frame.voted_rep_party.isin(['Democratic','Republican'])].copy()
    frame['race']=np.where(frame.race_h=='White','white_nh',np.where(frame.race_h=='Black','black','other'))
    frame['education']=np.where(frame.educ.isin(['4-Year','Post-Grad']),'college','noncollege')
    frame['cell']=frame.race+'_'+frame.education
    frame['dem']=(frame.voted_rep_party=='Democratic').astype(float)
    rows=[]
    for (year,cell),group in frame.groupby(['year','cell']):
        weights=group.weight
        rows.append({'cycle':year,'cell':cell,'unweighted_n':len(group),
                     'effective_n':weights.sum()**2/weights.pow(2).sum(),
                     'ces_dem_two_party_share':np.average(group.dem,weights=weights)})
    result=pd.DataFrame(rows)
    result.to_csv(OUT/'ces_alabama_joint_race_education_validation.csv',index=False)
    estimates=pd.read_csv(OUT/'alabama_joint_race_education_ei_estimates.csv')
    comparison=estimates.merge(result,on=['cycle','cell'],validate='one_to_one')
    comparison['ei_minus_ces']=comparison.estimated_dem_support-comparison.ces_dem_two_party_share
    comparison['external_validation_pass']=comparison.ei_minus_ces.abs()<=.15
    comparison.to_csv(OUT/'alabama_joint_ei_ces_comparison.csv',index=False)
    print(comparison[['cycle','cell','estimated_dem_support','ces_dem_two_party_share','effective_n',
                      'ei_minus_ces','external_validation_pass']].to_string(index=False))

if __name__=='__main__':main()
