# Combined historical Southern comparison panel

The combined experimental panel retains every strict HEDA/Klarner observation
and adds OpenElections-derived baselines only for keys absent from that sample.
Legislative outcomes and candidate metadata continue to come from Klarner.

OpenElections statewide context is joined to legislative precinct returns and
allocated across split precincts using legislative turnout. At least 95% of
the legislative turnout represented in a state-cycle-chamber must successfully
join to the selected context office. The share of statewide context assigned
is retained as an electoral-footprint diagnostic, but is not a completeness
gate because staggered Senate elections legitimately cover only part of a
state in a given cycle.

Cycle restrictions follow independent staging review. Georgia 2014 is
unofficial and sensitivity-only; Arkansas 2008 and South Carolina 2006 are
context-only; Missouri 2014 lacks a usable same-cycle context. Missouri 2012
HD150, Georgia 2012 SD30, and Georgia 2016 SD13 remain excluded for targeted
review. HEDA has precedence on overlapping eligible district keys.
