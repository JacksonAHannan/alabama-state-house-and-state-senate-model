# Warehouse source repairs — 2026-09-05

Source-confirmed repairs are committed to the central SQLite warehouse. This
is **not** a certification of every observation or dependent output.

## Runs and recovery

- Data repair: `RUN-40A033B9854141F6B05A76173E66D17B`, schema 26, validated.
- Provenance repair: `RUN-C7DE0A0267EC4445938D1CA0CB5C4BD3`, validated.
- Code base: `88878b973fdac3cee95a8d8648da321e38e0021c`, dirty working tree.
  Exact repair-script and adapter hashes are in the data run's configuration;
  provenance-helper/catalog hashes are in the provenance run's configuration.
- Verified pre-repair backup:
  `data/processed/elections/backups/pre-source-repair-2026-09-05.sqlite`
  (5,746,839,552 bytes; ignored by Git). It preserves the original database,
  including removed normalized rows and original geometries. Recovery should
  restore to a separate path and be checked before any warehouse replacement.
- Raw files were not changed. The main repair used one transaction with
  rollback on failed validation, source hashes, source-cell reconciliation, and
  guards against overlapping changes to the repaired observations/geometries.

## Applied repairs

| Audit issue | Applied change | Verification |
|---|---|---|
| WQA-01 | Removed 105 Jefferson 2014 county summaries from additive precinct observations | All 105 retained candidate-row precinct sums equal their printed summary |
| WQA-02 | Reparsed Marshall 2002 using printed metadata headers; excluded its summary column and applied the existing noncandidate filter to the correct candidate field | 2,950 retained cells; 59 printed summaries reconcile; no blank candidate labels |
| WQA-03 | Restored 1994 provider precinct numbers separately from display names; retained archive member, sheet, row, and column lineage | All 150,753 vote cells preserved; 1994 collision groups decrease from 20,228 to 83 |
| WQA-04 | Corrected AG2 export-code parsing in the shared adapter; retained inferred-party method and original code | 3,026 affected party labels corrected; fractional source value remains review evidence |
| WQA-05 | Reloaded Arkansas VEST geometry from the registered archive, repaired polygonal storage after WGS84 conversion | Nine replacements; source result IDs and all result components unchanged; every stored geometry is now valid |
| WQA-06 | Added roll-call category/total reconciliation and complete-roll-call/member-vote views | All 24 conflicts reproduced in the original JSON; member arrays and reported categories exactly match source storage |
| WQA-07 | Masked incomplete finance amounts and ratio in the existing SQL interface, matching its contract | Zero incomplete SQL rows retain numeric features; observed source/race-mart amounts remain intact |
| WQA-08 | Corrected DIME's unsupported retrieval timestamp, three registry grains, and three missing SOS download URLs | DIME retrieval remains unknown; all three remote SOS hashes match the registered files |

Marshall's previous 4,029 malformed rows become 2,950 correctly parsed cells.
The 1,079 excluded rows comprise 79 summary-column cells and 1,000 cells in
write-in/overvote/undervote columns, which the existing adapter contract already
excludes when metadata is parsed correctly. Those observations remain in the
immutable workbook and pre-repair backup. No blanket duplicate deletion was
performed.

The re-read also exposed an overbroad office-name normalization rule. It now
requires an explicit presidency label before classifying a Public Service
Commission office as its presidency. A regression test prevents ordinary
numbered seats from being renamed during future rebuilds.

The ponytail approach kept changes in existing adapters, views, and registry
helpers, with one scoped repair command; no new orchestration framework or
model automation was introduced.

## Source evidence

The [Alabama SOS election-data index](https://www.sos.alabama.gov/alabama-votes/voter/election-data)
links the original downloads used here. On 2026-09-05, streamed copies from
these URLs were hash-verified against the local registered artifacts without
replacing the local files:

- [1994 precinct archive](https://www.sos.alabama.gov/sites/default/files/election-data/2023-06/94g-prec.zip):
  `94512391c389c45d2899f06686484790adaf4c99fa638b217e31f54652c55097`.
- [2002 precinct workbook](https://www.sos.alabama.gov/sites/default/files/election-data/2017-06/2002-GeneralElection-PrecinctLevel_0.xls):
  `9400cfa16da62d303fac0115707ad3f71fc9d29a36f157ac17e0792d2a5ed45e`.
- [2014 precinct archive](https://www.sos.alabama.gov/sites/default/files/election-data/2017-06/2014General-precinctLevel.zip):
  `a4facea99c554d855eabe098305df4f2b73431ec57b64c1c46080abecb725e67`.

`qa_warehouse_source_repair` stores the 164 county-summary checks, geometry
pre/post hashes and source IDs, the 24 raw-JSON discrepancies, restored URLs,
and unresolved/stale scopes. Geometry and LegiScan sources retain their existing
registered archive IDs and terms. The DIME retrieval correction follows
`data/processed/war/dime_finance_build_manifest.json`; registration time is no
longer invented as acquisition time, and omitted registration fields no longer
erase known provenance.

## Remaining review and dependency limitations

- Across all election observations, **5,354** natural-key collision groups
  (**15,035** excess rows at that proposed grain) remain. They are not all
  proven duplicates. `qa_vote_observation_quality` exposes them without
  discarding conflicting or distinct source cells.
- One fractional source value remains. In `94g-prec/MORGAN.XLS`, cells K52 and
  K53 contain differing reported/calculated totals; the fractional observation
  is K48. This supports a source inconsistency, not independent precinct-level
  adjudication. The original value and reconciliation evidence remain visible.
- The 24 LegiScan conflicts are provider contradictions, not fabricated or
  dropped warehouse member votes. New `canonical_legiscan_roll_call` and
  `canonical_legiscan_member_vote` views exclude unreconciled roll calls.
  Existing consumers of the unrestricted source tables are **not** silently
  migrated by this repair.
- Legacy Alabama regional build lineage, missing terms/scope, and old running
  build statuses remain review items where original evidence is insufficient.
- Precinct nodes/fingerprints/links, affected historical weights/baselines,
  Arkansas spatial allocations, and dependent compatibility/publication files
  were **not rebuilt or certified**. `WQA-dependencies` records `stale_review`.
  This ledger entry is not an automatic gate in every legacy consumer. No
  models, forecasts, politician scores, or published scores were recalculated.

## Verification

The committed data run passed SQLite `quick_check`, foreign-key checks, view
compilation, all 164 summary reconciliations, repair-pattern checks, finance
missingness checks, and validity checks on all 53,510 stored geometries.
An additional source replay preserved candidate/county/vote cells exactly in
all 66 unaffected counties of the 2002 workbook.

Fresh targeted tests: **40 passed**, one existing pandas concatenation
`FutureWarning`, in 10.63 seconds:

```powershell
python -m pytest scripts/tests/test_sos_precinct.py scripts/tests/test_warehouse.py scripts/tests/test_data_catalog.py scripts/tests/test_oe_normalize.py scripts/tests/test_warehouse_data_repairs.py scripts/tests/test_southern_2016_vest_warehouse.py -q
```

Read-only post-commit checks confirmed both validated runs, schema 26, complete
1994 source-cell lineage, 83 remaining 1994 collision groups, restored URLs,
and DIME's null acquisition timestamp. The catalog was refreshed to include
98 assets and 93 lineage edges. The full repository suite and a full SQLite
`integrity_check` were not rerun in this repair turn; no whole-project or
downstream-publication validation is claimed.
