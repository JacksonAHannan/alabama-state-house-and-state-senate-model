#!/usr/bin/env python3
"""Infer 2024 Southern legislative incumbency from 2022 winners."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/historical_statewide_elections"
OUT = ROOT / "data/processed/forecast_calibration"
MEDSL = RAW / "dataverse_files (1).zip"
KLARNER = RAW / "dataverse_files.zip"
PANEL = OUT / "southern_legislative_probability_panel.csv"
STATES = {"Arkansas": "AR", "Georgia": "GA", "Tennessee": "TN", "Texas": "TX"}
KEYS = ["state", "year", "chamber", "district"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii").upper()
    if "," in text:
        last, rest = text.split(",", 1)
        text = f"{rest} {last}"
    text = re.sub(r"\b(JR|SR|II|III|IV)\b", " ", text)
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def prior_winners() -> pd.DataFrame:
    with ZipFile(KLARNER) as bundle:
        source = pd.read_csv(bundle.open("208slers_uoa_cand_contest20230810.csv"), low_memory=False)
    source = source.loc[
        source.year.isin([2020, 2022]) & source.state.isin(STATES) & source.outcome.eq("w")
        & source.partyt.isin(["d", "r"]) & source.dontuse.fillna(0).eq(0)
    ].copy()
    source["state"] = source.state.map(STATES)
    source["prior_year"] = source.year
    source["chamber"] = source.sen.map({0: "lower", 1: "upper"})
    source["district_2022"] = pd.to_numeric(source.dno, errors="coerce")
    source["prior_party"] = source.partyt.str.upper()
    source["prior_candidate"] = source.cand.astype(str)
    source["normalized_name"] = source.prior_candidate.map(normalized_name)
    source["normalized_surname"] = source["last"].fillna(
        source.prior_candidate.str.split(",").str[0]).map(normalized_name)
    source = source.dropna(subset=["chamber", "district_2022"])
    # Biennial lower chambers repeat in 2022; staggered upper chambers retain
    # the latest winner from either 2020 or 2022. Deduplicate people after name
    # normalization so a 2020 and 2022 reelection does not create ambiguity.
    source = source.sort_values("prior_year", ascending=False).drop_duplicates(
        ["state", "chamber", "normalized_name"], keep="first")
    return source[["state", "chamber", "district_2022", "prior_year", "prior_party", "prior_candidate",
                   "normalized_name", "normalized_surname", "uncont", "exper", "candid"]].drop_duplicates()


def current_candidates() -> pd.DataFrame:
    usecols = ["office", "party_simplified", "mode", "votes", "district", "candidate",
               "year", "state_po", "stage", "special", "writein", "precinct"]
    with ZipFile(MEDSL) as bundle:
        raw = pd.read_csv(bundle.open("STATE_precinct_general.csv"), usecols=usecols, low_memory=False)
    raw = raw.loc[
        raw.state_po.isin(STATES.values()) & raw.office.isin(["STATE HOUSE", "STATE SENATE"])
        & raw.year.eq(2024) & raw.stage.eq("GEN") & ~raw.special.fillna(False)
        & raw.party_simplified.isin(["DEMOCRAT", "REPUBLICAN"]) & ~raw.writein.fillna(False)
    ].copy()
    raw["votes"] = pd.to_numeric(raw.votes, errors="coerce")
    key = ["state_po", "office", "district", "precinct", "party_simplified", "candidate"]
    has_total = raw.groupby(key).mode.transform(lambda values: values.eq("TOTAL").any())
    raw = raw.loc[~has_total | raw["mode"].eq("TOTAL")]
    totals = (raw.groupby(["state_po", "office", "district", "party_simplified", "candidate"], as_index=False)
              .votes.sum(min_count=1))
    totals = totals.sort_values("votes", ascending=False).drop_duplicates(
        ["state_po", "office", "district", "party_simplified"])
    totals["state"] = totals.state_po
    totals["year"] = 2024
    totals["chamber"] = totals.office.map({"STATE HOUSE": "lower", "STATE SENATE": "upper"})
    totals["district"] = pd.to_numeric(totals.district, errors="coerce")
    totals["party"] = totals.party_simplified.map({"DEMOCRAT": "D", "REPUBLICAN": "R"})
    totals["normalized_name"] = totals.candidate.map(normalized_name)
    eligible = pd.read_csv(PANEL, low_memory=False)
    eligible = eligible.loc[eligible.year.eq(2024) & eligible.primary_calibration_eligible.astype(bool), KEYS]
    return totals.merge(eligible, on=KEYS, how="inner", validate="many_to_one")


def match_candidates(current: pd.DataFrame, winners: pd.DataFrame) -> pd.DataFrame:
    records = []
    for row in current.itertuples():
        pool = winners.loc[(winners.state.eq(row.state)) & (winners.chamber.eq(row.chamber))].copy()
        exact = pool.loc[pool.normalized_name.eq(row.normalized_name)]
        match, method, score, runner = None, "no_prior_winner_match", np.nan, np.nan
        if len(exact) == 1:
            match, method, score, runner = exact.iloc[0], "exact_normalized_name", 1.0, 0.0
        elif len(exact) > 1:
            method = "ambiguous_exact_name"
        else:
            one_token = len(row.normalized_name.split()) == 1
            comparison_pool = pool.loc[pool.prior_party.eq(row.party)].copy() if one_token else pool
            district_pool = comparison_pool.loc[comparison_pool.district_2022.eq(row.district)].copy()
            if len(district_pool):
                compare_column = "normalized_surname" if one_token else "normalized_name"
                district_pool["match_score"] = district_pool[compare_column].map(
                    lambda value: SequenceMatcher(None, row.normalized_name, value).ratio())
                district_pool = district_pool.sort_values("match_score", ascending=False)
                best = district_pool.iloc[0]
                second = district_pool.iloc[1].match_score if len(district_pool) > 1 else 0.0
                threshold = 0.90 if one_token else 0.85
                if best.match_score >= threshold and best.match_score - second >= 0.05:
                    match, method, score, runner = (
                        best, "district_surname_match" if one_token else "district_name_match",
                        float(best.match_score), float(second))
        if match is None and not method.startswith("ambiguous") and len(row.normalized_name.split()) == 1:
            surname_pool = pool.loc[pool.prior_party.eq(row.party)]
            surname_exact = surname_pool.loc[surname_pool.normalized_surname.eq(row.normalized_name)]
            if len(surname_exact) == 1:
                match, method, score, runner = surname_exact.iloc[0], "unique_exact_surname", 1.0, 0.0
            elif len(surname_exact) > 1:
                method = "ambiguous_exact_surname"
            elif len(surname_pool):
                scored = surname_pool.assign(match_score=surname_pool.normalized_surname.map(
                    lambda value: SequenceMatcher(None, row.normalized_name, value).ratio()))
                scored = scored.sort_values("match_score", ascending=False)
                best = scored.iloc[0]
                second = scored.iloc[1].match_score if len(scored) > 1 else 0.0
                score, runner = float(best.match_score), float(second)
                if score >= 0.90 and score - runner >= 0.05:
                    match, method = best, "unique_fuzzy_surname"
                elif score >= 0.80:
                    method = "ambiguous_fuzzy_surname"
        elif match is None and not method.startswith("ambiguous") and len(pool):
            scored = pool.assign(match_score=pool.normalized_name.map(
                lambda value: SequenceMatcher(None, row.normalized_name, value).ratio()))
            scored = scored.sort_values("match_score", ascending=False)
            best = scored.iloc[0]
            second = scored.iloc[1].match_score if len(scored) > 1 else 0.0
            score, runner = float(best.match_score), float(second)
            if score >= 0.94 and score - runner >= 0.05:
                match, method = best, "unique_fuzzy_name"
            elif score >= 0.85:
                method = "ambiguous_fuzzy_name"
        resolved = match is not None
        records.append({
            "state": row.state, "year": 2024, "chamber": row.chamber, "district": row.district,
            "party": row.party, "candidate": row.candidate, "candidate_votes": row.votes,
            "normalized_name": row.normalized_name,
            "incumbent": np.nan if method.startswith("ambiguous") else bool(resolved),
            "match_method": method, "match_score": score, "runner_up_score": runner,
            "prior_candidate": match.prior_candidate if resolved else np.nan,
            "prior_year": match.prior_year if resolved else np.nan,
            "prior_party": match.prior_party if resolved else np.nan,
            "prior_district": match.district_2022 if resolved else np.nan,
            "party_switch": bool(resolved and match.prior_party != row.party),
        })
    return pd.DataFrame(records)


def race_labels(matches: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, group in matches.groupby(KEYS, sort=True):
        parties = group.set_index("party")
        ambiguous = group.incumbent.isna().any()
        dem = parties.incumbent.get("D", np.nan)
        rep = parties.incumbent.get("R", np.nan)
        conflict = (not pd.isna(dem)) and (not pd.isna(rep)) and bool(dem) and bool(rep)
        if ambiguous or conflict or pd.isna(dem) or pd.isna(rep):
            status, balance, model_ready = ("ambiguous_or_conflicting", np.nan, False)
        else:
            balance = int(bool(dem)) - int(bool(rep))
            status = "incumbent_running" if balance else "inferred_open_complete_roster"
            model_ready = True
        rows.append(dict(zip(KEYS, key), dem_incumbent=dem, rep_incumbent=rep,
                         incumbency_balance=balance, incumbency_status=status,
                         incumbency_model_ready=model_ready))
    return pd.DataFrame(rows)


def main() -> None:
    winners, current = prior_winners(), current_candidates()
    matches = match_candidates(current, winners)
    races = race_labels(matches)
    review = matches.loc[matches.match_method.str.startswith("ambiguous")].copy()
    coverage = (races.groupby(["state", "chamber"], as_index=False)
                .agg(races=("district", "size"), model_ready=("incumbency_model_ready", "sum"),
                     inferred_open=("incumbency_status", lambda x: int(x.eq("inferred_open_complete_roster").sum())),
                     incumbent_running=("incumbency_status", lambda x: int(x.eq("incumbent_running").sum()))))
    outputs = {
        "southern_2024_incumbency_candidates.csv": matches,
        "southern_2024_incumbency_races.csv": races,
        "southern_2024_incumbency_review.csv": review,
        "southern_2024_incumbency_coverage.csv": coverage,
        "southern_2022_winner_roster.csv": winners,
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)
    manifest = {
        "schema_version": 1, "status": "staging", "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "inputs": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
                   for path in (MEDSL, KLARNER, PANEL)],
        "outputs": [{"path": f"data/processed/forecast_calibration/{name}", "rows": len(frame),
                     "sha256": sha256(OUT / name)} for name, frame in outputs.items()],
    }
    manifest["build_id"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:20]
    (OUT / "southern_2024_incumbency_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(coverage.to_string(index=False))
    print(f"matches={len(matches)} races={len(races)} review={len(review)} build={manifest['build_id']}")


if __name__ == "__main__":
    main()
