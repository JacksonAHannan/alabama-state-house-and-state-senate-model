"""Poststratify the Catalist/YouGov environment into 2026 districts."""
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd

from build_alabama_race_ei import block_race

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/census';MAPS=ROOT/'data/raw/alabama_elections_and_geography'
POLLING=ROOT/'data/processed/polling';DEM=ROOT/'data/processed/demographics';WAR=ROOT/'data/processed/war'
SIX=[f'{r}_{e}' for r in ['white_nh','black','other'] for e in ['noncollege','college']]
CORE=['white_nh_noncollege','white_nh_college','black_noncollege','black_college','other']

def block_cells():
    cells=pd.read_csv(DEM/'acs_block_group_joint_race_education_modeled.csv',dtype={'block_group_geoid':str})
    cells=cells[cells.acs_vintage==2024][['block_group_geoid',*SIX]]
    blocks=block_race(2020)[['blockid','population']];blocks['block_group_geoid']=blocks.blockid.str[:12]
    blocks['bg_vap']=blocks.groupby('block_group_geoid').population.transform('sum')
    blocks['bg_n']=blocks.groupby('block_group_geoid').blockid.transform('size')
    blocks['weight']=np.where(blocks.bg_vap>0,blocks.population/blocks.bg_vap,1/blocks.bg_n)
    blocks=blocks.merge(cells,on='block_group_geoid',validate='many_to_one')
    for c in SIX:blocks[c]*=blocks.weight
    blocks['other']=blocks.other_noncollege+blocks.other_college
    return blocks

def district_links(chamber):
    field='SLDLST' if chamber=='house' else 'SLDUST';folder='tl_2025_01_sldl' if chamber=='house' else 'tl_2025_01_sldu'
    shp=MAPS/folder/f'{folder}.shp'
    districts=gpd.read_file(shp)[[field,'geometry']].rename(columns={field:'district'}).to_crs(5070)
    blocks=gpd.read_file(f"zip://{(RAW/'tl_2020_01_tabblock20.zip').resolve()}")
    blocks=blocks[['GEOID20','geometry']].rename(columns={'GEOID20':'blockid'}).to_crs(5070)
    points=blocks.set_geometry(blocks.geometry.representative_point())
    links=gpd.sjoin(points,districts,predicate='within',how='inner')
    if links.blockid.duplicated().any():
        raise ValueError(f'Overlapping {chamber} districts assigned a block twice')
    links['district']=pd.to_numeric(links.district)
    return links[['blockid','district']]

def main():
    blocks=block_cells();outputs=[]
    for chamber in ['house','senate']:
        joined=blocks.merge(district_links(chamber),on='blockid',validate='one_to_one')
        agg=joined.groupby('district',as_index=False)[CORE].sum();agg['chamber']=chamber;agg['cycle']=2026
        outputs.append(agg)
    district_cells=pd.concat(outputs,ignore_index=True)
    district_cells.to_csv(DEM/'2026_district_joint_race_education_cells.csv',index=False)
    projection=pd.read_csv(POLLING/'2026_alabama_catalist_yougov_cell_projection.csv').set_index('cell')
    baseline=pd.read_csv(ROOT/'data/processed/presidential/2026_district_presidential_features.csv')
    rows=[]
    for row in district_cells.itertuples(index=False):
        populations=np.array([getattr(row,c) for c in CORE]);turnout=projection.loc[CORE].projected_turnout.to_numpy()
        voters=populations*turnout
        support24=projection.loc[CORE].projected_alabama_2024_support.to_numpy()
        support26=projection.loc[CORE].projected_alabama_2026_support.to_numpy()
        share24=float(voters@support24/voters.sum());share26=float(voters@support26/voters.sum())
        rows.append({'cycle':2026,'chamber':row.chamber,'district':row.district,
                     'demographic_model_2024_margin':200*share24-100,
                     'demographic_model_2026_margin':200*share26-100,
                     'demographic_swing_2024_2026':200*(share26-share24)})
    forecast=pd.DataFrame(rows).merge(baseline[['cycle','chamber','district','pres_2024_dem_margin']],
                                      on=['cycle','chamber','district'],validate='one_to_one')
    forecast['demographic_poll_adjusted_margin']=forecast.pres_2024_dem_margin+forecast.demographic_swing_2024_2026
    forecast['status']='catalist_yougov_demographic_transfer_gate_passed'
    forecast.to_csv(WAR/'2026_demographic_poll_adjusted_baseline.csv',index=False)
    print(forecast.groupby('chamber').agg(districts=('district','size'),mean_swing=('demographic_swing_2024_2026','mean'),
          min_swing=('demographic_swing_2024_2026','min'),max_swing=('demographic_swing_2024_2026','max'),
          mean_adjusted=('demographic_poll_adjusted_margin','mean')).to_string())

if __name__=='__main__':main()
