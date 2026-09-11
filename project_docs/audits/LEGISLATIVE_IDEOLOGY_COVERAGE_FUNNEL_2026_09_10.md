# Legislative ideology coverage funnel — 2026-09-10

Internal execution evidence for `ideology-01` ("Reconcile the current evidence
coverage funnel") under
[CHECKLIST-EXECUTION-20260910.md](../coordination/CHECKLIST-EXECUTION-20260910.md).
This is a read-only audit: no ideology pipeline stage, LLM call, score, page,
warehouse or `docs/` write ran. It recomputes the funnel from current local CSV
outputs and checks the documented figures. Supporting the task is **not**
completing it: scientific acceptance of the 2026-09-08 evidence layer remains
open under `ideology-04..11`.

Phase 5 governance reconciliation for the two accepted-but-undocumented
2026-09-08 changes is in
[ABSOLUTE_IDEOLOGY_REBUILD.md](../model/ABSOLUTE_IDEOLOGY_REBUILD.md), section
"Evidence layer as of 2026-09-08".

## Method

- Counted with Python `csv` streaming reads only (no pandas, no whole-table
  load); one bounded pandas process (the ontology builder, below) ran against a
  temporary directory copy and wrote nothing into the repository.
- No central-warehouse write. The only SQL used was one read-only
  `SELECT count(*) … FROM rollcall` on the derived roll-call research database
  (`file:…?mode=ro`, `PRAGMA query_only=ON`).
- Bill identifiers are normalized by stripping a trailing `.0` (the
  comprehensive-classification and ontology files store them as float strings;
  the manual adjudication file as plain integers).

Counted inputs (SHA256 and local modification time at read time):

| File | Rows | SHA256 | Modified (local) |
|---|---:|---|---|
| `data/processed/legislative/comprehensive_rollcall_classifications.csv` | 60,704 | `65f9c2f053b0f0efe6370ef33dbb528aad87ac57bb4d2db69f6f640d4b82a260` | 2026-08-24 22:33:07 -0500 |
| `data/processed/legislative/frontier_rollcall_ontology_v3.csv` | 61,003 | `b45f5f2ec74562bfafd2988e0c32e2502880b5888be36fe7c444993fba72c274` | 2026-09-08 20:55:29 -0500 |
| `data/manual/ideology/frontier_legislative_bill_adjudications.csv` | 28,833 | `c958e62433b1e6c482c63c3e2ac841886cfb92b0bb57511fb966c12f0dd2bb66` | 2026-09-08 20:55:27 -0500 |
| `data/manual/ideology/backups/frontier_legislative_bill_adjudications.human_review.pre-luna-20260908.csv` | 9,116 | `681ad56eacbe1f1c08caffe928913f50746df64c422cca43248faadf72328b86` | 2026-08-21 10:21 |
| `data/processed/ideology/candidate_legislative_position_evidence_v3.csv` | 35,619 | `6909ac46c9d7faf905aca47db9658de6371991793ab63d02b2ae6d850388d045` | 2026-09-08 20:59:36 -0500 |
| `data/processed/ideology/candidate_legislative_sponsorship_evidence_v3.csv` | 16,181 | `33fdc0ce15017151e9b79910e3d7a8c20f8f67799043a68bd1c538a5a6c34a8d` | 2026-09-08 23:18:49 -0500 |
| `data/processed/ideology/candidate_issue_valence_v3.csv` | 18,958 | `8506ac12e54dc83eab0e9b0b6633241d2ffc4f11ade49a500497949f0e68b18b` | 2026-09-08 23:21:49 -0500 |
| `data/processed/ideology/candidate_ideology_full_universe.csv` | 1,564 | `fef4365f6217dfb37ef6b0414cd7b8c8bb07217647774223dd633b8853985b59` | 2026-09-08 20:57:17 -0500 |
| `data/processed/legislative/historical_frontier_rollcall_ontology_v3.csv` | 29,475 | not hashed | — |

The session-chamber denominator is the existing audit rule (every year
1998–2026 × {house, senate}); it was confirmed against both
`unified_legislative_rollcall_coverage.csv` (57 present rows summing 60,704) and
the classification file's distinct `(session_year, chamber)` cells (57).

## Current funnel

| Stage | Count | Source and method |
|---|---:|---|
| Expected session-chamber cells, 1998–2026 | 58 | 29 years × 2 chambers |
| Present session-chamber cells | 57 | distinct `(session_year, chamber)` in `comprehensive_rollcall_classifications.csv`; the single absent cell is 2000 Senate |
| Normalized roll calls | 60,704 | distinct `canonical_rollcall_id` = 60,704 (31,233 LegiScan rows carrying `roll_call_id` + 29,471 pre-LegiScan journal rows without one); the research warehouse `rollcall` table independently holds 60,704 distinct ids |
| Roll calls with a terminal ontology disposition | 60,704 | `frontier_rollcall_ontology_v3.csv` covers exactly that id set; every id has one `terminal_status` |
| **Roll calls with a Luna-admitted canonical axis/pole** | **2,022** | ontology `decision = map`, distinct ids = 1,766 frontier-derived (LegiScan) + 256 historical journal, zero overlap |
| Mapped (roll call, axis, pole) rows | 2,321 | ontology rows with `decision = map` |
| Distinct mapped axes (roll-call layer) | 69 | ontology mapped rows |
| Roll calls appearing in candidate vote evidence | 782 | distinct `source_record_id` in the vote-evidence file (LS 573, JRC 142, SJRC 67) |
| Vote-evidence records | 35,619 | `candidate_legislative_position_evidence_v3.csv`; 550 candidate-cycles, 384 persons, 58 axes, all `evidence_weight` 1.0 |
| Sponsorship-evidence records | 16,181 | `candidate_legislative_sponsorship_evidence_v3.csv`; 420 candidate-cycles, 284 persons, 77 axes, 5,018 distinct bills (3,452 of them with no recorded floor roll call), all `evidence_weight` 1.2 |
| Candidate-cycles with legislative-channel evidence (vote ∪ sponsorship) | 569 | union of the two evidence files |
| Candidate-cycles with any v3 evidence profile | 1,124 | distinct cycles in `candidate_issue_valence_v3.csv` |
| Candidate-issue profiles | 18,958 | valence rows |
| Scoreable issue profiles (`issue_score_available`) | 16,044 | valence rows with `True` (2,914 `False`) |
| Candidate-cycles with ≥1 scoreable profile | 1,104 | valence `True` distinct cycles |
| Candidate-cycle universe | 1,564 | `candidate_ideology_full_universe.csv` rows |
| Universe cycles with a behavioral legislative score | 550 | non-empty `behavioral_ideology`; exactly equal to the 550 cycles carrying vote evidence |
| Universe cycles with no issue profile | 440 | 1,564 − 1,124 |

Bill-level adjudication layer (`frontier_legislative_bill_adjudications.csv`,
28,833 rows, one per digitized bill):

| Bucket | Bills |
|---|---:|
| Substantive mapping decisions (`map` + `multi_axis`) | 8,653 (7,637 + 1,016) |
| `symbolic` | 8,806 |
| `procedural` | 6,571 |
| `local_non_generalizable` | 3,469 |
| `mixed_no_scalar_direction` | 770 |
| `insufficient_text` | 564 |
| Mapping bills that have a recorded floor roll call | 2,905 (validator `eligible_bills`) |
| Mapping bills with no floor roll call | 5,748 |

## Disposition versus substantive evidence

Every roll call carries exactly one terminal disposition; only 2,022 of 60,704
(3.3%) carry substantive mapped direction. Exclusion classes (distinct roll
calls):

| Terminal status | Roll calls |
|---|---:|
| `mapped_frontier_policy_pole` | 1,766 |
| `mapped_historical_frontier_policy_pole` | 256 |
| `excluded_procedural_or_ambiguous_motion` | 49,305 |
| `excluded_historical_non_scalar` | 4,349 |
| `excluded_historical_local` | 1,572 |
| `excluded_frontier_procedural` | 1,446 |
| `excluded_frontier_local_non_generalizable` | 977 |
| `excluded_historical_budget_baseline` | 534 |
| `excluded_frontier_insufficient_text` | 149 |
| `excluded_frontier_mixed_no_scalar_direction` | 136 |
| `excluded_historical_insufficient_text` | 114 |
| `excluded_frontier_symbolic` | 66 |
| `excluded_historical_symbolic` | 24 |
| `excluded_historical_conflicting_poles` | 10 |
| **Total** | **60,704** |

Reading this correctly: the 8,653 substantive bill decisions are not 8,653
mapped roll calls. Only 2,905 of those bills have a recorded floor roll call at
all, and only 1,766 roll calls survive the motion test
(`motion_disposition = bill_direction_applies`) plus canonical admission. The
remaining 49,305 roll calls are procedural or ambiguous motions on bills that
the bill layer may also have mapped; they are disposition rows, not evidence.

## Documented figures: match / mismatch

| Documented figure | Documented in | Recomputed | Verdict |
|---|---:|---|---|
| 58 expected session-chambers, 1998–2026 | `LEGISLATIVE_IDEOLOGY_COVERAGE_AUDIT.md`; `legislative_ideology_coverage_audit_funnel.csv` | 58 | MATCH |
| 57 present session-chambers | same; `unified_legislative_rollcall_coverage.csv` | 57 (2000 Senate absent) | MATCH |
| 60,704 normalized roll calls | coverage audit; `LEGISLATIVE_IDEOLOGY_POST_REPAIR_COVERAGE.md`; both 2026-09-08 coordination records | 60,704 | MATCH |
| 987 issue-mapped (ontology-mapped) votes | coverage audit; post-repair coverage; funnel CSV | 987 | MATCH, reproduced |
| 550 candidate-cycles with legislative scores | coverage audit; post-repair coverage; `candidate_ideology_full_universe.csv` | 550 | MATCH |
| 2,022 mapped roll calls | `IDEOLOGY-ROLLCALL-OPENAI-CLASSIFY-20260908.md` (post-recovery result) | 2,022 (1,766 frontier + 256 historical) | MATCH |
| 35,619 vote-evidence records | same | 35,619 | MATCH |
| 16,181 sponsorship-evidence rows | `SPONSORSHIP-IDEOLOGY-PIPELINE-20260908.md` | 16,181 | MATCH |
| 16,044 scoreable issue positions | same | 16,044 | MATCH |
| 1,124 candidates with v3 evidence | same | 1,124 candidate-cycles (1,104 with ≥1 scoreable profile) | MATCH |
| 4,730 profiles corroborated by >1 source type | same | 4,730 | MATCH |
| 6,740 profiles carrying sponsorship signal | same | 6,739 | MISMATCH by 1 (definition of the sponsorship-touched profile not recorded; not resolved) |
| 2,895 eligible (mapping) bills | `IDEOLOGY-ROLLCALL-OPENAI-CLASSIFY-20260908.md` (first full-corpus result) | 2,905 | SUPERSEDED by the same record's recovery pass (`eligible_bills` 2,895 → 2,905); current 2,905 |
| 2,019 mapped / 781 distinct roll calls used | same, before/after table | 2,022 / 782 | SUPERSEDED by the recorded recovery pass (+3 mapped, +3 records, +1 distinct roll call); the table predates it |
| Decision mix map 7,616 / multi_axis 1,013 / symbolic 8,802 / procedural 6,563 / local 3,460 / mixed 780 / insufficient 599 | same, "Full-corpus Luna run" narrative | 7,637 / 1,016 / 8,806 / 6,571 / 3,469 / 770 / 564 | MISMATCH: the narrative's mix predates the recovery pass; the promoted file (7,637/1,016) is authoritative |
| 13,617 human vote-evidence records | post-repair coverage; before/after table (human column) | not recomputed | NOT ESTABLISHED |
| 403 distinct roll calls used; 26 axes (human column) | same | not recomputed | NOT ESTABLISHED |

The 987 reproduction is exact and deliberate: the ontology builder
`scripts/build_frontier_rollcall_ontology.py` (unmodified vs HEAD) was rerun
against a temporary copy of the two roll-call inputs with `MANUAL` pointed at
the retained pre-Luna human backup, writing to `%TEMP%` only. It reports
`Input roll calls: 60,704; mapped roll calls: 987` (731 `mapped_frontier_policy_pole`
+ 256 `mapped_historical_frontier_policy_pole`). No repository file changed.
What cannot be recomputed is the human-era *evidence* layer (13,617 records, 403
distinct roll calls, 26 axes): the human-era
`candidate_legislative_position_evidence_v3.csv` was overwritten in place on
2026-09-08 and no byte copy is retained, so those three figures rest on the
documented 2026-08-24 audit only.

## Provenance of the classification scoring input

Exact state at read time:

```text
$ git diff --stat HEAD -- data/processed/legislative/comprehensive_rollcall_classifications.csv
 .../comprehensive_rollcall_classifications.csv     | 103095 +++++++++++-------
 1 file changed, 60704 insertions(+), 42391 deletions(-)
$ git diff --numstat HEAD -- data/processed/legislative/comprehensive_rollcall_classifications.csv
60704  42391  data/processed/legislative/comprehensive_rollcall_classifications.csv
$ git status --porcelain -- data/processed/legislative/comprehensive_rollcall_classifications.csv
 M data/processed/legislative/comprehensive_rollcall_classifications.csv
```

- The file is **modified versus HEAD** with exactly `+60,704 / −42,391` lines,
  the same delta the 2026-09-08 record already flagged. HEAD
  (commit `7ffd27e`, 2026-08-16) holds the 42,391-row version. The working-tree
  mtime is 2026-08-24 22:33, i.e. it predates the Luna work.
- Producer: `scripts/build_comprehensive_rollcall_classifications.py` (itself
  modified vs HEAD). The accepted coordination record that explains the change is
  `coordination/IDEOLOGY-HISTORICAL-FINAL-VOTES-003.md` with its audit
  `audits/HISTORICAL_FINAL_VOTE_IDEOLOGY_COVERAGE.md`: every one of the 60,704
  normalized roll calls, including 18,337 previously omitted journal votes, was
  given an explicit terminal disposition, and measure-level direction is
  propagated only to final-passage/conference-report votes.
- Consequence: `frontier_rollcall_ontology_v3.csv`, all three v3 evidence files
  and the valence scores are downstream of this uncommitted 60,704-row input.
  The current scores therefore depend on a working-tree artifact whose
  provenance is accepted in a coordination record but not reproducible from
  HEAD. This audit records the state; it does not resolve it. Settling it is a
  precondition for any published score rebuild, as the 2026-09-08 record noted.
- Related working-tree state, recorded for completeness: the manual
  adjudication file is ` M` (the Luna replacement of the human layer, with the
  human file preserved as the hashed backup above); the ontology and evidence
  files are untracked (`??`), so they have no HEAD baseline at all.

## Documentation and provenance findings (recorded, not repaired)

1. **Stale authority label.** All 35,619 vote-evidence rows carry
   `adjudication_authority = frontier_manual_review:<rule>`, although the bill
   decisions they rest on were produced by `gpt-5.6-luna`
   (`reviewer = gpt-5.6-luna` on all 28,833 rows). The prefix is hardcoded at
   `scripts/build_legislative_position_evidence_v3.py:169`; the sponsorship
   channel correctly labels `frontier_luna_sponsorship:…`. Scores are
   unaffected, but any provenance report or release bundle that reads that
   column currently misattributes the vote channel to the superseded human
   layer. Out of this task's write scope; flagged for `ideology-11`.
2. **Stale decision-mix narrative.** The 2026-09-08 record's "Full-corpus Luna
   run" paragraph still prints the pre-recovery mix (map 7,616 / multi_axis
   1,013 / …); the promoted file and the validator carry the post-recovery mix.
   The record's own later sections already give the corrected numbers.
3. **Unreconciled coverage summary.** `candidate_ideology_full_coverage.csv`
   (modified 2026-09-08 20:57, untracked) sums to `legislative_scores = 550`,
   `any_ideology = 704`, `pct_profiles = 188` across its 16 cycle × party rows.
   Its `any_ideology` (704) does not match the 1,124 candidate-cycles with a v3
   evidence profile, and the file's column definitions are not documented in
   the records cited here. Treat its fields as unverified until defined.
4. **Closed-research baseline drift.** `audits/CANDIDATE_ISSUE_RESEARCH_CLOSURE.md`
   closes the search loop at 1,098 of 1,564 candidate-cycles with a temporally
   valid issue profile (466 without). The current valence layer shows 1,124 with
   a profile and 440 without. The improvement is consistent with the 2026-09-08
   Luna/sponsorship rebuild, but no record restates the closure audit's
   terminal accounting against the new layer.
5. **`reports`-side note.** `legislative_ideology_coverage_audit_funnel.csv`
   (2026-08-24) still reports `rollcalls_mapped = 987`; it is a historical
   snapshot, not a current funnel, and must not be read as the live count.

## What this evidence supports, and what stays open

Supports (does not complete):

- `ideology-01`: the funnel is now recomputed and reconciled as above; the task
  additionally asks that disposition be distinguished from substantive
  evidence, which the two disposition tables and the bill/roll-call distinction
  do. Closing the task is the primary session's decision.
- `ideology-04` (roll-call eligibility and issue mapping): the current
  exclusion census, the 1,766 admitted final-policy roll calls, the
  `excluded_*` classes and the zero-contradictory-pole validator check are the
  evidence base, but eligibility re-verification with fixtures is not done here.
- `ideology-05` (evidence channels without double counting): channel sizes,
  overlaps (550 vote cycles, 420 sponsorship cycles, 569 union, 1,124
  all-source, all inside the 1,564 universe) and the sponsorship weight are
  recorded; the minimum-evidence thresholds are not re-evaluated.
- `ideology-07` (temporal cutoffs and identity joins): every evidence row in
  both legislative files is `pre_or_same_cycle_legislative_action`, all 782
  source roll calls and 420 sponsor cycles sit inside the universe; the
  sponsorship mid-session placeholder is documented in the model document.

Not established by this audit:

- Scientific acceptance of the Luna full-corpus adjudication and of the
  sponsorship channel. Both were independently code-reviewed (per their
  coordination records) and the integration validator passes, but
  `validate_frontier_ideology_integration.py` checks wiring, identity, coverage
  and schema invariants only; it is not scientific validation, and the checklist
  currently carries no Phase 5 task that owns their acceptance.
- The human-era evidence-layer figures (13,617 records, 403 distinct roll calls,
  26 axes). The artifact is gone; only the documented value remains.
- Whether the uncommitted `+60,704 / −42,391` classification input is the
  version intended to feed a published rebuild.
- The single-profile `6,739` vs `6,740` sponsorship discrepancy and the
  `candidate_ideology_full_coverage.csv` field definitions.
- Any publication state: nothing here authorizes `docs/`, a commit, or a score
  rebuild.

## Verification

```powershell
& .venv/Scripts/python.exe scripts/validate_frontier_ideology_integration.py
```

Result: exit 0, all 12 checks passed — archive 28,833 rows / one terminal
disposition each; non-roll-call bills 19,722; `eligible_bills` 2,905;
roll-call input 60,704 / output 60,704; linked 9,111 with 0 missing; terminal
decisions `exclude` 58,682 / `map` 2,321; 2,321 mapped rows validate; 0
contradictory roll-call/axis pole pairs; 35,619 evidence rows use frontier
authority with 0 duplicate ids; 18,958 unique candidate-issue profiles; 564
`insufficient_text` bills with 0 scoring leak.

The recomputations above used counting scripts only; no focused test file was
added or run, because this audit changes no code or data and asserts no
new contract. The single pandas process was the bounded human-era builder
reproduction described under "Documented figures"; it wrote only to `%TEMP%`.

Repository HEAD inspected while working: `720c350`. No commit, publication,
score rebuild, page render, LLM call, `docs/` write or central-warehouse write
occurred.