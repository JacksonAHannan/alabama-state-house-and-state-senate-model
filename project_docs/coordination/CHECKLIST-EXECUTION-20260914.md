# Checklist execution, 2026-09-14

Continuation of `CHECKLIST-EXECUTION-20260911.md`. The 2026-09-11 session ended
mid-task on a provider rate limit immediately after the first caucus builder run;
nothing from that work was committed. This record restates the agreed scope and
tracks its execution.

## Agreed scope (owner grill, 2026-09-11, Q1–Q20)

The owner reframed the project as a portfolio piece, not published research.

- **Rigor (Q1b, Q2):** reproducible commands, enforced release gates and hash
  manifests, stated limits. Seventeen checklist items are to be retired with an
  explicit out-of-scope disposition and Phase 7 replaced by a product roadmap.
- **Ideology and caucuses (Q3c, Q4a, Q9b, Q10a, Q11a, Q12b, Q13a, Q19a, Q20):**
  rebuild from the current v3 evidence layer, using all channels; person-level
  career profiles over the eight issue families; ≥30% of features observed; k by
  resampling stability; labels proposed from the profiles and owner-approved;
  universe all Democratic general-election candidates 1994–2022 including
  uncontested; cycle WAR plus career cumulative WAR attached after clustering;
  one merged Democrats-only page, `caucuses.html` and CMO v4 retired.
- **Historical Alabama WAR (Q5, Q14, Q18):** v3 stays the single fixed reference;
  no era refits. Replace "backcast" wording with the fixed-reference statement
  and add career cumulative WAR to the page and downloads.
- **Forecast (Q6, Q15b, Q16a, Q17a, Q7):** identity-match the 2026 roster to
  prior Alabama races; each matched candidate's most recent raw gap enters
  through v3's fitted decaying-lag coefficient as the headline; fundamentals-only
  retained as a comparison scenario with both 2022-holdout MAEs and the owner's
  override reasoning printed; refresh the generic-ballot snapshot with a recorded
  as-of date.
- **Order:** ideology → forecast → historical wording and career WAR → hygiene
  and a single republish → checklist and roadmap.

## Checkpoint 1 (2026-09-15 01:15Z) — ideology rebuild

Accepted: `ideology-09`, `ideology-10`. Checklist 52/82.

Run `AL-DEM-CAUCUS-V1-675DE69CDA4A3D5513AF` on
`AL-HIST-WAR-V1-0E018273EBEDEEEFAD75`: 589 Democratic people, 431 with issue
evidence, 262 grouped; 776 candidate-cycles of which 266 have no contested
general election and stay unscored. k=5, silhouette 0.300, bootstrap ARI 0.845.

Material corrections made during execution:

1. **Specification defect in the unfinished 2026-09-11 build.** It clustered on
   30 features (families plus 22 primitive axes) — Q10 option (c), not the
   chosen (a). Rebuilt on the eight families, which also dominates on every
   diagnostic (262 people vs 198, silhouette 0.300 vs 0.208). Cross-spec ARI is
   0.262, so the deviation was material; the axis-augmented fit is retained as a
   recorded sensitivity. Note for the owner: the excluded axes are not free —
   55% of signed evidence rows sit on axes with no family loading, including tax
   burden, gun access, public spending, education funding and voting access.
2. **Era sensitivity added.** ARI 0.334 under within-era standardization: era
   level, and the era-specific evidence channels behind it, explain much of the
   partition. Disclosed on the page and in the audit; every person's
   era-normalized assignment is published beside the primary one so the
   disagreement is inspectable.
3. **2022 identity gap surfaced.** 22 Democratic people (19 grouped) have only a
   source stub (`GSL019DHAL`) in both the canonical and evidence layers. No name
   was invented: they are listed by their factual seat, flagged unresolved and
   counted on the page. This is the same defect family as open item
   `ideology-03`.

Owner decisions taken this checkpoint: the five proposed labels were approved as
proposed, and the raw career-profile partition (not the era-normalized one)
remains the published headline.

Retired in the cutover: `build_democratic_transition_page.py`,
`build_democratic_transition_page_v2.py`, `build_ideology_performance_page.py`,
`build_caucus_analysis_page.py`, `build_ideology_thesis_page.py`,
`analyze_democratic_ideological_clusters.py` and their three test modules.
`docs/caucuses.html` becomes a redirect at the next publish.

Verification: 18 focused tests pass; the page was driven in a real browser at
1280 px and 390 px (no horizontal overflow, measure toggle, search, group filter,
row selection and the era-normalized disclosure all exercised).
`test_published_site_consistency.py::test_public_ideology_and_caucus_routes_are_merged`
is marked `xfail(strict=True)` until the single republish, so it will fail loudly
the moment `docs/` is refreshed and the marker is not removed.

Open in this phase: nothing. Next: forecast WAR carry-forward.
