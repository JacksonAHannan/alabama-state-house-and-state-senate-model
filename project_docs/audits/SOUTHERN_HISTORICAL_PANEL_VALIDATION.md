# Southern historical panel validation

**Task:** `VALIDATE-SOUTHERN-HISTORICAL-PANEL-001`  
**Date:** 2026-08-22  
**Overall verdict:** **FAIL**  
**Layer verdicts:** revised HEDA staging **PASS for reproducible staging**;
Florida/HEDA **not approved as canonical fact**; experimental panel **FAIL pending
allocation-completeness remediation**.

## Independent procedure

I rebuilt both the HEDA staging and historical panel twice into separate
temporary workspace directories, repeated the staging build at the same path,
recomputed all eligibility and allocation checks from the source staging
tables, and ran the two focused test modules.

```powershell
python scripts/build_heda_historical_precinct_staging.py --output <absolute-temp-path>\heda
python scripts/build_historical_southern_legislative_panel.py --heda-dir <absolute-temp-path>\heda --output <absolute-temp-path>\panel
python -m pytest scripts/tests/test_heda_historical_precinct_staging.py scripts/tests/test_historical_southern_legislative_panel.py -q
```

Focused tests: **7 passed**.

## Revised HEDA staging: pass

- All seven data outputs are byte-identical across the two temporary builds
  and to the release candidate, including both gzip files.
- A repeated build at the same absolute path reproduced all seven data files
  and `build_manifest.json` byte for byte.
- The manifest's seven output sizes and SHA-256 hashes match the referenced
  files. Its two source hashes match the HEDA and Klarner inputs. Build ID,
  code commit, row counts, authority policy, and missing-value policy are
  present and stable.
- Output counts remain 85 coverage rows, 240,160 legislative fragments,
  1,777,718 context rows, 4,867 district rows, 4,867 reconciliation rows, and
  13,640 Florida 2010 fragments.
- Legislative fragment, context, district, panel, coverage, and allocation
  audit compound keys have zero duplicates.
- District D/R/total aggregates exactly reproduce the precinct-fragment sums.

Manifests generated in two *different* temporary directories are not byte
identical because they correctly record different output paths. Their build ID,
source/code identity, row counts, and data hashes are identical. This is not a
data determinism failure.

One CLI caveat remains: a relative custom `--output` path writes the seven data
files and then raises `ValueError` while making paths relative to the absolute
repository root. The documented/default absolute output and the contracted
absolute temporary rebuild work. This should be corrected, but it did not
alter the release candidate or the validation result for the staging data.

The staging pass does **not** promote HEDA or Florida 2010 to canonical
authority. HEDA and Klarner remain conflicting secondary observations, and the
Florida discrepancies documented in the earlier validation still require
official-source reconciliation.

## Panel output and outcome eligibility: pass

The three experimental panel outputs are byte-identical across both temporary
builds and to the release candidate:

| Output | SHA-256 |
|---|---|
| panel | `8fbc57abfafbe8bfebd940dc0abcf853a08dd98abf69c0ac56c3abc1fcae5f8d` |
| coverage | `ca9d9eb8da2685a1ad988aa1cdf84c1a7a235e6de1aad739b61f617b92c73f4d` |
| allocation audit | `f9638fb18d6f24e9c68839f9dec339ee675122e77947b8c718d74137e334c138` |

The panel contains 4,867 unique district-cycle rows, 4,679 rows with a selected
baseline, 2,225 contested Klarner outcomes, and 2,141 model-eligible rows.

Independently recomputed eligibility exactly equals:

```text
finite Klarner Democratic votes > 0
AND finite Klarner Republican votes > 0
AND selected baseline margin is present
```

There are zero eligibility mismatches, zero eligible nonfinite outcomes, and
zero eligible rows with a nonpositive party total. Legislative margin and raw
overperformance arithmetic have zero discrepancies. Every result is labeled
as Klarner district contest totals; HEDA legislative sums remain separate
reconciliation fields.

Most importantly, Florida 2010 has 20 districts with positive HEDA fragments
but no finite Klarner D/R contest (12 House and 8 Senate). All 20 have a
baseline, but **none is model eligible**. HEDA leakage therefore cannot create
a synthetic held contest under the current data and logic.

## Allocation conservation: partial pass with blocking gap

For every context-source/chamber group that receives weights:

- weights sum to one;
- allocated D, R, and total votes reproduce every nonmissing source value to
  floating-point precision;
- 345,065 rows use whole-precinct allocation and 30,235 use legislative-turnout
  share allocation; and
- presidential, then U.S. Senate, then governor priority is applied without a
  mismatch.

However, 1,067 multi-fragment source-context/chamber groups have no positive
legislative turnout proxy, so all their context is dropped. This is a valid
reason not to manufacture allocation weights, but the downstream district
aggregate can still receive other precincts and appear to have a complete
baseline.

This affects 721 selected district baselines and **331 model-eligible rows**.
Neither `baseline_allocation_quality` nor the allocation audit identifies these
selected baselines as partial: the quality field only distinguishes whole
precincts from baselines that include turnout-share allocations. Consequently,
an analyst cannot exclude or sensitivity-test the 331 incomplete baselines
from the published panel alone.

This contradicts the methodology's practical implication that unallocatable
context remains missing. It remains missing at the source-fragment level, but
is silently omitted from an otherwise nonmissing district result.

## Additional provenance caveat

The experimental panel has no panel-level manifest recording its input hashes,
pipeline/code hash, configuration, build ID, row counts, and three output
hashes. Its source-label columns and the upstream HEDA manifest are useful but
do not make the derived panel independently traceable as a versioned analytical
artifact.

## Required remediation before experimental use

1. Carry allocation completeness into each district-office aggregate: expected
   context groups, allocated groups, dropped groups, and preferably allocated
   vote coverage when a denominator exists.
2. Mark selected baselines with any dropped context as partial/unresolved.
   Either exclude them from `model_eligible` by default or expose a separately
   named permissive eligibility flag and require an explicit sensitivity run.
3. Add focused tests for a split precinct with zero/missing legislative proxy
   plus another successfully allocated precinct in the same district. The
   district must not be labeled unqualified/complete.
4. Add a deterministic panel manifest with HEDA manifest/input hashes, Klarner
   hash, code/configuration identity, row counts, and output hashes.
5. Normalize custom output paths before manifest path handling so relative
   temporary paths do not fail after writing data.

After those changes, the panel can be reconsidered for **experimental**
candidate-quality and downballot-lag analysis. Canonical promotion remains a
separate, stricter decision requiring authoritative result and geography
reconciliation.
