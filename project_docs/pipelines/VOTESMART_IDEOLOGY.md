# Vote Smart historical candidate-ideology pipeline

## Scope

The target universe is every Alabama House and Senate candidate in the 1994,
1998, 2002, 2006, 2010, 2014, 2018, and 2022 election cycles. Vote Smart is an
independent candidate-position source; election outcomes are never used to
construct its ideology features.

The downloader preserves four analytically distinct source types:

1. candidate-supplied Political Courage Test/NPAT responses;
2. Vote Smart inferred positions, when explicitly identified as inferred;
3. interest-group ratings or scorecards; and
4. interest-group endorsements.

These must not be collapsed into a single raw ideology score. Endorsements can
measure institutional support or viability as well as issue alignment. Ratings
are organization-, issue-, and period-specific.

## Access

The current Swagger specification publicly documents the required `/v2`
routes, but direct anonymous calls returned HTTP 401 on 2026-08-16. Use an
authorized bearer token:

```powershell
$env:VOTESMART_API_TOKEN='your-token'
python scripts/download_votesmart_ideology.py
```

The ignored `token.env` file may alternatively contain:

```text
VOTESMART_API_TOKEN=your-token
```

Tokens are neither printed nor written to manifests. Endorsement and public-
statement products may require additional entitlements.

The public candidate pages provide a second, credential-free acquisition path.
The project uses these ordinary HTML pages when they return public HTTP 200
responses:

```powershell
python scripts/scrape_votesmart_public.py
```

This proof-of-concept caches each PCT and evaluations page, waits at least one
second between uncached requests, fingerprints the HTML, and produces separate
PCT-option, rating, and endorsement tables. It does not attempt authentication,
CAPTCHA evasion, proxy rotation, or access-control circumvention.

## Raw acquisition

The first pass downloads:

- historical Alabama state-legislative candidate enumeration;
- multi-year Political Courage Test responses;
- corresponding multi-year questionnaire forms;
- candidate-specific historical interest-group ratings; and
- recorded campaign website addresses.

Responses are stored under `data/raw/ideology/votesmart/` with a SHA-256
manifest. Raw snapshots retain pagination and request parameters so later
normalization is auditable.

## Normalization contract

Downstream normalized records must retain:

```text
votesmart_candidate_id, canonical_candidate_id, person_id,
election_year, state, chamber, district, party,
record_type, source_year, question_or_scorecard_id,
question_text, raw_answer, candidate_supplied, votesmart_inferred,
interest_group_id, interest_group_name, rating_value, endorsement,
issue_category, source_url, retrieved_at, identity_match_method
```

Candidate nonresponse remains missing. Scores from different organizations or
scorecards are not placed on a common scale without an explicit calibration
model. Evidence dated after an election cannot become a prospective feature for
that election, although it may be retained as retrospective corroboration.

## Integration sequence

1. Download and fingerprint raw API responses.
2. Inspect actual response schemas and freeze representative test fixtures.
3. Crosswalk Vote Smart candidates to canonical candidate-election identities.
4. Normalize questionnaire, rating, endorsement, and website tables separately.
5. Map questionnaire items to the existing issue taxonomy with raw text intact.
6. Audit coverage and identity ambiguity by year, party, chamber, and district.
7. Add temporally eligible evidence to the ideology research layer.
8. Re-estimate ideology/CMO relationships only after the historical CMO model is
   rebuilt and validated for the added cycles.

## Public-site acquisition result

The first complete public-page pass on 2026-08-16 found 1,570 Alabama general-
election candidate entries representing 878 Vote Smart people for 1998-2022.
The public 1994 Alabama election page contained no candidate roster. Across the
878 profiles, the parser recovered 26,792 historical PCT option records, 7,682
interest-group ratings, and 810 endorsements. Exact-cycle PCT respondent counts
were 74 in 1998, 62 in 2002, 42 in 2006, 24 in 2010, 5 in 2014, 20 in 2018, and
6 in 2022. No 1998-2006 exact-cycle endorsement blocks were recovered.

The canonical crosswalk uses year, chamber, district, party, and name. Because
Vote Smart exposes no 1994 election roster, 1994 links are limited to repeated
candidates with an exceptionally strong and unique person-name match to a later
Vote Smart profile; all other 1994 candidates remain unmatched for archival
research.

The first canonical crosswalk matched 85 of 211 warehouse candidate records in
1994 by propagating a verified later Vote Smart identity through the canonical
person ID. It matched 165/170 records in 1998, 184/213 in 2002, 180/194 in 2006,
189/203 in 2010, 187/198 in 2014, 185/204 in 2018, and 161/173 in 2022. The
remaining cases are retained as an explicit review/archival queue.
