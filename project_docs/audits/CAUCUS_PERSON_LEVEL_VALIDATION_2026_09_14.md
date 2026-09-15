# Person-level Democratic caucus groupings — cluster and label validation

Checklist evidence for `ideology-09` (cluster and label revalidation) and
`ideology-10` (grouping independent of WAR outcomes).

- Run: `AL-DEM-CAUCUS-V1-75A31FF7D569EEE598FB`, generated 2026-09-15T00:43:11Z
- Builder: `scripts/build_democratic_caucuses_v1.py` (`b690cc04acd6…`)
- Ontology: `scripts/ideology_ontology_v3.py` (`2ee0d8b713ba…`)
- Outcome source: `AL-HIST-WAR-V1-0E018273EBEDEEEFAD75`
- Outputs: `data/processed/ideology/democratic_caucuses_v1/`
- Status: `descriptive_groupings_labels_pending_owner_review`

## Specification conformance

The 2026-09-11 owner decisions fix the design. Conformance as built:

| Decision | Required | Built |
|---|---|---|
| Q9 | person-level career profile | one row per `person_id`, 589 Democratic people |
| Q10 | the eight ontology issue families | 8 family features; 22 eligible primitive axes excluded and listed in the manifest |
| Q11 | ≥30% of eligible features observed | ≥3 of 8 families; median member observes 6 |
| Q12 | k chosen in 2–5 by resampling stability, labels proposed for approval | k=5 selected; labels provisional pending approval |
| Q19 | all career evidence through the latest session | no pre-election cutoff; disclosed as a career profile |
| Q20 | Democrats only | `canonical_party == "D"`, 1994–2022 |
| Q4 | uncontested candidates included | 776 candidate-cycles, 266 with no WAR, all retained |

**Corrected deviation.** The first build (2026-09-11, `AL-DEM-CAUCUS-V1-81C59DED…`)
clustered on 30 features — the 8 families *plus* 22 primitive axes — which is
option (c) of Q10, not the chosen option (a). It is superseded. The axis-augmented
solution is retained only as a sensitivity run because the exclusion is not free:
each primitive axis is either always family-mapped or never, and 13,459 of the
24,353 signed evidence rows (55%) sit on axes with no family loading, including
tax burden, gun access, public spending, education funding and voting access.

On every diagnostic the family specification the owner chose is the stronger one:

| Specification | Features | People clustered | k | Silhouette | Bootstrap ARI |
|---|---|---|---|---|---|
| Issue families (published) | 8 | 262 | 5 | 0.300 | 0.845 |
| Families + eligible axes (sensitivity) | 30 | 198 | 4 | 0.208 | 0.856 |

Agreement between the two partitions on the 198 people both cluster is
**ARI 0.262**, so the choice is material, not cosmetic.

## No outcome can inform a grouping (ideology-10)

- Clustering features are the 8 issue-family positions only. No WAR, margin,
  win, incumbency or finance column enters `fit_spec`.
- `attach_outcomes` runs after cluster assignment and is the only reader of
  `candidate_cycle_war.csv`.
- Consequence used as the test: 262 clustered people include members whose
  candidate-cycles are entirely unscored, and every clustered person keeps a
  group regardless of WAR availability.
- Unscored candidate-cycles stay missing. 266 of 776 cycles have no WAR and are
  reported as unscored, never as zero.

`scripts/tests/test_democratic_caucuses_v1.py` pins these properties.

## Cluster selection

k=5 satisfies the size floor (smallest cluster 27 people, 10.3%) and maximizes
the stability-adjusted score.

| k | Silhouette | Bootstrap ARI mean | Bootstrap ARI p10 | Smallest cluster |
|---|---|---|---|---|
| 2 | 0.221 | 0.772 | 0.343 | 57 |
| 3 | 0.249 | 0.802 | 0.356 | 53 |
| 4 | 0.286 | 0.785 | 0.508 | 27 |
| **5** | **0.300** | **0.845** | **0.736** | **27** |

Silhouette 0.300 is low separation in absolute terms: these are tendencies in a
continuous space, not discrete blocs.

## Sensitivity (ideology-09)

| Test | Statistic | Reading |
|---|---|---|
| Resampling stability | bootstrap ARI 0.845 (p10 0.736) | membership is stable under resampling |
| Evidence threshold (≥4 of 8 families, 247 people) | ARI 0.750 | robust to a stricter threshold |
| Imputation (KNN vs median) | ARI 0.439 | **sensitive**; members near boundaries move |
| Missingness structure (clusters of the observed-pattern matrix) | ARI 0.086 | groups are *not* a missingness artifact |
| Evidence channel (legislative-only profiles, 179 people) | ARI 0.191 | **sensitive**; questionnaire evidence shapes the partition |
| Era normalization (features centred within 1994–2002 / 2006–2014 / 2018–2022) | ARI 0.334 | **sensitive**; era level accounts for much of the partition |
| Issue selection (families vs families+axes) | ARI 0.262 | **sensitive**; see above |
| Repeated people | 39.7% of clustered people run in more than one cycle | handled by the person-level unit, not by clustered SEs |

The era result is the load-bearing limitation. Group era composition is uneven
(group 4 is 31/19/1 across the three eras; group 5 is 22/2/3; group 2 is
14/50/34), and Alabama's evidence channels themselves change with era —
questionnaire-era candidates in the 1990s, LegiScan roll calls from 2006. The
published groups therefore describe *position profiles conditioned on the
evidence a person's era generated*, and must be presented as such.

Every person's era-normalized assignment is published alongside the primary one
in `person_profiles.csv` / `person_membership.csv`
(`era_normalized_cluster_rank`) so a reader can inspect the disagreement
directly rather than trusting an ARI.

## Descriptive association with WAR

Attached after clustering; descriptive only, never causal, and never a
candidate-quality claim.

| Group | People | Cycles scored | Unscored share | Mean cycle WAR | SE | Median career WAR |
|---|---|---|---|---|---|---|
| 1 | 56 | 46 | 0.29 | 4.10 | 2.02 | 0.29 |
| 2 | 98 | 91 | 0.54 | 25.57 | 2.20 | 31.79 |
| 3 | 30 | 14 | 0.55 | 18.77 | 5.11 | 11.32 |
| 4 | 51 | 70 | 0.17 | 21.80 | 2.79 | 27.90 |
| 5 | 27 | 28 | 0.33 | 30.97 | 3.71 | 43.14 |

The ordering survives the era-normalized partition (group means 5.9 / 22.8 /
29.8 / 26.0 / 15.1), so the qualitative finding — the most liberal profile shows
the lowest overperformance against the fixed 2018–24 reference, and culturally
conservative profiles the highest — does not depend on the partition choice.
Unscored share differs sharply by group (0.17–0.55), so any group comparison
must show it.

## Required page disclosures

1. Groups are descriptive statistical tendencies, **not** formal caucus
   membership (the Alabama Legislative Black Caucus is a real organization; none
   of these groups is it).
2. Silhouette 0.300 — low separation; boundaries are soft.
3. Imputation, evidence-channel and era-normalization sensitivity, with the ARIs.
4. Career profile, not a pre-election snapshot: a member's later roll calls help
   place the group used to read an earlier race.
5. Coverage funnel: 589 people → 431 with any ontology evidence → 262 clustered;
   327 unclustered are listed with a reason, not dropped.
6. Per-group unscored share, and that unscored means no contested general
   election, not zero WAR.

## Open owner decisions

1. **Labels.** Five provisional labels await approval; proposals and their
   evidence are in this run's `group_profiles.csv` and
   `group_feature_coverage.csv`. Approved labels belong in
   `data/manual/ideology/democratic_caucus_labels.csv`
   (`cluster_rank,solution_k,label,description`), after which the builder drops
   the `labels_pending_owner_review` status.
2. **Primary partition.** Raw career profiles (published) or the era-normalized
   partition. Both are in the outputs; the raw one is published today.

## Commands

```powershell
.venv/Scripts/python.exe scripts/build_democratic_caucuses_v1.py
.venv/Scripts/python.exe -m pytest -p no:cacheprovider scripts/tests/test_democratic_caucuses_v1.py -q
```

Result: builder wrote 12 tables plus manifest; 10 tests passed.
