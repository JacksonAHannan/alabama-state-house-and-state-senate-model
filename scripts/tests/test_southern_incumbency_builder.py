from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "build_southern_incumbents.py"
SPEC = importlib.util.spec_from_file_location("southern_incumbency_builder", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_scope_and_order_insensitive_exact_name_contract() -> None:
    assert set(MOD.TARGET_STATES) == {
        "AL", "AR", "FL", "GA", "KY", "LA", "MO", "MS",
        "NC", "OK", "SC", "TN", "TX", "VA",
    }
    assert MOD.normalized_name("Salzman, Michelle") == MOD.normalized_name("Michelle Salzman")
    assert len(list(MOD.page_specs())) == 116


def test_published_roster_preserves_florida_sd20_open_seat() -> None:
    roster = pd.read_csv(
        MOD.OUT_DIR / "southern_incumbency_race_roster_2016_2024.csv",
        dtype={"district": str},
    )
    assert len(roster) == 4582
    assert not roster.duplicated(["state_code", "cycle", "chamber", "district"]).any()
    manifest = json.loads(
        (MOD.AUDIT_DIR / "southern_incumbency_2016_2024_manifest.json").read_text()
    )
    assert int(roster.strict_incumbency_eligible.sum()) == manifest["strict_ready"]
    row = roster[
        roster.state_code.eq("FL") & roster.cycle.eq(2020)
        & roster.chamber.eq("upper") & roster.district.eq("20")
    ].iloc[0]
    assert row.open_seat == 1
    assert row.incumbency_balance == 0
    assert row.incumbency_method == "approved_manual_adjudication"


def test_published_roster_marks_dexter_grimsley_incumbent() -> None:
    roster = pd.read_csv(
        MOD.OUT_DIR / "southern_incumbency_race_roster_2016_2024.csv",
        dtype={"district": str},
    )
    row = roster[
        roster.state_code.eq("AL") & roster.cycle.eq(2022)
        & roster.chamber.eq("lower") & roster.district.eq("85")
    ].iloc[0]
    assert row.dem_incumbent == 1
    assert row.rep_incumbent == 0
    assert row.incumbency_balance == 1
    assert row.strict_incumbency_eligible == 1


def test_party_scoped_positive_evidence_resolves_opaque_candidate_code() -> None:
    evidence = pd.DataFrame([{
        "incumbent_name": "GRIMSLEY, DEXTER",
        "party_family": "democratic",
        "method": "canonical_alabama_incumbency_roster",
    }])
    records = MOD.scoped_provider_records(
        evidence,
        {"democratic": "GSL085DGRI", "republican": "GSL085RREH"},
    )
    assert len(records) == 1
    assert records[0]["party_family"] == "democratic"
    assert records[0]["coverage_status"].endswith("exact_race_party_alabama_decoded_roster")


def test_unknown_party_evidence_still_requires_name_match() -> None:
    evidence = pd.DataFrame([{
        "incumbent_name": "Unrelated Person",
        "party_family": "unknown",
        "method": "fixture",
    }])
    assert MOD.scoped_provider_records(
        evidence,
        {"democratic": "Jane Doe", "republican": "John Smith"},
    ) == []


def test_retiring_incumbent_is_not_attached_to_same_party_successor() -> None:
    evidence = pd.DataFrame([{
        "incumbent_name": "DERBY, DAVID",
        "party_family": "republican",
        "method": "provider_reported_incumbent",
    }])
    explicit_open = pd.DataFrame([{
        "incumbent_name": "David Derby",
        "party_family": "republican",
    }])
    assert MOD.scoped_provider_records(
        evidence,
        {"democratic": "Jeri Moberly", "republican": "Dale Derby"},
        explicit_open,
    ) == []


def test_compound_and_former_surname_alias_is_retained() -> None:
    evidence = pd.DataFrame([{
        "incumbent_name": "PRICEHARRISON, MARY P (PRICEY)",
        "party_family": "democratic",
        "method": "provider_reported_incumbent",
    }])
    records = MOD.scoped_provider_records(
        evidence,
        {"democratic": 'Mary Price "Pricey" Harrison', "republican": "John Doe"},
    )
    assert len(records) == 1
    assert records[0]["coverage_status"].endswith("exact_race_party_and_surname")


def test_wikipedia_explicit_incumbent_table_is_parseable(tmp_path: Path) -> None:
    payload = {
        "parse": {"wikitext": {"*": """
===House District 1===
{| class="wikitable"
|-
| Republican || [[Jane Doe]] (incumbent) || 10,000
|}
"""}}
    }
    source = tmp_path / "wikipedia.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    manifest = pd.DataFrame([{
        "provider": "wikipedia", "acquisition_status": "acquired",
        "local_path": str(source), "state_code": "VA", "cycle": 2023,
        "chamber": "lower", "source_url": "https://en.wikipedia.org/wiki/fixture",
        "sha256": "fixture",
    }])
    parsed = MOD.parse_wikipedia_candidate_incumbents(manifest)
    assert len(parsed) == 1
    row = parsed.iloc[0]
    assert (row.district, row.incumbent_name, row.party_family) == ("1", "Jane Doe", "republican")
