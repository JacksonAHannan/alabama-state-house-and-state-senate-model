# Blind ideology review protocol

## Purpose

Independently recode election-specific ideology evidence without seeing the
candidate's identity, CMO, electoral result, district, party-performance data,
existing code, or article interpretation. The review tests reproducibility of
the hand codes; it does not ask whether the candidate overperformed.

## Permitted inputs

Use only `blind_review_pending.csv` and this protocol. Do not open the key,
prior decisions, evidence ledger, candidate memos, article, model output, URLs,
or identity-bearing files. Stop and report contamination if a candidate name,
CMO value, result, or district identifier appears in the queue.

Each queue row represents one candidate-cycle and one dimension. Multiple
evidence items may be joined with ` | `. `source_types` describes provenance
quality without exposing the original URL.

## Code scale

Use integer codes `-2, -1, 0, +1, +2`, relative to Alabama Democrats in that
election era:

- `-2`: clearly and strongly progressive on the named dimension.
- `-1`: mildly or conventionally progressive.
- `0`: genuinely mixed, centrist, internally conflicting, or insufficiently
  directional evidence.
- `+1`: mildly or conventionally conservative.
- `+2`: clearly and strongly conservative.

Do not use `0` merely because evidence is sparse. If the supplied evidence
cannot support any directional or mixed inference, leave `reviewer_code` blank,
set confidence to `low`, and write `insufficient evidence` in the note.

## Dimensions

- `economic_ideology`: taxes, spending, regulation, Medicaid, and education
  finance. Support for public investment generally points negative; fiscal
  retrenchment or anti-government positioning generally points positive.
- `social_ideology`: broad cultural positioning only. Do not duplicate a named
  gun or abortion position unless the evidence itself makes a broader claim.
- `guns_position`: gun regulation (`-`) versus gun rights (`+`). A narrow
  armed-security policy normally warrants no more than `+1` absent broader
  evidence.
- `abortion_position`: abortion rights (`-`) versus anti-abortion (`+`).
- `labor_position`: organized-labor alignment (`-`) versus anti-union or
  right-to-work alignment (`+`). Contributions or endorsements alone are
  weaker than votes, leadership, or explicit policy.
- `overall_ideological_valence`: signed synthesis of evidence that explicitly
  describes an overall orientation. Do not invent missing component positions.
  When the evidence is a pre-election Shor--McCarty percentile within the
  same-cycle Alabama Democratic chamber caucus, use a fixed rule: bottom/top
  10 percent receives `-2`/`+2`; 10th--35th and 65th--90th percentiles receive
  `-1` and `+1`; the middle 30 percent receives `0`. Boundary values enter the
  more moderate category. This threshold rule does not convert the ideal point
  into a complete issue platform.

## Confidence

- `high`: direct, temporally eligible statement, vote, bill, or strong and
  specific contemporary evidence.
- `medium`: directional evidence with limited scope, indirect organizational
  evidence, or a credible source lacking full issue detail.
- `low`: ambiguous, thin, partisan, or otherwise weak evidence. Blank codes for
  insufficient evidence must use `low`.

## Output

Return exactly one row per `(anonymous_case_id, dimension)` with:

`anonymous_case_id,dimension,reviewer_code,reviewer_confidence,reviewer_note`

The note should briefly identify the evidence-to-code reasoning without trying
to identify the candidate. Do not reconcile against existing codes; that occurs
only after the independent review is frozen.
