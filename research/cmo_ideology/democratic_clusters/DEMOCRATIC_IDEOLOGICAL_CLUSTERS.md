# Empirical ideological groupings in Alabama legislative caucuses

Clusters are fit separately by party from absolute, temporally eligible issue positions. CMO, election results, incumbency, fundraising, demographics, district partisanship, and era are excluded from clustering and attached only afterward.

## Democratic solution

Selected **2 clusters** among **117 candidate-cycles**, using **17 two-sided issue dimensions**. Silhouette is **0.212**; mean bootstrap ARI is **0.829**; KNN-versus-median-imputation ARI is **0.740**; absolute-versus-within-era ARI is **0.524**; position-versus-missingness ARI is **-0.014**.

- **Progressive-modern Democrats:** 41 candidate-cycles and 41 people.
- **Traditionalist-populist Democrats:** 76 candidate-cycles and 73 people.

### CMO attached after clustering

- **Progressive-modern Democrats:** mean -7.45, median -6.45, n=41.
- **Traditionalist-populist Democrats:** mean +2.70, median +0.48, n=76.

## Republican solution

Selected **3 clusters** among **164 candidate-cycles**, using **13 two-sided issue dimensions**. Silhouette is **0.222**; mean bootstrap ARI is **0.866**; KNN-versus-median-imputation ARI is **0.239**; absolute-versus-within-era ARI is **0.198**; position-versus-missingness ARI is **0.220**.

- **Business conservatives:** 57 candidate-cycles and 51 people.
- **Social and institutional conservatives:** 59 candidate-cycles and 59 people.
- **Moderate pre-realignment Republicans:** 48 candidate-cycles and 48 people.

### CMO attached after clustering

- **Business conservatives:** mean -1.14, median +0.82, n=57.
- **Social and institutional conservatives:** mean -1.92, median +1.04, n=59.
- **Moderate pre-realignment Republicans:** mean -5.79, median -4.61, n=48.

**Robustness warning:** this discrete solution changes substantially under alternate imputation or within-era normalization. Treat the labels as a description of historical tendencies, not stable caucus membership.

## Interpretation limits

- Low silhouettes indicate a continuum rather than formal caucuses.
- Issue evidence is more common for officeholders and is not missing at random.
- Candidate-cycles repeat people; person persistence and era composition are separate outputs.
- Performance differences are descriptive; electoral outcomes never determine assignment.
