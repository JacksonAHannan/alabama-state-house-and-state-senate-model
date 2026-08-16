# Vote Smart candidate ideology in the CMO analysis

Vote Smart ideology is integrated after the canonical CMO baseline is built.
This ordering is intentional: candidate ideology is an explanatory variable for
overperformance and must not be included in the baseline that defines the
overperformance outcome.

Run:

```powershell
python scripts/resolve_votesmart_pct_identities.py
python scripts/build_votesmart_pct_ideology.py
python scripts/integrate_votesmart_pct_cmo_features.py
```

Outputs:

- `votesmart_pct_identity_resolution.csv`: one disposition for every exact-cycle
  respondent, including two-party exclusions and conflicting identities;
- `votesmart_candidate_crosswalk_resolved.csv`: reviewed canonical identity
  bridge;
- `votesmart_pct_cmo_candidate_features.csv`: all 1,566 canonical candidate
  elections with PCT availability, dimension scores, and candidate-oriented CMO;
- `votesmart_pct_cmo_race_features.csv`: D and R scores, availability flags, and
  D-minus-R contrasts;
- `canonical_cmo_candidates_with_votesmart.csv` and
  `canonical_cmo_features_with_votesmart.csv`: non-destructive augmented copies
  of the canonical final-model inputs.

Higher dimension scores denote conventionally more conservative positions.
The composite is the equal-weight mean of available dimensions and is emitted
only with at least three scored dimensions. Dimension-specific values remain
preferred for substantive analyses.

Missing PCT values are never zero-filled. `dem_pct_available`,
`rep_pct_available`, and `both_pct_available` expose survey selection directly.
Only 15 races currently have surveys for both major-party candidates, so a
paired ideology-contrast analysis is a small-sample design. Candidate-level
analysis has 187 respondents but must report questionnaire selection and should
use cycle controls or cycle-stratified sensitivity checks.
