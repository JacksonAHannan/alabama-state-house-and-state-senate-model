from scripts.build_comprehensive_rollcall_classifications import (
    classify_text, extract_historical_synopsis, infer_historical_measure, motion_disposition,
)
import pandas as pd


def test_topic_does_not_force_direction():
    result = classify_text("Firearms", "Makes technical changes concerning firearms")
    assert result["issue_code"] == "guns"
    assert result["classification_status"] == "topic_only"


def test_clear_directional_rule():
    result = classify_text("Medicaid", "Expands Medicaid coverage to eligible adults")
    assert result["issue_code"] == "healthcare"
    assert result["yea_direction"] == -1


def test_habitual_offender_reform_uses_change_not_statute_name():
    result = classify_text("Habitual offenders", "Provides eligibility for parole consideration of nonviolent offenders")
    assert result["yea_direction"] == -1


def test_mixed_tax_levy_and_exemption_is_conflicted():
    result = classify_text("County tax", "Levies a sales tax but exempts farm machinery from the tax")
    assert result["classification_status"] == "direction_conflict"


def test_procedural_motion_does_not_inherit_bill_direction():
    assert motion_disposition("Smith motion to table") == "procedural_or_amendment"
    assert motion_disposition("Third reading and final passage") == "bill_direction_applies"


def test_historical_synopsis_is_anchored_to_target_bill():
    context = ("And the bill: HB18 To rename a county road. was read a third time and passed. "
               "And the bill: HB19 Relating to public schools; to increase teacher pay. "
               "was read a third time at length and passed.")
    assert extract_historical_synopsis(context, "HB", 19.0).startswith("Relating to public schools")


def test_historical_synopsis_rejects_missing_target():
    assert extract_historical_synopsis("And the bill: HB10 To do something.", "SB", 10) == ""


def test_formal_measure_marker_beats_prior_act_citation():
    context = "B.I.R., SB291, adopted. THE BILL: SB291 amending Act No. 99-519, SB 430, 1999 Regular Session"
    assert infer_historical_measure(context, "SB", 430)[:2] == ("SB", 291)


def test_generated_classification_covers_the_normalized_rollcall_universe():
    calls = pd.read_csv(
        "data/processed/legislative/comprehensive_rollcall_classifications.csv",
        low_memory=False,
    )
    assert len(calls) == 60704
    assert calls.canonical_rollcall_id.is_unique


def test_historical_nonfinal_motions_never_inherit_bill_direction():
    calls = pd.read_csv(
        "data/processed/legislative/comprehensive_rollcall_classifications.csv",
        low_memory=False,
    )
    historical = calls[calls.bill_id.isna()]
    nonfinal = historical[~historical.vote_description.isin(["final_passage", "conference_report"])]
    assert nonfinal.motion_disposition.ne("bill_direction_applies").all()
    assert nonfinal.yea_direction.isna().all()


def test_same_historical_measure_uses_one_bill_level_synopsis():
    calls = pd.read_csv(
        "data/processed/legislative/comprehensive_rollcall_classifications.csv",
        low_memory=False,
    )
    final = calls[
        calls.bill_id.isna()
        & calls.vote_description.isin(["final_passage", "conference_report"])
    ].copy()
    final["measure_key"] = final.session_year.astype(str) + "|" + final.bill_number.astype(str)
    assert not final.groupby("measure_key").description.nunique().gt(1).any()
