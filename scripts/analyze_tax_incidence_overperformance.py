"""Split the overbroad tax-burden axis by who or what bears the tax."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from analyze_issue_stance_durable_overperformance import panel as base_panel
from run_issue_stance_tournament import estimate, bh

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
OUT = ROOT / "data" / "processed" / "elections" / "validation"
DOC = ROOT / "project_docs" / "model" / "TAX_INCIDENCE_OVERPERFORMANCE.md"


def markdown(frame: pd.DataFrame) -> str:
    values = frame.fillna("").astype(str)
    return "\n".join(["| " + " | ".join(values.columns) + " |",
                      "|" + "|".join(["---"] * len(values.columns)) + "|",
                      *["| " + " | ".join(row) + " |" for row in values.to_numpy()]])


def classify(row: pd.Series) -> str | None:
    key = str(row.policy_key).lower()
    text = f"{key} {row.source_text}".lower()
    if any(x in text for x in ("grocery", "groceries", "sales tax on food", "food tax")):
        return "grocery_sales_tax"
    if any(x in text for x in ("tax_sales", "sales taxes", "general sales tax")):
        return "general_sales_tax"
    if any(x in text for x in ("tax_cigarette", "tax_alcohol", "tax_gasoline", "cigarette tax", "alcohol tax", "gasoline tax", "fuel tax", "tobacco tax")):
        return "excise_and_fuel_tax"
    if any(x in text for x in ("tax_corporate", "corporate tax", "business privilege", "business tax", "corporation")):
        return "corporate_and_business_tax"
    if any(x in text for x in ("tax_capital_gains", "tax_income_upper", "capital gains", "upper-income", "wealth tax", "estate tax", "wealthy")):
        return "upper_income_and_wealth_tax"
    if any(x in text for x in ("tax_income_lower", "individual income tax", "personal income tax", "income taxes below")):
        return "personal_income_tax"
    if any(x in text for x in ("tax_property", "property tax", "ad valorem")):
        return "property_tax"
    return None


def main() -> None:
    evidence = pd.read_csv(IDEOLOGY / "candidate_position_evidence_v3_all_sources.csv", low_memory=False)
    evidence = evidence[evidence.primitive_axis.eq("tax_burden") & evidence.temporal_model_eligible.fillna(False)].copy()
    evidence["tax_dimension"] = evidence.apply(classify, axis=1)
    evidence["position_value"] = pd.to_numeric(evidence.position_value, errors="coerce")
    evidence["evidence_weight"] = pd.to_numeric(evidence.evidence_weight, errors="coerce").fillna(1)
    classified = evidence.dropna(subset=["canonical_candidate_id", "tax_dimension", "position_value"]).copy()
    classified["weighted"] = classified.position_value * classified.evidence_weight
    scores = (classified.groupby(["canonical_candidate_id", "tax_dimension"], as_index=False)
              .agg(weighted=("weighted", "sum"), weight=("evidence_weight", "sum"),
                   evidence_records=("evidence_id", "nunique"), source_types=("source_type", "nunique")))
    scores["stance"] = scores.weighted / scores.weight

    panel = base_panel().merge(scores, on="canonical_candidate_id", how="inner")
    panel["senate_i"] = panel.chamber.astype(str).str.lower().eq("senate").astype(int)
    cycle_controls = [c for c in panel if c.startswith("cycle_")]
    rows = []
    for dimension, group in panel.groupby("tax_dimension"):
        for outcome in ["federal_index_overperformance", "presidential_overperformance"]:
            rows.append({"tax_dimension": dimension, **estimate(group, outcome, "pooled")})
            rows.append({"tax_dimension": dimension, **estimate(group, outcome, "total_association",
                         ["nonwhite_share", "white_college_share", "senate_i", *cycle_controls])})
            rows.append({"tax_dimension": dimension, **estimate(group, outcome, "incumbency_decomposition",
                         ["nonwhite_share", "white_college_share", "senate_i", "incumbent_i", *cycle_controls])})
    results = pd.DataFrame(rows)
    results["bh_q_value"] = np.nan
    for outcome in results.outcome.unique():
        for spec in results.specification.unique():
            mask = results.outcome.eq(outcome) & results.specification.eq(spec)
            results.loc[mask, "bh_q_value"] = bh(results.loc[mask, "p_value"])

    coverage = (classified.groupby("tax_dimension", as_index=False)
                .agg(evidence_records=("evidence_id", "nunique"), candidates=("canonical_candidate_id", "nunique"),
                     cycles=("election_cycle", "nunique"), sources=("source_type", "nunique")))
    excluded = evidence[evidence.tax_dimension.isna()]
    OUT.mkdir(parents=True, exist_ok=True)
    scores.to_csv(OUT / "tax_incidence_candidate_scores.csv", index=False)
    panel.to_csv(OUT / "tax_incidence_overperformance_panel.csv", index=False)
    results.to_csv(OUT / "tax_incidence_overperformance_estimates.csv", index=False)
    coverage.to_csv(OUT / "tax_incidence_coverage.csv", index=False)
    summary = results[(results.outcome.eq("federal_index_overperformance")) &
                      (results.specification.eq("total_association"))]
    lines = ["# Tax incidence and Democratic overperformance", "",
             "The former `tax_burden` axis is not substantively coherent: lowering a grocery sales tax and lowering a corporate or upper-income tax have different distributive meanings. This audit separates only evidence whose tax base can be identified; generic tax and budget votes remain unclassified.", "",
             f"Classified {len(classified):,} of {len(evidence):,} temporally eligible tax-burden evidence rows. The remainder are retained in source data but excluded from incidence estimates.", "", "## Coverage", "",
             markdown(coverage), "", "## Federal-baseline total associations", "",
             markdown(summary[["tax_dimension", "n", "coefficient", "ci_low", "ci_high", "p_value", "bh_q_value", "status"]]), "",
             "Positive coefficients mean that supporting an increase in that named tax base is associated with more Democratic legislative overperformance. Negative coefficients mean tax reduction is associated with more overperformance. These are descriptive total associations; they do not establish that changing a tax position causes the electoral result."]
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary[["tax_dimension", "n", "coefficient", "ci_low", "ci_high", "bh_q_value", "status"]].to_string(index=False))


if __name__ == "__main__":
    main()
