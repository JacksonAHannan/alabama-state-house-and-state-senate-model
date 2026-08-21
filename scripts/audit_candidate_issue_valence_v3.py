"""Produce reproducible coverage and conflict audit for ontology-v3 evidence."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IDEOLOGY = ROOT / "data" / "processed" / "ideology"
LEG = ROOT / "data" / "processed" / "legislative"
MANUAL = ROOT / "data" / "manual" / "ideology"
DOC = ROOT / "project_docs" / "audits" / "CANDIDATE_IDEOLOGY_V3_AUDIT.md"


def markdown_table(frame: pd.DataFrame) -> str:
    shown = frame.reset_index()
    columns = list(shown.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in shown.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def main() -> None:
    evidence = pd.read_csv(IDEOLOGY / "candidate_position_evidence_v3_all_sources.csv", low_memory=False)
    positions = pd.read_csv(IDEOLOGY / "candidate_issue_valence_v3.csv")
    final_legislative = LEG / "legislative_rollcall_ontology_v3_final_adjudications.csv"
    if final_legislative.exists():
        legislative = (pd.read_csv(final_legislative).groupby("terminal_status").size()
                       .rename("rollcalls").reset_index().rename(columns={"terminal_status": "v3_audit_status"}))
    else:
        legislative = pd.read_csv(LEG / "legislative_rollcall_ontology_v3_audit_summary.csv")
    ratings = pd.read_csv(IDEOLOGY / "votesmart_all_1998_2022_ratings.csv")
    endorsements = pd.read_csv(IDEOLOGY / "votesmart_all_1998_2022_endorsements.csv")
    mapping = pd.read_csv(MANUAL / "interest_group_ontology_v3.csv")
    mapped = set(mapping.organization)
    unmapped_ratings = (ratings[~ratings.organization.isin(mapped)].groupby("organization").size()
                        .sort_values(ascending=False).rename("records").reset_index())
    unmapped_endorsements = (endorsements[~endorsements.organization.isin(mapped)].groupby("organization").size()
                             .sort_values(ascending=False).rename("records").reset_index())
    unmapped_ratings.to_csv(IDEOLOGY / "interest_group_rating_ontology_v3_review_queue.csv", index=False)
    unmapped_endorsements.to_csv(IDEOLOGY / "interest_group_endorsement_ontology_v3_review_queue.csv", index=False)
    conflict = positions.sort_values(["conflict_ratio", "absolute_evidence_weight"], ascending=False)
    conflict[conflict.conflict_ratio.ge(.5)].to_csv(IDEOLOGY / "candidate_issue_valence_v3_conflict_review.csv", index=False)

    source = evidence.groupby("source_type").agg(records=("evidence_id", "nunique"), candidates=("canonical_candidate_id", "nunique"))
    coverage = positions.groupby("election_cycle").agg(candidates=("canonical_candidate_id", "nunique"), profiles=("primitive_axis", "size"), issues=("primitive_axis", "nunique"))
    lines = ["# Candidate ideology ontology-v3 audit", "",
             "This audit covers issue-specific candidate valence assembled without party-label imputation. Missing evidence remains missing.", "",
             "## Current evidence", "", markdown_table(source), "", "## Candidate-cycle coverage", "", markdown_table(coverage), "",
             "## Legislative audit", "", markdown_table(legislative.set_index("v3_audit_status")), "",
             f"There are **{len(positions):,}** candidate–issue profiles. **{positions.conflict_ratio.ge(.5).sum():,}** have substantial opposing evidence and are exported for review.", "",
             "The legislative audit is corpus-wide but adjudication remains incomplete. Generic budgets, procedural motions, amendments without reviewed amendment text, and ambiguous omnibus measures are not assigned a policy pole.", "",
             "## Known source gaps", "",
             "- No structured biography corpus is downloaded locally.",
             "- No structured Vote Smart public-statement corpus is downloaded locally.",
             "- Broad ideological ratings and coalition endorsements are not converted into specific issue positions unless the organization has an explicit issue mapping.",
             "- 1994 remains dependent on archival surveys, endorsement slates, newspapers, and historical journals; current Vote Smart evidence begins later.", "",
             f"Unmapped review queues contain **{len(unmapped_ratings):,} rating organizations** and **{len(unmapped_endorsements):,} endorsement organizations**. Many should remain unmapped because their signals are broad or constituency-based rather than issue-specific."]
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
