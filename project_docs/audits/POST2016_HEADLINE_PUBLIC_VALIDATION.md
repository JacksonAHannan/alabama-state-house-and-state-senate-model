# Post-2016 headline forecast and public-site validation

## Verdict

**PASS.** Forecast build `e178fb3f50c98c9c312b` and the current generated public site satisfy the release contract. The previously identified candidate-card finance inconsistency is fixed: every modeled candidate now displays the exact headline-package finance value/status, including explicit missing observations.

## Independent checks

### Rebuild, provenance, and determinism

- Rebuilt the post-2016 experiment and promoted package into a unique temporary directory by redirecting only output paths and invoking the production entry points.
- All 15 experiment outputs matched the release bytes, including the experiment manifest (`30d4e3967a7bbc38700e`).
- All five promoted CSV outputs matched the release bytes. The temporary promoted manifest had a different build ID solely because its recorded source paths pointed at the temporary directory; release numerical content was unchanged.
- Independently recomputed every production manifest hash: all 16 experiment input/code/output hashes and all 11 promoted-package hashes matched. The promoted build ID is `e178fb3f50c98c9c312b`.
- The six versioned files under `docs/data/post2016_headline_v1_*` match their processed release artifacts byte-for-byte.

### Model and scenario reconciliation

- The headline contains exactly 48 modeled contests: 33 House and 15 Senate, with unique chamber/district keys.
- The promoted headline exactly matches source scenario `uniform_polling_federal_within_cycle_orthogonal` and specification `polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising` for margins, component adjustments, finance fields, and model labels.
- Each of the three public scenarios contains the same 48 contests. The Democratic- and Republican-favorable scenarios shift the headline by exactly `+2.20385` and `-2.20385` points, within floating-point tolerance below `8e-15`.
- Headline arithmetic satisfies `predicted_dem_margin = polling_federal_margin + expected_cmo_adjustment` within `7.2e-15`.
- Student-t(5), scale 5.75 win probabilities reproduce within `1.2e-16`; all are bounded. The 80% intervals nest within the 95% intervals.
- The forward-test output contains 390 rows (13 specifications times 30 common 2022 test contests). Every specification uses 2018 training data and the same 2022 test cohort. Inspection found no realized legislative outcome in the prospective feature set.

### Finance and public payload

- Finance is complete in 43 modeled races and incomplete in five. Every incomplete race has a missing fundraising gap and `finance_model_applied = false`; missing values are not converted to zero.
- The dashboard payload reconciles every modeled candidate's finance total and status to the headline package. Explicit missing observations remain missing for House districts 8, 40, and 41 and Senate districts 25 and 28. No candidate-card fallback to the separate display-finance table remains.
- The payload exposes exactly the three current views: headline, Democratic-favorable environment, and Republican-favorable environment, all tagged with build `e178fb3f50c98c9c312b`.

### Chamber summaries and publication

- House composition is 33 modeled plus 72 fixed seats; Senate is 15 modeled plus 20 fixed seats. All fixed seats are labeled `unopposed-major-party`.
- Public chamber distributions reproduce the modeled distributions with fixed Democratic seats added (20 House and 6 Senate); probability mass sums to one.
- The independently regenerated methodology page matches `docs/methodology.html`; shared-theme transformation reproduces the other tested public pages. All seven public HTML files match their staged blue/oxblood artifacts byte-for-byte.
- Public methodology prominently discloses the single direct 2018-to-2022 Alabama forward test, the full-cycle historical versus partial-cycle 2026 finance mismatch, and that fundraising is predictive rather than established as causal.

### Browser validation

Chrome headless/CDP checks were run at 1280, exact 497, and 390 CSS-pixel widths for the forecast, methodology, CMO, and ideology pages.

- Zero horizontal overflow at every width.
- Zero severe console/runtime errors.
- Forecast map and all three scenario controls rendered and switched successfully; the default House view contained 105 districts.
- CMO rendered all four current map modes.
- Ideology payload rendered 274 members, including 115 Democrats, with 115 Democratic points and table rows.

## Commands

```powershell
python -m pytest scripts/tests/test_forecast_dashboard.py scripts/tests/test_published_site_consistency.py scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
python -m pytest -q
```

Results: focused suite `30 passed`; workflow validation passed; full suite `478 passed` with 11 non-blocking existing deprecation/future/dtype warnings. Temporary rebuild, hash reconciliation, payload arithmetic, and browser checks were executed with independent Python/Chrome-CDP validation scripts against the paths named in the contract.

## Caveats

- Model selection rests on one direct Alabama forward holdout (2018 to 2022). This limits empirical confidence but is disclosed clearly and is not a release-integrity defect.
- Historical finance covers completed cycles while 2026 finance is a partial-cycle snapshot; finance effects should not be interpreted causally.
- The promoted manifest intentionally records source paths, so a rebuild redirected to a temporary directory has a different manifest build ID even though all numerical CSV outputs are byte-identical. Production hashes and lineage are internally valid.

## Release decision

Approved for publication under the contracted build and current generated-site state.
