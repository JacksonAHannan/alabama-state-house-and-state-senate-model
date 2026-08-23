# Candidate-legislator identity and ideology coverage repair

## Result

The repair separates leakage-safe pre-election ideology from a career-through-2026
legislator profile. Candidate election facts and the canonical warehouse were read
only.

- 761 of 1,564 candidate-cycle rows link to a LegiScan identity.
- All 130 SOS ballot-code names in 2022 decode to a person name.
- Pre-election roll-call scores now cover 523 candidate-cycle rows, including 24
  in 1998, 53 in 2002, and 50 in 2006 that the LegiScan-only join could not see.
- The career mart contains 340 chamber-member records through 2026.
- All 264 chamber-members serving in at least four archived sessions have recorded
  votes, ideologically classified votes, and a career behavioral score.

## Method

Identity evidence is applied in this order: reviewed manual aliases, accepted
Ballotpedia election crosswalks, normalized/compact names, initial-surname plus
district, and unique incumbent district-party service. SOS GSL codes additionally
use their encoded surname prefix plus chamber, district, and party. Ambiguous or
duplicate assignments are quarantined.

Historical journal member IDs are joined only within the election's pre-election
window using decoded name, party, and parsed district. The separate career mart
uses LegiScan person IDs and is never an election-model input.

## Validation

`python -m pytest scripts/tests/test_candidate_legislator_identity_repair.py -q`
passes 6 tests. `python scripts/validate_agent_workflow.py` passes. Independent
release validation remains required before downstream analysis or publication.

## Caveats

Unlinked candidate rows are mostly challengers without legislative service, not
missing legislators. The 1994 roll-call archive is unavailable to this pipeline,
so 1994 candidates retain explicit unavailable status rather than fabricated scores.
