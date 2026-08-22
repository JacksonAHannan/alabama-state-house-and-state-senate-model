import pandas as pd

from analyze_democratic_ideological_clusters import OUT, PANEL, choose_k, issue_columns


def test_cluster_inputs_are_issue_positions_only():
    panel = pd.read_csv(PANEL, low_memory=False)
    forbidden = {"candidate_cmo", "winner", "incumbent_i", "candidate_finance_advantage"}
    for party in ("D", "R"):
        features = issue_columns(panel, party)
        assert len(features) >= 3
        assert all(column.startswith("primitive_conservative_") for column in features)
        assert forbidden.isdisjoint(features)


def test_selected_solutions_follow_rule_and_warn_on_republican_instability():
    diagnostics = pd.read_csv(OUT / "cluster_model_diagnostics.csv")
    sensitivity = pd.read_csv(OUT / "cluster_sensitivity.csv")
    for _, party in diagnostics.groupby("party"):
        assert int(party.loc[party.selected, "clusters"].iloc[0]) == choose_k(party)
    republican = sensitivity[sensitivity.party.eq("R")].iloc[0]
    assert republican.knn_vs_median_ari < .5
    report = (OUT / "DEMOCRATIC_IDEOLOGICAL_CLUSTERS.md").read_text(encoding="utf-8")
    assert "Robustness warning" in report
    assert "position-versus-missingness ARI" in report
