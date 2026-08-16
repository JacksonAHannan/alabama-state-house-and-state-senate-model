# Alabama 1994 candidate-ideology acquisition

## Current status

The public web resources establish that candidate-level records likely exist,
but they do not expose scans of those records. Downloaded finding aids and
access guides are registered in
`data/processed/ideology/alabama_1994_source_registry.csv`. Candidate-level
records must not be inferred from a collection description or aggregate court
finding.

Verified high-priority targets:

1. Trenholm, Gwen Patton Papers, #403003 / ComStoBox 11: ANSC Montgomery
   candidate surveys, screenings and endorsements, PAC material, newsletters,
   and flyers; #403006 / ComStoBox 13: 1994 ANSC convention booklet.
2. ADC: 1994 Democratic legislative-primary sample or yellow ballots and
   screening records. The court record confirms the endorsement program, but
   does not name the endorsed candidates.
3. Auburn, League of Women Voters of Alabama Records 0282: 1994 issues of *The
   Alabama Voter*, the 1994-95 *Capitol Newsletter*, and voter-service files.
4. Auburn, Alabama Textile Manufacturer's Association 0632, Box 6 Folder 22:
   BCA/ProgressPAC material, with emphasis on 1993-94 endorsements and candidate
   evaluations.
5. ADAH public-information subject files: SG006938/007 (ADC), /032 (Alabama
   Medical PAC), and /039 (ANSC), limited initially to January-November 1994.

## Ready-to-send Trenholm request

> I am conducting academic research on Alabama state legislative candidates in
> the 1994 election cycle. Would Special Collections please check #403003
> (ComStoBox 11) for materials dated 1994, particularly Montgomery Chapter
> Candidate Surveys, Screenings and Endorsements, PAC materials, newsletters,
> flyers, and sample ballots? Please also check #403006 (ComStoBox 13) for the
> 1994 Alabama New South Coalition Convention Souvenir Booklet. I would like a
> folder-level description first and, if permitted, digital scans of documents
> that name Alabama House or Senate candidates or reproduce their survey
> answers. Please advise regarding reproduction costs and permissions.

Trenholm Library lists 334-420-4455 and 334-420-4357.

## Ready-to-send Auburn request

> I am conducting academic research on the 1994 Alabama legislative elections.
> Could Special Collections identify and digitize, if permitted: (1) 1994
> candidate questionnaires, voter guides, or candidate comparisons in League of
> Women Voters of Alabama Records 0282, including *The Alabama Voter*, the
> 1994-95 *Capitol Newsletter*, and voter-service material; and (2) 1993-94
> ProgressPAC or Business Council of Alabama endorsement, questionnaire, or
> candidate-evaluation records in Alabama Textile Manufacturer's Association
> collection 0632, Box 6 Folder 22? A folder-level inventory before scanning is
> welcome. Please advise regarding reproduction costs.

Auburn Special Collections lists `archives@auburn.edu` and 334-844-1732.

## ADAH request scope

Use ADAH's research-request or reproduction-order form and request a date check
before ordering full scans. Ask for January-November 1994 material containing
`sample ballot`, `yellow ballot`, `endorsement`, `screening`, `candidate`,
`House`, or `Senate` in SG006938 folders 007, 032, and 039. The newspaper
catalog describes holdings, not digitized issues; Newspapers.com access is
available in the ADAH Research Room.

## Observation integration

Enter recovered evidence into
`data/manual/ideology/alabama_1994_candidate_observations.csv`. Preserve the
election stage (`primary`, `runoff`, or `general`) and distinguish:

- `questionnaire_response`;
- `endorsement` or `non_endorsement`;
- `rating`;
- `newspaper_position_statement`;
- `sample_ballot`.

An organization contribution is not an endorsement. Affiliations and the
aggregate ADC court finding are contextual evidence, not candidate-level
observations. Every entered row requires a document/page locator and review
status before it can join the canonical 1994 candidate universe.

Run `scripts/download_1994_ideology_sources.py` to refresh public artifacts and
the checksummed source registry.
