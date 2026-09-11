# Documentation architecture audit — 2026-09-05

## Result and scope

The remaining documentation was inventoried against the four-product architecture.
The misleading root entry points, duplicate roadmap, standing-team assumptions,
and selected old readiness/methodology instructions were corrected or explicitly
retired. Historical findings and validation evidence were not rewritten as current
claims, and no model, warehouse, source dataset or public page was rebuilt.

Audit ID: `DOCS-ARCH-2026-09-05`. Inventory/disposition work recorded at
`2026-09-06T04:17:01Z` (September 5 locally). Code baseline:
`88878b9`, existing dirty worktree. This is a documentation-maintenance run, not
a model/data validation run or independent scientific release approval.

The [machine-readable inventory](documentation_inventory_2026_09_05.csv) covers
the **751 pre-existing artifacts** discovered by `rg --files`: 466 Markdown or
reStructuredText documents and 285 text evidence/extraction files. The discovery
respects repository ignore rules and excludes dependencies, `.git`, and
`requirements.txt`; it is not a forensic search of ignored archives or external
companion repositories. Text extracts were hash-inventoried and preserved, not
semantically revalidated as instructions.

Every inventory row records a disposition, current authority route, action,
pre/post SHA-256, and reference-scan scope. Reference flags are conservative
basename matches in scripts and processed/public JSON manifests: they are useful
warnings, not proof that an unflagged document has no consumer or registered
warehouse lineage. Historical/generated evidence was preserved conservatively.

## Findings and changes

| Finding | Disposition |
|---|---|
| Root README still called the legacy CMO dispatcher canonical | Replaced with four-product routing and commands explicitly identified as checks; documented publish/rebuild distinctions |
| Repository layout claimed only CMO v4 belonged in public exports | Removed that stale rule; pointed to current routes and warned that the hygiene audit checks only limited legacy patterns |
| Scaffold-era roadmap duplicated the new phased checklist | Removed the obsolete phase list; retained a small redirect at its existing path |
| Warehouse architecture mixed migration snapshots with apparent live coverage and a long command list | Marked historical domain sections as migration snapshots and the commands as a reference catalog, not a wholesale rebuild recipe |
| Coordination guidance assumed a standing agent team and recurring all-product rebuild cycle | Made the workflow conditional on explicitly authorized parallel work; retained serialized writes and independent review where required; removed the standing cadence |
| Pre-rebase AGENTS backup could be mistaken for active instructions | Marked it archival and routed to the actual root AGENTS.md; retained its original body for recovery |
| Earlier readiness, probability, finance and environment documents competed with current routing | Added scoped historical notices without changing old measurements; current contracts remain linked from the pipeline index |
| Full-candidate/Vote Smart coverage snapshots looked like current whole-product coverage | Scoped them to their component/run and linked current coverage/routing |
| Roll-call guide implied a new estimator and predictive improvement were prerequisites for descriptive evidence | Removed those blanket requirements; retained accepted eligibility, missingness and product-specific validation boundaries |
| Old implementation plans and research loop could restart completed or superseded work | Marked four dated proposals non-operative; linked the research loop to source-search closure and current task routing |
| Legacy asset registry redirected everything to CMO v4 | Replaced obsolete replacements with current routing; explicitly retained compatibility inputs rather than implying schema-compatible substitution |
| Model and component folders lacked clear reading priority | Added short folder entry points distinguishing current contracts from research, compatibility and run-specific evidence |

The inventory records **25 pre-existing document edits and 726 documents/text
artifacts preserved byte-for-byte**. Separately updated the existing legacy-asset
CSV and internal checklist evidence. Added two short folder entry points, this
audit, and its inventory. These newly created files are intentionally outside
the pre-existing-document inventory; the inventory does not hash itself.

## What was retired, and what was deliberately retained

Removed redundant instructions inside the old roadmap, README command block and
standing coordination schedule. No entire source/evidence file was deleted or
moved. The retired tracked prose is recoverable from Git history; old proposal,
backup and research bodies remain in place under explicit status notices.

All 13 pre-existing documents detected by the manifest-reference scan retain
their bytes. All 123 audit/validation records, 285 text extracts and the raw-data
README also retain their bytes. This protects old report hashes and review
evidence instead of silently “updating” a prior run.

Two exact duplicate pairs were found: the CMO model card and CMO v6 methodology
each have a matching copy under `docs/data/`. These are publication copies, not
independent maintained instructions. They were retained pending a publisher/link
review; deleting them solely for byte duplication could break a compatibility
or externally bookmarked download. The separate v5 public copy is not identical
to its local methodology and likewise requires a scoped publication review.

## How to interpret retained holdovers

- `CURRENT_METHOD_RELEASE_VALIDATION.md` concerns its August 22 CMO v6/robust
  release, not the current four-product release.
- `FORECAST_PUBLIC_CONTRACT_VALIDATION.md` concerns its August 28 build and
  selected specification; its approval does not transfer to a different manifest.
- `IDEOLOGY_WAR_HEADLINE_VALIDATION.md` concerns its August 26 staged artifact
  and hash, not every later evidence rebuild or page.
- `REPOSITORY_CLEANUP_VALIDATION.md` records the earlier cleanup. Its statement
  about canonical commands is historical; current routing takes precedence.
- Generated model reports and versioned contracts, including research-only v4,
  retain their own method/run scope. They are not promoted by this audit.
- Coordination records retain owner/reviewer evidence. The ledger currently has
  2 active, 17 review, 184 complete and 4 blocked rows; those are recorded statuses,
  not proof of running agents. No rows were mass-closed or deleted.

The four archived August 12–13 development plans/specifications reference ten
distinct script names that no longer exist (20 document/script pairs after
normalizing path separators). These are retained as historical proposal content,
not runnable instructions. The initial overly broad script-link check correctly
exposed them; verification now reports them separately and still rejects missing
script references in maintained guidance. No replacement command was invented.

## Remaining implementation work, not documentation fixes

1. Migrate the legacy dispatcher only through a scoped implementation change;
   documenting its limitations does not create an end-to-end product rebuild.
2. Review old public methodology downloads and their generator/consumer links
   before an explicitly scoped publication cleanup. Nothing in `docs/` changed.
3. Reconcile current public prose with actual manifests and resolve stale data
   dependencies through their existing product tasks. This audit does not fix or
   certify model behavior merely by correcting internal descriptions.
4. Review old active/review task records with their evidence and accountable
   owners. Passing the collision validator does not establish task completion.
5. Keep status notices and routing current when a research generator is promoted
   or a compatibility input is removed. Do not bulk-regenerate old reports just
   to replace historical language.

The existing checklist's broader script-deletion, complete command-sequence and
release-certification items remain open. Documentation inventory alone does not
meet all their acceptance criteria.

## Verification

- `python scripts/audit_repository_paths.py`: passed, all five required paths.
- `python scripts/validate_agent_workflow.py`: passed; ledger left unchanged.
- Documentation checks passed: 66 local links in changed/new documents, no
  missing non-archive script references across 466 scanned documents, all 751
  inventory post-hashes and authority routes, 12 unique legacy-registry patterns,
  and valid checklist JSON/history. Historical missing-script references are
  reported separately above rather than silently ignored or “repaired.”
- `git diff --check` passed on the changed tracked documents; line-ending
  conversion warnings are not data corruption.
- The existing checklist browser regression passed at 1440px and 320px for
  counters, history, filters, persistence, export serialization and overflow.
  Progress remains 6/82 with three snapshots; the broader task stays open.
- No internal audit/checklist reference was found in the public site or inspected
  publisher. Browser test edits were restored and the test session was closed.
- No full model test suite or data/website rebuild is part of this documentation
  pass. Those unrun checks must not be reported as passing.

Ponytail kept existing paths and reused the existing checklist, routing index and
validation tools. No documentation framework, new runtime dependency, duplicate
live roadmap or standing automation was introduced.
