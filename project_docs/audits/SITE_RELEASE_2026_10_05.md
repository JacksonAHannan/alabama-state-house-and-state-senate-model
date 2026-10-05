# Site release 2026-10-05

- **Authorization:** the owner asked on 2026-10-05 to "Push changes to the live website". GitHub Pages serves `docs/` from `master`.
- **Release branch:** `publish-2026-10-05`.
- **Source commit:** `6436e6c1`. The `docs/` commit follows it.
- **Rollback:** `origin/master` was at `0d6c2a5b` before this release. Local `master` also carried five earlier unpushed commits, `0d6c2a5b..178d6f48`, which this push publishes too. To roll back, reset `master` to `0d6c2a5b`, or revert the release commits, and push.

## What was published

`python scripts/project.py build site --publish` ran every renderer in publish mode and passed every release gate. It then applied the site theme.

| Page | Source run |
|---|---|
| Forecast (`index.html`, `methodology.html`) | forecast build `ca64e43e988cc59c12bc`; environment Silver Bulletin generic ballot, two-party D+9.71 as of 2026-10-05; seats by cycle `AL-SEATS-V1-99F2D5EF80B48E69BF5B`; 2022–2026 plan-equivalence audit |
| Alabama WAR (`cmo.html`, `cmo-methodology.html`) | historical WAR `AL-HIST-WAR-V1-F9DF2D2E6C12C696A705` (1994 party-label repair, 1994 incumbency, HD1 1994 withheld) |
| Southern WAR | unchanged Southern run; payload sha256 `49ed37f6…`; redesigned page |
| Ideology and caucuses | caucus run `AL-DEM-CAUCUS-V1-DFA0C1C5015D988804CF`, status `descriptive_groupings`, owner-approved two-group labels |
| `methods.html`, `caucuses.html`, `legislators.html` | regenerated landing and redirect pages |

## Checks before push

- **Links.** All 21 static download links resolve, and so do the script-built links (seats reconciliation and manifest).
- **Published pages in a browser.** All 8 published pages (`file://`) showed:
  - no script errors;
  - one skip link and one `main` landmark each;
  - no page-level horizontal overflow at 1440 px.
- **Earlier checks.** The same candidates passed browser and axe checks before publication: 0 WCAG A/AA violations, responsive at 390, 768 and 1440 px, keyboard operation. Details are in `WEB_VISUAL_REDESIGN_VALIDATION_2026_10_03.md`.
- **Full suite.** `pytest -p no:cacheprovider` collected 1,401 tests. They were run in file chunks to stay within the foreground time limit; the slow `test_southern_candidate_cycle_finance.py` ran alone (30 passed).
  - All pass except 7 failures, which are new and caused by the 1994 repair.
  - Each failure is a research product downstream of 1994 canonical candidates that has not yet been rebuilt. None feeds a published page:

| Failing test | Cause |
|---|---|
| `test_absolute_ideology_rebuild::test_cqi_is_joined_exactly_and_estimated_by_era` | the absolute-ideology rebuild still reads the pre-repair CMO v5 candidate quality |
| `test_alabama_2018_official_results::test_reconciliation_audit_replays_exact_sources_and_code` | the 2018 reconciliation audit pins the sha256 of `scripts/sos_precinct.py`, which changed (1994-only adapter fix); the audit needs re-attesting |
| `test_candidate_ideology_storage_invariants` (2 tests) | the candidate-ideology storage outputs still hold 1,566 pre-repair rows and retired 1994 IDs (e.g. `AL-1994-senate-18-R-HORN`) |
| `test_candidate_issue_research_loop::test_every_research_attempt_targets_a_canonical_candidate` | manual research attempts reference retired 1994 IDs; the supersession record documents them, but the files were not rewritten |
| `test_canonical_historical_finance::test_canonical_finance_preserves_unknowns_and_observed_zeros` | historical finance features are built on the pre-repair 510 races |
| `test_cmo_southern_prior_v6::test_direct_cmo_is_unchanged_and_prior_excludes_alabama` | the CMO v6 Southern prior was built on the pre-repair 504-race universe |

- **Pins updated for the approved content.** Three published-site pins were updated, each keeping its check:
  - the forecast scenario selector is now the "Forecast view" tablist;
  - the caucus labels are the approved two-group labels;
  - the WAR map shows 503 scored races and 1,006 candidates, with HD1 1994 shown through the no-score panel.

## Reviews outstanding at release (owner decided to publish)

- **Second independent pass over the post-fix redesign.** This covers the selection display, the hatching fix, the 2022-result map mode and the new forecast charts.
- **Independent review of the rebuilt 1994 WAR and the Wikipedia-based incumbency adjudications.** The 1994 repair's dry run had passed an independent review and a delta review before the warehouse write.

## Sources and attribution

- **National environment.** Silver Bulletin's generic-ballot tracker, read from its public daily-average chart and attributed on the page. The subscriber poll-level data is not used. The derived daily series is git-ignored, since the terms were not reviewed.
- **Wikipedia.** The 1994 incumbency evidence quotes Wikipedia (CC BY-SA 4.0), with titles and URLs, in `data/manual/elections/alabama_1994_incumbency_wikipedia_evidence.csv`.

## Follow-up

1. Rebuild the 7 stale dependents listed above.
2. Re-attest the 2018 reconciliation audit.
3. Run the outstanding reviews.
