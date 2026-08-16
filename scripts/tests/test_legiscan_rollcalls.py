import json
from pathlib import Path
import zipfile

from scripts.import_legiscan_alabama_rollcalls import infer_year, normalize_name, parse_archives


def _write_json(archive, name, value):
    archive.writestr(name, json.dumps(value))


def test_normalize_name_removes_suffixes_and_punctuation():
    assert normalize_name("William J. Smith, Jr.") == "WILLIAM J SMITH"


def test_year_is_inferred_from_legiscan_archive_filename():
    assert infer_year(None, "AL_2014-2014_Regular_Session_JSON.zip") == 2014


def test_parse_legiscan_api_json_archive(tmp_path: Path):
    archive_path = tmp_path / "AL_2010.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        _write_json(archive, "bill/1.json", {"bill": {
            "bill_id": 1,
            "session": {"session_id": 10, "session_name": "2010 Regular Session"},
            "bill_number": "HB1", "title": "Example bill", "description": "Example",
        }})
        _write_json(archive, "people/101.json", {"person": {
            "people_id": 101, "name": "Billy Beasley", "party": "D",
            "role": "Senator", "district": "28", "year": 2010,
        }})
        _write_json(archive, "vote/500.json", {"roll_call": {
            "roll_call_id": 500, "bill_id": 1, "date": "2010-03-01",
            "chamber": "S", "yea": 1, "nay": 1, "nv": 0, "absent": 0,
            "total": 2, "votes": [
                {"people_id": 101, "vote_id": 1},
                {"people_id": 102, "vote_text": "Nay"},
            ],
        }})

    bills, rolls, people, votes, manifest = parse_archives([archive_path])

    assert bills.loc[0, "bill_number"] == "HB1"
    assert rolls.loc[0, "chamber"] == "senate"
    assert people.loc[0, "normalized_name"] == "BILLY BEASLEY"
    assert set(votes["vote"]) == {"Yea", "Nay"}
    assert set(votes["session_year"]) == {2010}
    assert manifest.loc[0, "sha256"]
