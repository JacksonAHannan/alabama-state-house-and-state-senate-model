# Initial findings and data audit

## Finding 1: the two largest nominal Democratic CMOs are invalid

The initial candidate output labeled “Holmes” in 2014 HD-31 and “Baker” in 2014 HD-66 as Democrats, producing CMO scores of roughly +128 and +75. Contemporary and official records identify Mike Holmes and Alan Baker as Republicans. HD-31 was uncontested by a Democrat. The candidate-identity fallback has now been repaired: secondary county fragments whose names clearly match an SOS nominee cannot create a phantom opponent under the other party label. The rebuilt model contains 216 rather than 218 eligible races and neither false Democrat appears in the candidate file.

This is consequential: the most visually dramatic initial “Democratic overperformance” cases were data artifacts, not evidence of ideological moderation. It also demonstrates why identity validation must precede qualitative interpretation.

## Finding 2: authentic high performers include distinct candidate types

After the repair, the provisional queue includes:

- Long-serving rural or small-town Democratic incumbents such as Barbara Bigsby Boyd and Richard Lindsey.
- Democrats associated with culturally conservative or gun-rights positioning, including Johnny Mack Morrow.
- Democrats who subsequently joined the Republican Party, including Jerry Fielding and Alan Harper.
- Black Democratic leaders in strongly Democratic districts, including Anthony Daniels and Napoleon Bracy, whose overperformance may reflect turnout, local organization, or baseline construction rather than ideological conservatism.
- Non-incumbent challengers who lost but materially exceeded the model expectation, a useful comparison group because “winning” and “overperforming” are not synonymous.

The leading clean OOF observations are now Anthony Daniels (2014), Richard Lindsey (2014), Jody Letson (2014), Barbara Bigsby Boyd (2010), Jeff McLaughlin (2014), David Burkette (2018), and Johnny Mack Morrow (2018). Burkette is a sensitivity warning: his random OOF score is strongly positive while his whole-cycle holdout score is negative. He should not anchor a substantive thesis without explaining that instability.

The heterogeneity argues against a simple “the most conservative Democrats do best” story. A better initial hypothesis is that **district-congruent differentiation from the national party brand—sometimes ideological, sometimes personal or organizational—contributes to overperformance**, with potentially different mechanisms in white-majority rural districts and Black-majority districts.

## Immediate research priorities

1. Repair and rerun party/contest eligibility for the 2014 extremes.
2. Complete identity and party-at-election validation for the top 30 unique candidates.
3. Begin paired profiles with Johnny Mack Morrow, Richard Lindsey, Barbara Bigsby Boyd, Jerry Fielding, Marc Keahey, Tammy Irons, Anthony Daniels, and Napoleon Bracy.
4. Acquire Alabama legislative roll calls and archived interest-group scorecards for the relevant sessions.
5. Construct comparison candidates matched on cycle, chamber, expected margin, incumbency, and district racial composition.

## Seed sources

- Alabama Secretary of State, certified 2014 general results: https://www.sos.alabama.gov/sites/default/files/voter-pdfs/2014/2014GeneralResults-WithWriteIn.pdf
- Alabama Secretary of State, 2014 election information: https://www.sos.alabama.gov/alabama-votes/voter/election-information/2014
- Alabama Political Reporter on Mike Holmes's 2014 Republican special election and lack of a Democratic opponent: https://www.alreporter.com/2014/02/05/mike-holmes-wins-in-house-district-31/
- Federal redistricting litigation recording Jerry Fielding's post-election party switch: https://www.govinfo.gov/content/pkg/USCOURTS-almd-2_12-cv-00691/pdf/USCOURTS-almd-2_12-cv-00691-5.pdf
- Johnny Mack Morrow issue statement on gun ownership and the Second Amendment: https://gadsdenmessenger.com/where-i-stand/
