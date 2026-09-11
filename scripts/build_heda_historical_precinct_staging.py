#!/usr/bin/env python3
"""Normalize HEDA Southern precinct returns into canonical-ready staging files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / "data/raw/historical_statewide_elections/dataverse_files (4).zip"
DEFAULT_KLARNER = ROOT / "data/raw/historical_statewide_elections/dataverse_files.zip"
DEFAULT_OUTPUT = ROOT / "data/processed/precinct_history/heda"
TARGET_STATES = {"AL", "AR", "FL", "GA", "KY", "LA", "MS", "MO", "NC", "OK", "SC", "TN", "TX", "VA"}
STATE_NAMES = {
    "Alabama": "AL", "Arkansas": "AR", "Florida": "FL", "Georgia": "GA",
    "Kentucky": "KY", "Louisiana": "LA", "Mississippi": "MS", "Missouri": "MO",
    "North Carolina": "NC", "Oklahoma": "OK", "South Carolina": "SC",
    "Tennessee": "TN", "Texas": "TX", "Virginia": "VA",
}
LEGISLATIVE_OFFICES = {"STH": "house", "STS": "senate"}
VOTE_RE = re.compile(r"^g(?P<year>\d{4})_(?P<office>[A-Z0-9]+)_(?P<party>dv|rv|tv)(?P<slot>\d*)$")
MEMBER_RE = re.compile(r"(?P<state>[A-Z]{2})_(?P<year>\d{4})\.dta$")


def archive_sha256(path: Path) -> str:
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


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def vote_columns(columns: list[str] | pd.Index) -> dict[tuple[int, str, int], dict[str, str]]:
    """Map (year, office, slot) to aggregate Democratic/Republican/total fields."""
    result: dict[tuple[int, str, int], dict[str, str]] = {}
    for column in columns:
        match = VOTE_RE.match(str(column))
        if not match:
            continue
        raw_slot = match.group("slot")
        slot = int(raw_slot) if raw_slot else 1
        result.setdefault((int(match.group("year")), match.group("office"), slot), {})[
            match.group("party")
        ] = str(column)
    return result


def district_column(frame: pd.DataFrame, office: str, slot: int) -> str | None:
    prefix = "ld" if office == "STH" else "sd" if office == "STS" else "cd" if office == "USH" else None
    if prefix is None:
        return None
    candidates = [prefix if slot == 1 else f"{prefix}{slot}"]
    return next((column for column in candidates if column in frame.columns), None)


def _identity(frame: pd.DataFrame, state: str, year: int, member: str, archive_hash: str) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out["state"] = state
    out["year"] = year
    out["source_member"] = member
    out["source_row"] = range(1, len(frame) + 1)
    out["archive_sha256"] = archive_hash
    for field in ("county", "precinct", "precinct_code"):
        out[field] = frame[field] if field in frame else pd.NA
    return out


def normalize_legislative(
    frame: pd.DataFrame, state: str, year: int, member: str, archive_hash: str
) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    identity = _identity(frame, state, year, member, archive_hash)
    for (contest_year, office, slot), fields in vote_columns(frame.columns).items():
        if contest_year != year or office not in LEGISLATIVE_OFFICES or not ({"dv", "rv"} & fields.keys()):
            continue
        district_field = district_column(frame, office, slot)
        if district_field is None:
            continue
        piece = identity.copy()
        piece["chamber"] = LEGISLATIVE_OFFICES[office]
        piece["district_slot"] = slot
        piece["district"] = pd.to_numeric(frame[district_field], errors="coerce").astype("Int64")
        piece["district_source_field"] = district_field
        for party, output in (("dv", "dem_votes"), ("rv", "rep_votes"), ("tv", "total_votes")):
            piece[output] = pd.to_numeric(frame[fields[party]], errors="coerce") if party in fields else pd.NA
            piece[f"{output}_source_field"] = fields.get(party, pd.NA)
        observed = piece[["dem_votes", "rep_votes", "total_votes"]].notna().any(axis=1)
        pieces.append(piece.loc[observed & piece["district"].notna()])
    if not pieces:
        return pd.DataFrame()
    return pd.concat(pieces, ignore_index=True)


def normalize_context(
    frame: pd.DataFrame, state: str, year: int, member: str, archive_hash: str
) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    identity = _identity(frame, state, year, member, archive_hash)
    for (contest_year, office, slot), fields in vote_columns(frame.columns).items():
        if contest_year != year or office in LEGISLATIVE_OFFICES or not ({"dv", "rv"} & fields.keys()):
            continue
        piece = identity.copy()
        piece["office"] = office
        piece["contest_slot"] = slot
        district_field = district_column(frame, office, slot)
        piece["district"] = (
            pd.to_numeric(frame[district_field], errors="coerce").astype("Int64")
            if district_field
            else pd.Series(pd.NA, index=frame.index, dtype="Int64")
        )
        piece["district_source_field"] = district_field or pd.NA
        for party, output in (("dv", "dem_votes"), ("rv", "rep_votes"), ("tv", "total_votes")):
            piece[output] = pd.to_numeric(frame[fields[party]], errors="coerce") if party in fields else pd.NA
            piece[f"{output}_source_field"] = fields.get(party, pd.NA)
        observed = piece[["dem_votes", "rep_votes", "total_votes"]].notna().any(axis=1)
        pieces.append(piece.loc[observed])
    if not pieces:
        return pd.DataFrame()
    return pd.concat(pieces, ignore_index=True)


def coverage_row(frame: pd.DataFrame, state: str, year: int, member: str) -> dict[str, object]:
    mappings = vote_columns(frame.columns)
    offices = sorted({office for contest_year, office, _ in mappings if contest_year == year})
    legislative = sorted(set(offices) & set(LEGISLATIVE_OFFICES))
    return {
        "state": state,
        "year": year,
        "source_member": member,
        "source_rows": len(frame),
        "has_county": "county" in frame,
        "has_precinct": "precinct" in frame,
        "has_house_district": "ld" in frame,
        "has_senate_district": "sd" in frame,
        "offices": "|".join(offices),
        "legislative_offices": "|".join(legislative),
        "use_class": "direct_legislative" if legislative else "context_only",
    }


def district_aggregate(legislative: pd.DataFrame) -> pd.DataFrame:
    if legislative.empty:
        return pd.DataFrame()
    group = ["state", "year", "chamber", "district"]
    out = legislative.groupby(group, dropna=False)[["dem_votes", "rep_votes", "total_votes"]].sum(min_count=1).reset_index()
    two_party = out["dem_votes"] + out["rep_votes"]
    out["dem_two_party_share"] = out["dem_votes"] / two_party.where(two_party > 0)
    out["dem_margin"] = (out["dem_votes"] - out["rep_votes"]) / two_party.where(two_party > 0)
    out["precinct_fragment_rows"] = legislative.groupby(group).size().to_numpy()
    return out


def reconcile_klarner(districts: pd.DataFrame, archive: Path) -> pd.DataFrame:
    """Compare HEDA district sums with the independent Klarner contest file."""
    if districts.empty or not archive.exists():
        return pd.DataFrame()
    with ZipFile(archive) as bundle:
        source = pd.read_csv(bundle.open("202slers_uoa_contest20230810.csv"), low_memory=False)
    source = source[source["state"].isin(STATE_NAMES)].copy()
    source["state"] = source["state"].map(STATE_NAMES)
    source["chamber"] = source["sen"].map({0: "house", 1: "senate"})
    source["district"] = pd.to_numeric(source["dno"], errors="coerce").astype("Int64")
    source["year"] = pd.to_numeric(source["year"], errors="coerce").astype("Int64")
    source["klarner_dem_votes"] = pd.to_numeric(source["dvote"], errors="coerce")
    source["klarner_rep_votes"] = pd.to_numeric(source["rvote"], errors="coerce")
    source = source.loc[
        source["state"].isin(TARGET_STATES)
        & source["chamber"].notna()
        & source["district"].notna()
        & source["year"].notna()
        & source["dseats"].eq(1)
        & source["eseats"].eq(1)
        & source["dontuse"].fillna(0).eq(0)
    ]
    source = source[["state", "year", "chamber", "district", "klarner_dem_votes", "klarner_rep_votes"]]
    source = source.drop_duplicates(["state", "year", "chamber", "district"], keep="first")
    audit = districts.merge(source, on=["state", "year", "chamber", "district"], how="left", validate="one_to_one")
    for party in ("dem", "rep"):
        audit[f"{party}_vote_delta"] = audit[f"{party}_votes"] - audit[f"klarner_{party}_votes"]
        audit[f"{party}_relative_delta"] = audit[f"{party}_vote_delta"] / audit[f"klarner_{party}_votes"].where(
            audit[f"klarner_{party}_votes"].abs() > 0
        )
    audit["has_klarner_comparison"] = audit["klarner_dem_votes"].notna() | audit["klarner_rep_votes"].notna()
    audit["exact_party_totals"] = (
        audit["dem_vote_delta"].fillna(float("inf")).eq(0)
        & audit["rep_vote_delta"].fillna(float("inf")).eq(0)
    )
    return audit


def build(archive: Path, output: Path, klarner_archive: Path = DEFAULT_KLARNER) -> dict[str, int]:
    archive = archive.resolve()
    output = output.resolve()
    klarner_archive = klarner_archive.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive_hash = archive_sha256(archive)
    coverage: list[dict[str, object]] = []
    legislative_parts: list[pd.DataFrame] = []
    context_parts: list[pd.DataFrame] = []
    with ZipFile(archive) as bundle:
        for member in sorted(bundle.namelist()):
            match = MEMBER_RE.search(member)
            if not match or match.group("state") not in TARGET_STATES:
                continue
            state, year = match.group("state"), int(match.group("year"))
            frame = pd.read_stata(BytesIO(bundle.read(member)), convert_categoricals=False)
            coverage.append(coverage_row(frame, state, year, member))
            legislative = normalize_legislative(frame, state, year, member, archive_hash)
            context = normalize_context(frame, state, year, member, archive_hash)
            if not legislative.empty:
                legislative_parts.append(legislative)
            if not context.empty:
                context_parts.append(context)

    coverage_frame = pd.DataFrame(coverage).sort_values(["state", "year"])
    legislative_frame = pd.concat(legislative_parts, ignore_index=True) if legislative_parts else pd.DataFrame()
    context_frame = pd.concat(context_parts, ignore_index=True) if context_parts else pd.DataFrame()
    districts = district_aggregate(legislative_frame)
    reconciliation = reconcile_klarner(districts, klarner_archive)

    coverage_frame.to_csv(output / "heda_state_year_coverage.csv", index=False)
    # Gzip CSV keeps the staging build dependency-light in the project's base
    # environment while remaining streamable by pandas and warehouse loaders.
    gzip_options = {"method": "gzip", "mtime": 0}
    legislative_frame.to_csv(output / "heda_legislative_precinct_fragments.csv.gz", index=False, compression=gzip_options)
    context_frame.to_csv(output / "heda_precinct_context.csv.gz", index=False, compression=gzip_options)
    districts.to_csv(output / "heda_legislative_district_totals.csv", index=False)
    reconciliation.to_csv(output / "heda_klarner_district_reconciliation.csv", index=False)

    fl_precinct = legislative_frame.loc[(legislative_frame["state"] == "FL") & (legislative_frame["year"] == 2010)].copy()
    fl_district = districts.loc[(districts["state"] == "FL") & (districts["year"] == 2010)].copy()
    fl_precinct.to_csv(output / "florida_2010_legislative_precinct_fragments.csv", index=False)
    fl_district.to_csv(output / "florida_2010_legislative_district_totals.csv", index=False)

    output_files = sorted(path for path in output.iterdir() if path.is_file() and path.name != "build_manifest.json")
    script_path = Path(__file__).resolve()
    build_id = hashlib.sha256(
        f"{archive_hash}:{archive_sha256(klarner_archive)}:{archive_sha256(script_path)}".encode()
    ).hexdigest()[:20]
    manifest = {
        "schema_version": 1,
        "build_id": build_id,
        "code_commit": git_commit(),
        "pipeline": str(script_path.relative_to(ROOT)).replace("\\", "/"),
        "source_cutoff": "2012",
        "sources": [
            {
                "provider": "Harvard Election Data Archive",
                "title": "Precinct-Level Election Data, Version 1.0",
                "documentation_date": "2014-01-20",
                "landing_url": "http://projects.iq.harvard.edu/eda/",
                "local_path": display_path(archive),
                "sha256": archive_hash,
                "local_file_mtime_utc": datetime.fromtimestamp(archive.stat().st_mtime, timezone.utc).isoformat(),
                "retrieval_timestamp_status": "local_file_mtime_only",
                "license": "not_identified_in_embedded_documentation",
                "geographic_vintage": "state-year fields documented in embedded heda_docs.pdf",
            },
            {
                "provider": "Klarner State Legislative Election Returns",
                "title": "SLER contest archive through 2022",
                "local_path": display_path(klarner_archive),
                "sha256": archive_sha256(klarner_archive),
                "local_file_mtime_utc": datetime.fromtimestamp(klarner_archive.stat().st_mtime, timezone.utc).isoformat(),
                "retrieval_timestamp_status": "local_file_mtime_only",
                "license": "not_recorded_by_this_pipeline",
            },
        ],
        "outputs": [
            {
                "path": display_path(path),
                "bytes": path.stat().st_size,
                "sha256": archive_sha256(path),
            }
            for path in output_files
        ],
        "row_counts": {
            "coverage": len(coverage_frame), "legislative_fragments": len(legislative_frame),
            "context": len(context_frame), "districts": len(districts),
            "reconciliation": len(reconciliation), "florida_2010_fragments": len(fl_precinct),
        },
        "authority_policy": "HEDA and Klarner remain conflicting secondary observations; official returns outrank both.",
        "missing_value_policy": "Missing source observations remain missing and are never silently converted to zero.",
    }
    (output / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {
        "coverage_rows": len(coverage_frame),
        "legislative_rows": len(legislative_frame),
        "context_rows": len(context_frame),
        "district_rows": len(districts),
        "florida_2010_rows": len(fl_precinct),
        "reconciliation_rows": len(reconciliation),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--klarner-archive", type=Path, default=DEFAULT_KLARNER)
    args = parser.parse_args()
    counts = build(args.archive, args.output, args.klarner_archive)
    print("HEDA historical staging complete:", ", ".join(f"{key}={value:,}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
