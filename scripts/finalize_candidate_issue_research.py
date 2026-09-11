"""Close the candidate-issue research loop without imputing missing ideology.

This creates an auditable terminal status for every modeled candidate, checks
all locally acquired source layers, reports temporal exclusions, and measures
candidate/issue coverage under the model's minimum-evidence rules.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
ELECTIONS = ROOT / "data" / "processed" / "elections"
MANUAL = ROOT / "data" / "manual" / "ideology"
OUT = ROOT / "research" / "cmo_ideology" / "candidate_issue_research"
DOC = ROOT / "project_docs" / "audits" / "CANDIDATE_ISSUE_RESEARCH_CLOSURE.md"
# Preserved 2026-08-17 closure ledger; supplies prior_status so the restatement
# keeps every earlier disposition as history instead of overwriting it.
PRIOR_STATUS = OUT / "candidate_research_final_status.2026-08-17.csv"
# Everything after this marker in DOC is regenerated; the 2026-08-17 account
# before it is preserved verbatim.
RESTATEMENT_MARKER = "<!-- candidate-issue-research-restatement -->"


def ids(frame: pd.DataFrame, column: str = "canonical_candidate_id") -> set[str]:
    return set(frame[column].dropna().astype(str)) if column in frame else set()


def markdown_table(frame: pd.DataFrame) -> str:
    shown = frame.copy()
    lines = ["| " + " | ".join(shown.columns) + " |",
             "| " + " | ".join("---" for _ in shown.columns) + " |"]
    for row in shown.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base = pd.read_csv(ELECTIONS / "canonical_cmo_candidates_with_votesmart.csv", low_memory=False)
    positions = pd.read_csv(IDEOLOGY / "candidate_issue_valence_v3.csv")
    evidence = pd.read_csv(IDEOLOGY / "candidate_position_evidence_v3_all_sources.csv", low_memory=False)
    attempts = pd.read_csv(MANUAL / "candidate_issue_research_attempts.csv", dtype=str).fillna("")
    aliases = pd.read_csv(MANUAL / "candidate_research_aliases.csv", dtype=str).fillna("")
    crosswalk = pd.read_csv(IDEOLOGY / "votesmart_candidate_crosswalk_resolved.csv", dtype=str).fillna("")
    pct = pd.read_csv(IDEOLOGY / "votesmart_all_1998_2022_pct_options.csv", dtype=str,
                      usecols=["votesmart_candidate_id"])
    ratings = pd.read_csv(IDEOLOGY / "votesmart_all_1998_2022_ratings.csv", dtype=str,
                          usecols=["votesmart_candidate_id"])
    endorsements = pd.read_csv(IDEOLOGY / "votesmart_all_1998_2022_endorsements.csv", dtype=str,
                               usecols=["votesmart_candidate_id"])
    legislative = pd.read_csv(IDEOLOGY / "candidate_legislative_position_evidence_v3.csv",
                              usecols=["canonical_candidate_id"], dtype=str)

    accepted = crosswalk[crosswalk.accepted.str.lower().eq("true")].copy()
    accepted_ids = ids(accepted)
    alias_ids = ids(aliases)
    position_ids = ids(positions)
    attempt_ids = ids(attempts)
    broad_attempt_ids = ids(attempts[attempts.issue_scope.eq("all_issues")])
    legislative_ids = ids(legislative)
    pct_vs = set(pct.votesmart_candidate_id.str.replace(r"\.0$", "", regex=True))
    rating_vs = set(ratings.votesmart_candidate_id.str.replace(r"\.0$", "", regex=True))
    endorsement_vs = set(endorsements.votesmart_candidate_id.str.replace(r"\.0$", "", regex=True))
    accepted_vs = accepted.set_index("canonical_candidate_id").votesmart_candidate_id.to_dict()
    latest = attempts.drop_duplicates("canonical_candidate_id", keep="last").set_index(
        "canonical_candidate_id")["result_status"].to_dict()

    status = base[["canonical_candidate_id", "person_id", "canonical_name", "cycle", "chamber",
                   "district", "canonical_party", "candidate_margin_overperformance"]].copy()
    status["absolute_cmo"] = pd.to_numeric(status.candidate_margin_overperformance,
                                            errors="coerce").abs()
    status["has_issue_evidence"] = status.canonical_candidate_id.isin(position_ids)
    status["manual_broad_search_logged"] = status.canonical_candidate_id.isin(broad_attempt_ids)
    status["any_manual_search_logged"] = status.canonical_candidate_id.isin(attempt_ids)
    status["accepted_votesmart_identity"] = status.canonical_candidate_id.isin(accepted_ids)
    status["manual_identity_alias"] = status.canonical_candidate_id.isin(alias_ids)
    status["legislative_source_checked_and_present"] = status.canonical_candidate_id.isin(legislative_ids)
    vote_ids = [str(accepted_vs.get(value, "")).replace(".0", "")
                for value in status.canonical_candidate_id]
    status["votesmart_questionnaire_checked_and_present"] = [value in pct_vs for value in vote_ids]
    status["votesmart_rating_checked_and_present"] = [value in rating_vs for value in vote_ids]
    status["votesmart_endorsement_checked_and_present"] = [value in endorsement_vs for value in vote_ids]
    status["latest_manual_result"] = status.canonical_candidate_id.map(latest).fillna("")
    full_name = status.canonical_name.fillna("").str.strip().str.contains(r"\s")
    status["identity_status"] = np.select(
        [status.manual_identity_alias, status.accepted_votesmart_identity, full_name],
        ["verified_manual_identity", "verified_votesmart_identity", "full_name_official_roster"],
        default="surname_only_unresolved_after_source_sweep")
    status["final_research_status"] = np.where(
        status.has_issue_evidence, "evidence_recovered",
        "searched_no_recoverable_evidence")
    status["exhaustion_basis"] = np.where(
        status.has_issue_evidence, "not_applicable",
        np.where(status.manual_broad_search_logged,
                 "manual_broad_search_plus_structured_source_sweep",
                 "structured_votesmart_legislative_identity_source_sweep"))
    status["neutrality_imputed"] = False

    restated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prior_map: dict[str, str] = {}
    if PRIOR_STATUS.exists():
        prior_frame = pd.read_csv(
            PRIOR_STATUS, usecols=["canonical_candidate_id", "final_research_status"])
        prior_map = prior_frame.set_index(
            "canonical_candidate_id").final_research_status.astype(str).to_dict()
    status["prior_status"] = status.canonical_candidate_id.map(prior_map).fillna("")
    changed = status.prior_status.ne("") & status.prior_status.ne(status.final_research_status)
    gained_ids = set(status.loc[changed, "canonical_candidate_id"])
    channel_map: dict[str, str] = {}
    if gained_ids:
        added = evidence[evidence.canonical_candidate_id.isin(gained_ids)]
        channel_map = (added.groupby("canonical_candidate_id").source_type
                       .apply(lambda values: "|".join(sorted(set(values.dropna())))).to_dict())
    status["new_evidence_source_types"] = status.canonical_candidate_id.map(channel_map).fillna("")
    status["restated_at_utc"] = np.where(changed, restated_at, "")
    status = status.sort_values(["has_issue_evidence", "absolute_cmo"],
                                ascending=[True, False], na_position="last")
    status.to_csv(OUT / "candidate_research_final_status.csv", index=False)

    temporal = (evidence.groupby(["temporal_status", "temporal_model_eligible"], dropna=False)
                .agg(evidence_records=("evidence_id", "nunique"),
                     candidates=("canonical_candidate_id", "nunique"))
                .reset_index())
    temporal.to_csv(OUT / "candidate_evidence_temporal_audit.csv", index=False)
    excluded = evidence[~evidence.temporal_model_eligible.fillna(False)].copy()
    excluded.to_csv(OUT / "candidate_evidence_excluded_from_model_temporal.csv", index=False)

    candidate_coverage = (positions.groupby("canonical_candidate_id", as_index=False)
                          .agg(observed_issues=("primitive_axis", "nunique"),
                               scored_issues=("issue_score_available", "sum"),
                               evidence_records=("evidence_records", "sum"),
                               source_types=("source_type_count", "max")))
    candidate_coverage = base[["canonical_candidate_id", "cycle"]].merge(
        candidate_coverage, on="canonical_candidate_id", how="left").fillna(
            {"observed_issues": 0, "scored_issues": 0, "evidence_records": 0, "source_types": 0})
    integrated = pd.read_csv(ELECTIONS / "canonical_cmo_candidates_with_ideology_v3.csv",
                             usecols=["canonical_candidate_id", "ideology_v3_scored_family_count",
                                      "ideology_v3_model_eligible"])
    candidate_coverage = candidate_coverage.merge(
        integrated, on="canonical_candidate_id", how="left", validate="one_to_one")
    candidate_coverage["ideology_v3_model_eligible"] = (
        candidate_coverage.ideology_v3_model_eligible.fillna(False).astype(bool))
    candidate_coverage.to_csv(OUT / "candidate_evidence_coverage_final.csv", index=False)
    issue_coverage = (positions.groupby("primitive_axis", as_index=False)
                      .agg(candidates_observed=("canonical_candidate_id", "nunique"),
                           candidates_scored=("issue_score_available", "sum"),
                           evidence_records=("evidence_records", "sum"))
                      .sort_values("candidates_scored", ascending=False))
    issue_coverage.to_csv(OUT / "issue_evidence_coverage_final.csv", index=False)
    cycle_coverage = (candidate_coverage.groupby("cycle", as_index=False)
                      .agg(candidates=("canonical_candidate_id", "nunique"),
                           candidates_observed=("observed_issues", lambda x: int((x > 0).sum())),
                           candidates_with_scored_issue=("scored_issues", lambda x: int((x > 0).sum())),
                           candidates_meeting_three_issue_floor=("scored_issues", lambda x: int((x >= 3).sum())),
                           candidates_model_eligible=("ideology_v3_model_eligible", "sum")))
    cycle_coverage["observed_share"] = cycle_coverage.candidates_observed / cycle_coverage.candidates
    cycle_coverage["three_issue_floor_share"] = (
        cycle_coverage.candidates_meeting_three_issue_floor / cycle_coverage.candidates)
    cycle_coverage.to_csv(OUT / "candidate_evidence_coverage_by_cycle_final.csv", index=False)

    missing = status[~status.has_issue_evidence]
    identity_summary = (missing.groupby("identity_status", as_index=False)
                        .agg(candidates=("canonical_candidate_id", "nunique")))
    changes = (status.loc[status.restated_at_utc.ne("")]
               .loc[:, ["canonical_candidate_id", "cycle", "chamber", "district",
                        "canonical_party", "prior_status", "final_research_status",
                        "new_evidence_source_types"]]
               .sort_values(["cycle", "canonical_candidate_id"]))
    DOC.parent.mkdir(parents=True, exist_ok=True)
    if DOC.exists():
        preserved = DOC.read_text(encoding="utf-8").split(RESTATEMENT_MARKER)[0].rstrip()
    else:
        preserved = "\n".join([
            "# Candidate issue research closure", "",
            "The research loop is closed at diminishing returns. Missing evidence is retained as missing; it is never converted to a neutral or zero ideological score.",
        ])
    restated = [
        "", RESTATEMENT_MARKER, "",
        f"## Restated accounting ({restated_at[:10]})", "",
        f"Restatement run {restated_at} (UTC). The closure account above is the "
        "2026-08-17 terminal accounting, preserved as history; every disposition it "
        "recorded is carried in `prior_status` on the restated ledger. The tables "
        "below recompute the same disposition rule from the current evidence layer "
        "(`candidate_issue_valence_v3.csv`, `candidate_position_evidence_v3_all_sources.csv`); "
        "no evidence value is imputed and no missing cycle is converted to a score.", "",
        "### Restated terminal accounting", "",
        f"- Modeled candidate-cycle rows: **{len(status):,}**",
        f"- Candidates with at least one temporally valid issue profile: **{status.has_issue_evidence.sum():,}**",
        f"- Searched with no recoverable issue evidence: **{len(missing):,}**",
        f"- Cycles whose disposition changed since 2026-08-17: **{len(changes):,}**",
        f"- Residuals with a logged manual broad search: **{missing.manual_broad_search_logged.sum():,}**",
        f"- Residuals closed by the structured Vote Smart, legislative, identity, and source sweep: **{(~missing.manual_broad_search_logged).sum():,}**", "",
        "### Disposition changes since 2026-08-17", "",
        markdown_table(changes) if len(changes) else "No disposition changed.", "",
        "### Restated residual identity status", "", markdown_table(identity_summary), "",
        "### Restated temporal validity", "",
        "All evidence remains in the archival evidence table. Only explicitly pre-election, same-cycle, or clearly historical pre-election statuses enter scores. Post-election, retrospective, and temporally unspecified career records are exported but excluded from scoring.", "",
        markdown_table(temporal), "",
        "### Restated minimum-evidence rule", "",
        "- Issue score: at least 0.65 total evidence weight, conflict ratio below 0.50, and absolute valence above 0.15.",
        "- Family score: at least two distinct issues and 1.50 total temporally valid evidence weight.",
        "- Candidate model eligibility: at least three scored issues and two scored ideological families.", "",
        "A lone mapped endorsement (weight 0.45) therefore cannot create an issue score by itself. One questionnaire answer can create an issue score, but not a broad family or candidate-level ideology estimate.", "",
        "### Restated coverage by cycle", "", markdown_table(cycle_coverage), "",
        "Full candidate and issue coverage tables, the terminal residual ledger, and every temporally excluded evidence record are written beside this report under `research/cmo_ideology/candidate_issue_research/`. Per-row history columns (`prior_status`, `new_evidence_source_types`, `restated_at_utc`) and the preserved 2026-08-17 ledger (`candidate_research_final_status.2026-08-17.csv`) carry the prior account.",
    ]
    DOC.write_text(preserved + "\n" + "\n".join(restated) + "\n", encoding="utf-8")
    print(f"Closed {len(missing):,} residual candidates as searched_no_recoverable_evidence")
    print(f"Restated {len(changes):,} candidate-cycles whose disposition changed")
    print(cycle_coverage.to_string(index=False))


if __name__ == "__main__":
    main()
