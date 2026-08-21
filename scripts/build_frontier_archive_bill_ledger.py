"""Create one auditable terminal frontier disposition for every archived bill."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
MANUAL = ROOT / "data" / "manual" / "ideology" / "frontier_legislative_bill_adjudications.csv"


def main() -> None:
    bills = pd.read_csv(LEG / "legiscan_alabama_bills.csv", low_memory=False)
    manual = pd.read_csv(MANUAL, low_memory=False)
    texts = pd.read_csv(LEG / "alabama_bill_text_archive_reconciliation.csv", low_memory=False)
    if not bills.bill_id.is_unique or not manual.bill_id.is_unique:
        raise ValueError("Bill identifiers must be unique")
    if set(manual.bill_id) - set(bills.bill_id):
        raise ValueError("Manual decisions reference unknown archive bills")

    text_summary = (texts.groupby("bill_id", as_index=False)
                    .agg(text_version_count=("doc_id", "nunique"),
                         text_available=("archive_status", lambda s: bool(s.eq("present").any())),
                         text_document_types=("document_type", lambda s: ";".join(sorted(set(s.dropna().astype(str))))),
                         text_hashes=("text_hash", lambda s: ";".join(sorted(set(s.dropna().astype(str)))))))
    ledger = bills.merge(text_summary, on="bill_id", how="left", validate="one_to_one")
    ledger = ledger.merge(manual, on=["bill_id", "session_year", "bill_number"], how="left",
                          validate="one_to_one", suffixes=("", "_review"), indicator=True)
    has_vote = ledger._merge.eq("both")
    ledger["recorded_individual_rollcall"] = has_vote
    ledger["archive_disposition"] = ledger["decision"]
    ledger.loc[~has_vote, "archive_disposition"] = "no_recorded_individual_rollcall"
    ledger.loc[~has_vote, "reviewed_document_type"] = "official_synopsis_and_text_inventory"
    ledger.loc[~has_vote, "confidence"] = "high"
    ledger.loc[~has_vote, "rationale"] = (
        "No recorded individual roll call is linked to this archived bill. It is explicitly non-scoring for "
        "candidate voting ideology; its synopsis and available text remain preserved for later sponsorship, "
        "amendment, or committee analysis."
    )
    ledger.loc[~has_vote, "reviewer"] = "frontier_archive_scope_review"
    ledger.loc[~has_vote, "review_date"] = "2026-08-18"
    ledger.loc[~has_vote, "supersedes_authority"] = "implicit_archive_deferral"
    ledger["candidate_vote_scoring_eligible"] = has_vote & ledger.archive_disposition.isin(["map", "multi_axis"])
    ledger["terminal_disposition"] = True
    ledger["text_version_count"] = ledger.text_version_count.fillna(0).astype(int)
    ledger["text_available"] = ledger.text_available.fillna(False).astype(bool)
    ledger = ledger.drop(columns="_merge")
    if len(ledger) != len(bills) or not ledger.bill_id.is_unique:
        raise AssertionError("Archive ledger failed completeness invariants")
    ledger.to_csv(LEG / "frontier_archive_bill_ledger.csv", index=False)
    summary = (ledger.groupby(["recorded_individual_rollcall", "archive_disposition", "text_available"],
                              dropna=False).size().rename("bills").reset_index())
    summary.to_csv(LEG / "frontier_archive_bill_ledger_summary.csv", index=False)
    print(f"Wrote {len(ledger):,} terminal bill dispositions")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
