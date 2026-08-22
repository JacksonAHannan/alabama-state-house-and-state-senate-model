# CMO explorer views validation

**Task:** `VALIDATE-CMO-VIEWS-001`
**Validated:** 2026-08-21
**Verdict:** **PASS**

The rebuilt CMO explorer exposes exactly the approved three map measures,
defaults to absolute CMO, updates correctly for both raw comparison views, and
places the selected legislator identity and CMO before the race and ticket
context boxes at desktop and narrow widths.

## Map controls and default

Both `docs/cmo.html` and the standalone CMO artifact contain exactly three
`data-map-mode` controls:

1. `absolute` — CMO;
2. `governor` — raw overperformance versus governor; and
3. `presidential` — raw overperformance versus the previous presidential
   margin.

Only the absolute control is active on initial load. The initial rendered map
subtitle is `CMO, absolute margin points`. No former relative, within-cycle,
raw-ticket, or career-pair map control is present.

## Functional browser checks

I inspected the page in headless Microsoft Edge at a 1,425-pixel desktop client
width and an exact 497-pixel narrow client width. At both widths:

- all three controls are visible;
- clicking each control leaves exactly that control active;
- the subtitle changes to the selected measure;
- the map is rerendered rather than retaining a stale scale;
- absolute, governor, and presidential views produce respectively 41, 38, and
  31 distinct rendered fill colors in the initial section; and
- horizontal overflow and application console errors are both zero.

The accessible district labels also change numerically with the measure. For
example, initial-cycle District 37 reports Democratic overperformance of 14.0
under CMO, 24.8 versus governor, and 45.8 versus the previous presidential
margin. This confirms that the alternate buttons change the mapped values, not
only their labels.

## Selected-legislator hierarchy

Selecting the first candidate row renders a `.candidate-headline` containing
the legislator name, party/district, CMO, and percentile before `.racebox` in
DOM and visual order. The race result wikibox follows it, and the district
top-of-ticket `.baseline-context`/`.baseline-wikibox` is nested later inside
that race box.

For the checked candidate, Nathaniel Ledbetter and `+34.6 CMO` begin at
approximately y=1,102 desktop / y=2,419 narrow; the race box begins around
y=1,297 / y=2,614, and the top-ticket context begins still later. The same
ordering is explicit in both the public and standalone generated HTML.

## Tests

Commands run:

```text
python -m pytest scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
```

Results:

- focused publication suite: **12 passed**;
- agent workflow validation: passed.

## Release decision

**PASS.** The simplified map views and selected-candidate hierarchy satisfy the
release contract at desktop and narrow widths. No blocking or nonblocking
finding remains from this audit.
