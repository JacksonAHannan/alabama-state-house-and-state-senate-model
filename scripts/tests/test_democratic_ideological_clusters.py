import pandas as pd

from analyze_democratic_ideological_clusters import assemble, fit_clusters


def test_cluster_input_uses_only_democrats_and_issue_evidence():
    frame, features = assemble()
    assert set(frame.canonical_party) == {"D"}
    assert any(column.startswith("issue__") for column in features)
    assert "raw_overperformance" not in features
    assert "core_index_margin" not in features


def test_cluster_solution_has_no_tiny_selected_cluster():
    frame, features = assemble()
    clustered, diagnostics, *_ = fit_clusters(frame, features)
    shares = clustered.cluster_id.value_counts(normalize=True)
    assert len(clustered) >= 150
    assert shares.min() >= .08
    assert diagnostics.clusters.tolist() == [2, 3, 4, 5, 6]
    assert clustered[["ideology_map_x", "ideology_map_y"]].notna().all().all()
    assert clustered.attrs["projection_loadings"].feature.is_unique
    assert len(clustered.attrs["projection_variance"]) == 2
