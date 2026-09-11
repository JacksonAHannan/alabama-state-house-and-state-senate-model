from pathlib import Path
import importlib.util
import sys
import csv
import hashlib


SCRIPT = Path(__file__).resolve().parents[1] / "acquire_southern_sos_precinct_results.py"
SPEC = importlib.util.spec_from_file_location("southern_sos", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def test_official_domain_allows_subdomains_but_not_impostors():
    domains = ("ncsbe.gov", "s3.amazonaws.com")
    assert MOD.official("https://www.ncsbe.gov/file.zip", domains)
    assert MOD.official("https://s3.amazonaws.com/dl.ncsbe.gov/file.zip", domains)
    assert not MOD.official("https://ncsbe.gov.example.com/file.zip", domains)


def test_target_year_and_granularity_inference():
    assert MOD.infer_year("2016 Nov 08 Election - Results (ZIP)", "x.zip", MOD.TARGET_EVEN) == 2016
    assert MOD.infer_year("2015 General", "x.zip", MOD.TARGET_ODD) == 2015
    assert MOD.coverage_hint("Results by precinct", "x.zip") == "precinct"
    assert MOD.coverage_hint("County recap", "x.xlsx") == "county"
    assert MOD.infer_year("2010 results", "/archive/2014/otherstats.txt", MOD.TARGET_EVEN) == 2014
    assert MOD.infer_year("results", "/2010-2019/2014/statprct.txt", MOD.TARGET_EVEN) == 2014
    registration = b"COMMONWEALTH OF KENTUCKY - VOTER REGISTRATION STATISTICS REPORT"
    assert MOD.refine_coverage("precinct", registration) == "registration"


def test_texas_is_not_reacquired():
    assert "TX" not in {source.state for source in MOD.SOURCES}


def test_raw_write_is_immutable(tmp_path):
    target = tmp_path / "source.zip"
    MOD.write_once(target, b"same")
    MOD.write_once(target, b"same")
    try:
        MOD.write_once(target, b"different")
    except RuntimeError:
        pass
    else:
        raise AssertionError("changed source bytes should not overwrite raw evidence")


def test_generated_manifest_is_traceable_and_texas_free():
    manifest_path = MOD.AUDIT / "southern_sos_download_manifest.csv"
    rows = list(csv.DictReader(manifest_path.open(encoding="utf-8-sig")))
    assert rows
    assert all(row["state"] != "TX" for row in rows)
    for row in rows:
        source = MOD.ROOT / row["local_path"]
        assert source.is_file()
        assert int(row["size_bytes"]) == source.stat().st_size
        assert row["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_north_carolina_has_downloaded_precinct_cycles():
    rows = list(csv.DictReader((MOD.AUDIT / "southern_sos_precinct_inventory.csv").open(encoding="utf-8-sig")))
    nc = {int(row["election_year"]): row["status"] for row in rows if row["state"] == "NC"}
    assert nc[2000] == "downloaded_precinct"
    assert nc[2016] == "downloaded_precinct"


def test_louisiana_legislative_cycles_are_precinct_downloads():
    rows = list(csv.DictReader((MOD.AUDIT / "louisiana_legislative_results_coverage.csv").open(encoding="utf-8-sig")))
    expected = {
        (year, stage, date)
        for year, stages in MOD.LA_LEGISLATIVE_ELECTION_DATES.items()
        for stage, date in stages.items()
    }
    observed = {(int(row["election_year"]), row["election_stage"], row["election_date"]) for row in rows}
    assert observed == expected
    assert all(row["status"] == "complete" for row in rows)
    assert all(int(row["race_index_downloaded"]) == 1 for row in rows)
    assert all(int(row["legislative_contest_files"]) > 0 for row in rows)
    assert all(int(row["failed_downloads"]) == 0 for row in rows)


def test_louisiana_manifest_preserves_round_and_valid_precinct_files():
    manifest_path = MOD.AUDIT / "louisiana_legislative_results_manifest.csv"
    rows = list(csv.DictReader(manifest_path.open(encoding="utf-8-sig")))
    precinct = [row for row in rows if row["coverage"] == "precinct"]
    assert precinct
    assert {row["election_stage"] for row in precinct} == {"first_round", "runoff"}
    for row in precinct:
        source = MOD.ROOT / row["local_path"]
        assert source.is_file()
        assert source.read_bytes().startswith(b"Office,Parish,Ward,Precinct")
        assert row["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_manual_access_has_exact_georgia_downloads_and_destinations():
    rows = list(csv.DictReader((MOD.AUDIT / "southern_sos_manual_access.csv").open(encoding="utf-8-sig")))
    georgia = [row for row in rows if row["state"] == "GA" and row["access_status"] == "manual_browser_download"]
    assert {row["cycles"] for row in georgia} == {"2012", "2014", "2016"}
    assert all(row["url"].endswith(".zip") for row in georgia)
    assert all(row["save_under"].startswith("data/raw/southern_sos_elections/GA/") for row in georgia)
