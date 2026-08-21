"""Completion gates for the direct roll-call frontier ideology pipeline."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ideology_ontology_v3 import validate_primitive

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "data" / "processed" / "legislative"
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
MANUAL = ROOT / "data" / "manual" / "ideology" / "frontier_legislative_bill_adjudications.csv"
OUT = ROOT / "project_docs" / "audits" / "FRONTIER_IDEOLOGY_VALIDATION.csv"


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"check": name, "passed": bool(passed), "detail": detail}


def main() -> None:
    calls = pd.read_csv(LEG / "comprehensive_rollcall_classifications.csv", low_memory=False)
    frontier = pd.read_csv(LEG / "frontier_rollcall_ontology_v3.csv", low_memory=False).fillna("")
    manual = pd.read_csv(MANUAL, low_memory=False).fillna("")
    evidence = pd.read_csv(IDEOLOGY / "candidate_legislative_position_evidence_v3.csv", low_memory=False).fillna("")
    candidate = pd.read_csv(IDEOLOGY / "candidate_issue_valence_v3.csv", low_memory=False)
    bills = pd.read_csv(LEG / "legiscan_alabama_bills.csv", low_memory=False)
    archive = pd.read_csv(LEG / "frontier_archive_bill_ledger.csv", low_memory=False)

    input_ids = set(calls.canonical_rollcall_id.astype(str))
    output_ids = set(frontier.canonical_rollcall_id.astype(str))
    linked_bills = set(calls.loc[calls.bill_id.notna(), "bill_id"].astype(int))
    reviewed_bills = set(pd.to_numeric(manual.bill_id, errors="coerce").dropna().astype(int))
    mapped = frontier[frontier.decision.eq("map")]
    valid = True
    for row in mapped.itertuples(index=False):
        try:
            validate_primitive(row.primitive_axis, row.policy_pole)
        except ValueError:
            valid = False
            break
    contradictions = (mapped.groupby(["canonical_rollcall_id", "primitive_axis"])
                      .policy_pole.nunique().gt(1).sum())
    results = [
        check("every_archive_bill_has_one_terminal_disposition",
              archive.bill_id.is_unique and set(archive.bill_id) == set(bills.bill_id)
              and archive.terminal_disposition.fillna(False).all(),
              f"archive={len(bills)} ledger={len(archive)} unique={archive.bill_id.nunique()}"),
        check("non_rollcall_bills_explicitly_non_scoring",
              archive.loc[~archive.recorded_individual_rollcall,
                          "archive_disposition"].eq("no_recorded_individual_rollcall").all()
              and not archive.loc[~archive.recorded_individual_rollcall,
                                  "candidate_vote_scoring_eligible"].any(),
              f"non_rollcall={int((~archive.recorded_individual_rollcall).sum())}"),
        check("archive_scoring_requires_frontier_reviewed_rollcall",
              archive.loc[archive.candidate_vote_scoring_eligible,
                          "recorded_individual_rollcall"].all()
              and archive.loc[archive.candidate_vote_scoring_eligible,
                              "archive_disposition"].isin(["map", "multi_axis"]).all(),
              f"eligible_bills={int(archive.candidate_vote_scoring_eligible.sum())}"),
        check("all_rollcalls_have_terminal_output", input_ids == output_ids,
              f"input={len(input_ids)} output={len(output_ids)}"),
        check("all_linked_rollcall_bills_frontier_reviewed", linked_bills <= reviewed_bills,
              f"linked={len(linked_bills)} missing={len(linked_bills-reviewed_bills)}"),
        check("every_output_has_terminal_decision", frontier.decision.isin(["map", "exclude"]).all(),
              frontier.decision.value_counts().to_dict().__str__()),
        check("all_mapped_poles_validate", valid, f"mapped_rows={len(mapped)}"),
        check("no_contradictory_mapped_poles", contradictions == 0,
              f"contradictory_rollcall_axes={contradictions}"),
        check("legislative_evidence_uses_frontier_authority",
              evidence.adjudication_authority.str.startswith("frontier_manual_review:").all(),
              f"evidence_rows={len(evidence)}"),
        check("legislative_evidence_ids_unique", evidence.evidence_id.is_unique,
              f"duplicates={evidence.evidence_id.duplicated().sum()}"),
        check("candidate_issue_profiles_unique",
              not candidate.duplicated(["canonical_candidate_id", "election_cycle", "primitive_axis"]).any(),
              f"profiles={len(candidate)}"),
        check("explicit_insufficient_text_retained",
              manual.decision.eq("insufficient_text").sum() == 2,
              f"bill_unknowns={manual.decision.eq('insufficient_text').sum()}"),
    ]
    result = pd.DataFrame(results)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(result.to_string(index=False))
    if not result.passed.all():
        raise SystemExit("frontier ideology validation failed")


if __name__ == "__main__":
    main()
