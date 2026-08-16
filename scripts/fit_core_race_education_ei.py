"""Fit the selected five-cell EI model with a pooled residual-race category."""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar

from build_alabama_race_ei import vest_statewide_returns

ROOT=Path(__file__).resolve().parents[1]
POLLING=ROOT/'data/processed/polling'
CELLS=['white_nh_noncollege','white_nh_college','black_noncollege','black_college','other']

def expit(x): return 1/(1+np.exp(-x))
def logit(x):
    x=np.clip(x,1e-6,1-1e-6);return np.log(x/(1-x))

def prepare_demographics(frame):
    frame=frame.copy()
    frame['other']=frame.other_noncollege+frame.other_college
    return frame

def priors(cycle,population,observed):
    election='us_house' if cycle==2018 else 'president'
    m=pd.read_csv(POLLING/'catalist_national_demographic_master.csv')
    m=m[(m.year==cycle)&(m.election_type==election)&(m.metric=='dem_two_party_share_pct')]
    lookup=m.set_index('group').value.to_dict()
    raw=np.array([lookup['White Non-College'],lookup['White College'],lookup['Black Non-College'],
                  lookup['Black College'],(lookup['Other Non-College']+lookup['Other College'])/2])/100
    shares=population.sum(axis=0);shares/=shares.sum()
    shift=minimize_scalar(lambda d:abs(shares@expit(logit(raw)+d)-observed),bounds=(-3,3),method='bounded').x
    return expit(logit(raw)+shift)

def fit(frame,prior,strength):
    x=frame[CELLS].to_numpy(float);d=frame.dem_votes.to_numpy(float);r=frame.rep_votes.to_numpy(float)
    common=np.clip((d.sum()+r.sum())/x.sum(),.05,.95);center=logit(np.array([common]))[0]
    def objective(params):
        t=expit(params[:5])
        # Residual-race preference is a calibrated nuisance parameter, fixed
        # to Catalist rather than weakly identified from Alabama aggregates.
        s=np.r_[expit(params[5:]),prior[4]]
        ed=np.clip(x@(t*s),1e-9,None);er=np.clip(x@(t*(1-s)),1e-9,None)
        likelihood=np.sum(ed-d*np.log(ed)+er-r*np.log(er))
        support=-strength*np.sum(prior[:4]*np.log(s[:4])+(1-prior[:4])*np.log(1-s[:4]))
        turnout=5000/2*np.sum((params[:5]-center)**2)
        return likelihood+support+turnout
    initial=np.r_[np.repeat(center,5),logit(prior[:4])]
    result=minimize(objective,initial,method='L-BFGS-B',options={'maxiter':2000})
    t=expit(result.x[:5]);s=np.r_[expit(result.x[5:]),prior[4]]
    ed=x@(t*s);er=x@(t*(1-s));valid=(d+r)>0
    mae=np.average(abs(ed[valid]/(ed[valid]+er[valid])-d[valid]/(d[valid]+r[valid])),weights=(d+r)[valid])
    return t,s,result.success,mae,(ed.sum()+er.sum()-d.sum()-r.sum())/(d.sum()+r.sum())

def main():
    demo=prepare_demographics(pd.read_csv(POLLING/'vest_precinct_joint_race_education.csv'))
    votes=vest_statewide_returns();rows=[]
    for cycle in [2018,2020]:
        dx=demo[(demo.cycle==cycle)&(demo.acs_vintage==2022)].sort_values('precinct_id')
        vx=votes[votes.cycle==cycle].reset_index(drop=True).reset_index(names='precinct_id')
        frame=vx.merge(dx[['precinct_id',*CELLS]],on='precinct_id',validate='one_to_one')
        observed=frame.dem_votes.sum()/(frame.dem_votes.sum()+frame.rep_votes.sum())
        prior=priors(cycle,frame[CELLS].to_numpy(float),observed)
        for strength in [25.,100.,400.,1600.]:
            turnout,support,success,mae,total_error=fit(frame,prior,strength)
            for i,cell in enumerate(CELLS):
                rows.append({'cycle':cycle,'acs_vintage':2022,'cell':cell,'prior_strength':strength,
                             'shifted_catalist_prior':prior[i],'estimated_dem_support':support[i],
                             'estimated_turnout':turnout[i],'optimizer_success':success,
                             'precinct_weighted_mae':mae,'vote_total_error_pct':total_error})
    result=pd.DataFrame(rows)
    ranges=result.groupby(['cycle','cell']).estimated_dem_support.agg(['min','max']).reset_index()
    ranges['prior_sensitivity_range']=ranges['max']-ranges['min']
    result=result.merge(ranges[['cycle','cell','prior_sensitivity_range']],on=['cycle','cell'])
    anchors=pd.read_csv(POLLING/'ei_homogeneous_precinct_validation.csv')
    anchors=anchors[(anchors.race=='black')&(anchors.composition_threshold==.95)].set_index('cycle').weighted_dem_share
    result['polarization_anchor']=result.cycle.map(anchors)
    result['anchor_difference']=np.where(result.cell.str.startswith('black'),
                                         result.estimated_dem_support-result.polarization_anchor,np.nan)
    result['cell_gate_passed']=(result.prior_sensitivity_range<.10)&result.optimizer_success
    black=result.cell.str.startswith('black')
    result.loc[black,'cell_gate_passed'] &= result.loc[black,'anchor_difference'].between(-.10,.05)
    result.to_csv(POLLING/'alabama_core_race_education_ei_sensitivity.csv',index=False)
    preferred=result[result.prior_strength==400].copy()
    six=pd.read_csv(POLLING/'alabama_joint_race_education_ei_estimates.csv')
    comparison=[]
    for cycle,g in preferred.groupby('cycle'):
        old=float(six[six.cycle==cycle].precinct_weighted_mae.iloc[0]);new=float(g.precinct_weighted_mae.iloc[0])
        comparison.append({'cycle':cycle,'six_cell_mae':old,'five_cell_mae':new,'mae_change':new-old,
                           'all_cell_gates_passed':bool(g.cell_gate_passed.all()),
                           'vote_total_error_pct':float(g.vote_total_error_pct.iloc[0]),
                           'model_gate_passed':bool(g.cell_gate_passed.all() and new<=old+.005
                                                    and abs(g.vote_total_error_pct.iloc[0])<.01)})
    preferred.to_csv(POLLING/'alabama_core_race_education_ei_estimates.csv',index=False)
    pd.DataFrame(comparison).to_csv(POLLING/'alabama_core_ei_model_gate.csv',index=False)
    print(preferred[['cycle','cell','estimated_dem_support','estimated_turnout','prior_sensitivity_range',
                     'anchor_difference','cell_gate_passed','precinct_weighted_mae']].to_string(index=False))
    print('\n',pd.DataFrame(comparison).to_string(index=False))

if __name__=='__main__':main()
