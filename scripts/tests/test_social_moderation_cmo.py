import numpy as np

from analyze_social_moderation_cmo import assemble, downstream_survival, fit_models


def test_social_moderation_sample_is_democratic_and_uses_selection_aware_cmo():
    data = assemble()
    assert set(data.canonical_party) == {"D"}
    assert data.social_progressivism.notna().all()
    assert np.allclose(data.cmo, data.candidate_cmo_total_oof)
    assert "incumbent" in data


def test_primary_models_do_not_control_for_incumbency_or_prior_candidate_strength():
    data = assemble()
    _, models = fit_models(data)
    primary = models[~models.model.str.contains("forecast")]
    assert not primary.formula.str.contains("incumbent", case=False).any()
    assert not primary.formula.str.contains("prior_candidate", case=False).any()


def test_missing_social_positions_are_not_imputed_to_center():
    data = assemble()
    assert len(data) == data.ideology_v3_social_liberty_equality.notna().sum()


def test_survival_is_marked_as_downstream_and_excludes_last_cycle_followup():
    data = assemble()
    rows, _ = downstream_survival(data)
    assert (rows.loc[rows.eligible_followup, "year"] + 4 <=
            rows.loc[rows.eligible_followup, "followup_through_cycle"]).all()
