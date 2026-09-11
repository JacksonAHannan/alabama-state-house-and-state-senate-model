# Ideology evidence layer validation — 2026-09-11

Internal validation evidence for `ideology-04` (roll-call eligibility and issue mapping),
`ideology-05` (channels without double counting), `ideology-06` (minimum evidence and
missingness) and `ideology-07` (temporal cutoffs and identity joins), plus the provenance of
`data/processed/legislative/comprehensive_rollcall_classifications.csv`.

This is a **read-only audit**: no pipeline stage, score, warehouse, `docs/` or published export
was written; the only outputs are this report and its JSON companion. Reading used the standard
library `csv` streamer (stdlib `csv` streaming; no pandas; no warehouse load). Run:

```powershell
& .venv/Scripts/python.exe scripts/audit_ideology_evidence_layer.py
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_ideology_evidence_layer.py -q
```

Runtime: 18.172s; traced peak 352.7 MB; largest input 40.18 MB; generated 2026-09-11T15:09:24+00:00.

## Inputs

| file | rows | MB | sha256 (first 16) |
| --- | --- | --- | --- |
| data/processed/legislative/comprehensive_rollcall_classifications.csv | 60704 | 40.18 | 65f9c2f053b0f0ef |
| data/processed/legislative/frontier_rollcall_ontology_v3.csv | 61003 | 27.61 | b45f5f2ec74562bf |
| data/processed/legislative/historical_frontier_rollcall_ontology_v3.csv | 29475 | 17.98 | b6a35753498502ae |
| data/manual/ideology/frontier_legislative_bill_adjudications.csv | 28833 | 5.76 | c958e62433b1e6c4 |
| data/processed/ideology/candidate_legislative_position_evidence_v3.csv | 35619 | 22.39 | 6909ac46c9d7faf9 |
| data/processed/ideology/candidate_legislative_sponsorship_evidence_v3.csv | 16181 | 6.99 | 33fdc0ce15017151 |
| data/processed/ideology/candidate_position_evidence_v3.csv | 62745 | 34.56 | f0bdfe2112e96ea8 |
| data/processed/ideology/candidate_position_evidence_v3_all_sources.csv | 63881 | 37.82 | 5198371f527e7a8b |
| data/processed/ideology/candidate_issue_valence_v3.csv | 18958 | 2.96 | 8506ac12e54dc83e |
| data/processed/ideology/candidate_family_valence_v3_all_sources.csv | 4538 | 0.56 | 3ab301fa8bdbc49d |
| data/processed/ideology/candidate_ideology_full_universe.csv | 1564 | 0.84 | fef4365f6217dfb3 |
| data/processed/ideology/candidate_legislator_identity_crosswalk.csv | 1564 | 0.3 | 6fa23d496d2c59f6 |
| data/processed/elections/canonical_cmo_candidates_with_ideology_v3.csv | 1564 | 0.45 | 42d591309eeec4b5 |
| research/cmo_ideology/candidate_issue_research/candidate_research_final_status.csv | 1564 | 0.41 | fbb4aa801c192c7e |
| data/processed/legislative/frontier_legislative_bill_adjudications_luna_review_queue.csv | 1 | 0.0 | 4ea5d282ce194a79 |
| data/processed/legislative/legislative_rollcall_ontology_v3_openai_review_queue.csv | 10 | 0.0 | 65b05e8e5d52d55b |
| scripts/build_comprehensive_rollcall_classifications.py | — | 0.02 | 3acd7f6738a7abb9 |
| project_docs/coordination/IDEOLOGY-HISTORICAL-FINAL-VOTES-003.md | — | 0.0 | e7e41670aee153d4 |
| project_docs/audits/HISTORICAL_FINAL_VOTE_IDEOLOGY_COVERAGE.md | — | 0.0 | b6f33ba2b30446e3 |

## ideology-04 — roll-call eligibility and issue mapping

| terminal disposition | distinct roll calls |
| --- | --- |
| excluded_procedural_or_ambiguous_motion | 49305 |
| excluded_historical_non_scalar | 4349 |
| mapped_frontier_policy_pole | 1766 |
| excluded_historical_local | 1572 |
| excluded_frontier_procedural | 1446 |
| excluded_frontier_local_non_generalizable | 977 |
| excluded_historical_budget_baseline | 534 |
| mapped_historical_frontier_policy_pole | 256 |
| excluded_frontier_insufficient_text | 149 |
| excluded_frontier_mixed_no_scalar_direction | 136 |
| excluded_historical_insufficient_text | 114 |
| excluded_frontier_symbolic | 66 |
| excluded_historical_symbolic | 24 |
| excluded_historical_conflicting_poles | 10 |

- Mapped rows / distinct mapped roll calls: **2,321 / 2,022**.
- Mapped roll calls passing the classification motion test (`motion_disposition = bill_direction_applies`): **2,022 / 2,022 (1.0000)**; procedural/ambiguous mapped: **0**.
- Descriptive motion classes from `vote_description` (derived label, not the terminal test): {'final_passage': 1041, 'concurrence': 652, 'other_adopt_or_misc': 227, 'conference_report': 102}.
- Mapped rows failing `validate_primitive`: **0**.
- Polarity, all vote rows: **1,495 / 1,495** shared (candidate, bill, axis) cells agree (fraction 1.0000). Yeas only: **1,492 / 1,492** (fraction 1.0000).
- Review queue: Luna bill queue 1 row(s), OpenAI roll-call queue 10 row(s). Low-confidence mapping bills: **16**, of which **0** are in the queue. Low-confidence mapped roll-call rows: **1**, queued: **0**. Every low-confidence mapping queued: **False**.

## ideology-05 — channels without double counting

| source_type (all sources) | rows |
| --- | --- |
| legislative_vote | 35623 |
| bill_sponsorship | 16251 |
| candidate_questionnaire | 9316 |
| interest_group_rating | 1675 |
| interest_group_endorsement | 407 |
| candidate_interview | 141 |
| public_statement | 129 |
| candidate_platform | 91 |
| candidate_voter_guide | 16 |
| candidate_announcement | 15 |
| legislative_cosponsorship | 12 |
| candidate_reported_position | 12 |
| legislative_position | 11 |
| candidate_profile | 9 |
| candidate_statement | 9 |

_66 further source types are listed in the JSON companion._

- Combined ledger channels: {'legislative_vote': 35619, 'bill_sponsorship': 16181, 'candidate_questionnaire': 10945}.
- Distinct candidate-axis cells per channel: {'candidate_questionnaire': 3653, 'legislative_vote': 11547, 'bill_sponsorship': 6709}.
- Double counting: **1,495** (candidate, bill, axis) keys appear in both channels, covering 1,135 (candidate, bill) pairs (1,877 vote rows and 1,495 sponsorship rows). `aggregate()` sums both rows' `evidence_weight` (vote 1.0, sponsorship 1.2) per (candidate, cycle, axis); both channels count **by design** as distinct signals.
- Duplicate `evidence_id`s — vote 0, sponsorship 0, combined ledger 0, all sources 0.
- Profiles corroborated by more than one channel: **4,730** (valence grain; primary three channels 3,947, archival all sources 4,742); vote + sponsorship: **3,947**; questionnaire + vote: **208**.
- Bill-level overlap of Vote Smart / research rows with roll-call evidence is **not constructible** (Vote Smart questionnaire rows use the Vote Smart question id as source_record_id and research rows use a source URL; neither carries a LegiScan bill id, so a bill-level overlap test with roll-call evidence is not constructible from the artifacts.).

## ideology-06 — minimum evidence and missingness

| rule | value |
| --- | --- |
| issue_min_weight | 0.65 |
| family_min_weight | 1.5 |
| family_min_distinct_issues | 2 |
| candidate_min_scored_issues | 3 |
| candidate_min_scored_families | 2 |

| threshold outcome | candidate-cycles |
| --- | --- |
| universe | 1564 |
| with_observed_profile | 1124 |
| with_scored_issue | 1104 |
| meeting_three_issue_floor | 802 |
| meeting_two_family_floor | 492 |
| model_eligible | 492 |
| model_ineligible | 1072 |

- Integrated `ideology_v3_model_eligible` = **492**; recompute agrees: **True**.
- Candidate-cycles without current observed evidence: **440**; all carry `final_research_status = searched_no_recoverable_evidence` (440), of which 318 logged a manual broad search and 122 were closed by the structured Vote Smart / legislative / identity sweep. **Not searched: 0.**
- Residuals that gained current evidence after the closure file: **26**.
- Imputation: `neutrality_imputed` true in 0 rows; position-value `fillna`/impute lines: **0**. no fillna/impute applies to a candidate position value; unavailable issues and families stay NaN via Series.where(issue_score_available).

## ideology-07 — temporal cutoffs and identity joins

| temporal channel | rows | exact date | mid-session placeholder |
| --- | --- | --- | --- |
| legislative_vote | 35619 | 31251 | 4368 |
| bill_sponsorship | 16181 | 0 | 16181 |

- Cutoff violations: **0**; session outside cycle window: **0**; leakage from later service: **0**.
- Identity cardinality: {'distinct_people': 311, 'rows_with_identity': 768, 'cardinality_violations': 0, 'repeated_people': 218, 'candidate_cycles_held_by_repeated_people': 675}.
- `person_id` mismatch vs the universe: **0**.
- Cross-chamber evidence: **607** rows across **9** candidate-cycles ({'senate->house': 607}); 9 cycles carry the identity layer's `cross_chamber_pre_election_score` flag; candidate-cycles with evidence from a chamber the person did not serve in: **0**.

## Provenance of the classification input

- File: `data/processed/legislative/comprehensive_rollcall_classifications.csv` — **60,704** rows; working-tree sha256 `65f9c2f053b0f0efe6370ef33dbb528aad87ac57bb4d2db69f6f640d4b82a260` (CRLF working tree / LF blob (core.autocrlf=true)); committed blob `eb52a5762c3658f9d4e5d047a30fd3dde3ae5124` with sha256 `db4b1a1dc99a0ce2b89b09dee6eb9ce7b086b9f6d7e4bb06b81e1a30460f60e2`.
- Producer: `scripts/build_comprehensive_rollcall_classifications.py` sha256 `3acd7f6738a7abb944f9a4eb05f9f6c2fccfc4341e408e61dd9045b385f11a31`; git blob `a24f120af625cdaa9c22cb95633c24ae80768832`.
- Commits: HEAD `38c30819f3524c3d97cb7a1bfa4fb6ec00e8f249`; last touching the file `f407b9d0febe4ebfd814ce7e9f4cc6496de225fc`; previous `7ffd27e382ca804612cdee63c87f5015f4c2fc72`; numstat `60704	42391	data/processed/legislative/comprehensive_rollcall_classifications.csv`.
- Explaining records: `project_docs/coordination/IDEOLOGY-HISTORICAL-FINAL-VOTES-003.md` and `project_docs/audits/HISTORICAL_FINAL_VOTE_IDEOLOGY_COVERAGE.md`.
  The +60,704 / −42,391 expansion is the historical final-vote disposition pass: every one of the
  60,704 normalized roll calls now carries a terminal disposition, and bill direction is admitted
  only for final-passage and conference-report votes.

## What this evidence does not establish

- Scientific acceptance of the Luna (gpt-5.6-luna) full-corpus bill adjudication and of the sponsorship channel.
- The human-era evidence layer (13,617 records / 403 roll calls / 26 axes): the artifact was overwritten and no byte copy is retained.
- Whether low-confidence (and medium-confidence) admitted mappings are analytically reliable; this audit only records that they are not diverted to the review queue.
- Bill-level overlap between Vote Smart / research rows and roll-call evidence: research rows carry no bill identifier.
- Identity of candidates without a resolved people_id (796 of 1,564 crosswalk rows): cardinality is only testable where an identity exists.
- The 26 candidate-cycles that gained evidence after the 2026-08-17 closure file: their missingness disposition is stale but not contradictory.

## Out-of-scope findings (recorded, not repaired)

- All 35,619 vote-evidence rows carry adjudication_authority frontier_manual_review:<rule> although the bill decisions are Luna; flagged for ideology-11 in the 2026-09-10 funnel audit.
- The 16 low-confidence admitted bill mappings and the single low-confidence mapped roll call are not diverted to any review queue, so the low-confidence signal survives into the scores (recorded under ideology-04, not repaired).
- candidate_ideology_full_coverage.csv any_ideology (704) still does not reconcile with the 1,124 candidate-cycles carrying a v3 observed profile.
- The historical ontology's mapped set is 260 rows over 256 distinct roll calls (multi-axis rows), not the 256 rows the historical audit's table implies.

## Acceptance disposition

### ideology-04

- Verdict: **sufficient evidence for acceptance with one recorded defect**.
- Basis: 2,022/2,022 mapped roll calls pass the classification motion test with 0 procedural/ambiguous; 0/2,321 mapped rows fail validate_primitive; vote-vs-sponsorship pole agreement is 1.0000 over 1,495 shared (candidate, bill, axis) cells; temporal/eligibility cross-checked under ideology-07.
- Caveat: the low-confidence-mapping review-queue requirement fails: 0 of 16 low-confidence mapping bills and 0 of 1 low-confidence mapped roll calls are in a review queue.

### ideology-05

- Verdict: **sufficient evidence for acceptance with a stated overlap-constructibility limit**.
- Basis: three primary channels are distinct; 0 duplicate evidence_ids in all four ledgers; 1,495 (candidate, bill, axis) keys appear in both legislative channels and both count by design (vote 1.0 + sponsorship 1.2); 4,730 profiles corroborated across channels.
- Caveat: bill-level overlap of Vote Smart/research rows with roll-call evidence is not constructible because those rows carry no bill identifier.

### ideology-06

- Verdict: **sufficient evidence for acceptance**.
- Basis: the declared threshold recomputes to 492 model-eligible candidate-cycles and matches the integrated artifact exactly; all 440 evidence-less cycles carry a searched-with-no-evidence disposition (0 not searched, 0 unaccounted); no position value is imputed from absence.
- Caveat: the closure file's accounting is stale for 26 cycles that gained evidence after 2026-08-17.

### ideology-07

- Verdict: **sufficient evidence for acceptance**.
- Basis: 0 action-after-cutoff and 0 session-outside-window violations across 51,800 legislative evidence rows; people_id->candidate is unique per cycle with 0 violations; 0 person_id mismatches; the 9 cross-chamber cycles are flagged by the identity layer and are pre-election service in the chamber the person actually served in.
- Caveat: identity is only testable for the 768 of 1,564 candidate-cycles with a resolved people_id.

## Defects and gaps (recorded, not repaired)

- REVIEW QUEUE (ideology-04): low-confidence admitted mappings are not queued. 16 bill-level map/multi_axis decisions carry confidence=low and 1 mapped roll call carries frontier_confidence=low; none appears in frontier_legislative_bill_adjudications_luna_review_queue.csv (1 row) or legislative_rollcall_ontology_v3_openai_review_queue.csv (10 rows).
- STALE CLOSURE ACCOUNTING (ideology-06): candidate_research_final_status.csv (2026-08-17) closes 1,098 cycles as evidence_recovered and 466 as searched_no_recoverable_evidence; the current layer has 1,124 with an observed profile and 440 without, so 26 residual cycles now carry evidence and the closure file has not been restated.
- OVERLAP CONSTRUCTIBILITY (ideology-05): Vote Smart questionnaire rows use Vote Smart question ids and research rows use source URLs, so a bill-level overlap test against roll-call evidence cannot be built from the artifacts; only the profile-level co-occurrence is verifiable.
- CHANNEL COMPLEMENTARITY (ideology-05): only 208 candidate-axis profiles carry both questionnaire and roll-call evidence, so corroboration across channels is dominated by vote+sponsorship (3,947 profiles) rather than questionnaire+vote.

## CSV evidence

Embedded in the JSON companion under each section's `csv_evidence` key.

## Verification

```powershell
& .venv/Scripts/python.exe scripts/audit_ideology_evidence_layer.py
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_ideology_evidence_layer.py -q
```

The fixture suite covers the checker functions directly: temporal violation detection
(late action and session-window breach), double-count detection at (candidate, bill, axis),
polarity agreement and answer filtering, the three-issue/two-family threshold rule, and
identity cardinality (same-cycle collision plus repeated people across cycles). The audit
recomputes the repository counts above from the current CSVs; it does not re-run any
pipeline stage, so a stale input would be reported as the observed state, not repaired.
