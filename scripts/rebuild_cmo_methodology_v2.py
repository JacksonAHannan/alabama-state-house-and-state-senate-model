"""Build the revised, versioned Alabama CMO methodology.

The headline context CMO deliberately excludes candidate-derived variables.
Incumbency, finance, and candidate history enter only the separately named
predictive expected-performance model.  Existing public outputs are untouched.
"""
from __future__ import annotations

import json
import hashlib
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.stats import pearsonr, spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
ELECTIONS = ROOT / "data" / "processed" / "elections"
WAR = ROOT / "data" / "processed" / "war"
PREFIX = WAR / "cmo_v2_"
SEED = 20260822
KEYS = ["cycle", "chamber", "district"]
CORE_NUMERIC = [
    "prior_pres_dem_margin_v2", "prior_pres_available_v2", "nonwhite_share",
    "white_college_share", "demographics_available_v2", "chamber_house",
    "state_federal_gap", "federal_available_v2", "baseline_fallback_share",
]
PREDICTIVE_EXTRA = [
    "dem_incumbent_i", "rep_incumbent_i", "open_seat_i",
    "log_fundraising_ratio_d_to_r", "ftm_finance_complete_i",
    "log_spending_ratio_d_to_r", "finance_complete_i",
    "dem_prior_overperformance", "rep_prior_overperformance",
    "dem_prior_winner", "rep_prior_winner",
]


def binary(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    text = series.astype("string").str.lower().map({"true": 1, "false": 0, "yes": 1, "no": 0})
    return numeric.fillna(text).fillna(0).astype(int)


def normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\b(JR|SR|II|III|IV)\b", "", text.upper())
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def load_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    races = pd.read_csv(ELECTIONS / "canonical_cmo_features.csv", low_memory=False)
    races = races[binary(races.war_eligible).eq(1) & binary(races.model_eligible).eq(1)].copy()
    races["district"] = pd.to_numeric(races.district, errors="raise").astype(int)
    candidates = pd.read_csv(ELECTIONS / "canonical_cmo_candidates.csv", low_memory=False)
    candidates = candidates[candidates.canonical_party.isin(["D", "R"])].copy()
    candidates = candidates.rename(columns={"year": "cycle"})
    candidates["district"] = pd.to_numeric(candidates.district, errors="raise").astype(int)
    # Historical person_id values may be surname buckets (for example SMITH),
    # so they are evidence rather than a safe longitudinal key. Full normalized
    # names are the default. A name observed in multiple races in one cycle is
    # conservatively split by chamber and district in every cycle.
    candidates["normalized_candidate_name"] = candidates.canonical_name.map(normalized_name)
    surname_only = ~candidates.canonical_name.astype("string").str.strip().str.contains(r"\s", regex=True, na=False)
    simultaneous = (candidates.groupby(["cycle", "normalized_candidate_name"])
                    .size().loc[lambda x: x.gt(1)].reset_index().normalized_candidate_name.unique())
    candidates["identity_collision_split"] = candidates.normalized_candidate_name.isin(simultaneous)
    candidates["candidate_effect_id"] = "ALNAME-" + candidates.normalized_candidate_name.str.replace(" ", "-", regex=False)
    candidates.loc[candidates.identity_collision_split, "candidate_effect_id"] += (
        "-" + candidates.loc[candidates.identity_collision_split, "chamber"].str.upper()
        + "-" + candidates.loc[candidates.identity_collision_split, "district"].astype(str))
    # A surname alone is not identity evidence, even if that surname appears
    # only once in a particular cycle. Keep it race-specific and explicitly
    # unresolved until a manual identity crosswalk supports a longitudinal join.
    candidates.loc[surname_only, "candidate_effect_id"] = (
        "UNRESOLVED-" + candidates.loc[surname_only, "canonical_candidate_id"].astype(str))
    candidates["identity_status"] = np.select(
        [surname_only, candidates.identity_collision_split],
        ["surname_only_unresolved_race_specific", "same_cycle_name_collision_split"],
        default="normalized_full_name")
    return races.sort_values(KEYS).reset_index(drop=True), candidates


def prior_presidential(data: pd.DataFrame) -> pd.Series:
    values = np.select(
        [data.cycle.eq(2010), data.cycle.eq(2014), data.cycle.eq(2018), data.cycle.eq(2022)],
        [data.pres_2008_dem_margin, data.pres_2012_dem_margin,
         data.pres_2016_dem_margin, data.pres_2020_dem_margin],
        default=np.nan,
    )
    historical = pd.to_numeric(data.get("prior_pres_dem_margin"), errors="coerce")
    pres_1992 = pd.to_numeric(data.get("pres_1992_dem_margin"), errors="coerce")
    return pd.Series(values, index=data.index).fillna(historical).fillna(pres_1992)


def build_source_aware_baseline(data: pd.DataFrame) -> pd.DataFrame:
    offices = pd.read_csv(ELECTIONS / "canonical_cmo_district_office_baselines.csv")
    for column in ("D", "R"):
        offices[column] = pd.to_numeric(offices[column], errors="coerce")
    # Aggregate votes rather than giving a low-turnout office the same weight as
    # a high-turnout office. This is a prespecified measurement rule.
    state = (offices.groupby(KEYS, as_index=False)
             .agg(state_dem_votes=("D", "sum"), state_rep_votes=("R", "sum"),
                  statewide_offices=("office", "nunique"),
                  office_fallback_share=("baseline_fallback_share", "max")))
    denom = state.state_dem_votes + state.state_rep_votes
    state["state_ticket_margin_weighted"] = 200 * state.state_dem_votes / denom - 100
    federal = pd.read_csv(ELECTIONS / "historical_federal_district_baselines.csv")
    keep = KEYS + ["federal_index_margin", "federal_contested_coverage", "federal_components"]
    out = data.merge(state, on=KEYS, how="left", validate="one_to_one").merge(
        federal[keep], on=KEYS, how="left", validate="one_to_one")
    out["prior_pres_dem_margin_v2"] = prior_presidential(out)
    out["federal_available_v2"] = (
        out.federal_index_margin.notna() & out.federal_contested_coverage.ge(.5)).astype(int)
    # A 30% federal component is restricted to the post-2016 era, where the
    # existing source-frozen comparison supports it. Earlier cycles remain on
    # the state ticket. Prior presidential margin is a fallback, not an extra
    # double-counted component.
    out["federal_weight_v2"] = np.where(
        out.cycle.ge(2018) & out.federal_available_v2.eq(1), .30, 0.0)
    state_margin = out.state_ticket_margin_weighted.fillna(out.statewide_index_margin)
    out["baseline_state_margin_v2"] = state_margin
    out["baseline_ensemble_margin"] = (
        (1 - out.federal_weight_v2) * state_margin
        + out.federal_weight_v2 * out.federal_index_margin.fillna(state_margin))
    out["baseline_ensemble_margin"] = out.baseline_ensemble_margin.fillna(out.prior_pres_dem_margin_v2)
    out["baseline_source_v2"] = np.select(
        [out.federal_weight_v2.gt(0), state_margin.notna()],
        ["state_ticket_70_federal_30", "state_ticket_vote_weighted"],
        default="prior_presidential_fallback")
    out["state_federal_gap"] = out.federal_index_margin - state_margin
    out.loc[out.federal_available_v2.eq(0), "state_federal_gap"] = 0
    out["raw_ticket_overperformance"] = out.legislative_dem_margin - out.baseline_ensemble_margin
    return out


def attach_candidate_history(data: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    race_values = data[KEYS + ["raw_ticket_overperformance"]]
    c = candidates.merge(race_values, on=KEYS, how="inner", validate="many_to_one")
    c["party_overperformance"] = c.raw_ticket_overperformance * c.canonical_party.map({"D": 1, "R": -1})
    c["winner_i"] = binary(c.winner)
    c = c.sort_values(["candidate_effect_id", "cycle", "canonical_votes"])
    grouped = c.groupby("candidate_effect_id", sort=False)
    c["prior_overperformance"] = grouped.party_overperformance.shift(1)
    c["prior_cycle"] = grouped.cycle.shift(1)
    c["prior_winner"] = grouped.winner_i.shift(1)
    c["prior_overperformance"] = c.prior_overperformance.where(c.prior_cycle.eq(c.cycle - 4))
    c["prior_winner"] = c.prior_winner.where(c.prior_cycle.eq(c.cycle - 4))
    wide = []
    for party, prefix in (("D", "dem"), ("R", "rep")):
        p = c[c.canonical_party.eq(party)][KEYS + ["prior_overperformance", "prior_winner"]].copy()
        p = p.drop_duplicates(KEYS, keep="last").rename(columns={
            "prior_overperformance": f"{prefix}_prior_overperformance",
            "prior_winner": f"{prefix}_prior_winner"})
        wide.append(p)
    out = data.merge(wide[0], on=KEYS, how="left", validate="one_to_one").merge(
        wide[1], on=KEYS, how="left", validate="one_to_one")
    return out


def prepare_features(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    out["chamber_house"] = out.chamber.eq("house").astype(int)
    out["prior_pres_available_v2"] = out.prior_pres_dem_margin_v2.notna().astype(int)
    out["demographics_available_v2"] = out[["nonwhite_share", "white_college_share"]].notna().all(axis=1).astype(int)
    out["dem_incumbent_i"] = binary(out.dem_incumbent)
    out["rep_incumbent_i"] = binary(out.rep_incumbent)
    conflict = out.dem_incumbent_i.eq(1) & out.rep_incumbent_i.eq(1)
    out.loc[conflict, ["dem_incumbent_i", "rep_incumbent_i"]] = 0
    out["open_seat_i"] = ((out.dem_incumbent_i + out.rep_incumbent_i).eq(0)).astype(int)
    out["ftm_finance_complete_i"] = binary(out.ftm_finance_complete)
    out["finance_complete_i"] = binary(out.finance_complete)
    for column in ("dem_prior_overperformance", "rep_prior_overperformance",
                   "dem_prior_winner", "rep_prior_winner"):
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0)
    losing_share = np.minimum(out.dem_votes, out.rep_votes) / (out.dem_votes + out.rep_votes)
    out["losing_party_vote_share"] = losing_share
    out["contest_tier"] = np.select(
        [losing_share.ge(.10), losing_share.ge(.05)],
        ["meaningful", "marginal"], default="nominal")
    out["headline_fit_eligible"] = losing_share.ge(.05)
    return out


def model(kind: str, numeric: list[str], alpha: float = 20.0) -> Pipeline:
    prep = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)),
                           ("scale", StandardScaler())]), numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), ["chamber"]),
    ])
    estimator = HuberRegressor(alpha=.001, epsilon=1.5, max_iter=2000) if kind == "huber" else Ridge(alpha=alpha)
    return Pipeline([("prep", prep), ("model", estimator)])


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, numeric: list[str], kind: str,
                alpha: float = 20.0, logit_target: bool = False) -> np.ndarray:
    train = train[train.headline_fit_eligible].copy()
    features = numeric + ["chamber"]
    if logit_target:
        actual_share = ((train.legislative_dem_margin + 100) / 200).clip(.0025, .9975)
        base_share = ((train.baseline_ensemble_margin + 100) / 200).clip(.0025, .9975)
        target = logit(actual_share) - logit(base_share)
    else:
        target = train.raw_ticket_overperformance
    fitted = model(kind, numeric, alpha)
    fitted.fit(train[features], target)
    adjustment = fitted.predict(test[features])
    if logit_target:
        base_share = ((test.baseline_ensemble_margin + 100) / 200).clip(.0025, .9975)
        return 200 * expit(logit(base_share) + adjustment) - 100
    # Linear models can extrapolate beyond a possible vote margin when a held-
    # out era contains a feature combination absent from training. Bound the
    # adjustment using training-only residual quantiles, then enforce the
    # logical two-party margin range. Raw observed overperformance is uncapped.
    lower, upper = np.quantile(np.asarray(target), [.025, .975])
    adjustment = np.clip(adjustment, lower, upper)
    return np.clip(test.baseline_ensemble_margin.to_numpy() + adjustment, -99.5, 99.5)


def cycle_crossfit(data: pd.DataFrame, numeric: list[str], kind: str = "ridge",
                   alpha: float = 20.0, logit_target: bool = False) -> np.ndarray:
    result = np.full(len(data), np.nan)
    for cycle in sorted(data.cycle.unique()):
        test_mask = data.cycle.eq(cycle)
        result[test_mask] = fit_predict(data[~test_mask], data[test_mask], numeric, kind, alpha, logit_target)
    return result


def nested_forward(data: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    result = np.full(len(data), np.nan)
    choices = []
    candidates = [
        ("baseline", None, None, False), ("ridge_a3", "ridge", 3.0, False),
        ("ridge_a20", "ridge", 20.0, False), ("ridge_a100", "ridge", 100.0, False),
        ("huber", "huber", 20.0, False), ("logit_ridge", "ridge", 20.0, True),
    ]
    cycles = sorted(data.cycle.unique())
    for position, cycle in enumerate(cycles):
        test_mask = data.cycle.eq(cycle)
        prior = data[data.cycle.lt(cycle)]
        if position < 2:
            selected = candidates[0]
            reason = "fewer_than_two_prior_cycles"
        else:
            losses: dict[str, float] = {}
            inner_cycles = sorted(prior.cycle.unique())[1:]
            for name, kind, alpha, is_logit in candidates:
                fold_errors = []
                for inner_cycle in inner_cycles:
                    inner_train = prior[prior.cycle.lt(inner_cycle)]
                    inner_test = prior[prior.cycle.eq(inner_cycle)]
                    if kind is None:
                        pred = inner_test.baseline_ensemble_margin.to_numpy()
                    else:
                        pred = fit_predict(inner_train, inner_test, CORE_NUMERIC, kind, alpha, is_logit)
                    fold_errors.append(mean_absolute_error(inner_test.legislative_dem_margin, pred))
                losses[name] = float(np.mean(fold_errors))
            selected = next(item for item in candidates if item[0] == min(losses, key=losses.get))
            reason = json.dumps(losses, sort_keys=True)
        name, kind, alpha, is_logit = selected
        if kind is None or prior.empty:
            prediction = data.loc[test_mask, "baseline_ensemble_margin"].to_numpy()
        else:
            prediction = fit_predict(prior, data[test_mask], CORE_NUMERIC, kind, alpha, is_logit)
        result[test_mask] = prediction
        choices.append({"test_cycle": cycle, "selected_specification": name,
                        "training_cycles": "+".join(map(str, sorted(prior.cycle.unique()))),
                        "selection_evidence": reason})
    return result, pd.DataFrame(choices)


def crossed_candidate_effects(races: pd.DataFrame, candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    c = candidates[candidates.canonical_party.isin(["D", "R"])].copy()
    pair = c.pivot_table(index=KEYS, columns="canonical_party", values="candidate_effect_id", aggfunc="first").reset_index()
    pair = pair.dropna(subset=["D", "R"]).merge(
        races[KEYS + ["context_cmo"]], on=KEYS, how="inner", validate="one_to_one")
    ids = sorted(set(pair.D) | set(pair.R)); lookup = {value: i for i, value in enumerate(ids)}
    design = np.zeros((len(pair), len(ids)))
    for row, item in enumerate(pair.itertuples()):
        design[row, lookup[item.D]] = 1
        design[row, lookup[item.R]] = -1
    # Ridge supplies the identifying constraint and partial pooling for sparse
    # candidates; effects sum approximately to zero.
    fit = Ridge(alpha=20.0, fit_intercept=False).fit(design, pair.context_cmo)
    appearance = pd.concat([pair.D, pair.R]).value_counts()
    effects = pd.DataFrame({"candidate_effect_id": ids, "partial_pooled_effect": fit.coef_})
    effects["appearances"] = effects.candidate_effect_id.map(appearance).fillna(0).astype(int)
    effects["attribution_reliability"] = effects.appearances / (effects.appearances + 2)
    pair["candidate_pair_component"] = fit.predict(design)
    pair["unattributed_race_residual"] = pair.context_cmo - pair.candidate_pair_component
    return effects, pair


def safe_correlation(x: pd.Series, y: pd.Series) -> dict[str, float | int | None]:
    mask = x.notna() & y.notna()
    if mask.sum() < 5 or x[mask].nunique() < 2 or y[mask].nunique() < 2:
        return {"n": int(mask.sum()), "pearson": None, "pearson_p": None,
                "spearman": None, "spearman_p": None}
    pearson = pearsonr(x[mask], y[mask]); spearman = spearmanr(x[mask], y[mask])
    return {"n": int(mask.sum()), "pearson": float(pearson.statistic),
            "pearson_p": float(pearson.pvalue), "spearman": float(spearman.statistic),
            "spearman_p": float(spearman.pvalue)}


def construct_validity(races: pd.DataFrame, candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    score = candidates.merge(races[KEYS + ["context_cmo", "within_cycle_cmo", "raw_ticket_overperformance"]],
                             on=KEYS, how="inner", validate="many_to_one")
    sign = score.canonical_party.map({"D": 1, "R": -1})
    score["winner_i"] = binary(score.winner)
    score["incumbent_i"] = binary(score.incumbent)
    for column in ("context_cmo", "within_cycle_cmo", "raw_ticket_overperformance"):
        score[f"candidate_{column}"] = score[column] * sign
    score = score.sort_values(["candidate_effect_id", "cycle"])
    grouped = score.groupby("candidate_effect_id", sort=False)
    score["prior_candidate_context_cmo"] = grouped.candidate_context_cmo.shift(1)
    score["prior_cycle"] = grouped.cycle.shift(1)
    repeat = score[score.prior_cycle.eq(score.cycle - 4)].copy()
    results = []
    for outcome in ("candidate_context_cmo", "candidate_within_cycle_cmo", "candidate_raw_ticket_overperformance"):
        result = safe_correlation(repeat.prior_candidate_context_cmo, repeat[outcome])
        results.append({"design": "repeat_candidate_next_cycle", "outcome": outcome, **result})
    result = safe_correlation(repeat.prior_candidate_context_cmo, repeat.winner_i)
    results.append({"design": "prior_cmo_next_win_bivariate_association", "outcome": "winner_i", **result})
    # Successors: same party/district/chamber after a different candidate.
    score["seat_party"] = score.chamber.astype(str) + ":" + score.district.astype(str) + ":" + score.canonical_party
    seat_group = score.sort_values(["seat_party", "cycle"]).groupby("seat_party", sort=False)
    score["prior_seat_candidate"] = seat_group.candidate_effect_id.shift(1)
    score["prior_seat_identity_status"] = seat_group.identity_status.shift(1)
    score["prior_seat_cycle"] = seat_group.cycle.shift(1)
    score["prior_seat_cmo"] = seat_group.candidate_context_cmo.shift(1)
    score["prior_seat_incumbent"] = seat_group.incumbent_i.shift(1)
    successors = score[
        score.prior_seat_cycle.eq(score.cycle - 4)
        & score.prior_seat_candidate.notna()
        & score.prior_seat_candidate.ne(score.candidate_effect_id)
        & score.identity_status.ne("surname_only_unresolved_race_specific")
        & score.prior_seat_identity_status.ne("surname_only_unresolved_race_specific")
        & score.cycle.isin([1998, 2006, 2010, 2018])].copy()
    result = safe_correlation(successors.prior_seat_cmo, successors.candidate_context_cmo)
    results.append({"design": "different_candidate_same_seat_party", "outcome": "candidate_context_cmo", **result})
    retirement_successors = successors[successors.prior_seat_incumbent.eq(1)]
    result = safe_correlation(retirement_successors.prior_seat_cmo, retirement_successors.candidate_context_cmo)
    results.append({"design": "incumbent_departure_successor", "outcome": "candidate_context_cmo", **result})
    return pd.DataFrame(results), successors


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance_manifest(races: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    inputs = [
        ELECTIONS / "canonical_cmo_features.csv",
        ELECTIONS / "canonical_cmo_candidates.csv",
        ELECTIONS / "canonical_cmo_district_office_baselines.csv",
        ELECTIONS / "historical_federal_district_baselines.csv",
    ]
    rows = [{"record_type": "input", "name": str(path.relative_to(ROOT)), "value": sha256(path)} for path in inputs]
    rows.extend([
        {"record_type": "code", "name": str(Path(__file__).resolve().relative_to(ROOT)), "value": sha256(Path(__file__).resolve())},
        {"record_type": "config", "name": "random_seed", "value": str(SEED)},
        {"record_type": "config", "name": "modern_federal_weight", "value": "0.30"},
        {"record_type": "config", "name": "headline_ridge_alpha", "value": "20.0"},
        {"record_type": "config", "name": "nominal_contest_threshold", "value": "0.05"},
        {"record_type": "count", "name": "eligible_races", "value": str(len(races))},
        {"record_type": "count", "name": "candidate_rows", "value": str(len(candidates))},
    ])
    run_material = "\n".join(f"{row['record_type']}|{row['name']}|{row['value']}" for row in rows)
    rows.append({"record_type": "run", "name": "build_run_id",
                 "value": hashlib.sha256(run_material.encode("utf-8")).hexdigest()})
    return pd.DataFrame(rows)


def metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {"mae": float(mean_absolute_error(actual, predicted)),
            "rmse": float(mean_squared_error(actual, predicted) ** .5),
            "r2": float(r2_score(actual, predicted)),
            "mean_error": float(np.mean(actual - predicted))}


def markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for item in frame.itertuples(index=False, name=None):
        rows.append("| " + " | ".join("" if pd.isna(value) else str(value) for value in item) + " |")
    return "\n".join(rows)


def build() -> dict[str, pd.DataFrame]:
    races, candidates = load_panel()
    data = prepare_features(attach_candidate_history(build_source_aware_baseline(races), candidates))
    if data.baseline_ensemble_margin.isna().any():
        raise ValueError("Every eligible race requires an ensemble baseline")

    data["expected_margin_context"] = cycle_crossfit(data, CORE_NUMERIC, "ridge", 20.0)
    data["expected_margin_context_huber"] = cycle_crossfit(data, CORE_NUMERIC, "huber", 20.0)
    data["expected_margin_context_logit"] = cycle_crossfit(data, CORE_NUMERIC, "ridge", 20.0, True)
    data["expected_margin_predictive"] = cycle_crossfit(data, CORE_NUMERIC + PREDICTIVE_EXTRA, "ridge", 20.0)
    data["expected_margin_nested_forward"], selection = nested_forward(data)
    data["context_cmo"] = data.legislative_dem_margin - data.expected_margin_context
    data["within_cycle_cmo"] = data.context_cmo - data.groupby(["cycle", "chamber"]).context_cmo.transform("median")
    data["predictive_residual"] = data.legislative_dem_margin - data.expected_margin_predictive
    data["context_cmo_huber"] = data.legislative_dem_margin - data.expected_margin_context_huber
    data["context_cmo_logit"] = data.legislative_dem_margin - data.expected_margin_context_logit

    spec_predictions = data[["baseline_ensemble_margin", "expected_margin_context",
                             "expected_margin_context_huber", "expected_margin_context_logit"]]
    data["specification_sd"] = spec_predictions.std(axis=1)
    quality_penalty = 5 * pd.to_numeric(data.baseline_fallback_share, errors="coerce").fillna(0)
    contest_penalty = data.contest_tier.map({"meaningful": 0.0, "marginal": 2.0, "nominal": 5.0})
    # CMO is the residual, so predictive error is not uncertainty *around* the
    # residual. The band instead measures disagreement among defensible
    # expectation specifications plus known baseline/contest-quality penalties.
    data["cmo_uncertainty_radius"] = (
        1.96 * data.specification_sd + quality_penalty + contest_penalty).clip(lower=2)
    data["context_cmo_low"] = data.context_cmo - data.cmo_uncertainty_radius
    data["context_cmo_high"] = data.context_cmo + data.cmo_uncertainty_radius

    effects, pair = crossed_candidate_effects(data, candidates)
    validity, successors = construct_validity(data, candidates)
    diagnostics = []
    for name in ("baseline_ensemble_margin", "expected_margin_context", "expected_margin_context_huber",
                 "expected_margin_context_logit", "expected_margin_predictive", "expected_margin_nested_forward"):
        for cycle, group in data.groupby("cycle"):
            valid = group[name].notna()
            if valid.any():
                diagnostics.append({"specification": name, "cycle": cycle, "races": int(valid.sum()),
                                    **metrics(group.loc[valid, "legislative_dem_margin"], group.loc[valid, name])})
    diagnostics = pd.DataFrame(diagnostics)

    candidate_scores = candidates.merge(data[KEYS + [
        "raw_ticket_overperformance", "context_cmo", "within_cycle_cmo", "predictive_residual",
        "context_cmo_low", "context_cmo_high", "contest_tier", "baseline_source_v2"]],
        on=KEYS, how="inner", validate="many_to_one")
    sign = candidate_scores.canonical_party.map({"D": 1, "R": -1})
    for column in ("raw_ticket_overperformance", "context_cmo", "within_cycle_cmo", "predictive_residual"):
        candidate_scores[f"candidate_{column}"] = candidate_scores[column] * sign
    candidate_scores["candidate_context_cmo_low"] = np.where(
        sign.eq(1), candidate_scores.context_cmo_low, -candidate_scores.context_cmo_high)
    candidate_scores["candidate_context_cmo_high"] = np.where(
        sign.eq(1), candidate_scores.context_cmo_high, -candidate_scores.context_cmo_low)
    candidate_scores = candidate_scores.merge(effects, on="candidate_effect_id", how="left", validate="many_to_one")
    # The crossed design already orients both parties toward own-party strength:
    # Democratic candidates enter +1 and Republican candidates enter -1.
    candidate_scores["candidate_partial_pooled_effect"] = candidate_scores.partial_pooled_effect

    baseline_diagnostics = (data.groupby(["cycle", "baseline_source_v2"], as_index=False)
                            .agg(races=("district", "size"), state_offices=("statewide_offices", "median"),
                                 federal_coverage=("federal_available_v2", "mean"),
                                 mean_raw_overperformance=("raw_ticket_overperformance", "mean")))
    identity_audit = candidates[["cycle", "chamber", "district", "canonical_party", "canonical_name",
                                 "normalized_candidate_name", "canonical_candidate_id", "person_id", "candidate_effect_id",
                                 "identity_status", "identity_collision_split"]].copy()
    return {"races": data, "candidates": candidate_scores, "diagnostics": diagnostics,
            "nested_forward_selection": selection, "candidate_effects": effects,
            "candidate_pair_attribution": pair, "construct_validity": validity,
            "successor_design": successors, "baseline_diagnostics": baseline_diagnostics,
            "identity_audit": identity_audit,
            "run_manifest": provenance_manifest(data, candidate_scores)}


def write_report(outputs: dict[str, pd.DataFrame]) -> None:
    races = outputs["races"]; diag = outputs["diagnostics"]; validity = outputs["construct_validity"]
    summary = (diag.groupby("specification", as_index=False)
               .agg(cycle_balanced_mae=("mae", "mean"), latest_cycle_mae=("mae", "last")))
    uncertainty = races.cmo_uncertainty_radius.quantile([.1, .5, .9]).to_dict()
    contest_counts = races.contest_tier.value_counts().rename_axis("tier").reset_index(name="races")
    lines = [
        "# CMO methodology v2", "",
        "This build replaces the single ambiguous headline with four explicitly different quantities. It is a versioned staging release and does not overwrite the prior public fields until independent validation and web migration are complete.", "",
        "## Four estimands", "",
        "1. **Raw ticket overperformance:** legislative Democratic margin minus the source-aware same-cycle ticket baseline.",
        "2. **Context CMO:** the cycle-held-out residual after adjusting only for non-candidate electoral context.",
        "3. **Within-cycle CMO:** context CMO centered on the chamber-cycle median for comparisons across eras.",
        "4. **Predictive residual:** error from a separately labeled expected-performance model that may use incumbency, finance, and strictly lagged candidate history.", "",
        "## Invariants", "",
        "- Headline context CMO excludes incumbency, finance, candidate history, and ideology.",
        "- Predictive expected performance is separately labeled and may use candidate-derived information.",
        "- The source-aware baseline vote-weights Governor and Attorney General and adds a prespecified 30% federal component from 2018 when federal coverage is usable.",
        "- Races below 5% losing-party vote share are nominal contests and do not train the expectation model.",
        "- Cycle-held-out margin ridge, Huber, and logit-share specifications are retained for uncertainty.",
        "- Nested-forward selection uses only cycles earlier than the test cycle.",
        "- Candidate/opponent effects use a crossed ridge model and are explicitly partial-pooled.", "",
        "## Implementation of the ten priorities", "",
        "1. The model card and implementation now use one candidate-variable-free headline definition.",
        "2. Absolute and chamber-cycle-centered CMO are both retained.",
        "3. Predictive expected performance is a different output rather than a replacement definition of CMO.",
        "4. Governor and Attorney General are aggregated by actual two-party votes; usable post-2016 federal context receives a prespecified 30% weight; previous presidential margin is the fallback.",
        "5. Nominal contests are scored but excluded from fitting.",
        "6. Ridge-in-margin-space, robust Huber, and bounded logit-share expectations are compared.",
        "7. Every expectation is cycle-held-out, and a nested-forward selector chooses specifications using earlier cycles only.",
        "8. Headline features are available conceptually in every era; recent-only region fields are excluded rather than zero-filled into the headline.",
        "9. Candidate and opponent attribution uses stable person identities in a crossed, partial-pooled model.",
        "10. Repeat-candidate, next-win bivariate, same-seat successor, and incumbent-departure successor diagnostics test construct validity.", "",
        f"Eligible races: {len(races)}.", "", markdown_table(contest_counts), "",
        "## Predictive diagnostics", "", markdown_table(summary), "",
        "## Construct validity", "", markdown_table(validity), "",
        "Repeat-candidate persistence is positive but modest, while same-seat persistence for different candidates is stronger. Context CMO must therefore remain a candidate-side electoral residual, not a fully identified personal effect. The partial-pooled effect is the more conservative candidate-level attribution.", "",
        "## Race-specific uncertainty", "",
        f"The specification/data-quality radius has a 10th percentile of {uncertainty[.1]:.2f} points, median of {uncertainty[.5]:.2f}, and 90th percentile of {uncertainty[.9]:.2f}. It combines disagreement among the baseline-only, ridge, Huber, and logit expectations with geographic-fallback and nominal-contest penalties. It does not add predictive residual error around a residual by definition.", "",
        "## Release rules", "",
        "- Public candidate tables should default to context CMO and offer raw, within-cycle, and partial-pooled views.",
        "- Cross-era rankings should use within-cycle CMO, not uncentered context CMO alone.",
        "- Forecasts should consume expected performance, never historical CMO labels as if they were probabilities.",
        "- Nominal contests and 1994 sensitivity rows require visible flags.",
        "- Candidate partial-pooled effects require appearance counts and attribution reliability.", "",
        "## Limitations", "",
        "The ensemble's post-2016 federal weight is prespecified from prior source-frozen analysis rather than identified anew here. Same-cycle ticket results make every CMO retrospective. Partial pooling cannot fully separate candidates who appear only once. Full-name identity linkage is conservative and splits names that collide within a cycle; surname-only rows are race-specific and excluded from longitudinal linkage until manually resolved. The method may still miss a person whose recorded full name changes. The uncertainty interval is a specification-and-data-quality band, not a causal confidence interval. The 1994 tier retains weaker geography and presidential inputs. Successor persistence shows that unmeasured local context remains. The bivariate prior-CMO/next-win association is not a multivariable predictive test and does not validate CMO as a future-win score.",
    ]
    (ROOT / "project_docs" / "model" / "CMO_METHODOLOGY_V2.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    outputs = build()
    for name, frame in outputs.items():
        if name == "run_manifest":
            continue
        frame.to_csv(WAR / f"cmo_v2_{name}.csv", index=False)
    manifest = outputs["run_manifest"].copy()
    output_rows = []
    for name in sorted(key for key in outputs if key != "run_manifest"):
        path = WAR / f"cmo_v2_{name}.csv"
        output_rows.append({"record_type": "output", "name": str(path.relative_to(ROOT)),
                            "value": sha256(path)})
    manifest = pd.concat([manifest, pd.DataFrame(output_rows)], ignore_index=True)
    manifest.to_csv(WAR / "cmo_v2_run_manifest.csv", index=False)
    write_report(outputs)
    print(outputs["diagnostics"].groupby("specification").mae.mean().sort_values().to_string())
    print("\nConstruct validity:\n", outputs["construct_validity"].to_string(index=False))


if __name__ == "__main__":
    main()
