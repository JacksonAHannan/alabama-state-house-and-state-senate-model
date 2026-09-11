# Historical final-vote ideology coverage repair

Date: 2026-08-24  
Task: `IDEOLOGY-HISTORICAL-FINAL-VOTES-003`

## Result

The classification and ontology ledgers now cover the exact 60,704-roll-call
universe in the normalized 1998-2026 research warehouse. Previously the
classification table contained 42,391 rows and omitted 18,337 journal votes.

Every omitted historical vote now receives an explicit terminal disposition.
Bill-level synopsis and issue direction are admitted only for
`final_passage` and `conference_report` votes. Amendments, substitutes,
budget-isolation resolutions, table motions, and other ambiguous motions fail
closed.

## Coverage change

| Metric | Before | After |
|---|---:|---:|
| Classified/dispositioned roll calls | 42,391 | 60,704 |
| Historical roll calls in classification ledger | 11,134 | 29,471 |
| Ontology-v3 mapped historical roll calls | approximately 187 | 256 |
| Ontology-v3 mapped roll calls, all sources | 918 | 987 |

The historical mapped set now contains 244 final-passage records and 16
conference-report records representing 256 unique roll calls. Some roll calls
map to more than one primitive axis.

## Propagation rule

Historical measure identity is keyed by corrected
`session_year + bill_type + bill_number`. All available journal-context and
representative synopsis candidates are compared. A formal bill synopsis
beginning with language such as “To” or “Relating” outranks an amendment
fragment, even if the fragment is longer. One selected bill-level synopsis is
then used consistently for that measure in both chambers.

Among substantive historical votes:

- 6,859 final-passage or conference-report roll calls are eligible to have
  bill direction evaluated;
- 6,808 have recovered measure text;
- no measure has inconsistent synopsis text across chambers in the final
  classification output;
- 52 mapped measure groups now reach recorded votes in both chambers.

The remaining 22,612 historical votes that are procedural, amendatory, or
otherwise ambiguous receive
`excluded_procedural_or_ambiguous_motion` in the frontier ontology. No
amendment or substitute is mapped to a final-bill pole.

## Additional correction

The raw LegiScan classification input contains 24 records that failed the
normalized warehouse's reported-total eligibility gate. Those records are now
excluded from the classification universe so the warehouse, classification,
and ontology ID sets are identical.

## Validation

- Comprehensive classification, historical ontology, and frontier ontology
  tests: 19 passed.
- `comprehensive_rollcall_classifications.csv` contains 60,704 unique IDs.
- `frontier_rollcall_ontology_v3.csv` covers the same ID set.
- Mapped historical motions are limited to final passage and conference
  reports.
- Mapped `(rollcall, primitive_axis)` pairs have one non-conflicting policy
  pole.

Candidate legislative evidence and downstream ideology analyses still need to
be rebuilt from the expanded ontology and repaired identity layer.

