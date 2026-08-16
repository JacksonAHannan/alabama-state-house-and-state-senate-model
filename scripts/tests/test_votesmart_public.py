from pathlib import Path

from scrape_votesmart_public import extract_years, parse_evaluations, parse_pct
from discover_votesmart_public_candidates import last_page, parse_candidates


FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_years_handles_scorecard_ranges():
    assert extract_years("1995-1998") == (1995, 1998)
    assert extract_years("2010 Endorsements") == (2010, 2010)


def test_parse_pct_preserves_question_options_and_selection():
    html = """
    <h2 class="card-title">Jane Doe's Issue Positions (Political Courage Test)</h2>
    <h3 class="text-left">Alabama State Legislative Election 1998 National Political Awareness Test</h3>
    <div class="card card-plain"><h5 class="returned-PCT-header">Guns</h5>
      <div class="card-body"><p class="text-left">Indicate which principles you support.</p>
      <tr id="issueTextTypesNpatoptionText"><td>X</td><td><i class="fas fa-circle"></i></td><td>Support A</td></tr>
      <tr id="issueTextTypesNpatoptionText"><td></td><td><i class="far fa-circle"></i></td><td>Oppose B</td></tr>
      </div></div>
    """
    rows = parse_pct(html, 42, "https://example.test/pct/42")
    assert len(rows) == 2
    assert rows[0]["candidate"] == "Jane Doe"
    assert rows[0]["election_year"] == 1998
    assert rows[0]["selected"] is True
    assert rows[1]["selected"] is False


def test_parse_evaluations_separates_ratings_and_endorsements():
    html = """
    <h2 class="card-title">Jane Doe's Ratings and Endorsements</h2>
    <div><div class="evaluations-category-header" id="heading0">Guns</div>
      <div id="collapse0"><table class="evaluations-table"><div class="row mb-2">
        <a href="https://votesmart.org/interest-group/10/rating/20">NRA</a>
        <div class="evaluations-item-primary">A+</div>
        <div class="evaluations-item-primary">1998</div>
      </div></table></div></div>
    <div class="card"><div class="evaluations-endorsement-header"><h4>2010 Endorsements</h4></div>
      <li class="evaluations-candidate-endorsement-item"><a href="https://votesmart.org/interest-group/10/nra">NRA</a></li>
    </div>
    """
    ratings, endorsements = parse_evaluations(html, 42, "https://example.test/eval/42")
    assert ratings[0]["rating"] == "A+"
    assert ratings[0]["rating_year_start"] == 1998
    assert endorsements[0]["endorsement_year"] == 2010


def test_parse_public_election_candidates_deduplicates_image_and_text_links():
    html = """
    <div class="col-md-12">Alabama State House District 30 (Nov. 3, 1998)</div>
    <div class="col" id="electionsDetailsResultsCol"><div class="media">
      <a href="/candidate/5646/blaine-galliher"><img></a><div class="media-body">
      <a href="/candidate/5646/blaine-galliher">Blaine Galliher</a>
      <h5 class="title">(Won)</h5><h5 class="title">Republican</h5></div></div></div>
    <div class="col" id="electionsDetailsResultsCol"><div class="media">
      <a href="/candidate/5704/john-rogers-jr">John Rogers, Jr.</a>
      <h5 class="title">(Won)</h5><h5 class="title">Democratic</h5></div></div>
    <a href="?stageId=G&p=5">5</a>
    """
    rows = parse_candidates(html, 1998, "https://example.test/election")
    assert [row["votesmart_candidate_id"] for row in rows] == [5646, 5704]
    assert rows[0]["chamber"] == "house"
    assert rows[0]["district"] == 30
    assert rows[0]["party"] == "Republican"
    assert last_page(html) == 5
