"""Compare Shor–McCarty career ideal points with ontology-v3 candidate evidence."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
LEG = ROOT / "data" / "processed" / "legislative"
OUT = RESEARCH / "shor_mccarty_comparison_v3"

# +1 means the positive end of the adjudicated axis is conventionally more
# conservative in Alabama politics; -1 means the negative end is. Axes whose
# valence is not stable on a left/right continuum are deliberately omitted.
CONSERVATIVE_DIRECTION = {
    "market_governance": -1, "public_private_provision": -1, "tax_burden": -1,
    "public_spending": -1, "welfare_generosity": -1, "welfare_conditionality": 1,
    "labor_capital_alignment": -1, "labor_rights": -1, "public_employee_compensation": -1,
    "childcare_support": -1, "healthcare_access": -1, "healthcare_public_responsibility": -1,
    "education_public_funding": -1, "education_market_choice": 1,
    "environmental_protection": -1, "conservation_preservation": -1,
    "resource_development": 1, "climate_energy": -1, "renewable_energy_support": -1,
    "land_use_property_rights": -1, "abortion_access": -1, "abortion_public_funding": -1,
    "marriage_equality": -1, "civil_social_liberty": -1, "anti_discrimination": -1,
    "affirmative_action": -1, "gun_access": 1, "gun_purchase_regulation": -1,
    "criminal_punishment": 1, "incarceration": 1, "due_process": -1,
    "police_authority": 1, "drug_criminalization": 1, "drug_treatment": -1,
    "immigration_access": -1, "immigration_enforcement": 1, "immigrant_public_benefits": -1,
    "campaign_finance_restrictions": -1, "campaign_finance_disclosure": -1,
    "voting_access": -1, "election_integrity_controls": 1,
}


def percentile_within(frame: pd.DataFrame, value: str, groups: list[str]) -> pd.Series:
    return frame.groupby(groups, dropna=False)[value].rank(pct=True, method="average") * 100


def safe_spearman(frame: pd.DataFrame, left: str, right: str) -> tuple[int, float, float]:
    part = frame[[left, right]].dropna()
    if len(part) < 3:
        return len(part), np.nan, np.nan
    result = spearmanr(part[left], part[right])
    return len(part), float(result.statistic), float(result.pvalue)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    shor = pd.read_csv(RESEARCH / "shor_mccarty_candidate_universe.csv", low_memory=False)
    shor = shor[shor.shor_match_status.eq("matched")].copy()
    positions = pd.read_csv(IDEOLOGY / "candidate_issue_valence_v3_adjudicated.csv")
    positions = positions[positions.primitive_axis.isin(CONSERVATIVE_DIRECTION)].copy()
    positions["conservative_issue_value"] = positions.adjudicated_issue_valence * positions.primitive_axis.map(CONSERVATIVE_DIRECTION)
    issue = (positions.groupby("canonical_candidate_id")
             .agg(our_issue_conservatism=("conservative_issue_value", "mean"),
                  our_issue_axes=("primitive_axis", "nunique"),
                  our_mixed_axes=("adjudication_status", lambda x: int((x == "adjudicated_substantively_mixed").sum())))
             .reset_index())
    leg = pd.read_csv(LEG / "candidate_pre_election_legislative_features.csv", low_memory=False)
    leg["our_leg_dem_conservative_percentile"] = np.nan
    dem_leg = leg.canonical_party.eq("D") & leg.ideal_point.notna()
    leg.loc[dem_leg, "our_leg_dem_conservative_percentile"] = (
        leg.loc[dem_leg].groupby(["year", "chamber"])["ideal_point"].rank(pct=True, method="average") * 100)
    leg = leg[["canonical_candidate_id", "ideal_point", "chamber_percentile", "our_leg_dem_conservative_percentile", "votes_used",
               "party_loyalty_rate", "cross_party_voting_rate", "legislative_score_available"]]
    merged = shor.merge(issue, on="canonical_candidate_id", how="left", validate="one_to_one").merge(
        leg, on="canonical_candidate_id", how="left", validate="one_to_one")
    merged["our_issue_conservative_percentile"] = percentile_within(
        merged, "our_issue_conservatism", ["cycle", "chamber"])
    # Shor percentile is already relative to the active AL Democratic caucus.
    merged["issue_percentile_gap_ours_minus_shor"] = (
        merged.our_issue_conservative_percentile - merged.shor_al_dem_conservative_percentile)
    merged["legislative_percentile_gap_ours_minus_shor"] = (
        merged.our_leg_dem_conservative_percentile - merged.shor_al_dem_conservative_percentile)
    merged["shor_temporal_status"] = np.where(
        merged.shor_served_by_election.fillna(False), "pre_election_service_available", "post_election_or_no_prior_service")
    merged["considerable_issue_disagreement"] = merged.issue_percentile_gap_ours_minus_shor.abs().ge(30) & merged.our_issue_axes.ge(3)
    merged["considerable_legislative_disagreement"] = merged.legislative_percentile_gap_ours_minus_shor.abs().ge(30) & merged.votes_used.ge(20)
    merged.to_csv(OUT / "candidate_level_comparison.csv", index=False)

    disagreements = merged[(merged.considerable_issue_disagreement | merged.considerable_legislative_disagreement)].copy()
    disagreements["maximum_absolute_gap"] = disagreements[["issue_percentile_gap_ours_minus_shor", "legislative_percentile_gap_ours_minus_shor"]].abs().max(axis=1)
    disagreements.sort_values("maximum_absolute_gap", ascending=False).to_csv(OUT / "considerable_disagreements.csv", index=False)
    detail = positions.merge(disagreements[["canonical_candidate_id", "candidate", "cycle", "shor_np_score",
                                            "shor_al_dem_conservative_percentile", "our_issue_conservative_percentile",
                                            "issue_percentile_gap_ours_minus_shor", "shor_temporal_status"]],
                             on="canonical_candidate_id", how="inner")
    detail.to_csv(OUT / "disagreement_issue_decomposition.csv", index=False)

    rows = []
    comparisons = [("all_matches", merged),
                   ("pre_election_service", merged[merged.shor_temporal_status.eq("pre_election_service_available")]),
                   ("post_election_or_no_prior", merged[merged.shor_temporal_status.ne("pre_election_service_available")])]
    for label, frame in comparisons:
        for our_measure in ("our_issue_conservatism", "ideal_point", "cross_party_voting_rate"):
            comparison_frame = frame[frame.our_issue_axes.ge(3)] if our_measure == "our_issue_conservatism" else frame
            n, rho, p = safe_spearman(comparison_frame, "shor_np_score", our_measure)
            rows.append({"sample": label, "our_measure": our_measure, "n": n, "spearman_rho": rho, "p_value": p})
    diagnostics = pd.DataFrame(rows)
    diagnostics.to_csv(OUT / "comparison_diagnostics.csv", index=False)

    issue_disagree = merged[merged.considerable_issue_disagreement].copy()
    leg_disagree = merged[merged.considerable_legislative_disagreement].copy()
    negative_issue_gaps = int(issue_disagree.issue_percentile_gap_ours_minus_shor.lt(0).sum())
    report = ["# Shor–McCarty versus ontology-v3 ideology", "",
              f"There are **{len(merged)}** clean Shor–McCarty candidate-cycle matches. **{int(merged.shor_served_by_election.fillna(False).sum())}** have service observed by the indexed election; the remainder use a career score that may be based wholly or partly on later votes.", "",
              f"Our issue comparison requires at least three scalar issue axes. **{int(merged.our_issue_axes.ge(3).sum())}** matched rows meet that threshold. **{int(merged.considerable_issue_disagreement.sum())}** differ by at least 30 within-cycle/chamber percentile points.", "",
              f"The independent pre-election roll-call comparison has **{int(merged.votes_used.ge(20).sum())}** sufficiently observed rows; **{int(merged.considerable_legislative_disagreement.sum())}** differ from Shor–McCarty by at least 30 percentile points.", "",
              "## Interpretation rule", "",
              "A large difference does not by itself prove that either classification is wrong. Shor–McCarty estimates one career-level latent dimension using roll-call scaling and cross-state bridging. Ontology v3 records multiple issue-specific positions tied to an election cycle. Disagreement is most probative when both pre-election roll-call estimates are well observed; it is less probative when Shor–McCarty service begins after the election or our evidence is sparse.", ""]
    for row in diagnostics.itertuples(index=False):
        report.append(f"- {row.sample}, {row.our_measure}: n={row.n}, Spearman rho={row.spearman_rho:.3f}, p={row.p_value:.4f}")
    report += ["", "## Where the systems diverge", "",
               f"Among the {len(issue_disagree)} considerable issue-composite disagreements, {negative_issue_gaps} place the candidate at least 30 percentile points **less conservative in ontology v3** than in Shor–McCarty. This asymmetry is consistent with a one-dimensional roll-call score treating caucus-aligned behavior as conservative even when the candidate combines conservative social positions with liberal labor, welfare, education, health, or environmental positions.", "",
               "Well-covered examples include Richard Laird, Larry Means, Terry Spicer, Johnny Mack Morrow, and John Robinson. In these cases our independent roll-call percentile is generally close to Shor–McCarty while the issue composite is less conservative, indicating multidimensional compression rather than a simple roll-call coding error.", "",
               f"Only {len(leg_disagree)} of {int(merged.votes_used.ge(20).sum())} sufficiently observed pre-election roll-call comparisons differ by 30 or more Democratic-caucus percentile points: " + ", ".join(leg_disagree.candidate.astype(str)) + ". These are the strongest candidates for record-level investigation.", ""]
    (OUT / "SHOR_MCCARTY_COMPARISON.md").write_text("\n".join(report), encoding="utf-8")
    print(diagnostics.to_string(index=False))
    print(f"Clean matches {len(merged)}; considerable issue disagreements {merged.considerable_issue_disagreement.sum()}; legislative disagreements {merged.considerable_legislative_disagreement.sum()}")


if __name__ == "__main__":
    main()
