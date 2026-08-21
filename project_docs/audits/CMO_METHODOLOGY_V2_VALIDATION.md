# CMO methodology v2 independent validation

- Task: `VALIDATE-CMO-V2-001`
- Reviewer: `/root/blue_oxblood_validation` (`validation_release`)
- Candidate: final remediated `CMO-METHODOLOGY-V2-001`, 2026-08-21
- Decision: **PASS**

The revised four-estimand CMO staging release passes the complete independent
gate. Race-level math, temporal separation, candidate-variable exclusion,
identity handling, partial pooling, construct restrictions, uncertainty,
manifest provenance, deterministic output, tests, and documentation are
internally consistent. No model, warehouse, or public-page files were changed
by validation; two validation rebuilds reproduced identical bytes.

## Identity and candidate attribution

- All 563 raw one-token candidate names, including apostrophe/hyphen surnames
  without whitespace, are race-specific unresolved identities.
- No one-token identity links longitudinally, and there are zero duplicate
  `(cycle, candidate_effect_id)` keys.
- `SMITH` and `ANDERSON` collision buckets are split correctly.
- `JACK WILLIAMS` House 47 links across 2006–2014 while House 102 and Senate 34
  remain separate.
- `PHIL WILLIAMS` House 6 and Senate 10 remain separate while each seat series
  links across 2010–2014.
- The repeat sample contains 77 conservatively resolved links, with none of the
  previously contaminated surname-only cases.
- Crossed candidate/opponent signs are correctly oriented toward own-party
  strength; effects are unique, reliability is bounded, and candidate-pair plus
  unattributed residual exactly reconstructs race context CMO.

## Construct validity

The same-seat successor design now requires both current and prior identities
to be resolved. It contains 173 rows: 172 normalized-full-name pairs and one
resolved same-cycle-collision split, with zero unresolved rows. No row labeled
as a different candidate shares the same upstream `person_id` across the pair.

Published construct counts and statistics reproduce:

- repeat-candidate designs: n=77;
- bivariate prior-CMO/next-win design: n=77;
- resolved different-candidate same-seat design: n=173, Spearman 0.48873;
- incumbent-departure successor design: n=16.

The documentation correctly labels next-win evidence as bivariate rather than
an independently controlled prediction and incumbent departure rather than
retirement. It reports the resolved-only 173-pair successor result.

## Ten-priority and statistical audit

| Area | Result | Independent finding |
|---|---|---|
| Candidate-free headline | PASS | Context feature list excludes incumbency, finance, candidate history, winner, and ideology. |
| Absolute and centered CMO | PASS | Both are emitted; every chamber-cycle centered median is zero within `1e-10`. |
| Separate predictive output | PASS | Candidate-derived inputs occur only in the distinctly labeled predictive residual. |
| Source-aware baseline | PASS | Vote-weighted Governor/AG and modern 70/30 federal math independently reproduce. |
| Contest tiers | PASS | 508 meaningful and one nominal race; nominal is scored but excluded from fitting. |
| Alternative specifications/bounds | PASS | Ridge, Huber, and logit specifications are emitted; all expected margins are bounded. |
| Outer-cycle/nested-forward separation | PASS | Training-cycle metadata and held-out/future perturbation tests show no target leakage. |
| Era-consistent features | PASS | Recent-only region variables are excluded; availability flags accompany imputation. |
| Stable identity/partial pooling | PASS | Unresolved one-token names never link; resolved names and collision splits satisfy key invariants. |
| Construct-validity restrictions | PASS | Repeat and successor designs exclude unresolved identities and use accurate labels. |
| Race-specific uncertainty | PASS | 494 distinct ordered radii; candidate-party interval orientation is correct. |

Core output integrity passes: 509 unique race keys, 1,018 unique race/party
keys, exactly two major-party rows per race, no null primary estimands, exact
raw/context/predictive equations, and expected margins within the logical vote
range.

## Manifest and determinism

The manifest contains and independently verifies:

- SHA-256 for four frozen inputs and the model code;
- four configuration records and two row-count records;
- a deterministic `build_run_id` recomputed exactly from ordered
  input/code/config/count records;
- SHA-256 for all ten non-manifest CSV outputs.

Two successive complete rebuilds left all 12 CSV/report hashes identical.

## Documentation

The generated methodology and model card match the outputs: 509 races, 77
repeat observations, resolved successor n=173/Spearman approximately 0.49, and
predictive cycle-balanced MAE 12.67749 (reported as 12.68). The limitations
correctly distinguish retrospective CMO, specification/data-quality bands,
identity uncertainty, and non-causal/non-probabilistic use.

## Tests and commands

- Focused v2 tests: **7 passed** in 13.01 seconds.
- Full suite: **367 passed**, 11 warnings, in 97.90 seconds.
- Agent workflow validation: passed.

```powershell
python -m pytest scripts/tests/test_cmo_methodology_v2.py -q
python scripts/rebuild_cmo_methodology_v2.py
python scripts/rebuild_cmo_methodology_v2.py
python -m pytest -q
python scripts/validate_agent_workflow.py
```

Additional Python-from-stdin checks independently recomputed baselines and
estimands, exercised temporal perturbation invariance, audited every one-token
and named identity, verified successor identity status, recomputed the run ID
and every recorded hash, and checked documentation numbers against diagnostics.

## Release decision

**PASS.** The CMO v2 staging release is independently validated. The model
owner may advance it to the separately controlled publication/migration step,
while retaining its documented limitations and unresolved identity statuses.
