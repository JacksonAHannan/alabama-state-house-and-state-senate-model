"""Test multidimensional ideology against durable Democratic overperformance.

The primary outcomes compare legislative margins with prior-presidential and
same-cycle federal baselines. Ontology-v3 signs are retained: +1 is the second
pole named by each family (for example liberty/equality, material generosity,
labor, government direction, or punitive enforcement).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT=Path(__file__).resolve().parents[1]
ELECTIONS=ROOT/"data"/"processed"/"elections"
IDEOLOGY=ROOT/"data"/"processed"/"ideology"
WAR=ROOT/"data"/"processed"/"war"
OUT=ELECTIONS/"validation"
DOC=ROOT/"project_docs"/"model"/"ISSUE_STANCE_DURABLE_OVERPERFORMANCE.md"

FAMILIES={
 "environment_resources":("preservation (+) vs extraction/property priority (-)"),
 "institutional_reform":("democratic reform (+) vs institutional control (-)"),
 "labor_capital":("labor (+) vs capital/management (-)"),
 "market_government_direction":("government direction (+) vs market autonomy (-)"),
 "material_support":("material generosity (+) vs restriction (-)"),
 "order_justice":("punitive enforcement (+) vs rehabilitation/due process (-)"),
 "social_liberty_equality":("liberty/equality (+) vs traditional restriction (-)"),
}
HYPOTHESES=[
 ("IDEO-01","Social traditionalism historically helped Democrats relative to federal baselines.","social_liberty_equality","negative","pre_2008 strongest; weaker after 2008 and 2016","registered"),
 ("IDEO-02","Economic material generosity can coexist with social traditionalism and independently predict overperformance.","material_support","positive","joint social/economic model","registered"),
 ("IDEO-03","Labor alignment historically helped Democratic candidates.","labor_capital","positive","pre_2016 strongest","registered_underpowered"),
 ("IDEO-04","Punitive law-and-order positioning improves fit in majority-white and federally Republican districts.","order_justice","positive","majority-white / federal R interaction","registered"),
 ("IDEO-05","Market autonomy improves Democratic fit in conservative districts, separately from material support.","market_government_direction","negative","federal R interaction","registered_underpowered"),
 ("IDEO-06","Extraction/property priority improves rural-conservative fit.","environment_resources","negative","federal R proxy; rural measure pending","registered"),
 ("IDEO-07","Issue congruence is more important than a universal moderation score.","all families","interaction","majority-white and federal-partisanship interactions","registered"),
 ("IDEO-08","Ideological advantages attenuate after the 2008 and 2016 nationalization steps.","all families","attenuation","era-stratified estimates","registered"),
 ("IDEO-09","Socially traditional and economically supportive Democrats form the strongest historical bundle.","social_liberty_equality + material_support","negative social / positive support","joint model and quadrant comparison","registered"),
 ("IDEO-10","The same issue signals predict durable multi-cycle rather than one-cycle overperformance.","all families","same direction","repeat-candidate mean and prospective persistence","registered"),
 ("IDEO-11","Institutional reform affects overperformance.","institutional_reform","unknown","retain null/insufficient result","registered_underpowered"),
]

def panel()->pd.DataFrame:
    ideology=pd.read_csv(ELECTIONS/"canonical_cmo_candidates_with_ideology_v3.csv",low_memory=False)
    ideology=ideology[(ideology.war_eligible.eq(True)) & ideology.canonical_party.eq("D")].rename(columns={"year":"election_year"})
    races=pd.read_csv(WAR/"preliminary_cmo_races.csv",low_memory=False)
    federal=pd.read_csv(ELECTIONS/"historical_federal_district_baselines.csv")
    cmo=pd.read_csv(WAR/"preliminary_cmo_candidates.csv",usecols=["canonical_candidate_id","candidate_cmo_total_oof"])
    keys=["cycle","chamber","district"]
    race_cols=keys+["legislative_dem_margin","prior_pres_dem_margin","nonwhite_share","white_college_share"]
    data=(ideology.drop(columns=[c for c in ["legislative_dem_margin"] if c in ideology])
          .merge(races[race_cols],on=keys,how="left",validate="many_to_one")
          .merge(federal,on=keys,how="left",validate="many_to_one")
          .merge(cmo,on="canonical_candidate_id",how="left",validate="one_to_one"))
    data["presidential_overperformance"]=data.legislative_dem_margin-data.prior_pres_dem_margin
    for base,name in [("federal_index_margin","federal_index_overperformance"),("us_house_dem_margin","us_house_overperformance"),("us_senate_dem_margin","us_senate_overperformance")]:
        data[name]=data.legislative_dem_margin-data[base]
    data["majority_white"]=data.nonwhite_share.lt(.5).astype(int)
    data["federal_republican"]=data.federal_index_margin.lt(0).astype(int)
    data["post_2008"]=data.cycle.ge(2010).astype(int)
    data["post_2016"]=data.cycle.ge(2018).astype(int)
    data["era"]=np.select([data.cycle.le(2006),data.cycle.le(2014)],["pre_2008","2008_2014"],default="post_2016")
    data["incumbent_i"]=data.incumbent.fillna(0).astype(int)
    for cycle in sorted(data.cycle.unique())[1:]: data[f"cycle_{cycle}"]=data.cycle.eq(cycle).astype(int)
    return data

def ols(frame,outcome,family,controls=(),interaction=None,label="bivariate"):
    cols=[outcome,f"ideology_v3_{family}",*controls]+([interaction] if interaction else [])
    d=frame[cols].replace([np.inf,-np.inf],np.nan).dropna().copy()
    result={"outcome":outcome,"family":family,"specification":label,"n":len(d),"people":frame.loc[d.index,"person_id"].nunique()}
    if len(d)<max(12,len(controls)+8) or d[f"ideology_v3_{family}"].nunique()<3:
        result["status"]="underpowered"; return result
    xcols=[f"ideology_v3_{family}",*controls]
    if interaction:
        d["stance_interaction"]=d[f"ideology_v3_{family}"]*d[interaction]
        xcols += [interaction,"stance_interaction"]
    X=np.column_stack([np.ones(len(d)),d[xcols].to_numpy(float)]); y=d[outcome].to_numpy(float)
    inv=np.linalg.pinv(X.T@X); beta=inv@X.T@y; resid=y-X@beta
    lev=np.clip(np.einsum("ij,jk,ik->i",X,inv,X),0,.999999); adj=resid/(1-lev)
    cov=inv@(X.T@(X*adj[:,None]**2))@inv; se=np.sqrt(np.maximum(np.diag(cov),0)); dof=max(len(d)-np.linalg.matrix_rank(X),1)
    tcrit=stats.t.ppf(.975,dof); ratios=np.divide(beta,se,out=np.full_like(beta,np.nan),where=se>0); p=2*stats.t.sf(np.abs(ratios),dof)
    result.update(status="estimated",coefficient=beta[1],hc3_se=se[1],ci_low=beta[1]-tcrit*se[1],ci_high=beta[1]+tcrit*se[1],p_value=p[1],effect_per_stance_sd=beta[1]*d[xcols[0]].std(ddof=1),r_squared=1-(resid@resid)/np.sum((y-y.mean())**2))
    # Candidate-clustered sandwich uncertainty handles repeat observations.
    fallback=pd.Series(frame.loc[d.index].index.astype(str),index=d.index)
    groups=frame.loc[d.index,"person_id"].fillna(fallback).astype(str)
    unique=groups.unique(); meat=np.zeros((X.shape[1],X.shape[1]))
    for group in unique:
        idx=np.flatnonzero(groups.to_numpy()==group); score=X[idx].T@resid[idx]; meat += np.outer(score,score)
    if len(unique)>1:
        correction=(len(unique)/(len(unique)-1))*((len(d)-1)/max(len(d)-X.shape[1],1))
        cluster_cov=correction*inv@meat@inv; cluster_se=np.sqrt(np.maximum(np.diag(cluster_cov),0))
        cluster_ratios=np.divide(beta,cluster_se,out=np.full_like(beta,np.nan),where=cluster_se>0)
        cluster_p=2*stats.t.sf(np.abs(cluster_ratios),len(unique)-1)
        result.update(cluster_people=len(unique),cluster_se=cluster_se[1],cluster_p_value=cluster_p[1])
    if interaction:
        j=xcols.index("stance_interaction")+1
        result.update(interaction=interaction,interaction_coefficient=beta[j],interaction_p_value=p[j])
    return result

def bh(values):
    p=np.asarray(values,float); out=np.full(len(p),np.nan); ok=np.isfinite(p); vals=p[ok]; order=np.argsort(vals); ranked=vals[order]
    adjusted=np.minimum.accumulate((ranked*len(ranked)/np.arange(1,len(ranked)+1))[::-1])[::-1]
    tmp=np.empty(len(vals)); tmp[order]=np.minimum(adjusted,1); out[ok]=tmp; return out

def run():
    data=panel(); outcomes=["presidential_overperformance","federal_index_overperformance","us_house_overperformance","us_senate_overperformance","candidate_cmo_total_oof"]
    cycle_controls=[f"cycle_{cycle}" for cycle in sorted(data.cycle.unique())[1:]]
    estimates=[]
    for outcome in outcomes:
      for family in FAMILIES:
        estimates.append(ols(data,outcome,family,label="bivariate"))
        estimates.append(ols(data,outcome,family,["nonwhite_share","white_college_share","incumbent_i",*cycle_controls],label="context_cycle_adjusted"))
        estimates.append(ols(data,outcome,family,interaction="majority_white",label="majority_white_interaction"))
        estimates.append(ols(data,outcome,family,interaction="federal_republican",label="federal_republican_interaction"))
        estimates.append(ols(data,outcome,family,interaction="post_2008",label="post_2008_interaction"))
        estimates.append(ols(data,outcome,family,interaction="post_2016",label="post_2016_interaction"))
        for era,g in data.groupby("era"):
            estimates.append(ols(g,outcome,family,label=f"era:{era}"))
      estimates.append(ols(data,outcome,"social_liberty_equality",["ideology_v3_material_support"],label="joint_social_material"))
      estimates.append(ols(data,outcome,"material_support",["ideology_v3_social_liberty_equality"],label="joint_social_material"))
      joint_context=["nonwhite_share","white_college_share","incumbent_i",*cycle_controls]
      estimates.append(ols(data,outcome,"social_liberty_equality",["ideology_v3_material_support",*joint_context],label="joint_social_material_context_cycle"))
      estimates.append(ols(data,outcome,"material_support",["ideology_v3_social_liberty_equality",*joint_context],label="joint_social_material_context_cycle"))
    est=pd.DataFrame(estimates)
    primary=est.specification.eq("bivariate") & est.outcome.isin(["presidential_overperformance","federal_index_overperformance"])
    est["primary_bh_q_value"]=np.nan; est.loc[primary,"primary_bh_q_value"]=bh(est.loc[primary,"cluster_p_value"])

    # Candidate-level durability: repeated candidates, averaging observed cycles.
    family_cols=[f"ideology_v3_{x}" for x in FAMILIES]
    durable=(data.groupby(["person_id","canonical_name"],dropna=False)
             .agg(races=("cycle","size"),first_cycle=("cycle","min"),last_cycle=("cycle","max"),
                  presidential_mean=("presidential_overperformance","mean"),federal_mean=("federal_index_overperformance","mean"),
                  federal_positive_share=("federal_index_overperformance",lambda x:(x>0).mean()),federal_sd=("federal_index_overperformance","std"),
                  **{c:(c,"mean") for c in family_cols}).reset_index())
    durable=durable[durable.races.ge(2)].copy()
    durable_est=[]
    renamed=durable.rename(columns={"presidential_mean":"presidential_overperformance","federal_mean":"federal_index_overperformance"})
    for outcome in ["presidential_overperformance","federal_index_overperformance"]:
      for family in FAMILIES: durable_est.append(ols(renamed,outcome,family,label="repeat_candidate_mean"))
    durable_est=pd.DataFrame(durable_est)

    # Prospective persistence after the first cycle with an observed stance.
    future=[]
    for person,g in data.sort_values("cycle").groupby("person_id"):
      if len(g)<2: continue
      for family in FAMILIES:
        col=f"ideology_v3_{family}"; observed=g[g[col].notna()]
        if observed.empty: continue
        first=observed.iloc[0]; later=g[g.cycle.gt(first.cycle)]
        if later.empty: continue
        future.append({"person_id":person,"family":family,"stance":first[col],"stance_cycle":first.cycle,"later_races":len(later),"later_presidential_mean":later.presidential_overperformance.mean(),"later_federal_mean":later.federal_index_overperformance.mean(),"first_presidential":first.presidential_overperformance,"first_federal":first.federal_index_overperformance})
    future=pd.DataFrame(future)

    both=data.dropna(subset=["ideology_v3_social_liberty_equality","ideology_v3_material_support"]).copy()
    both["issue_bundle"]=np.select([
        both.ideology_v3_social_liberty_equality.lt(0)&both.ideology_v3_material_support.ge(0),
        both.ideology_v3_social_liberty_equality.ge(0)&both.ideology_v3_material_support.ge(0),
        both.ideology_v3_social_liberty_equality.lt(0)&both.ideology_v3_material_support.lt(0)],
        ["traditional_supportive","liberty_supportive","traditional_restrictive"],default="liberty_restrictive")
    bundle=(both.groupby("issue_bundle",as_index=False).agg(candidate_cycles=("canonical_candidate_id","size"),people=("person_id","nunique"),
             presidential_mean=("presidential_overperformance","mean"),federal_mean=("federal_index_overperformance","mean"),cmo_mean=("candidate_cmo_total_oof","mean")))

    coverage=[]
    for family in FAMILIES:
      col=f"ideology_v3_{family}"
      coverage.append({"family":family,"description":FAMILIES[family],"candidate_cycles":int(data[col].notna().sum()),"people":int(data.loc[data[col].notna(),"person_id"].nunique()),"repeat_candidate_rows":int(data[data.person_id.isin(durable.person_id)][col].notna().sum()),"prospective_persistence_people":int(future.loc[future.family.eq(family),"person_id"].nunique()) if len(future) else 0})
    registry=pd.DataFrame(HYPOTHESES,columns=["hypothesis_id","hypothesis","focal_dimension","expected_direction","heterogeneity_test","status"])
    conclusions={
      "IDEO-01":("mixed_support","Pooled federal-relative association supports traditionalism, but cycle/context adjustment and era-specific estimates are imprecise."),
      "IDEO-02":("mixed_support","Material generosity is positive only when modeled jointly with social stance; the result disappears with cycle/context controls."),
      "IDEO-03":("insufficient","Labor has only 17 candidate-cycles and no repeat-candidate coverage."),
      "IDEO-04":("mixed_support","Punitive positioning is associated with presidential-relative performance, not robustly with the combined federal baseline."),
      "IDEO-05":("insufficient","Market/government direction has only 10 candidate-cycles."),
      "IDEO-06":("mixed_support","Extraction/property priority has a pooled association, concentrated in 2008-2014 and not robust to cycle/context adjustment."),
      "IDEO-07":("not_yet_supported","Most majority-white and federal-Republican interaction tests are imprecise; no stable general congruence effect is established."),
      "IDEO-08":("directional_only","The social coefficient is smaller after 2016, but formal attenuation interactions are not statistically distinguishable."),
      "IDEO-09":("descriptive_support","Traditional-supportive candidates have the highest raw bundle mean; joint coefficients vanish after cycle/context controls."),
      "IDEO-10":("insufficient","Only 17 repeat people have social scores and only five support a prospective social persistence test."),
      "IDEO-11":("insufficient","Institutional reform has four candidate-cycles."),
    }
    registry["current_result"]=registry.hypothesis_id.map(lambda x:conclusions[x][0])
    registry["result_note"]=registry.hypothesis_id.map(lambda x:conclusions[x][1])
    # Keep this focused valence ledger distinct from the broader IDEO namespace.
    registry["hypothesis_id"]=registry.hypothesis_id.str.replace("IDEO-","VAL-",regex=False)
    OUT.mkdir(parents=True,exist_ok=True)
    data.to_csv(OUT/"issue_stance_durable_panel.csv",index=False); est.to_csv(OUT/"issue_stance_durable_estimates.csv",index=False)
    durable.to_csv(OUT/"issue_stance_durable_candidates.csv",index=False); durable_est.to_csv(OUT/"issue_stance_durable_candidate_estimates.csv",index=False)
    future.to_csv(OUT/"issue_stance_durable_prospective_persistence.csv",index=False); pd.DataFrame(coverage).to_csv(OUT/"issue_stance_durable_coverage.csv",index=False)
    bundle.to_csv(OUT/"issue_stance_durable_bundles.csv",index=False)
    registry.to_csv(OUT/"issue_stance_durable_hypotheses.csv",index=False)
    write_report(data,est,durable,durable_est,future,pd.DataFrame(coverage),registry)
    return data,est,durable,durable_est,future

def write_report(data,est,durable,durable_est,future,coverage,registry):
    def markdown(frame):
        frame=frame.copy().fillna("")
        header="| "+" | ".join(frame.columns)+" |"
        rule="|"+"|".join(["---"]*len(frame.columns))+"|"
        rows=["| "+" | ".join(str(v).replace("|","/") for v in row)+" |" for row in frame.itertuples(index=False,name=None)]
        return "\n".join([header,rule,*rows])
    primary=est[(est.specification=="bivariate")&est.outcome.isin(["presidential_overperformance","federal_index_overperformance"])]
    lines=["# Issue stance and durable overperformance","","Positive family scores always mean the second pole shown below. Estimates are descriptive HC3 regressions among contested Democratic candidates; no missing stance is imputed.","","## Current reading","","- Social traditionalism has the clearest pooled association: the liberty/equality score is associated with 13.8 fewer Democratic overperformance points per full-scale unit against the combined federal baseline (75 candidate-cycles; candidate-clustered p=0.007; primary BH q=0.018). The coefficient shrinks to -5.6 and is not distinguishable from zero after cycle, demographics, and incumbency controls.","- Extraction/property priority has a pooled association of roughly 24 federal-relative points per full-scale move away from preservation (25 candidate-cycles; q=0.042), but it is concentrated in 2008-2014 and disappears with cycle/context controls.","- Punitive law-and-order positioning is associated with presidential-relative overperformance, but the combined-federal estimate is imprecise and has no post-2016 coverage.","- Among the 60 rows with both social and material-support scores, traditionalism and material generosity are independently favorable in the pooled model. Both coefficients disappear after cycle/context controls, so the attractive traditional-supportive bundle remains descriptive rather than predictive.","- Durable evidence is much thinner than cross-sectional evidence: only 17 repeat candidates have social-family scores, and only five can be evaluated prospectively after their first observed stance. Their durable social coefficient points in the expected traditionalist direction but is not precise.","","## Registered hypotheses and cumulative status","",markdown(registry),"","## Coverage","",markdown(coverage),"","## Primary estimates","",markdown(primary[["outcome","family","n","coefficient","ci_low","ci_high","cluster_p_value","primary_bh_q_value","status"]]),"",f"Repeat-candidate panel: {len(durable)} people. Prospective persistence panel: {future.person_id.nunique() if len(future) else 0} people.","","## Interpretation rules","","- Federal-relative outcomes are primary because the hypothesis concerns durable local performance beyond national partisanship.","- Era and district-fit interactions are exploratory and must not be promoted from p-values alone.","- Candidate-level means describe durability but can select on rerunning, winning, and contest entry.","- Later legislative evidence is not allowed to leak backward; the prospective persistence table starts at the first election-cycle-specific observed stance.","- Families with fewer than 12 usable observations are reported as underpowered."]
    DOC.write_text("\n".join(lines)+"\n",encoding="utf-8")

if __name__=="__main__":
    data,est,durable,durable_est,future=run()
    print("panel",len(data),"repeat people",len(durable),"future people",future.person_id.nunique() if len(future) else 0)
    print(est[(est.specification=="bivariate")&est.outcome.isin(["presidential_overperformance","federal_index_overperformance"])][["outcome","family","n","coefficient","p_value","primary_bh_q_value","status"]].to_string(index=False))
