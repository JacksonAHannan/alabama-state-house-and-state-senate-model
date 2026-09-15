#!/usr/bin/env python3
"""Carry a candidate's demonstrated WAR forward into the 2026 Alabama forecast.

Owner decision (2026-09-15): v3 has no candidate-history term — its decaying lag
is the prior-presidential district lag — so the persistence of a candidate's own
WAR is estimated on the Southern v3 panel's repeat candidates and applied to the
2026 roster.

Two deliberate limits are recorded rather than smoothed over:

* Persistence is estimated over 2-to-6-year gaps. A 2026 candidate whose last
  race was 2018 is an 8-year extrapolation, flagged as such.
* Identity matching is verified-crosswalk first, then exact unique normalized
  name. Ambiguous names are left unmatched and get the missing-history encoding,
  never a forced match.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
SOUTHERN = WAR / "post2016_southern_war_v3" / "candidate_cycle_war.csv"
ALABAMA = WAR / "alabama_historical_war_v1" / "candidate_cycle_war.csv"
ROSTER = WAR / "2026_final_candidate_roster.csv"
INCUMBENCY = WAR / "2026_candidate_incumbency.csv"
OUT = ROOT / "data" / "processed" / "forecast_calibration"
PREFIX = "alabama_forecast_candidate_history"

FORECAST_CYCLE = 2026
SUFFIXES = re.compile(r"\b(JR|SR|II|III|IV|DR|MR|MRS|MS)\b")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().upper()
    text = re.sub(r"[^A-Z ]", " ", text)
    return " ".join(SUFFIXES.sub(" ", text).split())


def repeat_pairs(training_before: int | None = None) -> pd.DataFrame:
    """Consecutive appearances of one candidate identity in the Southern v3 panel."""
    panel = pd.read_csv(SOUTHERN, low_memory=False)
    panel = panel[panel.candidate_cycle_war.notna() & panel.normalized_candidate_name.notna()]
    panel = panel[~panel.same_cycle_name_collision]
    panel["identity"] = (panel.state_code.astype(str) + "|" + panel.canonical_party.astype(str)
                         + "|" + panel.normalized_candidate_name.astype(str))
    rows = []
    for identity, group in panel.sort_values(["identity", "cycle"]).groupby("identity"):
        history = group.to_dict("records")
        for previous, current in zip(history, history[1:]):
            if current["cycle"] <= previous["cycle"]:
                continue
            rows.append({
                "identity": identity, "state_code": current["state_code"],
                "prior_cycle": int(previous["cycle"]), "cycle": int(current["cycle"]),
                "years_elapsed": int(current["cycle"] - previous["cycle"]),
                "prior_candidate_cycle_war": float(previous["candidate_cycle_war"]),
                "candidate_cycle_war": float(current["candidate_cycle_war"]),
            })
    pairs = pd.DataFrame(rows)
    if training_before is not None:
        pairs = pairs[pairs.cycle.lt(training_before)].copy()
    if len(pairs) < 100:
        raise RuntimeError(f"Too few repeat-candidate pairs to estimate persistence: {len(pairs)}")
    return pairs


def cluster_ols(y: np.ndarray, x: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """OLS with candidate-clustered standard errors; repeated people are not independent."""
    inverse = np.linalg.pinv(x.T @ x)
    beta = inverse @ x.T @ y
    residual = y - x @ beta
    meat = np.zeros((x.shape[1], x.shape[1]))
    for group in pd.unique(groups):
        index = np.where(groups == group)[0]
        score = x[index].T @ residual[index]
        meat += np.outer(score, score)
    return beta, np.sqrt(np.diag(inverse @ meat @ inverse))


def fit_persistence(pairs: pd.DataFrame) -> dict:
    """Estimate how much of a candidate's WAR carries into their next race.

    The years-elapsed interaction is only estimable when the training pairs span
    more than one gap length; a single-gap window (for example the pre-2022
    holdout, which is all 2018-to-2020) reports it as unavailable instead of
    dividing by a zero standard error.
    """
    centred = pairs.years_elapsed - 2
    interaction = pairs.prior_candidate_cycle_war * centred
    estimable = bool(np.ptp(pairs.years_elapsed) > 0 and interaction.std(ddof=0) > 0)
    columns = [np.ones(len(pairs)), pairs.prior_candidate_cycle_war]
    if estimable:
        columns.append(interaction)
    design = np.column_stack(columns)
    beta, se = cluster_ols(pairs.candidate_cycle_war.to_numpy(float), design, pairs.identity.to_numpy())
    predicted = design @ beta
    total = ((pairs.candidate_cycle_war - pairs.candidate_cycle_war.mean()) ** 2).sum()
    decay = float(beta[2]) if estimable else None
    decay_se = float(se[2]) if estimable else None
    decay_t = float(beta[2] / se[2]) if estimable and se[2] > 0 else None
    return {
        "intercept": float(beta[0]), "persistence": float(beta[1]), "decay_per_year": decay,
        "intercept_se": float(se[0]), "persistence_se": float(se[1]), "decay_se": decay_se,
        "persistence_t": float(beta[1] / se[1]), "decay_t": decay_t,
        "decay_estimable": estimable,
        "decay_supported": bool(decay_t is not None and abs(decay_t) >= 2.0),
        "pairs": int(len(pairs)), "candidates": int(pairs.identity.nunique()),
        "r_squared": float(1 - ((pairs.candidate_cycle_war - predicted) ** 2).sum() / total),
        "observed_year_gaps": sorted(int(gap) for gap in pairs.years_elapsed.unique()),
    }


def expected_carry(fit: dict, prior_war: pd.Series, years: pd.Series) -> pd.Series:
    """Predicted candidate effect. The decay term is applied only if the data support it."""
    carry = fit["persistence"] * prior_war
    if fit["decay_supported"]:
        carry = carry + fit["decay_per_year"] * prior_war * (years - 2)
    return carry


def alabama_history() -> pd.DataFrame:
    history = pd.read_csv(ALABAMA, low_memory=False)
    history = history[history.candidate_cycle_war.notna()].copy()
    history["match_name"] = history.canonical_name.map(normalize)
    return history


def match_roster() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Match 2026 candidates to their prior Alabama races; never force a match."""
    roster = pd.read_csv(ROSTER)
    incumbency = pd.read_csv(INCUMBENCY)
    history = alabama_history()

    verified = incumbency[incumbency.prior_winner_candidate_id.notna()][
        ["chamber", "district", "party", "candidate", "prior_winner_candidate_id"]
    ]
    identity = history[["canonical_candidate_id", "person_id"]].drop_duplicates()
    verified = verified.merge(identity, left_on="prior_winner_candidate_id",
                              right_on="canonical_candidate_id", how="left")

    roster = roster.merge(
        verified[["chamber", "district", "party", "candidate", "person_id"]],
        on=["chamber", "district", "party", "candidate"], how="left", validate="one_to_one",
    ).rename(columns={"person_id": "verified_person_id"})

    unique_names = (history.groupby("match_name").person_id.nunique()
                    .loc[lambda s: s.eq(1)].index)
    by_name = (history[history.match_name.isin(unique_names)]
               .drop_duplicates("match_name").set_index("match_name").person_id)
    roster["match_name"] = roster.candidate.map(normalize)
    roster["name_person_id"] = roster.match_name.map(by_name)
    ambiguous = set(history.groupby("match_name").person_id.nunique().loc[lambda s: s.gt(1)].index)

    roster["person_id"] = roster.verified_person_id.fillna(roster.name_person_id)
    roster["match_method"] = np.where(
        roster.verified_person_id.notna(), "verified_prior_winner_crosswalk",
        np.where(roster.name_person_id.notna(), "exact_unique_normalized_name",
                 np.where(roster.match_name.isin(ambiguous), "ambiguous_name_left_unmatched",
                          "no_prior_alabama_race")))

    summary = (history.sort_values("cycle").groupby("person_id")
               .agg(prior_cycles=("cycle", "size"), last_prior_cycle=("cycle", "max"),
                    last_prior_war=("candidate_cycle_war", "last"),
                    mean_prior_war=("candidate_cycle_war", "mean"),
                    last_prior_chamber=("chamber", "last"), last_prior_district=("district", "last"))
               .reset_index())
    matched = roster.merge(summary, on="person_id", how="left")
    matched["years_elapsed"] = FORECAST_CYCLE - matched.last_prior_cycle
    matched["history_available"] = matched.person_id.notna() & matched.last_prior_war.notna()
    matched["last_prior_race"] = (matched.last_prior_cycle.astype("Int64").astype(str) + "|"
                                  + matched.last_prior_chamber.astype(str) + "|"
                                  + matched.last_prior_district.astype("Int64").astype(str))
    return matched, history


def race_adjustments(candidates: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Effect of both candidates' carried WAR on the Democratic margin.

    Candidate WAR is oriented per candidate and a race's two values are exact
    negatives, so a rematch would otherwise count one prior race residual twice.
    When both candidates last ran against each other, the single Democratic-
    oriented value is used.
    """
    rows = []
    for key, race in candidates.groupby(keys):
        indexed = race.drop_duplicates("party").set_index("party")
        effects = indexed.expected_candidate_effect.to_dict()
        priors = indexed.last_prior_race.to_dict() if "last_prior_race" in indexed else {}
        democratic, republican = float(effects.get("D", 0.0)), float(effects.get("R", 0.0))
        carried = {party for party, value in effects.items() if value}
        rematch = ({"D", "R"} <= carried
                   and priors.get("D") is not None and priors.get("D") == priors.get("R"))
        adjustment = democratic if rematch else democratic - republican
        rows.append(dict(zip(keys, key if isinstance(key, tuple) else (key,)),
                         candidate_war_adjustment=float(adjustment),
                         candidate_history_used=bool(carried),
                         rematch_deduplicated=bool(rematch)))
    return pd.DataFrame(rows)


def holdout_race_adjustments(test_cycle: int, fit: dict, carry_limit: int) -> pd.DataFrame:
    """Race-level adjustments for a past cycle, using only evidence before it.

    Person identifiers do not link 2022 to earlier cycles — the 2022 canonical
    rows carry source stubs — so candidates are matched on an exact unique
    normalized name, exactly as the 2026 roster is.
    """
    history = alabama_history()
    prior = history[history.cycle.lt(test_cycle)]
    unique = prior.groupby("match_name").person_id.nunique().loc[lambda s: s.eq(1)].index
    last = (prior[prior.match_name.isin(unique)].sort_values("cycle").groupby("match_name")
            .agg(last_prior_cycle=("cycle", "max"), last_prior_war=("candidate_cycle_war", "last"),
                 last_prior_chamber=("chamber", "last"), last_prior_district=("district", "last"))
            .reset_index())
    current = history[history.cycle.eq(test_cycle)][
        ["match_name", "chamber", "district", "canonical_party"]
    ].rename(columns={"canonical_party": "party"})
    joined = current.merge(last, on="match_name", how="left")
    joined["years_elapsed"] = test_cycle - joined.last_prior_cycle
    carried = joined.last_prior_war.notna() & joined.years_elapsed.le(carry_limit)
    joined["expected_candidate_effect"] = np.where(
        carried, expected_carry(fit, joined.last_prior_war.fillna(0.0), joined.years_elapsed.fillna(0.0)), 0.0)
    joined["last_prior_race"] = np.where(
        carried,
        joined.last_prior_cycle.astype("Int64").astype(str) + "|"
        + joined.last_prior_chamber.astype(str) + "|"
        + joined.last_prior_district.astype("Int64").astype(str),
        None)
    return race_adjustments(joined, ["chamber", "district"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = repeat_pairs()
    fit = fit_persistence(pairs)
    holdout_fit = fit_persistence(repeat_pairs(training_before=2022))

    roster, _ = match_roster()
    # Persistence is measured over 2-to-6-year gaps. One cycle beyond that is a
    # defensible extrapolation; a 2006 result carried into 2026 at full strength
    # is not, so older matches keep their history but enter as missing.
    carry_limit = max(fit["observed_year_gaps"]) + 2
    fresh = roster.history_available & roster.years_elapsed.le(carry_limit)
    roster["carry_applied"] = fresh
    roster["expected_candidate_effect"] = np.where(
        fresh, expected_carry(fit, roster.last_prior_war.fillna(0.0), roster.years_elapsed.fillna(0.0)), 0.0,
    )
    roster["history_status"] = np.where(
        ~roster.history_available, "missing_history_encoded_as_zero",
        np.where(~fresh, "history_older_than_carry_limit_encoded_as_zero",
                 np.where(roster.years_elapsed > max(fit["observed_year_gaps"]),
                          "extrapolated_one_cycle_beyond_observed_gap", "within_observed_gap")))

    columns = ["cycle", "chamber", "district", "party", "candidate", "match_method", "person_id",
               "prior_cycles", "last_prior_cycle", "years_elapsed", "last_prior_war",
               "mean_prior_war", "history_available", "carry_applied", "history_status",
               "expected_candidate_effect"]
    roster[columns].to_csv(OUT / f"{PREFIX}.csv", index=False)
    pairs.to_csv(OUT / f"{PREFIX}_pairs.csv", index=False)
    races = race_adjustments(roster[roster.carry_applied | roster.history_available],
                             ["chamber", "district"])
    races.to_csv(OUT / f"{PREFIX}_race_adjustments.csv", index=False)

    matched = roster[roster.carry_applied]
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "estimand": "persistence of a candidate's own residual WAR into their next race",
        "specification": "candidate_cycle_war ~ prior_candidate_cycle_war (+ interaction with years elapsed)",
        "standard_errors": "clustered by candidate identity",
        "fit": fit,
        "holdout_fit_trained_before_2022": holdout_fit,
        "decay_note": ("The years-elapsed interaction is not statistically supported and is therefore "
                       "not applied; persistence is treated as constant over the observed 2-6 year gaps."),
        "identity_matching": roster.match_method.value_counts().to_dict(),
        "coverage": {
            "roster_rows": int(len(roster)),
            "matched_with_history": int(matched.shape[0]),
            "carry_applied": int(roster.carry_applied.sum()),
            "carry_limit_years": int(carry_limit),
            "extrapolated_one_cycle_beyond_observed_gap": int((roster.history_status == "extrapolated_one_cycle_beyond_observed_gap").sum()),
            "history_older_than_carry_limit": int((roster.history_status == "history_older_than_carry_limit_encoded_as_zero").sum()),
            "mean_abs_expected_effect": float(matched.expected_candidate_effect.abs().mean()) if len(matched) else 0.0,
        },
        "inputs": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
                   for path in (SOUTHERN, ALABAMA, ROSTER, INCUMBENCY)],
        "outputs": [{"path": f"data/processed/forecast_calibration/{PREFIX}.csv", "rows": int(len(roster))},
                    {"path": f"data/processed/forecast_calibration/{PREFIX}_pairs.csv", "rows": int(len(pairs))},
                    {"path": f"data/processed/forecast_calibration/{PREFIX}_race_adjustments.csv", "rows": int(len(races))}],
    }
    (OUT / f"{PREFIX}_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"persistence={fit['persistence']:.3f} (se {fit['persistence_se']:.3f}, t {fit['persistence_t']:.2f}) "
          f"on {fit['pairs']} pairs / {fit['candidates']} candidates; decay supported={fit['decay_supported']}")
    print(f"matched {len(matched)} of {len(roster)} roster rows; "
          f"{manifest['coverage']['extrapolated_one_cycle_beyond_observed_gap']} one cycle beyond the observed gaps, "
          f"{manifest['coverage']['history_older_than_carry_limit']} too old to carry")
    print(roster.match_method.value_counts().to_string())


if __name__ == "__main__":
    main()
