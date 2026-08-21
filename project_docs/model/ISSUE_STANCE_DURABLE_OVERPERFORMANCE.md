# Issue stance and durable overperformance

Positive family scores always mean the second pole shown below. Estimates are descriptive HC3 regressions among contested Democratic candidates; no missing stance is imputed.

## Current reading

- Social traditionalism has the clearest pooled association: the liberty/equality score is associated with 13.8 fewer Democratic overperformance points per full-scale unit against the combined federal baseline (75 candidate-cycles; candidate-clustered p=0.007; primary BH q=0.018). The coefficient shrinks to -5.6 and is not distinguishable from zero after cycle, demographics, and incumbency controls.
- Extraction/property priority has a pooled association of roughly 24 federal-relative points per full-scale move away from preservation (25 candidate-cycles; q=0.042), but it is concentrated in 2008-2014 and disappears with cycle/context controls.
- Punitive law-and-order positioning is associated with presidential-relative overperformance, but the combined-federal estimate is imprecise and has no post-2016 coverage.
- Among the 60 rows with both social and material-support scores, traditionalism and material generosity are independently favorable in the pooled model. Both coefficients disappear after cycle/context controls, so the attractive traditional-supportive bundle remains descriptive rather than predictive.
- Durable evidence is much thinner than cross-sectional evidence: only 17 repeat candidates have social-family scores, and only five can be evaluated prospectively after their first observed stance. Their durable social coefficient points in the expected traditionalist direction but is not precise.

## Registered hypotheses and cumulative status

| hypothesis_id | hypothesis | focal_dimension | expected_direction | heterogeneity_test | status | current_result | result_note |
|---|---|---|---|---|---|---|---|
| VAL-01 | Social traditionalism historically helped Democrats relative to federal baselines. | social_liberty_equality | negative | pre_2008 strongest; weaker after 2008 and 2016 | registered | mixed_support | Pooled federal-relative association supports traditionalism, but cycle/context adjustment and era-specific estimates are imprecise. |
| VAL-02 | Economic material generosity can coexist with social traditionalism and independently predict overperformance. | material_support | positive | joint social/economic model | registered | mixed_support | Material generosity is positive only when modeled jointly with social stance; the result disappears with cycle/context controls. |
| VAL-03 | Labor alignment historically helped Democratic candidates. | labor_capital | positive | pre_2016 strongest | registered_underpowered | insufficient | Labor has only 17 candidate-cycles and no repeat-candidate coverage. |
| VAL-04 | Punitive law-and-order positioning improves fit in majority-white and federally Republican districts. | order_justice | positive | majority-white / federal R interaction | registered | mixed_support | Punitive positioning is associated with presidential-relative performance, not robustly with the combined federal baseline. |
| VAL-05 | Market autonomy improves Democratic fit in conservative districts, separately from material support. | market_government_direction | negative | federal R interaction | registered_underpowered | insufficient | Market/government direction has only 10 candidate-cycles. |
| VAL-06 | Extraction/property priority improves rural-conservative fit. | environment_resources | negative | federal R proxy; rural measure pending | registered | mixed_support | Extraction/property priority has a pooled association, concentrated in 2008-2014 and not robust to cycle/context adjustment. |
| VAL-07 | Issue congruence is more important than a universal moderation score. | all families | interaction | majority-white and federal-partisanship interactions | registered | not_yet_supported | Most majority-white and federal-Republican interaction tests are imprecise; no stable general congruence effect is established. |
| VAL-08 | Ideological advantages attenuate after the 2008 and 2016 nationalization steps. | all families | attenuation | era-stratified estimates | registered | directional_only | The social coefficient is smaller after 2016, but formal attenuation interactions are not statistically distinguishable. |
| VAL-09 | Socially traditional and economically supportive Democrats form the strongest historical bundle. | social_liberty_equality + material_support | negative social / positive support | joint model and quadrant comparison | registered | descriptive_support | Traditional-supportive candidates have the highest raw bundle mean; joint coefficients vanish after cycle/context controls. |
| VAL-10 | The same issue signals predict durable multi-cycle rather than one-cycle overperformance. | all families | same direction | repeat-candidate mean and prospective persistence | registered | insufficient | Only 17 repeat people have social scores and only five support a prospective social persistence test. |
| VAL-11 | Institutional reform affects overperformance. | institutional_reform | unknown | retain null/insufficient result | registered_underpowered | insufficient | Institutional reform has four candidate-cycles. |

## Coverage

| family | description | candidate_cycles | people | repeat_candidate_rows | prospective_persistence_people |
|---|---|---|---|---|---|
| environment_resources | preservation (+) vs extraction/property priority (-) | 20 | 20 | 2 | 1 |
| institutional_reform | democratic reform (+) vs institutional control (-) | 4 | 4 | 0 | 0 |
| labor_capital | labor (+) vs capital/management (-) | 17 | 17 | 0 | 0 |
| market_government_direction | government direction (+) vs market autonomy (-) | 9 | 9 | 2 | 1 |
| material_support | material generosity (+) vs restriction (-) | 70 | 69 | 18 | 7 |
| order_justice | punitive enforcement (+) vs rehabilitation/due process (-) | 14 | 14 | 2 | 1 |
| social_liberty_equality | liberty/equality (+) vs traditional restriction (-) | 99 | 98 | 24 | 11 |

## Primary estimates

| outcome | family | n | coefficient | ci_low | ci_high | cluster_p_value | primary_bh_q_value | status |
|---|---|---|---|---|---|---|---|---|
| presidential_overperformance | environment_resources | 19 | -18.73988232245838 | -71.10025947364767 | 33.62049482873091 | 0.28866525660805403 | 0.519854248166442 | estimated |
| presidential_overperformance | institutional_reform | 3 |  |  |  |  |  | underpowered |
| presidential_overperformance | labor_capital | 17 |  |  |  |  |  | underpowered |
| presidential_overperformance | market_government_direction | 9 |  |  |  |  |  | underpowered |
| presidential_overperformance | material_support | 66 | 5.391792045382022 | -8.66290992847476 | 19.446494019238806 | 0.4334484712090596 | 0.5779312949454128 | estimated |
| presidential_overperformance | order_justice | 13 | 13.781636326009478 | -18.51761745658031 | 46.08089010859926 | 0.32490890510402626 | 0.519854248166442 | estimated |
| presidential_overperformance | social_liberty_equality | 93 | -19.455176683394356 | -26.906805144171006 | -12.003548222617706 | 8.409901479480226e-07 | 6.727921183584181e-06 | estimated |
| federal_index_overperformance | environment_resources | 20 | -7.986056430617904 | -43.520943299906406 | 27.548830438670603 | 0.5204287772315265 | 0.5947757454074588 | estimated |
| federal_index_overperformance | institutional_reform | 4 |  |  |  |  |  | underpowered |
| federal_index_overperformance | labor_capital | 17 |  |  |  |  |  | underpowered |
| federal_index_overperformance | market_government_direction | 9 |  |  |  |  |  | underpowered |
| federal_index_overperformance | material_support | 65 | 6.8149240113626215 | -7.413616555153523 | 21.043464577878765 | 0.31630975884853113 | 0.519854248166442 | estimated |
| federal_index_overperformance | order_justice | 12 | 4.0071603523905885 | -35.69254267339363 | 43.706863378174816 | 0.8116177067364387 | 0.8116177067364387 | estimated |
| federal_index_overperformance | social_liberty_equality | 89 | -11.487027650062103 | -19.91522522914846 | -3.0588300709757466 | 0.005999983145090157 | 0.02399993258036063 | estimated |

Repeat-candidate panel: 53 people. Prospective persistence panel: 13 people.

## Interpretation rules

- Federal-relative outcomes are primary because the hypothesis concerns durable local performance beyond national partisanship.
- Era and district-fit interactions are exploratory and must not be promoted from p-values alone.
- Candidate-level means describe durability but can select on rerunning, winning, and contest entry.
- Later legislative evidence is not allowed to leak backward; the prospective persistence table starts at the first election-cycle-specific observed stance.
- Families with fewer than 12 usable observations are reported as underpowered.
