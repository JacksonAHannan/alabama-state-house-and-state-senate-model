# CMO methodology v4: Alabama WAR analogue

CMO is the residual of a model predicting the legislative-minus-same-cycle-federal margin gap. Incumbency and down-ballot lag are the principal structural controls. Demographics are capped at three margin points and campaign effort at two. Ideology never enters the model.

## Formula

`CMO = raw legislative-ticket gap - predicted structural gap`

Federal-unavailable races use the same-cycle state ticket and are labeled sensitivity fallbacks. The model is trained only on races with usable federal baselines.

Selected ridge alpha: 100.

## Morrow, 1998 HD-18

- Raw legislative-federal gap: 11.909
- Predicted structural gap: 35.323
- WAR-style CMO: -23.415

## Tournament

| specification | alpha | cycles | races | mean_cycle_mae | mean_cycle_rmse | latest_cycle_mae |
| --- | --- | --- | --- | --- | --- | --- |
| barebones | 3.0 | 8 | 428 | 19.377527006187464 | 23.810615916899494 | 17.137731006124742 |
| barebones | 10.0 | 8 | 428 | 19.30112457914957 | 23.73130933310305 | 16.997518925892525 |
| barebones | 30.0 | 8 | 428 | 19.131211251182158 | 23.56488673790865 | 16.658197995574742 |
| barebones | 100.0 | 8 | 428 | 18.834254196968235 | 23.387654123472977 | 16.168106159896674 |
| full | 3.0 | 8 | 428 | 17.266407073192912 | 21.72984608331232 | 15.068588442636724 |
| full | 10.0 | 8 | 428 | 17.185209263960257 | 21.625777831290268 | 14.83921003684966 |
| full | 30.0 | 8 | 428 | 17.003950940889574 | 21.42662762976326 | 14.338740278193335 |
| full | 100.0 | 8 | 428 | 16.83122721990741 | 21.286665337443175 | 13.439065103646643 |

## Cycle diagnostics

| cycle | races | federal_primary | mean_raw_gap | mean_war | mae_war |
| --- | --- | --- | --- | --- | --- |
| 1994 | 72 | 49 | 15.07333406155528 | 0.4423131423197051 | 16.024092991307114 |
| 1998 | 85 | 85 | 32.69645432514265 | 5.208267010072049 | 14.432343074852534 |
| 2002 | 74 | 74 | 16.22617086946649 | -2.423982312430671 | 14.855389088066216 |
| 2006 | 62 | 35 | 32.317463534302526 | 10.646249262919754 | 19.124884635642495 |
| 2010 | 63 | 63 | 17.34608525672575 | -1.4528674133112969 | 13.230243006469491 |
| 2014 | 56 | 26 | 12.774446811185271 | -2.7635412211500774 | 13.733739702469228 |
| 2018 | 64 | 63 | 2.134588110946993 | -7.643087719181146 | 9.737970656548146 |
| 2022 | 33 | 33 | 1.051331260739931 | -12.488503697584273 | 13.6636568561631 |

## Construct validity

| design | outcome | n | pearson | pearson_p | spearman | spearman_p |
| --- | --- | --- | --- | --- | --- | --- |
| repeat_candidate_next_cycle | candidate_war_cmo | 77 | 0.038752813603057906 | 0.7379130876083427 | -0.014432935485567061 | 0.9008533341218711 |
| repeat_candidate_next_cycle | candidate_raw_ticket_gap | 77 | 0.2930445273830915 | 0.00969716908585802 | 0.22059519427940477 | 0.053870643272323944 |
