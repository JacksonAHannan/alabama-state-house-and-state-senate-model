from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "acquire_southern_candidate_finance_summaries.py"
SPEC = importlib.util.spec_from_file_location("southern_finance_summaries", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def test_candidate_universe_has_one_row_per_race_party() -> None:
    universe = MOD.candidate_universe()
    assert universe.state.isin({"AL", "AR", "FL", "GA", "KY", "LA", "MS", "MO", "NC", "OK", "SC", "TN", "TX", "VA"}).all()
    assert universe.cycle.between(2016, 2024).all()
    assert not universe.duplicated(
        ["state", "cycle", "chamber", "district", "party"]
    ).any()


def test_candidate_universe_can_use_final_warehouse_names_without_changing_keys() -> None:
    legacy = MOD.candidate_universe("NC")
    final = MOD.candidate_universe("NC", prefer_final_names=True)
    key = ["state", "cycle", "chamber", "district", "party"]
    assert legacy[key].equals(final[key])
    assert (final.candidate == "TED DAVIS, JR.").any()


def test_nc_committee_scope_rejects_explicit_nonlegislative_campaigns() -> None:
    assert MOD.nc_committee_is_legislative_compatible("Friends of Gale Adcock")
    assert MOD.nc_committee_is_legislative_compatible("Adcock for NC Senate")
    assert not MOD.nc_committee_is_legislative_compatible("Sam Davis for Congress")
    assert not MOD.nc_committee_is_legislative_compatible("Stevens for Justice")
    assert MOD.nc_committee_identity_name("Bishop for NC Senate") == "BISHOP"
    assert MOD.nc_committee_identity_name("Committee to Elect C Thomas") == "CTHOMAS"


def test_south_carolina_office_and_person_matching() -> None:
    assert MOD.sc_office_parts("SC House of Representatives District 91") == ("house", 91)
    assert MOD.sc_office_parts("SC Senate District 35") == ("senate", 35)
    assert MOD.sc_office_parts("Greenville County Council District 22") == (None, None)
    assert MOD.candidate_score("Ben Kinlaw", "Kinlaw, Benny") >= 88
    assert MOD.candidate_score("Heather Ammons Crawford", "Crawford, Heather Ammons") >= 95
    assert MOD.candidate_score("Jane Smith", "John Jones") < 50


def test_south_carolina_exact_name_wins_close_scoped_competitor() -> None:
    targets = pd.DataFrame([{
        "cycle": 2020, "chamber": "senate", "district": 25,
        "party": "D", "candidate": "greenfayson, shirley a",
    }])
    index = [
        {"office": "SC Senate District 25", "candidateName": "Green-Fayson, Shirley A",
         "candidateFilerId": 31454, "campaignId": 47151, "reportId": 1},
        {"office": "SC Senate District 25", "candidateName": "Green, Shirley",
         "candidateFilerId": 99999, "campaignId": 99999, "reportId": 2},
    ]
    matches, _ = MOD.match_sc_candidates(targets, index, 2020)
    assert matches.iloc[0].match_status == "accepted_automatic"
    assert matches.iloc[0].provider_candidate == "Green-Fayson, Shirley A"


def test_candidate_identity_score_handles_compound_surnames_without_family_false_match() -> None:
    assert MOD.normalized_tokens("Jeremy McPike") == ["JEREMY", "MCPIKE"]
    assert MOD.normalized_tokens("JOSE&#769; MENE&#769;NDEZ") == ["JOSE", "MENENDEZ"]
    assert MOD.candidate_identity_score(
        "carrollfoy, jennifer d", "Jennifer Carroll Foy",
        "Friends of Jennifer Carroll Foy",
    ) == 100
    assert MOD.candidate_identity_score(
        "fisherbaldwin, marva", "Marva Fisher Baldwin",
        "Committee to Elect Marva Fisher Baldwin",
    ) == 100
    assert MOD.candidate_identity_score(
        "underwood, richard (rick)", "Michelle E Underwood",
    ) < 94
    assert MOD.candidate_identity_score(
        "bell, robert b, iii", "Richard Preston Bell",
    ) < 94
    assert MOD.candidate_identity_score(
        "Josh E. Thomas", "John Thomas Stirrup",
    ) < 94
    assert MOD.candidate_identity_score(
        "Bob W. Smith", "Benjamin Thomas Smith",
    ) < 94
    assert MOD.candidate_identity_score(
        'J. D. "Danny" Diggs', "Joseph Daniel Diggs",
    ) >= 94
    assert MOD.candidate_identity_score(
        "RON STEPHENS", "James Ronald Stephens",
        "Committee to Re-Elect Ron Stephens",
    ) == 100
    assert MOD.candidate_identity_score(
        "RANDY ROBERTSON", "Wiley Randall Robertson",
    ) == 100
    assert MOD.candidate_identity_score(
        "TIMOTHY HICKEY", "Tim Hickey", "Tim Hickey for Delegate",
    ) == 100
    assert MOD.candidate_identity_score("Bobby Cleveland", "Robert L Cleveland") == 100
    assert MOD.candidate_identity_score("Cindy Roe", "Cynthia Jo Roe") == 100
    assert MOD.candidate_identity_score(
        "COTTERSMASAL, MELISSA", "Missy Cotter Smasal", "Missy for Senate",
    ) == 100


def test_arkansas_followthemoney_candidate_total_parser() -> None:
    content = b"""
    <table><tbody><tr>
      <td></td>
      <td token="c-t-id" tokenvalue="194412"><a token="c-t-eid" tokenvalue="22027719">WALLACE, DAVID RAY (DAVE)</a></td>
      <td>WON-GENERAL</td><td>WON</td><td>REPUBLICAN</td>
      <td token="c-t-p">REPUBLICAN</td><td>AR</td>
      <td token="y">2016</td><td>STANDARD</td>
      <td token="c-r-osid">SENATE DISTRICT 022</td>
      <td>CHALLENGER</td><td>125</td><td>$200,925</td>
    </tr></tbody></table>
    """
    rows = MOD.parse_ar_followthemoney_candidates(content)
    assert rows == [{
        "candidate": "WALLACE, DAVID RAY (DAVE)",
        "candidate_id": "194412", "entity_id": "22027719",
        "party": "REPUBLICAN", "office": "SENATE DISTRICT 022",
        "cycle": 2016, "record_count": 125,
        "total_contributions": 200925.0,
    }]


def test_concatenated_surname_discovery_includes_short_trailing_family_name() -> None:
    assert "JOYCE" in MOD.plausible_concatenated_surname_fragments(
        "ERBJOYCE, MICHELE"
    )
    assert MOD.candidate_score(
        "DENISESNYDERKANE, SHANNON", "Shannon DS Kane"
    ) >= 94
    assert MOD.candidate_score("Jane Ford", "Jason Ford") < 94


def test_candidate_identity_score_handles_natural_name_with_comma_suffix() -> None:
    assert MOD.candidate_identity_score(
        "JAMES A. THOMAS, JR.", "James A Thomas Jr.",
    ) == 100
    assert MOD.candidate_identity_score(
        'H. F. "BUDDY" FOWLER, JR.', "Hyland Franklin Fowler Jr.",
        "Buddy Fowler for Delegate",
    ) == 100
    assert MOD.candidate_identity_score(
        "LOPESMALDONADO, MICHELLEANN E",
        "Michelle-Ann Elizabeth Lopes Maldonado",
        "Friends of Michelle Maldonado",
    ) == 100


def test_person_parts_distinguishes_suffix_from_surname_first_comma() -> None:
    assert MOD.person_parts("James A. Thomas, Jr.") == (
        "JAMES", "THOMAS", "JAMES A THOMAS"
    )
    assert MOD.person_parts("Thomas, James A., Jr.") == (
        "JAMES", "THOMAS", "JAMES A THOMAS"
    )


def test_virginia_committee_scope_rejects_nonlegislative_offices() -> None:
    assert MOD.va_committee_is_compatible("Friends of Kelly Fowler", "house")
    assert MOD.va_committee_is_compatible("Smith for Delegate", "house")
    assert not MOD.va_committee_is_compatible("Smith for Senate", "house")
    assert not MOD.va_committee_is_compatible(
        "Jennifer Carroll Foy for Governor", "house"
    )
    assert not MOD.va_committee_is_compatible("Diggs for Sheriff", "senate")


def test_virginia_standard_committee_title_discovery_is_chamber_specific() -> None:
    assert "STUART for Senate" in MOD.va_standard_committee_discovery_queries(
        "RICHARD H. STUART", "senate"
    )
    assert "WOLF for Delegate" in MOD.va_standard_committee_discovery_queries(
        "RANDALL K. WOLF", "house"
    )
    assert "WOLF for Senate" not in MOD.va_standard_committee_discovery_queries(
        "RANDALL K. WOLF", "house"
    )


def test_south_carolina_report_selection_is_cycle_windowed() -> None:
    matches = pd.DataFrame([{
        "state": "SC", "cycle": 2024, "chamber": "house", "district": 1,
        "party": "D", "candidate": "Jane Smith", "provider_candidate": "Smith, Jane",
        "provider_identity": "house|1|SMITH JANE",
        "candidate_filer_id": "10", "campaign_id": "20", "match_score": 100.0,
        "match_margin": 50.0, "candidates_considered": 2,
        "match_status": "accepted_automatic",
    }])
    campaigns = {"house|1|SMITH JANE": [
        {"reportId": 1, "reportName": "Quarter 4, 2022 Report", "lastUpdated": "2023-01-10"},
        {"reportId": 2, "reportName": "Quarter 1, 2023 Report", "lastUpdated": "2023-04-10"},
        {"reportId": 3, "reportName": "Quarter 4, 2024 Report", "lastUpdated": "2025-01-10"},
        {"reportId": 4, "reportName": "Final Report", "lastUpdated": "2025-01-12"},
    ]}
    selected = MOD.select_sc_reports(matches, campaigns, 2024)
    assert {row["reportId"] for row in selected} == {2, 3, 4}


def test_south_carolina_duplicate_campaigns_do_not_create_false_tie() -> None:
    targets = pd.DataFrame([{
        "state": "SC", "cycle": 2024, "chamber": "house", "district": 1,
        "party": "D", "candidate": "Jane Smith",
    }])
    index_rows = [
        {
            "candidateFilerId": 10, "campaignId": 20, "reportId": 1,
            "candidateName": "Smith, Jane", "office": "SC House of Representatives District 1",
            "reportName": "Quarter 1, 2024 Report", "lastUpdated": "2024-04-10",
        },
        {
            "candidateFilerId": 10, "campaignId": 21, "reportId": 2,
            "candidateName": "Smith, Jane", "office": "SC House of Representatives District 1",
            "reportName": "Quarter 2, 2024 Report", "lastUpdated": "2024-07-10",
        },
        {
            "candidateFilerId": 11, "campaignId": 22, "reportId": 3,
            "candidateName": "Jones, John", "office": "SC House of Representatives District 1",
            "reportName": "Quarter 2, 2024 Report", "lastUpdated": "2024-07-10",
        },
    ]
    matches, campaigns = MOD.match_sc_candidates(targets, index_rows, 2024)
    assert matches.loc[0, "match_status"] == "accepted_automatic"
    assert matches.loc[0, "campaign_id"] == "20|21"
    selected = MOD.select_sc_reports(matches, campaigns, 2024)
    assert {row["reportId"] for row in selected} == {1, 2}


def test_florida_candidate_summary_parser() -> None:
    content = b"""<html><body><pre>
Candidate Name                           Party  Office  District  Group      Total Amount
Jane Q. Public                          DEM    STR     001                      7,907.00
John Smith                              REP    STS     012       3            -1,000.00
</pre></body></html>"""
    rows = MOD.parse_fl_candidate_summary(content)
    assert rows == [
        {
            "candidate": "Jane Q. Public", "party": "DEM", "office": "STR",
            "district": 1, "group": None, "total_amount": 7907.0,
        },
        {
            "candidate": "John Smith", "party": "REP", "office": "STS",
            "district": 12, "group": "3", "total_amount": -1000.0,
        },
    ]


def test_kentucky_candidate_index_parser() -> None:
    content = b"""<table><tr><td><a href='/kref/publicsearch/CandidateSearch/CandidateReports/99'>Jane Doe</a></td><td>State Representative</td><td>Closed</td><td>3rd District</td><td>11/5/2024</td><td>General</td><td>$12,345.67</td><td>$10,000.00</td><td>1/1/2024</td><td>1/2/2024</td></tr></table>"""
    rows = MOD.parse_ky_candidate_index(content, "house")
    assert rows[0]["candidate_id"] == "99"
    assert rows[0]["district"] == 3
    assert rows[0]["total_receipts"] == 12345.67


def test_kentucky_matcher_prefers_same_cycle_general_then_primary() -> None:
    targets = pd.DataFrame([
        {
            "state": "KY", "cycle": 2024, "chamber": "house",
            "district": 14, "party": "D", "candidate": "Chanda Garner",
        },
        {
            "state": "KY", "cycle": 2024, "chamber": "house",
            "district": 66, "party": "D", "candidate": "Peggy Houston-Nienaber",
        },
    ])
    source = pd.DataFrame([
        {
            "cycle": 2024, "chamber": "house", "district": 14,
            "candidate": "Chanda Garner", "candidate_id": "1",
            "election_type": "Primary", "total_receipts": 639.27,
        },
        {
            "cycle": 2022, "chamber": "house", "district": 14,
            "candidate": "Chanda Garner", "candidate_id": "old",
            "election_type": "General", "total_receipts": 99999.0,
        },
        {
            "cycle": 2024, "chamber": "house", "district": 66,
            "candidate": "Peggy Nienaber", "candidate_id": "2",
            "election_type": "General", "total_receipts": 2785.0,
        },
        {
            "cycle": 2024, "chamber": "house", "district": 66,
            "candidate": "Peggy Houston-Nienaber", "candidate_id": "3",
            "election_type": "General", "total_receipts": 0.0,
        },
    ])
    matches = MOD.match_ky_candidate_registrations(targets, source, 2024)
    assert matches.match_status.eq("accepted_automatic").all()
    assert matches.loc[matches.district.eq(14), "provider_identity"].iloc[0] == "1"
    assert matches.loc[matches.district.eq(14), "match_method"].iloc[0] == (
        "same_cycle_primary_registration"
    )
    assert matches.loc[matches.district.eq(66), "provider_identity"].iloc[0] == "3"


def test_virginia_report_index_parser_separates_period_and_amounts() -> None:
    content = b"""<table><tr><td>01/01/2024 to 03/31/2024</td><td>2</td><td>04/15/2024</td><td>$1,234.00</td><td>$500.00</td><td><a href='/Report/Index/456'>View Report</a></td></tr></table>"""
    rows = MOD.parse_va_committee_reports(content)
    assert rows == [{
        "period_start": "01/01/2024", "period_end": "03/31/2024",
        "amendment": "2", "filed": "04/15/2024",
        "contributions_received": 1234.0, "ending_balance": 500.0,
        "report_id": "456",
        "report_url": "https://cfreports.elections.virginia.gov/Report/Index/456",
        "xml_url": "https://cfreports.elections.virginia.gov/Report/ReportXML/456",
    }]


def test_georgia_recordsearch_registration_requires_exact_scope() -> None:
    targets = pd.DataFrame([
        {
            "state": "GA", "cycle": 2024, "chamber": "house",
            "district": 6, "party": "D", "candidate": "CATHY KOTT",
        },
        {
            "state": "GA", "cycle": 2024, "chamber": "house",
            "district": 7, "party": "D", "candidate": "CATHY KOTT",
        },
        {
            "state": "GA", "cycle": 2024, "chamber": "house",
            "district": 7, "party": "R", "candidate": "CATHY KOTT",
        },
    ])
    registrations = [{
        "filerName": "Cathy Kott", "filerEntityId": 564482,
        "filingCycleName": (
            "2024 State/Statewide Election Cycle for Candidates (January and June)"
        ),
        "office": "State Representative", "districtName": "6",
        "politicalPartyCode": "DEM", "committeeName": "Votes for Change",
        "_source_path": "data/raw/finance/southern_summaries/GA/query.json",
    }]
    matches = MOD.match_ga_recordsearch_registrations(targets, registrations)
    assert matches.loc[0, "match_status"] == "accepted_automatic"
    assert matches.loc[0, "provider_identity"] == "recordsearch:564482"
    assert matches.loc[1, "match_status"] == "accepted_automatic"
    assert matches.loc[1, "match_scope"] == (
        "prior_or_current_cycle_name_party_identity_continuity"
    )
    assert matches.loc[2, "match_status"] == "review_required"


def test_georgia_legacy_registration_parser_and_scope_match() -> None:
    detail = b"""<html><body>
    <span id='ctl00_ContentPlaceHolder1_NameInfo1_lblName'>Price, Elizabeth Clark</span>
    <table id='ctl00_ContentPlaceHolder1_NameInfo1_dlDOIs'>
      <tr><td>FilerID</td><td>Office Sought</td><td>Info</td><td>Status</td></tr>
      <tr><td>C2015000177</td><td>State Representative<br/><i>District: 48</i></td>
      <td>View</td><td>Active</td></tr>
    </table><span>No Reports Filed.</span></body></html>"""
    registrations = MOD.parse_ga_legacy_candidate_detail(detail)
    assert registrations == [{
        "provider_candidate": "Price, Elizabeth Clark",
        "provider_identity": "legacy:C2015000177", "chamber": "house",
        "district": 48, "registration_status": "Active",
        "no_reports_filed": True,
    }]
    registrations[0]["source_path"] = "data/raw/ga/detail.html"
    targets = pd.DataFrame([{
        "state": "GA", "cycle": 2020, "chamber": "house", "district": 48,
        "party": "R", "candidate": "BETTY PRICE",
    }])
    matches = MOD.match_ga_legacy_registrations(targets, registrations)
    assert matches.loc[0, "match_status"] == "accepted_automatic"
    assert matches.loc[0, "provider_identity"] == "legacy:C2015000177"


def test_georgia_legacy_registration_parser_accepts_state_senate_label() -> None:
    detail = b"""<html><body>
    <span id='ctl00_ContentPlaceHolder1_NameInfo1_lblName'>Moses, Cheryle R</span>
    <table id='ctl00_ContentPlaceHolder1_NameInfo1_dlDOIs'>
      <tr><td>C2018000229</td><td>State Senate<br/><i>District: 9</i></td>
      <td>View</td><td>Active</td></tr>
    </table></body></html>"""
    assert MOD.parse_ga_legacy_candidate_detail(detail) == [{
        "provider_candidate": "Moses, Cheryle R",
        "provider_identity": "legacy:C2018000229",
        "chamber": "senate", "district": 9,
        "registration_status": "Active", "no_reports_filed": False,
    }]


def test_georgia_legacy_registration_can_follow_predating_filer_across_district() -> None:
    registrations = [{
        "provider_candidate": "Talley, Rahim F.",
        "provider_identity": "legacy:C2014000073",
        "chamber": "house", "district": 109,
        "registration_status": "Active", "no_reports_filed": False,
        "source_path": "data/raw/ga/talley.html",
    }]
    targets = pd.DataFrame([{
        "state": "GA", "cycle": 2016, "chamber": "house", "district": 73,
        "party": "D", "candidate": "TALLEY, RAHIM",
    }])
    match = MOD.match_ga_legacy_registrations(targets, registrations).iloc[0]
    assert match.match_status == "accepted_automatic"
    assert match.match_scope == "predating_filer_name_identity_continuity"


def test_tennessee_candidate_and_report_parsers_preserve_ids_and_cycle() -> None:
    candidate = b"""<table><tr><td>DOE, JANE</td><td>contact</td><td>Democrat</td>
    <td>House of Representatives</td><td>7</td><td></td><td></td><td>2024</td>
    <td><a href='/tncamp/public/replist.htm?id=99&owner=DOE'>Report List</a></td>
    </tr></table>"""
    rows = MOD.parse_tn_candidate_page(candidate)
    assert rows[0]["provider_id"] == "99"
    assert rows[0]["chamber"] == "house"
    assert rows[0]["party"] == "D"
    report = b"""<table><tr><td>2024</td><td><a href='/tncamp/search/pub/report_full.htm?reportId=123'>
    1st Quarter 2024</a></td><td>Y</td><td>04/10/2024</td></tr></table>"""
    parsed = MOD.parse_tn_report_page(report)
    assert parsed[0]["report_id"] == "123"
    assert parsed[0]["report_year"] == 2024
    assert parsed[0]["is_amendment"]
