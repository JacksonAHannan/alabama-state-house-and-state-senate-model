# Candidate identity and career ideology repair validation

**Final verdict: PASS.**

Validated against the rebuilt outputs dated August 22, 2026.

## Reproduced gates

```powershell
python -m pytest scripts/tests/test_candidate_legislator_identity_repair.py scripts/tests/test_full_candidate_legislative_ideology.py scripts/tests/test_legislative_ideology.py scripts/tests/test_candidate_ideology_storage_invariants.py tests/test_absolute_ideology_rebuild.py scripts/tests/test_democratic_ideological_clusters.py scripts/tests/test_legislator_ideology_page.py scripts/tests/test_ideology_performance_page.py scripts/tests/test_caucus_analysis_page.py scripts/tests/test_site_brand.py -q
# 49 passed

python scripts/validate_agent_workflow.py
# Agent workflow validation passed.
```

## Independent findings

- The crosswalk contains 1,564 unique candidate-cycle rows, including 761 resolved identity links.
- The pre-election mart contains 523 available legislative scores. Available scores have zero duplicate `(year, chamber, member_source_id)` keys and zero `window_end > year` violations.
- The 2022 GSL decoding, chamber/cycle assignment, career cutoff labeling, and long-service coverage assertions pass in the focused suite.
- Pure district fallback (`incumbent_district_parsed`) is used 12 times, exclusively for candidates identified as incumbents. No ordinary opposing-party challenger is mapped by district-only fallback.
- The 34 party-transition matches require name evidence, with district constraints where applicable; no transition is inferred from district alone. Active-year party mismatches are named Alabama incumbents consistent with documented party changes, rather than opposing-party challengers.
- Ambiguous identities remain unscored.

## Jack Williams resolution

The prior blocker is corrected:

```text
AL-2014-house-47-R-JACK-WILLIAMS   LEGISCAN-3418   resolved
AL-2014-house-102-R-JACK-WILLIAMS  [unlinked]       ambiguous
```

HD-47 has 44 pre- or same-cycle legislative evidence rows. HD-102 has none. This retains the uniquely district-consistent legislator while quarantining the ambiguous same-name candidate.

No blocking identity, party-transition, duplication, or temporal-leakage defect remains.

