from __future__ import annotations

import numpy as np
import pandas as pd


PANEL = "research/cmo_ideology/absolute_rebuild_panel.csv"


def test_candidate_directional_ticket_outcomes_are_zero_sum() -> None:
    panel = pd.read_csv(PANEL)
    for outcome in ["candidate_statewide_overperformance", "candidate_federal_overperformance",
                    "candidate_presidential_overperformance"]:
        paired = panel.pivot_table(index=["cycle", "chamber", "district"], columns="party",
                                   values=outcome, aggfunc="first").dropna()
        assert (paired.D + paired.R).abs().max() < 1e-8


def test_cmo_is_the_frozen_ideology_blind_input() -> None:
    panel = pd.read_csv(PANEL)
    cmo = pd.read_csv("data/processed/war/cmo_v3_candidates.csv")
    expected = panel[["canonical_candidate_id", "candidate_cmo"]].merge(
        cmo[["canonical_candidate_id", "candidate_headline_cmo"]],
        on="canonical_candidate_id", how="left", validate="one_to_one")
    assert np.allclose(expected.candidate_cmo, expected.candidate_headline_cmo, equal_nan=True)
    assert panel.cmo_source.eq("cmo_v3_direct_ticket").all()


def test_barbara_boyd_uses_direct_ticket_cmo() -> None:
    panel = pd.read_csv(PANEL)
    boyd = panel[(panel.cycle.eq(2022)) & (panel.chamber.eq("house"))
                 & (panel.district.eq(32)) & panel.party.eq("D")]
    assert len(boyd) == 1
    assert 9.0 < boyd.iloc[0].candidate_cmo < 11.0


def test_absolute_and_issue_analyses_include_both_parties() -> None:
    panel = pd.read_csv(PANEL)
    assert set(panel.loc[panel.absolute_conservatism_z.notna(), "party"]) == {"D", "R"}
    assert set(panel.loc[panel.primitive_conservative_gun_access.notna(), "party"]) == {"D", "R"}


def test_guns_and_racial_civil_rights_remain_separate_axes() -> None:
    panel = pd.read_csv(PANEL)
    guns = panel.dropna(subset=["primitive_raw_gun_access"]).iloc[0]
    race = panel.dropna(subset=["primitive_raw_racial_civil_rights"]).iloc[0]
    assert guns.primitive_conservative_gun_access == guns.primitive_raw_gun_access
    assert race.primitive_conservative_racial_civil_rights == -race.primitive_raw_racial_civil_rights


def test_party_convergence_has_opposite_orientation() -> None:
    panel = pd.read_csv(PANEL).dropna(subset=["absolute_conservatism_z"])
    democrat = panel[panel.party.eq("D")].iloc[0]
    republican = panel[panel.party.eq("R")].iloc[0]
    assert democrat.party_directed_convergence == democrat.absolute_conservatism_z
    assert republican.party_directed_convergence == -republican.absolute_conservatism_z


def test_total_and_mediator_estimands_are_distinct() -> None:
    estimates = pd.read_csv("research/cmo_ideology/absolute_rebuild_estimates.csv")
    assert {"party_total_context", "party_mediator_adjusted"}.issubset(set(estimates.specification))
    total = estimates[estimates.specification.eq("party_total_context")]
    direct = estimates[estimates.specification.eq("party_mediator_adjusted")]
    assert total.n.max() > direct.n.max()


def test_symmetric_and_party_specific_incumbency_are_reported() -> None:
    estimates = pd.read_csv("research/cmo_ideology/absolute_rebuild_estimates.csv")
    common = estimates[(estimates.specification.eq("common_incumbency")) & estimates.term.eq("incumbent_i")]
    asymmetric = estimates[(estimates.specification.eq("party_specific_incumbency"))
                           & estimates.term.eq("democratic_x_incumbency")]
    assert len(common) == 4
    assert len(asymmetric) == 4


def test_primary_issue_tests_have_multiplicity_adjustment() -> None:
    estimates = pd.read_csv("research/cmo_ideology/absolute_rebuild_issue_estimates.csv")
    primary = estimates[
        estimates.specification.str.startswith("issue_total:primitive:")
        & estimates.outcome.isin(["candidate_federal_overperformance",
                                  "candidate_presidential_overperformance"])
        & estimates.status.eq("estimated")
    ]
    assert primary.primary_bh_q_value.notna().all()


def test_congruence_is_position_times_district_republicanism() -> None:
    panel = pd.read_csv(PANEL).dropna(subset=["primitive_conservative_gun_access",
                                             "district_republicanism_z"])
    expected = panel.primitive_conservative_gun_access * panel.district_republicanism_z
    assert np.allclose(panel.primitive_congruence_gun_access, expected)
