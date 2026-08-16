"""Compare state, federal, and blended baselines for historical CMO races."""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error,mean_squared_error

ROOT=Path(__file__).resolve().parents[1];ELECT=ROOT/'data'/'processed'/'elections';OUT=ELECT/'validation'
WEIGHTS=np.arange(0,1.01,.1)

def metrics(y,p):return {'mae':mean_absolute_error(y,p),'rmse':mean_squared_error(y,p)**.5,'mean_error':float(np.mean(y-p))}

def prepare()->pd.DataFrame:
    races=pd.read_csv(ELECT/'canonical_cmo_features.csv');fed=pd.read_csv(ELECT/'historical_federal_district_baselines.csv')
    data=races[races.war_eligible].merge(fed,on=['cycle','chamber','district'],how='left',validate='one_to_one')
    data['federal_state_gap']=data.federal_index_margin-data.core_index_margin
    data['era']=np.select([data.cycle.le(2006),data.cycle.le(2014)],['pre_2008','obama_era_2010_2014'],default='trump_era_2018_plus')
    data['federal_usable']=data.federal_index_margin.notna()&data.federal_contested_coverage.ge(.5)
    return data

def main()->None:
    data=prepare();usable=data[data.federal_usable].copy();rows=[]
    for era,g in usable.groupby('era'):
      for name,pred in {'state':g.core_index_margin,'federal':g.federal_index_margin}.items():
        rows.append({'scope':era,'baseline':name,'races':len(g),**metrics(g.legislative_dem_margin,pred)})
      for weight in WEIGHTS:
        pred=(1-weight)*g.core_index_margin+weight*g.federal_index_margin
        rows.append({'scope':era,'baseline':f'blend_federal_{weight:.1f}','races':len(g),**metrics(g.legislative_dem_margin,pred)})
    for name,pred in {'state':usable.core_index_margin,'federal':usable.federal_index_margin}.items():
      rows.append({'scope':'all','baseline':name,'races':len(usable),**metrics(usable.legislative_dem_margin,pred)})
    for weight in WEIGHTS:
      pred=(1-weight)*usable.core_index_margin+weight*usable.federal_index_margin
      rows.append({'scope':'all','baseline':f'blend_federal_{weight:.1f}','races':len(usable),**metrics(usable.legislative_dem_margin,pred)})
    comparison=pd.DataFrame(rows)

    # Honest forward selection: select the constrained blend on prior cycles,
    # then score the next cycle. No future-era weight is used.
    forward=[]
    for test_cycle in sorted(usable.cycle.unique())[1:]:
      train=usable[usable.cycle.lt(test_cycle)];test=usable[usable.cycle.eq(test_cycle)]
      if train.empty or test.empty:continue
      losses={w:mean_absolute_error(train.legislative_dem_margin,(1-w)*train.core_index_margin+w*train.federal_index_margin) for w in WEIGHTS}
      selected=min(losses,key=losses.get);pred=(1-selected)*test.core_index_margin+selected*test.federal_index_margin
      forward.append({'test_cycle':test_cycle,'train_cycles':'+'.join(map(str,sorted(train.cycle.unique()))),
        'selected_federal_weight':selected,'train_mae':losses[selected],'test_races':len(test),**metrics(test.legislative_dem_margin,pred),
        'state_mae':mean_absolute_error(test.legislative_dem_margin,test.core_index_margin),
        'federal_mae':mean_absolute_error(test.legislative_dem_margin,test.federal_index_margin)})
    forward=pd.DataFrame(forward)
    adaptive=[]
    for test_cycle in (2014,2022):
      era=usable.loc[usable.cycle.eq(test_cycle),'era'].iloc[0]
      train=usable[(usable.era.eq(era))&(usable.cycle.lt(test_cycle))];test=usable[usable.cycle.eq(test_cycle)]
      losses={w:mean_absolute_error(train.legislative_dem_margin,(1-w)*train.core_index_margin+w*train.federal_index_margin) for w in WEIGHTS}
      selected=min(losses,key=losses.get);pred=(1-selected)*test.core_index_margin+selected*test.federal_index_margin
      adaptive.append({'era':era,'test_cycle':test_cycle,'train_cycles':'+'.join(map(str,sorted(train.cycle.unique()))),
        'selected_federal_weight':selected,'train_races':len(train),'test_races':len(test),**metrics(test.legislative_dem_margin,pred),
        'state_mae':mean_absolute_error(test.legislative_dem_margin,test.core_index_margin),
        'federal_mae':mean_absolute_error(test.legislative_dem_margin,test.federal_index_margin)})
    adaptive=pd.DataFrame(adaptive)
    detail=usable[['cycle','chamber','district','era','legislative_dem_margin','core_index_margin','federal_index_margin',
      'federal_state_gap','federal_contested_coverage','us_house_dem_margin','us_senate_dem_margin']].copy()
    for weight in (.25,.5,.75):detail[f'blend_{weight:.2f}_margin']=(1-weight)*detail.core_index_margin+weight*detail.federal_index_margin
    comparison.to_csv(OUT/'federal_baseline_specification_comparison.csv',index=False)
    forward.to_csv(OUT/'federal_baseline_forward_validation.csv',index=False)
    adaptive.to_csv(OUT/'federal_baseline_era_adaptive_validation.csv',index=False)
    detail.to_csv(OUT/'federal_baseline_race_detail.csv',index=False)
    print('Best by era:');print(comparison.loc[comparison.groupby('scope').mae.idxmin()].sort_values('scope').to_string(index=False))
    print('\nForward selection:');print(forward.to_string(index=False))
    print('\nEra-adaptive forward selection:');print(adaptive.to_string(index=False))

if __name__=='__main__':main()
