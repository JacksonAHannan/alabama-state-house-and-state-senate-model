import pandas as pd

from build_historical_frontier_rollcall_ontology import classify_synopsis


def test_historical_high_precision_policy_examples():
    prayer = classify_synopsis(
        "Relating to public schools; to provide a period of quiet reflection at the opening of each school day."
    )
    assert (prayer["primitive_axis"], prayer["policy_pole"]) == (
        "religion_state", "accommodation_establishment")
    punishment = classify_synopsis(
        "To provide enhanced criminal penalties and a mandatory minimum sentence for the offense."
    )
    assert (punishment["primitive_axis"], punishment["policy_pole"]) == (
        "criminal_punishment", "punitive")


def test_historical_noise_and_local_measures_fail_closed():
    assert classify_synopsis("was adopted.")["terminal_status"] == "excluded_historical_insufficient_text"
    local = classify_synopsis("Relating to Mobile County; to alter compensation of the sheriff.")
    assert local["terminal_status"] == "excluded_historical_local"


def test_historical_output_covers_every_unlinked_rollcall():
    calls = pd.read_csv("data/processed/legislative/comprehensive_rollcall_classifications.csv", low_memory=False)
    calls = calls[calls.bill_id.isna()]
    output = pd.read_csv("data/processed/legislative/historical_frontier_rollcall_ontology_v3.csv", low_memory=False)
    assert set(calls.canonical_rollcall_id.astype(str)) == set(output.canonical_rollcall_id.astype(str))
    mapped = output[output.decision.eq("map")]
    assert mapped.primitive_axis.notna().all()
    assert mapped.policy_pole.notna().all()
