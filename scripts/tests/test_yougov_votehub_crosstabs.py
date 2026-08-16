from extract_yougov_votehub_crosstabs import extract_page


def test_yougov_pdf_text_parser_uses_first_demographic_table():
    headers = "\n".join(["Sex", "Race", "Age", "Education", "Total", "Male", "Female", "White",
                          "Black", "Hispanic", "18-29", "30-44", "45-64", "65+", "No degree",
                          "College grad"])
    pcts = "\n".join(f"{x}%" for x in range(12))
    reps = "\n".join(f"{x + 20}%" for x in range(12))
    bases = "\n".join(f"({100 + x})" for x in range(12))
    text = ("Generic Congressional Vote\n" + headers + "\nThe Democratic Party candidate\n" + pcts +
            "\nThe Republican Party candidate\n" + reps + "\nOther\nUnweighted N\n" + bases)
    out = extract_page(text, "x", "https://source#page=1", 1)
    white = out[out.group.eq("white")].iloc[0]
    assert white.dem_pct == 3
    assert white.rep_pct == 23
    assert white.cell_base == 103
