# CMO WAR analogue validation

**Task:** `VALIDATE-CMO-WAR-001`  
**Validated:** 2026-08-21  
**Verdict:** **PASS WITH NON-BLOCKING LIMITATIONS**

The v4 outputs pass the contracted release gate as a retrospective Alabama
analogue of the Split Ticket WAR design. All 509 race rows and 1,018 candidate
rows reconcile to the canonical inputs, the decomposition is arithmetically
exact, the federal-primary and state-ticket-fallback policies are implemented
as declared, and the candidate scores are zero-sum. This is not evidence that
the residual is a stable or causal candidate-quality trait; the published
repeat-candidate diagnostic provides no such support.

## Methodological fidelity

The reference design is Lakshya Jain's August 15, 2025 Split Ticket article,
[`Deconstructing WAR`](https://split-ticket.org/2025/08/15/deconstructing-war/).
That article defines WAR as the residual from a regression of congressional
margin minus same-cycle presidential margin, with incumbency and lagged
partisanship as the two dominant controls and spending and demographics as
minor controls. It explicitly describes white-college share and nonwhite share,
and says ideology does not enter the WAR regression.

The Alabama implementation is a defensible level-shifted analogue rather than
a literal reproduction: it models state-legislative margin minus the
same-cycle federal district index. It then uses the previous presidential
margin, presidential swing, and federal-versus-prior-presidential lag to model
the slower propagation of national realignment into state-legislative voting.
This matches the task contract's explicit same-cycle-federal primary baseline.

- Incumbency is symmetric. The only incumbency regressors are the Democratic
  incumbent indicator minus the Republican incumbent indicator, interacted
  with three eras. There is no party-specific incumbency entitlement.
- Lagged partisanship is represented by prior presidential margin,
  presidential swing, and era-specific federal-minus-prior-presidential lag.
- The only categorical model term is chamber. There is no cycle fixed effect.
- No ideology field appears in the race output or model feature lists.
- Demographics and effort are fitted only to the structural-model residual and
  are hard-capped at 3 and 2 margin points, respectively.

## Independent row reconciliation

I independently joined the v4 race output to
`canonical_cmo_features.csv`,
`historical_federal_district_baselines.csv`, and the vote-aggregated rows of
`canonical_cmo_district_office_baselines.csv`.

- All 509 race keys are unique and match eligible canonical rows.
- Democratic votes, Republican votes, and legislative Democratic margin match
  upstream for every row.
- The 428 federal-primary rows are exactly the rows with a nonmissing federal
  index and at least 0.50 contested federal coverage. Their baseline margin is
  exactly the upstream federal index and every label is
  `same_cycle_federal`.
- The remaining 81 rows all use the independently vote-weighted same-cycle
  state-office margin. None requires an undocumented presidential fallback,
  and every label is `same_cycle_state_fallback`.
- Fallback counts by cycle are 23 in 1994, 27 in 2006, 30 in 2014, and 1 in
  2018.
- Every candidate ID matches one upstream candidate on cycle, chamber,
  district, party, canonical name, and votes. There are exactly two party rows
  per race and no duplicate race-party rows.

## Arithmetic and constraints

Every row satisfies, within floating-point tolerance:

```text
raw ticket gap = legislative Democratic margin - selected baseline margin
structural expected gap = structural base + incumbency + lagged partisanship
predicted structural gap = structural expected gap + demographics + effort
WAR-style CMO = raw ticket gap - predicted structural gap
```

`cmo_v4_components.csv` matches the corresponding race columns on all 509
rows. The maximum absolute demographic and effort adjustments are exactly 3
and 2 points. Median absolute adjustments are 1.119 demographic points and
0.588 effort points, compared with 12.119 for incumbency and 3.940 for lagged
partisanship. The hard caps bind in 46 demographic rows and 112 effort rows.
Thus the primary terms dominate at the median, although effort reaches its cap
fairly often and should not be described as negligible in every race.

Candidate orientation is correct for all component and baseline fields:
Democratic values retain the race orientation and Republican values reverse
it. The Democratic and Republican `candidate_war_cmo` values sum to zero in
all 509 races.

## Tournament and validation design

The eight published leave-one-cycle-out tournament rows reproduce exactly in
memory. All eight eligible cycles and all 428 federal-primary, non-nominal
races appear once in a test fold. The declared selection rule chooses ridge
alpha 100 from the barebones structural specifications; that is the published
value and the result of the stated ordering.

Two interpretive cautions are important:

1. The cycle holdout is retrospective cross-validation, not a time-forward
   forecast test: a held-out historical cycle can be predicted using later
   cycles. This is acceptable for this retrospective score but must not be
   cited as prospective forecast validation.
2. The `full` tournament rows are a one-stage comparison model. The published
   score instead uses the selected barebones structural model followed by a
   separately regularized and capped minor-control residual model. The table
   therefore screens the structural alpha and illustrates the value of minor
   variables; it is not a direct cross-validation score for the final staged
   estimator.

## Repeat-candidate diagnostic

The resolved-identity consecutive-cycle sample reproduces at 77 observations.
Surname-only unresolved identities are excluded. Prior WAR-style CMO has
essentially no association with the same candidate's next-cycle WAR-style CMO
(Pearson 0.039, p=0.738; Spearman -0.014, p=0.901). In the same sample, prior
WAR-style CMO has a positive association with next-cycle raw ticket gap
(Pearson 0.293, p=0.010; Spearman 0.221, p=0.054).

This is a substantive limitation, not a failed arithmetic check. The output
is validated as a structural residual for a candidate-cycle. It is not
validated here as a durable personal effect, an independently identified
candidate contribution, or literal wins above replacement. Career-pooled
values should retain that caution.

## Provenance and tests

The provenance hashes for all three declared input files and the builder match
the current files. The manifest records alpha 100, the 3-point demographic cap,
and the 2-point effort cap.

Commands run:

```text
python scripts/validate_agent_workflow.py
python -m pytest scripts/tests/test_cmo_war_analogue.py -q
python -m pytest -q
```

Results:

- Agent workflow validation passed.
- Focused tests: 6 passed.
- Full suite: 378 passed, 11 warnings.

I also ran an independent in-memory reconstruction (without invoking the
write-producing builder) of the upstream joins, baseline selection, all four
arithmetic identities, caps, candidate orientation, tournament, and
repeat-candidate sample. All checks passed. The warnings in the full suite are
existing SWIG deprecations, pandas future warnings, and mixed-type CSV warnings;
none is specific to this model.

## Release decision

**PASS WITH NON-BLOCKING LIMITATIONS.** The contracted analogue is internally
correct and faithful to the declared adaptation of the Split Ticket framework.
Downstream work may use v4 as a retrospective candidate-cycle residual, but it
must preserve the state-ticket fallback label and must not characterize the
repeat-candidate evidence as validating a stable, causal, or forecast-ready
candidate-quality effect.
