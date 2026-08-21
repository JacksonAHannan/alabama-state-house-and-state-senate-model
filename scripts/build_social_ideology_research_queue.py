"""Prioritize high-CMO Democrats missing a social-ideology family score."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "cmo_ideology" / "social_moderation"


def build_queue() -> pd.DataFrame:
    scores = pd.read_csv(ROOT / "data" / "processed" / "war" / "preliminary_cmo_candidates.csv")
    ideology = pd.read_csv(
        ROOT / "data" / "processed" / "elections" /
        "canonical_cmo_candidates_with_ideology_v3.csv", low_memory=False)
    cols = ["canonical_candidate_id", "ideology_v3_social_liberty_equality",
            "ideology_v3_issue_count", "ideology_v3_evidence_records"]
    data = scores[scores.party.eq("D")].merge(ideology[cols], on="canonical_candidate_id", how="left")
    missing = data[data.ideology_v3_social_liberty_equality.isna()].copy()
    missing["full_name"] = missing.candidate.astype(str).str.contains(r"\s", regex=True)
    people = (missing.groupby("person_id", as_index=False)
              .agg(candidate=("candidate", lambda x: max(x.astype(str), key=len)),
                   max_cmo=("candidate_cmo_total_oof", "max"),
                   min_cmo=("candidate_cmo_total_oof", "min"),
                   median_cmo=("candidate_cmo_total_oof", "median"),
                   stability_low=("candidate_cmo_total_stability_low", "max"),
                   stability_high=("candidate_cmo_total_stability_high", "min"),
                   cycles_observed=("cycle", "nunique"), earliest_cycle=("cycle", "min"),
                   latest_cycle=("cycle", "max"), chambers=("chamber", lambda x: "|".join(sorted(set(x)))),
                   districts=("district", lambda x: "|".join(map(str, sorted(set(x))))),
                   incumbent_cycles=("incumbent", "sum"), wins=("winner", "sum"),
                   partial_issue_count=("ideology_v3_issue_count", "max"),
                   partial_evidence_records=("ideology_v3_evidence_records", "max"),
                   full_name=("full_name", "max")))
    people["identity_researchable"] = people.full_name | people.cycles_observed.gt(1)
    people["research_tail"] = np.where(
        people.max_cmo.abs().ge(people.min_cmo.abs()), "high_overperformance", "low_overperformance")
    people["extreme_cmo"] = np.where(
        people.research_tail.eq("high_overperformance"), people.max_cmo, people.min_cmo)
    people["tail_result_stable"] = np.where(
        people.research_tail.eq("high_overperformance"), people.stability_low.gt(0),
        people.stability_high.lt(0))
    people["priority_score"] = (
        people.extreme_cmo.abs().clip(0, 60)
        + 5 * np.log1p(people.cycles_observed)
        + 4 * people.identity_researchable.astype(int)
        + 2 * people.partial_issue_count.fillna(0).clip(0, 5)
        + 2 * people.tail_result_stable.astype(int)
    )
    people["high_tail_rank"] = people.max_cmo.rank(method="min", ascending=False).astype(int)
    people["low_tail_rank"] = people.min_cmo.rank(method="min", ascending=True).astype(int)
    people["research_status"] = "not_started"
    people["target_evidence"] = (
        "same-cycle questionnaire; campaign site; voter guide; explicit abortion/LGBT/cultural statement")
    return people.sort_values(["priority_score", "extreme_cmo"], ascending=[False, False]).reset_index(drop=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    queue = build_queue()
    queue.to_csv(OUT / "social_ideology_targeted_research_queue.csv", index=False)
    print(queue.head(40).to_string(index=False))


if __name__ == "__main__":
    main()
