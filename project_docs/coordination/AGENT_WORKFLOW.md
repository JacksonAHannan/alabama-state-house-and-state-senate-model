# Phase management and selective agent coordination

## Purpose

Use phase management for substantial authorized work under
[AGENTS.md](../../AGENTS.md). Its selective-delegation rule or a direct user
request may authorize bounded agents; neither requires a standing team. For
an ordinary scoped task, one implementer may perform the work and checks;
do not create agents, task contracts or new process merely to edit a document.

When multiple implementers are authorized, one coordinator sequences dependencies
and domain owners take bounded write scopes. Independent review is still required
where the product's release contract requires it; an implementer's own tests
must not be presented as independent approval.

The machine-readable role and path registry is
`agent_ownership.json`. Concurrent work is declared in `active_tasks.csv`.
Role names are stable ledger identifiers, not a complete product map. In
particular, `cmo_model` is a legacy role name used by historical WAR tasks; it
does not select an old CMO model. Current product routes are in
`../CANONICAL_PIPELINES.md`, and current planned work is in the internal checklist.
The registry's ownership patterns retain legacy compatibility paths and are not
an exhaustive inventory of current builders. A task's explicit write scope,
applicable instructions and collision check govern edits; role membership does
not grant blanket permission to rebuild every matching output.

## Phase management

The primary agent retains the overall goal, non-goals, acceptance criteria,
dependencies and decisions. It may implement small integration changes or
tightly coupled work itself. Delegate only a bounded question or outcome,
not the entire project or a large checklist phase by default.

1. Identify the authorized finish line and map it to existing checklist IDs.
   Order outcomes by dependencies. Use the task template for substantial
   assignments, including single-agent work that needs a durable handoff.
2. Give a worker the short overall goal, its specific outcome, constraints,
   input snapshot, read/write scope, acceptance checks and required handoff.
   Supply relevant contracts rather than the full planning history. Workers
   must read applicable instructions themselves and report unrelated findings
   without expanding scope.
3. Keep one implementation writer initially; add read-only exploration or
   review only for useful independent work. Use available runtime limits, not
   an assumed agent count. Further delegation follows the same constraints;
   do not create recursive teams or a manager that merely waits on one worker.
4. Inspect the actual diff, artifacts and verification evidence against the
   acceptance criteria. Request only concrete missing work. Review consequential
   source/schema changes and release candidates at meaningful boundaries;
   routine edits do not each require a separate reviewer.
5. Record accepted outcomes and evidence, then proceed to the next authorized,
   unblocked outcome without waiting for another "continue." Missing authority
   or a required user decision requires a pause. A blocked dependency prevents
   its consumers from proceeding, but not unrelated authorized work.

Follow the testing policy in `../../AGENTS.md` and `../CANONICAL_PIPELINES.md`:
testmon for routine Python changes, explicit affected tests for non-Python
inputs, and broader checks when risk or release requirements justify them.
Do not repeat unchanged passing checks without a new reason. Reviewers may
independently reproduce checks required by the acceptance contract.

### Progress and stopping

After a meaningful work cycle, identify what advanced: an accepted outcome,
a resolved uncertainty, an eliminated hypothesis, or an evidenced blocker.
After two consecutive cycles with none of these, reassess and simplify or
change approach. Do not abandon necessary hard work on a clock, manufacture
easy subtasks, or weaken acceptance criteria to increase the checkbox count.

The requested work is complete only when its required outcomes and integrated
checks pass, including any required independent review. An unresolved required
blocker means partial/blocked, not complete. An explicit reviewed exclusion may
close an item only where the product contract permits it; record who authorized
the disposition. Completion does not itself authorize publication.

### Durable state and recovery

The internal HTML checklist owns priorities and accepted project completion;
task contracts and handoffs own execution detail, and `active_tasks.csv` owns
concurrent write claims. Do not add a second authoritative checklist or place
the only copy of decisions/evidence in ignored scratch notes. The primary
agent coordinates edits to the checklist and ledger as single-writer files.

At handoff or interruption, record the exact input snapshot, owned paths/tables,
changes already applied, last command and known commit/output state, checks
completed and outstanding, replay safety, and the next safe action. Use the
handoff template; do not invent state that was not observed.

After a restart, reconcile live sessions and existing task claims with actual
files, warehouse build/transaction records and output hashes before resuming.
An interrupted command may already have committed. Do not blindly rerun a
write or retry against a changed snapshot; first determine whether it completed
and whether replay is safe. Use existing recovery safeguards, never overwrite
the central warehouse to recover a task.

For read-only work, verify effective tool permissions and use read-only SQLite
connections or a consistent frozen snapshot. A role name or "read-only" prompt
does not enforce permissions. Tests may write caches or fixtures: inspect their
side effects and isolate them from production data and other writers.

## Roles

| Role | Primary responsibility | Typical deliverable |
|---|---|---|
| `orchestrator` | Scope work, assign owners, sequence dependencies, resolve cross-domain decisions | task contracts and integration brief |
| `source_provenance` | Acquire immutable sources, hashes, licenses, and extraction metadata | registered raw-source manifest |
| `elections_geography` | Election normalization, precinct identity, maps, VTD/block links, historical allocations | canonical-ready election/geography staging data |
| `people_finance` | Person/candidate identity, aliases, rosters, incumbency, committees, finance | reviewed identity/resource staging data |
| `legislative_ideology` | Bills, roll calls, sponsorship, Vote Smart, public positions, ideology features | evidence ledger and ideology mart inputs |
| `cmo_model` | Historical Alabama and Southern WAR; legacy role identifier retained for existing contracts | versioned historical analysis candidate |
| `forecast_model` | 2026 environment, district forecast, uncertainty, simulations | versioned forecast run candidate |
| `web_product` | Dashboard code, accessibility, methodology presentation, publication exports | reviewed site build candidate |
| `warehouse_integrator` | Schema lifecycle, canonical views, migrations, atomic builds | validated warehouse version |
| `validation_release` | Independent QA, leakage checks, model gates, source audits, release approval | signed validation report |

## Standard work cycle

### 1. Intake and decomposition

The orchestrator writes one task contract per independently testable outcome.
Use `TASK_TEMPLATE.md`. A contract must identify one accountable role even when
several roles contribute.

Prefer tasks that produce a staging artifact or review packet. Avoid delegating
open-ended instructions such as "improve the model" or "clean the data."

### 2. Collision check

Before concurrent edits, add tasks to `active_tasks.csv`. Write scopes use
repository-relative paths and must be as narrow as practical. Run:

```powershell
& .venv/Scripts/python.exe scripts/validate_agent_workflow.py
```

Two live tasks may read the same input. They may not claim overlapping write
scopes. The validator treats a parent directory and any child path as an
overlap.

### 3. Domain execution

The domain agent works only inside its contract. It may inspect upstream data
outside its owned paths, but changing another domain requires a revised
contract. It records exact commands, source cutoffs, row counts, hashes where
appropriate, and validation results.

Domain agents do not directly publish canonical warehouse objects. They hand a
schema proposal, migration/staging artifact, reconciliation audit, and tests to
the warehouse integrator.

### 4. Warehouse integration

The warehouse integrator is the sole canonical database writer. It verifies:

- stable keys and declared cardinality;
- provenance back to raw observations and manual decisions;
- authority and missing-value policies;
- schema version and ownership metadata;
- atomic build behavior;
- compatibility diffs for consumers being migrated.

The database should have one writer but may have many read-only consumers.

### 5. Independent validation

The independent reviewer did not implement the change being reviewed. It checks
actual artifacts and source evidence against the same recorded snapshot, not
only the implementer's summary, and reproduces required contract checks. Source
completeness, key uniqueness, join cardinality, leakage, subgroup error, temporal
validity and before/after diffs are checked where relevant.

Return `pass`, `fail`, or `blocked/insufficient evidence`, with concrete findings,
checks performed and remaining limitations. A separate agent provides another
check, not automatic scientific or publication approval. Do not raise style-only
or speculative requirements or reopen settled issues without new evidence.

Failed gates return the smallest concrete repair to the domain owner. Missing
evidence stays unresolved rather than triggering endless repair loops. Required
gates cannot be waived by the coordinator alone; any scope/gate change needs
the explicit authority, review and updated contract required by `AGENTS.md`.

### 6. Handoff and close

Use `HANDOFF_TEMPLATE.md`. Review verdicts are evidence fields, not new ledger
statuses: use `review` while validation is pending, `active` for an in-scope
repair, `blocked` for missing evidence/authority, and `complete` only after
acceptance. Before releasing a blocked task's write claim, verify its writer
has stopped; recheck collisions before reactivating it. Preserve task and review
history.
An old row marked active/review is not proof that its owner is currently running,
nor permission to close or delete it without checking its evidence and owner.
Update only tasks within the requested scope; do not mass-close historical rows
to make the collision validator pass.

Update accepted task progress in `../PROJECT_COMPLETION_CHECKLIST.html`, with
evidence, a new revision and an accurate history snapshot. This internal file is
not a public-site asset and does not replace the concurrent-write ledger.

## Dependency flow

```text
source_provenance
        |
        +--> elections_geography ----+
        +--> people_finance ---------+--> warehouse_integrator
        +--> legislative_ideology ---+            |
                                                   +--> cmo_model
                                                   +--> forecast_model
                                                           |
                                                           +--> web_product
                                                                   |
                                                           validation_release
```

Model work may experiment against read-only snapshots while upstream work is in
progress, but promotion must reference an integrated warehouse version and data
cutoff.

## Safe parallel work

- Source downloads for unrelated providers.
- Precinct research and legislative research in separate paths.
- Separate product tasks reading the same frozen, validated inputs.
- UI prototypes using a frozen publication fixture.
- Independent validation while a different domain begins unrelated work.

## Work that must be serialized

- Canonical identity and authority changes.
- Warehouse migrations or replacement.
- Regeneration of shared marts and model headline outputs.
- Site publication into `docs/`.
- Changes to shared schemas, global configuration, or ownership rules.

## Integration and release boundary

The four products share election, geography, identity and legislative evidence,
but do not share one automatic refresh/retrain/publish cycle. Rebuild only
invalidated dependencies within the request. A source repair, optional finance
load or historical analysis does not authorize changing a forecast or publishing
all pages. Serialize warehouse writes and public-site publication, and retain
the applicable product-specific validation gates and rollback evidence.

Use the phased checklist for priorities rather than maintaining a second
standing workstream schedule here.
