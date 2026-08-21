"""Resolve every candidate-issue conflict with an explicit evidence hierarchy."""
from pathlib import Path

import numpy as np
import pandas as pd

from ideology_ontology_v3 import primitive_axis_direction

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
DIRECT = {"candidate_questionnaire", "legislative_vote", "legislative_rollcall", "candidate_public_statement"}


def main() -> None:
    evidence = pd.read_csv(IDEOLOGY / "candidate_position_evidence_v3_all_sources.csv", low_memory=False)
    evidence = evidence[evidence.canonical_candidate_id.notna() & evidence.position_value.notna()].copy()
    evidence["axis_direction"] = [primitive_axis_direction(a, p) for a, p in zip(evidence.primitive_axis, evidence.policy_pole)]
    evidence = evidence[evidence.axis_direction.notna()].copy()
    evidence["axis_contribution"] = evidence.position_value * evidence.axis_direction
    rows = []
    keys = ["canonical_candidate_id", "person_id", "candidate_name", "election_cycle", "primitive_axis"]
    for key, group in evidence.groupby(keys, dropna=False):
        direct = group[group.source_type.isin(DIRECT)]
        chosen = direct if not direct.empty else group
        chosen = chosen.copy()
        chosen["resolution_weight"] = chosen.evidence_weight
        # Recorded behavior and explicit statements control over group signals;
        # disagreement among direct evidence is a substantive mixed position.
        total = chosen.resolution_weight.sum()
        value = np.average(chosen.axis_contribution, weights=chosen.resolution_weight) if total else np.nan
        pos = chosen.loc[chosen.axis_contribution.gt(0), "resolution_weight"].sum()
        neg = chosen.loc[chosen.axis_contribution.lt(0), "resolution_weight"].sum()
        conflict = min(pos, neg) / max(pos, neg) if max(pos, neg) else 0
        if conflict >= .5:
            status = "adjudicated_substantively_mixed"
        elif value > .15:
            status = "adjudicated_alignment_with_named_pole"
        elif value < -.15:
            status = "adjudicated_opposition_to_named_pole"
        else:
            status = "adjudicated_balanced_or_unclear_direction"
        rows.append(dict(zip(keys, key)) | {
            "adjudicated_issue_valence": value, "adjudication_status": status,
            "controlling_evidence_scope": "direct_candidate_behavior_or_statement" if not direct.empty else "issue_specific_group_signals",
            "controlling_records": len(chosen), "controlling_source_types": "|".join(sorted(chosen.source_type.unique())),
            "post_adjudication_conflict_ratio": conflict,
        })
    out = pd.DataFrame(rows)
    out.to_csv(IDEOLOGY / "candidate_issue_valence_v3_adjudicated.csv", index=False)
    out[out.adjudication_status.eq("adjudicated_substantively_mixed")].to_csv(
        IDEOLOGY / "candidate_issue_valence_v3_genuinely_mixed.csv", index=False)
    print(out.adjudication_status.value_counts().to_string())
    print(f"Unresolved statuses: {out.adjudication_status.str.contains('needs|unresolved', case=False).sum()}")


if __name__ == "__main__":
    main()
