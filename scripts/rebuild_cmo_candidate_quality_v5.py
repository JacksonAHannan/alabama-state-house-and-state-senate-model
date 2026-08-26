"""Build CMO v5: direct ticket overperformance plus candidate WAR.

The headline CMO is observed legislative margin minus a same-cycle ticket
baseline. Wins Above Replacement (WAR) is the public name for the separate,
partial-pooled estimate of the repeatable candidate differential after
cycle/chamber/source replacement levels and strictly predetermined lag
features. The stable internal column remains ``candidate_quality_index`` for
compatibility. Current federal margin is never reused as a lag predictor.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import rebuild_cmo_methodology_v2 as v2

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
REPORT = ROOT / "project_docs" / "model" / "CMO_METHODOLOGY_V5.md"
KEYS = ["cycle", "chamber", "district"]
STRUCTURAL_ALPHAS = (10.0, 30.0, 100.0)
QUALITY_LAMBDAS = (1.0, 3.0, 10.0, 30.0, 100.0)
GENERIC_INCUMBENCY_MARGIN = 3.0


def cqi_normalized_name(value: object) -> str:
    """Normalize display variants, using a literal comma as Last, First evidence."""
    raw = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii").strip()
    if "," in raw:
        last, remainder = raw.split(",", 1)
        raw = f"{remainder.strip()} {last.strip()}"
    raw = re.sub(r"\b(JR|SR|II|III|IV)\b", "", raw.upper())
    return re.sub(r"[^A-Z0-9]+", " ", raw).strip()


def repair_model_identity(candidates: pd.DataFrame) -> pd.DataFrame:
    """Create conservative model-local longitudinal IDs without altering canonical facts."""
    candidates = candidates.copy()
    candidates["normalized_candidate_name"] = candidates.canonical_name.map(cqi_normalized_name)
    surname_only = ~candidates.canonical_name.astype("string").str.strip().str.contains(r"\s", regex=True, na=False)
    simultaneous = (candidates.groupby(["cycle", "normalized_candidate_name"])
                    .size().loc[lambda x: x.gt(1)].reset_index().normalized_candidate_name.unique())
    candidates["identity_collision_split"] = candidates.normalized_candidate_name.isin(simultaneous)
    candidates["candidate_effect_id"] = "ALNAME-" + candidates.normalized_candidate_name.str.replace(" ", "-", regex=False)
    candidates.loc[candidates.identity_collision_split, "candidate_effect_id"] += (
        "-" + candidates.loc[candidates.identity_collision_split, "chamber"].str.upper()
        + "-" + candidates.loc[candidates.identity_collision_split, "district"].astype(str))
    candidates.loc[surname_only, "candidate_effect_id"] = (
        "UNRESOLVED-" + candidates.loc[surname_only, "canonical_candidate_id"].astype(str))
    candidates["identity_status"] = np.select(
        [surname_only, candidates.identity_collision_split],
        ["surname_only_unresolved_race_specific", "same_cycle_name_collision_split"],
        default="normalized_full_name")
    return candidates


def markdown_table(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for column in display.select_dtypes(include=["number"]):
        display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
    header = "| " + " | ".join(display.columns) + " |"
    rule = "| " + " | ".join(["---"] * len(display.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in display.to_numpy()]
    return "\n".join([header, rule, *rows])


def prepare() -> tuple[pd.DataFrame, pd.DataFrame]:
    races, candidates = v2.load_panel()
    candidates = repair_model_identity(candidates)
    data = v2.prepare_features(v2.attach_candidate_history(v2.build_source_aware_baseline(races), candidates))
    data["federal_primary"] = data.federal_available_v2.eq(1) & data.federal_index_margin.notna()
    data["selected_ticket_margin"] = data.federal_index_margin.where(
        data.federal_primary, data.baseline_state_margin_v2)
    data["selected_ticket_source"] = np.where(
        data.federal_primary, "same_cycle_federal", "same_cycle_state_fallback")
    data["direct_cmo"] = data.legislative_dem_margin - data.selected_ticket_margin
    data["state_ticket_cmo"] = data.legislative_dem_margin - data.baseline_state_margin_v2
    data["federal_ticket_cmo"] = data.legislative_dem_margin - data.federal_index_margin
    data["presidential_ticket_cmo"] = data.legislative_dem_margin - data.prior_pres_dem_margin_v2
    alternatives = data[["state_ticket_cmo", "federal_ticket_cmo", "presidential_ticket_cmo"]]
    data["direct_baseline_low"] = alternatives.min(axis=1, skipna=True)
    data["direct_baseline_high"] = alternatives.max(axis=1, skipna=True)

    data["predetermined_presidential_swing"] = np.select(
        [data.cycle.eq(2014), data.cycle.eq(2018), data.cycle.eq(2022)],
        [data.pres_2012_dem_margin - data.pres_2008_dem_margin,
         data.pres_2016_dem_margin - data.pres_2012_dem_margin,
         data.pres_2020_dem_margin - data.pres_2016_dem_margin],
        default=np.nan)
    # This is deliberately prior presidential context only.  Do not construct
    # federal_t - presidential_t-1, because federal_t is already the baseline
    # inside direct_cmo and would mechanically enter both sides with opposite signs.
    data["prior_presidential_margin"] = data.prior_pres_dem_margin_v2
    data["replacement_group"] = (
        data.cycle.astype(str) + "_" + data.chamber + "_" + data.selected_ticket_source)
    fit = data.headline_fit_eligible.fillna(False)
    replacement = data.loc[fit].groupby("replacement_group").direct_cmo.mean()
    data["replacement_level"] = data.replacement_group.map(replacement)
    # Sparse source groups fall back to cycle/chamber and then the overall mean.
    cycle_chamber = data.loc[fit].groupby(["cycle", "chamber"]).direct_cmo.mean()
    missing = data.replacement_level.isna()
    data.loc[missing, "replacement_level"] = [
        cycle_chamber.get((r.cycle, r.chamber), data.loc[fit, "direct_cmo"].mean())
        for r in data.loc[missing].itertuples()]
    data["cycle_centered_cmo"] = data.direct_cmo - data.replacement_level
    return data, candidates


FEATURE_SETS = {
    "cycle_centered": [],
    "predetermined_lag": ["prior_presidential_margin", "predetermined_presidential_swing"],
    "lag_demographics": ["prior_presidential_margin", "predetermined_presidential_swing",
                         "nonwhite_share", "white_college_share"],
}


def structural_predictions(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = data.headline_fit_eligible.fillna(False)
    tournament, predictions = [], {"cycle_centered": np.zeros(len(data))}
    for specification, features in FEATURE_SETS.items():
        if not features:
            continue
        for alpha in STRUCTURAL_ALPHAS:
            pred = np.full(len(data), np.nan)
            fold_rows = []
            for cycle in sorted(data.loc[eligible, "cycle"].unique()):
                train = eligible & data.cycle.ne(cycle)
                test = eligible & data.cycle.eq(cycle)
                model = Pipeline([
                    ("impute", SimpleImputer(strategy="median")),
                    ("scale", StandardScaler()),
                    ("ridge", Ridge(alpha=alpha)),
                ])
                model.fit(data.loc[train, features], data.loc[train, "cycle_centered_cmo"])
                pred[test] = model.predict(data.loc[test, features])
                fold_rows.append(mean_absolute_error(data.loc[test, "cycle_centered_cmo"], pred[test]))
            scored = data.loc[eligible, ["candidate_stub" if "candidate_stub" in data else "district"]].copy()
            tournament.append({"stage": "structural", "specification": specification,
                               "parameter": alpha, "races": int(eligible.sum()),
                               "mean_cycle_mae": float(np.mean(fold_rows)),
                               "oof_mae": mean_absolute_error(data.loc[eligible, "cycle_centered_cmo"], pred[eligible]),
                               "oof_rmse": mean_squared_error(data.loc[eligible, "cycle_centered_cmo"], pred[eligible]) ** .5})
            key = f"{specification}_alpha_{alpha:g}"
            predictions[key] = pred
    table = pd.DataFrame(tournament)
    # Structural MAE is a screening criterion. Candidate persistence below is
    # the selection criterion for the published quality residual.
    return table, pd.DataFrame(predictions, index=data.index)


def attach_candidate_rows(data: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    cols = KEYS + ["direct_cmo", "state_ticket_cmo", "federal_ticket_cmo",
                   "presidential_ticket_cmo", "replacement_level", "cycle_centered_cmo",
                   "direct_baseline_low", "direct_baseline_high",
                   "selected_ticket_margin", "selected_ticket_source", "federal_primary",
                   "prior_presidential_margin", "predetermined_presidential_swing",
                   "nonwhite_share", "white_college_share", "contest_tier",
                   "headline_fit_eligible", "dem_incumbent_i", "rep_incumbent_i"]
    rows = candidates.merge(data[cols], on=KEYS, how="inner", validate="many_to_one")
    rows = rows[rows.canonical_party.isin(["D", "R"])].copy()
    counts = rows.groupby(KEYS).canonical_party.nunique()
    valid = counts[counts.eq(2)].index
    rows = rows.set_index(KEYS).loc[valid].reset_index()
    orientation = rows.canonical_party.map({"D": 1.0, "R": -1.0})
    for column in ["direct_cmo", "state_ticket_cmo", "federal_ticket_cmo",
                   "presidential_ticket_cmo", "cycle_centered_cmo"]:
        rows[f"candidate_{column}"] = rows[column] * orientation
    rows["candidate_direct_baseline_low"] = np.where(
        orientation.eq(1), rows.direct_baseline_low, -rows.direct_baseline_high)
    rows["candidate_direct_baseline_high"] = np.where(
        orientation.eq(1), rows.direct_baseline_high, -rows.direct_baseline_low)
    return rows


def repeat_validity(rows: pd.DataFrame, race_scores: pd.DataFrame) -> pd.DataFrame:
    candidate = rows.merge(race_scores, on=KEYS, how="left", validate="many_to_one")
    orientation = candidate.canonical_party.map({"D": 1.0, "R": -1.0})
    variants = {
        "direct_cmo": candidate.direct_cmo * orientation,
        "cycle_centered": candidate.cycle_centered_cmo * orientation,
    }
    for column in race_scores:
        if column.startswith("structural_residual_"):
            variants[column] = candidate[column] * orientation
    records = []
    stable = ~candidate.candidate_effect_id.str.startswith("UNRESOLVED-")
    for name, values in variants.items():
        frame = candidate.loc[stable, ["candidate_effect_id", "cycle"]].copy()
        frame["score"] = values[stable]
        pairs = []
        for _, group in frame.sort_values("cycle").groupby("candidate_effect_id"):
            if len(group) > 1:
                pairs.extend(zip(group.score.iloc[:-1], group.score.iloc[1:]))
        pairs = [(prior, future) for prior, future in pairs if np.isfinite(prior) and np.isfinite(future)]
        if len(pairs) < 3:
            continue
        prior, future = map(np.asarray, zip(*pairs))
        pearson = stats.pearsonr(prior, future)
        spearman = stats.spearmanr(prior, future)
        records.append({"stage": "construct", "specification": name, "parameter": np.nan,
                        "pairs": len(pairs), "pearson": pearson.statistic,
                        "pearson_p": pearson.pvalue, "spearman": spearman.statistic,
                        "spearman_p": spearman.pvalue,
                        "future_mae_using_prior": mean_absolute_error(future, prior),
                        "future_mae_zero": mean_absolute_error(future, np.zeros(len(future)))})
    return pd.DataFrame(records)


def quality_design(rows: pd.DataFrame, race_residual: pd.Series):
    races = rows[KEYS].drop_duplicates().reset_index(drop=True)
    parties = rows.pivot(index=KEYS, columns="canonical_party", values="candidate_effect_id")
    parties = parties.loc[pd.MultiIndex.from_frame(races)]
    ids = sorted(set(parties.D) | set(parties.R))
    lookup = {candidate: index for index, candidate in enumerate(ids)}
    x = np.zeros((len(races), len(ids)), dtype=float)
    for index, (democrat, republican) in enumerate(zip(parties.D, parties.R)):
        x[index, lookup[democrat]] = 1.0
        x[index, lookup[republican]] = -1.0
    y = race_residual.reindex(pd.MultiIndex.from_frame(races)).to_numpy(float)
    return races, parties, ids, lookup, x, y


def fit_quality(x: np.ndarray, y: np.ndarray, penalty: float):
    precision = x.T @ x + penalty * np.eye(x.shape[1])
    inverse = np.linalg.inv(precision)
    effect = inverse @ x.T @ y
    residual = y - x @ effect
    sigma = np.sqrt(np.sum(residual ** 2) / max(1, len(y) - np.trace(x @ inverse @ x.T)))
    se = sigma * np.sqrt(np.diag(inverse))
    return effect, se, residual


def forward_quality_tournament(rows: pd.DataFrame, race_residual: pd.Series) -> pd.DataFrame:
    records = []
    all_cycles = sorted(rows.cycle.unique())
    for penalty in QUALITY_LAMBDAS:
        predictions, outcomes, cycles, seen_flags = [], [], [], []
        for test_cycle in all_cycles[1:]:
            train_rows = rows[rows.cycle.lt(test_cycle)]
            test_rows = rows[rows.cycle.eq(test_cycle)]
            if train_rows.empty or test_rows.empty:
                continue
            train_keys = pd.MultiIndex.from_frame(train_rows[KEYS].drop_duplicates())
            train_residual = race_residual.reindex(train_keys)
            train_races, _, ids, lookup, x, y = quality_design(train_rows, train_residual)
            effects, _, _ = fit_quality(x, y, penalty)
            test_party = test_rows.pivot(index=KEYS, columns="canonical_party", values="candidate_effect_id")
            for key, pair in test_party.iterrows():
                dem_seen, rep_seen = pair.D in lookup, pair.R in lookup
                prediction = (effects[lookup[pair.D]] if dem_seen else 0.0) - (
                    effects[lookup[pair.R]] if rep_seen else 0.0)
                predictions.append(prediction)
                outcomes.append(float(race_residual.loc[key]))
                cycles.append(test_cycle)
                seen_flags.append(dem_seen or rep_seen)
        pred, actual, seen = np.asarray(predictions), np.asarray(outcomes), np.asarray(seen_flags)
        for scope, mask in [("all", np.ones(len(actual), dtype=bool)), ("seen_candidate", seen)]:
            if mask.sum() < 3:
                continue
            pearson = stats.pearsonr(pred[mask], actual[mask]) if np.std(pred[mask]) else None
            records.append({"stage": "quality", "specification": scope, "parameter": penalty,
                            "races": int(mask.sum()), "mae": mean_absolute_error(actual[mask], pred[mask]),
                            "zero_baseline_mae": mean_absolute_error(actual[mask], np.zeros(mask.sum())),
                            "rmse": mean_squared_error(actual[mask], pred[mask]) ** .5,
                            "pearson": pearson.statistic if pearson else np.nan,
                            "pearson_p": pearson.pvalue if pearson else np.nan})
    return pd.DataFrame(records)


def pre_election_quality(rows: pd.DataFrame, race_residual: pd.Series, penalty: float) -> pd.DataFrame:
    records = []
    for cycle in sorted(rows.cycle.unique()):
        train, test = rows[rows.cycle.lt(cycle)], rows[rows.cycle.eq(cycle)]
        if train.empty:
            for candidate in test.candidate_effect_id.unique():
                records.append({"cycle": cycle, "candidate_effect_id": candidate,
                                "pre_election_quality_index": 0.0, "pre_election_quality_se": np.nan,
                                "pre_election_appearances": 0, "pre_election_quality_source": "no_prior_race"})
            continue
        train_keys = pd.MultiIndex.from_frame(train[KEYS].drop_duplicates())
        _, _, ids, lookup, x, y = quality_design(train, race_residual.reindex(train_keys))
        effect, se, residual = fit_quality(x, y, penalty)
        unseen_se = float(np.std(residual, ddof=1) / np.sqrt(penalty)) if len(residual) > 1 else np.nan
        appearances = train.groupby("candidate_effect_id").size()
        for candidate in test.candidate_effect_id.unique():
            observed = candidate in lookup
            records.append({"cycle": cycle, "candidate_effect_id": candidate,
                            "pre_election_quality_index": effect[lookup[candidate]] if observed else 0.0,
                            "pre_election_quality_se": se[lookup[candidate]] if observed else unseen_se,
                            "pre_election_appearances": int(appearances.get(candidate, 0)),
                            "pre_election_quality_source": "prior_legislative_races" if observed else "no_prior_race"})
    return pd.DataFrame(records)


def main() -> None:
    data, candidates = prepare()
    candidate_rows = attach_candidate_rows(data, candidates)
    structural_table, oof = structural_predictions(data)
    race_scores = data[KEYS + ["direct_cmo", "cycle_centered_cmo"]].copy()
    for column in oof:
        if column == "cycle_centered":
            continue
        race_scores[f"structural_residual_{column}"] = data.cycle_centered_cmo - oof[column]
    validity = repeat_validity(candidate_rows, race_scores.drop(columns=["direct_cmo", "cycle_centered_cmo"]))
    eligible_validity = validity[validity.specification.ne("direct_cmo")].copy()
    selected_spec = eligible_validity.sort_values(
        ["spearman", "future_mae_using_prior"], ascending=[False, True]).iloc[0].specification
    if selected_spec == "cycle_centered":
        selected_residual = data.set_index(KEYS).cycle_centered_cmo
        structural_prediction = pd.Series(0.0, index=data.index)
    else:
        suffix = selected_spec.removeprefix("structural_residual_")
        selected_residual = race_scores.set_index(KEYS)[selected_spec]
        structural_prediction = oof[suffix]
    # Fill OOF-only missing predictions by fitting the selected structural form
    # on all eligible races. This affects publication, never OOF selection.
    if selected_spec != "cycle_centered":
        specification, alpha_text = suffix.rsplit("_alpha_", 1)
        features, alpha = FEATURE_SETS[specification], float(alpha_text)
        model = Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("scale", StandardScaler()), ("ridge", Ridge(alpha=alpha))])
        eligible = data.headline_fit_eligible.fillna(False)
        model.fit(data.loc[eligible, features], data.loc[eligible, "cycle_centered_cmo"])
        full_prediction = model.predict(data[features])
        selected_residual = pd.Series(data.cycle_centered_cmo.to_numpy() - full_prediction,
                                      index=pd.MultiIndex.from_frame(data[KEYS]))
        structural_prediction = pd.Series(full_prediction, index=data.index)

    quality_tournament = forward_quality_tournament(candidate_rows, selected_residual)
    seen = quality_tournament[quality_tournament.specification.eq("seen_candidate")]
    selected_penalty = float(seen.sort_values(["mae", "pearson"], ascending=[True, False]).iloc[0].parameter)
    races, parties, ids, lookup, x, y = quality_design(candidate_rows, selected_residual)
    total_effect, total_se, total_residual = fit_quality(x, y, selected_penalty)

    incumbent_advantage = data.set_index(KEYS).dem_incumbent_i - data.set_index(KEYS).rep_incumbent_i
    intrinsic_target = selected_residual - GENERIC_INCUMBENCY_MARGIN * incumbent_advantage.reindex(selected_residual.index)
    _, _, _, _, intrinsic_x, intrinsic_y = quality_design(candidate_rows, intrinsic_target)
    intrinsic_effect, intrinsic_se, _ = fit_quality(intrinsic_x, intrinsic_y, selected_penalty)

    appearances = candidate_rows.groupby("candidate_effect_id").size().reindex(ids).fillna(0).astype(int)
    effects = pd.DataFrame({"candidate_effect_id": ids, "candidate_quality_index": total_effect,
                            "candidate_quality_se": total_se, "intrinsic_quality_index": intrinsic_effect,
                            "intrinsic_quality_se": intrinsic_se, "appearances": appearances.to_numpy()})
    effects["candidate_quality_low"] = effects.candidate_quality_index - 1.96 * effects.candidate_quality_se
    effects["candidate_quality_high"] = effects.candidate_quality_index + 1.96 * effects.candidate_quality_se
    effects["quality_reliability"] = effects.appearances / (effects.appearances + selected_penalty)
    effects["quality_status"] = np.select(
        [effects.candidate_quality_low.gt(0), effects.candidate_quality_high.lt(0)],
        ["positive", "negative"], default="uncertain")
    # A disconnected one-race component identifies only q_D - q_R. Ridge's
    # equal split is a regularization convention, not candidate-level evidence.
    pair_frame = parties.reset_index()
    isolated_ids = set()
    occurrence = pd.concat([pair_frame.D, pair_frame.R]).value_counts()
    for pair in pair_frame.itertuples():
        if occurrence[pair.D] == 1 and occurrence[pair.R] == 1:
            isolated_ids.update([pair.D, pair.R])
    effects["quality_identification"] = np.where(
        effects.candidate_effect_id.isin(isolated_ids), "pair_differential_only", "candidate_network")
    effects.loc[effects.quality_identification.eq("pair_differential_only"), "quality_status"] = "uncertain"

    scored = candidate_rows.merge(effects, on="candidate_effect_id", how="left", validate="many_to_one")
    scored = scored.merge(pre_election_quality(candidate_rows, selected_residual, selected_penalty),
                          on=["cycle", "candidate_effect_id"], how="left", validate="many_to_one")
    scored["candidate_replacement_level"] = scored.replacement_level * scored.canonical_party.map({"D": 1, "R": -1})
    adjustment = data[KEYS].copy()
    adjustment["candidate_structural_adjustment"] = structural_prediction.to_numpy()
    scored = scored.merge(adjustment, on=KEYS, how="left", validate="many_to_one")
    race_output = data[KEYS + ["dem_votes", "rep_votes", "two_party_votes", "legislative_dem_margin",
        "selected_ticket_margin", "selected_ticket_source", "direct_cmo", "state_ticket_cmo",
        "federal_ticket_cmo", "presidential_ticket_cmo", "replacement_level", "cycle_centered_cmo",
        "direct_baseline_low", "direct_baseline_high",
        "prior_presidential_margin", "predetermined_presidential_swing", "federal_primary",
        "contest_tier"]].copy()
    race_output["selected_structural_specification"] = selected_spec
    race_output["selected_quality_penalty"] = selected_penalty
    race_output["structural_adjustment"] = structural_prediction.to_numpy()
    race_output["quality_target_residual"] = [selected_residual.loc[tuple(row)] for row in race_output[KEYS].to_numpy()]
    race_output["candidate_quality_differential"] = x @ total_effect
    race_output["candidate_quality_unexplained"] = total_residual

    tournament = pd.concat([structural_table, validity, quality_tournament], ignore_index=True, sort=False)
    mike = scored[scored.canonical_name.str.contains("MIKE CURTIS", case=False, na=False)]
    named_case_ids = set(scored.loc[
        scored.normalized_candidate_name.str.match(r"MIKE CURTIS|.*MORROW$|BARBARA BIGSBY BOYD", na=False),
        "candidate_effect_id"])
    named_cases = scored[scored.candidate_effect_id.isin(named_case_ids)]
    cases = named_cases[["cycle", "chamber", "district", "canonical_name", "normalized_candidate_name", "canonical_party",
                         "candidate_direct_cmo", "candidate_cycle_centered_cmo",
                         "candidate_quality_index", "candidate_quality_low", "candidate_quality_high",
                         "intrinsic_quality_index", "quality_status", "quality_identification", "appearances"]].copy()
    transitions = (scored.sort_values("cycle").groupby("candidate_effect_id")
                   .filter(lambda g: len(g) > 1)
                   .groupby(["canonical_party", "incumbent"], as_index=False)
                   .agg(candidate_cycles=("canonical_candidate_id", "size"),
                        mean_direct_cmo=("candidate_direct_cmo", "mean"),
                        mean_quality=("candidate_quality_index", "mean")))
    symmetry = (effects.merge(scored[["candidate_effect_id", "canonical_party"]].drop_duplicates(),
                              on="candidate_effect_id", how="left")
                .groupby("canonical_party", as_index=False)
                .agg(candidates=("candidate_effect_id", "size"), mean_quality=("candidate_quality_index", "mean"),
                     median_quality=("candidate_quality_index", "median"), mean_se=("candidate_quality_se", "mean"),
                     positive=("quality_status", lambda x: int((x == "positive").sum())),
                     negative=("quality_status", lambda x: int((x == "negative").sum()))))

    outputs = {
        "cmo_v5_races.csv": race_output, "cmo_v5_candidates.csv": scored,
        "cmo_v5_candidate_effects.csv": effects, "cmo_v5_model_tournament.csv": tournament,
        "cmo_v5_case_studies.csv": cases, "cmo_v5_incumbency_transitions.csv": transitions,
        "cmo_v5_party_symmetry.csv": symmetry,
    }
    for name, frame in outputs.items():
        frame.to_csv(WAR / name, index=False)
    manifest = []
    for name, path in [("canonical_cmo_features.csv", v2.ELECTIONS / "canonical_cmo_features.csv"),
                       ("canonical_cmo_candidates.csv", v2.ELECTIONS / "canonical_cmo_candidates.csv"),
                       ("canonical_cmo_district_office_baselines.csv", v2.ELECTIONS / "canonical_cmo_district_office_baselines.csv"),
                       ("historical_federal_district_baselines.csv", v2.ELECTIONS / "historical_federal_district_baselines.csv"),
                       ("rebuild_cmo_methodology_v2.py", Path(v2.__file__)),
                       ("code", Path(__file__))]:
        manifest.append({"record_type": "code" if name == "code" else "input", "name": name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest += [{"record_type": "config", "name": "selected_structural_specification", "value": selected_spec},
                 {"record_type": "config", "name": "selected_quality_penalty", "value": str(selected_penalty)},
                 {"record_type": "config", "name": "generic_incumbency_margin", "value": str(GENERIC_INCUMBENCY_MARGIN)}]
    for name in outputs:
        manifest.append({"record_type": "output", "name": name,
                         "sha256": hashlib.sha256((WAR / name).read_bytes()).hexdigest()})
    pd.DataFrame(manifest).to_csv(WAR / "cmo_v5_provenance.csv", index=False)

    REPORT.write_text(
        "# CMO methodology v5: observed overperformance and candidate WAR\n\n"
        "## Two estimands\n\n"
        "**Direct CMO** is the candidate-oriented legislative margin minus the selected same-cycle "
        "ticket margin. It is observed overperformance and is never residualized for incumbency, "
        "fundraising, demographics, or candidate history.\n\n"
        "**Wins Above Replacement (WAR)** is the public name for the partial-pooled candidate effect from the direct gap "
        "after cycle/chamber/source replacement levels and the selected predetermined structural "
        f"specification (`{selected_spec}`). The candidate ridge penalty is {selected_penalty:g}. "
        "The internal `candidate_quality_index` field is retained as a stable compatibility column; "
        "it does not denote a second public measure.\n\n"
        "## Downballot lag\n\nCurrent same-cycle federal margin appears only in the ticket baseline. "
        "Lag features use prior presidential margins and presidential changes completed before the "
        "legislative election. The former `federal_t - presidential_t-1` predictor is prohibited because "
        "it algebraically reused the baseline inside the outcome.\n\n"
        "## Incumbency\n\nTotal WAR retains officeholding as part of electoral value. An intrinsic "
        f"sensitivity subtracts a prespecified {GENERIC_INCUMBENCY_MARGIN:g}-point generic officeholding "
        "effect before estimating candidate effects. Fundraising is not subtracted from either score.\n\n"
        "## Identity and isolated races\n\nLiteral `Last, First` source names are reordered before model-local "
        "longitudinal linkage; surname-only records remain race-specific. A disconnected race containing "
        "two one-time candidates identifies only their differential. Both candidates are marked "
        "`pair_differential_only` and `uncertain` rather than receiving directional quality labels.\n\n"
        "## Mike Curtis audit\n\n" + markdown_table(mike[["cycle", "chamber", "district", "candidate_direct_cmo",
        "candidate_quality_index", "candidate_quality_low", "candidate_quality_high", "quality_status"]]) +
        "\n\n## Interpretation\n\nDirect CMO describes a candidate-cycle. CQI estimates a repeatable candidate "
        "component but cannot uniquely distinguish candidate strength from opponent weakness in a singleton "
        "race. Intervals and reliability are mandatory; `uncertain` is not a neutral-quality finding.\n",
        encoding="utf-8")
    print(f"races={len(race_output)} candidates={len(scored)} effects={len(effects)} "
          f"structural={selected_spec} penalty={selected_penalty:g}")


if __name__ == "__main__":
    main()
