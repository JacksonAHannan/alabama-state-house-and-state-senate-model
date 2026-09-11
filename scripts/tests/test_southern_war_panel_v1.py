from pathlib import Path
import importlib.util
import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "build_southern_war_panel_v1.py"
SPEC = importlib.util.spec_from_file_location("southern_war_panel_v1", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_louisiana_stage_selection_and_cycle_coverage():
    outcomes, candidates, contests = MOD.load_louisiana_official_outcomes()
    expected_years = {1995, 1999, 2003, 2007, 2011, 2015, 2019, 2023}
    assert set(outcomes.year) == expected_years
    assert set(candidates.election_stage) == {"first_round", "runoff"}
    assert set(contests.election_stage) == {"first_round", "runoff"}
    assert not outcomes.duplicated(MOD.KEYS).any()
    assert not contests.duplicated(MOD.KEYS + ["election_stage"]).any()

    runoff_keys = set(
        contests.loc[contests.election_stage.eq("runoff"), MOD.KEYS]
        .itertuples(index=False, name=None)
    )
    selected_runoff_keys = set(
        outcomes.loc[outcomes.election_stage.eq("runoff"), MOD.KEYS]
        .itertuples(index=False, name=None)
    )
    assert selected_runoff_keys == runoff_keys
    selected_first_round_keys = set(
        outcomes.loc[outcomes.election_stage.eq("first_round"), MOD.KEYS]
        .itertuples(index=False, name=None)
    )
    assert selected_first_round_keys.isdisjoint(runoff_keys)


def test_louisiana_first_round_is_retained_when_runoff_is_final():
    outcomes, candidates, contests = MOD.load_louisiana_official_outcomes()
    runoff_keys = set(
        outcomes.loc[outcomes.election_stage.eq("runoff"), MOD.KEYS]
        .itertuples(index=False, name=None)
    )
    first_round_keys = set(
        contests.loc[contests.election_stage.eq("first_round"), MOD.KEYS]
        .itertuples(index=False, name=None)
    )
    candidate_first_round_keys = set(
        candidates.loc[candidates.election_stage.eq("first_round"), MOD.KEYS]
        .itertuples(index=False, name=None)
    )
    assert runoff_keys <= first_round_keys
    assert runoff_keys <= candidate_first_round_keys
    assert candidates.loc[
        candidates.election_stage.eq("first_round")
        & candidates.set_index(MOD.KEYS).index.isin(runoff_keys),
        "is_final_stage",
    ].eq(False).all()


def test_louisiana_regular_panel_excludes_unexpired_term_duplicates():
    _, candidates, contests = MOD.load_louisiana_official_outcomes()
    assert not candidates.office.str.contains("Unexp", case=False, na=False).any()
    assert not contests.office.str.contains("Unexp", case=False, na=False).any()


def test_manifested_medsl_archives_are_admitted_for_2022_and_2024():
    frames = MOD._medsl_state_frames()
    sources = {(state, year, source) for state, year, source, _ in frames}
    assert any(state == "KY" and year == 2022 and "medsl_github/2022" in source for state, year, source in sources)
    assert any(state == "KY" and year == 2016 and "medsl_github/2016" in source for state, year, source in sources)
    assert any(state == "AR" and year == 2024 and "medsl_github/2024" in source for state, year, source in sources)


def test_manifested_medsl_ticket_context_has_complete_district_coverage():
    _, baselines, _ = MOD.build_medsl_observations()
    manifested = baselines[
        baselines.baseline_source_path.str.contains("medsl_github", na=False)
    ]
    assert set(zip(manifested.state, manifested.year)) == {
        ("KY", 2016),
        ("KY", 2022), ("MO", 2022), ("OK", 2022), ("SC", 2022),
        ("AR", 2024), ("KY", 2024), ("OK", 2024), ("SC", 2024), ("TN", 2024),
    }
    assert manifested.strict_baseline_eligible.all()
    assert manifested.baseline_coverage.ge(0.95).all()


def test_mississippi_2023_context_is_complete_and_same_cycle():
    outcomes, baselines = MOD.load_mississippi_2023_context()
    assert len(outcomes) == 25
    assert not outcomes.duplicated(MOD.KEYS).any()
    assert set(outcomes.chamber) == {"house", "senate"}
    assert baselines.strict_baseline_eligible.all()
    assert baselines.baseline_coverage.eq(1.0).all()
    assert set(baselines.baseline_class) == {"observed_same_cycle_ticket"}


def test_virginia_2023_offyear_policy_never_promotes_to_strict():
    outcomes, baselines = MOD.load_virginia_2023_context()
    assert len(outcomes) == 99
    assert not outcomes.duplicated(MOD.KEYS).any()
    assert baselines.research_baseline_eligible.all()
    assert not baselines.strict_baseline_eligible.any()
    assert set(baselines.baseline_class) == {"observed_prior_cycle_ticket"}
    assert baselines.baseline_coverage.between(0, 1).all()


def test_downloaded_official_long_files_fill_target_ticket_baselines():
    baselines = MOD.load_official_long_ticket_baselines()
    expected = {
        ("AR", 2016), ("FL", 2016), ("FL", 2018), ("FL", 2022), ("FL", 2024),
        ("NC", 2016), ("NC", 2022), ("OK", 2016), ("TN", 2016),
    }
    assert expected == set(zip(baselines.state, baselines.year))
    assert baselines.strict_baseline_eligible.all()
    assert baselines.baseline_coverage.ge(0.95).all()
    assert set(baselines.loc[baselines.year.eq(2022), "baseline_office"]) == {"US SENATE"}


def test_arkansas_2022_ticket_adapter_covers_contested_district_inputs():
    baselines = MOD.load_arkansas_2022_baselines()
    assert not baselines.duplicated(MOD.KEYS).any()
    assert baselines.groupby("chamber").size().to_dict() == {"house": 100, "senate": 35}
    assert set(baselines.baseline_office) == {"US SENATE"}
    assert baselines.research_baseline_eligible.sum() >= 130
    assert baselines.strict_baseline_eligible.sum() >= 125


def test_recent_georgia_and_tennessee_wide_adapters_are_complete():
    baselines = MOD.load_georgia_tennessee_2022_2024_baselines()
    assert not baselines.duplicated(MOD.KEYS).any()
    assert baselines.groupby(["state", "year", "chamber"]).size().to_dict() == {
        ("GA", 2022, "house"): 180,
        ("GA", 2022, "senate"): 56,
        ("GA", 2024, "house"): 180,
        ("GA", 2024, "senate"): 56,
        ("TN", 2022, "house"): 99,
        ("TN", 2022, "senate"): 17,
    }
    assert baselines.strict_baseline_eligible.all()
    assert baselines.baseline_coverage.ge(0.95).all()


def test_south_carolina_2016_fixed_width_adapter_covers_both_chambers():
    baselines = MOD.load_south_carolina_2016_baselines()
    assert baselines.groupby("chamber").size().to_dict() == {"house": 124, "senate": 46}
    assert baselines.strict_baseline_eligible.all()
    assert baselines.baseline_coverage.eq(1.0).all()


def test_virginia_2017_2021_policy_is_complete_but_research_only():
    baselines = MOD.load_virginia_2017_2021_research_baselines()
    assert baselines.groupby(["year", "chamber"]).size().to_dict() == {
        (2017, "house"): 100, (2017, "senate"): 40,
        (2019, "house"): 100, (2019, "senate"): 40,
        (2021, "house"): 100, (2021, "senate"): 40,
    }
    assert baselines.research_baseline_eligible.all()
    assert not baselines.strict_baseline_eligible.any()


def test_virginia_no_ticket_cycles_use_election_day_generic_ballot():
    # Use the published panel keys because the generic environment is a
    # national value replicated only to modeled Virginia contests.
    published = pd.read_csv(MOD.OUT / "southern_war_panel.csv", low_memory=False)
    baselines = MOD.load_virginia_generic_ballot_baselines(published)
    assert set(baselines.year) == {2019, 2023}
    assert set(baselines.baseline_class) == {"national_environment_generic_ballot"}
    assert baselines.strict_baseline_eligible.all()
    margins = baselines.groupby("year").baseline_dem_margin.first().to_dict()
    assert round(margins[2019], 3) == 5.441
    assert round(margins[2023], 3) == 0.520


def test_louisiana_modern_ticket_baselines_cover_every_observed_district():
    outcomes, _, _ = MOD.load_louisiana_official_outcomes()
    baselines, audit = MOD.load_louisiana_modern_baselines(outcomes)
    modern = outcomes[outcomes.year.isin([2019, 2023])]
    assert not baselines.duplicated(MOD.KEYS).any()
    assert set(modern[MOD.KEYS].itertuples(index=False, name=None)) == set(
        baselines[MOD.KEYS].itertuples(index=False, name=None)
    )
    assert baselines.baseline_dem_margin.notna().all()
    assert baselines.strict_baseline_eligible.all()
    assert baselines.baseline_coverage.ge(0.95).all()
    assert audit.loc[audit.year.eq(2019), "match_rate"].eq(1.0).all()
