"""Synthetic-fixture tests for the Southern v3 missing-context sensitivity audit."""
import json

import numpy as np
import pandas as pd
import pytest

import audit_southern_v3_context_sensitivity as audit
import retrain_post2016_southern_war_v2 as v2
import retrain_post2016_southern_war_v3 as v3


SPEC = "decaying_lag"
ALPHA = 10.0
RUN_ID = "WAR-POST2016-V3-TESTRUN00000000000"
WAREHOUSE_RUN = "RUN-TEST-WAREHOUSE"
LAG_STATES = {"AL": True, "GA": True, "FL": False, "KY": False}
CYCLES = (2018, 2020)


def make_races(missing: bool = True, lag_cycles=CYCLES, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for cycle in CYCLES:
        for state, has_lag in LAG_STATES.items():
            for chamber in ("lower", "upper"):
                for district in range(1, 5):
                    baseline = rng.normal(-8.0, 18.0)
                    lag_available = (has_lag or not missing) and cycle in lag_cycles
                    prior = baseline + rng.normal(0.0, 6.0) if lag_available else np.nan
                    incumbency = int(rng.choice([-1, 0, 1]))
                    change = 0.0 if not lag_available else baseline - prior
                    direct = (
                        2.5 * incumbency + 0.04 * baseline - 0.15 * change
                        + {"AL": 1.0, "GA": -1.0, "FL": 0.5, "KY": -0.5}[state]
                        + rng.normal(0.0, 3.0)
                    )
                    rows.append({
                        "build_run_id": WAREHOUSE_RUN,
                        "state_code": state,
                        "cycle": cycle,
                        "chamber": chamber,
                        "district": str(district),
                        "incumbency_balance": incumbency,
                        "baseline_dem_margin": baseline,
                        "baseline_office_family": "president" if cycle == 2020 else "governor",
                        "prior_pres_margin": prior,
                        "direct_overperformance": direct,
                    })
    frame = pd.DataFrame(rows)
    frame.insert(0, "war_outcome_id", [f"WAROUT-TEST-{index:04d}" for index in range(len(frame))])
    frame["lag_context_available"] = frame.prior_pres_margin.notna()
    frame["lag_current_ticket_change"] = frame.baseline_dem_margin - frame.prior_pres_margin
    frame["years_since_2016"] = frame.cycle - 2016
    frame["lag_change_x_years"] = frame.lag_current_ticket_change * frame.years_since_2016
    frame["lag_context_status"] = np.where(
        frame.lag_context_available, "validated_prior", "missing_validated_prior_presidential_context"
    )
    return frame


def publish(races: pd.DataFrame, specification: str = SPEC, alpha: float = ALPHA) -> pd.DataFrame:
    """Produce published columns with the actual v3 code path."""
    designs, lag_columns = v2.design_matrices(races)
    design = designs[specification]
    lag = [column for column in lag_columns if column in design.columns]
    fitted, _ = v3.fitted_cycle_predictions(races, design, specification, alpha, lag)
    validation = v3.cross_fitted_validation(races, design, specification, alpha, lag)
    published = v3.headline_races(races, fitted, validation)
    published.insert(0, "model_run_id", RUN_ID)
    return published


def make_manifest(specification: str = SPEC, alpha: float = ALPHA) -> dict:
    return {
        "model_run_id": RUN_ID,
        "warehouse_build_run_id": WAREHOUSE_RUN,
        "configuration": {
            "selected_structural_specification": specification,
            "selected_structural_alpha": alpha,
        },
    }


@pytest.fixture
def bundle():
    races = make_races()
    published = publish(races)
    frame = audit.audit_frame(published, races)
    return frame, make_manifest(), races, published


def selected(frame, manifest):
    return audit.reproduce_headline(frame, manifest)


# --------------------------------------------------------------------------- parity gate


def test_parity_gate_passes_on_self_generated_published_values(bundle):
    frame, manifest, _, _ = bundle
    result = selected(frame, manifest)
    assert result["status"] == "passed"
    assert result["specification"] == SPEC and result["alpha"] == ALPHA
    assert result["lag_columns"] == ["prior_pres_margin", "lag_current_ticket_change", "lag_change_x_years"]
    assert set(result["max_abs_difference"]) == set(audit.PARITY_COLUMNS)
    assert all(value < audit.PARITY_TOLERANCE for value in result["max_abs_difference"].values())
    assert set(result["designs"]) == {"fundamentals_no_lag", "constant_lag", "decaying_lag"}


@pytest.mark.parametrize("column", audit.PARITY_COLUMNS)
def test_parity_gate_raises_when_a_published_value_is_perturbed(bundle, column):
    frame, manifest, _, _ = bundle
    perturbed = frame.copy()
    perturbed.loc[3, column] += 1e-6
    with pytest.raises(ValueError, match="Parity gate failed"):
        selected(perturbed, manifest)


def test_parity_gate_raises_when_manifest_configuration_differs(bundle):
    frame, _, _, _ = bundle
    with pytest.raises(ValueError, match="Parity gate failed"):
        selected(frame, make_manifest(alpha=1.0))
    with pytest.raises(ValueError, match="Parity gate failed"):
        selected(frame, make_manifest(specification="fundamentals_no_lag"))


# --------------------------------------------------------------------------- loading


def _stub_warehouse(monkeypatch, raw: pd.DataFrame):
    monkeypatch.setattr(v2, "load_training", lambda: (raw.copy(), {"status": "validated"}))
    monkeypatch.setattr(v2, "attach_lag_context", lambda frame: frame)
    monkeypatch.setattr(v2, "add_finance_features", lambda frame: frame.copy())


def _write_run(tmp_path, manifest, published):
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    published.to_csv(tmp_path / "race_war.csv", index=False)
    return tmp_path


def test_load_run_aligns_published_rows_to_the_warehouse_order(bundle, monkeypatch, tmp_path):
    _, manifest, races, published = bundle
    run_dir = _write_run(tmp_path, manifest, published.iloc[::-1])
    _stub_warehouse(monkeypatch, races)
    loaded_manifest, loaded_published, loaded_training = audit.load_run(run_dir)
    assert loaded_manifest["model_run_id"] == RUN_ID
    assert loaded_published.war_outcome_id.tolist() == loaded_training.war_outcome_id.tolist()
    assert loaded_published.war_outcome_id.tolist() == races.war_outcome_id.tolist()


def test_load_run_rejects_warehouse_run_mismatch(bundle, monkeypatch, tmp_path):
    _, manifest, races, published = bundle
    run_dir = _write_run(tmp_path, manifest, published)
    _stub_warehouse(monkeypatch, races.assign(build_run_id="RUN-SOMETHING-ELSE"))
    with pytest.raises(ValueError, match="Warehouse build run"):
        audit.load_run(run_dir)


def test_load_run_rejects_row_set_mismatch(bundle, monkeypatch, tmp_path):
    _, manifest, races, published = bundle
    run_dir = _write_run(tmp_path, manifest, published)
    _stub_warehouse(monkeypatch, races.iloc[1:])
    with pytest.raises(ValueError, match="Race universe differs"):
        audit.load_run(run_dir)


def test_load_run_rejects_changed_published_inputs(bundle, monkeypatch, tmp_path):
    _, manifest, races, published = bundle
    altered = published.copy()
    altered.loc[5, "baseline_dem_margin"] += 0.5
    run_dir = _write_run(tmp_path, manifest, altered)
    _stub_warehouse(monkeypatch, races)
    with pytest.raises(ValueError, match="baseline_dem_margin"):
        audit.load_run(run_dir)


# --------------------------------------------------------------------------- sensitivity


def test_context_alternatives_follow_the_documented_nan_pattern(bundle):
    frame, manifest, _, _ = bundle
    result = selected(frame, manifest)
    by_race, summary = audit.context_sensitivity(
        frame, result["designs"], SPEC, ALPHA, result["lag_columns"]
    )
    assert len(by_race) == len(frame)
    assert by_race.war_outcome_id.tolist() == frame.war_outcome_id.tolist()
    available = by_race.lag_context_available.to_numpy(bool)
    assert available.any() and (~available).any()
    assert by_race.war_no_lag_spec.notna().all()
    assert by_race.war_lag_available_fit.notna().to_numpy().tolist() == available.tolist()
    assert by_race.war_missing_excluded_fit.notna().all()
    np.testing.assert_allclose(
        by_race.loc[available, "war_missing_excluded_fit"],
        by_race.loc[available, "war_lag_available_fit"],
        atol=1e-10,
    )
    np.testing.assert_allclose(by_race.war, frame.war, atol=1e-12)
    np.testing.assert_allclose(
        by_race.headline_zero_fill_lag_component, frame.fitted_lag_component, atol=1e-12
    )
    assert by_race.loc[~available, "headline_zero_fill_lag_component"].abs().max() == 0.0
    assert (by_race.war_no_lag_spec - by_race.war).abs().max() > 1e-6
    for name in audit.ALTERNATIVES:
        np.testing.assert_allclose(
            by_race[f"diff_{name}"], by_race[f"war_{name}"] - by_race.war, atol=1e-12
        )
    assert summary.loc[
        summary.cycle.eq("all") & summary.lag_context_available.eq("missing"),
        "lag_available_fit_n",
    ].item() == 0


def test_cycle_without_lag_context_leaves_lag_alternatives_missing():
    races = make_races(lag_cycles=(2018,))
    frame = audit.audit_frame(publish(races), races)
    result = selected(frame, make_manifest())
    by_race, summary = audit.context_sensitivity(
        frame, result["designs"], SPEC, ALPHA, result["lag_columns"]
    )
    in_2020 = by_race.cycle.eq(2020)
    assert by_race.loc[in_2020, "war_lag_available_fit"].isna().all()
    assert by_race.loc[in_2020, "war_missing_excluded_fit"].isna().all()
    assert by_race.loc[in_2020, "war_no_lag_spec"].notna().all()
    assert (by_race.loc[in_2020, "lag_available_fit_rows"] == 0).all()
    row = summary[summary.cycle.eq("2020") & summary.lag_context_available.eq("all")].iloc[0]
    assert row.missing_context_share == 1.0
    assert row.missing_excluded_fit_n == 0 and np.isnan(row.missing_excluded_fit_mae)
    assert row.no_lag_spec_n == in_2020.sum()


def test_context_alternatives_are_identical_when_no_rows_are_missing():
    races = make_races(missing=False)
    assert races.lag_context_available.all()
    frame = audit.audit_frame(publish(races), races)
    result = selected(frame, make_manifest())
    by_race, summary = audit.context_sensitivity(
        frame, result["designs"], SPEC, ALPHA, result["lag_columns"]
    )
    np.testing.assert_allclose(by_race.war_lag_available_fit, by_race.war, atol=1e-8)
    np.testing.assert_allclose(by_race.war_missing_excluded_fit, by_race.war, atol=1e-8)
    overall = summary[summary.cycle.eq("all") & summary.lag_context_available.eq("all")].iloc[0]
    assert overall.missing_context_share == 0.0
    assert overall.lag_available_fit_mae < 1e-8 and overall.missing_excluded_fit_mae < 1e-8
    assert overall.lag_available_fit_sign_change_share == 0.0
    assert overall.lag_available_fit_spearman == pytest.approx(1.0)
    missing_rows = summary[summary.lag_context_available.eq("missing")]
    assert (missing_rows.n == 0).all()


def test_context_sensitivity_summary_carries_expected_keys(bundle):
    frame, manifest, _, _ = bundle
    result = selected(frame, manifest)
    _, summary = audit.context_sensitivity(
        frame, result["designs"], SPEC, ALPHA, result["lag_columns"]
    )
    assert len(summary) == 3 * (1 + len(CYCLES))
    assert set(summary.lag_context_available) == {"all", "available", "missing"}
    assert set(summary.cycle) == {"all", *(str(cycle) for cycle in CYCLES)}
    base = {"cycle", "lag_context_available", "n", "missing_context_share",
            "lag_available_fit_rows", "headline_mean_abs_lag_component"}
    metrics = {"n", "mean_diff", "mae", "max_abs_diff", "sign_change_share", "spearman"}
    expected = base | {f"{name}_{metric}" for name in audit.ALTERNATIVES for metric in metrics}
    assert set(summary.columns) == expected
    overall = summary[summary.cycle.eq("all") & summary.lag_context_available.eq("all")].iloc[0]
    assert overall.n == len(frame)
    assert overall.missing_context_share == pytest.approx(
        1 - frame.lag_context_available.mean()
    )
    per_cycle = summary[summary.cycle.ne("all") & summary.lag_context_available.eq("all")]
    assert per_cycle.n.sum() == len(frame)
    assert summary.no_lag_spec_sign_change_share.dropna().between(0, 1).all()


# --------------------------------------------------------------------------- bootstrap


def test_bootstrap_is_reproducible_and_intervals_are_coherent(bundle):
    frame, manifest, _, _ = bundle
    result = selected(frame, manifest)
    first, first_summary = audit.bootstrap_uncertainty(
        frame, result["design"], ALPHA, result["lag_columns"], draws=60, seed=11
    )
    second, second_summary = audit.bootstrap_uncertainty(
        frame, result["design"], ALPHA, result["lag_columns"], draws=60, seed=11
    )
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(first_summary, second_summary)
    other, _ = audit.bootstrap_uncertainty(
        frame, result["design"], ALPHA, result["lag_columns"], draws=60, seed=12
    )
    assert not np.allclose(first.expected_gap_se, other.expected_gap_se)

    assert len(first) == len(frame)
    assert (first.expected_gap_se >= 0).all()
    assert (first.expected_gap_p05 <= first.expected_gap_p95).all()
    assert (first.expected_gap_p05 <= first.fitted_structural_expected_gap).all()
    assert (first.fitted_structural_expected_gap <= first.expected_gap_p95).all()
    np.testing.assert_allclose(first.war_p05, first.raw_gap - first.expected_gap_p95, atol=1e-12)
    np.testing.assert_allclose(first.war_p95, first.raw_gap - first.expected_gap_p05, atol=1e-12)
    assert (first.war_p05 <= first.war).all() and (first.war <= first.war_p95).all()
    expected_flag = (first.war_p05 > 0) | (first.war_p95 < 0)
    assert first.war_interval_excludes_zero.tolist() == expected_flag.tolist()
    assert first.war_party_draw_agreement_share.between(0, 1).all()
    assert (first.bootstrap_draws == 60).all()

    assert set(first_summary.group_type) == {"all", "cycle", "state_code"}
    assert set(first_summary.loc[first_summary.group_type.eq("state_code"), "group"]) == set(LAG_STATES)
    assert set(first_summary.loc[first_summary.group_type.eq("cycle"), "group"]) == {
        str(cycle) for cycle in CYCLES
    }
    assert set(first_summary.columns) == {
        "group_type", "group", "n", "median_expected_gap_se", "mean_expected_gap_se",
        "median_war_interval_width", "share_war_interval_excludes_zero",
        "share_war_party_stable_all_draws", "mean_war_party_draw_agreement",
    }
    overall = first_summary[first_summary.group_type.eq("all")].iloc[0]
    assert overall.n == len(frame)
    assert 0 <= overall.share_war_interval_excludes_zero <= 1
    assert overall.share_war_party_stable_all_draws <= overall.mean_war_party_draw_agreement + 1e-12


def test_bootstrap_rejects_fewer_than_two_draws(bundle):
    frame, manifest, _, _ = bundle
    result = selected(frame, manifest)
    with pytest.raises(ValueError, match="at least two draws"):
        audit.bootstrap_uncertainty(frame, result["design"], ALPHA, result["lag_columns"], draws=1)


# --------------------------------------------------------------------------- cross-fit


def test_cross_fit_comparison_by_cycle(bundle):
    frame, _, _, _ = bundle
    comparison = audit.cross_fit_comparison(frame)
    assert comparison.cycle.tolist() == ["all", *(str(cycle) for cycle in CYCLES)]
    assert set(comparison.columns) == {
        "cycle", "n", "headline_war_mae", "cross_fitted_residual_mae", "mean_difference",
        "mae_difference", "max_abs_difference", "pearson_correlation", "sign_agreement_share",
    }
    assert comparison.n.iloc[0] == len(frame) and comparison.n.iloc[1:].sum() == len(frame)
    assert (comparison.mae_difference >= 0).all()
    assert comparison.sign_agreement_share.between(0, 1).all()
    assert comparison.pearson_correlation.between(-1, 1).all()


# --------------------------------------------------------------------------- CLI


def test_cli_writes_every_output_when_load_run_is_patched(bundle, monkeypatch, tmp_path):
    frame, manifest, races, published = bundle
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_run(run_dir, manifest, published)
    monkeypatch.setattr(audit, "load_run", lambda root: (manifest, published, races))
    output_dir = tmp_path / "out"
    report = tmp_path / "docs" / "SOUTHERN_V3_CONTEXT_SENSITIVITY.md"
    exit_code = audit.main([
        "--run-dir", str(run_dir), "--output-dir", str(output_dir), "--report", str(report),
        "--draws", "25", "--seed", "3",
    ])
    assert exit_code == 0
    for name in audit.OUTPUT_FILES:
        assert (output_dir / name).exists(), name
    assert report.exists()

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["parity_gate"] == "passed"
    assert summary["model_run_id"] == RUN_ID
    assert summary["warehouse_build_run_id"] == WAREHOUSE_RUN
    assert summary["bootstrap"]["draws"] == 25 and summary["bootstrap"]["seed"] == 3
    assert set(summary["sha256"]) == {
        "manifest.json", "race_war.csv", "scripts/audit_southern_v3_context_sensitivity.py",
        "scripts/retrain_post2016_southern_war.py", "scripts/retrain_post2016_southern_war_v2.py",
        "scripts/retrain_post2016_southern_war_v3.py",
    }
    assert summary["sha256"]["race_war.csv"] == audit.sha256(run_dir / "race_war.csv")
    assert summary["training_rows"] == len(frame)
    assert {row["cycle"] for row in summary["missing_context_by_cycle"]} == set(CYCLES)
    assert set(summary["context_sensitivity"]) == {"all", "available", "missing"}
    assert set(summary["context_sensitivity"]["missing"]) == set(audit.ALTERNATIVES)
    assert summary["context_sensitivity"]["missing"]["lag_available_fit"]["mae"] is None
    assert "generated_at_utc" in summary and "runtime_seconds" in summary

    by_race = pd.read_csv(output_dir / "context_sensitivity_by_race.csv")
    assert len(by_race) == len(frame) and by_race.model_run_id.eq(RUN_ID).all()
    assert len(pd.read_csv(output_dir / "bootstrap_uncertainty_by_race.csv")) == len(frame)
    assert len(pd.read_csv(output_dir / "cross_fit_comparison.csv")) == 1 + len(CYCLES)
    assert len(pd.read_csv(output_dir / "context_sensitivity_summary.csv")) == 3 * (1 + len(CYCLES))
    text = report.read_text(encoding="utf-8")
    assert "## What this audit does not establish" in text
    assert "No predictive validation" in text
    assert RUN_ID in text and "Status: **passed**" in text
