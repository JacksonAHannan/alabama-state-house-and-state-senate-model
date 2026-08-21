from __future__ import annotations

import numpy as np

from scripts.rebuild_cmo_methodology_v2 import (
    CORE_NUMERIC, PREDICTIVE_EXTRA, build, load_panel,
)


def test_headline_context_excludes_candidate_variables() -> None:
    prohibited = {"incumbent", "finance", "fundraising", "prior_overperformance", "winner", "ideology"}
    assert not any(any(token in feature for token in prohibited) for feature in CORE_NUMERIC)
    assert any("incumbent" in feature for feature in PREDICTIVE_EXTRA)
    assert any("fundraising" in feature for feature in PREDICTIVE_EXTRA)


def test_revised_outputs_cover_every_eligible_race_and_candidate() -> None:
    raw_races, raw_candidates = load_panel()
    outputs = build()
    races = outputs["races"]
    assert len(races) == len(raw_races)
    assert not races[["raw_ticket_overperformance", "context_cmo", "within_cycle_cmo",
                      "predictive_residual", "cmo_uncertainty_radius"]].isna().any().any()
    expected = [column for column in races if column.startswith("expected_margin_")]
    assert races[expected].apply(lambda column: column.between(-100, 100).all()).all()
    assert len(outputs["candidates"]) == len(raw_candidates.merge(races[["cycle", "chamber", "district"]], on=["cycle", "chamber", "district"], how="inner"))


def test_within_cycle_scores_are_median_centered() -> None:
    races = build()["races"]
    medians = races.groupby(["cycle", "chamber"]).within_cycle_cmo.median()
    assert np.allclose(medians, 0, atol=1e-10)


def test_nominal_contests_and_variable_uncertainty_are_explicit() -> None:
    races = build()["races"]
    assert set(races.contest_tier).issubset({"meaningful", "marginal", "nominal"})
    assert races.cmo_uncertainty_radius.nunique() > 20
    assert (races.context_cmo_low < races.context_cmo_high).all()


def test_nested_forward_selection_never_uses_future_cycle() -> None:
    selection = build()["nested_forward_selection"]
    for row in selection.itertuples():
        if not row.training_cycles:
            continue
        assert max(map(int, row.training_cycles.split("+"))) < row.test_cycle


def test_partial_pooling_and_construct_validity_are_published() -> None:
    outputs = build()
    effects = outputs["candidate_effects"]
    assert effects.candidate_effect_id.is_unique
    assert effects.partial_pooled_effect.notna().all()
    assert effects.attribution_reliability.between(0, 1).all()
    assert set(outputs["construct_validity"].design) >= {
        "repeat_candidate_next_cycle", "prior_cmo_next_win_bivariate_association",
        "different_candidate_same_seat_party", "incumbent_departure_successor"}
    repeat = outputs["construct_validity"].query("design == 'repeat_candidate_next_cycle'")
    assert repeat.n.min() >= 20
    successors = outputs["successor_design"]
    assert successors.identity_status.ne("surname_only_unresolved_race_specific").all()
    assert successors.prior_seat_identity_status.ne("surname_only_unresolved_race_specific").all()


def test_identity_keys_do_not_conflate_same_cycle_candidates() -> None:
    outputs = build()
    audit = outputs["identity_audit"]
    assert not audit.duplicated(["cycle", "candidate_effect_id"]).any()
    assert audit.identity_collision_split.any()
    surname_only = ~audit.canonical_name.str.strip().str.contains(r"\s", regex=True)
    assert audit.loc[surname_only, "identity_status"].eq("surname_only_unresolved_race_specific").all()
    assert not audit.loc[surname_only].duplicated("candidate_effect_id").any()
    manifest = outputs["run_manifest"]
    assert set(manifest.record_type) >= {"input", "code", "config", "count", "run"}
    assert (manifest.query("record_type == 'input'").value.str.len() == 64).all()
