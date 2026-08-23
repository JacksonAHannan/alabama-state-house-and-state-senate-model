"""Package the selected post-2016 polling-CMO forecast for publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t


ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "data" / "processed" / "forecast_calibration"
SOURCE_FORECAST = CAL / "post2016_polling_cmo_2026_forecast.csv"
SOURCE_METRICS = CAL / "post2016_polling_cmo_metrics.csv"
SOURCE_BOOTSTRAP = CAL / "post2016_polling_cmo_bootstrap.csv"
SOURCE_MANIFEST = CAL / "post2016_polling_cmo_manifest.json"
ERROR_COMPONENTS = CAL / "robust_forecast_v1_error_components.csv"
SELECTED_SOURCE_SCENARIO = "uniform_polling_federal_within_cycle_orthogonal"
SELECTED_SPECIFICATION = (
    "polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising"
)
SEED = 20260822
SIMULATION_DRAWS = 50_000
PROBABILITY_DF = 5.0
PROBABILITY_SCALE = 5.75
OUTPUT_PREFIX = "post2016_headline_v1"
METHOD = ROOT / "project_docs" / "model" / "POST2016_HEADLINE_FORECAST_V1.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probability(margin: pd.Series | np.ndarray) -> np.ndarray:
    return np.clip(
        student_t.cdf(np.asarray(margin, dtype=float) / PROBABILITY_SCALE, PROBABILITY_DF),
        1e-6,
        1 - 1e-6,
    )


def build_scenarios() -> tuple[pd.DataFrame, float]:
    source = pd.read_csv(SOURCE_FORECAST)
    headline = source[source.scenario.eq(SELECTED_SOURCE_SCENARIO)].copy()
    assert len(headline) == 48
    assert headline.loc[headline.finance_complete, "model_used"].eq(SELECTED_SPECIFICATION).all()
    assert headline.loc[~headline.finance_complete, "model_used"].eq(
        "polling_federal_plus_incumbency"
    ).all()
    national_sd = float(pd.read_csv(ERROR_COMPONENTS).iloc[0].national_sd)
    frames = []
    definitions = {
        "headline": 0.0,
        "environment_dem_favorable": national_sd,
        "environment_rep_favorable": -national_sd,
    }
    for scenario, shift in definitions.items():
        frame = headline.copy()
        frame["source_scenario"] = frame.scenario
        frame["scenario"] = scenario
        frame["polling_error_adjustment"] = shift
        frame["environment_baseline_margin"] = frame.polling_federal_margin
        frame["headline_dem_margin"] = frame.predicted_dem_margin
        frame["predicted_dem_margin"] = frame.headline_dem_margin + shift
        frame["dem_win_probability"] = probability(frame.predicted_dem_margin)
        frame["selected_model"] = "post2016_polling_cmo_within_cycle_finance"
        frames.append(frame)
    scenarios = pd.concat(frames, ignore_index=True)
    return scenarios, national_sd


def simulate_headline(
    scenarios: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    headline = scenarios[scenarios.scenario.eq("headline")].reset_index(drop=True)
    components = pd.read_csv(ERROR_COMPONENTS).iloc[0]
    rng = np.random.default_rng(SEED)
    national = rng.normal(0, components.national_sd, SIMULATION_DRAWS)
    statewide = rng.normal(0, components.state_sd, SIMULATION_DRAWS)
    chamber_error = {
        chamber: rng.normal(0, components.chamber_sd, SIMULATION_DRAWS)
        for chamber in headline.chamber.unique()
    }
    wins = np.empty((SIMULATION_DRAWS, len(headline)), dtype=np.int8)
    uncertainty_rows = []
    for index, race in enumerate(headline.itertuples()):
        margins = (
            race.predicted_dem_margin
            + national
            + statewide
            + chamber_error[race.chamber]
            + rng.normal(0, components.district_sd, SIMULATION_DRAWS)
        )
        wins[:, index] = margins > 0
        uncertainty_rows.append(
            {
                "chamber": race.chamber,
                "district": race.district,
                "conditional_dem_probability": race.dem_win_probability,
                "full_uncertainty_dem_probability": wins[:, index].mean(),
                "margin_80_low": np.quantile(margins, 0.10),
                "margin_80_high": np.quantile(margins, 0.90),
                "margin_95_low": np.quantile(margins, 0.025),
                "margin_95_high": np.quantile(margins, 0.975),
                "draws": SIMULATION_DRAWS,
            }
        )
    seat_rows = []
    for chamber in headline.chamber.unique():
        chamber_wins = wins[:, headline.chamber.eq(chamber).to_numpy()].sum(axis=1)
        counts = pd.Series(chamber_wins).value_counts().sort_index()
        seat_rows.extend(
            {
                "chamber": chamber,
                "dem_modeled_seats": int(seats),
                "probability": count / SIMULATION_DRAWS,
                "draws": SIMULATION_DRAWS,
            }
            for seats, count in counts.items()
        )
    return pd.DataFrame(uncertainty_rows), pd.DataFrame(seat_rows)


def write_methodology(
    build_id: str,
    national_sd: float,
    selected_metric: pd.Series,
    selected_bootstrap: pd.Series,
    finance_complete: int,
) -> None:
    METHOD.write_text(
        f"""# Post-2016 headline forecast

## District estimate

The forecast treats the current national generic-ballot movement from 2024 as the federal result that would otherwise anchor down-ballot performance. Each district begins with its 2024 presidential margin and receives the same national polling swing.

The model then estimates the usual legislative difference from that federal baseline using Alabama elections after 2016. The candidate adjustment includes generic down-ballot lag, incumbency, and fundraising strength relative to what would normally be expected from district partisanship, competitiveness, chamber, and incumbency.

The fundraising normalization uses the current cycle's fundraising and district covariates but no election result. Missing campaign-finance observations remain missing and receive no fundraising adjustment. Current finance coverage is {finance_complete} of 48 contested Democratic-versus-Republican races.

## Historical test

The model trains on 59 contested races in 2018 and predicts 30 contested races in 2022. Its 2022 mean absolute margin error is {selected_metric.mae:.2f} points, compared with 10.00 for the polling-federal baseline and 9.54 for polling plus incumbency.

The paired bootstrap improvement over the polling-federal baseline is {selected_bootstrap.paired_mean_mae_improvement:+.2f} points, with a 95% interval from {selected_bootstrap.bootstrap_ci_low:+.2f} to {selected_bootstrap.bootstrap_ci_high:+.2f}.

## Polling-error scenarios

The Democratic-favorable and Republican-favorable scenarios move every district by one historical national polling-error standard deviation ({national_sd:.2f} margin points) in the corresponding direction. These are shared national shifts, not independent district adjustments.

## Probabilities and chamber totals

Expected margins are converted to conditional win probabilities with a Student-t curve with five degrees of freedom and a 5.75-point scale. Chamber summaries use 50,000 simulations with shared national, statewide, and chamber errors plus district-specific error.

## Limitations

Only one Alabama forward cycle directly tests the full candidate adjustment. Historical fundraising is measured over the full election cycle, while the current 2026 figures are a partial-cycle snapshot. Fundraising can reflect donor expectations and campaign strength as well as resources available to the candidate, so its coefficient should not be interpreted causally.

Build: `{build_id}`.
""",
        encoding="utf-8",
    )


def main() -> None:
    scenarios, national_sd = build_scenarios()
    uncertainty, seats = simulate_headline(scenarios)
    metrics = pd.read_csv(SOURCE_METRICS)
    bootstrap = pd.read_csv(SOURCE_BOOTSTRAP)
    selected_metric = metrics[metrics.specification.eq(SELECTED_SPECIFICATION)].squeeze()
    selected_bootstrap = bootstrap[
        bootstrap.target.eq(SELECTED_SPECIFICATION)
        & bootstrap.reference.eq("polling_federal_only")
    ].squeeze()

    expected_keys = set(
        map(
            tuple,
            scenarios.loc[scenarios.scenario.eq("headline"), ["chamber", "district"]].to_numpy(),
        )
    )
    assert scenarios.groupby("scenario").size().eq(48).all()
    assert not scenarios.duplicated(["scenario", "chamber", "district"]).any()
    for _, group in scenarios.groupby("scenario"):
        assert set(map(tuple, group[["chamber", "district"]].to_numpy())) == expected_keys
    headline = scenarios[scenarios.scenario.eq("headline")]
    assert np.allclose(
        headline.predicted_dem_margin,
        headline.polling_federal_margin + headline.expected_cmo_adjustment,
    )
    for scenario, direction in (
        ("environment_dem_favorable", 1),
        ("environment_rep_favorable", -1),
    ):
        shifted = scenarios[scenarios.scenario.eq(scenario)].sort_values(["chamber", "district"])
        base = headline.sort_values(["chamber", "district"])
        assert np.allclose(
            shifted.predicted_dem_margin.to_numpy() - base.predicted_dem_margin.to_numpy(),
            direction * national_sd,
        )
    assert scenarios.loc[~scenarios.finance_complete, "fundraising_gap_log50"].isna().all()
    assert uncertainty.groupby("chamber").size().to_dict() == headline.groupby("chamber").size().to_dict()
    assert seats.groupby("chamber").probability.sum().round(12).eq(1).all()

    outputs = {
        f"{OUTPUT_PREFIX}_2026_scenarios.csv": scenarios,
        f"{OUTPUT_PREFIX}_2026_full_uncertainty.csv": uncertainty,
        f"{OUTPUT_PREFIX}_2026_modeled_seats.csv": seats,
        f"{OUTPUT_PREFIX}_forward_metrics.csv": metrics,
        f"{OUTPUT_PREFIX}_bootstrap.csv": bootstrap,
    }
    for name, frame in outputs.items():
        frame.to_csv(CAL / name, index=False)

    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    inputs = [SOURCE_FORECAST, SOURCE_METRICS, SOURCE_BOOTSTRAP, SOURCE_MANIFEST, ERROR_COMPONENTS]
    code_inputs = [Path(__file__).resolve()]
    manifest = {
        "schema_version": 1,
        "status": "owner_selected_public_headline_release_candidate",
        "methodology_version": "post2016_headline_v1",
        "source_experiment_build": source_manifest["build_id"],
        "selected_source_scenario": SELECTED_SOURCE_SCENARIO,
        "selected_specification": SELECTED_SPECIFICATION,
        "probability": {"family": "student_t", "df": PROBABILITY_DF, "scale": PROBABILITY_SCALE},
        "simulation": {"seed": SEED, "draws": SIMULATION_DRAWS},
        "polling_error_scenarios": {"shift_points": national_sd},
        "forward_validation": {
            "train_cycle": 2018,
            "test_cycle": 2022,
            "train_races": int(selected_metric.train_races),
            "test_races": int(selected_metric.test_races),
            "mae": float(selected_metric.mae),
            "bootstrap_improvement_vs_polling_federal": float(selected_bootstrap.paired_mean_mae_improvement),
            "bootstrap_ci": [float(selected_bootstrap.bootstrap_ci_low), float(selected_bootstrap.bootstrap_ci_high)],
        },
        "inputs": [
            {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
            for path in inputs
        ],
        "code_inputs": [
            {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
            for path in code_inputs
        ],
        "outputs": [
            {
                "path": f"data/processed/forecast_calibration/{name}",
                "rows": len(frame),
                "sha256": sha256(CAL / name),
            }
            for name, frame in outputs.items()
        ],
    }
    stable = dict(manifest)
    manifest["build_id"] = hashlib.sha256(
        json.dumps(stable, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    manifest_path = CAL / f"{OUTPUT_PREFIX}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_methodology(
        manifest["build_id"],
        national_sd,
        selected_metric,
        selected_bootstrap,
        int(headline.finance_complete.sum()),
    )
    print(
        f"{OUTPUT_PREFIX} build={manifest['build_id']} races=48 "
        f"finance={int(headline.finance_complete.sum())}/48"
    )


if __name__ == "__main__":
    main()
