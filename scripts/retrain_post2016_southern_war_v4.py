#!/usr/bin/env python3
"""Fit a finance-free, Split Ticket-style Southern legislative WAR model.

WAR is the race residual from a regression of the legislative margin minus an
environment-adjusted presidential margin.  Structural predictors are lagged
presidential partisanship and swing, symmetric incumbency, two ACS demographic
shares, and state/chamber intercepts.  Finance and candidate history are not
used.  Rows without exact-vintage presidential context remain unscored.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from warehouse import connect


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/war/post2016_southern_war_v4"
TRAINING = ROOT / "data/processed/war/finance_free_southern_war/southern_war_training_no_finance.csv"
ACS = OUT / "acs_demographics.csv"
DAILY_KOS = ROOT / "data/raw/historical_statewide_elections/Daily Kos Elections Statewide Results by LD (public).xlsx"
BAF_2022 = ROOT / "data/raw/historical_statewide_elections/national_2022_elections_st_leg_boundaries.zip"
BLOCK_2020 = ROOT / "data/raw/historical_statewide_elections/national_block_2020_pres_results.zip"
VEST_ALLOCATION_MANIFEST = ROOT / "data/processed/presidential/southern_vest_2016_allocations/manifest.json"
HISTORICAL_ALLOCATION_MANIFEST = ROOT / "data/processed/presidential/southern_historical_plan_allocations/manifest.json"
PRECINCT_2012_ALLOCATION_MANIFEST = ROOT / "data/processed/presidential/southern_2012_plan_allocations/manifest.json"
MISSISSIPPI_2012_PARTIAL_MANIFEST = ROOT / "data/processed/presidential/mississippi_2012_partial_plan_allocations/manifest.json"
CENSUS_BLOCK_MANIFEST = ROOT / "data/processed/source_audits/southern_2020_census_block_manifest.csv"
AL_2018 = ROOT / "data/processed/presidential/2018_district_presidential_features.csv"
AL_2022 = ROOT / "data/processed/presidential/2022_district_presidential_features.csv"
RACE_KEYS = ["state_code", "cycle", "chamber", "district"]
NUMERIC_FEATURES = [
    "recent_pres_margin", "lag_swing_from_older", "lag_swing_from_recent",
    "incumbency_balance", "nonwhite_share", "white_college_share",
]
CATEGORICAL_FEATURES = ["state_code", "chamber"]
NATIONAL_ENVIRONMENT_SWING = {
    2018: 6.495625,
    2019: 3.214798,
    2020: 0.0,
    2022: -7.397496,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def district_number(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").round().astype("Int64")


def daily_kos_margins() -> pd.DataFrame:
    """Normalize presidential result groups from the public LD workbook."""
    outputs: list[pd.DataFrame] = []
    book = pd.ExcelFile(DAILY_KOS)
    states = {"AR", "FL", "GA", "KY", "LA", "MS", "MO", "NC", "OK", "SC", "TN", "TX", "VA"}
    candidate_pairs = {
        2012: ({"OBAMA"}, {"ROMNEY"}),
        2016: ({"CLINTON"}, {"TRUMP"}),
        2020: ({"BIDEN"}, {"TRUMP"}),
    }
    for sheet in book.sheet_names:
        clean = sheet.strip()
        state = clean.split("_", 1)[0]
        if state not in states or "_" not in clean:
            continue
        chamber = "upper" if clean.endswith("Upper") else "lower"
        raw = pd.read_excel(DAILY_KOS, sheet_name=sheet, header=None)
        if len(raw) < 3:
            continue
        row0 = raw.iloc[0].fillna("").astype(str).str.strip()
        row1 = raw.iloc[1].fillna("").astype(str).str.strip()
        district_all = district_number(raw.iloc[2:, 0]).reset_index(drop=True)
        valid_positions = np.flatnonzero(district_all.notna().to_numpy())
        if not len(valid_positions):
            continue
        first = int(valid_positions[0])
        following_missing = np.flatnonzero(district_all.iloc[first:].isna().to_numpy())
        stop = first + int(following_missing[0]) if len(following_missing) else len(district_all)
        row_slice = slice(2 + first, 2 + stop)
        district = district_all.iloc[first:stop].reset_index(drop=True)
        sheet_title = str(row0.iloc[0]).strip()
        plan_note = " | ".join(value for value in row0.iloc[1:6] if value)
        for year, (dem_names, rep_names) in candidate_pairs.items():
            starts = [index for index, value in enumerate(row0) if f"{year} President" in value]
            for start in starts:
                end = next((index for index in range(start + 1, len(row0)) if row0.iloc[index]), len(row0))
                labels = row1.iloc[start:end].str.upper().str.replace(r"[^A-Z]", "", regex=True)
                dem_columns = [start + index for index, value in enumerate(labels) if value in dem_names]
                rep_columns = [start + index for index, value in enumerate(labels) if value in rep_names]
                if not dem_columns or not rep_columns:
                    continue
                dem = pd.to_numeric(raw.iloc[row_slice, dem_columns[0]], errors="coerce").reset_index(drop=True)
                rep = pd.to_numeric(raw.iloc[row_slice, rep_columns[0]], errors="coerce").reset_index(drop=True)
                denominator = dem + rep
                frame = pd.DataFrame({
                    "state_code": state,
                    "chamber": chamber,
                    "district": district,
                    "presidential_year": year,
                    "presidential_dem_margin": 100 * (dem - rep) / denominator.where(denominator.gt(0)),
                    "presidential_source": "Daily Kos Elections presidential results by legislative district",
                    "presidential_source_path": str(DAILY_KOS.relative_to(ROOT)).replace("\\", "/"),
                    "source_plan_label": f"{sheet_title}; {plan_note}".strip("; "),
                }).dropna(subset=["district", "presidential_dem_margin"])
                outputs.append(frame)
    if not outputs:
        raise ValueError("Daily Kos workbook produced no presidential margins")
    combined = pd.concat(outputs, ignore_index=True)
    keys = ["state_code", "chamber", "district", "presidential_year"]
    # Repeated groups must agree; conflicting plan observations cannot be averaged.
    spread = combined.groupby(keys).presidential_dem_margin.agg(lambda x: x.max() - x.min())
    if spread.gt(1e-8).any():
        conflicts = spread[spread.gt(1e-8)].head().to_dict()
        raise ValueError(f"Conflicting Daily Kos presidential observations: {conflicts}")
    return combined.drop_duplicates(keys).sort_values(keys)


def new_plan_margins() -> pd.DataFrame:
    with closing(connect(readonly=True)) as connection:
        central = pd.read_sql_query(
            """SELECT state_code,chamber,district,election_cycle AS presidential_year,
                      100.0*two_party_dem_margin AS presidential_dem_margin,
                      assignment_source_file_id,allocation_method
               FROM fact_southern_presidential_district_result
               WHERE election_cycle IN (2016,2020) AND plan_cycle=2022
                 AND allocation_status='passed'""",
            connection,
        )
    keys = ["state_code", "chamber", "district", "presidential_year"]
    if len(central) != 4_532 or central.duplicated(keys).any():
        raise ValueError("Central 2016/2020 presidential context on the 2022 plan is incomplete")
    central["district"] = district_number(central.district)
    central["presidential_source"] = "central Southern presidential district result fact"
    central["presidential_source_path"] = "warehouse:fact_southern_presidential_district_result"
    central["source_plan_label"] = central.allocation_method.map({
        "vest_precinct_2020_vap_weighted_to_rdh_baf":
            "VEST 2016 precinct votes weighted by 2020 block VAP to RDH 2022 BAF",
        "exact_2020_census_block_assignment":
            "RDH 2020 block results joined to RDH 2022 BAF",
    }).fillna(central.allocation_method)
    return central[[
        "state_code", "chamber", "district", "presidential_year", "presidential_dem_margin",
        "presidential_source", "presidential_source_path", "source_plan_label",
    ]]


def historical_plan_margins() -> pd.DataFrame:
    with closing(connect(readonly=True)) as connection:
        central = pd.read_sql_query(
            """SELECT state_code,chamber,district,plan_cycle AS target_cycle,
                      election_cycle AS presidential_year,
                      100.0*two_party_dem_margin AS presidential_dem_margin,
                      allocation_method
               FROM fact_southern_presidential_district_result
               WHERE election_cycle IN (2012,2016,2020)
                 AND plan_cycle BETWEEN 2018 AND 2020""",
            connection,
        )
    keys = ["state_code", "chamber", "district", "target_cycle", "presidential_year"]
    if central.duplicated(keys).any():
        raise ValueError("Central historical-plan presidential context is duplicated")
    central["district"] = district_number(central.district)
    central["presidential_source"] = "central Southern presidential district result fact"
    central["presidential_source_path"] = "warehouse:fact_southern_presidential_district_result"
    central["source_plan_label"] = central.allocation_method
    central["source_priority"] = 0
    return central


def allocation_run_id() -> str:
    with closing(connect(readonly=True)) as connection:
        row = connection.execute(
            """SELECT build_run_id FROM warehouse_build_run
               WHERE target='southern_presidential_district_allocations' AND status='validated'
               ORDER BY completed_at_utc DESC LIMIT 1"""
        ).fetchone()
    if row is None:
        raise ValueError("No validated central presidential district allocation run exists")
    return row[0]


def vest_allocation_run_id() -> str:
    with closing(connect(readonly=True)) as connection:
        row = connection.execute(
            """SELECT build_run_id FROM warehouse_build_run
               WHERE target='southern_2016_vest_plan_allocation' AND status='validated'
               ORDER BY completed_at_utc DESC LIMIT 1"""
        ).fetchone()
    if row is None:
        raise ValueError("No validated VEST 2016 plan-allocation run exists")
    return row[0]


def historical_allocation_run_id() -> str:
    with closing(connect(readonly=True)) as connection:
        row = connection.execute(
            """SELECT build_run_id FROM warehouse_build_run
               WHERE target='southern_historical_plan_allocations' AND status='validated'
               ORDER BY completed_at_utc DESC LIMIT 1"""
        ).fetchone()
    if row is None:
        raise ValueError("No validated historical-plan presidential allocation run exists")
    return row[0]


def precinct_2012_allocation_run_id() -> str:
    with closing(connect(readonly=True)) as connection:
        row = connection.execute(
            """SELECT build_run_id FROM warehouse_build_run
               WHERE target='southern_2012_plan_allocations' AND status='validated'
               ORDER BY completed_at_utc DESC LIMIT 1"""
        ).fetchone()
    if row is None:
        raise ValueError("No validated 2012 precinct plan-allocation run exists")
    return row[0]


def mississippi_2012_partial_run_id() -> str:
    with closing(connect(readonly=True)) as connection:
        row = connection.execute(
            """SELECT build_run_id FROM warehouse_build_run
               WHERE target='mississippi_2012_partial_plan_allocations' AND status='validated'
               ORDER BY completed_at_utc DESC LIMIT 1"""
        ).fetchone()
    if row is None:
        raise ValueError("No validated district-specific Mississippi 2012 allocation run exists")
    return row[0]


def alabama_margins() -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    for cycle, path, years in ((2018, AL_2018, (2012, 2016)), (2022, AL_2022, (2016, 2020))):
        frame = pd.read_csv(path)
        frame["state_code"] = "AL"
        frame["chamber"] = frame.chamber.map({"house": "lower", "senate": "upper"}).fillna(frame.chamber)
        frame["district"] = district_number(frame.district)
        for year in years:
            margin = f"pres_{year}_dem_margin"
            complete = f"pres_{year}_source_complete"
            selected = frame[frame[complete].eq(True)] if complete in frame else frame
            out = selected[["state_code", "chamber", "district", margin]].rename(
                columns={margin: "presidential_dem_margin"}
            )
            out["presidential_year"], out["target_cycle"] = year, cycle
            out["presidential_source"] = "canonical Alabama presidential district feature"
            out["presidential_source_path"] = str(path.relative_to(ROOT)).replace("\\", "/")
            out["source_plan_label"] = f"Alabama {cycle} legislative plan"
            outputs.append(out)
    return pd.concat(outputs, ignore_index=True)


def presidential_context(races: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    old = daily_kos_margins()
    old["source_priority"] = 1
    old["target_cycle"] = np.nan
    historical = historical_plan_margins()
    new = new_plan_margins()
    alabama = alabama_margins()
    rows: list[dict[str, object]] = []
    for race in races[RACE_KEYS].itertuples(index=False):
        if race.cycle == 2022:
            source = new[
                new.state_code.eq(race.state_code) & new.chamber.eq(race.chamber)
                & new.district.eq(race.district)
            ]
            if race.state_code == "AL":
                source = alabama[
                    alabama.target_cycle.eq(2022) & alabama.chamber.eq(race.chamber)
                    & alabama.district.eq(race.district)
                ]
            needed = (2016, 2020)
        else:
            legacy = old[
                old.state_code.eq(race.state_code) & old.chamber.eq(race.chamber)
                & old.district.eq(race.district)
            ]
            exact = historical[
                historical.state_code.eq(race.state_code)
                & historical.target_cycle.eq(race.cycle)
                & historical.chamber.eq(race.chamber)
                & historical.district.eq(race.district)
            ]
            source = pd.concat([exact, legacy], ignore_index=True, sort=False).sort_values(
                "source_priority"
            ).drop_duplicates("presidential_year", keep="first")
            if race.state_code == "AL":
                source = alabama[
                    alabama.target_cycle.eq(2018) & alabama.chamber.eq(race.chamber)
                    & alabama.district.eq(race.district)
                ]
            needed = (2012, 2016, 2020) if race.cycle == 2020 else (2012, 2016)
        record: dict[str, object] = dict(zip(RACE_KEYS, race))
        for year in needed:
            match = source[source.presidential_year.eq(year)]
            record[f"pres_{year}_dem_margin"] = match.iloc[0].presidential_dem_margin if len(match) == 1 else np.nan
            record[f"pres_{year}_source"] = match.iloc[0].presidential_source_path if len(match) == 1 else ""
        rows.append(record)
    context = pd.DataFrame(rows)
    context["older_pres_year"] = np.where(context.cycle.eq(2022), 2016, 2012)
    context["recent_pres_year"] = np.where(context.cycle.eq(2022), 2020, 2016)
    context["current_pres_year"] = np.where(context.cycle.eq(2020), 2020, context.recent_pres_year)
    context["older_pres_margin"] = np.select(
        [context.older_pres_year.eq(2012), context.older_pres_year.eq(2016)],
        [context.get("pres_2012_dem_margin"), context.get("pres_2016_dem_margin")], default=np.nan,
    )
    context["recent_pres_margin"] = np.select(
        [context.recent_pres_year.eq(2016), context.recent_pres_year.eq(2020)],
        [context.get("pres_2016_dem_margin"), context.get("pres_2020_dem_margin")], default=np.nan,
    )
    context["current_pres_margin"] = np.select(
        [context.current_pres_year.eq(2016), context.current_pres_year.eq(2020)],
        [context.get("pres_2016_dem_margin"), context.get("pres_2020_dem_margin")], default=np.nan,
    )
    context["national_environment_swing"] = context.cycle.map(NATIONAL_ENVIRONMENT_SWING)
    context["environment_baseline_margin"] = context.current_pres_margin + context.national_environment_swing
    context["lag_swing_from_older"] = context.environment_baseline_margin - context.older_pres_margin
    context["lag_swing_from_recent"] = context.environment_baseline_margin - context.recent_pres_margin
    context["presidential_context_complete"] = context[
        ["older_pres_margin", "recent_pres_margin", "current_pres_margin", "national_environment_swing"]
    ].notna().all(axis=1)
    inventory = pd.concat(
        [old, historical, new.assign(target_cycle=2022), alabama], ignore_index=True,
    )
    return context, inventory


def model_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer([
        ("numeric", StandardScaler(), NUMERIC_FEATURES),
        ("categorical", OneHotEncoder(drop="first", handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    return Pipeline([("preprocess", preprocessor), ("regression", LinearRegression())])


def fit_headline(races: pd.DataFrame) -> pd.DataFrame:
    output = races.copy()
    output["fitted_structural_expected_gap"] = np.nan
    output["structural_training_rows"] = 0
    for cycle, group in output[output.model_eligible].groupby("cycle"):
        if len(group) < len(NUMERIC_FEATURES) + 10:
            continue
        model = model_pipeline().fit(group[NUMERIC_FEATURES + CATEGORICAL_FEATURES], group.raw_gap)
        prediction = model.predict(group[NUMERIC_FEATURES + CATEGORICAL_FEATURES])
        output.loc[group.index, "fitted_structural_expected_gap"] = prediction
        output.loc[group.index, "structural_training_rows"] = len(group)
    output["war"] = output.raw_gap - output.fitted_structural_expected_gap
    output["war_party"] = np.select([output.war.gt(0), output.war.lt(0)], ["D", "R"], default="UNSCORED")
    output["war_magnitude"] = output.war.abs()
    output["war_definition"] = "raw_presidential_gap_minus_same_cycle_fitted_structural_gap"
    return output


def forward_validation(races: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    predictions: list[pd.DataFrame] = []
    metrics: list[dict[str, object]] = []
    eligible = races[races.model_eligible].copy()
    for cycle in sorted(eligible.cycle.unique()):
        train = eligible[eligible.cycle.lt(cycle)]
        test = eligible[eligible.cycle.eq(cycle)]
        if len(train) < 100 or test.empty:
            continue
        model = model_pipeline().fit(train[NUMERIC_FEATURES + CATEGORICAL_FEATURES], train.raw_gap)
        predicted = model.predict(test[NUMERIC_FEATURES + CATEGORICAL_FEATURES])
        frame = test[["war_outcome_id", *RACE_KEYS, "raw_gap"]].copy()
        frame["forward_expected_gap"] = predicted
        frame["forward_residual"] = frame.raw_gap - predicted
        frame["training_rows"] = len(train)
        predictions.append(frame)
        metrics.append({
            "test_cycle": int(cycle), "train_min_cycle": int(train.cycle.min()),
            "train_max_cycle": int(train.cycle.max()), "training_rows": len(train), "test_rows": len(test),
            "model_mae": mean_absolute_error(test.raw_gap, predicted),
            "zero_adjustment_mae": mean_absolute_error(test.raw_gap, np.zeros(len(test))),
            "model_rmse": mean_squared_error(test.raw_gap, predicted) ** 0.5,
        })
    return (
        pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame(),
        pd.DataFrame(metrics),
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    races = pd.read_csv(TRAINING, low_memory=False)
    races = races[
        races.cycle.gt(2016) & races.cycle.le(2022)
        & races.training_status.eq("strict_war_ready_no_finance")
    ].copy()
    races["district"] = district_number(races.district)
    if races.duplicated(RACE_KEYS).any():
        raise ValueError("WAR v4 input contains duplicate race keys")
    context, inventory = presidential_context(races)
    demographics = pd.read_csv(ACS)
    races = races.merge(context, on=RACE_KEYS, how="left", validate="one_to_one")
    races = races.merge(demographics, on=RACE_KEYS, how="left", validate="one_to_one")
    races["raw_gap"] = races.legislative_dem_margin - races.environment_baseline_margin
    races["demographics_complete"] = races[["nonwhite_share", "white_college_share"]].notna().all(axis=1)
    races["incumbency_complete"] = races.incumbency_balance.notna()
    races["model_eligible"] = (
        races.presidential_context_complete & races.demographics_complete & races.incumbency_complete
        & races.raw_gap.notna()
    )
    scored = fit_headline(races)
    forward, metrics = forward_validation(races)
    candidate_rows: list[pd.DataFrame] = []
    for party, sign, name in (("D", 1.0, "dem_candidate_name"), ("R", -1.0, "rep_candidate_name")):
        frame = scored[["war_outcome_id", *RACE_KEYS, name, "war"]].rename(columns={name: "candidate_name"})
        frame["canonical_party"] = party
        frame["candidate_cycle_war"] = sign * frame.war
        frame["score_identification"] = "race_differential_party_orientation"
        candidate_rows.append(frame)
    candidates = pd.concat(candidate_rows, ignore_index=True)
    coverage = scored.groupby(["state_code", "cycle", "chamber"], as_index=False).agg(
        strict_races=("war_outcome_id", "size"),
        presidential_context_complete=("presidential_context_complete", "sum"),
        demographics_complete=("demographics_complete", "sum"),
        model_eligible=("model_eligible", "sum"),
        scored_war=("war", "count"),
    )
    input_paths = (
        TRAINING, ACS, DAILY_KOS, BAF_2022, BLOCK_2020, VEST_ALLOCATION_MANIFEST,
        HISTORICAL_ALLOCATION_MANIFEST, PRECINCT_2012_ALLOCATION_MANIFEST,
        MISSISSIPPI_2012_PARTIAL_MANIFEST, CENSUS_BLOCK_MANIFEST, AL_2018, AL_2022,
    )
    input_hashes = {str(path): sha256(path) for path in input_paths}
    context_allocation_run_id = allocation_run_id()
    vest_context_allocation_run_id = vest_allocation_run_id()
    historical_context_allocation_run_id = historical_allocation_run_id()
    precinct_2012_context_allocation_run_id = precinct_2012_allocation_run_id()
    mississippi_2012_context_allocation_run_id = mississippi_2012_partial_run_id()
    run_seed = json.dumps({
        "inputs": input_hashes,
        "context_allocation_run_id": context_allocation_run_id,
        "vest_context_allocation_run_id": vest_context_allocation_run_id,
        "historical_context_allocation_run_id": historical_context_allocation_run_id,
        "precinct_2012_context_allocation_run_id": precinct_2012_context_allocation_run_id,
        "mississippi_2012_context_allocation_run_id": mississippi_2012_context_allocation_run_id,
        "features": NUMERIC_FEATURES + CATEGORICAL_FEATURES,
        "cycles": ">2016,<=2022",
        "finance": False,
    }, sort_keys=True).encode("utf-8")
    model_run_id = f"WAR-SOUTH-V4-{hashlib.sha256(run_seed).hexdigest()[:20].upper()}"
    outputs = {
        "race_war.csv": scored,
        "candidate_cycle_war.csv": candidates,
        "coverage.csv": coverage,
        "presidential_context.csv": context,
        "presidential_margin_inventory.csv": inventory,
        "forward_predictions.csv": forward,
        "forward_metrics.csv": metrics,
    }
    for name, frame in outputs.items():
        frame["model_run_id"] = model_run_id
        frame["code_version"] = git_commit()
        frame.to_csv(OUT / name, index=False)
    manifest = {
        "model_run_id": model_run_id,
        "model_version": "post2016_southern_war_v4_finance_free",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "code_version": git_commit(),
        "training_window": "cycle > 2016 and cycle <= 2022",
        "headline_definition": "WAR = (legislative margin - environment-adjusted presidential margin) - fitted structural gap",
        "features": NUMERIC_FEATURES + CATEGORICAL_FEATURES,
        "finance_included": False,
        "candidate_history_included": False,
        "context_allocation_run_id": context_allocation_run_id,
        "vest_context_allocation_run_id": vest_context_allocation_run_id,
        "historical_context_allocation_run_id": historical_context_allocation_run_id,
        "precinct_2012_context_allocation_run_id": precinct_2012_context_allocation_run_id,
        "mississippi_2012_context_allocation_run_id": mississippi_2012_context_allocation_run_id,
        "missingness_policy": "unscored unless presidential context, ACS demographics, and incumbency are all observed",
        "diagnostics": {
            "strict_input_races": len(scored),
            "presidential_context_complete": int(scored.presidential_context_complete.sum()),
            "demographics_complete": int(scored.demographics_complete.sum()),
            "headline_scored_races": int(scored.war.notna().sum()),
            "max_war_reconciliation_error": float((
                scored.war - (scored.raw_gap - scored.fitted_structural_expected_gap)
            ).abs().dropna().max()),
        },
        "sources": [
            {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
            for path in input_paths
        ],
        "outputs": [
            {"path": str((OUT / name).relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(OUT / name)}
            for name in outputs
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest["diagnostics"], indent=2))
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
