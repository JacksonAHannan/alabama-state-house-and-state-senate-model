# Repository cleanup validation

**Task:** `VALIDATE-REPO-CLEANUP-001`  
**Validated:** 2026-08-21  
**Verdict:** **PASS**

The conservative cleanup removes obsolete public CMO copies without removing
source evidence, processed history, or active research. The canonical command
surface and machine-readable catalog now identify v4 consistently, the active
CMO page loader has no v2/v3/preliminary input dependency, and the current site
and complete test suite pass.

## Conservative deletion and recoverability

- The cleanup deletes exactly 18 tracked files, all under `docs/data/`: eleven
  CMO v2 exports, five CMO v3 exports, and two preliminary CMO exports.
- No tracked file under `data/raw/`, `data/manual/`, or `data/processed/` is
  deleted or modified by the cleanup diff.
- All 18 removed public files are recoverable from `HEAD` with `git cat-file`.
- All 18 have retained counterparts under `data/processed/war/`.
- `.gitignore` correctly excludes `.env`, the Blue/Oxblood staging folder,
  generated artifact PNG screenshots, and artifact JavaScript captures.

## Canonical command and dependency surface

`scripts/project.py` exposes exactly the documented `cmo`, `forecast`, and
`site` build targets, and every dispatched script exists. Its CMO target starts
with `rebuild_cmo_war_analogue.py`; neither superseded v2 nor v3 model builders
appear in the target.

The current `scripts/build_war_story_page.py` loader reads:

- `cmo_v4_candidates.csv`;
- `cmo_v4_races.csv`; and
- the independent `canonical_cmo_features.csv` metadata export.

It contains no read of `cmo_v2_*`, `cmo_v3_*`, or `preliminary_cmo_*`. I called
the loader under an open-file guard that raises if any such legacy filename is
accessed. It completed all 16 cycle/chamber payload sections and 1,018 candidate
rows without triggering the guard.

The remaining legacy patterns in the builder are output-cleanup globs only:
they ensure obsolete files cannot survive in `docs/data/`.

## Catalog and publication boundary

The generated `project_docs/data_catalog.csv` and its generator now declare one
active CMO publication asset:

```text
published_cmo_v4_data
docs/data/cmo_v4_candidates.csv
scripts/build_war_story_page.py
```

That file and producer exist. Neither catalog contains the deleted preliminary
path, obsolete asset ID, or former `scripts/build_site.py` producer. The catalog
lineage points from the CMO feature mart to the v4 publication asset.

`docs/data/` contains zero files matching `cmo_v2_*`, `cmo_v3_*`, or
`preliminary_cmo_*`. All eight `docs/data/cmo_v4_*.csv` exports byte-match their
counterparts under `data/processed/war/`.

## Site integrity

I inspected all six public HTML pages in headless Microsoft Edge at a
1,425-pixel desktop client width and an exact 497-pixel mobile client width.
Every page has zero horizontal overflow and zero application console errors.
A static internal-link audit found no broken local targets.

## Commands and results

```text
python scripts/project.py audit
python -m pytest scripts/tests/test_repository_hygiene.py scripts/tests/test_published_site_consistency.py scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_cmo_war_analogue.py -q
python -m pytest -q
python scripts/validate_agent_workflow.py
```

Results:

- repository hygiene audit: passed;
- focused cleanup/publication/model suite: **16 passed**;
- full suite: **380 passed**, 11 existing pandas/SWIG warnings;
- agent workflow validation: passed.

The build commands themselves were not executed because this independent task
has a read-only warehouse and a write scope limited to this audit and task
status. Their target dispatch, source dependencies, current byte-exact outputs,
payload construction, focused tests, and rendered pages were independently
validated without rewriting shared model or publication artifacts.

## Release decision

**PASS.** Both earlier blockers are resolved. The cleanup is conservative,
recoverable, internally consistent, and safe to release. No blocking or
nonblocking cleanup finding remains from this audit.
