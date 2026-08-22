# CMO v4 WAR-style site validation

**Task:** `VALIDATE-CMO-WAR-SITE-001`  
**Validated:** 2026-08-21  
**Verdict:** **PASS**

The rebuilt CMO and ideology release candidate publishes the approved v4
WAR-style residual consistently. The four prior blockers are resolved, the
public numerical payloads reconcile to the processed v4 outputs, and the
focused and full test suites pass.

## Remediation revalidation

- `docs/cmo.html section.validation` renders the real cycle-held-out tournament
  results: barebones MAE/RMSE ranges from 19.4/23.8 to 18.8/23.4, and full-model
  results range from 17.3/21.7 to 16.8/21.3. The construct checks have populated
  names, `n=77`, and values 0.039 and 0.293. No zero placeholders or blank names
  remain.
- After selecting a district, `.racebox-sub`, `.group-head`, and
  `.racebox-comparison` consistently say `structural expectation` or
  `Structural expected margin`. The separate top-of-ticket box remains labeled
  as the WAR ticket baseline.
- `docs/ideology-performance.html #measure` defines the observed ticket gap and
  subtracts the predicted structural gap. It identifies symmetric incumbency,
  era-specific downballot lag, limited demographics, and capped campaign effort
  as structural inputs, and explicitly says ideology is added only afterward.
- The literal strings `Narrower band`, `Wider band`, `Ticket alternatives
  agree`, and `Ticket direction differs` occur zero times in the CMO and
  ideology publication pages. The selected-candidate detail uses genuine v4
  decomposition and provenance fields; no synthetic range/agreement UI remains.

## Numerical and export fidelity

All eight `docs/data/cmo_v4_*.csv` files byte-match the corresponding processed
outputs: candidates, races, coefficients, components, model tournament,
construct validity, cycle diagnostics, and provenance.

The embedded CMO payload contains 1,018 unique candidate rows and joins
one-to-one to `cmo_v4_candidates.csv` by cycle, chamber, district, and party.
After the builder's two-decimal rounding, all 1,018 rows match v4 for WAR-style
CMO, raw ticket gap, lagged-partisanship adjustment, structural-base adjustment,
demographic adjustment, campaign-effort adjustment, predicted structural gap,
and career partial-pooling.

Barbara Bigsby Boyd's 2022 HD-32 Democratic score is **-2.41**, matching v4's
`-2.4131887778`; neither +48.1 nor the superseded v3 value is present.

The ideology analysis panel contains 1,018 rows, all labeled
`cmo_v4_war_residual`. Both `candidate_cmo` and `candidate_war_cmo` match the v4
candidate score by canonical candidate ID to floating-point precision.

No public page contains the stale identifiers or labels `Direct CMO`,
`candidate_context_cmo`, or `candidate_headline_cmo`.

## Browser validation

I inspected `cmo.html` and `ideology-performance.html` in headless Microsoft
Edge at a 1,425-pixel desktop client width and an exact 497-pixel mobile client
width. At both widths, document horizontal overflow is zero, the selected
district wiki-box shows structural-expectation language, the ideology measure
shows the v4 construction, no application console errors occur, and removed
pseudo-band/agreement text is absent from the rendered detail.

## Commands and results

```text
python scripts/validate_agent_workflow.py
python -m pytest scripts/tests/test_cmo_war_analogue.py scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_published_site_consistency.py scripts/tests/test_ideology_performance_page.py -q
python -m pytest -q
```

Results:

- agent workflow validation: passed;
- focused publication/model suite: **21 passed**;
- full suite: **378 passed**, 11 warnings (existing pandas/SWIG warnings).

Additional read-only Python checks decoded the embedded CMO payload, enforced a
one-to-one join to the v4 candidate export, compared every displayed component,
verified ideology-panel canonical-ID joins, byte-compared all eight public
exports, and searched the three public pages for stale terminology.

## Release decision

**PASS.** The current v4 CMO and ideology release candidate satisfies the
publication contract. No blocking or nonblocking release findings remain from
this audit.
