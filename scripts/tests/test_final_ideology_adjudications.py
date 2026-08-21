import pandas as pd


def test_legislative_adjudications_have_no_unresolved_statuses():
    frame = pd.read_csv("data/processed/legislative/legislative_rollcall_ontology_v3_final_adjudications.csv").fillna("")
    assert len(frame) == 42391
    assert not frame.terminal_status.str.startswith("needs_").any()
    mapped = frame.decision.eq("map")
    assert frame.loc[mapped, "primitive_axis"].ne("").all()
    assert frame.loc[mapped, "policy_pole"].ne("").all()


def test_candidate_conflicts_have_terminal_adjudications():
    frame = pd.read_csv("data/processed/ideology/candidate_issue_valence_v3_adjudicated.csv")
    assert not frame.adjudication_status.str.contains("needs|unresolved", case=False).any()
