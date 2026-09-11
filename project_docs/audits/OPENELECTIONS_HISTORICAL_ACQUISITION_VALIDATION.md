# OpenElections historical acquisition validation

**Task:** `VALIDATE-SOURCE-OPENELECTIONS-001`  
**Date:** 2026-08-22  
**Verdict:** **PASS as a secondary historical source bundle.**

## Scope and commands

I independently inspected the acquisition selector and focused tests, loaded
the manifest, enumerated the raw bundle, recomputed every local file hash and
size, queried each pinned Git tree, and downloaded all pinned raw URLs into
memory for byte-level hash comparison. No source or manifest was written.

```powershell
python -m pytest scripts/tests/test_openelections_historical_acquisition.py -q
```

Focused result: **2 passed**.

## Manifest and local files

- Manifest rows: **172**.
- Unique `(repository, commit, source_path)` keys: 172; duplicates: 0.
- Unique local paths: 172; duplicates: 0.
- Raw files on disk: 172; missing manifest files: 0; unmanifested files: 0.
- Missing manifest fields: 0 in every column.
- Recomputed local sizes: 172/172 match.
- Recomputed local SHA-256 hashes: 172/172 match.
- Raw URLs: 172/172 equal the expected repository, commit, and source path.
- Retrieval timestamps: 172/172 parse as timezone-aware UTC values.
- Provider, granularity, and authority fields are consistently
  `OpenElections`, `precinct`, and `secondary_validation_source`.

The bundle totals 89,751,634 bytes (85.59 MiB).

## Coverage

The fourteen expected state-cycle combinations are present exactly:

| State | Cycle | Files |
|---|---:|---:|
| Arkansas | 2008 | 1 |
| Georgia | 2012 | 1 |
| Georgia | 2014 | 1 |
| Georgia | 2016 | 159 |
| Missouri | 2000 | 1 |
| Missouri | 2002 | 1 |
| Missouri | 2004 | 1 |
| Missouri | 2006 | 1 |
| Missouri | 2008 | 1 |
| Missouri | 2010 | 1 |
| Missouri | 2012 | 1 |
| Missouri | 2014 | 1 |
| Missouri | 2016 | 1 |
| South Carolina | 2006 | 1 |

Every combination contains a nonempty `precinct` field. File contents range
from 12,977-byte county files to large statewide normalized tables; their
schemas vary by provider repository and cycle, as expected for adapter inputs.

## Pinned upstream verification

The four GitHub tree requests returned HTTP 200, were not truncated, and
resolved to the exact configured commits:

| Repository | Commit | Selected paths |
|---|---|---:|
| openelections-data-ar | `834ccef3cdcf64c8a381811e4d3ad02ec72ba336` | 1 |
| openelections-data-ga | `86bf341e68775bae06a54538dae0311fb6201872` | 161 |
| openelections-data-mo | `9d0ea2824c558a468ee8b44a11fc9910634a0379` | 9 |
| openelections-data-sc | `5e05b67e15f3614a20d31144df83248235cba6f2` | 1 |

For every state, applying the acquisition selector independently to the full
pinned tree produces exactly the manifest path set. All 172 paths exist as
blobs, and their Git-tree sizes match the manifest/local sizes.

As an additional check, I fetched all 172 `raw.githubusercontent.com` URLs at
the pinned commits without writing them. Every downloaded size and SHA-256
matches the manifest (172/172).

## Election-stage filter

- All 172 manifest rows are labeled `general`.
- All 172 source paths contain `general`.
- No source path contains `primary` or `special`.
- Every manifest member independently passes `selected_member`.
- The selector's exact date/path rules prevent other general, primary, or
  special files in the pinned trees from entering these cycle bundles.

The Georgia 2014 file is the sole `unofficial_label` row and its filename
explicitly contains `UNOFFICIAL`. The other 171 rows are labeled
`repository_normalized`.

## Disposition

The acquisition bundle passes provenance, coverage, file-integrity, pinned-path,
and stage-filtering checks. It is approved for downstream adapter staging as a
**secondary validation source**. It does not supersede official election
returns; Georgia 2014 must retain its explicit unofficial status through every
downstream reconciliation.
