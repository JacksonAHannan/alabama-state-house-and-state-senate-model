# Southern incumbency identity repair, 2016-2024

## Result

The repaired build retains all 4,582 modeled D-versus-R races and raises the
evidence-backed strict incumbency roster from 3,621 to 3,991 races. No prior
strict race becomes unresolved. The remaining 591 races retain explicit
unknown/review status rather than being converted to open seats or challengers.

The released roster manifest was generated at
`2026-09-02T02:53:16.068365+00:00`. Its roster hash is
`8e225c7bebe0d5640a3439c0c42c6270d358cd90168622b9f3e7c6e609ad7c0a`.

## Cause and correction

The earlier builder required a normalized full-name match between provider
incumbency evidence and the selected modeling outcome. That dropped valid
flags when the outcome used an opaque Alabama ballot code, a provider title,
a surname-only Texas label, or a compound/former surname. The warehouse also
retained the previous generated roster as a source observation, allowing a
rebuild to consume its own output and creating ten false two-incumbent Texas
races.

The corrected join requires exact state, cycle, chamber, district, and party,
plus one of the following identity links:

- normalized candidate-name agreement;
- compatible surname/compound-surname agreement;
- Alabama's independently decoded 2022 official ballot-code roster.

The generated roster is excluded from its own evidence query. A same-party
scope without person evidence is not accepted. In particular, David Derby's
retirement is not attached to Dale Derby, and the Missouri Dan/Justin Brown
conflict is not promoted.

## Reconciliation

- 370 previously unresolved races now have strict source-backed flags.
- 14 previously strict race flags were corrected: ten Texas races no longer
  assert both candidates as incumbents, and four redistricting races retain an
  incoming incumbent even though a different district incumbent retired.
- Asserted two-incumbent races: 0.
- Explicit open seats with an asserted incumbent: 0.
- Positive upstream incumbent race-party observations represented: all except
  the two documented retirement/person conflicts above.
- Dexter Grimsley, Alabama House 85 in 2022: Democratic incumbent = 1,
  Republican incumbent = 0.

## Downstream rebuild

The Southern WAR preparation mart now has 4,280 strict finance-free outcomes
and 3,635 strict finance-complete outcomes. The post-2016 residual WAR run is
`WAR-POST2016-V3-8BB52074EC806C5BF6BF` with 3,660 races. The Southern
historical release is `WAR-SOUTH-HIST-V1-458CB1F094597CD6AA1D` with 3,420
races.

After the full same-cycle refit, Grimsley's 2022 WAR is +19.6641. His 2018 WAR
is +13.2664; both remain race-specific residuals.

## Validation

The focused identity, incumbency, warehouse, WAR, historical, forecast, map,
finance, and publication regression set passes 97/97. The repository-wide run completed with 650 passed
and two failures before the one affected stale Grimsley snapshot was corrected;
that corrected test then passed. The sole remaining failure is the pre-existing
canonical historical-finance fixture, which expects 352 complete races while
the unrelated current finance build contains 353. The incumbency repair does
not modify that finance input or builder.
