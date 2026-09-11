# Historical Southern panel extension: Arkansas 1994-1998

This experimental panel preserves every row of the independently validated
2,273-row HEDA/OpenElections panel and adds only Arkansas contests that pass
four gates: independent SOS/Klarner reconciliation, a contested Democratic and
Republican race, finite same-cycle context, and at least 95% legislative-
turnout join coverage.

The baseline office is governor in 1994, president in 1996, and U.S. Senate in
1998. When a workbook precinct reports more than one legislative district, its
context vote is allocated in proportion to observed legislative turnout in
that precinct. This is an allocation device, not inferred precinct geometry.
Klarner remains the candidate-result and incumbency source.

The full Arkansas candidate audit and coverage diagnostics are retained even
when rows fail a gate. Existing combined-panel rows take precedence on any key
overlap. These outputs remain experimental and require independent validation
before a model tournament rerun.
