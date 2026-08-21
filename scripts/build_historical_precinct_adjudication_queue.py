"""Build an evidence-rich, activity-ranked queue for unresolved precinct geography."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

from audit_historical_precinct_geography import county_match_key, normalize_split_base
from warehouse import ROOT

PROCESSED = ROOT / "data/processed/precinct_history"
DB = ROOT / "data/processed/elections/alabama_elections.sqlite"
REVIEW = PROCESSED / "historical_precinct_geometry_review_queue.csv"
AUDIT = PROCESSED / "historical_precinct_geometry_audit.csv"
EDGES = PROCESSED / "adjacent_cycle_precinct_alias_edges.csv"
GEOCODE_CACHE = PROCESSED / "historical_precinct_geocode_cache.json"
DOJ = PROCESSED / "doj_precinct_candidate_submissions.csv"
OUT = PROCESSED / "historical_precinct_adjudication_queue.csv"
TOP = PROCESSED / "historical_precinct_adjudication_top200.csv"


def case_id(cycle: int, county: str, precinct: str) -> str:
    value = f"{int(cycle)}|{county_match_key(county)}|{precinct}".encode("utf-8")
    return "PCT-" + hashlib.sha256(value).hexdigest()[:12].upper()


def beat_box_signature(value: object) -> str:
    text = re.sub(r"[,/]", " ", str(value).upper())
    match = re.search(r"(?:\bBEAT\s*)?0*(\d+)\s+BOX\s*0*(\d+)\b", text)
    return f"BEAT-{int(match.group(1))}-BOX-{int(match.group(2))}" if match else ""


def activity() -> pd.DataFrame:
    query = """
      WITH contests AS (
        SELECT year AS cycle, county_key, precinct_key, office,
               COALESCE(CAST(district AS INTEGER), -1) AS district,
               SUM(votes) AS contest_votes
        FROM vote_observations
        WHERE source='alabama_sos' AND year IN (1994,1998,2002,2006)
        GROUP BY year,county_key,precinct_key,office,COALESCE(CAST(district AS INTEGER), -1)
      )
      SELECT cycle,county_key,precinct_key,
             MAX(contest_votes) AS turnout_proxy,
             MAX(CASE WHEN office IN ('State House','State Senate') THEN contest_votes END)
               AS legislative_activity_proxy,
             COUNT(*) AS observed_contests
      FROM contests GROUP BY cycle,county_key,precinct_key
    """
    with sqlite3.connect(DB) as connection:
        return pd.read_sql_query(query, connection)


def alias_evidence(queue: pd.DataFrame) -> pd.DataFrame:
    edges = pd.read_csv(EDGES)
    records: dict[tuple[int, str, str], list[str]] = {}
    for row in edges.itertuples(index=False):
        old_key = (int(row.old_year), county_match_key(row.county_key), row.old_precinct)
        new_key = (int(row.new_year), county_match_key(row.county_key), row.new_precinct)
        records.setdefault(old_key, []).append(
            f"{row.new_year}:{row.new_precinct} score={float(row.composite_score):.1f} "
            f"conf={row.confidence} rel={row.relationship}")
        records.setdefault(new_key, []).append(
            f"{row.old_year}:{row.old_precinct} score={float(row.composite_score):.1f} "
            f"conf={row.confidence} rel={row.relationship}")
    return pd.DataFrame([{
        "cycle": int(row.cycle), "county_key": row.county_key, "precinct_key": row.precinct_key,
        "alias_evidence": " || ".join(sorted(records.get(
            (int(row.cycle), county_match_key(row.county_key), row.precinct_key), []),
            key=lambda item: float(item.split("score=")[1].split()[0]), reverse=True)[:5])
    } for row in queue.itertuples(index=False)])


def adjacent_name_evidence(queue: pd.DataFrame) -> pd.DataFrame:
    """Retain useful below-threshold neighboring-cycle names for human review."""
    audit = pd.read_csv(AUDIT).fillna("")
    pools = {county_match_key(key): frame for key, frame in audit.groupby("county_key")}
    rows = []
    for row in queue.itertuples(index=False):
        pool = pools.get(county_match_key(row.county_key), pd.DataFrame())
        candidates = []
        row_signature = beat_box_signature(row.precinct_key)
        if not pool.empty:
            pool = pool[pool.cycle.ne(int(row.cycle))]
            for candidate in pool.itertuples(index=False):
                delta = abs(int(candidate.cycle) - int(row.cycle))
                if delta not in {4, 8}:
                    continue
                exact_base = normalize_split_base(candidate.precinct_key) == normalize_split_base(row.precinct_key)
                exact_signature = bool(row_signature and beat_box_signature(candidate.precinct_key) == row_signature)
                score = float(fuzz.WRatio(str(row.precinct_key), str(candidate.precinct_key)))
                if exact_base or exact_signature or score >= 65:
                    candidates.append((exact_signature, exact_base, score, candidate))
        candidates.sort(key=lambda value: (value[0], value[1], value[2]), reverse=True)
        evidence = []
        seen = set()
        for exact_signature, exact_base, score, candidate in candidates:
            identity = (int(candidate.cycle), candidate.precinct_key)
            if identity in seen: continue
            seen.add(identity)
            evidence.append(f"{candidate.cycle}:{candidate.precinct_key} score={score:.1f} "
                            f"code_exact={int(exact_signature)} base_exact={int(exact_base)} "
                            f"donor={candidate.donor_vtd_id or '[unresolved]'}")
            if len(evidence) == 5: break
        rows.append({"cycle": int(row.cycle), "county_key": row.county_key,
                     "precinct_key": row.precinct_key,
                     "adjacent_name_evidence": " || ".join(evidence)})
    return pd.DataFrame(rows)


def geocoder_evidence(queue: pd.DataFrame) -> pd.DataFrame:
    cache = json.loads(GEOCODE_CACHE.read_text(encoding="utf-8")) if GEOCODE_CACHE.exists() else {}
    rows = []
    for row in queue.itertuples(index=False):
        key = f"{county_match_key(row.county_key)}|{normalize_split_base(row.precinct_key)}"
        entry = cache.get(key, {})
        candidates = []
        for candidate in entry.get("candidates", [])[:3]:
            attributes = candidate.get("attributes", {})
            candidates.append(
                f"{candidate.get('address','')} score={candidate.get('score','')} "
                f"type={attributes.get('Addr_type','')} county={attributes.get('Subregion','')} "
                f"lon={candidate.get('location',{}).get('x','')} lat={candidate.get('location',{}).get('y','')}")
        rows.append({"cycle": int(row.cycle), "county_key": row.county_key,
                     "precinct_key": row.precinct_key, "geocoder_query": entry.get("query", ""),
                     "geocoder_evidence": " || ".join(candidates)})
    return pd.DataFrame(rows)


def doj_evidence(queue: pd.DataFrame) -> pd.DataFrame:
    doj = pd.read_csv(DOJ, dtype={"submission_number": str}) if DOJ.exists() else pd.DataFrame()
    lookup = doj.set_index("submission_number").to_dict("index") if not doj.empty else {}
    rows = []
    for row in queue.itertuples(index=False):
        evidence = []
        for number in str(row.intervening_submission_numbers or "").split("|"):
            if not number or number == "nan" or number not in lookup:
                continue
            source = lookup[number]
            evidence.append(f"{number}: {source.get('descriptions','')} [{source.get('activities','')}]")
        rows.append({"cycle": int(row.cycle), "county_key": row.county_key,
                     "precinct_key": row.precinct_key, "doj_evidence": " || ".join(evidence)})
    return pd.DataFrame(rows)


def build() -> pd.DataFrame:
    queue = pd.read_csv(REVIEW).fillna("")
    keys = ["cycle", "county_key", "precinct_key"]
    result = queue.merge(activity(), on=keys, how="left", validate="one_to_one")
    result = result.merge(alias_evidence(queue), on=keys, validate="one_to_one")
    result = result.merge(adjacent_name_evidence(queue), on=keys, validate="one_to_one")
    result = result.merge(geocoder_evidence(queue), on=keys, validate="one_to_one")
    result = result.merge(doj_evidence(queue), on=keys, validate="one_to_one")
    for column in ("turnout_proxy", "legislative_activity_proxy", "observed_contests"):
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)
    result["case_id"] = [case_id(*values) for values in result[keys].itertuples(index=False, name=None)]
    administrative = result.precinct_key.astype(str).str.contains(
        r"^(?:CALCULATED|REPORTED)$|\bCALCULATED(?: NUMBER OF)?\s+VOTES\b|\bCOUNTY REPORTING TOTAL\b|\bGRAND TOTAL\b",
        case=False, regex=True)
    result["administrative_likelihood"] = administrative.map({True: "high", False: "none"})
    result["physical_adjudication_candidate"] = ~administrative
    result["priority_activity"] = result.legislative_activity_proxy.where(
        result.legislative_activity_proxy.gt(0), result.turnout_proxy)
    result = result.sort_values(
        ["physical_adjudication_candidate", "priority_activity", "turnout_proxy", "cycle", "county_key", "precinct_key"],
        ascending=[False, False, False, True, True, True]).reset_index(drop=True)
    result.insert(0, "priority_rank", result.physical_adjudication_candidate.cumsum())
    result.loc[~result.physical_adjudication_candidate, "priority_rank"] = 0
    result.insert(1, "top_200", result.physical_adjudication_candidate & result.priority_rank.le(200))
    lead = ["priority_rank", "top_200", "case_id", "cycle", "county_key", "precinct_key",
            "priority_activity", "legislative_activity_proxy", "turnout_proxy", "observed_contests",
            "physical_adjudication_candidate", "administrative_likelihood",
            "known_race_assignments", "is_split_precinct", "house_district_count",
            "senate_district_count", "suggested_donor_vtd_id", "suggested_donor_name",
            "name_match_score", "name_match_margin", "alias_evidence", "adjacent_name_evidence", "geocoder_query",
            "geocoder_evidence", "intervening_submission_numbers", "doj_evidence"]
    result = result[lead + [column for column in result if column not in lead]]
    return result


def main() -> None:
    result = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    top = result[result.physical_adjudication_candidate].head(200)
    top.to_csv(TOP, index=False)
    print(f"Wrote {len(result):,} cases to {OUT}")
    eligible = result[result.physical_adjudication_candidate]
    print(f"Top 200 represent {top.priority_activity.sum()/eligible.priority_activity.sum():.1%} "
          "of unresolved physical-precinct legislative activity")


if __name__ == "__main__":
    main()
