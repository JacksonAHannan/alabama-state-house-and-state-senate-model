#!/usr/bin/env python3
"""Acquire election-year ACS SLD demographics for Southern WAR v4.

Each Census API response is retained as immutable raw evidence.  The derived
panel uses the exact scheduled state/cycle/chamber keys from the election-year
geometry contract and never fills an unavailable estimate with zero.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pandas as pd
import requests

from southern_war_map_contract import scheduled_keys_2016_2022


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/census/southern_sld_acs_2017_2022"
OUT = ROOT / "data/processed/war/post2016_southern_war_v4/acs_demographics.csv"
MANIFEST = ROOT / "data/processed/source_audits/southern_war_v4_acs_manifest.csv"
STATE_FIPS = {
    "AL": "01", "AR": "05", "FL": "12", "GA": "13", "KY": "21", "LA": "22",
    "MS": "28", "MO": "29", "NC": "37", "OK": "40", "SC": "45", "TN": "47",
    "TX": "48", "VA": "51",
}
COLLEGE = ["B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]
VARIABLES = [
    "NAME", "B03002_001E", "B03002_003E", "B15003_001E", *COLLEGE,
    "C15002H_001E", "C15002H_006E", "C15002H_011E",
]


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


def api_key() -> str:
    for name in (".env", "token.env"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("CENSUS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("CENSUS_API_KEY", "")


def schedule() -> list[tuple[str, int, str]]:
    return [key for key in sorted(scheduled_keys_2016_2022()) if int(key[1]) > 2016]


def query(year: int, state: str, chamber: str) -> tuple[str, dict[str, str]]:
    geography = (
        "state legislative district (upper chamber)" if chamber == "upper"
        else "state legislative district (lower chamber)"
    )
    params = {
        "get": ",".join(VARIABLES),
        "for": f"{geography}:*",
        "in": f"state:{STATE_FIPS[state]}",
    }
    key = api_key()
    if key:
        params["key"] = key
    return f"https://api.census.gov/data/{year}/acs/acs5", params


def raw_path(year: int, state: str, chamber: str) -> Path:
    return RAW / f"acs5_{year}_{state}_{chamber}_sld.json"


def acquire(year: int, state: str, chamber: str, offline: bool) -> tuple[list[list[str]], dict[str, object]]:
    destination = raw_path(year, state, chamber)
    url, params = query(year, state, chamber)
    source_url = requests.Request("GET", url, params={k: v for k, v in params.items() if k != "key"}).prepare().url
    if destination.exists():
        payload = json.loads(destination.read_text(encoding="utf-8"))
        retrieved_at = dt.datetime.fromtimestamp(destination.stat().st_mtime, dt.timezone.utc).isoformat()
    else:
        if offline:
            raise FileNotFoundError(destination)
        response = requests.get(url, params=params, timeout=120)
        response.raise_for_status()
        payload = response.json()
        with tempfile.NamedTemporaryFile(
            "w", delete=False, dir=destination.parent, suffix=".part", encoding="utf-8"
        ) as stream:
            json.dump(payload, stream, separators=(",", ":"))
            temporary = Path(stream.name)
        temporary.replace(destination)
        retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError(f"Empty or malformed ACS response: {state} {year} {chamber}")
    manifest = {
        "source_file_id": f"CENSUS-ACS5-{year}-{state}-{chamber.upper()}-SLD",
        "provider": "U.S. Census Bureau",
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "sha256": sha256(destination),
        "media_type": "application/json",
        "license_or_terms": "U.S. Census Bureau public data; no copyright restriction",
        "state_code": state,
        "cycle": year,
        "chamber": chamber,
        "geography_vintage": f"ACS {year} 5-year state legislative district tabulation",
        "authoritative_scope": "direct ACS SLD demographic estimates",
        "ingest_status": "acquired",
        "local_path": str(destination.relative_to(ROOT)).replace("\\", "/"),
    }
    return payload, manifest


def normalize(payload: list[list[str]], year: int, state: str, chamber: str) -> pd.DataFrame:
    frame = pd.DataFrame(payload[1:], columns=payload[0])
    geography = (
        "state legislative district (upper chamber)" if chamber == "upper"
        else "state legislative district (lower chamber)"
    )
    frame["district"] = pd.to_numeric(frame[geography], errors="coerce").astype("Int64")
    # Census includes an explicit ZZZ aggregate for areas where an SLD is not
    # defined.  It is not a district and must not enter a district-keyed mart.
    frame = frame[frame.district.notna()].copy()
    for variable in VARIABLES[1:]:
        frame[variable] = pd.to_numeric(frame[variable], errors="coerce")
    total_population = frame.B03002_001E.where(frame.B03002_001E.gt(0))
    total_25_plus = frame.B15003_001E.where(frame.B15003_001E.gt(0))
    white_25_plus = frame.C15002H_001E.where(frame.C15002H_001E.gt(0))
    white_college = frame.C15002H_006E + frame.C15002H_011E
    frame["nonwhite_share"] = 1 - frame.B03002_003E / total_population
    frame["college_share"] = frame[COLLEGE].sum(axis=1, min_count=len(COLLEGE)) / total_25_plus
    # Split Ticket describes the amount of white college-educated voters.  The
    # headline covariate is therefore their share of all residents age 25+;
    # the within-white rate is retained as a sensitivity field.
    frame["white_college_share"] = white_college / total_25_plus
    frame["white_college_rate_within_white"] = white_college / white_25_plus
    frame["state_code"], frame["cycle"], frame["chamber"] = state, year, chamber
    frame["acs_vintage"] = year
    frame["demographics_source"] = f"ACS {year} 5-year direct SLD tabulation"
    keep = [
        "state_code", "cycle", "chamber", "district", "nonwhite_share", "college_share",
        "white_college_share", "white_college_rate_within_white", "acs_vintage",
        "demographics_source",
    ]
    return frame[keep]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    manifests: list[dict[str, object]] = []
    for state, year, chamber in schedule():
        payload, manifest = acquire(year, state, chamber, args.offline)
        frame = normalize(payload, year, state, chamber)
        frames.append(frame)
        manifests.append(manifest)
        print(f"ACS {year} {state} {chamber}: {len(frame)} districts", flush=True)
    data = pd.concat(frames, ignore_index=True)
    keys = ["state_code", "cycle", "chamber", "district"]
    if data.duplicated(keys).any():
        raise ValueError("ACS SLD panel has duplicate race keys")
    if data[["nonwhite_share", "white_college_share"]].isna().any().any():
        raise ValueError("Scheduled ACS SLD rows contain missing headline demographic estimates")
    if not data.nonwhite_share.between(0, 1).all() or not data.white_college_share.between(0, 1).all():
        raise ValueError("ACS demographic shares fall outside [0, 1]")
    code_version = git_commit()
    source_digest = hashlib.sha256(
        "|".join(sorted(str(row["sha256"]) for row in manifests)).encode("utf-8")
    ).hexdigest()
    demographic_run_id = f"ACS-SLD-V4-{source_digest[:20].upper()}"
    data["demographic_run_id"] = demographic_run_id
    data["code_version"] = code_version
    data.sort_values(keys).to_csv(OUT, index=False)
    manifest_frame = pd.DataFrame(manifests).sort_values(["cycle", "state_code", "chamber"])
    if manifest_frame.source_file_id.duplicated().any():
        raise ValueError("ACS source manifest contains duplicate IDs")
    manifest_frame["demographic_run_id"] = demographic_run_id
    manifest_frame["code_version"] = code_version
    manifest_frame.to_csv(MANIFEST, index=False)
    print(f"ACS panel: {len(data)} rows; sources: {len(manifest_frame)}; output={OUT}")


if __name__ == "__main__":
    main()
