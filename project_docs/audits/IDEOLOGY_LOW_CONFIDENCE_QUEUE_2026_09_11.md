# Low-confidence admitted mappings — review-queue repair, 2026-09-11

Repair record for the `ideology-04` defect recorded in
`project_docs/audits/IDEOLOGY_EVIDENCE_LAYER_VALIDATION_2026_09_11.md` and its JSON
companion: low-confidence `map`/`multi_axis` bill decisions and one low-confidence mapped
roll call were admitted to scoring without appearing in any review queue.

This is a **queue-membership repair only**. No scoring decision, score, ontology, warehouse,
`docs/` or published export was changed. The manual adjudication file was not written. The
only files changed are the two review-queue CSVs and the three producing scripts, plus the
tests for this change.

## Defect as recorded

`ideology-04` measured, from the current artifacts:

- 16 bill-level `map` decisions with `confidence=low` in
  `data/manual/ideology/frontier_legislative_bill_adjudications.csv`;
- 1 mapped roll call with `frontier_confidence=low` in
  `data/processed/legislative/frontier_rollcall_ontology_v3.csv`;
- `frontier_legislative_bill_adjudications_luna_review_queue.csv`: 1 row, containing none of the 16;
- `legislative_rollcall_ontology_v3_openai_review_queue.csv`: 10 rows, all low-confidence
  **exclusions**, containing neither the 16 bills nor the mapped roll call;
- `every_low_confidence_mapping_queued = false` (recomputed below).

## The 17 items

16 low-confidence bill mappings (all `decision=map`, `confidence=low`, all admitted to scoring):

| bill_id | session | bill | axis | pole |
| --- | --- | --- | --- | --- |
| 96700 | 2010 | HB460 | civil_social_liberty | expand |
| 291787 | 2011 | HB20 | market_governance | market_autonomy |
| 414224 | 2012 | HB535 | constitutional_reform | reform |
| 421565 | 2012 | SB538 | civil_social_liberty | expand |
| 592130 | 2014 | HB285 | public_private_provision | public_provision |
| 639015 | 2014 | HB613 | family_support_enforcement | strict_enforcement |
| 767873 | 2015 | SB354 | land_use_property_rights | property_rights |
| 1060535 | 2018 | HB216 | civil_social_liberty | expand |
| 1248532 | 2019 | HB334 | tax_burden | decrease |
| 1250623 | 2019 | SB251 | anti_discrimination | expand |
| 1256416 | 2019 | HB555 | market_governance | intervention |
| 1491951 | 2021 | HB599 | criminal_punishment | rehabilitative |
| 1578824 | 2022 | HB176 | civil_social_liberty | expand |
| 2021827 | 2025 | SB316 | market_governance | intervention |
| 2073726 | 2026 | HB196 | security_preparedness | expand |
| 2089018 | 2026 | SB188 | civil_social_liberty | restrict |

1 low-confidence mapped roll call:

| canonical_rollcall_id | bill_id | session | chamber | bill | vote_description | axis | pole | terminal_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LS-1548315 | 2021827 | 2025 | senate | SB316 | Third Reading in House of Origin | market_governance | intervention | mapped_frontier_policy_pole |

Bill `2021827` appears twice because it is the only bill that is both a queued bill-level
low-confidence mapping **and** the source of the single low-confidence mapped roll call.

## Root cause

- `scripts/adjudicate_frontier_bills_luna.py` queues a bill only when `validate_item`
  returns a schema-failure `review_reason`. A clean `map`/`multi_axis` row returns
  `reason=None`, so a low-confidence admitted mapping was written to the scoring file and
  the queue was skipped. The producer's `if reason:` branch was the sole queue trigger.
- `scripts/adjudicate_legislative_ontology_v3_all.py` (the OpenAI roll-call queue producer)
  does queue a validated row whose confidence is `low`, including a `map` row, but only for
  audit units it adjudicates itself. The single low-confidence mapped roll call did not come
  from that path: it inherits its `frontier_confidence` from the bill-level Luna adjudication
  through `scripts/build_frontier_rollcall_ontology.py`, and no producer wrote a
  roll-call-level queue record for an inherited low-confidence mapping.
- The 2026-09-08 owner contract
  (`project_docs/coordination/IDEOLOGY-ROLLCALL-OPENAI-CLASSIFY-20260908.md`, line 15) says
  `low`-confidence and schema-rejected items go to the review queue. Only the
  schema-rejected half was implemented; nothing reconciled the queues against the admitted
  low-confidence mappings afterward.

## Code change

Producer fix — `scripts/adjudicate_frontier_bills_luna.py`:

- new constant `LOW_CONFIDENCE_REASON = "low_confidence_admitted_mapping"`;
- new pure helper `review_reason_for(row, reason)`: schema failures keep their reason; a
  clean `map`/`multi_axis` row is queued when `confidence == "low"`; everything else is
  unqueued;
- the batch loop keeps the existing failure queueing and adds the adopted low-confidence
  mapping to `review_rows` with `review_reason=low_confidence_admitted_mapping`. The
  scoring row written to the adjudication output is unchanged.

Invariant enforcement — `scripts/build_frontier_legislative_review_ledger.py`:

- new `reconcile_low_confidence_review_queues(manual_path, ontology_path, luna_queue_path,
  openai_queue_path)`. It appends only missing units, preserves every existing row, writes
  the 16 bill rows to the Luna queue and the low-confidence mapped roll-call rows to the
  OpenAI queue with `review_reason=low_confidence_admitted_mapping`, and then raises
  `AssertionError` if any low-confidence admitted mapping is still absent from the Luna
  queue. It is idempotent: a second run appends nothing.
- `main()` calls it after the existing follow-up queue is written.

Pipeline enforcement — `scripts/build_frontier_rollcall_ontology.py` imports and calls the
same function immediately after writing `frontier_rollcall_ontology_v3.csv`, so the step
that produces the low-confidence mapped roll-call rows enforces the invariant on every
rebuild (this builder is in `scripts/run_frontier_ideology_pipeline.py`'s step list; the
review-ledger builder is not).

## Before / after

| artifact | before rows | after rows | sha256 before | sha256 after |
| --- | --- | --- | --- | --- |
| `data/processed/legislative/frontier_legislative_bill_adjudications_luna_review_queue.csv` | 1 | 17 | `4ea5d282ce194a794e57fe61a6c3c857ad2c8e57b36b39293881eaa8996ce3af` | `8b8198d4b2b6f06c571e1bc16a7ac1925bb8475d97f2d169b60badd46e28481c` |
| `data/processed/legislative/legislative_rollcall_ontology_v3_openai_review_queue.csv` | 10 | 11 | `65b05e8e5d52d55b71d5bc25ca0250703251682b386ba936eb7d4c44a0efa63b` | `837ba402c022fad0eaa585b7de303871d41a09bbe1164e292e0ce49806e8fd57` |

Scoring inputs unchanged:

| artifact | sha256 before | sha256 after |
| --- | --- | --- |
| `data/manual/ideology/frontier_legislative_bill_adjudications.csv` | `c958e62433b1e6c482c63c3e2ac841886cfb92b0bb57511fb966c12f0dd2bb66` | `c958e62433b1e6c482c63c3e2ac841886cfb92b0bb57511fb966c12f0dd2bb66` |
| `data/manual/ideology/frontier_legislative_bill_adjudications_luna.csv` (promotion source) | `c958e62433b1e6c482c63c3e2ac841886cfb92b0bb57511fb966c12f0dd2bb66` | unchanged (not written) |
| `data/processed/legislative/frontier_rollcall_ontology_v3.csv` | `b45f5f2ec74562bfafd2988e0c32e2502880b5888be36fe7c444993fba72c274` | `b45f5f2ec74562bfafd2988e0c32e2502880b5888be36fe7c444993fba72c274` |

The manual file was not rewritten; its sha256 is byte-identical before and after (also
`frontier_legislative_bill_adjudications_luna.csv`, which is currently the same promoted
content). Queue membership does not change scores.

### Post-repair audit invariant (read-only recomputation of the audit's own logic)

| measure | before (audit JSON) | after |
| --- | --- | --- |
| Luna bill queue rows | 1 | 17 |
| OpenAI roll-call queue rows | 10 | 11 |
| low-confidence mapping bills | 16 | 16 |
| … in review queue | 0 | 16 |
| low-confidence mapped roll-call rows | 1 | 1 |
| … bill in Luna queue | 0 | 1 |
| `every_low_confidence_mapping_queued` | false | **true** |

Recomputation command (stdlib csv streaming, read-only):

```
.venv/Scripts/python.exe -c "<replicate audit_ideology_evidence_layer.py lines 411-443: read frontier_rollcall_ontology_v3.csv + the manual file + the Luna queue; compare bill sets>"
```

The repair step itself:

```
.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'scripts'); from build_frontier_legislative_review_ledger import reconcile_low_confidence_review_queues; print(reconcile_low_confidence_review_queues())"
# {'luna_queue_rows_appended': 16, 'openai_queue_rows_appended': 1, 'luna_queue_rows': 17, 'openai_queue_rows': 11}
# second run: {'luna_queue_rows_appended': 0, 'openai_queue_rows_appended': 0, 'luna_queue_rows': 17, 'openai_queue_rows': 11}
```

## Tests

```
.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_adjudicate_frontier_bills_luna.py scripts/tests/test_frontier_review_queue_low_confidence.py -q
# 15 passed in 1.37s
```

- `scripts/tests/test_adjudicate_frontier_bills_luna.py` (10 tests): unchanged coverage plus
  three producer tests — a low-confidence admitted `map` is queued with
  `low_confidence_admitted_mapping`, a high-confidence or non-scoring row is not, and a
  schema-failure reason is preserved.
- `scripts/tests/test_frontier_review_queue_low_confidence.py` (5 new tests, synthetic
  frames only): a low-confidence `map` and `multi_axis` are appended; a high-confidence
  mapping and a non-scoring row are not; existing queue rows and the manual adjudication
  bytes are preserved; the low-confidence mapped roll call is appended to the roll-call
  queue while a high-confidence one is not; the step is idempotent; a high-confidence-only
  frame appends nothing.

## Integration validator

```
.venv/Scripts/python.exe scripts/validate_frontier_ideology_integration.py
# exit 0; all 12 checks passed
```

The validator's output `project_docs/audits/FRONTIER_IDEOLOGY_VALIDATION.csv` is
byte-identical before and after (`d6157cd3e7e6892e0728c29f56aef4b884c12fcd7e28392bdf2fdc9d9dda1fde`).
The scoring pipeline was not rerun.

## What this does NOT establish

- Whether the 16 low-confidence and 1 roll-call mappings are analytically correct. They are
  now **reviewable**; no reviewer has adjudicated them, and the repair does not change the
  scoring decision (they remain admitted, by contract).
- That medium-confidence admitted mappings are reliable; `ideology-04` recorded only the
  low-confidence gap, and this repair follows that scope.
- That the OpenAI roll-call queue's new `review_reason` column is produced by its own
  producer. `scripts/adjudicate_legislative_ontology_v3_all.py` is not in this task's write
  scope and writes that queue with a fixed nine-column list; a rerun would drop the column
  and the appended roll-call row. The enforcement step
  (`reconcile_low_confidence_review_queues`, called by
  `scripts/build_frontier_rollcall_ontology.py`) restores both on the next ontology rebuild.
  A future edit to the roll-call producer should also queue mappings inherited from a
  low-confidence bill adjudication.
- That any downstream consumer of the OpenAI queue tolerates the added column. Only
  `scripts/audit_ideology_evidence_layer.py` was found reading it, and it counts rows only.
- Scientific acceptance of the Luna adjudication layer; `ideology-04`'s caveat on that
  remains.

## Limitations and notes

- The reconciliation is **append-only**: an existing queue row is never removed or
  rewritten, so a later re-adjudication that raises a bill to high confidence would leave
  its review row in place. Queue rows are review records, and the contract asks for
  queue-on-low, not dequeue-on-change.
- The registered write scope names
  `data/manual/ideology/frontier_legislative_bill_adjudications_luna_review_queue.csv`,
  which does not exist. The live artifact that the audit reads and the producer writes is
  `data/processed/legislative/frontier_legislative_bill_adjudications_luna_review_queue.csv`;
  that file was repaired. The scope row should be corrected to the processed path.
- The 16 appended Luna rows carry the manual file's columns plus
  `review_reason=low_confidence_admitted_mapping`; the roll-call row carries
  `unit_id=LS-1548315`, `decision=map`, the validated axis/pole, `confidence=low`,
  `terminal_status=mapped_frontier_policy_pole`, and the same `review_reason`.
- `scripts/promote_luna_bill_adjudications.py` was inspected but not changed: it promotes
  the adjudication output, and queue membership is independent of promotion.

## Out-of-scope findings (recorded, not repaired)

- The `adjudication_authority` of all 35,619 vote-evidence rows is
  `frontier_manual_review:<rule>` although the bill decisions are Luna; already flagged for
  `ideology-11` in the 2026-09-10 funnel audit.
- The stale `candidate_research_final_status.csv` (26 cycles) and the other `ideology-05..07`
  caveats are tracked under separate tasks and were not touched here.
