#!/usr/bin/env python3
"""Build complete Alabama 2012 presidential geography from audited sources."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from oe_normalize import load_oe, normalize_name
from sos_precinct import load_sos_year


ROOT = Path(__file__).resolve().parents[1]
OE = ROOT / "data/raw/openelections/20121106__al__general__precinct.csv"
SOS_PRECINCT = ROOT / "data/raw/alabama_elections_and_geography/2012General-PrecinctLevel.zip"
SOS_COUNTY = ROOT / "data/raw/alabama_elections_and_geography/eapresidentgeneral1976-2012_0.xls"
OUT = ROOT / "data/processed/presidential/2012_president_precinct_canonical.csv"
MANIFEST = ROOT / "data/processed/presidential/2012_president_precinct_canonical.manifest.json"
COUNTY_ALIASES = {
    "SAINT": "SAINT CLAIR", "ST CLAIR": "SAINT CLAIR", "STCLAIR": "SAINT CLAIR",
    "RADOLPH": "RANDOLPH",
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


def county_key(value: object) -> str:
    key = normalize_name(value)
    return COUNTY_ALIASES.get(key, key)


def official_totals() -> pd.DataFrame:
    raw = pd.read_excel(SOS_COUNTY, sheet_name="2012", header=None).iloc[:, :3]
    raw.columns = ["county", "dem_votes", "rep_votes"]
    raw[["dem_votes", "rep_votes"]] = raw[["dem_votes", "rep_votes"]].apply(
        pd.to_numeric, errors="coerce"
    )
    raw = raw[raw.dem_votes.notna() & ~raw.county.astype(str).str.contains("TOTAL", case=False)]
    raw["county_key"] = raw.county.map(county_key)
    if len(raw) != 67 or raw.county_key.duplicated().any():
        raise ValueError(f"Expected 67 unique SOS county totals, found {len(raw)}")
    return raw[["county_key", "dem_votes", "rep_votes"]]


def precinct_detail() -> pd.DataFrame:
    oe = load_oe(OE)
    oe = oe[oe.office.eq("President")].copy()
    oe["party_norm"] = pd.NA
    oe.loc[oe.candidate.str.contains("OBAMA", case=False, na=False), "party_norm"] = "D"
    oe.loc[oe.candidate.str.contains("ROMNEY", case=False, na=False), "party_norm"] = "R"
    oe = oe[oe.party_norm.notna()]
    oe["county_key"] = oe.county_key.map(county_key)
    oe = oe.groupby(["county_key", "precinct_key", "party_norm"], as_index=False).votes.sum()
    oe = oe.pivot(index=["county_key", "precinct_key"], columns="party_norm", values="votes")
    if oe[["D", "R"]].isna().any().any():
        raise ValueError("OpenElections precinct row lacks one major-party observation")
    oe = oe.reset_index().rename(columns={"D": "dem_votes", "R": "rep_votes"})
    oe["detail_provider"] = "OpenElections conversion of Alabama SOS"

    sos = load_sos_year(ROOT, 2012)
    sos = sos[sos.office.eq("President")].copy()
    sos["county_key"] = sos.county_key.map(county_key)
    sos["party_norm"] = pd.NA
    sos.loc[sos.candidate.str.contains("OBAMA", case=False, na=False), "party_norm"] = "D"
    sos.loc[sos.candidate.str.contains("ROMNEY", case=False, na=False), "party_norm"] = "R"
    sos = sos[sos.county_key.eq("MONTGOMERY") & sos.party_norm.notna()]
    sos = sos.groupby(["county_key", "precinct_key", "party_norm"], as_index=False).votes.sum()
    sos = sos.pivot(index=["county_key", "precinct_key"], columns="party_norm", values="votes")
    if sos.empty or sos[["D", "R"]].isna().any().any():
        raise ValueError("Official Montgomery workbook lacks a major-party precinct observation")
    sos = sos.reset_index().rename(columns={"D": "dem_votes", "R": "rep_votes"})
    sos["detail_provider"] = "Alabama SOS 2012 county precinct workbook"
    return pd.concat([oe[~oe.county_key.eq("MONTGOMERY")], sos], ignore_index=True)


def build() -> dict[str, object]:
    totals, detail = official_totals(), precinct_detail()
    rows: list[pd.DataFrame] = []
    for total in totals.itertuples(index=False):
        county = detail[detail.county_key.eq(total.county_key)].copy()
        if county.empty:
            county = pd.DataFrame([{
                "county_key": total.county_key,
                "precinct_key": "COUNTY-WIDE OFFICIAL TOTAL",
                "dem_votes": float(total.dem_votes),
                "rep_votes": float(total.rep_votes),
                "detail_provider": "Alabama SOS historical presidential county archive",
                "geography_type": "county",
                "dem_certification_factor": 1.0,
                "rep_certification_factor": 1.0,
            }])
        else:
            dem_sum, rep_sum = county.dem_votes.sum(), county.rep_votes.sum()
            if dem_sum <= 0 or rep_sum <= 0:
                raise ValueError(f"Nonpositive precinct total for {total.county_key}")
            dem_factor = float(total.dem_votes / dem_sum)
            rep_factor = float(total.rep_votes / rep_sum)
            county["dem_votes"] *= dem_factor
            county["rep_votes"] *= rep_factor
            county["geography_type"] = "precinct"
            county["dem_certification_factor"] = dem_factor
            county["rep_certification_factor"] = rep_factor
        rows.append(county)
    output = pd.concat(rows, ignore_index=True)
    output["two_party_votes"] = output.dem_votes + output.rep_votes
    output["pres_dem_margin"] = 100 * (output.dem_votes - output.rep_votes) / output.two_party_votes
    def source_ids(provider: str) -> str:
        identifiers = ["ALSOS-PRESIDENT-GENERAL-COUNTY-1976-2012"]
        if provider.startswith("Alabama SOS 2012"):
            identifiers.append("ALSOS-2012-PRECINCT")
        elif provider.startswith("OpenElections"):
            identifiers.append("OPENELECTIONS-2012-AL-PRECINCT")
        return json.dumps(identifiers)
    output["source_file_ids_json"] = output.detail_provider.map(source_ids)
    output = output.sort_values(["county_key", "precinct_key"]).reset_index(drop=True)
    actual = output[["dem_votes", "rep_votes"]].sum()
    expected = totals[["dem_votes", "rep_votes"]].sum()
    if not actual.sub(expected).abs().le(0.01).all():
        raise ValueError(f"Statewide reconciliation failed: {actual.to_dict()} != {expected.to_dict()}")
    if output.duplicated(["county_key", "precinct_key"]).any():
        raise ValueError("Duplicate canonical Alabama 2012 geography key")
    inputs = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
              for path in (OE, SOS_PRECINCT, SOS_COUNTY)}
    seed = json.dumps({"inputs": inputs, "contract_version": 1}, sort_keys=True).encode()
    run_id = f"ALPRES2012-{hashlib.sha256(seed).hexdigest()[:20].upper()}"
    output["build_run_id"] = run_id
    output["code_version"] = git_commit()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUT, index=False)
    manifest = {
        "build_run_id": run_id,
        "contract_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "code_version": git_commit(),
        "pipeline": "scripts/build_alabama_2012_presidential_source.py",
        "inputs": inputs,
        "output": str(OUT.relative_to(ROOT)).replace("\\", "/"),
        "validation": {
            "counties": int(output.county_key.nunique()),
            "geography_rows": len(output),
            "county_level_rows": int(output.geography_type.eq("county").sum()),
            "dem_votes": float(actual.dem_votes),
            "rep_votes": float(actual.rep_votes),
            "duplicate_keys": 0,
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
