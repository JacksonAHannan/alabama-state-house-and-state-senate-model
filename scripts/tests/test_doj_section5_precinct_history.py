from pathlib import Path

import pandas as pd

from scripts.ingest_doj_section5_precinct_history import (
    aggregate_submissions, event_types, notice_inventory, parse_html,
)


def test_notice_inventory_prefers_machine_readable_xls():
    html = '''<a href="/vnote010113.pdf">Notice of January 1, 2013</a>
              <a href="/vnote010113.xls">xls version</a>'''
    got = notice_inventory(html)
    assert len(got) == 1
    assert got[0]["source_format"] == "xls"
    assert got[0]["source_url"].endswith("vnote010113.xls")


def test_html_parser_retains_submission_activity_and_description(tmp_path: Path):
    path = tmp_path / "notice.html"
    path.write_text('''<table>
      <tr><td>04/06/98 - 98-1444</td></tr>
      <tr><td></td><td><b>State</b>: ALABAMA<br/><b>County</b>: LEE<br/>
      <b>Subjurisdiction</b>: AUBURN<br/>Precinct (realignment)<br/>Submission received</td></tr>
    </table>''', encoding="utf-8")
    rows = parse_html({"local_path": path})
    assert rows == [{"row_order": 0, "activity_date": "1998-04-06",
        "submission_number": "98-1444", "state": "ALABAMA", "county": "LEE",
        "subjurisdiction": "AUBURN", "activity": "Submission received",
        "change_description": "Precinct (realignment)",
        "raw_text": "State : ALABAMA County : LEE Subjurisdiction : AUBURN Precinct (realignment) Submission received"}]


def test_lifecycle_aggregation_keeps_non_candidates_and_flags_precinct_terms():
    frame = pd.DataFrame([
      {"submission_number":"98-1","state":"ALABAMA","county":"LEE","subjurisdiction":"AUBURN",
       "activity_date":"1998-01-01","notice_date":"1998-01-05","notice_id":"N1",
       "activity":"Submission received","change_description":"Precinct realignment"},
      {"submission_number":"98-1","state":"ALABAMA","county":"LEE","subjurisdiction":"AUBURN",
       "activity_date":"1998-02-01","notice_date":"1998-02-05","notice_id":"N2",
       "activity":"Withdrawal received","change_description":"Precinct realignment"},
      {"submission_number":"98-2","state":"ALABAMA","county":"LEE","subjurisdiction":"AUBURN",
       "activity_date":"1998-03-01","notice_date":"1998-03-05","notice_id":"N3",
       "activity":"Submission received","change_description":"Annexation"},
    ])
    got = aggregate_submissions(frame).set_index("submission_number")
    assert len(got) == 2
    assert got.loc["98-1", "precinct_candidate"] == 1
    assert got.loc["98-1", "withdrawn"] == 1
    assert got.loc["98-2", "classification_status"] == "retained_non_candidate"


def test_change_classifier_preserves_multiple_types():
    assert event_types("Precinct split, renumbering, and polling place change") == [
        "split", "renumber", "polling_place_change",
    ]
