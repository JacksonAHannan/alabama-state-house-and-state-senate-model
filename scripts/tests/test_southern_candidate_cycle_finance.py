from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "build_southern_candidate_cycle_finance.py"
SCRIPT_DIR = str(SCRIPT.parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
SPEC = importlib.util.spec_from_file_location("southern_candidate_cycle_finance", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def test_intervals_overlap_rejects_intersecting_periods() -> None:
    clean = pd.DataFrame({
        "period_start": pd.to_datetime(["2024-01-01", "2024-04-01"]),
        "period_end": pd.to_datetime(["2024-03-31", "2024-06-30"]),
    })
    overlap = pd.DataFrame({
        "period_start": pd.to_datetime(["2024-01-01", "2024-03-15"]),
        "period_end": pd.to_datetime(["2024-03-31", "2024-06-30"]),
    })
    assert not MOD.intervals_overlap(clean)
    assert MOD.intervals_overlap(overlap)


def test_zero_dollar_overlap_can_be_removed_without_changing_total() -> None:
    frame = pd.DataFrame({
        "period_start": pd.to_datetime(["2024-01-01", "2024-01-01"]),
        "period_end": pd.to_datetime(["2024-03-31", "2024-12-31"]),
        "monetary_receipts": [125.0, 0.0],
    })
    selected = MOD.drop_zero_overlapping_periods(frame)
    assert len(selected) == 1
    assert selected.monetary_receipts.sum() == 125.0


def test_strictly_contained_interim_period_is_not_double_counted() -> None:
    frame = pd.DataFrame({
        "report_id": ["pre-election", "quarter"],
        "period_start": pd.to_datetime(["2024-04-01", "2024-04-01"]),
        "period_end": pd.to_datetime(["2024-05-09", "2024-06-30"]),
        "monetary_receipts": [25.0, 100.0],
    })
    selected = MOD.drop_strictly_contained_report_periods(frame)
    assert selected.report_id.tolist() == ["quarter"]
    assert selected.monetary_receipts.sum() == 100.0


def test_partial_period_overlap_remains_for_review() -> None:
    frame = pd.DataFrame({
        "report_id": ["one", "two"],
        "period_start": pd.to_datetime(["2024-01-01", "2024-03-15"]),
        "period_end": pd.to_datetime(["2024-03-31", "2024-06-30"]),
        "monetary_receipts": [25.0, 100.0],
    })
    selected = MOD.drop_strictly_contained_report_periods(frame)
    assert len(selected) == 2
    assert MOD.intervals_overlap(selected)


def test_south_carolina_uses_official_election_cycle_totals() -> None:
    candidates, periods = MOD.aggregate_sc()
    assert len(candidates) >= 922
    assert not candidates.duplicated(MOD.KEY).any()
    assert candidates.finance_observation_status.isin(
        {"observed_zero", "observed_positive"}
    ).all()
    assert periods.cycle_monetary_receipts.notna().all()
    assert (
        candidates.total_fundraising.round(2)
        == (
            candidates.cash_contributions + candidates.other_receipts
        ).round(2)
    ).all()
    formerly_overlapping = candidates[
        candidates.cycle.eq(2016) & candidates.chamber.eq("house")
        & candidates.district.eq(39) & candidates.party.eq("D")
    ].iloc[0]
    assert formerly_overlapping.finance_observation_status == "observed_positive"
    assert "election_cycle_total_per_campaign" in (
        formerly_overlapping.aggregation_status
    )


def test_arkansas_legacy_parser_reads_flattened_layout_values() -> None:
    text = """
    SUMMARY FOR REPORTING PERIOD CUMULATIVE TOTAL
    6. Total Loans (enter total from line 12)             0.00        500.00
    7. Total Monetary Contributions (enter total from line 18) 1,550.00 29,155.11
    8. Total Expenditures (enter total from line 27)      8,044.00 29,155.11
    9. Carryover Funds or Debt at close of election                         0.00
    """
    parsed = MOD.parse_ar_legacy_report_text(text)
    assert parsed["monetary_contributions"] == 29155.11
    assert parsed["expenditures"] == 29155.11
    assert parsed["loans"] == 500.0
    assert parsed["ending_cash"] == 0.0


def test_arkansas_secondary_fallback_only_fills_official_gaps() -> None:
    candidates = MOD.arkansas_rows()
    assert len(candidates) >= 756
    assert not candidates.duplicated(MOD.KEY).any()
    assert candidates.finance_observation_status.isin(
        {"observed_zero", "observed_positive"}
    ).all()
    assert candidates.source_name.str.contains(
        "Arkansas Secretary of State|FollowTheMoney.org", regex=True
    ).all()
    assert candidates.source_name.str.contains("Arkansas Secretary of State").any()
    assert candidates.source_name.str.contains("FollowTheMoney.org").any()


def test_virginia_overlap_is_evaluated_within_each_committee() -> None:
    frame = pd.DataFrame({
        "committee_id": ["old-account", "new-account"],
        "period_start": pd.to_datetime(["2024-01-01", "2024-01-01"]),
        "period_end": pd.to_datetime(["2024-03-31", "2024-03-31"]),
    })
    assert MOD.intervals_overlap(frame)
    assert not any(
        MOD.intervals_overlap(committee_periods)
        for _, committee_periods in frame.groupby("committee_id", dropna=False)
    )


def test_virginia_same_committee_overlap_remains_for_review() -> None:
    frame = pd.DataFrame({
        "committee_id": ["one-account", "one-account"],
        "period_start": pd.to_datetime(["2024-01-01", "2024-03-15"]),
        "period_end": pd.to_datetime(["2024-03-31", "2024-06-30"]),
    })
    assert any(
        MOD.intervals_overlap(committee_periods)
        for _, committee_periods in frame.groupby("committee_id", dropna=False)
    )


def test_alabama_approved_completion_uses_official_calendar_year_summaries() -> None:
    rows = MOD.alabama_rows()
    assert len(rows) == 377
    assert not rows.duplicated(MOD.KEY).any()
    reviewed = rows[
        rows.aggregation_status.str.contains("approved_identity_adjudication:", na=False)
    ]
    assert len(reviewed) == 10
    assert reviewed.finance_observation_status.isin(
        {"observed_zero", "observed_positive"}
    ).all()
    pam = reviewed[
        reviewed.cycle.eq(2022) & reviewed.chamber.eq("house")
        & reviewed.district.eq(40) & reviewed.party.eq("D")
    ].iloc[0]
    assert pam.total_fundraising > 0
    assert "adjudicated_financial_summaries_v1" in pam.source_path
    bill_jones = reviewed[
        reviewed.cycle.eq(2018) & reviewed.chamber.eq("house")
        & reviewed.district.eq(27) & reviewed.party.eq("D")
    ].iloc[0]
    susan_smith = reviewed[
        reviewed.cycle.eq(2018) & reviewed.chamber.eq("house")
        & reviewed.district.eq(66) & reviewed.party.eq("D")
    ].iloc[0]
    assert bill_jones.committee_id == "fcpa_record:3059"
    assert susan_smith.committee_id == "fcpa_record:3159"
    assert bill_jones.total_fundraising > 0
    assert susan_smith.total_fundraising > 0
    alli = reviewed[
        reviewed.cycle.eq(2018) & reviewed.chamber.eq("house")
        & reviewed.district.eq(48) & reviewed.party.eq("D")
    ].iloc[0]
    assert alli.committee_id == "fcpa_record:2703"
    assert alli.total_fundraising == 76487.23


def test_virginia_one_day_boundary_amendment_supersedes_prior_period() -> None:
    frame = pd.DataFrame({
        "report_id": ["old", "new"],
        "period_start": pd.to_datetime(["2016-06-30", "2016-07-01"]),
        "period_end": pd.to_datetime(["2016-12-31", "2016-12-31"]),
        "amendment_num": [2, 4],
        "filed_sort": pd.to_datetime(["2017-01-10", "2017-02-10"]),
    })
    selected = MOD.drop_superseded_near_duplicate_periods(frame)
    assert selected.report_id.tolist() == ["new"]


def test_reciprocal_identity_matching_groups_aliases_and_rejects_wrong_family() -> None:
    targets = pd.DataFrame([
        {"candidate": "tarvin, thomas s (steve)"},
        {"candidate": "bolton, bill r (bill)"},
    ])
    identities = pd.DataFrame([
        {"provider_id": "legacy-1", "provider_name": "Thomas Steve Tarvin"},
        {"provider_id": "modern-1", "provider_name": "Thomas Stephen Steve Tarvin"},
        {"provider_id": "wrong-family", "provider_name": "LaDena Antionette Bolton"},
    ])
    assigned, _ = MOD.reciprocal_identity_assignments(
        targets, identities,
        identity_column="provider_id", name_column="provider_name",
    )
    assert assigned[0] == ["legacy-1", "modern-1"]
    assert assigned[1] == []


def test_committee_matching_strips_boilerplate_but_requires_given_name_when_present() -> None:
    targets = pd.DataFrame([
        {"candidate": "parrish, joe"},
        {"candidate": "martin, ray e"},
    ])
    identities = pd.DataFrame([
        {"committee_id": "parrish", "committee_name": "PARRISH FOR NC HOUSE"},
        {"committee_id": "wrong-martin", "committee_name": "CITIZENS FOR SUSAN MARTIN"},
    ])
    assigned, _ = MOD.reciprocal_identity_assignments(
        targets, identities,
        identity_column="committee_id", name_column="committee_name",
        committee_names=True,
    )
    assert assigned[0] == ["parrish"]
    assert assigned[1] == []


def test_align_to_universe_preserves_adapter_resolved_candidate_name(monkeypatch) -> None:
    universe = pd.DataFrame([{
        "state": "NC", "cycle": 2016, "chamber": "house", "district": 19,
        "party": "R", "candidate": "davis, robert t, jr 3",
    }])
    observed = universe.assign(
        candidate="TED DAVIS, JR.", total_fundraising=0.0,
        finance_observation_status="observed_zero",
        aggregation_status="fixture", source_name="fixture",
        source_measure="fixture",
    )
    monkeypatch.setattr(MOD, "candidate_universe", lambda: universe)
    aligned = MOD.align_to_universe(observed)
    assert aligned.loc[0, "candidate"] == "TED DAVIS, JR."


def test_south_carolina_amount_requires_one_explicit_value() -> None:
    assert MOD.amount([{"type": "Loans", "filingPeriod": 12.5}], "Loans") == 12.5
    assert pd.isna(MOD.amount([], "Loans"))
    assert pd.isna(MOD.amount([
        {"type": "Loans", "filingPeriod": 1},
        {"type": "Loans", "filingPeriod": 2},
    ], "Loans"))


def test_arkansas_output_is_unique_and_preserves_review_states() -> None:
    rows = MOD.arkansas_rows()
    assert not rows.empty
    assert not rows.duplicated(MOD.KEY).any()
    assert rows.finance_observation_status.isin({
        "observed_zero", "observed_positive",
        "review_conflicting_provider_registrations",
        "unknown_paper_filer_summary_not_authoritative",
        "unknown_missing_report_amount", "unknown_provider_identity_missing",
    }).all()


def test_florida_complete_transaction_types_are_authoritative_for_fundraising() -> None:
    rows = MOD.florida_rows()
    assert not rows.empty
    assert not rows.duplicated(MOD.KEY).any()
    usable = rows.finance_observation_status.isin({"observed_zero", "observed_positive"})
    assert usable.sum() >= 1100
    assert (
        rows.loc[usable, "total_fundraising"].round(2)
        == (
            rows.loc[usable, "cash_contributions"]
            + rows.loc[usable, "other_receipts"]
        ).round(2)
    ).all()
    assert rows.loc[usable, "in_kind_contributions"].gt(0).any()
    assert rows.loc[usable, "loans_received"].gt(0).any()
    negative = rows.finance_observation_status.eq("review_net_negative_cycle_receipts")
    assert rows.loc[negative, "total_fundraising"].isna().all()
    mismatch = rows[
        rows.cycle.eq(2020) & rows.chamber.eq("house")
        & rows.district.eq(59) & rows.party.eq("D")
    ].iloc[0]
    assert mismatch.finance_observation_status == "observed_positive"
    assert "summary_reconciliation=mismatch" in mismatch.aggregation_status


def test_florida_transaction_candidate_parser_handles_last_first_names() -> None:
    assert MOD.parse_fl_transaction_candidate(
        "Aristide, Wallace  (DEM)(STR)"
    ) == ("Aristide, Wallace", "DEM", "STR")
    assert MOD.parse_fl_transaction_candidate("malformed") is None


def test_kentucky_election_totals_are_unique_and_observed() -> None:
    rows = MOD.kentucky_rows()
    assert len(rows) >= 849
    assert not rows.duplicated(MOD.KEY).any()
    assert rows.finance_observation_status.isin({"observed_zero", "observed_positive"}).all()
    for cycle, chamber, district, party, candidate in (
        (2016, "house", 24, "R", "REED, WILLIAM B"),
        (2022, "house", 54, "D", "ELAINE WILSONREDDY"),
        (2024, "house", 95, "R", "BRANDON SPENCER"),
    ):
        recovered = rows[
            rows.cycle.eq(cycle) & rows.chamber.eq(chamber)
            & rows.district.eq(district) & rows.party.eq(party)
        ]
        assert len(recovered) == 1
        assert recovered.iloc[0].candidate == candidate


def test_virginia_xml_excludes_in_kind_and_loans_from_fundraising() -> None:
    candidates, periods = MOD.aggregate_virginia()
    assert not candidates.empty
    assert not candidates.duplicated(MOD.KEY).any()
    usable = candidates.finance_observation_status.isin({"observed_zero", "observed_positive"})
    assert usable.sum() >= 640
    assert (
        candidates.loc[usable, "total_fundraising"].round(2)
        == (
            candidates.loc[usable, "cash_contributions"]
            + candidates.loc[usable, "other_receipts"]
        ).round(2)
    ).all()
    assert periods.in_kind_contributions.notna().any()
    assert periods.loans_received.notna().any()


def test_missouri_captcha_gap_is_not_zero_filled() -> None:
    rows = MOD.missouri_rows()
    assert not rows.empty
    assert rows.total_fundraising.isna().all()
    assert rows.finance_observation_status.eq(
        "unknown_official_report_download_blocked_by_recaptcha"
    ).all()


def test_oklahoma_bulk_aggregation_excludes_loans_and_in_kind() -> None:
    rows = MOD.oklahoma_rows()
    assert len(rows) == 830
    assert not rows.duplicated(MOD.KEY).any()
    usable = rows.finance_observation_status.isin({"observed_zero", "observed_positive"})
    assert usable.sum() >= 735
    assert (
        rows.loc[usable, "total_fundraising"].round(2)
        == (
            rows.loc[usable, "cash_contributions"]
            + rows.loc[usable, "other_receipts"].fillna(0)
        ).round(2)
    ).all()
    assert rows.loc[usable, "loans_received"].notna().any()
    assert rows.loc[usable, "in_kind_contributions"].notna().any()
    for cycle, district, candidate in (
        (2016, 47, "O.A. CARGILL"),
        (2016, 85, "MATT JACKSON"),
        (2018, 85, "MATT JACKSON"),
    ):
        recovered = rows[
            rows.cycle.eq(cycle) & rows.chamber.eq("house")
            & rows.district.eq(district) & rows.candidate.eq(candidate)
        ]
        assert len(recovered) == 1
        assert recovered.iloc[0].finance_observation_status in {
            "observed_zero", "observed_positive"
        }


def test_louisiana_bulk_aggregation_uses_filer_identity_and_separates_categories() -> None:
    rows = MOD.louisiana_rows()
    assert len(rows) == 100
    assert not rows.duplicated(MOD.KEY).any()
    usable = rows.finance_observation_status.isin({"observed_zero", "observed_positive"})
    assert usable.sum() >= 90
    assert (
        rows.loc[usable, "total_fundraising"].round(2)
        == (
            rows.loc[usable, "cash_contributions"]
            + rows.loc[usable, "other_receipts"]
        ).round(2)
    ).all()
    assert rows.loc[usable, "loans_received"].notna().any()
    assert rows.loc[usable, "in_kind_contributions"].notna().any()
    frieman = rows[
        rows.cycle.eq(2019) & rows.chamber.eq("house")
        & rows.district.eq(74) & rows.party.eq("R")
    ].iloc[0]
    assert frieman.committee_id == "4430"
    assert frieman.finance_observation_status == "observed_positive"
    assert "FINID-LA-LAWRENCE-LARRY-FRIEMAN-HD74-2019" in frieman.aggregation_status
    josh_lewis = rows[
        rows.cycle.eq(2023) & rows.chamber.eq("senate")
        & rows.district.eq(25) & rows.party.eq("D")
    ].iloc[0]
    assert josh_lewis.committee_id == "5447"
    assert josh_lewis.in_kind_contributions == 900.0
    assert josh_lewis.total_fundraising == 0.0
    assert josh_lewis.finance_observation_status == "observed_zero"


def test_georgia_transactions_use_complete_2015_and_refreshed_2024_windows() -> None:
    rows = MOD.georgia_rows()
    assert len(rows) == 1528
    assert not rows.duplicated(MOD.KEY).any()
    assert rows.loc[
        rows.cycle.isin([2016, 2024]), "total_fundraising"
    ].notna().any()
    usable = rows.finance_observation_status.isin({"observed_zero", "observed_positive"})
    assert usable.sum() >= 1300
    assert (
        rows.loc[usable, "total_fundraising"].round(2)
        == (
            rows.loc[usable, "cash_contributions"]
            + rows.loc[usable, "other_receipts"]
        ).round(2)
    ).all()
    for candidate in ("KENDRICK, DARSHUN N", "WATSON, BEN L (BEN)", "CATHY KOTT"):
        recovered = rows[rows.candidate.eq(candidate)]
        assert not recovered.empty
        assert recovered.finance_observation_status.eq("observed_positive").any()


def test_north_carolina_candidate_committee_totals_are_conservative() -> None:
    rows = MOD.north_carolina_rows()
    assert len(rows) == 1475
    assert not rows.duplicated(MOD.KEY).any()
    assert rows.loc[rows.cycle.eq(2016), "total_fundraising"].notna().any()
    usable = rows.finance_observation_status.isin({"observed_zero", "observed_positive"})
    assert usable.sum() >= 1470
    assert rows.loc[usable, "total_fundraising"].notna().all()
    assert rows.loc[usable, "source_path"].str.contains(
        r"targeted_transactions_v\d+|transactions_v2"
    ).all()
    assert (
        rows.loc[usable, "total_fundraising"].round(2)
        == (
            rows.loc[usable, "cash_contributions"]
            + rows.loc[usable, "other_receipts"]
        ).round(2)
    ).all()
    ted_davis = rows[
        rows.cycle.eq(2016) & rows.chamber.eq("house")
        & rows.district.eq(19) & rows.party.eq("R")
    ].iloc[0]
    assert ted_davis.candidate == "TED DAVIS, JR."
    assert "DRACH" not in str(ted_davis.provider_candidate)
    chuck_edwards = rows[
        rows.cycle.eq(2020) & rows.chamber.eq("senate")
        & rows.district.eq(48) & rows.party.eq("R")
    ].iloc[0]
    assert chuck_edwards.candidate == "CHUCK EDWARDS"
    assert chuck_edwards.total_fundraising > 0
    for cycle, chamber, district, party in (
        (2016, "senate", 3, "D"),
        (2016, "house", 46, "D"),
        (2018, "senate", 29, "R"),
        (2022, "house", 66, "R"),
        (2022, "house", 117, "D"),
        (2024, "house", 96, "R"),
        (2024, "senate", 26, "D"),
    ):
        reviewed = rows[
            rows.cycle.eq(cycle) & rows.chamber.eq(chamber)
            & rows.district.eq(district) & rows.party.eq(party)
        ].iloc[0]
        assert reviewed.finance_observation_status == "observed_positive"
        assert "approved_identity_adjudication:" in reviewed.aggregation_status


def test_tennessee_omitted_receipt_section_is_explicit_zero() -> None:
    text = (
        "Beginning Balance Beginning Balance $0.00 Loans Received $0.00 "
        "ENDING BALANCE $0.00"
    )
    assert pd.isna(MOD.tn_summary_value(text, "TOTAL CONTRIBUTIONS"))


def test_tennessee_empty_adjustment_section_is_explicit_zero() -> None:
    text = (
        "TOTAL CONTRIBUTIONS (other than adjustments, loans, and interest) $100.00 "
        "Contribution Adjustments Loans Received $0.00 "
        "Interest Received This Reporting Period $2.00 TOTAL RECEIPTS $102.00"
    )
    assert MOD.tn_zero_when_section_is_empty(
        text, "Contribution Adjustments", "Loans Received"
    ) == 0.0
    nonempty = text.replace(
        "Contribution Adjustments Loans Received",
        "Contribution Adjustments unparsed adjustment row Loans Received",
    )
    assert pd.isna(MOD.tn_zero_when_section_is_empty(
        nonempty, "Contribution Adjustments", "Loans Received"
    ))


def test_tennessee_adjudicated_reports_use_workbook_fallback_without_zero_filling() -> None:
    rows, periods = MOD.tennessee_rows()
    harris = rows[
        rows.cycle.eq(2020) & rows.chamber.eq("house")
        & rows.district.eq(90) & rows.party.eq("D")
    ].iloc[0]
    huseth = rows[
        rows.cycle.eq(2024) & rows.chamber.eq("house")
        & rows.district.eq(97) & rows.party.eq("D")
    ].iloc[0]
    white = rows[
        rows.cycle.eq(2020) & rows.chamber.eq("house")
        & rows.district.eq(86) & rows.party.eq("R")
    ].iloc[0]
    assert round(harris.total_fundraising, 2) == 100364.18
    assert round(huseth.total_fundraising, 2) == 251801.82
    assert harris.finance_observation_status == "observed_positive"
    assert huseth.finance_observation_status == "observed_positive"
    assert periods.loc[
        periods.report_id.eq("126167"), "source_path"
    ].str.endswith("126167.xls").all()
    assert white.finance_observation_status == "unknown_no_report_summary"
    assert pd.isna(white.total_fundraising)


def test_texas_approved_identity_adjudications_are_exactly_scoped() -> None:
    crosswalk = pd.read_csv(
        MOD.TX_ROOT / "data/processed/features/tec_candidate_filer_crosswalk.csv",
        dtype=str,
    )
    crosswalk["cycle"] = pd.to_numeric(crosswalk.cycle, errors="coerce")
    resolved = MOD.apply_texas_identity_adjudications(
        crosswalk[crosswalk.cycle.between(2016, 2024)].copy()
    )
    bobby = resolved[
        resolved.cycle.eq(2024) & resolved.chamber.eq("house")
        & resolved.district.eq("41") & resolved.party.eq("D")
    ].iloc[0]
    assert bobby.filer_id == "00035579"
    assert bobby.filer_match_method.startswith("approved_identity_adjudication:")
    for district, filer_id in ((1, "00069367"), (49, "00082449"), (55, "00026513")):
        candidate = resolved[
            resolved.cycle.eq(2018) & resolved.chamber.eq("house")
            & resolved.district.eq(str(district)) & resolved.party.eq("R")
        ].iloc[0]
        assert candidate.filer_id == filer_id
        assert candidate.filer_match_method.startswith(
            "approved_identity_adjudication:"
        )
    for cycle, district, party, filer_id in (
        (2016, 109, "R", "00069509"),
        (2020, 142, "R", "00084443"),
        (2022, 31, "D", "00086413"),
    ):
        candidate = resolved[
            resolved.cycle.eq(cycle) & resolved.chamber.eq("house")
            & resolved.district.eq(str(district)) & resolved.party.eq(party)
        ].iloc[0]
        assert candidate.filer_id == filer_id
        assert candidate.filer_match_method.startswith(
            "approved_identity_adjudication:"
        )


def test_mississippi_ocr_parser_recognizes_handwritten_letter_o_zeroes() -> None:
    text = """TOTAL AMT OF CONTRIBUTIONS
$O
$O
$0
$0
TOTAL AMT OF DISBURSEMENTS
"""
    parsed = MOD._parse_ms_ocr_summary(text)
    assert parsed["aggregate_ytd"] == 0.0
