# Regional white-voting contextual effects

This aggregate precinct analysis compares incorporated-city and residual-county areas using 2024 Census TIGER/Line place boundaries. It covers the 2018 and 2022 governor elections and the 2020 and 2024 presidential elections. Coefficients are contextual effects, not individual white-voter estimates.

## Average adjusted regional residuals

| Region | Estimate |
|---|---:|
| Birmingham city | +8.85 |
| Huntsville city | +7.98 |
| Tuscaloosa city | +2.73 |
| Madison city | +2.12 |
| Madison County remainder | +1.95 |
| Birmingham educated suburbs | +1.33 |
| Mobile city | +0.36 |
| Auburn city | -2.54 |
| Shelby County remainder | -2.60 |
| Black Belt | -3.35 |

## White-college composition interactions

| Region | Estimate | Adjusted p |
|---|---:|---:|
| Birmingham city | +33.74 | 0.000 |
| Auburn city | +28.21 | 0.437 |
| Tuscaloosa city | +7.58 | 0.461 |
| Birmingham educated suburbs | -2.92 | 0.686 |
| Mobile city | -3.05 | 0.686 |
| Madison County remainder | -7.09 | 0.480 |
| Black Belt | -18.78 | 0.437 |
| Huntsville city | -21.61 | 0.000 |
| Shelby County remainder | -26.27 | 0.002 |
| Madison city | -41.16 | 0.000 |

The interaction coefficients are slopes rather than average regional effects and can be unstable where a region has a narrow education range.

## High-white-precinct sensitivity

These are average adjusted residuals only where non-Hispanic white adults are at least 70% of the modeled adult population, reducing reliance on ecological assumptions about Black voting.

| Region | Estimate |
|---|---:|
| Birmingham city | +15.70 |
| Huntsville city | +8.18 |
| Tuscaloosa city | +3.19 |
| Madison County remainder | +2.68 |
| Madison city | +2.42 |
| Mobile city | +1.35 |
| Birmingham educated suburbs | +0.72 |
| Shelby County remainder | -2.40 |
| Auburn city | -2.47 |
| Black Belt | -3.16 |

## Black Belt composition check

The Black Belt uses the traditional 12-county definition: Bullock, Choctaw, Dallas, Greene, Hale, Lowndes, Macon, Marengo, Perry, Pickens, Sumter, and Wilcox. Precinct subgroups are based on modeled adult race composition.

| Cycle | Precinct type | Precincts | Adjusted residual |
|---:|---|---:|---:|
| 2018 | majority-Black precinct | 139 | -5.70 |
| 2018 | majority-white precinct | 76 | -1.74 |
| 2018 | racially mixed precinct | 10 | -6.77 |
| 2020 | majority-Black precinct | 139 | -3.28 |
| 2020 | majority-white precinct | 76 | -1.82 |
| 2020 | racially mixed precinct | 11 | -2.71 |
| 2022 | majority-Black precinct | 125 | -1.30 |
| 2022 | majority-white precinct | 69 | -0.42 |
| 2022 | racially mixed precinct | 10 | -6.71 |
| 2024 | majority-Black precinct | 130 | -4.23 |
| 2024 | majority-white precinct | 64 | -2.75 |
| 2024 | racially mixed precinct | 10 | -8.37 |

## Expanding-cycle prediction test

| Cycle | Scope | Base MAE | Regional MAE | Gain |
|---:|---|---:|---:|---:|
| 2020 | named_regions | 0.0839 | 0.0695 | +0.0144 |
| 2020 | statewide | 0.0689 | 0.0648 | +0.0041 |
| 2022 | named_regions | 0.0830 | 0.0698 | +0.0131 |
| 2022 | statewide | 0.0687 | 0.0630 | +0.0058 |
| 2024 | named_regions | 0.0754 | 0.0624 | +0.0130 |
| 2024 | statewide | 0.0601 | 0.0556 | +0.0045 |

Positive gain means regional features reduced held-out MAE. Statewide election means are removed in each cycle, so the test evaluates relative geographic prediction rather than leaking the statewide environment.

## Limitations

Precincts are assigned by representative point; split-place precincts are not fractionally allocated. HC1 uncertainty treats precincts as observations and can overstate certainty for a region represented by one place. Results are multiple-test corrected within each coefficient family. Mixed gubernatorial and presidential cycles limit the time-trend interpretation.
