# Candidate campaign website acquisition

`scripts/discover_candidate_campaign_websites.py` discovers campaign URLs from
Vote Smart's public candidate profile/contact data, caches responses, and can
inventory Internet Archive captures. It operates on accepted rows in
`votesmart_candidate_crosswalk_resolved.csv` and expands each stable Vote Smart
candidate ID back to every associated CMO election cycle.

Run a small availability check first:

```powershell
python scripts/discover_candidate_campaign_websites.py --limit 10
```

When both Vote Smart and Internet Archive are responding normally:

```powershell
python scripts/discover_candidate_campaign_websites.py --wayback
```

The run is resumable. Successful source responses and CDX results are cached in
`data/raw/ideology/campaign_websites/`; failures remain visible in
`candidate_campaign_website_discovery_status.csv`.

## Temporal rule

A campaign URL shown on a candidate profile at retrieval time is not itself
evidence for every past race. The output labels it
`current_profile_link_as_of_retrieval`. Only an archived page captured near a
given election cycle should contribute stated-position evidence for that cycle.
The nearest capture fields are consequently calculated separately for every
candidate-cycle row.

This stage inventories URLs and captures only. Page text must subsequently be
parsed into the shared candidate-position evidence contract and adjudicated
under ontology v3 before it enters model features.
