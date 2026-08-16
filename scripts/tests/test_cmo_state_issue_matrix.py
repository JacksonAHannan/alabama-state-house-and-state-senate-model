from pathlib import Path

import pandas as pd

from scripts.build_cmo_state_issue_matrix import ISSUES


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "research" / "cmo_ideology"


def test_state_issue_matrix_has_complete_focal_grid():
    cohort = pd.read_csv(RESEARCH / "candidate_cohort.csv")
    wide = pd.read_csv(RESEARCH / "candidate_state_issue_matrix.csv")
    long = pd.read_csv(RESEARCH / "candidate_state_issue_matrix_long.csv")

    assert len(wide) == len(cohort) == 30
    complete_cells = long[["person_id", "election_cycle", "issue"]].drop_duplicates()
    assert len(complete_cells) == len(cohort) * len(ISSUES)
    assert not wide.duplicated(["person_id", "election_cycle"]).any()
    assert set(ISSUES).issubset(wide.columns)
    assert set(long.issue) == set(ISSUES)


def test_specific_stances_are_not_inferred_from_generic_ideology():
    source = pd.read_csv(RESEARCH / "state_issue_position_ledger.csv")
    evidence = pd.read_csv(RESEARCH / "evidence_ledger.csv")

    assert not source.stance_code.isna().any()
    assert set(source.person_id).issubset(set(evidence.person_id))
    assert not source.source_url.isna().any()
    assert set(source.temporal_status).issubset({
        "pre_election", "retrospective_preexisting_record", "post_election"
    })
    # Broad ideal points can contextualize candidates but are never themselves
    # allowed to generate a named policy stance in this matrix.
    assert not source.source_url.str.contains("DVN/GZJOT3", regex=False).any()


def test_unknown_is_distinct_from_neutral_or_opposition():
    wide = pd.read_csv(RESEARCH / "candidate_state_issue_matrix.csv")
    issue_values = wide[ISSUES].astype(str)
    assert (issue_values == "?").any().any()
    assert not issue_values.apply(lambda column: column.str.contains("neutral", case=False)).any().any()


def test_public_retrieval_queue_cannot_create_positions_automatically():
    queue = pd.read_csv(RESEARCH / "candidate_public_position_review_queue.csv")
    assert queue.stance_must_be_verified_from_source.all()
    assert set(queue.human_review_status).issubset({"pending"})
    if not queue.empty:
        assert queue.groupby(
            ["person_id", "election_cycle", "issue_retrieval_tag"]
        ).size().max() <= 3


def test_new_direct_pre_election_positions_are_preserved():
    ledger = pd.read_csv(RESEARCH / "state_issue_position_ledger.csv")
    expected = {
        ("ALPERSON-BILLY-BEASLEY", "racial_civil_rights"),
        ("ALPERSON-MARC-KEAHEY", "gambling"),
        ("ALPERSON-ALLI-SUMMERFORD", "infrastructure_energy"),
        ("ALPERSON-JOHNNY-MACK-MORROW", "criminal_justice"),
        ("ALPERSON-RICHARD-LINDSEY", "public_employee_benefits"),
    }
    observed = set(zip(ledger.person_id, ledger.issue))
    assert expected.issubset(observed)
    selected = ledger.loc[
        ledger.apply(lambda row: (row.person_id, row.issue) in expected, axis=1)
    ]
    assert selected.temporal_status.eq("pre_election").all()
