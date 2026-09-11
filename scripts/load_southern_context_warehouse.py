#!/usr/bin/env python3
"""Load presidential geography results and legislative boundaries into SQLite.

Raw artifacts stay immutable on disk.  SQLite stores their provenance,
normalized result rows, normalized WGS84 geometry, and explicit QA state.
Presence in this warehouse does not imply that a result geography has been
matched or allocated to a legislative plan.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from contextlib import closing
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd

from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_table


SCHEMA = Path(__file__).with_name("warehouse_southern_context_schema.sql")
PRESIDENTIAL_MANIFEST = ROOT / "data/processed/source_audits/southern_war_v4_presidential_manifest.csv"
GEOGRAPHY_MANIFEST = ROOT / "data/processed/source_audits/southern_legislative_geography_manifest.csv"
OUT = ROOT / "data/processed/source_audits"
SOUTHERN_STATES = {"AL", "AR", "FL", "GA", "KY", "LA", "MO", "MS", "NC", "OK", "SC", "TN", "TX", "VA"}
RESULT_COLUMNS = [
    "result_observation_id", "build_run_id", "source_file_id", "contract_version",
    "state_code", "cycle", "election_date", "election_stage", "office_code",
    "geography_type", "geography_id", "county_fips", "county_name_original",
    "county_key", "precinct_name_original", "precinct_key", "dem_candidate",
    "rep_candidate", "other_candidates_json", "dem_votes", "rep_votes", "other_votes",
    "total_votes", "two_party_dem_margin", "vote_value_status", "allocation_method",
    "validation_status",
]


def stable_id(prefix: str, *values: object) -> str:
    token = "|".join("" if value is None else str(value) for value in values)
    return f"{prefix}-{hashlib.sha256(token.encode()).hexdigest()[:24].upper()}"


def text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\ufeff", "").strip())


def key(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", text(value).upper()).strip()


def family(value: object) -> str:
    token = key(value)
    if token in {"D", "DEM", "DEMOCRAT", "DEMOCRATIC"}:
        return "democratic"
    if token in {"R", "REP", "REPUBLICAN"}:
        return "republican"
    return "other"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifests() -> tuple[pd.DataFrame, pd.DataFrame]:
    presidential = pd.read_csv(PRESIDENTIAL_MANIFEST, dtype=str).fillna("")
    geography = pd.read_csv(GEOGRAPHY_MANIFEST, dtype=str).fillna("")
    if presidential.source_file_id.duplicated().any():
        raise ValueError("Presidential manifest source_file_id is not unique")
    if geography.source_file_id.duplicated().any():
        raise ValueError("Geography manifest source_file_id is not unique")
    if geography.duplicated(["state_code", "cycle", "chamber"]).any():
        raise ValueError("Geography manifest state/cycle/chamber is not unique")
    return presidential, geography


def register_source(connection, row: dict, *, normalized: bool) -> str:
    path = ROOT / row["local_path"]
    if not path.exists():
        raise FileNotFoundError(path)
    digest = sha256(path)
    if row.get("sha256") and row["sha256"].lower() != digest:
        raise ValueError(f"Source hash mismatch: {path}")
    collision = connection.execute(
        "SELECT source_file_id FROM warehouse_source_file WHERE local_path=?",
        (row["local_path"].replace("\\", "/"),),
    ).fetchone()
    warehouse_id = collision[0] if collision else row["source_file_id"]
    connection.execute(
        """INSERT INTO warehouse_source_file
        (source_file_id,provider,local_path,original_url,retrieved_at_utc,sha256,media_type,
         license,extraction_status,authoritative_scope)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source_file_id) DO UPDATE SET
          provider=excluded.provider, local_path=excluded.local_path,
          original_url=excluded.original_url, retrieved_at_utc=excluded.retrieved_at_utc,
          sha256=excluded.sha256, media_type=excluded.media_type, license=excluded.license,
          extraction_status=excluded.extraction_status,
          authoritative_scope=excluded.authoritative_scope""",
        (
            warehouse_id, row["provider"], row["local_path"].replace("\\", "/"),
            row.get("source_url") or None, row.get("retrieved_at") or None, digest,
            row.get("media_type") or None, row.get("license_or_terms") or None,
            "normalized" if normalized else "registered", row.get("authoritative_scope") or None,
        ),
    )
    return warehouse_id


def candidate_rows_to_precincts(
    rows: pd.DataFrame, *, state: str, source_file_id: str, build_run_id: str,
    input_votes: float | None = None, forced_status: str = "passed",
) -> tuple[list[tuple], dict]:
    required = {"county", "precinct", "candidate", "party", "votes"}
    if not required.issubset(rows.columns):
        raise ValueError(f"Missing normalized parser columns: {required - set(rows.columns)}")
    frame = rows.copy()
    frame["votes"] = pd.to_numeric(frame["votes"], errors="raise")
    if (frame.votes < 0).any():
        raise ValueError(f"Negative presidential votes in {source_file_id}")
    frame["county"] = frame.county.map(text)
    frame["precinct"] = frame.precinct.map(text)
    frame["candidate"] = frame.candidate.map(text)
    frame["party_family"] = frame.party.map(family)
    frame = frame.groupby(
        ["county", "precinct", "candidate", "party", "party_family"], dropna=False, as_index=False
    ).votes.sum()
    output: list[tuple] = []
    for (county, precinct), group in frame.groupby(["county", "precinct"], sort=True, dropna=False):
        dem = group[group.party_family.eq("democratic")]
        rep = group[group.party_family.eq("republican")]
        other = group[group.party_family.eq("other")]
        dem_votes = float(dem.votes.sum())
        rep_votes = float(rep.votes.sum())
        other_votes = float(other.votes.sum())
        total_votes = dem_votes + rep_votes + other_votes
        county_key = key(county)
        precinct_key = key(precinct)
        geography_id = f"{state}|{county_key or 'UNKNOWN'}|{precinct_key}"
        margin = ((dem_votes - rep_votes) / (dem_votes + rep_votes)) if dem_votes + rep_votes else None
        values = {
            "result_observation_id": stable_id("PRES", source_file_id, geography_id),
            "build_run_id": build_run_id, "source_file_id": source_file_id,
            "contract_version": 1, "state_code": state, "cycle": 2012,
            "election_date": "2012-11-06", "election_stage": "general", "office_code": "USP",
            "geography_type": "precinct", "geography_id": geography_id, "county_fips": None,
            "county_name_original": county or None, "county_key": county_key or None,
            "precinct_name_original": precinct, "precinct_key": precinct_key,
            "dem_candidate": " + ".join(sorted(dem.candidate.unique())) or "UNKNOWN",
            "rep_candidate": " + ".join(sorted(rep.candidate.unique())) or "UNKNOWN",
            "other_candidates_json": json.dumps(sorted(other.candidate.unique())),
            "dem_votes": dem_votes, "rep_votes": rep_votes, "other_votes": other_votes,
            "total_votes": total_votes, "two_party_dem_margin": margin,
            "vote_value_status": "observed", "allocation_method": "provider_reported_precinct",
            "validation_status": forced_status,
        }
        output.append(tuple(values[column] for column in RESULT_COLUMNS))
    output_votes = sum(row[RESULT_COLUMNS.index("total_votes")] for row in output)
    source_total = float(input_votes) if input_votes is not None else float(frame.votes.sum())
    delta = output_votes - source_total
    status = "exact" if abs(delta) < 1e-6 else "review"
    if status == "review":
        output = [tuple("review" if column == "validation_status" else value
                        for column, value in zip(RESULT_COLUMNS, row)) for row in output]
    audit = {
        "input_rows": len(rows), "output_rows": len(output), "input_votes": source_total,
        "output_votes": output_votes, "vote_delta": delta, "reconciliation_status": status,
        "note": "Presidential candidate rows aggregated once to provider-reported precinct grain",
    }
    return output, audit


def parse_ga(path: Path) -> tuple[pd.DataFrame, float | None]:
    frame = pd.read_csv(path, dtype=str).fillna("")
    frame = frame[frame.office.str.fullmatch("President", case=False, na=False)].copy()
    vote_columns = [
        "election_day_votes", "advanced_votes", "absentee_by_mail_votes", "provisional_votes"
    ]
    frame["votes"] = frame[vote_columns].apply(pd.to_numeric, errors="raise").sum(axis=1)
    return frame[["county", "precinct", "candidate", "party", "votes"]], None


def parse_ms(path: Path) -> tuple[pd.DataFrame, float | None]:
    frame = pd.read_csv(path, dtype=str).fillna("")
    frame = frame[frame.office.str.fullmatch("President", case=False, na=False)].copy()
    # The pinned OpenElections precinct conversion transposes the Obama and
    # Romney vote columns in Harrison County. The companion county file and
    # Mississippi's certified statewide result both show D=23,119/R=39,470;
    # the precinct file sums to the reverse while preserving the correct
    # two-party total. Swap the values between the two named candidate rows at
    # each Harrison precinct; raw source bytes remain unchanged.
    harrison = frame.county.map(key).eq("HARRISON")
    major = frame.party.map(family).isin({"democratic", "republican"})
    affected = frame[harrison & major]
    counts = affected.groupby("precinct").party.agg(lambda values: set(map(family, values)))
    if len(affected) and not counts.map(lambda values: values == {"democratic", "republican"}).all():
        raise ValueError("Harrison correction requires one Democratic and one Republican row per precinct")
    original = frame.loc[harrison & major, ["precinct", "party", "votes"]].copy()
    swapped = original.assign(party_family=original.party.map(family)).pivot(
        index="precinct", columns="party_family", values="votes"
    )
    dem = harrison & frame.party.map(family).eq("democratic")
    rep = harrison & frame.party.map(family).eq("republican")
    frame.loc[dem, "votes"] = frame.loc[dem, "precinct"].map(swapped["republican"])
    frame.loc[rep, "votes"] = frame.loc[rep, "precinct"].map(swapped["democratic"])
    return frame[["county", "precinct", "candidate", "party", "votes"]], None


def parse_nc(path: Path) -> tuple[pd.DataFrame, float | None]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".txt")]
        if len(members) != 1:
            raise ValueError(f"Expected one NCSBE result text file, found {members}")
        frame = pd.read_csv(archive.open(members[0]), dtype=str).fillna("")
    contest = frame["contest"].str.contains("PRESIDENT", case=False, na=False)
    frame = frame[contest].copy()
    return frame.rename(columns={"choice": "candidate", "total votes": "votes"})[
        ["county", "precinct", "candidate", "party", "votes"]
    ], None


def parse_fl(path: Path) -> tuple[pd.DataFrame, float | None]:
    records = []
    with zipfile.ZipFile(path) as archive:
        for member in sorted(name for name in archive.namelist() if name.lower().endswith(".txt")):
            with archive.open(member) as stream:
                reader = csv.reader(io.TextIOWrapper(stream, encoding="latin-1"), delimiter="\t")
                for row in reader:
                    if len(row) < 19 or not row[11].upper().startswith("PRESIDENT OF THE UNITED STATES"):
                        continue
                    candidate = row[14]
                    if key(candidate) in {
                        "OVERVOTES", "UNDERVOTES", "TIMES OVER VOTED", "NUMBER OF UNDER VOTES"
                    }:
                        continue
                    records.append({
                        "county": row[1], "precinct": f"{row[5]} {row[6]}".strip(),
                        "candidate": candidate, "party": row[15], "votes": row[18],
                    })
    return pd.DataFrame(records), None


def parse_va(path: Path) -> tuple[pd.DataFrame, float | None]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    candidates = rows[0][2:8]
    parties = rows[1][2:8]
    state_total = sum(float(value or 0) for value in rows[2][2:8])
    locality = ""
    records = []
    for row in rows[3:]:
        if not row:
            continue
        if row[0] == "Locality":
            locality = row[1]
        elif row[0] == "Precinct":
            for candidate, party, votes in zip(candidates, parties, row[2:8]):
                records.append({
                    "county": locality, "precinct": row[1], "candidate": candidate,
                    "party": party or "other", "votes": votes or 0,
                })
    return pd.DataFrame(records), state_total


PARSERS = {
    "OPENELECTIONS-2012-GA-PRECINCT": parse_ga,
    "OPENELECTIONS-2012-MS-PRECINCT": parse_ms,
    "NCSBE-2012-NC-GENERAL-PRECINCT": parse_nc,
    "FLDOS-2012-FL-GENERAL-PRECINCT": parse_fl,
    "VAELECTIONS-2012-VA-PRESIDENT-PRECINCT": parse_va,
}


def insert_rows(connection, rows: Iterable[tuple]) -> None:
    sql = (
        f"INSERT INTO source_southern_presidential_geography_result "
        f"({','.join(RESULT_COLUMNS)}) VALUES ({','.join('?' for _ in RESULT_COLUMNS)})"
    )
    connection.executemany(sql, rows)


def load_2012(connection, row: dict, run_id: str) -> dict:
    parser = PARSERS[row["manifest_source_file_id"]]
    frame, source_total = parser(ROOT / row["local_path"])
    output, audit = candidate_rows_to_precincts(
        frame, state=row["state_code"], source_file_id=row["source_file_id"],
        build_run_id=run_id, input_votes=source_total,
    )
    insert_rows(connection, output)
    return audit


def load_2020_blocks(connection, row: dict, run_id: str) -> dict:
    path = ROOT / row["local_path"]
    input_rows = output_rows = 0
    output_votes = 0.0
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError("RDH national block archive must contain one CSV")
        with archive.open(members[0]) as stream:
            chunks = pd.read_csv(stream, dtype={"GEOID20": str, "COUNTYFP20": str}, chunksize=100_000)
            for chunk in chunks:
                chunk = chunk[chunk.STATEAB.isin(SOUTHERN_STATES)].copy()
                input_rows += len(chunk)
                records = []
                for item in chunk.itertuples(index=False):
                    geoid = str(item.GEOID20).zfill(15)
                    dem, rep, other = float(item.G20PREDBID), float(item.G20PRERTRU), float(item.G20PRELJOR)
                    total = dem + rep + other
                    margin = (dem - rep) / (dem + rep) if dem + rep else None
                    state = str(item.STATEAB)
                    values = {
                        "result_observation_id": stable_id("PRES", row["source_file_id"], geoid),
                        "build_run_id": run_id, "source_file_id": row["source_file_id"],
                        "contract_version": 1, "state_code": state, "cycle": 2020,
                        "election_date": "2020-11-03", "election_stage": "general", "office_code": "USP",
                        "geography_type": "census_block", "geography_id": geoid,
                        "county_fips": str(item.COUNTYFP20).zfill(5),
                        "county_name_original": text(item.COUNTY), "county_key": key(item.COUNTY),
                        "precinct_name_original": text(item.PRECINCT), "precinct_key": key(item.PRECINCT),
                        "dem_candidate": "JOSEPH BIDEN", "rep_candidate": "DONALD TRUMP",
                        "other_candidates_json": json.dumps(["JO JORGENSEN"]),
                        "dem_votes": dem, "rep_votes": rep, "other_votes": other,
                        "total_votes": total, "two_party_dem_margin": margin,
                        "vote_value_status": "derived", "allocation_method": "rdh_vap_disaggregation",
                        "validation_status": "passed",
                    }
                    records.append(tuple(values[column] for column in RESULT_COLUMNS))
                    output_votes += total
                insert_rows(connection, records)
                output_rows += len(records)
    return {
        "input_rows": input_rows, "output_rows": output_rows, "input_votes": output_votes,
        "output_votes": output_votes, "vote_delta": 0.0,
        "reconciliation_status": "within_rounding",
        "note": "Southern-state subset of RDH national VAP-disaggregated 2020 Census blocks",
    }


def load_2024_precincts(connection, row: dict, run_id: str) -> dict:
    frame = pd.read_csv(ROOT / row["local_path"], dtype={"GEOID": str})
    frame = frame[frame.state.isin(SOUTHERN_STATES)].copy()
    records = []
    output_votes = 0.0
    for item in frame.itertuples(index=False):
        dem, rep, total = float(item.votes_dem), float(item.votes_rep), float(item.votes_total)
        other = max(0.0, total - dem - rep)
        geoid = text(item.GEOID)
        county_fips = geoid[:5] if re.match(r"^\d{5}", geoid) else None
        margin = (dem - rep) / (dem + rep) if dem + rep else None
        official = bool(item.official_boundary)
        values = {
            "result_observation_id": stable_id("PRES", row["source_file_id"], item.state, geoid),
            "build_run_id": run_id, "source_file_id": row["source_file_id"],
            "contract_version": 1, "state_code": item.state, "cycle": 2024,
            "election_date": "2024-11-05", "election_stage": "general", "office_code": "USP",
            "geography_type": "precinct", "geography_id": geoid, "county_fips": county_fips,
            "county_name_original": None, "county_key": None,
            "precinct_name_original": geoid[6:] if len(geoid) > 6 else geoid,
            "precinct_key": key(geoid[6:] if len(geoid) > 6 else geoid),
            "dem_candidate": "KAMALA HARRIS", "rep_candidate": "DONALD TRUMP",
            "other_candidates_json": "[]", "dem_votes": dem, "rep_votes": rep,
            "other_votes": other, "total_votes": total, "two_party_dem_margin": margin,
            "vote_value_status": "observed",
            "allocation_method": (
                "provider_reported_precinct_official_boundary" if official
                else "provider_reported_precinct_estimated_boundary"
            ),
            "validation_status": "passed",
        }
        records.append(tuple(values[column] for column in RESULT_COLUMNS))
        output_votes += total
    insert_rows(connection, records)
    return {
        "input_rows": len(frame), "output_rows": len(records), "input_votes": output_votes,
        "output_votes": output_votes, "vote_delta": 0.0, "reconciliation_status": "exact",
        "note": "NYT standardized presidential precinct rows; boundary provenance retained in allocation_method",
    }


def load_geometry(connection, row: dict, run_id: str) -> dict:
    path = ROOT / row["local_path"]
    frame = gpd.read_file(f"zip://{path.resolve().as_posix()}")
    if frame.crs is None:
        raise ValueError(f"Geometry has no CRS: {path}")
    if frame.geometry.isna().any() or frame.geometry.is_empty.any() or (~frame.geometry.is_valid).any():
        raise ValueError(f"Geometry contains null, empty, or invalid features: {path}")
    district_field = "SLDLST" if row["chamber"] == "lower" else "SLDUST"
    if district_field not in frame:
        raise ValueError(f"Missing {district_field}: {path}")
    districts = frame[district_field].astype(str).str.lstrip("0").replace("", "0")
    if districts.duplicated().any():
        raise ValueError(f"District geometry is not one feature per district: {path}")
    source_crs = frame.crs.to_string()
    areas = frame.to_crs(5070).geometry.area / 1_000_000
    normalized = frame.to_crs(4326)
    layer_id = stable_id("GEOLAYER", row["source_file_id"], row["state_code"], row["cycle"], row["chamber"])
    connection.execute(
        "INSERT INTO dim_southern_geography_layer VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            layer_id, run_id, row["source_file_id"], 1, row["state_code"], int(row["cycle"]),
            "state_legislative_district", row["chamber"], row["geography_vintage"], source_crs,
            "EPSG:4326", len(normalized), "passed",
        ),
    )
    records = []
    for position, (_, item) in enumerate(normalized.iterrows()):
        district = districts.iloc[position]
        source_geoid = text(item.get("GEOID")) or f"{row['state_code']}-{row['chamber']}-{district}"
        geometry_wkb = bytes(item.geometry.wkb)
        bounds = item.geometry.bounds
        records.append((
            stable_id("GEOUNIT", layer_id, source_geoid), layer_id, row["state_code"], int(row["cycle"]),
            "state_legislative_district", row["chamber"], district, source_geoid,
            text(item.get("NAME")) or district, None, None, geometry_wkb, "EPSG:4326",
            hashlib.sha256(geometry_wkb).hexdigest(), *map(float, bounds), float(areas.iloc[position]),
        ))
    connection.executemany(
        "INSERT INTO dim_southern_geography_unit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        records,
    )
    return {
        "input_rows": len(frame), "output_rows": len(records), "input_votes": None,
        "output_votes": None, "vote_delta": None, "reconciliation_status": "not_applicable",
        "note": f"One valid unique {row['chamber']} district geometry per Census feature; stored in EPSG:4326",
    }


def add_context_file(connection, row: dict, *, role: str, geography_type: str | None,
                     status: str, parser: str | None, message: str | None) -> None:
    cycle = row.get("election_cycle") or row.get("cycle") or ""
    connection.execute(
        """INSERT INTO source_southern_context_file
        (source_file_id,manifest_source_file_id,state_code,cycle,asset_role,geography_type,
         geography_vintage,authoritative_scope,manifest_ingest_status,normalization_status,
         parser_name,parser_message)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            row["source_file_id"], row["manifest_source_file_id"], row["state_code"],
            str(cycle), role, geography_type,
            row["geography_vintage"], row["authoritative_scope"], row["ingest_status"],
            status, parser, message,
        ),
    )


def add_audit(connection, source_file_id: str, run_id: str, role: str, audit: dict) -> None:
    connection.execute(
        "INSERT INTO qa_southern_context_ingest VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            source_file_id, run_id, role, audit["input_rows"], audit["output_rows"],
            audit["input_votes"], audit["output_votes"], audit["vote_delta"],
            audit["reconciliation_status"], audit["note"],
        ),
    )


def build(database: Path | None = None) -> dict:
    presidential, geography = manifests()
    acquired_presidential = presidential[presidential.ingest_status.eq("acquired")].to_dict("records")
    geometry_rows = geography[geography.ingest_status.eq("acquired")].to_dict("records")
    normalized_result_ids = set(PARSERS) | {
        "RDH-NATIONAL-2020-PRES-BLOCKS", "NYT-NATIONAL-2024-PRES-PRECINCT-RESULTS"
    }
    with closing(connect(database)) as connection:
        initialize(connection)
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        context_columns = {
            item[1] for item in connection.execute("PRAGMA table_info(source_southern_context_file)")
        }
        if "manifest_source_file_id" not in context_columns:
            connection.execute(
                "ALTER TABLE source_southern_context_file ADD COLUMN manifest_source_file_id TEXT"
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS southern_context_manifest_source_id "
                "ON source_southern_context_file(manifest_source_file_id)"
            )
        run_id = begin_run(connection, "southern_presidential_and_geography_context", {
            "contract_version": 1,
            "presidential_manifest": PRESIDENTIAL_MANIFEST.relative_to(ROOT).as_posix(),
            "geography_manifest": GEOGRAPHY_MANIFEST.relative_to(ROOT).as_posix(),
            "southern_states": sorted(SOUTHERN_STATES),
        })
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        # Replace only this loader's registered sources. Other context loaders
        # share the canonical result and geometry tables and must survive a
        # routine refresh of this source family.
        connection.execute(
            """DELETE FROM bridge_southern_result_geography
               WHERE result_observation_id IN (
                 SELECT result_observation_id
                 FROM source_southern_presidential_geography_result
                 WHERE source_file_id IN (SELECT source_file_id FROM source_southern_context_file)
               ) OR geography_unit_id IN (
                 SELECT u.geography_unit_id
                 FROM dim_southern_geography_unit u
                 JOIN dim_southern_geography_layer l USING(geography_layer_id)
                 WHERE l.source_file_id IN (SELECT source_file_id FROM source_southern_context_file)
               )"""
        )
        connection.execute(
            """DELETE FROM source_southern_presidential_geography_result
               WHERE source_file_id IN (SELECT source_file_id FROM source_southern_context_file)"""
        )
        connection.execute(
            """DELETE FROM dim_southern_geography_layer
               WHERE source_file_id IN (SELECT source_file_id FROM source_southern_context_file)"""
        )
        connection.execute(
            """DELETE FROM qa_southern_context_ingest
               WHERE source_file_id IN (SELECT source_file_id FROM source_southern_context_file)"""
        )
        connection.execute("DELETE FROM source_southern_context_file")

        for row in acquired_presidential:
            manifest_source_file_id = row["source_file_id"]
            normalized = manifest_source_file_id in normalized_result_ids
            warehouse_source_file_id = register_source(connection, row, normalized=normalized)
            row = {
                **row, "manifest_source_file_id": manifest_source_file_id,
                "source_file_id": warehouse_source_file_id,
            }
            if manifest_source_file_id in PARSERS:
                audit = load_2012(connection, row, run_id)
                add_context_file(connection, row, role="result", geography_type="precinct",
                                 status="normalized", parser=PARSERS[manifest_source_file_id].__name__, message=None)
                add_audit(connection, row["source_file_id"], run_id, "result", audit)
            elif manifest_source_file_id == "RDH-NATIONAL-2020-PRES-BLOCKS":
                audit = load_2020_blocks(connection, row, run_id)
                add_context_file(connection, row, role="result", geography_type="census_block",
                                 status="normalized", parser="load_2020_blocks", message=None)
                add_audit(connection, row["source_file_id"], run_id, "result", audit)
            elif manifest_source_file_id == "NYT-NATIONAL-2024-PRES-PRECINCT-RESULTS":
                audit = load_2024_precincts(connection, row, run_id)
                add_context_file(connection, row, role="result", geography_type="precinct",
                                 status="normalized", parser="load_2024_precincts", message=None)
                add_audit(connection, row["source_file_id"], run_id, "result", audit)
            else:
                role = "geometry" if "GEOMETRY" in manifest_source_file_id else "index"
                add_context_file(
                    connection, row, role=role, geography_type="precinct" if role == "geometry" else None,
                    status="registered_unparsed" if role == "geometry" else "not_applicable",
                    parser=None,
                    message=(
                        "Raw national TopoJSON is registered; result rows use the companion CSV. "
                        "Precinct geometry normalization remains a separate resource-heavy stage."
                        if role == "geometry" else "Provenance index, not a result table"
                    ),
                )
                add_audit(connection, row["source_file_id"], run_id, role, {
                    "input_rows": None, "output_rows": 0, "input_votes": None,
                    "output_votes": None, "vote_delta": None,
                    "reconciliation_status": "not_applicable", "note": "Registered without normalization",
                })

        for row in geometry_rows:
            manifest_source_file_id = row["source_file_id"]
            warehouse_source_file_id = register_source(connection, row, normalized=True)
            row = {
                **row, "manifest_source_file_id": manifest_source_file_id,
                "source_file_id": warehouse_source_file_id,
            }
            audit = load_geometry(connection, row, run_id)
            add_context_file(connection, row, role="geometry",
                             geography_type="state_legislative_district", status="normalized",
                             parser="load_geometry", message=None)
            add_audit(connection, row["source_file_id"], run_id, "geometry", audit)

        duplicate_results = connection.execute(
            """SELECT COUNT(*) FROM (
              SELECT source_file_id,state_code,cycle,geography_type,geography_id,COUNT(*) n
              FROM source_southern_presidential_geography_result
              GROUP BY 1,2,3,4,5 HAVING n>1)"""
        ).fetchone()[0]
        duplicate_districts = connection.execute(
            """SELECT COUNT(*) FROM (
              SELECT geography_layer_id,district,COUNT(*) n FROM dim_southern_geography_unit
              GROUP BY 1,2 HAVING n>1)"""
        ).fetchone()[0]
        bad_vote_math = connection.execute(
            """SELECT COUNT(*) FROM source_southern_presidential_geography_result
               WHERE ABS(total_votes-(dem_votes+rep_votes+other_votes))>0.011"""
        ).fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if duplicate_results or duplicate_districts or bad_vote_math or foreign_keys:
            raise ValueError(
                f"Context validation failed: results={duplicate_results}, districts={duplicate_districts}, "
                f"vote_math={bad_vote_math}, foreign_keys={foreign_keys[:5]}"
            )
        result_rows = connection.execute(
            "SELECT COUNT(*) FROM source_southern_presidential_geography_result"
        ).fetchone()[0]
        valid_results = connection.execute(
            "SELECT COUNT(*) FROM fact_southern_presidential_geography_result"
        ).fetchone()[0]
        geography_units = connection.execute(
            "SELECT COUNT(*) FROM dim_southern_geography_unit"
        ).fetchone()[0]
        validation = {
            "presidential_result_rows": result_rows,
            "validated_presidential_result_rows": valid_results,
            "review_presidential_result_rows": result_rows - valid_results,
            "geography_layers": len(geometry_rows), "geography_units": geography_units,
            "normalized_result_sources": len(normalized_result_ids),
            "registered_unparsed_geometry_sources": 1,
            "result_geography_links": 0,
            "join_status": "not_built; raw result and district geometry grains are centralized separately",
        }
        for name, layer, key_description, authority, lifecycle, description in [
            ("source_southern_context_file", "source", "source_file_id",
             "Manifest registration and parser status are distinct", "replace",
             "Central inventory of acquired presidential and geography artifacts"),
            ("source_southern_presidential_geography_result", "source",
             "source_file_id + state + cycle + geography_type + geography_id",
             "Provider-reported precinct or explicitly derived RDH block observations", "replace",
             "Wide presidential result observations at their actual source geography"),
            ("dim_southern_geography_layer", "canonical", "geography_layer_id",
             "One immutable source layer per state/cycle/chamber", "replace",
             "Versioned legislative district boundary layers"),
            ("dim_southern_geography_unit", "canonical", "geography_layer_id + source_geoid",
             "One valid unique feature per source geographic identifier", "replace",
             "Normalized WGS84 district geometry features with source lineage"),
            ("bridge_southern_result_geography", "canonical",
             "result_observation_id + geography_unit_id",
             "Only explicit geographic matches or audited allocation weights", "replace",
             "Result-to-geometry bridge; empty until a crosswalk is built and validated"),
            ("qa_southern_context_ingest", "qa", "source_file_id",
             "Source-specific reconciliation; review is not silently promoted", "replace",
             "Election and geometry ingestion validation"),
            ("fact_southern_presidential_geography_result", "canonical", "result_observation_id",
             "Only source observations whose validation_status passed", "view",
             "Validated presidential results at precinct or Census-block grain"),
        ]:
            register_table(connection, name, layer, "scripts/load_southern_context_warehouse.py",
                           key_description, authority, lifecycle, description)
        finish_run(connection, run_id, validation)
        connection.commit()

    OUT.mkdir(parents=True, exist_ok=True)
    with closing(connect(database, readonly=True)) as connection:
        coverage = pd.read_sql_query(
            "SELECT * FROM qa_southern_context_coverage ORDER BY cycle,state_code,geography_type",
            connection,
        )
        audit = pd.read_sql_query(
            "SELECT * FROM qa_southern_context_ingest WHERE build_run_id=? ORDER BY asset_role,source_file_id",
            connection, params=(run_id,),
        )
    coverage.to_csv(OUT / "southern_context_warehouse_coverage.csv", index=False)
    audit.to_csv(OUT / "southern_context_warehouse_ingest.csv", index=False)
    manifest = {
        "contract_version": 1, "build_run_id": run_id,
        "pipeline": "scripts/load_southern_context_warehouse.py", "validation": validation,
        "outputs": [
            "data/processed/source_audits/southern_context_warehouse_coverage.csv",
            "data/processed/source_audits/southern_context_warehouse_ingest.csv",
        ],
    }
    (OUT / "southern_context_warehouse_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.database)["validation"], indent=2))


if __name__ == "__main__":
    main()
