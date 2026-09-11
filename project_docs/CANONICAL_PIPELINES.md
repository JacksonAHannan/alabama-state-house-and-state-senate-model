# Canonical pipelines

Routing checked against the builders on 2026-09-05. This index identifies the
current consumers and their side effects; it does not certify the freshness or
scientific validity of every existing output. Read each product's manifest,
contract, and latest validation/dependency audit before rebuilding or publishing.
Paths and commands below are relative to the repository root.

## Four product routes

| Product | Current analytical source | Page entry point | Output / side effect |
|---|---|---|---|
| 2026 Alabama forecast | `data/processed/forecast_calibration/alabama_war_forecast_v1_manifest.json` and its scenario/diagnostic exports | `python scripts/build_2026_forecast_dashboard.py --artifact-only` | Local candidate HTML in `artifacts/site/`; omitting `--artifact-only` also writes `docs/index.html`, methodology and downloads |
| Historical Alabama WAR | `data/processed/war/alabama_historical_war_v1/manifest.json` and its race/candidate exports | `python scripts/build_war_story_page.py` | Writes local artifacts, `docs/cmo.html`, methodology and downloads; not preview-only |
| Ideology and caucuses | Reviewed issue evidence and descriptive analysis consumed by `scripts/build_democratic_transition_page_v2.py`, joined to historical Alabama candidate-cycle WAR | `python scripts/build_democratic_transition_page.py` | Writes `artifacts/site/ideology-performance.html`; the site publisher copies it to `docs/ideology-performance.html` |
| Southern WAR, 2016–2024 | `data/processed/war/southern_historical_war_v1/manifest.json` and its race/candidate exports | `python scripts/build_southern_war_map.py` | Writes `docs/southern-war.html`, methodology, payload, downloads, join audit and a local artifact; applies shared theme |

Both the historical builder and the map builder require
`project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json` to match the exact modern
v3 manifest and independent review record and to contain
`approved_for_descriptive_historical_use`. On 2026-09-08 that decision was
re-bound to the retrained run `WAR-POST2016-V3-4AF79A70EAA8F39EBD49` after the
independent review recorded in
`audits/SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_08.md`; the historical run
`WAR-SOUTH-HIST-V1-45EC0B380AAEA007C2DF` and the local map artifacts were rebuilt
from it. The exact previously reviewed run (`WAR-POST2016-V3-8BB52074EC806C5BF6BF`,
NOT APPROVED) is preserved byte for byte under
`data/processed/war/post2016_southern_war_v3_archive/`. Approval is descriptive
historical use only; publication of `docs/` remains a separate authorized action.

Since 2026-09-10 every publication-writing route above checks its declared
inputs before reading model rows (`scripts/southern_war_release_gate.py`):
`build_alabama_war_v1.py` and `build_alabama_historical_war_v1.py` require the
approved v3 decision and an Alabama v1 export derived from that run;
`build_war_story_page.py` and `build_democratic_transition_page_v2.py` call
`require_alabama_historical_release`, which requires the historical export's
declared files to be unchanged and its Southern and Alabama sources to be the
approved and published runs; `build_2026_forecast_dashboard.py` requires every
declared forecast input to match disk. Refusals name the file or run ids
(`Declared manifest file changed: <path>`, `… derives from <run>, not approved
<run>`). The gate also honors `accepted_input_revisions` in the decision file:
an explicit, independently reviewed statement that one declared input changed
bytes after approval without changing what the run consumed, matched only on
the exact old and new digests and the review record's hash. The first such
entry (2026-09-10) covers the warehouse file after the metadata-only runs
`RUN-91B2A0C3…`/`RUN-55E4997B…`, supported by a byte-identical scratch replay
and `audits/SOUTHERN_V3_INPUT_REVISION_REVIEW_2026_09_10.md`. File existence,
a newer version, or an environment flag never satisfy a gate.

Current route status (2026-09-11, `audits/SITE_RELEASE_2026_09_11.md`): the
approved Southern residual source is `WAR-POST2016-V3-530FBD4238CC483E557C`
(warehouse `RUN-504CE4C4DF904D88A5A40D268F3FCEAB`); its manifest declares the
warehouse by training-frame content digest (`training_frame`, verified live by
the gate) rather than whole-file hash, so unrelated warehouse writes no longer
trip the release gate. All four pages were republished on this lineage:
`WAR-SOUTH-HIST-V1-6D84680E7B757B057AF1`, `AL-WAR-V1-C00FF05BC2BE58E16087`,
`AL-HIST-WAR-V1-76814789B2F7641E4255`, forecast build `368bb272a990ff436e56`.
Superseded runs `4AF79A70…` and `A937708D…` are archived byte for byte.
`build_war_story_page.py --artifact-only` renders without writing `docs/`.

The Alabama certified-canvass integration that unblocked the route is recorded in
`coordination/SOUTHERN-WAR-COMPLETION-20260908.md` and
`audits/ALABAMA_CERTIFIED_CANONICAL_REPAIR_2026_09_08.md`: the 2018 certified
cohort was loaded (`scripts/load_alabama_2018_certified_source.py`), Alabama
canonical candidates were bridged to certified cells with 21 total corrections
(`scripts/repair_alabama_canonical_certified_totals.py`, schema 27), and the outcome
mart was rebuilt so every Alabama strict race carries its canvass source file. The
preparation producer now fails if a bridged canonical total disagrees with the
canvass. Missing-context sensitivity and bootstrap uncertainty for the v3 run are
recorded by `scripts/audit_southern_v3_context_sensitivity.py`; per-state release
limitations are published by the historical builder's `state_release_coverage.csv`
and the map methodology.

The ideology entry point delegates to the v2 page implementation; that suffix
does not select a WAR version. Its payload composes the existing caucus and
ideology analysis helpers. The separate `scripts/build_caucus_analysis_page.py`
renders `artifacts/site/caucuses.html`, also copied by the site publisher. Neither
renderer is a complete legislative-evidence or cluster rebuild.

## Analytical build stages and prerequisites

These are individual stages, not interchangeable end-to-end refresh commands.
Inspect their imports, input lists, source manifests and side effects first.

- **Modern Southern residual source:**
  `python scripts/retrain_post2016_southern_war_v3.py` produces
  `data/processed/war/post2016_southern_war_v3/`. It consumes prepared warehouse
  inputs and existing context/diagnostic products; it does not acquire and
  reconcile all raw sources. Retraining changes model outputs and requires
  its own validation, not merely a request to render a page.
- **Historical Alabama:** `python scripts/build_alabama_historical_war_v1.py`
  produces `data/processed/war/alabama_historical_war_v1/`. It consumes historical
  race/candidate/context inputs, the modern Southern manifest and
  `data/processed/war/alabama_war_v1/` modern residuals. Some compatibility inputs
  still carry `cmo_v5` filenames; that is not the published WAR definition.
- **Historical Southern:** `python scripts/build_southern_historical_war_v1.py`
  produces `data/processed/war/southern_historical_war_v1/` from strict warehouse
  outcomes, published modern Southern residuals and name evidence, including
  the historical Alabama candidate export. The map renderer additionally needs
  the registered election-year boundary manifest. The acquisition command
  `python scripts/acquire_southern_legislative_geography.py --offline` verifies
  locally available source assets; it cannot download missing files offline.
- **Forecast:** `python scripts/run_alabama_war_generic_forecast.py` produces
  the `alabama_war_forecast_v1` analytical bundle under
  `data/processed/forecast_calibration/`. It consumes existing WAR, roster,
  polling/environment and uncertainty inputs. Source refresh and upstream
  certification are separate prerequisites; a forecast renderer does neither.
- **Ideology:** source loading, identity reconciliation, roll-call eligibility,
  issue evidence, scale estimation, descriptive grouping and page rendering are
  separate stages. Trace the current payload's actual dependencies and the
  evidence-repair audits before choosing which to rerun. There is not yet a
  certified single-command rebuild for this entire product.

See the [warehouse architecture](WAREHOUSE_ARCHITECTURE.md) for source/domain
loaders and lifecycle safeguards. The election database bootstrap creates a new
election-only database; it must never replace the populated central warehouse.
After a source repair, resolve affected stale dependencies before running any
of the publication-writing commands above.

## Definitions and release status

The historical public WAR products use a Split Ticket-style race residual:
legislative-minus-ticket margin gap minus fitted structural expected gap.
Candidate rows are opposite party orientations of that residual, not pooled
candidate-career coefficients. The historical Alabama map and current combined
ideology page use the same historical Alabama WAR export.

Modern Southern scores retain the published v3 residual source. The Southern
2016 and pre-2016 Alabama extensions are explicitly labeled backcasts. The
finance overlay is not an input to the current headline historical WAR.
The prospective forecast is a separate generic-candidate product; its own
manifest and contract control active components and validation limitations.

`post2016_southern_war_v4` is research-only pending its documented coverage and
publication decisions. CMO v4/v5 and other legacy experiments are not current
public defaults merely because they exist; some remain required compatibility
inputs. Trace consumers before deletion. Promotion or changing a gate requires
an explicit reviewed decision and updated contracts, never file-existence or
highest-version fallback.

### Completion scope and accountable roles

Completing the existing four products does not require migration to research
v4. Retain the current Southern v3 residual source and labeled 2016 backcasts;
defer v4 promotion, its additional coverage expansion and its research-specific
validation work. Its existing failed/unresolved gates remain in force. This
disposition does not waive the current product's source, plan or release checks.

Finance acquisition expansion is likewise deferred. Retain only the existing
complete, source-backed descriptive overlay; incomplete amounts stay unknown
and masked. Finance is not a headline WAR input or a release prerequisite.
Overlay parity and missingness checks are still required wherever displayed.

| Product | Accountable implementation role | Independent acceptance role |
|---|---|---|
| 2026 Alabama forecast | `forecast_model` | `validation_release` |
| Historical Alabama WAR | `cmo_model` (legacy role name) | `validation_release` |
| Ideology and caucuses | `legislative_ideology` | `validation_release` |
| Southern historical WAR | `cmo_model` (legacy role name) | `validation_release` |

`warehouse_integrator` owns shared database changes and `web_product` owns
presentation. These are existing registry roles, not new agents or scientific
approval. Exact candidate run IDs remain in the linked manifests; no presently
stored run is recertified by this scope statement. Ideology's public population
is the existing Democratic 1998–2022 analysis, restricted to sufficiently
evidenced candidate-cycles with valid historical-WAR joins. The both-party
research inventory is not a commitment to a Republican public analysis.
Evidence channels include recorded legislative votes, questionnaires,
interest-group evidence, sponsorship/proposals and campaign/public positions;
full-inventory source cards do not certify eligibility for the displayed sample.
Statistical groups are not formal caucus membership. Current evidence-window,
identity and sensitivity validation remain required; this records scope only.
Publication remains a
separate explicit authorization after the required acceptance evidence exists.

### Acceptance meanings

Historical WAR acceptance requires source/outcome reconciliation, race-grain
and orientation identities, correct comparator provenance and plan, explicit
exclusions, and backcast/era sensitivity. Same-cycle residual fit checks do not
constitute prospective validation. The existing forward specification-selection
and finance gates remain applicable; the deferred v4 promotion gate is not waived.

Forecast acceptance additionally requires as-of source eligibility, time-forward
comparisons, calibration/uncertainty diagnostics and seat accounting. The
owner-required structural specification stays explicit even when its advisory
comparison is unfavorable; a tuned holdout is not independent evaluation.
Neither simulation count nor a successful renderer satisfies these checks.

For all products, observed source facts, reconstructed allocations, imputed
model inputs, explicit exclusions and unknown values remain distinct. Missing
or contradictory source evidence cannot become zero or a passed record. A
documented exclusion may remain visible only where the affected product contract
permits it and an independent reviewer accepts its evidence and consequences.
Unresolved required provenance, vintage, identity, reconciliation or stale-input
checks block release of the affected consumer. This is the existing contract's
review boundary, not an arbitrary completeness threshold or a waiver for
missing observations. Implementation and final release validation remain open.

## Product contracts and evidence

- **Forecast:** [field contract](model/ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md),
  [methodology](model/ALABAMA_WAR_GENERIC_FORECAST_V1.md),
  [validation](audits/ALABAMA_WAR_FORECAST_VALIDATION.md).
- **Historical Alabama:**
  [field contract](model/ALABAMA_HISTORICAL_WAR_V1_FIELD_CONTRACT.md),
  [methodology](model/ALABAMA_HISTORICAL_WAR_V1.md),
  [validation](audits/ALABAMA_HISTORICAL_WAR_V1_VALIDATION.md).
- **Southern:**
  [map contract](model/SOUTHERN_HISTORICAL_WAR_MAP_FIELD_CONTRACT.md),
  [methodology](model/SOUTHERN_HISTORICAL_WAR_V1.md),
  [2024 map release](audits/SOUTHERN_WAR_2024_MAP_RELEASE.md),
  [v4 research validation](audits/POST2016_SOUTHERN_WAR_V4_VALIDATION.md).
- **Ideology/caucuses:** [scale methodology](model/ABSOLUTE_IDEOLOGY_REBUILD.md),
  [legislative evidence coverage](audits/LEGISLATIVE_IDEOLOGY_POST_REPAIR_COVERAGE.md),
  [candidate research disposition](audits/CANDIDATE_ISSUE_RESEARCH_CLOSURE.md),
  [cluster validation](audits/CAUCUS_RECLUSTER_VALIDATION.md). These document
  different stages and dates; compare against current consumed inputs rather
  than treating any one audit as certification of the whole current page.
- **Shared repairs:** [source repairs and dependency limitations](audits/WAREHOUSE_SOURCE_REPAIRS_2026_09_05.md).

## Testing and testmon

Use the repository virtual environment, which has `pytest-testmon` installed;
the system Python may not. For routine Python changes:

```powershell
& .venv/Scripts/python.exe -m pytest --testmon -q
```

Keep `.testmondata` and its SQLite sidecars local and ignored by Git. Cache
presence is not proof of a complete baseline or a passing suite. A missing
baseline requires an initial full testmon run; do not delete a useful cache
between edits. `pytest.ini` does not enable testmon automatically.

[Testmon tracks executed Python dependencies](https://www.testmon.org/), not
changes to SQL, SQLite contents, CSV/JSON, templates, or external sources.
For those edits, explicitly choose all affected producer/consumer tests and
disable deselection while still collecting dependency data. For example, a
warehouse lifecycle/source-repair change may require:

```powershell
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect scripts/tests/test_warehouse.py scripts/tests/test_warehouse_data_repairs.py -q
```

That pair is an example, not complete coverage for every warehouse change.
Include the affected domain, marts, and publication parity tests as appropriate;
retain source reconciliation, integrity, cardinality and stale-dependency checks.
Do not use `--testmon-forceselect` to filter an explicitly required data test.

Run the full suite for integrated releases, broad-impact changes, or uncertain
dependency coverage. This also refreshes the dependency baseline:

```powershell
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -q
```

Plain pytest remains available in environments without the optional plugin;
use explicit affected paths there. Documentation-only changes need path/link
and command checks, not a model rebuild. Report the command, interpreter,
pass/fail/skip/deselection counts and remaining validation limits. A selected
run is not a full-suite pass or publication approval.

The [test relevance audit](audits/TEST_RELEASE_RELEVANCE_AUDIT_2026_09_05.md)
records the retired-release assertions removed and compatibility coverage kept.

## Existing dispatcher and publication boundary

`scripts/project.py` is a partial convenience dispatcher, not a certified
end-to-end pipeline for all four products:

- The superseded `build cmo` shortcut is removed: it chained older analyses and
  did not rebuild the current historical WAR mart. Use the product routes above.
- `build forecast --publish` runs the forecast renderer with publication enabled. It does
  not run the analytical forecast or refresh sources.
- `build site --publish` calls `scripts/build_blue_oxblood_site.py`, which runs renderers
  across products, copies ideology/caucus candidates into `docs/`, creates the
  methods landing/redirect and applies the shared theme. It is a site-wide
  publishing command, not a safe preview or an upstream validation pipeline.
- `audit` invokes `scripts/audit_repository_hygiene.py`; hygiene checks are not
  full warehouse or model validation. `test` invokes `python -m pytest -q`
  (the full suite, not testmon selection); use the direct commands above for
  targeted runs.

Both remaining build targets refuse to start without `--publish`. This is an
explicit side-effect acknowledgement, not a scientific validation or release
approval gate. Direct builder commands retain their documented behavior; the
dispatcher does not make them safe previews. The dispatcher tests mock subprocess
execution and do not generate models, artifacts or publication files.

`docs/` and `docs/data/` are output only. Upstream scripts consume canonical
warehouse views, versioned marts, or reviewed research/compatibility products.
Existing commands do not all enforce every required publication gate: inspect
their effects and validation evidence rather than assuming automatic approval.
Shared presentation lives in `dashboard/war_explorer.css`,
`dashboard/blue_oxblood_theme.css`, and `scripts/site_brand.py`.

The [internal completion checklist](PROJECT_COMPLETION_CHECKLIST.html) belongs
only in `project_docs/`; never copy it into the public site or add it to site
navigation/builders. Mark only genuinely completed tasks, attach evidence, and
preserve the embedded progress history when saving an updated revision.

For holdover documents, use the
[documentation audit and inventory](audits/DOCUMENTATION_ARCHITECTURE_AUDIT_2026_09_05.md).
An older model card or PASS report retains authority only over its own named
artifact and scope; it is not a competing current entry point.
