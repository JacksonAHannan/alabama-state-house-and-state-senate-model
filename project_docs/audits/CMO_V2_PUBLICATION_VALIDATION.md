# CMO v2 publication validation

- Task: `VALIDATE-WEB-CMO-V2-001`
- Reviewer: `/root/blue_oxblood_validation` (`validation_release`)
- Candidate: final remediated staged `WEB-CMO-V2-001`, 2026-08-21
- Decision: **PASS**

The staged CMO v2 dashboard and methodology are approved for publication.

## Final blocker revalidation

- `docs/cmo.html` now says that within-cycle CMO removes the chamber-cycle
  **median**. The stale mean wording is absent from both the rendered page and
  builder.
- All 63 rendered 2010 district contexts use `Ron Sparks` and
  `Robert Bentley` for Governor.
- All 63 rendered 2010 district contexts use `James H. Anderson` and
  `Luther Strange` for Attorney General.

## Complete release gate

- All 1,018 candidate rows and 509 races match the approved CMO v2 outputs.
- The four estimands remain distinct, and all 16 cycle/chamber controls and
  seven map modes are present and functional.
- Real House and Senate SVG maps, district/candidate selection, race wiki-box,
  and baseline toggles work.
- At an exact effective 497 px Chrome client width, the CMO page has
  `clientWidth = scrollWidth = 497`; map controls wrap and detail panels remain
  contained.
- Identity cautions appear on exactly the 387 surname-only unresolved rows and
  on none of the 631 resolved rows.
- Methodology fragments and local downloads resolve, including the CSV run
  manifest.
- No rendered legacy Fundamentals+ claims, remote display fonts, application
  console errors, or computed contrast failures remain.
- Focused publication tests pass: **12 passed in 0.74s**.
- The earlier complete suite passed: **367 passed** with 11 warnings.

## Commands

```powershell
python -m pytest scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
```

Additional Python audits parsed the embedded payload, verified exact 2010
office-name counts, checked canonical identity-caution assignment, and resolved
all local/fragment links. Selenium supplied responsive geometry, controls,
maps, contrast, and console checks during the full gate.

## Release decision

**PASS.** The CMO v2 public dashboard and methodology may be published. No
model or publication caveat remains from this validation task.
