"""Fixture and integration tests for the forecast roster-universe audit."""
from __future__ import annotations

import pandas as pd
import pytest

import audit_forecast_roster_universe as audit


ROSTER_COLUMNS = ["cycle", "chamber", "district", "party", "candidate"]


def roster(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=ROSTER_COLUMNS)


def seat_lookup(seats: pd.DataFrame) -> dict[tuple[str, int], str]:
    return {
        (str(row.chamber), int(row.district)): str(row.seat_class) for row in seats.itertuples(index=False)
    }


def test_seat_classes_partition_every_enumerated_seat():
    frame = roster(
        [
            (2026, "house", 1, "D", "Ann D"),
            (2026, "house", 1, "R", "Bob R"),
            (2026, "house", 2, "D", "Cara D"),
            (2026, "house", 3, "R", "Dan R"),
            (2026, "house", 4, "I", "Eve I"),
            (2026, "house", 5, "D", "Fay D"),
            (2026, "house", 5, "D", "Fay D II"),
            (2026, "house", 5, "R", "Gus R"),
        ]
    )
    plan = {"house": [1, 2, 3, 4, 5, 6]}
    seats = audit.seat_frame(frame, plan)
    labels = seat_lookup(seats)
    assert labels == {
        ("house", 1): "modeled_d_r",
        ("house", 2): "single_major_party_d",
        ("house", 3): "single_major_party_r",
        ("house", 4): "independent_only",
        ("house", 5): "unresolved",
        ("house", 6): "no_candidate",
    }
    counts = audit.partition_counts(seats)
    assert counts["total_seats"] == 6
    assert counts["classes_partition_total"] is True
    assert counts["class_counts_sum"] == 6
    assert counts["partition_complete"] is False
    assert counts["counts"] == {
        "modeled_d_r": 1,
        "single_major_party_d": 1,
        "single_major_party_r": 1,
        "independent_only": 1,
        "no_candidate": 1,
        "unresolved": 1,
    }
    assert counts["by_chamber"]["house"]["no_candidate"] == 1


def test_independent_candidate_does_not_prevent_a_single_major_party_fix():
    frame = roster(
        [
            (2026, "senate", 1, "D", "Ann D"),
            (2026, "senate", 1, "I", "Ivy I"),
            (2026, "senate", 2, "R", "Bob R"),
            (2026, "senate", 2, "I", "Ivan I"),
            (2026, "senate", 3, "D", "Cara D"),
            (2026, "senate", 3, "R", "Dan R"),
            (2026, "senate", 3, "I", "Iris I"),
        ]
    )
    seats = audit.seat_frame(frame, {"senate": [1, 2, 3]})
    labels = seat_lookup(seats)
    assert labels[("senate", 1)] == "single_major_party_d"
    assert labels[("senate", 2)] == "single_major_party_r"
    assert labels[("senate", 3)] == "modeled_d_r"
    assert seats.has_independent_or_third_party.all()
    assert seats.set_index(["chamber", "district"]).loc[("senate", 1), "other_party_nominees"] == "I"


def test_multi_nominee_major_party_seat_is_unresolved_and_not_prospectively_eligible():
    frame = roster(
        [
            (2026, "house", 1, "D", "Ann D"),
            (2026, "house", 1, "D", "Ava D"),
            (2026, "house", 1, "R", "Bob R"),
            (2026, "house", 2, "D", "Cara D"),
            (2026, "house", 2, "R", "Dan R"),
        ]
    )
    seats = audit.seat_frame(frame, {"house": [1, 2]})
    labels = seat_lookup(seats)
    assert labels[("house", 1)] == "unresolved"
    assert labels[("house", 2)] == "modeled_d_r"
    assert audit.prospective_eligibility(frame) == {("house", 2)}
    unresolved = seats.set_index(["chamber", "district"]).loc[("house", 1)]
    assert int(unresolved.dem_nominees) == 2 and int(unresolved.rep_nominees) == 1


def test_repeated_identical_nominee_row_is_rejected():
    frame = roster(
        [
            (2026, "house", 1, "D", "Ann D"),
            (2026, "house", 1, "D", "Ann D"),
        ]
    )
    with pytest.raises(ValueError, match="identical nominee row"):
        audit.seat_frame(frame, {"house": [1]})


def test_policy_reconciliation_fixes_independent_bearing_seat_and_keeps_unmodeled_visible():
    frame = roster(
        [
            (2026, "house", 1, "D", "Ann D"),
            (2026, "house", 1, "R", "Bob R"),
            (2026, "house", 2, "D", "Cara D"),
            (2026, "house", 3, "R", "Dan R"),
            (2026, "house", 3, "I", "Ivy I"),
            (2026, "house", 4, "I", "Ida I"),
            (2026, "senate", 1, "R", "Earl R"),
        ]
    )
    seats = audit.seat_frame(frame, {"house": [1, 2, 3, 4], "senate": [1]})
    modeled_seats = pd.DataFrame(
        {
            "chamber": ["house", "house"],
            "dem_modeled_seats": [0, 1],
            "probability": [0.5, 0.5],
            "draws": [10, 10],
        }
    )
    payload = {
        "house": {
            "races": [
                {"district": 1, "status": "modeled", "demProbability": 0.55, "candidates": []},
                {"district": 2, "status": "unopposed-major-party", "demProbability": 1.0, "candidates": []},
                {"district": 3, "status": "unopposed-major-party", "demProbability": 0.0,
                 "candidates": [{"name": "Dan R", "party": "R"}, {"name": "Ivy I", "party": "I"}]},
                {"district": 4, "status": "unmodeled", "demProbability": None,
                 "candidates": [{"name": "Ida I", "party": "I"}]},
            ],
            "modelSeatDistributions": {
                "headline": [{"demSeats": 1, "probability": 0.5}, {"demSeats": 2, "probability": 0.5}],
                "environment_dem_favorable": [{"demSeats": 1, "probability": 0.6}, {"demSeats": 2, "probability": 0.4}],
                "environment_rep_favorable": [{"demSeats": 1, "probability": 0.7}, {"demSeats": 2, "probability": 0.3}],
            },
        },
        "senate": {
            "races": [{"district": 1, "status": "unopposed-major-party", "demProbability": 0.0, "candidates": []}],
            "modelSeatDistributions": {"headline": [{"demSeats": 0, "probability": 1.0}]},
        },
    }
    result = audit.policy_reconciliation(frame, seats, payload, modeled_seats)
    assert result["fixed_dem_from_roster"] == {"house": 1, "senate": 0}
    assert result["fixed_rep_from_roster"] == {"house": 1, "senate": 1}
    assert result["payload_fixed_offset_matches_roster"] is True
    assert result["payload_headline_distribution_matches_csv"] == {"house": True}
    assert result["payload_unmodeled_count"] == {"house": 1, "senate": 0}
    assert result["payload_status_matches_classes"] is True
    assert result["payload_status_mismatches"] == []
    assert [row["district"] for row in result["independent_candidate_seats"]] == [3, 4]
    assert result["independent_with_major_party_fixed"] is True
    assert result["independent_only_unmodeled"] is True
    bearing = next(row for row in result["independent_candidate_seats"] if row["district"] == 3)
    assert bearing["seat_class"] == "single_major_party_r"
    assert bearing["payload_status"] == "unopposed-major-party"
    assert bearing["payload_dem_probability"] == 0.0


def test_policy_reconciliation_detects_a_status_mismatch():
    frame = roster([(2026, "house", 1, "D", "Ann D")])
    seats = audit.seat_frame(frame, {"house": [1]})
    modeled_seats = pd.DataFrame({"chamber": [], "dem_modeled_seats": [], "probability": []})
    payload = {
        "house": {
            "races": [{"district": 1, "status": "modeled", "demProbability": 0.9, "candidates": []}],
            "modelSeatDistributions": {},
        },
        "senate": {"races": [], "modelSeatDistributions": {}},
    }
    result = audit.policy_reconciliation(frame, seats, payload, modeled_seats)
    assert result["payload_status_matches_classes"] is False
    assert result["payload_status_mismatches"] == [
        {
            "chamber": "house",
            "district": 1,
            "seat_class": "single_major_party_d",
            "expected_status": "unopposed-major-party",
            "payload_status": "modeled",
        }
    ]


def test_policy_evidence_distinguishes_contract_silence_from_stated_policy():
    dashboard = "fixed_dem=len(dem_districts-rep_districts)\n"
    js = "const unknown=DATA[c].races.filter(r=>r.demProbability==null).length\n"
    published_index = "Districts with one major-party nominee are fixed; genuinely unresolved districts remain unmodeled and gray.\n"
    published_methodology = "Single-major-party seats are fixed in chamber totals.\n"
    silent = audit.policy_evidence(
        dashboard, js, "", published_index, published_methodology, "No seat treatment is stated here."
    )
    assert silent["implementation"]["fixed_dem_from_roster"] is True
    assert silent["implementation"]["unresolved_visibility"] is True
    assert silent["published"]["index_caveat_present"] is True
    assert silent["published"]["methodology_fixed_totals_present"] is True
    assert silent["field_contract"]["terms_found"] == []
    assert silent["field_contract"]["states_seat_treatment"] is False
    assert silent["agreement"] == "page_and_implementation_agree_contract_silent"

    stated = audit.policy_evidence(
        dashboard,
        js,
        "",
        published_index,
        published_methodology,
        "A single-major-party seat is fixed in the chamber totals; independent candidates do not change it.",
    )
    assert stated["field_contract"]["states_seat_treatment"] is True
    assert stated["agreement"] == "page_and_implementation_agree_contract_states_policy"


def test_real_roster_partition_and_policy_agreement():
    summary = audit.build_summary()
    partition = summary["partition"]
    assert partition["total_seats"] == 140
    assert partition["partition_complete"] is True
    assert partition["class_counts_sum"] == 140
    assert partition["counts"] == {
        "modeled_d_r": 48,
        "single_major_party_d": 26,
        "single_major_party_r": 66,
        "independent_only": 0,
        "no_candidate": 0,
        "unresolved": 0,
    }
    assert partition["by_chamber"]["house"]["modeled_d_r"] == 33
    assert partition["by_chamber"]["senate"]["modeled_d_r"] == 15
    assert summary["model_check"]["modeled_matches_expected"] is True
    assert summary["model_check"]["classified_equals_eligible"] is True
    assert summary["model_check"]["scenario_races_identical"] is True
    assert summary["model_check"]["scenario_keys_equal_classified"] is True
    assert summary["ambiguous_seats"] == []
    assert summary["plan_membership"] == {
        "roster_seat_keys": 140,
        "plan_seat_keys": 140,
        "baseline_seat_keys": 140,
        "roster_equals_plan": True,
        "roster_equals_baseline": True,
    }
    assert summary["provenance_summary"]["rows_on_2026_plan"] == 189
    assert summary["provenance_summary"]["incumbency_join_resolved"] == 189
    assert summary["provenance_summary"]["roster_rows"] == 189
    assert summary["roster_deltas"]["summary"]["provisional_duplicate_keys"] == [
        {"chamber": "senate", "district": 10, "party": "R", "candidates": ["Andrew Jones", "Jesse Battles"]}
    ]
    assert summary["policy"]["agreement"] == "page_and_implementation_agree_contract_states_policy"
    assert summary["policy"]["field_contract"]["states_seat_treatment"] is True
    if not audit.ARTIFACT.exists():
        pytest.skip("Rendered forecast artifact is not present in this checkout")
    reconciliation = summary["policy"]["reconciliation"]
    assert reconciliation["fixed_dem_from_roster"] == {"house": 20, "senate": 6}
    assert reconciliation["payload_fixed_offset_matches_roster"] is True
    assert reconciliation["payload_headline_distribution_matches_csv"] == {"house": True, "senate": True}
    assert reconciliation["payload_status_matches_classes"] is True
    bearing = reconciliation["independent_candidate_seats"]
    assert [row["seat_class"] for row in bearing] == ["single_major_party_r"]
    assert reconciliation["independent_with_major_party_fixed"] is True
    assert reconciliation["independent_only_unmodeled"] is None
