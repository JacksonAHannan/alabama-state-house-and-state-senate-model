#!/usr/bin/env python3
"""Build 2016-2022 Southern race-residual WAR with a leakage-safe 2016 backcast."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

import retrain_post2016_southern_war as v1
import retrain_post2016_southern_war_v2 as v2
from southern_war_map_contract import scheduled_keys_2016_2022


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data/processed/elections/alabama_elections.sqlite"
PUBLISHED = ROOT / "data/processed/war/post2016_southern_war_v3"
ALABAMA_NAMES = ROOT / "data/processed/war/alabama_historical_war_v1/candidate_cycle_war.csv"
WIKIPEDIA_CANDIDATES = ROOT / "data/processed/war/wikipedia_legislative_candidates.csv"
WIKIPEDIA_2022_VALIDATION = ROOT / "data/processed/war/2022_wikipedia_vote_validation.csv"
FIELD_CONTRACT = ROOT / "project_docs/model/SOUTHERN_HISTORICAL_WAR_MAP_FIELD_CONTRACT.md"
METHOD = ROOT / "project_docs/model/SOUTHERN_HISTORICAL_WAR_V1.md"
AUDIT = ROOT / "project_docs/audits/SOUTHERN_HISTORICAL_WAR_V1_VALIDATION.md"
OUT = ROOT / "data/processed/war/southern_historical_war_v1"
RACE_KEYS = ["state_code", "cycle", "chamber", "district"]
SPECIFICATION = "decaying_lag"
ALPHA = 100.0
TITLE_PREFIX = re.compile(r"^(?:STATE\s+)?(?:REPRESENTATIVE|SENATOR)\s+", re.I)
SOURCE_ID = re.compile(r"^[A-Z]{3}\d{2,3}[A-Z]{3,}$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_strict_history() -> tuple[pd.DataFrame, dict[str, object]]:
    query = """
        SELECT war_outcome_id,build_run_id,state_code,cycle,chamber,district,
               election_stage,election_date,district_plan_id,geography_vintage,
               dem_candidate_result_id,rep_candidate_result_id,
               dem_candidate_name,rep_candidate_name,dem_votes,rep_votes,
               two_party_votes,third_party_votes,legislative_dem_margin,
               baseline_dem_margin,baseline_source,baseline_office,baseline_class,
               baseline_quality,baseline_coverage,dem_incumbent,rep_incumbent,
               incumbency_balance,incumbency_source,incumbency_quality,
               direct_overperformance,training_status,selection_status,
               source_provider,source_family,source_file_id,
               democratic_fundraising,republican_fundraising,
               democratic_finance_status,republican_finance_status,
               finance_complete,log_fundraising_ratio_d_to_r,race_finance_status
        FROM mart_southern_war_training_with_finance
        WHERE cycle BETWEEN 2016 AND 2022 AND training_status = ?
        ORDER BY state_code,cycle,chamber,CAST(district AS INTEGER),district
    """
    uri = f"file:{DATABASE.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        frame = pd.read_sql_query(query, connection, params=(v2.TRAINING_STATUS,))
        run_ids = frame.build_run_id.drop_duplicates().tolist()
        if len(run_ids) != 1:
            raise ValueError(f"Expected one warehouse build run, found {run_ids}")
        run = pd.read_sql_query(
            "SELECT * FROM warehouse_build_run WHERE build_run_id=?", connection,
            params=(run_ids[0],),
        )
    if len(run) != 1 or run.iloc[0].status != "validated":
        raise ValueError("Southern historical WAR input is not one validated warehouse run")
    if frame.empty or frame.duplicated(RACE_KEYS).any() or frame.war_outcome_id.duplicated().any():
        raise ValueError("Southern historical WAR input race grain failed")
    expected = frame.legislative_dem_margin - frame.baseline_dem_margin
    np.testing.assert_allclose(frame.direct_overperformance, expected, atol=1e-10)
    frame["district"] = frame.district.map(v2.normalized_district)
    frame["baseline_office_family"] = frame.baseline_office.map(v1.office_family)
    return frame, run.iloc[0].to_dict()


def score_history(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    modern, _ = v2.load_training()
    modern = v2.add_finance_features(v2.attach_lag_context(modern))
    history = v2.add_finance_features(v2.attach_lag_context(history))
    backcast = history[history.cycle.eq(2016)].copy()
    combined = pd.concat([modern, backcast], ignore_index=True, sort=False)
    designs, lag_columns = v2.design_matrices(combined)
    design = designs[SPECIFICATION]
    model = v2.ridge_model(ALPHA).fit(
        design.iloc[: len(modern)], modern.direct_overperformance.to_numpy(float)
    )
    backcast_design = design.iloc[len(modern):].copy()
    prediction = model.predict(backcast_design)
    nonlag = backcast_design.copy()
    for column in lag_columns:
        nonlag[column] = 0.0
    backcast["fitted_structural_expected_gap"] = prediction
    backcast["fitted_structural_nonlag_expected_gap"] = model.predict(nonlag)
    backcast["fitted_lag_component"] = (
        backcast.fitted_structural_expected_gap - backcast.fitted_structural_nonlag_expected_gap
    )
    backcast["raw_gap"] = backcast.direct_overperformance
    backcast["war"] = backcast.raw_gap - backcast.fitted_structural_expected_gap
    backcast["scoring_scope"] = "post2016_southern_model_backcast"

    published = pd.read_csv(PUBLISHED / "race_war.csv", low_memory=False)
    published["district"] = published.district.map(v2.normalized_district)
    keep = RACE_KEYS + [
        "raw_gap", "fitted_structural_expected_gap",
        "fitted_structural_nonlag_expected_gap", "fitted_lag_component", "war",
    ]
    post = history[history.cycle.gt(2016)].merge(
        published[keep], on=RACE_KEYS, how="left", validate="one_to_one",
    )
    if post.war.isna().any():
        raise ValueError("A strict 2017-2022 race is absent from published Southern WAR v3")
    np.testing.assert_allclose(post.direct_overperformance, post.raw_gap, atol=1e-9)
    post["scoring_scope"] = "published_same_cycle_residual"
    races = pd.concat([backcast, post], ignore_index=True, sort=False)
    races["war_party"] = np.select([races.war.gt(0), races.war.lt(0)], ["D", "R"], default="EVEN")
    races["war_magnitude"] = races.war.abs()
    races["war_definition"] = "raw_gap_minus_fitted_structural_expected_gap"
    races["backcast_extrapolation_years"] = np.where(races.cycle.eq(2016), 2, 0)

    coefficients = v2.full_model_coefficients(model, list(design.columns))
    scaler = model.named_steps["scale"]
    ridge = model.named_steps["ridge"]
    original = ridge.coef_ / scaler.scale_
    intercept = float(ridge.intercept_ - np.dot(scaler.mean_, original))
    coefficients = pd.concat([
        pd.DataFrame({"feature": ["__intercept__"], "coefficient": [intercept]}),
        coefficients,
    ], ignore_index=True)
    coefficients.insert(0, "structural_alpha", ALPHA)
    coefficients.insert(0, "structural_specification", SPECIFICATION)
    return races.sort_values(RACE_KEYS).reset_index(drop=True), coefficients


def public_name(source_name: object) -> str:
    name = TITLE_PREFIX.sub("", str(source_name).strip())
    if name.upper() == name and any(character.isalpha() for character in name):
        name = name.title()
        name = re.sub(r"\b(Jr|Sr|Ii|Iii|Iv)\b", lambda m: m.group(0).upper(), name)
    return re.sub(r"\s+", " ", name).strip()


def candidate_rows(races: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for race in races.itertuples(index=False):
        for party, orientation in (("D", 1.0), ("R", -1.0)):
            source_name = getattr(race, "dem_candidate_name" if party == "D" else "rep_candidate_name")
            votes = int(getattr(race, "dem_votes" if party == "D" else "rep_votes"))
            incumbent = int(getattr(race, "dem_incumbent" if party == "D" else "rep_incumbent"))
            result_id = getattr(race, "dem_candidate_result_id" if party == "D" else "rep_candidate_result_id")
            rows.append({
                "war_outcome_id": race.war_outcome_id,
                "state_code": race.state_code, "cycle": int(race.cycle),
                "chamber": race.chamber, "district": race.district,
                "canonical_party": party, "candidate_result_id": result_id,
                "source_candidate_name": source_name, "candidate_name": public_name(source_name),
                "votes": votes, "incumbent": incumbent,
                "winner": int(votes > getattr(race, "rep_votes" if party == "D" else "dem_votes")),
                "candidate_cycle_war": orientation * race.war,
                "candidate_raw_gap": orientation * race.raw_gap,
                "candidate_structural_expected_gap": orientation * race.fitted_structural_expected_gap,
                "score_identification": "race_differential_party_orientation",
            })
    candidates = pd.DataFrame(rows)
    alabama = pd.read_csv(ALABAMA_NAMES, low_memory=False)
    alabama["state_code"] = "AL"
    alabama["chamber"] = alabama.chamber.map({"house": "lower", "senate": "upper"})
    alabama["district"] = alabama.district.map(v2.normalized_district)
    aliases = alabama.rename(columns={
        "canonical_party": "canonical_party", "candidate_name": "alabama_verified_name",
    })[RACE_KEYS + ["canonical_party", "alabama_verified_name"]]
    candidates = candidates.merge(
        aliases, on=RACE_KEYS + ["canonical_party"], how="left", validate="one_to_one"
    )
    candidates["candidate_name"] = candidates.alabama_verified_name.fillna(candidates.candidate_name)
    candidates["display_name_source"] = np.where(
        candidates.alabama_verified_name.notna(),
        "verified_alabama_election_identity", "warehouse_election_candidate_cleaned_title",
    )
    candidates = candidates.drop(columns="alabama_verified_name")

    public_aliases: dict[tuple[int, str, str, str, int], str] = {}
    wikipedia = pd.read_csv(WIKIPEDIA_CANDIDATES, low_memory=False)
    wikipedia["chamber"] = wikipedia.chamber.map({"house": "lower", "senate": "upper"})
    for row in wikipedia.itertuples(index=False):
        if pd.notna(row.votes_wikipedia):
            public_aliases[(int(row.cycle), row.chamber, v2.normalized_district(row.district), row.party, int(row.votes_wikipedia))] = str(row.candidate)
    validation = pd.read_csv(WIKIPEDIA_2022_VALIDATION, low_memory=False)
    validation["chamber"] = validation.chamber.map({"house": "lower", "senate": "upper"})
    for row in validation.itertuples(index=False):
        if pd.notna(row.votes_modeled):
            display = row.candidate_wikipedia if pd.notna(row.candidate_wikipedia) else row.candidate_modeled
            if pd.notna(display):
                public_aliases[(int(row.cycle), row.chamber, v2.normalized_district(row.district), row.party, int(row.votes_modeled))] = str(display)
    alabama_mask = candidates.state_code.eq("AL")
    for index, row in candidates.loc[alabama_mask].iterrows():
        key = (int(row.cycle), row.chamber, row.district, row.canonical_party, int(row.votes))
        if key in public_aliases:
            candidates.at[index, "candidate_name"] = public_aliases[key]
            candidates.at[index, "display_name_source"] = "archived_election_page_exact_race_vote_match"
    bad = candidates.candidate_name.astype(str).str.fullmatch(SOURCE_ID)
    committee = candidates.candidate_name.astype(str).str.contains("committee", case=False, na=False)
    blank = candidates.candidate_name.astype(str).str.strip().str.lower().isin({"", "nan", "none", "null"})
    if bad.any() or committee.any() or blank.any():
        raise ValueError("Blank, identifier-, or committee-shaped candidate display name entered Southern WAR")
    return candidates


def main() -> None:
    history, warehouse_run = load_strict_history()
    races, coefficients = score_history(history)
    candidates = candidate_rows(races)
    formula_error = float(np.max(np.abs(
        races.war - (races.raw_gap - races.fitted_structural_expected_gap)
    )))
    paired = candidates.pivot(index="war_outcome_id", columns="canonical_party", values="candidate_cycle_war")
    orientation_error = float(np.max(np.abs(paired.D + paired.R)))
    if formula_error > 1e-9 or orientation_error > 1e-9:
        raise ValueError("Southern historical WAR arithmetic failed")

    schedule = pd.DataFrame(
        sorted(scheduled_keys_2016_2022()),
        columns=["state_code", "cycle", "chamber"],
    )
    coverage = races.groupby(["state_code", "cycle", "chamber"], as_index=False).agg(
        scored_races=("war_outcome_id", "size"),
        finance_complete_races=("finance_complete", "sum"),
        lag_context_races=("lag_context_available", "sum"),
        mean_absolute_war=("war", lambda values: float(values.abs().mean())),
    )
    coverage = schedule.merge(coverage, on=["state_code", "cycle", "chamber"], how="left", validate="one_to_one")
    for column in ("scored_races", "finance_complete_races", "lag_context_races"):
        coverage[column] = coverage[column].fillna(0).astype(int)
    coverage["finance_coverage_rate"] = np.where(
        coverage.scored_races.gt(0), coverage.finance_complete_races / coverage.scored_races, np.nan
    )

    race_columns = [
        "war_outcome_id", *RACE_KEYS, "election_date", "district_plan_id", "geography_vintage",
        "dem_candidate_name", "rep_candidate_name", "dem_votes", "rep_votes", "two_party_votes",
        "legislative_dem_margin", "baseline_dem_margin", "baseline_source", "baseline_office",
        "incumbency_balance", "raw_gap", "lag_context_available",
        "fitted_structural_nonlag_expected_gap", "fitted_lag_component",
        "fitted_structural_expected_gap", "war", "war_party", "war_magnitude",
        "war_definition", "scoring_scope", "backcast_extrapolation_years",
        "democratic_fundraising", "republican_fundraising", "democratic_finance_status",
        "republican_finance_status", "finance_complete", "log_fundraising_ratio_d_to_r",
        "race_finance_status", "source_provider", "source_family", "source_file_id",
    ]
    race_output = races[race_columns].copy()
    incomplete_finance = ~race_output.finance_complete.eq(1)
    race_output.loc[
        incomplete_finance,
        ["democratic_fundraising", "republican_fundraising", "log_fundraising_ratio_d_to_r"],
    ] = np.nan
    candidate_output = candidates.copy()
    input_paths = [
        DATABASE, PUBLISHED / "manifest.json", PUBLISHED / "race_war.csv", ALABAMA_NAMES,
        WIKIPEDIA_CANDIDATES, WIKIPEDIA_2022_VALIDATION,
        FIELD_CONTRACT, Path(__file__).resolve(), Path(v2.__file__).resolve(), Path(v1.__file__).resolve(),
        Path(__file__).with_name("southern_war_map_contract.py"),
    ]
    run_basis = {
        "methodology_version": "southern_historical_war_v1",
        "warehouse_build_run_id": warehouse_run["build_run_id"],
        "inputs": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in input_paths},
        "configuration": {
            "scope": "prespecified Southern regular elections 2016-2022",
            "strict_training_status": v2.TRAINING_STATUS,
            "post2016_score_source": "post2016_southern_war_v3 published same-cycle residual",
            "backcast_cycle": 2016,
            "backcast_training_cutoff": "cycle > 2016",
            "structural_specification": SPECIFICATION,
            "structural_alpha": ALPHA,
            "finance_in_headline_war": False,
        },
    }
    run_id = "WAR-SOUTH-HIST-V1-" + hashlib.sha256(
        json.dumps(run_basis, sort_keys=True).encode()
    ).hexdigest()[:20].upper()
    for frame in (race_output, candidate_output, coefficients, coverage):
        frame.insert(0, "historical_war_run_id", run_id)
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "race_war.csv": race_output,
        "candidate_cycle_war.csv": candidate_output,
        "structural_coefficients.csv": coefficients,
        "coverage.csv": coverage,
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)

    state_finance = race_output.groupby("state_code").agg(
        scored=("war_outcome_id", "size"), complete=("finance_complete", "sum")
    )
    generated = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest = {
        "schema_version": 1, "historical_war_run_id": run_id,
        "status": "validated_descriptive_historical_release", "generated_at_utc": generated,
        "source_commit": git_commit(), **run_basis,
        "diagnostics": {
            "scheduled_slices": len(schedule), "scored_races": len(race_output),
            "candidate_cycle_rows": len(candidate_output), "states": int(race_output.state_code.nunique()),
            "cycles": sorted(int(value) for value in race_output.cycle.unique()),
            "backcast_races": int(race_output.cycle.eq(2016).sum()),
            "published_post2016_races": int(race_output.cycle.gt(2016).sum()),
            "finance_complete_races": int(race_output.finance_complete.sum()),
            "formula_max_error": formula_error, "orientation_max_error": orientation_error,
        },
        "finance_coverage_by_state": {
            state: {"scored_races": int(row.scored), "complete_races": int(row.complete),
                    "coverage_rate": float(row.complete / row.scored)}
            for state, row in state_finance.iterrows()
        },
        "outputs": [],
    }
    for name, frame in outputs.items():
        manifest["outputs"].append({
            "path": str((OUT / name).relative_to(ROOT)).replace("\\", "/"),
            "rows": len(frame), "sha256": sha256(OUT / name),
        })
    METHOD.write_text(
        f"# Southern historical WAR v1\n\nRun: `{run_id}`\n\n"
        f"The release scores {len(race_output):,} strict D-versus-R regular legislative races "
        "in the 14-state Southern scope from 2016 through 2022. Post-2016 races preserve the "
        "published Southern WAR v3 same-cycle structural residual. The 2016 races are scored "
        "by applying the selected post-2016 `decaying_lag` ridge model (alpha 100) backward, "
        "without using any 2016 outcome to fit the model.\n\n"
        "`WAR = legislative-minus-ticket gap - fitted structural expected gap`.\n\n"
        "Fundraising is displayed only where both major-party observations and identities are "
        "complete. It does not enter headline WAR because the prespecified nested time-forward "
        "finance test failed. Missouri and Mississippi are the principal finance gaps in this "
        "warehouse run; missing finance is unknown, never zero. Research-only context, "
        "uncontested races, and non-D/R races remain unscored.\n",
        encoding="utf-8",
    )
    AUDIT.write_text(
        f"# Southern historical WAR v1 validation\n\nRun `{run_id}` generated {generated}.\n\n"
        f"- {len(schedule)} scheduled state/cycle/chamber slices from 2016 through 2022.\n"
        f"- {len(race_output):,} unique strict race scores and {len(candidate_output):,} exact party orientations.\n"
        f"- {int(race_output.cycle.eq(2016).sum()):,} 2016 backcast races use no 2016 fitting outcomes.\n"
        f"- Formula error: {formula_error:.3g}; candidate-orientation error: {orientation_error:.3g}.\n"
        "- Missing finance remains null and finance is excluded from headline WAR.\n"
        "- Public map geometry is validated separately against exact election-year Census files.\n",
        encoding="utf-8",
    )
    manifest["reports"] = [
        {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
        for path in (FIELD_CONTRACT, METHOD, AUDIT)
    ]
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Southern historical WAR: run={run_id} races={len(race_output):,} candidates={len(candidate_output):,}")


if __name__ == "__main__":
    main()
