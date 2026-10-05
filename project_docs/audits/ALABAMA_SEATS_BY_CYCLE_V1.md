# Alabama seats won by party per regular general election, v1 — audit

Task contract: `coordination/ALABAMA-SEATS-BY-CYCLE-20261003.md` (checklist `roadmap-07`).
Run `AL-SEATS-V1-44C73422B2A2A12D733C`, built 2026-10-04T01:59:55Z from git HEAD
`178d6f48` (the script was uncommitted; its SHA-256 is in the manifest). Status: a local
build for the parent's review. It is not published, and nothing consumes it yet.

## Definition

The dataset counts seats won by party at the regular general election: the final-stage
general-election winner of each district. This is not chamber composition at session
start. Special elections and special runoffs, appointments, deaths, resignations and other
later vacancies, and party switches after the general election are excluded, as are
primaries and primary runoffs. Uncontested seats count for the winner's party. If the
warehouse can't determine a district's winner, or other evidence contradicts it, the
district is marked `unknown` and queued for review. A winner is never inferred from a
reference page or filled in silently.

## Sources and method

- **Warehouse** `data/processed/elections/alabama_elections.sqlite`. The build opened it
  read-only (`mode=ro`, `PRAGMA query_only=ON`). Schema version 27. Whole-file SHA-256
  `114725fe…f9475` (5,819,064,320 bytes, mtime 2026-09-15). The latest validated build run
  is `RUN-DFB1D093D7594AB68A264292050E924D`. The manifest also records content digests of
  every query result the build used.
- **Contest selection** comes from `fact_southern_legislative_final_candidate_election`,
  which is the regular-cycle final-stage interface named in `DATA_CONTRACTS.md`. The build
  keeps Alabama rows for 1994–2022 and gets exactly one observation set per
  cycle/chamber/district for all 1,120 districts. Of these sets, 1,056 are Alabama
  canonical and 64 are Klarner gap fills: 1994 HD92; 1998 48 House and 7 Senate; 2006
  HD 1, 2, 3, 5, 18, 24, 86 and SD1.
- **Winner.** The winner is the recorded flag of the selected set:
  `canonical_candidates.winner`, or Klarner's `winner_status` for gap-fill rows. The flag
  must be unique. It must also equal the plurality of the set's named candidates when all
  votes are present. All 1,120 recorded winners passed this check.
- **Cross-check.** Every other general-election warehouse observation of the same contest
  is reduced to the party of its plurality winner. These observations are Klarner (all
  cycles), the certified SOS canvass (2018, 2022) and MEDSL (2018). Write-in aggregates and
  over/under votes are excluded. Any disagreement about the winning party makes the
  district `unknown`.
- **References.** These are the saved pages under `data/raw/`:
  - eight Wikipedia pages in `data/raw/wikipedia/`, which are git-tracked;
  - four Wikipedia saves in `data/raw/alabama_elections_and_geography/`: 2010 House,
    2014 Senate, 2026 House and 2026 Senate;
  - sixteen Ballotpedia index snapshots in `data/raw/ballotpedia/election_indexes/`.

  The build reads seat totals from the Wikipedia infobox ("Seats after/won", and "Last
  election" for the previous cycle) and from Ballotpedia's "After …" composition column.
  For 2010–2022 it also reads the Wikipedia district result tables. A district-table
  contradiction makes a district `unknown` only when an external seat total for that cycle
  and chamber is off from the warehouse count in the same direction. Otherwise the
  contradiction is logged as a non-blocking item. References never supply a winner. No
  reference file has a `warehouse_source_file` row, and none records a license
  (`SOURCE_TERMS_AND_HYGIENE_2026_09_11.md`).
- **Districts.** Each cycle keeps its own reported districts. Every row carries the
  warehouse `district_plan_id` (`AL-<cycle>-<chamber>-reported-unknown-vintage`), and no
  district is relabelled across plans. The warehouse holds no verified plan vintage for
  these rows, and this build does not resolve the 1994 plan-vintage risk.

## Uncontested winners in the warehouse

- The final-stage interface has a contest for every district in all 16 cycle-chamber
  slices: 105 House and 35 Senate per cycle. `qa_southern_legislative_final_competition_coverage`
  agrees.
- `canonical_candidates` holds only D and R rows, so a non-major-party winner can't
  appear in the canonical layer. This is how 2010 SD29 and 2014 SD29 come about. Single-
  candidate canonical contests exist in every cycle except 1998. In 1998 the 57 House and
  28 Senate canonical contests are all D-vs-R. All 48 House and 7 Senate uncontested seats
  for that year exist only as Klarner gap-fill rows.
- The warehouse records `contest_status = unknown` on every Alabama row. The build
  derives the status from positive evidence instead. A contest is `contested` when any
  observation lists two or more named candidates. It is `uncontested` when every
  full-ballot observation lists exactly one named candidate; write-in aggregates don't
  count as opponents. Otherwise the status is `unknown`. The result is 581 contested
  districts, 538 uncontested and 1 unknown (2014 SD29).

## Results (seats won; D / R / other / unknown)

| Cycle | House | Senate |
|---|---|---|
| 1994 | 74 / 18 / 0 / 13 | 23 / 6 / 0 / 6 |
| 1998 | 68 / 36 / 0 / 1 | 23 / 11 / 0 / 1 |
| 2002 | 64 / 41 / 0 / 0 | 25 / 10 / 0 / 0 |
| 2006 | 61 / 43 / 0 / 1 | 22 / 12 / 0 / 1 |
| 2010 | 43 / 62 / 0 / 0 | 12 / 22 / 0 / 1 |
| 2014 | 33 / 72 / 0 / 0 | 8 / 26 / 0 / 1 |
| 2018 | 28 / 77 / 0 / 0 | 8 / 27 / 0 / 0 |
| 2022 | 28 / 77 / 0 / 0 | 8 / 27 / 0 / 0 |

Every row sums to the chamber size. Of the 1,120 districts, 1,095 are `observed` and 25
are `unknown`. Of the observed winners, 1,031 are corroborated by a second warehouse
source. The other 64 rest on Klarner alone: these are the gap fills, and their party
labels have no second source.

## Reconciliation (`reconciliation.csv`, 70 rows)

Deltas are this build minus the reference.

| Cycle / chamber | External page references | Warehouse secondary |
|---|---|---|
| 1994 House | Ballotpedia snapshot is "page does not exist" | Klarner 74/31: consistent with unknowns (R −13) |
| 1994 Senate | Ballotpedia: page not found | Klarner 23/12: consistent (R −6) |
| 1998 House | Ballotpedia: page not found | Klarner 69/36: consistent (D −1); 48 districts selected from Klarner |
| 1998 Senate | Ballotpedia: page not found | Klarner 24/11: consistent (D −1); 7 dependent |
| 2002 House | Ballotpedia page has no seat totals | Klarner 64/41: **match** |
| 2002 Senate | Ballotpedia: no totals | Klarner 25/10: **match** |
| 2006 House | 2010 Wikipedia "Last election" D62 R43 (two saves): consistent (D −1); Ballotpedia is a 120-byte stub | Klarner 62/43: consistent |
| 2006 Senate | Ballotpedia: no totals | Klarner 23/12: consistent (D −1) |
| 2010 House | Wikipedia 62 R / 43 D (2010 page ×2, 2014 "Last election", district tables ×2): **match**. Ballotpedia "After the 2010 Election" D39 R66: **mismatch** (D +4, R −4) | Klarner: match |
| 2010 Senate | Wikipedia 22+1 / 12, Ballotpedia D12 R22 I1, district tables: all consistent (other −1) | Klarner 12/22/1: consistent |
| 2014 House | Wikipedia 72/33 (2014 page, 2018 "Last election"), Ballotpedia ×2: **match**. District tables D41 R64: mismatch, because eight tables reproduce 2010 results | Klarner: match |
| 2014 Senate | Wikipedia 26+1 / 8 (×2, plus 2018 "Last election"), Ballotpedia D8 R26 I1 (×2): consistent (other −1) | Klarner 8/27: consistent |
| 2018 House, Senate | Wikipedia, 2022 "Last election", district tables, Ballotpedia: **match** | Klarner, certified canvass, MEDSL: match |
| 2022 House, Senate | Wikipedia, 2026 "Last election" (House), Ballotpedia: **match**; 2022 House district tables have 3 tables without votes (consistent) | Klarner, certified canvass: match |

Wikipedia lists an independent who caucuses with a party as "N+1" in that party's
column. The build parses the "+1" as an `other` seat and keeps the raw value.

Totals reconciled exactly with an independent reference: 2002 (both chambers, through
Klarner only), 2010 House, 2014 House, 2018 and 2022. Every other total is in the review
queue.

## Open review items (`review_queue.csv`: 51 items, 34 blocking)

**Blocking. District winner conflicts (25 unknown districts).**

- *1994: canonical vs Klarner (13 House, 6 Senate).*
  - Same sole candidate with the same or near-identical votes, but opposite party
    (canonical D, Klarner R): HD 10, 20, 41, 44, 45, 47, 74, 94, 100, 102; SD 15, 16, 17.
  - One canonical D row carries the combined, or nearly combined, D+R Klarner vote:
    HD 51, 91, 101; SD 11, 31. In HD91, Klarner has Moore (R) 5,935 over Spicer (D)
    5,826.
  - SD25: the two sources disagree on candidates and votes.
  - Probable cause (an inference, not established): all 1994 `State House` and
    `State Senate` rows in `vote_observations` carry
    `party_method = ballot_order_with_export_code`. Party was therefore inferred from
    ballot position, so a sole candidate is read as the first-position Democrat. Every
    1994 uncontested Republican in Klarner appears as a Democrat in canonical.
- *Partial canonical totals that reverse Klarner's winner:* 1998 HD35, 1998 SD31,
  2006 HD85 and 2006 SD22. For example, in 2006 SD22 canonical has Lindsey 9,258 vs
  McMillan 9,309, while Klarner has 19,744 vs 16,748.
- *2010 SD29:* Harri Anne Smith (independent, 23,800) is in Klarner and on the Wikipedia
  page but missing from the D/R-only canonical record.
- *2014 SD29:* Harri Anne Smith (independent, 17,830) beat McClendon (R, 16,145) according
  to both Wikipedia saves. Canonical and Klarner both list McClendon alone. The Wikipedia
  infobox and both Ballotpedia pages report one independent seat, which backs the
  conflict.

**Blocking. Totals.**

- *Not reconciled with an independent reference:* 1994 H/S, 1998 H/S, 2006 H/S,
  2010 S and 2014 S.
- *2010 House Ballotpedia mismatch:* 66 R / 39 D against 62 / 43 everywhere else. That
  column is a composition snapshot. A post-election change in party labels would explain
  it, but nothing local establishes that.

**Info.**

- *2014 House district tables (8):* Wikipedia's tables for HD 17, 23, 35, 37, 61, 80, 89
  and 90 match the 2010 page's tables exactly. The totals agree with the warehouse, so
  these winners stand.
- *2010 SD29:* the reference table also contradicts the recorded winner.
- *Winners resting on one source (5):* 1994 House, 1998 House and Senate, 2006 House and
  Senate.
- *No external page reference (2):* 2002 House and Senate.
- *2002 HD27:* this contest has two observation sets in the materialized canonical table.
  This was already documented as F2 in `ALABAMA_2002_MARSHALL_CANONICAL_REVIEW_2026_09_11.md`.
  The sets agree on the winner.

Resolving the blocking district items needs a source adjudication by the
`warehouse_integrator`. That is outside this task, which had no warehouse writes and no
source repairs.

## Limitations

- These are seat totals, not session composition. Mid-term changes are excluded by
  definition.
- 1994, 1998 and the 2006 Senate have no external page with seat totals. Klarner is
  their only comparison, and 64 winners rest on Klarner alone.
- Saved Wikipedia district tables contain stale copies (2014 House), a vandalized row
  (2014 SD13) and tables without votes (2022 House). This is why a district-table
  contradiction alone never withholds a winner.

## Reproduction and verification

```powershell
& .venv/Scripts/python.exe scripts/build_alabama_seats_by_cycle.py
& .venv/Scripts/python.exe -m pytest scripts/tests/test_alabama_seats_by_cycle.py -q
```

- The build took about 28 s, including the whole-file hash.
  `--skip-warehouse-hash --output <dir>` reproduced all four CSVs byte for byte with the
  same run id.
- Tests: 16 passed. That is 14 fixture tests plus 2 contract tests on this run's outputs.
  No testmon or full-suite run was done: the build is a new standalone script, and no
  existing module or input changed.
