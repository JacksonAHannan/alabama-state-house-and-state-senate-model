from pathlib import Path
import pandas as pd

from ideology_ontology_v3 import PRIMITIVES

ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/"data"/"processed"/"elections"/"validation"

def test_issue_tournament_uses_expanded_coverage():
    coverage=pd.read_csv(OUT/"issue_stance_tournament_coverage.csv")
    panel=pd.read_csv(OUT/"issue_stance_tournament_panel.csv",low_memory=False)
    # Coverage grows as newly adjudicated roll calls enter the frontier ledger;
    # guard against regression without freezing an obsolete exact snapshot.
    assert panel.canonical_candidate_id.nunique()>=350
    assert len(panel)>=2900
    assert coverage.set_index("primitive_axis").loc["gun_access","candidate_cycles"]>=260
    assert coverage.primary_eligible.sum()>=15

def test_verdicts_and_multiplicity_are_complete():
    verdicts=pd.read_csv(OUT/"issue_stance_tournament_verdicts.csv")
    estimates=pd.read_csv(OUT/"issue_stance_tournament_estimates.csv")
    assert set(verdicts.outcome)=={"presidential_overperformance","federal_index_overperformance"}
    assert verdicts.bh_q_value_pooled.dropna().between(0,1).all()
    assert estimates[estimates.specification.eq("pooled")].groupby("outcome").primitive_axis.nunique().eq(verdicts.primitive_axis.nunique()).all()
    federal=verdicts[verdicts.outcome.eq("federal_index_overperformance")].set_index("primitive_axis")
    assert "total_association_signal" in set(federal.evidence_grade)
    assert federal.loc["institutional_populism","evidence_grade"]!="total_association_signal"

def test_durability_output_is_explicit_about_power():
    durability=pd.read_csv(OUT/"issue_stance_tournament_durable_estimates.csv")
    estimated=durability[durability.status.eq("estimated")]
    # The set of axes with enough candidate-cycle power grows as coverage expands
    # (the full Luna bill-corpus pass brings more issues over the N threshold), so
    # guard the known axes without freezing an exact snapshot. The invariant that
    # matters is that an "estimated" durability is never claimed as significant.
    assert {"gun_access","market_governance"}<=set(estimated.primitive_axis)
    assert estimated.primitive_axis.isin(PRIMITIVES).all()
    # These durability estimates are small-sample and multiplicity is not
    # corrected in the output itself. The invariant is that no estimated durable
    # effect survives a Bonferroni guard across the estimates: the expanded Luna
    # coverage surfaces one raw p~0.03 (market_governance x federal index, n=24)
    # that does not survive correction. A genuinely robust durable effect would
    # break this and should be reviewed rather than absorbed silently.
    assert estimated.p_value.between(0, 1).all()
    assert estimated.p_value.min() * len(estimated) >= 0.05
