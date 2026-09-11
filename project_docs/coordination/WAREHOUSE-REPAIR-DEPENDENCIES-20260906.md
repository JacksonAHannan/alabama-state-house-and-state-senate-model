# Task: WAREHOUSE-REPAIR-DEPENDENCIES-20260906

- Accountable role / owner: `orchestrator` / primary session.
- Status: complete — dependency inventory only; independent review passed.
- Objective / checklist: `warehouse-02`; inventory dependencies of the September
  5 source repairs and classify current, stale or unresolved from recorded evidence.
- Non-goals: source acquisition, database writes, repairs, rebuilding models,
  changing methodology, publishing, or declaring the four products validated.
- Inputs: `WAREHOUSE_SOURCE_REPAIRS_2026_09_05.md`, `WQA-dependencies`, central
  warehouse build/lineage records, actual script consumers and file manifests.
- Repair snapshot: `RUN-40A033B9854141F6B05A76173E66D17B` and
  `RUN-C7DE0A0267EC4445938D1CA0CB5C4BD3`; confirm live observations in the audit.
- Read scope: scripts, SQL, manifests, audits, central SQLite via `mode=ro`
  plus `PRAGMA query_only=ON`; use bounded queries and do not run builders.
- Primary write scope: this task/handoff; the dated dependency report/evidence
  under `project_docs/audits/`; accepted evidence/status for `warehouse-02` in
  the existing internal checklist. No other task statuses are owned.
- Delegated read-only questions: (1) precinct identity, Alabama historical
  allocation and Arkansas VEST consumer paths; (2) roll-call/finance/provenance
  consumers and downstream ideology paths. Helpers return evidence in messages,
  write no files, run no builders or tests, and do not modify SQLite.
- Acceptance: cover every named `WQA-dependencies` branch and other repaired
  interfaces; trace to the four current product routes; compare available
  run timestamps and dependency/output hashes; identify missing lineage rather
  than inferring freshness; give a bounded next action per finding.
- Review: an independent read-only review of the inventory and evidence is
  required before checking `warehouse-02` complete. Inventory completion does
  not resolve any identified stale dependency.
- Publication authority: none.
- Recovery: diagnostic reads are repeatable; no warehouse mutation is authorized.
  On resume, recheck snapshot/build records and existing report/checklist edits;
  preserve prior history and unrelated working-tree changes.

## Handoff

- Output: `project_docs/audits/WAREHOUSE_REPAIR_DEPENDENCIES_2026_09_06.md`
  and companion `.json`; only `warehouse-02` accepted in the internal checklist.
- Snapshot: latest registered build remains the provenance repair above;
  database SHA256 `2dfcdcb81079605b9ac36f5670d30957500f8cec74ddafa1da18b3eccd613377`.
  Size/mtime were unchanged during the hash/SQL capture.
- Evidence: 76 manifest-declared comparisons, 74 matching and two input drifts;
  source-key anti-joins, Arkansas allocation reachability, finance masking and
  known roll-call ID exclusion checks. Report distinguishes stale materializations
  from unresolved numerical/product impact and matching bytes.
- Review: independent `inventory_review` returned PASS after reproducing the
  decisive SQL/key/masking findings and 74 non-database actual hashes. No product
  release or scientific validation is implied.
- Changes: this task/handoff, the two dated audit files, and checklist evidence,
  revision and one accurate UTC history snapshot. No code, raw data, warehouse,
  model or public-site changes. Files remain unstaged; no commit was created.
- Verification: report relative links and JSON counts passed; existing internal
  browser check script passed all five check groups and restored its test edits.
  Final saved snapshot passed stable-ID, 7/82 count, four-event history, UTC
  revision, link, whitespace and database size/mtime checks. Reloaded browser
  checks passed; displayed counter was `7 / 82 checked` at revision
  `2026-09-06T17:00:01Z`. One auxiliary direct-eval diagnostic failed across
  the shell argument boundary; identical JavaScript passed via base64 input.
  No page-code change was needed, and the test browser was closed.
  No pytest/model/site build was run for the documentation-only inventory.
- Recovery: repeat read-only snapshot checks before further work; do not replay
  builders. Node IDs may renumber and the existing VEST allocation builder deletes
  all-state allocation outputs. The database stale-review flag remains open.
- Next safe action: obtain scoped repair authority for the stale finance export
  or staged identity/link comparison (`warehouse-03`); do not automatically
  advance into repairs, analytical changes or publication.
