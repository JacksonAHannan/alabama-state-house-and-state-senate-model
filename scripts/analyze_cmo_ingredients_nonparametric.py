"""Nonparametric and design-based analyses of federal-relative overperformance."""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor,RandomForestRegressor
from sklearn.feature_selection import mutual_info_regression
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error,mean_squared_error
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from compare_federal_cmo_baselines import prepare

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'processed'/'elections'/'validation'
FEATURES=['nonwhite_share','white_college_share','dem_incumbent_i','rep_incumbent_i','resource_ratio',
          'resource_complete_i','federal_state_gap','federal_contested_coverage','prior_pres_dem_margin','house_i']

def enrich()->pd.DataFrame:
    data=prepare();data=data[data.federal_usable].copy()
    data['federal_relative_overperformance']=data.legislative_dem_margin-data.federal_index_margin
    data['dem_incumbent_i']=data.dem_incumbent.fillna(False).astype(int);data['rep_incumbent_i']=data.rep_incumbent.fillna(False).astype(int)
    resource=pd.Series(np.nan,index=data.index)
    for col in ('log_spending_ratio_d_to_r','log_fundraising_ratio_d_to_r','log_resource_ratio_d_to_r'):
        if col in data:resource=resource.fillna(pd.to_numeric(data[col],errors='coerce'))
    data['resource_ratio']=resource;data['resource_complete_i']=resource.notna().astype(int);data['house_i']=data.chamber.eq('house').astype(int)
    current=np.select([data.cycle.eq(2014),data.cycle.eq(2018),data.cycle.eq(2022)],
      [data.pres_2012_dem_margin,data.pres_2016_dem_margin,data.pres_2020_dem_margin],default=np.nan)
    data['prior_pres_dem_margin']=pd.Series(current,index=data.index).fillna(data.get('prior_pres_dem_margin')).fillna(data.get('pres_1992_dem_margin'))
    return data

def model_pipeline(kind:str):
    model=(ExtraTreesRegressor(n_estimators=240,min_samples_leaf=8,max_features=.8,random_state=20260816,n_jobs=-1)
           if kind=='extra_trees' else RandomForestRegressor(n_estimators=240,min_samples_leaf=8,max_features=.8,random_state=20260816,n_jobs=-1))
    return Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),('model',model)])

def forward_models(data:pd.DataFrame):
    rows=[];predictions=[];importance=[];ycol='federal_relative_overperformance'
    for test_cycle in (2010,2014,2018,2022):
      test=data[data.cycle.eq(test_cycle)]
      windows={'all_prior':data[data.cycle.lt(test_cycle)]}
      if test_cycle in (2014,2022):windows['same_era_prior']=data[(data.era.eq(test.era.iloc[0]))&(data.cycle.lt(test_cycle))]
      for training_window,train in windows.items():
       if len(train)<50 or test.empty:continue
       for kind in ('extra_trees','random_forest'):
        model=model_pipeline(kind);model.fit(train[FEATURES],train[ycol]);pred=model.predict(test[FEATURES])
        rows.append({'model':kind,'training_window':training_window,'test_cycle':test_cycle,'train_races':len(train),'test_races':len(test),
          'mae':mean_absolute_error(test[ycol],pred),'rmse':mean_squared_error(test[ycol],pred)**.5,
          'zero_baseline_mae':mean_absolute_error(test[ycol],np.zeros(len(test)))})
        out=test[['cycle','chamber','district','era',ycol]].copy();out['model']=kind;out['training_window']=training_window;out['prediction']=pred;out['error']=out[ycol]-pred;predictions.append(out)
        perm=permutation_importance(model,test[FEATURES],test[ycol],scoring='neg_mean_absolute_error',n_repeats=10,random_state=20260816,n_jobs=-1)
        importance.extend({'model':kind,'training_window':training_window,'test_cycle':test_cycle,'feature':feature,'importance_mae':value}
                          for feature,value in zip(FEATURES,perm.importances_mean))
    return pd.DataFrame(rows),pd.concat(predictions,ignore_index=True),pd.DataFrame(importance)

def matched_contrasts(data:pd.DataFrame)->pd.DataFrame:
    d=data.copy();d['federal_more_republican_than_state']=d.federal_state_gap.lt(d.groupby('era').federal_state_gap.transform('median')).astype(int)
    d['high_nonwhite']=d.nonwhite_share.gt(d.groupby('era').nonwhite_share.transform('median')).astype(int)
    d['high_white_college']=d.white_college_share.gt(d.groupby('era').white_college_share.transform('median')).astype(int)
    d['dem_resource_advantage']=(d.resource_ratio.gt(0)&d.resource_ratio.notna()).astype(int)
    treatments=['federal_more_republican_than_state','high_nonwhite','high_white_college','dem_incumbent_i','rep_incumbent_i','dem_resource_advantage']
    covars=['nonwhite_share','white_college_share','federal_index_margin','federal_contested_coverage']
    rows=[]
    for treatment in treatments:
      diffs=[]
      for (_, _),group in d.groupby(['era','chamber']):
        treated=group[group[treatment].eq(1)];control=group[group[treatment].eq(0)]
        if treated.empty or control.empty:continue
        treatment_source={'high_nonwhite':'nonwhite_share','high_white_college':'white_college_share',
                          'federal_more_republican_than_state':'federal_state_gap'}.get(treatment)
        cols=[c for c in covars if c!=treatment_source]
        imp=SimpleImputer(strategy='median');scale=StandardScaler()
        combined=pd.concat([treated[cols],control[cols]]);z=scale.fit_transform(imp.fit_transform(combined))
        tz=z[:len(treated)];cz=z[len(treated):];indices=NearestNeighbors(n_neighbors=1).fit(cz).kneighbors(tz,return_distance=False).ravel()
        diffs.extend((treated.federal_relative_overperformance.to_numpy()-control.iloc[indices].federal_relative_overperformance.to_numpy()).tolist())
      arr=np.asarray(diffs);rows.append({'ingredient':treatment,'matched_pairs':len(arr),'mean_contrast':arr.mean() if len(arr) else np.nan,
        'median_contrast':np.median(arr) if len(arr) else np.nan,'positive_share':np.mean(arr>0) if len(arr) else np.nan})
    return pd.DataFrame(rows)

def profiles_and_breaks(data:pd.DataFrame):
    profiles=[]
    for feature in ('federal_state_gap','nonwhite_share','white_college_share','resource_ratio'):
      valid=data[data[feature].notna()].copy();valid['bin']=pd.qcut(valid[feature],5,duplicates='drop')
      for (era,bin_),g in valid.groupby(['era','bin'],observed=True):profiles.append({'era':era,'feature':feature,'bin':str(bin_),
        'races':len(g),'feature_mean':g[feature].mean(),'mean_overperformance':g.federal_relative_overperformance.mean(),
        'median_overperformance':g.federal_relative_overperformance.median()})
    eras=(data.groupby('era',as_index=False).agg(races=('district','size'),mean_federal_relative=('federal_relative_overperformance','mean'),
      median_federal_relative=('federal_relative_overperformance','median'),sd_federal_relative=('federal_relative_overperformance','std'),
      mean_state_relative=('raw_overperformance','mean'),mean_federal_state_gap=('federal_state_gap','mean')))
    return pd.DataFrame(profiles),eras

def main()->None:
    data=enrich();models,predictions,importance=forward_models(data);matched=matched_contrasts(data);profiles,eras=profiles_and_breaks(data)
    imputed=SimpleImputer(strategy='median').fit_transform(data[FEATURES]);mi=mutual_info_regression(imputed,data.federal_relative_overperformance,random_state=20260816)
    mutual=pd.DataFrame({'feature':FEATURES,'mutual_information':mi}).sort_values('mutual_information',ascending=False)
    outputs={'cmo_nonparametric_forward_validation.csv':models,'cmo_nonparametric_predictions.csv':predictions,
      'cmo_permutation_importance.csv':importance,'cmo_matched_ingredient_contrasts.csv':matched,
      'cmo_ingredient_binned_profiles.csv':profiles,'cmo_era_break_diagnostics.csv':eras,'cmo_mutual_information.csv':mutual}
    for name,frame in outputs.items():frame.to_csv(OUT/name,index=False)
    print(models.to_string(index=False));print('\nMatched contrasts:\n',matched.to_string(index=False));print('\nMutual information:\n',mutual.to_string(index=False))

if __name__=='__main__':main()
