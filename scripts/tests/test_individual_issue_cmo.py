from analyze_individual_issue_cmo import MIN_N, assemble, estimate


def test_issue_models_preserve_missingness_and_minimum_coverage():
    data = assemble()
    results = estimate(data)
    assert results.n.ge(MIN_N).all()
    assert results.primitive_axis.is_unique
    assert "abortion_access" in set(results.primitive_axis)
    assert "renewable_energy_support" not in set(results.primitive_axis)


def test_issue_results_define_direction_and_multiple_testing_control():
    results = estimate(assemble())
    assert results.positive_pole.notna().all()
    assert results.negative_pole.notna().all()
    assert results.continuous_bh_q.between(0, 1).all()
