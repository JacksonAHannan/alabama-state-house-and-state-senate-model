# Task contract: <task ID and title>

Use for substantial phase assignments or authorized delegated/concurrent work;
see `AGENT_WORKFLOW.md`. This template does not itself authorize spawning agents
or require a contract for every single-agent documentation edit.

- Accountable role: `<role from agent_ownership.json>`
- Owner: `<agent/session/worktree>`
- Status: `planned | active | blocked | review | complete`
- Objective: `<one independently testable outcome>`
- Product/layer and checklist IDs: `<affected product, owning layer, task IDs>`
- Dependencies: `<required accepted tasks/input readiness; what this outcome unblocks>`
- Non-goals: `<what this task deliberately will not change>`
- Upstream snapshot: `<warehouse version, model run, commit, or dated files>`
- Read scope: `<paths/tables>`
- Write scope: `<narrow repository-relative paths>`
- Warehouse mode: `read-only | staging proposal | integrator write`
- Inputs: `<source files/tables and cutoffs>`
- Outputs: `<files/tables/reports>`
- Acceptance checks: `<exact commands and expected invariants>`
- Review requirement: `<self-checks | independent review required, reviewer and gates>`
- Publication authority: `<none | explicitly requested scope and release gate>`
- Recovery/replay: `<possible side effects, how to detect completion, safe retry/rollback reference>`
- Handoff recipient: `<role>`
- Known risks: `<identity, time, leakage, source, or publication risks>`

Declare concurrent write claims in `active_tasks.csv`; separate write scopes
with semicolons and run `.venv/Scripts/python.exe scripts/validate_agent_workflow.py`
before concurrent edits. Read-only helpers have no warehouse write scope; their
parent contract records the assignment. If a helper will write a report or run
tests with file side effects, declare and coordinate those paths explicitly.
