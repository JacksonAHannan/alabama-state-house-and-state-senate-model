# Madison–Huntsville white-voting area-effect test

## Scope

This precinct-level contextual analysis covers the 2018 governor, 2020 president, 2022 governor, and 2024 president elections. Madison County is the reproducible proxy for the Huntsville–Madison metro. It does **not** identify individual white voters, and municipal boundaries are not yet separated from the rest of the county.

## Results

- Madison × white-college composition: -12.40 points (95% CI -20.45 to -4.35; p=0.003).
- Madison area effect per two-year step: -0.02 points (95% CI -1.80 to +1.76; p=0.985).
- Additional growth in the white-college interaction per step: +3.22 points (95% CI -1.20 to +7.65; p=0.153).

Adjusted residual by election:

| cycle | area | precincts | votes | weighted residual | white-college share |
|---:|---|---:|---:|---:|---:|
| 2018 | Rest of Alabama | 1913 | 1575438 | -0.0029 | 0.1939 |
| 2018 | Madison County | 72 | 141396 | 0.0324 | 0.3292 |
| 2020 | Rest of Alabama | 1898 | 2100709 | -0.0049 | 0.1939 |
| 2020 | Madison County | 72 | 190066 | 0.0539 | 0.3292 |
| 2022 | Rest of Alabama | 1859 | 1245591 | -0.0032 | 0.1939 |
| 2022 | Madison County | 74 | 114235 | 0.0347 | 0.3292 |
| 2024 | Rest of Alabama | 1865 | 2041744 | -0.0066 | 0.1990 |
| 2024 | Madison County | 79 | 193254 | 0.0692 | 0.3335 |

## Interpretation

A positive Madison coefficient means precincts in the county vote more Democratic than statewide demographic composition and election-year effects predict. A positive Madison × white-college term is consistent with the difference being concentrated in educated-white precinct composition. Because this is aggregate ecological evidence, it should be treated as a forecast feature hypothesis, not a causal or individual-level finding.

The time test has only four elections and mixes gubernatorial with presidential electorates. Promotion requires forward-validation showing that the area terms improve held-out prediction, plus a municipal/suburban geography refinement using Census place and urban-area boundaries.
