"""Tests for the Alabama seats-won-by-cycle build (small fixtures plus output contract)."""
from __future__ import annotations

import json
import sqlite3

import pandas as pd
import pytest

from scripts import build_alabama_seats_by_cycle as seats

FIXTURE_SIZES = {"house": 3, "senate": 2}
FIXTURE_CYCLES = (2010,)
PLAN = "AL-2010-{}-reported-unknown-vintage"

SCHEMA = """
CREATE TABLE fact_southern_legislative_final_candidate_election (
  candidate_result_id TEXT, observation_set_id TEXT, state_code TEXT, cycle INTEGER,
  chamber TEXT, district TEXT, district_plan_id TEXT, geography_vintage TEXT,
  election_stage TEXT, election_date TEXT, candidate_name TEXT, party_family TEXT,
  party_original TEXT, votes INTEGER, vote_value_status TEXT, source_provider TEXT,
  source_family TEXT, source_file_id TEXT, authority_rank INTEGER, build_run_id TEXT,
  validation_status TEXT, final_stage_rule TEXT);
CREATE TABLE canonical_candidates (canonical_candidate_id TEXT, year INTEGER, chamber TEXT,
  district INTEGER, canonical_party TEXT, winner INTEGER, canonical_source TEXT, person_id TEXT);
CREATE TABLE source_southern_legislative_observation_set (observation_set_id TEXT,
  source_family TEXT, provider TEXT, source_file_id TEXT, source_member TEXT, state_code TEXT,
  cycle INTEGER, chamber TEXT, district TEXT, election_stage TEXT, validation_status TEXT);
CREATE TABLE source_southern_legislative_candidate_result (source_candidate_result_id TEXT,
  observation_set_id TEXT, candidate_name TEXT, party_family TEXT, party_original TEXT,
  votes INTEGER, writein_status TEXT, winner_status INTEGER);
CREATE TABLE bridge_alabama_canonical_candidate_certified_result (canonical_candidate_id TEXT,
  source_file_id TEXT, source_candidate_result_id TEXT, match_method TEXT,
  correction_status TEXT, cycle INTEGER);
CREATE TABLE canonical_southern_legislative_candidate_election (state_code TEXT, cycle INTEGER,
  chamber TEXT, district TEXT, election_stage TEXT, observation_set_id TEXT, source_family TEXT);
CREATE TABLE warehouse_schema_version (version INTEGER, applied_at_utc TEXT, description TEXT);
CREATE TABLE warehouse_build_run (build_run_id TEXT, target TEXT, completed_at_utc TEXT,
  status TEXT, code_commit TEXT);
"""


def fact_row(cid, set_id, chamber, district, name, party, votes, family="alabama_canonical"):
    return (cid, set_id, "AL", 2010, chamber, district, PLAN.format(chamber),
            "provider-reported", "general", "2010-11-02", name, party, party[:1].upper(), votes,
            "observed", "provider", family, "SRC-K" if family == "klarner" else None,
            30 if family == "klarner" else 5,
            "RUN-K" if family == "klarner" else "legacy-alabama-canonical", "passed",
            "regular_general")


def make_warehouse(path):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany(
        "INSERT INTO fact_southern_legislative_final_candidate_election VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            # HD1 contested D win; HD2 uncontested R; HD3 deliberately absent.
            fact_row("C-H1-D", "ALCANON-2010-house-1", "lower", "1", "Alice", "democratic", 100),
            fact_row("C-H1-R", "ALCANON-2010-house-1", "lower", "1", "Bob", "republican", 50),
            fact_row("C-H2-R", "ALCANON-2010-house-2", "lower", "2", "Carol", "republican", 200),
            # SD1: canonical says R; Klarner says an independent won (conflict).
            fact_row("C-S1-R", "ALCANON-2010-senate-1", "upper", "1", "Eve", "republican", 250),
            # SD2: the final-stage interface selected the Klarner gap fill.
            fact_row("K-S2-D", "LSET-S2", "upper", "2", "GINA", "democratic", 400, "klarner"),
        ])
    con.executemany("INSERT INTO canonical_candidates VALUES (?,?,?,?,?,?,?,?)", [
        ("C-H1-D", 2010, "house", 1, "D", 1, "alabama_sos", "P1"),
        ("C-H1-R", 2010, "house", 1, "R", 0, "alabama_sos", "P2"),
        ("C-H2-R", 2010, "house", 2, "R", 1, "alabama_sos", "P3"),
        ("C-S1-R", 2010, "senate", 1, "R", 1, "alabama_sos", "P4"),
    ])
    sets = [("LSET-H1", "klarner", "lower", "1"), ("LSET-H2", "klarner", "lower", "2"),
            ("LSET-H3", "klarner", "lower", "3"), ("LSET-S1", "klarner", "upper", "1"),
            ("LSET-S2", "klarner", "upper", "2"),
            ("CANV-H1", "alabama_sos_certified_canvass", "lower", "1")]
    con.executemany(
        "INSERT INTO source_southern_legislative_observation_set VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(sid, fam, "prov", "SRC-" + fam[:3].upper(), None, "AL", 2010, ch, d, "general",
          "passed") for sid, fam, ch, d in sets])
    con.executemany(
        "INSERT INTO source_southern_legislative_candidate_result VALUES (?,?,?,?,?,?,?,?)", [
            ("K-H1-D", "LSET-H1", "ALICE", "democratic", "d", 100, "false", 1),
            ("K-H1-R", "LSET-H1", "BOB", "republican", "r", 50, "false", 0),
            ("K-H2-R", "LSET-H2", "CAROL", "republican", "r", 200, "false", 1),
            ("K-H3-D", "LSET-H3", "DAN", "democratic", "d", 300, "false", 1),
            ("K-S1-O", "LSET-S1", "FRANK", "other", "nm", 300, "false", 1),
            ("K-S1-R", "LSET-S1", "EVE", "republican", "r", 250, "false", 0),
            ("K-S2-D", "LSET-S2", "GINA", "democratic", "d", 400, "false", 1),
            ("V-H1-D", "CANV-H1", "Alice", "democratic", "D", 100, "false", None),
            ("V-H1-R", "CANV-H1", "Bob", "republican", "R", 50, "false", None),
            ("V-H1-W", "CANV-H1", "Write-In", "unknown", None, 5, "true", None),
        ])
    con.execute("INSERT INTO bridge_alabama_canonical_candidate_certified_result VALUES "
                "('C-H1-D','SRC-CANV','V-H1-D','exact','agrees',2010)")
    con.executemany(
        "INSERT INTO canonical_southern_legislative_candidate_election VALUES (?,?,?,?,?,?,?)", [
            ("AL", 2010, "lower", "1", "general", "ALCANON-2010-house-1", "alabama_canonical"),
            ("AL", 2010, "lower", "1", "general", "LSET-H1", "klarner"),
            ("AL", 2010, "lower", "2", "general", "ALCANON-2010-house-2", "alabama_canonical"),
            ("AL", 2010, "upper", "1", "general", "ALCANON-2010-senate-1", "alabama_canonical"),
            ("AL", 2010, "upper", "2", "general", "LSET-S2", "klarner"),
        ])
    con.execute("INSERT INTO warehouse_schema_version VALUES (27,'2026-09-08','fixture')")
    con.execute("INSERT INTO warehouse_build_run VALUES "
                "('RUN-K','fixture','2026-09-01T00:00:00+00:00','validated','abc')")
    con.commit()
    con.close()


BALLOTPEDIA_HOUSE = """Title: Alabama House of Representatives elections, 2010

URL Source: https://ballotpedia.org/Alabama_House_of_Representatives_elections,_2010

| Alabama House of Representatives |
| --- |
| Party | As of November 1, 2010 | After the 2010 Election |
|  | [Democratic Party](https://ballotpedia.org/Democratic_Party "Democratic Party") | **2** | 2 |
|  | [Republican Party](https://ballotpedia.org/Republican_Party "Republican Party") | 1 | **1** |
| **Total** | 3 | 3 |
"""

BALLOTPEDIA_MISSING = ("Title: Alabama State Senate elections, 2010\n\n"
                       "**Oops! The page you're looking for does not exist.**\n" + "x" * 500)

WIKI_SENATE = """<html><head>
<link rel="canonical" href="https://en.wikipedia.org/wiki/2010_Alabama_Senate_election"></head>
<body><table class="infobox vevent"><tr><td><table>
<tr><th>Party</th><td>Republican</td><td>Democratic</td></tr>
<tr><th>Seats after</th><td>0+1</td><td>1</td></tr>
</table></td></tr></table>
<table class="wikitable"><caption>Alabama's 1st Senate district election, 2010</caption>
<tr><th>Party</th><th>Candidate</th><th>Votes</th></tr>
<tr><td></td><td>Independent</td><td>Frank</td><td>300</td></tr>
<tr><td></td><td>Republican</td><td>Eve</td><td>250</td></tr>
<tr><td></td><td>Independent hold</td></tr>
</table></body></html>"""


@pytest.fixture(scope="module")
def fixture_build(tmp_path_factory):
    root = tmp_path_factory.mktemp("seats")
    warehouse = root / "warehouse.sqlite"
    make_warehouse(warehouse)
    raw = root / "raw"
    (raw / "ballotpedia" / "election_indexes").mkdir(parents=True)
    (raw / "wikipedia").mkdir()
    (raw / "ballotpedia" / "election_indexes" / "2010_house.md").write_text(
        BALLOTPEDIA_HOUSE, encoding="utf-8")
    (raw / "ballotpedia" / "election_indexes" / "2010_senate.md").write_text(
        BALLOTPEDIA_MISSING, encoding="utf-8")
    (raw / "wikipedia" / "2010_senate.html").write_text(WIKI_SENATE, encoding="utf-8")
    before = seats.sha256_file(warehouse)
    out = root / "out"
    manifest = seats.build(warehouse, raw, out, cycles=FIXTURE_CYCLES, sizes=FIXTURE_SIZES)
    return {
        "warehouse": warehouse, "before": before, "manifest": manifest,
        "districts": pd.read_csv(out / "district_winners.csv"),
        "seats": pd.read_csv(out / "seats_by_cycle.csv"),
        "recon": pd.read_csv(out / "reconciliation.csv"),
        "review": pd.read_csv(out / "review_queue.csv"),
        "manifest_file": json.loads((out / "manifest.json").read_text(encoding="utf-8")),
    }


def district(frame, chamber, number):
    return frame[(frame.chamber == chamber) & (frame.district == number)].iloc[0]


def test_one_row_per_cycle_chamber_district(fixture_build):
    frame = fixture_build["districts"]
    assert not frame.duplicated(["cycle", "chamber", "district"]).any()
    assert frame.groupby("chamber").size().to_dict() == FIXTURE_SIZES


def test_seat_totals_equal_chamber_size_with_explicit_unknowns(fixture_build):
    table = fixture_build["seats"]
    sums = table.groupby(["cycle", "chamber"]).seats.sum()
    sizes = table.groupby(["cycle", "chamber"]).chamber_size.first()
    assert (sums == sizes).all()
    assert set(table.party) == {"democratic", "republican", "other", "unknown"}
    house = table[table.chamber == "house"].set_index("party").seats.to_dict()
    assert house == {"democratic": 1, "republican": 1, "other": 0, "unknown": 1}


def test_missing_district_is_unknown_and_never_imputed(fixture_build):
    frame = fixture_build["districts"]
    row = district(frame, "house", 3)
    # Klarner has a winner for HD3, but the final-stage interface has no row:
    # the district stays unknown instead of being filled from another source.
    assert row.winner_status == "unknown"
    assert row.winner_party == "unknown"
    assert "no_final_stage_observation" in row.unknown_reason
    unknown = frame[frame.winner_status == "unknown"]
    assert (unknown.winner_party == "unknown").all()
    review = fixture_build["review"]
    assert "SEATS-V1-2010-HOUSE-003-no_final_stage_observation" in set(review.review_id)


def test_cross_source_party_conflict_is_unknown_with_review(fixture_build):
    row = district(fixture_build["districts"], "senate", 1)
    assert row.winner_status == "unknown"
    assert row.winner_name_recorded == "Eve"  # what the warehouse recorded is kept
    assert row.winner_party_recorded == "republican"
    assert "cross_source_winner_party_conflict" in row.unknown_reason
    # The reference table agrees with Klarner but never supplies the winner.
    assert row.reference_check.startswith("conflict_with_recorded_winner")
    ids = set(fixture_build["review"].review_id)
    assert "SEATS-V1-2010-SENATE-001-cross_source_winner_party_conflict" in ids


def test_uncontested_seats_are_retained_for_the_winner(fixture_build):
    frame = fixture_build["districts"]
    hd2 = district(frame, "house", 2)
    assert (hd2.winner_status, hd2.winner_party, hd2.contest_status) == \
        ("observed", "republican", "uncontested")
    sd2 = district(frame, "senate", 2)
    assert (sd2.winner_status, sd2.winner_party, sd2.contest_status) == \
        ("observed", "democratic", "uncontested")
    assert sd2.source_family == "klarner" and sd2.corroboration == "single_source"
    table = fixture_build["seats"]
    rep = table[(table.chamber == "house") & (table.party == "republican")].iloc[0]
    assert rep.seats == 1 and rep.uncontested_seats == 1


def test_contested_winner_has_lineage_and_corroboration(fixture_build):
    row = district(fixture_build["districts"], "house", 1)
    assert (row.winner_status, row.winner_party, row.contest_status) == \
        ("observed", "democratic", "contested")
    assert row.winner_basis == "recorded_winner_flag_and_plurality"
    assert row.warehouse_table == seats.SELECTED_TABLE
    assert row.observation_set_id == "ALCANON-2010-house-1"
    assert row.winner_candidate_result_id == "C-H1-D"
    assert row.certified_source_file_id == "SRC-CANV"
    assert "agree:klarner" in row.cross_source_check
    assert "agree:alabama_sos_certified_canvass" in row.cross_source_check


def test_reconciliation_statuses(fixture_build):
    recon = fixture_build["recon"].set_index(["chamber", "reference_kind"])
    ballot = recon.loc[("house", "ballotpedia_composition_after_election")]
    assert ballot.status == "consistent_with_unknowns"
    assert (ballot.ref_democratic, ballot.ref_republican) == (2, 1)
    assert recon.loc[("senate", "ballotpedia_composition_after_election")].status == \
        "reference_unavailable"
    wiki = recon.loc[("senate", "wikipedia_infobox_seats_after")]
    assert (wiki.ref_republican, wiki.ref_other, wiki.ref_democratic) == (0, 1, 1)
    assert wiki.status == "consistent_with_unknowns"
    totals = fixture_build["review"]
    assert {"SEATS-V1-2010-HOUSE-TOTAL-total_not_reconciled_with_independent_reference",
            "SEATS-V1-2010-HOUSE-001-multiple_observation_sets_in_materialized_canonical_table"
            } <= set(totals.review_id)


def test_manifest_records_definition_and_provenance(fixture_build):
    manifest = fixture_build["manifest_file"]
    assert manifest["definition"].startswith("Seats won by party at the regular general election")
    assert "not chamber composition at session start" in manifest["definition"]
    assert "special elections and special runoffs" in manifest["excluded_from_definition"]
    assert "party switches after the general election" in manifest["excluded_from_definition"]
    assert manifest["warehouse"]["sha256"] == fixture_build["before"]
    assert manifest["warehouse"]["schema_version"]["version"] == 27
    assert set(manifest["outputs"]) == {"district_winners.csv", "seats_by_cycle.csv",
                                        "reconciliation.csv", "review_queue.csv"}
    assert manifest["row_counts"]["district_winners"] == 5


def test_build_never_writes_the_warehouse(fixture_build):
    assert seats.sha256_file(fixture_build["warehouse"]) == fixture_build["before"]
    con = seats.connect_readonly(fixture_build["warehouse"])
    with pytest.raises(sqlite3.OperationalError):
        con.execute("CREATE TABLE should_fail (x INTEGER)")
    con.close()


def test_recorded_winner_rejects_flag_that_contradicts_votes():
    rows = [{"candidate_name": "A", "bucket": "democratic", "votes": 10, "aggregate": False,
             "winner_flag": 1},
            {"candidate_name": "B", "bucket": "republican", "votes": 20, "aggregate": False,
             "winner_flag": 0}]
    assert seats.recorded_winner(rows)["reason"] == "recorded_winner_contradicts_votes"


def test_write_in_aggregates_are_not_opponents_or_winners():
    cands = [{"bucket": "republican", "votes": 50, "aggregate": False},
             {"bucket": None, "votes": 3, "aggregate": True}]
    assert seats.plurality(cands) == ("republican", "plurality")
    assert seats.is_aggregate("Write-In") and seats.is_aggregate("OVER VOTES")
    assert seats.classify_contest(1, "major_party_rows_only", {}) == \
        ("unknown", "no_full_ballot_observation")
    assert seats.classify_contest(1, "major_party_rows_only", {"klarner": 1})[0] == "uncontested"
    assert seats.classify_contest(1, "major_party_rows_only", {"klarner": 2})[0] == "contested"


def test_reconcile_match_and_mismatch():
    ours = {"democratic": 8, "republican": 27, "other": 0, "unknown": 0}
    assert seats.reconcile(ours, {"democratic": 8, "republican": 27, "other": 0}, 35)[0] == "match"
    status, deltas, _ = seats.reconcile(
        ours, {"democratic": 8, "republican": 26, "other": 1}, 35)
    assert status == "mismatch" and deltas == {"democratic": 0, "republican": 1, "other": -1}


def test_reference_conflict_withholds_winner_only_when_backed_by_totals():
    frame = pd.DataFrame([
        {"cycle": 2014, "chamber": "senate", "district": 29, "winner_status": "observed",
         "winner_party": "republican", "reference_check": "agree:x"},
        {"cycle": 2014, "chamber": "senate", "district": 30, "winner_status": "observed",
         "winner_party": "republican", "reference_check": "conflict:wikipedia_district_table"},
    ])
    refs = {(2014, "senate", "30"): [{"winner_bucket": "other"}]}
    backed_total = [{"cycle": 2014, "chamber": "senate", "independence": "external",
                     "democratic": 0, "republican": 1, "other": 1}]
    agreeing_total = [{"cycle": 2014, "chamber": "senate", "independence": "external",
                       "democratic": 0, "republican": 2, "other": 0}]
    assert seats.supported_reference_conflicts(frame, refs, backed_total) == \
        frozenset({(2014, "senate", "30")})
    assert seats.supported_reference_conflicts(frame, refs, agreeing_total) == frozenset()


def test_ballotpedia_and_wikipedia_parsers():
    tables = seats.ballotpedia_tables(BALLOTPEDIA_HOUSE)
    assert len(tables) == 1 and tables[0]["cycle"] == 2010
    assert (tables[0]["democratic"], tables[0]["republican"]) == (2, 1)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(WIKI_SENATE, "html.parser")
    totals = seats.wiki_infobox_totals(seats.wiki_infobox_rows(soup), seats.WIKI_SEATS_AFTER_LABELS)
    assert (totals["republican"], totals["democratic"], totals["other"]) == (0, 1, 1)
    district_tables = seats.wiki_district_tables(soup, 2)
    assert seats.wiki_table_winner(district_tables[1][0]) == ("other", "hold_gain_row_and_plurality")


# ------------------------------------------------- contract on the committed run

OUTPUT = seats.OUT
needs_output = pytest.mark.skipif(not (OUTPUT / "manifest.json").exists(),
                                  reason="seats-by-cycle output not built")


@needs_output
def test_output_grid_totals_and_unknowns():
    frame = pd.read_csv(OUTPUT / "district_winners.csv")
    assert not frame.duplicated(["cycle", "chamber", "district"]).any()
    counts = frame.groupby(["cycle", "chamber"]).size()
    assert set(counts.index.get_level_values(0)) == set(seats.CYCLES)
    for (_, chamber), n in counts.items():
        assert n == seats.CHAMBER_SIZES[chamber]
    assert ((frame.winner_status == "unknown") == (frame.winner_party == "unknown")).all()
    table = pd.read_csv(OUTPUT / "seats_by_cycle.csv")
    sums = table.groupby(["cycle", "chamber"]).seats.sum()
    assert (sums == table.groupby(["cycle", "chamber"]).chamber_size.first()).all()
    observed_uncontested = frame[(frame.winner_status == "observed")
                                 & (frame.contest_status == "uncontested")]
    assert len(observed_uncontested) > 0


@needs_output
def test_output_every_unknown_and_unreconciled_total_is_queued():
    frame = pd.read_csv(OUTPUT / "district_winners.csv")
    review = pd.read_csv(OUTPUT / "review_queue.csv")
    recon = pd.read_csv(OUTPUT / "reconciliation.csv")
    blocking = review[review.severity == "blocking"]
    queued = {(r.cycle, r.chamber, int(r.district)) for r in blocking.itertuples()
              if r.scope == "district"}
    for row in frame[frame.winner_status == "unknown"].itertuples():
        assert (row.cycle, row.chamber, row.district) in queued
    independent = recon.independence.isin(
        ["external", "warehouse_secondary_independent_of_selected_rows"])
    reconciled = set(map(tuple, recon[independent & (recon.status == "match")]
                         [["cycle", "chamber"]].drop_duplicates().values))
    totals = {(r.cycle, r.chamber) for r in blocking.itertuples() if r.scope == "total"}
    for cycle in seats.CYCLES:
        for chamber in seats.CHAMBER_SIZES:
            assert (cycle, chamber) in reconciled or (cycle, chamber) in totals
