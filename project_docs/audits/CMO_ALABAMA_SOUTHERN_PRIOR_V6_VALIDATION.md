# Alabama CMO v6 Southern-prior validation

**Verdict: PASS as a historical research decomposition; correctly rejected for direct 2026 promotion.**

The V6 candidate validly estimates an external Southern structural expectation without Alabama, leaves Direct CMO invariant, and exposes generic incumbency separately from residual candidate quality. Its negative modern-era validation result is real: despite improving the cycle-balanced all-era score, it performs much worse than the ticket baseline in 2018–2022 and therefore must not be promoted into the 2026 forecast unchanged.

## Independent rebuild and tests

Because the research script writes to its module-level WAR directory, I redirected that directory to an isolated workspace, copied only the two required V5 inputs there, and invoked the same implementation:

```powershell
$env:VALIDATION_V6_OUT = "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\.validation_tmp\cmo_v6_southern"
@'
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
import rebuild_cmo_southern_prior_v6 as model
model.WAR = Path(os.environ["VALIDATION_V6_OUT"]).resolve()
model.main()
'@ | python -X utf8 -

python -m pytest scripts/tests/test_cmo_southern_prior_v6.py -q
```

Two isolated rebuilds are byte-deterministic. Their path-local manifest SHA-256 is `074ae9fe979f7c14056b028eccd3d1e492e031030e631ca2734d0409ed1d6c8a`; all five CSV outputs byte-match the release candidate. The focused suite passes 5/5.

## External-prior isolation

- Validated Southern input: 2,402 eligible contests.
- Alabama observations excluded: 52.
- External training sample: exactly 2,350 contests from ten non-Alabama states.
- No Alabama row occurs in the fitted training frame.
- Every one of the 509 Alabama race rows records 2,350 training rows and ten training states.

The production manifest explicitly records `southern_training_excludes_alabama: true`, and its panel, Southern-tournament, V5-race, and V5-candidate input hashes all match the current versioned artifacts.

## Direct CMO and decomposition identities

All 509 V5 races join one-to-one to V6. Direct CMO differs only at floating-point serialization precision—the maximum absolute difference is `3.55e-15`, well below the `1e-12` invariant tolerance.

All 509 rows have finite values for the inclusive expectation, low/high source-office sensitivity, incumbent-neutral expectation, generic incumbency gap, and residual quality. Independently recomputed identities hold to `7.11e-15`:

```text
residual candidate quality = Direct CMO - inclusive Southern expectation
generic incumbency gap     = inclusive expectation - incumbent-neutral expectation
```

For every race with zero incumbency balance, the generic incumbency gap is exactly zero.

## Candidate orientation and pooling

- Candidate output contains 1,018 unique party observations, exactly two per race.
- Democratic and Republican orientations are exactly zero-sum for Direct CMO, the Southern expected gap, and the residual candidate-quality differential; maximum symmetry error is zero.
- Total electoral value remains a separate measure: pooled residual quality plus the candidate-oriented half-share of generic incumbency.
- All candidate total-value and pooled-quality fields are finite.

The forward candidate-effect tournament selects ridge penalty `3`. Its seen-candidate MAE is `15.988790`, versus `16.350262` for zero candidate effect. Other penalties score 16.036865 (10), 16.185952 (30), 16.287951 (100), and 16.384995 (1). The gain is correctly described as small and uncertainty labels remain required.

## Cycle validation

The 24-row validation table independently reproduces all cycle metrics:

| Cycle | Races | Ticket MAE | Southern inclusive MAE |
|---:|---:|---:|---:|
| 1994 | 72 | 22.343114 | 21.271808 |
| 1998 | 85 | 33.980159 | 20.503110 |
| 2002 | 74 | 24.078509 | 17.102002 |
| 2006 | 62 | 36.449805 | 22.774931 |
| 2010 | 63 | 25.081963 | 15.689245 |
| 2014 | 55 | 15.596797 | 13.653527 |
| 2018 | 64 | 6.653165 | 9.818403 |
| 2022 | 33 | 6.429530 | 17.504253 |

Cycle-balanced all-era MAE improves from `21.326630` for the unadjusted ticket baseline to `17.289660` for the Southern expectation. But the 2018–2022 average deteriorates from `6.541348` to `13.661328`. The recent-era failure is substantial, occurs in both modern cycles, and supports the documented non-promotion decision.

## Named cases

- Mike Curtis appears in 2010 and 2014 with Direct CMO `+19.531130` and `+10.533344`. The external expectation changes his residual interpretation from `-9.450072` in 2010 to `+5.560622` in 2014; the decomposition does not erase the observed direct scores.
- Barbara Bigsby Boyd has four retained Democratic observations: 2002, 2006, 2010, and 2018. Direct CMO is `+30.072092`, `+12.602572`, `+30.263799`, and `+8.767802`; corresponding residuals are `+13.817201`, `+12.786979`, `+14.132064`, and `-4.985865`.

These results reconcile with the six-row case-study export and demonstrate why direct performance, external expectation, and pooled residual quality must remain separately visible.

## Provenance and decision

The production artifact remains labeled `research_candidate`. All four input hashes and all five output hashes/counts reproduce; release output rows are 509 races, 1,018 candidates, 889 quality/tournament rows, 24 validation rows, and six case-study rows.

V6 is approved for historical decomposition and as an input to a future regime-aware tournament. It is not approved as a direct 2026 forecast adjustment. A promotable successor must combine the historical Southern evidence with post-2016 data and pass explicit modern-era forward validation.
