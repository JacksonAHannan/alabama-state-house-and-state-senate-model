# Legislative activity and candidate-issue evidence

This extension measures what focal candidates prioritized and, where the record
permits, what policy direction they supported. It deliberately does not treat every
legislative action as an ideological position.

## Sources and coverage

- LegiScan Alabama bulk JSON supplies bill metadata, sponsors, amendments, history,
  legislators, and roll calls for sessions beginning in 2010.
- Official Alabama Legislature PDFs are the text authority. The local archive contains
  39,841 of 39,853 version records. Twelve old version links failed, and 279 of 28,833
  measures have no text-version metadata in the source archive.
- The separate amendment archive contains all 5,912 amendment PDFs in the metadata.
- Twenty of the 30 focal candidate cases have a manually reviewed LegiScan legislator
  identity. The other ten were challengers or remain unmatched and therefore have no
  legislative activity inferred.

## Evidence hierarchy

1. A manually adjudicated roll call or amendment direction is position evidence.
2. Primary or joint sponsorship is strong priority evidence, but it is not automatically
   a stance. A sponsor may introduce a bill by request, compromise on its content, or
   support only part of it.
3. Cosponsorship is weaker priority/alignment evidence and is reported separately.
4. A committee referral or report describes the bill's path. It is not evidence of an
   individual member's committee vote unless the source names that action.
5. Campaign statements and contemporaneous questionnaires can establish positions when
   their date and candidate identity are verified.

`E` means activity on or before the exact general-election date; `L` means later activity.
Later evidence may describe a subsequent record but cannot explain an earlier election
without independent evidence that the position already existed.

Joint sponsorship is fractionally weighted by the number of same-role sponsors on the
bill. A sole primary sponsor receives weight 1; each of 20 joint sponsors receives
weight 1/20. Raw bill counts remain available beside weighted priority so large caucus
sign-on bills do not dominate the agenda profile.

## Attribution and classification

Candidate-to-legislator links come only from reviewed rows in
`focal_legislator_identity_crosswalk.csv`. Named amendments require the reviewed
legislator's surname immediately before “amendment,” “substitute,” or their modern
adoption variants. This prevents committee names such as “Ways and Means” from being
misread as a Larry Means amendment. A second provenance gate compares the target bill
printed in the official amendment header with the bill to which LegiScan linked the
instrument. Ten cross-bill duplicate links failed this check and are excluded from
position inference; 62 focal amendment instruments remain validated.

Issue tags on sponsorships are conservative, multi-label retrieval classifications based
on the official title/synopsis and LegiScan subjects. They indicate topic, not valence.
The two local language models may draft amendment summaries and direction codes, but all
model output remains a review queue. It cannot populate a candidate stance until a human
reviewer verifies the quoted amendment text and adjudicates the direction.

## Generated artifacts

- `candidate_sponsored_bill_evidence.csv`: bill-level sponsorship and topic evidence.
- `candidate_sponsorship_issue_summary.csv`: candidate/topic/timing/role counts.
- `candidate_legislative_priority_matrix*.csv`: primary/joint sponsorship priorities.
- `candidate_attributed_amendments.csv`: conservatively named amendment authors.
- `candidate_named_legislative_actions.csv`: other named instrument actions.
- `candidate_sponsored_bill_committee_events.csv`: committee path for sponsored bills,
  with an explicit no-individual-action warning and a flag for events preceding the
  bill's first recorded floor-passage action.
- `candidate_legislative_activity_coverage.csv`: identity and activity coverage.
- `candidate_sponsorship_direction_review_queue.csv`: at most three high-priority,
  pre-election bills per candidate/issue, linked to the locally archived canonical text.
- `candidate_sponsorship_position_evidence.csv`: directional sponsorship evidence only
  where the underlying bill has received either a reviewed human final-passage code or
  a bill-text sponsorship adjudication. Model drafts never enter this file directly.
- `human_sponsorship_adjudications.csv`: the explicit per-bill review gate for the
  bounded sponsorship direction queue.
- `focal_amendment_bill_link_validation.csv`: official-header validation of each
  amendment's LegiScan bill association.
- `candidate_state_issue_matrix_long.csv`: stance evidence plus separate, non-stance
  sponsorship and amendment counts.
- `amendment_llm_classifications.csv` and `amendment_llm_consensus_review.csv`: draft
  classifications awaiting human adjudication.
- `candidate_public_position_review_queue.csv`: a bounded retrieval queue of up to three
  pre-election sources for each still-undocumented candidate/topic cell. Keyword matches
  rank review candidates but never establish a stance automatically.

The current activity build contains 3,705 distinct focal sponsored bills, 62 validated
amendment-to-bill links (plus 10 excluded cross-bill source links), and 10,252
committee-path events. Of those
committee events, 9,147 precede the first recorded floor-passage action on their bill.
All validated amendments occurred after the focal candidate's studied election, so
they may describe later governing behavior but cannot be used to explain that prior CMO.

## Remaining limitations

LegiScan does not provide comprehensive individual committee votes. Amendment PDFs often
state the offered revision but may depend on unseen lines of a substitute or engrossed
bill. Campaign websites from older cycles are unevenly archived. Unknown cells therefore
remain unknown; absence of a position is not coded as neutrality or opposition.
