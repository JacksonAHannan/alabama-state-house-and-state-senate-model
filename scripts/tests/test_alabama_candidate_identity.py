"""Contract tests for shared Alabama candidate identity resolution.

The properties here are what keep three products from publishing a source code
as a person's name, or merging two people because their names look alike.
"""
import pandas as pd
import pytest

from scripts import alabama_candidate_identity as identity


def test_stub_detection_covers_both_district_widths():
    # House districts are three digits, Senate districts two; an earlier
    # three-digit-only pattern published GSU12DMCC and GSU33DFIG as names.
    assert identity.is_stub_name("GSL019DHAL")
    assert identity.is_stub_name("GSU33DFIG")
    assert identity.is_stub_name("GSU12DMCC")
    assert identity.is_stub_person("ALPERSON-GSL019DHAL")
    assert identity.is_stub_person("ALPERSON-GSU33RRIE")
    for real in ("Laura Hall", "Kerry \"Bubba\" Underwood", "Frances Holk-Jones",
                 "ALPERSON-LAURA-HALL", "Mose Jones Jr."):
        assert not identity.is_stub_name(real)
        assert not identity.is_stub_person(real)


def test_verified_aliases_are_unique_and_cover_the_published_stubs():
    aliases = identity.verified_aliases()
    assert aliases, "adjudications must exist"
    candidates = pd.read_csv(
        identity.ROOT / "data/processed/elections/canonical_cmo_candidates.csv", low_memory=False)
    stubs = candidates[candidates.canonical_name.map(identity.is_stub_name)]
    assert not stubs.empty, "the 2022 canonical rows still carry source stubs"
    missing = set(stubs.canonical_candidate_id) - set(aliases)
    assert missing == set(), f"unadjudicated stubs would publish as codes: {sorted(missing)[:5]}"


def test_resolve_names_reports_where_each_name_came_from():
    frame = pd.DataFrame({
        "canonical_candidate_id": ["AL-2022-house-19-D-GSL019DHAL", "AL-1994-house-1-D-STARKEY",
                                   "AL-2022-house-99-D-GSL099DNOPE"],
        "canonical_name": ["GSL019DHAL", "Starkey", "GSL099DNOPE"],
    })
    resolved = identity.resolve_names(frame)
    assert resolved.name_source.tolist() == [
        "verified_adjudication", "canonical_election_record", "unresolved_source_stub"]
    assert resolved.resolved_name.iloc[0] and not identity.is_stub_name(resolved.resolved_name.iloc[0])
    assert resolved.resolved_name.iloc[1] == "Starkey"
    assert pd.isna(resolved.resolved_name.iloc[2]), "an unadjudicated stub is never given a name"


def test_career_folding_requires_an_unambiguous_resolved_name():
    frame = pd.DataFrame({
        "person_id": ["ALPERSON-JANE-DOE", "ALPERSON-GSL019DHAL", "ALPERSON-GSL052DROG",
                      "ALPERSON-PAT-ROE-A", "ALPERSON-PAT-ROE-B", "ALPERSON-GSU33DAMB"],
        "resolved_name": ["Jane Doe", "Jane Doe", None, "Pat Roe", "Pat Roe", "Pat Roe"],
    })
    folded = identity.career_identity(frame)
    assert folded.career_person_id.tolist() == [
        "ALPERSON-JANE-DOE", "ALPERSON-JANE-DOE", "ALPERSON-GSL052DROG",
        "ALPERSON-PAT-ROE-A", "ALPERSON-PAT-ROE-B", "ALPERSON-GSU33DAMB",
    ]
    assert folded.career_identity_method.tolist() == [
        "canonical_person_id", "stub_folded_by_exact_unique_name", "unresolved_source_stub",
        "canonical_person_id", "canonical_person_id", "unresolved_source_stub",
    ]


def test_normalize_ignores_suffixes_and_punctuation():
    assert identity.normalize("Mose Jones Jr.") == identity.normalize("mose jones")
    assert identity.normalize('Kerry "Bubba" Underwood') == "KERRY BUBBA UNDERWOOD"
    assert identity.normalize("Frances Holk-Jones") == "FRANCES HOLK JONES"
