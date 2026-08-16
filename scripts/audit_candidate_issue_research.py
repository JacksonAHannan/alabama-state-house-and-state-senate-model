"""Produce a requirement-level audit of the candidate-issue research pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
DATA = ROOT / "data" / "processed" / "legislative"


def read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def main() -> None:
    archive = read(DATA / "alabama_bill_text_archive_reconciliation.csv")
    amendments_archive = read(DATA / "alabama_amendment_download_status.csv")
    identities = read(RESEARCH / "focal_legislator_identity_crosswalk.csv")
    sponsored = read(RESEARCH / "candidate_sponsored_bill_evidence.csv")
    attributed = read(RESEARCH / "candidate_attributed_amendments.csv")
    amendment_text = read(DATA / "focal_amendment_text_manifest.csv")
    amendment_validation = read(DATA / "focal_amendment_bill_link_validation.csv")
    amendment_llm = read(RESEARCH / "amendment_llm_classifications.csv")
    amendment_consensus = read(RESEARCH / "amendment_llm_consensus_review.csv")
    amendment_human = read(RESEARCH / "human_amendment_adjudications.csv")
    sponsorship_llm = read(RESEARCH / "sponsorship_bill_llm_classifications.csv")
    sponsorship_review = read(RESEARCH / "candidate_sponsorship_direction_llm_review.csv")
    sponsorship_human = read(RESEARCH / "human_sponsorship_adjudications.csv")
    sponsorship_validation = read(DATA / "sponsorship_bill_text_link_validation.csv")
    committee = read(RESEARCH / "candidate_sponsored_bill_committee_events.csv")
    public_decisions = read(RESEARCH / "candidate_public_position_review_decisions.csv")
    public_queue = read(RESEARCH / "candidate_public_position_review_queue.csv")
    campaign_queue = read(RESEARCH / "candidate_campaign_position_research_queue.csv")
    positions = read(RESEARCH / "state_issue_position_ledger.csv")
    matrix = read(RESEARCH / "candidate_state_issue_matrix_long.csv")
    cohort = read(RESEARCH / "candidate_cohort.csv")

    valid_amendment_ids = set(
        amendment_validation.loc[
            amendment_validation.position_inference_allowed.eq(True), "amendment_id"
        ].astype(int)
    ) if not amendment_validation.empty else set()
    attributed_amendment_count = len(valid_amendment_ids)
    expected_amendment_models = attributed_amendment_count * 2
    cached_amendment_models = sum(
        1 for path in (RESEARCH / "amendment_llm_classifications").glob("*.json")
        if int(path.stem.split("_", 1)[0]) in valid_amendment_ids
    )
    final_valid_models = (
        amendment_llm.amendment_id.astype(int).isin(valid_amendment_ids).sum()
        if not amendment_llm.empty else 0
    )
    amendment_models_observed = max(final_valid_models, cached_amendment_models)
    reviewed_amendments = (
        amendment_human.loc[
            amendment_human.review_status.eq("reviewed")
            & amendment_human.amendment_id.astype(int).isin(valid_amendment_ids)
        ]
        .amendment_id.nunique()
    ) if not amendment_human.empty else 0
    consensus_valid_count = (
        amendment_consensus.amendment_id.astype(int).isin(valid_amendment_ids).sum()
        if not amendment_consensus.empty else 0
    )
    extracted_valid_count = (
        amendment_text.loc[
            amendment_text.amendment_id.astype(int).isin(valid_amendment_ids)
            & amendment_text.text_status.eq("extracted"), "amendment_id"
        ].nunique()
        if not amendment_text.empty else 0
    )
    valid_sponsorship_ids = set(
        sponsorship_validation.loc[
            sponsorship_validation.position_review_allowed.eq(True), "bill_id"
        ].astype(int)
    ) if not sponsorship_validation.empty else set()
    sponsorship_bills_expected = len(valid_sponsorship_ids)
    sponsorship_models_expected = sponsorship_bills_expected * 2
    cached_sponsorship_models = sum(
        1 for path in (RESEARCH / "sponsorship_bill_llm_classifications").glob("*.json")
        if int(path.stem.split("_", 1)[0]) in valid_sponsorship_ids
    )
    final_sponsorship_models = (
        sponsorship_llm.bill_id.astype(int).isin(valid_sponsorship_ids).sum()
        if not sponsorship_llm.empty else 0
    )
    sponsorship_models_observed = max(
        cached_sponsorship_models, final_sponsorship_models
    )
    reviewed_sponsorship_bills = (
        sponsorship_human.loc[
            sponsorship_human.review_status.eq("reviewed")
            & sponsorship_human.bill_id.astype(int).isin(valid_sponsorship_ids)
        ]
        .bill_id.nunique()
    ) if not sponsorship_human.empty else 0
    reviewed_identities = int(
        identities.review_status.eq("reviewed").sum()
    ) if not identities.empty else 0
    valid_committee_semantics = bool(
        not committee.empty
        and committee.individual_member_action_observed.eq(False).all()
        and committee.inference_limit.notna().all()
    )
    sourced_positions = int(
        positions.source_url.fillna("").ne("").sum()
    ) if not positions.empty else 0
    matrix_people = matrix.person_id.nunique() if not matrix.empty else 0
    matrix_issues = matrix.issue.nunique() if not matrix.empty else 0
    open_campaign_rows = int(
        campaign_queue.review_status.fillna("").str.startswith("open").sum()
    ) if not campaign_queue.empty else 0

    requirements = {
        "bill_text_archive": {
            "complete": bool(not archive.empty),
            "expected_versions": int(len(archive)),
            "present_versions": int(archive.archive_status.eq("present").sum()) if not archive.empty else 0,
            "missing_versions": int(archive.archive_status.ne("present").sum()) if not archive.empty else 0,
        },
        "sponsorships": {
            "complete": bool(not sponsored.empty),
            "distinct_bills": int(sponsored.bill_id.nunique()) if not sponsored.empty else 0,
            "reviewed_legislator_identities": reviewed_identities,
            "focal_candidate_cases": int(len(cohort)),
        },
        "amendment_attribution_and_text": {
            "complete": bool(
                attributed_amendment_count > 0
                and extracted_valid_count == attributed_amendment_count
            ),
            "attributed_amendments": int(attributed_amendment_count),
            "texts_extracted": int(extracted_valid_count),
        },
        "amendment_revision_direction": {
            "complete": bool(
                expected_amendment_models > 0
                and amendment_models_observed == expected_amendment_models
                and consensus_valid_count == attributed_amendment_count
                and reviewed_amendments == attributed_amendment_count
            ),
            "expected_model_cases": int(expected_amendment_models),
            "observed_model_cases": int(amendment_models_observed),
            "human_reviewed_amendments": int(reviewed_amendments),
            "human_adjudication_required": True,
            "excluded_cross_bill_links": int(
                amendment_validation.bill_link_status.eq("mismatch").sum()
            ) if not amendment_validation.empty else 0,
        },
        "sponsorship_policy_direction": {
            "complete": bool(
                sponsorship_models_expected > 0
                and sponsorship_models_observed == sponsorship_models_expected
                and not sponsorship_review.empty
                and reviewed_sponsorship_bills == sponsorship_bills_expected
            ),
            "review_bills": int(sponsorship_bills_expected),
            "expected_model_cases": int(sponsorship_models_expected),
            "observed_model_cases": int(sponsorship_models_observed),
            "human_reviewed_bills": int(reviewed_sponsorship_bills),
            "human_adjudication_required": True,
            "excluded_bad_text_links": int(
                sponsorship_validation.position_review_allowed.eq(False).sum()
            ) if not sponsorship_validation.empty else 0,
        },
        "pre_floor_committee_activity": {
            "complete": valid_committee_semantics,
            "committee_path_events": int(len(committee)),
            "pre_first_floor_passage_events": int(committee.pre_first_floor_passage.sum()) if not committee.empty else 0,
            "individual_votes_available": False,
        },
        "public_campaign_positions": {
            "complete": bool(public_queue.empty and open_campaign_rows == 0),
            "sourced_position_rows": sourced_positions,
            "reviewed_nonposition_sources": int(len(public_decisions)),
            "pending_ranked_sources": int(len(public_queue)),
            "open_campaign_issue_searches": open_campaign_rows,
            "open_campaign_candidates": int(
                campaign_queue.loc[
                    campaign_queue.review_status.fillna("").str.startswith("open"),
                    "person_id",
                ].nunique()
            ) if not campaign_queue.empty else 0,
        },
        "matrix_integration": {
            "complete": bool(
                matrix_people == len(cohort)
                and sourced_positions > 0
                and matrix.source_url.loc[matrix.documented].fillna("").ne("").all()
            ),
            "candidate_cases": int(matrix_people),
            "issues": int(matrix_issues),
            "documented_evidence_rows": int(matrix.documented.sum()) if not matrix.empty else 0,
        },
    }
    overall_complete = all(item["complete"] for item in requirements.values())
    payload = {"overall_complete": overall_complete, "requirements": requirements}
    (RESEARCH / "candidate_issue_research_audit.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    lines = ["# Candidate-issue research completion audit", "",
             f"Overall automated completion: **{overall_complete}**", ""]
    for name, item in requirements.items():
        lines += [f"## {name.replace('_', ' ').title()}", "",
                  f"Status: **{'complete' if item['complete'] else 'in progress'}**", ""]
        lines += [f"- {key.replace('_', ' ')}: `{value}`"
                  for key, value in item.items() if key != "complete"]
        lines.append("")
    (RESEARCH / "CANDIDATE_ISSUE_RESEARCH_AUDIT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
