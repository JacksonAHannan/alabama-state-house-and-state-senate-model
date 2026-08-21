from __future__ import annotations

import pandas as pd
import hashlib

from build_historical_precinct_adjudication_queue import case_id


def test_case_id_is_stable_and_county_normalized() -> None:
    assert case_id(1998, "ST CLAIR", "BOX 1") == case_id(1998, "STCLAIR", "BOX 1")
    assert case_id(1998, "ST CLAIR", "BOX 1").startswith("PCT-")


def test_top_200_contains_only_physical_candidates() -> None:
    data = pd.read_csv(
        "data/processed/precinct_history/historical_precinct_adjudication_top200.csv")
    assert len(data) == 200
    assert data.physical_adjudication_candidate.astype(bool).all()
    assert data.priority_rank.tolist() == list(range(1, 201))


def test_geocoding_is_reserved_for_overflow_inventories() -> None:
    audit = pd.read_csv(
        "data/processed/precinct_history/historical_precinct_geometry_audit.csv").fillna("")
    geocoded = audit[audit.name_match_method.eq("named_place_geocode_to_containing_vtd")]
    assert not geocoded.empty
    assert set(geocoded.vtd_inventory_relation) == {"overflow"}


def test_complete_equal_inventories_are_bijective() -> None:
    audit = pd.read_csv(
        "data/processed/precinct_history/historical_precinct_geometry_audit.csv").fillna("")
    equal = audit[audit.vtd_inventory_relation.eq("one_to_one")]
    for _, group in equal.groupby(["cycle", "county_key"]):
        physical = group[~group.name_match_method.eq("county_level_ballot")]
        if physical.donor_vtd_id.ne("").all():
            assert physical.donor_vtd_id.nunique() == len(physical)


def test_iterative_matches_do_not_modify_one_to_one_inventory() -> None:
    audit = pd.read_csv(
        "data/processed/precinct_history/historical_precinct_geometry_audit.csv").fillna("")
    iterative = audit[pd.to_numeric(audit.iterative_match_round, errors="coerce").fillna(0).gt(0)]
    assert not iterative.empty
    assert "one_to_one" not in set(iterative.vtd_inventory_relation)


def test_frozen_one_to_one_anchors_remain_unique() -> None:
    audit = pd.read_csv(
        "data/processed/precinct_history/historical_precinct_geometry_audit.csv").fillna("")
    frozen = audit[audit.frozen_one_to_one.astype(str).str.lower().eq("true")]
    assert not frozen.empty
    for _, group in frozen.groupby(["cycle", "county_key"]):
        assert group.donor_vtd_id.ne("").all()
        assert group.donor_vtd_id.nunique() == len(group)


def test_frozen_anchor_release_hash() -> None:
    frozen = pd.read_csv("data/manual/precinct_history/frozen_one_to_one_anchors.csv")
    frozen = frozen.sort_values(["cycle", "county_key", "precinct_key"])
    payload = "\n".join(frozen.cycle.astype(str) + "|" + frozen.county_key + "|"
                        + frozen.precinct_key + "|" + frozen.donor_vtd_id)
    assert len(frozen) == 832
    assert hashlib.sha256(payload.encode()).hexdigest() == (
        "ccec4ff703e69491563f0e8e1e2e99290f64c10b11d9612d11c319dfcb440a7b")


def test_physical_queue_excludes_administrative_records() -> None:
    queue = pd.read_csv(
        "data/processed/precinct_history/historical_precinct_adjudication_queue.csv")
    assert len(queue) == 1376
    assert not queue.precinct_key.str.contains(
        r"(?i)\b(?:calculated|reported|county reporting total|challenged|provisional)\b",
        regex=True).any()
