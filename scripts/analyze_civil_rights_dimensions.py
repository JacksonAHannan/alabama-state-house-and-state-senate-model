"""Decompose the legacy civil/social-liberty axis into substantive domains."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from analyze_issue_stance_durable_overperformance import panel as base_panel
from run_issue_stance_tournament import estimate, bh

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
OUT = ROOT / "data" / "processed" / "elections" / "validation"
DOC = ROOT / "project_docs" / "model" / "CIVIL_RIGHTS_DIMENSIONS.md"


def classify(row: pd.Series) -> tuple[str | None, float]:
    key, text = str(row.policy_key).lower(), str(row.source_text).lower()
    joined = f"{key} {text}"
    if row.primitive_axis == "abortion_access":
        return "abortion_access", 1.0
    if any(x in joined for x in ("same_sex", "same-sex", "sexual_orientation", "gender_identity", " gay", "lesbian", "lgbt")):
        return "christian_sexual_morality", -1.0
    if any(x in joined for x in ("affirmative_action", "confederate", "racial discrimination", "racial equality", "civil rights", "black voters")):
        return "racial_civil_rights", 1.0
    if "abstinence" in joined:
        return "christian_sexual_morality", 1.0
    if any(x in joined for x in ("comprehensive_sex_education", "contraceptives", "hiv/std prevention")):
        return "christian_sexual_morality", -1.0
    if any(x in joined for x in ("sex toy", "sexual device", "obscenity", "nude entertainment")):
        return "christian_sexual_morality", -1.0
    if any(x in joined for x in ("smoking ban", "require vaccination", "vaccine mandate")):
        return "public_health_authority", 1.0
    if "stem_cell" in joined or "stem cell" in joined:
        return "abortion_access", 1.0
    return None, 1.0


def markdown(frame: pd.DataFrame) -> str:
    f = frame.fillna("").astype(str)
    return "\n".join(["| " + " | ".join(f.columns) + " |", "|" + "|".join(["---"]*len(f.columns)) + "|",
                      *["| " + " | ".join(r) + " |" for r in f.to_numpy()]])


def main() -> None:
    evidence = pd.read_csv(IDEOLOGY / "candidate_position_evidence_v3_all_sources.csv", low_memory=False)
    scope = evidence.primitive_axis.isin(["civil_social_liberty", "anti_discrimination", "marriage_equality", "confederate_commemoration", "abortion_access"])
    evidence = evidence[scope & evidence.temporal_model_eligible.fillna(False)].copy()
    classified = evidence.apply(classify, axis=1, result_type="expand")
    evidence[["civil_dimension", "orientation"]] = classified
    evidence["position_value"] = pd.to_numeric(evidence.position_value, errors="coerce") * evidence.orientation
    evidence["evidence_weight"] = pd.to_numeric(evidence.evidence_weight, errors="coerce").fillna(1)
    classified = evidence.dropna(subset=["canonical_candidate_id", "civil_dimension", "position_value"]).copy()
    classified["weighted"] = classified.position_value * classified.evidence_weight
    scores = (classified.groupby(["canonical_candidate_id", "civil_dimension"], as_index=False)
              .agg(weighted=("weighted", "sum"), weight=("evidence_weight", "sum"),
                   evidence_records=("evidence_id", "nunique"), source_types=("source_type", "nunique")))
    scores["stance"] = scores.weighted / scores.weight
    panel = base_panel().merge(scores, on="canonical_candidate_id", how="inner")
    panel["senate_i"] = panel.chamber.astype(str).str.lower().eq("senate").astype(int)
    cycle_controls = [c for c in panel if c.startswith("cycle_")]
    rows=[]
    for dimension, group in panel.groupby("civil_dimension"):
        for outcome in ["federal_index_overperformance", "presidential_overperformance"]:
            rows.append({"civil_dimension":dimension, **estimate(group,outcome,"pooled")})
            rows.append({"civil_dimension":dimension, **estimate(group,outcome,"total_association",["nonwhite_share","white_college_share","senate_i",*cycle_controls])})
            rows.append({"civil_dimension":dimension, **estimate(group,outcome,"incumbency_decomposition",["nonwhite_share","white_college_share","senate_i","incumbent_i",*cycle_controls])})
            for era, era_group in group.groupby("era"):
                rows.append({"civil_dimension":dimension, **estimate(era_group,outcome,f"era:{era}")})
    results=pd.DataFrame(rows); results["bh_q_value"]=np.nan
    for outcome in results.outcome.unique():
        for spec in results.specification.unique():
            mask=results.outcome.eq(outcome)&results.specification.eq(spec); results.loc[mask,"bh_q_value"]=bh(results.loc[mask,"p_value"])
    coverage=(classified.groupby("civil_dimension",as_index=False).agg(evidence_records=("evidence_id","nunique"),candidates=("canonical_candidate_id","nunique"),cycles=("election_cycle","nunique"),sources=("source_type","nunique")))
    scores.to_csv(OUT/"civil_rights_candidate_scores.csv",index=False); panel.to_csv(OUT/"civil_rights_overperformance_panel.csv",index=False)
    results.to_csv(OUT/"civil_rights_overperformance_estimates.csv",index=False); coverage.to_csv(OUT/"civil_rights_coverage.csv",index=False)
    primary=results[(results.outcome.eq("federal_index_overperformance"))&results.specification.eq("total_association")]
    DOC.write_text("\n".join(["# Decomposed civil-rights dimensions","","The legacy `civil_social_liberty` score is retired. Social evidence is collapsed into two interpretable caucus dimensions: `christian_sexual_morality` and `racial_civil_rights`. Embryonic stem-cell research is incorporated into `abortion_access` rather than treated as a separate civil-liberty axis.","","Christian sexual morality is positive for traditional marriage, abstinence-centered education, and regulation of sexual conduct; it is negative for LGBTQ+ equality, comprehensive sex education, and private-adult sexual autonomy. Racial civil rights is positive for affirmative action, racial equality, anti-discrimination, and removal of Confederate commemoration.","","## Coverage","",markdown(coverage),"","## Federal-baseline total associations","",markdown(primary[["civil_dimension","n","coefficient","ci_low","ci_high","p_value","bh_q_value","status"]]),"","Childcare, Head Start, and at-risk-youth spending are excluded and belong in material-support or education dimensions."])+"\n",encoding="utf-8")
    print(primary[["civil_dimension","n","coefficient","ci_low","ci_high","bh_q_value","status"]].to_string(index=False))


if __name__=="__main__": main()
