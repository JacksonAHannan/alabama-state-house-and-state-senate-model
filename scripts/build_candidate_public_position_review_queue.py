"""Rank pre-election public sources that may fill undocumented issue cells.

This is a retrieval queue only. Keyword matches and ranking scores never become
candidate positions without human review of the underlying source.
"""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
OUTPUT = RESEARCH / "candidate_public_position_review_queue.csv"
DECISIONS = RESEARCH / "candidate_public_position_review_decisions.csv"

DIRECT_TITLE = re.compile(
    r"\b(?:campaign|candidate|interview|questionnaire|statement|platform|"
    r"supports?|opposes?|calls? for|plans?|pledges?|seeks?|wants?)\b", re.I
)


def main() -> None:
    sources = pd.read_csv(RESEARCH / "candidate_public_source_content_review.csv")
    matrix = pd.read_csv(RESEARCH / "candidate_state_issue_matrix_long.csv")

    known = (
        matrix.groupby(["person_id", "election_cycle", "issue"], as_index=False)
        .documented.max()
        .rename(columns={"issue": "issue_retrieval_tag", "documented": "already_documented"})
    )
    queue = sources.loc[
        sources.temporal_status.eq("pre_election")
        & sources.issue_retrieval_tag.ne("unclassified")
    ].merge(
        known,
        on=["person_id", "election_cycle", "issue_retrieval_tag"],
        how="left",
    )
    queue["already_documented"] = queue.already_documented.fillna(False).astype(bool)
    queue = queue.loc[~queue.already_documented].copy()

    if DECISIONS.exists():
        decisions = pd.read_csv(DECISIONS)
        reviewed = decisions[[
            "person_id", "election_cycle", "issue_retrieval_tag", "url"
        ]].drop_duplicates().assign(_reviewed=True)
        queue = queue.merge(
            reviewed,
            on=["person_id", "election_cycle", "issue_retrieval_tag", "url"],
            how="left",
        )
        reviewed_mask = queue._reviewed.eq(True)
        queue = queue.loc[~reviewed_mask].drop(columns="_reviewed")

    queue["days_before_election"] = (
        pd.to_datetime(queue.election_cycle.astype(str) + "-11-30")
        - pd.to_datetime(queue.publication_date)
    ).dt.days
    queue["direct_title_signal"] = queue.title.fillna("").str.contains(DIRECT_TITLE)
    queue["candidate_in_title"] = queue.apply(
        lambda row: all(
            token.lower() in str(row.title).lower()
            for token in re.findall(r"[A-Za-z]{3,}", str(row.candidate))[-1:]
        ), axis=1,
    )
    queue["review_priority"] = (
        queue.direct_title_signal.astype(int) * 3
        + queue.candidate_in_title.astype(int) * 2
        + queue.days_before_election.between(0, 730).astype(int)
    )
    queue = queue.sort_values(
        ["person_id", "issue_retrieval_tag", "review_priority", "publication_date"],
        ascending=[True, True, False, False],
    ).groupby(["person_id", "election_cycle", "issue_retrieval_tag"], as_index=False).head(3)
    queue["human_review_status"] = "pending"
    queue["stance_must_be_verified_from_source"] = True
    columns = [
        "person_id", "candidate", "election_cycle", "issue_retrieval_tag",
        "review_priority", "publication_date", "title", "url",
        "candidate_context_excerpt", "direct_title_signal", "candidate_in_title",
        "human_review_status", "stance_must_be_verified_from_source",
    ]
    queue[columns].to_csv(OUTPUT, index=False)
    print(
        f"Wrote {len(queue)} ranked source rows for "
        f"{queue.person_id.nunique()} candidates and "
        f"{queue[['person_id', 'issue_retrieval_tag']].drop_duplicates().shape[0]} "
        f"undocumented candidate-issue cells to {OUTPUT}"
    )


if __name__ == "__main__":
    main()
