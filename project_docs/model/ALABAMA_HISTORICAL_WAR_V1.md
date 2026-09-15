# Alabama historical WAR v1

Run: `AL-HIST-WAR-V1-0E018273EBEDEEEFAD75`

This product restores the 1994–2022 Alabama race explorer under the corrected race-residual definition. For 1994–2014, the selected post-2016 Southern `decaying_lag` ridge model (alpha 100) is fit only on strict races after 2016 and applied backward to Alabama. For 2018 and 2022, the output preserves the exact published Alabama WAR v1 same-cycle residual.

`WAR = legislative-minus-ticket gap - fitted structural expected gap`.

One fixed reference model scores every cycle: the post-2016 Southern fit is applied unchanged to 1994-2014 rather than refit by era. Pre-2016 expectations are therefore modern partisan expectations, so early-era Democrats show large positive WAR by construction; read those levels as distance from modern partisan gravity, not as a contemporaneous fit. The schema keeps `scoring_scope = post2016_southern_model_backcast` and `backcast_extrapolation_years` as stable contract fields, but reader-facing copy states the fixed-reference framing. Candidate rows are opposite orientations of one race residual. Finance, ideology, pooled effects, and committee identities are excluded.

## Career cumulative WAR

`scripts/build_alabama_career_war.py` sums each person's scored candidate-cycle WAR into `data/processed/war/alabama_career_war_v1/career_war.csv` (849 people, 138 across more than one cycle). Single-cycle WAR credits the first defiant cycle in full and later ones only net of the decayed prior gap, so career WAR is the measure of sustained overperformance. Identity is the canonical `person_id`; a 2022 source stub is folded into an earlier person only on an exact unique normalized name, and the 43 that cannot be resolved are counted as single-cycle careers rather than merged on a guess.
