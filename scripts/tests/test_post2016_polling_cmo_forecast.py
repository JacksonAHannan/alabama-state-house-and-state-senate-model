from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from run_post2016_polling_cmo_forecast import prospective_panel
from build_2026_forecast_dashboard import build_payload


def test_prospective_forecast_uses_reconciled_finance():
    panel = prospective_panel()
    hd25 = panel[(panel.chamber.eq("house")) & panel.district.eq(25)].squeeze()
    assert hd25.dem_fundraising == 6257.20
    assert hd25.dem_finance_status == "single_official_state_record_with_activity"


def test_complete_races_have_two_observed_state_records():
    panel = prospective_panel()
    source = pd.read_csv(ROOT / "data/processed/finance/2026_candidate_finance_reconciled.csv")
    observed = source.finance_observation_status.isin(
        ["observed_positive", "observed_noncash_only", "observed_zero"]
    )
    usable = source[observed].pivot_table(
        index=["chamber", "district"], columns="party", values="candidate", aggfunc="nunique", fill_value=0
    )
    for row in panel[panel.finance_complete].itertuples(index=False):
        assert usable.loc[(row.chamber, row.district), "D"] == 1
        assert usable.loc[(row.chamber, row.district), "R"] == 1


def test_unverified_live_zeros_are_not_usable():
    panel = prospective_panel()
    source = pd.read_csv(ROOT / "data/processed/finance/2026_candidate_finance_reconciled.csv")
    unresolved = source[source.finance_observation_status.eq("unverified_live_summary_zero")]
    assert set(unresolved.candidate) == {
        "Kinsley Hammons", "Charlie Watts", "Thayer Bear Havard Spencer"
    }
    contested = panel.merge(
        unresolved[["chamber", "district"]].drop_duplicates(), on=["chamber", "district"], how="inner"
    )
    assert contested.finance_complete.eq(False).all()


def test_dashboard_payload_uses_same_reconciled_candidate_amount():
    data = build_payload()
    hd25 = next(race for race in data["house"]["races"] if race["district"] == 25)
    allison = next(candidate for candidate in hd25["candidates"] if candidate["name"] == "Allison T Montgomery")
    assert allison["raised"] == 6257.20
    assert allison["spent"] == 3969.71
    assert allison["financeStatus"] == "single_official_state_record_with_activity"


def test_sd7_uses_full_cycle_finance_and_correct_incumbency():
    panel = prospective_panel()
    sd7 = panel[(panel.chamber.eq("senate")) & panel.district.eq(7)].squeeze()

    assert sd7.dem_incumbent_i == 0
    assert sd7.rep_incumbent_i == 1
    assert sd7.dem_fundraising == 19146.16
    assert sd7.rep_fundraising == 370509.84

    forecast = pd.read_csv(
        ROOT / "data/processed/forecast_calibration/post2016_headline_v1_2026_scenarios.csv"
    )
    headline = forecast[
        forecast.scenario.eq("headline")
        & forecast.chamber.eq("senate")
        & forecast.district.eq(7)
    ].squeeze()
    assert headline.headline_dem_margin < 0
    assert headline.dem_win_probability < 0.5


def test_promoted_headline_has_one_valid_row_per_modeled_race():
    forecast = pd.read_csv(
        ROOT / "data/processed/forecast_calibration/post2016_headline_v1_2026_scenarios.csv"
    )
    headline = forecast[forecast.scenario.eq("headline")]

    assert len(headline) == 48
    assert not headline.duplicated(["chamber", "district"]).any()
    assert headline.dem_win_probability.between(0, 1, inclusive="both").all()
    assert headline.headline_dem_margin.notna().all()
