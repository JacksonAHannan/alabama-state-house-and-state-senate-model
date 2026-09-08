"""Bridge Alabama canonical legislative candidates to certified canvass cells.

Authority decision (SOUTHERN-WAR-COMPLETION-20260908): the certified State
Canvassing Board canvass supplies Alabama 2018 and 2022 general-election
legislative contest totals.  The Alabama canonical candidate route remains the
outcome source family so that stable candidate identifiers, names and finance
identity links survive, but every canonical candidate must bridge to exactly one
certified canvass cell at exact cycle/chamber/district/party grain with explicit
name evidence.  Nothing here fuzzy-matches names, invents a bridge, or converts
an unknown value to zero.  The bridge table is the reviewable provenance record;
the Southern preparation producer consumes it and refuses to build when a
bridged canonical total disagrees with the canvass.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import pandas as pd

from oe_normalize import normalize_name
from warehouse import ROOT

CERTIFIED_FAMILY = "alabama_sos_certified_canvass"
BRIDGE_TABLE = "bridge_alabama_canonical_candidate_certified_result"
CYCLES = (2018, 2022)
BALLOT_CODE = re.compile(r"^G(?:SL\d{3}|SU\d{2})[DR][A-Z]{3}$")
SUFFIXES = {"JR", "SR", "II", "III", "IV"}
PARTY_FAMILY = {"D": "democratic", "R": "republican"}
CHAMBER = {"house": "lower", "senate": "upper"}
BRIDGE_COLUMNS = [
    "bridge_id", "build_run_id", "canonical_candidate_id", "cycle", "chamber", "district",
    "canonical_party", "canonical_name", "decoded_canonical_name", "observation_set_id",
    "source_candidate_result_id", "source_file_id", "certified_candidate_name", "match_method",
    "canonical_votes_before", "certified_votes", "vote_delta", "correction_status",
    "review_status", "evidence_json", "recorded_at_utc",
]


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def identifier(prefix: str, *parts) -> str:
    return prefix + "-" + hashlib.sha256(encode(parts).encode()).hexdigest()[:24].upper()


def native_records(frame: pd.DataFrame) -> list[dict]:
    """Rows with native Python scalars (numpy types are not JSON- or sqlite-bindable)."""
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def normalized_district(value) -> str:
    text = str(value).strip()
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        return str(int(float(text)))
    return text.upper()


def integer_votes(value, label: str) -> int:
    if value is None or isinstance(value, bool) or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError(f"Non-integer vote value for {label}: {value!r}")
    number = float(value)
    if number < 0 or not number.is_integer():
        raise ValueError(f"Non-integer vote value for {label}: {value!r}")
    return int(number)


def ballot_code_names() -> dict[str, str]:
    """Return the accepted README decoder for Alabama's opaque 2022 ballot codes."""
    from build_incumbency_features import read_candidate_code_names

    return read_candidate_code_names()


def tokens(name: str) -> list[str]:
    return [token for token in normalize_name(str(name)).split() if token]


def name_evidence(canonical_name: str, certified_name: str, decoder: dict[str, str],
                  aligned_precinct_name: str | None = None) -> tuple[str | None, str | None]:
    """Return (match_method, decoded_name); method is None when evidence is absent.

    Evidence order: an opaque ballot code is decoded through the accepted README
    decoder first; then exact normalized equality; then surname agreement at the
    already-unique race/party grain (the 2018 canvass prints surnames only);
    finally an exact normalized match to the same provider's precinct-workbook
    candidate aligned to the certified cell at exact contest/party/category grain.
    """
    decoded = None
    prefix = ""
    compared = str(canonical_name)
    if BALLOT_CODE.fullmatch(compared.strip().upper()):
        decoded = decoder.get(compared.strip().upper())
        if decoded is None:
            return None, None
        compared = decoded
        prefix = "decoded_ballot_code_"
    canonical_tokens, certified_tokens = tokens(compared), tokens(certified_name)
    if not canonical_tokens or not certified_tokens:
        return None, decoded
    if normalize_name(compared) == normalize_name(str(certified_name)):
        return prefix + "exact_normalized_name", decoded
    canonical_surname = [token for token in canonical_tokens if token not in SUFFIXES]
    certified_surname = [token for token in certified_tokens if token not in SUFFIXES]
    if canonical_surname and certified_surname and canonical_surname[-1] == certified_surname[-1]:
        if len(canonical_tokens) > 1 and len(certified_tokens) > 1 and canonical_tokens[0] == certified_tokens[0]:
            return prefix + "surname_and_given_name", decoded
        return prefix + "surname_unique_race_party", decoded
    if aligned_precinct_name and normalize_name(compared) == normalize_name(str(aligned_precinct_name)):
        return prefix + "precinct_workbook_exact_name_alignment_canvass_label_disagrees", decoded
    return None, decoded


def certified_rows(connection, cycles=CYCLES) -> pd.DataFrame:
    """Return every certified canvass row (named and write-in) for the cycles."""
    placeholders = ",".join("?" for _ in cycles)
    frame = pd.read_sql_query(f"""
        SELECT s.observation_set_id, s.source_file_id, s.cycle, s.chamber, s.district,
               s.validation_status AS set_validation_status, s.quality_flags_json,
               r.source_candidate_result_id, r.candidate_name, r.party_family, r.party_original,
               r.votes, r.vote_value_status, r.writein_status,
               r.validation_status AS candidate_validation_status
        FROM source_southern_legislative_observation_set s
        JOIN source_southern_legislative_candidate_result r USING(observation_set_id)
        WHERE s.state_code='AL' AND s.source_family=? AND s.cycle IN ({placeholders})
        ORDER BY s.cycle, s.chamber, CAST(s.district AS INTEGER), r.party_family, r.candidate_name
    """, connection, params=(CERTIFIED_FAMILY, *cycles))
    if frame.empty:
        return frame
    frame["district"] = frame.district.map(normalized_district)
    sets = frame.groupby(["cycle", "chamber", "district"]).observation_set_id.nunique()
    if (sets != 1).any():
        raise ValueError("Multiple certified observation sets share one Alabama contest")
    if frame.votes.isna().any() or not frame.vote_value_status.eq("observed").all():
        raise ValueError("Certified canvass rows must carry observed integer totals")
    frame["votes"] = [integer_votes(value, identifier) for value, identifier
                      in zip(frame.votes, frame.source_candidate_result_id)]
    return frame


def canonical_rows(connection, cycles=CYCLES) -> pd.DataFrame:
    placeholders = ",".join("?" for _ in cycles)
    frame = pd.read_sql_query(f"""
        SELECT year AS cycle, chamber AS canonical_chamber, district, canonical_party,
               canonical_name, canonical_votes, canonical_candidate_id, incumbent, winner
        FROM canonical_candidates WHERE year IN ({placeholders})
        ORDER BY year, chamber, CAST(district AS INTEGER), canonical_party
    """, connection, params=tuple(cycles))
    if frame.empty:
        raise ValueError("No Alabama canonical candidates for the requested cycles")
    frame["chamber"] = frame.canonical_chamber.map(CHAMBER)
    if frame.chamber.isna().any() or not frame.canonical_party.isin(PARTY_FAMILY).all():
        raise ValueError("Unexpected canonical chamber or party label")
    frame["district"] = frame.district.map(normalized_district)
    frame["canonical_votes"] = [integer_votes(value, identifier) for value, identifier
                                in zip(frame.canonical_votes, frame.canonical_candidate_id)]
    if frame.duplicated(["cycle", "chamber", "district", "canonical_party"]).any():
        raise ValueError("Canonical candidates are not unique at race/party grain")
    return frame


def set_totals(certified: pd.DataFrame) -> pd.DataFrame:
    """Per certified contest: all-row total, write-in and other-named components."""
    if certified.empty:
        return pd.DataFrame(columns=["observation_set_id", "source_file_id", "total_votes",
                                     "write_in_votes", "other_named_votes", "dem_votes", "rep_votes"])
    frame = certified.copy()
    write_in = frame.writein_status.eq("true")
    dem = frame.party_family.eq("democratic") & ~write_in
    rep = frame.party_family.eq("republican") & ~write_in
    frame["total_votes"] = frame.votes.astype(int)
    frame["write_in_votes"] = frame.votes.where(write_in, 0).astype(int)
    frame["dem_votes"] = frame.votes.where(dem, 0).astype(int)
    frame["rep_votes"] = frame.votes.where(rep, 0).astype(int)
    frame["other_named_votes"] = frame.votes.where(~write_in & ~dem & ~rep, 0).astype(int)
    grouped = frame.groupby(["observation_set_id", "source_file_id"], as_index=False)[
        ["total_votes", "write_in_votes", "other_named_votes", "dem_votes", "rep_votes"]
    ].sum()
    for column in ("total_votes", "write_in_votes", "other_named_votes", "dem_votes", "rep_votes"):
        grouped[column] = grouped[column].astype(int)
    return grouped


def precinct_alignment_2018(root: Path = ROOT) -> dict[tuple, str]:
    """Aligned precinct-workbook names per certified 2018 named cell (secondary evidence)."""
    import alabama_2018_official_results as adapter

    reconciled, _ = adapter.reconcile_sources(root)
    aligned = reconciled[
        reconciled.category.eq("named_candidate")
        & reconciled.candidate_alignment_method.eq("unique_exact_contest_party_category")
    ]
    result = {}
    for row in aligned.itertuples(index=False):
        key = (2018, CHAMBER[row.chamber], normalized_district(row.district), row.party,
               str(row.canvass_printed_candidate))
        if key in result:
            raise ValueError(f"Ambiguous 2018 precinct alignment: {key}")
        result[key] = str(row.candidate_norm)
    return result


def build_bridge(canonical: pd.DataFrame, certified: pd.DataFrame, decoder: dict[str, str],
                 precinct_alignment: dict[tuple, str] | None = None, run_id: str = "staged",
                 recorded_at: str = "staged") -> pd.DataFrame:
    """Return one approved bridge row per canonical candidate or raise with the failures."""
    precinct_alignment = precinct_alignment or {}
    named = certified[certified.writein_status.ne("true")]
    index: dict[tuple, list] = {}
    for row in named.itertuples(index=False):
        index.setdefault((int(row.cycle), row.chamber, row.district, row.party_family), []).append(row)
    failures, rows = [], []
    for row in canonical.itertuples(index=False):
        key = (int(row.cycle), row.chamber, row.district, PARTY_FAMILY[row.canonical_party])
        matches = index.get(key, [])
        if len(matches) != 1:
            failures.append({"canonical_candidate_id": row.canonical_candidate_id,
                             "reason": "no_certified_candidate" if not matches else "ambiguous_certified_candidates"})
            continue
        certified_row = matches[0]
        aligned = precinct_alignment.get((int(row.cycle), row.chamber, row.district, row.canonical_party,
                                          str(certified_row.candidate_name)))
        method, decoded = name_evidence(row.canonical_name, certified_row.candidate_name, decoder, aligned)
        if method is None:
            failures.append({"canonical_candidate_id": row.canonical_candidate_id,
                             "reason": "no_name_evidence", "certified_candidate_name": certified_row.candidate_name})
            continue
        before, after = int(row.canonical_votes), int(certified_row.votes)
        evidence = {
            "authority": "certified State Canvassing Board canvass total",
            "certified_candidate_name": certified_row.candidate_name,
            "certified_party_original": certified_row.party_original,
            "canonical_name": row.canonical_name,
            "decoded_canonical_name": decoded,
            "aligned_precinct_candidate_norm": aligned,
            "physical_cell_source_candidate_result_id": certified_row.source_candidate_result_id,
            "certified_set_validation_status": certified_row.set_validation_status,
            "certified_candidate_validation_status": certified_row.candidate_validation_status,
            "rationale": ("Unique certified named candidate at exact cycle/chamber/district/party grain; "
                          f"name evidence {method}; canonical total "
                          + ("equals the certified total" if before == after
                             else f"corrected from {before} to certified {after} (precinct blanks are unknown, not zero)")),
        }
        rows.append({
            "bridge_id": identifier("ALCERTBR", row.canonical_candidate_id, certified_row.source_candidate_result_id),
            "build_run_id": run_id, "canonical_candidate_id": row.canonical_candidate_id,
            "cycle": int(row.cycle), "chamber": row.chamber, "district": row.district,
            "canonical_party": row.canonical_party, "canonical_name": row.canonical_name,
            "decoded_canonical_name": decoded, "observation_set_id": certified_row.observation_set_id,
            "source_candidate_result_id": certified_row.source_candidate_result_id,
            "source_file_id": certified_row.source_file_id,
            "certified_candidate_name": certified_row.candidate_name, "match_method": method,
            "canonical_votes_before": before, "certified_votes": after, "vote_delta": after - before,
            "correction_status": "agrees" if before == after else "corrected_to_certified",
            "review_status": "approved", "evidence_json": encode(evidence), "recorded_at_utc": recorded_at,
        })
    if failures:
        raise ValueError("Alabama certified bridge is incomplete: " + encode(failures[:25]))
    bridge = pd.DataFrame(rows, columns=BRIDGE_COLUMNS)
    if bridge.source_candidate_result_id.duplicated().any():
        raise ValueError("Two canonical candidates bridged to one certified cell")
    return bridge


def bridge_lookup(connection) -> tuple[dict[str, dict] | None, dict[str, dict] | None]:
    """Return (candidate bridge rows by canonical ID, certified set totals) or (None, None)."""
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (BRIDGE_TABLE,)
    ).fetchone()
    if not exists:
        return None, None
    bridge = pd.read_sql_query(f"SELECT * FROM {BRIDGE_TABLE}", connection)
    if bridge.empty:
        return None, None
    if not bridge.review_status.eq("approved").all():
        raise ValueError("Unapproved Alabama certified bridge rows present")
    cycles = tuple(sorted(int(value) for value in bridge.cycle.unique()))
    totals = set_totals(certified_rows(connection, cycles))
    candidates = {row["canonical_candidate_id"]: row for row in bridge.to_dict("records")}
    sets = {row["observation_set_id"]: row for row in totals.to_dict("records")}
    return candidates, sets


def alabama_certified_outcome_fields(group: pd.DataFrame, candidates: dict[str, dict],
                                     sets: dict[str, dict]) -> tuple[str, int, dict]:
    """Return (source_file_id, third_party_votes, flags) for one Alabama canonical contest.

    Every contributing canonical candidate must bridge to the same certified
    observation set and source file with an equal vote total; otherwise the
    Southern preparation build must fail rather than propagate a stale total.
    """
    bridged = []
    for row in group.itertuples(index=False):
        record = candidates.get(row.candidate_result_id)
        if record is None:
            raise ValueError(f"Alabama canonical candidate lacks a certified bridge: {row.candidate_result_id}")
        if int(row.votes) != int(record["certified_votes"]):
            raise ValueError(
                "Alabama canonical total disagrees with its bridged certified canvass cell; "
                f"rerun the certified-total repair: {row.candidate_result_id}"
            )
        bridged.append(record)
    set_ids = {record["observation_set_id"] for record in bridged}
    files = {record["source_file_id"] for record in bridged}
    if len(set_ids) != 1 or len(files) != 1:
        raise ValueError("Alabama canonical contest bridges to more than one certified set or file")
    set_id, source_file = set_ids.pop(), files.pop()
    totals = sets.get(set_id)
    if totals is None:
        raise ValueError(f"Certified set totals missing for {set_id}")
    third_party = int(totals["total_votes"]) - int(totals["dem_votes"]) - int(totals["rep_votes"])
    if third_party < 0 or int(totals["dem_votes"]) + int(totals["rep_votes"]) != int(group.votes.sum()):
        raise ValueError(f"Certified set totals do not reconcile with the bridged D/R rows: {set_id}")
    flags = {"alabama_certified_bridge": {
        "observation_set_id": set_id, "source_file_id": source_file,
        "third_party_votes_source": "alabama_sos_certified_canvass: all non-major-party named and write-in totals",
        "write_in_votes": int(totals["write_in_votes"]),
        "other_named_votes": int(totals["other_named_votes"]),
        "bridge_match_methods": sorted({record["match_method"] for record in bridged}),
        "corrected_candidates": sorted(record["canonical_candidate_id"] for record in bridged
                                       if record["correction_status"] == "corrected_to_certified"),
    }}
    return source_file, third_party, flags
