"""Translate Catalist and YouGov into a 2026 Alabama demographic environment."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
POLLING=ROOT/'data/processed/polling'
DEMOGRAPHICS=ROOT/'data/processed/demographics'
CORE=['white_nh_noncollege','white_nh_college','black_noncollege','black_college','other']
CATALIST={'white_nh_noncollege':'White Non-College','white_nh_college':'White College',
          'black_noncollege':'Black Non-College','black_college':'Black College'}

def logit(x):
    x=np.clip(np.asarray(x,dtype=float),1e-6,1-1e-6);return np.log(x/(1-x))
def expit(x): return 1/(1+np.exp(-np.asarray(x,dtype=float)))

def weighted_poll_group(snapshot,cycle,groups):
    selected=snapshot[(snapshot.cycle==cycle)&snapshot.group.isin(groups)]
    weights=selected.mean_unweighted_base
    return float(np.average(selected.dem_two_party_share,weights=weights))

def poll_movements():
    p=pd.read_csv(POLLING/'yougov_generic_ballot_election_snapshots.csv')
    values={2024:{
            'overall':weighted_poll_group(p,cycle,['all']),
            'white':weighted_poll_group(p,cycle,['white']),
            'black':weighted_poll_group(p,cycle,['black']),
            'college':weighted_poll_group(p,cycle,['college_grad','postgrad']),
            'noncollege':weighted_poll_group(p,cycle,['hs_or_less','some_college']),
        } for cycle in [2024]}
    # Current levels use the Silver B-or-better quality-gated VoteHub environment. The
    # topline pools eight eligible pollsters; race shapes pool three, while the
    # compatible education split is supplied by A- rated Marist.
    topline=pd.read_csv(POLLING/'votehub_silver_bplus_topline_environment.csv').iloc[0]
    environment=pd.read_csv(POLLING/'votehub_silver_bplus_demographic_environment.csv')
    lookup=environment.set_index(['dimension','group']).projected_dem_two_party_share.to_dict()
    values[2026]={
        'overall':topline.dem_two_party_share,
        'white':lookup[('race','white')],
        'black':lookup[('race','black')],
        'college':lookup[('education','marist_college_grad')],
        'noncollege':lookup[('education','marist_not_college_grad')],
    }
    return {group:float(logit(values[2026][group])-logit(values[2024][group])) for group in values[2024]},values

def catalist_support(year,election):
    m=pd.read_csv(POLLING/'catalist_national_demographic_master.csv')
    m=m[(m.year==year)&(m.election_type==election)&(m.metric=='dem_two_party_share_pct')]
    lookup=m.set_index('group').value.to_dict()
    result={cell:lookup[group]/100 for cell,group in CATALIST.items()}
    result['other']=np.mean([lookup['Other Non-College'],lookup['Other College']])/100
    return result

def main():
    movements,poll_values=poll_movements()
    national_2024=catalist_support(2024,'us_house')
    national_2026={}
    for cell in CORE:
        if cell=='other': delta=movements['overall']
        else:
            race='white' if cell.startswith('white') else 'black'
            education='noncollege' if cell.endswith('noncollege') else 'college'
            # Add race and education deviations while subtracting the common
            # national movement once to avoid double-counting it.
            delta=movements[race]+movements[education]-movements['overall']
        national_2026[cell]=float(expit(logit(national_2024[cell])+delta))

    estimates=pd.read_csv(POLLING/'alabama_core_race_education_ei_estimates.csv')
    offsets=[]
    for cycle in [2018,2020]:
        national=catalist_support(cycle,'us_house' if cycle==2018 else 'president')
        for row in estimates[estimates.cycle==cycle].itertuples():
            offsets.append({'cycle':cycle,'cell':row.cell,
                            'alabama_logit_offset':float(logit(row.estimated_dem_support)-logit(national[row.cell]))})
    offsets=pd.DataFrame(offsets)
    pooled=offsets.groupby('cell').alabama_logit_offset.agg(['mean','min','max']).reset_index()

    # Forward check: can the 2018 offset recover the independently estimated
    # 2020 Alabama preference when applied to Catalist 2020?
    actual20=estimates[estimates.cycle==2020].set_index('cell').estimated_dem_support
    national20=catalist_support(2020,'president')
    offset18=offsets[offsets.cycle==2018].set_index('cell').alabama_logit_offset
    backtest=[]
    for cell in CORE:
        predicted=float(expit(logit(national20[cell])+offset18[cell]))
        backtest.append({'target_cycle':2020,'cell':cell,'predicted_support':predicted,
                         'actual_ei_support':actual20[cell],'absolute_error_points':100*abs(predicted-actual20[cell])})
    backtest=pd.DataFrame(backtest)
    backtest.to_csv(POLLING/'catalist_alabama_offset_forward_check.csv',index=False)
    gate=bool(backtest[backtest.cell!='other'].absolute_error_points.mean()<=5
              and backtest[backtest.cell!='other'].absolute_error_points.max()<=10)

    turnout18=estimates[estimates.cycle==2018].set_index('cell').estimated_turnout
    rows=[]
    for row in pooled.itertuples():
        cell=row.cell;base=national_2026[cell]
        projected=float(expit(logit(base)+row.mean))
        alabama_2024=float(expit(logit(national_2024[cell])+row.mean))
        endpoints=[float(expit(logit(base)+row.min)),float(expit(logit(base)+row.max))]
        rows.append({'cycle':2026,'cell':cell,'catalist_2024_us_house_support':national_2024[cell],
                     'projected_national_2026_support':base,'pooled_alabama_logit_offset':row.mean,
                     'projected_alabama_2024_support':alabama_2024,
                     'projected_alabama_2026_support':projected,
                     'offset_endpoint_low':min(endpoints),'offset_endpoint_high':max(endpoints),
                     'projected_turnout':turnout18[cell],
                     'forward_offset_gate_passed':gate})
    projection=pd.DataFrame(rows)
    projection.to_csv(POLLING/'2026_alabama_catalist_yougov_cell_projection.csv',index=False)

    cells=pd.read_csv(DEMOGRAPHICS/'acs_block_group_joint_race_education_modeled.csv')
    cells=cells[cells.acs_vintage==2024]
    population={cell:cells[cell].sum() for cell in CORE if cell!='other'}
    population['other']=cells.other_noncollege.sum()+cells.other_college.sum()
    projection['adult25_population']=projection.cell.map(population)
    projection['projected_voters']=projection.adult25_population*projection.projected_turnout
    projection['projected_dem_votes_index']=projection.projected_voters*projection.projected_alabama_2026_support
    state_share=projection.projected_dem_votes_index.sum()/projection.projected_voters.sum()
    summary=pd.DataFrame([{'cycle':2026,'dem_two_party_share':state_share,
                          'dem_two_party_margin':200*state_share-100,
                          'yougov_2024_overall':poll_values[2024]['overall'],
                          'votehub_silver_bplus_2026_overall':poll_values[2026]['overall'],
                          'forward_offset_mean_ae':backtest[backtest.cell!='other'].absolute_error_points.mean(),
                          'forward_offset_max_ae':backtest[backtest.cell!='other'].absolute_error_points.max(),
                          'release_gate_passed':gate,
                          'environment_source':'Silver B or better VoteHub and supplemental toplines; quality-gated reviewed race and education crosstabs',
                          'status':'eligible_silver_bplus_demographic_environment' if gate else 'experimental'}])
    projection.to_csv(POLLING/'2026_alabama_catalist_yougov_cell_projection.csv',index=False)
    summary.to_csv(POLLING/'2026_alabama_demographic_environment.csv',index=False)
    pd.DataFrame([{'component':k,'hybrid_poll_logit_change_2024_2026':v} for k,v in movements.items()]).to_csv(
        POLLING/'yougov_2024_2026_demographic_movements.csv',index=False)
    print(backtest.to_string(index=False));print('\n',projection.to_string(index=False));print('\n',summary.to_string(index=False))

if __name__=='__main__':main()
