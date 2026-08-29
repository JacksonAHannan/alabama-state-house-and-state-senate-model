# Forecast public-contract validation

Date: 2026-08-28

Task: `VALIDATE-FORECAST-PUBLIC-CONTRACT-034`
Forecast build: `8cad753f1720c2a1b107`

## Verdict

**APPROVE.** The two obsolete `7.08` headline-MAE assertions now derive the promoted specification and MAE from the current forecast manifest and metrics. The refreshed tests enforce the published direct-fundraising headline precisely and continue to fail if the public methodology reports a different model or value.

## Contract change

Both `scripts/tests/test_forecast_dashboard.py` and `scripts/tests/test_published_site_consistency.py` now:

1. read `selected_specification` from `post2016_headline_v1_manifest.json`;
2. require exactly one matching row in `post2016_headline_v1_forward_metrics.csv`;
3. require that row's MAE to equal the manifest's `forward_validation.mae` within `1e-12`;
4. require the public methodology's exact sentence to report that MAE rounded to two decimals; and
5. require the visible table label `Headline: direct relative fundraising`.

For the approved build, the selected specification is `polling_federal_plus_incumbency_fundraising` and the derived MAE is `8.430118180791245`, so the required public text is `8.43 points`.

No unrelated assertion was removed or relaxed. Existing model-export byte equality, forecast scenario, uncertainty, stale-language, CMO, and publication row-count checks remain unchanged.

## Disagreement sensitivity

I independently replaced the expected current methodology sentence in memory with the former `7.08` sentence. In both test modules, the manifest-derived exact assertion became false. Thus a stale or otherwise disagreeing publication still fails; the change is not a vague string-presence check.

## Commands

```powershell
python scripts/validate_agent_workflow.py
python -m pytest scripts/tests/test_post2016_polling_cmo_forecast.py scripts/tests/test_forecast_dashboard.py scripts/tests/test_published_site_consistency.py -q
```

Results:

- Agent workflow validation passed.
- Focused forecast/public suite: `34 passed in 7.27s`.

## Release recommendation

Approve the refreshed public consistency contract. It follows the manifest-selected model automatically while remaining strict about the exact published metric and label.
