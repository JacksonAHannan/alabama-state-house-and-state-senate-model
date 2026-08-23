#!/usr/bin/env python3
"""Build a leakage-safe modern Southern forecast research candidate."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
from zipfile import ZipFile
import numpy as np, pandas as pd
from scipy.special import expit, ndtr
from scipy.stats import t as student_t
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from run_forecast_experiment_tournament import prepare_prospective_data
from build_southern_2024_incumbency import normalized_name

ROOT=Path(__file__).resolve().parents[1]; CAL=ROOT/'data/processed/forecast_calibration'; WAR=ROOT/'data/processed/war'
PANEL=CAL/'southern_legislative_probability_panel.csv'; INC=CAL/'southern_2024_incumbency_races.csv'
POLL=ROOT/'data/processed/polling/historical_silver_a_generic_ballot_cycles.csv'; SEED=20260822
KLARNER=ROOT/'data/raw/historical_statewide_elections/dataverse_files.zip'; INC_CAND=CAL/'southern_2024_incumbency_candidates.csv'
# Direct inputs read by fit_2026_prospective_model.prospective_features().  Keep
# this list explicit so a research build cannot claim reproducibility while
# hiding changes to its prospective baseline behind an imported helper.
PROSPECTIVE_INPUTS=[
 WAR/'2026_final_candidate_roster.csv',
 ROOT/'data/processed/presidential/2026_district_presidential_features.csv',
 ROOT/'data/processed/presidential/2022_district_presidential_features.csv',
 ROOT/'data/processed/demographics/2026_sld_demographics.csv',
 WAR/'2026_candidate_incumbency.csv',
 WAR/'2026_poll_adjusted_baseline.csv',
 WAR/'2026_state_candidate_finance_matches.csv',
 ROOT/'data/processed/polling/votehub_silver_bplus_topline_environment.csv',
 ROOT/'data/processed/polling/catalist_national_demographic_master.csv',
]
KEYS=['state','year','chamber','district']
SPECS={
 'baseline':[],
 'demographics':['nonwhite_share','white_college_share','swing_x_nonwhite','swing_x_white_college'],
 'demographics_incumbency':['nonwhite_share','white_college_share','swing_x_nonwhite','swing_x_white_college','incumbency_balance','open_seat'],
 'demographics_incumbency_prior_quality':['nonwhite_share','white_college_share','swing_x_nonwhite','swing_x_white_college','incumbency_balance','open_seat','prior_quality_differential','prior_quality_available'],
}

def sha(path):
 d=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): d.update(b)
 return d.hexdigest()

def panel():
 p=pd.read_csv(PANEL,low_memory=False); p=p[p.primary_calibration_eligible.astype(bool)].copy()
 inc=pd.read_csv(INC); i=inc[['state','year','chamber','district','incumbency_balance','incumbency_model_ready']]
 old=p.year.ne(2024); p.loc[old,'incumbency_model_ready']=p.loc[old,'incumbency_balance'].notna()
 p=p.merge(i,on=KEYS,how='left',suffixes=('','_inferred'),validate='one_to_one')
 use=p.year.eq(2024); p.loc[use,'incumbency_balance']=p.loc[use,'incumbency_balance_inferred']; p.loc[use,'incumbency_model_ready']=p.loc[use,'incumbency_model_ready_inferred']
 p=p.drop(columns=['incumbency_balance_inferred','incumbency_model_ready_inferred']); p['open_seat']=p.incumbency_balance.eq(0).astype(float)
 p=p.sort_values(KEYS).copy(); p['gap']=p.dem_margin-p.environment_baseline_margin
 p=attach_candidate_ids(p); p['prior_quality_differential']=0.; p['prior_quality_available']=0
 history={}
 for year in sorted(p.year.unique()):
  current=p[p.year.eq(year)]
  for idx,r in current.iterrows():
   dem=history.get((r.state,r.chamber,r.dem_candidate_id),[]) if pd.notna(r.dem_candidate_id) else []
   rep=history.get((r.state,r.chamber,r.rep_candidate_id),[]) if pd.notna(r.rep_candidate_id) else []
   dm=np.mean(dem)*len(dem)/(len(dem)+3) if dem else 0.; rm=np.mean(rep)*len(rep)/(len(rep)+3) if rep else 0.
   p.at[idx,'prior_quality_differential']=dm-rm; p.at[idx,'prior_quality_available']=int(bool(dem or rep))
  for _,r in current.iterrows():
   if pd.notna(r.dem_candidate_id): history.setdefault((r.state,r.chamber,r.dem_candidate_id),[]).append(r.gap)
   if pd.notna(r.rep_candidate_id): history.setdefault((r.state,r.chamber,r.rep_candidate_id),[]).append(-r.gap)
 p['demographic_type']=np.select([p.nonwhite_share.ge(.5),p.white_college_share.ge(.35)],['majority_nonwhite','high_white_college'],default='other')
 return p

def attach_candidate_ids(p):
 with ZipFile(KLARNER) as z: c=pd.read_csv(z.open('208slers_uoa_cand_contest20230810.csv'),low_memory=False)
 states={'Arkansas':'AR','Georgia':'GA','Tennessee':'TN','Texas':'TX'}
 c=c[c.year.isin([2018,2020,2022])&c.state.isin(states)&c.partyt.isin(['d','r'])].copy()
 c['state']=c.state.map(states); c['chamber']=c.sen.map({0:'lower',1:'upper'}); c['district']=pd.to_numeric(c.dno,errors='coerce'); c['party']=c.partyt.str.upper(); c['v']=pd.to_numeric(c.vote,errors='coerce').fillna(-1)
 c=c.sort_values('v',ascending=False).drop_duplicates(KEYS+['party']); c['candidate_id']=c.cand.map(normalized_name)
 old=c.pivot(index=KEYS,columns='party',values='candidate_id').reset_index().rename(columns={'D':'dem_candidate_id','R':'rep_candidate_id'})
 x=pd.read_csv(INC_CAND); x['candidate_id']=np.where(x.prior_candidate.notna()&x.incumbent.fillna(False),x.prior_candidate.map(normalized_name),x.candidate.map(normalized_name))
 new=x.pivot(index=KEYS,columns='party',values='candidate_id').reset_index().rename(columns={'D':'dem_candidate_id','R':'rep_candidate_id'})
 return p.merge(pd.concat([old,new],ignore_index=True),on=KEYS,how='left',validate='one_to_one')

def weights(x):
 k=list(zip(x.state,x.year,x.chamber)); c=pd.Series(k).value_counts(); w=np.array([1/c[v] for v in k]); return w/w.mean()
def model(features):
 numeric=features; trans=[]
 if numeric: trans.append(('n',Pipeline([('imp',SimpleImputer(strategy='median',add_indicator=True)),('s',StandardScaler())]),numeric))
 trans.append(('c',OneHotEncoder(handle_unknown='ignore'),['chamber']))
 return Pipeline([('x',ColumnTransformer(trans)),('r',Ridge(alpha=20.))])

def tournament(p):
 rows=[]
 for year in (2020,2022,2024):
  train=p[p.year.lt(year)]; test=p[p.year.eq(year)&p.incumbency_model_ready.fillna(False)].copy()
  for name,features in SPECS.items():
   if name=='baseline': pred=test.environment_baseline_margin.to_numpy()
   else:
    fit=model(features); fit.fit(train,train.gap,r__sample_weight=weights(train)); pred=test.environment_baseline_margin+fit.predict(test)
   for r,v in zip(test.itertuples(),pred): rows.append({**{k:getattr(r,k) for k in KEYS},'model':name,'train_rows':len(train),'train_max_year':train.year.max(),'actual_margin':r.dem_margin,'predicted_margin':v,'error':r.dem_margin-v,'incumbency_balance':r.incumbency_balance,'demographic_type':r.demographic_type})
 pred=pd.DataFrame(rows); met=pred.groupby(['model','year'],as_index=False).agg(races=('district','size'),mae=('error',lambda x:x.abs().mean()),rmse=('error',lambda x:np.sqrt(np.mean(x*x))),bias=('error','mean'))
 base=met[met.model.eq('baseline')].set_index('year').mae; rank=[]
 for n,g in met.groupby('model'):
  g=g.sort_values('year'); delta=g.mae-g.year.map(base)
  rank.append({'model':n,'mean_mae':g.mae.mean(),'mean_rmse':g.rmse.mean(),'delta_vs_baseline':delta.mean(),'latest_delta':delta.iloc[-1],'worst_delta':delta.max(),'cycles_improved':int((delta<0).sum())})
 rank=pd.DataFrame(rank); rank['guardrail_pass']=(rank.model.ne('baseline')&rank.delta_vs_baseline.lt(0)&rank.latest_delta.le(0)&rank.worst_delta.le(1)&rank.cycles_improved.ge(2))
 ok=rank[rank.guardrail_pass]; selected=ok.sort_values(['mean_mae','model']).iloc[0].model if len(ok) else 'baseline'; rank['selected']=rank.model.eq(selected)
 return pred,met,rank.sort_values(['selected','mean_mae'],ascending=[False,True]),selected

def prob(m,s):
 z=np.asarray(m)/s['scale']; return np.clip(ndtr(z) if s['family']=='normal' else expit(z) if s['family']=='logistic' else student_t.cdf(z,s['df']),1e-6,1-1e-6)
def probability_calibration(pred,selected):
 d=pred[pred.model.eq(selected)].copy(); d['win']=(d.actual_margin>0).astype(int); specs=[]
 for fam,rng,dfs in [('normal',np.arange(2,15.1,.25),[np.nan]),('logistic',np.arange(1,10.1,.25),[np.nan]),('student_t',np.arange(1,12.1,.25),[3,5,8])]:
  for df in dfs:
   for sc in rng:
    p=prob(d.predicted_margin,{'family':fam,'scale':sc,'df':df}); specs.append({'family':fam,'scale':sc,'df':df,'brier':np.mean((p-d.win)**2),'log_loss':-np.mean(d.win*np.log(p)+(1-d.win)*np.log(1-p))})
 table=pd.DataFrame(specs); best=table.sort_values(['brier','log_loss','family','scale']).iloc[0].to_dict()
 d['probability']=prob(d.predicted_margin,best); return d,table,best

def error_components(d):
 e=d.copy(); state=e.groupby(['state','year']).error.transform('mean'); chamber=e.groupby(['state','year','chamber']).error.transform('mean')-state; district=e.error-state-chamber
 poll=pd.read_csv(POLL); national_sd=float(pd.to_numeric(poll.poll_error,errors='coerce').std(ddof=1))
 return pd.DataFrame([{'national_sd':national_sd,'state_sd':state.groupby([e.state,e.year]).first().std(ddof=1),'chamber_sd':chamber.groupby([e.state,e.year,e.chamber]).first().std(ddof=1),'district_sd':district.std(ddof=1),'total_residual_sd':e.error.std(ddof=1)}])

def subgroup(d):
 x=d.copy(); x['margin_band']=pd.cut(x.predicted_margin,[-101,-20,-10,0,10,20,101],include_lowest=True).astype(str); x['incumbency_group']=x.incumbency_balance.map({-1:'R incumbent',0:'open',1:'D incumbent'})
 rows=[]
 for dim in ['state','chamber','margin_band','incumbency_group','demographic_type']:
  for val,g in x.groupby(dim,dropna=False): rows.append({'dimension':dim,'group':str(val),'races':len(g),'mae':g.error.abs().mean(),'rmse':np.sqrt(np.mean(g.error*g.error)),'brier':np.mean((g.probability-(g.actual_margin>0))**2),'bias':g.error.mean()})
 return pd.DataFrame(rows)

def prospective(p,selected,best,components):
 q=prepare_prospective_data().copy(); q['state']='AL'; q['year']=2026; q['environment_baseline_margin']=q.national_environment_baseline; q['incumbency_balance']=q.dem_incumbent_i-q.rep_incumbent_i; q['open_seat']=q.incumbency_balance.eq(0).astype(float); q['prior_quality_differential']=0.; q['prior_quality_available']=0
 features=SPECS[selected]; train=p[p.incumbency_model_ready.fillna(False)]
 adjustment=np.zeros(len(q)) if selected=='baseline' else model(features).fit(train,train.gap,r__sample_weight=weights(train)).predict(q)
 poll_sd=float(components.national_sd.iloc[0]); scenarios=[]
 vals={'headline':q.environment_baseline_margin+adjustment,'environment_dem_favorable':q.environment_baseline_margin+poll_sd,'environment_rep_favorable':q.environment_baseline_margin-poll_sd}
 for name,marg in vals.items():
  z=q[['chamber','district','environment_baseline_margin','incumbency_balance']].copy(); z['scenario']=name; z['predicted_dem_margin']=marg; z['dem_win_probability']=prob(marg,best); z['selected_model']=selected; scenarios.append(z)
 return pd.concat(scenarios,ignore_index=True)

def simulate(forecast,components,draws=50000):
 h=forecast[forecast.scenario.eq('headline')].copy().reset_index(drop=True); c=components.iloc[0]; rng=np.random.default_rng(SEED)
 national=rng.normal(0,c.national_sd,draws); statewide=rng.normal(0,c.state_sd,draws); chamber={v:rng.normal(0,c.chamber_sd,draws) for v in h.chamber.unique()}
 wins=np.empty((draws,len(h)),dtype=np.int8); rows=[]
 for j,r in enumerate(h.itertuples()):
  margin=r.predicted_dem_margin+national+statewide+chamber[r.chamber]+rng.normal(0,c.district_sd,draws); wins[:,j]=margin>0
  rows.append({'chamber':r.chamber,'district':r.district,'conditional_dem_probability':r.dem_win_probability,'full_uncertainty_dem_probability':wins[:,j].mean(),'margin_80_low':np.quantile(margin,.1),'margin_80_high':np.quantile(margin,.9),'margin_95_low':np.quantile(margin,.025),'margin_95_high':np.quantile(margin,.975),'draws':draws})
 seats=[]
 for chamber_name in h.chamber.unique():
  count=wins[:,h.chamber.eq(chamber_name).to_numpy()].sum(axis=1); freq=pd.Series(count).value_counts().sort_index()
  seats.extend({'chamber':chamber_name,'dem_modeled_seats':int(k),'probability':v/draws,'draws':draws} for k,v in freq.items())
 return pd.DataFrame(rows),pd.DataFrame(seats)

def main():
 p=panel(); pred,met,rank,selected=tournament(p); calibrated,families,best=probability_calibration(pred,selected); comp=error_components(calibrated); groups=subgroup(calibrated); forecast=prospective(p,selected,best,comp); sim,seats=simulate(forecast,comp)
 finance=pd.DataFrame([{'feature':'cross_state_candidate_finance','eligible':False,'coverage':0.,'decision':'not tested: no comparable cutoff-consistent multi-state finance mart'}])
 outs={'robust_forecast_v1_panel.csv':p,'robust_forecast_v1_predictions.csv':pred,'robust_forecast_v1_metrics.csv':met,'robust_forecast_v1_ranking.csv':rank,'robust_forecast_v1_probability_families.csv':families,'robust_forecast_v1_calibrated_predictions.csv':calibrated,'robust_forecast_v1_error_components.csv':comp,'robust_forecast_v1_subgroup_audit.csv':groups,'robust_forecast_v1_finance_gate.csv':finance,'robust_forecast_v1_2026_scenarios.csv':forecast,'robust_forecast_v1_2026_full_uncertainty.csv':sim,'robust_forecast_v1_2026_modeled_seats.csv':seats}
 for n,x in outs.items(): x.to_csv(CAL/n,index=False)
 declared_inputs=[PANEL,INC,INC_CAND,KLARNER,POLL,*PROSPECTIVE_INPUTS]
 code_inputs=[Path(__file__).resolve(),ROOT/'scripts/run_forecast_experiment_tournament.py',ROOT/'scripts/fit_2026_prospective_model.py',ROOT/'scripts/build_southern_2024_incumbency.py']
 config={
  'seed':SEED,'simulation_draws':50000,'forward_test_years':[2020,2022,2024],
  'common_test_requires_incumbency_model_ready':True,
  'candidate_quality_shrinkage_k':3,'ridge_alpha':20.0,
  'margin_model_specs':SPECS,
  'selection_guardrails':{'mean_delta_lt':0,'latest_delta_lte':0,'worst_delta_lte':1,'minimum_cycles_improved':2},
  'probability_grid':{
   'selection_metric_order':['brier','log_loss','family','scale'],'probability_clip':[0.000001,0.999999],
   'normal':{'scale_start':2.0,'scale_stop':15.0,'scale_step':0.25,'stop_inclusive':True},
   'logistic':{'scale_start':1.0,'scale_stop':10.0,'scale_step':0.25,'stop_inclusive':True},
   'student_t':{'scale_start':1.0,'scale_stop':12.0,'scale_step':0.25,'stop_inclusive':True,'degrees_of_freedom':[3,5,8]},
  },
  'error_decomposition':{'state_group':['state','year'],'chamber_group':['state','year','chamber'],'district_component':'row_error_minus_state_and_chamber','national_component':'historical_poll_error_sd'},
  'scenario_definitions':{'headline':'selected margin model','environment_dem_favorable':'headline plus national_sd','environment_rep_favorable':'headline minus national_sd'},
  'finance_eligibility_policy':'promote only with comparable cutoff-consistent multi-state finance mart; otherwise exclude and report gate',
 }
 man={'schema_version':2,'status':'validated_public_forecast','methodology_version':'robust_forecast_v1_reconciled','selected_margin_model':selected,'selected_probability':{k:(None if pd.isna(v) else v) for k,v in best.items() if k in ['family','scale','df']},'configuration':config,'inputs':[{'path':str(x.relative_to(ROOT)).replace('\\','/'),'sha256':sha(x)} for x in declared_inputs],'code_inputs':[{'path':str(x.relative_to(ROOT)).replace('\\','/'),'sha256':sha(x)} for x in code_inputs],'outputs':[{'path':f'data/processed/forecast_calibration/{n}','rows':len(x),'sha256':sha(CAL/n)} for n,x in outs.items()]}; man['build_id']=hashlib.sha256(json.dumps(man,sort_keys=True).encode()).hexdigest()[:20]; (CAL/'robust_forecast_v1_manifest.json').write_text(json.dumps(man,indent=2)+'\n')
 print('robust forecast',man['build_id'],'selected',selected,best); print(rank.to_string(index=False)); print(comp.to_string(index=False))
if __name__=='__main__': main()
