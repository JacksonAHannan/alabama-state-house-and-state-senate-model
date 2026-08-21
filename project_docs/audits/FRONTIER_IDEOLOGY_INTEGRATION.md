# Frontier legislative ideology integration

Status date: 2026-08-18

## Archive coverage

The frontier archive ledger gives every one of the 28,833 LegiScan bills a
terminal, auditable disposition. All 9,116 bills linked to an individual roll
call have direct bill-specific frontier adjudications. The other 19,717 are
explicitly non-scoring for candidate voting ideology because no individual
vote is observed. That disposition does not assert that their policies are
ideologically neutral; their synopses, text inventories, hashes, and provenance
remain available for later sponsorship, amendment, and committee research.

- All 42,391 comprehensive roll calls have a terminal frontier output.
- All 11,134 recovered historical journal roll calls have a separate
  recovered-synopsis adjudication; 187 support a high-precision policy pole.
- 918 roll calls support at least one canonical frontier policy pole: 731 from
  LegiScan-linked records and 187 from historical journals.
- Procedural and motion-ambiguous votes never inherit a parent bill's pole.
- Local, symbolic, mixed, untranslatable, and insufficient-text records retain
  explicit non-scoring dispositions.
- Two roll-call bills remain explicit `insufficient_text` cases after available
  full text was inspected. No direction was invented for either.

## Downstream authority

The candidate legislative evidence layer reads the frontier roll-call ledger,
not inherited small-model directions. Every legislative evidence record carries
frontier adjudication authority. The resulting all-source layer contains 21,642
evidence records, 8,577 candidate-issue profiles, and 2,986 family profiles.
Of 1,564 canonical candidate-cycle rows, 1,106 have ontology-v3 evidence.

The issue, headline, durability, and ideological-bundle analyses are rebuilt
from this adjudicated candidate ledger. Current estimates should be read from
their generated CSVs rather than copied into this coverage audit.

## Interpretation

Candidate vote evidence records positions revealed by recorded votes. It does
not measure the ideological content of bills on which no individual vote was
recorded, nor does it infer how a legislator would have voted. Sponsorship,
amendment direction, and committee-only activity remain separate future
evidence types and must not be silently mixed into roll-call scores.

## Reproduction

```powershell
python scripts/run_frontier_ideology_pipeline.py
```

The machine-readable gates are written to
`project_docs/audits/FRONTIER_IDEOLOGY_VALIDATION.csv`.
