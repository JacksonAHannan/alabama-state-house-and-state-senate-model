# Matched findings 01: ideology is neither necessary nor sufficient

## Purpose

This memo tests the ideology hypothesis against lower-CMO Democrats selected by
the reproducible matching routine. Matches share cycle, chamber, incumbency
status, and approximate district expectation and demographics. They are
diagnostic comparisons, not causal twins.

The model was refit before this memo after the research audit found that the
canonical candidate table was not consuming the project's prior-winner
incumbency roster. All CMO values below use the corrected build.

## Five pairs with ideology scores on both sides

Only five current matched pairs have clean Shor--McCarty scores for both
candidates. Their directions are mixed:

| Higher-CMO candidate | Comparison | CMO gap | NP-score gap | Reading |
|---|---:|---:|---:|---|
| Anthony Daniels | Barbara Drummond | +26.1 | +0.250 | higher-CMO candidate more conservative |
| Richard Lindsey | John Robinson | +35.9 | +0.039 | nearly identical broad ideology |
| Barbara Boyd | Alan Harper | +16.2 | -0.399 | higher-CMO candidate more progressive |
| Barbara Drummond | Louise Alexander | +21.8 | -0.131 | higher-CMO candidate more progressive |
| Richard Lindsey | Mike Curtis | +26.7 | +0.016 | nearly identical broad ideology |

Positive NP-score differences mean the focal candidate is more conservative.
The table alone rejects a universal directional account: one comparison points
right, two point left, and two show large CMO gaps with almost no ideological
gap.

## Lindsey versus Robinson: opponent and personal-vote mechanisms

Richard Lindsey and John Robinson are the cleanest falsification pair. Both were
long-serving rural Democratic incumbents in 2014. Lindsey had represented his
district since 1983 and had chaired education appropriations; Robinson had held
HD-23 since 1994. Their NP-scores are nearly identical (`-0.130` and `-0.169`),
but Lindsey's corrected OOF CMO exceeds Robinson's by about 36 points.

Money explains part, but not most, of that gap. The state-file spending feature
shows Lindsey with a very large Democratic spending advantage while Robinson
was outspent. Moving from Total CMO to resource-adjusted CMO reduces the pair's
gap from about 36.3 to 31.4 points. The comparison therefore flags finance as a
meaningful competing explanation without making the broad ideology difference
any more informative.

The opponent environment differed materially. Lindsey faced Heath Jones, a
grassroots challenger whose public message stressed term limits, small
government, opposition to Medicaid expansion, and fiscal and social
conservatism. Robinson faced Tommy Hanes, a retired firefighter and commercial
fisherman with deep Jackson County roots. Contemporary Republican material
presented Hanes as pro-life, pro-family, strongly pro-Second Amendment, and
focused directly on Robinson's relationship with the Alabama Education
Association.

Sources:

- [Heath Jones campaign profile, Alabama Political Reporter](https://www.alreporter.com/2014/09/24/heath-jones-running-as-republican-in-house-district-39/)
- [Tommy Hanes 2014 candidate profile, Alabama Republican Party](https://algop.org/candidate-spotlight-week-september-22-2014/)
- [Richard Lindsey retirement and committee history, Alabama Political Reporter](https://www.alreporter.com/2017/11/14/longtime-democratic-state-rep-richard-lindsey-retire-house/)
- [Certified 2014 results, Alabama Secretary of State](https://www.sos.alabama.gov/sites/default/files/voter-pdfs/2014/2014GeneralResults-WithWriteIn.pdf)

This pair does not prove that opponent quality caused the CMO gap. It does show
that a broad ideology score cannot explain it, even after matching on observable
district context and incumbency.

## Daniels versus Drummond: a possible ideological contrast with limits

Anthony Daniels and Barbara Drummond were both first-time Democratic winners in
majority-Black districts in 2014. Daniels is moderately to the right of Drummond
in the Shor--McCarty space (`-0.360` versus `-0.610`) and has about 26 more CMO
points. This is consistent with the ideology hypothesis, but it is not a clean
test:

- both ideology scores are derived from service after the election;
- the districts have distinct local political organizations and turnout
  histories;
- Republican opponent quality is not yet coded;
- later roll-call evidence places both within the Democratic caucus rather than
  establishing that voters perceived Daniels as a conservative in 2014.

The appropriate claim is that this pair is **consistent with**, not proof of, a
moderation advantage.

## Tenure does not rescue a simple personal-vote model

Among 44 matched candidate-cycle observations with pre-election legislative
service, the rank correlation between observed service years and OOF CMO is
approximately `-0.05`. After demeaning by cycle and chamber, the ordinary
correlation is approximately `-0.06`. Long tenure matters in named cases, but
tenure length alone is not a general explanation. Constituency service, local
networks, occupation, opponent quality, and the ability to separate from the
national party require more specific coding.

## Working interpretation

The matched evidence currently supports a conditional account:

1. Cultural conservatism sometimes helped preserve a rural Democratic vote,
   especially during the 2014 partisan collapse.
2. It was not sufficient: similarly conservative incumbents had very different
   outcomes.
3. It was not necessary: several high-CMO Black-majority candidates were more
   progressive than their comparisons.
4. Candidate-specific local brands and opponent recruitment are plausible
   omitted mechanisms and should be central in the next research loop.

Machine-readable pair details are in `matched_pair_evidence.csv`.
