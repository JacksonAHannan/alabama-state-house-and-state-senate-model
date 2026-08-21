# Task contract: <task ID and title>

- Accountable role: `<role from agent_ownership.json>`
- Owner: `<agent/session/worktree>`
- Status: `planned | active | blocked | review | complete`
- Objective: `<one independently testable outcome>`
- Non-goals: `<what this task deliberately will not change>`
- Upstream snapshot: `<warehouse version, model run, commit, or dated files>`
- Read scope: `<paths/tables>`
- Write scope: `<narrow repository-relative paths>`
- Warehouse mode: `read-only | staging proposal | integrator write`
- Inputs: `<source files/tables and cutoffs>`
- Outputs: `<files/tables/reports>`
- Acceptance checks: `<exact commands and expected invariants>`
- Handoff recipient: `<role>`
- Known risks: `<identity, time, leakage, source, or publication risks>`

Add active or review work to `active_tasks.csv`. Separate multiple write scopes
with semicolons and run `python scripts/validate_agent_workflow.py` before work.
