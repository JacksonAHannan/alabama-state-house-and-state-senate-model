# CMO absolute color validation

**Task:** `VALIDATE-CMO-ABSOLUTE-COLOR-001`
**Validated:** 2026-08-21
**Verdict:** **PASS**

The rebuilt public and standalone CMO pages use the approved direct linear
signed-point color scale. The corrected legend represents the same scale, all
three map modes preserve uncensored source values, and values outside the
visual range remain uncapped in accessible labels and tooltips.

## Numeric color and legend checks

I evaluated the generated page's `color(v)` function in Microsoft Edge at
desktop and exact 497-pixel effective client widths:

| Input | Rendered color | Interpretation |
|---:|---|---|
| -45 | `#d34b45` | clipped Republican endpoint |
| -30 | `#d34b45` | Republican endpoint |
| -15 | `#e39e99` | exact 50% neutral-to-Republican mix |
| 0 | `#f2f1ed` | neutral |
| +15 | `#98b4cb` | exact 50% neutral-to-Democratic mix |
| +30 | `#3d77a8` | Democratic endpoint |
| +45 | `#3d77a8` | clipped Democratic endpoint |

The generated legend is the matching endpoint-neutral-endpoint gradient:

```text
linear-gradient(90deg,
  rgb(211, 75, 69) 0%,
  rgb(242, 241, 237) 50%,
  rgb(61, 119, 168) 100%)
```

Its evenly spaced labels are `R +30`, `R +15`, `Even`, `D +15`, and `D +30`.
The former mismatched intermediate colors and +/-10 quarter labels are absent
from both generated pages.

## Modes and uncapped values

The page exposes exactly the three approved controls. `mapMetric` reads
`demWar`, `rawVsGovernor`, and `rawVsPresidential` directly; `mapRawValue`
returns that same uncensored value. The map subtitles identify the selected
measure.

As an extreme-value regression check, 1994 Senate District 25 has +119.31 in
the governor comparison. Its polygon correctly clips to `#3d77a8`, while its
accessible label and visible tooltip both report the uncapped value `119.3`.
Thus the +/-30 cap affects color only.

## Browser and responsive checks

At desktop and an exact 497-pixel effective client width in headless Microsoft
Edge:

- the corrected gradient and labels render;
- all three map controls remain visible and functional;
- `scrollWidth == clientWidth`, so there is no horizontal overflow; and
- no application JavaScript error occurs.

The only console entry was the site's unrelated missing `favicon.ico` network
404.

## Commands run

```text
python -m pytest scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
python -m http.server 8765 --directory docs
python scripts/validate_agent_workflow.py
```

Results:

- focused publication suite: **12 passed**;
- agent workflow validation: passed;
- desktop and exact-497 browser checks: passed;
- arithmetic, clipping, raw accessors, tooltip fidelity, and legend agreement:
  passed.

## Release decision

**PASS.** The direct linear CMO color release satisfies the contract. No
blocking or non-blocking finding remains from this audit.
