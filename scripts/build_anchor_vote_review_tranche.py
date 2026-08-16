"""Build a balanced, metadata-rich first tranche of anchor votes for review."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
DATA = ROOT / "data" / "processed" / "legislative"
FINAL_PASSAGE = re.compile(
    r"^(Motion to Read a Third Time and Pass(?: as Amended)?|Read a Third Time and Pass(?: as Amended)?|"
    r"(?:HBIR|SBIR): Passed by House of Origin)$", re.I
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-issue", type=int, default=5)
    args = parser.parse_args()
    queue = pd.read_csv(RESEARCH / "legislative_issue_bill_review_queue.csv")
    bills = pd.read_csv(DATA / "legiscan_alabama_bills.csv")
    subjects = pd.read_csv(DATA / "legiscan_bill_subjects.csv")
    sponsors = pd.read_csv(DATA / "legiscan_bill_sponsors.csv")
    votes = pd.read_csv(DATA / "legiscan_alabama_individual_votes.csv")
    crosswalk = pd.read_csv(RESEARCH / "focal_legislator_identity_crosswalk.csv")

    queue = queue[queue.vote_description.fillna("").str.match(FINAL_PASSAGE)].copy()
    queue = queue.drop_duplicates(["candidate_issues", "bill_id", "chamber"], keep="first")
    subject_text = subjects.groupby("bill_id").subject_name.agg(lambda values: " | ".join(sorted(set(values.dropna()))))
    primary_sponsors = sponsors.sort_values("sponsor_order").groupby("bill_id").first()
    queue = queue.merge(
        bills[["bill_id", "url", "state_link"]].rename(columns={"url": "bill_url", "state_link": "bill_state_link"}),
        on="bill_id", how="left", validate="many_to_one",
    )
    queue = queue.merge(subject_text.rename("legiscan_subjects"), on="bill_id", how="left")
    queue = queue.merge(
        primary_sponsors[["name", "party", "district"]].rename(columns={
            "name": "primary_sponsor", "party": "sponsor_party", "district": "sponsor_district"}),
        on="bill_id", how="left",
    )

    ids = pd.to_numeric(crosswalk.loc[crosswalk.review_status.eq("reviewed"), "legiscan_people_id"], errors="coerce").dropna().astype(int)
    focal_votes = votes[votes.people_id.isin(ids) & votes.vote.isin(["Yea", "Nay"])].merge(
        crosswalk[["legiscan_people_id", "candidate"]], left_on="people_id", right_on="legiscan_people_id", how="left"
    )
    focal_summary = focal_votes.groupby("roll_call_id").apply(
        lambda group: " | ".join(f"{row.candidate}: {row.vote}" for row in group.itertuples()),
        include_groups=False,
    ).rename("focal_candidate_votes")
    focal_count = focal_votes.groupby("roll_call_id").size().rename("focal_candidates_voting")
    queue = queue.merge(focal_summary, on="roll_call_id", how="left").merge(focal_count, on="roll_call_id", how="left")
    queue["focal_candidates_voting"] = queue.focal_candidates_voting.fillna(0).astype(int)
    queue["anchor_priority_score"] = (
        queue.party_gap.fillna(0) * 10
        + queue.focal_candidates_voting.clip(upper=10) * .4
        + queue.vote_description.str.contains("as Amended", case=False, na=False).map({True: -0.5, False: 0})
    )
    selected = (queue.sort_values(["anchor_priority_score", "session_year"], ascending=[False, True])
                .groupby("candidate_issues", group_keys=False).head(args.per_issue))
    selected = selected.sort_values(["candidate_issues", "anchor_priority_score"], ascending=[True, False])
    selected["reviewed_issue"] = ""
    selected["substantive_final_passage"] = ""
    selected["yea_policy_direction"] = ""
    selected["ideological_valence"] = ""
    selected["summary_sufficient_for_coding"] = ""
    selected["human_confidence"] = ""
    selected["human_review_note"] = ""
    columns = [
        "candidate_issues", "session_year", "chamber", "bill_number", "bill_id", "roll_call_id",
        "vote_date", "vote_description", "title", "legiscan_subjects", "primary_sponsor",
        "sponsor_party", "sponsor_district", "yea", "nay", "dem_yea_share", "rep_yea_share",
        "party_gap", "focal_candidates_voting", "focal_candidate_votes", "bill_url", "bill_state_link",
        "anchor_priority_score", "reviewed_issue", "substantive_final_passage", "yea_policy_direction",
        "ideological_valence", "summary_sufficient_for_coding", "human_confidence", "human_review_note",
    ]
    selected[columns].to_csv(RESEARCH / "anchor_vote_manual_review.csv", index=False)
    print(f"Selected {len(selected)} anchor candidates across {selected.candidate_issues.nunique()} issues")
    print(selected.groupby("candidate_issues").size().to_string())


if __name__ == "__main__":
    main()
