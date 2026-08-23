# Southern 2024 incumbency staging

Klarner supplies incumbent flags directly for the 2018, 2020, and 2022 race
rows already used by the recent Southern panel. The missing 2024 layer is
reconstructed from candidate identity continuity.

The source roster contains every locally available 2020 and 2022 Klarner
winner, including uncontested winners. Using both years is necessary for
staggered state senates. MEDSL's 2024 precinct return supplies candidate names;
the staging pipeline selects the highest-vote Democratic and Republican
candidate in each of the 335 calibration races.

Matches are attempted within state and chamber. Full-name exact matches have
priority, followed by district-supported and uniquely separated fuzzy matches.
Texas MEDSL names are usually surnames only, so surname matching is restricted
to the same party to prevent false party-switch assignments. Full-name matching
remains party-neutral and correctly identifies Mesha Mainor's Democratic-to-
Republican switch.

The result is 323 model-ready races (96.4 percent) and 12 unresolved races.
Ambiguous candidates retain missing incumbency; they are not converted to
challengers or open seats. The ready set contains 246 incumbent-running and 77
inferred-open contests. These remain staging labels rather than canonical
person identities. Post-2022 special-election succession is a residual risk
requiring sensitivity analysis.
