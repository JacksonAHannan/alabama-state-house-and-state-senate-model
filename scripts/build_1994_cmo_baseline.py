"""Build an auditable 1994 CMO baseline from official Alabama SOS returns.

The official precinct workbook identifies the legislative district(s) appearing
on each precinct ballot. A precinct with one district receives weight 1. Split
precincts have no independent subprecinct geography in the source collection,
so statewide votes are provisionally divided in proportion to legislative
ballot activity. Those two methods are deliberately kept distinct.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_source_file, register_table

CYCLE = 1994
CORE = ("Governor", "Attorney General")
PARTY_CORRECTIONS = {
    # The 1994 SOS workbook/parser repeats the Democratic party label for both
    # attorney-general candidates. Jeff Sessions was the Republican nominee.
    ("Attorney General", "EVANS"): "D",
    ("Attorney General", "SESSIONS"): "R",
}
ELECTION_DB = ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite"
OUT = ROOT / "data" / "processed" / "elections"
SCHEMA = Path(__file__).with_name("warehouse_historical_baseline_schema.sql")
PLAN_FILES = {
    "house": ROOT / "data" / "raw" / "alabama_elections_and_geography" / "al_lower_1992_2000" / "al_lower_1992_2000.shp",
    "senate": ROOT / "data" / "raw" / "alabama_elections_and_geography" / "al_upper_1992_2000" / "al_upper_1992_2000.shp",
}


def load_returns() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with sqlite3.connect(ELECTION_DB) as connection:
        legislative = pd.read_sql_query(
            """SELECT county_key,precinct_key,office,district,votes
               FROM vote_observations
               WHERE source='alabama_sos' AND year=?
                 AND office IN ('State House','State Senate') AND district IS NOT NULL""",
            connection, params=(CYCLE,))
        statewide = pd.read_sql_query(
            """SELECT county_key,precinct_key,office,candidate_key,party_norm,votes
               FROM vote_observations
               WHERE source='alabama_sos' AND year=? AND office IN (?,?)
                 AND party_norm IN ('D','R')""",
            connection, params=(CYCLE, *CORE))
        candidates = pd.read_sql_query(
            """SELECT chamber,district,canonical_party,SUM(canonical_votes) AS votes
               FROM canonical_candidates
               WHERE year=? AND canonical_party IN ('D','R')
               GROUP BY chamber,district,canonical_party""",
            connection, params=(CYCLE,))
    corrected = [PARTY_CORRECTIONS.get((row.office, row.candidate_key), row.party_norm)
                 for row in statewide.itertuples(index=False)]
    statewide["party_norm"] = corrected
    statewide = statewide[statewide.party_norm.isin(["D", "R"])].copy()
    return legislative, statewide, candidates


def build_weights(legislative: pd.DataFrame) -> pd.DataFrame:
    data = legislative.copy()
    data["chamber"] = data.office.map({"State House": "house", "State Senate": "senate"})
    data["district"] = pd.to_numeric(data.district, errors="raise").astype(int)
    activity = (data.groupby(["chamber", "county_key", "precinct_key", "district"], as_index=False).votes.sum()
                .rename(columns={"votes": "district_activity"}))
    activity["precinct_activity"] = activity.groupby(
        ["chamber", "county_key", "precinct_key"])["district_activity"].transform("sum")
    activity = activity[activity.precinct_activity.gt(0)].copy()
    activity["allocation_weight"] = activity.district_activity / activity.precinct_activity
    activity["district_count"] = activity.groupby(
        ["chamber", "county_key", "precinct_key"])["district"].transform("size")
    activity["allocation_method"] = np.where(
        activity.district_count.eq(1), "official_ballot_single_district",
        "legislative_activity_split_provisional")
    activity.insert(0, "cycle", CYCLE)
    return activity


def allocate(statewide: pd.DataFrame, weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pieces, qa, unmatched = [], [], []
    for chamber in ("house", "senate"):
        chamber_weights = weights[weights.chamber.eq(chamber)]
        merged = statewide.merge(chamber_weights, on=["county_key", "precinct_key"], how="left", indicator=True)
        missing = merged[merged._merge.eq("left_only")].copy()
        if not missing.empty:
            missing["chamber"] = chamber
            unmatched.append(missing[["county_key", "precinct_key", "office", "party_norm", "votes", "chamber"]])
        matched = merged[merged._merge.eq("both")].copy()
        matched["allocated_votes"] = matched.votes * matched.allocation_weight
        matched["chamber"] = chamber
        pieces.append(matched)
        source_totals = statewide.groupby(["office", "party_norm"], as_index=False).votes.sum()
        allocated_totals = matched.groupby(["office", "party_norm"], as_index=False).allocated_votes.sum()
        audit = source_totals.merge(allocated_totals, on=["office", "party_norm"], how="left").fillna({"allocated_votes": 0})
        audit["unmatched_votes"] = audit.votes - audit.allocated_votes
        audit["allocation_coverage"] = audit.allocated_votes / audit.votes.where(audit.votes.gt(0))
        audit.insert(0, "chamber", chamber); audit.insert(0, "cycle", CYCLE)
        audit = audit.rename(columns={"party_norm": "party", "votes": "source_votes"})
        qa.append(audit)
    return pd.concat(pieces, ignore_index=True), pd.concat(qa, ignore_index=True), pd.concat(unmatched, ignore_index=True)


def build_features(candidates: pd.DataFrame, allocated: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    office = (allocated.groupby(["chamber", "district", "office", "party_norm"], as_index=False).allocated_votes.sum()
              .pivot(index=["chamber", "district", "office"], columns="party_norm", values="allocated_votes")
              .fillna(0).reset_index().rename(columns={"D": "dem_votes", "R": "rep_votes"}))
    for column in ("dem_votes", "rep_votes"):
        if column not in office: office[column] = 0.0
    office["two_party_votes"] = office.dem_votes + office.rep_votes
    office["office_dem_margin"] = 100 * (office.dem_votes-office.rep_votes) / office.two_party_votes.where(office.two_party_votes.gt(0))
    methods = (allocated.groupby(["chamber", "district", "office"]).allocation_method
               .agg(lambda values: "legislative_activity_split_provisional" if
                    (values == "legislative_activity_split_provisional").any() else "official_ballot_single_district")
               .reset_index(name="baseline_allocation_method"))
    office = office.merge(methods, on=["chamber", "district", "office"], validate="one_to_one")
    office.insert(0, "cycle", CYCLE)

    races = (candidates.pivot(index=["chamber", "district"], columns="canonical_party", values="votes")
             .fillna(0).reset_index().rename(columns={"D": "dem_votes", "R": "rep_votes"}))
    for column in ("dem_votes", "rep_votes"):
        if column not in races: races[column] = 0.0
    races["two_party_votes"] = races.dem_votes + races.rep_votes
    races["legislative_dem_margin"] = 100 * (races.dem_votes-races.rep_votes) / races.two_party_votes.where(races.two_party_votes.gt(0))
    baseline = (office.groupby(["chamber", "district"], as_index=False)
                .agg(core_index_margin=("office_dem_margin", "mean"), core_index_offices=("office", "nunique"),
                     baseline_allocation_method=("baseline_allocation_method", lambda values:
                       "legislative_activity_split_provisional" if
                       (values == "legislative_activity_split_provisional").any() else "official_ballot_single_district")))
    races = races.merge(baseline, on=["chamber", "district"], how="left", validate="one_to_one")
    races["core_index_complete"] = races.core_index_offices.eq(len(CORE))
    races["contested_two_party"] = races.dem_votes.gt(0) & races.rep_votes.gt(0)
    races["raw_overperformance"] = races.legislative_dem_margin - races.core_index_margin
    races["score_status"] = "provisional_raw_baseline_not_fitted_cmo"
    races.insert(0, "cycle", CYCLE)
    return office, races


def main() -> None:
    legislative, statewide, candidates = load_returns()
    weights = build_weights(legislative)
    allocated, qa, unmatched = allocate(statewide, weights)
    office, races = build_features(candidates, allocated)
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "1994_precinct_district_ballot_weights.csv": weights,
        "1994_district_baseline_office.csv": office,
        "1994_cmo_race_features.csv": races,
        "1994_baseline_allocation_qa.csv": qa,
        "1994_unmatched_precinct_review.csv": unmatched,
    }
    for filename, frame in outputs.items(): frame.to_csv(OUT / filename, index=False)

    with closing(connect()) as connection:
        initialize(connection); connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run = begin_run(connection, "historical_1994_cmo_baseline", {"cycle": CYCLE,
            "split_precinct_policy": "legislative_activity_split_provisional"})
        for chamber, path in PLAN_FILES.items():
            register_source_file(connection, provider="alabama_reapportionment_archive", path=path,
                media_type="application/x-esri-shapefile", extraction_status="registered",
                authoritative_scope=f"1994_{chamber}_district_plan_geometry")
        table_frames = {
            "mart_historical_precinct_district_weight": weights,
            "mart_historical_district_office_baseline": office,
            "mart_historical_cmo_race_feature": races,
            "qa_historical_baseline_allocation": qa,
        }
        for table, frame in table_frames.items():
            connection.execute(f"DELETE FROM {table} WHERE cycle=?", (CYCLE,))
            frame.astype({"core_index_complete": int, "contested_two_party": int}) if table == "mart_historical_cmo_race_feature" else frame
            if table == "mart_historical_cmo_race_feature":
                frame = frame.copy(); frame["core_index_complete"] = frame.core_index_complete.astype(int); frame["contested_two_party"] = frame.contested_two_party.astype(int)
            frame.to_sql(table, connection, if_exists="append", index=False)
            register_table(connection, table, "mart" if not table.startswith("qa_") else "qa",
                "scripts/build_1994_cmo_baseline.py", "cycle/chamber/district",
                "Official SOS returns; split precincts remain explicitly provisional", "replace", "1994 historical CMO baseline audit")
        finish_run(connection, run, {"weight_rows": len(weights), "race_rows": len(races),
            "contested_two_party_races": int(races.contested_two_party.sum()),
            "unmatched_precinct_party_rows": len(unmatched),
            "minimum_allocation_coverage": float(qa.allocation_coverage.min())})
        connection.commit()
    print(races.groupby("chamber").agg(races=("district", "size"), contested=("contested_two_party", "sum"),
        complete_baseline=("core_index_complete", "sum")).to_string())
    print("\nAllocation coverage by chamber/office/party:")
    print(qa[["chamber","office","party","allocation_coverage","unmatched_votes"]].to_string(index=False))


if __name__ == "__main__": main()
