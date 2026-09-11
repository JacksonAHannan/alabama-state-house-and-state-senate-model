from pathlib import Path
import importlib.util

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "identity_repair", ROOT / "scripts" / "repair_candidate_legislator_identities.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_numeric_district_parses_prefixed_labels():
    assert MODULE.numeric_district("HD-086") == 86
    assert MODULE.numeric_district("SD-025") == 25


def test_name_normalization_handles_suffixes_and_nicknames():
    assert MODULE.normalized_name('John "Jack" Smith, Jr.') == "JOHN SMITH"


def test_recorded_role_overrides_future_district_prefix_on_transition_rows():
    members = MODULE.load_members()
    beasley_2010 = members[(members.people_id == 3386) & (members.session_year == 2010)].iloc[0]
    ward_2010 = members[(members.people_id == 3405) & (members.session_year == 2010)].iloc[0]
    assert beasley_2010.chamber == "house"
    assert ward_2010.chamber == "house"


def test_2022_ballot_codes_are_decoded():
    crosswalk = pd.read_csv(ROOT / "data/processed/ideology/candidate_legislator_identity_crosswalk.csv")
    codes = crosswalk[(crosswalk.year == 2022) & crosswalk.canonical_name.str.startswith("GSL", na=False)]
    assert len(codes) > 100
    assert not codes.resolved_name.fillna("").str.startswith("GSL").any()


def test_no_duplicate_cycle_member_assignment():
    crosswalk = pd.read_csv(ROOT / "data/processed/ideology/candidate_legislator_identity_crosswalk.csv")
    linked = crosswalk[crosswalk.member_source_id.notna()]
    assert not linked.duplicated(["year", "chamber", "member_source_id"]).any()


def test_reviewed_nickname_and_cross_chamber_identities_are_linked():
    crosswalk = pd.read_csv(ROOT / "data/processed/ideology/candidate_legislator_identity_crosswalk.csv")
    expected = {
        "AL-2010-senate-14-R-CAM-WARD": "LEGISCAN-3405",
        "AL-2018-senate-28-D-BILLY-BEASLEY": "LEGISCAN-3386",
        "AL-2018-senate-6-D-JOHNNY-MACK-MORROW": "LEGISCAN-3402",
        "AL-2018-house-2-R-LYNN-GREER": "LEGISCAN-12488",
    }
    observed = crosswalk.set_index("canonical_candidate_id").member_source_id.to_dict()
    for candidate_id, member_id in expected.items():
        assert observed[candidate_id] == member_id


def test_house_ballot_codes_do_not_inherit_same_number_senators():
    crosswalk = pd.read_csv(ROOT / "data/processed/ideology/candidate_legislator_identity_crosswalk.csv")
    false_old_links = {
        "AL-2022-house-26-D-GSL026DALF": "LEGISCAN-21299",
        "AL-2022-house-32-R-GSL032RJAC": "LEGISCAN-21169",
        "AL-2022-house-33-D-GSL033DCRU": "LEGISCAN-3490",
    }
    observed = crosswalk.set_index("canonical_candidate_id").member_source_id.to_dict()
    for candidate_id, wrong_member_id in false_old_links.items():
        assert observed[candidate_id] != wrong_member_id


def test_same_name_house_and_senate_members_are_disambiguated_by_district():
    crosswalk = pd.read_csv(ROOT / "data/processed/ideology/candidate_legislator_identity_crosswalk.csv")
    indexed = crosswalk.set_index("canonical_candidate_id")
    assert indexed.loc["AL-2014-house-6-R-PHIL-WILLIAMS", "member_source_id"] == "LEGISCAN-3437"
    assert indexed.loc["AL-2014-senate-10-R-PHIL-WILLIAMS", "member_source_id"] == "LEGISCAN-12498"


def test_pre_election_windows_do_not_leak_future_votes():
    ideology = pd.read_csv(ROOT / "data/processed/ideology/candidate_ideology_full_universe.csv")
    scored = ideology[ideology.legislative_ideology_available]
    assert not scored.duplicated(["year", "chamber", "member_source_id"]).any()
    ambiguous = ideology[ideology.identity_status.eq("ambiguous")]
    assert not ambiguous.legislative_ideology_available.any()
    assert (scored.window_end <= scored.year).all()
    assert (scored.window_start <= scored.window_end).all()
    assert scored.score_chamber.isin(["house", "senate"]).all()


def test_cross_chamber_candidates_keep_the_source_vote_chamber():
    ideology = pd.read_csv(ROOT / "data/processed/ideology/candidate_ideology_full_universe.csv")
    indexed = ideology.set_index("canonical_candidate_id")
    expected = {
        "AL-2010-senate-14-R-CAM-WARD": "house",
        "AL-2010-senate-28-D-BILLY-BEASLEY": "house",
        "AL-2018-senate-6-D-JOHNNY-MACK-MORROW": "house",
    }
    for candidate_id, score_chamber in expected.items():
        row = indexed.loc[candidate_id]
        assert bool(row.legislative_ideology_available)
        assert row.chamber == "senate"
        assert row.score_chamber == score_chamber


def test_prior_winner_inference_recovers_historical_incumbent_score():
    ideology = pd.read_csv(ROOT / "data/processed/ideology/candidate_ideology_full_universe.csv")
    fuller = ideology[ideology.canonical_candidate_id == "AL-1998-house-38-D-FULLER"].iloc[0]
    assert bool(fuller.expected_prior_officeholder)
    assert bool(fuller.legislative_ideology_available)
    assert fuller.member_source_id == "AL1996L102"


def test_known_false_historical_assignments_are_quarantined():
    ideology = pd.read_csv(ROOT / "data/processed/ideology/candidate_ideology_full_universe.csv")
    indexed = ideology.set_index("canonical_candidate_id")
    assert not bool(indexed.loc["AL-2010-house-7-D-JOHN-JODY-LETSON",
                                "legislative_ideology_available"])
    assert not bool(indexed.loc["AL-2010-senate-5-R-GREG-REED",
                                "legislative_ideology_available"])
    assert not bool(indexed.loc["AL-2022-house-26-D-GSL026DALF",
                                "legislative_ideology_available"])


def test_career_and_long_service_coverage():
    career = pd.read_csv(ROOT / "data/processed/ideology/candidate_career_ideology_through_2026.csv")
    assert not career.duplicated(["chamber", "member_source_id"]).any()
    assert (career.career_window_end == 2026).all()
    audit = pd.read_csv(ROOT / "data/processed/ideology/long_service_ideology_coverage_audit.csv")
    assert (audit.sessions >= 4).all()
    assert (audit.raw_recorded_votes > 0).all()
    assert (audit.classified_votes > 0).all()
    assert audit.coverage_flag.eq("covered").all()
