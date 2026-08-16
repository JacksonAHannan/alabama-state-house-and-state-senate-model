"""Build a reproducible archival-search queue for unresolved candidate positions."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
CORE_ISSUES = [
    "guns", "abortion", "school_choice", "labor_unions", "taxes_budget",
    "healthcare_medicaid", "public_education", "criminal_justice",
    "business_economic_development", "ethics_government",
]


def main() -> None:
    matrix = pd.read_csv(RESEARCH / "candidate_state_issue_matrix_long.csv")
    cohort = pd.read_csv(RESEARCH / "candidate_cohort.csv")[[
        "person_id", "validation_priority", "best_cmo"
    ]]
    cells = matrix[[
        "person_id", "candidate", "election_cycle", "chamber", "district",
        "issue", "documented", "sponsored_bills_pre",
    ]].drop_duplicates(["person_id", "election_cycle", "issue"])
    cells = cells.merge(cohort, on="person_id", how="left", validate="many_to_one")
    queue = cells.loc[cells.issue.isin(CORE_ISSUES) & ~cells.documented].copy()
    queue["priority_score"] = (
        queue.validation_priority.map({"critical": 3, "standard": 2}).fillna(1) * 100
        + queue.best_cmo.fillna(0)
        + queue.issue.map({
            "guns": 10, "abortion": 10, "school_choice": 9,
            "labor_unions": 8, "taxes_budget": 7, "healthcare_medicaid": 7,
        }).fillna(3)
        + queue.sponsored_bills_pre.gt(0).astype(int) * 5
    )
    labels = {
        "guns": "guns firearm", "abortion": "abortion reproductive",
        "school_choice": "school choice charter voucher private school",
        "labor_unions": "labor union AEA collective bargaining",
        "taxes_budget": "tax budget spending", "healthcare_medicaid": "Medicaid health care",
        "public_education": "public education schools teachers",
        "criminal_justice": "crime prison sentencing police",
        "business_economic_development": "jobs business economic development",
        "ethics_government": "ethics corruption government reform",
    }
    queue["search_query"] = queue.apply(
        lambda row: (
            f'"{row.candidate}" Alabama {int(row.election_cycle)} '
            f'{labels[row.issue]} campaign'
        ), axis=1
    )
    queue["archive_query"] = queue.apply(
        lambda row: f'"{row.candidate}" {int(row.election_cycle)} Alabama', axis=1
    )
    queue["recommended_sources"] = (
        "contemporaneous local newspapers; VoteSmart questionnaire; endorsements; "
        "campaign mail/video; archived campaign website"
    )
    queue["review_status"] = "open_no_position_found"
    queue["inference_rule"] = "Unknown remains unknown; do not infer stance from party or sponsorship topic."
    queue = queue.sort_values(
        ["priority_score", "candidate", "issue"], ascending=[False, True, True]
    )
    queue.to_csv(RESEARCH / "candidate_campaign_position_research_queue.csv", index=False)
    print(f"Wrote {len(queue)} unresolved candidate/issue searches for {queue.person_id.nunique()} candidates")


if __name__ == "__main__":
    main()
