# Vote Smart manual-adjudication UI

Launch from the repository root:

```powershell
python scripts/serve_votesmart_adjudication.py
```

Open `http://127.0.0.1:8765` in a browser. The server binds only to localhost.
Stop it with `Ctrl+C`.

If port 8765 is blocked or already occupied, the server automatically selects a
free localhost port and prints the URL to open. To request this behavior
directly, run `python scripts/serve_votesmart_adjudication.py --port 0`.

The queue contains the 114 unresolved year-specific policy groups with selected
responses from canonical CMO candidates. It is ordered by candidate impact and
shows the original section, prompt, option, affected candidates, response count,
two small-model proposals, and the Ministral escalation where applicable.

The redesigned form records a primary domain and zero or more descriptive
axis/pole effects. It does not ask the reviewer to assign a generic progressive
or conservative direction. `Enter` saves and advances; arrow keys navigate.

Version 2 decisions autosave atomically to
`data/manual/ideology/votesmart_pct_multiaxis_v2_manual_adjudications.csv`.
Earlier binary adjudications remain untouched in the legacy manual CSV. The UI
does not modify deterministic coding rules or final feature tables. A separate
validated import step should apply completed decisions and derive any scalar
ideology measures transparently after manual review is complete.

The two small-model outputs are combined additively when they are compatible.
Policy-domain labels are retained as a union rather than forced to one label.
Only same-axis/opposite-pole conflicts are sent to a focused Ministral prompt.
Complete semantic disagreements remain pending. This currently produces 91
automatic adjudications and a 23-item manual queue. Manual saves override an
automatic record with the same review ID.
