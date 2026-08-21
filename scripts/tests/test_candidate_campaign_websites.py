from discover_candidate_campaign_websites import parse_biography_links, parse_campaign_links, select_nearest_capture


def test_only_explicit_campaign_links_are_extracted():
    html = '''
      <div>Campaign Website <a href="https://example.com/jane">Jane for Alabama</a></div>
      <a href="https://facebook.com/jane">Campaign Website</a>
      <a href="https://example.org">Unrelated organization</a>
    '''
    links = parse_campaign_links(html, "https://j.futurefacts.votesmart.io/candidate/1")
    assert [row["campaign_url"] for row in links] == ["https://example.com/jane"]


def test_nearest_capture_is_cycle_specific():
    captures = [
        {"timestamp": "19980501000000", "original": "http://example.com"},
        {"timestamp": "19981102000000", "original": "http://example.com"},
        {"timestamp": "20010101000000", "original": "http://example.com"},
    ]
    assert select_nearest_capture(captures, 1998)["timestamp"] == "19981102000000"


def test_public_biography_campaign_contacts_are_parsed():
    payload = {"electionWebAddresses": [{"webaddress": "https://candidate.example"}]}
    links = parse_biography_links(payload, "https://votesmart.example/biography/1")
    assert links[0]["campaign_url"] == "https://candidate.example"
