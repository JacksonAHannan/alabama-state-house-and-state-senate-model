# Historical Southern panel extension: Tennessee 1998

This experimental extension preserves all 2,383 validated prior rows and adds
Tennessee 1998 only when four gates pass: SOS/Klarner district-total
reconciliation, a contested Democratic/Republican race, finite governor
context, and at least 95% legislative-turnout coverage under an exact
canonical-county/alphanumeric-precinct join.

Governor votes are allocated across a split precinct in proportion to observed
legislative turnout. OCR-ambiguous governor cells remain missing. No fuzzy
precinct-name join, printed-total imputation, or missing-to-zero conversion is
used. Klarner remains the candidate result and incumbency source.

The candidate and coverage exports retain every excluded Tennessee district
and its failed gates. These outputs remain experimental pending independent
validation and a new tournament run.

The allocation audit records each observed governor precinct-party total,
its chamber-specific allocation weights, and the resulting conservation
difference. This makes split-precinct allocation independently testable.
