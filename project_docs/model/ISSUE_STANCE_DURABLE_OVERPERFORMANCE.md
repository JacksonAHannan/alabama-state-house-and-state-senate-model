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
| environment_resources | preservation (+) vs extraction/property priority (-) | 34 | 34 | 3 | 3 |
| institutional_reform | democratic reform (+) vs institutional control (-) | 5 | 5 | 0 | 0 |
| labor_capital | labor (+) vs capital/management (-) | 22 | 22 | 2 | 1 |
| market_government_direction | government direction (+) vs market autonomy (-) | 39 | 38 | 6 | 4 |
| material_support | material generosity (+) vs restriction (-) | 83 | 80 | 20 | 8 |
| order_justice | punitive enforcement (+) vs rehabilitation/due process (-) | 44 | 42 | 10 | 7 |
| social_liberty_equality | liberty/equality (+) vs traditional restriction (-) | 134 | 129 | 28 | 14 |

## Primary estimates

| outcome | family | n | coefficient | ci_low | ci_high | cluster_p_value | primary_bh_q_value | status |
|---|---|---|---|---|---|---|---|---|
| presidential_overperformance | environment_resources | 31 | -2.2466016599323213 | -46.64049246006523 | 42.147289140200584 | 0.8845118911509755 | 0.8845118911509755 | estimated |
| presidential_overperformance | institutional_reform | 4 |  |  |  |  |  | underpowered |
| presidential_overperformance | labor_capital | 22 | -14.249818206167715 | -44.46115286928636 | 15.961516456950926 | 0.232451165109461 | 0.5194644458996476 | estimated |
| presidential_overperformance | market_government_direction | 37 | 5.205602811046234 | -12.471271161185367 | 22.882476783277834 | 0.5211664818403472 | 0.6948886424537962 | estimated |
| presidential_overperformance | material_support | 79 | 10.07009478863101 | -3.7621364138612776 | 23.9023259911233 | 0.14317580205437783 | 0.5194644458996476 | estimated |
| presidential_overperformance | order_justice | 43 | 10.108478886605784 | -8.683041123235935 | 28.899998896447503 | 0.2597322229498238 | 0.5194644458996476 | estimated |
| presidential_overperformance | social_liberty_equality | 127 | -16.801781518918315 | -24.34234957413609 | -9.261213463700539 | 1.3270966967434126e-05 | 0.0001592516036092095 | estimated |
| federal_index_overperformance | environment_resources | 29 | 4.677798325321607 | -24.402802031943136 | 33.758398682586346 | 0.6718071066417757 | 0.7328804799728462 | estimated |
| federal_index_overperformance | institutional_reform | 4 |  |  |  |  |  | underpowered |
| federal_index_overperformance | labor_capital | 22 | -5.317162881446129 | -21.60715252148332 | 10.972826758591061 | 0.4484565527201073 | 0.6948886424537962 | estimated |
| federal_index_overperformance | market_government_direction | 33 | 5.6437193877443175 | -17.582707929888315 | 28.870146705376946 | 0.5994903877911412 | 0.7193884653493694 | estimated |
| federal_index_overperformance | material_support | 77 | 8.731007525740576 | -5.97149234334093 | 23.433507394822083 | 0.22056679635213414 | 0.5194644458996476 | estimated |
| federal_index_overperformance | order_justice | 41 | 4.92954704895603 | -11.297989354747118 | 21.15708345265918 | 0.5200672527981756 | 0.6948886424537962 | estimated |
| federal_index_overperformance | social_liberty_equality | 118 | -13.827657146770612 | -21.36836767358706 | -6.286946619954165 | 0.00024264606881746142 | 0.0014558764129047686 | estimated |

Repeat-candidate panel: 53 people. Prospective persistence panel: 20 people.

## Interpretation rules

- Federal-relative outcomes are primary because the hypothesis concerns durable local performance beyond national partisanship.
- Era and district-fit interactions are exploratory and must not be promoted from p-values alone.
- Candidate-level means describe durability but can select on rerunning, winning, and contest entry.
- Later legislative evidence is not allowed to leak backward; the prospective persistence table starts at the first election-cycle-specific observed stance.
- Families with fewer than 12 usable observations are reported as underpowered.
