"""Physical metadata survives legacy parsing without changing observations."""
import pytest

import scripts.sos_precinct as sos


@pytest.mark.parametrize("year", [1998, 2004])
def test_matrix_normalization_preserves_repeated_physical_cells(monkeypatch, year):
    if year == 1998:
        rows = [["", "unresolved office label", ""],
                ["", " Example ", " Example "],
                [" Same place ", 0, 1.5], ["Same place", 2, 3],
                ["TOTAL", 2, 4.5]]
        row_numbers, columns = [3, 3, 4, 4], [2, 3, 2, 3]
        precincts = [" Same place "] * 2 + ["Same place"] * 2
    else:
        rows = [["", "", "", " Same place ", "Same place"],
                ["unresolved office label", " Example ", "", 0, 1.5],
                ["unresolved office label", " Example ", "", 2, 3]]
        row_numbers, columns = [2, 2, 3, 3], [4, 5, 4, 5]
        precincts = [" Same place ", "Same place"] * 2
    monkeypatch.setattr(sos, "_workbook_sheets", lambda _: {"Sheet A": rows, "Sheet B": rows})
    data = sos.normalize_workbook(b"fixture", "Example", year)
    assert data.votes.tolist() == [0, 1.5, 2, 3] * 2
    assert data.office.tolist() == ["unresolved office label"] * 8
    assert data.source_sheet.tolist() == ["Sheet A"] * 4 + ["Sheet B"] * 4
    assert data.source_row.tolist() == row_numbers * 2
    assert data.source_column.tolist() == columns * 2
    assert data.printed_precinct.tolist() == precincts * 2
    assert data.printed_candidate.tolist() == [" Example "] * 8
    assert not data.duplicated(["source_sheet", "source_row", "source_column"]).any()


def test_1998_summary_label_preserves_printed_cell(monkeypatch):
    rows = [["", "unresolved office label"], ["", " Example "], [" TOTAL ", 0]]
    monkeypatch.setattr(sos, "_workbook_sheets", lambda _: {"Summary": rows})
    data = sos.normalize_workbook(b"fixture", "Example", 1998)
    assert data.precinct.tolist() == ["COUNTY REPORTING TOTAL"]
    assert data.printed_precinct.tolist() == [" TOTAL "]
    assert data.source_row.tolist() == [3]
    assert data.source_column.tolist() == [2]


@pytest.mark.parametrize("year", [2004, 2006])
def test_fallback_header_preserves_labels_and_offsets(monkeypatch, year):
    rows = [[""], ["", "", "unresolved office label", ""],
            ["", "PRECINCT", " Example - D ", " Example - D "],
            ["", " Same place ", 0, 1.5], ["", "TOTAL", 0, 1.5]]
    monkeypatch.setattr(sos, "_workbook_sheets", lambda _: {"Offset": rows})
    data = sos.normalize_workbook(b"fixture", "Example", year)
    assert data.candidate.tolist() == ["Example", "Example"]
    assert data.votes.tolist() == [0, 1.5]
    assert data.source_sheet.tolist() == ["Offset", "Offset"]
    assert data.source_row.tolist() == [4, 4]
    assert data.source_column.tolist() == [3, 4]
    assert data.printed_candidate.tolist() == [" Example - D "] * 2
    assert data.printed_precinct.tolist() == [" Same place "] * 2
