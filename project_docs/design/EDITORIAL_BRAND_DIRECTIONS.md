# Jackson Hannan editorial brand directions

> **Documentation status — 2026-09-05:** Historical design exploration. The alternatives and recommendations below do not override the implemented shared theme or current product controls. Inspect dashboard/blue_oxblood_theme.css, dashboard/war_explorer.css and scripts/site_brand.py from the repository root; follow AGENTS.md before design changes. This audit does not select a new visual direction.

## Purpose

The site should feel like an authored Alabama elections publication with data
tools, not a generic analytics dashboard. The working identity is **Jackson
Hannan** with the social handle **@electionsjack**. The supplied portrait is the
primary human mark; it replaces abstract logos, fake institutional branding,
and decorative AI-generated imagery.

## Reference audit

The references contribute different structural lessons:

- **State Navigate:** clear product categories, election-specific utility, and
  an identity grounded in state legislative coverage.
- **The Argument:** strong article hierarchy, readable long-form argument, and
  an editorial voice that lets analysis lead.
- **Silver Bulletin:** compact model navigation, restrained archive rows, and a
  useful bridge between frequently updated trackers and explanatory articles.

No direction reproduces a reference site's visual identity, logo, page
composition, or proprietary graphic treatment.

## Shared brand grammar

- Portrait-derived palette: oxblood, copper, parchment, charcoal, and muted
  slate blue. Party colors remain semantically blue and red inside charts.
- The portrait appears as a real byline/identity device, never as a full-bleed
  decorative hero.
- `@electionsjack` is visible in the masthead and authorship line.
- Page titles are literal product names. Subheads state scope, definitions, or
  inputs without advancing a thesis. Analytical findings belong in labeled
  results sections and figure captions, not in promotional headlines.
- Rules, ledgers, captions, and tables provide hierarchy. Avoid gradients,
  glass panels, rounded card grids, glowing shadows, decorative pill overload,
  and interchangeable “insight” callouts.
- Forecast, CMO, ideology, candidate, and methodology pages share navigation
  and tokens while retaining layouts appropriate to their jobs.
- Redesigns preserve product controls and content: maps, district selection,
  chamber tabs, cycle selection, model toggles, candidate detail, and tables are
  functional requirements rather than optional decorative elements.
- Typography uses familiar system faces: Arial/Helvetica for interface and
  headings, Georgia for limited long-form passages and tabular display values,
  and Consolas/Courier for compact metadata. No remote display-font dependency
  is required.

## Palette A: Powder blue and oxblood — recommended

Portrait-derived powder blue, dark oxblood rules, Newsreader serif, restrained
monospaced labels, and a square portrait. The pale blue is the dominant page
ground rather than an accent. Off-white blue panels distinguish maps and figures.

## Palette B: Gray blue and copper

A quieter gray-blue ground, compact sans-serif hierarchy, copper rules, charcoal
text, circular portrait, and denser tables. It is the most neutral and
utilitarian option while still connecting to the photograph.

## Palette C: Deep slate

Slate-navy ground, copper accents, condensed display type, and a bordered round
portrait. It creates the strongest memorability and works especially well for
election-night products, but sustained methodology reading is less comfortable.

## Page templates

- **Forecast:** map-first split layout, chamber ledger, races-to-watch table.
- **CMO:** metric ledger, full-width candidate plot, selected-race evidence rail.
- **Ideology:** thesis-led headline, transparent sample counts, absolute-position
  plot, and figure captions that distinguish association from causation.
- **Candidate atlas:** durable identity rail plus a chronological evidence record.
- **Methodology:** narrow reading column, numbered contents rail, equations and
  caveats treated as editorial figures rather than dashboard components.

## Recommendation

Use **Field Notes** as the site-wide base, borrow **Election Ledger** density for
forecast tables and selectors, and reserve **Night Desk** as a possible election-
night mode rather than the permanent reading theme.
