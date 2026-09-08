# Southern historical panel validation, v2

**Task:** `VALIDATE-SOUTHERN-HISTORICAL-PANEL-002`  
**Date:** 2026-08-22  
**Verdict:** **FAIL release provenance; allocation and eligibility remediation pass.**

## Independent rebuild and tests

I rebuilt the current HEDA staging and historical panel into a new absolute
temporary path, compared the generated data with the release candidate,
recomputed allocation and eligibility invariants, then rebuilt the panel a
second time at the identical path.

```powershell
python scripts/build_heda_historical_precinct_staging.py --output <absolute-temp>\heda
python scripts/build_historical_southern_legislative_panel.py --heda-dir <absolute-temp>\heda --output <absolute-temp>\panel
python -m pytest scripts/tests/test_heda_historical_precinct_staging.py scripts/tests/test_historical_southern_legislative_panel.py -q
```

Focused result: **8 passed**.

All seven HEDA data files and all three panel CSVs are byte-identical between
the temporary rebuild and release. The panel manifest is byte-identical when
the panel is rebuilt at the same path. Temporary and release manifests differ
in their displayed absolute/relative paths as expected.

## Allocation remediation: pass

The revised allocation retains unallocatable fragment rows instead of dropping
them. Across the 4,679 district rows with a selected baseline:

- `expected_context_groups = allocated_context_groups + incomplete_context_groups`
  for every row (4,679/4,679);
- expected groups total 233,161, comprising 231,227 allocated and 1,934
  incomplete district-context group appearances;
- 735 selected baselines are labeled `partial_unresolved` and every one has a
  positive incomplete-group count;
- no nonpartial baseline has a positive incomplete-group count; and
- all complete source-context allocations conserve nonmissing Democratic,
  Republican, and total votes to floating-point precision.

The focused fixture now covers the formerly silent failure mode: a split
precinct with no usable turnout proxy remains present, has an incomplete group,
is labeled `partial_unresolved`, and does not manufacture a baseline margin.

## Strict and permissive eligibility: pass

The panel has 4,867 unique state/year/chamber/district rows and zero duplicate
keys. Independent recomputation gives:

| Eligibility definition | Rows |
|---|---:|
| finite positive Klarner D and R plus baseline | 2,141 |
| same, excluding any incomplete context group | 1,805 |
| permissive-only difference | 336 |

Both stored flags exactly equal those independent definitions. All 336
permissive-only rows are `partial_unresolved`; no strict-eligible row is
partial or has an incomplete context group. The strict sample comprises 914
whole-precinct and 891 complete turnout-share baselines.

The coverage output sums to the same 1,805 strict-eligible rows. The 20 Florida
2010 districts with positive HEDA legislative fragments but no finite Klarner
D/R result remain ineligible under both definitions. Thus HEDA leakage cannot
create a model outcome.

## Panel manifest: internally valid

Both temporary and release panel manifests correctly reproduce their own:

- three output sizes and SHA-256 hashes;
- panel (4,867) and coverage (69) row counts;
- strict (1,805) and permissive (2,141) eligibility counts;
- Klarner input hash;
- HEDA-manifest input hash;
- pipeline, configuration, code commit, and deterministic build ID.

The three release CSV hashes match the independent rebuild:

| Output | SHA-256 |
|---|---|
| panel | `0c4c028df369c561eb837746686517f5e9aa2a643c932522b2a1707d3d142e0d` |
| coverage | `1b1fc113ef4a918428864335e2b2ba7dd8ff0c7ca8259573f1b7f87393a711ed` |
| allocation audit | `d8f07212959faf71b5aea1d95d7ef5820c2b5dfa6025829968e48aa1ddf93cc8` |

## Blocking release-chain finding

The release HEDA manifest is stale relative to the current HEDA staging code.
The current temporary rebuild produces HEDA build ID
`fd2eb9662a0190c1c7a0`, while the release manifest records
`c79a58b60a21a535b043`. Output location cannot explain this difference because
the build ID hashes only the two source archives and the staging script, not
the output path. Source hashes and all seven data bytes are identical, so the
remaining cause is a different staging-script hash.

This matters because the release panel manifest correctly hashes the *stale
release HEDA manifest*, while an independent rebuild with the current code
necessarily hashes the new HEDA manifest and receives a different panel build
ID. The CSVs are numerically reproducible, but the published provenance chain
does not identify the current producer code.

## Required release action

Rebuild the release HEDA staging with the current staging script, then rebuild
the panel so its manifest points to that refreshed HEDA manifest. Re-run the
manifest/hash checks. No allocation or eligibility logic change is indicated.

After that provenance-only rebuild, this experimental panel is fit for
exploratory use under the strict 1,805-row flag. It remains secondary-source
analytical material, not canonical election or geographic fact.
