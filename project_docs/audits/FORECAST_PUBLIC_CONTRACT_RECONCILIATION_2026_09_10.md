# Forecast public-contract reconciliation — 2026-09-10

Read-only documentation audit for checklist items `forecast-01`, `forecast-05` and
`forecast-06`. No builder, page, manifest, methodology, dashboard asset, data file
or warehouse file was modified; no forecast script was executed. Commands used were
reads, `git show`/`git log`/`git diff`/`git status` and shell header reads only.
Repository HEAD inspected: `720c3507b147bc0a7c048c4c84ab0262920802c1`. Audit
timestamp: `2026-09-11T03:44:29Z`.

**Important working-tree caveat.** The repository has extensive uncommitted work.
`scripts/build_2026_forecast_dashboard.py` and
`scripts/tests/test_forecast_dashboard.py` are modified in the working tree but
`scripts/` was not part of this audit's write scope. The working-tree builder
already contains part of the `forecast-01` copy fix; HEAD `720c350` does not.
Both states are reported below and distinguished explicitly.

## Artifacts read

- `data/processed/forecast_calibration/alabama_war_forecast_v1_manifest.json`
  (working tree = uncommitted; build `b5ae4b8054e027862fbe`, generated
  `2026-09-02T03:28:24.831126+00:00`, `git_commit`
  `88878b973fdac3cee95a8d8648da321e38e0021c`). The copy committed at HEAD
  (`70f0a9c`) is a different, older build: `00509565ea4fb62b4e10`, generated
  `2026-09-02T00:44:48.885584+00:00`, `git_commit`
  `94fad6e7a8e0fd90f076aa4530d4e96328bd3215`,
  `war_training_warehouse_run_id RUN-A4718C009110424B872392120C7F7E9F`.
- `project_docs/model/ALABAMA_WAR_GENERIC_FORECAST_V1.md`,
  `project_docs/model/ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md`,
  `project_docs/audits/ALABAMA_WAR_FORECAST_VALIDATION.md`.
- `scripts/build_2026_forecast_dashboard.py` (working tree and HEAD),
  `dashboard/forecast_dashboard.js`, `docs/index.html`, `docs/methodology.html`,
  `artifacts/site/alabama-2026-legislative-forecast.html`,
  `artifacts/site/forecast-methodology.html`.
- `docs/data/` forecast CSVs (headers and bounded samples only) and
  `data/processed/forecast_calibration/production_probability_model_card.json`.
- Lineage: `data/processed/war/alabama_war_v1/manifest.json` and
  `data/processed/war/post2016_southern_war_v3/manifest.json` were read only as
  committed Git blobs (`git show`) because the parent is rebuilding
  `data/processed/war/alabama_war_v1/` and `alabama_historical_war_v1/`
  concurrently. Neither churning directory was read from disk as current.

## Verdict summary

| Item | Verdict | Where |
|---|---|---|
| `forecast-01` "adjustment remains zero" | **Contradiction persists** | `docs/index.html:144` (committed at HEAD and in the working tree) and committed builder `scripts/build_2026_forecast_dashboard.py` line 316 at HEAD. Fixed in the uncommitted working tree builder, `docs/methodology.html`, and the test. |
| `forecast-05` uniform national→Alabama transfer | **Stated but not labeled; validity not demonstrated** | `docs/methodology.html:139`, field contract §15, model doc §2. No owner-selected label; no Alabama-specific transfer validation. |
| `forecast-06` active/excluded components | **Descriptions mostly consistent; downloads not aligned** | Legacy CMO-era contribution/decomposition/probability files remain published under `docs/data/`; the ledger links `2026_model_comparison.csv` whose contents are legacy models. |

Contradictions found: **9** (1 high, 5 medium, 3 low). Ambiguities/gaps: **7**.

## 1. `forecast-01` — structural adjustment "remains zero"

Manifest actual behavior (working-tree manifest): `structural_applied: true`,
`war_structural_specification: "decaying_lag"`,
`structural_selection_policy: "owner_selected; forward validation retained as
advisory"`, `selected_specification: "generic_war_structural"`, `selection_reason:
"owner_required_war_structural_expectation_with_generic_ballot_environment"`,
`status: "published_owner_selected_environment_adjusted_war_forecast_with_validation_warning"`,
`diagnostics.structural_improves_baseline_on_holdout: false`,
`diagnostics.selected_forward_mae: 7.655182820521864` vs
`baseline_forward_mae: 7.073410990280289`.

### The contradiction (verbatim)

- `docs/index.html:144` (working tree **and** committed at HEAD, inside the
  `section class="section method"` paragraph):
  > "Both nominees are evaluated as generic candidates. Prior WAR/CMO, candidate
  > history, ideology, and fundraising are excluded. **A structural adjustment was
  > tested from 2018 into 2022, worsened margin error, and therefore remains zero
  > in the headline.**"
- `git show HEAD:scripts/build_2026_forecast_dashboard.py` line 316 contains the
  identical sentence. So at HEAD the contradiction existed in both the builder
  source and the published page.
- `artifacts/site/alabama-2026-legislative-forecast.html` (the builder's OUTPUT,
  payload `"version":"b5ae4b8054e027862fbe"`) also still contains the sentence.
  The page and artifact were both produced with the current payload but the stale
  prose, i.e. the payload was refreshed without regenerating this paragraph's
  template text.

### The uncommitted partial fix (already in the working tree)

- `scripts/build_2026_forecast_dashboard.py` working-tree line 319 now reads:
  > "Both nominees are evaluated as generic candidates. Prior WAR/CMO, candidate
  > history, ideology, and fundraising are excluded. The headline includes the
  > owner-selected structural adjustment, including its symmetric incumbency
  > effect. It performed worse than the generic-ballot-only benchmark on the sole
  > direct Alabama forward holdout; that comparison is an advisory limitation, not
  > evidence that the structural term is zero. Candidate-specific WAR remains
  > fixed at zero."
- `scripts/tests/test_forecast_dashboard.py` now asserts the new wording and
  asserts `"therefore remains zero in the headline" not in explanation`.
- `docs/methodology.html` (working tree, build `b5ae4b80`) is already consistent:
  no occurrence of "remains zero"; sections 1–6 match the manifest.

### Where it does **not** persist

`docs/methodology.html` (all lines), `dashboard/forecast_dashboard.js`,
`data/processed/forecast_calibration/alabama_war_forecast_v1_manifest.json`,
`project_docs/model/ALABAMA_WAR_GENERIC_FORECAST_V1.md`,
`project_docs/model/ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md`,
`project_docs/audits/ALABAMA_WAR_FORECAST_VALIDATION.md`. There is **no**
downloads README under `docs/data/`; no model card for the WAR forecast other
than the manifest (the only `model_card` files published are
`cmo_model_card.md`, which is CMO-scoped, and
`production_probability_model_card.json`, which is the probability calibrator and
does contradict the active probability family — see row 6 below).

## 2. `forecast-05` — uniform national-to-Alabama generic-ballot transfer

### Where it is stated

- `docs/methodology.html:139` (`section id="environment"`):
  > "The national quality-gated generic ballot is used as a stand-in for the
  > election environment because Alabama-specific polling is sparse. Its change
  > from the 2024 national presidential margin is applied uniformly to every
  > district's 2024 presidential margin. The Dem and Rep scenario tabs add or
  > subtract one historical national polling-error standard deviation."
- `docs/index.html:136` (quick method): "Headline applies the polling-implied
  national swing and the generic WAR structural expected gap".
- `docs/index.html:144` first sentence: "The headline begins with each district's
  2024 presidential margin and applies the national swing implied by current
  generic-ballot polling."
- `project_docs/model/ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md:15`:
  > "Historical validation reconstructs 2018 and 2022 district baselines as prior
  > presidential district margin plus the contemporaneous generic-ballot swing
  > from the prior national presidential margin. The 2026 baseline uses the
  > published uniform generic-ballot adjustment to each district's 2024
  > presidential margin."
- `project_docs/model/ALABAMA_WAR_GENERIC_FORECAST_V1.md:7`: "The baseline is each
  district's prior presidential margin shifted by the national generic ballot."

### Labeling

The uniform transfer is **not labeled as an owner-selected assumption anywhere**.
The only `owner`-labeled statements concern the *structural specification*, not the
transfer: the model doc says the structural gap is applied "at the project owner's
direction"; the validation audit says the specification was chosen "by
owner-required model definition"; the manifest's owner-selected field is
`structural_selection_policy`. `generic_ballot_environment: true` in the manifest
records that the environment channel is on, not that the uniform transfer is an
owner choice.

The closest public hedge is `docs/methodology.html:143`: "The national generic
ballot is an imperfect proxy for Alabama's state-legislative environment."

### Validation evidence for transfer validity: none in the audit

`project_docs/audits/ALABAMA_WAR_FORECAST_VALIDATION.md` records only the single
2018→2022 Alabama forward test (33 races, 2039 training races; MAE 7.655 vs 7.073)
and the limitation "Alabama supplies only one direct forward cycle, so calibration
and structural estimates remain sample-limited". It does **not** test whether the
national swing transfers uniformly into Alabama legislative districts. Its one
Alabama experiment shows the structural specification performing *worse* than the
generic-ballot-only benchmark, so it cannot be read as transfer validation. The
manifest has no transfer-validation field.

Dead builder templates (`METHODOLOGY` constant at working-tree line 325,
`build_methodology` line 341, `build_methodology_v2` line 361) contain the only
"Historical tests support transferring none of the swing before 2018, half in
2018, and the full swing in 2022 and 2026" language. Those templates are never
called (verified: `build_methodology_v3` is the only call site, at line 520), so
that claim is not published, but it is a misleading source-level statement.

Conclusion: the transfer is a stated, undocumented-as-owner-selected modeling
assumption. Its Alabama validity is **not established**; the historical 2018/2022
reconstruction of the baseline is not a validity test of the 2026 uniform
transfer.

## 3. `forecast-06` — active vs excluded components

Manifest (working tree):

Active/included
- `generic_ballot_environment: true`
- `generic_candidate_assumption: true`
- `structural_applied: true`, `war_structural_specification: decaying_lag`,
  `ridge_alpha: 100.0`
- `incumbency_treatment: included_as_symmetric_race_condition_in_war_structure`
- `simulation_draws: 50000`; `probability: {family: student_t, df: 5.0, scale: 2.0}`
- `design_features`: 34 names — baseline margins, years/time, state dummies,
  chamber, office family, prior presidential margin, ticket-change lag terms,
  incumbency balance. No finance, candidate, ideology or history feature.

Excluded
- `finance_used: false`
- `candidate_history_used: false`
- `ideology_used: false`
- `candidate_war_adjustment: 0.0` (candidate-specific residual WAR fixed at zero)

Public description agreement:

| Component | Manifest | Public copy | Agreement |
|---|---|---|---|
| Generic-ballot environment | true | methodology:139; index:136/144 | consistent |
| Structural WAR adjustment | applied, owner-selected | index method paragraph (stale) says zero → **contradiction**; methodology:138/141 consistent; field contract §17 consistent | contradiction in index |
| Symmetric incumbency | included structurally | methodology:138,140; index:144/411 | consistent |
| Candidate WAR = 0 | 0.0 | methodology:138,140; index:136/144/411; JS:411 | consistent |
| Finance excluded | false | index:135/411/395 "not used by forecast"; methodology:140 | description consistent |
| Candidate history excluded | false | index:411; payload provenance "displayed only and excluded"; JS:391 | consistent |
| Ideology excluded | false | methodology:140; index:144 | consistent |
| Student-t(5), scale 2.0, 50k draws | manifest | methodology:142; index:136 | consistent |
| Probability calibrator files | — | `docs/data/production_probability_model_card.json` says `{"family":"normal","scale":6.0,"df":null}`, training 1,188 races | **contradiction** (published, unlinked) |

Contribution tables and downloads (`docs/data/`):

- The page's own "Forecast components" table is rendered from the payload
  (`DATA.contributionVariables` and per-district `steps`; JS
  `dashboard/forecast_dashboard.js:61,265-268`) and lists exactly: "Generic-ballot
  district baseline", "Generic WAR structure", "WAR incumbency effect",
  "Candidate WAR (fixed at zero)", "Polling-error scenario". This is consistent
  with the manifest.
- Published but never linked by the forecast pages, and inconsistent with the
  active finance-free generic-WAR contract:
  - `2026_model_variable_contributions.csv` — header
    `chamber,district,step,variable,value,contribution,model,model_label,running_margin`,
    rows use `model=ensemble_ramp_ridge_80_20` and variables such as
    `model_intercept_and_chamber`, plus finance/incumbency terms in
    `dashboard/forecast_dashboard.js:30-44`.
  - `2026_forecast_decomposition.csv` — header includes `cmo_adjustment`,
    `finance_adjustment`, `demographic_residual_adjustment`,
    `ensemble_adjustment`, `selected_specification=ensemble_ramp_ridge_80_20`.
  - `forecast_experiment_tournament_summary.csv`, `2026_residual_layer_backtest_summary.csv`
    (CMO-era `national_environment_post2016_ramp` promotion), `robust_forecast_v1_*`,
    `post2016_headline_v1_*`, `post2016_polling_cmo_*`.
- `alabama_war_forecast_v1_2026_scenarios.csv` (the download the page does link)
  carries the active generic-WAR fields (`war_structural_expected_gap`,
  `generic_downballot_lag`, `incumbency_adjustment`, `generic_structural_adjustment`,
  `candidate_war_adjustment=0`, `candidate_history_used=False`, `finance_used=False`,
  `generic_candidate_assumption=True`) plus legacy columns
  (`geographic_elasticity`, `demographic_swing_2024_2026`,
  `demographic_poll_adjusted_margin`, `low_elasticity_075_margin`,
  `high_elasticity_125_margin`, `votehub_2026_dem_margin`,
  `fundraising_adjustment` — all-zero) and a stale `status` value
  `catalist_yougov_demographic_transfer_selected` alongside
  `source_scenario=uniform_generic_ballot_environment`.
- The index "Election baseline" provenance entry links
  `data/2026_model_comparison.csv`; that file's `model` values are
  `ensemble_ramp_ridge_80_20`, `post2016_ramp`, `ramp_all_elastic_net`,
  `ramp_all_extra_trees`, `ramp_all_gradient_boosting`, `ramp_all_spline_ridge`
  — a legacy CMO-era comparison, not 2024 presidential results.

## 4. Reconciliation table

| # | Claim (verbatim) | Source (file:line) | Manifest field | Status |
|---|---|---|---|---|
| 1 | "Candidate history and fundraising are not forecast inputs." | docs/index.html:135 | candidate_history_used=false, finance_used=false | consistent |
| 2 | "Headline applies the polling-implied national swing and the generic WAR structural expected gap; candidate-specific WAR remains zero." | docs/index.html:136 | structural_applied, generic_ballot_environment, candidate_war_adjustment=0 | consistent |
| 3 | "Dem/Rep scenario … move every district by one historical national polling-error standard deviation." | docs/index.html:136 | scenarios `polling_error_adjustment` | consistent |
| 4 | "District probabilities use a Student-t curve; chamber summaries use 50,000 simulations with shared statewide and chamber uncertainty." | docs/index.html:136 | probability.student_t, simulation_draws=50000 | consistent |
| 5 | "The displayed MAE is the average district-margin error when the model was trained on 2018 and tested on 2022." | docs/index.html:137; builder:312 | forward_test=train_post2016_southern_before_2022_test_alabama_2022 (2039 train races) | **contradiction** |
| 6 | "A structural adjustment was tested from 2018 into 2022, worsened margin error, and therefore remains zero in the headline." | docs/index.html:144; builder HEAD:316 | structural_applied=true; owner_selected policy | **contradiction (high)** |
| 7 | "Observed, modeled, missing, and imputed values are distinguished in district details." | docs/index.html:144 | — (no general taxonomy field) | ambiguous |
| 8 | "Full methodology / Historical WAR model" links | docs/index.html:144 | — | consistent |
| 9 | Payload model description: "generic ballot shifts … WAR model adds its generic structural expectation. Candidate-specific WAR is fixed at zero." | docs/index.html payload (line 144) | structural_applied, candidate_war_adjustment | consistent |
| 10 | contributionVariables list (5 components) | docs/index.html payload / JS:61,265-268 | design_features, structural, incumbency, candidate WAR, scenarios | consistent |
| 11 | Provenance "Candidate history … displayed only and excluded"; download `alabama_war_v1_candidate_cycle_war.csv` | docs/index.html payload (line 144) | candidate_history_used=false | consistent in wording; linked WAR export is pre-repair (staleness) |
| 12 | Provenance "Methodology … generic-candidate WAR structural forecast definitions" | docs/index.html payload (line 144) | manifest | consistent |
| 13 | Provenance "Election baseline" → `data/2026_model_comparison.csv` | docs/index.html payload (line 144) | — | **contradiction** (file holds legacy model comparison) |
| 14 | JS: candidate finance "not used by forecast" | docs/index.html JS:395 | finance_used=false | consistent |
| 15 | JS: "Candidate WAR, history, ideology, and fundraising are not used" | docs/index.html JS:411 | three excluded flags + zero candidate WAR | consistent |
| 16 | JS: "retrospective race residuals … shown for context only … does not use prior WAR" | docs/index.html JS:391 | candidate_history_used=false | consistent |
| 17 | JS dead maps `finance_ratio_capped`, `finance_x_open`, `cmc_adjustment` etc. | docs/index.html JS:174-191; dashboard/forecast_dashboard.js:30-44 | no finance/CMO variable in active design | **contradiction (low; dead code, no call site)** |
| 18 | Methodology dek: "generic-candidate WAR forecast anchored to the national generic ballot, with prior candidate performance explicitly excluded." | docs/methodology.html:136 | manifest | consistent |
| 19 | Identity formula + "Candidate-specific residual WAR is fixed at zero" | docs/methodology.html:138 | required identity; candidate_war_adjustment=0 | consistent |
| 20 | "Its change … is applied uniformly to every district's 2024 presidential margin." | docs/methodology.html:139 | generic_ballot_environment=true; no owner-selected transfer field | ambiguous (forecast-05 gap) |
| 21 | "The prospective design does not contain candidate identity, prior WAR or CMO, repeat-candidate history, ideology, fundraising, receipts, or expenditures." | docs/methodology.html:140 | finance_used, candidate_history_used, ideology_used = false | consistent |
| 22 | "fits the selected WAR design on 2039 eligible Southern races after 2016 and before 2022, then evaluates 33 Alabama races in 2022" | docs/methodology.html:141 | forward_test, forward_test_rows=33, historical_rows=97 | consistent |
| 23 | "baseline records 7.07 points of MAE and 97.0% winner accuracy. The selected WAR structural specification records 7.66 points of MAE." | docs/methodology.html:141 | 7.073410990280289 / 7.655182820521864 | consistent |
| 24 | "Student-t … five degrees of freedom and a 2.00-point scale … 50,000 correlated simulations with national (2.20), statewide (2.01), chamber (1.03), district (5.91)" | docs/methodology.html:142 | probability{student_t,5.0,2.0}; draws 50000; robust_forecast_v1_error_components | consistent (component file is legacy-named) |
| 25 | "performed worse than the generic-ballot-only benchmark on it" + "national generic ballot is an imperfect proxy" | docs/methodology.html:143 | structural_improves_baseline_on_holdout=false | consistent |
| 26 | Downloads list (scenarios, forward predictions, forward metrics, manifest, WAR ratings) | docs/methodology.html:144 | outputs[] | consistent naming; WAR ratings export stale |
| 27 | "The published specification applies that structural expected gap at the project owner's direction." | model doc:11 | structural_selection_policy, selection_reason | consistent |
| 28 | "The baseline is each district's prior presidential margin shifted by the national generic ballot." | model doc:7 | generic_ballot_environment | consistent |
| 29 | "2026 baseline uses the published uniform generic-ballot adjustment to each district's 2024 presidential margin." | field contract:15 | scenarios `uniform_poll_adjusted_dem_margin` (used as baseline) | consistent statement; not labeled owner-selected (forecast-05) |
| 30 | Prospective identity and required zero/false fields | field contract:17,19 | required fields present in scenarios/forward CSV headers | consistent |
| 31 | "Selected specification … by owner-required model definition; forward validation is advisory." | validation audit:8 | structural_selection_policy | consistent |
| 32 | "Candidate-specific WAR is zero, incumbency is included structurally, candidate history is false, finance is false, and the forecast identity reconciles within floating-point tolerance." | validation audit:10 | all four fields + max_forecast_identity_error 7.1e-15 | consistent |
| 33 | Holdout assessment: structural performs worse than generic-ballot-only | validation audit:11 | structural_improves_baseline_on_holdout=false | consistent |
| 34 | Dead builder copy: "Historical tests support transferring none of the swing before 2018, half in 2018, and the full swing in 2022 and 2026." | builder:354 (dead `METHODOLOGY`/v1/v2, never called) | no such field | **contradiction (low; not rendered)** |
| 35 | Dead builder copy: `P(D win)=Φ(margin/6.0)`, "1,188 contested … races", "Basic"/"Fundamentals+" | builder:325-396 (dead templates) | active family student_t/2.0 | **contradiction (low; not rendered)** |
| 36 | `2026_model_variable_contributions.csv` header + finance/CMO variable rows | docs/data (published, unlinked) | finance_used=false; no CMO in design | **contradiction** |
| 37 | `2026_forecast_decomposition.csv` header `cmo_adjustment`,`finance_adjustment`,`demographic_residual_adjustment` | docs/data (published, unlinked) | no such active components | **contradiction** |
| 38 | `production_probability_model_card.json` normal/6.0, 1188 races | docs/data (published, unlinked) | probability student_t df5 scale2 | **contradiction** |
| 39 | `alabama_war_forecast_v1_2026_scenarios.csv` `status=catalist_yougov_demographic_transfer_selected`, `fundraising_adjustment` (0.0), elasticity/demographic columns | docs/data (linked download) | generic uniform environment; finance excluded | ambiguous/stale |
| 40 | `2026_model_comparison.csv` contains legacy `ensemble_ramp_ridge_80_20` etc. | docs/data (linked download) | selected_specification generic_war_structural | **contradiction** |
| 41 | `docs/data/` forecast downloads include `post2016_headline_v1_*`, `robust_forecast_v1_*`, `post2016_polling_cmo_*`, `forecast_experiment_tournament_summary.csv`, `2026_residual_layer_backtest_summary.csv` | docs/data | manifest outputs[] only lists 7 alabama_war_forecast_v1 files | ambiguous (no published/superseded separation) |
| 42 | `robust_forecast_v1_error_components.csv` is the live uncertainty-component input for methodology v3 | builder:403; docs/methodology.html:142 | — | ambiguous (legacy-named active input) |
| 43 | No downloads README or forecast model card exists in `docs/data/` | (absence) | — | unstated |
| 44 | `docs/index.html` inlined JS duplicates `dashboard/forecast_dashboard.js` | docs/index.html:145+ | — | consistent |

## 5. Required exact edits

Line numbers are working-tree as observed; each edit is keyed by verbatim text so
it survives concurrent line shifts. `forecast-01` edits are documentation/render
only and need no model rebuild.

**E1 — `docs/index.html` line 144 (method paragraph).** Replace
`A structural adjustment was tested from 2018 into 2022, worsened margin error, and
therefore remains zero in the headline.`
with
`The headline includes the owner-selected structural adjustment, including its
symmetric incumbency effect. It performed worse than the generic-ballot-only
benchmark on the sole direct Alabama forward holdout; that comparison is an
advisory limitation, not evidence that the structural term is zero.
Candidate-specific WAR remains fixed at zero.`
(Preferred: regenerate `docs/index.html` and
`artifacts/site/alabama-2026-legislative-forecast.html` from the working-tree
builder, which already emits this text, and then re-run the site publisher so the
shared theme is reapplied. Do not hand-edit only the artifact.)

**E2 — `docs/index.html` line 137; `scripts/build_2026_forecast_dashboard.py`
working-tree line 312 (same text in both).** Replace
`The displayed MAE is the average district-margin error when the model was trained
on 2018 and tested on 2022.`
with
`The displayed MAE is the average Alabama district-margin error for the 2022
holdout after training on eligible post-2016 Southern races before 2022 (2,039
training races).`
The same string must be corrected in the builder template or it will reappear on
the next render.

**E3 — `docs/data/2026_model_comparison.csv` link in `docs/index.html` payload
(provenance "Election baseline").** Either repoint the link to the scenario/
baseline download (`data/alabama_war_forecast_v1_2026_scenarios.csv`) or replace
the file with a generic-WAR baseline comparison. Currently the linked file is a
legacy `ensemble_ramp_ridge_80_20` comparison.

**E4 — remove or regenerate legacy published forecast downloads.** In
`scripts/build_2026_forecast_dashboard.py` main() copy list (working-tree lines
531–560) remove the copies of `2026_model_variable_contributions.csv`,
`2026_forecast_decomposition.csv`, `forecast_experiment_tournament_summary.csv`,
`2026_residual_layer_backtest_summary.csv`, `2026_model_comparison.csv` (if not
repointed), `production_probability_*`, `robust_forecast_v1_*`,
`post2016_headline_v1_*`, and `post2016_polling_cmo_*` unless the contract is
updated; delete the corresponding files from `docs/data/`. Keep only artifacts
that describe the active generic-WAR bundle, or move the rest under an explicitly
labelled superseded/research path.

**E5 — `data/processed/forecast_calibration/alabama_war_forecast_v1_2026_scenarios.csv`
schema (requires a forecast-script run; parent-owned).** Drop the legacy columns
`geographic_elasticity`, `demographic_swing_2024_2026`,
`demographic_poll_adjusted_margin`, `low_elasticity_075_margin`,
`high_elasticity_125_margin`, `votehub_2026_dem_margin`, `fundraising_adjustment`;
replace `status=catalist_yougov_demographic_transfer_selected` with a status that
describes the uniform generic-ballot environment (or document the column in the
field contract). This is the one forecast-06 edit that needs the bundle rebuilt.

**E6 — dead builder templates.** Delete the unused `METHODOLOGY` constant
(working-tree line 325), `build_methodology` (line 341) and `build_methodology_v2`
(line 361) from `scripts/build_2026_forecast_dashboard.py`. They are never called
and carry CMO-era/full-swing/6.0-point claims that contradict the active
contract.

**E7 — dead JS label maps.** Delete `variableLabels`/`variableGroups` from
`dashboard/forecast_dashboard.js` (lines 30–44) — no call site exists — and
regenerate `docs/index.html`/artifact so the inlined copy is removed.

**E8 — `forecast-05` labeling (documentation).** Append to
`docs/methodology.html:139`: "The uniform national-to-Alabama transfer is an
owner-selected model assumption; the validation audit does not establish its
Alabama-specific validity beyond the single 2022 forward holdout." Mirror the
label in `project_docs/model/ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md:15` and
`project_docs/model/ALABAMA_WAR_GENERIC_FORECAST_V1.md:7`, and add the missing
transfer-validity limitation to
`project_docs/audits/ALABAMA_WAR_FORECAST_VALIDATION.md`.

**E9 — stale upstream WAR export published.** `docs/data/alabama_war_v1_race_war.csv`,
`docs/data/alabama_war_v1_candidate_cycle_war.csv` and
`docs/data/alabama_war_v1_manifest.json` are the pre-repair `alabama_war_v1`
copies consumed by this forecast bundle; either refresh them together with the
forecast rebuild or label them as the forecast's superseded inputs.

## 6. Lineage staleness

Established from manifests and Git blobs:

- The forecast manifest (working tree) records `git_commit`
  `88878b973fdac3cee95a8d8648da321e38e0021c` ("Publish Southern historical WAR
  map"), `generated_at_utc 2026-09-02T03:28:24Z`, and
  `war_training_warehouse_run_id RUN-85A4692E481448B6BB1380D76E07742B` — a
  pre-repair warehouse run.
- Its declared `inputs` include `data/processed/war/alabama_war_v1/race_war.csv`
  (`sha256 a971d5e8…`), `data/processed/war/alabama_war_v1/manifest.json`
  (`sha256 50f6a92a…`) and
  `data/processed/war/post2016_southern_war_v3/manifest.json`
  (`sha256 0ea55873…`).
- None of those three hashes matches the corresponding committed blob at HEAD or
  at the forecast's own `git_commit 88878b9`: HEAD blobs hash
  `alabama_war_v1/manifest.json = 7fc26b30…`,
  `alabama_war_v1/race_war.csv = 9a95e3ff…`,
  `post2016_southern_war_v3/manifest.json = 25d9eb5d…`. The forecast bundle's
  recorded input identity is therefore **not reproducible from any committed
  revision**; the consumed copies were working-tree variants. This is a recorded
  hash mismatch, not an inference.
- The committed `alabama_war_v1` manifest (`42e2ad1`, which is the only commit
  that has touched it) declares run `AL-WAR-V1-E1F8E11BF2853322239F`,
  `source_model_run_id WAR-POST2016-V3-D9C7EE17BD14B8C7D23A`, and consumes
  `post2016_southern_war_v3/{race_war,candidate_cycle_war}.csv`.
- At the forecast's `git_commit 88878b9`, the committed
  `post2016_southern_war_v3/manifest.json` still declared
  `model_run_id WAR-POST2016-V3-D9C7EE17BD14B8C7D23A`,
  `warehouse_build_run_id RUN-4ED478C647B34A7B9A402970625DB334`. The directory was
  only re-bound to the approved run `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`
  (generated `2026-09-08`, warehouse `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`) at
  `d4497d7`; the not-approved `WAR-POST2016-V3-8BB52074EC806C5BF6BF` is preserved
  under `data/processed/war/post2016_southern_war_v3_archive/`.
- Therefore the forecast consumed a pre-retrain (`D9C7EE17`) `alabama_war_v1`
  lineage. The exact run id the task associates with that input
  (`WAR-POST2016-V3-8BB52074EC806C5BF6BF`) is **not** the run recorded in the
  committed `alabama_war_v1` manifest; that manifest records `D9C7EE17`. Whether
  `D9C7EE17` is an ancestor of `8BB52074` is **not established** by the committed
  manifests read here. What *is* established is that the forecast's consumed WAR
  lineage is pre-repair and does not include the approved `4AF79A70` run.

Conclusion: the forecast bundle is a stale consumer. Its inputs predate the
`4AF79A70` approval, its recorded input hashes do not match current artifacts, and
it must be rebuilt from the approved Southern WAR lineage before
`forecast-01/05/06` are described as validated. **No numerical impact is asserted
or implied by this audit.**

## 7. Already consistent

- `docs/methodology.html` sections 1–6 (identity, environment, generic candidates,
  forward test, uncertainty, limitations) agree with the manifest, the field
  contract and the validation audit, including the explicit statement that the
  structural specification performed worse than the baseline and that the
  probability scale is sample-limited.
- The index hero, quick-method list, payload model description,
  `contributionVariables`, the district "Forecast components" table ("Candidate
  WAR, history, ideology, and fundraising are not used"), the candidate-history
  context note, and the finance "not used by forecast" label all agree with
  `structural_applied=true`, the zero candidate-specific WAR and the three
  excluded flags.
- The field contract's required-field/exclusion rules are satisfied by the
  `alabama_war_forecast_v1_2026_scenarios.csv` and
  `alabama_war_forecast_v1_forward_predictions.csv` headers
  (`candidate_war_adjustment`, `candidate_history_used`, `finance_used`,
  `generic_candidate_assumption`).
- The validation audit correctly records the advisory (non-gating) status of the
  forward test and the sample-limited limitation.
- The probability family values shown publicly (`student_t`, df 5, scale 2.00,
  50,000 draws, error components 2.20/2.01/1.03/5.91) match the manifest and the
  live component input.

## 8. Not established / limitations

- The Alabama-specific validity of the uniform national→Alabama generic-ballot
  transfer is **not established**; no validation output in this repository tests
  it (forecast-05).
- The forecast bundle is a **stale consumer** of a pre-repair `alabama_war_v1`
  lineage; no numerical or seat-share impact of that staleness has been measured
  here.
- Whether `WAR-POST2016-V3-D9C7EE17BD14B8C7D23A` is an ancestor of the archived
  not-approved `WAR-POST2016-V3-8BB52074EC806C5BF6BF` is **not established** from
  the committed manifests read.
- The `alabama_war_forecast_v1_historical_panel.csv` output listed in the
  working-tree manifest was not opened; its internal consistency is not assessed.
- Checklist completion dependency:
  - `forecast-01` — completable by documentation/render edits only (E1; then
    regenerate `docs/index.html` + artifact). No model rebuild needed.
  - `forecast-05` — completable by documentation edits (E8) if the acceptance
    criterion is "documented as an owner-selected assumption and not
    demonstrated"; if the criterion requires demonstrated transfer validity, it
    needs an expanded validation build and remains open.
  - `forecast-06` — completable by E3/E4/E6/E7 and by E9 after the forecast
    bundle is rebuilt; the scenario-schema cleanup (E5) and the stale-WAR refresh
    (E9) require a rebuilt forecast bundle produced from the approved Southern
    WAR lineage. Until then, only the description-level portion can be closed.