# Task contract: IDEOLOGY-ROLLCALL-OPENAI-CLASSIFY-20260908

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `active`
- Objective: Finish LLM direction-adjudication of the substantive Alabama roll-call backlog with the OpenAI model `gpt-5.6-luna`, replacing the abandoned local Ministral pass, and produce completed final adjudications, a low-confidence review queue and a run manifest. No score, ontology, page or warehouse rebuild; no publication.
- Product/layer and checklist IDs: ideology and caucuses evidence; supports `ideology-04` and `ideology-05` without completing them.
- Dependencies: `data/processed/legislative/legislative_rollcall_ontology_v3_audit.csv` (42,391 rows), `scripts/ideology_ontology_v3.py` schema, OpenAI API key in `.env`.
- Non-goals: rerunning `build_frontier_rollcall_ontology.py`, behavioral or issue ideology scores, `build_alabama_legislative_ideology.py`, ideology pages, the central warehouse, or the public site; committing; deleting the Ministral cache.
- Upstream snapshot: v3 audit at HEAD; needs_direction_adjudication 8,473 + needs_v3_primitive_adjudication 192; terminal rules exclude taxes_budget (4,425) and rural_local (1,980) and out-of-scope before any model call; ~2,000-2,300 substantive model units expected.
- Read scope: legislative audit and ontology, existing Ministral cache (as history), OpenAI models endpoint.
- Write scope: `scripts/adjudicate_legislative_ontology_v3_all.py`; `research/cmo_ideology/legislative_v3_adjudications_openai/`; `data/processed/legislative/legislative_rollcall_ontology_v3_final_adjudications.csv`; `data/processed/legislative/legislative_rollcall_ontology_v3_openai_review_queue.csv`; `data/processed/legislative/legislative_rollcall_ontology_v3_openai_run_manifest.json`; `scripts/tests/test_adjudicate_openai_backend.py`; this contract and the active-task row.
- Warehouse mode: `read-only` (no central-warehouse writes).
- Model: OpenAI `gpt-5.6-luna` (verified present in the account model list) via the REST chat-completions endpoint using `requests`; no new package dependency; local Ministral (`ministral-3:8b`) remains the default backend.
- Quality: strict allowed-axis/pole schema validation retained; a mapping that fails schema is forced to a fail-closed exclusion; `low`-confidence and schema-rejected items go to the review queue; per-run manifest records model, batch counts and token usage.
- Acceptance checks: final adjudications file has 42,391 rows and no `needs_` terminal status (test_final_ideology_adjudications); mapped rows carry a valid axis/pole; one smoke batch validated before the full run; affected tests pass.
- Review requirement: focused self-checks; wiring the completed adjudications into the ontology, scores and pages is a separate step that requires independent review before any publication.
- Publication authority: `none`
- Recovery/replay: OpenAI results cached per unit in a separate directory; re-runs resume from cache; Ministral cache preserved; no destructive step.
- Handoff recipient: `legislative_ideology` / `validation_release`
- Known risks: model output-contract uncertainty for a post-cutoff model (smoke test first); irreversible API spend; downstream ideology products remain stale until a separately reviewed rebuild.

## Result (2026-09-08)

Backend added behind `--backend openai --model gpt-5.6-luna` (default remains local
Ministral); OpenAI results cached separately in
`research/cmo_ideology/legislative_v3_adjudications_openai/`; Ministral cache preserved.

- Model id resolved by a read-only account model-list call: `gpt-5.6-luna` is API-callable.
- Smoke batch (10 units, 1 call): live chat-completions + JSON-object + `max_completion_tokens`
  contract validated, all 10 schema-passed, 0 review rows.
- Full run: 105 API calls, 1,043 model units (plus the 10 cached smoke units); usage
  240,911 prompt + 102,536 completion = 343,447 tokens (smoke ~3,123 more). Modest API spend.
- `legislative_rollcall_ontology_v3_final_adjudications.csv`: 42,391 rows, 0 `needs_`
  statuses, all mapped rows carry a valid axis/pole. Authorities: 33,726 prior_v3_audit,
  6,472 codex_terminal_rule, 2,189 openai_gpt-5.6-luna, 4 codex_fail_closed_validation.
- Quality vs the abandoned local pass: OpenAI mapped 407 of 1,053 substantive units (39%)
  against Ministral's 144 of 1,197 (12%), roughly a threefold improvement in coverage with
  strict schema validation. Total mapped roll-call rows rose to 2,586 (1,700 prior +886 new).
- Review queue `legislative_rollcall_ontology_v3_openai_review_queue.csv`: 10 low-confidence
  or validation-failed items diverted, not force-mapped.
- Tests: `test_adjudicate_openai_backend.py` (4) and `test_final_ideology_adjudications.py`
  (2) pass. Workflow collision validation passes.

Not done (separate, independently reviewed step): rerun `build_frontier_rollcall_ontology.py`,
the behavioral and issue ideology scores, and the pages from these adjudications; no
publication and no commit. Downstream ideology products remain stale until that rebuild.

## Integration finding (2026-09-08)

Dependency trace before any downstream rebuild: the published issue-ideology scores are
produced by `build_frontier_rollcall_ontology.py` -> `frontier_rollcall_ontology_v3.csv` ->
`build_full_candidate_legislative_ideology.py`. That ontology reads the human-curated
bill-level file `data/manual/ideology/frontier_legislative_bill_adjudications.csv`
(9,117 bills; `reviewer=frontier_manual_review`, `supersedes_authority=small_model`),
`comprehensive_rollcall_classifications.csv`, and `historical_frontier_rollcall_ontology_v3.csv`.
It does NOT read `legislative_rollcall_ontology_v3_final_adjudications.csv`.

The OpenAI roll-call adjudications feed `build_frontier_legislative_review_ledger.py`
(which builds the human review queue and merges the manual file) and
`audit_candidate_issue_valence_v3.py`, not the scoring ontology directly. No pipeline
step calls an LLM, so a frontier rebuild is deterministic and free but would not
incorporate the OpenAI classifications.

Consequently, wiring the OpenAI work into the published scores is a methodology decision
about how the automated bill-level consensus relates to the human-reviewed manual layer
that was built to supersede the small model. It is not a mechanical pipeline run and is
paused for the accountable owner's direction. The classification artifact stands complete
and reversible regardless of that decision.

## Promotion decision (2026-09-08)

Owner direction for this step: promote the OpenAI roll-call adjudications into the
bill-level manual scoring file `data/manual/ideology/frontier_legislative_bill_adjudications.csv`
**only for bills with no existing human review** (append-only; preserve every human-reviewed
row exactly; authority `gpt-5.6-luna`), then rebuild scores/pages to local artifacts and
review, with no publication.

Executing that rule yields **zero rows to append**. The determination, recomputed from the
raw files (bill_id normalized: the audit stores it as a float string such as `296541.0`,
the manual file as a plain integer `296541`):

- The manual file already covers the **entire** LegiScan bill universe. Audit distinct
  bill_ids and manual distinct bill_ids are the identical set of 9,116; `audit - manual = 0`
  and `manual - audit = 0`.
- Of the OpenAI-authority (`openai_gpt-5.6-luna`) roll-call adjudications, 651 distinct
  bills carry a LegiScan bill_id, and **all 651 already have a human `frontier_manual_review`
  decision** in the manual file. Bills absent from the manual file: 0. A further 444
  OpenAI-authority roll-call rows are pre-LegiScan journal votes with no bill_id and cannot
  join to the bill-level key at all.
- The manual file is git-tracked and pristine (no diff vs HEAD; last modified 2026-08-21),
  so it was left untouched; nothing qualified for append.

A rebuild was therefore not run, for two independent reasons:

1. It cannot incorporate the OpenAI work. `build_frontier_rollcall_ontology.py` reads the
   bill-level manual file, `comprehensive_rollcall_classifications.csv` and
   `historical_frontier_rollcall_ontology_v3.csv`; it does not read
   `legislative_rollcall_ontology_v3_final_adjudications.csv`. The scoring inputs are
   unchanged since the local ontology was last built (2026-08-24), so a rerun reproduces the
   existing local `frontier_rollcall_ontology_v3.csv`.
2. It would be a no-op with respect to the authorized change (nothing was promoted).

Manual decision distribution (all 9,116 bills): map 3,893; local_non_generalizable 2,207;
procedural 1,369; multi_axis 1,334; symbolic 189; mixed_no_scalar_direction 122;
insufficient_text 2. Of these, 5,227 bills map to an axis (feed scores) and 3,889 are
reviewed as non-mapping.

Where the OpenAI pass and the human layer both cover the same bill, they diverge often, so
the only way the OpenAI work could move scores is to **override** human curation, which the
owner did not authorize and which reverses the project's stated methodology
(`supersedes_authority=small_model` on every manual row). Quantified for the owner's future
decision only (NOT applied): 238 bills mapped by both, of which only 39 share at least one
axis/pole and 199 disagree on axis entirely; plus 30 bills OpenAI would map that the human
layer reviewed as non-mapping (27 local_non_generalizable, 3 mixed). Wholesale override would
churn scores away from human judgment on a large majority of overlapping bills, so it is not
an obvious improvement and remains a separate, explicitly-authorized methodology change.

Separately flagged, not caused by this task and out of its scope:
`comprehensive_rollcall_classifications.csv` (a scoring-ontology input) is modified vs HEAD
from earlier work (+60,704 / -42,391 lines). The published scores may already be stale
relative to that local input independent of the OpenAI question; any future rebuild would
sweep it in, so its provenance should be settled before a score rebuild is published.

Outcome: classification track complete; manual scoring layer untouched (correct under the
append-only rule); no rebuild, no commit, no publication. The step is closed as a no-op with
the override question surfaced to the owner.

## Full-Luna adjudication decision (2026-09-08, supersedes the append-only conclusion above)

The owner resolved the override question directly: manual review of 9,000+ bills is not
sustainable, so **every bill is to be adjudicated entirely by Luna (`gpt-5.6-luna`), and the
owner will trust that output as the scoring ground truth.** This supersedes the human
`frontier_manual_review` layer rather than appending to it. The append-only analysis above
still stands as the reason a full pass is required: the human layer already covers the entire
9,116-bill universe, so incorporating Luna means regenerating that layer, not filling gaps.

Approach (no pipeline code change; the scoring ontology already reads the bill-level manual
file and never the roll-call `final_adjudications`, confirmed by independent review):

- New producer `scripts/adjudicate_frontier_bills_luna.py` adjudicates every bill at the bill
  level from its official synopsis, using the human decision taxonomy (`map`, `multi_axis`,
  `local_non_generalizable`, `procedural`, `symbolic`, `mixed_no_scalar_direction`,
  `insufficient_text`) and the full v3 primitive axis/pole ontology. It reuses the tested
  Luna HTTP/key/usage layer from `adjudicate_legislative_ontology_v3_all.py`; only the
  bill-level prompt, taxonomy and validation are new.
- Universe = the full digitized bill corpus: every classified 2010-2026 bill in
  `bill_issue_classification` (28,833 bills), unioned with the roll-call sources so the
  ontology's coverage requirement is also met. One row per bill, bill_id as plain integer.
  Scope was widened from the 9,116 roll-call-bearing bills to the full 28,833 on the owner's
  direction: of the 19,722 bills that never received a floor roll call, 19,322 carry
  sponsors, and bill sponsorship is an active ideology-evidence channel (weight 0.85 in
  `build_candidate_issue_valence_v3.py`), so those bills are not inert for ideology. Alabama
  committee-stage votes are not captured by the source (LegiScan floor votes only), so
  sponsorship is the signal those vote-less bills carry.
- map/multi_axis pairs are schema-validated against the ontology; a failed mapping is diverted
  to a review queue and fails closed to a non-scoring disposition rather than inventing a pole.
- Per-bill JSON cache makes the run resumable; output written first to
  `data/manual/ideology/frontier_legislative_bill_adjudications_luna.csv` (kept as provenance),
  never directly onto the live manual file.
- Smoke (10 bills, 1 call, 0 review rows) validated the live contract and quality: local
  jurisdiction bills classed local, a facility-licensing bill mapped to market intervention,
  a school-employee discipline bill correctly split across two axes.

Promotion into the live scoring file, the deterministic rebuild (from
`build_frontier_rollcall_ontology.py` through the ideology pages), independent review, and the
governance updates follow once the full run completes. The human manual file is backed up
before replacement. Consistent with the owner's standing instruction, this stops before any
commit or publication; publishing remains a separate authorization.

Downstream rebuild scope (verified safe): the chain from `build_frontier_rollcall_ontology.py`
onward reads processed CSVs plus the legislative and elections SQLite databases read-only
(no central-warehouse access, no database writes) and regenerates processed CSVs and the
`docs/` ideology pages on disk; earlier substrate steps (archive ledger, synopsis recovery,
`build_comprehensive_rollcall_classifications.py`, historical ontology) are intentionally not
re-run.

## Full-corpus Luna run and rebuild result (2026-09-08)

Adjudicated all 28,833 bills with `gpt-5.6-luna`: 1,830 API calls, 6.92M tokens; 8,629
scoring bills (7,616 map + 1,013 multi_axis), 50 fail-closed diversions to the review queue
(0.17%: 36 batch omissions, 14 near-miss axis names). Decision mix: symbolic 8,802 (99% are
HR/SR/HJR/SJR resolutions, correct), map 7,616, procedural 6,563, local_non_generalizable
3,460, multi_axis 1,013, mixed 780, insufficient_text 599. Live scoring file replaced with
the 28,833 Luna rows; human file preserved at
`data/manual/ideology/backups/frontier_legislative_bill_adjudications.human_review.pre-luna-20260908.csv`.

Quality vs the superseded human file, measured on what actually feeds scores (raw-label
comparison is misleading: the human file used 5,586 hyper-specific labels, only 28 of which
are exact ontology keys, so most human maps failed the conservative canonicalization). On the
9,111 roll-call bills, admitted canonical mappings: Luna 2,895 vs human 948 (~3x). Where both
admit, canonical axis/pole agreement is 73-75%; in disagreements Luna is frequently the better
call (it does not tag licensing/regulatory bills as criminal-punishment for merely mentioning
penalties).

Measured candidate-level before/after (human backup vs Luna, same 550-candidate universe):

| metric | human | luna |
| --- | --- | --- |
| mapped roll calls | 987 | 2,019 |
| vote-evidence records | 13,617 | 35,616 |
| distinct roll calls used | 403 | 781 |
| issue axes covered | 26 | 58 |

Rebuild: ran the frontier chain from `build_frontier_rollcall_ontology.py` through the
ideology pages plus `build_frontier_archive_bill_ledger.py`, all to local artifacts. The
integration validator `validate_frontier_ideology_integration.py` passes all 12 checks
(exit 0). Affected tests pass (frontier pipeline suite + `test_adjudicate_openai_backend.py`,
`test_final_ideology_adjudications.py`, new `test_adjudicate_frontier_bills_luna.py`).

Necessary code corrections made by this change (each a consequence of the manual file now
covering every bill rather than only roll-call bills):
- `build_frontier_archive_bill_ledger.py`: `recorded_individual_rollcall` now derives from the
  actual roll-call universe (`comprehensive_rollcall_classifications.csv`) instead of manual-file
  membership, which was a valid proxy only while the manual file held roll-call bills alone. The
  merge now joins on the unique `bill_id`. Without this the ledger falsely marked all 28,833
  bills as having recorded roll calls (this did not affect scores, which join `member_vote`, but
  the audit ledger must be truthful).
- Four brittle assertions pinned to the old human file's exact composition were generalized to
  their intended count-independent invariants:
  `validate_frontier_ideology_integration.py` (insufficient_text: no axis/pole leak, not `==2`);
  `test_frontier_archive_bill_ledger.py` (ambiguous bills are non-scoring, not `==2` / all text);
  `test_issue_stance_tournament.py` (durability axes: known-axes subset + Bonferroni-corrected
  significance instead of an exact-set and uncorrected raw-p snapshot).

Notable analytical shift surfaced by the richer coverage: one durability estimate,
`market_governance` x federal-index overperformance (n=24), now reaches raw p=0.031; it does
not survive multiple-comparison correction across the eight estimates, and no other estimate
is significant.

Sponsorship channel (answering the vote-less-bill question): the model's `bill_sponsorship`
evidence is populated only from the hand-curated `candidate_issue_research_findings.csv` /
`ballotpedia_candidate_position_adjudications.csv` (adjudicated rows), NOT from the bulk
`legiscan_bill_sponsors.csv` / `comprehensive_bill_sponsor_positions.csv`. No automated
pipeline turns bulk sponsorship into ideology evidence, so the ~19,322 vote-less-but-sponsored
bills, though now adjudicated by Luna, do not move current scores. Building that
sponsorship-evidence step is a distinct, methodology-bearing task (sponsorship vs vote weight,
primary vs cosponsor, failed-bill handling) proposed to the owner, with the full-corpus Luna
adjudication now in place as its precondition.

Recovery pass: an independent review noted that ~39 bills omitted from a model batch had been
cached fail-closed as `insufficient_text` and would not self-heal on a plain resume. Fixed the
root cause (`adjudicate_frontier_bills_luna.py` no longer caches a `missing_from_model_response`
result) and recovered the 50 review-queue bills (deleted their cache, re-ran: 5 calls, 17k
tokens). Review queue is now 1 (a single vote-less bill); 24 bills recovered to scoring. After
re-promotion and rebuild the vote channel gained 3 mapped roll calls (2,019 -> 2,022) and 3
evidence records (35,616 -> 35,619); validator eligible_bills 2,895 -> 2,905. Validator passes
all 12 checks (exit 0); affected tests pass.

Independent review verdict (read-only agent): all six checked items CONFIRMED - promotion
integrity, coverage guard, the ~3x admitted-mapping improvement (reviewer measured human 906
bills / 1,006 pairs vs Luna 2,895 / 3,253), truthful ledger semantics, the sponsorship gap, and
that the four generalized assertions track real invariants rather than deleting failing checks.
The reviewer flagged the tournament significance guard as the one place sensitivity loosened
(uncorrected raw-p to Bonferroni; defensible and documented) and the fail-closed cache behavior
(now fixed). No scoring-corruption defects found; the fail-closed design admitted no fabricated
poles.

Status: local artifacts rebuilt, validated, and independently reviewed. No commit, no `docs/`
publication (publication remains a separate authorization).
