from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"data"/"processed"/"elections"/"validation"

def test_hypothesis_ledger_and_panel_are_complete():
    hypotheses=pd.read_csv(OUT/"issue_stance_durable_hypotheses.csv")
    panel=pd.read_csv(OUT/"issue_stance_durable_panel.csv",low_memory=False)
    assert hypotheses.hypothesis_id.is_unique
    assert set(hypotheses.hypothesis_id)=={f"VAL-{i:02d}" for i in range(1,12)}
    assert hypotheses.current_result.notna().all()
    assert len(panel)==509
    assert panel.canonical_candidate_id.is_unique
    assert set(panel.canonical_party)=={"D"}

def test_primary_results_preserve_sparse_coverage():
    coverage=pd.read_csv(OUT/"issue_stance_durable_coverage.csv")
    estimates=pd.read_csv(OUT/"issue_stance_durable_estimates.csv")
    panel=pd.read_csv(OUT/"issue_stance_durable_panel.csv",low_memory=False)
    observed=panel.ideology_v3_social_liberty_equality.notna().sum()
    assert coverage.set_index("family").loc["social_liberty_equality","candidate_cycles"]==observed
    assert observed >= 79  # frontier review must not regress the prior evidence floor
    primary=estimates[(estimates.specification=="bivariate") & estimates.outcome.isin(["presidential_overperformance","federal_index_overperformance"])]
    assert len(primary)==14
    assert primary.loc[primary.family.eq("institutional_reform"),"status"].eq("underpowered").all()
    assert primary.primary_bh_q_value.dropna().between(0,1).all()
