# CMO and Candidate Quality Index v5 validation

**Task:** `VALIDATE-CMO-CQI-V5-001`
**Validated:** 2026-08-21
**Verdict:** **PASS**

The repaired v5 build passes direct-score arithmetic, source replacement,
model-local identity, structural and lambda selection, ridge estimation,
uncertainty/status, temporal safety, named-case, subgroup, provenance, and
determinism checks. The model now publishes 509 races, 1,018 candidate-cycle
rows, and 879 candidate effects.

## Direct scores and replacement levels

I independently reconstructed the same-cycle ticket from canonical statewide
office and federal district inputs. All 509 race rows satisfy:

```text
direct_cmo = legislative_dem_margin - selected_ticket_margin
```

The maximum arithmetic error was `1.42e-14`; federal-versus-state-fallback
source selection matched on every row. The 23 cycle/chamber/source replacement
means reproduce from the 508 fit-eligible races with maximum error `1.78e-15`,
and eligible groups center to numerical zero. All 1,018 candidate direct scores
remain exactly D/R zero-sum.

## Model-local identity repair

Literal commas are now used as evidence for `Last, First` display order before
normalization. The identity audit found zero candidate-effect IDs assigned to
multiple races in the same cycle after collision splitting.

The two required repaired cases are correct:

- `Boyd, Barbara Bigsby` and the three `Barbara Bigsby Boyd` rows now share
  `ALNAME-BARBARA-BIGSBY-BOYD`, four appearances, and pre-election appearance
  counts 0, 1, 2, and 3.
- `Hammett, Seth` and `Seth Hammett` now share `ALNAME-SETH-HAMMETT`, two
  appearances, and pre-election counts 0 and 1.

Surname-only rows remain race-specific unresolved, and same-cycle normalized
name collisions remain chamber/district split. A separate scan of comma-form
rows with reverse-form matches found no remaining mismatch within the scored
panel.

## Structural and quality selection

After rebuilding the repaired identity graph, the implemented repeat-validity
gate selects `cycle_centered`: it has the highest eligible repeat-candidate
Spearman correlation, 0.360. The implemented seen-candidate forward gate
selects ridge penalty 1: 129 seen-candidate races have MAE 13.140 versus 14.925
for zero and Pearson correlation 0.525 (`p = 1.71e-10`). Published race rows
agree uniformly with both choices.

The level-prediction diagnostic for prior cycle-centered scores remains weaker
than zero (MAE 17.212 versus 15.231). This is not an arithmetic defect: the
declared structural gate prioritizes repeat rank persistence, while the quality
penalty gate separately tests forward prediction. That distinction should
remain explicit whenever v5 is summarized.

## Ridge effects, uncertainty, and identification

I independently reconstructed the 509-by-879 signed candidate design, ridge
solution, effective-degrees-of-freedom residual scale, diagonal SEs, intervals,
candidate differentials, and unexplained race residuals. Maximum discrepancies
were:

- candidate effects: `3.55e-15`;
- candidate SEs: `5.33e-15`;
- race candidate differentials: `1.07e-14`.

The graph audit independently identifies 606 effects belonging to fully
isolated one-race pairs. The published set matches exactly. Every such row has
`quality_identification = pair_differential_only` and `quality_status =
uncertain`; none retains an unsupported directional candidate label. Connected
effects are labeled `candidate_network`. Reliability remains bounded in
`[0,1]`.

## Temporal safety

Current same-cycle federal margin is used only in the ticket baseline. The
structural feature sets contain prior presidential margin, completed prior
presidential swing, and optionally demographics; no current federal-derived
lag appears.

I refit every pre-election fold using only cycles earlier than the scored
cycle. All published pre-election effects, SEs, appearances, and source labels
reproduce; maximum effect and SE discrepancies were `3.55e-15`. There were zero
future/same-cycle appearance violations, and every first-cycle candidate has
zero prior appearances with `no_prior_race`.

## Named cases and subgroup behavior

- **Mike Curtis:** direct CMO is +19.53 in 2010 and +10.53 in 2014. CQI is
  +3.63 with interval -12.46 to +19.71, correctly `uncertain`; the 2014
  pre-election estimate uses only 2010.
- **Johnny Mack Morrow:** the 2014/2018 full-name pair shares a resolved effect
  and remains uncertain. The two surname-only 1998 Morrow rows remain separate,
  pair-differential-only identities.
- **Barbara Bigsby Boyd:** all four full-name rows are present in
  `cmo_v5_case_studies.csv`, share CQI +4.07, and remain uncertain. Their direct
  scores are +30.07, +12.60, +30.26, and +8.77.

Candidate/effect outputs reconcile across party, House/Senate, era, fallback
source, incumbency, and singleton/network identification. Party symmetry means
remain close (-0.170 Democratic, +0.244 Republican at effect grain); the five
resolved party switchers explain why party-group counts can exceed unique
effect count.

## Provenance and determinism

The manifest now includes hashes for canonical features, canonical candidates,
district office baselines, federal district baselines, the imported v2 builder,
the v5 builder, and all seven non-manifest CSV outputs. Every recorded hash
matches current bytes. Configuration rows use a separate `value` field and
leave `sha256` empty.

The imported v2 Python dependency is recorded with a valid hash, though its
`record_type` is `input` rather than `code`; this is a harmless catalog-label
inconsistency, not a reproducibility gap.

Two successive complete rebuilds produced the identical aggregate SHA-256
`f7e0c428e54dd60d40036ea5b78ae650290df07c9b11dd112ff747031f80068a`
across all v5 CSV outputs and the methodology report.

## Commands run

```text
python scripts/rebuild_cmo_candidate_quality_v5.py
python -m pytest scripts/tests/test_cmo_candidate_quality_v5.py -q
python scripts/validate_agent_workflow.py
```

I also ran independent pandas/NumPy source arithmetic, identity/collision,
ridge, pre-election, isolated-component, case-study, subgroup, and hash audits.

Results:

- focused suite: **7 passed**;
- workflow validation: passed;
- independent arithmetic, identity, selection, ridge, temporal, case, and
  provenance checks: passed;
- deterministic rebuild: passed.

## Release decision

**PASS.** CMO/CQI v5 satisfies the validation contract. No blocking finding
remains.
