# Ideology CMO v2 integration validation

- Task: `VALIDATE-IDEOLOGY-CMO-V2-001`
- Reviewer: `/root/blue_oxblood_validation`
- Candidate: `IDEO-ABS-REBUILD-001` and `WEB-IDEOLOGY-CMO-V2-001`
- Decision: **PASS**

The ideology analysis and public payload use CMO v2 candidate context scores
throughout. No preliminary CMO value is used by the analysis or page.

## Full candidate-ID reconciliation

Both `absolute_rebuild_panel.csv` and `cmo_v2_candidates.csv` contain exactly
1,018 rows and 1,018 unique, nonmissing `canonical_candidate_id` values. Their
ID sets are identical. A declared one-to-one outer join produced:

```text
both:       1,018
left_only:      0
right_only:     0
```

Cycle, chamber, district, and party agree for every joined ID. For all 1,018
candidates:

- analysis `candidate_context_cmo` equals v2 `candidate_context_cmo`;
- analysis `candidate_cmo` equals v2 `candidate_context_cmo`;
- null patterns are identical.

The maximum observed CSV floating-point parse difference was
`3.55e-15`, below the exact-audit tolerance and not an analytical difference.

## Barbara Boyd guardrail

The canonical record used for Barbara Boyd is:

```text
canonical_candidate_id: AL-2022-house-32-D-GSL032DBOY
cycle/chamber/district: 2022 / house / 32
party: D
CMO v2 context score: -4.368377366695523
```

The analysis `candidate_context_cmo` and `candidate_cmo` both equal that value.
The public payload contains four issue-evidence observations for the same
canonical ID, each carrying `cmo = -4.3683773667`; the difference is JSON
serialization only. The value rounds to **-4.368**, as required.

For comparison, the retained historical
`candidate_margin_overperformance` column on the research panel is +9.3921.
That source column is not consumed as CMO and does not appear in the public
payload.

## Stale-field and public-payload audit

Neither `scripts/build_ideology_thesis_page.py` nor
`docs/ideology-performance.html` references:

- `candidate_margin_overperformance`;
- `raw_overperformance`;
- `core_index_margin`.

The builder reads `candidate_cmo`, which is explicitly sourced from
`candidate_context_cmo` and labeled `cmo_v2_context` in the rebuilt panel.
Every candidate-level CMO value exposed by the page was checked against the
panel by stable ID:

- 407 Shor-point observations;
- 4,290 issue-evidence observations;
- 4,697 public observations total.

The maximum public serialization difference was `4.97e-11`; all values agree
at the published precision. The preliminary Barbara Boyd value is absent.

## Tests

```text
17 passed in 3.13s
Agent workflow validation passed.
```

Commands:

```powershell
python -m pytest tests/test_absolute_ideology_rebuild.py scripts/tests/test_ideology_performance_page.py -q
python scripts/validate_agent_workflow.py
```

## Release decision

**PASS.** The ideology analysis and public page are fully reconciled to CMO v2
candidate context scores. No correction or downstream invalidation is needed.
