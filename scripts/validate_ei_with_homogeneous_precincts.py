"""Validate ecological estimates against racially homogeneous precincts."""
from pathlib import Path
import numpy as np
import pandas as pd

from build_alabama_race_ei import vest_statewide_returns

ROOT=Path(__file__).resolve().parents[1]
POLLING=ROOT/'data/processed/polling'

def main():
    demographics=pd.read_csv(POLLING/'vest_precinct_joint_race_education.csv')
    votes=vest_statewide_returns()
    rows=[]
    for cycle in [2018,2020]:
        demo=demographics[(demographics.cycle==cycle)&(demographics.acs_vintage==2022)].copy()
        election=votes[votes.cycle==cycle].reset_index(drop=True).reset_index(names='precinct_id')
        frame=election.merge(demo,on='precinct_id',validate='one_to_one')
        frame['black_share']=(frame.black_college+frame.black_noncollege)/frame.adult25_total
        frame['white_share']=(frame.white_nh_college+frame.white_nh_noncollege)/frame.adult25_total
        frame['votes']=frame.dem_votes+frame.rep_votes
        frame=frame[frame.votes>0].copy();frame['dem_share']=frame.dem_votes/frame.votes
        for race,column in [('black','black_share'),('white_nh','white_share')]:
            for threshold in [.80,.90,.95]:
                selected=frame[frame[column]>=threshold]
                rows.append({'cycle':cycle,'race':race,'composition_threshold':threshold,
                             'precincts':len(selected),'two_party_votes':selected.votes.sum(),
                             'weighted_dem_share':np.average(selected.dem_share,weights=selected.votes),
                             'median_precinct_dem_share':selected.dem_share.median(),
                             'validation_role':'primary_polarization_anchor'})
    result=pd.DataFrame(rows)
    result.to_csv(POLLING/'ei_homogeneous_precinct_validation.csv',index=False)
    estimates=pd.read_csv(POLLING/'alabama_joint_race_education_ei_estimates.csv')
    black=estimates[estimates.cell.str.startswith('black_')].copy()
    anchors=result[(result.race=='black')&(result.composition_threshold==.95)][['cycle','weighted_dem_share']]
    black=black.merge(anchors,on='cycle')
    black['difference_from_95pct_black_precincts']=black.estimated_dem_support-black.weighted_dem_share
    black['polarization_plausibility_pass']=black.difference_from_95pct_black_precincts.between(-.10,.05)
    black.to_csv(POLLING/'ei_black_polarization_validation.csv',index=False)
    print(result.to_string(index=False));print('\nBlack-cell comparison\n',black[[
        'cycle','cell','estimated_dem_support','weighted_dem_share',
        'difference_from_95pct_black_precincts','polarization_plausibility_pass']].to_string(index=False))

if __name__=='__main__':main()
