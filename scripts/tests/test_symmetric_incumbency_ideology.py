from __future__ import annotations

import pandas as pd

from scripts.analyze_symmetric_incumbency_ideology import fit


def test_candidate_directional_outcomes_are_zero_sum() -> None:
    panel = pd.read_csv("research/cmo_ideology/symmetric_incumbency_panel.csv")
    paired = panel.pivot_table(index=["cycle", "chamber", "district"], columns="party", values="candidate_statewide_overperformance", aggfunc="first").dropna()
    assert (paired.D + paired.R).abs().max() < 1e-8


def test_both_parties_have_analysis_ready_matches() -> None:
    panel = pd.read_csv("research/cmo_ideology/symmetric_incumbency_panel.csv")
    assert panel.groupby("party").size().min() >= 50
    assert panel.groupby("party").incumbent_i.sum().min() >= 10


def test_cross_party_moderation_points_toward_center() -> None:
    panel = pd.read_csv("research/cmo_ideology/symmetric_incumbency_panel.csv")
    democrat = panel[panel.party.eq("D")].sort_values("absolute_np_z").iloc[-1]
    republican = panel[panel.party.eq("R")].sort_values("absolute_np_z").iloc[0]
    assert democrat.cross_party_moderation == democrat.absolute_np_z
    assert republican.cross_party_moderation == -republican.absolute_np_z


def test_absolute_moderation_contrasts_are_published() -> None:
    contrasts = pd.read_csv("research/cmo_ideology/symmetric_incumbency_ideology_contrasts.csv")
    focal = contrasts[contrasts.specification.eq("party_specific_cross_party_moderation")]
    assert set(focal.contrast) >= {
        "Republican movement toward center", "Democratic movement toward center",
        "Democratic-minus-Republican moderation slope",
    }


def test_party_hostility_interactions_are_published() -> None:
    terms = pd.read_csv("research/cmo_ideology/symmetric_incumbency_model_terms.csv")
    focal = terms[
        terms.specification.eq("party_moderation_x_baseline_hostility")
        & terms.term.eq("moderation_x_hostility")
    ]
    assert set(focal["sample"]) == {"D", "R"}
    assert set(focal["outcome"]) == {
        "candidate_cmo",
        "candidate_statewide_overperformance",
        "candidate_federal_overperformance",
        "candidate_presidential_overperformance",
    }


def test_fit_recovers_incumbency_effect() -> None:
    frame = pd.DataFrame({
        "shor_u_id": [f"p{i}" for i in range(30)], "cycle": [1998] * 15 + [2002] * 15,
        "chamber": ["house"] * 30, "incumbent_i": [0, 1] * 15,
    })
    frame["outcome"] = 5 * frame.incumbent_i + (frame.cycle == 2002).astype(int)
    result = fit(frame, "outcome", ["incumbent_i", "cycle", "chamber"], "fixture")
    term = result[1].set_index("term")
    assert abs(term.loc["incumbent_i", "coefficient"] - 5) < 1e-8

