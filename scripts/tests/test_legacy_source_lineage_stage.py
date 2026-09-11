"""Synthetic source metadata reconciliation; no analytical calculations."""
import copy
import pytest

from stage_legacy_source_lineage import CORE, FIELDS, compare_county


def pair():
    old = dict(zip(CORE, (1998, "County", "COUNTY", "Place", "PLACE", "Office",
                         None, "Literal", "LITERAL", "", "O", 1.0, "alabama_sos", 1)))
    old.update({field: None for field in FIELDS}, stored_rowid=10, build_run_id="keep-original")
    fresh = old | dict(source_file="member.xls", source_sheet="Sheet", source_row=3,
                       source_column=2, printed_precinct=" Place ", printed_candidate=" Literal ")
    return old, fresh


def test_unique_pair_preserves_input_and_original_ingest():
    old, fresh = pair()
    before = copy.deepcopy(old)
    result = compare_county([old], [fresh], "SRC")
    assert old == before
    assert result["status"] == "reconciled"
    assert len(result["changes"]) == 1
    assert set(result["changes"][0]["after"]) == set(FIELDS)
    assert result["changes"][0]["after"]["source_file_id"] == "SRC"


def test_float_coordinates_are_staged_as_sqlite_integers():
    old, fresh = pair()
    fresh.update(source_row=3.0, source_column=2.0)
    after = compare_county([old], [fresh], "SRC")["changes"][0]["after"]
    assert type(after["source_row"]) is int
    assert type(after["source_column"]) is int


@pytest.mark.parametrize("field", CORE)
def test_any_substantive_difference_refuses_entire_county(field):
    old, fresh = pair()
    bad = fresh | {field: "different", "source_column": 3}
    result = compare_county([old, old | {"stored_rowid": 11}], [fresh, bad], "SRC")
    assert result["status"] == "substantive_mismatch"
    assert result["changes"] == []


def test_equal_source_values_keep_all_alternatives():
    old, fresh = pair()
    result = compare_county([old, old | {"stored_rowid": 11}],
                           [fresh, fresh | {"source_column": 3}], "SRC")
    assert result["changes"] == []
    assert result["ambiguous"][0]["stored_rowids"] == [10, 11]
    assert len(result["ambiguous"][0]["candidate_cells"]) == 2


def test_conflicting_nonnull_locator_refuses_county():
    old, fresh = pair()
    result = compare_county([old | {"source_row": 99}], [fresh], "SRC")
    assert result["status"] == "lineage_conflict"
    assert result["changes"] == []


@pytest.mark.parametrize("coordinate", [None, 0, -1, 1.5, True, "3"])
def test_invalid_physical_coordinate_fails(coordinate):
    old, fresh = pair()
    with pytest.raises(ValueError, match="physical source"):
        compare_county([old], [fresh | {"source_row": coordinate}], "SRC")


def test_already_filled_pair_needs_no_update():
    old, fresh = pair()
    old.update({field: fresh[field] for field in FIELDS[:4]}, source_file_id="SRC")
    assert compare_county([old], [fresh], "SRC")["changes"] == []


def test_explicit_label_equivalence_preserves_original_fields():
    old, fresh = pair()
    old["office"] = "Legacy office"
    assert compare_county([old], [fresh], "SRC")["status"] == "substantive_mismatch"
    result = compare_county([old], [fresh], "SRC", {"Legacy office": "Office"})
    change = result["changes"][0]
    assert "office" not in change["after"]
    assert change["source_key"][CORE.index("office")] == "Legacy office"
    assert change["office_match"] == {"stored": "Legacy office", "parsed": "Office"}
    assert old["office"] == "Legacy office"
    fresh["votes"] = 2
    assert compare_county([old], [fresh], "SRC", {"Legacy office": "Office"})["changes"] == []
