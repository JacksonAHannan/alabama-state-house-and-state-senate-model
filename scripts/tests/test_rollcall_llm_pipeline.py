from scripts.classify_legislative_rollcalls_ollama import quote_supported, relevant_excerpt
from scripts.build_focal_legislator_crosswalk import district_number


def test_quote_verification_ignores_outer_quotes_and_whitespace():
    text = "The jail staff shall maintain a record of all communications."
    assert quote_supported('“The jail staff shall maintain a record of all communications.”', text)
    assert not quote_supported("The jail must keep every communication forever.", text)


def test_relevant_excerpt_keeps_start_and_keyword_window():
    text = "A" * 15000 + " medicaid expansion language " + "B" * 20000
    excerpt = relevant_excerpt(text, "Medicaid", limit=18000)
    assert excerpt.startswith("A")
    assert "medicaid expansion" in excerpt
    assert len(excerpt) <= 18000


def test_district_number_handles_legiscan_prefixes():
    assert district_number("HD-007") == 7
    assert district_number("SD 28") == 28
