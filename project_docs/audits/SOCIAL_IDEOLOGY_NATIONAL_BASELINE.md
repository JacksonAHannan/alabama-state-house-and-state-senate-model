# Social conservatism and national-baseline overperformance

## Question

Could Alabama Democrats' relationship between social conservatism and CMO be
obscured because the published historical baseline relies heavily on statewide
offices whose Democratic nominees were themselves often socially conservative?

This audit replaces the state-ticket comparator with three national measures:

- preceding presidential margin;
- same-cycle U.S. Senate margin, where a contested Senate race is available;
- their equal-component average when both exist, otherwise the available one.

Positive ideology is more conservative. Positive overperformance means the
Democratic legislative candidate ran ahead of the national benchmark.

## Coverage

The best available pre-election social score is available for 95 Democratic
candidate-cycle observations. Presidential comparisons cover 81, Senate
comparisons cover 43, and the combined national benchmark covers 90. Evidence
comes from exact-cycle Vote Smart responses or reviewed pre-election legislative
votes. No party-average ideology is imputed. The usable period is predominantly
1998–2018; 1994 and 2022 currently have no individual social score, and Alabama's
2008 presidential precinct return is unavailable.

## Main result

The baseline choice changes the pooled descriptive relationship substantially.
On the same candidate observations, a full-unit increase in social conservatism
is associated with:

- **−5.1 CMO points** under the published state-context CMO among the 81
  presidential-comparison candidates;
- **+14.6 points** relative to the preceding presidential margin;
- **+19.0 points** relative to same-cycle U.S. Senate margin;
- **+16.6 points** relative to the combined national benchmark.

The combined estimate is about **+8.5 points per one standard deviation** of the
social score (HC3 95% interval +3.6 to +29.6 for a full-unit change, p=.013).
Presidential-only is borderline in the bivariate specification (p=.052); the
Senate-only estimate is positive with p=.048.

The national-benchmark tercile means are 12.5 points for the most progressive
third, 20.0 for the middle, and 32.8 for the most conservative third. In
majority-white districts they are also strongly positive before controls.

## Why this is not yet an independent ideology effect

The positive pooled relationship is not stable after separating election era,
incumbency, and geography. Social conservatism correlates with Democratic
incumbency (r=.38), lower nonwhite share (r=−.44), and lower white-college share
(r=−.50). Democratic incumbency itself correlates strongly with national-relative
overperformance (r=.58).

Adding only cycle and chamber fixed effects reduces the combined coefficient
from +16.6 to +8.0 and makes it imprecise. Adding economic ideology leaves it
near +9.4. Adding incumbency reduces it to +3.0; the nonincumbent-only estimate
is +3.4 (p=.71). The fully adjusted estimate is −3.2 with a wide interval spanning
zero. Within-cycle estimates are positive in 1998, 2006, 2010, and 2018, negative
in 2002 and 2014, and individually imprecise except for 2006.

The relationship is strongest in the pre-2008 Vote Smart portion of the sample.
It is weak in the reviewed legislative-vote sample concentrated in 2014 and
2018. This can reflect real party-system change, different evidence sources, or
both.

## Interpretation

The hypothesis receives meaningful but qualified support. Statewide-ticket CMO
does conceal a large *descriptive* national-relative advantage among socially
conservative Democrats. But the current evidence does not show that ideology
itself independently produced that advantage. Much of the pattern describes a
specific historical candidate type: established, often incumbent conservative
Democrats who retained local support after their districts had become Republican
in federal elections.

That distinction is substantively important. Social conservatism may have helped
those politicians build or retain incumbency, so controlling for incumbency can
remove part of the historical pathway. It nevertheless prevents the current
data from supporting a clean causal claim about an otherwise comparable new
candidate adopting conservative issue positions.

## Outputs

- `social_ideology_national_baseline_detail.csv`
- `social_ideology_national_baseline_estimates.csv`
- `social_ideology_national_baseline_paired.csv`
- `social_ideology_national_baseline_terciles.csv`
- `social_ideology_national_baseline_correlations.csv`
