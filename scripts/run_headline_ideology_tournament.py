"""Collapse detailed issue evidence into nine interpretable headline dimensions."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from analyze_issue_stance_durable_overperformance import panel as base_panel
from run_issue_stance_tournament import estimate, bh

ROOT=Path(__file__).resolve().parents[1]
IDEOLOGY=ROOT/"data"/"processed"/"ideology"; VALID=ROOT/"data"/"processed"/"elections"/"validation"
DOC=ROOT/"project_docs"/"model"/"HEADLINE_IDEOLOGY_TOURNAMENT.md"

# Every sign orients the raw primitive toward the named positive pole.
DIMENSIONS={
 "social_traditionalism":{"christian_sexual_morality":1,"abortion_access":-1},
 "racial_and_political_equality":{"racial_civil_rights":1,"voting_access":1},
 "gun_rights":{"gun_access":1,"gun_purchase_regulation":-1},
 "punitive_law_and_order":{"criminal_punishment":1,"incarceration":1,"police_authority":1,"due_process":-1,"drug_criminalization":1},
 "labor_power":{"labor_rights":1,"labor_capital_alignment":1,"public_employee_compensation":1},
 "material_redistribution":{"welfare_generosity":1,"welfare_conditionality":-1},
 "public_services":{"education_public_funding":1,"healthcare_access":1,"childcare_support":1,"education_accountability":1},
 "market_and_development_autonomy":{"market_governance":-1,"education_market_choice":1,"resource_development":1,"environmental_protection":-1,"renewable_energy_support":-1},
 "institutional_democratic_reform":{"campaign_finance_restrictions":1,"institutional_populism":1},
}
POLES={
 "social_traditionalism":("traditional Christian and abortion-restrictive","social and reproductive autonomy"),
 "racial_and_political_equality":("expand racial and voting equality","restrict or preserve status quo"),
 "gun_rights":("expand gun rights","strengthen gun restrictions"),
 "punitive_law_and_order":("punitive enforcement","rehabilitation and due process"),
 "labor_power":("expand labor power","favor management and restrict labor"),
 "material_redistribution":("expand unconditional material support","restrict or condition support"),
 "public_services":("expand public services","reduce public provision"),
 "market_and_development_autonomy":("market, choice, and development autonomy","government direction and preservation"),
 "institutional_democratic_reform":("expand popular control and campaign regulation","institutional control and fewer restrictions"),
}

def build_scores():
    issue=pd.read_csv(IDEOLOGY/"candidate_issue_valence_v3_adjudicated.csv",low_memory=False)
    raw=issue.pivot_table(index="canonical_candidate_id",columns="primitive_axis",values="adjudicated_issue_valence",aggfunc="first")
    civil=pd.read_csv(VALID/"civil_rights_candidate_scores.csv").pivot_table(index="canonical_candidate_id",columns="civil_dimension",values="stance",aggfunc="first")
    # The reviewed derived dimensions supersede legacy abortion/civil aggregates.
    for col in civil: raw[col]=civil[col].combine_first(raw[col] if col in raw else pd.Series(index=raw.index,dtype=float))
    rows=[]
    for dimension,components in DIMENSIONS.items():
        cols=[]
        for axis,sign in components.items():
            if axis in raw: cols.append(raw[axis]*sign)
        if not cols: continue
        matrix=pd.concat(cols,axis=1)
        score=matrix.mean(axis=1,skipna=True)
        observed=matrix.notna().sum(axis=1)
        for candidate in score[score.notna()].index:
            rows.append({"canonical_candidate_id":candidate,"headline_dimension":dimension,"stance":score[candidate],
                         "components_observed":int(observed[candidate]),"components_available":len(components)})
    return pd.DataFrame(rows)

def markdown(frame):
    f=frame.fillna("").astype(str); return "\n".join(["| "+" | ".join(f.columns)+" |","|"+"|".join(["---"]*len(f.columns))+"|",*["| "+" | ".join(r)+" |" for r in f.to_numpy()]])

def main():
    scores=build_scores(); panel=base_panel().merge(scores,on="canonical_candidate_id",how="inner")
    panel["senate_i"]=panel.chamber.astype(str).str.lower().eq("senate").astype(int); cycles=[c for c in panel if c.startswith("cycle_")]
    rows=[]
    for dimension,g in panel.groupby("headline_dimension"):
      for outcome in ["federal_index_overperformance","presidential_overperformance"]:
        rows.append({"headline_dimension":dimension,**estimate(g,outcome,"pooled")})
        rows.append({"headline_dimension":dimension,**estimate(g,outcome,"total_association",["nonwhite_share","white_college_share","senate_i",*cycles])})
        rows.append({"headline_dimension":dimension,**estimate(g,outcome,"incumbency_decomposition",["nonwhite_share","white_college_share","senate_i","incumbent_i",*cycles])})
        for era,eg in g.groupby("era"): rows.append({"headline_dimension":dimension,**estimate(eg,outcome,f"era:{era}")})
    results=pd.DataFrame(rows); results["bh_q_value"]=np.nan
    for outcome in results.outcome.unique():
      for spec in ["pooled","total_association","incumbency_decomposition"]:
        mask=results.outcome.eq(outcome)&results.specification.eq(spec); results.loc[mask,"bh_q_value"]=bh(results.loc[mask,"p_value"])
    coverage=(panel.groupby("headline_dimension",as_index=False).agg(candidate_cycles=("canonical_candidate_id","nunique"),people=("person_id","nunique"),cycles=("cycle","nunique"),mean_components=("components_observed","mean")))
    coverage["positive_pole"]=coverage.headline_dimension.map(lambda x:POLES[x][0]); coverage["negative_pole"]=coverage.headline_dimension.map(lambda x:POLES[x][1])
    scores.to_csv(VALID/"headline_ideology_candidate_scores.csv",index=False); panel.to_csv(VALID/"headline_ideology_panel.csv",index=False)
    results.to_csv(VALID/"headline_ideology_estimates.csv",index=False); coverage.to_csv(VALID/"headline_ideology_coverage.csv",index=False)
    primary=results[(results.outcome.eq("federal_index_overperformance"))&results.specification.eq("total_association")]
    DOC.write_text("\n".join(["# Headline ideology tournament","","Nine headline dimensions replace the flat issue menu. Gun rights and punitive law-and-order are intentionally separate. Tax incidence remains a drill-down and is not averaged into a single tax score.","","A score is the mean of available oriented components. This maximizes coverage but `components_observed` must remain visible because a one-component score is less comprehensive than a multi-component score.","","## Definitions","",markdown(pd.DataFrame([{"headline_dimension":d,"positive_pole":p[0],"negative_pole":p[1],"components":", ".join(DIMENSIONS[d])} for d,p in POLES.items()])),"","## Coverage","",markdown(coverage),"","## Federal-baseline total associations","",markdown(primary[["headline_dimension","n","coefficient","ci_low","ci_high","p_value","bh_q_value","status"]])])+"\n",encoding="utf-8")
    print(primary[["headline_dimension","n","coefficient","ci_low","ci_high","bh_q_value","status"]].to_string(index=False))

if __name__=="__main__": main()
