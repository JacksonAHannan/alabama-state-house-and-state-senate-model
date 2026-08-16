"""Build detailed, source-linked issue profiles from reviewed roll-call votes only.

The report deliberately does not blend sponsorships, amendments, campaign statements,
or party labels into the vote narrative. A Nay is described as opposition to the
specific motion; it is not treated as proof that the legislator supports the policy's
conceptual opposite.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"

ISSUE_LABELS = {
    "abortion": "Abortion",
    "anti_esg_governance": "ESG and state financial governance",
    "assisted_dying": "Assisted dying",
    "business_economic_development": "Business and economic development",
    "criminal_justice": "Criminal justice",
    "culture_lgbtq": "LGBTQ and cultural policy",
    "environment_energy": "Environment and energy",
    "ethics_government": "Ethics and government",
    "gambling": "Gambling",
    "gambling_cultural": "Gambling and cultural regulation",
    "guns": "Firearms",
    "healthcare_conscience": "Health-care conscience rules",
    "healthcare_medicaid_finance": "Health care and Medicaid finance",
    "immigration": "Immigration",
    "labor_unions": "Labor and unions",
    "occupational_licensing": "Occupational licensing",
    "public_education": "Public education",
    "public_employee_benefits": "Public-employee benefits",
    "public_private_partnerships": "Public-private partnerships",
    "school_choice": "School choice",
    "social_services": "Social services",
    "taxes_budget": "Taxes and budgeting",
    "taxes_revenue": "Taxes and revenue",
}


def clean_policy(value: str) -> str:
    text = " ".join(str(value).strip().split())
    if not text:
        return "has an unavailable policy description"
    return text[0].lower() + text[1:]


def timing_label(value: str) -> str:
    return {
        "pre_or_during_election": "before or during the candidate's indexed election cycle",
        "post_election": "after the candidate's indexed election cycle",
    }.get(str(value), str(value).replace("_", " "))


def vote_sentence(row: pd.Series) -> str:
    policy = clean_policy(row.policy_direction_of_yea)
    if row.vote == "Yea":
        return f"Voted for a motion that {policy}."
    return (
        f"Voted against the motion described as: “{policy}.” This establishes opposition "
        "to that motion, not necessarily support for every possible alternative."
    )


def pattern_sentence(group: pd.DataFrame) -> str:
    yea = int(group.vote.eq("Yea").sum())
    nay = int(group.vote.eq("Nay").sum())
    if yea and nay:
        return (
            f"In this reviewed sample, the candidate supported {yea} motion"
            f"{'s' if yea != 1 else ''} and opposed {nay}. The mixed tally should be "
            "read proposal by proposal because the motions need not measure one ideological axis."
        )
    if yea:
        return (
            f"The candidate supported all {yea} reviewed motion"
            f"{'s' if yea != 1 else ''} in this issue sample."
        )
    return (
        f"The candidate opposed all {nay} reviewed motion"
        f"{'s' if nay != 1 else ''} in this issue sample."
    )


def substantive_synthesis(group: pd.DataFrame) -> str:
    supported = list(dict.fromkeys(
        clean_policy(value) for value in group.loc[group.vote.eq("Yea"), "policy_direction_of_yea"]
    ))
    opposed = list(dict.fromkeys(
        clean_policy(value) for value in group.loc[group.vote.eq("Nay"), "policy_direction_of_yea"]
    ))
    parts = []
    if supported:
        parts.append("The reviewed record shows support for: " + "; ".join(supported) + ".")
    if opposed:
        parts.append("It shows opposition to motions that: " + "; ".join(opposed) + ".")
    return " ".join(parts)


def main() -> None:
    evidence = pd.read_csv(RESEARCH / "candidate_rollcall_position_evidence.csv")
    cohort = pd.read_csv(RESEARCH / "candidate_cohort.csv")
    evidence = evidence.drop_duplicates(
        ["person_id", "roll_call_id", "human_issue_code"], keep="last"
    ).copy()
    evidence["vote_date"] = evidence.vote_date.astype(str)

    summaries = []
    for (person_id, candidate, cycle, issue), group in evidence.groupby(
        ["person_id", "candidate", "election_cycle", "human_issue_code"], sort=False
    ):
        summaries.append({
            "person_id": person_id,
            "candidate": candidate,
            "election_cycle": int(cycle),
            "issue": issue,
            "issue_label": ISSUE_LABELS.get(issue, issue.replace("_", " ").title()),
            "reviewed_vote_records": len(group),
            "yea_votes": int(group.vote.eq("Yea").sum()),
            "nay_votes": int(group.vote.eq("Nay").sum()),
            "distinct_roll_calls": int(group.roll_call_id.nunique()),
            "distinct_bills": int(group.bill_number.nunique()),
            "observed_pattern": pattern_sentence(group),
            "first_vote_date": group.vote_date.min(),
            "last_vote_date": group.vote_date.max(),
            "source_urls": " | ".join(dict.fromkeys(group.source_url.dropna().astype(str))),
        })
    summary = pd.DataFrame(summaries)
    summary.to_csv(RESEARCH / "candidate_vote_issue_summary.csv", index=False)

    ordered = cohort.sort_values(["best_cmo", "candidate"], ascending=[False, True])
    lines = [
        "# Candidate issue profiles from recorded votes",
        "",
        "This report describes what each candidate did on the manually reviewed, issue-relevant "
        "Alabama legislative roll calls currently in the research dataset. It deliberately excludes "
        "sponsorships, amendments, campaign statements, endorsements, and party labels so the claims "
        "below remain specifically about recorded Yea and Nay votes.",
        "",
        f"The evidence contains **{evidence.roll_call_id.nunique()} distinct reviewed roll calls**, "
        f"**{len(evidence)} candidate–issue vote records**, **{evidence.person_id.nunique()} candidates "
        f"with observed votes**, and **{evidence.human_issue_code.nunique()} issue codes**. The full CMO "
        f"cohort contains **{len(cohort)} candidates**.",
        "",
        "## How to read the profiles",
        "",
        "- A **Yea** means the candidate supported the particular motion described.",
        "- A **Nay** means the candidate opposed that motion. It does not automatically prove support "
        "for the exact opposite policy.",
        "- A bill may appear under more than one issue when the reviewed policy affected multiple dimensions.",
        "- These are reviewed anchor and issue-relevant votes, not an exhaustive ideological coding of "
        "every roll call in the LegiScan archive.",
        "- `Post-election` refers to timing relative to the election cycle for which the candidate enters "
        "the CMO cohort; it does not make the later legislative vote invalid.",
        "",
        "## Candidate profiles",
        "",
    ]

    for person in ordered.itertuples(index=False):
        candidate_votes = evidence.loc[evidence.person_id.eq(person.person_id)].copy()
        lines += [
            f"### {person.candidate.title() if str(person.candidate).isupper() else person.candidate}",
            "",
            f"Indexed CMO race: {int(person.cycle)} {str(person.chamber).title()} District {person.district}. "
            f"Best recorded CMO: {float(person.best_cmo):.1f} points.",
            "",
        ]
        if candidate_votes.empty:
            lines += [
                "**No reviewed roll-call evidence is available for this candidate.** This is not evidence "
                "of moderation, conservatism, progressivism, or avoidance. The candidate may not have served "
                "in the Legislature during the archived period, may not have matched to a reviewed legislator "
                "identity, or may not have cast a Yea/Nay vote on the currently adjudicated roll calls.",
                "",
            ]
            continue

        lines += [
            f"Observed record: **{candidate_votes.roll_call_id.nunique()} distinct roll calls** producing "
            f"**{len(candidate_votes)} issue-coded vote records** across "
            f"**{candidate_votes.human_issue_code.nunique()} issues**.",
            "",
        ]
        for issue, group in candidate_votes.groupby("human_issue_code", sort=True):
            group = group.sort_values(["vote_date", "bill_number", "roll_call_id"])
            label = ISSUE_LABELS.get(issue, issue.replace("_", " ").title())
            lines += [
                f"#### {label}", "", pattern_sentence(group), "",
                substantive_synthesis(group), "",
            ]
            for _, row in group.iterrows():
                source = f"[LegiScan]({row.source_url})"
                if pd.notna(row.state_link) and str(row.state_link).strip():
                    source += f" · [official state record]({row.state_link})"
                lines.append(
                    f"- **{row.vote_date} — {row.bill_number}, {row.vote}:** "
                    f"{vote_sentence(row)} Timing: {timing_label(row.evidence_timing)}. {source}"
                )
            lines.append("")

    output = RESEARCH / "CANDIDATE_VOTE_ISSUE_PROFILES.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"Wrote {output.relative_to(ROOT)} and {len(summary)} candidate-issue summaries "
        f"from {len(evidence)} reviewed vote records"
    )


if __name__ == "__main__":
    main()
