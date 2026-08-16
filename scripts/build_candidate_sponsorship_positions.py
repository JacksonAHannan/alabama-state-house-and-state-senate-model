"""Create directional candidate evidence from human-coded bills they sponsored."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
DATA = ROOT / "data" / "processed" / "legislative"
ISSUE_MAP = {
    "abortion": "abortion", "anti_esg_governance": "anti_esg_governance",
    "assisted_dying": "assisted_dying",
    "business_economic_development": "business_economic_development",
    "criminal_justice": "criminal_justice", "culture_lgbtq": "lgbtq_cultural",
    "environment_energy": "environment", "ethics_government": "ethics_government",
    "gambling": "gambling", "gambling_cultural": "gambling", "guns": "guns",
    "healthcare_conscience": "healthcare_conscience",
    "healthcare_medicaid_finance": "healthcare_medicaid", "immigration": "immigration",
    "labor_unions": "labor_unions", "occupational_licensing": "occupational_licensing",
    "public_education": "public_education",
    "public_employee_benefits": "public_employee_benefits",
    "public_private_partnerships": "public_private_partnerships",
    "racial_civil_rights": "racial_civil_rights", "rural_hunting": "rural_hunting",
    "school_choice": "school_choice", "social_services": "health_social_services",
    "taxes_budget": "taxes_budget", "taxes_revenue": "taxes_budget",
    "infrastructure_energy": "infrastructure_energy",
    "minimum_wage_worker_pay": "minimum_wage_worker_pay",
}


def main() -> None:
    queue = pd.read_csv(
        RESEARCH / "legislative_issue_bill_review_queue.csv", dtype={"roll_call_id": str}
    )
    codes = pd.read_csv(
        RESEARCH / "anchor_vote_human_codes.csv", dtype={"roll_call_id": str}
    )
    coded = queue[["roll_call_id", "bill_id", "bill_number", "vote_description"]].merge(
        codes, on="roll_call_id", how="inner", validate="many_to_many"
    )
    coded = coded.loc[
        coded.review_status.eq("reviewed")
        & coded.substantive_vote.astype(str).str.lower().isin(["true", "yes", "1"])
        & coded.policy_direction_of_yea.notna()
    ].copy()
    # Every accepted anchor is final passage, but retain the explicit gate.
    coded = coded.loc[coded.vote_description.str.contains(
        r"third time|passed by house of origin", case=False, na=False, regex=True
    )]
    coded["issue"] = coded.human_issue_code.map(ISSUE_MAP)
    coded = coded.loc[coded.issue.notna()].drop_duplicates(
        ["bill_id", "issue", "policy_direction_of_yea"]
    )

    sponsors = pd.read_csv(RESEARCH / "candidate_sponsored_bill_evidence.csv")
    sponsors = sponsors.drop_duplicates([
        "person_id", "election_cycle", "bill_id", "sponsorship_role"
    ]).drop(columns=["issue"], errors="ignore")
    anchor_evidence = sponsors.merge(coded, on=["bill_id", "bill_number"], how="inner")
    anchor_evidence["position_summary"] = anchor_evidence.apply(
        lambda row: (
            f"{row.sponsorship_role.replace('_', ' ').title()} of legislation that "
            f"{row.policy_direction_of_yea}."
        ), axis=1
    )
    anchor_evidence["stance_code"] = "sponsorship_support"
    anchor_evidence["evidence_date"] = anchor_evidence.activity_date
    anchor_evidence["temporal_status"] = anchor_evidence.activity_timing.map({
        "pre_or_during_election": "pre_election", "post_election": "post_election"
    })
    anchor_evidence["confidence"] = anchor_evidence.sponsorship_role.map({
        "primary_sponsor": "high", "joint_sponsor": "high", "cosponsor": "medium"
    }).fillna("low")
    anchor_evidence["source_url"] = anchor_evidence.url
    anchor_evidence["evidence_type"] = "human_coded_anchor_bill_sponsorship"
    anchor_evidence["review_status"] = "reviewed"

    direction_path = RESEARCH / "human_sponsorship_adjudications.csv"
    if direction_path.exists():
        directions = pd.read_csv(direction_path)
        validation_path = DATA / "sponsorship_bill_text_link_validation.csv"
        if not validation_path.exists():
            raise FileNotFoundError(
                "Run validate_sponsorship_bill_text_links.py before building evidence"
            )
        validation = pd.read_csv(validation_path)
        valid_ids = set(validation.loc[
            validation.position_review_allowed.eq(True), "bill_id"
        ].astype(int))
        directions = directions.loc[
            directions.bill_id.astype(int).isin(valid_ids)
        ].copy()
        required = {
            "bill_id", "human_issue_code", "policy_direction_of_yea",
            "ideological_valence", "position_summary", "confidence",
            "review_status", "position_evidence_allowed", "review_note",
        }
        missing = required - set(directions.columns)
        if missing:
            raise ValueError(f"Missing sponsorship adjudication fields: {sorted(missing)}")
        directions = directions.loc[directions.review_status.eq("reviewed")].copy()
        allowed = directions.position_evidence_allowed.astype(str).str.lower().map(
            {"true": True, "false": False}
        )
        if allowed.isna().any():
            bad = directions.loc[allowed.isna(), "bill_id"].tolist()
            raise ValueError(f"Invalid position_evidence_allowed values: {bad}")
        directions = directions.loc[allowed].copy()
        directions["issue"] = directions.human_issue_code.map(ISSUE_MAP)
        if directions.issue.isna().any():
            bad = directions.loc[directions.issue.isna(), "human_issue_code"].unique()
            raise ValueError(f"Unknown sponsorship issue codes: {sorted(bad)}")
        directional_evidence = sponsors.merge(
            directions, on="bill_id", how="inner", validate="many_to_one"
        )
        directional_evidence["stance_code"] = "sponsorship_support"
        directional_evidence["evidence_date"] = directional_evidence.activity_date
        directional_evidence["temporal_status"] = directional_evidence.activity_timing.map({
            "pre_or_during_election": "pre_election", "post_election": "post_election"
        })
        directional_evidence["source_url"] = directional_evidence.url
        directional_evidence["evidence_type"] = "human_coded_bill_sponsorship"
    else:
        directional_evidence = pd.DataFrame(columns=anchor_evidence.columns)

    evidence = pd.concat([anchor_evidence, directional_evidence], ignore_index=True)
    columns = [
        "person_id", "candidate", "election_cycle", "issue", "stance_code",
        "position_summary", "evidence_date", "temporal_status", "confidence",
        "source_url", "bill_id", "bill_number", "sponsorship_role",
        "human_issue_code", "policy_direction_of_yea", "ideological_valence",
        "evidence_type", "review_status",
    ]
    evidence[columns].sort_values(
        ["election_cycle", "candidate", "evidence_date", "bill_number", "issue"]
    ).to_csv(RESEARCH / "candidate_sponsorship_position_evidence.csv", index=False)
    print(
        f"Wrote {len(evidence)} human-coded sponsorship positions for "
        f"{evidence.person_id.nunique()} candidates and {evidence.bill_id.nunique()} bills"
    )


if __name__ == "__main__":
    main()
