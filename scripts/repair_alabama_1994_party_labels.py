"""Apply the owner-adjudicated 1994 Alabama party-label and House 92 district repair.

Task ``ALABAMA-1994-PARTY-LABELS-20261004``. Evidence and decisions:
``data/manual/elections/alabama_1994_party_label_adjudications.csv`` (one row per
contest), ``data/manual/elections/alabama_1994_candidate_id_supersession.csv``
(old -> new canonical IDs) and
``project_docs/audits/ALABAMA_1994_PARTY_LABEL_REPAIR_2026_10_04.md``.

The 1994 precinct reader inferred party from ballot position. It read every lone
candidate as the first (Democratic) column, read a second-position code whose
district ends in 1 (``BHS91``) as Democratic, read independents in the second or
third position as Republican, and left Covington's "House 92" columns without a
district. This script corrects only the stored rows the owner adjudicated:

* ``vote_observations``: ``party``/``party_norm``/``party_method`` of the
  adjudicated source columns and the district of the three Covington House 92
  columns. Votes, rowids, ballot codes, candidate labels and ingestion run IDs
  are unchanged; before-images are kept in ``qa_warehouse_source_repair``.
* ``canonical_candidates`` and the ``ALCANON-1994-*`` sets of
  ``canonical_southern_legislative_candidate_election`` for the 38 affected
  contests. The party letter is part of ``canonical_candidate_id``, so relabelled
  candidates are re-keyed; retired IDs are listed in the supersession record.
  Canonical votes follow the precinct-cell-sum rule (Marshall 2002 precedent).
* registers the official 1994 legislative workbook and the 1994 candidate roster
  in ``warehouse_source_file`` (retrieval time and license unknown: NULL).
* one ``warehouse_manual_adjudication`` row per adjudication, one
  ``warehouse_build_run`` and one ``qa_warehouse_source_repair`` row.

Dry run (default) is read-only and prints every changed canonical and
materialized row and every changed source column. ``--apply`` requires the exact
latest warehouse run, a new separate backup path and an authorization
reference. Nothing downstream is rebuilt here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

from oe_normalize import norm_party, normalize_name
from warehouse import ROOT, begin_run, database_path, file_sha256, finish_run, source_file_id, utcnow

TARGET = "alabama_1994_party_label_repair"
YEAR = 1994
TASK = "ALABAMA-1994-PARTY-LABELS-20261004"
VOTES = "vote_observations"
CANONICAL = "canonical_candidates"
MATERIALIZED = "canonical_southern_legislative_candidate_election"
ADJUDICATION = "warehouse_manual_adjudication"
SOURCES = "warehouse_source_file"
BUILD = "warehouse_build_run"
REPAIR = "qa_warehouse_source_repair"
OWNED_INSERT = {CANONICAL, MATERIALIZED, ADJUDICATION, SOURCES, BUILD, REPAIR}
OWNED_DELETE = {CANONICAL, MATERIALIZED}
VOTE_COLUMNS = {"party", "party_norm", "party_method", "district"}
CONTROL_TABLES = (BUILD, REPAIR, ADJUDICATION, SOURCES)
UNOWNED_TABLES = ("warehouse_table_registry", "warehouse_schema_version", "candidate_aliases",
                  "candidate_party_affiliations", "candidate_party_switches", "mart_historical_candidate_incumbency",
                  "mart_southern_war_outcome", "source_southern_legislative_candidate_result")

PRECINCT_SOURCE_ID = "SRC-E64FFC4299ED54CB2D3A"
PRECINCT_ARCHIVE = "data/raw/alabama_elections_and_geography/94g-prec.zip"
PRECINCT_ARCHIVE_SHA256 = "94512391c389c45d2899f06686484790adaf4c99fa638b217e31f54652c55097"
KLARNER_SOURCE_ID = "SRC-C3ABE0AF40990D35F24C"
ADJUDICATIONS_CSV = "data/manual/elections/alabama_1994_party_label_adjudications.csv"
SUPERSESSION_CSV = "data/manual/elections/alabama_1994_candidate_id_supersession.csv"
# Content hashes with CRLF normalized to LF, so a Git checkout does not change them.
ADJUDICATIONS_SHA256 = "d952e600d6ebe73feaafc26c46d0acbf49b0b9283a09c22d755d720b741ba606"
SUPERSESSION_SHA256 = "026a8fd10dd38996d7e64749252b9b1740657b7c5320f0bb52c18d9092d90997"
AUDIT = "project_docs/audits/ALABAMA_1994_PARTY_LABEL_REPAIR_2026_10_04.md"
EVIDENCE_REGISTRATIONS = (
    {"provider": "alabama_sos", "path": "data/raw/alabama_elections_and_geography/eastateleg94.xls",
     "sha256": "76a5b08dc298a62865a4fc34f30c4e3a9d3a153b903f6d5a04a915147a718a80",
     # Cited in data/manual/ideology/candidate_issue_research_attempts.csv; the 1986 and
     # 1990 sibling workbooks are registered from the same SOS path.
     "original_url": "https://www.sos.alabama.gov/sites/default/files/election-data/2017-06/eastateleg94.xls",
     "media_type": "application/vnd.ms-excel",
     "authoritative_scope": "official_historical_legislative_county_totals; 1994 printed party labels used as repair evidence"},
    {"provider": "alabama_forestry_commission",
     "path": "data/raw/ideology/alabama_1994_archival_sources/alabama_treasured_forests_fall_1994.pdf",
     "sha256": "adff09d18afef4f6ca62f10121f142879413ded484a08554fa62797ee0f92248",
     "original_url": "https://www.forestry.alabama.gov/Pages/Informational/Treasured_Forests/Magazine/1994_Fall.pdf",
     "media_type": "application/pdf",
     "authoritative_scope": "contemporaneous pre-election 1994 legislative candidate roster; repair evidence only"},
)
BEFORE_METHOD = "ballot_order_with_export_code"
OFFICIAL = "adjudicated_official_summary"
REVIEWED = "adjudicated_reviewed_evidence"
MANUAL_DIR = "data/manual"
NOT_REBUILT = [
    "candidate_aliases, candidate_alias_match_candidates, candidate_party_affiliations, candidate_party_switches "
    "(identity-build snapshots keyed on the old 1994 IDs; candidate_party_switches holds false 1994->1998 switches "
    "such as Haney, Sanderford, Waggoner and Turner)",
    "mart_historical_candidate_incumbency, mart_historical_candidate_finance_coverage, "
    "mart_historical_cmo_context_feature and data/processed/elections/1994_candidate_incumbency.csv, "
    "1994_cmo_context_features.csv (rerun build_1994_context_features.py)",
    "1994 baseline weights and race features (1994_precinct_district_ballot_weights.csv still allocates 51 Covington "
    "precincts to House 1; rerun build_1994_cmo_baseline.py); mart_candidate_resources 1994 rows",
    "canonical_cmo_features.csv, canonical_cmo_candidates.csv, historical_cmo_extension.csv, cmo_v5_*, "
    "alabama_historical_war_v1, alabama_career_war_v1, democratic_caucuses_v1, seats by cycle, WAR story page",
    "canonical_southern_legislative_candidate_election: the Klarner House 92 set LSET-B2A1E6695F8E176E7E2F stays "
    "beside the new ALCANON-1994-house-92 set until load_southern_legislative_history_warehouse.py re-materializes; "
    "the final-candidate view already prefers ALCANON",
    "mart_historical_federal_district_baseline and historical_federal_* exports (1994 U.S. House 1 still absent; "
    "owner: do not rebuild federal baselines)",
    "southern_war_panel_v1 Alabama 1994 backcast rows (outside the v3 training frame)",
    "data/raw/sos_normalized/1994_general_precinct.csv (stale adapter output under raw; left unchanged)",
    "derived ideology/finance exports that copy 1994 IDs (see the audit's stale list); docs/cmo.html",
]


@dataclass(frozen=True)
class SourceTarget:
    """One adjudicated set of 1994 source columns, selected by its export code."""
    adjudication_id: str
    ballot_code: str
    office: str | None            # None: any office label (statewide and federal codes)
    district_before: float | None  # stored district; None is NULL (ignored when office is None)
    county_key: str | None
    party_before: str
    party_after: str
    district_after: float | None  # None: unchanged
    method_after: str | None      # None: unchanged
    columns: int
    rows: int
    votes: float


@dataclass(frozen=True)
class Contest:
    """Canonical rows (id, party, votes, winner, name, person_id) before and after."""
    before: tuple
    after: tuple


SOURCE_TARGETS = [
    SourceTarget('ADJ-1994-AL-HD010-SOLE-R', 'AHS10', 'State House', 10, None, 'D', 'R', None, OFFICIAL, 1, 11, 10090.0),
    SourceTarget('ADJ-1994-AL-HD020-SOLE-R', 'AHS20', 'State House', 20, None, 'D', 'R', None, OFFICIAL, 1, 16, 11641.0),
    SourceTarget('ADJ-1994-AL-HD044-SOLE-R', 'AHS44', 'State House', 44, None, 'D', 'R', None, OFFICIAL, 1, 14, 10765.0),
    SourceTarget('ADJ-1994-AL-HD045-SOLE-R', 'AHS45', 'State House', 45, None, 'D', 'R', None, OFFICIAL, 1, 22, 10599.0),
    SourceTarget('ADJ-1994-AL-HD047-SOLE-R', 'AHS47', 'State House', 47, None, 'D', 'R', None, OFFICIAL, 2, 61, 13349.0),
    SourceTarget('ADJ-1994-AL-HD074-SOLE-R', 'AHS74', 'State House', 74, None, 'D', 'R', None, OFFICIAL, 1, 11, 10410.0),
    SourceTarget('ADJ-1994-AL-HD094-SOLE-R', 'AHS94', 'State House', 94, None, 'D', 'R', None, OFFICIAL, 1, 26, 12329.0),
    SourceTarget('ADJ-1994-AL-HD100-SOLE-R', 'AHS100', 'State House', 100, None, 'D', 'R', None, OFFICIAL, 1, 8, 8307.0),
    SourceTarget('ADJ-1994-AL-HD102-SOLE-R', 'AHS102', 'State House', 102, None, 'D', 'R', None, OFFICIAL, 1, 11, 7192.0),
    SourceTarget('ADJ-1994-AL-HD041-HILL-R', 'AHS41', 'State House', 41, None, 'D', 'R', None, REVIEWED, 1, 41, 10277.0),
    SourceTarget('ADJ-1994-AL-SD015-SOLE-R', 'ASENAT15', 'State Senate', 15, None, 'D', 'R', None, OFFICIAL, 1, 52, 32505.0),
    SourceTarget('ADJ-1994-AL-SD016-SOLE-R', 'ASENAT16', 'State Senate', 16, None, 'D', 'R', None, OFFICIAL, 2, 90, 42672.0),
    SourceTarget('ADJ-1994-AL-SD017-SOLE-R', 'ASENAT17', 'State Senate', 17, None, 'D', 'R', None, OFFICIAL, 2, 75, 28720.0),
    SourceTarget('ADJ-1994-AL-HD001-SPLIT-B1', 'BHS1', 'State House', 1, None, 'D', 'R', None, OFFICIAL, 1, 21, 4396.0),
    SourceTarget('ADJ-1994-AL-HD011-SPLIT-B1', 'BHS11', 'State House', 11, None, 'D', 'R', None, OFFICIAL, 2, 39, 5936.0),
    SourceTarget('ADJ-1994-AL-HD021-SPLIT-B1', 'BHS21', 'State House', 21, None, 'D', 'R', None, OFFICIAL, 1, 17, 3366.0),
    SourceTarget('ADJ-1994-AL-HD051-SPLIT-B1', 'BHS51', 'State House', 51, None, 'D', 'R', None, OFFICIAL, 1, 31, 8086.0),
    SourceTarget('ADJ-1994-AL-HD091-SPLIT-B1', 'BHS91', 'State House', 91, None, 'D', 'R', None, OFFICIAL, 1, 59, 5935.0),
    SourceTarget('ADJ-1994-AL-HD101-SPLIT-B1', 'BHS101', 'State House', 101, None, 'D', 'R', None, OFFICIAL, 1, 11, 8223.0),
    SourceTarget('ADJ-1994-AL-SD011-SPLIT-B1', 'BSENAT11', 'State Senate', 11, None, 'D', 'R', None, OFFICIAL, 3, 78, 17246.0),
    SourceTarget('ADJ-1994-AL-SD031-SPLIT-B1', 'BSENAT31', 'State Senate', 31, None, 'D', 'R', None, OFFICIAL, 4, 145, 14888.0),
    SourceTarget('ADJ-1994-AL-HD008-THIRD-PARTY', 'BHS8', 'State House', 8, None, 'R', 'I', None, OFFICIAL, 1, 14, 2602.0),
    SourceTarget('ADJ-1994-AL-HD012-THIRD-PARTY', 'BHS12', 'State House', 12, None, 'R', 'P', None, OFFICIAL, 1, 41, 3013.0),
    SourceTarget('ADJ-1994-AL-HD019-HALL-D-ANDERSON-I', 'BHS19', 'State House', 19, None, 'R', 'I', None, OFFICIAL, 1, 15, 1030.0),
    SourceTarget('ADJ-1994-AL-HD029-THIRD-PARTY', 'BHS29', 'State House', 29, None, 'R', 'I', None, OFFICIAL, 1, 28, 2464.0),
    SourceTarget('ADJ-1994-AL-HD053-THIRD-PARTY', 'BHS53', 'State House', 53, None, 'R', 'I', None, OFFICIAL, 1, 22, 3029.0),
    SourceTarget('ADJ-1994-AL-HD058-THIRD-PARTY', 'BHS58', 'State House', 58, None, 'R', 'P', None, OFFICIAL, 1, 22, 813.0),
    SourceTarget('ADJ-1994-AL-HD067-THIRD-PARTY', 'BHS67', 'State House', 67, None, 'R', 'I', None, OFFICIAL, 1, 27, 3785.0),
    SourceTarget('ADJ-1994-AL-HD069-THIRD-PARTY', 'BHS69', 'State House', 69, None, 'R', 'I', None, OFFICIAL, 2, 33, 1097.0),
    SourceTarget('ADJ-1994-AL-HD072-THIRD-PARTY', 'BHS72', 'State House', 72, None, 'R', 'I', None, OFFICIAL, 4, 95, 2516.0),
    SourceTarget('ADJ-1994-AL-HD086-THIRD-PARTY', 'BHS86', 'State House', 86, None, 'R', 'I', None, OFFICIAL, 1, 31, 3997.0),
    SourceTarget('ADJ-1994-AL-HD097-THIRD-PARTY', 'BHS97', 'State House', 97, None, 'R', 'I', None, OFFICIAL, 1, 12, 2320.0),
    SourceTarget('ADJ-1994-AL-HD103-THIRD-PARTY', 'BHS103', 'State House', 103, None, 'R', 'I', None, OFFICIAL, 1, 12, 1227.0),
    SourceTarget('ADJ-1994-AL-SD018-THIRD-PARTY', 'BSENAT18', 'State Senate', 18, None, 'R', 'P', None, OFFICIAL, 1, 74, 6649.0),
    SourceTarget('ADJ-1994-AL-SD023-THIRD-PARTY', 'BSENAT23', 'State Senate', 23, None, 'R', 'I', None, OFFICIAL, 7, 193, 2201.0),
    SourceTarget('ADJ-1994-AL-HD032-THIRD-PARTY', 'CHS32', 'State House', 32, None, 'R', 'I', None, OFFICIAL, 2, 37, 789.0),
    SourceTarget('ADJ-1994-AL-HD092-COVINGTON-DISTRICT', 'AHS92', 'State House', None, 'COVINGTN', 'D', 'D', 92, None, 1, 57, 5449.0),
    SourceTarget('ADJ-1994-AL-HD092-COVINGTON-DISTRICT', 'BHS92', 'State House', None, 'COVINGTN', 'R', 'R', 92, None, 1, 57, 3683.0),
    SourceTarget('ADJ-1994-AL-HD092-COVINGTON-DISTRICT', 'CHS92', 'State House', 1, 'COVINGTN', 'R', 'I', 92, OFFICIAL, 1, 57, 550.0),
    SourceTarget('ADJ-1994-AL-SD025-DIXON-R', 'ASENAT25', 'State Senate', 25, 'MONTGMRY', 'D', 'R', None, OFFICIAL, 1, 57, 27972.0),
    SourceTarget('ADJ-1994-AL-SD025-DIXON-R', 'ASENAT25', 'State Senate', 25, 'ELMORE', 'D', '', None, REVIEWED, 1, 29, 1468.0),
    SourceTarget('ADJ-1994-AL-USHOUSE01-CALLAHAN-R', 'BUSHS1', None, None, None, 'D', 'R', None, REVIEWED, 6, 302, 103431.0),
    SourceTarget('ADJ-1994-AL-CHIEFJUSTICE-HOOPER-R', 'SUPJUST2', None, None, None, 'D', 'R', None, REVIEWED, 66, 3048, 560068.0),
    SourceTarget('ADJ-1994-AL-PSC1-HELMS-R', 'BPSC1', None, None, None, 'D', 'R', None, REVIEWED, 67, 3078, 537368.0),
    SourceTarget('ADJ-1994-AL-CCA1-LONG-R', 'BCRIC1', None, None, None, 'D', 'R', None, REVIEWED, 67, 3079, 525746.0),
]

CONTESTS = {
    ('house', 1): Contest(
        before=(('AL-1994-house-1-D-STARKEY', 'D', 7385.0, 1, 'Starkey', 'ALPERSON-STARKEY'), ('AL-1994-house-1-R-PHILLIPS', 'R', 4946.0, 0, 'Phillips', 'ALPERSON-PHILLIPS'), ),
        after=(('AL-1994-house-1-D-STARKEY', 'D', 7385.0, 1, 'Starkey', 'ALPERSON-STARKEY'), ('AL-1994-house-1-R-PHILLIPS', 'R', 4396.0, 0, 'Phillips', 'ALPERSON-PHILLIPS'), )),
    ('house', 8): Contest(
        before=(('AL-1994-house-8-D-DUKES', 'D', 8391.0, 1, 'Dukes', 'ALPERSON-DUKES'), ('AL-1994-house-8-R-NEW', 'R', 2602.0, 0, 'New', 'ALPERSON-NEW'), ),
        after=(('AL-1994-house-8-D-DUKES', 'D', 8391.0, 1, 'Dukes', 'ALPERSON-DUKES'), )),
    ('house', 10): Contest(
        before=(('AL-1994-house-10-D-HANEY', 'D', 10090.0, 1, 'Haney', 'ALPERSON-HANEY'), ),
        after=(('AL-1994-house-10-R-HANEY', 'R', 10090.0, 1, 'Haney', 'ALPERSON-HANEY'), )),
    ('house', 11): Contest(
        before=(('AL-1994-house-11-D-DRAKE', 'D', 12518.0, 1, 'Drake', 'ALPERSON-DRAKE'), ),
        after=(('AL-1994-house-11-D-DRAKE', 'D', 6582.0, 1, 'Drake', 'ALPERSON-DRAKE'), ('AL-1994-house-11-R-ODEN', 'R', 5936.0, 0, 'Oden', 'ALPERSON-ODEN'), )),
    ('house', 12): Contest(
        before=(('AL-1994-house-12-D-MORRISON', 'D', 7159.0, 1, 'Morrison', 'ALPERSON-MORRISON'), ('AL-1994-house-12-R-BOWLING', 'R', 6564.0, 0, 'Bowling', 'ALPERSON-BOWLING'), ),
        after=(('AL-1994-house-12-D-MORRISON', 'D', 7159.0, 1, 'Morrison', 'ALPERSON-MORRISON'), ('AL-1994-house-12-R-HOLLIS', 'R', 3551.0, 0, 'Hollis', 'ALPERSON-HOLLIS'), )),
    ('house', 19): Contest(
        before=(('AL-1994-house-19-D-HALL', 'D', 7314.0, 1, 'Hall', 'ALPERSON-HALL'), ('AL-1994-house-19-R-ANDERSON', 'R', 1030.0, 0, 'Anderson', 'ALPERSON-ANDERSON'), ),
        after=(('AL-1994-house-19-D-HALL', 'D', 7314.0, 1, 'Hall', 'ALPERSON-HALL'), )),
    ('house', 20): Contest(
        before=(('AL-1994-house-20-D-SANDERFORD', 'D', 11641.0, 1, 'Sanderford', 'ALPERSON-SANDERFORD'), ),
        after=(('AL-1994-house-20-R-SANDERFORD', 'R', 11641.0, 1, 'Sanderford', 'ALPERSON-SANDERFORD'), )),
    ('house', 21): Contest(
        before=(('AL-1994-house-21-D-JOHNSTON', 'D', 9877.0, 1, 'Johnston', 'ALPERSON-JOHNSTON'), ),
        after=(('AL-1994-house-21-D-HINSHAW', 'D', 6511.0, 1, 'Hinshaw', 'ALPERSON-HINSHAW'), ('AL-1994-house-21-R-JOHNSTON', 'R', 3366.0, 0, 'Johnston', 'ALPERSON-JOHNSTON'), )),
    ('house', 29): Contest(
        before=(('AL-1994-house-29-D-PAGE', 'D', 7064.0, 1, 'Page', 'ALPERSON-PAGE'), ('AL-1994-house-29-R-ESTES', 'R', 2464.0, 0, 'Estes', 'ALPERSON-ESTES'), ),
        after=(('AL-1994-house-29-D-PAGE', 'D', 7064.0, 1, 'Page', 'ALPERSON-PAGE'), )),
    ('house', 32): Contest(
        before=(('AL-1994-house-32-D-BOYD', 'D', 4541.0, 1, 'Boyd', 'ALPERSON-BOYD'), ('AL-1994-house-32-R-MONTGOMERY', 'R', 2241.0, 0, 'Montgomery', 'ALPERSON-MONTGOMERY'), ),
        after=(('AL-1994-house-32-D-BOYD', 'D', 4541.0, 1, 'Boyd', 'ALPERSON-BOYD'), ('AL-1994-house-32-R-BRADFORD', 'R', 1452.0, 0, 'Bradford', 'ALPERSON-BRADFORD'), )),
    ('house', 41): Contest(
        before=(('AL-1994-house-41-D-HILL', 'D', 10277.0, 1, 'Hill', 'ALPERSON-HILL'), ),
        after=(('AL-1994-house-41-R-HILL', 'R', 10277.0, 1, 'Hill', 'ALPERSON-HILL'), )),
    ('house', 44): Contest(
        before=(('AL-1994-house-44-D-PAYNE', 'D', 10765.0, 1, 'Payne', 'ALPERSON-PAYNE'), ),
        after=(('AL-1994-house-44-R-PAYNE', 'R', 10765.0, 1, 'Payne', 'ALPERSON-PAYNE'), )),
    ('house', 45): Contest(
        before=(('AL-1994-house-45-D-MORTON', 'D', 10599.0, 1, 'Morton', 'ALPERSON-MORTON'), ),
        after=(('AL-1994-house-45-R-MORTON', 'R', 10599.0, 1, 'Morton', 'ALPERSON-MORTON'), )),
    ('house', 47): Contest(
        before=(('AL-1994-house-47-D-GAINES', 'D', 13349.0, 1, 'Gaines', 'ALPERSON-GAINES'), ),
        after=(('AL-1994-house-47-R-GAINES', 'R', 13349.0, 1, 'Gaines', 'ALPERSON-GAINES'), )),
    ('house', 51): Contest(
        before=(('AL-1994-house-51-D-PETELOS', 'D', 12582.0, 1, 'Petelos', 'ALPERSON-PETELOS'), ),
        after=(('AL-1994-house-51-D-ROGERS', 'D', 4496.0, 0, 'Rogers', 'ALPERSON-ROGERS--1994-HOUSE-51'), ('AL-1994-house-51-R-PETELOS', 'R', 8086.0, 1, 'Petelos', 'ALPERSON-PETELOS'), )),
    ('house', 53): Contest(
        before=(('AL-1994-house-53-D-NEWTON', 'D', 5925.0, 1, 'Newton', 'ALPERSON-NEWTON'), ('AL-1994-house-53-R-BLAKE', 'R', 3029.0, 0, 'Blake', 'ALPERSON-BLAKE'), ),
        after=(('AL-1994-house-53-D-NEWTON', 'D', 5925.0, 1, 'Newton', 'ALPERSON-NEWTON'), )),
    ('house', 58): Contest(
        before=(('AL-1994-house-58-D-JOHNSON', 'D', 6055.0, 1, 'Johnson', 'ALPERSON-JOHNSON'), ('AL-1994-house-58-R-LELAND', 'R', 813.0, 0, 'Leland', 'ALPERSON-LELAND'), ),
        after=(('AL-1994-house-58-D-JOHNSON', 'D', 6055.0, 1, 'Johnson', 'ALPERSON-JOHNSON'), )),
    ('house', 67): Contest(
        before=(('AL-1994-house-67-D-MAULL', 'D', 7507.0, 1, 'Maull', 'ALPERSON-MAULL'), ('AL-1994-house-67-R-WALKER', 'R', 3785.0, 0, 'Walker', 'ALPERSON-WALKER'), ),
        after=(('AL-1994-house-67-D-MAULL', 'D', 7507.0, 1, 'Maull', 'ALPERSON-MAULL'), )),
    ('house', 69): Contest(
        before=(('AL-1994-house-69-D-THOMAS', 'D', 4706.0, 1, 'Thomas', 'ALPERSON-THOMAS'), ('AL-1994-house-69-R-BROOKS', 'R', 1097.0, 0, 'Brooks', 'ALPERSON-BROOKS'), ),
        after=(('AL-1994-house-69-D-THOMAS', 'D', 4706.0, 1, 'Thomas', 'ALPERSON-THOMAS'), )),
    ('house', 72): Contest(
        before=(('AL-1994-house-72-D-HAYDEN', 'D', 7631.0, 1, 'Hayden', 'ALPERSON-HAYDEN'), ('AL-1994-house-72-R-WILLIAMS', 'R', 2516.0, 0, 'Williams', 'ALPERSON-WILLIAMS'), ),
        after=(('AL-1994-house-72-D-HAYDEN', 'D', 7631.0, 1, 'Hayden', 'ALPERSON-HAYDEN'), )),
    ('house', 74): Contest(
        before=(('AL-1994-house-74-D-MCKEE', 'D', 10410.0, 1, 'Mckee', 'ALPERSON-MCKEE'), ),
        after=(('AL-1994-house-74-R-MCKEE', 'R', 10410.0, 1, 'Mckee', 'ALPERSON-MCKEE'), )),
    ('house', 86): Contest(
        before=(('AL-1994-house-86-D-CAROTHERS', 'D', 5368.0, 1, 'Carothers', 'ALPERSON-CAROTHERS'), ('AL-1994-house-86-R-SHUEMAKE', 'R', 3997.0, 0, 'Shuemake', 'ALPERSON-SHUEMAKE'), ),
        after=(('AL-1994-house-86-D-CAROTHERS', 'D', 5368.0, 1, 'Carothers', 'ALPERSON-CAROTHERS'), )),
    ('house', 91): Contest(
        before=(('AL-1994-house-91-D-SPICER', 'D', 11761.0, 1, 'Spicer', 'ALPERSON-SPICER'), ),
        after=(('AL-1994-house-91-D-SPICER', 'D', 5826.0, 0, 'Spicer', 'ALPERSON-SPICER'), ('AL-1994-house-91-R-MOORE', 'R', 5935.0, 1, 'Moore', 'ALPERSON-MOORE'), )),
    ('house', 92): Contest(
        before=(),
        after=(('AL-1994-house-92-D-HAMMETT', 'D', 5449.0, 1, 'Hammett', 'ALPERSON-HAMMETT'), ('AL-1994-house-92-R-MARTIN', 'R', 3683.0, 0, 'Martin', 'ALPERSON-MARTIN--1994-HOUSE-92'), )),
    ('house', 94): Contest(
        before=(('AL-1994-house-94-D-PENRY', 'D', 12329.0, 1, 'Penry', 'ALPERSON-PENRY'), ),
        after=(('AL-1994-house-94-R-PENRY', 'R', 12329.0, 1, 'Penry', 'ALPERSON-PENRY'), )),
    ('house', 97): Contest(
        before=(('AL-1994-house-97-D-KENNEDY', 'D', 4609.0, 1, 'Kennedy', 'ALPERSON-KENNEDY'), ('AL-1994-house-97-R-BAUMHAUER', 'R', 2320.0, 0, 'Baumhauer', 'ALPERSON-BAUMHAUER'), ),
        after=(('AL-1994-house-97-D-KENNEDY', 'D', 4609.0, 1, 'Kennedy', 'ALPERSON-KENNEDY'), )),
    ('house', 100): Contest(
        before=(('AL-1994-house-100-D-GASTON', 'D', 8307.0, 1, 'Gaston', 'ALPERSON-GASTON'), ),
        after=(('AL-1994-house-100-R-GASTON', 'R', 8307.0, 1, 'Gaston', 'ALPERSON-GASTON'), )),
    ('house', 101): Contest(
        before=(('AL-1994-house-101-D-PRINGLE', 'D', 13416.0, 1, 'Pringle', 'ALPERSON-PRINGLE'), ),
        after=(('AL-1994-house-101-D-ZOGHBY', 'D', 5193.0, 0, 'Zoghby', 'ALPERSON-ZOGHBY'), ('AL-1994-house-101-R-PRINGLE', 'R', 8223.0, 1, 'Pringle', 'ALPERSON-PRINGLE'), )),
    ('house', 102): Contest(
        before=(('AL-1994-house-102-D-TURNER', 'D', 7192.0, 1, 'Turner', 'ALPERSON-TURNER'), ),
        after=(('AL-1994-house-102-R-TURNER', 'R', 7192.0, 1, 'Turner', 'ALPERSON-TURNER'), )),
    ('house', 103): Contest(
        before=(('AL-1994-house-103-D-MITCHELL', 'D', 4915.0, 1, 'Mitchell', 'ALPERSON-MITCHELL'), ('AL-1994-house-103-R-GARDNER', 'R', 1227.0, 0, 'Gardner', 'ALPERSON-GARDNER'), ),
        after=(('AL-1994-house-103-D-MITCHELL', 'D', 4915.0, 1, 'Mitchell', 'ALPERSON-MITCHELL'), )),
    ('senate', 11): Contest(
        before=(('AL-1994-senate-11-D-SPRAYBERRY', 'D', 30774.0, 1, 'Sprayberry', 'ALPERSON-SPRAYBERRY'), ),
        after=(('AL-1994-senate-11-D-SPRAYBERRY', 'D', 13528.0, 0, 'Sprayberry', 'ALPERSON-SPRAYBERRY'), ('AL-1994-senate-11-R-HILL', 'R', 17246.0, 1, 'Hill', 'ALPERSON-HILL--1994-SENATE-11'), )),
    ('senate', 15): Contest(
        before=(('AL-1994-senate-15-D-AMARI', 'D', 32505.0, 1, 'Amari', 'ALPERSON-AMARI'), ),
        after=(('AL-1994-senate-15-R-AMARI', 'R', 32505.0, 1, 'Amari', 'ALPERSON-AMARI'), )),
    ('senate', 16): Contest(
        before=(('AL-1994-senate-16-D-WAGGONER', 'D', 42672.0, 1, 'Waggoner', 'ALPERSON-WAGGONER'), ),
        after=(('AL-1994-senate-16-R-WAGGONER', 'R', 42672.0, 1, 'Waggoner', 'ALPERSON-WAGGONER'), )),
    ('senate', 17): Contest(
        before=(('AL-1994-senate-17-D-BIDDLE', 'D', 28720.0, 1, 'Biddle', 'ALPERSON-BIDDLE'), ),
        after=(('AL-1994-senate-17-R-BIDDLE', 'R', 28720.0, 1, 'Biddle', 'ALPERSON-BIDDLE'), )),
    ('senate', 18): Contest(
        before=(('AL-1994-senate-18-D-SMITHERMAN', 'D', 19558.0, 1, 'Smitherman', 'ALPERSON-SMITHERMAN'), ('AL-1994-senate-18-R-HORN', 'R', 6649.0, 0, 'Horn', 'ALPERSON-HORN'), ),
        after=(('AL-1994-senate-18-D-SMITHERMAN', 'D', 19558.0, 1, 'Smitherman', 'ALPERSON-SMITHERMAN'), )),
    ('senate', 23): Contest(
        before=(('AL-1994-senate-23-D-SANDERS', 'D', 16678.0, 1, 'Sanders', 'ALPERSON-SANDERS'), ('AL-1994-senate-23-R-CURL', 'R', 2201.0, 0, 'Curl', 'ALPERSON-CURL'), ),
        after=(('AL-1994-senate-23-D-SANDERS', 'D', 16678.0, 1, 'Sanders', 'ALPERSON-SANDERS'), )),
    ('senate', 25): Contest(
        before=(('AL-1994-senate-25-D-ANDERSON', 'D', 29440.0, 1, 'Anderson', 'ALPERSON-ANDERSON'), ('AL-1994-senate-25-R-DIXON', 'R', 4578.0, 0, 'Dixon', 'ALPERSON-DIXON'), ),
        after=(('AL-1994-senate-25-R-DIXON', 'R', 32550.0, 1, 'Dixon', 'ALPERSON-DIXON'), )),
    ('senate', 31): Contest(
        before=(('AL-1994-senate-31-D-ADAMS', 'D', 29700.0, 1, 'Adams', 'ALPERSON-ADAMS'), ),
        after=(('AL-1994-senate-31-D-ELLIS', 'D', 14812.0, 0, 'Ellis', 'ALPERSON-ELLIS'), ('AL-1994-senate-31-R-ADAMS', 'R', 14888.0, 1, 'Adams', 'ALPERSON-ADAMS'), )),
}


# A new 1994 row whose name-derived person_id ("ALPERSON-" + surname, the identity
# build's rule) is already held by a different 1994 contest gets a stable,
# district-qualified person_id instead, so the repair never merges two 1994 people.
# "--" cannot occur in a name-derived id. Canonical candidate IDs are unchanged.
DISAMBIGUATED_PERSON_IDS = {
    "AL-1994-house-51-D-ROGERS": ("ALPERSON-ROGERS", "ALPERSON-ROGERS--1994-HOUSE-51"),
    "AL-1994-house-92-R-MARTIN": ("ALPERSON-MARTIN", "ALPERSON-MARTIN--1994-HOUSE-92"),
    "AL-1994-senate-11-R-HILL": ("ALPERSON-HILL", "ALPERSON-HILL--1994-SENATE-11"),
}


def name_person_id(name: str) -> str:
    return "ALPERSON-" + re.sub(r"[^A-Z0-9]+", "-", normalize_name(name)).strip("-")


def adjudication_ids() -> list[str]:
    seen: list[str] = []
    for target in SOURCE_TARGETS:
        if target.adjudication_id not in seen:
            seen.append(target.adjudication_id)
    return seen


def contest_adjudication(chamber: str, district: int) -> str:
    prefix = f"ADJ-1994-AL-{'HD' if chamber == 'house' else 'SD'}{district:03d}-"
    matches = [a for a in adjudication_ids() if a.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"No unique adjudication for {chamber} {district}: {matches}")
    return matches[0]


def set_id(chamber: str, district: int) -> str:
    return f"ALCANON-{YEAR}-{chamber}-{district}"


def supersession_rows() -> list[dict]:
    """Derive old -> new canonical IDs from the contest before/after images."""
    rows = []
    for (chamber, district), contest in CONTESTS.items():
        adjudication = contest_adjudication(chamber, district)
        after_by_id = {r[0]: r for r in contest.after}
        after_by_person = {r[5]: r for r in contest.after}
        claimed = set()
        for old in contest.before:
            new = after_by_id.get(old[0])
            if new is None and old[5] in after_by_person:
                new = after_by_person[old[5]]
            if new is None:
                action = "retired"
            elif new[0] == old[0]:
                if (new[2], new[3]) == (old[2], old[3]):
                    continue
                action = "votes_corrected_same_id"
            else:
                action = "rekeyed_party_relabel" if (new[2], new[3]) == (old[2], old[3]) else \
                    "rekeyed_party_relabel_votes_corrected"
            if new is not None:
                claimed.add(new[0])
            rows.append({"old_canonical_candidate_id": old[0], "new_canonical_candidate_id": new[0] if new else "",
                         "action": action, "chamber": chamber, "district": district, "candidate_name": old[4],
                         "party_before": old[1], "party_after": new[1] if new else "",
                         "votes_before": int(old[2]), "votes_after": int(new[2]) if new else "",
                         "winner_before": old[3], "winner_after": new[3] if new else "",
                         "person_id_before": old[5], "person_id_after": new[5] if new else "",
                         "adjudication_id": adjudication})
        for new in contest.after:
            if new[0] not in claimed and new[0] not in {r[0] for r in contest.before}:
                rows.append({"old_canonical_candidate_id": "", "new_canonical_candidate_id": new[0], "action": "new_row",
                             "chamber": chamber, "district": district, "candidate_name": new[4],
                             "party_before": "", "party_after": new[1], "votes_before": "", "votes_after": int(new[2]),
                             "winner_before": "", "winner_after": new[3], "person_id_before": "",
                             "person_id_after": new[5], "adjudication_id": adjudication})
    return rows


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def digest_rows(rows) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, default=str).encode("utf-8")); digest.update(b"\n")
    return digest.hexdigest()


def read_manual_records(root: Path) -> dict:
    """Check the reviewed adjudication and supersession records against this script."""
    adjudication_path, supersession_path = root / ADJUDICATIONS_CSV, root / SUPERSESSION_CSV
    for path, expected in ((adjudication_path, ADJUDICATIONS_SHA256), (supersession_path, SUPERSESSION_SHA256)):
        if normalized_sha256(path) != expected:
            raise ValueError(f"Reviewed record changed: {path.relative_to(root).as_posix()}")
    with adjudication_path.open(encoding="utf-8", newline="") as stream:
        adjudications = list(csv.DictReader(stream))
    with supersession_path.open(encoding="utf-8", newline="") as stream:
        supersession = list(csv.DictReader(stream))
    if [row["adjudication_id"] for row in adjudications] != adjudication_ids():
        raise ValueError("Adjudication record does not list exactly this script's adjudications")
    keys = ("old_canonical_candidate_id", "new_canonical_candidate_id", "action", "adjudication_id",
            "person_id_after")
    if [tuple(r[k] for k in keys) for r in supersession] != [tuple(str(r[k]) for k in keys) for r in supersession_rows()]:
        raise ValueError("Supersession record does not match the contest before/after images")
    return {"adjudications": adjudications, "supersession": supersession,
            "hashes": {ADJUDICATIONS_CSV: ADJUDICATIONS_SHA256, SUPERSESSION_CSV: SUPERSESSION_SHA256}}


def manual_reference_report(root: Path) -> dict:
    """Classify manual-file references to superseded IDs; re-keyed references block application."""
    mapping = {r["old_canonical_candidate_id"]: r for r in supersession_rows() if r["old_canonical_candidate_id"]}
    rekeyed = {old for old, r in mapping.items() if r["new_canonical_candidate_id"] and r["new_canonical_candidate_id"] != old}
    retired = {old for old, r in mapping.items() if not r["new_canonical_candidate_id"]}
    pattern = re.compile(r"AL-1994-(?:house|senate)-\d+-[A-Z]-[A-Z0-9-]+")
    report = {"rekeyed_references": {}, "retired_references": {}}
    skip = {(root / ADJUDICATIONS_CSV).resolve(), (root / SUPERSESSION_CSV).resolve()}
    for path in sorted((root / MANUAL_DIR).rglob("*.csv")):
        if path.resolve() in skip:
            continue
        found = pattern.findall(path.read_text(encoding="utf-8", errors="replace"))
        relative = path.relative_to(root).as_posix()
        for kind, ids in (("rekeyed_references", rekeyed), ("retired_references", retired)):
            hits = sorted({i for i in found if i in ids})
            if hits:
                report[kind][relative] = hits
    return report


def evidence_files(root: Path) -> list[dict]:
    files = []
    archive = root / PRECINCT_ARCHIVE
    if file_sha256(archive) != PRECINCT_ARCHIVE_SHA256:
        raise ValueError(f"Precinct archive hash changed: {PRECINCT_ARCHIVE}")
    for spec in EVIDENCE_REGISTRATIONS:
        path = root / spec["path"]
        if file_sha256(path) != spec["sha256"]:
            raise ValueError(f"Evidence file hash changed: {spec['path']}")
        files.append({**spec, "source_file_id": source_file_id(spec["provider"], spec["path"])})
    return files


def _target_rows(connection, target: SourceTarget):
    where = ["year=?", "source='alabama_sos'", "source_file_id=?", "ballot_code=?"]
    params: list = [YEAR, PRECINCT_SOURCE_ID, target.ballot_code]
    if target.office is not None:
        where.append("office=?"); params.append(target.office)
    if target.county_key is not None:
        where.append("county_key=?"); params.append(target.county_key)
    return connection.execute(
        f"""SELECT rowid, source_file, source_column, county_key, office, district, candidate, party,
                   party_norm, party_method, votes FROM {VOTES} WHERE {' AND '.join(where)} ORDER BY rowid""",
        params).fetchall()


def _same_district(value, expected) -> bool:
    return value is None if expected is None else value is not None and float(value) == float(expected)


def _target_state(target: SourceTarget, rows) -> str:
    before = (target.party_before, norm_party(target.party_before), BEFORE_METHOD)
    after = (target.party_after, norm_party(target.party_after), target.method_after or BEFORE_METHOD)
    district_after = target.district_after if target.district_after is not None else target.district_before
    states = set()
    for row in rows:
        labels = (row[7], row[8], row[9])
        if target.office is None:
            district_ok_before = district_ok_after = True
        else:
            district_ok_before = _same_district(row[5], target.district_before)
            district_ok_after = _same_district(row[5], district_after)
        if labels == before and district_ok_before:
            states.add("before")
        elif labels == after and district_ok_after:
            states.add("after")
        else:
            states.add("drift")
    return states.pop() if len(states) == 1 else "drift"


def stage_sources(connection) -> list[dict]:
    staged = []
    for target in SOURCE_TARGETS:
        rows = _target_rows(connection, target)
        columns = {(r[1], r[2]) for r in rows}
        state = _target_state(target, rows) if rows else "drift"
        observed = (len(columns), len(rows), sum(float(r[10]) for r in rows))
        if observed != (target.columns, target.rows, target.votes):
            state = "drift"
        per_column = {}
        for row in rows:
            entry = per_column.setdefault((row[1], row[2]), {
                "source_file": row[1], "source_column": row[2], "county_key": row[3], "office": row[4],
                "district": row[5], "candidate": row[6], "party": row[7], "party_method": row[9],
                "rowids": [], "votes": 0.0})
            entry["rowids"].append(row[0]); entry["votes"] += float(row[10])
        staged.append({"target": asdict(target), "state": state, "observed": observed,
                       "columns": sorted(per_column.values(), key=lambda c: (c["source_file"], c["source_column"]))})
    return staged


def _canonical_rows(connection, chamber: str, district: int):
    return connection.execute(
        f"""SELECT canonical_candidate_id, canonical_party, canonical_votes, winner, canonical_name, person_id,
                   canonical_source, incumbent FROM {CANONICAL} WHERE year=? AND chamber=? AND district=?""",
        (YEAR, chamber, district)).fetchall()


def _as_image(rows) -> list:
    return sorted((r[0], r[1], float(r[2]), int(r[3]), r[4], r[5]) for r in rows)


def _materialized_rows(connection, chamber: str, district: int):
    return connection.execute(
        f"""SELECT candidate_result_id, party_original, votes, vote_share, candidate_name
            FROM {MATERIALIZED} WHERE observation_set_id=?""", (set_id(chamber, district),)).fetchall()


def _materialized_image(contest_rows) -> list:
    total = sum(r[2] for r in contest_rows)
    return sorted((r[0], r[1], int(r[2]), round(r[2] / total, 9) if total else None, r[4]) for r in contest_rows)


def stage_canonical(connection) -> list[dict]:
    staged = []
    for (chamber, district), contest in CONTESTS.items():
        rows = _canonical_rows(connection, chamber, district)
        image = _as_image(rows)
        conformant = all(r[6] == "alabama_sos" and int(r[7]) == 0 for r in rows)
        state = ("before" if image == sorted(contest.before) else
                 "after" if image == sorted(contest.after) else "drift")
        materialized = sorted((r[0], r[1], int(r[2]), round(r[3], 9) if r[3] is not None else None, r[4])
                              for r in _materialized_rows(connection, chamber, district))
        m_state = ("before" if materialized == _materialized_image(contest.before) else
                   "after" if materialized == _materialized_image(contest.after) else "drift")
        if not conformant:
            state = "drift"
        staged.append({"chamber": chamber, "district": district, "state": state, "materialized_state": m_state,
                       "adjudication_id": contest_adjudication(chamber, district),
                       "canonical_current": image, "materialized_current": materialized,
                       "before": list(contest.before), "after": list(contest.after)})
    return staged


def stage_person_ids(connection) -> list[dict]:
    """Check that no new 1994 person shares a person_id with another 1994 contest.

    Re-keyed and unchanged rows keep their existing person_id, including
    pre-existing surname merges, which this repair does not touch. A new
    person takes its name-derived id unless a different 1994 contest already
    holds it; then it takes the reviewed district-qualified id.
    """
    holders: dict = {}
    for chamber, district, person in connection.execute(
            f"SELECT chamber, district, person_id FROM {CANONICAL} WHERE year=?", (YEAR,)):
        if (chamber, int(district)) not in CONTESTS:
            holders.setdefault(person, set()).add((chamber, int(district)))
    for key, contest in CONTESTS.items():
        for row in contest.after:
            holders.setdefault(row[5], set()).add(key)
    staged = []
    for key, contest in CONTESTS.items():
        carried = {row[5] for row in contest.before}
        for cid, _, _, _, name, person in contest.after:
            if person in carried:
                continue
            name_id = name_person_id(name)
            elsewhere = sorted(holders.get(name_id, set()) - {key})
            if sorted(holders.get(person, set()) - {key}):
                raise ValueError(f"Person ID collision: {cid} {person} is held by another 1994 contest")
            expected = DISAMBIGUATED_PERSON_IDS.get(cid)
            if expected is not None and (expected != (name_id, person) or not elsewhere):
                raise ValueError(f"Unjustified person ID qualification: {cid} {person}")
            if expected is None and (person != name_id or elsewhere):
                raise ValueError(f"New 1994 person needs a reviewed qualified ID: {cid} {name_id} {elsewhere}")
            staged.append({"canonical_candidate_id": cid, "person_id": person, "name_person_id": name_id,
                           "name_person_id_held_by": [f"{c}-{d}" for c, d in elsewhere]})
    return staged


def simulate_canonical(connection) -> dict:
    """Recompute affected contests from corrected source rows with the identity-build rule."""
    keys = {(c, d) for c, d in CONTESTS}
    rows = connection.execute(
        f"""SELECT rowid, office, district, candidate_key, party_norm, votes FROM {VOTES}
            WHERE year=? AND source='alabama_sos' AND office IN ('State House','State Senate')""", (YEAR,)).fetchall()
    updates = {}
    for target in SOURCE_TARGETS:
        district_after = target.district_after if target.district_after is not None else None
        for row in _target_rows(connection, target):
            updates[row[0]] = (norm_party(target.party_after), district_after)
    aliases: dict = {}
    for rowid, office, district, candidate_key, party_norm, votes in rows:
        if rowid in updates:
            party_norm = updates[rowid][0]
            if updates[rowid][1] is not None:
                district = updates[rowid][1]
        if district is None:
            continue
        chamber = "house" if office == "State House" else "senate"
        if (chamber, int(district)) not in keys:
            continue
        alias = aliases.setdefault((chamber, int(district), candidate_key), {"parties": [], "votes": 0.0})
        alias["parties"].append(party_norm); alias["votes"] += float(votes)
    totals: dict = {}
    for (chamber, district, _), alias in aliases.items():
        party = next((p for p in alias["parties"] if p in {"D", "R"}), "O")
        if party in {"D", "R"}:
            totals[(chamber, district, party)] = totals.get((chamber, district, party), 0.0) + alias["votes"]
    mismatches = []
    for (chamber, district), contest in CONTESTS.items():
        expected = sorted((r[1], r[2]) for r in contest.after)
        observed = sorted((p, v) for (c, d, p), v in totals.items() if (c, d) == (chamber, district))
        if expected != observed:
            mismatches.append({"contest": f"{chamber}-{district}", "expected": expected, "observed": observed})
    return {"mismatches": mismatches}


def seat_summary(connection, which: str) -> dict:
    """1994 seats won by party and D-vs-R contests, current or after the repair."""
    rows = connection.execute(f"SELECT chamber, district, canonical_party, canonical_votes, winner FROM {CANONICAL} WHERE year=?",
                              (YEAR,)).fetchall()
    contests: dict = {}
    for chamber, district, party, votes, winner in rows:
        contests.setdefault((chamber, int(district)), []).append((party, float(votes), int(winner)))
    if which == "after":
        for key, contest in CONTESTS.items():
            contests[key] = [(r[1], r[2], r[3]) for r in contest.after]
    seats: dict = {}
    contested = []
    for (chamber, district), contest in contests.items():
        for party, _, winner in contest:
            if winner:
                seats.setdefault(chamber, {}).setdefault(party, 0)
                seats[chamber][party] += 1
        parties = [p for p, v, _ in contest if v > 0]
        if parties.count("D") == 1 and parties.count("R") == 1:
            contested.append(f"{chamber}-{district}")
    return {"seats": seats, "dr_contests": sorted(contested)}


def stage(connection, root: Path) -> dict:
    records = read_manual_records(root)
    files = evidence_files(root)
    sources = stage_sources(connection)
    canonical = stage_canonical(connection)
    persons = stage_person_ids(connection)
    adjudications = {r[0] for r in connection.execute(
        f"SELECT adjudication_id FROM {ADJUDICATION} WHERE adjudication_id LIKE 'ADJ-1994-AL-%'")}
    registered = {r[0]: r[1] for r in connection.execute(
        f"SELECT source_file_id, sha256 FROM {SOURCES} WHERE source_file_id IN ({','.join('?' for _ in files)})",
        [f["source_file_id"] for f in files])}
    for spec in files:
        if spec["source_file_id"] in registered and registered[spec["source_file_id"]] != spec["sha256"]:
            raise ValueError(f"Registered evidence hash differs: {spec['path']}")
    precinct = connection.execute(f"SELECT sha256 FROM {SOURCES} WHERE source_file_id=?", (PRECINCT_SOURCE_ID,)).fetchone()
    if not precinct or precinct[0] != PRECINCT_ARCHIVE_SHA256:
        raise ValueError("The 1994 precinct archive registration does not match the reviewed archive")
    states = ({s["state"] for s in sources} | {c["state"] for c in canonical} |
              {c["materialized_state"] for c in canonical})
    expected_adjudications = set(adjudication_ids())
    if states == {"before"} and not (adjudications & expected_adjudications):
        overall = "pending"
    elif states == {"after"} and expected_adjudications <= adjudications:
        overall = "applied"
    else:
        drift = ([f"source {s['target']['adjudication_id']} {s['target']['ballot_code']}: {s['state']} {s['observed']}"
                  for s in sources if s["state"] != "before"] +
                 [f"canonical {c['chamber']}-{c['district']}: {c['state']}/{c['materialized_state']}"
                  for c in canonical if (c["state"], c["materialized_state"]) != ("before", "before")])
        raise ValueError("Before-image mismatch (partial or drifted state): " + "; ".join(drift[:20]))
    simulation = simulate_canonical(connection) if overall == "pending" else {"mismatches": []}
    if simulation["mismatches"]:
        raise ValueError(f"Corrected source rows do not reproduce the reviewed canonical rows: {simulation['mismatches']}")
    template = {}
    columns = [d[1] for d in connection.execute(f"PRAGMA table_info({MATERIALIZED})")]
    for chamber in ("house", "senate"):
        row = connection.execute(
            f"SELECT * FROM {MATERIALIZED} WHERE observation_set_id LIKE ? AND cycle=? AND source_family='alabama_canonical' ORDER BY rowid LIMIT 1",
            (f"ALCANON-{YEAR}-{chamber}-%", YEAR)).fetchone()
        if row is None:
            raise ValueError(f"No materialized 1994 {chamber} template row")
        template[chamber] = dict(zip(columns, row))
        if template[chamber]["authority_rank"] != 5 or template[chamber]["state_code"] != "AL":
            raise ValueError("Unexpected materialized Alabama canonical template")
    return {"state": overall, "records": records, "files": files, "registered": sorted(registered),
            "sources": sources, "canonical": canonical, "adjudications_present": sorted(adjudications & expected_adjudications),
            "template": template, "template_columns": columns, "person_ids": persons,
            "manual_references": manual_reference_report(root)}


def summarize(staged: dict, connection) -> dict:
    sources = staged["sources"]
    rows = sum(s["observed"][1] for s in sources)
    columns = sum(s["observed"][0] for s in sources)
    canonical = staged["canonical"]
    supersession = supersession_rows()
    actions: dict = {}
    for row in supersession:
        actions[row["action"]] = actions.get(row["action"], 0) + 1
    before, after = seat_summary(connection, "current"), seat_summary(connection, "after")
    return {"source_targets": len(sources), "source_columns": columns, "source_rows": rows,
            "contests": len(canonical), "canonical_rows_before": sum(len(c["before"]) for c in canonical),
            "canonical_rows_after": sum(len(c["after"]) for c in canonical), "supersession_actions": actions,
            "adjudications": len(adjudication_ids()), "seats_current": before["seats"], "seats_after": after["seats"],
            "dr_contests_current": len(before["dr_contests"]), "dr_contests_after": len(after["dr_contests"]),
            "war_universe_enter": sorted(set(after["dr_contests"]) - set(before["dr_contests"])),
            "war_universe_leave": sorted(set(before["dr_contests"]) - set(after["dr_contests"])),
            "new_people": len(staged["person_ids"]),
            "person_id_qualifications": [p for p in staged["person_ids"] if p["person_id"] != p["name_person_id"]],
            "manual_references": staged["manual_references"]}


def print_proposal(staged: dict, summary: dict) -> None:
    print(f"State: {staged['state']}")
    print("\nSource columns (vote_observations; every changed column, before -> after):")
    for source in staged["sources"]:
        t = source["target"]
        for column in source["columns"]:
            print(f"  {t['adjudication_id']} {column['source_file']} col {column['source_column']} {t['ballot_code']} "
                  f"{column['candidate']}: party {column['party']!r}->{t['party_after']!r} "
                  f"district {column['district']}->{t['district_after'] if t['district_after'] is not None else column['district']} "
                  f"method {column['party_method']}->{t['method_after'] or column['party_method']} "
                  f"({len(column['rowids'])} rows, {column['votes']:.0f} votes)")
    print("\nCanonical and materialized rows (id, party, votes, winner, name, person_id):")
    for contest in staged["canonical"]:
        print(f"  {contest['adjudication_id']} {contest['chamber']} {contest['district']}")
        for row in contest["before"]:
            print(f"    - {row}")
        for row in contest["after"]:
            print(f"    + {row}")
    print("\nSummary:")
    print(json.dumps(summary, indent=2, default=str))


def authorize(action, table, column, database, trigger):
    if action in (sqlite3.SQLITE_READ, sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION):
        return sqlite3.SQLITE_OK
    if trigger:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if table in OWNED_INSERT else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_DELETE:
        return sqlite3.SQLITE_OK if table in OWNED_DELETE else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_UPDATE:
        if table == VOTES and column in VOTE_COLUMNS:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_OK if table == BUILD else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE,
                  sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW, sqlite3.SQLITE_CREATE_TRIGGER,
                  sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_INDEX,
                  sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _available(connection) -> set:
    return {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def control_snapshot(connection) -> dict:
    available = _available(connection)
    return {n: digest_rows(connection.execute(f'SELECT * FROM "{n}" ORDER BY rowid'))
            for n in (*CONTROL_TABLES, *UNOWNED_TABLES) if n in available}


def counts(connection) -> dict:
    available = _available(connection)
    return {n: connection.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
            for n in (VOTES, CANONICAL, MATERIALIZED, *CONTROL_TABLES) if n in available}


def _contest_clause() -> tuple[str, list]:
    keys = list(CONTESTS)
    clause = " OR ".join("(chamber=? AND district=?)" for _ in keys)
    return f"NOT (year={YEAR} AND ({clause}))", [v for key in keys for v in key]


def canonical_others_digest(connection) -> str:
    clause, params = _contest_clause()
    return digest_rows(connection.execute(f"SELECT * FROM {CANONICAL} WHERE {clause} ORDER BY rowid", params))


def materialized_others_digest(connection) -> str:
    sets = [set_id(c, d) for c, d in CONTESTS]
    return digest_rows(connection.execute(
        f"SELECT * FROM {MATERIALIZED} WHERE observation_set_id NOT IN ({','.join('?' for _ in sets)}) ORDER BY rowid", sets))


def votes_others_digest(connection, rowids: set) -> str:
    digest = hashlib.sha256()
    for row in connection.execute(f"SELECT rowid, * FROM {VOTES} ORDER BY rowid"):
        if row[0] in rowids:
            continue
        digest.update(json.dumps(row, default=str).encode("utf-8")); digest.update(b"\n")
    return digest.hexdigest()


def votes_scope_digest(connection) -> str:
    return digest_rows(connection.execute(
        f"SELECT rowid, * FROM {VOTES} WHERE year=? AND source='alabama_sos' ORDER BY rowid", (YEAR,)))


def _write_sources(connection, staged: dict, run: str) -> int:
    updated = 0
    for source in staged["sources"]:
        t = source["target"]
        party_after = t["party_after"]
        for column in source["columns"]:
            district_after = t["district_after"] if t["district_after"] is not None else column["district"]
            method_after = t["method_after"] or column["party_method"]
            for rowid in column["rowids"]:
                cursor = connection.execute(
                    f"""UPDATE {VOTES} SET party=?, party_norm=?, party_method=?, district=?
                        WHERE rowid=? AND year=? AND source='alabama_sos' AND ballot_code=? AND party=?
                          AND party_method=? AND district IS ?""",
                    (party_after, norm_party(party_after), method_after, district_after, rowid, YEAR,
                     t["ballot_code"], column["party"], column["party_method"], column["district"]))
                if cursor.rowcount != 1:
                    raise ValueError(f"Guarded source update mismatch at rowid {rowid}")
                updated += 1
    return updated


def _write_canonical(connection, staged: dict, run: str, timestamp: str) -> None:
    columns = staged["template_columns"]
    for contest in staged["canonical"]:
        chamber, district = contest["chamber"], contest["district"]
        removed = connection.execute(f"DELETE FROM {CANONICAL} WHERE year=? AND chamber=? AND district=?",
                                     (YEAR, chamber, district)).rowcount
        if removed != len(contest["before"]):
            raise ValueError(f"Guarded canonical delete mismatch: {chamber} {district}")
        for cid, party, votes, winner, name, person in contest["after"]:
            connection.execute(
                f"""INSERT INTO {CANONICAL} (year, chamber, district, canonical_party, canonical_votes, canonical_name,
                    canonical_source, person_id, canonical_candidate_id, incumbent, winner)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (YEAR, chamber, district, party, float(votes), name, "alabama_sos", person, cid, 0, int(winner)))
        removed = connection.execute(f"DELETE FROM {MATERIALIZED} WHERE observation_set_id=?",
                                     (set_id(chamber, district),)).rowcount
        if removed != len(contest["before"]):
            raise ValueError(f"Guarded materialized delete mismatch: {chamber} {district}")
        total = sum(r[2] for r in contest["after"])
        for cid, party, votes, winner, name, person in contest["after"]:
            row = dict(staged["template"][chamber])
            row.update({"candidate_result_id": cid, "observation_set_id": set_id(chamber, district), "build_run_id": run,
                        "district": str(district), "candidate_name": name, "candidate_name_original": name,
                        "party_family": "democratic" if party == "D" else "republican", "party_original": party,
                        "votes": int(votes), "vote_share": votes / total, "as_of_utc": timestamp})
            connection.execute(f"INSERT INTO {MATERIALIZED} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                               [row[c] for c in columns])


def _write_records(connection, staged: dict, run: str, timestamp: str, authorized_by: str) -> None:
    for spec in staged["files"]:
        if spec["source_file_id"] in staged["registered"]:
            continue
        connection.execute(
            f"""INSERT INTO {SOURCES} (source_file_id, provider, local_path, original_url, retrieved_at_utc, sha256,
                media_type, license, extraction_status, authoritative_scope) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (spec["source_file_id"], spec["provider"], spec["path"], spec["original_url"], None, spec["sha256"],
             spec["media_type"], None, "registered", spec["authoritative_scope"]))
    for record in staged["records"]["adjudications"]:
        subject = (f"AL-{YEAR}-{record['chamber']}-{record['district']}" if record["chamber"]
                   else f"AL-{YEAR}-source-{record['adjudication_id'].split('-', 3)[3]}")
        evidence = {key: record[key] for key in record if key not in {"rationale", "decision"}}
        evidence.update({"record": ADJUDICATIONS_CSV, "record_sha256": ADJUDICATIONS_SHA256, "audit": AUDIT,
                         "task": TASK, "build_run_id": run, "authorized_by": authorized_by})
        connection.execute(
            f"""INSERT INTO {ADJUDICATION} (adjudication_id, domain, subject_type, subject_id, decision, rationale,
                evidence_locator, review_status, decided_at_utc, supersedes_adjudication_id) VALUES (?,?,?,?,?,?,?,?,?,NULL)""",
            (record["adjudication_id"], "elections_source_canonical",
             "canonical_contest" if record["chamber"] else "vote_observation_contest", subject, record["decision"],
             record["rationale"], json.dumps(evidence, sort_keys=True), "approved", timestamp))


def repair(database: Path, *, apply: bool = False, expected_run: str | None = None, backup: Path | None = None,
           authorized_by: str | None = None, root: Path = ROOT) -> dict:
    database = database.resolve()
    if apply and (not expected_run or backup is None or not authorized_by):
        raise ValueError("Application requires --expected-run, --backup and --authorized-by")
    if not database.is_file():
        raise FileNotFoundError(database)
    report_path = None
    if apply:
        backup = backup.resolve(); report_path = backup.with_name(backup.name + ".application.json")
        if backup == database or backup.exists() or report_path.exists():
            raise FileExistsError("Backup and application report require new separate paths")
    mode = "rw" if apply else "ro"
    with closing(sqlite3.connect(database.as_uri() + f"?mode={mode}", uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if not apply:
            connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        try:
            latest = connection.execute(f"SELECT build_run_id FROM {BUILD} ORDER BY rowid DESC LIMIT 1").fetchone()
            latest = latest[0] if latest else None
            if expected_run is not None and expected_run != latest:
                raise ValueError(f"Warehouse snapshot changed: expected {expected_run}, found {latest}")
            staged = stage(connection, root)
            summary = summarize(staged, connection)
            if staged["state"] == "applied":
                connection.rollback()
                return {"warehouse_status": "unchanged", "latest_run": latest, "summary": summary}
            if not apply:
                connection.rollback()
                return {"warehouse_status": "dry_run", "latest_run": latest, "staged": staged, "summary": summary}
            if summary["manual_references"]["rekeyed_references"]:
                raise ValueError(f"Manual files reference re-keyed IDs: {summary['manual_references']['rekeyed_references']}")
            if any(r[0] in {VOTES, CANONICAL, MATERIALIZED, *OWNED_INSERT}
                   for r in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Triggers on owned tables require separate review")
            target_rowids = {rowid for s in staged["sources"] for c in s["columns"] for rowid in c["rowids"]}
            before_controls = control_snapshot(connection)
            before_counts = counts(connection)
            before_canonical = canonical_others_digest(connection)
            before_materialized = materialized_others_digest(connection)
            before_votes = votes_others_digest(connection, target_rowids)
            before_scope = votes_scope_digest(connection)
            code_paths = [Path(__file__), Path(__file__).with_name("warehouse.py"), Path(__file__).with_name("oe_normalize.py")]
            application_code = {p.name: file_sha256(p) for p in code_paths}
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, \
                    closing(sqlite3.connect(backup)) as destination:
                source.execute("PRAGMA query_only=ON"); source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup quick_check failed")
                if (control_snapshot(destination) != before_controls or votes_scope_digest(destination) != before_scope
                        or canonical_others_digest(destination) != before_canonical):
                    raise ValueError("Separate backup validation failed")
            if {p.name: file_sha256(p) for p in code_paths} != application_code:
                raise ValueError("Application code changed during repair")
            connection.set_authorizer(authorize)
            configuration = {"task": TASK, "backup": str(backup), "expected_run": expected_run,
                             "authorized_by": authorized_by, "records": staged["records"]["hashes"], "audit": AUDIT,
                             "precinct_source_file_id": PRECINCT_SOURCE_ID, "klarner_source_file_id": KLARNER_SOURCE_ID,
                             "evidence_files": staged["files"], "application_code_sha256": application_code,
                             "before_counts": before_counts, "before_controls": before_controls,
                             "canonical_digest_outside_contests": before_canonical,
                             "materialized_digest_outside_sets": before_materialized,
                             "votes_digest_outside_targets": before_votes, "summary": summary}
            run = begin_run(connection, TARGET, configuration)
            timestamp = utcnow()
            _write_records(connection, staged, run, timestamp, authorized_by)
            updated = _write_sources(connection, staged, run)
            _write_canonical(connection, staged, run, timestamp)
            # Validation.
            after_staged_sources = stage_sources(connection)
            if {s["state"] for s in after_staged_sources} != {"after"}:
                raise ValueError("Source after-image mismatch")
            after_canonical = stage_canonical(connection)
            if {(c["state"], c["materialized_state"]) for c in after_canonical} != {("after", "after")}:
                raise ValueError("Canonical or materialized after-image mismatch")
            for contest in after_canonical:
                share = connection.execute(f"SELECT ROUND(SUM(vote_share), 9) FROM {MATERIALIZED} WHERE observation_set_id=?",
                                           (set_id(contest["chamber"], contest["district"]),)).fetchone()[0]
                if share != 1.0:
                    raise ValueError(f"Vote shares do not sum to one: {contest['chamber']} {contest['district']}")
            if canonical_others_digest(connection) != before_canonical:
                raise ValueError("Canonical rows outside the adjudicated contests changed")
            if materialized_others_digest(connection) != before_materialized:
                raise ValueError("Materialized rows outside the adjudicated sets changed")
            if votes_others_digest(connection, target_rowids) != before_votes:
                raise ValueError("Vote observations outside the adjudicated columns changed")
            if updated != len(target_rowids):
                raise ValueError("Source update count mismatch")
            details = {"summary": summary, "source_updates": updated, "backup": str(backup),
                       "source_before_images": [{"target": s["target"], "columns": s["columns"]} for s in staged["sources"]],
                       "canonical_before_after": [{k: c[k] for k in ("chamber", "district", "adjudication_id", "before", "after")}
                                                  for c in staged["canonical"]],
                       "supersession": supersession_rows(), "registered_sources": staged["files"],
                       "vote_rule": "precinct-cell sums; official county totals recorded in the adjudication record",
                       "not_rebuilt": NOT_REBUILT,
                       "report_status": "database commit evidence authoritative; report written after commit"}
            connection.execute(f"INSERT INTO {REPAIR} VALUES (?,?,?,?,?,?,?)",
                               ("WQA-1994-PARTY-LABELS-" + run, run, f"{VOTES};{CANONICAL};{MATERIALIZED}",
                                "1994 Alabama general-election party labels and the House 92 district (owner adjudications 2026-10-04)",
                                "repaired_with_adjudication", json.dumps(details, sort_keys=True, default=str), timestamp))
            after_counts = counts(connection)
            delta = summary["canonical_rows_after"] - summary["canonical_rows_before"]
            new_sources = len([f for f in staged["files"] if f["source_file_id"] not in staged["registered"]])
            expected = {VOTES: 0, CANONICAL: delta, MATERIALIZED: delta, BUILD: 1, REPAIR: 1,
                        ADJUDICATION: len(adjudication_ids()), SOURCES: new_sources}
            for table, count in before_counts.items():
                if after_counts[table] != count + expected.get(table, 0):
                    raise ValueError(f"Unexpected row-count change: {table}")
            for table in CONTROL_TABLES:
                if table in before_counts:
                    preserved = digest_rows(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid LIMIT ?',
                                                               (before_counts[table],)))
                    if preserved != before_controls[table]:
                        raise ValueError(f"Prior control rows changed: {table}")
            for table, digest in before_controls.items():
                if table not in CONTROL_TABLES and digest_rows(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')) != digest:
                    raise ValueError(f"Unowned table changed: {table}")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Foreign key violation")
            finish_run(connection, run, {"summary": summary, "source_updates": updated, "not_rebuilt": NOT_REBUILT})
            connection.commit()
        except BaseException:
            connection.rollback(); raise
    report = {"warehouse_status": "committed", "build_run_id": run, "latest_run_before": latest,
              "configuration": {k: v for k, v in configuration.items() if k not in {"before_controls"}},
              "summary": summary}
    try:
        with report_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2, default=str) + "\n")
        report["report_status"] = "written"
    except OSError as exc:
        report["report_status"] = "failed_after_commit"; report["report_error"] = str(exc)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, default=database_path())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-run")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--authorized-by")
    parser.add_argument("--proposal-json", type=Path, help="Write the dry-run proposal (every changed row) to this new file")
    args = parser.parse_args(argv)
    result = repair(args.database, apply=args.apply, expected_run=args.expected_run, backup=args.backup,
                    authorized_by=args.authorized_by)
    if result["warehouse_status"] == "dry_run":
        print_proposal(result["staged"], result["summary"])
        if args.proposal_json:
            with args.proposal_json.open("x", encoding="utf-8") as stream:
                json.dump({k: v for k, v in result["staged"].items() if k != "template"} | {"summary": result["summary"]},
                          stream, indent=1, default=str)
    else:
        print(json.dumps({k: v for k, v in result.items() if k != "staged"}, indent=2, default=str))
    return 1 if result.get("report_status") == "failed_after_commit" else 0


if __name__ == "__main__":
    raise SystemExit(main())
