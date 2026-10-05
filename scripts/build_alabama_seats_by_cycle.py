#!/usr/bin/env python3
"""Build Alabama House and Senate seats won by party at each regular general election.

Definition: seats won by party at the regular general election, counted as the
final-stage general-election winner of each district, 1994-2022. This is not
chamber composition at session start. Special elections, appointments, deaths
and party switches are excluded. Uncontested seats count for the winner's party.

Winners come only from the central warehouse, opened read-only:

* contest selection: ``fact_southern_legislative_final_candidate_election``
  (the repository's regular-cycle final-stage interface; one observation set
  per state/cycle/chamber/district);
* the recorded winner flag of the selected set: ``canonical_candidates.winner``
  for Alabama canonical rows, ``source_southern_legislative_candidate_result``
  ``winner_status`` for Klarner gap-fill rows;
* every other warehouse observation of the same contest (Klarner, the certified
  SOS canvass, MEDSL) as a cross-check.

A district is ``observed`` only when the selected set has exactly one recorded
winner that is consistent with its votes and no other evidence contradicts the
winner's party. Otherwise it is ``unknown`` and queued for review. Saved
Wikipedia and Ballotpedia pages under ``data/raw/`` are reconciliation evidence
only: they never supply or change a winner, but a district-level contradiction
withholds certification (``unknown``) until a reviewer resolves it.

The script writes only ``data/processed/elections/alabama_seats_by_cycle_v1/``
and never writes to the warehouse.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sqlite3
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "elections" / "alabama_seats_by_cycle_v1"

PRODUCT = "alabama_seats_by_cycle_v1"
CYCLES = (1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022)
CHAMBER_SIZES = {"house": 105, "senate": 35}
WAREHOUSE_CHAMBER = {"house": "lower", "senate": "upper"}
FROM_WAREHOUSE_CHAMBER = {v: k for k, v in WAREHOUSE_CHAMBER.items()}
PARTIES = ("democratic", "republican", "other")
SEAT_PARTIES = PARTIES + ("unknown",)
SELECTED_TABLE = "fact_southern_legislative_final_candidate_election"
REGULAR_STAGE = "general"

DEFINITION = (
    "Seats won by party at the regular general election, counted as the final-stage "
    "general-election winner of each district. This is not chamber composition at "
    "session start. Uncontested seats count for the winner's party. A district whose "
    "winner cannot be determined from the warehouse, or whose warehouse winner is "
    "contradicted by other evidence, is 'unknown' and queued for review; no winner is "
    "inferred from a reference page or filled in silently."
)
EXCLUSIONS = (
    "special elections and special runoffs",
    "appointments to vacancies",
    "deaths, resignations and other vacancies after the general election",
    "party switches after the general election",
    "primary and primary-runoff results",
)
PARTY_BUCKET = {
    "democratic": "democratic",
    "republican": "republican",
    "independent": "other",
    "other": "other",
}
AGGREGATE_NAME = re.compile(
    r"^\s*(write[- ]?ins?|writein|over\s*votes?|under\s*votes?|scattering|blank)\s*$", re.I)

# District-level winner checks compare only the party bucket, never names.
WIKI_PARTY_LABELS = {
    "democratic": "democratic", "republican": "republican", "independent": "other",
    "libertarian": "other", "green": "other", "constitution": "other", "reform": "other",
}
WIKI_CAPTION_EXCLUDE = re.compile(
    r"primary|runoff|special|\b(?:Democratic|Republican|Libertarian)\s+election\b", re.I)
WIKI_DISTRICT_PATTERNS = (
    re.compile(r"(\d+)(?:st|nd|rd|th)\s+(?:State\s+)?(?:House|Senate)\b"),
    re.compile(r"(\d+)(?:st|nd|rd|th)\s+[Dd]istrict\b"),
    re.compile(r"\b[Dd]istrict\s+(\d+)\b"),
)
WIKI_HOLD_GAIN = re.compile(
    r"^(Democratic|Republican|Independent|Libertarian)\s+(?:hold|gain)\b", re.I)
WIKI_SEATS_AFTER_LABELS = ("Seats after", "Seats won")
WIKI_LAST_ELECTION_LABEL = "Last election"


# --------------------------------------------------------------------------- utils

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def connect_readonly(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"Warehouse not found: {path}")
    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    return con


def frame_digest(frame: pd.DataFrame) -> str:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n")
    return sha256_bytes(buffer.getvalue().encode("utf-8"))


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n", encoding="utf-8")


def bucket(party_family: object) -> str | None:
    return PARTY_BUCKET.get(str(party_family).strip().lower()) if party_family is not None else None


def is_aggregate(name: object, writein_status: object = None) -> bool:
    if str(writein_status).lower() == "true":
        return True
    return bool(AGGREGATE_NAME.match(str(name or "")))


def int_or_none(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return int(value)


def text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


REVIEW_COLUMNS = ("review_id", "cycle", "chamber", "district", "scope", "issue_type", "severity",
                  "recorded_value", "conflicting_value", "evidence", "evidence_sources",
                  "review_status")
SCOPE_ORDER = {"district": 0, "contest_structure": 1, "total": 2}


# ------------------------------------------------------------- warehouse loading

def load_warehouse(con: sqlite3.Connection, cycles: tuple[int, ...]) -> dict[str, pd.DataFrame]:
    """Read only the Alabama rows needed, as small filtered queries."""
    marks = ",".join("?" for _ in cycles)
    selected = pd.read_sql_query(
        f"""SELECT candidate_result_id, observation_set_id, cycle, chamber, district,
                   district_plan_id, geography_vintage, election_stage, election_date,
                   candidate_name, party_family, party_original, votes, vote_value_status,
                   source_provider, source_family, source_file_id, authority_rank,
                   build_run_id, validation_status, final_stage_rule
            FROM {SELECTED_TABLE}
            WHERE state_code='AL' AND cycle IN ({marks})""",
        con, params=list(cycles))
    canonical = pd.read_sql_query(
        f"""SELECT canonical_candidate_id, year, chamber, district, canonical_party,
                   winner, canonical_source, person_id
            FROM canonical_candidates WHERE year IN ({marks})""",
        con, params=list(cycles))
    observations = pd.read_sql_query(
        f"""SELECT s.observation_set_id, s.source_family, s.provider, s.source_file_id,
                   s.source_member, s.cycle, s.chamber, s.district, s.election_stage,
                   s.validation_status AS set_validation_status,
                   c.source_candidate_result_id, c.candidate_name, c.party_family,
                   c.party_original, c.votes, c.writein_status, c.winner_status
            FROM source_southern_legislative_candidate_result c
            JOIN source_southern_legislative_observation_set s USING(observation_set_id)
            WHERE s.state_code='AL' AND s.cycle IN ({marks}) AND s.election_stage=?""",
        con, params=[*cycles, REGULAR_STAGE])
    bridge = pd.read_sql_query(
        f"""SELECT canonical_candidate_id, source_file_id AS certified_source_file_id,
                   source_candidate_result_id AS certified_candidate_result_id,
                   match_method, correction_status
            FROM bridge_alabama_canonical_candidate_certified_result
            WHERE cycle IN ({marks})""",
        con, params=list(cycles))
    lo, hi = min(cycles), max(cycles)
    stages = pd.read_sql_query(
        """SELECT 'canonical_southern_legislative_candidate_election' AS warehouse_object,
                  election_stage, COUNT(DISTINCT observation_set_id) AS observation_sets
           FROM canonical_southern_legislative_candidate_election
           WHERE state_code='AL' AND cycle BETWEEN ? AND ? GROUP BY election_stage
           UNION ALL
           SELECT 'source_southern_legislative_observation_set', election_stage, COUNT(*)
           FROM source_southern_legislative_observation_set
           WHERE state_code='AL' AND cycle BETWEEN ? AND ? GROUP BY election_stage""",
        con, params=[lo, hi, lo, hi])
    for frame in (selected, observations):
        frame["district"] = frame["district"].astype(str)
    canonical["district"] = canonical["district"].astype(int).astype(str)
    return {"selected": selected, "canonical": canonical, "observations": observations,
            "bridge": bridge, "stages": stages}


def warehouse_metadata(con: sqlite3.Connection, selected: pd.DataFrame) -> dict:
    schema = con.execute(
        "SELECT version, applied_at_utc, description FROM warehouse_schema_version "
        "ORDER BY version DESC LIMIT 1").fetchone()
    latest = con.execute(
        "SELECT build_run_id, target, completed_at_utc, status, code_commit "
        "FROM warehouse_build_run WHERE status='validated' "
        "ORDER BY completed_at_utc DESC LIMIT 1").fetchone()
    row_runs = sorted(selected["build_run_id"].dropna().unique().tolist())
    run_rows = []
    for run in row_runs:
        found = con.execute(
            "SELECT build_run_id, target, completed_at_utc, status, code_commit "
            "FROM warehouse_build_run WHERE build_run_id=?", (run,)).fetchone()
        run_rows.append(dict(zip(("build_run_id", "target", "completed_at_utc", "status",
                                  "code_commit"), found)) if found else
                        {"build_run_id": run, "registered": False,
                         "note": "synthetic id emitted by the all-observations view"})
    return {
        "schema_version": dict(zip(("version", "applied_at_utc", "description"), schema))
        if schema else None,
        "latest_validated_build_run": dict(zip(
            ("build_run_id", "target", "completed_at_utc", "status", "code_commit"), latest))
        if latest else None,
        "selected_row_build_runs": run_rows,
    }


# ---------------------------------------------------------- winner determination

def plurality(candidates: list[dict]) -> tuple[str | None, str]:
    """Party bucket of the unique top named candidate, or None with a reason.

    Each candidate is a dict with ``bucket``, ``votes`` and ``aggregate`` keys.
    Write-in aggregates and over/under votes are never winners; if an aggregate
    meets or beats the top named candidate the result is undetermined.
    """
    named = [c for c in candidates if not c["aggregate"]]
    if not named:
        return None, "no_named_candidates"
    if any(c["votes"] is None for c in named):
        return None, "named_candidate_votes_missing"
    top = max(c["votes"] for c in named)
    leaders = [c for c in named if c["votes"] == top]
    if len(leaders) != 1:
        return None, "tie_for_first"
    aggregates = [c["votes"] for c in candidates if c["aggregate"] and c["votes"] is not None]
    if aggregates and max(aggregates) >= top:
        return None, "aggregate_votes_meet_or_exceed_leader"
    if leaders[0]["bucket"] is None:
        return None, "leader_party_unrecorded"
    return leaders[0]["bucket"], "plurality"


def recorded_winner(rows: list[dict]) -> dict:
    """Winner of the selected set from its recorded winner flag, checked against votes."""
    flags = [r["winner_flag"] for r in rows]
    flagged = [r for r in rows if r["winner_flag"] == 1]
    result = {"winner": None, "basis": "", "reason": ""}
    if len(flagged) > 1:
        result["reason"] = "multiple_recorded_winners"
        return result
    if len(flagged) == 1:
        winner = flagged[0]
        named = [r for r in rows if not r["aggregate"]]
        if all(r["votes"] is not None for r in named):
            top = max(r["votes"] for r in named)
            leaders = [r for r in named if r["votes"] == top]
            if len(leaders) != 1 or leaders[0] is not winner:
                result["reason"] = "recorded_winner_contradicts_votes"
                return result
            result["basis"] = "recorded_winner_flag_and_plurality"
        else:
            result["basis"] = "recorded_winner_flag_votes_incomplete"
        result["winner"] = winner
    elif any(f is not None for f in flags):
        result["reason"] = "no_recorded_winner"
        return result
    else:
        party, why = plurality(rows)
        if party is None:
            result["reason"] = f"no_winner_flag_and_{why}"
            return result
        named = [r for r in rows if not r["aggregate"]]
        top = max(r["votes"] for r in named)
        result["winner"] = next(r for r in named if r["votes"] == top)
        result["basis"] = "plurality_without_recorded_flag"
    if result["winner"]["bucket"] is None:
        result["winner"] = None
        result["basis"] = ""
        result["reason"] = "winner_party_unrecorded"
    return result


def classify_contest(selected_named: int, selected_scope: str,
                     full_ballot_counts: dict[str, int]) -> tuple[str, str]:
    """Contested / uncontested from positive evidence only.

    ``full_ballot_counts`` maps each observation family that lists every named
    ballot candidate to its count of named candidates. A D/R-only selected set
    cannot by itself establish that a contest was uncontested.
    """
    counts = dict(full_ballot_counts)
    if selected_scope == "all_named_candidates":
        counts.setdefault("selected", selected_named)
    largest = max([selected_named, *counts.values()]) if counts else selected_named
    if largest >= 2:
        sources = sorted(k for k, v in counts.items() if v >= 2) or ["selected"]
        return "contested", "two_or_more_named_candidates:" + ",".join(sources)
    if counts and largest == 1 and all(v == 1 for v in counts.values()) and selected_named == 1:
        return "uncontested", "single_named_candidate_in_all_full_ballot_observations:" + \
            ",".join(sorted(counts))
    if largest == 0:
        return "unknown", "no_named_candidates"
    return "unknown", "no_full_ballot_observation"


def candidate_rows(frame: pd.DataFrame, *, name: str, bucket_col: str = "party_family",
                   writein_col: str | None = None) -> list[dict]:
    rows = []
    for record in frame.to_dict("records"):
        rows.append({
            **record,
            "bucket": bucket(record.get(bucket_col)),
            "votes": int_or_none(record.get("votes")),
            "winner_flag": int_or_none(record.get("winner_flag")),
            "aggregate": is_aggregate(record.get(name),
                                      record.get(writein_col) if writein_col else None),
        })
    return rows


def determine_districts(data: dict[str, pd.DataFrame], cycles: tuple[int, ...],
                        sizes: dict[str, int], reference_districts: dict | None = None,
                        demote_keys: frozenset = frozenset()) -> tuple[pd.DataFrame, list[dict]]:
    """One row per cycle x chamber x district, plus district-level review items.

    ``demote_keys`` lists districts whose reference contradiction is backed by an
    external seat total (see ``supported_reference_conflicts``)."""
    reference_districts = reference_districts or {}
    selected = data["selected"].copy()
    canonical = data["canonical"].set_index("canonical_candidate_id")
    if not canonical.index.is_unique:
        raise ValueError("canonical_candidates.canonical_candidate_id is not unique")
    observations = data["observations"]
    obs_by_id = observations.drop_duplicates("source_candidate_result_id") \
        .set_index("source_candidate_result_id")
    if len(obs_by_id) != len(observations):
        raise ValueError("source_candidate_result_id is not unique")
    bridge = data["bridge"].set_index("canonical_candidate_id")
    if not bridge.index.is_unique:
        raise ValueError("certified bridge has more than one row per canonical candidate")

    # Recorded winner flag joins: each selected row joins at most one flag row (1:0..1).
    def flag_for(row: pd.Series) -> tuple[int | None, str]:
        if row["source_family"] == "alabama_canonical":
            if row["candidate_result_id"] in canonical.index:
                return int_or_none(canonical.at[row["candidate_result_id"], "winner"]), \
                    "canonical_candidates"
            return None, "canonical_candidates(missing)"
        if row["candidate_result_id"] in obs_by_id.index:
            return int_or_none(obs_by_id.at[row["candidate_result_id"], "winner_status"]), \
                "source_southern_legislative_candidate_result"
        return None, ""

    flag_info = selected.apply(flag_for, axis=1, result_type="expand")
    selected["winner_flag"] = flag_info[0] if not selected.empty else []
    selected["winner_flag_table"] = flag_info[1] if not selected.empty else []
    selected["chamber_key"] = selected["chamber"].map(FROM_WAREHOUSE_CHAMBER)
    obs = observations.copy()
    obs["chamber_key"] = obs["chamber"].map(FROM_WAREHOUSE_CHAMBER)

    sel_groups = {k: g for k, g in selected.groupby(["cycle", "chamber_key", "district"])}
    obs_groups = {k: g for k, g in obs.groupby(["cycle", "chamber_key", "district"])}

    records, review = [], []
    expected = {(c, ch, str(d)) for c in cycles for ch, n in sizes.items()
                for d in range(1, n + 1)}
    for key in sorted(set(sel_groups) - expected, key=lambda k: (k[0], k[1], str(k[2]))):
        review.append(review_item(key[0], key[1], key[2], "district",
                                  "unexpected_district_label", "blocking",
                                  recorded=str(sorted(sel_groups[key].observation_set_id.unique())),
                                  evidence="Selected final-stage set has a district label outside "
                                           "the chamber's numbered districts; not counted."))
    for cycle in cycles:
        for chamber, size in sizes.items():
            for number in range(1, size + 1):
                key = (cycle, chamber, str(number))
                record, items = decide_district(
                    key, sel_groups.get(key), obs_groups.get(key), bridge,
                    canonical, reference_districts.get(key), key in demote_keys)
                records.append(record)
                review.extend(items)
    frame = pd.DataFrame.from_records(records)
    return frame, review


def decide_district(key, sel: pd.DataFrame | None, alts: pd.DataFrame | None,
                    bridge: pd.DataFrame, canonical: pd.DataFrame,
                    reference: list[dict] | None,
                    demote_on_reference: bool = False) -> tuple[dict, list[dict]]:
    cycle, chamber, district = key
    rec = {
        "cycle": cycle, "chamber": chamber, "district": int(district),
        "district_plan_id": "", "geography_vintage": "", "election_stage": "",
        "election_date": "", "winner_status": "unknown", "winner_party": "unknown",
        "winner_name_recorded": "", "winner_party_recorded": "",
        "winner_party_original": "", "winner_votes": None, "winner_basis": "",
        "contest_status": "unknown", "contest_status_basis": "",
        "named_candidates_selected": 0, "named_candidates_max_any_observation": 0,
        "selected_candidate_scope": "", "corroboration": "", "cross_source_check": "",
        "reference_check": "not_available", "unknown_reason": "", "review_ids": "",
        "warehouse_table": SELECTED_TABLE, "observation_set_id": "",
        "winner_candidate_result_id": "", "candidate_result_ids": "",
        "source_family": "", "source_provider": "", "source_file_id": "",
        "winner_flag_table": "", "canonical_source": "", "person_id": "",
        "certified_source_file_id": "", "certified_candidate_result_id": "",
        "row_build_run_ids": "", "final_stage_rule": "",
    }
    items: list[dict] = []
    reasons: list[str] = []

    if sel is None or sel.empty:
        reasons.append("no_final_stage_observation")
        rec["unknown_reason"] = ";".join(reasons)
        items.append(review_item(cycle, chamber, district, "district",
                                 "no_final_stage_observation", "blocking",
                                 evidence=f"No row in {SELECTED_TABLE} for this district."))
        return finish(rec, items)

    sets = sorted(sel["observation_set_id"].unique())
    first = sel.iloc[0]
    rec.update({
        "district_plan_id": text(first["district_plan_id"]),
        "geography_vintage": text(first["geography_vintage"]),
        "election_stage": first["election_stage"],
        "election_date": text(first["election_date"]),
        "observation_set_id": ";".join(sets),
        "candidate_result_ids": ";".join(sorted(sel["candidate_result_id"])),
        "source_family": ";".join(sorted(sel["source_family"].unique())),
        "source_provider": ";".join(sorted(sel["source_provider"].unique())),
        "source_file_id": ";".join(sorted(sel["source_file_id"].dropna().unique())),
        "row_build_run_ids": ";".join(sorted(sel["build_run_id"].dropna().unique())),
        "final_stage_rule": first["final_stage_rule"],
        "winner_flag_table": ";".join(sorted(set(sel["winner_flag_table"]) - {""})),
    })
    if len(sets) != 1:
        reasons.append("multiple_final_stage_sets")
        items.append(review_item(cycle, chamber, district, "district",
                                 "multiple_final_stage_sets", "blocking",
                                 recorded=";".join(sets),
                                 evidence="The final-stage interface returned more than one "
                                          "observation set; the expected cardinality is 1."))
        rec["unknown_reason"] = ";".join(reasons)
        return finish(rec, items)
    if (sel["election_stage"] != REGULAR_STAGE).any():
        reasons.append("non_general_stage")

    family = first["source_family"]
    scope = "major_party_rows_only" if family == "alabama_canonical" else "all_named_candidates"
    rec["selected_candidate_scope"] = scope
    rows = candidate_rows(sel, name="candidate_name")
    rec["named_candidates_selected"] = sum(
        1 for r in rows if not r["aggregate"] and (r["votes"] is None or r["votes"] > 0))

    decided = recorded_winner(rows)
    winner = decided["winner"]
    if winner is None:
        reasons.append(decided["reason"])
    else:
        rec.update({
            "winner_name_recorded": winner["candidate_name"],
            "winner_party_recorded": winner["party_family"],
            "winner_party_original": text(winner["party_original"]),
            "winner_votes": winner["votes"],
            "winner_basis": decided["basis"],
            "winner_candidate_result_id": winner["candidate_result_id"],
        })
        wid = winner["candidate_result_id"]
        if family == "alabama_canonical" and wid in canonical.index:
            rec["canonical_source"] = text(canonical.at[wid, "canonical_source"])
            rec["person_id"] = text(canonical.at[wid, "person_id"])
        if wid in bridge.index:
            rec["certified_source_file_id"] = text(bridge.at[wid, "certified_source_file_id"])
            rec["certified_candidate_result_id"] = text(
                bridge.at[wid, "certified_candidate_result_id"])

    # Cross-check against every other warehouse observation of the same contest.
    checks, full_ballot, conflicts = [], {}, []
    if alts is not None:
        for set_id, group in sorted(alts.groupby("observation_set_id"), key=lambda kv: kv[0]):
            if set_id in sets:
                continue
            fam = group["source_family"].iloc[0]
            cands = candidate_rows(group, name="candidate_name", writein_col="writein_status")
            named = [c for c in cands if not c["aggregate"]
                     and (c["votes"] is None or c["votes"] > 0)]
            full_ballot[fam] = max(full_ballot.get(fam, 0), len(named))
            party, why = plurality(cands)
            if party is None:
                checks.append(f"undetermined:{fam}({why})")
            elif winner is None:
                checks.append(f"observed:{fam}={party}")
            elif party == winner["bucket"]:
                checks.append(f"agree:{fam}")
            else:
                checks.append(f"conflict:{fam}")
                conflicts.append((fam, set_id, party, summarize_candidates(cands)))
    rec["cross_source_check"] = "|".join(checks) if checks else "none_available"
    rec["named_candidates_max_any_observation"] = max(
        [rec["named_candidates_selected"], *full_ballot.values()])
    status, basis = classify_contest(rec["named_candidates_selected"], scope, full_ballot)
    rec["contest_status"], rec["contest_status_basis"] = status, basis

    selected_summary = summarize_candidates(rows)
    if conflicts:
        reasons.append("cross_source_winner_party_conflict")
        items.append(review_item(
            cycle, chamber, district, "district", "cross_source_winner_party_conflict",
            "blocking", recorded=f"{family} {sets[0]}: {selected_summary}",
            conflicting=" || ".join(f"{fam} {sid}: winner party {p}; {summary}"
                                    for fam, sid, p, summary in conflicts),
            evidence="The selected final-stage set and another warehouse observation of the "
                     "same contest disagree on the winning party. No winner is counted until "
                     "a reviewer adjudicates the source conflict.",
            sources=";".join([f"{SELECTED_TABLE}:{sets[0]}"] + [
                f"source_southern_legislative_observation_set:{sid}"
                for _, sid, _, _ in conflicts])))

    # District-level reference check (never supplies a winner).
    if reference:
        determined = [r for r in reference if r["winner_bucket"]]
        if not determined:
            rec["reference_check"] = "undetermined:" + ",".join(
                sorted({r["reference_kind"] for r in reference}))
        else:
            ref_parties = {r["winner_bucket"] for r in determined}
            if winner is None:
                rec["reference_check"] = "observed:" + ",".join(sorted(ref_parties))
            elif ref_parties == {winner["bucket"]}:
                rec["reference_check"] = "agree:" + ",".join(
                    sorted({r["reference_kind"] for r in determined}))
            else:
                kinds = ",".join(sorted({r["reference_kind"] for r in determined}))
                conflicting = " || ".join(
                    f"{r['reference_path']} [{r['caption']}]: winner party "
                    f"{r['winner_bucket']} ({r['winner_rule']}); {r['candidates']}"
                    for r in determined)
                sources = ";".join(sorted({r["reference_path"] for r in determined}))
                recorded = f"{family} {sets[0]}: {selected_summary}"
                if reasons:
                    rec["reference_check"] = "conflict_with_recorded_winner:" + kinds
                    items.append(review_item(
                        cycle, chamber, district, "district",
                        "reference_table_also_contradicts_recorded_winner", "info",
                        recorded=recorded, conflicting=conflicting,
                        evidence="The district is already held as unknown ("
                                 + ";".join(reasons) + "); a reference district result table "
                                 "also names a different winning party than the recorded "
                                 "warehouse winner. Supporting evidence for the reviewer only.",
                        sources=sources))
                elif demote_on_reference:
                    rec["reference_check"] = "conflict_backed_by_external_totals:" + kinds
                    reasons.append("reference_winner_party_conflict")
                    items.append(review_item(
                        cycle, chamber, district, "district", "reference_winner_party_conflict",
                        "blocking", recorded=recorded, conflicting=conflicting,
                        evidence="A reference district result table names a different winning "
                                 "party, and an external seat total for this cycle and chamber "
                                 "is off from the warehouse count in the same direction. The "
                                 "reference does not supply the winner; the district is held "
                                 "as unknown until a reviewer resolves the conflict.",
                        sources=sources))
                else:
                    rec["reference_check"] = "conflict_not_backed_by_external_totals:" + kinds
                    items.append(review_item(
                        cycle, chamber, district, "district",
                        "reference_table_conflict_not_backed_by_totals", "info",
                        recorded=recorded, conflicting=conflicting,
                        evidence="A reference district result table names a different winning "
                                 "party, but no external seat total for this cycle and chamber "
                                 "is off in that direction, so the reference table is treated "
                                 "as internally inconsistent and the warehouse winner stands. "
                                 "Cross-source check: " + (";".join(checks) or "none"),
                        sources=sources))

    reasons = list(dict.fromkeys(reasons))
    if "reference_winner_party_conflict" in reasons and rec["contest_status"] == "uncontested":
        # A reference naming another winner undermines the single-candidate evidence.
        rec["contest_status"] = "unknown"
        rec["contest_status_basis"] = "warehouse_lists_one_candidate_but_reference_conflicts"
    if winner is not None and not reasons:
        rec["winner_status"] = "observed"
        rec["winner_party"] = winner["bucket"]
    elif winner is None or not any(i["severity"] == "blocking" for i in items):
        items.append(review_item(
            cycle, chamber, district, "district", reasons[0], "blocking",
            recorded=f"{family} {sets[0]}: {selected_summary}",
            evidence="The selected final-stage set does not yield a single recorded winner "
                     "consistent with its votes." if winner is None else
                     f"The selected final-stage set is held as unknown: {reasons[0]}."))
    rec["unknown_reason"] = ";".join(reasons)
    agreeing = [c for c in checks if c.startswith("agree:")]
    if rec["winner_status"] == "unknown":
        rec["corroboration"] = "unresolved"
    elif agreeing:
        rec["corroboration"] = "corroborated_by_other_warehouse_source"
    elif rec["reference_check"].startswith("agree:"):
        rec["corroboration"] = "corroborated_by_reference_only"
    else:
        rec["corroboration"] = "single_source"
    return finish(rec, items)


def summarize_candidates(rows: list[dict]) -> str:
    parts = []
    for r in sorted(rows, key=lambda x: -(x["votes"] or -1)):
        if r["aggregate"]:
            continue
        parts.append(f"{r['candidate_name']} ({r['party_family']}) {r['votes']}")
    return "; ".join(parts)


def finish(rec: dict, items: list[dict]) -> tuple[dict, list[dict]]:
    rec["review_ids"] = ";".join(i["review_id"] for i in items)
    return rec, items


def review_item(cycle, chamber, district, scope, issue, severity, *, recorded="",
                conflicting="", evidence="", sources="") -> dict:
    district_part = f"{int(district):03d}" if str(district).isdigit() else "TOTAL"
    return {
        "review_id": f"SEATS-V1-{cycle}-{chamber.upper()}-{district_part}-{issue}",
        "cycle": cycle, "chamber": chamber,
        "district": int(district) if str(district).isdigit() else "",
        "scope": scope, "issue_type": issue, "severity": severity,
        "recorded_value": recorded, "conflicting_value": conflicting,
        "evidence": evidence, "evidence_sources": sources, "review_status": "open",
    }


# ------------------------------------------------------------------ seat totals

def summarize_seats(districts: pd.DataFrame, sizes: dict[str, int]) -> pd.DataFrame:
    if not districts["winner_party"].isin(SEAT_PARTIES).all():
        raise ValueError("unexpected winner_party value")
    bad = districts[(districts.winner_status == "unknown") != (districts.winner_party == "unknown")]
    if not bad.empty:
        raise ValueError("winner_status and winner_party disagree on unknown")
    rows = []
    for (cycle, chamber), group in districts.groupby(["cycle", "chamber"], sort=True):
        size = sizes[chamber]
        if len(group) != size or group["district"].nunique() != size:
            raise ValueError(f"{cycle} {chamber}: {len(group)} district rows, expected {size}")
        for party in SEAT_PARTIES:
            part = group[group.winner_party == party]
            rows.append({
                "cycle": cycle, "chamber": chamber, "party": party, "seats": len(part),
                "uncontested_seats": int((part.contest_status == "uncontested").sum()),
                "chamber_size": size,
            })
    seats = pd.DataFrame(rows)
    totals = seats.groupby(["cycle", "chamber"])["seats"].sum()
    if not (totals == seats.groupby(["cycle", "chamber"])["chamber_size"].first()).all():
        raise ValueError("seat counts do not sum to chamber size")
    return seats


def seat_counts(seats: pd.DataFrame) -> dict[tuple[int, str], dict[str, int]]:
    out: dict[tuple[int, str], dict[str, int]] = defaultdict(dict)
    for row in seats.itertuples(index=False):
        out[(row.cycle, row.chamber)][row.party] = row.seats
    return out


# ------------------------------------------------------------- reference parsing

def parse_seat_value(text: str) -> tuple[int, int] | None:
    match = re.match(r"^\s*(\d+)(?:\s*\+\s*(\d+))?", text or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2) or 0)


def wiki_infobox_rows(soup) -> list[dict[str, list[str]]]:
    """Infobox label rows grouped into party blocks (a new block per 'Party' row)."""
    box = soup.find("table", class_=re.compile(r"\binfobox\b"))
    if box is None:
        return []
    blocks: list[dict[str, list[str]]] = []
    for tr in box.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"], recursive=False)]
        if len(cells) < 2:
            continue
        if cells[0] == "Party":
            blocks.append({"Party": cells[1:]})
        elif blocks and cells[0] not in blocks[-1]:
            blocks[-1][cells[0]] = cells[1:]
    return blocks


def wiki_infobox_totals(blocks: list[dict[str, list[str]]], labels: tuple[str, ...]) -> dict | None:
    totals = {"democratic": 0, "republican": 0, "other": 0}
    raw, found = [], False
    for block in blocks:
        label = next((lab for lab in labels if lab in block), None)
        if label is None:
            continue
        for party, value in zip(block["Party"], block[label]):
            parsed = parse_seat_value(value)
            if parsed is None:
                continue
            found = True
            base, plus = parsed
            key = WIKI_PARTY_LABELS.get(party.strip().lower(), "other")
            totals[key] += base
            # Wikipedia lists a member caucusing with a party as "N+1" in that
            # party's column; the "+1" is not a seat won under that party label.
            totals["other"] += plus
            raw.append(f"{party}={value}")
        raw_label = label
    if not found:
        return None
    return {**totals, "raw": f"{raw_label}: " + "; ".join(raw), "field": raw_label}


def wiki_district_tables(soup, size: int) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = defaultdict(list)
    for table in soup.find_all("table"):
        caption_tag = table.find("caption")
        if caption_tag is None:
            continue
        caption = caption_tag.get_text(" ", strip=True)
        if WIKI_CAPTION_EXCLUDE.search(caption):
            continue
        number = None
        for pattern in WIKI_DISTRICT_PATTERNS:
            match = pattern.search(caption)
            if match:
                number = int(match.group(1))
                break
        if number is None or not 1 <= number <= size:
            continue
        cands, hold = [], None
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            for cell in cells:
                hit = WIKI_HOLD_GAIN.match(cell)
                if hit:
                    hold = WIKI_PARTY_LABELS[hit.group(1).lower()]
            idx = next((i for i, x in enumerate(cells) if x.lower() in WIKI_PARTY_LABELS), None)
            if idx is None or idx + 1 >= len(cells):
                continue
            name = re.sub(r"\[[^]]*]", "", cells[idx + 1]).strip()
            if not name or re.search(r"write[- ]?in", name, re.I):
                continue
            raw_votes = cells[idx + 2].replace(",", "").strip() if idx + 2 < len(cells) else ""
            cands.append({"candidate_name": name, "party_family": cells[idx],
                          "bucket": WIKI_PARTY_LABELS[cells[idx].lower()],
                          "votes": int(raw_votes) if re.fullmatch(r"\d+", raw_votes) else None,
                          "aggregate": False})
        out[number].append({"caption": caption, "candidates": cands, "hold": hold})
    return out


def wiki_table_winner(table: dict) -> tuple[str | None, str]:
    cands = table["candidates"]
    party, why = plurality(cands) if cands else (None, "no_candidates")
    if party is None and len(cands) == 1:
        party, why = cands[0]["bucket"], "single_listed_candidate"
    hold = table["hold"]
    if hold and party and hold != party:
        return None, "hold_gain_row_contradicts_votes"
    if hold:
        return hold, "hold_gain_row" + ("_and_plurality" if party else "")
    return party, why


def ballotpedia_tables(text: str) -> list[dict]:
    """Composition tables: header '| Party | As of ... | After ... |'."""
    lines = text.splitlines()
    tables = []
    for i, line in enumerate(lines):
        header = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(header) < 3 or header[0] != "Party" or not header[1].startswith("As of"):
            continue
        after_idx = next((j for j, h in enumerate(header) if h.startswith("After")), None)
        year = re.search(r"(\d{4})", header[after_idx]) if after_idx is not None else None
        if year is None:
            continue
        from_end = len(header) - after_idx
        counts = {"democratic": 0, "republican": 0, "other": 0, "vacancy": 0}
        raw, total = [], None
        for row in lines[i + 1:i + 12]:
            if not row.strip().startswith("|"):
                break
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            label = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", " ".join(cells[:-len(header) + 1]))
            label = label.replace("*", "").strip()
            value = cells[-from_end].replace("*", "").strip()
            number = int(value) if value.isdigit() else 0
            raw.append(f"{label or '?'}={value}")
            lower = label.lower()
            if lower.startswith("total"):
                total = number
                break
            if "democratic" in lower:
                counts["democratic"] += number
            elif "republican" in lower:
                counts["republican"] += number
            elif "vacan" in lower:
                counts["vacancy"] += number
            else:
                counts["other"] += number
        tables.append({"cycle": int(year.group(1)), "header": header[after_idx],
                       "line": i + 1, "total": total, "raw": "; ".join(raw), **counts})
    return tables


def discover_references(raw: Path) -> list[dict]:
    refs = []
    for path in sorted((raw / "wikipedia").glob("*.html")):
        match = re.fullmatch(r"(\d{4})_(house|senate)\.html", path.name)
        if match:
            refs.append({"kind": "wikipedia", "path": path, "cycle": int(match.group(1)),
                         "chamber": match.group(2),
                         "registration": "git-tracked raw page; no warehouse_source_file row; "
                                         "license not recorded"})
    for path in sorted((raw / "alabama_elections_and_geography").glob("*Wikipedia.html")):
        match = re.fullmatch(r"(\d{4}) Alabama (House of Representatives|Senate) election - "
                             r"Wikipedia\.html", path.name)
        if match:
            refs.append({"kind": "wikipedia", "path": path, "cycle": int(match.group(1)),
                         "chamber": "house" if match.group(2).startswith("House") else "senate",
                         "registration": "local untracked raw page; no warehouse_source_file "
                                         "row; license not recorded"})
    for path in sorted((raw / "ballotpedia" / "election_indexes").glob("*.md")):
        match = re.fullmatch(r"(\d{4})_(house|senate)\.md", path.name)
        if match:
            refs.append({"kind": "ballotpedia", "path": path, "cycle": int(match.group(1)),
                         "chamber": match.group(2),
                         "registration": "local untracked raw page; no warehouse_source_file "
                                         "row; license not recorded"})
    return refs


def page_provenance(kind: str, text: str, soup=None) -> str:
    if kind == "wikipedia" and soup is not None:
        canon = soup.find("link", rel="canonical")
        edited = soup.find(id="footer-info-lastmod")
        return "; ".join(x for x in (
            canon.get("href") if canon else "",
            edited.get_text(" ", strip=True) if edited else "") if x)
    url = re.search(r"^URL Source:\s*(\S+)", text, re.M)
    published = re.search(r"^Published Time:\s*(.+)$", text, re.M)
    return "; ".join(x for x in (url.group(1) if url else "",
                                 f"Published Time: {published.group(1).strip()}"
                                 if published else "") if x)


def load_references(raw: Path, cycles: tuple[int, ...], sizes: dict[str, int]):
    """Parse every saved reference page; return totals, district winners and file facts."""
    from bs4 import BeautifulSoup  # local import keeps fixture tests light

    totals, district_refs, files = [], defaultdict(list), []
    for ref in discover_references(raw):
        path, kind, chamber = ref["path"], ref["kind"], ref["chamber"]
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        digest = sha256_bytes(data)
        base = {"reference_path": rel(path), "reference_sha256": digest,
                "reference_registration": ref["registration"], "chamber": chamber}
        if kind == "wikipedia":
            soup = BeautifulSoup(text, "html.parser")
            provenance = page_provenance(kind, text, soup)
            files.append({**base, "kind": kind, "bytes": len(data), "provenance": provenance})
            blocks = wiki_infobox_rows(soup)
            for target, labels, field in (
                    (ref["cycle"], WIKI_SEATS_AFTER_LABELS, "infobox_seats_after"),
                    (ref["cycle"] - 4, (WIKI_LAST_ELECTION_LABEL,), "infobox_last_election")):
                if target not in cycles:
                    continue
                found = wiki_infobox_totals(blocks, labels)
                if found:
                    totals.append({**base, "cycle": target,
                                   "reference_kind": f"wikipedia_{field}",
                                   "reference_field": f"{found['field']} (page cycle "
                                                      f"{ref['cycle']})",
                                   "reference_raw": found["raw"], "independence": "external",
                                   "provenance": provenance,
                                   "democratic": found["democratic"],
                                   "republican": found["republican"], "other": found["other"],
                                   "unresolved": None})
            if ref["cycle"] in cycles:
                tables = wiki_district_tables(soup, sizes[chamber])
                counts = {"democratic": 0, "republican": 0, "other": 0}
                undetermined = 0
                for number in range(1, sizes[chamber] + 1):
                    winners = []
                    for table in tables.get(number, []):
                        party, why = wiki_table_winner(table)
                        winners.append((party, why, table))
                    determined = {p for p, _, _ in winners if p}
                    agreed = determined.pop() if len(determined) == 1 else None
                    if agreed is None:
                        undetermined += 1
                    else:
                        counts[agreed] += 1
                    for party, why, table in winners:
                        district_refs[(ref["cycle"], chamber, str(number))].append({
                            "reference_kind": "wikipedia_district_table",
                            "reference_path": rel(path), "caption": table["caption"],
                            "winner_bucket": agreed if party else None,
                            "winner_rule": why,
                            "candidates": summarize_candidates(table["candidates"])})
                totals.append({**base, "cycle": ref["cycle"],
                               "reference_kind": "wikipedia_district_tables",
                               "reference_field": "general-election district result tables "
                                                  "(winner by hold/gain row or plurality)",
                               "reference_raw": f"districts determined="
                                                f"{sizes[chamber] - undetermined}; "
                                                f"undetermined={undetermined}",
                               "independence": "external_district_aggregate",
                               "provenance": provenance,
                               **counts, "unresolved": undetermined})
            del soup
        else:
            provenance = page_provenance(kind, text)
            files.append({**base, "kind": kind, "bytes": len(data), "provenance": provenance})
            found_tables = ballotpedia_tables(text)
            seen = set()
            for table in found_tables:
                signature = (table["cycle"], table["democratic"], table["republican"],
                             table["other"], table["vacancy"])
                if table["cycle"] not in cycles or signature in seen:
                    continue
                seen.add(signature)
                totals.append({**base, "cycle": table["cycle"],
                               "reference_kind": "ballotpedia_composition_after_election",
                               "reference_field": f"'{table['header']}' column (line "
                                                  f"{table['line']})",
                               "reference_raw": table["raw"], "independence": "external",
                               "provenance": provenance,
                               "democratic": table["democratic"],
                               "republican": table["republican"], "other": table["other"],
                               "unresolved": table["vacancy"]})
            if ref["cycle"] in cycles and not any(t["cycle"] == ref["cycle"]
                                                  for t in found_tables):
                if re.search(r"page you.re looking for does not exist", text):
                    missing = "page_not_found_snapshot"
                elif len(text.strip()) < 400:
                    missing = "empty_or_stub_snapshot"
                else:
                    missing = "no_seat_totals_on_page"
                totals.append({**base, "cycle": ref["cycle"],
                               "reference_kind": "ballotpedia_composition_after_election",
                               "reference_field": "", "reference_raw": missing,
                               "independence": "external", "provenance": provenance,
                               "democratic": None, "republican": None, "other": None,
                               "unresolved": None, "unavailable": missing})
    return totals, district_refs, files


def warehouse_reference_totals(data: dict[str, pd.DataFrame], districts: pd.DataFrame,
                               cycles: tuple[int, ...], sizes: dict[str, int]) -> list[dict]:
    """Per-family plurality winners aggregated by party, as secondary comparisons."""
    obs = data["observations"].copy()
    obs["chamber_key"] = obs["chamber"].map(FROM_WAREHOUSE_CHAMBER)
    selected_from = districts.groupby(["cycle", "chamber", "source_family"]).size()
    out = []
    for (cycle, chamber, family), group in obs.groupby(["cycle", "chamber_key", "source_family"]):
        if cycle not in cycles or chamber not in sizes:
            continue
        counts = {"democratic": 0, "republican": 0, "other": 0}
        undetermined = 0
        for _, contest in group.groupby("district"):
            party, _ = plurality(candidate_rows(contest, name="candidate_name",
                                                writein_col="writein_status"))
            if party is None:
                undetermined += 1
            else:
                counts[party] += 1
        missing = sizes[chamber] - group["district"].nunique()
        dependent = int(selected_from.get((cycle, chamber, family), 0))
        independence = "warehouse_secondary_independent_of_selected_rows" if dependent == 0 \
            else f"warehouse_secondary_partially_dependent:{dependent}_districts_selected_from_it"
        if family == "alabama_sos_certified_canvass":
            independence = "warehouse_official_certified:canonical_votes_bridged_to_it"
        files = ";".join(sorted(group["source_file_id"].dropna().unique()))
        out.append({
            "cycle": cycle, "chamber": chamber,
            "reference_kind": f"warehouse_observation_{family}",
            "reference_path": f"warehouse:source_southern_legislative_observation_set "
                              f"source_family={family}",
            "reference_sha256": "", "reference_registration": f"warehouse_source_file {files}",
            "reference_field": "plurality winner per district (write-in aggregates excluded)",
            "reference_raw": f"contests={group['district'].nunique()}; "
                             f"undetermined={undetermined}; missing={missing}",
            "independence": independence, "provenance": "",
            **counts, "unresolved": undetermined + missing,
        })
    return out


def supported_reference_conflicts(districts: pd.DataFrame, reference_districts: dict,
                                  page_totals: list[dict]) -> frozenset:
    """Districts whose reference-table contradiction is backed by an external seat total.

    A contradiction (warehouse party A, reference party B) is backed when some
    external page total for the same cycle and chamber has fewer A seats and more
    B seats than the warehouse-only count. Both pieces of reference evidence must
    point the same way before a warehouse winner is withheld.
    """
    counts: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in districts.itertuples(index=False):
        counts[(row.cycle, row.chamber)][row.winner_party] += 1
    backed = set()
    for row in districts.itertuples(index=False):
        if row.winner_status != "observed" or not row.reference_check.startswith("conflict"):
            continue
        key = (row.cycle, row.chamber, str(row.district))
        ref_parties = {r["winner_bucket"] for r in reference_districts.get(key, [])
                       if r["winner_bucket"]} - {row.winner_party}
        ours = counts[(row.cycle, row.chamber)]
        for total in page_totals:
            if (total["cycle"], total["chamber"]) != (row.cycle, row.chamber) or \
                    total.get("independence") != "external" or total.get("unavailable"):
                continue
            over = ours[row.winner_party] - (total.get(row.winner_party) or 0)
            if over > 0 and any((total.get(p) or 0) - ours[p] > 0 for p in ref_parties):
                backed.add(key)
    return frozenset(backed)


def reconcile(ours: dict[str, int], ref: dict, size: int) -> tuple[str, dict, str]:
    """Compare our counts with a reference total; return status, deltas and a note."""
    if ref.get("unavailable"):
        return "reference_unavailable", {}, ref["unavailable"]
    reported = {p: ref.get(p) for p in PARTIES if ref.get(p) is not None}
    unresolved = int(ref.get("unresolved") or 0)
    implied = size - sum(reported.values()) - unresolved
    note = ""
    if implied != 0:
        note = f"reference parties plus unresolved sum to {size - implied}, not {size}"
    deltas = {p: ours.get(p, 0) - v for p, v in reported.items()}
    unknown = ours.get("unknown", 0)
    if implied == 0 and unknown == 0 and unresolved == 0 and all(d == 0 for d in deltas.values()):
        return "match", deltas, note
    need_ours = sum(max(0, -d) for d in deltas.values())  # reference seats we hold as unknown
    need_ref = sum(max(0, d) for d in deltas.values())     # our seats the reference leaves open
    if implied == 0 and need_ours <= unknown and need_ref <= unresolved and (
            unknown > 0 or unresolved > 0):
        return "consistent_with_unknowns", deltas, (note + "; " if note else "") + \
            "reference totals are reachable only by resolving unknown/undetermined seats"
    if implied != 0:
        return "mismatch_incomplete_reference", deltas, note
    return "mismatch", deltas, note


def build_reconciliation(seats: pd.DataFrame, references: list[dict],
                         sizes: dict[str, int]) -> pd.DataFrame:
    counts = seat_counts(seats)
    rows = []
    for ref in references:
        key = (ref["cycle"], ref["chamber"])
        if key not in counts:
            continue
        ours = counts[key]
        status, deltas, note = reconcile(ours, ref, sizes[ref["chamber"]])
        rows.append({
            "cycle": ref["cycle"], "chamber": ref["chamber"],
            "reference_kind": ref["reference_kind"], "reference_path": ref["reference_path"],
            "reference_sha256": ref["reference_sha256"],
            "reference_registration": ref["reference_registration"],
            "reference_provenance": ref.get("provenance", ""),
            "reference_field": ref["reference_field"], "reference_raw": ref["reference_raw"],
            "independence": ref["independence"],
            "ref_democratic": ref.get("democratic"), "ref_republican": ref.get("republican"),
            "ref_other": ref.get("other"), "ref_unresolved": ref.get("unresolved"),
            "ours_democratic": ours.get("democratic", 0),
            "ours_republican": ours.get("republican", 0),
            "ours_other": ours.get("other", 0), "ours_unknown": ours.get("unknown", 0),
            "delta_democratic": deltas.get("democratic"),
            "delta_republican": deltas.get("republican"),
            "delta_other": deltas.get("other"),
            "status": status, "note": note,
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for col in ("ref_democratic", "ref_republican", "ref_other", "ref_unresolved",
                "delta_democratic", "delta_republican", "delta_other"):
        frame[col] = frame[col].astype("Int64")
    return frame.sort_values(["cycle", "chamber", "reference_kind", "reference_path"],
                             kind="mergesort").reset_index(drop=True)


def total_review_items(recon: pd.DataFrame, districts: pd.DataFrame,
                       cycles: tuple[int, ...], sizes: dict[str, int]) -> list[dict]:
    items = []
    for cycle in cycles:
        for chamber in sizes:
            part = recon[(recon.cycle == cycle) & (recon.chamber == chamber)] \
                if not recon.empty else recon
            summary = "; ".join(f"{r.reference_kind} [{r.reference_path}]: {r.status}"
                                for r in part.itertuples(index=False)) or "none"
            group = districts[(districts.cycle == cycle) & (districts.chamber == chamber)]
            for row in part.itertuples(index=False):
                # District-table aggregates are itemized district by district instead.
                if row.status.startswith("mismatch") and \
                        row.independence != "external_district_aggregate":
                    items.append(review_item(
                        cycle, chamber, "TOTAL", "total", f"reference_total_{row.status}",
                        "blocking", recorded=_counts_text(group),
                        conflicting=f"{row.reference_kind}: {row.reference_raw}",
                        evidence=f"Deltas (ours-reference) D={row.delta_democratic} "
                                 f"R={row.delta_republican} other={row.delta_other}. "
                                 f"{row.note} All comparisons for this total: "
                                 f"{summary}".replace("  ", " ").strip(),
                        sources=row.reference_path))
                    items[-1]["review_id"] += \
                        f"-{reference_slug(row.reference_kind, row.reference_path)}"
            matches = part[part.status == "match"] if not part.empty else part
            external_match = (not matches.empty) and (matches.independence == "external").any()
            secondary_match = (not matches.empty) and (
                matches.independence == "warehouse_secondary_independent_of_selected_rows").any()
            if not (external_match or secondary_match):
                items.append(review_item(
                    cycle, chamber, "TOTAL", "total",
                    "total_not_reconciled_with_independent_reference", "blocking",
                    recorded=_counts_text(group),
                    evidence="No independent reference reconciles exactly with this total "
                             "(unknown districts must be resolved first, or no reference "
                             f"exists). Comparisons: {summary}",
                    sources=";".join(sorted(set(part.reference_path))) if not part.empty
                    else ""))
            elif not external_match:
                items.append(review_item(
                    cycle, chamber, "TOTAL", "total", "no_external_page_reference", "info",
                    recorded=_counts_text(group),
                    evidence="The total matches a warehouse secondary source that is "
                             "independent of the selected rows (Klarner), but no saved external "
                             f"page reports seat totals for this cycle. Comparisons: {summary}",
                    sources=";".join(sorted(set(part.reference_path)))))
            group = districts[(districts.cycle == cycle) & (districts.chamber == chamber)]
            single = group[group.corroboration == "single_source"]
            if len(single):
                items.append(review_item(
                    cycle, chamber, "TOTAL", "total", "winners_resting_on_one_source", "info",
                    recorded=f"{len(single)} districts: " + ",".join(
                        str(d) for d in sorted(single.district)),
                    evidence="These observed winners come from one warehouse observation with no "
                             "second warehouse source or district-level reference to "
                             "corroborate the winner's party. Families: " + ", ".join(
                                 f"{k}={v}" for k, v in
                                 single.source_family.value_counts().sort_index().items())))
    return items


def reference_slug(kind: str, path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", f"{kind}_{Path(path).stem}")[:80].strip("_")


def _counts_text(group: pd.DataFrame) -> str:
    counts = group.winner_party.value_counts()
    return " ".join(f"{p}={int(counts.get(p, 0))}" for p in SEAT_PARTIES)


def structural_review_items(data: dict[str, pd.DataFrame]) -> list[dict]:
    """Informational upstream grain issues: several sets for one contest in the
    materialized canonical table (expected cardinality 1). They do not change the
    selected set, whose winner is cross-checked against the other sets."""
    items = []
    sel = data["selected"]
    dup = data.get("canonical_set_counts")
    if dup is None:
        return items
    for row in dup.itertuples(index=False):
        chosen = sel[(sel.cycle == row.cycle) & (sel.chamber == row.chamber)
                     & (sel.district == str(row.district))].observation_set_id.unique()
        items.append(review_item(
            row.cycle, FROM_WAREHOUSE_CHAMBER[row.chamber], row.district, "contest_structure",
            "multiple_observation_sets_in_materialized_canonical_table", "info",
            recorded=f"sets: {row.sets}",
            evidence=f"canonical_southern_legislative_candidate_election holds {row.n} "
                     f"observation sets for this contest; the final-stage view selected "
                     f"{';'.join(chosen)} by its date/observation_set_id ordering. The other "
                     "set's winner party was compared in the cross-source check.",
            sources="project_docs/audits/ALABAMA_2002_MARSHALL_CANONICAL_REVIEW_2026_09_11.md"
            if row.cycle == 2002 else ""))
    return items


def canonical_set_counts(con: sqlite3.Connection, cycles: tuple[int, ...]) -> pd.DataFrame:
    marks = ",".join("?" for _ in cycles)
    return pd.read_sql_query(
        f"""SELECT cycle, chamber, district, COUNT(DISTINCT observation_set_id) AS n,
                   GROUP_CONCAT(DISTINCT observation_set_id || ':' || source_family) AS sets
            FROM canonical_southern_legislative_candidate_election
            WHERE state_code='AL' AND cycle IN ({marks}) AND election_stage=?
            GROUP BY cycle, chamber, district HAVING COUNT(DISTINCT observation_set_id) > 1
            ORDER BY cycle, chamber, CAST(district AS INTEGER)""",
        con, params=[*cycles, REGULAR_STAGE])


# ------------------------------------------------------------------------ build

def build(warehouse: Path = WAREHOUSE, raw: Path = RAW, out: Path = OUT,
          cycles: tuple[int, ...] = CYCLES, sizes: dict[str, int] | None = None,
          hash_warehouse: bool = True) -> dict:
    sizes = dict(sizes or CHAMBER_SIZES)
    con = connect_readonly(warehouse)
    try:
        data = load_warehouse(con, cycles)
        data["canonical_set_counts"] = canonical_set_counts(con, cycles)
        meta = warehouse_metadata(con, data["selected"])
    finally:
        con.close()

    ref_totals, ref_districts, ref_files = load_references(raw, cycles, sizes)
    # Pass 1: warehouse evidence only; pass 2 withholds the districts whose reference
    # contradiction is backed by an external seat total.
    first_pass, _ = determine_districts(data, cycles, sizes, ref_districts)
    backed = supported_reference_conflicts(first_pass, ref_districts, ref_totals)
    districts, review = determine_districts(data, cycles, sizes, ref_districts, backed)
    seats = summarize_seats(districts, sizes)
    references = ref_totals + warehouse_reference_totals(data, districts, cycles, sizes)
    recon = build_reconciliation(seats, references, sizes)
    review += total_review_items(recon, districts, cycles, sizes)
    review += structural_review_items(data)
    review_frame = order_review(pd.DataFrame(review, columns=list(REVIEW_COLUMNS)))
    if review_frame.review_id.duplicated().any():
        raise ValueError("duplicate review_id")

    districts = districts.sort_values(["cycle", "chamber", "district"]).reset_index(drop=True)
    districts["winner_votes"] = districts["winner_votes"].astype("Int64")
    validate_outputs(districts, seats, cycles, sizes)

    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "district_winners.csv": districts, "seats_by_cycle.csv": seats,
        "reconciliation.csv": recon, "review_queue.csv": review_frame,
    }
    output_hashes = {}
    for name, frame in paths.items():
        write_csv(frame, out / name)
        output_hashes[name] = sha256_file(out / name)
    run_id = "AL-SEATS-V1-" + sha256_bytes(
        json.dumps(output_hashes, sort_keys=True).encode()).upper()[:20]

    script = Path(__file__).resolve()
    manifest = {
        "product": PRODUCT, "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "local build for review; not published",
        "definition": DEFINITION,
        "excluded_from_definition": list(EXCLUSIONS),
        "code": {
            "git_head": git_value("rev-parse", "HEAD"),
            "script": rel(script), "script_sha256": sha256_file(script),
            "script_git_status": git_value("status", "--porcelain", "--", rel(script)) or "clean",
            "command": "python scripts/build_alabama_seats_by_cycle.py",
        },
        "warehouse": {
            "path": rel(warehouse),
            "bytes": warehouse.stat().st_size,
            "mtime_utc": datetime.fromtimestamp(warehouse.stat().st_mtime, timezone.utc)
            .isoformat(timespec="seconds"),
            "sha256": sha256_file(warehouse) if hash_warehouse else None,
            "sha256_note": "whole-file hash" if hash_warehouse else "skipped by --skip-warehouse-hash",
            "connection": "sqlite3 URI mode=ro with PRAGMA query_only=ON; no writes",
            **meta,
            "consumed_content_sha256": {
                name: frame_digest(data[name]) for name in
                ("selected", "canonical", "observations", "bridge")},
            "objects_read": [SELECTED_TABLE, "canonical_candidates",
                             "source_southern_legislative_observation_set",
                             "source_southern_legislative_candidate_result",
                             "bridge_alabama_canonical_candidate_certified_result",
                             "canonical_southern_legislative_candidate_election",
                             "warehouse_build_run", "warehouse_schema_version"],
            "alabama_legislative_sets_by_stage_in_cycle_span": data["stages"].to_dict("records"),
        },
        "scope": {"state": "AL", "cycles": list(cycles), "chamber_sizes": sizes,
                  "plan_rule": "Each cycle's districts are those reported for that cycle "
                               "(warehouse district_plan_id carried per row); districts are "
                               "never relabelled across plans."},
        "rules": {
            "selection": f"{SELECTED_TABLE}: one regular general-election observation set per "
                         "cycle/chamber/district (Alabama canonical first; Klarner only where "
                         "the canonical record omits the contest).",
            "winner": "Recorded winner flag of the selected set (canonical_candidates.winner or "
                      "Klarner winner_status); it must be unique and equal the plurality of the "
                      "set's named candidates when all votes are present.",
            "cross_check": "Every other general-election warehouse observation of the same "
                           "contest (Klarner, certified SOS canvass, MEDSL) is reduced to its "
                           "plurality winner's party; any disagreement makes the district "
                           "unknown.",
            "reference_check": "Saved Wikipedia district result tables (2010-2022) are compared "
                               "by winner party only. A contradiction makes the district "
                               "unknown only when an external seat total (Wikipedia infobox or "
                               "Ballotpedia) for the same cycle and chamber is off from the "
                               "warehouse-only count in the same direction; otherwise it is "
                               "queued as a non-blocking item. References never supply or "
                               "change a winner.",
            "contest_status": "contested = two or more named ballot candidates in any "
                              "observation; uncontested = exactly one named candidate in every "
                              "full-ballot observation (write-in aggregates are not "
                              "opponents); otherwise unknown. A D/R-only canonical set never "
                              "establishes uncontested on its own, and a reference-backed "
                              "winner conflict turns 'uncontested' into unknown.",
            "party_buckets": "democratic, republican, other (independent and minor parties), "
                             "unknown (winner_status unknown).",
            "reconciliation_status": {
                "match": "all reported party counts equal ours and neither side has unknowns",
                "consistent_with_unknowns": "differences are fully explained by our unknown "
                                            "or the reference's undetermined seats",
                "mismatch": "reported counts cannot be reached by resolving unknowns",
                "mismatch_incomplete_reference": "reference does not account for every seat "
                                                 "and its reported counts differ",
                "reference_unavailable": "saved page has no seat totals for this cycle",
            },
        },
        "inputs": {"reference_files": [
            {k: v for k, v in f.items()} for f in
            sorted(ref_files, key=lambda f: f["reference_path"])]},
        "row_counts": {
            "district_winners": len(districts), "seats_by_cycle": len(seats),
            "reconciliation": len(recon), "review_queue": len(review_frame),
            "review_blocking": int((review_frame.severity == "blocking").sum()),
            "selected_candidate_rows": len(data["selected"]),
            "canonical_candidate_rows": len(data["canonical"]),
            "warehouse_observation_rows": len(data["observations"]),
        },
        "summary": summary_table(seats),
        "district_status_counts": {
            "winner_status": districts.winner_status.value_counts().sort_index().to_dict(),
            "contest_status": districts.contest_status.value_counts().sort_index().to_dict(),
            "corroboration": districts.corroboration.value_counts().sort_index().to_dict(),
            "selected_source_family": districts.source_family.value_counts().sort_index()
            .to_dict(),
        },
        "outputs": output_hashes,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n",
                                       encoding="utf-8")
    return manifest


def order_review(frame: pd.DataFrame) -> pd.DataFrame:
    order = frame.assign(
        _scope=frame.scope.map(SCOPE_ORDER).fillna(9),
        _district=pd.to_numeric(frame.district, errors="coerce").fillna(-1))
    return order.sort_values(["cycle", "chamber", "_scope", "_district", "review_id"],
                             kind="mergesort").drop(columns=["_scope", "_district"]) \
        .reset_index(drop=True)


def summary_table(seats: pd.DataFrame) -> list[dict]:
    wide = seats.pivot_table(index=["cycle", "chamber"], columns="party", values="seats",
                             aggfunc="sum").reset_index()
    return [{"cycle": int(r["cycle"]), "chamber": r["chamber"],
             **{p: int(r.get(p, 0)) for p in SEAT_PARTIES}}
            for r in wide.to_dict("records")]


def validate_outputs(districts: pd.DataFrame, seats: pd.DataFrame,
                     cycles: tuple[int, ...], sizes: dict[str, int]) -> None:
    key = ["cycle", "chamber", "district"]
    if districts.duplicated(key).any():
        raise ValueError("cycle-chamber-district key is not unique")
    expected = {(c, ch, d) for c in cycles for ch, n in sizes.items() for d in range(1, n + 1)}
    actual = set(map(tuple, districts[key].itertuples(index=False, name=None)))
    if actual != expected:
        raise ValueError("district grid does not match the expected chambers")
    observed = districts.winner_status == "observed"
    if (districts.loc[~observed, "winner_party"] != "unknown").any():
        raise ValueError("an unknown district carries a counted party")
    if not set(districts.winner_status) <= {"observed", "unknown"}:
        raise ValueError("unexpected winner_status")
    if seats.groupby(["cycle", "chamber"]).seats.sum().ne(
            seats.groupby(["cycle", "chamber"]).chamber_size.first()).any():
        raise ValueError("seat totals do not equal chamber size")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE)
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--skip-warehouse-hash", action="store_true",
                        help="do not hash the whole warehouse file (content digests are kept)")
    args = parser.parse_args(argv)
    manifest = build(args.warehouse, args.raw, args.output,
                     hash_warehouse=not args.skip_warehouse_hash)
    print(f"{manifest['run_id']} -> {rel(args.output)}")
    for row in manifest["summary"]:
        print(f"  {row['cycle']} {row['chamber']:<6} D={row['democratic']:>3} "
              f"R={row['republican']:>3} other={row['other']:>2} unknown={row['unknown']:>2}")
    print(f"  review items: {manifest['row_counts']['review_queue']} "
          f"({manifest['row_counts']['review_blocking']} blocking)")


if __name__ == "__main__":
    main()
