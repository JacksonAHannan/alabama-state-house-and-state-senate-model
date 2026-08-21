# Ideology panel-border validation

- Task: `VALIDATE-IDEOLOGY-BORDERS-001`
- Reviewer: `/root/blue_oxblood_validation`
- Candidate: rebuilt `docs/ideology-performance.html`, 2026-08-21
- Decision: **PASS**

## Browser validation

The page was inspected in headless Chrome at an effective 1280 px desktop
client width and an exact 497 px mobile client width. Computed styles confirm
visible left and right edges on every contracted panel family:

| Selector | Count | Computed horizontal edges |
|---|---:|---|
| `.thesis` | 1 | 1 px oxblood left and right |
| `.stats` | 1 | 1 px blue-gray left and right |
| `.callout` | 5 | 4 px oxblood left, 1 px oxblood right |
| `.formula` | 1 | 1 px blue-gray left and right |
| `.mini-card` | 6 | 1 px blue-gray left and right |
| `.issue-note` | 1 | 1 px blue-gray left and right |
| `.evidence-summary` | 1 | 1 px blue-gray left and right |
| `.method-grid > div` | 8 | 1 px blue-gray left and right |

The statistics and evidence-summary containers own the exterior border. Their
children use only internal left dividers where needed, avoiding doubled outer
rules. On mobile those components stack into one column; exterior edges remain
visible and internal horizontal separation remains coherent. Mini-cards and
method panels retain consistent gaps instead of collapsing into a single box.

Visual inspection found the oxblood callout edge, pale blue-gray panel edges,
nested dividers, and surrounding whitespace legible at both widths. No panel
touches or crosses the viewport edge.

## Responsive and interaction checks

- Desktop: `clientWidth = scrollWidth = 1280`.
- Exact mobile: `clientWidth = scrollWidth = 497`.
- Issue and party/baseline controls continued to rerender the evidence and
  forest views; the tested Republican forest produced 22 rows.
- Dynamic mini-card, issue-note, and evidence-summary content rendered before
  computed-style inspection.
- No application-level severe console errors occurred. The favicon request was
  excluded as the known local-server artifact.

## Tests

```text
11 passed in 2.98s
```

Commands:

```powershell
python -m pytest scripts/tests/test_ideology_performance_page.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
python -m http.server 8765 --directory docs
```

## Release decision

**PASS.** The ideology border remediation is visually coherent, responsive,
and regression-free. No selector requires correction.
