"""Build a current environment using Silver B-rated or better polls."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
POLLING=ROOT/'data/processed/polling'
CATALOG=ROOT/'data/raw/polling/votehub_generic_ballot_catalog.json'
SUPPLEMENT=POLLING/'silver_recent_generic_ballot_cells.csv'
POP={'lv':1.0,'rv':0.75,'a':0.5}

def logit(x):
    x=np.clip(np.asarray(x,dtype=float),1e-6,1-1e-6);return np.log(x/(1-x))
def expit(x): return 1/(1+np.exp(-np.asarray(x,dtype=float)))

def main():
    catalog=pd.read_json(CATALOG)
    grades=pd.read_csv(POLLING/'votehub_crosstab_documents_with_silver_grades.csv')[
        ['pollster','silver_pollster','silver_grade','b_plus_or_better']].drop_duplicates('pollster')
    catalog=catalog.merge(grades,on='pollster',how='left')
    catalog=catalog[catalog.b_plus_or_better.fillna(False)&~catalog.internal.fillna(False)&catalog.partisan.isna()].copy()
    catalog['end_date']=pd.to_datetime(catalog.end_date)
    catalog['dem_pct']=catalog.answers.map(lambda a:next((x['pct'] for x in a if str(x['choice']).lower() in {'dem','democrat','democratic'}),np.nan))
    catalog['rep_pct']=catalog.answers.map(lambda a:next((x['pct'] for x in a if str(x['choice']).lower() in {'rep','republican','gop'}),np.nan))
    catalog['share']=catalog.dem_pct/(catalog.dem_pct+catalog.rep_pct)
    if SUPPLEMENT.exists():
        supplement=pd.read_csv(SUPPLEMENT)
        overall=supplement[supplement.dimension.eq('overall')].copy()
        extra=pd.DataFrame({
            'id':overall.poll_id,'pollster':overall.pollster,
            'silver_pollster':overall.pollster,'silver_grade':overall.silver_grade,
            'b_plus_or_better':True,'internal':False,'partisan':np.nan,
            'start_date':overall.start_date,'end_date':overall.end_date,
            'population':overall.population,'sample_size':overall.sample_size,
            'dem_pct':overall.dem_pct,'rep_pct':overall.rep_pct,
            'share':overall.dem_two_party_share,
        })
        catalog=pd.concat([catalog,extra],ignore_index=True,sort=False)
    catalog['end_date']=pd.to_datetime(catalog.end_date)
    as_of=catalog.end_date.max();recent=catalog[catalog.end_date.ge(as_of-pd.Timedelta(days=59))].copy()
    recent=recent.sort_values('end_date').drop_duplicates('silver_pollster',keep='last')
    recent['weight']=recent.population.str.lower().map(POP).fillna(.5)*np.power(.5,(as_of-recent.end_date).dt.days/21)
    overall=float(np.average(recent.share,weights=recent.weight))
    pd.DataFrame([{'as_of':as_of.date().isoformat(),'dem_two_party_share':overall,
                   'dem_two_party_margin':200*overall-100,'pollsters':recent.silver_pollster.nunique(),
                   'pollster_list':' | '.join(sorted(recent.silver_pollster.unique())),
                   'window_days':60,'minimum_silver_grade':'B'}]).to_csv(
        POLLING/'votehub_silver_bplus_topline_environment.csv',index=False)

    cells=pd.read_csv(POLLING/'votehub_demographic_crosstabs_long.csv')
    cells=cells[cells.b_plus_or_better.fillna(False)].copy()
    canonical=grades[['pollster','silver_pollster']].drop_duplicates('pollster')
    cells=cells.drop(columns=['silver_pollster'],errors='ignore').merge(canonical,on='pollster',how='left')
    cells['canonical_pollster']=cells.silver_pollster.fillna(cells.pollster)
    if SUPPLEMENT.exists():
        extra_cells=pd.read_csv(SUPPLEMENT)
        extra_cells['canonical_pollster']=extra_cells.pollster
        extra_cells['end_date']=extra_cells.end_date
        extra_cells['dem_two_party_share']=extra_cells.dem_two_party_share
        cells=pd.concat([cells,extra_cells],ignore_index=True,sort=False)
    totals=cells[cells.dimension.eq('overall')][['poll_id','dem_two_party_share']].rename(columns={'dem_two_party_share':'overall_share'})
    cells=cells.merge(totals,on='poll_id',how='left',validate='many_to_one')
    selected=cells[((cells.dimension.eq('race'))&cells.group.isin(['white','black','hispanic']))|
                   ((cells.dimension.eq('education'))&cells.group.isin([
                       'marist_not_college_grad','marist_college_grad',
                       'echelon_noncollege','echelon_college','fox_no_college_degree',
                       'fox_college_degree']))].copy()
    selected['group']=selected.group.replace({
        'echelon_noncollege':'marist_not_college_grad',
        'fox_no_college_degree':'marist_not_college_grad',
        'echelon_college':'marist_college_grad',
        'fox_college_degree':'marist_college_grad',
    })
    selected['relative_logit']=logit(selected.dem_two_party_share)-logit(selected.overall_share)
    selected['end_date']=pd.to_datetime(selected.end_date)
    selected=selected.sort_values('end_date').drop_duplicates(['canonical_pollster','dimension','group'],keep='last')
    age=(as_of-selected.end_date).dt.days.clip(lower=0)
    selected['weight']=selected.population.str.lower().map(POP).fillna(.5)*np.power(.5,age/90)
    rows=[]
    for (dimension,group),part in selected.groupby(['dimension','group']):
        effect=float(np.average(part.relative_logit,weights=part.weight))
        rows.append({'as_of':as_of.date().isoformat(),'dimension':dimension,'group':group,
                     'relative_logit':effect,'projected_dem_two_party_share':float(expit(logit(overall)+effect)),
                     'pollsters':part.canonical_pollster.nunique(),'polls':part.poll_id.nunique(),
                     'pollster_list':' | '.join(sorted(part.canonical_pollster.unique())),
                     'minimum_silver_grade':'B'})
    pd.DataFrame(rows).to_csv(POLLING/'votehub_silver_bplus_demographic_environment.csv',index=False)
    print(pd.DataFrame(rows).to_string(index=False))

if __name__=='__main__':main()
