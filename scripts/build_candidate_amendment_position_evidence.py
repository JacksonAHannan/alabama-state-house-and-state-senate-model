"""Convert manually adjudicated focal amendments into sourced position evidence."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
DATA = ROOT / "data" / "processed" / "legislative"


def main() -> None:
    adjudications = pd.read_csv(RESEARCH / "human_amendment_adjudications.csv")
    adjudications = adjudications.loc[adjudications.review_status.eq("reviewed")].copy()
    if "position_evidence_allowed" not in adjudications.columns:
        raise ValueError(
            "Human amendment adjudications must explicitly set "
            "position_evidence_allowed"
        )
    allowed = adjudications.position_evidence_allowed.astype(str).str.lower().map(
        {"true": True, "false": False}
    )
    if allowed.isna().any():
        bad = adjudications.loc[allowed.isna(), "amendment_id"].tolist()
        raise ValueError(f"Invalid position_evidence_allowed values: {bad}")
    adjudications = adjudications.loc[allowed].copy()
    manifest = pd.read_csv(DATA / "focal_amendment_text_manifest.csv")
    manifest = manifest.drop_duplicates("amendment_id")
    validation = pd.read_csv(DATA / "focal_amendment_bill_link_validation.csv")
    validation = validation.drop_duplicates("amendment_id")
    manifest = manifest.merge(validation, on="amendment_id", how="left", validate="one_to_one")
    evidence = adjudications.merge(
        manifest,
        on="amendment_id",
        how="left",
        validate="one_to_one",
    )
    if evidence.person_id.isna().any():
        missing = evidence.loc[evidence.person_id.isna(), "amendment_id"].tolist()
        raise ValueError(f"Reviewed amendment IDs absent from manifest: {missing}")
    evidence = evidence.loc[evidence.position_inference_allowed.eq(True)].copy()
    evidence["issue"] = evidence.human_issue_code
    evidence["stance_code"] = "amendment_support"
    evidence["position_summary"] = evidence.candidate_position
    evidence["evidence_date"] = evidence.date
    evidence["temporal_status"] = evidence.activity_timing.map({
        "pre_or_during_election": "pre_election",
        "post_election": "post_election",
    })
    evidence["source_url"] = evidence.url
    columns = [
        "amendment_id", "person_id", "candidate", "election_cycle", "bill_number",
        "issue", "stance_code", "position_summary", "revision_direction",
        "ideological_valence", "evidence_date", "temporal_status", "confidence",
        "source_url", "local_text", "review_note",
        "linked_bill_number", "header_bill_number", "bill_link_status",
    ]
    evidence[columns].to_csv(
        RESEARCH / "candidate_amendment_position_evidence.csv", index=False
    )
    print(f"Wrote {len(evidence)} manually adjudicated amendment positions")


if __name__ == "__main__":
    main()
