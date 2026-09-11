#!/usr/bin/env python3
"""Load the complete local Southern legislative election history.

Provider observations remain separate.  The schema's canonical view selects an
entire observation set per contest under an explicit authority order, so an
overlapping MEDSL, Klarner, or state file can never double candidate votes.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from load_southern_election_warehouse import (
    SOUTHERN_STATES,
    canonical_name,
    general_election_date,
    party_family,
    stable_id,
)
from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_table, source_file_id


RAW = ROOT / "data/raw/historical_statewide_elections"
AUDIT = ROOT / "data/processed/source_audits"
OUT = ROOT / "data/processed/elections"
SCHEMA = Path(__file__).with_name("warehouse_southern_legislative_history_schema.sql")
KLARNER = RAW / "dataverse_files.zip"
MEDSL_NATIONAL = {2018: RAW / "dataverse_files (3).zip", 2020: RAW / "dataverse_files (2).zip",
                  2024: RAW / "dataverse_files (1).zip"}
MEDSL_GITHUB_MANIFEST = RAW / "medsl_github/manifest.csv"
MS_2023 = RAW / "ms_gen_2023_prec.zip"
VA_2023 = ROOT / "data/raw/southern_sos_elections/VA/Election Results_2023.csv"

STATE_NAMES = {
    "Alabama": "AL", "Arkansas": "AR", "Florida": "FL", "Georgia": "GA",
    "Kentucky": "KY", "Louisiana": "LA", "Mississippi": "MS", "Missouri": "MO",
    "North Carolina": "NC", "Oklahoma": "OK", "South Carolina": "SC",
    "Tennessee": "TN", "Texas": "TX", "Virginia": "VA",
}
DISTRICT_LIMITS = {
    "AL": {"lower": 105, "upper": 35}, "AR": {"lower": 100, "upper": 35},
    "FL": {"lower": 120, "upper": 40}, "GA": {"lower": 180, "upper": 56},
    "KY": {"lower": 100, "upper": 38}, "LA": {"lower": 105, "upper": 39},
    "MS": {"lower": 122, "upper": 52}, "MO": {"lower": 163, "upper": 34},
    "NC": {"lower": 120, "upper": 50}, "OK": {"lower": 101, "upper": 48},
    "SC": {"lower": 124, "upper": 46}, "TN": {"lower": 99, "upper": 33},
    "TX": {"lower": 150, "upper": 31}, "VA": {"lower": 100, "upper": 40},
}
KLARNER_STAGES = {
    "g": "general", "gs": "general", "lafsettled": "general", "larunoff": "other",
    "ssg": "special", "s": "special", "srunoff": "special_runoff",
    "lasrunoff": "special_runoff", "dpsrunoff": "primary_runoff", "rp": "other",
}
MEDSL_PROVIDER = "MIT Election Data and Science Lab"
KLARNER_PROVIDER = "Carl Klarner, State Legislative Election Returns, 1967-2022"
UNKNOWN_TERMS = "reuse terms not retained with local artifact; review required"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def valid_district(state: str, chamber: str, district: object) -> bool:
    try:
        number = int(str(district))
    except (TypeError, ValueError):
        return False
    limit = DISTRICT_LIMITS.get(state, {}).get(chamber)
    return limit is not None and 1 <= number <= limit


def normalized_district(value: object) -> str | None:
    text = "" if value is None or pd.isna(value) else str(value).strip()
    match = re.fullmatch(r"0*(\d+)(?:\.0+)?", text)
    return str(int(match.group(1))) if match else None


def source_catalog() -> list[dict]:
    rows = [{
        "provider": KLARNER_PROVIDER, "path": KLARNER,
        "source_url": "https://doi.org/10.7910/DVN/FJOGJB",
        "retrieved_at_utc": mtime_utc(KLARNER), "retrieval_time_status": "filesystem_mtime_proxy",
        "license_or_terms": UNKNOWN_TERMS, "source_family": "klarner",
        "authoritative_scope": "secondary candidate-contest state legislative general-election returns, 1967-2022",
    }]
    for year, path in MEDSL_NATIONAL.items():
        rows.append({
            "provider": MEDSL_PROVIDER, "path": path,
            "source_url": "https://electionlab.mit.edu/data",
            "retrieved_at_utc": mtime_utc(path), "retrieval_time_status": "filesystem_mtime_proxy",
            "license_or_terms": UNKNOWN_TERMS, "source_family": "medsl_national",
            "authoritative_scope": f"standardized precinct-level {year} general-election returns",
            "year": year,
        })
    if MEDSL_GITHUB_MANIFEST.exists():
        for row in pd.read_csv(MEDSL_GITHUB_MANIFEST, dtype=str).fillna("").to_dict("records"):
            path = ROOT / row["local_path"]
            rows.append({
                "provider": row["provider"], "path": path, "source_url": row["download_url"],
                "retrieved_at_utc": row["retrieved_utc"], "retrieval_time_status": "observed",
                "license_or_terms": UNKNOWN_TERMS, "source_family": "medsl_github",
                "authoritative_scope": "standardized precinct-level legislative and ticket general-election returns",
                "state": row["state"], "year": int(row["year"]),
                "repository": row["repository"], "github_blob_sha": row["github_blob_sha"],
            })
    rows.extend([
        {
            "provider": "Redistricting Data Hub; Mississippi SOS via OpenElections", "path": MS_2023,
            "source_url": "https://github.com/openelections/openelections-data-ms",
            "retrieved_at_utc": mtime_utc(MS_2023), "retrieval_time_status": "filesystem_mtime_proxy",
            "license_or_terms": UNKNOWN_TERMS, "source_family": "rdh_official_derivative",
            "authoritative_scope": "Mississippi 2023 precinct-level general-election results",
            "state": "MS", "year": 2023,
        },
        {
            "provider": "Virginia Department of Elections", "path": VA_2023,
            "source_url": "https://www.elections.virginia.gov/resultsreports/election-results/",
            "retrieved_at_utc": mtime_utc(VA_2023), "retrieval_time_status": "filesystem_mtime_proxy",
            "license_or_terms": "official public record; reuse terms not recorded; review required",
            "source_family": "official_state_direct",
            "authoritative_scope": "Virginia 2023 candidate-by-precinct general-election results",
            "state": "VA", "year": 2023,
        },
    ])
    for row in rows:
        if not row["path"].exists():
            raise FileNotFoundError(row["path"])
        row["local_path"] = rel(row["path"])
        row["sha256"] = sha256(row["path"])
        row["bytes"] = row["path"].stat().st_size
        row["geography_vintage"] = "provider-reported district; plan vintage unverified"
    return rows


def upsert_source(connection: sqlite3.Connection, meta: dict) -> str:
    existing = connection.execute(
        "SELECT source_file_id FROM warehouse_source_file WHERE local_path=?", (meta["local_path"],)
    ).fetchone()
    identifier = existing[0] if existing else source_file_id(meta["provider"], meta["local_path"])
    connection.execute("""
      INSERT INTO warehouse_source_file
      (source_file_id,provider,local_path,original_url,retrieved_at_utc,sha256,media_type,
       license,extraction_status,authoritative_scope)
      VALUES (?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(source_file_id) DO UPDATE SET provider=excluded.provider,
        original_url=excluded.original_url,retrieved_at_utc=excluded.retrieved_at_utc,
        sha256=excluded.sha256,media_type=excluded.media_type,license=excluded.license,
        extraction_status=excluded.extraction_status,authoritative_scope=excluded.authoritative_scope
    """, (identifier, meta["provider"], meta["local_path"], meta["source_url"],
          meta["retrieved_at_utc"], meta["sha256"], "application/zip" if meta["path"].suffix.lower()==".zip" else "text/csv",
          meta["license_or_terms"], "normalized", meta["authoritative_scope"]))
    return identifier


def empty_result() -> tuple[list[dict], list[dict], list[dict]]:
    return [], [], []


def set_record(*, source_id: str, build_run_id: str, provider: str, source_family: str,
               authority_rank: int, state: str, year: int, stage: str, stage_original: str,
               chamber: str, district: str, parser: str, source_member: str | None,
               election_date: str | None, date_status: str, quality: dict,
               validation: str = "passed") -> dict:
    office = "SLDL" if chamber == "lower" else "SLDU"
    observation_set_id = stable_id(
        "LSET", source_id, source_member, state, year, stage_original, chamber, district
    )
    return {
        "observation_set_id": observation_set_id, "build_run_id": build_run_id,
        "source_file_id": source_id, "source_member": source_member, "provider": provider,
        "source_family": source_family, "authority_rank": authority_rank, "state_code": state,
        "cycle": year, "election_date": election_date, "election_date_status": date_status,
        "election_stage": stage, "election_stage_original": stage_original,
        "office_code": office, "chamber": chamber,
        "district_plan_id": f"{state}-{year}-{chamber}-reported-unknown-vintage",
        "geography_vintage": "provider-reported district; plan vintage unverified",
        "district": district, "district_original": district,
        "source_coverage": "district_total", "contest_status": "unknown",
        "parser_name": parser, "quality_flags_json": json.dumps(quality, sort_keys=True),
        "validation_status": validation, "as_of_utc": datetime.now(timezone.utc).isoformat(),
    }


def finalize_candidates(sets: list[dict], candidates: list[dict]) -> None:
    collapsed: dict[tuple, dict] = {}
    for row in candidates:
        key = (row["observation_set_id"], row["candidate_name"], row["party_family"], row.get("party_original"))
        if key not in collapsed:
            collapsed[key] = dict(row)
            collapsed[key]["_original_names"] = {row["candidate_name_original"]}
            collapsed[key]["_source_ids"] = {row.get("candidate_source_id")} - {None}
            continue
        current = collapsed[key]
        current["_original_names"].add(row["candidate_name_original"])
        if row.get("candidate_source_id"):
            current["_source_ids"].add(row["candidate_source_id"])
        if current["votes"] is None:
            current["votes"] = row["votes"]
        elif row["votes"] is not None:
            current["votes"] += row["votes"]
        current["vote_value_status"] = "observed" if current["votes"] is not None else "unknown"
        current["writein_status"] = "true" if "true" in {current["writein_status"], row["writein_status"]} else "false"
        if current.get("incumbent_status") != row.get("incumbent_status"):
            current["incumbent_status"] = None
        if current.get("winner_status") != row.get("winner_status"):
            current["winner_status"] = None
        if row["validation_status"] == "review":
            current["validation_status"] = "review"
    candidates[:] = list(collapsed.values())
    for row in candidates:
        row["candidate_name_original"] = "|".join(sorted(row.pop("_original_names")))
        row["candidate_source_id"] = "|".join(sorted(row.pop("_source_ids"))) or None
    by_set: dict[str, list[dict]] = defaultdict(list)
    for row in candidates:
        by_set[row["observation_set_id"]].append(row)
    as_of = datetime.now(timezone.utc).isoformat()
    for source_set in sets:
        rows = by_set[source_set["observation_set_id"]]
        denominator = sum(row["votes"] for row in rows if row["votes"] is not None)
        for row in rows:
            row["vote_share"] = row["votes"] / denominator if row["votes"] is not None and denominator > 0 else None
            row["source_candidate_result_id"] = stable_id(
                "LCAND", source_set["observation_set_id"], row["candidate_name"],
                row["party_family"], row.get("party_original")
            )
            row["as_of_utc"] = as_of


def parse_klarner(meta: dict, source_id: str, run_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    member = "208slers_uoa_cand_contest20230810.csv"
    usecols = ["year", "state", "sen", "dno", "geopost", "mmdpost", "specpost", "dseats", "eseats",
               "etype", "candid", "cand", "partyt", "exper", "vote", "outcome", "dontuse", "vmiss",
               "bigthird", "mixeduncont", "partuncont", "uncont"]
    with zipfile.ZipFile(meta["path"]) as archive:
        frame = pd.read_csv(archive.open(member), usecols=usecols, low_memory=False)
    frame = frame[
        frame.state.isin(STATE_NAMES) & frame.dseats.eq(1) & frame.eseats.eq(1)
        & frame.etype.isin(KLARNER_STAGES)
    ].copy()
    frame["state_code"] = frame.state.map(STATE_NAMES)
    frame["chamber"] = frame.sen.map({0: "lower", 1: "upper"})
    frame["district"] = frame.dno.map(normalized_district)
    sets, candidates = [], []
    group_keys = ["state_code", "year", "chamber", "district", "etype"]
    for key, group in frame.groupby(group_keys, dropna=False, sort=True):
        state, year, chamber, district, etype = key
        district = None if pd.isna(district) else str(district)
        source_bad = bool(group.dontuse.fillna(0).astype(float).gt(0).any())
        # Klarner's dontuse flag is an analytical/modeling exclusion, not a
        # declaration that the candidate-contest observation did not occur.
        # Preserve it in quality_flags_json while validating source structure
        # independently for the warehouse fact layer.
        validation = "passed" if district and valid_district(state, chamber, district) else "review"
        unknown_date = state == "LA" or KLARNER_STAGES[etype] not in {"general"}
        source_set = set_record(
            source_id=source_id, build_run_id=run_id, provider=meta["provider"], source_family="klarner",
            authority_rank=30, state=state, year=int(year), stage=KLARNER_STAGES[etype],
            stage_original=f"Klarner etype={etype}", chamber=chamber, district=district or "UNKNOWN",
            parser="parse_klarner_candidate_contests", source_member=member,
            election_date=None if unknown_date else general_election_date(int(year)),
            date_status="unknown" if unknown_date else "derived",
            quality={"dontuse": source_bad, "vmiss": bool(group.vmiss.fillna(0).astype(float).gt(0).any()),
                     "bigthird": bool(group.bigthird.fillna(0).astype(float).gt(0).any()),
                     "uncont": bool(group.uncont.fillna(0).astype(float).gt(0).any()),
                     "source_etype": etype}, validation=validation,
        )
        sets.append(source_set)
        for _, row in group.iterrows():
            original = "" if pd.isna(row.cand) else str(row.cand).strip()
            name = canonical_name(original) or "[UNKNOWN CANDIDATE]"
            code = "" if pd.isna(row.partyt) else str(row.partyt).strip().lower()
            family = {"d": "democratic", "r": "republican", "nm": "other", "w": "other", "m": "other"}.get(code, "unknown")
            vote = None if pd.isna(row.vote) else int(round(float(row.vote)))
            candidate_validation = "passed" if validation == "passed" and original else "review"
            candidates.append({
                "observation_set_id": source_set["observation_set_id"],
                "candidate_source_id": None if pd.isna(row.candid) else str(int(row.candid)),
                "candidate_name": name, "candidate_name_original": original or "[missing in source]",
                "party_family": family, "party_original": code or None, "votes": vote,
                "vote_value_status": "unknown" if vote is None else "observed",
                "writein_status": "true" if code == "w" else "false",
                "incumbent_status": 1 if str(row.exper).lower()=="inc" else (0 if str(row.exper).lower()=="none" else None),
                "winner_status": 1 if str(row.outcome).lower()=="w" else (0 if str(row.outcome).lower()=="l" else None),
                "validation_status": candidate_validation,
            })
    finalize_candidates(sets, candidates)
    observed_input = int(frame.vote.notna().sum())
    observed_votes = int(pd.to_numeric(frame.vote, errors="coerce").sum())
    output_votes = sum(row["votes"] for row in candidates if row["votes"] is not None)
    audit = [{
        "reconciliation_id": stable_id("LREC", source_id, member), "build_run_id": run_id,
        "source_file_id": source_id, "source_member": member, "state_code": None, "cycle": None,
        "parser_name": "parse_klarner_candidate_contests", "input_rows": len(frame),
        "output_candidate_rows": len(candidates), "input_votes": observed_votes,
        "output_votes": output_votes, "vote_delta": output_votes-observed_votes,
        "unknown_vote_rows": int(frame.vote.isna().sum()),
        "reconciliation_status": "exact" if output_votes==observed_votes else "review",
        "note": (f"All {observed_input:,} finite vote rows preserved; null votes remain unknown. "
                 "Canonical-name collisions, if any, retain joined original spellings."),
    }]
    return sets, candidates, audit


MEDSL_COLS = ["precinct", "office", "party_detailed", "party_simplified", "mode", "votes",
              "county_name", "county_fips", "candidate", "district", "year", "stage", "special",
              "writein", "state_po", "date"]


def read_medsl_member(archive: zipfile.ZipFile, member: str, states: set[str]) -> pd.DataFrame:
    chunks = []
    with archive.open(member) as handle:
        for chunk in pd.read_csv(handle, usecols=lambda c: c in MEDSL_COLS, low_memory=False, chunksize=200_000):
            state_mask = chunk.state_po.astype(str).str.upper().isin(states)
            office_mask = chunk.office.astype(str).str.upper().isin(["STATE HOUSE", "STATE SENATE"])
            selected = chunk[state_mask & office_mask].copy()
            if not selected.empty:
                chunks.append(selected)
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=MEDSL_COLS)


def medsl_inputs(meta: dict) -> list[tuple[str, int, str, pd.DataFrame]]:
    result = []
    with zipfile.ZipFile(meta["path"]) as archive:
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if meta["source_family"] == "medsl_github":
            member = csv_members[0]
            frame = read_medsl_member(archive, member, {meta["state"]})
            result.append((meta["state"], int(meta["year"]), member, frame))
        elif int(meta["year"]) in {2018, 2020}:
            year = int(meta["year"])
            lower_members = {name.lower(): name for name in csv_members}
            for state in SOUTHERN_STATES:
                suffix = f"{year}-{state.lower()}-precinct-general.csv"
                member = next((original for lower, original in lower_members.items() if lower.endswith(suffix)), None)
                if member:
                    result.append((state, year, member, read_medsl_member(archive, member, {state})))
        else:
            member = next(name for name in csv_members if name.lower().endswith("state_precinct_general.csv"))
            frame = read_medsl_member(archive, member, set(SOUTHERN_STATES))
            for state, state_frame in frame.groupby(frame.state_po.astype(str).str.upper(), sort=True):
                result.append((state, int(meta["year"]), member, state_frame.copy()))
    return result


def parse_medsl(meta: dict, source_id: str, run_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    all_sets, all_candidates, audits = [], [], []
    authority = 20 if meta["source_family"] == "medsl_github" else 25
    for expected_state, expected_year, member, frame in medsl_inputs(meta):
        if frame.empty:
            audits.append({
                "reconciliation_id": stable_id("LREC", source_id, member, expected_state), "build_run_id": run_id,
                "source_file_id": source_id, "source_member": member, "state_code": expected_state,
                "cycle": expected_year, "parser_name": "parse_medsl_precinct_returns", "input_rows": 0,
                "output_candidate_rows": 0, "input_votes": 0, "output_votes": 0, "vote_delta": 0,
                "unknown_vote_rows": 0, "reconciliation_status": "not_available",
                "note": "Archive/member has no legislative rows for this state-year.",
            })
            continue
        frame["state_code"] = frame.state_po.astype(str).str.upper()
        frame["year_num"] = pd.to_numeric(frame.year, errors="coerce").fillna(expected_year).astype(int)
        frame["district_num"] = frame.district.map(normalized_district)
        frame["votes_num"] = pd.to_numeric(frame.votes, errors="coerce")
        frame["candidate_original"] = frame.candidate.fillna("").astype(str).str.strip()
        frame["party_original"] = frame.party_simplified.fillna(frame.party_detailed).fillna("").astype(str).str.strip()
        frame["special_bool"] = frame.special.astype(str).str.lower().isin(["true", "1", "yes"])
        frame["writein_bool"] = frame.writein.astype(str).str.lower().isin(["true", "1", "yes"])
        frame["date_text"] = frame.date.fillna("").astype(str).str[:10]
        frame["stage_text"] = frame.stage.fillna("GEN").astype(str).str.upper()
        frame["county_key"] = frame.county_fips.fillna(frame.county_name).astype(str).str.upper().str.strip()
        frame["precinct_key"] = frame.precinct.astype(str).str.upper().str.strip()
        malformed = frame.district_num.isna() | frame.votes_num.isna() | frame.candidate_original.eq("")
        usable = frame[~malformed].copy()
        key = ["state_code", "year_num", "date_text", "stage_text", "special_bool", "county_key", "precinct_key",
               "office", "district_num", "candidate_original", "party_original", "writein_bool"]
        usable["has_total"] = usable["mode"].astype(str).str.upper().eq("TOTAL").groupby(
            [usable[column] for column in key], dropna=False
        ).transform("max")
        total_mode = usable["mode"].astype(str).str.upper().eq("TOTAL")
        usable = usable[(~usable.has_total) | total_mode].copy()
        input_votes = int(usable.votes_num.sum())
        candidate_group = ["state_code", "year_num", "date_text", "stage_text", "special_bool", "office",
                           "district_num", "candidate_original", "party_original", "writein_bool"]
        aggregated = usable.groupby(candidate_group, dropna=False, as_index=False).agg(
            votes=("votes_num", "sum"), reported_geographies=("precinct_key", "nunique")
        )
        for contest_key, group in aggregated.groupby(
            ["state_code", "year_num", "date_text", "stage_text", "special_bool", "office", "district_num"],
            dropna=False, sort=True
        ):
            state, year, date_text, stage_text, special, office, district = contest_key
            chamber = "lower" if str(office).upper()=="STATE HOUSE" else "upper"
            district_text = str(int(district))
            stage = "special" if special else ("general" if stage_text=="GEN" else "other")
            validation = "passed" if valid_district(state, chamber, district_text) else "review"
            source_set = set_record(
                source_id=source_id, build_run_id=run_id, provider=meta["provider"],
                source_family=meta["source_family"], authority_rank=authority, state=state, year=int(year),
                stage=stage, stage_original=f"MEDSL stage={stage_text}; special={bool(special)}",
                chamber=chamber, district=district_text, parser="parse_medsl_precinct_returns",
                source_member=member, election_date=date_text or None,
                date_status="observed" if date_text else "unknown",
                quality={"reported_precincts": int(group.reported_geographies.max()),
                         "mode_total_precedence": True, "contested_only_possible": int(year)==2024},
                validation=validation,
            )
            all_sets.append(source_set)
            for _, row in group.iterrows():
                original = row.candidate_original
                original_party = row.party_original or None
                all_candidates.append({
                    "observation_set_id": source_set["observation_set_id"], "candidate_source_id": None,
                    "candidate_name": canonical_name(original), "candidate_name_original": original,
                    "party_family": party_family(original_party), "party_original": original_party,
                    "votes": int(round(float(row.votes))), "vote_value_status": "observed",
                    "writein_status": "true" if row.writein_bool else "false",
                    "incumbent_status": None, "winner_status": None,
                    "validation_status": validation,
                })
        output_votes = sum(row["votes"] for row in all_candidates if row["observation_set_id"] in
                           {source_set["observation_set_id"] for source_set in all_sets if source_set["source_member"]==member
                            and source_set["state_code"]==expected_state and source_set["cycle"]==expected_year})
        audits.append({
            "reconciliation_id": stable_id("LREC", source_id, member, expected_state, expected_year),
            "build_run_id": run_id, "source_file_id": source_id, "source_member": member,
            "state_code": expected_state, "cycle": expected_year,
            "parser_name": "parse_medsl_precinct_returns", "input_rows": len(usable),
            "output_candidate_rows": len(aggregated), "input_votes": input_votes,
            "output_votes": output_votes, "vote_delta": output_votes-input_votes,
            "unknown_vote_rows": int(malformed.sum()),
            "reconciliation_status": "exact" if output_votes==input_votes else "review",
            "note": f"{int(malformed.sum())} malformed legislative precinct rows excluded to review.",
        })
    finalize_candidates(all_sets, all_candidates)
    return all_sets, all_candidates, audits


def parse_ms_2023(meta: dict, source_id: str, run_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    with zipfile.ZipFile(meta["path"]) as archive:
        member = next(name for name in archive.namelist() if name.lower().endswith("_prec.csv"))
        frame = pd.read_csv(archive.open(member), low_memory=False)
        readme_name = next(name for name in archive.namelist() if name.lower().endswith("readme.txt"))
        readme = archive.read(readme_name).decode("utf-8", errors="replace")
    mappings = {}
    for line in readme.splitlines():
        match = re.match(r"(GS(?:L\d{3}|U\d{2})[A-Z0-9]+)\s+(.+?)-:-([A-Z]+)-:-State (House|Senate)-(\d+)\s*$", line.strip())
        if match:
            code, name, party, office, district = match.groups()
            mappings[code] = (name.strip(), party.strip(), office.lower(), district)
    sets, candidates = [], []
    contests: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    for code, (name, party, office, district) in sorted(mappings.items()):
        if code in frame.columns:
            contests[(office, district)].append((code, name, party))
    for (office, district), contest_candidates in sorted(contests.items()):
        chamber = "lower" if office == "house" else "upper"
        validation = "passed" if valid_district("MS", chamber, district) else "review"
        source_set = set_record(
            source_id=source_id, build_run_id=run_id, provider=meta["provider"],
            source_family=meta["source_family"], authority_rank=15, state="MS", year=2023,
            stage="general", stage_original="General", chamber=chamber, district=district,
            parser="parse_mississippi_rdh_wide", source_member=member, election_date="2023-11-07",
            date_status="observed",
            quality={"field_codes": [item[0] for item in contest_candidates], "readme_mapping": True},
            validation=validation,
        )
        sets.append(source_set)
        for code, name, party in contest_candidates:
            votes = pd.to_numeric(frame[code], errors="coerce")
            total = None if votes.notna().sum()==0 else int(votes.sum())
            candidates.append({
                "observation_set_id": source_set["observation_set_id"], "candidate_source_id": code,
                "candidate_name": canonical_name(name), "candidate_name_original": name,
                "party_family": party_family(party), "party_original": party, "votes": total,
                "vote_value_status": "unknown" if total is None else "observed", "writein_status": "false",
                "incumbent_status": None, "winner_status": None, "validation_status": validation,
            })
    finalize_candidates(sets, candidates)
    output_votes = sum(row["votes"] for row in candidates if row["votes"] is not None)
    input_votes = sum(int(pd.to_numeric(frame[code], errors="coerce").sum()) for code in mappings if code in frame)
    audit = [{
        "reconciliation_id": stable_id("LREC", source_id, member), "build_run_id": run_id,
        "source_file_id": source_id, "source_member": member, "state_code": "MS", "cycle": 2023,
        "parser_name": "parse_mississippi_rdh_wide", "input_rows": len(frame),
        "output_candidate_rows": len(candidates), "input_votes": input_votes, "output_votes": output_votes,
        "vote_delta": output_votes-input_votes,
        "unknown_vote_rows": sum(row["votes"] is None for row in candidates),
        "reconciliation_status": "exact" if input_votes==output_votes else "review",
        "note": "Candidate, party, chamber, and district labels decoded from the ZIP README.",
    }]
    return sets, candidates, audit


def parse_va_2023(meta: dict, source_id: str, run_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    frame = pd.read_csv(meta["path"], low_memory=False)
    frame = frame[frame.DistrictType.astype(str).str.lower().isin(["state-house", "state-senate"])].copy()
    frame["district"] = frame.DistrictName.astype(str).str.extract(r"(\d+)", expand=False)
    frame["votes"] = pd.to_numeric(frame.TOTAL_VOTES, errors="coerce")
    group_keys = ["ElectionDate", "ElectionType", "DistrictType", "district", "CandidateId", "CandidateName", "Party", "WriteInVote"]
    aggregated = frame.groupby(group_keys, dropna=False, as_index=False).agg(votes=("votes", lambda x: x.sum(min_count=1)))
    sets, candidates = [], []
    for contest_key, group in aggregated.groupby(["ElectionDate", "ElectionType", "DistrictType", "district"], dropna=False):
        election_date, election_type, district_type, district = contest_key
        chamber = "lower" if district_type == "state-house" else "upper"
        district = str(int(float(district))) if not pd.isna(district) else "UNKNOWN"
        validation = "passed" if valid_district("VA", chamber, district) else "review"
        stage = "special" if "special" in str(election_type).lower() else "general"
        source_set = set_record(
            source_id=source_id, build_run_id=run_id, provider=meta["provider"],
            source_family=meta["source_family"], authority_rank=10, state="VA", year=2023,
            stage=stage, stage_original=str(election_type), chamber=chamber, district=district,
            parser="parse_virginia_2023_candidate_precinct", source_member=None,
            election_date=pd.to_datetime(election_date).date().isoformat(), date_status="observed",
            quality={"candidate_precinct_rows": int(len(frame)), "number_of_seats_expected": 1},
            validation=validation,
        )
        sets.append(source_set)
        for _, row in group.iterrows():
            vote = None if pd.isna(row.votes) else int(round(float(row.votes)))
            original_party = None if pd.isna(row.Party) else str(row.Party)
            candidates.append({
                "observation_set_id": source_set["observation_set_id"],
                "candidate_source_id": None if pd.isna(row.CandidateId) else str(row.CandidateId),
                "candidate_name": canonical_name(row.CandidateName), "candidate_name_original": str(row.CandidateName),
                "party_family": party_family(original_party), "party_original": original_party,
                "votes": vote, "vote_value_status": "unknown" if vote is None else "observed",
                "writein_status": "true" if str(row.WriteInVote).lower() in {"1","true"} else "false",
                "incumbent_status": None, "winner_status": None, "validation_status": validation,
            })
    finalize_candidates(sets, candidates)
    input_votes = int(frame.votes.sum())
    output_votes = sum(row["votes"] for row in candidates if row["votes"] is not None)
    audit = [{
        "reconciliation_id": stable_id("LREC", source_id, "VA2023"), "build_run_id": run_id,
        "source_file_id": source_id, "source_member": None, "state_code": "VA", "cycle": 2023,
        "parser_name": "parse_virginia_2023_candidate_precinct", "input_rows": len(frame),
        "output_candidate_rows": len(candidates), "input_votes": input_votes, "output_votes": output_votes,
        "vote_delta": output_votes-input_votes, "unknown_vote_rows": int(frame.votes.isna().sum()),
        "reconciliation_status": "exact" if input_votes==output_votes else "review",
        "note": "Precinct candidate votes aggregated to provider-reported legislative districts.",
    }]
    return sets, candidates, audit


def scheduled_post2016_keys() -> set[tuple[str, int, str]]:
    keys: set[tuple[str, int, str]] = set()
    for state in ["AR", "FL", "GA", "KY", "MO", "NC", "OK", "TN", "TX"]:
        for year in [2018, 2020, 2022, 2024]:
            keys.update({(state, year, "lower"), (state, year, "upper")})
    for year in [2018, 2022]:
        keys.update({("AL", year, "lower"), ("AL", year, "upper")})
    for state in ["LA", "MS"]:
        for year in [2019, 2023]:
            keys.update({(state, year, "lower"), (state, year, "upper")})
    for year in [2018, 2020, 2022, 2024]:
        keys.add(("SC", year, "lower"))
    for year in [2020, 2024]:
        keys.add(("SC", year, "upper"))
    for year in [2019, 2021, 2023]:
        keys.add(("VA", year, "lower"))
    for year in [2019, 2023]:
        keys.add(("VA", year, "upper"))
    return keys


def export_loaded(database: Path | None, run_id: str) -> dict:
    with closing(connect(database, readonly=True)) as connection:
        history = pd.read_sql_query("SELECT * FROM fact_southern_legislative_candidate_election ORDER BY state_code,cycle,chamber,district,candidate_name", connection)
        coverage = pd.read_sql_query("SELECT * FROM qa_southern_legislative_canonical_coverage ORDER BY state_code,cycle,chamber", connection)
        final_history = pd.read_sql_query(
            "SELECT * FROM fact_southern_legislative_final_candidate_election "
            "ORDER BY state_code,cycle,chamber,district,candidate_name", connection
        )
        competition_coverage = pd.read_sql_query(
            "SELECT * FROM qa_southern_legislative_final_competition_coverage "
            "ORDER BY state_code,cycle,chamber", connection
        )
        reconciliation = pd.read_sql_query(
            "SELECT * FROM qa_southern_legislative_source_reconciliation WHERE build_run_id=? ORDER BY source_file_id,state_code,cycle",
            connection, params=(run_id,)
        )
        run = connection.execute("SELECT code_commit,validation_json FROM warehouse_build_run WHERE build_run_id=?", (run_id,)).fetchone()
    OUT.mkdir(parents=True, exist_ok=True); AUDIT.mkdir(parents=True, exist_ok=True)
    history.to_csv(OUT / "southern_legislative_candidate_history.csv.gz", index=False,
                   compression={"method": "gzip", "mtime": 0})
    final_history.to_csv(OUT / "southern_legislative_final_candidate_history.csv.gz", index=False,
                         compression={"method": "gzip", "mtime": 0})
    coverage.to_csv(AUDIT / "southern_legislative_history_coverage.csv", index=False)
    competition_coverage.to_csv(
        AUDIT / "southern_legislative_final_competition_coverage.csv", index=False
    )
    reconciliation.to_csv(AUDIT / "southern_legislative_history_reconciliation.csv", index=False)
    manifest = {"contract_version": 2, "pipeline": "scripts/load_southern_legislative_history_warehouse.py",
                "build_run_id": run_id, "code_version": run[0], "validation": json.loads(run[1]),
                "outputs": ["data/processed/elections/southern_legislative_candidate_history.csv.gz",
                            "data/processed/elections/southern_legislative_final_candidate_history.csv.gz",
                            "data/processed/source_audits/southern_legislative_history_coverage.csv",
                            "data/processed/source_audits/southern_legislative_final_competition_coverage.csv",
                            "data/processed/source_audits/southern_legislative_history_reconciliation.csv"]}
    (AUDIT / "southern_legislative_history_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


OWNED_SOURCE_FAMILIES = ("klarner", "medsl_github", "medsl_national",
                         "official_state_direct", "rdh_official_derivative")
OWNED_SOURCE_PARSERS = ("parse_klarner_candidate_contests", "parse_medsl_precinct_returns",
                        "parse_mississippi_rdh_wide", "parse_virginia_2023_candidate_precinct")


def clear_owned_history_sources(connection: sqlite3.Connection) -> None:
    """Refresh only this loader's observations; retain independently owned data."""
    placeholders = ",".join("?" for _ in OWNED_SOURCE_FAMILIES)
    # An empty MEDSL input emits QA without any observation set. Parser
    # provenance owns those rows too; a set-only join would retain stale IDs.
    parser_placeholders = ",".join("?" for _ in OWNED_SOURCE_PARSERS)
    connection.execute(f"""DELETE FROM qa_southern_legislative_source_reconciliation
        WHERE parser_name IN ({parser_placeholders})""", OWNED_SOURCE_PARSERS)
    connection.execute(f"""DELETE FROM source_southern_legislative_candidate_result
        WHERE observation_set_id IN (SELECT observation_set_id
          FROM source_southern_legislative_observation_set
          WHERE source_family IN ({placeholders}))""", OWNED_SOURCE_FAMILIES)
    connection.execute(f"""DELETE FROM source_southern_legislative_observation_set
        WHERE source_family IN ({placeholders})""", OWNED_SOURCE_FAMILIES)


def build(database: Path | None = None) -> dict:
    sources = source_catalog()
    with closing(connect(database)) as connection:
        initialize(connection)
        connection.executescript((Path(__file__).with_name("warehouse_southern_elections_schema.sql")).read_text(encoding="utf-8"))
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run_id = begin_run(connection, "southern_legislative_election_history", {
            "contract_version": 2, "states": list(SOUTHERN_STATES), "source_files": len(sources),
            "source_years": "all locally available through 2024",
        })
        connection.commit(); connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM canonical_southern_legislative_candidate_election")
        clear_owned_history_sources(connection)
        source_ids = {meta["local_path"]: upsert_source(connection, meta) for meta in sources}
        all_sets, all_candidates, all_audits = [], [], []
        for meta in sources:
            source_id = source_ids[meta["local_path"]]
            if meta["source_family"] == "klarner":
                parsed = parse_klarner(meta, source_id, run_id)
            elif meta["source_family"].startswith("medsl_"):
                parsed = parse_medsl(meta, source_id, run_id)
            elif meta["state"] == "MS":
                parsed = parse_ms_2023(meta, source_id, run_id)
            else:
                parsed = parse_va_2023(meta, source_id, run_id)
            sets, candidates, audits = parsed
            all_sets.extend(sets); all_candidates.extend(candidates); all_audits.extend(audits)

        set_columns = [row[1] for row in connection.execute("PRAGMA table_info(source_southern_legislative_observation_set)")]
        candidate_columns = [row[1] for row in connection.execute("PRAGMA table_info(source_southern_legislative_candidate_result)")]
        audit_columns = [row[1] for row in connection.execute("PRAGMA table_info(qa_southern_legislative_source_reconciliation)")]
        connection.executemany(
            f"INSERT INTO source_southern_legislative_observation_set ({','.join(set_columns)}) VALUES ({','.join('?' for _ in set_columns)})",
            [tuple(row.get(column) for column in set_columns) for row in all_sets]
        )
        connection.executemany(
            f"INSERT INTO source_southern_legislative_candidate_result ({','.join(candidate_columns)}) VALUES ({','.join('?' for _ in candidate_columns)})",
            [tuple(row.get(column) for column in candidate_columns) for row in all_candidates]
        )
        connection.executemany(
            f"INSERT INTO qa_southern_legislative_source_reconciliation ({','.join(audit_columns)}) VALUES ({','.join('?' for _ in audit_columns)})",
            [tuple(row.get(column) for column in audit_columns) for row in all_audits]
        )
        connection.execute("""INSERT INTO canonical_southern_legislative_candidate_election
          SELECT * FROM resolved_southern_legislative_candidate_election""")

        bad_fk = connection.execute("PRAGMA foreign_key_check").fetchall()
        duplicate_source = connection.execute("""SELECT COUNT(*) FROM (
          SELECT observation_set_id,candidate_name,party_family,coalesce(party_original,''),COUNT(*) n
          FROM source_southern_legislative_candidate_result GROUP BY 1,2,3,4 HAVING n>1)""").fetchone()[0]
        duplicate_fact = connection.execute("""SELECT COUNT(*) FROM (
          SELECT state_code,cycle,election_stage,chamber,district,candidate_name,party_family,
                 coalesce(party_original,''),COUNT(*) n
          FROM fact_southern_legislative_candidate_election GROUP BY 1,2,3,4,5,6,7,8 HAVING n>1)""").fetchone()[0]
        actual_keys = set(connection.execute("""SELECT DISTINCT state_code,cycle,chamber
          FROM fact_southern_legislative_candidate_election WHERE cycle BETWEEN 2018 AND 2024""").fetchall())
        missing_scheduled = sorted(scheduled_post2016_keys()-actual_keys)
        louisiana_runoff_without_first_round = connection.execute("""SELECT COUNT(*) FROM (
          SELECT DISTINCT cycle,chamber,district
          FROM fact_southern_legislative_candidate_election r
          WHERE state_code='LA' AND cycle>=1995 AND election_stage='other'
            AND NOT EXISTS (
              SELECT 1 FROM fact_southern_legislative_candidate_election f
              WHERE f.state_code='LA' AND f.cycle=r.cycle AND f.chamber=r.chamber
                AND f.district=r.district AND f.election_stage='general'
            ))""").fetchone()[0]
        duplicate_final_contests = connection.execute("""SELECT COUNT(*) FROM (
          SELECT state_code,cycle,chamber,district,COUNT(DISTINCT observation_set_id) n
          FROM fact_southern_legislative_final_candidate_election
          GROUP BY 1,2,3,4 HAVING n>1)""").fetchone()[0]
        bad_reconciliation = connection.execute("""SELECT COUNT(*) FROM qa_southern_legislative_source_reconciliation
          WHERE reconciliation_status='review'""").fetchone()[0]
        if (bad_fk or duplicate_source or duplicate_fact or missing_scheduled or bad_reconciliation
                or louisiana_runoff_without_first_round or duplicate_final_contests):
            raise ValueError(f"Legislative history validation failed: foreign_keys={bad_fk[:3]}, "
                             f"source_duplicates={duplicate_source}, fact_duplicates={duplicate_fact}, "
                             f"missing_scheduled={missing_scheduled}, reconciliation_review={bad_reconciliation}, "
                             f"louisiana_runoff_without_first_round={louisiana_runoff_without_first_round}, "
                             f"duplicate_final_contests={duplicate_final_contests}")
        canonical_rows = connection.execute("SELECT COUNT(*) FROM fact_southern_legislative_candidate_election").fetchone()[0]
        canonical_states = connection.execute("SELECT COUNT(DISTINCT state_code) FROM fact_southern_legislative_candidate_election").fetchone()[0]
        min_year, max_year = connection.execute("SELECT MIN(cycle),MAX(cycle) FROM fact_southern_legislative_candidate_election").fetchone()
        validation = {
            "source_observation_sets": len(all_sets), "source_candidate_results": len(all_candidates),
            "canonical_candidate_results": canonical_rows, "canonical_states": canonical_states,
            "first_year": min_year, "last_year": max_year, "source_files": len(sources),
            "scheduled_2018_2024_state_cycle_chambers": len(scheduled_post2016_keys()),
            "scheduled_2018_2024_missing": 0, "reconciliation_review": 0,
            "foreign_key_violations": 0, "source_duplicate_keys": 0, "canonical_duplicate_keys": 0,
            "louisiana_runoff_without_first_round": 0, "duplicate_final_contests": 0,
        }
        register_table(connection, "source_southern_legislative_observation_set", "source", __file__,
                       "observation_set_id", "Provider observations coexist; no cross-source vote summation", "replace",
                       "One provider-specific state legislative contest observation")
        register_table(connection, "source_southern_legislative_candidate_result", "source", __file__,
                       "source_candidate_result_id", "Candidate-party result within one provider observation set", "replace",
                       "Klarner, MEDSL, and modern state-source candidate results")
        register_table(connection, "all_southern_legislative_candidate_election_observations", "source", __file__,
                       "candidate_result_id + observation_set_id", "Retains all official and secondary observations", "view",
                       "Union of Alabama canonical, official state, MEDSL, Klarner, and modern gap observations")
        register_table(connection, "canonical_southern_legislative_candidate_election", "canonical", __file__,
                       "candidate_result_id", "Materialized whole-contest authority selection", "replace",
                       "Validated materialization behind the comprehensive Southern legislative fact view")
        register_table(connection, "fact_southern_legislative_candidate_election", "canonical", __file__,
                       "candidate_result_id", "Alabama canonical, official state, MEDSL GitHub, MEDSL national, Klarner", "view",
                       "Authority-ranked complete Southern legislative candidate history")
        register_table(connection, "qa_southern_legislative_canonical_coverage", "qa", __file__,
                       "state_code + cycle + chamber", "Observed coverage only; absent contests never become zero", "view",
                       "Canonical legislative history coverage by state, cycle, and chamber")
        register_table(connection, "fact_southern_legislative_final_candidate_election", "mart", __file__,
                       "candidate_result_id", "Louisiana runoff if present, otherwise first round; other states regular general", "view",
                       "One final regular-cycle contest stage for comparable legislative outcome modeling")
        register_table(connection, "qa_southern_legislative_final_competition_coverage", "qa", __file__,
                       "state_code + cycle + chamber", "Exactly one positive-vote Democrat and Republican defines WAR eligibility", "view",
                       "Final-contest and model-eligible competition coverage")
        finish_run(connection, run_id, validation)
        connection.commit()

    manifest_frame = pd.DataFrame([{key: value for key, value in row.items() if key != "path"} for row in sources])
    AUDIT.mkdir(parents=True, exist_ok=True)
    manifest_frame.to_csv(AUDIT / "southern_legislative_history_source_manifest.csv", index=False)
    return export_loaded(database, run_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    result = build(args.database)
    print(json.dumps(result["validation"], indent=2))


if __name__ == "__main__":
    main()
