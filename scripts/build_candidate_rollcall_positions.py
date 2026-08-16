"""Join human-coded roll calls to focal candidates' recorded votes.

No LLM-only classification can enter this output. Both the bill/roll-call code
and candidate identity must be marked reviewed.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
DATA = ROOT / "data" / "processed" / "legislative"


def main() -> None:
    queue = pd.read_csv(RESEARCH / "legislative_issue_bill_review_queue.csv", keep_default_na=False)
    bills = pd.read_csv(DATA / "legiscan_alabama_bills.csv", keep_default_na=False)
    queue = queue.merge(
        bills[["bill_id", "url", "state_link"]].rename(
            columns={"url": "bill_url", "state_link": "bill_state_link"}
        ), on="bill_id", how="left", validate="many_to_one",
    )
    code_frames = []
    for codes_path in [RESEARCH / "human_rollcall_codes.csv", RESEARCH / "anchor_vote_human_codes.csv"]:
        if codes_path.exists():
            code_frames.append(pd.read_csv(codes_path, keep_default_na=False))
    if code_frames:
        codes = pd.concat(code_frames, ignore_index=True).drop_duplicates(
            ["roll_call_id", "human_issue_code"], keep="last"
        )
        queue = queue.drop(columns=["human_issue_code", "policy_direction_of_yea", "substantive_vote"], errors="ignore").merge(
            codes, on="roll_call_id", how="left"
        ).fillna("")
    crosswalk = pd.read_csv(RESEARCH / "focal_legislator_identity_crosswalk.csv", keep_default_na=False)
    votes = pd.read_csv(DATA / "legiscan_alabama_individual_votes.csv")
    approved = queue[
        queue.substantive_vote.astype(str).str.lower().isin(["true", "yes", "1"])
        & queue.human_issue_code.ne("") & queue.review_status.eq("reviewed")
        & queue.policy_direction_of_yea.ne("")
    ].drop_duplicates(["roll_call_id", "human_issue_code"]).copy()
    identities = crosswalk[crosswalk.review_status.eq("reviewed") & crosswalk.legiscan_people_id.ne("")].copy()
    if approved.empty or identities.empty:
        columns = ["person_id", "candidate", "election_cycle", "roll_call_id", "bill_number",
                   "vote_date", "human_issue_code", "policy_direction_of_yea", "vote",
                   "candidate_position", "evidence_timing", "source_url", "state_link"]
        pd.DataFrame(columns=columns).to_csv(RESEARCH / "candidate_rollcall_position_evidence.csv", index=False)
        print("No fully reviewed bill classifications and identities are ready; wrote an empty evidence table")
        return
    identities["legiscan_people_id"] = pd.to_numeric(identities.legiscan_people_id).astype(int)
    votes = votes[votes.vote.isin(["Yea", "Nay"])].copy()
    joined = approved.merge(votes, on="roll_call_id", how="inner", suffixes=("_roll", "_vote"))
    joined = joined.merge(identities, left_on="people_id", right_on="legiscan_people_id", how="inner")
    joined["candidate_position"] = joined.apply(
        lambda row: row.policy_direction_of_yea if row.vote == "Yea" else f"opposes: {row.policy_direction_of_yea}", axis=1
    )
    joined["vote_date"] = joined["vote_date_roll"]
    joined["evidence_timing"] = joined.apply(
        lambda row: "pre_or_during_election" if str(row.vote_date)[:4].isdigit() and int(str(row.vote_date)[:4]) <= int(row.election_cycle)
        else "post_election", axis=1
    )
    joined["source_url"] = joined.bill_url
    joined["state_link"] = joined.bill_state_link
    columns = ["person_id", "candidate", "election_cycle", "roll_call_id", "bill_number",
               "vote_date", "human_issue_code", "policy_direction_of_yea", "vote",
               "candidate_position", "evidence_timing", "source_url", "state_link"]
    joined[columns].to_csv(RESEARCH / "candidate_rollcall_position_evidence.csv", index=False)
    print(f"Wrote {len(joined)} reviewed candidate/roll-call evidence rows")


if __name__ == "__main__":
    main()
