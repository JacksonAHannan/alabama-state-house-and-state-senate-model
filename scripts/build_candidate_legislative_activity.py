"""Build focal-candidate sponsorship, amendment, and committee-activity evidence.

Sponsorship is treated as priority evidence, not automatically as a policy stance.
Amendment authors are attributed only when a reviewed legislator's surname appears
in LegiScan's amendment title. Committee-authored amendments remain unattributed.
"""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"
RESEARCH = ROOT / "research" / "cmo_ideology"


# Multi-label, deliberately conservative issue tagging from official synopsis text and
# LegiScan subject labels. Ambiguous broad words are avoided where possible.
ISSUE_PATTERNS = {
    "public_education": r"\b(public schools?|teachers?|education budget|school boards?|classrooms?|universit(?:y|ies)|community colleges?)\b",
    "school_choice": r"\b(charter schools?|school choice|education savings account|vouchers?|private schools?)\b",
    "healthcare_medicaid": r"\b(medicaid|health insurance|hospitals?|health care|healthcare)\b",
    "labor_unions": r"\b(labor unions?|collective bargaining|right[- ]to[- ]work|workers?' compensation)\b",
    "guns": r"\b(firearms?|handguns?|pistols?|guns?|concealed carry|weapons?)\b",
    "abortion": r"\b(abortion|unborn|fetal|fetus|pregnancy termination)\b",
    "taxes_budget": r"\b(tax(?:es|ation)?|appropriations?|general fund|education trust fund|budget|revenue)\b",
    "business_economic_development": r"\b(economic development|job creation|business incentives?|industrial development|commerce|small business)\b",
    "ethics_government": r"\b(ethics|campaign contributions?|open records?|public records?|lobbyists?|government transparency|conflicts? of interest)\b",
    "lgbtq_cultural": r"\b(transgender|sexual orientation|gender identity|same[- ]sex|drag (?:show|performance)|pronouns?)\b",
    "gambling": r"\b(gambling|lotter(?:y|ies)|casino|bingo|sports betting)\b",
    "infrastructure_energy": r"\b(highways?|roads?|bridges?|broadband|utilities|electricity|natural gas|infrastructure)\b",
    "health_social_services": r"\b(mental health|human services|child welfare|foster care|public assistance|disabilit(?:y|ies))\b",
    "criminal_justice": r"\b(criminal|prisons?|corrections|sentenc(?:e|ing)|parole|probation|law enforcement|police|death penalty)\b",
    "environment": r"\b(environment|pollution|conservation|water quality|air quality|hazardous waste)\b",
    "immigration": r"\b(immigration|undocumented|illegal aliens?|e-verify)\b",
    "rural_hunting": r"\b(hunting|fishing|wildlife|game and fish|agriculture|farmers?|forestry|rural)\b",
    "public_employee_benefits": r"\b(retirement systems? of alabama|public employees?' (?:retirement|benefits)|teachers?' retirement|state employees?' insurance)\b",
    "assisted_dying": r"\b(assisted suicide|physician-assisted|right to die)\b",
    "healthcare_conscience": r"\b(healthcare conscience|health care conscience|religious conscience)\b",
    "public_private_partnerships": r"\b(public-private|public private partnership|p3 project)\b",
    "occupational_licensing": r"\b(occupational licens|professional licens|licensing board)\b",
    "anti_esg_governance": r"\b(environmental,? social,? and governance|\besg\b|boycott.*(?:firearm|energy)|debanking)\b",
    "racial_civil_rights": r"\b(civil rights?|racial discrimination|race discrimination|"
                            r"voting rights?|equal protection|hate crimes?|racial profiling|"
                            r"minority representation)\b",
    "minimum_wage_worker_pay": r"\b(minimum wage|living wage|wage increase|worker pay|"
                               r"employee pay|overtime pay|prevailing wage)\b",
}

ELECTION_DATES = {
    2010: pd.Timestamp("2010-11-02"),
    2014: pd.Timestamp("2014-11-04"),
    2018: pd.Timestamp("2018-11-06"),
    2022: pd.Timestamp("2022-11-08"),
}


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def issue_tags(row: pd.Series) -> list[str]:
    haystack = " | ".join(
        normalize(row.get(column, ""))
        for column in ["title", "description", "bill_title", "bill_description", "subject_names"]
    ).lower()
    return [issue for issue, pattern in ISSUE_PATTERNS.items() if re.search(pattern, haystack, re.I)]


def temporal_status(activity_date: object, election_year: int) -> str:
    election_date = ELECTION_DATES[int(election_year)]
    date = pd.to_datetime(activity_date, errors="coerce")
    if pd.isna(date):
        return "date_unknown"
    return "pre_or_during_election" if date <= election_date else "post_election"


def named_instrument_pattern(last_name: str) -> str:
    """Match a named amendment/substitute author, not a committee such as Ways and Means."""
    ordinal = r"(?:(?:first|second|third|fourth|\d+(?:st|nd|rd|th))\s+)?"
    instrument = r"(?:Amendment|Substitute|amendment|substitution)"
    return (rf"(?<![A-Za-z]){re.escape(last_name)}(?![A-Za-z])"
            rf"(?:\s+\([A-Za-z]+\))?\s+{ordinal}{instrument}\b")


def main() -> None:
    crosswalk = pd.read_csv(RESEARCH / "focal_legislator_identity_crosswalk.csv")
    identities = crosswalk.loc[
        crosswalk.review_status.eq("reviewed") & crosswalk.legiscan_people_id.notna()
    ].copy()
    identities["legiscan_people_id"] = identities.legiscan_people_id.astype(int)

    bills = pd.read_csv(DATA / "legiscan_alabama_bills.csv")
    history = pd.read_csv(DATA / "legiscan_bill_history.csv")
    first_actions = (history.assign(_date=pd.to_datetime(history.action_date, errors="coerce"))
                     .groupby("bill_id")._date.min().rename("first_action_date")
                     .reset_index())
    first_floor_orders = (history.loc[
        history.action.fillna("").str.contains(
            r"read (?:a |the )?third time|third reading|passed (?:the )?(?:house|senate)|"
            r"passed as amended|final passage",
            case=False, regex=True,
        )
    ].groupby("bill_id").history_order.min().rename("first_floor_passage_order")
      .reset_index())
    bills = bills.merge(first_actions, on="bill_id", how="left", validate="one_to_one")
    subjects = pd.read_csv(DATA / "legiscan_bill_subjects.csv")
    subject_text = (subjects.groupby("bill_id").subject_name
                    .agg(lambda values: "; ".join(dict.fromkeys(map(str, values))))
                    .rename("subject_names").reset_index())
    bills = bills.merge(subject_text, on="bill_id", how="left", validate="one_to_one")
    bills["subject_names"] = bills.subject_names.fillna("")

    sponsors = pd.read_csv(DATA / "legiscan_bill_sponsors.csv")
    role_counts = (sponsors.groupby(["bill_id", "sponsor_type_id"]).people_id.nunique()
                   .rename("same_role_sponsor_count").reset_index())
    sponsors = sponsors.merge(
        role_counts, on=["bill_id", "sponsor_type_id"], how="left",
        validate="many_to_one",
    )
    sponsored = identities.merge(
        sponsors, left_on="legiscan_people_id", right_on="people_id",
        how="inner", suffixes=("_candidate", "_sponsor"), validate="one_to_many",
    ).merge(
        bills[["bill_id", "session_year", "first_action_date", "title", "description", "status",
               "status_date", "url", "state_link", "subject_names"]],
        on="bill_id", how="left", validate="many_to_one",
    )
    sponsored["sponsorship_role"] = sponsored.sponsor_type_id.map({
        0: "joint_sponsor", 1: "primary_sponsor", 2: "cosponsor"
    }).fillna("unknown")
    sponsored["priority_weight"] = sponsored.apply(
        lambda row: (
            1.0 if row.sponsorship_role == "primary_sponsor" else
            1.0 / max(1, int(row.same_role_sponsor_count))
            if row.sponsorship_role == "joint_sponsor" else
            0.25 / max(1, int(row.same_role_sponsor_count))
            if row.sponsorship_role == "cosponsor" else 0.0
        ), axis=1
    )
    sponsored["activity_date"] = sponsored.first_action_date.fillna(sponsored.status_date)
    sponsored["activity_timing"] = sponsored.apply(
        lambda row: temporal_status(row.activity_date, int(row.election_cycle)), axis=1
    )
    sponsored["issue"] = sponsored.apply(issue_tags, axis=1)
    sponsored["issue"] = sponsored.issue.map(lambda values: values or ["unclassified"])
    sponsored = sponsored.explode("issue")
    sponsor_columns = [
        "person_id", "candidate", "election_cycle", "candidate_chamber",
        "candidate_district", "legiscan_people_id", "bill_id", "bill_number",
        "session_year", "session_name", "sponsorship_role", "sponsor_order",
        "same_role_sponsor_count", "priority_weight", "activity_date",
        "issue", "subject_names", "title", "description", "status", "status_date",
        "activity_timing", "url", "state_link",
    ]
    sponsored[sponsor_columns].sort_values(
        ["election_cycle", "candidate", "session_year", "bill_number", "issue"]
    ).to_csv(RESEARCH / "candidate_sponsored_bill_evidence.csv", index=False)

    summary = (sponsored.groupby([
        "person_id", "candidate", "election_cycle", "issue", "activity_timing",
        "sponsorship_role"
    ]).agg(bill_count=("bill_id", "nunique"),
           weighted_priority=("priority_weight", "sum"),
           enacted_count=("status", lambda values: pd.to_numeric(values, errors="coerce").ge(4).sum()),
           source_count=("url", "nunique"))
      .reset_index())
    summary.to_csv(RESEARCH / "candidate_sponsorship_issue_summary.csv", index=False)

    # Publication-facing priority matrix: only primary/joint sponsorship, because a
    # long cosponsor list is substantially weaker evidence of agenda priority.
    cohort = pd.read_csv(RESEARCH / "candidate_cohort.csv")
    issues = list(ISSUE_PATTERNS)
    strong = summary.loc[
        summary.sponsorship_role.isin(["primary_sponsor", "joint_sponsor"])
        & summary.issue.isin(issues)
    ].copy()
    strong["timing_prefix"] = strong.activity_timing.map({
        "pre_or_during_election": "E", "post_election": "L"
    })
    strong = (strong.groupby(["person_id", "election_cycle", "issue", "timing_prefix"])
              .agg(bill_count=("bill_count", "sum"),
                   weighted_priority=("weighted_priority", "sum")).reset_index())
    strong["priority_cell"] = strong.apply(
        lambda row: f"{row.timing_prefix}:{row.weighted_priority:.1f} ({int(row.bill_count)} bills)", axis=1
    )
    cells = (strong.groupby(["person_id", "election_cycle", "issue"])
             .priority_cell.agg(lambda values: "; ".join(values)).reset_index())
    grid = cohort[["person_id", "candidate", "cycle", "chamber", "district", "best_cmo"]].copy()
    grid = grid.rename(columns={"cycle": "election_cycle"})
    grid = grid.assign(_key=1).merge(
        pd.DataFrame({"issue": issues, "_key": 1}), on="_key"
    ).drop(columns="_key")
    priority_long = grid.merge(
        cells, on=["person_id", "election_cycle", "issue"], how="left"
    )
    priority_long["priority_cell"] = priority_long.priority_cell.fillna("")
    priority_long.to_csv(RESEARCH / "candidate_legislative_priority_matrix_long.csv", index=False)
    priority_wide = priority_long.pivot(
        index=["person_id", "candidate", "election_cycle", "chamber", "district", "best_cmo"],
        columns="issue", values="priority_cell"
    ).reset_index()
    priority_wide.to_csv(RESEARCH / "candidate_legislative_priority_matrix.csv", index=False)

    # Bounded direction-review queue: up to three strongest pre-election instruments
    # per candidate/issue. Full sponsorship evidence remains in the bill-level file.
    review = sponsored.loc[
        sponsored.activity_timing.eq("pre_or_during_election")
        & sponsored.sponsorship_role.isin(["primary_sponsor", "joint_sponsor"])
        & sponsored.issue.isin(issues)
    ].copy()
    review["role_priority"] = review.sponsorship_role.map({
        "primary_sponsor": 2, "joint_sponsor": 1
    })
    review["status_numeric"] = pd.to_numeric(review.status, errors="coerce").fillna(0)
    review = review.sort_values(
        ["person_id", "election_cycle", "issue", "role_priority",
         "priority_weight", "status_numeric", "activity_date"],
        ascending=[True, True, True, False, False, False, False],
    ).groupby(["person_id", "election_cycle", "issue"], as_index=False).head(3)
    text_manifest = pd.read_csv(DATA / "alabama_bill_text_archive_reconciliation.csv")
    text_manifest = text_manifest.loc[text_manifest.archive_status.eq("present")].copy()
    text_manifest["version_priority"] = text_manifest.document_type.map({
        "Enrolled": 3, "Engrossed": 2, "Introduced": 1
    }).fillna(0)
    canonical_text = (text_manifest.sort_values(
        ["bill_id", "version_priority", "document_date", "doc_id"]
    ).drop_duplicates("bill_id", keep="last")[[
        "bill_id", "doc_id", "document_type", "local_path"
    ]].rename(columns={
        "doc_id": "text_doc_id", "document_type": "text_document_type",
        "local_path": "bill_text_path",
    }))
    review = review.merge(canonical_text, on="bill_id", how="left", validate="many_to_one")
    review["review_status"] = "needs_human_direction_review"
    review["position_inference_allowed"] = False
    review["review_note"] = (
        "Sponsorship establishes priority; inspect bill text before assigning policy direction or stance."
    )
    review_columns = [
        "person_id", "candidate", "election_cycle", "issue", "bill_id",
        "bill_number", "session_year", "activity_date", "sponsorship_role",
        "same_role_sponsor_count", "priority_weight", "title", "description",
        "subject_names", "url", "state_link", "text_doc_id", "text_document_type",
        "bill_text_path", "review_status", "position_inference_allowed", "review_note",
    ]
    review[review_columns].to_csv(
        RESEARCH / "candidate_sponsorship_direction_review_queue.csv", index=False
    )

    amendments = pd.read_csv(DATA / "legiscan_bill_amendments.csv")
    amendments = amendments.merge(
        bills[["bill_id", "session_year", "title", "description", "url", "subject_names"]]
        .rename(columns={"title": "bill_title", "description": "bill_description", "url": "bill_url"}),
        on="bill_id", how="left", validate="many_to_one",
    )
    amendment_rows = []
    for identity in identities.itertuples(index=False):
        last_name = normalize(identity.legiscan_name).split()[-1]
        # Parenthetical initials and chamber prefixes may surround the surname.
        matched = amendments.loc[
            amendments.title.fillna("").str.contains(
                named_instrument_pattern(last_name), case=False, regex=True
            )
        ].copy()
        if matched.empty:
            continue
        matched["person_id"] = identity.person_id
        matched["candidate"] = identity.candidate
        matched["election_cycle"] = int(identity.election_cycle)
        matched["legiscan_people_id"] = int(identity.legiscan_people_id)
        matched["attributed_name"] = last_name
        matched["attribution_method"] = "reviewed_identity_surname_in_amendment_title"
        matched["attribution_confidence"] = "high"
        matched["activity_timing"] = matched.date.map(
            lambda date: temporal_status(date, int(identity.election_cycle))
        )
        matched["issue"] = matched.apply(issue_tags, axis=1)
        matched["issue"] = matched.issue.map(lambda values: values or ["unclassified"])
        amendment_rows.append(matched.explode("issue"))
    if amendment_rows:
        attributed = pd.concat(amendment_rows, ignore_index=True)
    else:
        attributed = pd.DataFrame()
    amendment_columns = [
        "person_id", "candidate", "election_cycle", "legiscan_people_id",
        "bill_id", "bill_number", "session_year", "session_name", "amendment_id",
        "date", "chamber", "title", "description", "adopted", "issue",
        "attributed_name", "attribution_method", "attribution_confidence",
        "activity_timing", "url", "state_link", "bill_url", "bill_title",
        "bill_description", "subject_names",
    ]
    attributed.reindex(columns=amendment_columns).sort_values(
        ["election_cycle", "candidate", "date", "amendment_id", "issue"]
    ).to_csv(RESEARCH / "candidate_attributed_amendments.csv", index=False)

    history = history.merge(
        bills[["bill_id", "session_year", "title", "description", "url", "subject_names"]]
        .rename(columns={"title": "bill_title", "description": "bill_description", "url": "bill_url"}),
        on="bill_id", how="left", validate="many_to_one",
    )
    named_actions = []
    for identity in identities.itertuples(index=False):
        last_name = normalize(identity.legiscan_name).split()[-1]
        matched = history.loc[
            history.action.fillna("").str.contains(
                named_instrument_pattern(last_name), case=False, regex=True
            )
        ].copy()
        if matched.empty:
            continue
        matched["person_id"] = identity.person_id
        matched["candidate"] = identity.candidate
        matched["election_cycle"] = int(identity.election_cycle)
        matched["legiscan_people_id"] = int(identity.legiscan_people_id)
        matched["matched_name"] = last_name
        matched["activity_timing"] = matched.action_date.map(
            lambda date: temporal_status(date, int(identity.election_cycle))
        )
        named_actions.append(matched)
    named = pd.concat(named_actions, ignore_index=True) if named_actions else pd.DataFrame()
    named_columns = [
        "person_id", "candidate", "election_cycle", "legiscan_people_id",
        "bill_id", "bill_number", "session_year", "session_name", "history_order",
        "action_date", "action", "chamber", "importance", "matched_name",
        "activity_timing", "bill_url", "bill_title", "bill_description", "subject_names",
    ]
    named.reindex(columns=named_columns).sort_values(
        ["election_cycle", "candidate", "action_date", "bill_id", "history_order"]
    ).to_csv(RESEARCH / "candidate_named_legislative_actions.csv", index=False)

    # Committee events on bills sponsored by focal legislators. These establish a
    # bill's path through committee, not the individual sponsor's committee vote.
    sponsored_bills = sponsored[[
        "person_id", "candidate", "election_cycle", "legiscan_people_id",
        "bill_id", "sponsorship_role", "activity_timing",
    ]].drop_duplicates()
    committee = history.loc[
        history.action.fillna("").str.contains(
            r"committee|reported from|reported out|referred to", case=False, regex=True
        )
    ].copy()
    committee = sponsored_bills.merge(
        committee, on="bill_id", how="inner", validate="many_to_many"
    )
    committee = committee.merge(
        first_floor_orders, on="bill_id", how="left", validate="many_to_one"
    )
    committee = committee.rename(columns={"activity_timing": "sponsorship_timing"})
    committee["activity_timing"] = committee.apply(
        lambda row: temporal_status(row.action_date, int(row.election_cycle)), axis=1
    )
    committee["committee_event_type"] = "other_committee_event"
    committee.loc[
        committee.action.str.contains(r"referred to", case=False, na=False),
        "committee_event_type"
    ] = "referral"
    committee.loc[
        committee.action.str.contains(r"reported from|reported out", case=False, na=False),
        "committee_event_type"
    ] = "committee_report"
    committee.loc[
        committee.action.str.contains(r"amendment|substitute", case=False, na=False),
        "committee_event_type"
    ] = "committee_instrument_action"
    committee["individual_member_action_observed"] = False
    committee["floor_passage_observed"] = committee.first_floor_passage_order.notna()
    committee["pre_first_floor_passage"] = (
        committee.first_floor_passage_order.isna()
        | committee.history_order.lt(committee.first_floor_passage_order)
    )
    committee["inference_limit"] = (
        "Event concerns a sponsored bill; source does not identify the candidate's committee vote or conduct."
    )
    committee_columns = [
        "person_id", "candidate", "election_cycle", "legiscan_people_id",
        "bill_id", "bill_number", "session_year", "session_name", "sponsorship_role",
        "sponsorship_timing", "activity_timing", "history_order", "action_date", "action", "chamber",
        "importance", "committee_event_type", "first_floor_passage_order",
        "pre_first_floor_passage", "floor_passage_observed", "individual_member_action_observed",
        "inference_limit", "bill_url", "bill_title", "bill_description", "subject_names",
    ]
    committee[committee_columns].sort_values(
        ["election_cycle", "candidate", "action_date", "bill_id", "history_order"]
    ).to_csv(RESEARCH / "candidate_sponsored_bill_committee_events.csv", index=False)

    coverage = identities[[
        "person_id", "candidate", "election_cycle", "legiscan_people_id",
        "match_method", "review_status"
    ]].copy()
    sponsor_counts = sponsored.groupby("person_id").bill_id.nunique()
    amendment_counts = (attributed.groupby("person_id").amendment_id.nunique()
                        if not attributed.empty else pd.Series(dtype=int))
    action_counts = (named.groupby("person_id").size()
                     if not named.empty else pd.Series(dtype=int))
    coverage["sponsored_bills"] = coverage.person_id.map(sponsor_counts).fillna(0).astype(int)
    coverage["attributed_amendments"] = coverage.person_id.map(amendment_counts).fillna(0).astype(int)
    coverage["named_history_actions"] = coverage.person_id.map(action_counts).fillna(0).astype(int)
    committee_bill_counts = committee.groupby("person_id").bill_id.nunique()
    coverage["sponsored_bills_with_committee_events"] = coverage.person_id.map(
        committee_bill_counts
    ).fillna(0).astype(int)
    coverage.to_csv(RESEARCH / "candidate_legislative_activity_coverage.csv", index=False)

    print(
        f"Wrote {sponsored.bill_id.nunique():,} focal sponsored bills, "
        f"{attributed.amendment_id.nunique() if not attributed.empty else 0:,} "
        f"attributed amendments, and {len(named):,} named history actions for "
        f"{len(identities)} reviewed legislator identities"
    )


if __name__ == "__main__":
    main()
