# Test release-relevance audit

Audit date: 2026-09-05 (America/Chicago). Scope: test cleanup and testing
instructions, not model selection, data repair, or publication.

## Result and review scope

The configured suite collected 727 tests in 159 files before this change and
714 tests in 158 files afterward. Removed 13 obsolete or redundant tests;
no skips, collection exclusions, or weakened release gates were introduced.
All 27 tests in the five candidate files passed before editing: deletion was
based on current relevance, not an attempt to conceal failures.

Static triage covered all 159 test modules: test definitions, direct imports,
and script callers. Manual review then traced the suspect legacy forecast,
CMO, dispatcher and presentation checks against current builders, compatibility
consumers and [canonical routes](../CANONICAL_PIPELINES.md). A missing Python
import is not evidence of retirement: subprocess entry points and file-based
consumers also count. This is not a claim that every retained assertion received
a fresh scientific review, or that the complete suite passed.

## Deletions and surviving protection

| Test file | Removed | Reason and surviving protection |
|---|---:|---|
| `scripts/tests/test_cmo_direct_estimand.py` | 5 | Tests only `cmo_v3_races.csv` / `cmo_v3_candidates.csv`, the retired direct-gap headline. Those outputs have no current analytical reader in the scanned scripts; the publisher explicitly removes their public exports. Current residual arithmetic, orientation, backcast and provenance checks remain in `test_alabama_war_v1.py`, `test_alabama_historical_war_v1.py` and `test_post2016_southern_war_v3.py`. |
| `scripts/tests/test_2026_baseline_first_forecast.py` | 4 | Removed the old public blend20/blend100 view requirement, SD2 sign/decomposition smell test, frozen promotion winners, and required superiority of the old environment ramp. Also removed two historical ranking assertions from the retained forward-cycle check. Current scenarios, decomposition and public agreement remain covered by `test_alabama_war_generic_forecast.py`, `test_forecast_dashboard.py` and `test_published_site_consistency.py`. Five compatibility artifact checks remain. |
| `scripts/tests/test_southern_probability_calibration.py` | 2 | Removed the requirement that a research challenger lose and the old HD21 Republican probability threshold. These are historical empirical results, not current release invariants. Calibration-panel scope and forward/geographic evaluation checks remain; current probabilities are checked against the selected forecast exports. |
| `scripts/tests/test_repository_hygiene.py` | 1 | Removed the assertion calling the legacy `rebuild_cmo_war_analogue.py` dispatcher target canonical/current and requiring that exact target set. The pipeline index explicitly identifies its pending migration. Publication-boundary checks and site-builder existence checks remain. The dispatcher itself was not changed. |
| `scripts/tests/test_published_site_consistency.py` | 1 | Removed a second check of Grimsley's 2018 page value against the modern Alabama export. `test_historical_war_story_page.py::test_grimsley_2018_is_exact_published_race_residual` checks the same page, exact cycle/chamber/district/party match and scoring scope. Export byte-parity and the separate corrected-race regression remain. |

Only one whole file was deleted. It was tracked and had no preexisting local
diff; recover its original contents from Git history. Historical audits that
mention its old command are preserved as dated evidence, not rewritten to imply
that command still exists. No source archives, model code, manifests, research
results, or public downloads were deleted.

## Deliberately retained

- Warehouse lifecycle, transaction/rollback, repair, identity, provenance,
  schema, allocation and reconciliation tests. Their relevance does not depend
  on which model version is currently public.
- CMO v2 helper coverage: `rebuild_cmo_candidate_quality_v5.py` and the legacy
  dispatcher still call its panel/baseline/history helpers. Old names alone
  cannot establish that these tests are disposable.
- CMO v5/v6 compatibility coverage: current builders still consume historical
  inputs or publish compatibility outputs. Separate migration is needed before
  deleting those contracts wholesale.
- `test_robust_forecast_pipeline.py`: the current forecast still consumes
  `robust_forecast_v1_error_components.csv`; old forecast code also supplies
  reusable features. Its historical manifest is not current publication approval.
- `test_ideology_performance_page.py`: its old-named builder delegates to the
  current merged page. These are live payload/accessibility tests, not dead UI.
- `test_legislator_ideology_page.py`: the site builder still invokes that builder
  before replacing the public page with a redirect. Removing that redundant
  build stage and evaluating its remaining consumers is separate runtime work.
- Southern v4 and other research tests: research-only is not synonymous with
  abandoned. No bulk deletion was justified without an explicit retirement and
  consumer review. Current publication tests remain alongside them.

The expensive CMO v2 tests repeatedly build the old analytical result. This is a
candidate for separating shared-helper tests from historical replay checks, not
a reason to silently discard identity or temporal coverage in this cull.

## Testmon policy

Updated `AGENTS.md`, `README.md` and the
[testing commands](../CANONICAL_PIPELINES.md#testing-and-testmon): routine Python
changes use the repository `.venv` and `--testmon`; required data/SQL/template
tests explicitly use `--testmon-noselect`. Full runs remain for integrated
releases, broad changes, uncertain coverage and establishing a complete baseline.
No plugin was added to runtime requirements or forced into pytest configuration.

Verified `pytest-testmon 2.1.4` in `.venv`; the system Python lacks the plugin.
The existing `.testmondata` passed a read-only SQLite `quick_check`. The cache
and its sidecars are now ignored, not deleted. Cache integrity does not prove
baseline completeness or warehouse freshness.

## Verification

Using `.venv/Scripts/python.exe`:

1. Before editing: `-m pytest --no-testmon --collect-only -q` collected **727**.
2. Before editing: `-m pytest --testmon --testmon-noselect` on the five files
   in the deletion table: **27 passed**.
3. After editing: `-m pytest --testmon --testmon-noselect ... -q` on the following
   explicit files: **80 passed, 1 warning**, with no deselection:

   ```text
   scripts/tests/test_2026_baseline_first_forecast.py
   scripts/tests/test_southern_probability_calibration.py
   scripts/tests/test_repository_hygiene.py
   scripts/tests/test_repository_layout.py
   scripts/tests/test_published_site_consistency.py
   scripts/tests/test_historical_war_story_page.py
   scripts/tests/test_alabama_war_v1.py
   scripts/tests/test_alabama_historical_war_v1.py
   scripts/tests/test_alabama_war_generic_forecast.py
   scripts/tests/test_forecast_dashboard.py
   scripts/tests/test_southern_historical_war_v1.py
   scripts/tests/test_post2016_southern_war_v3.py
   scripts/tests/test_warehouse.py
   scripts/tests/test_warehouse_data_repairs.py
   ```

4. After editing: complete collection with `--no-testmon --collect-only -q`
   succeeded: **714 tests / 158 files**. Collection executes no test bodies.
5. Repository path audit: **passed, 5 required paths**. Agent-workflow validator:
   **passed**. Cache files confirmed ignored.

The targeted run reported the existing pandas empty/all-NA concatenation
FutureWarning in `sos_precinct.py`; collection reported SWIG deprecations.
The initial diff check found two trailing blank lines introduced by deletion;
those were removed. No full-suite execution, model rebuild, source refresh or
publication was performed. Selected passes do not certify unrun tests or every
warehouse consumer.
