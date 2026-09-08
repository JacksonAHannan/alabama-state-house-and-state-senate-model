# AGENTS.md

These instructions apply to the entire repository.

## Mission

Maintain four reproducible, auditable research products:

1. The 2026 Alabama legislative forecast.
2. Historical Alabama legislative WAR maps.
3. Ideology and caucus analysis.
4. Southern state-legislative WAR analysis for 2016–2024.

This repository hosts their shared central SQLite warehouse as well as
Alabama-specific and cross-state pipelines. Companion state repositories remain
compatible through explicit source and export contracts. Accuracy, provenance,
and honest uncertainty take priority over coverage or visual completeness.

WAR follows a documented adaptation of Split Ticket's methodology. Historical
race residuals, prospective forecasts, and ideology measures are different
products; do not substitute one for another or treat a residual as an isolated
causal measure of candidate quality.

## Required reading

Start with `project_docs/CANONICAL_PIPELINES.md` for current product routing and
`project_docs/PROJECT_COMPLETION_CHECKLIST.html` for internal task status. Neither
a checked task nor an existing output file is publication approval.

Before changing pipelines, schemas, or model behavior, read:

1. `project_docs/ARCHITECTURE.md` and both architecture documents it links
2. `project_docs/DATA_CONTRACTS.md`
3. `project_docs/STATE_ADAPTER_GUIDE.md`
4. the affected product's field contract, methodology, run manifest, and
   validation/dependency audit, starting from the pipeline index

For documentation-only work, read the documents and implementation being
described; do not rebuild models merely to edit instructions. Keep mutable
model versions, counts, cutoffs, and run IDs in the pipeline index, manifests,
and audits rather than duplicating them here. If those sources disagree,
document the conflict and reconcile it before claiming validation or publishing.

## Non-negotiable rules

- Treat `data/raw/` as immutable. Never silently modify or replace a source.
- Record source URL, retrieval time, hash, license/terms, geographic vintage,
  election cycle, and authoritative scope in a manifest.
- Keep provider-specific parsing in adapters. Downstream tables must use the
  shared canonical field names and keys.
- Register and reconcile useful stray data before loading it. A local file is
  not automatically authoritative, nonredundant, licensed, or model-ready.
- Never convert missing values to zero without an explicit source contract.
- Never substitute one redistricting plan, election cycle, chamber, office, or
  geographic vintage for another.
- Preserve conflicting source observations and reconciliation evidence.
  Natural-key collisions are not automatically duplicates; adjudicate their
  grain and source meaning before deleting canonical records.
- Human adjudications require evidence, rationale, reviewer status, and a
  stable identifier; do not hide them in code conditionals.
- Every reusable join must declare and test its expected cardinality.
- Keep observed, reconstructed, imputed, excluded, and unknown values distinct.
  Display geometry does not certify a vote allocation; backcasts are not
  contemporaneous fits. Fundraising receipts are not spending, and optional
  finance coverage is not a prerequisite for a declared finance-free product.
- Preserve the populated central warehouse. A bootstrap election database is
  not a replacement for it. Scope writes to the owned domain, use transactions
  and appropriate recovery safeguards, and never discard unrelated domains or
  build history during a refresh.
- Source repairs invalidate affected dependencies until revalidated. Trace
  downstream identities, allocations, marts, and publications; a successful
  repair or recorded stale flag does not certify every consumer.
- Generated files in `docs/`, `artifacts/`, and `data/processed/` must identify
  the code version, configuration, and model/data run that produced them.
- Do not commit credentials, tokens, proprietary data, or restricted source
  files. Check source terms before committing raw material.
- Do not describe a scaffold, placeholder, or unvalidated output as a model.
- Separate published, research-only, compatibility, and superseded artifacts.
  Neither a higher version number nor file existence authorizes promotion.
  Do not bypass an existing release gate; changes to gates require explicit
  rationale, review, and updated contracts.
- `docs/` and `docs/data/` are publication outputs, never upstream inputs.
  Internal checklists, review queues, and coordination notes remain outside
  the public site unless the user explicitly requests publication.

## Scope and simplicity

Prefer deleting unnecessary work, then simplifying, then optimizing, then
automating. Trace consumers before removing code or compatibility outputs;
preserve immutable sources, required replay artifacts, and unrelated user edits.
Reuse existing adapters, shared styles, and deterministic scripts. Do not add
an orchestration framework, dependency, predictor, or exhaustive acquisition
campaign without a demonstrated need within the requested scope.

Identify whether the request is an audit, repair, analysis, presentation change,
or publication. An audit does not authorize repairs; a layout change does not
authorize retraining; a terminal instruction does not broaden scope. Inspect
command side effects before execution. Page rendering is not source refresh,
and a site-wide build is not a scoped product build.

## Long-horizon execution

For authorized work spanning multiple independently verifiable outcomes or
subsystems, use the phase-management procedure in
`project_docs/coordination/AGENT_WORKFLOW.md`. The primary agent owns scope,
dependencies and acceptance, and may also implement tightly coupled work.
Delegate bounded independent work when it can run alongside useful local work
and materially improve speed or confidence; this instruction requests selective
delegation, not a standing team or delegation for every task. Respect runtime
limits and any instruction restricting delegation.

Use the existing internal checklist and coordination records, not a second
execution-state system. Continue to the next authorized, unblocked outcome
after acceptance. Pause for missing authority or a required unresolved decision;
do not turn an audit into repairs, a repair into retraining, or a build into
publication. Small local changes need no manager loop or new task contract.

## Development workflow

1. Identify the product, layer, owning component/reviewer, requested scope, and
   affected dependencies. Check existing changes before editing.
2. Update affected source/field contracts before changing data or model behavior.
3. Make the smallest scoped change. Use state/provider adapters for ingestion,
   canonical interfaces for downstream data, and existing templates for UI.
4. Add relevant fixtures, characterization tests, uniqueness/cardinality checks,
   reconciliation totals, and explicit failure/review states.
5. Use the repository virtual environment and `pytest --testmon` for routine
   code changes; preserve its local dependency cache. Explicitly run affected
   tests without testmon deselection for SQL, warehouse contents, CSV/JSON,
   templates, and other non-Python inputs that testmon does not track. Keep
   required data reconciliation and downstream validation checks. Run the full
   suite for integrated releases, broad-impact changes, or when affected
   coverage cannot be established, not after every warehouse edit. See the
   testing commands in `project_docs/CANONICAL_PIPELINES.md`. For documentation
   changes, verify links, paths, commands, and consistency; for interactive
   internal tools, also verify browser behavior and persistence. Report exactly
   what ran, including deselections and skipped, failed, or incomplete checks;
   never imply an unrun suite passed.
6. Update affected lineage, catalog, methodology, and validation notes. Record
   remaining stale dependencies and release limitations.
7. Publish only when requested, from a validated, versioned run. Reconcile page
   prose, downloads, and manifests before release; retain a rollback path.

Prefer deterministic scripts over notebooks for production pipelines. Keep
notebooks exploratory and move accepted logic into tested modules.

## Validation expectations

For affected data/model paths, test schema, primary-key uniqueness, join
cardinality, state/chamber/district coverage, election stage, vote-total
reconciliation, party normalization, geographic vintage, and temporal leakage.

- **Historical Alabama and Southern WAR:** verify the race universe, residual
  identity/sign/units, candidate orientations, baseline provenance, correct
  plans, source parity, excluded races, and backcast/era sensitivity. Separate
  retrospective fit checks from predictive validation; neither replaces the
  other when a product contract requires both.
- **2026 forecast:** require as-of source eligibility, roster/seat accounting,
  time-forward comparisons, calibration and uncertainty diagnostics. Distinguish
  owner-selected assumptions from validation-selected choices. Simulation count
  is not independent validation evidence.
- **Ideology and caucuses:** verify identities, pre-election evidence windows,
  roll-call reconciliation, issue eligibility/polarity, coverage and missingness,
  scale comparability, and sensitivity of descriptive groups. Keep group formation
  independent of WAR outcomes; account for repeated people. Statistical clusters
  are not formal caucus membership, and associations are not causal findings.
- **Presentation:** inspect the established interface first; preserve the shared
  Blue/Oxblood design and Alabama historical explorer conventions where relevant.
  Check keyboard access, focus, responsive behavior, empty/error states, readable
  outcomes, and agreement between visuals and downloadable data. Use the supplied
  design-reference library when applicable; report if unavailable.

If evidence is incomplete, stop at a review queue or an explicit `unknown`.
Never manufacture certainty to make a pipeline pass.

## Internal completion tracking

Keep `project_docs/PROJECT_COMPLETION_CHECKLIST.html` internal: no copy to
`docs/`, public navigation link, or site-builder integration. Mark a task complete
only with evidence of its acceptance criteria or an explicit reviewed disposition;
do not mark a whole phase complete because one related edit shipped.

Follow the page's handoff instructions. Browser drafts do not update the
repository. When editing embedded JSON, preserve stable task IDs and prior
history, update evidence, append an accurate UTC count/total snapshot for status
or scope changes, and bump the revision so an old browser draft cannot shadow
the new repository version. Do not invent past completion dates.

