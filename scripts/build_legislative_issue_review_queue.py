"""Create a review queue of potentially issue-relevant, polarized AL roll calls.

Keyword hits nominate bills for human coding; they never determine policy
direction or candidate stance automatically.
"""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"
OUT = ROOT / "research" / "cmo_ideology" / "legislative_issue_bill_review_queue.csv"

ISSUE_PATTERNS = {
    "public_education": r"public school|education|teacher|classroom|school funding|literacy",
    "school_choice": r"charter school|school choice|education savings|voucher|private school",
    "healthcare_medicaid": r"medicaid|health care|healthcare|hospital|health insurance",
    "labor_unions": r"collective bargain|labor union|right.to.work|prevailing wage|public employee",
    "guns": r"firearm|handgun|pistol|gun |weapons?|concealed carry|permitless carry",
    "abortion": r"abortion|unborn|fetal|embryo|reproductive|pregnancy",
    "taxes_revenue": r"income tax|sales tax|property tax|tax credit|tax exemption|revenue",
    "economic_development": r"economic development|jobs act|incentive|industrial development",
    "ethics_government": r"ethics commission|campaign finance|public corruption|lobbyist|open records",
    "culture_lgbtq": r"transgender|sexual orientation|gender identity|same.sex|bathroom|diversity equity",
    "gambling": r"gambling|lottery|casino|sports betting|pari.mutuel",
    "infrastructure": r"transportation|highway|road and bridge|broadband|infrastructure",
    "social_services": r"food assistance|snap|temporary assistance|child care|housing assistance",
    "criminal_justice": r"criminal justice|sentencing|parole|prison|corrections|death penalty|bail reform",
    "environment_energy": r"environment|pollution|renewable|solar|coal|oil and gas|conservation",
    "immigration": r"immigration|immigrant|alien|e.verify|citizenship status",
}


def issue_hits(text: object) -> list[str]:
    value = str(text or "").lower()
    return [issue for issue, pattern in ISSUE_PATTERNS.items() if re.search(pattern, value)]


def main() -> None:
    rolls = pd.read_csv(DATA / "legiscan_rollcall_analysis_eligibility.csv")
    votes = pd.read_csv(DATA / "legiscan_alabama_individual_votes.csv")
    people = pd.read_csv(DATA / "legiscan_alabama_legislators.csv")
    people = people.drop_duplicates(["session_year", "people_id"], keep="last")
    votes = votes[votes.vote.isin(["Yea", "Nay"])].merge(
        people[["session_year", "people_id", "party"]],
        on=["session_year", "people_id"], how="left", validate="many_to_one",
    )
    votes["yea_binary"] = votes.vote.eq("Yea").astype(int)
    party = votes[votes.party.isin(["D", "R"])].groupby(
        ["roll_call_id", "party"]
    ).yea_binary.agg(["mean", "count"]).reset_index()
    shares = party.pivot(index="roll_call_id", columns="party", values="mean").rename(
        columns={"D": "dem_yea_share", "R": "rep_yea_share"}
    )
    counts = party.pivot(index="roll_call_id", columns="party", values="count").rename(
        columns={"D": "dem_votes", "R": "rep_votes"}
    )
    metrics = shares.join(counts).reset_index()
    metrics["party_gap"] = (metrics.dem_yea_share - metrics.rep_yea_share).abs()
    rolls["search_text"] = rolls[["title", "description", "vote_description"]].fillna("").agg(" ".join, axis=1)
    rolls["candidate_issues"] = rolls.search_text.map(issue_hits)
    queue = rolls[rolls.candidate_issues.map(bool) & rolls.eligible_ideal_point].explode("candidate_issues")
    queue = queue.merge(metrics, on="roll_call_id", how="left")
    queue = queue.sort_values(
        ["party_gap", "session_year", "roll_call_id"], ascending=[False, True, True]
    )
    queue["human_issue_code"] = ""
    queue["policy_direction_of_yea"] = ""
    queue["substantive_vote"] = ""
    queue["review_note"] = ""
    columns = [
        "candidate_issues", "session_year", "chamber", "bill_number", "bill_id",
        "roll_call_id", "vote_date", "vote_description", "title", "description",
        "dem_yea_share", "rep_yea_share", "party_gap", "yea", "nay",
        "url", "state_link", "human_issue_code", "policy_direction_of_yea",
        "substantive_vote", "review_note",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    queue[columns].to_csv(OUT, index=False)
    print(f"Wrote {len(queue):,} candidate issue/roll-call rows covering {queue.roll_call_id.nunique():,} votes")


if __name__ == "__main__":
    main()
