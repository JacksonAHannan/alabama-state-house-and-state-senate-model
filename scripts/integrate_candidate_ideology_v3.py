"""Attach audited ontology-v3 ideology features to canonical CMO candidates."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ELECTIONS = ROOT / "data" / "processed" / "elections"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"


def main() -> None:
    base = pd.read_csv(ELECTIONS / "canonical_cmo_candidates_with_votesmart.csv", low_memory=False)
    features = pd.read_csv(IDEOLOGY / "candidate_ideology_v3_model_features.csv")
    positions = pd.read_csv(IDEOLOGY / "candidate_issue_valence_v3.csv")
    if not features.canonical_candidate_id.is_unique:
        raise ValueError("Ontology-v3 model features are not candidate-unique")
    counts = (positions.groupby("canonical_candidate_id")
              .agg(ideology_v3_issue_count=("primitive_axis", "nunique"),
                   ideology_v3_scored_issue_count=("issue_score_available", "sum"),
                   ideology_v3_evidence_records=("evidence_records", "sum"),
                   ideology_v3_source_type_count=("source_type_count", "max"),
                   ideology_v3_max_conflict_ratio=("conflict_ratio", "max"))
              .reset_index())
    # Issue-only candidates (for example, a firearms rating when firearms does
    # not load onto a broad family) must remain represented. Start from issue
    # coverage rather than from the narrower family-feature pivot.
    features = counts.merge(features, on="canonical_candidate_id", how="left", validate="one_to_one")
    output = base.merge(features, on="canonical_candidate_id", how="left", validate="one_to_one")
    output["ideology_v3_available"] = output.ideology_v3_issue_count.fillna(0).gt(0)
    family_columns = [column for column in output if column.startswith("ideology_v3_")
                      and column not in {"ideology_v3_issue_count", "ideology_v3_scored_issue_count",
                                         "ideology_v3_evidence_records", "ideology_v3_source_type_count",
                                         "ideology_v3_max_conflict_ratio", "ideology_v3_available"}]
    output["ideology_v3_scored_family_count"] = output[family_columns].notna().sum(axis=1)
    # Candidate-level ideological comparisons require breadth across at least
    # three issue scores and two independently estimated broad families.
    output["ideology_v3_model_eligible"] = (
        output.ideology_v3_scored_issue_count.fillna(0).ge(3)
        & output.ideology_v3_scored_family_count.ge(2)
    )
    output.to_csv(ELECTIONS / "canonical_cmo_candidates_with_ideology_v3.csv", index=False)
    print(f"Wrote {len(output):,} canonical candidate rows; {output.ideology_v3_available.sum():,} have v3 evidence")


if __name__ == "__main__":
    main()
