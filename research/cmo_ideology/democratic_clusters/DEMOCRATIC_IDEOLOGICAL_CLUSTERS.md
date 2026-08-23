# Empirical ideological groupings in Alabama legislative caucuses

Clusters are fit separately by party from absolute, temporally eligible issue positions. CMO, election results, incumbency, fundraising, demographics, district partisanship, and era are excluded from clustering and attached only afterward.

## Democratic solution

Selected **2 clusters** among **115 candidate-cycles**, using **17 two-sided issue dimensions**. Silhouette is **0.218**; mean bootstrap ARI is **0.906**; KNN-versus-median-imputation ARI is **0.616**; absolute-versus-within-era ARI is **0.398**; position-versus-missingness ARI is **-0.014**.

- **Progressive-modern Democrats:** 39 candidate-cycles and 39 people.
- **Traditionalist-populist Democrats:** 76 candidate-cycles and 73 people.

### CMO attached after clustering

- **Progressive-modern Democrats:** mean -7.29, median -6.45, n=39.
- **Traditionalist-populist Democrats:** mean +1.30, median -0.60, n=76.

## Republican solution

Selected **3 clusters** among **159 candidate-cycles**, using **14 two-sided issue dimensions**. Silhouette is **0.201**; mean bootstrap ARI is **0.824**; KNN-versus-median-imputation ARI is **0.080**; absolute-versus-within-era ARI is **0.283**; position-versus-missingness ARI is **0.128**.

- **Business conservatives:** 61 candidate-cycles and 55 people.
- **Social and institutional conservatives:** 68 candidate-cycles and 67 people.
- **Moderate pre-realignment Republicans:** 30 candidate-cycles and 30 people.

### CMO attached after clustering

- **Business conservatives:** mean +1.03, median +2.53, n=61.
- **Social and institutional conservatives:** mean -1.56, median +1.06, n=68.
- **Moderate pre-realignment Republicans:** mean -4.40, median -3.91, n=30.

**Robustness warning:** this discrete solution changes substantially under alternate imputation or within-era normalization. Treat the labels as a description of historical tendencies, not stable caucus membership.

## Interpretation limits

- Low silhouettes indicate a continuum rather than formal caucuses.
- Issue evidence is more common for officeholders and is not missing at random.
- Candidate-cycles repeat people; person persistence and era composition are separate outputs.
- Performance differences are descriptive; electoral outcomes never determine assignment.
