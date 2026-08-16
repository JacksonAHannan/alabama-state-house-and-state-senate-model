"""Build sourced long- and wide-form state-issue matrices for focal CMO candidates."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
ISSUES = [
    "public_education", "school_choice", "healthcare_medicaid", "labor_unions",
    "guns", "abortion", "taxes_budget", "business_economic_development",
    "ethics_government", "lgbtq_cultural", "gambling", "infrastructure_energy",
    "health_social_services", "criminal_justice", "environment",
    "immigration", "rural_hunting", "public_employee_benefits",
    "assisted_dying", "healthcare_conscience", "public_private_partnerships",
    "occupational_licensing", "anti_esg_governance",
    "racial_civil_rights",
    "minimum_wage_worker_pay",
]
ISSUE_LABELS = {
    "public_education": "Public education",
    "school_choice": "School choice / private funding",
    "healthcare_medicaid": "Health care / Medicaid",
    "labor_unions": "Labor / AEA",
    "guns": "Guns",
    "abortion": "Abortion",
    "taxes_budget": "Taxes / budget",
    "business_economic_development": "Jobs / economic development",
    "ethics_government": "Ethics / government reform",
    "lgbtq_cultural": "Cultural / LGBTQ issues",
    "gambling": "Lottery / gambling",
    "infrastructure_energy": "Infrastructure / energy",
    "health_social_services": "Social services",
    "criminal_justice": "Criminal justice",
    "environment": "Environment",
    "immigration": "Immigration enforcement",
    "rural_hunting": "Rural / hunting interests",
    "public_employee_benefits": "Public employee benefits",
    "assisted_dying": "Assisted dying",
    "healthcare_conscience": "Health-care conscience rights",
    "public_private_partnerships": "Public-private infrastructure",
    "occupational_licensing": "Occupational licensing",
    "anti_esg_governance": "Anti-ESG governance",
    "racial_civil_rights": "Race / civil rights",
    "minimum_wage_worker_pay": "Minimum wage / worker pay",
}
STANCE_LABELS = {
    "support": "Supports",
    "support_reform": "Supports reform/investment",
    "support_access": "Supports access",
    "support_expansion": "Supports expansion",
    "support_lottery": "Supports lottery",
    "support_public_investment": "Supports public investment",
    "oppose": "Opposes",
    "oppose_private_diversion": "Opposes private-school diversion",
    "oppose_charter_diversion": "Opposes charter-school diversion",
    "aligned": "Aligned",
    "strongly_aligned": "Strongly aligned",
    "gun_rights": "Gun-rights",
    "gun_regulation": "Gun-regulation",
    "anti_abortion": "Anti-abortion",
    "abortion_rights": "Abortion-rights",
    "mixed_qualified": "Mixed/qualified",
    "business_friendly": "Business-friendly",
    "local_development": "Local development",
    "industrial_jobs": "Industrial jobs",
    "jobs_wages": "Jobs and wages",
    "reform": "Reform",
    "progressive": "Progressive",
    "conservative": "Conservative",
    "protective": "Protective",
    "education_lottery": "Education lottery",
    "education_professional": "Education professional",
    "school_governance_record": "School-governance record",
    "universal_access": "Universal access",
    "support_referendum": "Supports voter referendum",
    "oppose_restrictive_law": "Opposes restrictive law",
    "workforce_development": "Workforce development",
    "supports_hunter_user_fee": "Supports hunter user fee",
    "opposes_hunter_user_fee": "Opposes hunter user fee increase",
    "sponsorship_support": "Sponsored",
    "rollcall_support": "Voted Yea",
    "rollcall_oppose": "Voted Nay",
    "race_neutral_representation": "Individual-character standard",
    "support_stand_your_ground": "Supports stand-your-ground",
    "support_targeted_incentives": "Supports targeted incentives",
    "oppose_grocery_tax": "Opposes grocery sales tax",
    "support_living_wage": "Supports living wage",
    "support_clean_energy": "Supports clean energy",
    "oppose_aca": "Opposes Affordable Care Act",
    "support_seniority_protection": "Supports teacher seniority protection",
    "amendment_support": "Offered policy amendment",
}

ROLLCALL_ISSUE_MAP = {
    "abortion": "abortion",
    "anti_esg_governance": "anti_esg_governance",
    "assisted_dying": "assisted_dying",
    "business_economic_development": "business_economic_development",
    "criminal_justice": "criminal_justice",
    "culture_lgbtq": "lgbtq_cultural",
    "environment_energy": "environment",
    "ethics_government": "ethics_government",
    "gambling": "gambling",
    "gambling_cultural": "gambling",
    "guns": "guns",
    "healthcare_conscience": "healthcare_conscience",
    "healthcare_medicaid_finance": "healthcare_medicaid",
    "immigration": "immigration",
    "labor_unions": "labor_unions",
    "occupational_licensing": "occupational_licensing",
    "public_education": "public_education",
    "public_employee_benefits": "public_employee_benefits",
    "public_private_partnerships": "public_private_partnerships",
    "school_choice": "school_choice",
    "social_services": "health_social_services",
    "taxes_budget": "taxes_budget",
    "taxes_revenue": "taxes_budget",
}


def status_prefix(status: str) -> str:
    if status == "pre_election":
        return "E"
    if status == "retrospective_preexisting_record":
        return "B"
    if status == "post_election":
        return "L"
    raise ValueError(f"Unknown temporal status: {status}")


def main() -> None:
    cohort = pd.read_csv(RESEARCH / "candidate_cohort.csv")
    positions = pd.read_csv(RESEARCH / "state_issue_position_ledger.csv")
    evidence = pd.read_csv(RESEARCH / "evidence_ledger.csv")
    rollcalls = pd.read_csv(
        RESEARCH / "candidate_rollcall_position_evidence.csv",
        dtype={"roll_call_id": str},
    )
    human_codes = pd.read_csv(
        RESEARCH / "anchor_vote_human_codes.csv",
        dtype={"roll_call_id": str},
    )[["roll_call_id", "human_issue_code", "human_confidence"]]
    human_codes = human_codes.drop_duplicates(
        ["roll_call_id", "human_issue_code"], keep="last"
    )
    rollcalls = rollcalls.merge(
        human_codes,
        on=["roll_call_id", "human_issue_code"],
        how="left",
        validate="many_to_one",
    )
    rollcalls["issue"] = rollcalls.human_issue_code.map(ROLLCALL_ISSUE_MAP)
    rollcalls = rollcalls.loc[rollcalls.issue.notna()].copy()
    rollcalls["stance_code"] = rollcalls.vote.map({
        "Yea": "rollcall_support", "Nay": "rollcall_oppose"
    })
    rollcalls["position_summary"] = rollcalls.candidate_position
    rollcalls["evidence_date"] = rollcalls.vote_date
    rollcalls["temporal_status"] = rollcalls.evidence_timing.map({
        "pre_or_during_election": "pre_election",
        "post_election": "post_election",
    })
    rollcalls["confidence"] = rollcalls.human_confidence.fillna("medium")
    roll_positions = rollcalls[[
        "person_id", "candidate", "election_cycle", "issue", "stance_code",
        "position_summary", "evidence_date", "temporal_status", "confidence",
        "source_url",
    ]]
    positions = pd.concat([positions, roll_positions], ignore_index=True)
    sponsorship_path = RESEARCH / "candidate_sponsorship_position_evidence.csv"
    if sponsorship_path.exists():
        sponsorship_positions = pd.read_csv(sponsorship_path)[[
            "person_id", "candidate", "election_cycle", "issue", "stance_code",
            "position_summary", "evidence_date", "temporal_status", "confidence",
            "source_url",
        ]]
        positions = pd.concat([positions, sponsorship_positions], ignore_index=True)
    amendment_path = RESEARCH / "candidate_amendment_position_evidence.csv"
    if amendment_path.exists():
        amendment_positions = pd.read_csv(amendment_path)[[
            "person_id", "candidate", "election_cycle", "issue", "stance_code",
            "position_summary", "evidence_date", "temporal_status", "confidence",
            "source_url",
        ]]
        positions = pd.concat([positions, amendment_positions], ignore_index=True)
    positions = positions.drop_duplicates(
        ["person_id", "election_cycle", "issue", "source_url"], keep="last"
    )

    if positions.duplicated(["person_id", "election_cycle", "issue", "source_url"]).any():
        raise ValueError("Duplicate candidate-cycle-issue-source rows")
    if not set(positions.issue).issubset(ISSUES):
        raise ValueError(f"Unknown issues: {sorted(set(positions.issue) - set(ISSUES))}")
    if not set(positions.temporal_status).issubset({
        "pre_election", "retrospective_preexisting_record", "post_election"
    }):
        raise ValueError("Unknown temporal status")

    focal = cohort[["person_id", "cycle", "candidate", "chamber", "district", "best_cmo"]].copy()
    focal = focal.rename(columns={"cycle": "election_cycle", "candidate": "cohort_candidate"})
    preferred_names = (evidence[["person_id", "candidate"]].drop_duplicates("person_id")
                       .rename(columns={"candidate": "display_candidate"}))
    focal = focal.merge(preferred_names, on="person_id", how="left", validate="many_to_one")
    focal["display_candidate"] = focal.display_candidate.fillna(focal.cohort_candidate)
    if focal.duplicated(["person_id", "election_cycle"]).any():
        raise ValueError("Duplicate focal candidate-cycle rows")
    unknown_people = set(positions.person_id) - set(focal.person_id)
    if unknown_people:
        raise ValueError(f"Position ledger contains non-focal people: {sorted(unknown_people)}")

    grid = focal.assign(_key=1).merge(
        pd.DataFrame({"issue": ISSUES, "_key": 1}), on="_key"
    ).drop(columns="_key")
    joined = grid.merge(
        positions,
        on=["person_id", "election_cycle", "issue"],
        how="left", validate="one_to_many",
    )
    # Legislative activity enriches the matrix without being converted into a stance.
    # Sponsorship is priority evidence; an offered amendment is directional only after
    # its text has been manually adjudicated.
    sponsor_path = RESEARCH / "candidate_sponsorship_issue_summary.csv"
    if sponsor_path.exists():
        sponsor = pd.read_csv(sponsor_path)
        sponsor = sponsor.loc[
            sponsor.sponsorship_role.isin(["primary_sponsor", "joint_sponsor"])
            & sponsor.issue.isin(ISSUES)
        ].copy()
        sponsor["timing"] = sponsor.activity_timing.map({
            "pre_or_during_election": "pre", "post_election": "post"
        })
        sponsor = (sponsor.groupby(["person_id", "election_cycle", "issue", "timing"])
                   .bill_count.sum().unstack(fill_value=0).reset_index())
        sponsor = sponsor.rename(columns={
            "pre": "sponsored_bills_pre", "post": "sponsored_bills_post"
        })
        joined = joined.merge(
            sponsor, on=["person_id", "election_cycle", "issue"], how="left",
            validate="many_to_one",
        )
    amendment_path = RESEARCH / "candidate_attributed_amendments.csv"
    if amendment_path.exists():
        amendments = pd.read_csv(amendment_path)
        amendments = amendments.loc[amendments.issue.isin(ISSUES)].copy()
        amendments["timing"] = amendments.activity_timing.map({
            "pre_or_during_election": "pre", "post_election": "post"
        })
        amendments = (amendments.groupby([
            "person_id", "election_cycle", "issue", "timing"
        ]).amendment_id.nunique().unstack(fill_value=0).reset_index())
        amendments = amendments.rename(columns={
            "pre": "attributed_amendments_pre", "post": "attributed_amendments_post"
        })
        joined = joined.merge(
            amendments, on=["person_id", "election_cycle", "issue"], how="left",
            validate="many_to_one",
        )
    activity_columns = [
        "sponsored_bills_pre", "sponsored_bills_post",
        "attributed_amendments_pre", "attributed_amendments_post",
    ]
    for column in activity_columns:
        if column not in joined:
            joined[column] = 0
        joined[column] = joined[column].fillna(0).astype(int)
    joined["issue_label"] = joined.issue.map(ISSUE_LABELS)
    joined["documented"] = joined.stance_code.notna()
    joined["stance_label"] = joined.stance_code.map(STANCE_LABELS)
    joined["candidate"] = joined.display_candidate
    joined = joined[[
        "person_id", "candidate", "election_cycle", "chamber", "district", "best_cmo",
        "issue", "issue_label", "documented", "stance_code", "stance_label",
        "position_summary", "evidence_date", "temporal_status", "confidence", "source_url",
        *activity_columns,
    ]].sort_values(["election_cycle", "candidate", "issue"])
    joined.to_csv(RESEARCH / "candidate_state_issue_matrix_long.csv", index=False)

    coverage = (joined.groupby([
        "person_id", "candidate", "election_cycle", "chamber", "district", "best_cmo"
    ], as_index=False)
        .agg(
            documented_issue_rows=("documented", "sum"),
            documented_issues=("issue", lambda values: 0),
            source_count=("source_url", lambda values: values.dropna().nunique()),
            unknown_issue_cells=("documented", lambda values: (~values).sum()),
        ))
    documented_counts = (joined.loc[joined.documented]
                         .groupby(["person_id", "election_cycle"])
                         .issue.nunique())
    pre_counts = (joined.loc[joined.temporal_status.eq("pre_election")]
                  .groupby(["person_id", "election_cycle"]).issue.nunique())
    later_counts = (joined.loc[joined.temporal_status.eq("post_election")]
                    .groupby(["person_id", "election_cycle"]).issue.nunique())
    biographical_counts = (joined.loc[
        joined.temporal_status.eq("retrospective_preexisting_record")
    ].groupby(["person_id", "election_cycle"]).issue.nunique())
    key_index = pd.MultiIndex.from_frame(coverage[["person_id", "election_cycle"]])
    coverage["documented_issues"] = documented_counts.reindex(key_index, fill_value=0).to_numpy()
    coverage["pre_election_issues"] = pre_counts.reindex(key_index, fill_value=0).to_numpy()
    coverage["later_only_issues"] = later_counts.reindex(key_index, fill_value=0).to_numpy()
    coverage["retrospective_record_issues"] = biographical_counts.reindex(
        key_index, fill_value=0
    ).to_numpy()
    coverage["needs_archival_research"] = coverage.pre_election_issues.lt(2)
    priority_counts = (joined.loc[joined.sponsored_bills_pre.gt(0)]
                       .groupby(["person_id", "election_cycle"]).issue.nunique())
    amendment_issue_counts = (joined.loc[joined.attributed_amendments_pre.gt(0)]
                              .groupby(["person_id", "election_cycle"]).issue.nunique())
    coverage["pre_election_priority_issues"] = priority_counts.reindex(
        key_index, fill_value=0
    ).to_numpy()
    coverage["pre_election_amendment_issues"] = amendment_issue_counts.reindex(
        key_index, fill_value=0
    ).to_numpy()
    coverage.to_csv(RESEARCH / "candidate_state_issue_coverage.csv", index=False)

    documented = joined.loc[joined.documented].copy()
    documented["matrix_cell"] = documented.apply(
        lambda row: f"{status_prefix(row.temporal_status)}: {row.stance_label}", axis=1
    )
    cells = (documented.groupby(["person_id", "election_cycle", "issue"])
             .matrix_cell.agg(lambda values: "; ".join(dict.fromkeys(values)))
             .reset_index())
    wide = grid.merge(cells, on=["person_id", "election_cycle", "issue"], how="left")
    wide.matrix_cell = wide.matrix_cell.fillna("?")
    wide = wide.pivot(
        index=["person_id", "election_cycle", "cohort_candidate", "display_candidate", "chamber", "district", "best_cmo"],
        columns="issue", values="matrix_cell"
    ).reset_index()
    wide = wide[[
        "person_id", "election_cycle", "display_candidate", "chamber", "district", "best_cmo",
        *ISSUES,
    ]].sort_values(["election_cycle", "display_candidate"])
    wide.to_csv(RESEARCH / "candidate_state_issue_matrix.csv", index=False)

    lines = [
        "# Alabama Democratic CMO candidate state-issue matrix", "",
        "This matrix covers the 30 focal positive-CMO candidate-cycle cases. `E` means",
        "the position is documented before or during that election; `B` means a later",
        "source documents a preexisting record; `L` means the stance was documented only",
        "after the scored election; `?` means no position was found. A broad ideology score",
        "is never converted into a specific issue stance.", "",
    ]
    table_groups = [
        ("Education, health care, and labor", ISSUES[:4]),
        ("Guns, abortion, budgets, and economic development", ISSUES[4:8]),
        ("Governance, cultural issues, and other state policy", ISSUES[8:]),
    ]
    for heading, columns in table_groups:
        lines.extend([f"## {heading}", ""])
        headers = ["Candidate", "Cycle"] + [ISSUE_LABELS[c] for c in columns]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in wide.itertuples(index=False):
            values = [row.display_candidate, str(row.election_cycle)] + [getattr(row, c) for c in columns]
            lines.append("| " + " | ".join(str(v).replace("|", "/") for v in values) + " |")
        lines.append("")
    lines.extend([
        "## Source-level detail", "",
        "The publication matrix is intentionally compact. Exact position summaries, dates,",
        "temporal classifications, confidence ratings, and URLs are retained in",
        "`candidate_state_issue_matrix_long.csv` and `state_issue_position_ledger.csv`.", "",
    ])
    (RESEARCH / "CANDIDATE_STATE_ISSUE_MATRIX.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(
        f"Wrote {len(wide)} candidate rows, {len(joined)} candidate-issue cells, "
        f"and {len(documented)} sourced position rows"
    )


if __name__ == "__main__":
    main()
