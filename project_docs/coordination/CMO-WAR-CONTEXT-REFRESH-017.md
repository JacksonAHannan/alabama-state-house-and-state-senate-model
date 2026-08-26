# Task contract: CMO-WAR-CONTEXT-REFRESH-017

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Refit the current candidate-quality products after the previous-presidential correction and formalize the public name WAR for the partial-pooled candidate-quality estimate while retaining CMO as a separate observed ticket comparison.
- Acceptance checks: CMO v5 and the Southern-prior decomposition rebuild from the refreshed canonical context; 2010 HD-32 uses the corrected D+24.05 prior presidential margin; its Democratic presidential overperformance is approximately +18.69 rather than +48.59; candidate/race keys remain unique; direct CMO remains distinct from WAR; model tests pass.
- Read scope: Completed `WAREHOUSE-CMO-CONTEXT-REFRESH-016` exports, current historical Southern calibration panel, current candidate identities, and existing model tests.
- Write scope: `scripts/rebuild_cmo_candidate_quality_v5.py`; `data/processed/war/cmo_v5_`; `data/processed/war/cmo_v6_southern_`; `project_docs/model/CMO_METHODOLOGY_V5.md`; `project_docs/coordination/CMO-WAR-CONTEXT-REFRESH-017.md`; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: Corrected canonical CMO context and current frozen Southern comparison panel.
- Expected outputs: Refreshed v5/v6 race and candidate files, manifests, validation tables, case studies, and model terminology ready for the public WAR page.
- Warehouse mode: `read-only`
- Handoff recipient: `web_product`.

## Handoff

- Rebuilt 509 races and 1,018 candidate-cycle rows in both v5 and the Southern-prior v6 product.
- HD-32 now uses a 2008 presidential margin of D+24.052976 and Barbara Bigsby Boyd's raw presidential overperformance is +18.694287 rather than +48.588364.
- Direct CMO remains +30.263799 because it is a separate same-cycle-ticket comparison; the public candidate-quality label is WAR while the stable internal compatibility column remains `candidate_quality_index`.
- Candidate/race keys are unique and all 12 focused v5/v6 tests pass.
- The public WAR page must now be rebuilt from these outputs with WAR as its title and candidate-quality headline.
