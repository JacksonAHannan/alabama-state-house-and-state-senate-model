"""Validate and combine ontology-v3 candidate position evidence sources."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ideology_ontology_v3 import ONTOLOGY_VERSION, family_loading, validate_primitive

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
OUT = IDEOLOGY / "candidate_position_evidence_v3.csv"
COVERAGE_OUT = IDEOLOGY / "candidate_position_evidence_v3_coverage.csv"

REQUIRED_COLUMNS = [
    "ontology_version", "evidence_id", "canonical_candidate_id", "person_id",
    "candidate_name", "election_cycle", "evidence_date", "temporal_status",
    "source_type", "source_provider", "source_record_id", "source_url", "item_id",
    "policy_family", "policy_key", "primitive_axis", "policy_pole",
    "candidate_stance", "position_value", "response_mode", "family",
    "family_direction", "family_contribution", "constituency_tags_json",
    "confidence", "adjudication_authority", "evidence_weight", "source_text",
    "raw_answer",
]
SOURCE_TYPES = {
    "candidate_questionnaire", "legislative_vote", "bill_sponsorship",
    "public_statement", "campaign_website", "campaign_literature",
    "candidate_interview",
}
TEMPORAL_STATUSES = {
    "same_cycle_candidate_statement", "pre_or_during_election", "post_election",
    "date_unknown", "pre_or_same_cycle_legislative_action",
}
STANCES = {"support", "oppose", "maintain", "mixed", "unclear"}


def validate(frame: pd.DataFrame, source: Path) -> pd.DataFrame:
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"{source.name} missing columns: {sorted(missing)}")
    result = frame[REQUIRED_COLUMNS].copy()
    if result.ontology_version.astype(str).ne(ONTOLOGY_VERSION).any():
        raise ValueError(f"{source.name} contains a different ontology version")
    if not set(result.source_type.astype(str)) <= SOURCE_TYPES:
        raise ValueError(f"{source.name} contains an unsupported source type")
    if not set(result.temporal_status.astype(str)) <= TEMPORAL_STATUSES:
        raise ValueError(f"{source.name} contains an unsupported temporal status")
    if not set(result.candidate_stance.astype(str)) <= STANCES:
        raise ValueError(f"{source.name} contains an unsupported candidate stance")
    for row in result.itertuples(index=False):
        validate_primitive(row.primitive_axis, row.policy_pole)
        expected_family, expected_direction = family_loading(row.primitive_axis, row.policy_pole)
        observed_family = str(row.family or "")
        if observed_family != (expected_family or ""):
            raise ValueError(f"family mismatch for evidence {row.evidence_id}")
        if expected_direction is None and str(row.family_direction).strip():
            raise ValueError(f"unexpected family direction for evidence {row.evidence_id}")
        if expected_direction is not None and float(row.family_direction) != expected_direction:
            raise ValueError(f"family direction mismatch for evidence {row.evidence_id}")
        json.loads(row.constituency_tags_json or "[]")
    return result


def main() -> None:
    # Consume only source-specific ledgers. Aggregates, coverage reports, and
    # unmatched review queues must never be read back as upstream evidence.
    sources = [path for path in [IDEOLOGY / "candidate_position_evidence_v3_votesmart.csv"]
               if path.exists()]
    legislative = IDEOLOGY / "candidate_legislative_position_evidence_v3.csv"
    if legislative.exists():
        sources.append(legislative)
    sources = list(dict.fromkeys(sources))
    if not sources:
        raise FileNotFoundError("no ontology-v3 evidence sources found")
    frames = [validate(pd.read_csv(path).fillna(""), path) for path in sources]
    ledger = pd.concat(frames, ignore_index=True)
    duplicates = ledger.evidence_id.astype(str).duplicated(keep=False)
    if duplicates.any():
        raise ValueError(f"duplicate evidence IDs: {sorted(set(ledger.loc[duplicates, 'evidence_id']))[:5]}")
    ledger = ledger.sort_values(["election_cycle", "canonical_candidate_id", "source_type", "policy_key"])
    ledger.to_csv(OUT, index=False)
    coverage = ledger.groupby(
        ["election_cycle", "source_type", "temporal_status"], dropna=False, as_index=False
    ).agg(evidence_rows=("evidence_id", "nunique"),
          candidates=("canonical_candidate_id", lambda s: s.astype(str).replace("", pd.NA).nunique()),
          policies=("policy_key", "nunique"), primitives=("primitive_axis", "nunique"),
          families=("family", lambda s: s.astype(str).replace("", pd.NA).nunique()))
    coverage.to_csv(COVERAGE_OUT, index=False)
    print(f"Combined {len(ledger):,} evidence rows from {len(sources)} source file(s)")
    print("Final candidate ratings are intentionally deferred until additional sources are mapped.")


if __name__ == "__main__":
    main()
