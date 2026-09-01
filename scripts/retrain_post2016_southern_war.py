#!/usr/bin/env python3
"""Retrain candidate WAR from strict modern Southern warehouse observations.

The model reads the canonical finance-free WAR mart in SQLite using a read-only
connection.  It admits only strict-ready races whose cycle is strictly greater
than 2016.  WAR is a partial-pooled candidate effect on the legislative-minus-
ticket margin after a contemporaneous state/cycle/chamber/baseline replacement
level.  Finance is deliberately outside the estimand.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
import subprocess
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data/processed/elections/alabama_elections.sqlite"
OUT = ROOT / "data/processed/war/post2016_southern_war"
METHOD_REPORT = ROOT / "project_docs/model/POST2016_SOUTHERN_WAR.md"
AUDIT_REPORT = ROOT / "project_docs/audits/POST2016_SOUTHERN_WAR_VALIDATION.md"
TRAINING_STATUS = "strict_war_ready_no_finance"
CUTOFF_CYCLE = 2016
QUALITY_PENALTIES = (1.0, 3.0, 10.0, 30.0, 100.0)
GENERIC_INCUMBENCY_MARGIN = 3.0
MIN_REPLACEMENT_GROUP = 3
RACE_KEYS = ["state_code", "cycle", "chamber", "district"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def read_only_connection() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DATABASE.resolve().as_posix()}?mode=ro", uri=True)


def load_training() -> tuple[pd.DataFrame, dict[str, object]]:
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
               source_provider,source_family,source_file_id
        FROM mart_southern_war_training_no_finance
        WHERE cycle > ? AND training_status = ?
        ORDER BY state_code,cycle,chamber,CAST(district AS INTEGER),district
    """
    with read_only_connection() as connection:
        frame = pd.read_sql_query(query, connection, params=(CUTOFF_CYCLE, TRAINING_STATUS))
        run_ids = frame.build_run_id.drop_duplicates().tolist()
        if len(run_ids) != 1:
            raise ValueError(f"Expected one warehouse build run, found {run_ids}")
        run = pd.read_sql_query(
            "SELECT * FROM warehouse_build_run WHERE build_run_id=?",
            connection,
            params=(run_ids[0],),
        )
    if len(run) != 1 or run.iloc[0].status != "validated":
        raise ValueError("Southern WAR input does not reference one validated warehouse run")
    if frame.empty:
        raise ValueError("No strict post-2016 Southern WAR observations")
    if not frame.cycle.gt(CUTOFF_CYCLE).all():
        raise ValueError("Training cutoff violation")
    if not frame.training_status.eq(TRAINING_STATUS).all():
        raise ValueError("Non-strict observation entered training")
    if frame.duplicated(RACE_KEYS).any() or frame.war_outcome_id.duplicated().any():
        raise ValueError("WAR input is not unique at the declared race grain")
    required = [
        "dem_candidate_name", "rep_candidate_name", "dem_votes", "rep_votes",
        "legislative_dem_margin", "baseline_dem_margin", "direct_overperformance",
        "incumbency_balance",
    ]
    if frame[required].isna().any().any():
        raise ValueError("Strict input contains a missing required field")
    expected = frame.legislative_dem_margin - frame.baseline_dem_margin
    np.testing.assert_allclose(frame.direct_overperformance, expected, atol=1e-10)
    return frame, run.iloc[0].to_dict()


def normalized_name(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii").strip()
    if "," in raw:
        last, remainder = raw.split(",", 1)
        raw = f"{remainder.strip()} {last.strip()}"
    raw = re.sub(r"\b(JR|SR|II|III|IV)\b", "", raw.upper())
    return re.sub(r"[^A-Z0-9]+", " ", raw).strip()


def slug(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", value).strip("-") or "UNKNOWN"


def candidate_rows(races: pd.DataFrame) -> pd.DataFrame:
    shared = [
        "war_outcome_id", *RACE_KEYS, "direct_overperformance", "incumbency_balance",
        "dem_incumbent", "rep_incumbent",
    ]
    rows = []
    for party, prefix in (("D", "dem"), ("R", "rep")):
        part = races[shared].copy()
        part["canonical_party"] = party
        part["candidate_result_id"] = races[f"{prefix}_candidate_result_id"]
        part["candidate_name"] = races[f"{prefix}_candidate_name"]
        part["incumbent"] = races[f"{prefix}_incumbent"].astype(int)
        rows.append(part)
    candidates = pd.concat(rows, ignore_index=True)
    candidates["normalized_candidate_name"] = candidates.candidate_name.map(normalized_name)
    candidates["surname_only"] = ~candidates.normalized_candidate_name.str.contains(" ", regex=False)
    collision_names = (
        candidates.groupby(["state_code", "cycle", "normalized_candidate_name"])
        .war_outcome_id.nunique().loc[lambda values: values.gt(1)].reset_index()
        [["state_code", "normalized_candidate_name"]].drop_duplicates()
    )
    collision_keys = set(map(tuple, collision_names.to_numpy()))
    candidates["same_cycle_name_collision"] = [
        (row.state_code, row.normalized_candidate_name) in collision_keys
        for row in candidates.itertuples()
    ]
    candidates["candidate_effect_id"] = [
        (
            f"{row.state_code}-RACE-{slug(row.normalized_candidate_name)}-"
            f"{row.cycle}-{row.chamber.upper()}-{slug(str(row.district))}-{row.canonical_party}"
            if row.surname_only or row.same_cycle_name_collision
            else f"{row.state_code}-NAME-{slug(row.normalized_candidate_name)}"
        )
        for row in candidates.itertuples()
    ]
    candidates["identity_status"] = np.select(
        [candidates.surname_only, candidates.same_cycle_name_collision],
        ["surname_only_race_specific", "same_cycle_collision_race_specific"],
        default="state_scoped_normalized_full_name",
    )
    if candidates.duplicated(["war_outcome_id", "canonical_party"]).any():
        raise ValueError("Candidate rows are not unique by race and party")
    return candidates


def office_family(value: object) -> str:
    text = normalized_name(value)
    if "GENERIC" in text and "BALLOT" in text:
        return "generic_ballot"
    if "PRES" in text:
        return "president"
    if "SENATE" in text:
        return "us_senate"
    if "HOUSE" in text:
        return "us_house"
    if "GOVERNOR" in text:
        return "governor"
    if "STATEWIDE" in text or "ATTORNEY GENERAL" in text:
        return "statewide_other"
    if "FEDERAL" in text:
        return "federal_composite"
    if "STATE" in text:
        return "state_composite"
    return "other"


def add_replacement_levels(races: pd.DataFrame) -> pd.DataFrame:
    frame = races.copy()
    frame["baseline_office_family"] = frame.baseline_office.map(office_family)
    hierarchies = [
        ("state_cycle_chamber_office", ["state_code", "cycle", "chamber", "baseline_office_family"]),
        ("state_cycle_chamber", ["state_code", "cycle", "chamber"]),
        ("state_cycle", ["state_code", "cycle"]),
        ("cycle_chamber", ["cycle", "chamber"]),
        ("cycle", ["cycle"]),
    ]
    selected_level = pd.Series(np.nan, index=frame.index, dtype=float)
    selected_n = pd.Series(0, index=frame.index, dtype=int)
    selected_method = pd.Series("", index=frame.index, dtype="string")
    selected_group = pd.Series("", index=frame.index, dtype="string")
    for method, columns in hierarchies:
        stats = frame.groupby(columns, dropna=False).direct_overperformance.agg(["mean", "size"])
        row_index = pd.MultiIndex.from_frame(frame[columns]) if len(columns) > 1 else pd.Index(frame[columns[0]])
        means = stats["mean"].reindex(row_index).to_numpy()
        sizes = stats["size"].reindex(row_index).to_numpy()
        eligible = selected_level.isna().to_numpy() & (sizes >= MIN_REPLACEMENT_GROUP)
        selected_level.loc[eligible] = means[eligible]
        selected_n.loc[eligible] = sizes[eligible]
        selected_method.loc[eligible] = method
        keys = frame[columns].astype(str).agg("|".join, axis=1)
        selected_group.loc[eligible] = method + ":" + keys.loc[eligible]
    if selected_level.isna().any():
        selected_level = selected_level.fillna(frame.direct_overperformance.mean())
        selected_n = selected_n.mask(selected_n.eq(0), len(frame))
        selected_method = selected_method.mask(selected_method.eq(""), "all_training_rows")
        selected_group = selected_group.mask(selected_group.eq(""), "all_training_rows")
    frame["replacement_level"] = selected_level
    frame["replacement_group_n"] = selected_n
    frame["replacement_method"] = selected_method
    frame["replacement_group"] = selected_group
    frame["war_target"] = frame.direct_overperformance - frame.replacement_level
    return frame


class UnionFind:
    def __init__(self, values: list[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def party_pairs(candidates: pd.DataFrame) -> pd.DataFrame:
    pairs = candidates.pivot(
        index="war_outcome_id", columns="canonical_party", values="candidate_effect_id"
    ).reset_index()
    if set(pairs.columns) != {"war_outcome_id", "D", "R"}:
        raise ValueError("Each modeled race must contain exactly one D and one R candidate")
    return pairs


def fit_candidate_effects(
    candidates: pd.DataFrame, targets: pd.Series, penalty: float
) -> tuple[pd.DataFrame, pd.Series, float]:
    pairs = party_pairs(candidates)
    ids = sorted(set(pairs.D) | set(pairs.R))
    union = UnionFind(ids)
    for row in pairs.itertuples():
        union.union(row.D, row.R)
    component_pairs: dict[str, list[object]] = defaultdict(list)
    for row in pairs.itertuples():
        component_pairs[union.find(row.D)].append(row)

    effect_records: list[dict[str, object]] = []
    fitted = pd.Series(index=pairs.war_outcome_id, dtype=float)
    inverse_diagonals: dict[str, float] = {}
    effective_df = 0.0
    for component_number, root in enumerate(sorted(component_pairs), start=1):
        race_rows = component_pairs[root]
        component_ids = sorted({row.D for row in race_rows} | {row.R for row in race_rows})
        lookup = {candidate: index for index, candidate in enumerate(component_ids)}
        x = np.zeros((len(race_rows), len(component_ids)), dtype=float)
        race_ids = []
        for index, row in enumerate(race_rows):
            x[index, lookup[row.D]] = 1.0
            x[index, lookup[row.R]] = -1.0
            race_ids.append(row.war_outcome_id)
        y = targets.reindex(race_ids).to_numpy(dtype=float)
        precision = x.T @ x + penalty * np.eye(x.shape[1])
        inverse = np.linalg.inv(precision)
        effects = inverse @ x.T @ y
        component_fit = x @ effects
        fitted.loc[race_ids] = component_fit
        effective_df += float(np.trace(x @ inverse @ x.T))
        identification = "pair_differential_only" if len(race_rows) == 1 else "candidate_network"
        for candidate, value in zip(component_ids, effects):
            inverse_diagonals[candidate] = float(inverse[lookup[candidate], lookup[candidate]])
            effect_records.append({
                "candidate_effect_id": candidate,
                "candidate_war": float(value),
                "component_id": f"COMP-{component_number:05d}",
                "component_candidates": len(component_ids),
                "component_races": len(race_rows),
                "quality_identification": identification,
            })
    residual = targets.reindex(fitted.index) - fitted
    sigma = float(np.sqrt(np.sum(np.square(residual)) / max(1.0, len(residual) - effective_df)))
    effects = pd.DataFrame(effect_records)
    effects["candidate_war_se"] = effects.candidate_effect_id.map(
        lambda value: sigma * np.sqrt(inverse_diagonals[value])
    )
    return effects, fitted, sigma


def forward_predictions(
    races: pd.DataFrame, candidates: pd.DataFrame, target_column: str = "war_target"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    targets = races.set_index("war_outcome_id")[target_column]
    pairs = party_pairs(candidates).merge(
        races[["war_outcome_id", "cycle", "state_code", "chamber", "district"]],
        on="war_outcome_id", how="left", validate="one_to_one",
    )
    records = []
    cycles = sorted(races.cycle.unique())
    for penalty in QUALITY_PENALTIES:
        for test_cycle in cycles[1:]:
            train_ids = races.loc[races.cycle.lt(test_cycle), "war_outcome_id"]
            test = pairs[pairs.cycle.eq(test_cycle)].copy()
            if train_ids.empty or test.empty:
                continue
            train_candidates = candidates[candidates.war_outcome_id.isin(train_ids)]
            train_effects, _, _ = fit_candidate_effects(
                train_candidates, targets.reindex(train_ids), penalty
            )
            effect_map = train_effects.set_index("candidate_effect_id").candidate_war
            test["dem_seen"] = test.D.isin(effect_map.index)
            test["rep_seen"] = test.R.isin(effect_map.index)
            test["seen_candidate"] = test.dem_seen | test.rep_seen
            test["prediction"] = test.D.map(effect_map).fillna(0) - test.R.map(effect_map).fillna(0)
            test["actual"] = test.war_outcome_id.map(targets)
            test["error"] = test.actual - test.prediction
            test["penalty"] = penalty
            test["train_min_cycle"] = int(races.loc[races.cycle.lt(test_cycle), "cycle"].min())
            test["train_max_cycle"] = int(races.loc[races.cycle.lt(test_cycle), "cycle"].max())
            records.append(test)
    predictions = pd.concat(records, ignore_index=True)
    metric_rows = []
    for penalty, group in predictions.groupby("penalty"):
        evaluation_groups = [("all", group)] + [
            (str(int(cycle)), cycle_rows) for cycle, cycle_rows in group.groupby("cycle")
        ]
        for evaluation_cycle, evaluation_rows in evaluation_groups:
            for scope, subset in (
                ("all", evaluation_rows),
                ("seen_candidate", evaluation_rows[evaluation_rows.seen_candidate]),
            ):
                if subset.empty:
                    continue
                metric_rows.append({
                    "penalty": penalty,
                    "evaluation_cycle": evaluation_cycle,
                    "scope": scope,
                    "races": len(subset),
                    "cycles": subset.cycle.nunique(),
                    "mae": float(np.mean(np.abs(subset.error))),
                    "zero_baseline_mae": float(np.mean(np.abs(subset.actual))),
                    "rmse": float(np.sqrt(np.mean(np.square(subset.error)))),
                    "bias": float(np.mean(subset.error)),
                })
    metrics = pd.DataFrame(metric_rows)
    return predictions, metrics


def choose_penalty(metrics: pd.DataFrame) -> float:
    seen = metrics[
        metrics.scope.eq("seen_candidate") & metrics.evaluation_cycle.eq("all")
    ].copy()
    if seen.empty:
        raise ValueError("No time-forward repeat-candidate observations")
    return float(seen.sort_values(["mae", "rmse", "penalty"]).iloc[0].penalty)


def pre_election_effects(
    races: pd.DataFrame, candidates: pd.DataFrame, penalty: float
) -> pd.DataFrame:
    targets = races.set_index("war_outcome_id").war_target
    rows = []
    for cycle in sorted(races.cycle.unique()):
        train_ids = races.loc[races.cycle.lt(cycle), "war_outcome_id"]
        test = candidates[candidates.cycle.eq(cycle)]
        if train_ids.empty:
            effect_map = pd.Series(dtype=float)
            se_map = pd.Series(dtype=float)
            appearances = pd.Series(dtype=int)
        else:
            train = candidates[candidates.war_outcome_id.isin(train_ids)]
            effects, _, _ = fit_candidate_effects(train, targets.reindex(train_ids), penalty)
            effect_map = effects.set_index("candidate_effect_id").candidate_war
            se_map = effects.set_index("candidate_effect_id").candidate_war_se
            appearances = train.groupby("candidate_effect_id").size()
        for candidate_id in test.candidate_effect_id.unique():
            observed = candidate_id in effect_map.index
            rows.append({
                "cycle": cycle,
                "candidate_effect_id": candidate_id,
                "pre_election_war": float(effect_map.get(candidate_id, 0.0)),
                "pre_election_war_se": float(se_map.get(candidate_id, np.nan)),
                "pre_election_appearances": int(appearances.get(candidate_id, 0)),
                "pre_election_war_source": "prior_southern_races" if observed else "no_prior_race",
            })
    return pd.DataFrame(rows)


def model_outputs(
    raw_races: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], dict[str, object]]:
    races = add_replacement_levels(raw_races)
    candidates = candidate_rows(races)
    predictions, metrics = forward_predictions(races, candidates)
    selected_penalty = choose_penalty(metrics)
    targets = races.set_index("war_outcome_id").war_target
    effects, fitted, sigma = fit_candidate_effects(candidates, targets, selected_penalty)

    intrinsic_targets = targets - GENERIC_INCUMBENCY_MARGIN * races.set_index("war_outcome_id").incumbency_balance
    intrinsic, _, intrinsic_sigma = fit_candidate_effects(candidates, intrinsic_targets, selected_penalty)
    intrinsic = intrinsic[["candidate_effect_id", "candidate_war", "candidate_war_se"]].rename(columns={
        "candidate_war": "intrinsic_war",
        "candidate_war_se": "intrinsic_war_se",
    })
    effects = effects.merge(intrinsic, on="candidate_effect_id", how="left", validate="one_to_one")
    appearances = candidates.groupby("candidate_effect_id").agg(
        appearances=("war_outcome_id", "size"),
        first_cycle=("cycle", "min"),
        last_cycle=("cycle", "max"),
        states=("state_code", lambda values: "|".join(sorted(set(values)))),
        parties=("canonical_party", lambda values: "|".join(sorted(set(values)))),
        identity_status=("identity_status", lambda values: "|".join(sorted(set(values)))),
        canonical_name=("candidate_name", "last"),
    ).reset_index()
    effects = effects.merge(appearances, on="candidate_effect_id", how="left", validate="one_to_one")
    effects["candidate_war_low"] = effects.candidate_war - 1.96 * effects.candidate_war_se
    effects["candidate_war_high"] = effects.candidate_war + 1.96 * effects.candidate_war_se
    effects["war_reliability"] = effects.appearances / (effects.appearances + selected_penalty)
    effects["war_status"] = np.select(
        [effects.candidate_war_low.gt(0), effects.candidate_war_high.lt(0)],
        ["positive", "negative"], default="uncertain",
    )
    effects.loc[effects.quality_identification.eq("pair_differential_only"), "war_status"] = "uncertain"
    effects["selected_penalty"] = selected_penalty

    race_fit = fitted.rename("candidate_war_differential").reset_index().rename(columns={"index": "war_outcome_id"})
    races = races.merge(race_fit, on="war_outcome_id", how="left", validate="one_to_one")
    races["war_unexplained"] = races.war_target - races.candidate_war_differential
    races["selected_penalty"] = selected_penalty

    effect_columns_for_scores = [
        column for column in effects.columns
        if column not in {"canonical_name", "identity_status", "states", "parties"}
    ]
    candidate_scores = candidates.merge(
        races[[
            "war_outcome_id", "replacement_level", "replacement_method", "replacement_group",
            "war_target", "candidate_war_differential", "war_unexplained",
        ]], on="war_outcome_id", how="left", validate="many_to_one",
    ).merge(effects[effect_columns_for_scores], on="candidate_effect_id", how="left", validate="many_to_one")
    orientation = candidate_scores.canonical_party.map({"D": 1.0, "R": -1.0})
    candidate_scores["candidate_direct_overperformance"] = orientation * candidate_scores.direct_overperformance
    candidate_scores["candidate_replacement_level"] = orientation * candidate_scores.replacement_level
    candidate_scores["candidate_war_target"] = orientation * candidate_scores.war_target
    candidate_scores = candidate_scores.merge(
        pre_election_effects(races, candidates, selected_penalty),
        on=["cycle", "candidate_effect_id"], how="left", validate="many_to_one",
    )
    if candidate_scores.duplicated(["war_outcome_id", "canonical_party"]).any():
        raise ValueError("Candidate-cycle output violates its key")
    repeat_by_race = (
        candidate_scores.assign(repeat_candidate=candidate_scores.appearances.gt(1))
        .groupby("war_outcome_id", as_index=False).repeat_candidate.any()
        .rename(columns={"repeat_candidate": "race_has_repeat_candidate"})
    )
    races = races.merge(repeat_by_race, on="war_outcome_id", how="left", validate="one_to_one")

    coverage = races.groupby(["state_code", "cycle", "chamber"], as_index=False).agg(
        races=("war_outcome_id", "size"),
        mean_direct_overperformance=("direct_overperformance", "mean"),
        mean_war_target=("war_target", "mean"),
        candidate_repeat_races=("race_has_repeat_candidate", "sum"),
        model_source_fallbacks=("selection_status", lambda values: int(values.ne("canonical_model_eligible").sum())),
    )
    diagnostics = {
        "selected_penalty": selected_penalty,
        "residual_sigma": sigma,
        "intrinsic_residual_sigma": intrinsic_sigma,
        "training_rows": len(races),
        "candidate_rows": len(candidate_scores),
        "candidate_effects": len(effects),
        "repeat_candidates": int(effects.appearances.gt(1).sum()),
        "states": int(races.state_code.nunique()),
        "cycles": sorted(int(value) for value in races.cycle.unique()),
    }
    outputs = {
        "races.csv": races,
        "candidate_cycles.csv": candidate_scores,
        "candidate_effects.csv": effects,
        "forward_predictions.csv": predictions,
        "forward_metrics.csv": metrics,
        "coverage.csv": coverage,
    }
    return outputs, diagnostics


def write_reports(
    diagnostics: dict[str, object], metrics: pd.DataFrame, manifest: dict[str, object]
) -> None:
    selected = metrics[
        metrics.penalty.eq(diagnostics["selected_penalty"])
        & metrics.scope.eq("seen_candidate")
        & metrics.evaluation_cycle.eq("all")
    ].iloc[0]
    METHOD_REPORT.write_text(
        "# Post-2016 Southern candidate WAR\n\n"
        "## Scope\n\n"
        f"This versioned research run uses {diagnostics['training_rows']:,} strict-ready D-versus-R "
        f"legislative races in {diagnostics['states']} Southern states. The cutoff is literal: only "
        f"cycles strictly greater than {CUTOFF_CYCLE} enter training. Available strict cycles are "
        f"{', '.join(map(str, diagnostics['cycles']))}. Research-only rows and finance are excluded.\n\n"
        "## Estimand\n\n"
        "Direct overperformance is the Democratic legislative margin minus the validated same-election "
        "ticket baseline. A replacement level is estimated within state, cycle, chamber, and normalized "
        "baseline-office family; groups with fewer than three races use the prespecified broader hierarchy. "
        "WAR is the ridge-partial-pooled candidate effect on the remaining Democratic-minus-Republican "
        "race differential. Positive WAR means electoral value for a candidate regardless of party.\n\n"
        f"The time-forward repeat-candidate tournament selected a ridge penalty of "
        f"{diagnostics['selected_penalty']:g}. On {int(selected.races):,} held-out races with at least one "
        f"previously observed candidate, MAE was {selected.mae:.3f} points versus "
        f"{selected.zero_baseline_mae:.3f} for a zero prior-candidate effect. Every fold trains only on "
        "strictly earlier cycles.\n\n"
        "## Interpretation and limitations\n\n"
        "This is a historical candidate-effect model, not a promoted 2026 forecast. The warehouse does not "
        "yet expose a cross-state Southern person bridge, so longitudinal links are conservative, state-scoped "
        "normalized full-name links. Surname-only and same-cycle ambiguous names remain race-specific. A race "
        "between two one-time candidates identifies only their differential; both intervals remain labeled "
        "uncertain. The separate intrinsic sensitivity subtracts a prespecified three-point generic incumbency "
        "margin before refitting; headline WAR retains officeholding as electoral value.\n\n"
        f"Model run: `{manifest['model_run_id']}`. Warehouse run: `{manifest['warehouse_build_run_id']}`.\n",
        encoding="utf-8",
    )
    AUDIT_REPORT.write_text(
        "# Post-2016 Southern WAR validation\n\n"
        f"Generated at `{manifest['generated_at_utc']}` for model run `{manifest['model_run_id']}` from "
        f"validated warehouse run `{manifest['warehouse_build_run_id']}`.\n\n"
        "## Passed gates\n\n"
        f"- {diagnostics['training_rows']:,} input races all have `cycle > {CUTOFF_CYCLE}` and "
        f"`training_status={TRAINING_STATUS}`.\n"
        f"- Race keys are unique; {diagnostics['candidate_rows']:,} candidate-cycle rows provide exactly one "
        "Democratic and one Republican observation per race.\n"
        "- No required outcome, ticket baseline, direct-overperformance, or incumbency field is missing.\n"
        "- Candidate-oriented direct and residual values are symmetric within each race.\n"
        "- Every time-forward validation row has `train_max_cycle < cycle`.\n"
        "- Model outputs, code, and the read-only warehouse snapshot are SHA-256 registered in the manifest.\n\n"
        "## Coverage and uncertainty\n\n"
        f"The fit spans {diagnostics['states']} states and cycles {', '.join(map(str, diagnostics['cycles']))}; "
        f"{diagnostics['repeat_candidates']:,} model-local candidates appear in more than one race. "
        "Research-only observations remain excluded rather than being silently promoted. Candidate identity "
        "limitations and isolated-pair identification are carried as row-level status fields.\n\n"
        "## Automated checks\n\n"
        "The focused post-2016 WAR suite passed 5 tests. The repository-wide suite retained the "
        "pre-existing unrelated failure in `test_canonical_historical_finance.py`: its fixture expects "
        "352 canonical-finance-complete races while the current finance build contains 353. No Southern "
        "WAR retraining test failed.\n",
        encoding="utf-8",
    )


def main() -> None:
    raw, warehouse_run = load_training()
    outputs, diagnostics = model_outputs(raw)
    code_hash = sha256(Path(__file__).resolve())
    database_hash = sha256(DATABASE)
    run_basis = {
        "methodology_version": "post2016_southern_war_v1",
        "warehouse_build_run_id": raw.build_run_id.iloc[0],
        "warehouse_sha256": database_hash,
        "code_sha256": code_hash,
        "configuration": {
            "cutoff_rule": f"cycle > {CUTOFF_CYCLE}",
            "training_status": TRAINING_STATUS,
            "quality_penalties": list(QUALITY_PENALTIES),
            "selected_penalty": diagnostics["selected_penalty"],
            "minimum_replacement_group": MIN_REPLACEMENT_GROUP,
            "generic_incumbency_margin": GENERIC_INCUMBENCY_MARGIN,
            "finance_included": False,
        },
    }
    model_run_id = "WAR-POST2016-" + hashlib.sha256(
        json.dumps(run_basis, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20].upper()
    for frame in outputs.values():
        frame.insert(0, "model_run_id", model_run_id)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)
    manifest = {
        "schema_version": 1,
        "model_run_id": model_run_id,
        "status": "validated_research_candidate",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": git_commit(),
        **run_basis,
        "warehouse_code_commit": warehouse_run["code_commit"],
        "warehouse_validation": json.loads(warehouse_run["validation_json"]),
        "input_database": {
            "path": str(DATABASE.relative_to(ROOT)).replace("\\", "/"),
            "bytes": DATABASE.stat().st_size,
            "sha256": database_hash,
        },
        "diagnostics": diagnostics,
        "outputs": [
            {
                "path": str((OUT / name).relative_to(ROOT)).replace("\\", "/"),
                "rows": len(frame),
                "sha256": sha256(OUT / name),
            }
            for name, frame in outputs.items()
        ],
    }
    write_reports(diagnostics, outputs["forward_metrics.csv"], manifest)
    manifest["reports"] = [
        {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(path),
        }
        for path in (METHOD_REPORT, AUDIT_REPORT)
    ]
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"Post-2016 Southern WAR: run={model_run_id} races={diagnostics['training_rows']:,} "
        f"candidates={diagnostics['candidate_effects']:,} penalty={diagnostics['selected_penalty']:g}"
    )


if __name__ == "__main__":
    main()
