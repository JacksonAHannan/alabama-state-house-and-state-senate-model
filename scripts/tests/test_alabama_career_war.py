"""Contract tests for career cumulative WAR and the fixed-reference wording."""
import json

import pandas as pd
import pytest

from scripts import build_alabama_career_war as career


@pytest.fixture(scope="module")
def table():
    return pd.read_csv(career.OUT / "career_war.csv")


@pytest.fixture(scope="module")
def manifest():
    return json.loads((career.OUT / "manifest.json").read_text(encoding="utf-8"))


def test_career_war_sums_the_scored_cycles(table):
    source = pd.read_csv(career.SOURCE, low_memory=False)
    scored = source[source.candidate_cycle_war.notna()]
    assert int(table.cycles_scored.sum()) == len(scored)
    assert table.career_war.sum() == pytest.approx(scored.candidate_cycle_war.sum(), abs=1e-6)
    multi = table[table.cycles_scored.gt(1)]
    assert not multi.empty
    assert (multi.career_war.abs() >= multi.mean_cycle_war.abs() - 1e-9).all()


def test_identity_folding_is_recorded_and_never_guessed(manifest):
    methods = manifest["diagnostics"]["identity_methods"]
    assert set(methods) <= {"canonical_person_id", "stub_folded_by_exact_unique_name",
                            "unresolved_source_stub"}
    # Adjudicated names let a stub join an earlier career; a 2022-only person
    # still stands alone rather than being merged on a guess.
    assert methods.get("stub_folded_by_exact_unique_name", 0) > 0
    assert manifest["historical_war_run_id"].startswith("AL-HIST-WAR-V1-")


def test_page_uses_fixed_reference_language_and_publishes_careers():
    page = (career.ROOT / "artifacts" / "site" / "alabama-legislative-cmo.html").read_text(encoding="utf-8")
    assert 'id="career"' in page
    assert "Career cumulative WAR" in page
    assert "data/alabama_career_war_v1_career_war.csv" in page
    assert "fixed 2018\u201324 reference model" in page
    assert "Fixed 2018-24 reference" in page
    # The retired framing must not return to reader-facing copy.
    assert "Modern-model backcast" not in page
    assert "It is explicitly a historical backcast" not in page
