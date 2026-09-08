# Southern historical panel validation, v3

**Task:** `VALIDATE-SOUTHERN-HISTORICAL-PANEL-003`  
**Date:** 2026-08-22  
**Verdict:** **PASS for experimental use.**

## Provenance reconstruction

I independently recomputed build IDs from the exact algorithm in each current
pipeline.

HEDA staging:

```text
SHA256(HEDA archive hash : Klarner archive hash : current staging-script hash)
expected: fd2eb9662a0190c1c7a0
recorded: fd2eb9662a0190c1c7a0
```

Historical panel:

```text
SHA256(current HEDA-manifest hash : Klarner archive hash : current panel-script hash)
expected: e249019058aa1177bca1
recorded: e249019058aa1177bca1
```

The current HEDA manifest hash is
`f7b54092fd479d42f1a216d39303b1d4da1970284dd62fc7b2388d32f3a0bbab`.
The panel manifest records that exact path and hash as its first input. Its
second input is the current Klarner archive with SHA-256
`b4c0913fa7bfb0aff4da2dbf67a22da696e9f07b45615f30e78127edd794a3e1`.

This resolves the stale-producer mismatch found in validation v2.

## Output integrity and counts

Every HEDA and panel output exists, and every byte size and SHA-256 matches its
manifest entry.

Independently loaded HEDA counts equal the manifest:

| Table | Rows |
|---|---:|
| coverage | 85 |
| legislative fragments | 240,160 |
| context | 1,777,718 |
| districts | 4,867 |
| reconciliation | 4,867 |
| Florida 2010 fragments | 13,640 |

Independently loaded panel counts also equal the manifest:

| Measure | Rows |
|---|---:|
| panel | 4,867 |
| coverage | 69 |
| strict model eligible | 1,805 |
| permissive eligible | 2,141 |

Panel district keys have zero duplicates, and no strict-eligible row is marked
`partial_unresolved`.

## Tests and disposition

```powershell
python -m pytest scripts/tests/test_heda_historical_precinct_staging.py scripts/tests/test_historical_southern_legislative_panel.py -q
```

Result: **8 passed**.

The dependency-ordered rebuild and current manifests satisfy the final
provenance gate. The 1,805-row strict panel is approved for the documented
exploratory Southern historical analysis. This approval does not make HEDA,
allocated baselines, Florida 2010 fragments, or Klarner totals canonical facts;
official-source and geography reconciliation remain separate requirements.
