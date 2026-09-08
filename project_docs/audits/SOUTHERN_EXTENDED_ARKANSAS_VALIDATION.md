# Southern historical panel Arkansas extension validation

**Verdict: PASS for experimental model use, with coverage caveats**

The Arkansas extension independently reproduces, preserves the validated 2,273-row panel, and admits exactly 110 Arkansas rows through all declared gates. The resulting panel has 2,383 unique state/year/chamber/district keys.

## Reproduction

I rebuilt to an absolute temporary output path and ran the focused suite:

```powershell
python scripts/build_extended_historical_southern_panel.py `
  --combined "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\data\processed\forecast_calibration\historical_southern_combined_panel.csv" `
  --arkansas-dir "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\data\processed\precinct_history\arkansas_pre2000" `
  --klarner "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\data\raw\historical_statewide_elections\dataverse_files.zip" `
  --output "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\.validation_tmp\southern_extended_ar"
python -m pytest scripts/tests/test_extended_historical_southern_panel.py -q
```

The independent rebuild reports 2,273 input rows, 119 reconciled Arkansas rows, 110 strict Arkansas admissions, and 2,383 extended rows. Its three CSV outputs are byte-identical to the release outputs.

Two consecutive builds to the same path produced the same manifest SHA-256, `709cd3fb0d3df8327ec521c6d4fcbf600809345567bb146bc285f2e4500f1eee`, and build ID `ec3eca6a58834c1365d3`.

## Preservation and keys

- All 2,273 prior keys occur exactly once in the extended panel.
- All 53 prior columns agree after a key-based one-to-one join. Eighteen floating-point cells across three derived margin fields differ only at CSV round-trip precision; the maximum absolute difference is `3.55e-15`. All source vote totals, categories, identifiers, and substantive numerical values are unchanged.
- Exactly 110 new Arkansas keys are added.
- The 2,383-row extended panel has no duplicate state/year/chamber/district key.
- Existing-panel precedence is effective; no admitted row overwrites an earlier key.

## Arkansas release gates

Every one of the 110 admitted rows satisfies all contracted conditions:

- `staging_reconciliation_gate=True`;
- reconciliation status is `exact` (104 rows) or `within_one_percent` (6 rows);
- finite, positive Klarner Democratic and Republican totals;
- a contested two-party race;
- finite Democratic and Republican context votes, margin, legislative margin, and residual;
- the correct same-cycle context office; and
- legislative-turnout join coverage of at least 95%.

The minimum coverage among admitted rows is `0.9981489927`. All admissions carry `sos_legislative_turnout_join_95pct` allocation quality.

Admission counts are:

| Cycle | House | Senate | Context office |
|---|---:|---:|---|
| 1994 | 26 | 7 | Governor |
| 1996 | 26 | 6 | President |
| 1998 | 39 | 6 | U.S. Senate |
| **Total** | **91** | **19** | |

The nine reconciled but unadmitted staging rows are exposed rather than silently lost: eight are not contested two-party races and one lacks a finite baseline. The full Arkansas candidate audit retains all outcomes and gate fields.

## Allocation and conservation

I reconstructed the allocation independently from the Arkansas observation table:

1. legislative observations were grouped by county/precinct/chamber/district;
2. district weights were divided by total observed legislative turnout within county/precinct/chamber;
3. the selected Democratic and Republican context was joined by county/precinct;
4. context votes were multiplied by the weights and aggregated to districts; and
5. coverage and context-footprint fields were recomputed.

For all 5,778 positive-turnout precinct/chamber groups, weights sum to one within `1.11e-16`. All 11,481 positive-turnout joined context-party groups conserve their source votes within `4.55e-13`. Independently reconstructed baseline votes, margins, and coverage agree with the release within floating-point precision.

There are 89 joined context-party groups with zero legislative turnout, totaling 5,686 context votes. They have no valid allocation weight and remain unallocated; they are not zero-filled into a district. This is appropriately visible in the context-footprint diagnostic. Coverage by cycle/chamber is:

| Cycle | Chamber | Turnout-join coverage | Minimum party context footprint |
|---|---|---:|---:|
| 1994 | House | 0.999994 | 0.487773 |
| 1994 | Senate | 1.000000 | 0.314065 |
| 1996 | House | 1.000000 | 0.398067 |
| 1996 | Senate | 1.000000 | 0.209994 |
| 1998 | House | 0.998149 | 0.764926 |
| 1998 | Senate | 1.000000 | 0.495804 |

The low statewide context-footprint shares are a material coverage caveat, not a failed turnout-join gate: many context precincts do not contain a usable legislative observation, while nearly all observed legislative turnout successfully joins to context. The panel must not be described as statewide-complete precinct coverage.

## Provenance and hashes

All manifest input hashes match the current files:

- combined-panel manifest: `0ed7e569f03fc97fb815f2a253c6d60605012c214ca0651be4fc43928b9efcdf`
- Arkansas staging manifest: `df55c938e40117e904c6a9b867ad8968129bdc78999a2dbb95ca31399fca8229`
- Klarner archive: `b4c0913fa7bfb0aff4da2dbf67a22da696e9f07b45615f30e78127edd794a3e1`

The reproduced output hashes match the release:

- Arkansas candidates: `bc76a75f29cff76b6f025751a71d969dd2fb8b963bd58811048f321d17c9797f`
- Arkansas coverage: `603fc53fa20f3430c8558ad17dd688eb4ce4115726b22fa450be6755d655a670`
- extended panel: `6fcc43c63224af67ed73168daaeb2f8a6dc027c5e76ff6594a9eca678ebb6493`

Manifest configuration correctly records the 95% threshold, office priority `{1994: GOV, 1996: USP, 1998: USS}`, existing-panel precedence, counts, code commit, and deterministic build identity.

## Tests and approval

```text
3 passed in 0.56s
```

The 2,383-row panel is approved for an **experimental, time-safe model tournament**. Downstream work should retain the Arkansas source/allocation fields, restrict modeling to the strict panel, and disclose the uneven geographic and contest coverage, turnout-share allocation, and secondary Klarner outcome source.
