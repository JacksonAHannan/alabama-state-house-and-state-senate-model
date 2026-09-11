from __future__ import annotations

import csv
import hashlib
import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "acquire_southern_campaign_finance.py"
SPEC = importlib.util.spec_from_file_location("southern_finance_acquisition", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def test_state_inventory_is_explicit_and_existing_sources_are_not_reacquired() -> None:
    states = {source.state for source in MOD.SOURCES}
    assert states == {"AL", "AR", "DE", "FL", "GA", "KY", "LA", "MD", "MS", "MO", "NC", "OK", "SC", "TN", "TX", "VA", "WV"}
    assert {spec["state"] for spec in MOD.DIRECT_FILES} == {"AR", "LA", "OK", "SC"}
    assert not ({"AL", "TX"} & {spec["state"] for spec in MOD.DIRECT_FILES})
    missouri = next(source for source in MOD.SOURCES if source.state == "MO")
    assert missouri.access_class == "unconfigured"


def test_direct_bulk_file_contracts_cover_target_period() -> None:
    la = [spec for spec in MOD.DIRECT_FILES if spec["state"] == "LA"]
    ok = [spec for spec in MOD.DIRECT_FILES if spec["state"] == "OK"]
    ar = [spec for spec in MOD.DIRECT_FILES if spec["state"] == "AR"]
    sc = [spec for spec in MOD.DIRECT_FILES if spec["state"] == "SC"]
    assert len(ar) == 6
    assert len(la) == 9
    assert len(ok) == 18
    assert len(sc) == 18
    assert {spec["data_kind"] for spec in la} == {"contributions", "loans", "expenditures"}
    assert {spec["cycle"] for spec in la} == {"2016-2019", "2020-2023", "2024-2027"}
    assert {int(spec["cycle"]) for spec in ok} == set(range(2016, 2025))
    assert {int(spec["cycle"]) for spec in ar} == {2022, 2023, 2024}
    assert {spec["data_kind"] for spec in ar} == {"contributions_and_loans", "expenditures"}
    assert all(spec["method"] == "POST" for spec in ar)
    assert all(spec["acquisition_method"] == "official_public_api_export" for spec in ar)
    assert {int(spec["cycle"]) for spec in sc} == set(range(2016, 2025))
    assert {spec["data_kind"] for spec in sc} == {"contributions", "expenditures"}
    assert all(spec["method"] == "POST" for spec in sc)
    assert all(spec["count_json_records"] for spec in sc)
    assert all(str(spec["url"]).startswith("https://www.ethics.la.gov/") for spec in la)
    assert all(str(spec["url"]).startswith("https://guardian.ok.gov/") for spec in ok)
    assert len({spec["name"] for spec in MOD.DIRECT_FILES}) == len(MOD.DIRECT_FILES)


def test_coverage_does_not_call_query_portals_complete() -> None:
    coverage, unresolved = MOD.build_coverage([], [])
    by_state = {row["state"]: row for row in coverage}
    assert by_state["AL"]["acquisition_status"] == "existing_not_reacquired"
    assert by_state["TX"]["acquisition_status"] == "existing_not_reacquired"
    assert by_state["AR"]["acquisition_status"] == "partial_bulk_incomplete"
    assert by_state["FL"]["acquisition_status"] == "partitioned_query_incomplete"
    assert by_state["MS"]["acquisition_status"] == "adapter_required"
    assert by_state["NC"]["acquisition_status"] == "form_query_incomplete"
    assert by_state["SC"]["acquisition_status"] == "annual_query_incomplete"
    assert by_state["MO"]["acquisition_status"] == "unconfigured"
    assert {row["state"] for row in unresolved} >= {"AR", "DE", "FL", "GA", "KY", "MD", "MS", "MO", "NC", "SC", "TN", "VA", "WV"}


def test_south_carolina_annual_json_query_contract() -> None:
    specs = MOD.south_carolina_files()
    contribution = next(
        spec for spec in specs
        if spec["cycle"] == "2024" and spec["data_kind"] == "contributions"
    )
    expenditure = next(
        spec for spec in specs
        if spec["cycle"] == "2024" and spec["data_kind"] == "expenditures"
    )
    assert contribution["json"]["contributionYear"] == 2024
    assert expenditure["json"]["expenditureYear"] == 2024
    assert contribution["query_scope"] == "year=2024;kind=contributions"
    assert expenditure["query_scope"] == "year=2024;kind=expenditures"
    assert contribution["url"].startswith("https://ethicsfiling.sc.gov/api/")


def test_florida_query_contract_is_legislative_partitioned_and_reproducible() -> None:
    spec = MOD.florida_query_spec("contributions", 2024, "STS", "A")
    assert spec["method"] == "POST"
    assert spec["data"]["election"] == "20241105-GEN"
    assert spec["data"]["office"] == "STS"
    assert spec["data"]["CanLName"] == "A"
    assert spec["data"]["CanNameSrch"] == "2"
    assert spec["data"]["queryformat"] == "2"
    assert spec["response_limit"] == 9999
    assert spec["request_parameters"]
    expenditure = MOD.florida_query_spec("expenditures", 2024, "STR", "B")
    assert expenditure["url"].endswith("/expend.exe")
    assert expenditure["expected_header"].endswith("Payee Name")
    assert "cpurpose" in expenditure["data"]


def test_florida_coverage_requires_every_cycle_chamber_kind_and_prefix() -> None:
    assert MOD.florida_query_coverage([]) == (0, 20)
    rows = []
    for year in MOD.FLORIDA_ELECTIONS:
        for office in MOD.FLORIDA_OFFICES:
            for kind in ("contributions", "expenditures"):
                for prefix in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    rows.append({
                        "state_code": "FL", "data_kind": kind,
                        "query_scope": f"year={year};office={office};surname_prefix={prefix}",
                        "ingest_status": "acquired_unparsed",
                    })
    assert MOD.florida_query_coverage(rows) == (20, 20)


def test_north_carolina_query_contract_and_coverage() -> None:
    assert 2015 in MOD.SOURCE_YEARS
    spec = MOD.north_carolina_spec(2024, "NSHS")
    assert spec["url"].endswith("/CFTxnLkup/Export")
    assert spec["query_scope"] == "year=2024;office=NSHS;committee_types=CNC,JNT"
    assert spec["name"] == "transactions_v2/2024/NSHS.csv"
    payload = MOD.north_carolina_search_payload(2024, "NSHS", "token")
    assert ("Filter.SelectedOfficeTypes", "NSHS") in payload
    assert ("Filter.SelectedCommitteeTypes", "CNC") in payload
    assert ("Filter.CommitteeAll", "true") not in payload
    assert ("Filter.StartDate", "01/01/2024") in payload
    assert ("Filter.EndDate", "12/31/2024") in payload
    assert MOD.north_carolina_query_coverage([]) == (0, 18)
    rows = [
        {
            "state_code": "NC", "ingest_status": "acquired_unparsed",
            "query_scope": f"year={year};office={office};committee_types=CNC,JNT",
        }
        for year in MOD.TARGET_YEARS
        for office in ("NCSN", "NSHS")
    ]
    assert MOD.north_carolina_query_coverage(rows) == (18, 18)


def test_tennessee_query_contract_and_coverage() -> None:
    contribution = MOD.tennessee_spec("contributions", 2016)
    expenditure = MOD.tennessee_spec("expenditures", 2016)
    assert contribution["query_scope"] == "year=2016;kind=contributions"
    assert "Recipient Name" in contribution["expected_header"]
    assert "Candidate/PAC Name" in expenditure["expected_header"]
    assert ("fromIndividual", "true") in MOD.tennessee_search_payload("contributions", 2016)
    assert ("toOther", "true") in MOD.tennessee_search_payload("expenditures", 2016)
    assert MOD.tennessee_query_coverage([]) == (0, 18)
    rows = [
        {
            "state_code": "TN", "ingest_status": "acquired_unparsed",
            "query_scope": f"year={year};kind={kind}",
        }
        for year in MOD.TARGET_YEARS
        for kind in ("contributions", "expenditures")
    ]
    assert MOD.tennessee_query_coverage(rows) == (18, 18)


def test_georgia_query_contract_and_coverage() -> None:
    contribution = MOD.georgia_spec("contributions", 2024)
    expenditure = MOD.georgia_spec("expenditures", 2024)
    assert contribution["url"].startswith("https://media.ethics.ga.gov/")
    assert "From=01%2F01%2F2024" in contribution["url"]
    assert contribution["name"].endswith(".csv")
    assert expenditure["name"].endswith(".xls")
    assert expenditure["expected_header"] == "<table"
    assert contribution["query_scope"].startswith("system=legacy;")
    modern = MOD.georgia_modern_spec("contributions", 2024, 1)
    assert modern["name"].startswith("recordsearch_v2/")
    assert modern["query_scope"] == "system=recordsearch;year=2024;month=01;kind=contributions"
    assert modern["payload"]["transactionDetailsSearchFilter"]["committeeType"] == "CAN"
    assert MOD.georgia_query_coverage([]) == (0, 84)
    rows = [
        {
            "state_code": "GA", "ingest_status": "acquired_unparsed",
            "query_scope": f"system=legacy;year={year};kind={kind}",
        }
        for year in range(2016, 2022)
        for kind in ("contributions", "expenditures")
    ]
    rows.extend([
        {
            "state_code": "GA", "ingest_status": "acquired_unparsed",
            "query_scope": (
                f"system=recordsearch;year={year};month={month:02d};kind={kind}"
            ),
        }
        for year in (2022, 2023, 2024)
        for month in range(1, 13)
        for kind in ("contributions", "expenditures")
    ])
    assert MOD.georgia_query_coverage(rows) == (84, 84)


def test_georgia_provider_anomaly_does_not_pass_as_complete() -> None:
    rows = [
        {
            "state_code": "GA", "record_count": "0",
            "query_scope": (
                f"system=recordsearch;year=2024;month={month:02d};kind={kind}"
            ),
        }
        for month in range(1, 13)
        for kind in ("contributions", "expenditures")
    ]
    anomalies = MOD.georgia_recordsearch_anomalies(rows)
    assert len(anomalies) == 2
    assert any("contributions" in anomaly for anomaly in anomalies)
    assert any("expenditures" in anomaly for anomaly in anomalies)


def test_generated_manifest_is_traceable_when_present() -> None:
    if not MOD.MANIFEST_PATH.exists():
        return
    with MOD.MANIFEST_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert set(MOD.MANIFEST_FIELDS) <= set(rows[0])
    for row in rows:
        source = MOD.ROOT / row["local_path"]
        assert source.is_file()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert row["sha256"] == digest
        assert int(row["size_bytes"]) == source.stat().st_size
        assert row["ingest_status"] in {"acquired_unparsed", "acquired_truncated"}
        assert row["geography_vintage"] == "not_applicable"
