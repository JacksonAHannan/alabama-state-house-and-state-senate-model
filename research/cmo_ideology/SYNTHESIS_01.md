# Synthesis 01: ideology is plausible, but it is not one mechanism

## Current evidentiary status

This is an interim memo, not an article draft. The cleaned dataset contains 216 eligible candidate-cycle races. The research cohort contains the top 30 unique Democratic candidates by out-of-fold Total CMO, with robustness measures from random out-of-fold, whole-cycle holdout, and district-grouped predictions.

The evidence ledger now covers twenty-eight people, including two excluded data-error
identities and three lower-CMO comparison candidates. Twelve cases have at least
two pieces of evidence available by the relevant election. Johnny Mack Morrow,
Larry Means, Tammy Irons, Henry White, Jody Letson, Darrell Turner, and the 2018
suburban candidates now have usable multidimensional or triangulated profiles;
several other classifications remain dependent on broad roll-call scores.

## Claim 1: culturally conservative positioning is a credible mechanism in white, lower-college districts

Nine of the twenty highest Democratic candidate-cycle CMO observations are in districts classified as majority-white and lower-college. Several leading candidates fit an older Alabama Democratic pattern:

- Johnny Mack Morrow was described during the 2018 campaign as a conservative Democrat with pro-life and pro-Second Amendment positions. But he also defended public education, educator retirement, and rural public investment. His profile is culturally conservative and economically populist—not uniformly right-wing.
- Jeff McLaughlin publicly described himself as a conservative resistant to extreme partisanship. His anti-PAC record and refusal of campaign contributions may also have generated a personal reform brand independent of ideology.
- Marc Keahey sponsored legislation protecting lawful firearms from confiscation or regulation during declared emergencies.
- Alan Harper and Jerry Fielding later switched to the Republican Party, but the timing and contemporary accounts caution against treating a switch as a clean ideological measure. Reporting at the time specifically disputed whether Fielding's voting record was especially conservative.

This pattern makes ideological congruence plausible, especially on guns and abortion. It does not show that economic conservatism was the key. Public schools, teacher pay, retirement systems, rural health, and local economic development recur throughout these candidates' messages.

## Claim 2: localism and an established personal vote may be at least as important

Several high performers had unusually deep local roots:

- Richard Lindsey represented HD-39 from 1983 through 2018 and chaired education appropriations for a decade.
- Jody Letson had represented his area for fourteen years before his 2014 comeback attempt. His campaign emphasized schools, educator pay, jobs, and local businesses.
- Morrow emphasized accessibility, rural representation, and bipartisan Rural Caucus leadership.
- McLaughlin's reform identity distinguished him from both party establishments.

These characteristics can correlate with ideological moderation while operating through a different mechanism: voters may support a familiar and responsive local figure despite their national partisanship. The matched-comparison design must therefore code localism separately rather than labeling every personal vote “moderation.”

Jody Letson provides an especially useful within-candidate example. His actual Democratic margin was fairly similar in 2010 (-1.3) and 2014 (-4.5), but the same-cycle Democratic statewide baseline in the district fell from roughly -14.6 to -33.2. His raw overperformance consequently rose from +13.3 to +28.7, and his model CMO moved from about -8 to +37. The striking change was not evidence that Letson suddenly adopted a different ideology. It was evidence that his local vote held up while the broader Democratic ticket collapsed. That is consistent with an established personal brand insulating a candidate from partisan realignment.

## Claim 3: the highest production score is a counterexample--and a sensitivity warning

Anthony Daniels's 2014 observation is the highest production Democratic OOF
score. Available evidence from his later legislative and congressional record
points left of Alabama's center on Medicaid expansion, abortion, and
concealed-carry permits, but no issue evidence available by the 2014 election
has been recovered. His district is majority nonwhite, and his CMO may reflect
mobilization, local organization, candidate strength, or problems in the
same-cycle statewide baseline rather than conservative ideological positioning.

The baseline warning is measurable. The production precinct weights yield a
`-13.65` core statewide margin in HD-53; richer unambiguous precinct-link
scenarios yield `-4.38`. The resulting 9.27-point range moves raw
overperformance from 69.2 to 61.8 at the scenario mean. Daniels remains an
extreme case either way, but the precise rank and magnitude are geography
sensitive.

Refitting the entire OOF model under each audited geography scenario reveals
two other unstable headline cases. Barbara Drummond ranges from about `+12.9`
to `+29.9` CMO, and Craig Ford from `+8.1` to `+23.7`. Both remain positive, so
their qualitative role survives, but their rank does not. Because altered 2014
targets also change the fitted model, some 2018 scores move even though their
own district baselines do not: Alli Summerford ranges from `+19.0` to `+24.1`
and Felicia Stewart from `+16.7` to `+22.3`. Geography sensitivity must therefore
be propagated by refitting, not treated as a district-only error bar.

Four of the top twenty observations are in majority-nonwhite districts, including repeated high scores for Barbara Bigsby Boyd. These cases likely require a different explanatory model from white rural crossover districts. Racial polarization and differences in down-ballot versus statewide turnout can make a single pooled ideological story misleading.

The higher-education suburban cases also resist the simple theory. Alli Summerford and Felicia Stewart both have strongly positive model CMO in 2018. Their contemporary campaigns emphasized education, health care, ethics, environmental protection, and—in Stewart's case—explicit criticism of conservative culture-war priorities. These candidates did not win, and both ran behind the unusually strong 2018 statewide Democratic context on the raw measure, but they performed better than the full contextual model expected. They are useful counterexamples and a warning that CMO and raw top-ticket overperformance answer different questions.

The currently coded sample is far too small for inference. Across eight coded candidate-cycle observations representing only six substantive candidates, the descriptive Spearman relationship between the available issue-ideology mean and CMO is approximately 0.12. That number should not appear as a finding in the article; it is recorded here because it demonstrates that the present evidence does not remotely establish a monotonic “more conservative means more overperformance” relationship.

## Claim 4: model robustness must constrain candidate storytelling

David Burkette's 2018 Senate score is about +33 in random out-of-fold scoring but about -6 when the entire 2018 cycle is withheld. That is not a stable candidate estimate. More broadly, whole-cycle validation remains weak, and 2010 lacks the same demographic completeness as later cycles.

The article should therefore privilege candidates who:

1. remain positive across OOF, cycle-holdout, and district-grouped scores;
2. have verified identity and party-at-election;
3. have two or more time-appropriate ideology sources;
4. can be compared with a plausibly similar lower-CMO candidate; and
5. retain their ranking under resource-adjusted and 2014-excluded sensitivity checks.

## Working thesis

The strongest defensible thesis at this stage is:

> Alabama Democrats have historically overperformed through district-congruent differentiation from the national party brand. In white rural districts, that often included cultural conservatism, but it was bundled with economic populism, public-school advocacy, and a strong personal vote. In Black-majority districts and changing suburbs, different mechanisms appear to dominate. “Moderation” is therefore not a universal linear advantage; congruence, local credibility, and coalition-specific mobilization are better candidates for the general explanation.

## Falsification tests

The ideology hypothesis should be weakened if any of the following occur:

- Matched lower-CMO Democrats have equally conservative issue records.
- Ideology coefficients disappear after controlling for local tenure, incumbency, money, and opponent quality.
- High CMO among progressive candidates is equally common within comparable white rural districts.
- Results depend on 2014, unstable cycle-holdout scores, or source-fallback districts.
- Candidate positions postdate the scored election and cannot be corroborated contemporaneously.

## Update: systematic roll-call ideology check

Before this comparison was finalized, the research audit found that the
canonical candidate table used explicit secondary-source incumbent annotations
but did not consume the project's more complete prior-winner incumbency roster.
For example, 2010 winner Napoleon Bracy was incorrectly treated as a
non-incumbent in 2014. The roster is now overlaid during candidate-identity
construction and the CMO models and research files have been rebuilt. This
changed individual scores and rankings but not the broad conclusion below.

The first Shor--McCarty merge reinforces the qualified thesis above. Among 52
analysis-ready Democratic candidate-cycle observations through 2018, the rank
correlation between the common-space ideology score (higher is more
conservative) and corrected OOF CMO is `-0.03`. Restricting the sample to
candidates with legislative service by the election produces another near-zero
result (`0.03`). Raw top-ticket overperformance is weakly negative (`-0.15`).
These are descriptive statistics from a selected officeholder sample, not
causal estimates.

There is nevertheless a modest upper-tail pattern: the top CMO quintile has a mean
Alabama Democratic caucus conservatism percentile of about 72, compared with 64
for the rest of the matched sample. The relationship is not monotonic. The most
conservative ideology quintile has lower average CMO than the
next-most-conservative quintile, and cycle-specific correlations reverse sign:
approximately `-0.48` in 2010 and `+0.55` in 2014. Only three clean matches are
available in 2018.

The better article question is therefore: **under what electoral conditions did
a locally conservative or party-differentiated identity preserve a Democratic
personal vote?** The current results do not support a claim that each increment
of conservatism mechanically increased overperformance.

The 2014-excluded sensitivity test sharpens that warning. Across 32 clean
matched observations outside 2014, the rank correlation is `-0.35` for OOF CMO
(person-cluster bootstrap interval approximately `-0.63` to `-0.03`). The
district-grouped (`-0.38`) and resource-adjusted (`-0.34`) specifications point
the same way. Among the 27 observations with pre-election legislative service,
the estimate is `-0.34`, but its bootstrap interval crosses zero. This is not
evidence that moving left generally causes overperformance: the matched sample
is selected, 2010 supplies most observations, and only three matches exist in
2018. It does show that the apparent conservative advantage is carried by 2014
and cannot be presented as a stable cross-cycle law.

Named cases illustrate the heterogeneity. Richard Lindsey, Jeff McLaughlin,
Johnny Mack Morrow, Larry Means, and Craig Ford are near the conservative edge
of their contemporary Democratic caucuses. Anthony Daniels is around the 68th
percentile rather than at the edge, while Barbara Boyd is around the 32nd
percentile; both are among the largest CMO observations.

Repeat candidates are an especially strong check on ideological storytelling.
Their career-level ideology score is invariant while CMO can move dramatically.
Larry Means moves from roughly `-6` in 2010 to `+25` in 2014; Dexter Grimsley
moves from `+3` to `+15` and then `-4`. Ideology alone cannot explain those
within-person changes.

The first matched-pair audit reaches the same conclusion from a different
direction. Richard Lindsey exceeds John Robinson by about 36 CMO points and
Mike Curtis by about 27, even though their Shor--McCarty scores differ by only
`0.039` and `0.016`, respectively. Across the five current pairs with scores on
both sides, the higher-CMO candidate is more conservative once, more progressive
twice, and in essentially the same broad ideological band twice. See
`MATCHED_FINDINGS_01.md` and `matched_pair_evidence.csv`.

Simple tenure is not a sufficient competing explanation either. Among 45
matched observations with pre-election legislative service, rank correlation
between observed service years and OOF CMO is about `-0.05`; demeaning by cycle
and chamber gives approximately `-0.06`. The more plausible personal-vote
construct is qualitative and relational--constituency service, local networks,
occupation, and opponent quality--rather than years served alone.

Two completed candidate memos now show why the article needs multiple
mechanisms. Larry Means combines a 100 percent NRA rating and sponsorship of
Alabama's stand-your-ground law with public-school advocacy, job-retention
economic development, and an unusually durable Attalla personal vote. His CMO
moves from about `-6` in the indictment-shadowed 2010 campaign to `+29` after
acquittal and a decisive local mayoral comeback. That is a culturally
conservative profile whose electoral expression depended on reputation and
context.

Barbara Boyd points in the opposite ideological direction. Her Shor--McCarty
score places her around the 32nd conservative percentile of the 2010 Alabama
Democratic House caucus, yet she records about `+40` OOF CMO in 2010 and remains
positive in contested 2018 and 2022 races. Her long educator career, service
since 1994, and majority-Black district suggest community networks and
down-ballot coalition strength rather than conservative crossover. See
`candidate_memos/larry_means.md` and `candidate_memos/barbara_boyd.md`.

The next focal and comparison memos reinforce the same conclusion. Tammy Irons
recorded roughly `+28` OOF CMO but was near the middle of her contemporary
Democratic caucus, with the recovered issue record emphasizing public education
and ties to the education establishment. Henry White was relatively conservative
in roll-call space, yet his campaign message was public schools, local business,
jobs, and services. Craig Ford combined an explicitly conservative cultural and
party-independent identity with Medicaid expansion and public-school investment.

Two lower-CMO comparisons clarify the rival mechanisms. Jennifer Marsden ran an
economically progressive rural campaign and badly underperformed Henry White,
but White possessed decades of school-system, city-council, and legislative
networks that Marsden did not. Darrell Turner shared Larry Means's working-family
and public-education emphasis. Turner also had an extreme spending disadvantage
and faced a late economic-interest filing complaint; resource adjustment cuts
the Means--Turner CMO gap roughly in half. Neither pair isolates ideology.

## Update: temporal and blind coding audit

The initial hand-code join pooled a person's evidence across election cycles.
That could copy later positions backward into an earlier candidacy. The analysis
now keys issue codes to both person and election cycle and excludes evidence
dated after election day or explicitly marked retrospective/post-election.
Later evidence remains available for biographical interpretation but does not
enter the issue-code exhibits.

An anonymized, CMO-free recoding packet produced agreement on 22 of 23 eligible
issue decisions. The sole disagreement concerned Felicia Stewart's explicit
criticism of conservative culture-war priorities; the blind review supported a
strongly rather than mildly progressive code, and the ledger was revised. The
review packet, key, decisions, and results are retained as separate CSV files.

The packet now uses stable hash-based anonymous IDs, so adding candidates cannot
silently reassign old review decisions. After the Betterton, Burkette, and Harper
research pass, the original adjudicated decisions remain 23-for-23; the newly
eligible Harper and Burkette codes are pending a separate blind review rather
than being mislabeled as independently validated. Subsequent research added
Drummond and Randall White codes. The generated `blind_review_pending.csv` now
provides the authoritative queue rather than relying on a hand-maintained count.
After adding Linda Meigs and Kim Caudle Lewis, 12 temporally eligible ideological
decisions are pending independent review; the 23 completed decisions remain in
full agreement with the adjudicated ledger.

## Update: documented suburban candidates in 2018 and 2022

Two later-cycle cases strengthen the evidence against a universal conservative-
moderation mechanism. Linda Meigs recorded about +15.1 Total OOF CMO in 2018
while campaigning for Medicaid expansion and an education lottery. Her resource-
adjusted score falls to about +9.7, suggesting that campaign resources explain
part, but not all, of her result. Her background as a retired Huntsville teacher
provided occupational credibility, although she was a first-time candidate.

Kim Caudle Lewis recorded about +15.0 Total OOF CMO in Senate District 2 in 2022,
and the resource-adjusted score remains approximately +15.8. Contemporary
interviews document support for educational investment and protecting
reproductive choice after *Dobbs*. They also document a powerful non-ideological
profile: lifelong Madison County residence, local technology-business leadership,
and service as the first Black woman to chair the Huntsville/Madison County
Chamber of Commerce. Lewis therefore combines progressive issue positioning with
business and civic valence unusually well matched to a changing suburban seat.

## Update: James Fields and cross-racial local membership

James Fields recorded about +15.6 Total OOF CMO in House District 12 in 2010.
Although he lost by roughly eight points, the same-cycle Democratic statewide
baseline in the district was approximately -43, leaving a raw legislative gap of
about 34 points. His pre-election Shor--McCarty score placed him around the 64th
conservative percentile of the Democratic House caucus: somewhat conservative,
but not an ideological extreme. Official county minutes also show him supporting
an immediate half-cent sales tax to address a school-funding crisis.

Fields's distinctive asset was local membership. He was a Cullman County native,
Methodist minister, and longtime state employment-service worker who had already
won the overwhelmingly white district in a 2008 special election. His case does
not show racial polarization disappearing. It shows a deeply embedded local
identity partially overriding both racial and national partisan cues. After this
addition, the generated independent-review queue contains 14 eligible ideology
decisions; the count is checked by the article validator.

## Update: Cheatham, Bracy, and Varner

Rex Cheatham adds a well-documented education-labor profile. Before his +16.7
CMO run in 2014, he had taught in Morgan County schools for ten years, worked for
the Alabama Education Association, and led a gubernatorial education-reform
committee. He faced a large Republican resource advantage, and both resource-
adjusted scores remain strongly positive. His cultural positions remain unknown;
the evidence supports an education-network mechanism, not a generic ideological
label.

Napoleon Bracy and Greg Varner are now explicit unresolved cases. Bracy's 2010
ideology cannot be inferred from a Shor--McCarty record that begins after the
election. His prior Prichard City Council service and large fundraising advantage
are better-documented explanations; fundraising adjustment reduces +20.7 CMO to
about +12.9. Varner lacks usable issue evidence and raised roughly $1.14 million
to Gerald Dial's $404,000. Fundraising adjustment reduces his +15.5 CMO to about
+8.4, while Dial brought long tenure and a prior Democratic personal vote to his
new Republican affiliation. These missing-value cases are substantively useful:
the research loop does not manufacture ideological explanations where archival
evidence is absent. The independent ideology-review queue contained 15 items at
this stage.

## Update: Jerry Fielding and opponent disruption

Jerry Fielding recorded about +18.2 CMO as a Democrat in Senate District 11 in
2010, then switched parties in 2012 and described culturally conservative
positions. Those later statements cannot establish his campaign-time ideology.
The contemporaneous competing explanations are unusually strong. Fielding had
spent 26 years as a Talladega County judge, while Republican incumbent Jim
Preuitt quit the race on September 1 and the party selected Ray Robbins as a
replacement on September 7. Fielding thus combined district-wide public-service
recognition with an opponent who had only about eight weeks to campaign. This is
another case where a later party switch is weaker causal evidence than the
electoral circumstances visible before Election Day.

## Update: Betterton, Burkette, and Harper

These three cases further separate ideology from local credibility. Alan Harper
was on the conservative side of the 2010 Democratic House caucus (about the
71st percentile) and later became a Republican. Yet the later switch statement
also foregrounded his long economic-development and local-service record, and
both Harper and Democratic leader Craig Ford disputed the idea that affiliation
alone described his substantive position. He is compatible with ideological
congruence, but not a clean causal test.

David Burkette supplies almost the reverse pattern. Contemporaneous evidence
emphasizes public education and AEA support, while reporting credits his local
history as a coach, educator, and three-term city councilman and documents ADC
organizational support. Detailed reports of debt and campaign-management
conflict make superior campaign execution an implausible explanation. His case
is better evidence for community networks and down-ballot coalition loyalty
than for conservative moderation.

Andy Betterton had substantial Florence school-board and city-council tenure.
His issues page is economically progressive on public education, private-school
funding, and Medicaid expansion. The site's WordPress API records the page as
published and last modified in August 2014, resolving the provenance problem and
making its economic-ideology code temporally eligible. Betterton is therefore a
case in which a progressive economic platform and deep local credibility coexist,
not evidence that ideological conservatism was necessary for overperformance.
This newly eligible code brings the independent-review queue to 16 items.

## Update: party-switchers and the HD-24 sequence

Nathaniel Ledbetter adds a particularly revealing party-switch case. He posted
about `+22` OOF CMO as a Democrat in HD-24 in 2010, then switched parties and
won the district as a Republican in 2014. A memorandum of his 2013 switch
discussion reports that he identified as conservative on abortion and gay
rights and expected most of his former Democratic supporters to remain with
him. Because this postdates the scored campaign and comes from an interested
participant, it is corroboration rather than a pre-election code. Still, the
expectation of voter continuity across party labels is unusually direct support
for a personal-vote mechanism.

The next Democrat in HD-24, David Beddingfield, recorded roughly `+23` CMO
against Ledbetter in 2014 despite being out-raised by more than two-to-one.
An official 2008 school directory and April 2014 correspondence establish that
Beddingfield had long served as president of the Fort Payne City Board of
Education. Without his full issue platform, the sequence cannot isolate ideology.
It does show why party realignment, competing local education networks, resources,
and ideology should be analyzed jointly.

Dennis Stephens supplies a lower-CMO comparison rather than another success
story. He signed an anti-corruption pledge but faced Ritchie Whorton immediately
after Whorton defeated a Republican incumbent with a strong grassroots and
anti-Montgomery message. Stephens's ideology remains unknown, and a surviving
index to his Clarion interview now points to a dead page. His case shows that a
generic reform signal did not overcome a strong opponent and resource deficit;
it cannot show that ideological moderation was absent or ineffective.

## Update: McLaughlin's conservative-reform bundle

Jeff McLaughlin recorded about `+37.7` CMO in 2014 despite being out-raised by
roughly eight to one. Because he had served in the House before the election,
his Shor–McCarty score is temporally usable and places him near the conservative
edge of the Democratic caucus. But the campaign record does not reduce to a
single left-right label. McLaughlin emphasized education, infrastructure, TVA
protection, anti-partisanship, clean government, and refusing special-interest
money. He also brought a decade of prior district representation and deep
Guntersville professional and civic ties.

McLaughlin therefore strengthens the case that relative ideological conservatism
could help in a white district while also showing what “conservative Democrat”
conceals: public-institution commitments, reform positioning, and a durable local
identity. His new overall-valence code raises the independent blind-review queue
to 17 items.

## Update: Lindsey versus Robinson

Richard Lindsey and John Robinson form the cleanest challenge to an ideology-only
explanation. Their pre-election Shor–McCarty scores differ by just `0.039`; both
sit near the conservative end of the Alabama Democratic House caucus. Both also
received substantial AEA support, and Robinson additionally received the Alabama
Retail Association endorsement. Yet Lindsey recorded about `+40.8` CMO while
Robinson recorded only `+4.5`.

The campaigns differed much more than the candidates' broad ideology. Lindsey
had represented HD-39 for 31 years, held education-budget influence, and faced
an opponent with only about `$5,891` in observed fundraising. Robinson faced a
retired firefighter and commercial fisherman with deep local roots in a nearly
even fundraising contest. Resource adjustment narrows the CMO gap by only about
five points, leaving tenure, network strength, and opponent quality as the more
plausible residual explanations. The four newly eligible ideology decisions bring
the independent-review queue to 21 items.

## Update: Drummond versus Alexander

The production model classifies Barbara Drummond as about `22.5` CMO points
above Louise Alexander and later roll-call data place Drummond farther left.
That apparent ideological direction is not robust enough for a causal story.
Neither woman had pre-election legislative service, so both ideal points are
post-election. Drummond also raised about `$85,460` against an opponent with
roughly `$8,292`, while Alexander faced Darius Foster, who raised about `$114,147`
and received national coverage for sustained community outreach.

Geography is more damaging still. Drummond's audited CMO range is about `+12.9`
to `+29.9`; Alexander's is about `+7.4` to `+12.1`. Comparing the least favorable
Drummond estimate with the most favorable Alexander estimate leaves less than
one point. The sign barely persists, but the claimed magnitude disappears. This
pair should be presented as an example of post-election ideology, resource,
opponent, and geography confounding—not as evidence that progressivism caused
overperformance.

Randall White is a lower-confidence version of the culturally conservative
local Democrat. Contemporaneous Democratic commentary called him highly
conservative while emphasizing lifelong district residency and an
adult-education career. The source is partisan and gives no issue specifics, so
White should remain a supporting case until independently corroborated.

For the two largest 2014 Black-majority cases, new institutional evidence also
complicates a left-right story. Drummond received AEA support before the
election. Daniels combined earlier education-association leadership with a 2014
RetailPAC endorsement. The latter is better described as cross-institutional
acceptance than ideological moderation.

Vivian Davis Figures is a stronger progressive counterexample because her
evidence is contemporaneous. Her roll-call score was around the 23rd
conservative percentile of the Democratic Senate caucus, and she sponsored a
firearm safe-storage bill in the 2010 election year. Her positive CMO is better
explained through long incumbency, the Figures family network, and majority-Black
down-ballot coalition strength than through conservative positioning.

Billy Beasley falls nearer the moderately conservative side of the caucus but
was already a multi-term House member before seeking an open Senate seat. The
temporal pipeline now correctly distinguishes that pre-election other-chamber
service from genuinely post-election evidence. This adds one valid observation
to the pre-election-service sensitivity sample without materially changing its
near-zero overall relationship.

Current source coverage is 53 clean matches among 216 Democratic
candidate-cycle rows (41 people), with 45 matched rows through 2018 having pre-election
legislative service. Shor--McCarty should therefore remain a
convergent-validity check for officeholders; the candidate evidence ledger is
still essential for challengers.

## Next evidence targets

1. Recover contemporaneous campaign material for Beddingfield, Daniels,
   Drummond, Drama Breland, and Randall White, plus cultural-issue evidence for
   Betterton.
2. Research the paired lower-CMO candidates in `matched_comparisons.csv` before viewing or revising their ideological codes.
3. Add opponent-quality variables: incumbent status, prior office, scandal, campaign activity, and fundraising.
4. Separate majority-white rural, majority-Black, and higher-education suburban analyses.
5. Add the 2024 special and regular elections as descriptive external cases, not as training observations, including Marilyn Lands as an explicit possible counterexample to “move right.”

The reproducible article exhibits are generated by
`scripts/build_cmo_ideology_article_exhibits.py`; see the `article_*.csv` files
in this directory. The sensitivity table uses person-clustered bootstrap
intervals so repeat candidates are not treated as fully independent.
`cmo_geography_sensitivity.csv` separately reports full-model score ranges across
the five allocation regimes and verifies that the production scenario exactly
reproduces the published OOF scores.

## Final blind-review update

The independent review is complete for all 46 currently eligible
candidate-dimension decisions. The reviewer saw only an identity-redacted,
CMO-free queue and a written rubric. Exact agreement was 40 of 46. None of the
six disagreements reversed ideological direction; all concerned whether the
evidence warranted a mild or strong code. A fixed percentile rule and explicit
scope rules for narrow gun policy and conventional public investment governed
adjudication. Three reviewer codes were adopted and three original codes were
retained. The complete decisions, comparison results, and adjudications are
preserved in separate CSV files.

This strengthens the central conclusion without making it causal. The recovered
ideology evidence is reproducible enough to distinguish broad bundles, but the
largest CMO differences repeatedly coincide with local tenure, reputation,
opponent strength, resources, or changing baselines. Alabama Democratic
overperformance since 2010 is best described as district-congruent
differentiation rather than a uniform reward for ideological moderation.

## Remaining extensions

The most valuable extensions are additional archival recovery for candidates
whose platforms remain unknown, full-sample structured opponent-quality fields,
and 2024 special and regular elections as descriptive external cases. Any newly
recovered ideology codes should enter a fresh identity-redacted blind-review
batch before they affect article conclusions.
