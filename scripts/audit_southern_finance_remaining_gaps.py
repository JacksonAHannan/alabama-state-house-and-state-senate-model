#!/usr/bin/env python3
"""Publish the remaining Southern finance repair queue from canonical coverage."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/processed/finance/southern_candidate_cycle_finance_coverage.csv"
OUTPUT = ROOT / "data/processed/source_audits/southern_finance_remaining_gap_queue.csv"
MANIFEST = ROOT / "data/processed/source_audits/southern_finance_remaining_gap_queue_manifest.json"


POLICY = {
    "AL": ("residual_source_or_identity_gap", "review the ten unresolved FCPA candidate rows"),
    "AR": ("legacy_report_gap", "extract official legacy reports for 2016-2022; retain 2024 API totals"),
    "FL": ("residual_transaction_reconciliation_gap", "review 2018 legacy detail mismatches, duplicate special/general summaries, invalid contribution codes, and net-negative refunds"),
    "GA": ("residual_candidate_transaction_identity", "review candidates not resolved to the complete 2015-2024 legacy and refreshed Record Search transaction identities"),
    "KY": ("residual_candidate_match_gap", "review unmatched KREF registrations; do not infer zero"),
    "LA": ("residual_candidate_match_gap", "review unmatched filer identities against official bulk files"),
    "MO": ("official_report_access_block", "obtain reports through an authorized non-reCAPTCHA bulk path and recover the legacy 2016-2018 index"),
    "MS": ("paper_filing_ocr_and_portal_identity_gap", "adjudicate candidates absent from the electronic index and unreadable paper filings using cached page-level OCR evidence"),
    "NC": ("residual_committee_identity", "review unresolved candidate committees after the complete 2015-2024 transaction acquisition"),
    "OK": ("residual_candidate_match_gap", "review unmatched Guardian committee identities"),
    "SC": ("identity_or_report_period_review", "resolve ambiguous filer identities and overlapping or boundary-spanning report periods"),
    "TN": ("residual_report_layout_or_candidate_identity", "review the small set of unmatched candidates and report pages without a parseable receipt summary"),
    "TX": ("residual_filer_or_report_period_review", "review unresolved filer links and positive boundary-spanning or overlapping report periods"),
    "VA": ("residual_xml_or_candidate_match", "review unresolved committee identities and report-period gaps after the versioned 2023 refresh"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    coverage = pd.read_csv(INPUT)
    rows = []
    for state, group in coverage.groupby("state", sort=True):
        gap_class, next_action = POLICY[state]
        zero_cycles = group.loc[group.observed_candidates.eq(0), "cycle"].astype(str).tolist()
        rows.append({
            "state": state,
            "target_candidates": int(group.target_candidates.sum()),
            "observed_candidates": int(group.observed_candidates.sum()),
            "candidate_coverage": group.observed_candidates.sum() / group.target_candidates.sum(),
            "unobserved_candidates": int(group.target_candidates.sum() - group.observed_candidates.sum()),
            "zero_coverage_cycles": "|".join(zero_cycles),
            "gap_class": gap_class,
            "next_action": next_action,
            "zero_fill_allowed": 0,
        })
    frame = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT, index=False)
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "pipeline": Path(__file__).relative_to(ROOT).as_posix(),
        "pipeline_sha256": sha256(Path(__file__)),
        "input": INPUT.relative_to(ROOT).as_posix(),
        "input_sha256": sha256(INPUT),
        "output": OUTPUT.relative_to(ROOT).as_posix(),
        "output_sha256": sha256(OUTPUT),
        "states": len(frame),
        "policy": "Unresolved official-source gaps remain unknown and are prioritized by source-specific repair path.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(frame[["state", "observed_candidates", "target_candidates", "candidate_coverage", "gap_class"]].to_string(index=False))


if __name__ == "__main__":
    main()
