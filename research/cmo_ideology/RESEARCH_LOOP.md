# Alabama Democratic CMO and ideology research loop

## Research question

Which candidate attributes have historically helped Alabama Democrats outperform a district-specific electoral expectation since 2010, and how much of that pattern is plausibly associated with ideological congruence rather than incumbency, local roots, opponent quality, money, or data error?

The project does **not** begin by assuming that a single left–right score explains CMO. “Ideological valence” is coded by issue and relative to the candidate's cycle and constituency.

## Repeatable loop

1. Rebuild `candidate_cohort.csv` from the published out-of-fold Total CMO file.
2. Validate candidate identity, party at the time of the election, contest status, vote totals, and district. Exclude invalid records before ideological research.
3. Collect time-specific evidence, prioritizing official candidate materials, roll-call votes, bill sponsorships, archived legislative biographies, party certifications, and contemporary interviews.
4. Code each dimension independently; record both evidence and uncertainty. Never infer ideology solely from party, race, geography, religion, or a later party switch.
5. Record competing explanations: incumbency, prior office, local family/name recognition, occupation, endorsements, fundraising, opponent weakness/scandal, contest salience, and district demographic or partisan change.
6. Pair each high-CMO Democrat with comparisons from the same cycle and chamber, preferably districts with similar expected margins and demographics but lower CMO.
7. Analyze candidate-cycle observations with clustered candidate uncertainty and sensitivity exclusions for 2014, source fallbacks, invalid party labels, and extreme scores.
8. Write a candidate memo only after two independent evidence items, including at least one primary or contemporaneous source where available.
9. Revisit codes after blind review of the evidence without displaying the candidate's CMO.
10. Update the synthesis: supported findings, counterexamples, unresolved cases, and the next most valuable evidence search.

## Coding rubric

Most dimensions use `-2, -1, 0, +1, +2`, where negative is more progressive, zero is mixed/unclear, and positive is more conservative **relative to Alabama Democrats in that election era**.

- `economic_ideology`: taxes, spending, regulation, Medicaid, education finance.
- `social_ideology`: broad cultural positioning, coded separately from named issues.
- `guns_position`: gun-rights to gun-regulation orientation.
- `abortion_position`: anti-abortion to abortion-rights orientation.
- `labor_position`: anti-union/right-to-work to organized-labor alignment.
- `party_independence`: strength of public differentiation from national/state party brands, `0–2`.
- `localism_personal_vote`: evidence for constituency service, long local tenure, family/network strength, or a non-ideological personal vote, `0–2`.
- `overall_ideological_valence`: signed synthesis only after issue codes; never substitute it for the components.
- `confidence`: low, medium, or high based on evidence quality and temporal fit.

Use `NA` when an issue is genuinely unobserved. “No evidence found” is not a centrist score.

## Evidence hierarchy

1. Official election records, roll calls, legislation, archived campaign pages, direct interviews.
2. Contemporary local reporting and established statewide/national reporting.
3. Interest-group scorecards and endorsements, interpreted according to what they actually measure.
4. Biographical aggregators and encyclopedic sources for discovery and cross-checking.
5. Social posts, retrospective commentary, and unsourced assertions only as leads.

Every claim in the eventual article should link to its source. Exact quotations should be saved sparingly with publication date and context.

## Tests planned

- Descriptive: CMO distributions by issue code, party independence, and localism.
- Matched comparisons: high- and low-CMO Democrats in similar expected districts and cycles.
- Within-candidate change for repeat candidates.
- Multivariable exploratory models controlling for incumbency, district expectation, chamber, cycle, finance, race/education composition, and source quality.
- Sensitivity: exclude 2014; exclude invalid/uncertain identities; use cycle-holdout CMO; use resource-adjusted CMO; winsorize extremes; analyze white-majority and Black-majority districts separately.

## Systematic ideology validation

The hand-coded issue profile is checked against Shor--McCarty NPAT common-space
scores for candidates who served in a state legislature. Run:

```powershell
python scripts/download_shor_mccarty_ideology.py
python scripts/analyze_canonical_baselines.py
python scripts/build_cmo_geography_sensitivity.py
python scripts/build_cmo_ideology_research_cohort.py
python scripts/build_cmo_ideology_legislator_matches.py
python scripts/build_cmo_ideology_legislator_universe.py
python scripts/build_cmo_ideology_matched_pair_evidence.py
python scripts/analyze_cmo_ideology_research.py
python scripts/build_cmo_ideology_article_exhibits.py
```

The source is the July 2020 Harvard Dataverse release (1993--2018), DOI
`10.7910/DVN/GZJOT3`. The raw file is fingerprinted in
`data/raw/ideology/shor_mccarty_manifest.json`. Only normalized-exact or explicit
alias matches enter analysis; fuzzy results remain in a review queue.

These scores are descriptive validation, not a universal candidate feature:

- they exist only for people who served;
- a legislator has a career-level score, so it can incorporate votes cast after
  the election being explained;
- party switchers may have party-specific scores and require explicit handling;
- broad latent roll-call ideology cannot identify the issue that created appeal.

Report both the full matched sample and the subset with legislative service
before the election. Never impute a score to unmatched challengers.

## Current loop status

- The evidence ledger now covers 38 researched candidate-cycle cases, including
  later suburban cases Linda Meigs and Kim Caudle Lewis.
- The full Shor--McCarty universe contains 53 clean candidate-cycle matches.
- The overall ideology--CMO relationship is approximately zero. Excluding 2014
  reverses its sign; this result is retained as a sensitivity check, not treated
  as a causal estimate.
- Reproducible article tables are written as `article_*.csv`. All 46 eligible
  candidate-dimension codes have completed identity-redacted independent review;
  `blind_review_pending.csv` is empty. Exact agreement was 40/46, and the six
  intensity-only disagreements are resolved in `blind_review_adjudication.csv`.
  The next
  archival pass should prioritize lower-ranked gaps such as Jerry Fielding and
  candidates in the matched-comparison set. Napoleon Bracy and Greg Varner now
  have explicit unresolved-case memos rather than inferred ideology; Rex Cheatham
  has strong education-labor evidence but unresolved cultural-issue positions.
- Ambiguous live pages and unsuccessful archival searches are logged in
  `source_provenance_audit.csv`, including the metadata check that established
  Betterton's issues page as contemporaneous and the unsuccessful 2014 Daniels
  platform search. This prevents later passes from silently treating a current
  footer as the source date or repeating an undocumented negative search.
- The production geography is included in the baseline uncertainty envelope.
  `cmo_geography_sensitivity.csv` refits OOF CMO under every allocation regime;
  candidate interpretation should use its low/high range, not merely the
  production point estimate.

## Publication guardrails

- Association is not causation: candidates choose positions strategically, and viable candidates are selected into contested races.
- “Moderate” may mean culturally conservative, economically populist, locally rooted, bipartisan, or simply less tied to the national brand. These are different mechanisms.
- Alabama's racially polarized electorate requires explicit subgroup and district-composition analysis; statewide averages can conceal distinct electoral coalitions.
- Party switching can be evidence of ideological fit, strategic adaptation, or institutional pressure. Code the timing and stated reason rather than treating every switch as identical.
