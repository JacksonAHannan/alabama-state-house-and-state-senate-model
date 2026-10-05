import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/forecast_calibration"
PREFIX = "alabama_war_forecast_v1"


def test_forecast_combines_generic_ballot_war_structure_and_candidate_history():
    scenarios = pd.read_csv(OUT / f"{PREFIX}_2026_scenarios.csv")
    assert set(scenarios.scenario) == {
        "headline", "environment_dem_favorable", "environment_rep_favorable",
        "fundamentals_only_no_candidate_history",
    }
    assert scenarios.groupby("scenario").size().eq(48).all()
    assert scenarios.finance_used.eq(False).all()
    np.testing.assert_allclose(
        scenarios.predicted_dem_margin,
        scenarios.environment_baseline_margin + scenarios.generic_structural_adjustment
        + scenarios.candidate_war_adjustment,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        scenarios.generic_structural_adjustment,
        scenarios.war_structural_expected_gap,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        scenarios.war_structural_expected_gap,
        scenarios.generic_downballot_lag + scenarios.incumbency_adjustment,
        atol=1e-10,
    )
    assert scenarios.generic_structural_adjustment.abs().gt(1e-8).any()
    assert scenarios.incumbency_adjustment.abs().gt(1e-8).any()
    assert scenarios.status.eq("uniform_generic_ballot_environment_selected").all()
    legacy_columns = {
        "geographic_elasticity", "demographic_swing_2024_2026",
        "demographic_poll_adjusted_margin", "low_elasticity_075_margin",
        "high_elasticity_125_margin", "votehub_2026_dem_margin",
        "fundraising_adjustment",
    }
    assert not legacy_columns & set(scenarios.columns)


def test_candidate_history_applies_only_where_a_prior_race_is_matched():
    scenarios = pd.read_csv(OUT / f"{PREFIX}_2026_scenarios.csv")
    headline = scenarios[scenarios.scenario.eq("headline")]
    comparison = scenarios[scenarios.scenario.eq("fundamentals_only_no_candidate_history")]
    assert headline.candidate_war_adjustment.abs().gt(0).any()
    assert headline.candidate_history_used.eq(headline.candidate_war_adjustment.ne(0)).all()
    assert headline.generic_candidate_assumption.eq(~headline.candidate_history_used).all()
    # The comparison scenario is the same forecast with the carry switched off.
    assert comparison.candidate_war_adjustment.eq(0).all()
    assert comparison.candidate_history_used.eq(False).all()
    merged = headline.merge(comparison, on=["chamber", "district"], suffixes=("", "_plain"))
    np.testing.assert_allclose(
        merged.predicted_dem_margin - merged.predicted_dem_margin_plain,
        merged.candidate_war_adjustment, atol=1e-10,
    )


def test_owner_selected_specification_publishes_its_holdout_comparison():
    metrics = pd.read_csv(OUT / f"{PREFIX}_forward_metrics.csv").set_index("specification")
    selected = metrics.loc["war_structural_plus_candidate_history"]
    # Owner-selected despite trailing the benchmark; the comparison must stay visible.
    assert selected.mae > metrics.loc["generic_ballot_baseline", "mae"]
    assert selected.mae < metrics.loc["generic_war_structural", "mae"]
    assert int(selected.races_with_candidate_history) > 0
    manifest = json.loads((OUT / f"{PREFIX}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["selected_specification"] == "war_structural_plus_candidate_history"
    assert manifest["configuration"]["structural_applied"] is True
    assert manifest["diagnostics"]["structural_improves_baseline_on_holdout"] is False
    assert manifest["diagnostics"]["candidate_history_improves_structural_on_holdout"] is True
    assert manifest["configuration"]["incumbency_treatment"] == (
        "included_as_symmetric_race_condition_in_war_structure"
    )
    assert manifest["configuration"]["war_structural_specification"] == "decaying_lag"
    assert manifest["configuration"]["war_training_cutoff_rule"].startswith("cycle > 2016")
    assert "incumbency_balance" in manifest["configuration"]["design_features"]
    assert manifest["configuration"]["candidate_history_used"] is True
    assert 0.0 < manifest["configuration"]["candidate_history_persistence"] < 1.0
    assert manifest["configuration"]["finance_used"] is False
    # Candidate history is a post-model adjustment, never a structural design column.
    forbidden = ("candidate", "war", "cmo", "history", "ideology", "fundrais", "receipt", "expenditure")
    assert all(not any(term in feature.lower() for term in forbidden)
               for feature in manifest["configuration"]["design_features"])


def test_forecast_manifest_hashes_outputs():
    manifest = json.loads((OUT / f"{PREFIX}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["diagnostics"]["max_forecast_identity_error"] < 1e-10
    for record in manifest["outputs"]:
        path = ROOT / record["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]


def test_environment_seat_joint_reproduces_the_modeled_seat_distribution():
    joint = pd.read_csv(OUT / f"{PREFIX}_2026_environment_seat_joint.csv")
    seats = pd.read_csv(OUT / f"{PREFIX}_2026_modeled_seats.csv")
    assert (joint.environment_shift_high - joint.environment_shift_low).eq(1.0).all()
    assert not joint.duplicated(["chamber", "environment_shift_low", "dem_modeled_seats"]).any()
    for chamber, part in joint.groupby("chamber"):
        assert part.draw_count.sum() == part.draws.iloc[0]
        marginal = part.groupby("dem_modeled_seats").draw_count.sum() / part.draws.iloc[0]
        expected = seats[seats.chamber.eq(chamber)].set_index("dem_modeled_seats").probability
        pd.testing.assert_series_equal(marginal, expected, check_names=False, rtol=0, atol=1e-12)


def test_run_ledger_keeps_one_row_per_distinct_result():
    import run_alabama_war_generic_forecast as forecast

    ledger = pd.read_csv(OUT / f"{PREFIX}_run_ledger.csv")
    manifest = json.loads((OUT / f"{PREFIX}_manifest.json").read_text(encoding="utf-8"))
    current = ledger[ledger.build_id.eq(manifest["build_id"])]
    assert set(current.chamber) == {"house", "senate"}
    identity = [c for c in ledger.columns if c not in {"generated_at_utc", "git_commit"}]
    assert not ledger.duplicated(identity).any()
    assert current.dem_seats_p10.le(current.dem_seats_median).all() and current.dem_seats_median.le(current.dem_seats_p90).all()
    # The page's quantile rule: the smallest total whose cumulative share reaches q.
    total = np.array([3, 4, 4, 5, 9])
    summary = forecast.seat_summary(total - 1, "senate", {"senate": {"D": 1, "R": 0}})
    assert (summary["dem_seats_p10"], summary["dem_seats_median"], summary["dem_seats_p90"]) == (3, 4, 9)
