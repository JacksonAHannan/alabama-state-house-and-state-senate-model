"""Build a resumable candidate-by-issue research queue for the CMO universe."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote_plus

import numpy as np
import pandas as pd

from ideology_ontology_v3 import PRIMITIVES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "cmo_ideology" / "candidate_issue_research"
ATTEMPTS = ROOT / "data" / "manual" / "ideology" / "candidate_issue_research_attempts.csv"
ALIASES = ROOT / "data" / "manual" / "ideology" / "candidate_research_aliases.csv"
EXCLUSIONS = ROOT / "data" / "manual" / "ideology" / "candidate_research_exclusions.csv"
QUALITY_FLAGS = ROOT / "data" / "manual" / "ideology" / "candidate_research_quality_flags.csv"

CORE_ISSUES = [
    "abortion_access", "marriage_equality", "civil_social_liberty", "religion_state",
    "gun_access", "gun_purchase_regulation", "market_governance", "tax_burden",
    "welfare_generosity", "welfare_conditionality", "labor_capital_alignment", "labor_rights",
    "healthcare_access", "education_public_funding", "education_market_choice",
    "environmental_protection", "resource_development", "immigration_enforcement",
    "criminal_punishment", "voting_access", "childcare_support",
]
SOCIAL_QUERY = "abortion OR pro-life OR pro-choice OR marriage OR gay OR LGBT OR church OR prayer"
ECON_QUERY = "taxes OR business OR welfare OR labor OR union OR healthcare OR education"
SOCIAL_ISSUES = {"abortion_access", "abortion_public_funding", "marriage_equality",
                 "civil_social_liberty", "anti_discrimination", "affirmative_action",
                 "religion_state", "gun_access", "gun_purchase_regulation"}
ECON_ISSUES = {"market_governance", "public_private_provision", "economic_stimulus",
               "tax_burden", "tax_distribution", "public_spending", "deficit_discipline",
               "welfare_generosity", "welfare_conditionality", "labor_capital_alignment",
               "labor_rights", "public_employee_compensation", "business_subsidy",
               "childcare_support", "healthcare_access", "education_public_funding",
               "education_market_choice"}


def clean_name(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9' -]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def load_attempts() -> pd.DataFrame:
    columns = ["canonical_candidate_id", "issue_scope", "attempt_date", "search_type",
               "query", "result_status", "source_url", "notes"]
    if not ATTEMPTS.exists():
        return pd.DataFrame(columns=columns)
    attempts = pd.read_csv(ATTEMPTS, dtype=str).fillna("")
    for column in columns:
        if column not in attempts:
            attempts[column] = ""
    return attempts[columns]


def _subject_queue(gaps: pd.DataFrame, attempts: pd.DataFrame,
                   status: str | None = None) -> pd.DataFrame:
    selected = gaps if status is None else gaps[gaps.research_status.eq(status)]
    subject = (selected
               .groupby(["canonical_candidate_id", "person_id", "candidate", "cycle", "chamber",
                         "district", "party", "candidate_cmo", "cmo_tail", "cmo_extremity",
                         "cmo_priority_valid", "identity_researchable"], as_index=False)
               .agg(missing_core_issues=("issue_priority", lambda x: int((x == 1).sum())),
                    missing_all_issues=("primitive_axis", "size")))
    attempt_counts = attempts.groupby("canonical_candidate_id").size().to_dict()
    latest_results = (attempts.drop_duplicates("canonical_candidate_id", keep="last")
                      .set_index("canonical_candidate_id")["result_status"].to_dict())
    subject["prior_attempts"] = subject.canonical_candidate_id.map(attempt_counts).fillna(0).astype(int)
    subject["latest_result_status"] = subject.canonical_candidate_id.map(latest_results).fillna("")
    subject["social_query"] = [
        f'"{name}" Alabama candidate {year} ({SOCIAL_QUERY})'
        for name, year in zip(subject.candidate, subject.cycle)]
    subject["economic_query"] = [
        f'"{name}" Alabama candidate {year} ({ECON_QUERY})'
        for name, year in zip(subject.candidate, subject.cycle)]
    subject["archive_query"] = [
        f'"{name}" Alabama House Senate campaign {year}'
        for name, year in zip(subject.candidate, subject.cycle)]
    subject["search_url"] = subject.social_query.map(
        lambda query: "https://www.google.com/search?q=" + quote_plus(query))
    subject["priority_score"] = (
        subject.cmo_extremity.clip(upper=60) * subject.cmo_priority_valid.astype(int)
        + 8 * subject.identity_researchable.astype(int)
        + 0.25 * subject.missing_core_issues
        + 0.05 * subject.missing_all_issues
        - 2 * subject.prior_attempts.clip(upper=10)
    )
    # Exhaust the universe in rounds: every candidate with fewer searches comes
    # before candidates already given another pass. Priority only orders peers
    # within a round, preventing high-CMO subjects from monopolizing the queue.
    subject = subject.sort_values(
        ["prior_attempts", "priority_score"], ascending=[True, False]).reset_index(drop=True)
    subject["tail_rank"] = subject.groupby("cmo_tail").cumcount() + 1
    return subject


def _balanced_batch(subject: pd.DataFrame, per_tail: int = 20) -> pd.DataFrame:
    batch = pd.concat([subject[subject.cmo_tail.eq("high")].head(per_tail),
                       subject[subject.cmo_tail.eq("low")].head(per_tail)], ignore_index=True)
    return batch.sort_values(["tail_rank", "cmo_tail"]).reset_index(drop=True)


def build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    scores = pd.read_csv(ROOT / "data" / "processed" / "war" / "preliminary_cmo_candidates.csv")
    positions = pd.read_csv(
        ROOT / "data" / "processed" / "ideology" / "candidate_issue_valence_v3.csv")
    scores = scores.copy()
    if EXCLUSIONS.exists():
        exclusions = pd.read_csv(EXCLUSIONS, dtype=str).fillna("")
        scores = scores[~scores.canonical_candidate_id.isin(exclusions.canonical_candidate_id)].copy()
    scores["candidate_name"] = scores.candidate.map(clean_name)
    if ALIASES.exists():
        aliases = pd.read_csv(ALIASES, dtype=str).fillna("")
        research_names = dict(zip(aliases.canonical_candidate_id, aliases.research_name))
        scores["candidate_name"] = [
            clean_name(research_names.get(candidate_id, candidate_name))
            for candidate_id, candidate_name in zip(
                scores.canonical_candidate_id, scores.candidate_name)
        ]
    scores["identity_researchable"] = scores.candidate_name.str.contains(" ") | scores.person_id.duplicated(False)
    scores["cmo_tail"] = np.where(scores.candidate_cmo_total_oof.ge(0), "high", "low")
    scores["cmo_extremity"] = scores.candidate_cmo_total_oof.abs()
    scores["cmo_priority_valid"] = True
    if QUALITY_FLAGS.exists():
        flags = pd.read_csv(QUALITY_FLAGS, dtype=str).fillna("")
        invalid = set(flags.loc[
            flags.quality_flag.eq("corrupted_vote_total_do_not_prioritize_by_cmo"),
            "canonical_candidate_id"])
        scores["cmo_priority_valid"] = ~scores.canonical_candidate_id.isin(invalid)
    observed = set(zip(positions.canonical_candidate_id, positions.primitive_axis))
    binary_issues = [issue for issue, poles in PRIMITIVES.items() if len(poles) == 2]
    rows = []
    for candidate in scores.itertuples(index=False):
        for issue in binary_issues:
            if (candidate.canonical_candidate_id, issue) in observed:
                continue
            rows.append({
                "canonical_candidate_id": candidate.canonical_candidate_id,
                "person_id": candidate.person_id, "candidate": candidate.candidate_name,
                "cycle": candidate.cycle, "chamber": candidate.chamber,
                "district": candidate.district, "party": candidate.party,
                "candidate_cmo": candidate.candidate_cmo_total_oof,
                "cmo_tail": candidate.cmo_tail, "cmo_extremity": candidate.cmo_extremity,
                "cmo_priority_valid": candidate.cmo_priority_valid,
                "identity_researchable": candidate.identity_researchable,
                "primitive_axis": issue, "positive_pole": PRIMITIVES[issue][0],
                "negative_pole": PRIMITIVES[issue][1],
                "issue_priority": 1 if issue in CORE_ISSUES else 2,
            })
    gaps = pd.DataFrame(rows)
    attempts = load_attempts()
    attempted = set(zip(attempts.canonical_candidate_id, attempts.issue_scope))
    gaps["research_status"] = [
        "searched" if ((candidate, issue) in attempted or (candidate, "all_issues") in attempted
                       or (issue in SOCIAL_ISSUES and (candidate, "social_issues") in attempted)
                       or (issue in ECON_ISSUES and (candidate, "economic_issues") in attempted))
        else "not_yet_searched"
        for candidate, issue in zip(gaps.canonical_candidate_id, gaps.primitive_axis)
    ]
    gaps = gaps.sort_values(
        ["research_status", "issue_priority", "identity_researchable", "cmo_extremity"],
        ascending=[False, True, False, False]).reset_index(drop=True)

    subject = _subject_queue(gaps, attempts, "not_yet_searched")
    batch = _balanced_batch(subject)
    # A broad first pass must not make remaining issue gaps disappear. This queue
    # deliberately includes searched candidates for deeper source- and axis-specific rounds.
    return gaps, subject, batch


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    gaps, subjects, batch = build()
    followup = _subject_queue(gaps, load_attempts())
    followup_batch = _balanced_batch(followup)
    gaps.to_csv(OUT / "candidate_issue_gap_matrix.csv", index=False)
    subjects.to_csv(OUT / "candidate_research_subject_queue.csv", index=False)
    batch.to_csv(OUT / "candidate_research_next_batch.csv", index=False)
    followup.to_csv(OUT / "candidate_research_followup_queue.csv", index=False)
    followup_batch.to_csv(OUT / "candidate_research_followup_next_batch.csv", index=False)
    summary = (gaps.groupby(["research_status", "issue_priority"], as_index=False)
               .agg(candidate_issue_cells=("primitive_axis", "size"),
                    candidates=("canonical_candidate_id", "nunique")))
    summary.to_csv(OUT / "candidate_issue_research_summary.csv", index=False)
    print(summary.to_string(index=False))
    print("\nNext balanced batch:\n", batch[["candidate", "cycle", "chamber", "district",
                                                 "candidate_cmo", "cmo_tail"]].to_string(index=False))
    print("\nNext follow-up batch:\n", followup_batch[["candidate", "cycle", "chamber", "district",
             "candidate_cmo", "cmo_tail", "missing_core_issues", "missing_all_issues",
             "prior_attempts"]].to_string(index=False))


if __name__ == "__main__":
    main()
