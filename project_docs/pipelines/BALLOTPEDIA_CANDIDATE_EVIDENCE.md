# Ballotpedia candidate evidence staging

Ballotpedia's public candidate pages are a useful supplementary discovery
source. They commonly contain candidate-authored Candidate Connection answers,
campaign themes, editorial biography fields, outbound source footnotes, and a
directory of state legislative scorecards.

The paid Ballotpedia API is not used. Direct scripted requests currently return
an empty HTTP 202 response in this environment, so the acquisition script uses
Jina Reader as a read-only renderer of each public Ballotpedia URL. Both URLs,
the retrieval date, local path, and SHA-256 hash are retained. Requests are
throttled and cached source documents under `data/raw/ballotpedia/` are never
overwritten.

Run:

```powershell
python scripts/download_ballotpedia_candidate_pages.py --cycles 1994 1998 2002 2006 2010 2014 2018 2022
python scripts/extract_ballotpedia_candidate_evidence.py
python scripts/normalize_ballotpedia_candidate_sources.py
python scripts/download_ballotpedia_linked_sources.py
python scripts/extract_ballotpedia_scorecard_ratings.py
```

The resulting files are staging artifacts:

- `ballotpedia_candidate_crosswalk.csv`: election-index-derived identity links;
- `ballotpedia_page_manifest.csv`: retrieval provenance and hashes;
- `ballotpedia_candidate_sections.csv`: biography, campaign-theme, scorecard,
  endorsement, and footnote sections;
- `ballotpedia_candidate_source_links.csv`: outbound citations by section.
- `ballotpedia_questionnaire_items.csv`: same-cycle candidate-authored questions
  and answers, with item-level provenance;
- `ballotpedia_article_and_source_urls.csv`: normalized outbound URLs classified
  as news, campaign, official, archived, scorecard, or other sources;
- `ballotpedia_group_endorsements.csv`: parsed endorsement records with explicit
  temporal status;
- `ballotpedia_candidate_coalition_signals.csv`: the endorsement research mart;
  only exact same-cycle signals are marked model eligible, and none are silently
  assigned an issue direction;
- `ballotpedia_candidate_scorecard_ratings.csv`: candidate ratings extracted
  from the linked PDFs and conservatively matched to canonical identities;
- `ballotpedia_scorecard_votesmart_overlap.csv`: source overlap and integration
  decisions by scorecard publisher.

No extracted text is automatically assigned ideological valence. Candidate
Connection answers may enter the evidence ledger only after item-level policy
and temporal adjudication. Biography prose is contextual unless it explicitly
states a position. The Scorecards section is generally an index of external
scorecard publications, not a candidate's score; linked scorecards must be
downloaded, parsed, matched, and adjudicated separately. Later page revisions
must not be silently backcast into earlier election cycles.

The downloader also caches the fixed House and Senate district pages. Candidate
links found there are matched only to the corresponding chamber and district.
Statewide election-index links are used as a fallback only for candidates with
full names; surname-only records cannot use the statewide fallback. Accepted
Vote Smart identities may supply a full name for an otherwise surname-only
canonical record.

The collision-audited acquisition pass resolved 5 canonical candidates in 1994,
14 in 1998, 45 in 2002, 42 in 2006, 188 in 2010, 186 in 2014, 79 in 2018, and 127 in
2022. Some district requests were rate-limited by the renderer and remain
retryable acquisition errors. The initial manually adjudicated same-cycle
positions are stored in
`data/manual/ideology/ballotpedia_candidate_position_adjudications.csv` and are
loaded by the ontology-v3 evidence build.

The normalized pass currently contains 10 questionnaire items for six
candidates, 127 campaign-site link observations (36 unique URLs), 72 news-link
observations (23 unique URLs), and 27 parsed endorsement observations. Five
endorsements are same-cycle records; the remainder are retained with historical,
post-election, or undated status and are not backcast. Fifteen distinct linked
scorecard publications were identified, 11 were downloaded successfully, and
977 ratings were parsed from ACU, NFIB Alabama, and Club for Growth documents.
There are 421 conservatively matched canonical identity observations across
those rating rows.

NFIB's recovered ratings duplicate Vote Smart data. ACU is a broad composite
without a sufficiently narrow ontology mapping. Those two sources remain in the
research mart but do not enter issue scoring. Club for Growth has an explicit
existing `market_governance / market_autonomy` mapping and adds 62 latest,
pre-election candidate-cycle observations to the v3 evidence ledger. This rule
prevents a broad conservative score from being treated as a bundle of unobserved
social positions.
