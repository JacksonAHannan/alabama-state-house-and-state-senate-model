# Alabama roll-call and ideology pipeline

## Source policy

LegiScan API JSON session archives are the structured ingestion source. ALISON,
the Alabama Legislature's official system, is the authority used to verify a
sample of bills, vote totals, member votes, and ambiguous records. Retain the
LegiScan and state links supplied in each record. LegiScan data are attributed
under CC BY 4.0.

Only recorded roll calls are observable. Voice votes and other unrecorded
procedures must remain missing; they are not unanimous votes.

## Ingestion

1. Register for a free LegiScan account.
2. Download the API JSON ZIP for every Alabama regular and special session from
   2010 through the latest available 2026 session.
3. Put the untouched ZIPs in `data/raw/legiscan/alabama/`.
4. Run `python scripts/import_legiscan_alabama_rollcalls.py`.
5. Run `python scripts/load_legislative_warehouse.py` to transactionally load
   the constrained source tables and reviewed identity links. The generated
   CSVs remain compatibility exports during migration.
6. Review `legiscan_rollcall_qa.csv` and manually verify a stratified sample
   against ALISON, including close votes, special sessions, and every era.

The normalized output separates bills, roll calls, legislators, and individual
votes. It also creates conservative exact-name candidate suggestions within an
eight-year pre-election window for manual review. Party is deliberately not a
matching key because Alabama legislators sometimes changed parties. Chamber,
district history, name collisions, and temporal plausibility still require
review. Stable LegiScan `people_id` values—not names—are the analytical
identifier after reconciliation.

## Building ideological measures

The first model should estimate chamber-specific latent ideal points from
substantive, contested Yea/Nay votes. Exclude attendance states, voice votes,
purely ceremonial measures, and near-unanimous votes that provide negligible
ideological information. Keep the exclusion rules and sensitivity thresholds
versioned rather than hand-selecting bills based on outcomes.

Estimate House and Senate separately. Orient every scale so larger values mean
more conservative voting, using party caucus means only to fix the otherwise
arbitrary sign. Link adjacent sessions through returning legislators, with
uncertainty increasing where member overlap is weak. Do not compare raw scores
across chambers or disconnected eras until the linking diagnostics support it.

For each legislator-session, derive:

- ideal point and uncertainty;
- percentile and distance from the same-session caucus median;
- ideological extremity (absolute distance from the chamber median);
- party-loyalty and opposite-party voting rates on contested votes;
- participation rate; and
- issue-specific voting summaries built from documented bill classifications.

The implemented first-pass ideal point is a descriptive one-dimensional PCA of
centered votes within each chamber and two-year election cycle. It includes only
HB/SB roll calls with at least two members and 2.5% of recorded Yea/Nay votes on
the minority side, and requires 20 observed votes per legislator. This is a
useful exploratory ordering, but it should be called a chamber-cycle voting
score—not DW-NOMINATE—until a probabilistic item-response model, uncertainty,
session linking, and stability validation are complete.

Roll calls whose reported aggregate total does not equal the parsed individual
vote count are quarantined from scoring pending ALISON review.

For electoral modeling, join only measures observed before that election's
cutoff date. First-term challengers have no legislative score and require an
explicit missingness indicator; they must not be assigned a caucus-average
score silently. Test these features out of sample against candidate margin
overperformance, retaining them only if forward-cycle validation improves.

## Issue-position matrix integration

Roll calls are behavioral evidence, not automatically plain-language policy
positions. Classify bills using title, description, subject, sponsor, and bill
text, then manually validate high-impact and ambiguous classifications against
ALISON. Preserve bill IDs and vote dates in the evidence ledger. Conflicts with
campaign statements should be displayed as separate evidence types rather than
collapsed into a single undocumented label.

Run `python scripts/build_legislative_issue_review_queue.py` to create keyword-
nominated records for human review. Its `candidate_issues` field is a search aid,
not a substantive classification. Reviewers must separately confirm the issue,
whether the vote was substantive, and whether Yea represents the progressive,
conservative, mixed, or procedurally indeterminate position.

## Bill-text and local-model workflow

1. `python scripts/build_legiscan_bill_text_manifest.py` extracts every versioned
   document URL and hash from the session archives.
2. `python scripts/download_legislative_bill_text_pilot.py --min-year 2023`
   selects a stratified issue pilot, downloads PDFs, records SHA-256 hashes, and
   extracts page-labelled text.
3. `python scripts/classify_legislative_rollcalls_ollama.py` runs Qwen 3.5 9B and
   Ministral 3 8B with deterministic, schema-constrained prompts.
4. `rollcall_llm_consensus_review.csv` prioritizes disagreements and unsupported
   quotations. Model agreement never sets `eligible_for_automatic_stance`.
5. A researcher codes `human_issue_code`, `policy_direction_of_yea`, and
   `substantive_vote` in the review queue after checking the motion and source.
6. `python scripts/build_focal_legislator_crosswalk.py` creates the stable-person
   identity review file. Only rows marked `reviewed` may be joined.
7. `python scripts/build_candidate_rollcall_positions.py` emits sourced candidate
   position evidence only where both the identity and roll-call code were reviewed.

Legacy ALISON `alisondb` document URLs currently return HTTP 403, and the public
LegiScan text endpoint also rejects unauthenticated downloads. Recent Legislature
PDFs are available directly. Older bills may therefore require an authenticated
LegiScan API/text workflow, restored official URLs, or manual retrieval. Until
then, title and synopsis metadata can nominate old bills for review but cannot be
represented as full-text classification.
