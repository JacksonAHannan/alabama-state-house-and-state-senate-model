"""Diagnose selection, survivorship, and within-person incumbency transitions."""
from pathlib import Path

import pandas as pd
from scipy.stats import mannwhitneyu, wilcoxon

ROOT = Path(__file__).resolve().parents[1]
ELECTIONS = ROOT / "data" / "processed" / "elections"
RESEARCH = ROOT / "research" / "cmo_ideology"
OUT = RESEARCH / "incumbency_survivorship"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_csv(ELECTIONS / "canonical_cmo_candidates_with_ideology_v3.csv")
    races = pd.read_csv(ELECTIONS / "canonical_cmo_features.csv")
    modeled = pd.read_csv(RESEARCH / "candidate_cycle_analysis.csv", low_memory=False)
    democrats = candidates[candidates.canonical_party.eq("D")].merge(
        races[["cycle", "chamber", "district", "contest_status"]],
        left_on=["year", "chamber", "district"], right_on=["cycle", "chamber", "district"], how="left")
    democrats = democrats.merge(
        modeled[["canonical_candidate_id", "expected_cmo_total_oof", "candidate_cmo_total_oof"]],
        on="canonical_candidate_id", how="left", validate="one_to_one")
    democrats = democrats.sort_values(["person_id", "year"])
    grouped = democrats.groupby("person_id")
    for column in ["year", "incumbent", "winner", "raw_overperformance", "contest_status",
                   "candidate_cmo_total_oof", "expected_cmo_total_oof", "chamber", "district"]:
        democrats[f"next_{column}"] = grouped[column].shift(-1)
    democrats["consecutive_next_cycle"] = democrats.next_year.sub(democrats.year).eq(4)

    contested = democrats[democrats.contest_status.eq("contested_two_party")].copy()
    status_summary = (contested.groupby("incumbent")
                      .agg(candidate_cycles=("canonical_candidate_id", "size"),
                           raw_mean=("raw_overperformance", "mean"), raw_median=("raw_overperformance", "median"),
                           residual_cmo_mean=("candidate_cmo_total_oof", "mean"),
                           residual_cmo_median=("candidate_cmo_total_oof", "median"))
                      .reset_index())
    status_summary.to_csv(OUT / "incumbent_nonincumbent_comparison.csv", index=False)

    first_entries = (contested[contested.incumbent.eq(0)].sort_values("year")
                     .drop_duplicates("person_id", keep="first").copy())
    entry_summary = (first_entries.groupby("winner")
                     .agg(candidates=("canonical_candidate_id", "size"),
                          raw_mean=("raw_overperformance", "mean"), raw_median=("raw_overperformance", "median"),
                          residual_cmo_mean=("candidate_cmo_total_oof", "mean"),
                          residual_cmo_median=("candidate_cmo_total_oof", "median"))
                     .reset_index())
    entry_summary.to_csv(OUT / "first_contested_entry_selection.csv", index=False)

    acquisitions = democrats[
        democrats.incumbent.eq(0) & democrats.winner.eq(1) &
        democrats.contest_status.eq("contested_two_party") & democrats.consecutive_next_cycle &
        democrats.next_incumbent.eq(1)].copy()
    acquisitions["next_unopposed"] = acquisitions.next_contest_status.eq("unopposed_democrat")
    acquisitions["next_contested"] = acquisitions.next_contest_status.eq("contested_two_party")
    acquisitions["raw_change"] = acquisitions.next_raw_overperformance - acquisitions.raw_overperformance
    acquisitions["residual_cmo_change"] = acquisitions.next_candidate_cmo_total_oof - acquisitions.candidate_cmo_total_oof
    acquisitions.to_csv(OUT / "nonincumbent_to_incumbent_transitions.csv", index=False)

    paired = acquisitions[acquisitions.next_contested].copy()
    raw_pair = paired[["raw_overperformance", "next_raw_overperformance"]].dropna()
    cmo_pair = paired[["candidate_cmo_total_oof", "next_candidate_cmo_total_oof"]].dropna()
    tests = pd.DataFrame([
        {"comparison": "first_entry_winner_vs_loser_raw", "n": len(first_entries),
         "difference": first_entries.loc[first_entries.winner.eq(1), "raw_overperformance"].mean() - first_entries.loc[first_entries.winner.eq(0), "raw_overperformance"].mean(),
         "p_value": mannwhitneyu(first_entries.loc[first_entries.winner.eq(1), "raw_overperformance"], first_entries.loc[first_entries.winner.eq(0), "raw_overperformance"]).pvalue},
        {"comparison": "first_entry_winner_vs_loser_residual_cmo", "n": int(first_entries.candidate_cmo_total_oof.notna().sum()),
         "difference": first_entries.loc[first_entries.winner.eq(1), "candidate_cmo_total_oof"].mean() - first_entries.loc[first_entries.winner.eq(0), "candidate_cmo_total_oof"].mean(),
         "p_value": mannwhitneyu(first_entries.loc[first_entries.winner.eq(1), "candidate_cmo_total_oof"].dropna(), first_entries.loc[first_entries.winner.eq(0), "candidate_cmo_total_oof"].dropna()).pvalue},
        {"comparison": "within_person_raw_change_after_incumbency_contested_only", "n": len(raw_pair),
         "difference": (raw_pair.next_raw_overperformance - raw_pair.raw_overperformance).mean(),
         "p_value": wilcoxon(raw_pair.next_raw_overperformance, raw_pair.raw_overperformance).pvalue},
        {"comparison": "within_person_residual_cmo_change_after_incumbency_contested_only", "n": len(cmo_pair),
         "difference": (cmo_pair.next_candidate_cmo_total_oof - cmo_pair.candidate_cmo_total_oof).mean(),
         "p_value": wilcoxon(cmo_pair.next_candidate_cmo_total_oof, cmo_pair.candidate_cmo_total_oof).pvalue},
    ])
    tests.to_csv(OUT / "survivorship_diagnostic_tests.csv", index=False)

    inc = status_summary.set_index("incumbent")
    entry = entry_summary.set_index("winner")
    report = ["# Incumbency and survivorship in Democratic CMO", "",
              "Incumbency is an endogenous state: candidates must win and continue running to enter the observed incumbent pool. These diagnostics distinguish cross-sectional incumbent differences from within-person transitions.", "",
              "## Cross-sectional pattern", "",
              f"In contested races, incumbent Democrats average **{inc.loc[1,'raw_mean']:.2f}** points of raw overperformance versus **{inc.loc[0,'raw_mean']:.2f}** for nonincumbents—a raw gap of **{inc.loc[1,'raw_mean']-inc.loc[0,'raw_mean']:.2f}** points. But residual out-of-fold CMO averages **{inc.loc[1,'residual_cmo_mean']:.2f}** for incumbents versus **{inc.loc[0,'residual_cmo_mean']:.2f}** for nonincumbents.", "",
              "## Selection into office", "",
              f"At the first observed contested nonincumbent race, winners average **{entry.loc[1,'raw_mean']:.2f}** raw overperformance and **{entry.loc[1,'residual_cmo_mean']:.2f}** residual CMO; losers average **{entry.loc[0,'raw_mean']:.2f}** and **{entry.loc[0,'residual_cmo_mean']:.2f}**, respectively. Winning therefore selects an unusually strong-performance subset into the potential incumbent pool.", "",
              "## Within-person transition", "",
              f"There are **{len(acquisitions)}** observed Democrats who win a contested race as a nonincumbent and appear four years later as an incumbent. **{int(acquisitions.next_unopposed.sum())}** are unopposed at the next election; challenger deterrence is itself a possible incumbency effect.",
              f"Among the **{len(paired)}** who face another two-party contest, raw overperformance changes by **{tests.loc[tests.comparison.str.startswith('within_person_raw'),'difference'].iloc[0]:.2f}** points and residual CMO by **{tests.loc[tests.comparison.str.startswith('within_person_residual'),'difference'].iloc[0]:.2f}** points on average. The residual decline has p = **{tests.loc[tests.comparison.str.startswith('within_person_residual'),'p_value'].iloc[0]:.4f}**.", "",
              "## Interpretation", "",
              "The data are consistent with substantial survivorship and regression-to-the-mean. The large cross-sectional raw incumbent premium should not be interpreted as a causal incumbency effect. At the same time, conditioning on a subsequent contested race excludes incumbents who deter challengers and can bias a transition estimate downward. A structural model should treat winning, rerunning, challenger entry, and vote performance as linked stages rather than placing a single exogenous incumbent dummy in the outcome equation."]
    (OUT / "INCUMBENCY_SURVIVORSHIP_AUDIT.md").write_text("\n".join(report), encoding="utf-8")
    print(status_summary.to_string(index=False))
    print(entry_summary.to_string(index=False))
    print(tests.to_string(index=False))


if __name__ == "__main__":
    main()
