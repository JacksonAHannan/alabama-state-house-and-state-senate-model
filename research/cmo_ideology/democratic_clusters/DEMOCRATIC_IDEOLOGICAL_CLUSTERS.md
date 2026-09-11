# Empirical ideological groupings in Alabama legislative caucuses

Clusters are fit separately by party from absolute, temporally eligible issue positions. CMO, election results, incumbency, fundraising, demographics, district partisanship, and era are excluded from clustering and attached only afterward.

## Democratic solution

Selected **3 clusters** among **131 candidate-cycles**, using **18 two-sided issue dimensions**. Silhouette is **0.235**; mean bootstrap ARI is **0.838**; KNN-versus-median-imputation ARI is **0.352**; absolute-versus-within-era ARI is **0.642**; position-versus-missingness ARI is **0.283**.

- **Traditionalist-populist Democrats:** 33 candidate-cycles and 33 people.
- **Bridge-coalition Democrats:** 59 candidate-cycles and 58 people.
- **Progressive-modern Democrats:** 39 candidate-cycles and 39 people.

### CMO attached after clustering

- **Traditionalist-populist Democrats:** mean +0.49, median -2.18, n=33.
- **Bridge-coalition Democrats:** mean +3.09, median +2.20, n=59.
- **Progressive-modern Democrats:** mean -7.36, median -6.75, n=39.

**Robustness warning:** this discrete solution changes substantially under alternate imputation or within-era normalization. Treat the labels as a description of historical tendencies, not stable caucus membership.

## Republican solution

Selected **3 clusters** among **180 candidate-cycles**, using **15 two-sided issue dimensions**. Silhouette is **0.181**; mean bootstrap ARI is **0.674**; KNN-versus-median-imputation ARI is **-0.008**; absolute-versus-within-era ARI is **0.392**; position-versus-missingness ARI is **0.139**.

- **Social and institutional conservatives:** 88 candidate-cycles and 87 people.
- **Moderate pre-realignment Republicans:** 34 candidate-cycles and 34 people.
- **Business conservatives:** 58 candidate-cycles and 54 people.

### CMO attached after clustering

- **Social and institutional conservatives:** mean +0.03, median +1.41, n=88.
- **Moderate pre-realignment Republicans:** mean -7.37, median -4.61, n=34.
- **Business conservatives:** mean +1.17, median +2.88, n=58.

**Robustness warning:** this discrete solution changes substantially under alternate imputation or within-era normalization. Treat the labels as a description of historical tendencies, not stable caucus membership.

## Interpretation limits

- Low silhouettes indicate a continuum rather than formal caucuses.
- Issue evidence is more common for officeholders and is not missing at random.
- Candidate-cycles repeat people; person persistence and era composition are separate outputs.
- Performance differences are descriptive; electoral outcomes never determine assignment.
