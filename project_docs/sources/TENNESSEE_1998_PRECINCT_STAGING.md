# Tennessee 1998 precinct OCR staging

The official Tennessee Secretary of State 1998 House, Senate, and governor
precinct reports are scanned PDFs without embedded text. This experimental
pipeline renders each page at 2x resolution, runs RapidOCR, and preserves every
recognized token with its page, bounding box, and confidence before parsing.

Legislative precinct rows retain total candidate turnout for use as a possible
context-allocation weight. Governor columns one and two are John Jay Hooker
(Democratic) and Don Sundquist (Republican); later minor-party and write-in
columns are not used as the two-party context. The official books contain a
complete ordered sequence of House districts 1-99, the seventeen regular odd
Senate districts, and a source-confirmed special District 8 contest. District
identity is assigned from that source order; the OCR-read
number and every override are retained in a header audit. This prevents blank,
punctuated, or misread header numbers from contaminating later rows. County and
precinct labels still come from visible report headers. County/district totals
and candidate headers are excluded. One explicit source-continuation rule is
retained: Senate District 33 continues Shelby County from the preceding block
without reprinting a county header on pages 28-29. Its printed district total
is 23,653, but recognized precinct rows sum to 22,460; the district therefore
remains explicitly ineligible rather than being filled from the aggregate.

Parsed legislative turnout is compared with Klarner's Democratic, Republican,
and other-candidate vote total. Experimental eligibility requires both totals
and a discrepancy no larger than the greater of ten votes or one percent.
Ambiguous governor rows and low-confidence major-party cells remain in a
separate review file and are never silently converted to zero.

These outputs are staging evidence only. Independent visual sampling and
deterministic rebuild validation are required before panel integration.

The current cached pass contains 47,212 OCR tokens, 4,008 unique legislative
precinct/district turnout rows, and 2,518 governor precinct rows. Fifty
governor lines remain in the explicit review queue. Seventy-eight legislative
districts reconcile to Klarner within the declared tolerance. The parsed
governor major-party totals are 283,618 Democratic and 656,815 Republican,
below the official statewide summary totals; panel integration must therefore
apply district-specific join coverage rather than assume complete context.

Three concurrent RapidOCR processes oversubscribed the local runtime. The
token cache makes this harmless for reproducibility, but future scanned-report
acquisitions should benchmark a single worker before increasing concurrency.
