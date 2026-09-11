# Archived agent operating rules — not active instructions

This is a pre-rebase backup retained for recovery and historical comparison.
Follow [AGENTS.md](AGENTS.md) for current repository instructions. The text below
does not authorize delegation, mandatory standing agents, or publication.

This repository uses the coordinated workflow in
`project_docs/coordination/AGENT_WORKFLOW.md`. Read that document before making
changes that span more than one domain.

## Required task contract

Every delegated task must name:

- one role from `project_docs/coordination/agent_ownership.json`;
- a concrete objective and acceptance checks;
- an explicit read scope and write scope;
- upstream inputs and expected outputs;
- whether warehouse access is read-only or requires the warehouse writer.

Record concurrent write tasks in
`project_docs/coordination/active_tasks.csv`, then run:

```powershell
python scripts/validate_agent_workflow.py
```

Do not start work while that command reports overlapping active write scopes.

## Repository-wide rules

- Preserve `data/raw/` files as immutable source evidence.
- Treat `docs/` as publication output. Upstream code must never read from it.
- Models consume canonical warehouse views or versioned marts, not whichever
  optional CSV happens to exist.
- Only the `warehouse_integrator` may publish schema changes or canonical
  warehouse tables. Domain agents may prepare migrations, staging tables, and
  compatibility exports in their owned paths.
- Human adjudications belong under `data/manual/` and must remain reviewable,
  attributable, and separate from machine-generated evidence.
- Never silently convert missing observations to zero.
- Preserve unrelated work in a dirty worktree. Do not rewrite or delete another
  task's outputs.
- A task is not complete until its stated checks pass and its handoff names all
  changed files, generated outputs, caveats, and downstream actions.
- Publication requires independent validation; the agent implementing a model
  or public page does not approve its own release.

## Parallel-work boundary

Parallelize source acquisition, research, model experiments, and UI work when
their write scopes do not overlap. Serialize canonical identity decisions,
warehouse publication, shared generated marts, and `docs/` publication.

Use separate branches or worktrees for long-running agents. In this shared
workspace, never ask two agents to edit the same file or regenerate the same
output concurrently.
