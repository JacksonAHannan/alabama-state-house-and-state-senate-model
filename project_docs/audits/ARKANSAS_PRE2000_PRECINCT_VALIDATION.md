# Arkansas pre-2000 precinct staging validation — V2

**Verdict: PASS for experimental panel integration, with source-coverage caveats**

The remediated release resolves both prior blockers. The independent rebuild is byte-identical to the published CSVs, terminal aggregate/report columns no longer enter the precinct table, and every eligible reconciliation row now has complete finite SOS and Klarner party totals.

## Scope and commands

I validated the three official Arkansas workbooks, acquisition provenance, current parser and tests, published staging outputs, and an independent rebuild at the absolute temporary path `.validation_tmp/arkansas_pre2000_v2`.

```powershell
python scripts/build_arkansas_pre2000_precinct_staging.py --output "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\.validation_tmp\arkansas_pre2000_v2"
python -m pytest scripts/tests/test_arkansas_pre2000_precinct_staging.py -q
```

I additionally recomputed observation constraints, district aggregates, reconciliation deltas/tolerances/statuses, eligibility, source and output hashes, and cycle/chamber counts independently with pandas. I ran the rebuild twice to the same absolute path and compared its manifest hash.

## Provenance and deterministic outputs

The current source files match the acquisition records and release manifest:

| Cycle | Bytes | SHA-256 |
|---|---:|---|
| 1994 | 1,160,192 | `828b187f3ad35ce31e6c7af5d974a1449f08cce844f569b3d29b833bf62d32f2` |
| 1996 | 1,682,432 | `cc34766d89d119ba44356013401bebf75d5ec561599a37503fc6bb4243bda2f7` |
| 1998 | 536,721 | `042122238b735e15e2e202daa8c35d548841e7126ab0983208c9679640156248` |

The temporary rebuild produced 66,239 observations, 441 district-candidate rows, 14 coverage rows, 351 reconciliation rows, and 119 eligible rows. All four CSVs are byte-identical to the release outputs:

| Output | SHA-256 |
|---|---|
| observations | `efbcd9f76dd088158f525052ef1d0bd27d50b3d667072947f31b3c66148a50e0` |
| district candidates | `033c16a359922910d32311408356c1e178b4982de60061e6c7c42c0fcb9a6fea` |
| coverage | `eeb8f76110486dabc971e3034a49e55ba1b288d972a530e684d3c753dfd6f26b` |
| reconciliation | `021302b93d8571ba0459ceca1ef9e57226d931c410c3f92860ab4ce1b386f4d2` |

Every manifest row count, byte count, and output hash matches the generated file. Two consecutive builds to the same path produced the same manifest SHA-256, `524c6db1693aefcf5598adc166211d9f27277397619fbc8e6e9ba7ae28a3f8d5`.

## Workbook parsing and observation integrity

- Each source workbook contains 75 county sheets and one aggregate sheet. The 1994 and 1998 `Summary` sheets and 1996 `GRAND TOTALS` sheet remain excluded.
- Parsing now stops at the first exact terminal `TOTAL`, `TOTALS`, or `GRAND TOTAL` header. Exact `SUBTOTAL`/`SUBTOTALS` columns are skipped without stopping the scan, so legitimate later overseas/absentee vote buckets are retained.
- The prior **1994 Union County** pseudo-precinct `AS PER UNION CTY ELEC. COMM.` is absent.
- The prior **1998 Benton County** pseudo-precincts `FINAL REPORT` and `DIFFERENCE` are absent.
- No observation uses `TOTAL`, `TOTALS`, `GRAND TOTAL`, `SUBTOTAL`, `SUBTOTALS`, `FINAL REPORT`, or `DIFFERENCE` as a precinct.
- Overseas/absentee observations remain present in all cycles: 570 rows in 1994, 1,133 in 1996, and 1,127 in 1998.
- Observation keys are unique on state/year/county/precinct/office/district/candidate/party. Votes are all nonnegative integers.
- Re-aggregating observations reproduces all 441 district-candidate rows exactly, including votes, precinct-row counts, and county counts.
- The labeled non-candidate reset remains in place, preventing inheritance across later labeled blocks. No conflicting duplicate source keys were found.

## Statewide context plausibility

The corrected major-party context totals are plausible and move in the expected direction after removal of duplicated report columns:

| Cycle / office | Democratic | Republican |
|---|---:|---:|
| 1994 Governor | 428,576 | 269,909 |
| 1996 President | 469,456 | 323,211 |
| 1996 U.S. Senate | 395,495 | 443,146 |
| 1998 Governor | 271,519 | 419,485 |
| 1998 U.S. Senate | 383,968 | 293,906 |

The remaining incompleteness is documented by the workbooks. For example, the 1996 Phillips sheet says no precinct totals were submitted. Adding its county totals of 5,715 Clinton votes and 2,205 Dole votes to the staged presidential totals gives 475,171 and 325,416. The pipeline correctly does not fabricate precinct allocations for that county.

## Reconciliation and eligibility

I independently reconstructed party totals, deltas, `total_absolute_delta` with two required components, Klarner major votes with two required components, the `max(10 votes, 1% of Klarner major votes)` tolerance, statuses, and eligibility. All values and statuses reproduce with zero disagreement. No eligible row has a missing SOS or Klarner D/R total, and every eligible row is a complete `both` merge within tolerance.

| Cycle | House eligible | Senate eligible | Total |
|---|---:|---:|---:|
| 1994 | 27 | 7 | 34 |
| 1996 | 27 | 6 | 33 |
| 1998 | 45 | 7 | 52 |
| **Total** | **99** | **20** | **119** |

The previously false exact rows with missing Klarner totals are now `missing_one_source` and ineligible. The corrected parser also changes contaminated Benton/Union comparisons as expected.

## Tests

```text
4 passed in 0.62s
```

The focused suite rejects the known aggregate labels and requires complete four-field vote data for every eligible row.

## Approval and caveats

The 119 reconciled rows are approved for **experimental panel integration** under the strict gate. This is not complete Arkansas coverage:

- unopposed contests often lack usable vote observations or an independent Klarner total;
- some county/district combinations are absent from one source;
- Phillips County 1996 has totals but no precinct allocation;
- material mismatches remain explicitly ineligible; and
- the manifest identifies the parser path but does not hash the parser code or Klarner archive. Adding those hashes would improve provenance, though it does not invalidate this independently reproduced release.

Downstream integration must consume only `model_eligible=True` rows and preserve reconciliation and coverage fields.
