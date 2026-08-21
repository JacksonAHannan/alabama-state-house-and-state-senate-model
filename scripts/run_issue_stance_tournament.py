"""Comprehensive adjudicated issue-position tournament for Democratic CMO research."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

from analyze_issue_stance_durable_overperformance import panel as build_base_panel
from ideology_ontology_v3 import PRIMITIVES

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"data"/"processed"/"elections"/"validation"
IDEOLOGY=ROOT/"data"/"processed"/"ideology"; DOC=ROOT/"project_docs"/"model"/"ISSUE_STANCE_TOURNAMENT.md"
MIN_PRIMARY=20; MIN_SUBGROUP=15

def estimate(frame,outcome,label,controls=(),interaction=None):
    cols=[outcome,"stance",*controls]+([interaction] if interaction else [])
    d=frame[cols].replace([np.inf,-np.inf],np.nan).dropna().copy()
    result={"n":len(d),"people":frame.loc[d.index,"person_id"].nunique(),"outcome":outcome,"specification":label}
    if len(d)<max(MIN_SUBGROUP,len(controls)+8) or d.stance.nunique()<2:
        return result|{"status":"underpowered"}
    xcols=["stance",*controls]
    if interaction:
        d["stance_interaction"]=d.stance*d[interaction]; xcols += [interaction,"stance_interaction"]
    X=np.column_stack([np.ones(len(d)),d[xcols].to_numpy(float)]); y=d[outcome].to_numpy(float)
    inv=np.linalg.pinv(X.T@X); beta=inv@X.T@y; resid=y-X@beta
    groups=frame.loc[d.index,"person_id"].fillna(pd.Series(d.index.astype(str),index=d.index)).astype(str)
    meat=np.zeros_like(inv)
    for group in groups.unique():
        idx=np.flatnonzero(groups.to_numpy()==group); score=X[idx].T@resid[idx]; meat+=np.outer(score,score)
    g=groups.nunique(); correction=(g/(g-1))*((len(d)-1)/max(len(d)-X.shape[1],1)) if g>1 else 1
    cov=correction*inv@meat@inv; se=np.sqrt(np.maximum(np.diag(cov),0)); ratio=np.divide(beta,se,out=np.full_like(beta,np.nan),where=se>0)
    p=2*stats.t.sf(np.abs(ratio),max(g-1,1)); tcrit=stats.t.ppf(.975,max(g-1,1))
    result|={"status":"estimated","coefficient":beta[1],"cluster_se":se[1],"ci_low":beta[1]-tcrit*se[1],"ci_high":beta[1]+tcrit*se[1],"p_value":p[1],"effect_per_stance_sd":beta[1]*d.stance.std(ddof=1),"r_squared":1-(resid@resid)/np.sum((y-y.mean())**2)}
    if interaction:
        j=xcols.index("stance_interaction")+1; result|={"interaction":interaction,"interaction_coefficient":beta[j],"interaction_p_value":p[j]}
    return result

def bh(series):
    p=pd.to_numeric(series,errors="coerce").to_numpy(); out=np.full(len(p),np.nan); ok=np.isfinite(p)
    vals=p[ok]; order=np.argsort(vals); ranked=vals[order]; adj=np.minimum.accumulate((ranked*len(ranked)/np.arange(1,len(ranked)+1))[::-1])[::-1]
    restored=np.empty(len(vals)); restored[order]=np.minimum(adj,1); out[ok]=restored; return out

def build_panel():
    base=build_base_panel()
    issues=pd.read_csv(IDEOLOGY/"candidate_issue_valence_v3_adjudicated.csv",low_memory=False).rename(columns={"adjudicated_issue_valence":"stance"})
    data=base.merge(issues[["canonical_candidate_id","primitive_axis","stance","adjudication_status","controlling_source_types","controlling_records","post_adjudication_conflict_ratio"]],on="canonical_candidate_id",how="inner",validate="one_to_many")
    data["positive_pole"]=data.primitive_axis.map(lambda x:PRIMITIVES.get(x,("unknown",))[0])
    data["negative_pole"]=data.primitive_axis.map(lambda x:PRIMITIVES.get(x,(None,"unknown"))[1])
    data["senate_i"]=(data.chamber.astype(str).str.lower()=="senate").astype(int)
    return data

def main():
    data=build_panel(); counts=data.groupby("primitive_axis").canonical_candidate_id.nunique(); axes=counts[counts.ge(MIN_PRIMARY)].index.tolist()
    cycle_controls=[c for c in data if c.startswith("cycle_")]
    outcomes=["presidential_overperformance","federal_index_overperformance"]
    rows=[]
    for axis in axes:
      issue=data[data.primitive_axis.eq(axis)].copy()
      source_dummies=pd.get_dummies(issue.controlling_source_types.fillna("unknown"),prefix="source",drop_first=True,dtype=int)
      issue=issue.join(source_dummies)
      source_controls=source_dummies.columns.tolist()
      for outcome in outcomes:
        for spec,controls,interaction in [
          ("pooled",[],None),("cycle_context",["nonwhite_share","white_college_share","incumbent_i",*cycle_controls],None),
          ("total_association",["nonwhite_share","white_college_share","senate_i",*cycle_controls],None),
          ("cycle_context_source",["nonwhite_share","white_college_share","incumbent_i","post_adjudication_conflict_ratio",*cycle_controls,*source_controls],None),
          ("majority_white_interaction",[],"majority_white"),("federal_republican_interaction",[],"federal_republican"),
          ("post_2008_interaction",[],"post_2008"),("post_2016_interaction",[],"post_2016")]:
            rows.append({"primitive_axis":axis,**estimate(issue,outcome,spec,controls,interaction)})
        for era,g in issue.groupby("era"):
            rows.append({"primitive_axis":axis,**estimate(g,outcome,f"era:{era}")})
        for source,g in issue.groupby("controlling_source_types"):
            if len(g)>=MIN_SUBGROUP: rows.append({"primitive_axis":axis,**estimate(g,outcome,f"source:{source}")})
    estimates=pd.DataFrame(rows)
    estimates["bh_q_value"]=np.nan
    for outcome in outcomes:
      for spec in ["pooled","total_association","cycle_context","cycle_context_source"]:
        mask=estimates.outcome.eq(outcome)&estimates.specification.eq(spec)
        estimates.loc[mask,"bh_q_value"]=bh(estimates.loc[mask,"p_value"])

    # Compact issue verdict: require direction stability; distinguish pooled discovery from adjusted evidence.
    piv=estimates[estimates.specification.isin(["pooled","total_association","cycle_context","cycle_context_source"])].pivot_table(index=["primitive_axis","outcome"],columns="specification",values=["coefficient","bh_q_value","n"],aggfunc="first").reset_index()
    piv.columns=["_".join([str(x) for x in col if x]) if isinstance(col,tuple) else col for col in piv.columns]
    piv["cycles"]=piv.primitive_axis.map(data.groupby("primitive_axis").cycle.nunique())
    same_total=np.sign(piv.coefficient_pooled)==np.sign(piv.coefficient_total_association)
    piv["evidence_grade"]=np.select([same_total&piv.cycles.ge(3)&piv.bh_q_value_pooled.lt(.1)&piv.bh_q_value_total_association.lt(.1),piv.bh_q_value_pooled.lt(.1),same_total],["total_association_signal","pooled_only","directional"],default="null_or_unstable")

    # Repeat-candidate descriptive durability and strictly future persistence.
    durable=(data.groupby(["person_id","primitive_axis"],as_index=False).agg(candidate_cycles=("cycle","nunique"),stance=("stance","mean"),federal_mean=("federal_index_overperformance","mean"),presidential_mean=("presidential_overperformance","mean")))
    durable=durable[durable.candidate_cycles.ge(2)]
    future=[]
    for (person,axis),g in data.sort_values("cycle").groupby(["person_id","primitive_axis"]):
        if g.cycle.nunique()<2: continue
        first=g.iloc[0]; later=g[g.cycle.gt(first.cycle)]
        if later.empty: continue
        future.append({"person_id":person,"primitive_axis":axis,"stance_cycle":first.cycle,"stance":first.stance,"later_races":later.cycle.nunique(),"first_federal":first.federal_index_overperformance,"first_presidential":first.presidential_overperformance,"later_federal_mean":later.federal_index_overperformance.mean(),"later_presidential_mean":later.presidential_overperformance.mean()})
    future=pd.DataFrame(future)

    durability=[]
    for axis,g in durable.groupby("primitive_axis"):
        renamed=g.rename(columns={"federal_mean":"federal_index_overperformance","presidential_mean":"presidential_overperformance"})
        for outcome in outcomes: durability.append({"primitive_axis":axis,"durability_test":"repeat_candidate_mean",**estimate(renamed,outcome,"repeat_candidate_mean")})
    for axis,g in future.groupby("primitive_axis"):
        renamed=g.rename(columns={"later_federal_mean":"federal_index_overperformance","later_presidential_mean":"presidential_overperformance"})
        durability.append({"primitive_axis":axis,"durability_test":"future_federal_bivariate",**estimate(renamed,"federal_index_overperformance","future_bivariate")})
        durability.append({"primitive_axis":axis,"durability_test":"future_federal_first_performance_adjusted",**estimate(renamed,"federal_index_overperformance","future_first_adjusted",["first_federal"])})
    durability=pd.DataFrame(durability)

    coverage=(data.groupby("primitive_axis",as_index=False).agg(candidate_cycles=("canonical_candidate_id","nunique"),people=("person_id","nunique"),cycles=("cycle","nunique"),source_patterns=("controlling_source_types","nunique"),mean_conflict=("post_adjudication_conflict_ratio","mean"),positive_pole=("positive_pole","first"),negative_pole=("negative_pole","first")))
    coverage["primary_eligible"]=coverage.candidate_cycles.ge(MIN_PRIMARY)
    coverage=coverage.merge(durable.groupby("primitive_axis").person_id.nunique().rename("repeat_people"),on="primitive_axis",how="left").merge(future.groupby("primitive_axis").person_id.nunique().rename("future_people"),on="primitive_axis",how="left").fillna({"repeat_people":0,"future_people":0})
    OUT.mkdir(parents=True,exist_ok=True)
    data.to_csv(OUT/"issue_stance_tournament_panel.csv",index=False); coverage.to_csv(OUT/"issue_stance_tournament_coverage.csv",index=False)
    estimates.to_csv(OUT/"issue_stance_tournament_estimates.csv",index=False); piv.to_csv(OUT/"issue_stance_tournament_verdicts.csv",index=False)
    durable.to_csv(OUT/"issue_stance_tournament_durable_candidates.csv",index=False); future.to_csv(OUT/"issue_stance_tournament_future_persistence.csv",index=False); durability.to_csv(OUT/"issue_stance_tournament_durable_estimates.csv",index=False)
    report(coverage,piv,estimates,durable,future,durability)
    print(piv.sort_values(["outcome","evidence_grade","bh_q_value_pooled"])[["primitive_axis","outcome","coefficient_pooled","bh_q_value_pooled","coefficient_cycle_context_source","bh_q_value_cycle_context_source","evidence_grade"]].to_string(index=False))

def md(frame):
    f=frame.copy().fillna(""); return "\n".join(["| "+" | ".join(f.columns)+" |","|"+"|".join(["---"]*len(f.columns))+"|",*["| "+" | ".join(str(v).replace("|","/") for v in r)+" |" for r in f.itertuples(index=False,name=None)]])

def report(coverage,verdicts,estimates,durable,future,durability):
    ranked=verdicts.sort_values(["outcome","bh_q_value_pooled"],na_position="last")
    federal=ranked[ranked.outcome.eq("federal_index_overperformance")]
    robust=federal[federal.evidence_grade.eq("total_association_signal")]
    durable_ok=durability[durability.status.eq("estimated")]
    axes=", ".join(robust.primitive_axis.tolist()) or "none"
    lines=["# Adjudicated issue-stance tournament","","This tournament uses issue-level adjudications rather than requiring a broad family score. Positive stance values mean the first pole listed in the coverage table. Outcomes are Democratic legislative margin above the indicated federal baseline.","",f"The panel contains {int(coverage.candidate_cycles.max())} candidates on its largest issue and {coverage.primary_eligible.sum()} issues meeting the 20-candidate primary threshold.","","## Current reading","",f"The total-association screen identifies {len(robust)} federal-baseline signals across at least three cycles: {axes}. This specification adjusts only for pre-treatment district demographics, chamber, and cycle; it deliberately preserves pathways through incumbency, fundraising, survival, and prior electoral support.","","Incumbency- and source-adjusted estimates are decomposition and measurement-sensitivity checks, not gates for the total electoral relationship. A coefficient that shrinks there may indicate mediation or limited within-source comparability rather than absence of an electoral advantage.","","Strict future-persistence evidence remains thin because ideology is observed for relatively few candidates before a later race. This is a limitation of the persistence design, not evidence that conservative positioning has no durable value.","","## Verdicts","",md(ranked[["primitive_axis","outcome","cycles","n_pooled","coefficient_pooled","bh_q_value_pooled","coefficient_total_association","bh_q_value_total_association","coefficient_cycle_context_source","bh_q_value_cycle_context_source","evidence_grade"]]),"","## Durability estimates with adequate sample","",md(durable_ok[["primitive_axis","durability_test","n","outcome","coefficient","ci_low","ci_high","p_value"]]),"","## Coverage and pole direction","",md(coverage.sort_values("candidate_cycles",ascending=False)),"","## Guardrails","","- Candidate-clustered uncertainty is used throughout; pooled, total-association, mediator-adjusted, and source-adjusted multiple-testing corrections are separate.","- `total_association_signal` requires at least three cycles and BH q<0.10 in pooled and pre-treatment district-context specifications with the same sign.","- Incumbency, finance, prior performance, and survival are not controlled in the headline estimand because they can transmit ideological fit into electoral performance.","- Ratings, questionnaires, legislative records, and public evidence remain available as measurement-sensitivity estimates rather than causal controls.","- Repeat-candidate means are descriptive and selected on rerunning; strictly future persistence is reported separately.",f"- Repeat-candidate issue profiles: {len(durable)}. Strictly future profiles: {len(future)}."]
    DOC.write_text("\n".join(lines)+"\n",encoding="utf-8")

if __name__=="__main__": main()
