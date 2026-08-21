# Ideology narrative and dynamic-chart validation

- Task: `VALIDATE-IDEOLOGY-DYNAMIC-001`
- Reviewer: `/root/blue_oxblood_validation`
- Candidate: final remediated `WEB-IDEOLOGY-DYNAMIC-001`, 2026-08-21
- Decision: **PASS**

The rewritten narrative and dynamic ideology charts are approved for
publication.

## Final tooltip revalidation

The prior contrast blocker is resolved. At both an effective 1280 px desktop
width and exact 497 px mobile width, pointer hover and keyboard focus produce:

```text
#tip foreground: rgb(255, 255, 255)
#tip background: rgb(91, 35, 51)
contrast ratio: 12.12:1
```

Every visible `#tip b` descendant also computes to white at 12.12:1. Pointer
and keyboard-visible states both pass WCAG AA and AAA. Keyboard focus remains
on the selected dot, the tooltip is visible, and no document overflow or severe
application console error occurs.

## Complete release gate

- The embedded analysis payload is deeply identical to the approved payload
  and prior staged analysis artifact; no analytical value changed.
- Narrative claims agree with the approved absolute-ideology, mediator,
  selection, issue, robustness, and era outputs.
- All nine party/outcome combinations update points, counts, y-axis labels,
  status text, and Democratic/Republican slopes correctly:

| Outcome | Both | Democrats | Republicans |
|---|---:|---:|---:|
| Federal baseline | 360 | 187 | 173 |
| Context CMO | 407 | 209 | 198 |
| Previous presidential | 389 | 199 | 190 |

- Pointer and keyboard point disclosure is functional and labeled.
- Existing forest, candidate-evidence, district-fit, and era controls rerender
  coherently.
- Normal transitions work; emulated reduced motion computes to `0s` transitions
  and `none` animations.
- Desktop and exact-497 px mobile layouts have zero horizontal overflow.
- Panel borders, nested dividers, local/fragment links, and computed text
  contrast pass.
- Focused tests pass: **11 passed in 3.02s**.
- The earlier complete suite passes: **367 passed**, 11 warnings.

## Commands

```powershell
python -m pytest scripts/tests/test_ideology_performance_page.py scripts/tests/test_site_brand.py -q
python -m pytest -q
python scripts/validate_agent_workflow.py
python -m http.server 8765 --directory docs
```

## Release decision

**PASS.** No unresolved model, narrative, interaction, responsive, or
accessibility finding remains from this gate.
