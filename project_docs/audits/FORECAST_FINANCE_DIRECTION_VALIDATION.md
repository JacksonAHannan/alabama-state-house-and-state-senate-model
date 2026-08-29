# Forecast finance-direction validation

Date: 2026-08-28

Task: `VALIDATE-FORECAST-FINANCE-DIRECTION-032`
Validated build: `8cad753f1720c2a1b107`

## Verdict

**APPROVE** the model package and staged web candidate for publication. The repaired headline now measures direct Democratic-minus-Republican fundraising strength, its contribution has the correct direction in every finance-complete contest, and the staged dashboard and methodology faithfully present that construct.

This approval is about internal consistency and release safety, not causal identification. Fundraising remains correlated with incumbency, donor expectations, and candidate strength, and the complete candidate adjustment has only one forward Alabama holdout.

## Independent numerical checks

I independently joined the headline scenarios to `2026_candidate_finance_reconciled.csv` by chamber, district, and party, recalculated

`log1p(D receipts / 50000) - log1p(R receipts / 50000)`,

and reconstructed every additive margin.

- Headline contests: 48 unique chamber-district keys.
- Finance-complete contests: 45.
- Candidate receipt/status mismatches against the reconciled finance table: 0 for Democrats and 0 for Republicans.
- Maximum independently recalculated log-gap difference: `2.22e-16`.
- Finance sign reversals: 0 of 45.
- The fitted contribution-to-gap ratio is positive and constant at approximately `4.91785256` across all nonzero complete gaps.
- Maximum headline decomposition error was floating-point noise (`1.07e-14`).
- The headline rows match the selected `uniform_polling_federal` / `polling_federal_plus_incumbency_fundraising` source rows to floating-point precision.

The three incomplete contests are HD-82, HD-99, and SD-23. Each retains the observed Democratic receipt total, a missing Republican receipt observation, a missing relative-fundraising gap, `finance_complete=False`, the fallback `polling_federal_plus_incumbency` model, and exactly zero fundraising adjustment. Missingness was not converted to zero receipts.

### Senate District 7

Independent values:

- Jared Sluss (D): `$19,146.16`.
- Sam Givhan (R): `$370,509.84`.
- Direct D-minus-R log fundraising gap: `-1.8052453547`.
- Democratic fundraising contribution: `-8.8779304882` points.
- Headline Democratic margin: `-10.3800415408` (`R+10.4`).
- Conditional Democratic win probability: `0.0654371905`.

The contribution therefore points toward the higher-raising Republican, as required.

## Manifest and methodology

Every declared input, code-input, and output SHA-256 in `post2016_headline_v1_manifest.json` matches the current file. All declared output row counts match. Independently hashing the stable manifest body reproduces build ID `8cad753f1720c2a1b107`.

The manifest, model package, model note, dashboard payload, and staged methodology agree on:

- source scenario `uniform_polling_federal`;
- selected specification `polling_federal_plus_incumbency_fundraising`;
- methodology version `post2016_headline_v1_1`;
- 45 of 48 finance-complete races;
- Student-t probability family, five degrees of freedom, and 5.75-point scale;
- 50,000 simulation draws;
- direct observed relative fundraising rather than residualized fundraising as the headline construct;
- one 2018-to-2022 forward holdout and the noncausal interpretation of finance.

The residualized model appears only as a clearly labeled historical sensitivity that scored better on the single holdout but is not promoted as relative fundraising strength.

## Staged-page integrity

Headless Chrome 151 checks at 1440px and 390px found zero horizontal overflow and zero severe console entries on both staged pages.

The forecast payload reports build `8cad753f1720c2a1b107`. All 48 modeled contest margins, probabilities, finance steps, candidate receipt totals, and finance statuses reconcile to the headline scenario file with zero mismatches. The three incomplete contests display a zero finance step.

The rendered SD-7 detail shows:

- `$19,146 raised` for Jared Sluss;
- `$370,510 raised` for Sam Givhan;
- `Relative fundraising strength` as `R+8.88`;
- a running and headline margin of `R+10.4` and a `7% D chance`.

The staged methodology explicitly defines the direct log receipt gap, states the 45/48 coverage, explains the missing-finance fallback, and does not present the residualized sensitivity as the headline.

## Commands and tests

```powershell
python scripts/validate_agent_workflow.py
python -m pytest scripts/tests/test_post2016_polling_cmo_forecast.py scripts/tests/test_forecast_dashboard.py -q
```

Results:

- Agent workflow validation passed.
- Focused forecast/model/dashboard suite: `27 passed in 7.12s`.

I also ran `scripts/tests/test_published_site_consistency.py` as an extra pre-publication diagnostic. Its publication-byte-match assertion fails because `docs/data/` still contains the prior forecast package. That is expected at this staged gate: both upstream contracts explicitly prohibit publication to `docs/` before independent approval. It is not a defect in the staged candidate. The normal publication rebuild must refresh `docs/` and rerun that test before release.

## Release condition

Publish through the normal dashboard build so the approved model files and staged pages replace the intentionally stale `docs/` copies, then rerun the publication-consistency test. No model or staged-page blocker remains.
