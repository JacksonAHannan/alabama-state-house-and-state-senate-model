"""Build stable, non-overlapping review batches covering every Alabama bill."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "research" / "cmo_ideology" / "frontier_legislative_review"
LEDGER = REVIEW / "bill_review_ledger.csv"
BATCHES = REVIEW / "batches"
BATCH_SIZE = 200


def main() -> None:
    ledger = pd.read_csv(LEDGER, low_memory=False)
    ledger = ledger.sort_values(
        ["review_priority", "session_year", "bill_number", "bill_id"]
    ).reset_index(drop=True)
    ledger["review_batch"] = (ledger.index // BATCH_SIZE) + 1
    pending = ledger[ledger.frontier_review_status.ne("reviewed")].copy()

    BATCHES.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    keep = [
        "bill_id", "session_year", "session_name", "bill_number", "title", "description",
        "rollcalls", "mapped_rollcalls", "current_axes", "current_poles", "authorities",
        "taxonomy_warning", "review_priority", "text_documents", "documents_present",
    ]
    for batch_id, frame in pending.groupby("review_batch", sort=True):
        path = BATCHES / f"batch_{int(batch_id):03d}.csv"
        frame[keep].to_csv(path, index=False)
        manifest_rows.append({
            "review_batch": int(batch_id),
            "path": path.relative_to(ROOT).as_posix(),
            "bills": len(frame),
            "with_rollcalls": int(frame.rollcalls.gt(0).sum()),
            "first_year": int(frame.session_year.min()),
            "last_year": int(frame.session_year.max()),
            "minimum_priority": int(frame.review_priority.min()),
            "maximum_priority": int(frame.review_priority.max()),
        })
    pd.DataFrame(manifest_rows).to_csv(REVIEW / "batch_manifest.csv", index=False)

    coverage = pd.DataFrame({
        "metric": ["archive_bills", "reviewed_bills", "pending_bills", "pending_batches"],
        "value": [len(ledger), ledger.frontier_review_status.eq("reviewed").sum(), len(pending), len(manifest_rows)],
    })
    coverage.to_csv(REVIEW / "coverage_status.csv", index=False)
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
