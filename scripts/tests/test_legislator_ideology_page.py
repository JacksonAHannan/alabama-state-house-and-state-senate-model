from scripts.build_legislator_ideology_page import GROUP_ORDER, build_page, build_payload


def test_atlas_has_complete_cohort_and_records():
    payload = build_payload()
    assert len(payload["candidates"]) == 30
    assert len(payload["groups"]) == len(GROUP_ORDER) == 14
    assert payload["method"]["allRecords"] >= 800
    assert all(len(candidate["cells"]) == 14 for candidate in payload["candidates"])


def test_uncoded_public_positions_do_not_become_directional_scores():
    payload = build_payload()
    public = [record for candidate in payload["candidates"] for record in candidate["records"]
              if record["source_type"] == "Public position"]
    assert public
    assert all(record["direction"] is None for record in public)


def test_generated_page_has_navigation_and_accessible_controls():
    page = build_page()
    assert '<title>Alabama Legislator Issue Atlas</title>' in page
    assert 'href="cmo.html"' in page
    assert 'id="heatmap"' in page
    assert 'Evidence timing' in page


def test_votesmart_pct_is_separate_candidate_supplied_evidence():
    payload = build_payload()
    assert payload["method"]["voteSmartProfiles"] == 5
    pct = [record for candidate in payload["candidates"] for record in candidate["records"]
           if record["source_type"] == "Vote Smart PCT"]
    assert pct
    assert all(record["timing"] == "pre_election_candidate_supplied" for record in pct)
    assert all(record["direction"] is not None for record in pct)
    assert all("Vote Smart questionnaire" in record["summary"] for record in pct)


def test_votesmart_never_uses_questionnaire_after_focal_election():
    payload = build_payload()
    for candidate in payload["candidates"]:
        if candidate["voteSmart"] is not None:
            assert candidate["voteSmart"]["questionnaireYear"] <= candidate["cycle"]
