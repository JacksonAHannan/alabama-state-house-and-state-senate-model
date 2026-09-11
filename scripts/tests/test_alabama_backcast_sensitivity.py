"""Synthetic-fixture tests for the Alabama backcast sensitivity audit."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

import audit_alabama_backcast_sensitivity as audit
import retrain_post2016_southern_war_v2 as v2


ALPHA = 10.0
RUN_ID = "AL-HIST-WAR-V1-TESTRUN0000000000"
WAREHOUSE_RUN = "RUN-TEST-WAREHOUSE"
MODERN_CYCLES = (2018, 2020)
HISTORICAL_CYCLES = (1994, 1998, 2010, 2014)


def make_races(
    cycles=(1994, 1998, 2010, 2014),
    missing_cycles=(1994,),
    modern: bool = False,
    seed: int = 11,
) -> pd.DataFrame:
    """Small synthetic race frame usable for both the modern and historical sides."""
    rng = np.random.default_rng(seed)
    rows = []
    for cycle in cycles:
        for chamber in ("lower", "upper"):
            for district in range(1, 4):
                baseline = rng.normal(-6.0, 15.0)
                lag_available = cycle not in missing_cycles
                prior = baseline + rng.normal(0.0, 5.0) if lag_available else np.nan
                incumbency = int(rng.choice([-1, 0, 1]))
                change = 0.0 if not lag_available else baseline - prior
                direct = (
                    2.0 * incumbency + 0.05 * baseline - 0.12 * change
                    + 0.4 * (cycle - 2016) + rng.normal(0.0, 2.0)
                )
                if modern:
                    rows.append({
                        "build_run_id": WAREHOUSE_RUN,
                        "state_code": "AL" if district == 1 else "GA",
                        "cycle": cycle,
                        "chamber": chamber,
                        "district": str(district),
                        "incumbency_balance": incumbency,
                        "baseline_dem_margin": baseline,
                        "baseline_office_family": "president" if cycle == 2020 else "governor",
                        "prior_pres_margin": prior,
                        "lag_current_ticket_change": change if lag_available else np.nan,
                        "years_since_2016": cycle - 2016,
                        "lag_change_x_years": (
                            (change if lag_available else np.nan) * (cycle - 2016)
                        ),
                        "direct_overperformance": direct,
                        "lag_context_available": lag_available,
                    })
                else:
                    rows.append({
                        "state_code": "AL",
                        "cycle": cycle,
                        "chamber": chamber,
                        "district": district,
                        "raw_gap": direct,
                        "direct_overperformance": direct,
                        "incumbency_balance": incumbency,
                        "baseline_dem_margin": baseline,
                        "baseline_office_family": "federal_composite" if chamber == "lower"
                        else "state_composite",
                        "prior_pres_margin": prior,
                        "prior_presidential_margin": prior,
                        "lag_context_available": lag_available,
                        "lag_current_ticket_change": baseline - prior,
                        "years_since_2016": cycle - 2016,
                        "lag_change_x_years": (baseline - prior) * (cycle - 2016),
                    })
    frame = pd.DataFrame(rows)
    return frame


@pytest.fixture
def frame():
    """Historical frame with a rebuilt backcast and the matching design."""
    historical = make_races()
    modern = make_races(cycles=MODERN_CYCLES, missing_cycles=(), modern=True)
    combined = pd.concat([modern, historical], ignore_index=True, sort=False)
    designs, lag_columns = v2.design_matrices(combined)
    backcast, design, model = audit.reproduce_backcast(
        historical,
        designs[audit.SPECIFICATION],
        len(modern),
        modern.direct_overperformance.to_numpy(float),
        lag_columns,
        alpha=ALPHA,
    )
    return {
        "modern": modern,
        "historical": historical,
        "designs": designs,
        "lag_columns": lag_columns,
        "backcast": backcast,
        "design": design,
        "model": model,
    }


# --------------------------------------------------------------------------- helpers


def test_war_party_labels_uses_the_published_even_rule():
    labels = audit.war_party_labels(np.array([1e-13, 0.0, -0.5, np.nan, -1e-9]))
    assert labels.tolist()[:3] == ["EVEN", "EVEN", "R"]
    assert labels[3] is None
    assert labels[4] == "R"


def test_comparison_metrics_identity_and_shift():
    headline = np.array([1.0, -2.0, 3.0, 0.0, 5.0])
    identity = audit.comparison_metrics(headline, headline)
    assert identity["n"] == 5
    assert identity["mae"] == 0.0 and identity["max_abs_diff"] == 0.0
    assert identity["sign_change_share"] == 0.0
    assert identity["pearson"] == pytest.approx(1.0)
    assert identity["spearman"] == pytest.approx(1.0)
    assert identity["median_diff"] == 0.0

    shifted = audit.comparison_metrics(headline, headline + 4.0)
    assert shifted["mean_diff"] == pytest.approx(4.0)
    assert shifted["mae"] == pytest.approx(4.0)
    assert shifted["pearson"] == pytest.approx(1.0)
    assert shifted["sign_change_share"] > 0.0

    flipped = audit.comparison_metrics(headline, -headline)
    assert flipped["pearson"] == pytest.approx(-1.0)
    assert flipped["sign_change_share"] == pytest.approx(0.8)


def test_comparison_metrics_drops_non_finite_pairs():
    headline = np.array([1.0, np.nan, 3.0])
    alternative = np.array([1.0, 2.0, np.nan])
    metrics = audit.comparison_metrics(headline, alternative)
    assert metrics["n"] == 1
    assert metrics["mae"] == 0.0
    assert np.isnan(metrics["pearson"])
    empty = audit.comparison_metrics(np.array([np.nan]), np.array([1.0]))
    assert empty["n"] == 0 and np.isnan(empty["mae"])


def test_normalize_race_keys_maps_chambers_and_districts():
    frame = pd.DataFrame({
        "cycle": [2010, 2010],
        "chamber": ["house", "Senate"],
        "district": ["7.0", 9],
    })
    normalized = audit.normalize_race_keys(frame)
    assert normalized.chamber.tolist() == ["lower", "upper"]
    assert normalized.district.tolist() == ["7", "9"]
    with pytest.raises(ValueError, match="Unknown chamber"):
        audit.normalize_race_keys(frame.assign(chamber="school board"))


# --------------------------------------------------------------------------- parity gate


def test_parity_gate_accepts_matching_values_and_refuses_perturbations():
    published = pd.DataFrame({
        "cycle": [1994, 1998],
        "chamber": ["lower", "upper"],
        "district": ["1", "2"],
        "war": [1.5, -2.0],
        "fitted_structural_expected_gap": [0.5, 0.25],
    })
    reproduced = published.rename(columns={
        "war": "backcast_war", "fitted_structural_expected_gap": "backcast_expected_gap"
    })
    pairs = {"war": "backcast_war", "fitted_structural_expected_gap": "backcast_expected_gap"}
    differences = audit.parity_check(
        published, reproduced.assign(backcast_war=[1.5 + 1e-12, -2.0]), pairs
    )
    assert set(differences) == set(pairs)
    assert all(value <= audit.PARITY_TOLERANCE for value in differences.values())

    with pytest.raises(ValueError, match="Parity gate failed"):
        audit.parity_check(published, reproduced.assign(backcast_war=[1.5 + 1e-4, -2.0]), pairs)
    with pytest.raises(ValueError, match="Parity gate failed"):
        audit.parity_check(
            published, reproduced.assign(backcast_expected_gap=np.nan), pairs
        )
    with pytest.raises(ValueError, match="Parity gate failed"):
        audit.parity_check(published, reproduced.iloc[:1], pairs)
    with pytest.raises(ValueError, match="lacks"):
        audit.parity_check(
            published, reproduced.drop(columns=["backcast_war"]), pairs
        )


def test_load_published_run_refuses_a_foreign_run_id(tmp_path):
    manifest = {"historical_war_run_id": RUN_ID}
    published = pd.DataFrame({
        "historical_war_run_id": [RUN_ID, RUN_ID],
        "cycle": [1994, 1998],
        "chamber": ["lower", "upper"],
        "district": ["1", "2"],
        "war": [1.0, -1.0],
    })
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    published.to_csv(tmp_path / "race_war.csv", index=False)
    loaded_manifest, loaded = audit.load_published_run(tmp_path, RUN_ID)
    assert loaded_manifest["historical_war_run_id"] == RUN_ID
    assert len(loaded) == 2

    with pytest.raises(ValueError, match="not the bound run"):
        audit.load_published_run(tmp_path, "AL-HIST-WAR-V1-SOMETHINGELSE0000")
    published.assign(historical_war_run_id="AL-HIST-WAR-V1-SOMETHINGELSE0000").to_csv(
        tmp_path / "race_war.csv", index=False
    )
    with pytest.raises(ValueError, match="carries run ids"):
        audit.load_published_run(tmp_path, RUN_ID)


def test_align_published_refuses_missing_races():
    published = pd.DataFrame({
        "cycle": [1994],
        "chamber": ["lower"],
        "district": ["1"],
        "war": [1.0],
    })
    keys = pd.DataFrame({
        "cycle": [1994, 1998],
        "chamber": ["house", "upper"],
        "district": ["1", "2"],
    })
    aligned = audit.align_published(published, keys.iloc[:1])
    assert aligned.war.tolist() == [1.0]
    with pytest.raises(ValueError, match="lacks rebuilt races"):
        audit.align_published(published, keys)


# --------------------------------------------------------------------------- era fits


def test_reproduce_backcast_zero_fills_missing_lag_entries(frame):
    backcast = frame["backcast"]
    missing = ~backcast.lag_context_available.astype(bool)
    assert missing.any() and (~missing).any()
    assert backcast.loc[missing, "backcast_lag_component"].abs().max() == 0.0
    np.testing.assert_allclose(
        backcast.backcast_war,
        backcast.raw_gap - backcast.backcast_expected_gap,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        backcast.backcast_expected_gap - backcast.backcast_nonlag_expected_gap,
        backcast.backcast_lag_component,
        atol=1e-12,
    )


def test_era_transportability_compares_each_cycle(frame):
    backcast, design = frame["backcast"], frame["design"]
    by_race, summary = audit.era_transportability(backcast, design, alpha=ALPHA)
    assert len(by_race) == len(backcast)
    assert by_race.cycle.tolist() == backcast.cycle.tolist()
    assert set(summary.cycle) == {"all", *(str(c) for c in HISTORICAL_CYCLES)}
    assert summary.loc[summary.cycle.ne("all"), "n"].sum() == len(backcast)
    assert summary.pearson.dropna().between(-1, 1).all()
    assert summary.sign_change_share.between(0, 1).all()
    assert (summary.mae >= 0).all()
    np.testing.assert_allclose(
        by_race.diff_same_era_minus_backcast,
        by_race.same_era_war - by_race.backcast_war,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        by_race.same_era_war, by_race.raw_gap - by_race.same_era_expected_gap, atol=1e-12
    )
    overall = summary[summary.cycle.eq("all")].iloc[0]
    assert overall.n == len(backcast)
    assert overall.p05_diff <= overall.median_diff <= overall.p95_diff


def test_leave_one_era_out_scores_the_held_out_half_and_drifts_coefficients(frame):
    backcast, design = frame["backcast"], frame["design"]
    summary = audit.leave_one_era_out(backcast, design, alpha=ALPHA)
    assert summary.fit_era.tolist() == ["1994_2006", "2010_2014"]
    assert summary.score_era.tolist() == ["2010_2014", "1994_2006"]
    assert summary.n.tolist() == [
        int(backcast.cycle.isin((2010, 2014)).sum()),
        int(backcast.cycle.isin((1994, 1998)).sum()),
    ]
    assert summary.mae.between(0, np.inf).all()

    drift = audit.coefficient_drift_table(
        design,
        backcast.direct_overperformance.to_numpy(float),
        backcast.cycle.to_numpy(),
        audit.model_coefficients(frame["model"], list(design.columns)),
        frame["lag_columns"],
        alpha=ALPHA,
    )
    assert drift.feature.iloc[0] == "__intercept__"
    assert set(drift.term_family) == {"intercept", "structural", "lag"}
    np.testing.assert_allclose(
        drift.era_drift,
        drift.coefficient_historical_2010_2014 - drift.coefficient_historical_1994_2006,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        drift.pooled_vs_modern_drift,
        drift.coefficient_historical_pooled_1994_2014 - drift.coefficient_modern_backcast,
        atol=1e-12,
    )
    assert not drift.loc[drift.feature.ne("__intercept__"), "era_comparable"].all()
    constant = drift[(drift.term_family.eq("structural")) & (~drift.era_comparable)]
    assert (constant.era_drift == 0.0).all()
    assert constant.coefficient_historical_1994_2006.eq(0.0).all()


def test_model_coefficients_reproduce_the_scaled_ridge_fit(frame):
    design, model = frame["design"], frame["model"]
    coefficients = audit.model_coefficients(model, list(design.columns))
    prediction = design.to_numpy(float) @ coefficients[list(design.columns)].to_numpy(float)
    prediction += coefficients["__intercept__"]
    np.testing.assert_allclose(
        prediction, model.predict(design), atol=1e-9
    )


# --------------------------------------------------------------------------- missing lag


def test_missing_lag_sensitivity_rescores_the_full_backcast(frame):
    backcast = frame["backcast"]
    by_race, summary = audit.missing_lag_sensitivity(
        backcast,
        frame["designs"],
        len(frame["modern"]),
        frame["modern"].direct_overperformance.to_numpy(float),
        frame["modern"].lag_context_available.to_numpy(bool),
        frame["lag_columns"],
        alpha=ALPHA,
    )
    assert len(by_race) == len(backcast)
    available = by_race.lag_context_available.to_numpy(bool)
    assert available.any() and (~available).any()
    for name in audit.LAG_ALTERNATIVES:
        assert by_race[f"war_{name}"].notna().all()
        np.testing.assert_allclose(
            by_race[f"diff_{name}"],
            by_race[f"war_{name}"] - by_race.war,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            by_race[f"war_{name}"], by_race.raw_gap - by_race[f"expected_gap_{name}"], atol=1e-12
        )
    assert by_race.loc[~available, "headline_zero_fill_lag_component"].abs().max() == 0.0
    assert (by_race.diff_no_lag_spec.abs().max()) > 1e-6

    assert len(summary) == 3 * (1 + len(HISTORICAL_CYCLES))
    assert set(summary.lag_context_available) == {"all", "available", "missing"}
    base = {"cycle", "lag_context_available", "n", "missing_context_share",
            "headline_mean_abs_lag_component"}
    expected = base | {
        f"{name}_{metric}" for name in audit.LAG_ALTERNATIVES for metric in audit.METRIC_KEYS
    } | {f"{name}_sign_changes" for name in audit.LAG_ALTERNATIVES}
    assert set(summary.columns) == expected
    overall = summary[summary.cycle.eq("all") & summary.lag_context_available.eq("all")].iloc[0]
    assert overall.n == len(backcast)
    assert summary.no_lag_spec_sign_change_share.dropna().between(0, 1).all()
    assert summary.no_lag_spec_sign_changes.dropna().ge(0).all()
    missing_row = summary[summary.cycle.eq("all") & summary.lag_context_available.eq("missing")].iloc[0]
    assert missing_row.n == int((~available).sum())
    assert missing_row.no_lag_spec_sign_changes == int(
        by_race.loc[~available, "sign_change_no_lag_spec"].sum()
    )


def test_missing_lag_sensitivity_refuses_a_mismatched_tail_mask(frame):
    backcast = frame["backcast"]
    with pytest.raises(ValueError, match="tail mask"):
        audit.missing_lag_sensitivity(
            backcast,
            frame["designs"],
            len(frame["modern"]),
            frame["modern"].direct_overperformance.to_numpy(float),
            frame["modern"].lag_context_available.to_numpy(bool),
            frame["lag_columns"],
            tail_mask=np.ones(len(backcast) - 1, dtype=bool),
            alpha=ALPHA,
        )


# --------------------------------------------------------------------------- bootstrap


def test_bootstrap_expected_gap_is_deterministic_and_responds_to_the_seed(frame):
    design = frame["designs"][audit.SPECIFICATION].iloc[: len(frame["modern"])]
    score = frame["design"]
    target = frame["modern"].direct_overperformance.to_numpy(float)
    cycles = frame["modern"].cycle.to_numpy()
    first = audit.bootstrap_expected_gap(design, target, cycles, score, alpha=ALPHA,
                                         draws=24, seed=5)
    second = audit.bootstrap_expected_gap(design, target, cycles, score, alpha=ALPHA,
                                          draws=24, seed=5)
    np.testing.assert_allclose(first, second)
    other = audit.bootstrap_expected_gap(design, target, cycles, score, alpha=ALPHA,
                                        draws=24, seed=6)
    assert first.shape == (24, len(score))
    assert not np.allclose(first, other)
    with pytest.raises(ValueError, match="at least two draws"):
        audit.bootstrap_expected_gap(design, target, cycles, score, alpha=ALPHA, draws=1)
    with pytest.raises(ValueError, match="different columns"):
        audit.bootstrap_expected_gap(design, target, cycles, score.iloc[:, :-1], alpha=ALPHA,
                                     draws=4, seed=1)


def test_bootstrap_backcast_intervals_are_coherent(frame):
    by_race, summary = audit.bootstrap_backcast(
        frame["backcast"],
        frame["designs"][audit.SPECIFICATION].iloc[: len(frame["modern"])],
        frame["modern"].direct_overperformance.to_numpy(float),
        frame["modern"].cycle.to_numpy(),
        frame["design"],
        alpha=ALPHA,
        draws=32,
        seed=9,
    )
    assert len(by_race) == len(frame["backcast"])
    assert (by_race.expected_gap_se >= 0).all()
    assert (by_race.expected_gap_p05 <= by_race.expected_gap_p95).all()
    np.testing.assert_allclose(
        by_race.war_p05, by_race.raw_gap - by_race.expected_gap_p95, atol=1e-12
    )
    np.testing.assert_allclose(
        by_race.war_p95, by_race.raw_gap - by_race.expected_gap_p05, atol=1e-12
    )
    expected_flag = (by_race.war_p05 > 0) | (by_race.war_p95 < 0)
    assert by_race.war_interval_excludes_zero.tolist() == expected_flag.tolist()
    assert by_race.war_party_draw_agreement_share.between(0, 1).all()
    assert (by_race.bootstrap_draws == 32).all()
    assert set(summary.group_type) == {"all", "cycle"}
    assert set(summary.loc[summary.group_type.eq("cycle"), "group"]) == {
        str(cycle) for cycle in HISTORICAL_CYCLES
    }
    assert set(summary.columns) == {
        "group_type", "group", "n", "median_expected_gap_se", "mean_expected_gap_se",
        "median_war_interval_width", "share_war_interval_excludes_zero",
        "share_war_party_stable_all_draws", "mean_war_party_draw_agreement",
    }
    overall = summary[summary.group_type.eq("all")].iloc[0]
    assert overall.n == len(frame["backcast"])
    assert overall.share_war_party_stable_all_draws <= overall.mean_war_party_draw_agreement + 1e-12


# --------------------------------------------------------------------------- CLI


def _write_run(tmp_path, manifest, published):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    published.to_csv(run_dir / "race_war.csv", index=False)
    return run_dir


def test_cli_writes_every_output_when_inputs_are_patched(frame, monkeypatch, tmp_path):
    # ``main`` uses the module default alpha, so publish the fixture's values with it.
    backcast, _, _ = audit.reproduce_backcast(
        frame["historical"].reset_index(drop=True),
        frame["designs"][audit.SPECIFICATION],
        len(frame["modern"]),
        frame["modern"].direct_overperformance.to_numpy(float),
        frame["lag_columns"],
    )
    published = pd.DataFrame({
        "historical_war_run_id": RUN_ID,
        "cycle": backcast.cycle,
        "chamber": backcast.chamber.map({"lower": "house", "upper": "senate"}),
        "district": backcast.district,
        "raw_gap": backcast.raw_gap,
        "fitted_structural_expected_gap": backcast.backcast_expected_gap,
        "fitted_structural_nonlag_expected_gap": backcast.backcast_nonlag_expected_gap,
        "fitted_lag_component": backcast.backcast_lag_component,
        "war": backcast.backcast_war,
        "modern_backcast_structural_expected_gap": backcast.backcast_expected_gap,
        "modern_backcast_war": backcast.backcast_war,
    })
    manifest = {
        "historical_war_run_id": RUN_ID,
        "warehouse_build_run_id": WAREHOUSE_RUN,
        "source_southern_war_run_id": "WAR-POST2016-V3-TESTSOURCE",
        "source_alabama_war_run_id": "AL-WAR-V1-TESTMODERN",
        "input_hashes": {},
    }
    run_dir = _write_run(tmp_path, manifest, published)
    monkeypatch.setattr(audit, "EXPECTED_HISTORICAL_RUN_ID", RUN_ID)
    monkeypatch.setattr(
        audit.historical_builder, "prepare_historical_races", lambda: frame["historical"]
    )
    monkeypatch.setattr(
        audit.v2, "load_training",
        lambda: (frame["modern"], {"build_run_id": WAREHOUSE_RUN, "status": "validated"}),
    )
    monkeypatch.setattr(audit.v2, "attach_lag_context", lambda frame: frame)
    output_dir = tmp_path / "out"
    report = tmp_path / "docs" / "ALABAMA_BACKCAST_SENSITIVITY_2026_09_11.md"
    report_json = tmp_path / "docs" / "ALABAMA_BACKCAST_SENSITIVITY_2026_09_11.json"
    exit_code = audit.main([
        "--run-dir", str(run_dir), "--output-dir", str(output_dir),
        "--report", str(report), "--report-json", str(report_json),
        "--expected-run-id", RUN_ID, "--draws", "16", "--seed", "3",
    ])
    assert exit_code == 0
    for name in audit.OUTPUT_FILES:
        assert (output_dir / name).exists(), name
    assert report.exists() and report_json.exists()

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["parity_gate"] == "passed"
    assert summary["historical_war_run_id"] == RUN_ID
    assert summary["parity_max_abs_difference"]["war"] <= audit.PARITY_TOLERANCE
    assert summary["bootstrap"]["draws"] == 16 and summary["bootstrap"]["seed"] == 3
    assert summary["race_counts"]["backcast_races"] == len(frame["backcast"])
    assert summary["race_counts"]["warehouse_writes"] == 0
    missing_headline = summary["headline"]["missing_lag"]["no_lag_spec"]
    assert 0 <= missing_headline["sign_changes"] <= missing_headline["n"]
    assert missing_headline["max_abs_diff"] >= abs(missing_headline["mean_diff"]) - 1e-12
    assert set(summary["headline"]["era_transportability_by_cycle"]) == {
        str(cycle) for cycle in HISTORICAL_CYCLES
    }
    assert "generated_at_utc" in summary and "runtime_seconds" in summary
    assert set(summary["sha256"]) == {
        "manifest.json", "race_war.csv",
        "scripts/audit_alabama_backcast_sensitivity.py",
        "scripts/build_alabama_historical_war_v1.py",
        "scripts/retrain_post2016_southern_war.py",
        "scripts/retrain_post2016_southern_war_v2.py",
    }
    assert summary["sha256"]["race_war.csv"] == audit.sha256(run_dir / "race_war.csv")
    assert summary["input_hash_drift"] == []

    by_race = pd.read_csv(output_dir / "missing_lag_by_race.csv")
    assert len(by_race) == len(frame["backcast"])
    assert by_race.historical_war_run_id.eq(RUN_ID).all()
    assert len(pd.read_csv(output_dir / "era_transportability_summary.csv")) == 1 + len(
        HISTORICAL_CYCLES
    )
    assert len(pd.read_csv(output_dir / "bootstrap_backcast_summary.csv")) == 1 + len(
        HISTORICAL_CYCLES
    )
    text = report.read_text(encoding="utf-8")
    assert "## Parity gate" in text
    assert "## What this audit does not establish" in text
    assert "No recertification" in text and RUN_ID in text
