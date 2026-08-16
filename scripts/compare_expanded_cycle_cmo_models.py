"""Compare the published-era CMO training window with experimental older cycles.

This is a research diagnostic only.  It never changes ``model_eligible`` or any
published CMO output.  The fair comparison uses the same pre-election/context
features and evaluates both windows on the shared 2014, 2018, and 2022 cycles.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GridSearchCV, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data'/'processed'/'elections'/'canonical_cmo_features.csv'
OUT=ROOT/'data'/'processed'/'elections'/'validation'
ALPHAS=(.1,.3,1,3,10,30,100)
BASE_FEATURES=['dem_incumbent_i','rep_incumbent_i','prior_pres_dem_margin',
               'nonwhite_share','white_college_share']
INTERACTION_FEATURES=BASE_FEATURES+['modern_cycle','nonwhite_x_modern','white_college_x_modern',
    'house_i','nonwhite_x_house','white_college_x_house','dem_incumbent_x_house','rep_incumbent_x_house']
RESOURCE_FEATURES=BASE_FEATURES+['resource_ratio','resource_complete_i']

def prepare(frame:pd.DataFrame)->pd.DataFrame:
    data=frame[frame.war_eligible.fillna(False)].copy()
    def as_binary(series):
        numeric=pd.to_numeric(series,errors='coerce')
        text=series.astype('string').str.lower().map({'true':1,'false':0,'yes':1,'no':0})
        return numeric.fillna(text).fillna(0).astype(int)
    data['dem_incumbent_i']=as_binary(data.dem_incumbent)
    data['rep_incumbent_i']=as_binary(data.rep_incumbent)
    current=np.select(
        [data.cycle.eq(2014),data.cycle.eq(2018),data.cycle.eq(2022)],
        [data.get('pres_2012_dem_margin'),data.get('pres_2016_dem_margin'),data.get('pres_2020_dem_margin')],
        default=np.nan)
    historical=data.get('prior_pres_dem_margin',pd.Series(np.nan,index=data.index))
    pres_1992=data.get('pres_1992_dem_margin',pd.Series(np.nan,index=data.index))
    data['prior_pres_dem_margin']=pd.Series(current,index=data.index).fillna(historical).fillna(pres_1992)
    data['modern_cycle']=data.cycle.ge(2014).astype(int)
    chamber=data.get('chamber',pd.Series('senate',index=data.index))
    data['house_i']=chamber.eq('house').astype(int)
    nonwhite=data.get('nonwhite_share',pd.Series(np.nan,index=data.index))
    white_college=data.get('white_college_share',pd.Series(np.nan,index=data.index))
    data['nonwhite_x_modern']=nonwhite*data.modern_cycle
    data['white_college_x_modern']=white_college*data.modern_cycle
    data['nonwhite_x_house']=nonwhite*data.house_i
    data['white_college_x_house']=white_college*data.house_i
    data['dem_incumbent_x_house']=data.dem_incumbent_i*data.house_i
    data['rep_incumbent_x_house']=data.rep_incumbent_i*data.house_i
    data['incumbency_group']=np.select(
        [data.dem_incumbent_i.eq(1),data.rep_incumbent_i.eq(1)],['dem_incumbent','rep_incumbent'],default='open')
    fallback=data.get('baseline_fallback_share',pd.Series(0.0,index=data.index)).fillna(0)
    data['fallback_group']=np.where(fallback.gt(.05),'fallback_over_5pct','direct_or_minor_fallback')
    resource=pd.Series(np.nan,index=data.index,dtype=float)
    for column in ('log_spending_ratio_d_to_r','log_fundraising_ratio_d_to_r','log_resource_ratio_d_to_r'):
        if column in data:resource=resource.fillna(pd.to_numeric(data[column],errors='coerce'))
    data['resource_ratio']=resource
    data['resource_complete_i']=resource.notna().astype(int)
    return data.replace([np.inf,-np.inf],np.nan)

def estimator(train_rows:int,features:list[str])->GridSearchCV:
    numeric=Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                      ('scale',StandardScaler())])
    prep=ColumnTransformer([('numeric',numeric,features),
                            ('chamber',OneHotEncoder(drop='first',handle_unknown='ignore'),['chamber'])])
    model=Pipeline([('preprocess',prep),('model',Ridge())])
    folds=max(2,min(5,train_rows//20))
    return GridSearchCV(model,{'model__alpha':ALPHAS},scoring='neg_mean_absolute_error',
                          cv=KFold(folds,shuffle=True,random_state=20260816))

def score(y,pred)->dict:
    return {'mae':mean_absolute_error(y,pred),'rmse':mean_squared_error(y,pred)**.5,
            'mean_error':float(np.mean(np.asarray(y)-pred))}

def main()->None:
    data=prepare(pd.read_csv(SOURCE))
    windows={'published_era_2010_2022':(2010,2014,2018,2022),
             'expanded_1998_2022':(1998,2002,2006,2010,2014,2018,2022),
             'expanded_1994_2022':(1994,1998,2002,2006,2010,2014,2018,2022)}
    variants={'base':BASE_FEATURES,'era_chamber_interactions':INTERACTION_FEATURES,
              'resource_adjusted':RESOURCE_FEATURES}
    rows=[];predictions=[]
    for test_cycle in (2014,2018,2022):
        for window,cycles in windows.items():
            for variant,features in variants.items():
                train=data[data.cycle.isin([c for c in cycles if c<test_cycle])]
                test=data[data.cycle.eq(test_cycle)]
                est=estimator(len(train),features);est.fit(train[features+['chamber']],train.raw_overperformance)
                pred=est.predict(test[features+['chamber']])
                rows.append({'window':window,'variant':variant,'test_cycle':test_cycle,'train_cycles':'+'.join(map(str,sorted(train.cycle.unique()))),
                             'train_races':len(train),'test_races':len(test),'selected_alpha':est.best_params_['model__alpha'],
                             **score(test.raw_overperformance,pred)})
                out=test[['cycle','chamber','district','raw_overperformance','incumbency_group','fallback_group']].copy()
                out['window']=window;out['variant']=variant;out['prediction']=pred;out['error']=out.raw_overperformance-pred
                predictions.append(out)
    detail=pd.concat(predictions,ignore_index=True)
    summary=pd.DataFrame(rows)
    aggregate=(detail.groupby(['window','variant']).apply(
        lambda x:pd.Series({'shared_test_races':len(x),'pooled_mae':mean_absolute_error(x.raw_overperformance,x.prediction),
                            'pooled_rmse':mean_squared_error(x.raw_overperformance,x.prediction)**.5}),
        include_groups=False).reset_index())
    reference=float(aggregate.loc[aggregate.window.eq('published_era_2010_2022')&aggregate.variant.eq('base'),'pooled_mae'].iloc[0])
    aggregate['delta_mae_vs_published_era']=aggregate.pooled_mae-reference
    cycle_mae=summary.pivot(index=['window','variant'],columns='test_cycle',values='mae')
    recent_reference=float(cycle_mae.loc[('published_era_2010_2022','base'),2022])
    aggregate=aggregate.merge(cycle_mae[2022].rename('mae_2022'),on=['window','variant'],validate='one_to_one')
    aggregate['delta_2022_mae_vs_published_era']=aggregate.mae_2022-recent_reference
    # A research window advances only if it materially improves pooled error
    # without degrading the most recent genuine forward test by >0.5 points.
    aggregate['screening_gate_passed']=(aggregate.delta_mae_vs_published_era.lt(-.25)&
                                        aggregate.delta_2022_mae_vs_published_era.le(.5))
    subgroup=[]
    for (window,variant),group in detail.groupby(['window','variant']):
        for dimension in ('chamber','incumbency_group','fallback_group'):
            for value,part in group.groupby(dimension):
                subgroup.append({'window':window,'variant':variant,'dimension':dimension,'group':value,
                    'races':len(part),'mae':mean_absolute_error(part.raw_overperformance,part.prediction),
                    'mean_error':part.error.mean()})
    subgroup=pd.DataFrame(subgroup)
    # Cycle-block bootstrap: intentionally resamples the three test cycles as
    # clusters. It is descriptive because three clusters cannot support a
    # precise confidence interval.
    rng=np.random.default_rng(20260816);boot=[];cycles=np.array([2014,2018,2022])
    ref=detail[(detail.window.eq('published_era_2010_2022'))&(detail.variant.eq('base'))]
    for (window,variant),candidate in detail.groupby(['window','variant']):
        deltas=[]
        for _ in range(5000):
            sampled=rng.choice(cycles,size=3,replace=True)
            c=pd.concat([candidate[candidate.cycle.eq(cycle)] for cycle in sampled])
            r=pd.concat([ref[ref.cycle.eq(cycle)] for cycle in sampled])
            deltas.append(mean_absolute_error(c.raw_overperformance,c.prediction)-mean_absolute_error(r.raw_overperformance,r.prediction))
        boot.append({'window':window,'variant':variant,'cycle_clusters':3,'replicates':5000,
                     'probability_mae_improvement':float(np.mean(np.array(deltas)<0)),
                     'delta_mae_p05':float(np.quantile(deltas,.05)),'delta_mae_p95':float(np.quantile(deltas,.95))})
    OUT.mkdir(parents=True,exist_ok=True)
    summary.to_csv(OUT/'expanded_cycle_cmo_forward_validation.csv',index=False)
    aggregate.to_csv(OUT/'expanded_cycle_cmo_comparison_summary.csv',index=False)
    detail.to_csv(OUT/'expanded_cycle_cmo_predictions.csv',index=False)
    subgroup.to_csv(OUT/'expanded_cycle_cmo_subgroup_diagnostics.csv',index=False)
    pd.DataFrame(boot).to_csv(OUT/'expanded_cycle_cmo_cycle_bootstrap.csv',index=False)
    print(aggregate.to_string(index=False));print('\n',summary.to_string(index=False))

if __name__=='__main__':main()
