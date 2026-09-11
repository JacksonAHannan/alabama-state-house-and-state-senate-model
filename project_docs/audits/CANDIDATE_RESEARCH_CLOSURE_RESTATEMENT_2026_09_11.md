# Candidate research closure restatement — 2026-09-11

Task `IDEOLOGY-CLOSURE-RESTATEMENT-20260911` (checklist `ideology-06` caveat). The
2026-08-17 closure ledger `research/cmo_ideology/candidate_issue_research/candidate_research_final_status.csv`
was stale: the `IDEOLOGY_EVIDENCE_LAYER_VALIDATION_2026_09_11` audit recorded that
it closed 1,098 candidate-cycles as `evidence_recovered` and 466 as
`searched_no_recoverable_evidence`, while the current evidence layer carries a
valence profile for 1,124 cycles. This record restates the ledger through its
producer (`scripts/finalize_candidate_issue_research.py`) and audits the delta.

Scope: the closure ledger, its sibling outputs, and the disposition rule only.
No source was adjudicated, no evidence value was imputed, no model or threshold
was changed, and `data/processed/ideology/` was read only.

## Method and commands

1. Snapshot the prior ledger byte for byte:
   `candidate_research_final_status.csv` → `candidate_research_final_status.2026-08-17.csv`.
   The snapshot's SHA-256 is `fbb4aa801c192c7e1e193fbe9784e79a39f8dfb58065271396802649318f527b`
   (426,403 bytes), identical to the hash the evidence-layer validation recorded
   for the old closure file — the snapshot is the exact audited prior bytes.
2. Extend the producer so every row carries `prior_status` (from the snapshot,
   keyed on `canonical_candidate_id`), `new_evidence_source_types` (source types
   of the newly supplying evidence rows) and `restated_at_utc` (only on rows whose
   disposition moved). The producer's closure-document writer now preserves the
   pre-existing 2026-08-17 account and appends a marked restatement section
   instead of overwriting the document.
3. Rerun the producer (pure recomputation, no network or API step):

```powershell
& .venv/Scripts/python.exe scripts/finalize_candidate_issue_research.py
```

```
Closed 440 residual candidates as searched_no_recoverable_evidence
Restated 26 candidate-cycles whose disposition changed
```

4. Rerun the affected test file:

```powershell
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_candidate_issue_research_closure.py -q
```

```
4 passed in 1.74s
```

## Reconciliation

| ledger | rows | evidence_recovered | searched_no_recoverable_evidence |
| --- | --- | --- | --- |
| prior (2026-08-17, preserved) | 1,564 | 1,098 | 466 |
| restated (2026-09-11) | 1,564 | 1,124 | 440 |
| delta | 0 | +26 | −26 |

The restated recovered count equals the 1,124 distinct `canonical_candidate_id`
values in `data/processed/ideology/candidate_issue_valence_v3.csv` exactly. The
440 residual count is `1,564 − 1,124`. No cycle lost evidence (`prior − current = 0`),
no cycle is unaccounted for (`0` of the 1,564 universe ids missing from either
file), and the disposition rule is unchanged: `evidence_recovered` iff the cycle
carries a valence profile in the current layer, otherwise
`searched_no_recoverable_evidence` with `neutrality_imputed = False`.

The 26 moved cycles explain the residual-basis shift in the ledger:
manual-broad-search residuals `326 → 318` (8 of the 26 had
`manual_broad_search_logged = True`) and structured-sweep residuals `140 → 122`
(18 of the 26 were closed by the structured Vote Smart/legislative/identity sweep).

## The 26 cycles that gained evidence

| canonical_candidate_id | cycle | chamber | district | party | new evidence source types |
| --- | --- | --- | --- | --- | --- |
| AL-1998-house-24-D-BURKE | 1998 | house | 24 | D | legislative_vote |
| AL-1998-house-35-R-SIMS | 1998 | house | 35 | R | legislative_vote |
| AL-2002-house-55-D-MAJOR-ERIC | 2002 | house | 55 | D | legislative_vote |
| AL-2002-house-58-D-ROBINSON-OLIVER | 2002 | house | 58 | D | legislative_vote |
| AL-2010-house-1-D-GREG-BURDINE | 2010 | house | 1 | D | bill_sponsorship |
| AL-2010-house-60-D-JUANDALYNN-LEE-LEE-GIVAN | 2010 | house | 60 | D | bill_sponsorship |
| AL-2010-house-68-D-THOMAS-E-ACTION-JACKSON | 2010 | house | 68 | D | bill_sponsorship, legislative_vote |
| AL-2010-house-70-D-CHRISTOPHER-JOHN-ENGLAND | 2010 | house | 70 | D | bill_sponsorship, legislative_vote |
| AL-2010-house-83-D-GEORGE-TOOTIE-BANDY | 2010 | house | 83 | D | bill_sponsorship, legislative_vote |
| AL-2010-house-84-D-BERRY-FORTE | 2010 | house | 84 | D | bill_sponsorship |
| AL-2010-house-85-D-DEXTER-GRIMSLEY | 2010 | house | 85 | D | bill_sponsorship, legislative_cosponsorship |
| AL-2010-senate-9-R-CLAY-SCOFIELD | 2010 | senate | 9 | R | bill_sponsorship |
| AL-2014-house-32-D-BARBARA-BIGSBY-BOYD | 2014 | house | 32 | D | bill_sponsorship, legislative_vote |
| AL-2014-house-68-D-THOMAS-E-ACTION-JACKSON | 2014 | house | 68 | D | bill_sponsorship, legislative_vote |
| AL-2014-house-70-D-CHRISTOPHER-JOHN-ENGLAND | 2014 | house | 70 | D | bill_sponsorship, legislative_vote |
| AL-2014-house-83-D-GEORGE-TOOTIE-BANDY | 2014 | house | 83 | D | bill_sponsorship, legislative_vote |
| AL-2014-house-94-R-T-JOE-FAUST | 2014 | house | 94 | R | bill_sponsorship, legislative_vote |
| AL-2014-house-97-D-ADLINE-C-CLARKE | 2014 | house | 97 | D | bill_sponsorship, legislative_vote |
| AL-2018-house-13-R-CONNIE-COONER-ROWE | 2018 | house | 13 | R | bill_sponsorship, legislative_vote |
| AL-2018-house-32-D-BARBARA-BIGSBY-BOYD | 2018 | house | 32 | D | bill_sponsorship, legislative_vote |
| AL-2018-house-42-R-JAMES-M-JIMMY-MARTIN | 2018 | house | 42 | R | bill_sponsorship, legislative_vote |
| AL-2018-house-55-D-RODERICK-ROD-HAMPTON-SCOTT | 2018 | house | 55 | D | bill_sponsorship, legislative_vote |
| AL-2018-house-68-D-THOMAS-E-ACTION-JACKSON | 2018 | house | 68 | D | bill_sponsorship, legislative_vote |
| AL-2018-house-69-D-KELVIN-JAMICHAEL-LAWRENCE | 2018 | house | 69 | D | legislative_vote |
| AL-2018-house-70-D-CHRISTOPHER-JOHN-ENGLAND | 2018 | house | 70 | D | bill_sponsorship, legislative_vote |
| AL-2018-house-82-D-PEBBLIN-WALKER-WARREN | 2018 | house | 82 | D | bill_sponsorship, legislative_vote |

Channel mix: 16 cycles supplied by `bill_sponsorship` + `legislative_vote`, 5 by
`legislative_vote` alone, 4 by `bill_sponsorship` alone, and 1
(`AL-2010-house-85-D-DEXTER-GRIMSLEY`) by `bill_sponsorship` +
`legislative_cosponsorship`. 21 of the 26 are touched by the legislative-vote
channel; 21 are touched by a sponsorship channel. The sources are consistent with
the 2026-09-08 Luna full-corpus adjudication and sponsorship-pipeline rebuild
(`coordination/SPONSORSHIP-IDEOLOGY-PIPELINE-20260908.md`,
`coordination/IDEOLOGY-ROLLCALL-OPENAI-CLASSIFY-20260908.md`); this audit does not
re-adjudicate those sources or verify the eligibility of the newly admitted rows
(that is `ideology-04`/`ideology-05` scope).

## Producer purity

`scripts/finalize_candidate_issue_research.py` imports only `datetime`, `pathlib`,
`numpy` and `pandas`; it reads local CSVs under `data/processed/` and
`data/manual/` and writes only under `research/cmo_ideology/candidate_issue_research/`
and `project_docs/audits/CANDIDATE_ISSUE_RESEARCH_CLOSURE.md`. It performs no
network call, no LLM/API call, no warehouse write, and no `docs/` write. The run
completed in under 2 s. `prior_status` is read from the preserved snapshot, so the
delta is reproducible rather than hardcoded.

## Recomputed fields outside the disposition (limitation)

The producer recomputes every derived column from the current upstream inputs; it
does not freeze the prior file. Comparing the restated ledger to the snapshot
keyed on `canonical_candidate_id`:

- Disposition columns changed only on the 26 moved rows: `has_issue_evidence`,
  `final_research_status`, `exhaustion_basis` (26 rows each, 0 outside the 26).
- Informational columns drifted on rows outside the 26 because their upstream
  inputs changed after 2026-08-17: `candidate_margin_overperformance` /
  `absolute_cmo` (771 rows, 749 outside the 26, from the refreshed
  `canonical_cmo_candidates_with_votesmart.csv`) and
  `legislative_source_checked_and_present` (396 rows, 375 outside the 26, from the
  grown `candidate_legislative_position_evidence_v3.csv`).
- `identity_status`, `manual_broad_search_logged`, `any_manual_search_logged`,
  `accepted_votesmart_identity`, `manual_identity_alias`, the Vote Smart
  questionnaire/rating/endorsement flags and `latest_manual_result` are unchanged
  for every row.

So the restatement preserves every prior *disposition* verbatim and records the
delta, but it is a recomputation, not a byte-level replica: the CMO margin and
legislative-source-check columns reflect the current upstream files.

## Not established

- Whether the newly admitted evidence is correct, temporally eligible, or outside
  the known low-confidence mapping queue. This audit verifies only the closure
  ledger's disposition bookkeeping.
- That the 440 residual cycles have no recoverable evidence anywhere; they have no
  profile in the current local layer and a logged search disposition.
- That `candidate_issue_research_summary.csv` (search-queue status, 1,007
  candidates) or the follow-up queue files were restated; they are produced by a
  separate research-queue stage and were not touched.
- That the published ideology page or any model was re-derived; the evidence layer
  and the page payload were not rebuilt.

## Related records now stale (out of scope, not edited)

- `scripts/audit_ideology_evidence_layer.py` still emits the static
  "STALE CLOSURE ACCOUNTING (ideology-06)" defect and the static `ideology-06`
  caveat ("the closure file's accounting is stale for 26 cycles"); both describe
  the pre-restatement file and now contradict this ledger. Its input-hash entry
  for the closure CSV (`fbb4aa80…`, 426,403 bytes) is superseded by the restated
  file (see the digest under Related records).
- `project_docs/audits/IDEOLOGY_EVIDENCE_LAYER_VALIDATION_2026_09_11.{md,json}`
  records the same stale-caveat text and the old closure hash; regenerating that
  audit is the evidence-layer owner's action, outside this task's write scope.
- `project_docs/coordination/CHECKLIST-EXECUTION-20260911.md` lists the stale
  closure ledger as open work; the checklist is not edited here.
- The restated ledger's SHA-256 is `f015c414c4c79a0c2ac12b5b1d24fc16c11abb2bf89efdfb71708753303b5258`
  (465,374 bytes) as of the recorded run; the ledger carries a per-row
  `restated_at_utc`, so a rerun changes that digest without changing any
  disposition.

## Artifacts

- `research/cmo_ideology/candidate_issue_research/candidate_research_final_status.csv`
  — restated ledger (1,564 rows; 1,124 recovered / 440 residual; adds
  `prior_status`, `new_evidence_source_types`, `restated_at_utc`).
- `research/cmo_ideology/candidate_issue_research/candidate_research_final_status.2026-08-17.csv`
  — preserved prior ledger (`fbb4aa801c192c7e…`).
- `project_docs/audits/CANDIDATE_ISSUE_RESEARCH_CLOSURE.md` — 2026-08-17 account
  preserved; restatement section appended under
  `<!-- candidate-issue-research-restatement -->`.
- `research/cmo_ideology/candidate_issue_research/CANDIDATE_RESEARCH_CLOSURE_RESTATEMENT_2026_09_11.json`
  — machine-readable companion of this audit.

Restatement run: 2026-09-11T16:54:07Z.
