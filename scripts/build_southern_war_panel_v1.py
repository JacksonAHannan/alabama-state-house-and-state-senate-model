#!/usr/bin/env python3
"""Build a provenance-preserving Southern legislative WAR research panel.

This is an experimental model mart, not a canonical warehouse publication.
It inventories all repository source families, preserves competing baseline
observations, and selects only explicitly ranked observations. Missing values
remain missing. Observed same-cycle ticket baselines are never conflated with
synthetic presidential-plus-national-environment baselines.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
CAL = ROOT / "data/processed/forecast_calibration"
WAR = ROOT / "data/processed/war"
OUT = WAR / "southern_war_panel_v1"
TX_ROOT = ROOT.parent / "texas-state-house-and-state-senate-model"
INCUMBENCY_ROSTER = ROOT / "data/processed/incumbency/southern_incumbency_race_roster_2016_2024.csv"
GENERIC_BALLOT_ENVIRONMENT = ROOT / "data/processed/polling/virginia_generic_ballot_environment.csv"

TARGET_STATES = ["AL", "AR", "FL", "GA", "KY", "LA", "MS", "MO", "NC", "OK", "SC", "TN", "TX", "VA"]
STATE_NAMES = {
    "Alabama": "AL", "Arkansas": "AR", "Florida": "FL", "Georgia": "GA",
    "Kentucky": "KY", "Louisiana": "LA", "Mississippi": "MS", "Missouri": "MO",
    "North Carolina": "NC", "Oklahoma": "OK", "South Carolina": "SC",
    "Tennessee": "TN", "Texas": "TX", "Virginia": "VA",
}
KEYS = ["state", "year", "chamber", "district"]


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


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def source_ref(path: Path) -> str:
    """Return a stable provenance reference for local or sibling-repository inputs."""
    try:
        return rel(path)
    except ValueError:
        if path.resolve().is_relative_to(TX_ROOT.resolve()):
            suffix = path.resolve().relative_to(TX_ROOT.resolve())
            return f"external://texas-state-house-and-state-senate-model/{str(suffix).replace(chr(92), '/')}"
        return str(path.resolve()).replace("\\", "/")


def normalized_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value).upper()
    text = re.sub(r"\b(JR|SR|II|III|IV)\b", " ", text)
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def standard_chamber(value: object) -> str:
    text = str(value).lower().strip()
    return {"lower": "house", "upper": "senate", "state house": "house", "state senate": "senate"}.get(text, text)


def standard_district(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.round().astype("Int64")


def texas_tlc_result_file(year: int) -> Path:
    base = (
        TX_ROOT
        / "data/raw/tx_sos/Texas_Precincts_2012_2020_Downloader"
        / "Texas_Precincts_2012_2020"
    )
    paths = list(base.rglob(f"{year}_General_Election_Returns.csv"))
    if not paths:
        raise FileNotFoundError(f"Texas TLC normalized returns missing for {year}")
    return sorted(paths, key=lambda path: ("FTP_Election_Data_12G" not in str(path), len(str(path))))[0]


def load_klarner_universe() -> pd.DataFrame:
    path = RAW / "historical_statewide_elections/dataverse_files.zip"
    with ZipFile(path) as bundle:
        contests = pd.read_csv(bundle.open("202slers_uoa_contest20230810.csv"), low_memory=False)
        candidates = pd.read_csv(bundle.open("208slers_uoa_cand_contest20230810.csv"), low_memory=False)

    contests = contests[
        contests.state.isin(STATE_NAMES)
        & contests.year.between(1994, 2022)
        & contests.dseats.eq(1)
        & contests.eseats.eq(1)
        & contests.etype.eq("g")
    ].copy()
    contests["state"] = contests.state.map(STATE_NAMES)
    contests["chamber"] = contests.sen.map({0: "house", 1: "senate"})
    contests["district"] = standard_district(contests.dno)
    contests["dem_votes"] = pd.to_numeric(contests.dvote, errors="coerce")
    contests["rep_votes"] = pd.to_numeric(contests.rvote, errors="coerce")
    contests["incumbency_balance"] = pd.to_numeric(contests.dinc, errors="coerce") - pd.to_numeric(contests.rinc, errors="coerce")
    contests["dem_incumbent"] = pd.to_numeric(contests.dinc, errors="coerce")
    contests["rep_incumbent"] = pd.to_numeric(contests.rinc, errors="coerce")
    contests["dem_win"] = pd.to_numeric(contests.dwin, errors="coerce")
    contests["rep_win"] = pd.to_numeric(contests.rwin, errors="coerce")

    candidates = candidates[
        candidates.state.isin(STATE_NAMES)
        & candidates.year.between(1994, 2022)
        & candidates.dseats.eq(1)
        & candidates.eseats.eq(1)
        & candidates.etype.eq("g")
        & candidates.partyt.isin(["d", "r"])
    ].copy()
    candidates["state"] = candidates.state.map(STATE_NAMES)
    candidates["chamber"] = candidates.sen.map({0: "house", 1: "senate"})
    candidates["district"] = standard_district(candidates.dno)
    candidates["candidate_votes"] = pd.to_numeric(candidates.vote, errors="coerce")
    candidates = candidates.sort_values("candidate_votes", ascending=False).drop_duplicates(KEYS + ["partyt"])
    names = candidates.pivot(index=KEYS, columns="partyt", values="cand").reset_index().rename(
        columns={"d": "dem_candidate", "r": "rep_candidate"}
    )

    keep = KEYS + [
        "dem_votes", "rep_votes", "dem_incumbent", "rep_incumbent", "incumbency_balance",
        "dem_win", "rep_win", "uncont", "dontuse", "bigthird", "dswitch", "rswitch",
    ]
    out = contests[keep].merge(names, on=KEYS, how="left", validate="one_to_one")
    denominator = out.dem_votes + out.rep_votes
    out["legislative_dem_margin"] = 100 * (out.dem_votes - out.rep_votes) / denominator.where(denominator > 0)
    out["outcome_eligible"] = (
        out.dem_votes.gt(0) & out.rep_votes.gt(0) & out.dontuse.fillna(0).eq(0) & out.uncont.fillna(0).eq(0)
    )
    out["outcome_source"] = "Klarner State Legislative Election Returns"
    out["outcome_source_path"] = rel(path)
    out["candidate_source"] = "Klarner candidate-contest archive"
    out["incumbency_source"] = "Klarner contest archive"
    out["incumbency_quality"] = np.where(out.incumbency_balance.notna(), "source_observed", "missing")
    return out


def load_alabama_canonical() -> tuple[pd.DataFrame, pd.DataFrame]:
    race_path = WAR / "cmo_v5_races.csv"
    candidate_path = WAR / "cmo_v5_candidates.csv"
    races = pd.read_csv(race_path, low_memory=False).rename(columns={"cycle": "year"})
    candidates = pd.read_csv(candidate_path, low_memory=False).rename(columns={"cycle": "year"})
    candidates["chamber"] = candidates.chamber.map(standard_chamber)
    names = candidates.pivot_table(
        index=["year", "chamber", "district"], columns="canonical_party", values="canonical_name", aggfunc="first"
    ).reset_index().rename(columns={"D": "dem_candidate", "R": "rep_candidate"})
    inc = candidates.pivot_table(
        index=["year", "chamber", "district"], columns="canonical_party", values="incumbent", aggfunc="max"
    ).reset_index().rename(columns={"D": "dem_incumbent", "R": "rep_incumbent"})
    out = races.merge(names, on=["year", "chamber", "district"], how="left", validate="one_to_one")
    out = out.merge(inc, on=["year", "chamber", "district"], how="left", validate="one_to_one")
    out["state"] = "AL"
    out["rep_incumbent"] = out.rep_incumbent.fillna(0)
    out["dem_incumbent"] = out.dem_incumbent.fillna(0)
    out["incumbency_balance"] = out.dem_incumbent - out.rep_incumbent
    out["outcome_eligible"] = out.dem_votes.gt(0) & out.rep_votes.gt(0)
    out["outcome_source"] = "Canonical Alabama election warehouse export"
    out["outcome_source_path"] = rel(race_path)
    out["candidate_source"] = "Canonical Alabama candidate export"
    out["incumbency_source"] = "Canonical Alabama candidate export"
    out["incumbency_quality"] = "canonical_reviewed"
    outcome_columns = KEYS + [
        "dem_votes", "rep_votes", "legislative_dem_margin", "dem_candidate", "rep_candidate",
        "dem_incumbent", "rep_incumbent", "incumbency_balance", "outcome_eligible",
        "outcome_source", "outcome_source_path", "candidate_source", "incumbency_source", "incumbency_quality",
    ]
    outcome = out[outcome_columns].copy()
    outcome["dem_win"] = outcome.dem_votes.gt(outcome.rep_votes).astype(int)
    outcome["rep_win"] = outcome.rep_votes.gt(outcome.dem_votes).astype(int)
    outcome["uncont"] = 0
    outcome["dontuse"] = 0
    outcome["bigthird"] = 0
    outcome["dswitch"] = np.nan
    outcome["rswitch"] = np.nan

    baseline = out[KEYS + ["selected_ticket_margin", "selected_ticket_source"]].rename(
        columns={"selected_ticket_margin": "baseline_dem_margin", "selected_ticket_source": "baseline_source"}
    )
    baseline["baseline_office"] = baseline.baseline_source
    baseline["baseline_class"] = "canonical_observed_ticket"
    baseline["baseline_quality"] = "canonical_reviewed"
    baseline["baseline_priority"] = 1
    baseline["baseline_coverage"] = 1.0
    baseline["baseline_source_path"] = rel(race_path)
    baseline["strict_baseline_eligible"] = True
    baseline["research_baseline_eligible"] = True
    return outcome, baseline


def recover_texas_ticket_baselines(existing: pd.DataFrame) -> pd.DataFrame:
    """Recover ticket context where party/name defects excluded a valid race.

    These rows use the same observed-precinct-membership allocation as the
    Texas full-history pipeline, but membership does not require every
    legislative candidate's party label. This recovers five 1994 races and one
    1998 race while leaving the two 1996 districts absent from the TLC precinct
    export explicitly missing.
    """
    archive = TX_ROOT / "data/raw/tx_sos/OneDrive_2026-08-17.zip"
    with ZipFile(archive) as bundle:
        text = io.TextIOWrapper(
            bundle.open("Election Results by Precinct/1994 General.csv"), encoding="utf-8-sig"
        )
        reader = csv.reader(text)
        next(reader)
        parsed = [
            (fields[0], fields[1], fields[5], fields[6], fields[7])
            for fields in reader if len(fields) >= 8
        ]
    raw_1994 = pd.DataFrame(parsed, columns=["county", "precinct", "office", "candidate", "votes"])
    raw_1994["votes"] = pd.to_numeric(raw_1994.votes, errors="coerce")
    raw_1994["precinct_key"] = (
        raw_1994.county.astype(str).str.upper().str.strip()
        + "|"
        + raw_1994.precinct.astype(str).str.upper().str.strip()
    )
    raw_1994["context_party"] = raw_1994.candidate.map({"Richards": "D", "Bush": "R"})

    path_1998 = texas_tlc_result_file(1998)
    raw_1998 = pd.read_csv(path_1998, dtype={"cntyvtd": str}, low_memory=False)
    raw_1998.columns = raw_1998.columns.str.lower()
    raw_1998["votes"] = pd.to_numeric(raw_1998.votes, errors="coerce")
    raw_1998["precinct_key"] = raw_1998.cntyvtd.astype(str).str.replace(r"\.0$", "", regex=True)
    raw_1998["context_party"] = raw_1998.party.where(raw_1998.party.isin(["D", "R"]))

    targets = [
        (1994, "house", 18), (1994, "house", 57), (1994, "house", 97),
        (1994, "house", 116), (1994, "senate", 27), (1998, "house", 51),
    ]
    existing_keys = set(existing[KEYS].itertuples(index=False, name=None))
    rows: list[dict[str, object]] = []
    for year, chamber, district in targets:
        key = ("TX", year, chamber, district)
        if key in existing_keys:
            continue
        frame = raw_1994 if year == 1994 else raw_1998
        office = f"State {'Rep' if chamber == 'house' else 'Sen'} {district}"
        race = frame[frame.office.astype(str).str.fullmatch(office, case=False, na=False)].copy()
        if race.empty:
            continue
        turnout = race.groupby("precinct_key", as_index=False).votes.sum().rename(columns={"votes": "race_turnout"})
        context = frame[
            frame.office.astype(str).str.fullmatch("Governor", case=False, na=False)
            & frame.context_party.isin(["D", "R"])
        ].groupby(["precinct_key", "context_party"], as_index=False).votes.sum()
        context = context.pivot(index="precinct_key", columns="context_party", values="votes").reset_index()
        if "D" not in context or "R" not in context:
            continue
        joined = turnout.merge(context[["precinct_key", "D", "R"]], on="precinct_key", how="left", validate="one_to_one")
        matched = joined.D.notna() & joined.R.notna()
        coverage = joined.loc[matched, "race_turnout"].sum() / joined.race_turnout.sum()
        dem_votes = joined.loc[matched, "D"].sum(min_count=1)
        rep_votes = joined.loc[matched, "R"].sum(min_count=1)
        denominator = dem_votes + rep_votes
        rows.append({
            "state": "TX", "year": year, "chamber": chamber, "district": district,
            "baseline_dem_margin": 100 * (dem_votes - rep_votes) / denominator if denominator > 0 else np.nan,
            "baseline_office": "Governor",
            "baseline_source": "Texas official precinct returns; recovered race-membership governor allocation",
            "baseline_class": "observed_same_cycle_ticket",
            "baseline_quality": "official_results_vtd_membership_recovery",
            "baseline_priority": 1,
            "baseline_coverage": coverage,
            "baseline_source_path": source_ref(archive if year == 1994 else path_1998),
            "strict_baseline_eligible": bool(denominator > 0 and coverage >= 0.95),
            "research_baseline_eligible": bool(denominator > 0),
        })
    return pd.DataFrame(rows)


def load_texas_upstream(klarner: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load official-source Texas facts without importing Texas model scores.

    Official candidate-total exports supply outcomes and names. The sibling
    repository's full-history candidate export is used only as a normalized
    carrier for observed incumbency and district-allocated ticket margins. Its
    ``total_cmo`` and percentile fields are intentionally ignored. The 2024 baseline is repaired from the explicit
    presidential-margin field because the compatibility export's expected-margin
    column contains the non-presidential statewide-office index in that cycle.
    """
    full_path = TX_ROOT / "data/processed/models/full_history_cmo_candidates.csv"
    feature_path = TX_ROOT / "data/processed/features/historical_cmo_features.csv"
    legacy_result_path = TX_ROOT / "data/processed/elections/sos_canonical_candidate_totals_1992_2018.csv"
    current_result_path = TX_ROOT / "data/processed/elections/sos_official_candidate_totals_2020_2024.csv"
    if not all(path.exists() for path in (full_path, feature_path, legacy_result_path, current_result_path)):
        raise FileNotFoundError(
            "Texas upstream is required at the sibling texas-state-house-and-state-senate-model repository"
        )

    candidates = pd.read_csv(full_path, low_memory=False)
    required = {
        "cycle", "chamber", "district", "candidate_name", "party", "votes", "incumbent",
        "candidate_margin", "expected_margin", "baseline_office", "source",
    }
    missing = required - set(candidates.columns)
    if missing:
        raise ValueError(f"Texas full-history export missing columns: {sorted(missing)}")
    candidates = candidates[candidates.party.isin(["D", "R"])].copy()
    candidates["chamber"] = candidates.chamber.map(standard_chamber)
    candidates["district"] = standard_district(candidates.district)
    tx_keys = ["cycle", "chamber", "district"]
    if candidates.duplicated(tx_keys + ["party"]).any():
        raise ValueError("Texas upstream has duplicate party observations within a race")
    party_sets = candidates.groupby(tx_keys).party.agg(lambda values: set(values))
    if not party_sets.map(lambda values: values == {"D", "R"}).all():
        raise ValueError("Texas upstream contains a race without exactly one D and one R observation")

    dem = candidates[candidates.party.eq("D")].copy()
    rep = candidates[candidates.party.eq("R")].copy()
    paired = dem.merge(rep, on=tx_keys, how="inner", suffixes=("_dem", "_rep"), validate="one_to_one")
    for column in ("candidate_margin", "expected_margin"):
        symmetry = (
            pd.to_numeric(paired[f"{column}_dem"], errors="coerce")
            + pd.to_numeric(paired[f"{column}_rep"], errors="coerce")
        ).abs()
        if symmetry.gt(1e-8).any():
            raise ValueError(f"Texas party-oriented {column} is not symmetric")

    legacy = pd.read_csv(legacy_result_path, low_memory=False)
    legacy = legacy[
        legacy.cycle.between(1994, 2018)
        & legacy.chamber.isin(["house", "senate"])
        & legacy.party.isin(["D", "R"])
        & ~legacy.office.astype(str).str.contains("Unexpired Term", case=False, na=False)
    ][["cycle", "chamber", "district", "party", "candidate_name", "votes"]].copy()
    legacy["incumbent_official"] = np.nan
    legacy["result_source_path"] = source_ref(legacy_result_path)
    current = pd.read_csv(current_result_path, low_memory=False)
    current = current[
        current.cycle.between(2020, 2024)
        & current.chamber.isin(["house", "senate"])
        & current.party.isin(["D", "R"])
    ][["cycle", "chamber", "district", "party", "candidate_name", "official_votes", "incumbent"]].copy()
    current = current.rename(columns={"official_votes": "votes", "incumbent": "incumbent_official"})
    current["result_source_path"] = source_ref(current_result_path)
    official = pd.concat([legacy, current], ignore_index=True)
    official["chamber"] = official.chamber.map(standard_chamber)
    official["district"] = standard_district(official.district)
    if official.duplicated(tx_keys + ["party"]).any():
        raise ValueError("Texas official totals have duplicate major-party observations within a race")
    official_sets = official.groupby(tx_keys).party.agg(lambda values: set(values))
    contested_keys = official_sets[official_sets.map(lambda values: values == {"D", "R"})].index
    official = official.set_index(tx_keys).loc[contested_keys].reset_index()
    official_dem = official[official.party.eq("D")].copy()
    official_rep = official[official.party.eq("R")].copy()
    official_paired = official_dem.merge(
        official_rep, on=tx_keys, how="inner", suffixes=("_dem", "_rep"), validate="one_to_one"
    )
    carrier = paired[tx_keys + ["incumbent_dem", "incumbent_rep"]].copy()
    official_paired = official_paired.merge(carrier, on=tx_keys, how="left", validate="one_to_one")
    official_paired["dem_incumbent"] = official_paired.incumbent_official_dem.astype(str).str.lower().map(
        {"true": 1.0, "false": 0.0}
    ).fillna(official_paired.incumbent_dem.astype(str).str.lower().map({"true": 1.0, "false": 0.0}))
    official_paired["rep_incumbent"] = official_paired.incumbent_official_rep.astype(str).str.lower().map(
        {"true": 1.0, "false": 0.0}
    ).fillna(official_paired.incumbent_rep.astype(str).str.lower().map({"true": 1.0, "false": 0.0}))
    denominator = pd.to_numeric(official_paired.votes_dem) + pd.to_numeric(official_paired.votes_rep)
    outcome = pd.DataFrame({
        "state": "TX",
        "year": official_paired.cycle.astype(int),
        "chamber": official_paired.chamber,
        "district": standard_district(official_paired.district),
        "dem_votes": pd.to_numeric(official_paired.votes_dem, errors="coerce"),
        "rep_votes": pd.to_numeric(official_paired.votes_rep, errors="coerce"),
        "legislative_dem_margin": 100 * (
            pd.to_numeric(official_paired.votes_dem) - pd.to_numeric(official_paired.votes_rep)
        ) / denominator.where(denominator.gt(0)),
        "dem_candidate": official_paired.candidate_name_dem,
        "rep_candidate": official_paired.candidate_name_rep,
        "dem_incumbent": official_paired.dem_incumbent,
        "rep_incumbent": official_paired.rep_incumbent,
        "result_source_path": official_paired.result_source_path_dem,
    })
    # The 1994 compatibility builder hard-coded incumbency False because its
    # precinct file carried no status field. Replace those placeholders with
    # the source-observed Klarner flags where the exact race key is available.
    outcome.loc[outcome.year.eq(1994), ["dem_incumbent", "rep_incumbent"]] = np.nan
    fallback = klarner[klarner.state.eq("TX")][KEYS + ["dem_incumbent", "rep_incumbent"]].rename(
        columns={"dem_incumbent": "klarner_dem_incumbent", "rep_incumbent": "klarner_rep_incumbent"}
    )
    outcome = outcome.merge(fallback, on=KEYS, how="left", validate="one_to_one")
    dem_fallback = outcome.dem_incumbent.isna() & outcome.klarner_dem_incumbent.notna()
    rep_fallback = outcome.rep_incumbent.isna() & outcome.klarner_rep_incumbent.notna()
    outcome.loc[dem_fallback, "dem_incumbent"] = outcome.loc[dem_fallback, "klarner_dem_incumbent"]
    outcome.loc[rep_fallback, "rep_incumbent"] = outcome.loc[rep_fallback, "klarner_rep_incumbent"]
    used_klarner = dem_fallback | rep_fallback
    outcome["incumbency_balance"] = outcome.dem_incumbent - outcome.rep_incumbent
    outcome["outcome_eligible"] = outcome.dem_votes.gt(0) & outcome.rep_votes.gt(0)
    outcome["dem_win"] = outcome.dem_votes.gt(outcome.rep_votes).astype(int)
    outcome["rep_win"] = outcome.rep_votes.gt(outcome.dem_votes).astype(int)
    outcome["uncont"], outcome["dontuse"], outcome["bigthird"] = 0, 0, np.nan
    outcome["dswitch"], outcome["rswitch"] = np.nan, np.nan
    outcome["outcome_source"] = "Texas official returns normalized by the Texas project"
    outcome["outcome_source_path"] = outcome.result_source_path
    outcome["candidate_source"] = "Texas Secretary of State candidate-total exports"
    outcome["incumbency_source"] = np.where(
        used_klarner,
        "Texas official outcomes; Klarner source-observed 1994 incumbency",
        "Texas official/canonical candidate and full-history incumbency exports",
    )
    outcome["incumbency_quality"] = np.where(
        outcome.incumbency_balance.isna(), "missing", "source_observed"
    )
    outcome = outcome.drop(columns=["klarner_dem_incumbent", "klarner_rep_incumbent", "result_source_path"])

    baseline = pd.DataFrame({
        "state": "TX",
        "year": paired.cycle.astype(int),
        "chamber": paired.chamber,
        "district": standard_district(paired.district),
        "baseline_dem_margin": pd.to_numeric(paired.expected_margin_dem, errors="coerce"),
        "baseline_office": paired.baseline_office_dem,
        "upstream_source": paired.source_dem,
    })
    features = pd.read_csv(feature_path, low_memory=False)
    features = features.rename(columns={"cycle": "year"})
    features["chamber"] = features.chamber.map(standard_chamber)
    features["district"] = standard_district(features.district)
    features = features[features.year.isin([2022, 2024])][
        KEYS[1:] + ["state_top_ticket_margin", "presidential_dem_margin", "state_top_ticket_office_count", "baseline_source"]
    ].copy()
    baseline = baseline.merge(features, on=KEYS[1:], how="left", validate="one_to_one")
    is_2022 = baseline.year.eq(2022)
    is_2024 = baseline.year.eq(2024)
    baseline.loc[is_2022, "baseline_dem_margin"] = baseline.loc[is_2022, "state_top_ticket_margin"]
    baseline.loc[is_2022, "baseline_office"] = "STATEWIDE_OFFICE_INDEX"
    baseline.loc[is_2024, "baseline_dem_margin"] = baseline.loc[is_2024, "presidential_dem_margin"]
    baseline.loc[is_2024, "baseline_office"] = "PRESIDENT"
    baseline["baseline_source"] = np.select(
        [is_2022, is_2024, baseline.upstream_source.eq("sos_precinct_returns")],
        [
            "Texas Legislative Council RED-206 statewide-office average",
            "Texas Legislative Council RED-206 presidential result",
            "Texas Secretary of State precinct returns; district-allocated governor result",
        ],
        default="Texas Legislative Council VTD-normalized returns; district-allocated ballot-first context",
    )
    baseline["baseline_class"] = "observed_same_cycle_ticket"
    baseline["baseline_quality"] = "official_results_district_allocated"
    baseline["baseline_priority"] = 1
    baseline["baseline_coverage"] = 1.0
    baseline["baseline_source_path"] = np.where(
        baseline.year.isin([2022, 2024]), source_ref(feature_path), source_ref(full_path)
    )
    baseline["strict_baseline_eligible"] = baseline.baseline_dem_margin.notna()
    baseline["research_baseline_eligible"] = baseline.baseline_dem_margin.notna()
    baseline = baseline.drop(columns=[
        "upstream_source", "state_top_ticket_margin", "presidential_dem_margin",
        "state_top_ticket_office_count",
    ])
    recovered_baseline = recover_texas_ticket_baselines(baseline)
    if not recovered_baseline.empty:
        baseline = pd.concat([baseline, recovered_baseline], ignore_index=True, sort=False)

    comparison = outcome.merge(
        klarner[klarner.state.eq("TX")][
            KEYS + ["dem_votes", "rep_votes", "legislative_dem_margin", "dem_candidate", "rep_candidate", "incumbency_balance"]
        ].rename(columns={
            "dem_votes": "klarner_dem_votes", "rep_votes": "klarner_rep_votes",
            "legislative_dem_margin": "klarner_legislative_dem_margin",
            "dem_candidate": "klarner_dem_candidate", "rep_candidate": "klarner_rep_candidate",
            "incumbency_balance": "klarner_incumbency_balance",
        }),
        on=KEYS, how="outer", indicator=True, validate="one_to_one",
    )
    comparison["dem_vote_difference_texas_minus_klarner"] = comparison.dem_votes - comparison.klarner_dem_votes
    comparison["rep_vote_difference_texas_minus_klarner"] = comparison.rep_votes - comparison.klarner_rep_votes
    comparison["margin_difference_texas_minus_klarner"] = (
        comparison.legislative_dem_margin - comparison.klarner_legislative_dem_margin
    )
    comparison["selected_outcome_source"] = np.where(
        comparison._merge.ne("right_only"), "texas_official_upstream", "klarner_fallback"
    )
    return outcome, baseline, comparison


def load_louisiana_official_outcomes() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Parse both Louisiana stages and select each district's actual final stage.

    Louisiana's October open primary is the final election for a district when
    a candidate wins outright.  If the district appears on the November
    runoff ballot, only that later contest is the final outcome.  Stage-level
    rows are retained separately and are never summed across dates.
    """
    base = RAW / "southern_sos_elections/LA"
    candidate_rows: list[dict[str, object]] = []
    contest_rows: list[dict[str, object]] = []
    for directory in sorted(path for path in base.iterdir() if path.is_dir() and path.name.isdigit()):
        year = int(directory.name)
        index_paths = sorted(directory.glob("ElectionRaces_*.htm"))
        dates = [re.search(r"(\d{8})", path.stem).group(1) for path in index_paths]
        stage_by_date = {
            date: "first_round" if date == min(dates) else "runoff"
            for date in dates
        } if dates else {}
        for index_path in index_paths:
            date_match = re.search(r"(\d{8})", index_path.stem)
            if not date_match:
                continue
            election_date = date_match.group(1)
            election_stage = stage_by_date[election_date]
            payload = json.loads(index_path.read_text(encoding="utf-8-sig"))
            races = payload.get("Races", {}).get("Race", [])
            if isinstance(races, dict):
                races = [races]
            legislative = [race for race in races if re.search(
                r"State (?:Representative|Senator)\b", race.get("OfficeTitleAndDesc", ""), re.I
            )]
            for race in legislative:
                race_id = str(race.get("RaceID", "")).strip()
                path = directory / f"ByPrecinct_{race_id}.csv"
                if not path.is_file():
                    raise FileNotFoundError(f"Louisiana race {race_id} is indexed but {path} is missing")
                frame = pd.read_csv(path, low_memory=False)
                if frame.empty or "Office" not in frame:
                    raise ValueError(f"Louisiana contest export is empty or malformed: {path}")
                office = str(frame.Office.dropna().iloc[0]) if frame.Office.notna().any() else str(
                    race.get("OfficeTitleAndDesc", "")
                )
                # The 1999 ballot also carried two simultaneous unexpired-term
                # elections for districts 16 and 93. Preserve those raw files,
                # but exclude them from the regular-cycle panel.
                if re.search(r"\bUnexp(?:d|ired)?\.?\s*Term\b", office, re.I):
                    continue
                chamber = "house" if "Representative" in office else "senate" if "Senator" in office else None
                district_match = re.search(r"--\s*(\d+)", office)
                if chamber is None or district_match is None:
                    raise ValueError(f"Could not parse legislative office from {office!r} in {path}")
                district = int(district_match.group(1))
                candidates: list[dict[str, object]] = []
                for column in list(frame.columns[4:]):
                    label = str(column)
                    party_match = re.search(r"\(([^()]*)\)\s*$", label)
                    party_label = party_match.group(1).upper().strip() if party_match else ""
                    party = "D" if party_label.startswith("DEM") else "R" if party_label.startswith("REP") else "O"
                    name = re.sub(r"\s*\([^)]*\)\s*$", "", label).strip()
                    votes = pd.to_numeric(frame[column], errors="coerce").sum(min_count=1)
                    candidate = {"name": name, "party": party, "party_label": party_label, "votes": votes}
                    candidates.append(candidate)
                    candidate_rows.append({
                        "state": "LA", "year": year, "election_date": election_date,
                        "election_stage": election_stage, "race_id": race_id,
                        "chamber": chamber, "district": district, "office": office,
                        "candidate_name": name, "party": party, "party_label": party_label,
                        "candidate_votes": votes, "source_file": rel(path),
                        "race_index_source": rel(index_path),
                    })
                valid = [candidate for candidate in candidates if pd.notna(candidate["votes"])]
                winners = sorted(valid, key=lambda candidate: float(candidate["votes"]), reverse=True)
                dem = [candidate for candidate in valid if candidate["party"] == "D" and candidate["votes"] > 0]
                rep = [candidate for candidate in valid if candidate["party"] == "R" and candidate["votes"] > 0]
                contest_rows.append({
                    "state": "LA", "year": year, "election_date": election_date,
                    "election_stage": election_stage, "race_id": race_id,
                    "chamber": chamber, "district": district, "office": office,
                    "dem_candidate": dem[0]["name"] if len(dem) == 1 else pd.NA,
                    "rep_candidate": rep[0]["name"] if len(rep) == 1 else pd.NA,
                    "dem_votes": dem[0]["votes"] if len(dem) == 1 else np.nan,
                    "rep_votes": rep[0]["votes"] if len(rep) == 1 else np.nan,
                    "dem_candidate_count": len(dem), "rep_candidate_count": len(rep),
                    "candidate_count": len([candidate for candidate in valid if candidate["votes"] > 0]),
                    "winner_name": winners[0]["name"] if winners else pd.NA,
                    "winner_party": winners[0]["party"] if winners else pd.NA,
                    "stage_total_votes": sum(float(candidate["votes"]) for candidate in valid),
                    "source_files": rel(path), "race_index_source": rel(index_path),
                })

    stage_candidates = pd.DataFrame(candidate_rows)
    stage_contests = pd.DataFrame(contest_rows)
    if stage_contests.duplicated(KEYS + ["election_stage"]).any():
        duplicates = stage_contests.loc[
            stage_contests.duplicated(KEYS + ["election_stage"], keep=False),
            KEYS + ["election_stage", "race_id"],
        ]
        raise ValueError(f"Multiple Louisiana contests for a district/stage:\n{duplicates.to_string(index=False)}")
    final_stage = stage_contests.sort_values(
        KEYS + ["election_date"]
    ).drop_duplicates(KEYS, keep="last")[KEYS + ["election_stage"]].rename(
        columns={"election_stage": "selected_final_stage"}
    )
    stage_contests = stage_contests.merge(final_stage, on=KEYS, how="left", validate="many_to_one")
    stage_contests["is_final_stage"] = stage_contests.election_stage.eq(stage_contests.selected_final_stage)
    stage_candidates = stage_candidates.merge(final_stage, on=KEYS, how="left", validate="many_to_one")
    stage_candidates["is_final_stage"] = stage_candidates.election_stage.eq(stage_candidates.selected_final_stage)

    out = stage_contests[stage_contests.is_final_stage].copy()
    years = sorted(out.year.unique())
    prior_year = {year: years[index - 1] if index else None for index, year in enumerate(years)}
    prior_winners = {
        (year, chamber): set(group.winner_name.dropna().map(normalized_name))
        for (year, chamber), group in out.groupby(["year", "chamber"])
    }
    for index, row in out.iterrows():
        previous = prior_year[int(row.year)]
        if previous is None:
            out.at[index, "dem_incumbent"] = np.nan
            out.at[index, "rep_incumbent"] = np.nan
            out.at[index, "incumbency_balance"] = np.nan
            continue
        winner_set = prior_winners.get((previous, row.chamber), set())
        dem_inc = bool(pd.notna(row.dem_candidate) and normalized_name(row.dem_candidate) in winner_set)
        rep_inc = bool(pd.notna(row.rep_candidate) and normalized_name(row.rep_candidate) in winner_set)
        out.at[index, "dem_incumbent"] = float(dem_inc)
        out.at[index, "rep_incumbent"] = float(rep_inc)
        out.at[index, "incumbency_balance"] = float(dem_inc) - float(rep_inc)

    denominator = out.dem_votes + out.rep_votes
    out["legislative_dem_margin"] = 100 * (out.dem_votes - out.rep_votes) / denominator.where(denominator.gt(0))
    out["outcome_eligible"] = (
        out.dem_candidate_count.eq(1) & out.rep_candidate_count.eq(1) & out.dem_votes.gt(0) & out.rep_votes.gt(0)
    )
    out["dem_win"] = out.dem_votes.gt(out.rep_votes).astype(float)
    out["rep_win"] = out.rep_votes.gt(out.dem_votes).astype(float)
    out["uncont"], out["dontuse"], out["bigthird"] = 0, 0, np.nan
    out["dswitch"], out["rswitch"] = np.nan, np.nan
    out["outcome_source"] = "Louisiana Secretary of State two-stage precinct contest exports"
    out["outcome_source_path"] = out.source_files
    out["candidate_source"] = "Louisiana Secretary of State column labels"
    out["incumbency_source"] = "Exact name match to prior-cycle official final-stage winner"
    out["incumbency_quality"] = np.where(
        out.incumbency_balance.notna(), "experimental_exact_prior_winner", "missing"
    )
    return out, stage_candidates, stage_contests


def _la_compact_token(value: object) -> str:
    text = str(value).upper().strip().replace(" ", "")
    return re.sub(r"\d+", lambda match: str(int(match.group())), text)


def _la_vest_precinct_name(value: object) -> str:
    return "-".join(
        _la_compact_token(part)
        for part in re.split(r"[-\s]+", str(value).strip())
        if part
    )


def _la_official_precinct_aliases(ward: object, precinct: object) -> list[str]:
    """Generate documented-format aliases without fuzzy geographic guessing."""
    ward_token = _la_compact_token(ward)
    precinct_token = _la_compact_token(precinct)
    variants = [precinct_token]
    # Some official rows split one mapped VTD by alphabet or subpart. RDH/VEST
    # combines those rows, so retain the combined token as an alias.
    combined = re.sub(r"-(?:1|2)$", "", precinct_token)
    if combined != precinct_token:
        variants.append(combined)
    for suffix in ("AK", "LZ", "Y", "Z", "A", "B", "J", "K", "L", "M"):
        if precinct_token.endswith(suffix):
            variants.append(precinct_token[:-len(suffix)])

    aliases: list[str] = []

    def add(value: str) -> None:
        normalized = _la_vest_precinct_name(value)
        if normalized and normalized not in aliases:
            aliases.append(normalized)

    for variant in variants:
        add(variant)
        if ward_token not in {"", "0", "NAN"}:
            add(f"{ward_token}-{variant}")
        alpha_prefix = re.fullmatch(r"([A-Z]+)(\d+)([A-Z]*)", variant)
        if alpha_prefix:
            prefix, number, suffix = alpha_prefix.groups()
            add(f"{prefix}{number}")
            add(f"{number}-{prefix}{suffix}")
            add(number)
    return aliases


def load_louisiana_modern_baselines(
    louisiana_outcomes: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build stage-matched 2019 and 2023 statewide ticket baselines."""
    import geopandas as gpd

    path_2019 = RAW / "historical_statewide_elections/la_vest_19.zip"
    path_2023 = RAW / "historical_statewide_elections/la_2023_gen_prim_pber.zip"
    vest_2019 = gpd.read_file(f"zip://{path_2019.resolve()}").drop(columns="geometry")
    vest_2023 = gpd.read_file(f"zip://{path_2023.resolve()}").drop(columns="geometry")

    def party_sum(frame: pd.DataFrame, prefix: str) -> pd.Series:
        columns = [column for column in frame.columns if str(column).startswith(prefix)]
        if not columns:
            raise ValueError(f"Louisiana context bundle has no columns matching {prefix}")
        return frame[columns].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)

    baselines: list[pd.DataFrame] = []
    audits: list[dict[str, object]] = []

    # The 2023 RDH file carries official House/Senate district assignments.
    stage_columns_2023 = {
        "first_round": ("G23GOVD", "G23GOVR", "GOVERNOR"),
        "runoff": ("R23ATGD", "R23ATGR", "ATTORNEY GENERAL"),
    }
    for stage, (dem_prefix, rep_prefix, office) in stage_columns_2023.items():
        context = vest_2023.copy()
        context["baseline_dem_votes"] = party_sum(context, dem_prefix)
        context["baseline_rep_votes"] = party_sum(context, rep_prefix)
        for chamber, district_column in (("house", "SLDL_DIST"), ("senate", "SLDU_DIST")):
            selected = louisiana_outcomes[
                louisiana_outcomes.year.eq(2023)
                & louisiana_outcomes.chamber.eq(chamber)
                & louisiana_outcomes.election_stage.eq(stage)
            ][["district"]].drop_duplicates()
            district_context = context.copy()
            district_context["district"] = standard_district(district_context[district_column])
            aggregated = district_context.groupby("district", as_index=False)[
                ["baseline_dem_votes", "baseline_rep_votes"]
            ].sum(min_count=1)
            aggregated = selected.merge(aggregated, on="district", how="left", validate="one_to_one")
            aggregated["state"], aggregated["year"], aggregated["chamber"] = "LA", 2023, chamber
            aggregated["baseline_coverage"] = np.where(aggregated.baseline_dem_votes.notna(), 1.0, 0.0)
            denominator = aggregated.baseline_dem_votes + aggregated.baseline_rep_votes
            aggregated["baseline_dem_margin"] = 100 * (
                aggregated.baseline_dem_votes - aggregated.baseline_rep_votes
            ) / denominator.where(denominator.gt(0))
            aggregated["baseline_office"] = office
            aggregated["baseline_source"] = f"RDH/VEST Louisiana 2023 {stage} {office} context"
            aggregated["baseline_class"] = "observed_same_cycle_ticket"
            aggregated["baseline_quality"] = "official_district_assignment"
            aggregated["baseline_priority"] = 2
            aggregated["baseline_source_path"] = rel(path_2023)
            aggregated["strict_baseline_eligible"] = aggregated.baseline_dem_margin.notna()
            aggregated["research_baseline_eligible"] = aggregated.baseline_dem_margin.notna()
            baselines.append(aggregated)
            audits.append({
                "year": 2023, "election_stage": stage, "chamber": chamber,
                "districts": len(aggregated), "strict_districts": int(aggregated.strict_baseline_eligible.sum()),
                "matched_legislative_turnout": np.nan, "total_legislative_turnout": np.nan,
                "match_rate": 1.0, "source_path": rel(path_2023),
            })

    # The 2019 VEST file predates district attributes. Recover membership from
    # the official contest files, then turnout-weight a VTD only when it is
    # split across legislative districts.
    parish_map = {
        re.sub(r"[^A-Z0-9]", "", str(row.Parish).upper()): str(row.COUNTYFP).zfill(3)
        for row in vest_2023[["Parish", "COUNTYFP"]].drop_duplicates().itertuples()
    }
    vest_2019["county_fips"] = vest_2019.COUNTYFP.astype(str).str.zfill(3)
    vest_2019["precinct_name"] = vest_2019.NAME.map(_la_vest_precinct_name)
    vest_2019["precinct_key"] = vest_2019.county_fips + "|" + vest_2019.precinct_name
    if vest_2019.precinct_key.duplicated().any():
        raise ValueError("Louisiana 2019 VEST precinct keys are not unique")
    known_names = {
        fips: set(group.precinct_name)
        for fips, group in vest_2019.groupby("county_fips")
    }
    stage_columns_2019 = {
        "first_round": ("G19GOVD", "G19GOVR", "GOVERNOR"),
        "runoff": ("R19GOVD", "R19GOVR", "GOVERNOR RUNOFF"),
    }
    for stage, (dem_prefix, rep_prefix, office) in stage_columns_2019.items():
        context = vest_2019[["precinct_key"]].copy()
        context["baseline_dem_votes"] = party_sum(vest_2019, dem_prefix)
        context["baseline_rep_votes"] = party_sum(vest_2019, rep_prefix)
        for chamber in ("house", "senate"):
            selected = louisiana_outcomes[
                louisiana_outcomes.year.eq(2019)
                & louisiana_outcomes.chamber.eq(chamber)
                & louisiana_outcomes.election_stage.eq(stage)
            ]
            membership_rows: list[dict[str, object]] = []
            for outcome in selected.itertuples():
                frame = pd.read_csv(
                    ROOT / outcome.source_files,
                    dtype={"Parish": str, "Ward": str, "Precinct": str},
                    low_memory=False,
                )
                vote_columns = list(frame.columns[4:])
                turnout = frame[vote_columns].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)
                for source_row, legislative_turnout in zip(frame.itertuples(), turnout):
                    if str(source_row.Ward).upper().startswith("EARLY"):
                        continue
                    parish_key = re.sub(r"[^A-Z0-9]", "", str(source_row.Parish).upper())
                    county_fips = parish_map.get(parish_key)
                    matched_name = next((
                        alias for alias in _la_official_precinct_aliases(source_row.Ward, source_row.Precinct)
                        if alias in known_names.get(county_fips, set())
                    ), None)
                    membership_rows.append({
                        "district": outcome.district,
                        "legislative_turnout": legislative_turnout,
                        "precinct_key": f"{county_fips}|{matched_name}" if matched_name else pd.NA,
                        "matched": matched_name is not None,
                    })
            membership = pd.DataFrame(membership_rows)
            total_by_district = membership.groupby("district", as_index=False).legislative_turnout.sum(min_count=1).rename(
                columns={"legislative_turnout": "total_legislative_turnout"}
            )
            matched = membership[membership.matched].copy()
            matched_by_district = matched.groupby("district", as_index=False).legislative_turnout.sum(min_count=1).rename(
                columns={"legislative_turnout": "matched_legislative_turnout"}
            )
            fragments = matched.groupby(["precinct_key", "district"], as_index=False).legislative_turnout.sum(min_count=1)
            fragments["allocation_weight"] = fragments.legislative_turnout / fragments.groupby(
                "precinct_key"
            ).legislative_turnout.transform("sum").where(lambda values: values.gt(0))
            joined = fragments.merge(context, on="precinct_key", how="left", validate="many_to_one")
            joined["allocated_dem_votes"] = joined.baseline_dem_votes * joined.allocation_weight
            joined["allocated_rep_votes"] = joined.baseline_rep_votes * joined.allocation_weight
            aggregated = joined.groupby("district", as_index=False).agg(
                baseline_dem_votes=("allocated_dem_votes", lambda values: values.sum(min_count=1)),
                baseline_rep_votes=("allocated_rep_votes", lambda values: values.sum(min_count=1)),
            )
            aggregated = selected[["district"]].drop_duplicates().merge(
                aggregated, on="district", how="left", validate="one_to_one"
            ).merge(total_by_district, on="district", how="left", validate="one_to_one").merge(
                matched_by_district, on="district", how="left", validate="one_to_one"
            )
            aggregated["matched_legislative_turnout"] = aggregated.matched_legislative_turnout.fillna(0)
            aggregated["baseline_coverage"] = aggregated.matched_legislative_turnout / aggregated.total_legislative_turnout.where(
                aggregated.total_legislative_turnout.gt(0)
            )
            denominator = aggregated.baseline_dem_votes + aggregated.baseline_rep_votes
            aggregated["baseline_dem_margin"] = 100 * (
                aggregated.baseline_dem_votes - aggregated.baseline_rep_votes
            ) / denominator.where(denominator.gt(0))
            aggregated["state"], aggregated["year"], aggregated["chamber"] = "LA", 2019, chamber
            aggregated["baseline_office"] = office
            aggregated["baseline_source"] = f"RDH/VEST Louisiana 2019 {stage} {office} context; SOS contest membership"
            aggregated["baseline_class"] = "observed_same_cycle_ticket"
            aggregated["baseline_quality"] = np.where(
                aggregated.baseline_coverage.ge(0.95), "validated_coverage", "partial_coverage"
            )
            aggregated["baseline_priority"] = 2
            aggregated["baseline_source_path"] = rel(path_2019)
            aggregated["strict_baseline_eligible"] = aggregated.baseline_dem_margin.notna() & aggregated.baseline_coverage.ge(0.95)
            aggregated["research_baseline_eligible"] = aggregated.baseline_dem_margin.notna()
            baselines.append(aggregated)
            audits.append({
                "year": 2019, "election_stage": stage, "chamber": chamber,
                "districts": len(aggregated), "strict_districts": int(aggregated.strict_baseline_eligible.sum()),
                "matched_legislative_turnout": float(aggregated.matched_legislative_turnout.sum()),
                "total_legislative_turnout": float(aggregated.total_legislative_turnout.sum()),
                "match_rate": float(aggregated.matched_legislative_turnout.sum() / aggregated.total_legislative_turnout.sum()),
                "source_path": rel(path_2019),
            })

    keep = KEYS + [
        "baseline_dem_margin", "baseline_office", "baseline_source", "baseline_class", "baseline_quality",
        "baseline_priority", "baseline_coverage", "baseline_source_path", "strict_baseline_eligible",
        "research_baseline_eligible",
    ]
    return pd.concat([frame[keep] for frame in baselines], ignore_index=True), pd.DataFrame(audits)


def _medsl_clean(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame[
        frame.stage.eq("GEN")
        & ~frame.special.fillna(False)
        & (
            frame.party_simplified.isin(["DEMOCRAT", "REPUBLICAN"])
            | frame.office.isin(["STATE HOUSE", "STATE SENATE"])
        )
    ].copy()
    frame["votes"] = pd.to_numeric(frame.votes, errors="coerce")
    frame = frame.dropna(subset=["votes", "precinct"])
    frame["county_key"] = frame.county_fips.astype(str).str.replace(r"\.0$", "", regex=True)
    frame.loc[frame.county_fips.isna(), "county_key"] = frame.loc[frame.county_fips.isna(), "county_name"].astype(str).str.upper().str.strip()
    frame["precinct_key"] = frame.precinct.astype(str).str.upper().str.strip()
    dedupe = ["county_key", "precinct_key", "office", "district", "candidate", "party_simplified"]
    normalized_keys = frame[dedupe].astype("string").fillna("<NA>")
    row_hash = pd.util.hash_pandas_object(normalized_keys, index=False)
    total_row = frame["mode"].astype(str).str.upper().eq("TOTAL")
    total_hashes = set(row_hash[total_row].tolist())
    has_total = row_hash.isin(total_hashes)
    return frame[(~has_total) | total_row].copy()


def _medsl_state_frames() -> list[tuple[str, int, str, pd.DataFrame]]:
    base = RAW / "historical_statewide_elections"
    result: list[tuple[str, int, str, pd.DataFrame]] = []
    usecols = [
        "precinct", "office", "party_simplified", "mode", "votes", "county_name", "county_fips",
        "candidate", "district", "year", "stage", "special", "writein", "state_po",
        "state_postal", "party",
    ]

    # Prefer the smaller state-specific official-result archives when they are
    # present.  The acquisition manifest is the source contract: a file is not
    # admitted merely because a ZIP happens to exist under data/raw.
    manifest_path = base / "medsl_github/manifest.csv"
    if manifest_path.exists():
        manifest = pd.read_csv(manifest_path)
        required = {
            "state", "year", "local_path", "sha256", "validation_status",
            "ticket_major_parties_present",
        }
        if not required.issubset(manifest.columns):
            raise ValueError(f"MEDSL GitHub manifest missing columns: {sorted(required-set(manifest.columns))}")
        admitted = manifest[
            manifest.validation_status.eq("validated")
            & manifest.ticket_major_parties_present.astype("boolean").fillna(False)
        ].sort_values(["year", "state"])
        for row in admitted.itertuples():
            path = ROOT / str(row.local_path)
            if not path.exists():
                raise FileNotFoundError(f"Manifested MEDSL archive missing: {path}")
            if sha256(path) != str(row.sha256):
                raise ValueError(f"Manifested MEDSL archive hash mismatch: {path}")
            with ZipFile(path) as bundle:
                members = sorted(name for name in bundle.namelist() if name.lower().endswith(".csv"))
                if len(members) != 1:
                    raise ValueError(f"Expected one CSV in {path}, found {members}")
                frame = pd.read_csv(
                    bundle.open(members[0]), usecols=lambda column: column in usecols, low_memory=False
                )
            if "state_po" not in frame and "state_postal" in frame:
                frame["state_po"] = frame.state_postal
            if "party_simplified" not in frame:
                party = frame.get("party", pd.Series(index=frame.index, dtype=object)).fillna("").astype(str).str.upper()
                candidate = frame.candidate.fillna("").astype(str).str.upper()
                frame["party_simplified"] = np.select(
                    [party.str.contains("DEM") | candidate.str.contains("HILLARY CLINTON"),
                     party.str.contains("REP") | candidate.str.contains("DONALD TRUMP")],
                    ["DEMOCRAT", "REPUBLICAN"], default=party,
                )
            frame["office"] = frame.office.astype(str).str.upper()
            frame["stage"] = frame.stage.astype(str).str.upper()
            if not pd.api.types.is_bool_dtype(frame.special):
                frame["special"] = frame.special.astype(str).str.lower().isin(["true", "1", "yes"])
            result.append((str(row.state), int(row.year), rel(path), _medsl_clean(frame)))

    for archive_name, year in (("dataverse_files (3).zip", 2018), ("dataverse_files (2).zip", 2020)):
        path = base / archive_name
        with ZipFile(path) as bundle:
            members = {name.lower(): name for name in bundle.namelist()}
            for state in TARGET_STATES:
                suffix = f"{year}-{state.lower()}-precinct-general.csv"
                member = next((original for lower, original in members.items() if lower.endswith(suffix)), None)
                if member is None:
                    continue
                frame = pd.read_csv(bundle.open(member), usecols=lambda column: column in usecols, low_memory=False)
                result.append((state, year, rel(path), _medsl_clean(frame)))
    path = base / "dataverse_files (1).zip"
    with ZipFile(path) as bundle:
        frame = pd.read_csv(bundle.open("STATE_precinct_general.csv"), usecols=lambda column: column in usecols, low_memory=False)
    for state, state_frame in frame[frame.state_po.isin(TARGET_STATES)].groupby("state_po", sort=True):
        result.append((state, 2024, rel(path), _medsl_clean(state_frame)))
    return result


def build_medsl_observations(klarner: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    outcomes: list[pd.DataFrame] = []
    baselines: list[pd.DataFrame] = []
    audit: list[dict[str, object]] = []
    priority = {
        2016: ["US PRESIDENT", "US SENATE", "GOVERNOR", "US HOUSE"],
        2018: ["US SENATE", "GOVERNOR", "US HOUSE"],
        2020: ["US PRESIDENT", "US SENATE", "GOVERNOR", "US HOUSE"],
        2022: ["US SENATE", "GOVERNOR", "US HOUSE"],
        2024: ["US PRESIDENT", "US SENATE", "GOVERNOR", "US HOUSE"],
    }
    for state, year, source_path, frame in _medsl_state_frames():
        if state == "KY" and year == 2016:
            if klarner is None:
                klarner = load_klarner_universe()
            lookup: dict[tuple[str, int, str], str] = {}
            prior = klarner[klarner.state.eq("KY") & klarner.year.eq(2016)]
            for row in prior.itertuples():
                if pd.notna(row.dem_candidate):
                    lookup[(row.chamber, int(row.district), normalized_name(row.dem_candidate))] = "DEMOCRAT"
                if pd.notna(row.rep_candidate):
                    lookup[(row.chamber, int(row.district), normalized_name(row.rep_candidate))] = "REPUBLICAN"
            unresolved = (
                frame.office.isin(["STATE HOUSE", "STATE SENATE"])
                & ~frame.party_simplified.isin(["DEMOCRAT", "REPUBLICAN"])
            )
            for index, row in frame[unresolved].iterrows():
                chamber = {"STATE HOUSE": "house", "STATE SENATE": "senate"}[row.office]
                district = pd.to_numeric(row.district, errors="coerce")
                if pd.notna(district):
                    frame.at[index, "party_simplified"] = lookup.get(
                        (chamber, int(district), normalized_name(row.candidate)), row.party_simplified
                    )
        legislative = frame[frame.office.isin(["STATE HOUSE", "STATE SENATE"]) & frame.district.notna()].copy()
        if legislative.empty:
            audit.append({"state": state, "year": year, "status": "no_legislative_rows", "source_path": source_path})
            continue
        legislative["chamber"] = legislative.office.map({"STATE HOUSE": "house", "STATE SENATE": "senate"})
        legislative["district_number"] = standard_district(legislative.district)
        legislative = legislative.dropna(subset=["district_number"])
        group = ["county_key", "precinct_key", "chamber", "district_number", "party_simplified"]
        party = legislative.groupby(group, dropna=False).votes.sum().unstack(fill_value=0).reset_index()
        turnout = legislative.groupby(
            ["county_key", "precinct_key", "chamber", "district_number"], dropna=False, as_index=False
        ).votes.sum().rename(columns={"votes": "all_candidate_turnout"})
        party = party.merge(
            turnout, on=["county_key", "precinct_key", "chamber", "district_number"],
            how="left", validate="one_to_one",
        )
        for label in ("DEMOCRAT", "REPUBLICAN"):
            if label not in party:
                party[label] = 0.0
        party["legislative_turnout"] = party.all_candidate_turnout
        district_outcome = party.groupby(["chamber", "district_number"], as_index=False)[["DEMOCRAT", "REPUBLICAN"]].sum()
        district_outcome = district_outcome[
            district_outcome.DEMOCRAT.gt(0) & district_outcome.REPUBLICAN.gt(0)
        ].copy()
        if not district_outcome.empty:
            candidates = (
                legislative.groupby(["chamber", "district_number", "party_simplified", "candidate"], dropna=False).votes.sum()
                .reset_index().sort_values("votes", ascending=False)
                .drop_duplicates(["chamber", "district_number", "party_simplified"])
                .pivot(index=["chamber", "district_number"], columns="party_simplified", values="candidate").reset_index()
                .rename(columns={"DEMOCRAT": "dem_candidate", "REPUBLICAN": "rep_candidate"})
            )
            district_outcome = district_outcome.merge(candidates, on=["chamber", "district_number"], how="left", validate="one_to_one")
            district_outcome = district_outcome.rename(columns={"district_number": "district", "DEMOCRAT": "dem_votes", "REPUBLICAN": "rep_votes"})
            district_outcome["state"], district_outcome["year"] = state, year
            denominator = district_outcome.dem_votes + district_outcome.rep_votes
            district_outcome["legislative_dem_margin"] = 100 * (district_outcome.dem_votes - district_outcome.rep_votes) / denominator
            district_outcome["outcome_eligible"] = True
            district_outcome["outcome_source"] = f"MEDSL {year} precinct general returns"
            district_outcome["outcome_source_path"] = source_path
            district_outcome["candidate_source"] = f"MEDSL {year} precinct general returns"
            outcomes.append(district_outcome)

        selected_office = None
        for office in priority[year]:
            office_rows = frame[frame.office.eq(office)]
            totals = office_rows.groupby("party_simplified").votes.sum()
            if totals.get("DEMOCRAT", 0) > 0 and totals.get("REPUBLICAN", 0) > 0:
                selected_office = office
                break
        if selected_office is None:
            audit.append({"state": state, "year": year, "status": "no_two_party_ticket_context", "source_path": source_path})
            continue
        context = frame[frame.office.eq(selected_office)].groupby(
            ["county_key", "precinct_key", "party_simplified"], dropna=False
        ).votes.sum().unstack(fill_value=0).reset_index()
        for label in ("DEMOCRAT", "REPUBLICAN"):
            if label not in context:
                context[label] = 0.0
        precinct_chamber = ["county_key", "precinct_key", "chamber"]
        party["precinct_chamber_turnout"] = party.groupby(precinct_chamber).legislative_turnout.transform("sum")
        party["allocation_weight"] = party.legislative_turnout / party.precinct_chamber_turnout.where(
            party.precinct_chamber_turnout.gt(0)
        )
        party.loc[party.groupby(precinct_chamber).district_number.transform("size").eq(1), "allocation_weight"] = 1.0
        joined = party.merge(context, on=["county_key", "precinct_key"], how="left", suffixes=("_leg", "_context"), validate="many_to_one")
        joined["context_present"] = joined.DEMOCRAT_context.notna() & joined.REPUBLICAN_context.notna()
        joined["allocated_dem_votes"] = joined.DEMOCRAT_context * joined.allocation_weight
        joined["allocated_rep_votes"] = joined.REPUBLICAN_context * joined.allocation_weight
        joined["matched_legislative_turnout"] = joined.legislative_turnout.where(joined.context_present, 0)
        aggregated = joined.groupby(["chamber", "district_number"], as_index=False).agg(
            baseline_dem_votes=("allocated_dem_votes", lambda values: values.sum(min_count=1)),
            baseline_rep_votes=("allocated_rep_votes", lambda values: values.sum(min_count=1)),
            legislative_turnout=("legislative_turnout", "sum"),
            matched_legislative_turnout=("matched_legislative_turnout", "sum"),
            split_precinct_fragments=("allocation_weight", lambda values: int(((values > 0) & (values < 1)).sum())),
        )
        aggregated["baseline_coverage"] = aggregated.matched_legislative_turnout / aggregated.legislative_turnout.where(
            aggregated.legislative_turnout.gt(0)
        )
        denominator = aggregated.baseline_dem_votes + aggregated.baseline_rep_votes
        aggregated["baseline_dem_margin"] = 100 * (
            aggregated.baseline_dem_votes - aggregated.baseline_rep_votes
        ) / denominator.where(denominator > 0)
        aggregated = aggregated.rename(columns={"district_number": "district"})
        aggregated["state"], aggregated["year"] = state, year
        aggregated["baseline_office"] = selected_office
        aggregated["baseline_source"] = f"MEDSL ballot-first {selected_office} context"
        aggregated["baseline_class"] = "observed_same_cycle_ticket"
        aggregated["baseline_quality"] = np.where(aggregated.baseline_coverage.ge(0.95), "validated_coverage", "partial_coverage")
        aggregated["baseline_priority"] = 2
        aggregated["baseline_source_path"] = source_path
        aggregated["strict_baseline_eligible"] = aggregated.baseline_dem_margin.notna() & aggregated.baseline_coverage.ge(0.95)
        aggregated["research_baseline_eligible"] = aggregated.baseline_dem_margin.notna()
        baselines.append(aggregated)
        audit.append({
            "state": state, "year": year, "status": "processed", "source_path": source_path,
            "selected_office": selected_office, "legislative_districts": len(district_outcome),
            "baseline_districts": len(aggregated), "strict_baselines": int(aggregated.strict_baseline_eligible.sum()),
        })
    return (
        pd.concat(outcomes, ignore_index=True) if outcomes else pd.DataFrame(),
        pd.concat(baselines, ignore_index=True) if baselines else pd.DataFrame(),
        pd.DataFrame(audit),
    )


def allocate_long_ticket_baselines(
    frame: pd.DataFrame, state: str, year: int, source_path: Path, provider_label: str,
    ticket_office: str = "US PRESIDENT",
) -> pd.DataFrame:
    """Allocate a D/R ticket contest to legislative district fragments.

    Input is one row per precinct/candidate with canonical ``ticket``,
    ``house``, or ``senate`` office labels.  Same-precinct district splits use
    observed legislative two-party turnout and report that match coverage.
    """
    required = {"county_key", "precinct_key", "office", "district", "party", "votes"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Long ticket input missing columns: {sorted(required-set(frame.columns))}")
    data = frame.copy()
    data["votes"] = pd.to_numeric(data.votes, errors="coerce")
    data = data[data.party.isin(["D", "R"]) & data.votes.notna()].copy()
    context = data[data.office.eq("ticket")].groupby(
        ["county_key", "precinct_key", "party"], dropna=False
    ).votes.sum().unstack(fill_value=0).reset_index()
    for label in ("D", "R"):
        if label not in context:
            context[label] = 0.0
    outputs: list[pd.DataFrame] = []
    for chamber in ("house", "senate"):
        legislative = data[data.office.eq(chamber) & data.district.notna()].copy()
        if legislative.empty:
            continue
        legislative["district"] = standard_district(legislative.district)
        party = legislative.groupby(
            ["county_key", "precinct_key", "district", "party"], dropna=False
        ).votes.sum().unstack(fill_value=0).reset_index()
        for label in ("D", "R"):
            if label not in party:
                party[label] = 0.0
        party["legislative_turnout"] = party.D + party.R
        precinct = ["county_key", "precinct_key"]
        party["precinct_turnout"] = party.groupby(precinct).legislative_turnout.transform("sum")
        party["weight"] = party.legislative_turnout / party.precinct_turnout.where(party.precinct_turnout.gt(0))
        party.loc[party.groupby(precinct).district.transform("size").eq(1), "weight"] = 1.0
        joined = party.merge(context, on=precinct, how="left", suffixes=("_leg", "_ticket"), validate="many_to_one")
        joined["context_present"] = joined.D_ticket.notna() & joined.R_ticket.notna()
        joined["allocated_dem"] = joined.D_ticket * joined.weight
        joined["allocated_rep"] = joined.R_ticket * joined.weight
        joined["matched_turnout"] = joined.legislative_turnout.where(joined.context_present, 0)
        agg = joined.groupby("district", as_index=False).agg(
            baseline_dem_votes=("allocated_dem", lambda values: values.sum(min_count=1)),
            baseline_rep_votes=("allocated_rep", lambda values: values.sum(min_count=1)),
            legislative_turnout=("legislative_turnout", "sum"),
            matched_turnout=("matched_turnout", "sum"),
        )
        denominator = agg.baseline_dem_votes + agg.baseline_rep_votes
        agg["baseline_dem_margin"] = 100 * (agg.baseline_dem_votes-agg.baseline_rep_votes) / denominator.where(denominator.gt(0))
        agg["baseline_coverage"] = agg.matched_turnout / agg.legislative_turnout.where(agg.legislative_turnout.gt(0))
        agg["state"], agg["year"], agg["chamber"] = state, year, chamber
        agg["baseline_office"] = ticket_office
        agg["baseline_source"] = f"{provider_label} ballot-first presidential context"
        agg["baseline_class"] = "observed_same_cycle_ticket"
        agg["baseline_quality"] = np.where(agg.baseline_coverage.ge(0.95), "validated_coverage", "partial_coverage")
        agg["baseline_priority"] = 2
        agg["baseline_source_path"] = rel(source_path)
        agg["strict_baseline_eligible"] = agg.baseline_dem_margin.notna() & agg.baseline_coverage.ge(0.95)
        agg["research_baseline_eligible"] = agg.baseline_dem_margin.notna()
        outputs.append(agg)
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()


def allocate_wide_ticket_baselines(
    frame: pd.DataFrame,
    state: str,
    year: int,
    source_path: Path,
    provider_label: str,
    ticket_dem_column: str,
    ticket_rep_column: str,
    ticket_office: str,
) -> pd.DataFrame:
    """Allocate wide precinct ticket totals using observed legislative turnout.

    RDH/VEST packages keep one column per candidate. A precinct can contain
    votes for more than one legislative district after a district split, so
    the ticket vote is apportioned by the observed all-candidate legislative
    turnout in each district fragment. This is the same ballot-first rule used
    for canonical long-form inputs and avoids duplicating statewide votes.
    """
    if ticket_dem_column not in frame or ticket_rep_column not in frame:
        raise ValueError(
            f"{state} {year} wide ticket columns missing: "
            f"{ticket_dem_column}, {ticket_rep_column}"
        )
    data = frame.copy().reset_index(drop=True)
    data["row_number"] = data.index
    data["ticket_dem_votes"] = pd.to_numeric(data[ticket_dem_column], errors="coerce").fillna(0)
    data["ticket_rep_votes"] = pd.to_numeric(data[ticket_rep_column], errors="coerce").fillna(0)
    outputs: list[pd.DataFrame] = []
    for chamber, prefix, digits in (("house", "GSL", "2,3"), ("senate", "GSU", "1,2")):
        pattern = re.compile(rf"^{prefix}(\d{{{digits}}})[A-Z]")
        district_columns: dict[str, list[str]] = {}
        for column in data.columns:
            match = pattern.match(str(column))
            if match:
                district_columns.setdefault(str(int(match.group(1))), []).append(column)
        fragments = []
        for district, columns in district_columns.items():
            turnout = data[columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
            present = turnout.gt(0)
            if present.any():
                fragments.append(pd.DataFrame({
                    "row_number": data.loc[present, "row_number"],
                    "district": district,
                    "legislative_turnout": turnout[present],
                }))
        if not fragments:
            continue
        fragment = pd.concat(fragments, ignore_index=True)
        fragment["precinct_turnout"] = fragment.groupby("row_number").legislative_turnout.transform("sum")
        fragment["weight"] = fragment.legislative_turnout / fragment.precinct_turnout.where(
            fragment.precinct_turnout.gt(0)
        )
        fragment["baseline_dem_votes"] = (
            fragment.row_number.map(data.set_index("row_number").ticket_dem_votes) * fragment.weight
        )
        fragment["baseline_rep_votes"] = (
            fragment.row_number.map(data.set_index("row_number").ticket_rep_votes) * fragment.weight
        )
        covered_rows = set(fragment.row_number)
        total_ticket = float((data.ticket_dem_votes + data.ticket_rep_votes).sum())
        covered_ticket = float(
            data.loc[data.row_number.isin(covered_rows), ["ticket_dem_votes", "ticket_rep_votes"]].sum().sum()
        )
        coverage = covered_ticket / total_ticket if total_ticket > 0 else np.nan
        aggregate = fragment.groupby("district", as_index=False).agg(
            baseline_dem_votes=("baseline_dem_votes", "sum"),
            baseline_rep_votes=("baseline_rep_votes", "sum"),
            legislative_turnout=("legislative_turnout", "sum"),
        )
        denominator = aggregate.baseline_dem_votes + aggregate.baseline_rep_votes
        aggregate["baseline_dem_margin"] = 100 * (
            aggregate.baseline_dem_votes-aggregate.baseline_rep_votes
        ) / denominator.where(denominator.gt(0))
        aggregate["state"], aggregate["year"], aggregate["chamber"] = state, year, chamber
        aggregate["baseline_office"] = ticket_office
        aggregate["baseline_source"] = f"{provider_label} ballot-first {ticket_office.lower()} context"
        aggregate["baseline_class"] = "observed_same_cycle_ticket"
        aggregate["baseline_coverage"] = coverage
        aggregate["baseline_quality"] = (
            "validated_coverage" if pd.notna(coverage) and coverage >= 0.95 else "partial_coverage"
        )
        aggregate["baseline_priority"] = 2
        aggregate["baseline_source_path"] = rel(source_path)
        aggregate["strict_baseline_eligible"] = (
            aggregate.baseline_dem_margin.notna() & aggregate.baseline_coverage.ge(0.95)
        )
        aggregate["research_baseline_eligible"] = aggregate.baseline_dem_margin.notna()
        outputs.append(aggregate)
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()


def load_arkansas_2022_baselines() -> pd.DataFrame:
    """Normalize the already-downloaded official/OpenElections Arkansas files."""
    directory = RAW / "historical_statewide_elections/arkansas_2022_openelections/counties"
    files = sorted(directory.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No Arkansas 2022 precinct files under {directory}")
    source = pd.concat([pd.read_csv(path, low_memory=False) for path in files], ignore_index=True)
    office = source.office.fillna("").astype(str)
    source["canonical_office"] = np.select(
        [office.eq("U.S. Senate"), office.eq("State House"), office.eq("State Senate")],
        ["ticket", "house", "senate"], default=None,
    )
    party = source.party.fillna("").astype(str).str.upper()
    source["canonical_party"] = np.select(
        [party.eq("D") | party.str.startswith("DEM"), party.eq("R") | party.str.startswith("REP")],
        ["D", "R"], default=None,
    )
    legislative_unknown = source.canonical_office.isin(["house", "senate"]) & source.canonical_party.isna()
    source.loc[legislative_unknown, "canonical_party"] = "D"
    long = pd.DataFrame({
        "county_key": source.county.astype(str).str.upper().str.strip(),
        "precinct_key": source.precinct.astype(str).str.upper().str.strip(),
        "office": source.canonical_office,
        "district": source.district,
        "party": source.canonical_party,
        "votes": source.votes,
    })
    return allocate_long_ticket_baselines(
        long, "AR", 2022, directory,
        "Arkansas Secretary of State files normalized by OpenElections", "US SENATE",
    )


def load_georgia_tennessee_2022_2024_baselines() -> pd.DataFrame:
    """Decode local RDH/VEST wide packages for the remaining modern gaps."""
    import geopandas as gpd

    outputs: list[pd.DataFrame] = []
    ga_2022 = RAW / "historical_statewide_elections/ga_2022_gen_prec.zip"
    ga_2022_frame = gpd.read_file(
        f"zip://{ga_2022.resolve()}!ga_2022_gen_prec_no_splits/ga_2022_gen_prec_no_splits.shp",
        ignore_geometry=True,
    )
    outputs.append(allocate_wide_ticket_baselines(
        ga_2022_frame, "GA", 2022, ga_2022,
        "RDH/VEST Georgia 2022 precinct package", "G22USSDWAR", "G22USSRWAL", "US SENATE",
    ))

    ga_2024 = RAW / "historical_statewide_elections/ga_2024_gen_prec_csv.zip"
    with ZipFile(ga_2024) as bundle:
        member = next(name for name in bundle.namelist() if name.lower().endswith(".csv"))
        ga_2024_frame = pd.read_csv(bundle.open(member), low_memory=False)
    outputs.append(allocate_wide_ticket_baselines(
        ga_2024_frame, "GA", 2024, ga_2024,
        "RDH/VEST Georgia 2024 precinct package", "G24PREDHAR", "G24PRERTRU", "US PRESIDENT",
    ))

    tn_2022 = RAW / "historical_statewide_elections/tn_2022_gen_prec.zip"
    tn_2022_frame = gpd.read_file(
        f"zip://{tn_2022.resolve()}!tn_2022_gen_all_prec/tn_2022_gen_all_prec.shp",
        ignore_geometry=True,
    )
    tn_wide = allocate_wide_ticket_baselines(
        tn_2022_frame, "TN", 2022, tn_2022,
        "RDH/VEST Tennessee 2022 precinct package", "G22GOVDMAR", "G22GOVRLEE", "GOVERNOR",
    )
    # Every precinct row retained for the staggered upper-chamber contests
    # declares its upper-district membership. Use that authoritative field
    # instead of treating the unelected half of the chamber as unmatched
    # legislative turnout in the statewide coverage denominator.
    tn_house = tn_wide[tn_wide.chamber.eq("house")].copy()
    tn_senate = tn_2022_frame.copy()
    tn_senate["district"] = standard_district(tn_senate.SLDU_DIST)
    tn_senate["baseline_dem_votes"] = pd.to_numeric(tn_senate.G22GOVDMAR, errors="coerce").fillna(0)
    tn_senate["baseline_rep_votes"] = pd.to_numeric(tn_senate.G22GOVRLEE, errors="coerce").fillna(0)
    tn_senate = tn_senate.groupby("district", as_index=False)[
        ["baseline_dem_votes", "baseline_rep_votes"]
    ].sum()
    denominator = tn_senate.baseline_dem_votes + tn_senate.baseline_rep_votes
    tn_senate["baseline_dem_margin"] = 100 * (
        tn_senate.baseline_dem_votes-tn_senate.baseline_rep_votes
    ) / denominator.where(denominator.gt(0))
    tn_senate["state"], tn_senate["year"], tn_senate["chamber"] = "TN", 2022, "senate"
    tn_senate["baseline_office"] = "GOVERNOR"
    tn_senate["baseline_source"] = "RDH/VEST Tennessee 2022 declared upper-district membership"
    tn_senate["baseline_class"] = "observed_same_cycle_ticket"
    tn_senate["baseline_coverage"] = 1.0
    tn_senate["baseline_quality"] = "official_results_validated_district_membership"
    tn_senate["baseline_priority"] = 2
    tn_senate["baseline_source_path"] = rel(tn_2022)
    tn_senate["strict_baseline_eligible"] = tn_senate.baseline_dem_margin.notna()
    tn_senate["research_baseline_eligible"] = tn_senate.baseline_dem_margin.notna()
    outputs.extend([tn_house, tn_senate])
    return pd.concat(outputs, ignore_index=True)


def load_official_long_ticket_baselines() -> pd.DataFrame:
    """Normalize already-downloaded official 2016/2022/2024 long-form files."""
    outputs: list[pd.DataFrame] = []

    florida_paths = {
        2016: RAW / "southern_sos_elections/FL/2016/precinctlevelelectionresults2016gen.zip",
        2018: RAW / "historical_statewide_elections/precinctlevelelectionresults2018gen.zip",
        2022: RAW / "historical_statewide_elections/2022-gen-outputofficial.zip",
        2024: RAW / "historical_statewide_elections/2024-gen-outputofficial1.zip",
    }
    for year, path in florida_paths.items():
        rows = []
        with ZipFile(path) as bundle:
            for member in bundle.namelist():
                if not member.lower().endswith(".txt"):
                    continue
                text = bundle.read(member).decode("utf-8-sig", errors="replace").replace("\x00", "")
                for fields in csv.reader(io.StringIO(text), delimiter="\t"):
                    if len(fields) < 19:
                        continue
                    office_text = fields[11].upper()
                    office = "ticket" if (
                        "PRESIDENT" in office_text or (year in {2018, 2022} and "UNITED STATES SENATOR" in office_text)
                    ) else (
                        "house" if "STATE REPRESENTATIVE" in office_text else
                        "senate" if "STATE SENATOR" in office_text else None
                    )
                    if office is None:
                        continue
                    district_match = re.search(r"(\d+)", fields[12])
                    party = {"DEM": "D", "REP": "R"}.get(fields[15].strip().upper())
                    rows.append({
                        "county_key": fields[0].strip().upper(), "precinct_key": fields[5].strip().upper(),
                        "office": office, "district": int(district_match.group()) if district_match else np.nan,
                        "party": party, "votes": fields[18],
                    })
        outputs.append(allocate_long_ticket_baselines(
            pd.DataFrame(rows), "FL", year, path, "Florida Division of Elections",
            "US SENATE" if year in {2018, 2022} else "US PRESIDENT",
        ))

    nc_paths = {
        2016: RAW / "southern_sos_elections/NC/2016/results_pct_20161108.zip",
        2022: RAW / "historical_statewide_elections/results_pct_20221108.zip",
    }
    for year, path in nc_paths.items():
        with ZipFile(path) as bundle:
            member = next(name for name in bundle.namelist() if not name.endswith("/"))
            frame = pd.read_csv(bundle.open(member), sep="\t", low_memory=False)
        contest = frame["Contest Name"].fillna("").astype(str).str.upper()
        frame["office"] = np.select(
            [contest.eq("US PRESIDENT") | ((year == 2022) & contest.eq("US SENATE")),
             contest.str.startswith("NC HOUSE OF REPRESENTATIVES DISTRICT"),
             contest.str.startswith("NC STATE SENATE DISTRICT")],
            ["ticket", "house", "senate"], default=None,
        )
        frame["district"] = standard_district(contest.str.extract(r"DISTRICT\s+(\d+)", expand=False))
        frame["party"] = frame["Choice Party"].map({"DEM": "D", "REP": "R"})
        long = pd.DataFrame({
            "county_key": frame.County.astype(str).str.upper().str.strip(),
            "precinct_key": frame.Precinct.astype(str).str.upper().str.strip(),
            "office": frame.office, "district": frame.district, "party": frame.party,
            "votes": frame["Total Votes"],
        })
        outputs.append(allocate_long_ticket_baselines(
            long, "NC", year, path, "North Carolina State Board of Elections",
            "US SENATE" if year == 2022 else "US PRESIDENT",
        ))

    ok_path = RAW / "southern_sos_elections/OK/2016/20161108_PrecinctResults_csv_2d9b372099d6.zip"
    ok_rows = []
    with ZipFile(ok_path) as bundle:
        member = next(name for name in bundle.namelist() if name.lower().endswith(".csv"))
        stream = io.TextIOWrapper(bundle.open(member), encoding="utf-8-sig", errors="replace", newline="")
        for record in csv.DictReader(stream):
            office_text = str(record.get("race_description", "")).upper()
            office = "ticket" if "PRESIDENT AND VICE PRESIDENT" in office_text else (
                "house" if "STATE REPRESENTATIVE DISTRICT" in office_text else
                "senate" if "STATE SENATOR DISTRICT" in office_text else None
            )
            if office is None:
                continue
            district_match = re.search(r"DISTRICT\s+(\d+)", office_text)
            ok_rows.append({
                "county_key": str(record.get("precinct", ""))[:2], "precinct_key": record.get("precinct"),
                "office": office, "district": int(district_match.group(1)) if district_match else np.nan,
                "party": {"DEM": "D", "REP": "R"}.get(str(record.get("cand_party", "")).upper()),
                "votes": record.get("cand_tot_votes"),
            })
    outputs.append(allocate_long_ticket_baselines(pd.DataFrame(ok_rows), "OK", 2016, ok_path, "Oklahoma State Election Board"))

    tn_path = RAW / "southern_sos_elections/TN/2016/StateGeneralbyPrecinctNov2016.xlsx"
    source = pd.read_excel(tn_path, sheet_name=0, dtype=object)
    tn_rows = []
    for record in source.to_dict("records"):
        office_text = str(record.get("OFFICENAME", ""))
        upper = office_text.upper()
        office = "ticket" if upper == "UNITED STATES PRESIDENT" else (
            "house" if upper.startswith("TENNESSEE HOUSE OF REPRESENTATIVES DISTRICT") else
            "senate" if upper.startswith("TENNESSEE SENATE DISTRICT") else None
        )
        if office is None:
            continue
        district_match = re.search(r"DISTRICT\s+(\d+)", upper)
        for number in range(1, 11):
            name = record.get(f"RNAME{number}")
            if pd.isna(name):
                continue
            tn_rows.append({
                "county_key": str(record.get("COUNTY", "")).upper(),
                "precinct_key": str(record.get("PRCTSEQ", record.get("PRECINCT", ""))).upper(),
                "office": office, "district": int(district_match.group(1)) if district_match else np.nan,
                "party": {"D": "D", "DEM": "D", "DEMOCRATIC": "D", "R": "R", "REP": "R", "REPUBLICAN": "R"}.get(
                    str(record.get(f"PARTY{number}", "")).strip().upper()
                ),
                "votes": record.get(f"PVTALLY{number}"),
            })
    outputs.append(allocate_long_ticket_baselines(pd.DataFrame(tn_rows), "TN", 2016, tn_path, "Tennessee Secretary of State"))

    ar_path = RAW / "southern_sos_elections/AR/2016/2016_FullDataFile.json"
    payload = json.loads(ar_path.read_text(encoding="utf-8-sig"))
    ar_rows = []
    for contest in payload["ContestData"]:
        office_text = str(contest.get("ContestName", ""))
        upper = office_text.upper()
        office = "ticket" if upper == "U.S. PRESIDENT & VICE PRESIDENT" else (
            "house" if upper.startswith("STATE REPRESENTATIVE DISTRICT") else
            "senate" if upper.startswith("STATE SENATE DISTRICT") else None
        )
        if office is None:
            continue
        district_match = re.search(r"DISTRICT\s+(\d+)", upper)
        for county in contest.get("Counties", []):
            for precinct in county.get("Precincts", []):
                for candidate in precinct.get("Candidates", []):
                    party_text = str(candidate.get("PartyName", "")).upper()
                    ar_rows.append({
                        "county_key": str(county.get("CountyName", "")).upper(),
                        "precinct_key": str(precinct.get("PrecinctName", "")).upper(),
                        "office": office, "district": int(district_match.group(1)) if district_match else np.nan,
                        "party": "D" if "DEMOCRAT" in party_text else "R" if "REPUBLICAN" in party_text else None,
                        "votes": candidate.get("TotalVotes"),
                    })
    outputs.append(allocate_long_ticket_baselines(pd.DataFrame(ar_rows), "AR", 2016, ar_path, "Arkansas Secretary of State"))
    return pd.concat([frame for frame in outputs if not frame.empty], ignore_index=True)


def load_south_carolina_2016_baselines() -> pd.DataFrame:
    """Parse the official county fixed-width detail exports at precinct grain."""
    directory = RAW / "southern_sos_elections/SC/2016"
    rows: list[dict[str, object]] = []
    for path in sorted(directory.glob("*_detailtxt.zip")):
        county_key = path.name.removesuffix("_detailtxt.zip").upper()
        with ZipFile(path) as bundle:
            member = next(name for name in bundle.namelist() if not name.endswith("/"))
            lines = bundle.read(member).decode("utf-8-sig", errors="replace").splitlines()
        index = 0
        while index < len(lines):
            title = lines[index].strip()
            upper = title.upper()
            normalized_title = re.sub(r"\s+", " ", upper)
            office = "ticket" if normalized_title.startswith("PRESIDENT AND VICE PRESIDENT") else (
                "house" if normalized_title.startswith("STATE HOUSE OF REPRESENTATIVES, DISTRICT") else
                "senate" if normalized_title.startswith("STATE SENATE, DISTRICT") else None
            )
            if office is None or "(VOTE FOR" not in normalized_title:
                index += 1
                continue
            district_match = re.search(r"DISTRICT\s+(\d+)", normalized_title)
            candidate_index = index + 1
            while candidate_index < len(lines) and not lines[candidate_index].strip():
                candidate_index += 1
            header_index = candidate_index + 1
            while header_index < len(lines) and not lines[header_index].strip().startswith("Precinct"):
                header_index += 1
            candidates = [
                lines[candidate_index][start:start+60].strip()
                for start in range(60, len(lines[candidate_index]), 60)
            ]
            candidates = [candidate for candidate in candidates if candidate]
            row_index = header_index + 1
            while row_index < len(lines) and not lines[row_index].strip().startswith("Totals:"):
                cells = [lines[row_index][start:start+30].strip() for start in range(0, len(lines[row_index]), 30)]
                precinct = cells[0] if cells else ""
                if precinct and precinct.upper() not in {"TOTAL", "TOTALS"}:
                    for position, candidate in enumerate(candidates):
                        vote_index = 3 + 2*position
                        votes = pd.to_numeric(cells[vote_index] if vote_index < len(cells) else None, errors="coerce")
                        if pd.isna(votes):
                            continue
                        if office == "ticket":
                            name = candidate.upper()
                            party = "D" if "CLINTON" in name else "R" if "TRUMP" in name else None
                        else:
                            # Party labels are absent, but total legislative
                            # turnout is all the allocator needs for membership.
                            party = "D"
                        rows.append({
                            "county_key": county_key, "precinct_key": precinct.upper(), "office": office,
                            "district": int(district_match.group(1)) if district_match else np.nan,
                            "party": party, "votes": votes,
                        })
                row_index += 1
            index = max(index+1, row_index+1)
    return allocate_long_ticket_baselines(
        pd.DataFrame(rows), "SC", 2016, directory,
        "South Carolina Election Commission county detail exports",
    )


def load_openelections_gap_baselines() -> pd.DataFrame:
    """Use commit-pinned OpenElections normalizations for two isolated gaps."""
    specs = [
        ("GA", 2016, RAW / "openelections_historical_gaps/GA/2016", "President of the United States"),
        ("MO", 2018, RAW / "openelections_historical_gaps/MO/2018", "U.S. Senate"),
        ("SC", 2020, RAW / "openelections_historical_gaps/SC/2020", "President"),
    ]
    outputs = []
    for state, year, directory, ticket_name in specs:
        files = sorted(directory.glob("*.csv"))
        if not files:
            raise FileNotFoundError(f"No commit-pinned OpenElections inputs under {directory}")
        source = pd.concat([pd.read_csv(path, low_memory=False) for path in files], ignore_index=True)
        office_text = source.office.fillna("").astype(str)
        source["canonical_office"] = np.select(
            [office_text.eq(ticket_name), office_text.isin(["State Representative", "State House"]),
             office_text.isin(["State Senator", "State Senate"])],
            ["ticket", "house", "senate"], default=None,
        )
        party = source.party.fillna("").astype(str).str.upper()
        candidate = source.candidate.fillna("").astype(str).str.upper()
        source["canonical_party"] = np.select(
            [party.str.contains("DEM") | candidate.str.contains("CLINTON"),
             party.str.contains("REP") | candidate.str.contains("TRUMP")],
            ["D", "R"], default=None,
        )
        legislative_unknown = (
            source.canonical_office.isin(["house", "senate"])
            & pd.Series(source.canonical_party, index=source.index).isna()
        )
        source.loc[legislative_unknown, "canonical_party"] = "D"
        long = pd.DataFrame({
            "county_key": source.county.astype(str).str.upper().str.strip(),
            "precinct_key": source.precinct.astype(str).str.upper().str.strip(),
            "office": source.canonical_office,
            "district": source.district,
            "party": source.canonical_party,
            "votes": source.votes,
        })
        outputs.append(allocate_long_ticket_baselines(
            long, state, year, directory, "Commit-pinned OpenElections normalization",
            "US SENATE" if (state, year) == ("MO", 2018) else "US PRESIDENT",
        ))
    return pd.concat(outputs, ignore_index=True)


def load_existing_baselines() -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    strict_path = CAL / "historical_southern_extended_v2_panel.csv"
    strict = pd.read_csv(strict_path, low_memory=False)
    strict = strict[strict.model_eligible.eq(True) & strict.state.ne("AL")].copy()
    strict["baseline_office"] = strict.get("baseline_office", pd.Series(index=strict.index, dtype=object)).fillna(strict.office)
    strict["baseline_source"] = strict.panel_source.astype(str) + "; " + strict.baseline_source.astype(str)
    strict["baseline_class"] = "validated_observed_ticket"
    strict["baseline_quality"] = strict.baseline_allocation_quality
    strict["baseline_priority"] = 3
    strict["baseline_coverage"] = 1.0
    strict["baseline_source_path"] = rel(strict_path)
    strict["strict_baseline_eligible"] = True
    strict["research_baseline_eligible"] = True
    rows.append(strict)

    heda_path = CAL / "historical_southern_heda_panel.csv"
    heda = pd.read_csv(heda_path, low_memory=False)
    la = heda[
        heda.state.eq("LA") & heda.year.isin([2003, 2007])
        & heda.baseline_dem_margin.notna() & heda.incomplete_context_groups.fillna(0).eq(0)
    ].copy()
    la["baseline_office"] = la.office
    la["baseline_class"] = "validated_observed_ticket"
    la["baseline_quality"] = la.baseline_allocation_quality
    la["baseline_priority"] = 3
    la["baseline_coverage"] = 1.0
    la["baseline_source_path"] = rel(heda_path)
    la["strict_baseline_eligible"] = True
    la["research_baseline_eligible"] = True
    rows.append(la)

    heda = heda[heda.model_eligible_permissive.eq(True) & ~heda.model_eligible.eq(True) & heda.state.ne("AL")].copy()
    heda["baseline_office"] = heda.office
    heda["baseline_class"] = "partial_observed_ticket"
    heda["baseline_quality"] = "partial_unresolved_allocation"
    heda["baseline_priority"] = 4
    heda["baseline_coverage"] = np.nan
    heda["baseline_source_path"] = rel(heda_path)
    heda["strict_baseline_eligible"] = False
    heda["research_baseline_eligible"] = True
    rows.append(heda)

    synthetic_path = CAL / "southern_legislative_probability_panel.csv"
    synthetic = pd.read_csv(synthetic_path, low_memory=False)
    synthetic = synthetic[synthetic.environment_baseline_margin.notna()].copy()
    synthetic["chamber"] = synthetic.chamber.map(standard_chamber)
    synthetic["district"] = standard_district(synthetic.district)
    synthetic["baseline_dem_margin"] = synthetic.environment_baseline_margin
    synthetic["baseline_office"] = "PRIOR_PRESIDENTIAL_PLUS_NATIONAL_SWING"
    synthetic["baseline_source"] = synthetic.presidential_source.astype(str) + "; realized national swing"
    synthetic["baseline_class"] = "synthetic_environment"
    synthetic["baseline_quality"] = "probability_calibration_only"
    synthetic["baseline_priority"] = 5
    synthetic["baseline_coverage"] = np.where(synthetic.prior_pres_margin.notna(), 1.0, np.nan)
    synthetic["baseline_source_path"] = rel(synthetic_path)
    synthetic["strict_baseline_eligible"] = False
    synthetic["research_baseline_eligible"] = True
    rows.append(synthetic)
    keep = KEYS + [
        "baseline_dem_margin", "baseline_office", "baseline_source", "baseline_class", "baseline_quality",
        "baseline_priority", "baseline_coverage", "baseline_source_path", "strict_baseline_eligible",
        "research_baseline_eligible",
    ]
    return pd.concat([frame[keep] for frame in rows], ignore_index=True)


def load_mississippi_2019_baselines() -> pd.DataFrame:
    """Use the repository's district-split RDH/VEST Mississippi 2019 package."""
    import geopandas as gpd

    path = RAW / "historical_statewide_elections/ms_gen_19_prec.zip"
    state = gpd.read_file(f"zip://{path.resolve()}!ms_gen_19_st_prec.shp", ignore_geometry=True)
    state["join_id"] = state.UNIQUE_ID.astype(str).str.replace(r"-\(S[LU]-\d+\)$", "", regex=True)
    context = state.groupby("join_id", as_index=False)[["G19GOVDHOO", "G19GOVRREE"]].sum()
    outputs = []
    for chamber, layer, district_field, prefix in (
        ("house", "ms_gen_19_sldl_prec.shp", "SLDL_DIST", "GSL"),
        ("senate", "ms_gen_19_sldu_prec.shp", "SLDU_DIST", "GSU"),
    ):
        frame = gpd.read_file(f"zip://{path.resolve()}!{layer}", ignore_geometry=True)
        frame["join_id"] = frame.UNIQUE_ID.astype(str).str.replace(r"-\(S[LU]-\d+\)$", "", regex=True)
        dem_cols = [column for column in frame if re.match(rf"^{prefix}\d{{2,3}}D", column)]
        rep_cols = [column for column in frame if re.match(rf"^{prefix}\d{{2,3}}R", column)]
        frame["leg_dem_votes"] = frame[dem_cols].sum(axis=1)
        frame["leg_rep_votes"] = frame[rep_cols].sum(axis=1)
        frame = frame.merge(context, on="join_id", how="left", validate="many_to_one")
        frame["district"] = standard_district(frame[district_field])
        agg = frame.groupby("district", as_index=False).agg(
            baseline_dem_votes=("G19GOVDHOO", "sum"), baseline_rep_votes=("G19GOVRREE", "sum"),
            legislative_dem_check=("leg_dem_votes", "sum"), legislative_rep_check=("leg_rep_votes", "sum"),
        )
        denominator = agg.baseline_dem_votes + agg.baseline_rep_votes
        agg["baseline_dem_margin"] = 100 * (agg.baseline_dem_votes - agg.baseline_rep_votes) / denominator.where(denominator.gt(0))
        agg["state"], agg["year"], agg["chamber"] = "MS", 2019, chamber
        agg["baseline_office"] = "GOVERNOR"
        agg["baseline_source"] = "RDH/VEST Mississippi 2019 district-split precinct package"
        agg["baseline_class"] = "observed_same_cycle_ticket"
        agg["baseline_quality"] = "official_results_validated_district_split"
        agg["baseline_priority"] = 2
        agg["baseline_coverage"] = 1.0
        agg["baseline_source_path"] = rel(path)
        agg["strict_baseline_eligible"] = agg.baseline_dem_margin.notna()
        agg["research_baseline_eligible"] = agg.baseline_dem_margin.notna()
        outputs.append(agg)
    return pd.concat(outputs, ignore_index=True)


def load_mississippi_2023_context() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Decode the RDH/VEST wide file into contest outcomes and governor context."""
    path = RAW / "historical_statewide_elections/ms_gen_2023_prec.zip"
    with ZipFile(path) as bundle:
        member = next(name for name in bundle.namelist() if name.lower().endswith("_prec.csv"))
        readme_name = next(name for name in bundle.namelist() if name.lower().endswith("readme.txt"))
        frame = pd.read_csv(bundle.open(member), low_memory=False)
        readme = bundle.read(readme_name).decode("utf-8", errors="replace")
    labels: dict[str, tuple[str, str, str, int]] = {}
    pattern = re.compile(
        r"(GS(?:L\d{3}|U\d{2})[A-Z0-9]+)\s+(.+?)-:-([A-Z]+)-:-State (House|Senate)-(\d+)\s*$"
    )
    for line in readme.splitlines():
        match = pattern.match(line.strip())
        if match:
            code, name, party, chamber, district = match.groups()
            labels[code] = (name.strip(), party.strip(), chamber.lower(), int(district))

    outcomes: list[dict[str, object]] = []
    baselines: list[pd.DataFrame] = []
    for chamber, prefix in (("house", "GSL"), ("senate", "GSU")):
        codes = [code for code, value in labels.items() if value[2] == chamber and code in frame]
        districts = sorted({labels[code][3] for code in codes})
        fragment_rows: list[pd.DataFrame] = []
        for district in districts:
            district_codes = [code for code in codes if labels[code][3] == district]
            party_codes = {
                party: [code for code in district_codes if labels[code][1] == party]
                for party in ("DEM", "REP")
            }
            dem_votes = sum(float(pd.to_numeric(frame[code], errors="coerce").sum()) for code in party_codes["DEM"])
            rep_votes = sum(float(pd.to_numeric(frame[code], errors="coerce").sum()) for code in party_codes["REP"])
            if dem_votes > 0 and rep_votes > 0:
                top = {}
                for party in ("DEM", "REP"):
                    ranked = sorted(
                        party_codes[party],
                        key=lambda code: float(pd.to_numeric(frame[code], errors="coerce").sum()),
                        reverse=True,
                    )
                    top[party] = labels[ranked[0]][0] if ranked else pd.NA
                outcomes.append({
                    "state": "MS", "year": 2023, "chamber": chamber, "district": district,
                    "dem_votes": dem_votes, "rep_votes": rep_votes,
                    "legislative_dem_margin": 100 * (dem_votes-rep_votes) / (dem_votes+rep_votes),
                    "dem_candidate": top["DEM"], "rep_candidate": top["REP"],
                    "outcome_eligible": True,
                    "outcome_source": "RDH/VEST Mississippi 2023 precinct package",
                    "outcome_source_path": rel(path),
                    "candidate_source": "RDH/VEST ZIP README field-code mapping",
                    "dem_incumbent": np.nan, "rep_incumbent": np.nan,
                    "incumbency_balance": np.nan, "incumbency_source": pd.NA,
                    "incumbency_quality": "missing",
                })
            turnout = frame[district_codes].apply(pd.to_numeric, errors="coerce").sum(axis=1)
            fragment_rows.append(pd.DataFrame({
                "row_number": frame.index, "district": district, "legislative_turnout": turnout,
            }))
        fragments = pd.concat(fragment_rows, ignore_index=True)
        fragments = fragments[fragments.legislative_turnout.gt(0)].copy()
        fragments["precinct_chamber_turnout"] = fragments.groupby("row_number").legislative_turnout.transform("sum")
        fragments["weight"] = fragments.legislative_turnout / fragments.precinct_chamber_turnout
        fragments["baseline_dem_votes"] = (
            fragments.row_number.map(pd.to_numeric(frame.G23GOVDPRE, errors="coerce")) * fragments.weight
        )
        fragments["baseline_rep_votes"] = (
            fragments.row_number.map(pd.to_numeric(frame.G23GOVRREE, errors="coerce")) * fragments.weight
        )
        agg = fragments.groupby("district", as_index=False).agg(
            baseline_dem_votes=("baseline_dem_votes", "sum"),
            baseline_rep_votes=("baseline_rep_votes", "sum"),
            legislative_turnout=("legislative_turnout", "sum"),
        )
        denominator = agg.baseline_dem_votes + agg.baseline_rep_votes
        agg["baseline_dem_margin"] = 100 * (agg.baseline_dem_votes-agg.baseline_rep_votes) / denominator.where(denominator.gt(0))
        agg["state"], agg["year"], agg["chamber"] = "MS", 2023, chamber
        agg["baseline_office"] = "GOVERNOR"
        agg["baseline_source"] = "RDH/VEST Mississippi 2023 ballot-first governor context"
        agg["baseline_class"] = "observed_same_cycle_ticket"
        agg["baseline_quality"] = "official_results_validated_district_split"
        agg["baseline_priority"] = 2
        agg["baseline_coverage"] = 1.0
        agg["baseline_source_path"] = rel(path)
        agg["strict_baseline_eligible"] = agg.baseline_dem_margin.notna()
        agg["research_baseline_eligible"] = agg.baseline_dem_margin.notna()
        baselines.append(agg)
    return pd.DataFrame(outcomes), pd.concat(baselines, ignore_index=True)


def load_virginia_2023_context() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build 2023 contests and a documented prior-governor research baseline.

    Virginia had no same-cycle statewide/federal contest in 2023.  The 2021
    governor vote is therefore retained as an observed, prior-cycle research
    baseline and is never promoted through the strict same-cycle gate.
    """
    import geopandas as gpd

    outcome_path = RAW / "southern_sos_elections/VA/Election Results_2023.csv"
    context_path = RAW / "southern_sos_elections/VA/va_vest_21.zip"
    raw = pd.read_csv(outcome_path, low_memory=False)
    raw = raw[
        raw.DistrictType.astype(str).str.lower().isin(["state-house", "state-senate"])
        & raw.Party.isin(["Democratic", "Republican"])
    ].copy()
    raw["votes"] = pd.to_numeric(raw.TOTAL_VOTES, errors="coerce")
    raw["chamber"] = raw.DistrictType.map({"state-house": "house", "state-senate": "senate"})
    raw["district"] = standard_district(raw.DistrictName)
    raw["locality_key"] = pd.to_numeric(raw.LocalityCode, errors="coerce").astype("Int64").astype(str)
    raw["precinct_key"] = pd.to_numeric(raw.PrecinctId, errors="coerce").astype("Int64").astype(str)

    party = raw.groupby(
        ["locality_key", "precinct_key", "chamber", "district", "Party"], dropna=False
    ).votes.sum().unstack(fill_value=0).reset_index()
    for label in ("Democratic", "Republican"):
        if label not in party:
            party[label] = 0.0
    party["legislative_turnout"] = party.Democratic + party.Republican

    aggregate = party.groupby(["chamber", "district"], as_index=False)[["Democratic", "Republican"]].sum()
    aggregate = aggregate[aggregate.Democratic.gt(0) & aggregate.Republican.gt(0)].copy()
    names = (
        raw.groupby(["chamber", "district", "Party", "CandidateName"], dropna=False).votes.sum().reset_index()
        .sort_values("votes", ascending=False).drop_duplicates(["chamber", "district", "Party"])
        .pivot(index=["chamber", "district"], columns="Party", values="CandidateName").reset_index()
        .rename(columns={"Democratic": "dem_candidate", "Republican": "rep_candidate"})
    )
    aggregate = aggregate.merge(names, on=["chamber", "district"], how="left", validate="one_to_one")
    aggregate = aggregate.rename(columns={"Democratic": "dem_votes", "Republican": "rep_votes"})
    aggregate["state"], aggregate["year"] = "VA", 2023
    aggregate["legislative_dem_margin"] = 100 * (
        aggregate.dem_votes-aggregate.rep_votes
    ) / (aggregate.dem_votes+aggregate.rep_votes)
    aggregate["outcome_eligible"] = True
    aggregate["outcome_source"] = "Virginia Department of Elections 2023 candidate-precinct returns"
    aggregate["outcome_source_path"] = rel(outcome_path)
    aggregate["candidate_source"] = "Virginia Department of Elections 2023 candidate-precinct returns"
    aggregate["dem_incumbent"] = np.nan
    aggregate["rep_incumbent"] = np.nan
    aggregate["incumbency_balance"] = np.nan
    aggregate["incumbency_source"] = pd.NA
    aggregate["incumbency_quality"] = "missing"

    context = gpd.read_file(f"zip://{context_path.resolve()}", ignore_geometry=True)
    context["locality_key"] = pd.to_numeric(context.COUNTYFP, errors="coerce").astype("Int64").astype(str)
    context["precinct_key"] = pd.to_numeric(context.VTDST, errors="coerce").astype("Int64").astype(str)
    context = context.groupby(["locality_key", "precinct_key"], as_index=False).agg(
        context_dem=("G21GOVDMCA", "sum"), context_rep=("G21GOVRYOU", "sum")
    )
    locality = context.groupby("locality_key", as_index=False).agg(
        locality_dem=("context_dem", "sum"), locality_rep=("context_rep", "sum")
    )
    baselines: list[pd.DataFrame] = []
    for chamber, fragments in party.groupby("chamber", sort=True):
        fragments = fragments.copy()
        precinct_group = ["locality_key", "precinct_key"]
        fragments["precinct_turnout"] = fragments.groupby(precinct_group).legislative_turnout.transform("sum")
        fragments["precinct_weight"] = fragments.legislative_turnout / fragments.precinct_turnout.where(
            fragments.precinct_turnout.gt(0)
        )
        fragments = fragments.merge(context, on=precinct_group, how="left", validate="many_to_one")
        fragments["direct_match"] = fragments.context_dem.notna() & fragments.context_rep.notna()
        fragments["allocated_dem"] = (fragments.context_dem * fragments.precinct_weight).where(fragments.direct_match)
        fragments["allocated_rep"] = (fragments.context_rep * fragments.precinct_weight).where(fragments.direct_match)
        matched = fragments.groupby("locality_key", as_index=False).agg(
            matched_dem=("allocated_dem", "sum"), matched_rep=("allocated_rep", "sum")
        )
        fragments = fragments.merge(locality, on="locality_key", how="left", validate="many_to_one")
        fragments = fragments.merge(matched, on="locality_key", how="left", validate="many_to_one")
        fragments["residual_dem"] = (fragments.locality_dem-fragments.matched_dem).clip(lower=0)
        fragments["residual_rep"] = (fragments.locality_rep-fragments.matched_rep).clip(lower=0)
        unmatched = ~fragments.direct_match
        fragments["unmatched_locality_turnout"] = fragments.legislative_turnout.where(unmatched, 0).groupby(
            fragments.locality_key
        ).transform("sum")
        fallback_weight = fragments.legislative_turnout / fragments.unmatched_locality_turnout.where(
            fragments.unmatched_locality_turnout.gt(0)
        )
        fragments.loc[unmatched, "allocated_dem"] = fragments.loc[unmatched, "residual_dem"] * fallback_weight[unmatched]
        fragments.loc[unmatched, "allocated_rep"] = fragments.loc[unmatched, "residual_rep"] * fallback_weight[unmatched]
        fragments["matched_turnout"] = fragments.legislative_turnout.where(fragments.direct_match, 0)
        agg = fragments.groupby("district", as_index=False).agg(
            baseline_dem_votes=("allocated_dem", lambda values: values.sum(min_count=1)),
            baseline_rep_votes=("allocated_rep", lambda values: values.sum(min_count=1)),
            legislative_turnout=("legislative_turnout", "sum"),
            matched_turnout=("matched_turnout", "sum"),
        )
        denominator = agg.baseline_dem_votes + agg.baseline_rep_votes
        agg["baseline_dem_margin"] = 100 * (agg.baseline_dem_votes-agg.baseline_rep_votes) / denominator.where(denominator.gt(0))
        agg["baseline_coverage"] = agg.matched_turnout / agg.legislative_turnout.where(agg.legislative_turnout.gt(0))
        agg["state"], agg["year"], agg["chamber"] = "VA", 2023, chamber
        agg["baseline_office"] = "2021 GOVERNOR"
        agg["baseline_source"] = "VEST 2021 governor vote allocated to 2023 districts; locality fallback"
        agg["baseline_class"] = "observed_prior_cycle_ticket"
        agg["baseline_quality"] = "research_only_offyear_prior_ticket_with_locality_fallback"
        agg["baseline_priority"] = 4
        agg["baseline_source_path"] = rel(context_path)
        agg["strict_baseline_eligible"] = False
        agg["research_baseline_eligible"] = agg.baseline_dem_margin.notna()
        baselines.append(agg)
    return aggregate, pd.concat(baselines, ignore_index=True)


def load_virginia_2017_2021_research_baselines() -> pd.DataFrame:
    """Create explicitly non-strict Virginia baselines under the off-year policy.

    The 2019 VEST legislative files supply precinct-to-district membership for
    the unchanged 2011 plan. Governor observations come from 2017 or 2021.
    Cross-election precinct matching and locality fallback make these useful
    for sensitivity analysis, but never strict WAR training.
    """
    import geopandas as gpd

    root = RAW / "southern_sos_elections/VA"
    contexts = {}
    for context_year, dem_col, rep_col in (
        (2017, "G17GOVDNOR", "G17GOVRGIL"),
        (2021, "G21GOVDMCA", "G21GOVRYOU"),
    ):
        path = root / f"va_vest_{str(context_year)[-2:]}.zip"
        frame = gpd.read_file(f"zip://{path.resolve()}", ignore_geometry=True)
        frame["locality_key"] = pd.to_numeric(frame.COUNTYFP, errors="coerce").astype("Int64").astype(str)
        frame["precinct_key"] = pd.to_numeric(frame.VTDST, errors="coerce").astype("Int64").astype(str)
        contexts[context_year] = frame.groupby(["locality_key", "precinct_key"], as_index=False).agg(
            context_dem=(dem_col, "sum"), context_rep=(rep_col, "sum")
        )

    outputs: list[pd.DataFrame] = []
    for chamber, filename, district_col, dem_col, rep_col in (
        ("house", "va_vest_19_statehouse.zip", "HOD_DIST", "G19HODDEM", "G19HODREP"),
        ("senate", "va_vest_19_statesenate.zip", "SOV_DIST", "G19SOVDEM", "G19SOVREP"),
    ):
        membership_path = root / filename
        membership = gpd.read_file(f"zip://{membership_path.resolve()}", ignore_geometry=True)
        membership["locality_key"] = pd.to_numeric(membership.COUNTYFP, errors="coerce").astype("Int64").astype(str)
        membership["precinct_key"] = pd.to_numeric(membership.VTDST, errors="coerce").astype("Int64").astype(str)
        membership["district"] = standard_district(membership[district_col])
        membership["legislative_turnout"] = (
            pd.to_numeric(membership[dem_col], errors="coerce").fillna(0)
            + pd.to_numeric(membership[rep_col], errors="coerce").fillna(0)
        )
        membership = membership.dropna(subset=["district"]).copy()
        for target_year, context_year in ((2017, 2017), (2019, 2017), (2021, 2021)):
            fragments = membership.copy()
            precinct = ["locality_key", "precinct_key"]
            if target_year == 2017:
                # Avoid using 2019 outcomes to weight a 2017 split.
                fragments["allocation_measure"] = 1.0
            else:
                fragments["allocation_measure"] = fragments.legislative_turnout
                zero = fragments.groupby(precinct).allocation_measure.transform("sum").eq(0)
                fragments.loc[zero, "allocation_measure"] = 1.0
            fragments["precinct_measure"] = fragments.groupby(precinct).allocation_measure.transform("sum")
            fragments["precinct_weight"] = fragments.allocation_measure / fragments.precinct_measure
            context = contexts[context_year]
            locality = context.groupby("locality_key", as_index=False).agg(
                locality_dem=("context_dem", "sum"), locality_rep=("context_rep", "sum")
            )
            fragments = fragments.merge(context, on=precinct, how="left", validate="many_to_one")
            fragments["direct_match"] = fragments.context_dem.notna() & fragments.context_rep.notna()
            fragments["allocated_dem"] = (fragments.context_dem*fragments.precinct_weight).where(fragments.direct_match)
            fragments["allocated_rep"] = (fragments.context_rep*fragments.precinct_weight).where(fragments.direct_match)
            matched = fragments.groupby("locality_key", as_index=False).agg(
                matched_dem=("allocated_dem", "sum"), matched_rep=("allocated_rep", "sum")
            )
            fragments = fragments.merge(locality, on="locality_key", how="left", validate="many_to_one")
            fragments = fragments.merge(matched, on="locality_key", how="left", validate="many_to_one")
            fragments["residual_dem"] = (fragments.locality_dem-fragments.matched_dem).clip(lower=0)
            fragments["residual_rep"] = (fragments.locality_rep-fragments.matched_rep).clip(lower=0)
            unmatched = ~fragments.direct_match
            fragments["unmatched_measure"] = fragments.allocation_measure.where(unmatched, 0).groupby(
                fragments.locality_key
            ).transform("sum")
            fallback_weight = fragments.allocation_measure / fragments.unmatched_measure.where(fragments.unmatched_measure.gt(0))
            fragments.loc[unmatched, "allocated_dem"] = fragments.loc[unmatched, "residual_dem"]*fallback_weight[unmatched]
            fragments.loc[unmatched, "allocated_rep"] = fragments.loc[unmatched, "residual_rep"]*fallback_weight[unmatched]
            fragments["matched_measure"] = fragments.allocation_measure.where(fragments.direct_match, 0)
            agg = fragments.groupby("district", as_index=False).agg(
                baseline_dem_votes=("allocated_dem", lambda values: values.sum(min_count=1)),
                baseline_rep_votes=("allocated_rep", lambda values: values.sum(min_count=1)),
                allocation_measure=("allocation_measure", "sum"),
                matched_measure=("matched_measure", "sum"),
            )
            denominator = agg.baseline_dem_votes + agg.baseline_rep_votes
            agg["baseline_dem_margin"] = 100*(agg.baseline_dem_votes-agg.baseline_rep_votes) / denominator.where(denominator.gt(0))
            agg["baseline_coverage"] = agg.matched_measure / agg.allocation_measure.where(agg.allocation_measure.gt(0))
            agg["state"], agg["year"], agg["chamber"] = "VA", target_year, chamber
            agg["baseline_office"] = f"{context_year} GOVERNOR"
            agg["baseline_source"] = (
                f"VEST {context_year} governor vote with 2019-plan precinct membership; locality fallback"
            )
            agg["baseline_class"] = (
                "observed_same_cycle_ticket_cross_election_membership"
                if target_year == context_year else "observed_prior_cycle_ticket"
            )
            agg["baseline_quality"] = "research_only_cross_election_precinct_membership"
            agg["baseline_priority"] = 4
            agg["baseline_source_path"] = rel(root / f"va_vest_{str(context_year)[-2:]}.zip")
            agg["strict_baseline_eligible"] = False
            agg["research_baseline_eligible"] = agg.baseline_dem_margin.notna()
            outputs.append(agg)
    return pd.concat(outputs, ignore_index=True)


def load_virginia_governor_baselines() -> pd.DataFrame:
    """Allocate official Virginia governor precinct returns to House districts."""
    outputs = []
    for year in (2005, 2009, 2013):
        path = RAW / f"southern_sos_elections/VA/{year}/{year}_November_General.csv"
        frame = pd.read_csv(path, low_memory=False)
        frame = frame[frame.Party.isin(["Democratic", "Republican"])].copy()
        frame["votes"] = pd.to_numeric(frame.TOTAL_VOTES, errors="coerce")
        frame["county_key"] = frame.LocalityCode.astype(str).str.upper().str.strip()
        frame["precinct_key"] = frame.PrecinctName.astype(str).str.upper().str.strip()
        legislative = frame[frame.DistrictType.eq("House of Delegates")].copy()
        legislative["district"] = standard_district(legislative.DistrictName)
        party = legislative.groupby(
            ["county_key", "precinct_key", "district", "Party"], dropna=False
        ).votes.sum().unstack(fill_value=0).reset_index()
        for label in ("Democratic", "Republican"):
            if label not in party:
                party[label] = 0.0
        party["legislative_turnout"] = party.Democratic + party.Republican
        governor = frame[frame.OfficeTitle.astype(str).str.match(r"^Governor(?:\s|-|$)", na=False)].groupby(
            ["county_key", "precinct_key", "Party"], dropna=False
        ).votes.sum().unstack(fill_value=0).reset_index()
        for label in ("Democratic", "Republican"):
            if label not in governor:
                governor[label] = 0.0
        precinct = ["county_key", "precinct_key"]
        party["precinct_turnout"] = party.groupby(precinct).legislative_turnout.transform("sum")
        party["weight"] = party.legislative_turnout / party.precinct_turnout.where(party.precinct_turnout.gt(0))
        party.loc[party.groupby(precinct).district.transform("size").eq(1), "weight"] = 1.0
        joined = party.merge(governor, on=precinct, how="left", suffixes=("_leg", "_gov"), validate="many_to_one")
        joined["context_present"] = joined.Democratic_gov.notna() & joined.Republican_gov.notna()
        joined["allocated_dem"] = joined.Democratic_gov * joined.weight
        joined["allocated_rep"] = joined.Republican_gov * joined.weight
        joined["matched_turnout"] = joined.legislative_turnout.where(joined.context_present, 0)
        agg = joined.groupby("district", as_index=False).agg(
            baseline_dem_votes=("allocated_dem", lambda values: values.sum(min_count=1)),
            baseline_rep_votes=("allocated_rep", lambda values: values.sum(min_count=1)),
            legislative_turnout=("legislative_turnout", "sum"), matched_turnout=("matched_turnout", "sum"),
        )
        agg["baseline_coverage"] = agg.matched_turnout / agg.legislative_turnout.where(agg.legislative_turnout.gt(0))
        denominator = agg.baseline_dem_votes + agg.baseline_rep_votes
        agg["baseline_dem_margin"] = 100 * (agg.baseline_dem_votes - agg.baseline_rep_votes) / denominator.where(denominator.gt(0))
        agg["state"], agg["year"], agg["chamber"] = "VA", year, "house"
        agg["baseline_office"] = "GOVERNOR"
        agg["baseline_source"] = "Virginia Department of Elections ballot-first governor context"
        agg["baseline_class"] = "observed_same_cycle_ticket"
        agg["baseline_quality"] = np.where(agg.baseline_coverage.ge(0.95), "validated_coverage", "partial_coverage")
        agg["baseline_priority"] = 2
        agg["baseline_source_path"] = rel(path)
        agg["strict_baseline_eligible"] = agg.baseline_dem_margin.notna() & agg.baseline_coverage.ge(0.95)
        agg["research_baseline_eligible"] = agg.baseline_dem_margin.notna()
        outputs.append(agg)
    return pd.concat(outputs, ignore_index=True)


def attach_2024_incumbency(outcomes: pd.DataFrame, klarner: pd.DataFrame) -> pd.DataFrame:
    if outcomes.empty:
        return outcomes
    out = outcomes.copy()
    out["dem_incumbent"] = np.nan
    out["rep_incumbent"] = np.nan
    out["incumbency_balance"] = np.nan
    out["incumbency_source"] = pd.NA
    out["incumbency_quality"] = "missing"
    reviewed_path = CAL / "southern_2024_incumbency_races.csv"
    reviewed = pd.read_csv(reviewed_path)
    reviewed["chamber"] = reviewed.chamber.map(standard_chamber)
    reviewed["district"] = standard_district(reviewed.district)
    reviewed = reviewed.rename(columns={"dem_incumbent": "review_dem_incumbent", "rep_incumbent": "review_rep_incumbent",
                                        "incumbency_balance": "review_incumbency_balance"})
    out = out.merge(reviewed[KEYS + ["review_dem_incumbent", "review_rep_incumbent", "review_incumbency_balance", "incumbency_model_ready"]],
                    on=KEYS, how="left", validate="one_to_one")
    ready = out.incumbency_model_ready.astype("boolean").fillna(False)
    out.loc[ready, "dem_incumbent"] = out.loc[ready, "review_dem_incumbent"].astype(float)
    out.loc[ready, "rep_incumbent"] = out.loc[ready, "review_rep_incumbent"].astype(float)
    out.loc[ready, "incumbency_balance"] = out.loc[ready, "review_incumbency_balance"]
    out.loc[ready, "incumbency_source"] = rel(reviewed_path)
    out.loc[ready, "incumbency_quality"] = "reviewed_inference"

    prior = klarner[klarner.year.between(2018, 2022)].copy()
    winner_names: dict[tuple[str, str, str], set[str]] = {}
    for _, row in prior.iterrows():
        if row.dem_win > 0 and pd.notna(row.dem_candidate):
            winner_names.setdefault((row.state, row.chamber, "D"), set()).add(normalized_name(row.dem_candidate))
        if row.rep_win > 0 and pd.notna(row.rep_candidate):
            winner_names.setdefault((row.state, row.chamber, "R"), set()).add(normalized_name(row.rep_candidate))
    unresolved = out.incumbency_balance.isna()
    for index, row in out[unresolved].iterrows():
        dem = normalized_name(row.dem_candidate)
        rep = normalized_name(row.rep_candidate)
        dem_inc = bool(dem and dem in winner_names.get((row.state, row.chamber, "D"), set()))
        rep_inc = bool(rep and rep in winner_names.get((row.state, row.chamber, "R"), set()))
        out.at[index, "dem_incumbent"] = float(dem_inc)
        out.at[index, "rep_incumbent"] = float(rep_inc)
        out.at[index, "incumbency_balance"] = float(dem_inc) - float(rep_inc)
        out.at[index, "incumbency_source"] = "Exact normalized-name match to 2018-2022 Klarner winners"
        out.at[index, "incumbency_quality"] = "experimental_exact_prior_winner"
    return out.drop(columns=["review_dem_incumbent", "review_rep_incumbent", "review_incumbency_balance", "incumbency_model_ready"])


def attach_exact_prior_winner_incumbency(outcomes: pd.DataFrame, klarner: pd.DataFrame) -> pd.DataFrame:
    """Attach auditable research-only incumbency from exact prior-winner names.

    An exact match is useful evidence that a candidate is an incumbent.  A
    non-match is not sufficient open-seat evidence, so this adapter remains
    outside the strict incumbency gate pending a reviewed roster.
    """
    if outcomes.empty:
        return outcomes
    out = outcomes.copy()
    prior_year = {("MS", 2023): 2019, ("VA", 2023): 2021}
    for index, row in out.iterrows():
        year = prior_year.get((row.state, int(row.year)))
        if year is None:
            continue
        prior = klarner[
            klarner.state.eq(row.state) & klarner.year.eq(year) & klarner.chamber.eq(row.chamber)
        ]
        dem_winners = {normalized_name(value) for value in prior.loc[prior.dem_win.gt(0), "dem_candidate"].dropna()}
        rep_winners = {normalized_name(value) for value in prior.loc[prior.rep_win.gt(0), "rep_candidate"].dropna()}
        dem_inc = normalized_name(row.dem_candidate) in dem_winners
        rep_inc = normalized_name(row.rep_candidate) in rep_winners
        out.at[index, "dem_incumbent"] = float(dem_inc)
        out.at[index, "rep_incumbent"] = float(rep_inc)
        out.at[index, "incumbency_balance"] = float(dem_inc)-float(rep_inc)
        out.at[index, "incumbency_source"] = (
            f"Exact normalized-name match to {year} Klarner chamber winners; non-match not reviewed as open seat"
        )
        out.at[index, "incumbency_quality"] = "experimental_exact_prior_winner"
    return out


def attach_validated_incumbency_roster(outcomes: pd.DataFrame) -> pd.DataFrame:
    """Overlay only complete, evidence-bearing race incumbency observations."""
    roster = pd.read_csv(INCUMBENCY_ROSTER, dtype={"district": str})
    roster = roster[roster.strict_incumbency_eligible.eq(1)].copy()
    roster["state"] = roster.state_code
    roster["year"] = pd.to_numeric(roster.cycle, errors="raise").astype(int)
    roster["chamber"] = roster.chamber.map({"lower": "house", "upper": "senate"})
    roster["district"] = standard_district(roster.district)
    roster = roster.rename(
        columns={
            "dem_incumbent": "validated_dem_incumbent",
            "rep_incumbent": "validated_rep_incumbent",
            "incumbency_balance": "validated_incumbency_balance",
            "incumbency_method": "validated_incumbency_method",
            "incumbency_quality": "validated_incumbency_quality",
        }
    )
    keep = KEYS + [
        "validated_dem_incumbent", "validated_rep_incumbent",
        "validated_incumbency_balance", "validated_incumbency_method",
        "validated_incumbency_quality",
    ]
    if roster.duplicated(KEYS).any():
        raise ValueError("Validated incumbency roster is not unique at race grain")
    out = outcomes.merge(roster[keep], on=KEYS, how="left", validate="one_to_one")
    use = out.validated_incumbency_balance.notna()
    out.loc[use, "dem_incumbent"] = out.loc[use, "validated_dem_incumbent"]
    out.loc[use, "rep_incumbent"] = out.loc[use, "validated_rep_incumbent"]
    out.loc[use, "incumbency_balance"] = out.loc[use, "validated_incumbency_balance"]
    out.loc[use, "incumbency_source"] = (
        rel(INCUMBENCY_ROSTER) + ": " + out.loc[use, "validated_incumbency_method"].astype(str)
    )
    out.loc[use, "incumbency_quality"] = out.loc[use, "validated_incumbency_quality"]
    return out.drop(
        columns=[column for column in out if isinstance(column, str) and column.startswith("validated_")]
    )


def load_virginia_generic_ballot_baselines(outcomes: pd.DataFrame) -> pd.DataFrame:
    """Use national generic-ballot environment when no same-year ticket exists."""
    environment = pd.read_csv(GENERIC_BALLOT_ENVIRONMENT)
    environment = environment[environment.cycle.isin([2019, 2023])].copy()
    if set(environment.cycle) != {2019, 2023} or environment.duplicated("cycle").any():
        raise ValueError("Virginia generic-ballot input must uniquely cover 2019 and 2023")
    keys = outcomes[
        outcomes.state.eq("VA") & outcomes.year.isin([2019, 2023])
    ][KEYS].drop_duplicates()
    result = keys.merge(environment, left_on="year", right_on="cycle", how="left", validate="many_to_one")
    if result.democratic_margin.isna().any():
        raise ValueError("A Virginia no-ticket cycle is missing national environment")
    result["baseline_dem_votes"] = np.nan
    result["baseline_rep_votes"] = np.nan
    result["baseline_dem_margin"] = result.democratic_margin
    result["baseline_office"] = "NATIONAL GENERIC CONGRESSIONAL BALLOT"
    result["baseline_source"] = result.polling_measure
    result["baseline_class"] = "national_environment_generic_ballot"
    result["baseline_quality"] = "observed_election_day_polling_average"
    result["baseline_priority"] = 3
    result["baseline_coverage"] = 1.0
    result["baseline_source_path"] = result.source_local_path
    result["strict_baseline_eligible"] = True
    result["research_baseline_eligible"] = True
    return result


def select_outcomes(
    klarner: pd.DataFrame,
    alabama: pd.DataFrame,
    supplemental: pd.DataFrame,
    texas: pd.DataFrame,
    fallback: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = []
    k = klarner.copy(); k["outcome_priority"] = 3; candidates.append(k)
    if not supplemental.empty:
        m = supplemental.copy(); m["outcome_priority"] = 2; candidates.append(m)
    if not texas.empty:
        t = texas.copy(); t["outcome_priority"] = 1; candidates.append(t)
    if fallback is not None and not fallback.empty:
        f = fallback.copy(); f["outcome_priority"] = 4; candidates.append(f)
    a = alabama.copy(); a["outcome_priority"] = 1; candidates.append(a)
    all_rows = pd.concat(candidates, ignore_index=True, sort=False)
    all_rows = all_rows.sort_values(KEYS + ["outcome_priority"])
    selected = all_rows.drop_duplicates(KEYS, keep="first").copy()
    selected_keys = selected[KEYS + ["outcome_priority"]].rename(columns={"outcome_priority": "selected_priority"})
    audit = all_rows.merge(selected_keys, on=KEYS, how="left", validate="many_to_one")
    audit["selected"] = audit.outcome_priority.eq(audit.selected_priority)
    return selected, audit


def source_catalog() -> tuple[pd.DataFrame, pd.DataFrame]:
    top_rows = []
    for directory in sorted(path for path in RAW.iterdir() if path.is_dir()):
        files = [path for path in directory.rglob("*") if path.is_file()]
        top_rows.append({
            "source_family": directory.name, "root_path": rel(directory), "file_count": len(files),
            "bytes": sum(path.stat().st_size for path in files),
            "war_role": (
                "core_election_or_geography" if directory.name in {"alabama_elections_and_geography", "historical_statewide_elections", "openelections", "openelections_historical_gaps", "rdh", "sos_normalized", "southern_sos_elections"}
                else "supporting_covariate" if directory.name in {"acs", "census", "finance", "fec", "candidate_demographics", "candidates", "ideology", "ballotpedia"}
                else "reviewed_not_core_to_panel"
            ),
        })
    texas_inputs = [
        TX_ROOT / "data/processed/models/full_history_cmo_candidates.csv",
        TX_ROOT / "data/processed/features/historical_cmo_features.csv",
        TX_ROOT / "data/processed/elections/sos_canonical_candidate_totals_1992_2018.csv",
        TX_ROOT / "data/processed/elections/sos_official_candidate_totals_2020_2024.csv",
        TX_ROOT / "data/raw/tx_sos/OneDrive_2026-08-17.zip",
        texas_tlc_result_file(1998),
    ]
    existing_texas_inputs = [path for path in texas_inputs if path.exists()]
    top_rows.append({
        "source_family": "texas_project_upstream",
        "root_path": "external://texas-state-house-and-state-senate-model",
        "file_count": len(existing_texas_inputs),
        "bytes": sum(path.stat().st_size for path in existing_texas_inputs),
        "war_role": "core_election_or_geography",
    })
    detailed_roots = [
        RAW / "historical_statewide_elections", RAW / "southern_sos_elections", RAW / "openelections",
        RAW / "openelections_historical_gaps", ROOT / "data/processed/precinct_history",
    ]
    detail = []
    state_pattern = re.compile(r"(?:^|[\\/_-])(" + "|".join(TARGET_STATES) + r")(?:[\\/_-]|$)", re.I)
    year_pattern = re.compile(r"(?:19|20)\d{2}")
    for base in detailed_roots:
        if not base.exists():
            continue
        for path in sorted(candidate for candidate in base.rglob("*") if candidate.is_file()):
            relative = rel(path)
            state_match = state_pattern.search(relative)
            year_match = year_pattern.search(relative)
            detail.append({
                "path": relative, "source_root": rel(base), "bytes": path.stat().st_size,
                "suffix": path.suffix.lower(), "inferred_state": state_match.group(1).upper() if state_match else pd.NA,
                "inferred_year": int(year_match.group()) if year_match else pd.NA,
                "inspection_status": "represented_by_normalized_staging" if "data/processed/precinct_history" in relative
                else "catalogued_raw_evidence",
            })
    for path in existing_texas_inputs:
        detail.append({
            "path": source_ref(path),
            "source_root": "external://texas-state-house-and-state-senate-model",
            "bytes": path.stat().st_size,
            "suffix": path.suffix.lower(),
            "inferred_state": "TX",
            "inferred_year": pd.NA,
            "inspection_status": "represented_by_normalized_staging",
        })
    return pd.DataFrame(top_rows), pd.DataFrame(detail)


def build() -> dict[str, int]:
    OUT.mkdir(parents=True, exist_ok=True)
    klarner = load_klarner_universe()
    alabama_outcome, alabama_baseline = load_alabama_canonical()
    texas_outcome, texas_baseline, texas_audit = load_texas_upstream(klarner)
    louisiana_outcome, louisiana_stage_candidates, louisiana_stage_contests = load_louisiana_official_outcomes()
    louisiana_modern_baseline, louisiana_modern_baseline_audit = load_louisiana_modern_baselines(louisiana_outcome)
    medsl_outcome, medsl_baseline, medsl_audit = build_medsl_observations(klarner)
    # State-specific manifested archives are emitted before the national
    # archive. Keep that authoritative observation at the contest grain while
    # retaining every competing baseline in baseline_observations below.
    medsl_outcome = medsl_outcome.drop_duplicates(KEYS, keep="first").copy()
    medsl_historical_fallback = medsl_outcome[medsl_outcome.year.lt(2024)].copy()
    medsl_historical_fallback["dem_incumbent"] = np.nan
    medsl_historical_fallback["rep_incumbent"] = np.nan
    medsl_historical_fallback["incumbency_balance"] = np.nan
    medsl_historical_fallback["incumbency_source"] = pd.NA
    medsl_historical_fallback["incumbency_quality"] = "missing"
    medsl_outcome = attach_2024_incumbency(medsl_outcome, klarner)
    mississippi_2023_outcome, mississippi_2023_baseline = load_mississippi_2023_context()
    virginia_2023_outcome, virginia_2023_baseline = load_virginia_2023_context()
    mississippi_2023_outcome = attach_exact_prior_winner_incumbency(mississippi_2023_outcome, klarner)
    virginia_2023_outcome = attach_exact_prior_winner_incumbency(virginia_2023_outcome, klarner)
    # For 2018 and 2020, prefer Klarner outcomes and incumbency. MEDSL outcomes
    # remain competing observations; their 2024 rows fill the post-Klarner gap.
    medsl_selected_outcomes = medsl_outcome[medsl_outcome.year.eq(2024)].copy()
    supplemental_outcomes = pd.concat(
        [medsl_selected_outcomes, louisiana_outcome, mississippi_2023_outcome, virginia_2023_outcome],
        ignore_index=True, sort=False,
    )
    outcomes, outcome_audit = select_outcomes(
        klarner, alabama_outcome, supplemental_outcomes, texas_outcome, medsl_historical_fallback
    )
    outcomes = attach_validated_incumbency_roster(outcomes)

    existing_baselines = load_existing_baselines()
    official_long_baselines = load_official_long_ticket_baselines()
    arkansas_2022_baseline = load_arkansas_2022_baselines()
    georgia_tennessee_recent_baseline = load_georgia_tennessee_2022_2024_baselines()
    south_carolina_2016_baseline = load_south_carolina_2016_baselines()
    openelections_gap_baseline = load_openelections_gap_baselines()
    mississippi_baseline = load_mississippi_2019_baselines()
    virginia_baseline = load_virginia_governor_baselines()
    virginia_recent_research_baseline = load_virginia_2017_2021_research_baselines()
    virginia_generic_ballot_baseline = load_virginia_generic_ballot_baselines(outcomes)
    baseline_observations = pd.concat(
        [alabama_baseline, texas_baseline, louisiana_modern_baseline, medsl_baseline,
         official_long_baselines, arkansas_2022_baseline, georgia_tennessee_recent_baseline,
         south_carolina_2016_baseline, openelections_gap_baseline,
         mississippi_baseline, mississippi_2023_baseline, virginia_baseline,
         virginia_recent_research_baseline,
         virginia_generic_ballot_baseline,
         virginia_2023_baseline, existing_baselines],
        ignore_index=True, sort=False,
    )
    baseline_observations["district"] = standard_district(baseline_observations.district)
    baseline_observations = baseline_observations.sort_values(KEYS + ["baseline_priority"])
    baseline_observations["observation_id"] = [f"BL-{index + 1:07d}" for index in range(len(baseline_observations))]
    selected_baseline = baseline_observations.drop_duplicates(KEYS, keep="first").copy()
    selected_ids = set(selected_baseline.observation_id)
    baseline_observations["selected"] = baseline_observations.observation_id.isin(selected_ids)

    panel = outcomes.merge(
        selected_baseline.drop(columns="selected", errors="ignore"), on=KEYS, how="left", validate="one_to_one"
    )
    panel["direct_overperformance"] = panel.legislative_dem_margin - panel.baseline_dem_margin
    panel["strict_incumbency_eligible"] = panel.incumbency_quality.isin(
        ["canonical_reviewed", "source_observed", "reviewed_inference", "source_validated"]
    )
    outcome_ok = panel.outcome_eligible.astype("boolean").fillna(False)
    strict_baseline_ok = panel.strict_baseline_eligible.astype("boolean").fillna(False)
    research_baseline_ok = panel.research_baseline_eligible.astype("boolean").fillna(False)
    panel["strict_war_eligible"] = (
        outcome_ok
        & strict_baseline_ok
        & panel.incumbency_balance.notna() & panel.strict_incumbency_eligible
        & panel.dem_candidate.notna() & panel.rep_candidate.notna()
    )
    panel["research_war_eligible"] = (
        outcome_ok
        & research_baseline_ok
        & panel.incumbency_balance.notna()
    )
    panel["eligibility_reason"] = np.select(
        [
            panel.strict_war_eligible,
            ~outcome_ok,
            panel.baseline_dem_margin.isna(),
            ~strict_baseline_ok & research_baseline_ok,
            panel.incumbency_balance.isna(),
            ~panel.strict_incumbency_eligible,
            panel.dem_candidate.isna() | panel.rep_candidate.isna(),
        ],
        [
            "strict_war_ready", "outcome_not_contested_or_source_flagged", "missing_baseline",
            "research_only_baseline", "missing_incumbency", "experimental_incumbency_only", "missing_candidate_identity",
        ], default="other_gate_failure",
    )

    coverage = panel.groupby(["state", "year", "chamber"], as_index=False).agg(
        outcome_rows=("district", "size"), contested_outcomes=("outcome_eligible", "sum"),
        any_baseline=("baseline_dem_margin", "count"), strict_war_ready=("strict_war_eligible", "sum"),
        research_war_ready=("research_war_eligible", "sum"),
    )
    coverage["strict_coverage_of_contested"] = coverage.strict_war_ready / coverage.contested_outcomes.where(
        coverage.contested_outcomes.gt(0)
    )
    exclusions = panel[~panel.strict_war_eligible].copy()
    raw_families, election_files = source_catalog()

    output_frames = {
        "southern_war_panel.csv": panel,
        "southern_war_panel_coverage.csv": coverage,
        "southern_war_exclusions.csv": exclusions,
        "race_outcome_observation_audit.csv": outcome_audit,
        "baseline_observations.csv": baseline_observations,
        "medsl_ballot_first_audit.csv": medsl_audit,
        "louisiana_legislative_stage_candidates.csv": louisiana_stage_candidates,
        "louisiana_legislative_stage_contests.csv": louisiana_stage_contests,
        "louisiana_modern_baseline_audit.csv": louisiana_modern_baseline_audit,
        "texas_upstream_reconciliation.csv": texas_audit,
        "repository_raw_source_families.csv": raw_families,
        "repository_election_source_files.csv": election_files,
    }
    for name, frame in output_frames.items():
        frame.to_csv(OUT / name, index=False)

    key_inputs = [
        RAW / "historical_statewide_elections/dataverse_files.zip",
        RAW / "historical_statewide_elections/dataverse_files (1).zip",
        RAW / "historical_statewide_elections/dataverse_files (2).zip",
        RAW / "historical_statewide_elections/dataverse_files (3).zip",
        RAW / "historical_statewide_elections/medsl_github/manifest.csv",
        ROOT / "data/processed/source_audits/openelections_historical_gap_manifest.csv",
        CAL / "historical_southern_extended_v2_panel.csv",
        CAL / "historical_southern_heda_panel.csv",
        CAL / "southern_legislative_probability_panel.csv",
        CAL / "southern_2024_incumbency_races.csv",
        RAW / "historical_statewide_elections/ms_gen_19_prec.zip",
        RAW / "historical_statewide_elections/ms_gen_2023_prec.zip",
        RAW / "historical_statewide_elections/precinctlevelelectionresults2018gen.zip",
        RAW / "historical_statewide_elections/2022-gen-outputofficial.zip",
        RAW / "historical_statewide_elections/2024-gen-outputofficial1.zip",
        RAW / "historical_statewide_elections/results_pct_20221108.zip",
        RAW / "historical_statewide_elections/ga_2022_gen_prec.zip",
        RAW / "historical_statewide_elections/ga_2024_gen_prec_csv.zip",
        RAW / "historical_statewide_elections/tn_2022_gen_prec.zip",
        RAW / "historical_statewide_elections/la_vest_19.zip",
        RAW / "historical_statewide_elections/la_2023_gen_prim_pber.zip",
        ROOT / "data/processed/source_audits/louisiana_legislative_results_manifest.csv",
        INCUMBENCY_ROSTER,
        GENERIC_BALLOT_ENVIRONMENT,
        RAW / "southern_sos_elections/VA/2005/2005_November_General.csv",
        RAW / "southern_sos_elections/VA/2009/2009_November_General.csv",
        RAW / "southern_sos_elections/VA/2013/2013_November_General.csv",
        RAW / "southern_sos_elections/VA/Election Results_2023.csv",
        RAW / "southern_sos_elections/VA/va_vest_17.zip",
        RAW / "southern_sos_elections/VA/va_vest_19_statehouse.zip",
        RAW / "southern_sos_elections/VA/va_vest_19_statesenate.zip",
        RAW / "southern_sos_elections/VA/va_vest_21.zip",
        RAW / "southern_sos_elections/FL/2016/precinctlevelelectionresults2016gen.zip",
        RAW / "southern_sos_elections/NC/2016/results_pct_20161108.zip",
        RAW / "southern_sos_elections/OK/2016/20161108_PrecinctResults_csv_2d9b372099d6.zip",
        RAW / "southern_sos_elections/TN/2016/StateGeneralbyPrecinctNov2016.xlsx",
        RAW / "southern_sos_elections/AR/2016/2016_FullDataFile.json",
        WAR / "cmo_v5_races.csv", WAR / "cmo_v5_candidates.csv",
        TX_ROOT / "data/processed/models/full_history_cmo_candidates.csv",
        TX_ROOT / "data/processed/features/historical_cmo_features.csv",
        TX_ROOT / "data/processed/elections/sos_canonical_candidate_totals_1992_2018.csv",
        TX_ROOT / "data/processed/elections/sos_official_candidate_totals_2020_2024.csv",
        TX_ROOT / "data/raw/tx_sos/OneDrive_2026-08-17.zip",
        texas_tlc_result_file(1998),
    ]
    medsl_manifest = pd.read_csv(RAW / "historical_statewide_elections/medsl_github/manifest.csv")
    key_inputs.extend(ROOT / path for path in medsl_manifest.local_path.astype(str))
    key_inputs.extend(sorted((RAW / "southern_sos_elections/SC/2016").glob("*_detailtxt.zip")))
    key_inputs.extend(sorted((RAW / "openelections_historical_gaps/GA/2016").glob("*.csv")))
    key_inputs.extend(sorted((RAW / "openelections_historical_gaps/MO/2018").glob("*.csv")))
    key_inputs.extend(sorted((RAW / "openelections_historical_gaps/SC/2020").glob("*.csv")))
    key_inputs.extend(sorted((RAW / "historical_statewide_elections/arkansas_2022_openelections/counties").glob("*.csv")))
    output_paths = sorted(OUT.glob("*.csv"))
    manifest = {
        "schema_version": 1,
        "build_id": hashlib.sha256(":".join(sha256(path) for path in key_inputs).encode()).hexdigest()[:20],
        "code_commit": git_commit(),
        "pipeline": rel(Path(__file__)),
        "states": TARGET_STATES,
        "years": [1994, 2024],
        "baseline_policy": [
            "canonical Alabama observed ticket", "Texas official observed ballot-first ticket",
            "Louisiana stage-matched observed statewide ticket",
            "MEDSL observed same-cycle ballot-first ticket",
            "validated historical HEDA/OpenElections/SOS ticket",
            "Virginia same-year governor ticket with cross-election membership (research only)",
            "election-day national generic-ballot polling average when no same-year ticket exists",
            "partial HEDA context (research only)",
            "prior presidential plus realized national swing (research only)",
        ],
        "inputs": [{"path": source_ref(path), "sha256": sha256(path)} for path in key_inputs],
        "outputs": [{"path": rel(path), "rows": len(pd.read_csv(path, low_memory=False)), "sha256": sha256(path)} for path in output_paths],
        "row_counts": {
            "panel": len(panel), "contested_outcomes": int(panel.outcome_eligible.sum()),
            "strict_war_ready": int(panel.strict_war_eligible.sum()),
            "research_war_ready": int(panel.research_war_eligible.sum()),
            "states_with_strict_rows": int(panel.loc[panel.strict_war_eligible, "state"].nunique()),
            "state_years_with_strict_rows": int(panel.loc[panel.strict_war_eligible, ["state", "year"]].drop_duplicates().shape[0]),
        },
        "missing_value_policy": "Missing source observations remain missing and are never converted to zero.",
        "publication_status": "experimental research mart; not canonical or public",
    }
    (OUT / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    assert not panel.duplicated(KEYS).any(), "Selected panel race keys are not unique"
    al = panel[panel.state.eq("AL") & panel.strict_war_eligible]
    assert sorted(al.year.unique().tolist()) == [1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022]
    # 510 after the 2002 Marshall canonical repair (RUN-DFB1D093D7594AB68A264292050E924D) added House 27.
    assert len(al) == 510, f"Expected 510 canonical Alabama WAR races, got {len(al)}"
    assert panel.loc[panel.strict_war_eligible, ["dem_votes", "rep_votes", "baseline_dem_margin", "incumbency_balance"]].notna().all().all()
    return manifest["row_counts"]


def main() -> None:
    counts = build()
    print("Southern WAR panel v1:", ", ".join(f"{key}={value:,}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
