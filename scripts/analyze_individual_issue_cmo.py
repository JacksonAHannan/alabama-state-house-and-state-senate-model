"""Estimate issue-specific associations with Democratic candidate-strength CMO."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from analyze_social_moderation_cmo import ols_hc3
from ideology_ontology_v3 import PRIMITIVES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "cmo_ideology" / "individual_issues"
MIN_N = 15


def assemble() -> pd.DataFrame:
    scores = pd.read_csv(ROOT / "data" / "processed" / "war" / "preliminary_cmo_candidates.csv")
    roster = pd.read_csv(ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv")
    positions = pd.read_csv(
        ROOT / "data" / "processed" / "ideology" / "candidate_issue_valence_v3.csv")
    # A small number of candidate/issues have separate source-layer rows due to
    # historical person/name variants. Collapse them at the canonical candidate
    # key so no candidate is counted twice and no source is chosen arbitrarily.
    positions["weighted_valence"] = positions.issue_valence * positions.absolute_evidence_weight
    positions = (positions.groupby(["canonical_candidate_id", "primitive_axis"], as_index=False)
                 .agg(weighted_valence=("weighted_valence", "sum"),
                      absolute_evidence_weight=("absolute_evidence_weight", "sum"),
                      evidence_records=("evidence_records", "sum")))
    positions["issue_valence"] = positions.weighted_valence / positions.absolute_evidence_weight
    base = (scores[scores.party.eq("D")][["canonical_candidate_id", "candidate_cmo_total_oof"]]
            .merge(roster[["canonical_candidate_id", "person_id", "canonical_name", "year", "chamber"]],
                   on="canonical_candidate_id", how="left", validate="one_to_one")
            .rename(columns={"candidate_cmo_total_oof": "cmo"}))
    return base.merge(positions, on="canonical_candidate_id", how="inner", validate="one_to_many")


def estimate(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for issue, group in data.groupby("primitive_axis"):
        minority_value_n = len(group) - int(group.issue_valence.value_counts().max())
        if len(group) < MIN_N or group.issue_valence.nunique() < 2 or minority_value_n < 5:
            continue
        continuous, diag = ols_hc3(group.rename(columns={"issue_valence": "stance"}),
                                   ["stance"], ["year", "chamber"])
        effect = continuous[continuous.term.eq("stance")].iloc[0]
        contrasted = group[group.issue_valence.abs().gt(.15)].copy()
        contrasted["supports_positive_pole"] = contrasted.issue_valence.gt(.15).astype(int)
        contrast_n = len(contrasted)
        contrast = None
        pole_counts = contrasted.supports_positive_pole.value_counts()
        if contrast_n >= MIN_N and len(pole_counts) == 2 and pole_counts.min() >= 5:
            table, _ = ols_hc3(contrasted, ["supports_positive_pole"], ["year", "chamber"])
            contrast = table[table.term.eq("supports_positive_pole")].iloc[0]
        positive_pole, negative_pole = PRIMITIVES.get(issue, ("positive", "negative"))
        rows.append({
            "primitive_axis": issue, "negative_pole": negative_pole, "positive_pole": positive_pole,
            "n": diag["n"], "candidates": group.canonical_candidate_id.nunique(),
            "minority_value_n": minority_value_n,
            "continuous_estimate": effect.estimate, "continuous_se": effect.std_error,
            "continuous_p": effect.p_value, "continuous_ci_low": effect.ci_low,
            "continuous_ci_high": effect.ci_high, "contrast_n": contrast_n,
            "positive_vs_negative_estimate": contrast.estimate if contrast is not None else np.nan,
            "positive_vs_negative_se": contrast.std_error if contrast is not None else np.nan,
            "positive_vs_negative_p": contrast.p_value if contrast is not None else np.nan,
        })
    result = pd.DataFrame(rows).sort_values("continuous_p").reset_index(drop=True)
    if not result.empty:
        rank = np.arange(1, len(result) + 1)
        result["continuous_bh_q"] = np.minimum.accumulate(
            (result.continuous_p.to_numpy() * len(result) / rank)[::-1])[::-1].clip(max=1)
        valid = result.positive_vs_negative_p.notna()
        ordered = result.loc[valid].sort_values("positive_vs_negative_p")
        if len(ordered):
            q = np.minimum.accumulate(
                (ordered.positive_vs_negative_p.to_numpy() * len(ordered) /
                 np.arange(1, len(ordered) + 1))[::-1])[::-1].clip(max=1)
            result.loc[ordered.index, "contrast_bh_q"] = q
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sample = assemble()
    results = estimate(sample)
    sample.to_csv(OUT / "individual_issue_analysis_sample.csv", index=False)
    results.to_csv(OUT / "individual_issue_cmo_results.csv", index=False)
    significant = results[results.continuous_bh_q.le(.10)]
    summary = ["# Individual issue associations with Democratic CMO", "",
               f"Tested **{len(results)} issues** with at least {MIN_N} observed candidate-cycles. "
               "Each model adjusts for election cycle and chamber and uses HC3 robust uncertainty. "
               "Positive estimates mean movement toward the named positive pole is associated with "
               "higher selection-aware CMO.", "",
               f"**{len(significant)} issues** clear a 10% Benjamini-Hochberg false-discovery-rate threshold.", "",
               "The screen is observational and exploratory. Missing issue positions remain missing; "
               "they are not coded as neutral."]
    (OUT / "INDIVIDUAL_ISSUE_CMO_ANALYSIS.md").write_text("\n".join(summary), encoding="utf-8")
    print(results.to_string(index=False))


if __name__ == "__main__":
    main()
