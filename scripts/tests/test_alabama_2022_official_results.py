"""Read-only official source evidence retains identities and missingness."""

import pandas as pd
import pytest

import alabama_2022_official_results as official


def rows():
    return [
        ["Contest Title", "Party", "Candidate", "P", "Q", "TOTAL VOTES"],
        ["State Representative, District 1", "DEM", "Jane Doe", 7, "", 7],
        ["State Representative, District 1", "LIB", "Sam Other", 2, 0, 2],
        ["State Representative, District 1", "NON", "Write-In", 1, 0, 1],
        ["State Representative, District 1", "", "Over Votes", 3, 0, 3],
        ["State Representative, District 1", "", "Under Votes", 4, 0, 4],
        ["State Senator, District 1", "REP", "John Roe", 9, 0, 9],
    ]


def parse(monkeypatch, source_rows=None):
    monkeypatch.setattr(official, "_workbook_sheets", lambda _: {"Precinct Results": source_rows or rows()})
    return official.parse_workbook(b"fixture", "2022-General-A.xls", "A")


def test_cells_keep_locators_blank_status_and_separate_categories(monkeypatch):
    cells = parse(monkeypatch)
    assert len(cells) == 18
    first = cells.iloc[0]
    assert (first.source_member, first.source_sheet, first.source_row, first.source_column) == ("2022-General-A.xls", "Precinct Results", 2, 4)
    assert first.printed_candidate == "Jane Doe" and first.printed_party == "DEM"
    assert cells.iloc[1].value_status == "unknown" and pd.isna(cells.iloc[1].votes)
    assert cells.cell_kind.eq("summary").sum() == 6
    assert cells.category.value_counts().to_dict() == {"named_candidate": 9, "write_in": 3, "overvote": 3, "undervote": 3}
    totals = official.candidate_totals(cells)
    assert totals.votes.tolist() == [7, 2, 9]
    jane = totals[totals.candidate_norm.eq("JANE DOE")].iloc[0]
    assert (jane.observed_cells, jane.unknown_cells, jane.aggregation_status) == (1, 1, "observed_cell_subtotal")


@pytest.mark.parametrize("value", ["?", "n/a", "nan", "inf", -1, 0.5, True])
def test_malformed_nonempty_votes_fail(monkeypatch, value):
    source = rows()
    source[1][3] = value
    with pytest.raises(ValueError, match="[Mm]alformed vote|Invalid vote"):
        parse(monkeypatch, source)


@pytest.mark.parametrize("change", ["duplicate", "blank", "metadata", "extra", "district", "candidate", "party"])
def test_ambiguous_or_missing_headers_and_identity_fail(monkeypatch, change):
    source = rows()
    if change == "duplicate": source[0][4] = source[0][3]
    if change == "blank": source[0][4] = ""
    if change == "metadata": source[0][1] = "Something else"
    if change == "extra": source[1].append(10)
    if change == "district": source[1][0] = "State Representative"
    if change == "candidate": source[1][2] = ""
    if change == "party": source[1][1] = "???"
    with pytest.raises(ValueError):
        parse(monkeypatch, source)


def test_all_null_candidate_is_not_zero(monkeypatch):
    source = rows()
    source[1][3:5] = ["", ""]
    with pytest.raises(ValueError, match="Missing candidate totals"):
        official.candidate_totals(parse(monkeypatch, source))


def test_printed_labels_are_preserved_without_trimming(monkeypatch):
    source = rows()
    source[1][0:3] = [" State Representative, District 1 ", " DEM ", " Jane Doe "]
    source[0][3] = " P "
    first = parse(monkeypatch, source).iloc[0]
    assert (first.printed_office, first.printed_party, first.printed_candidate, first.printed_precinct) == (" State Representative, District 1 ", " DEM ", " Jane Doe ", " P ")


def test_repeated_candidate_rows_fail(monkeypatch):
    source = rows()
    source.append(source[1].copy())
    with pytest.raises(ValueError, match="Ambiguous repeated"):
        parse(monkeypatch, source)


DESCRIPTIONS = """GSL001DDOE State Representative, District 1-:-Jane Doe-:-Dem
GSU01RROE State Senator, District 1-:-John Roe-:-Rep"""


def test_exact_name_join_keeps_opaque_codes(monkeypatch):
    cells = parse(monkeypatch)
    names = official.read_rdh_candidate_names(DESCRIPTIONS)
    matched = official.match_code_totals(cells, names)
    assert matched.candidate_code.tolist() == ["GSL001DDOE", "GSU01RROE"]
    assert matched.votes.tolist() == [7, 9]
    assert matched.unknown_cells.tolist() == [1, 0]
    assert matched.observed_cells.tolist() == [1, 2]
    assert matched.aggregation_status.eq("observed_cell_subtotal").all()


@pytest.mark.parametrize("description", [DESCRIPTIONS.replace("Jane Doe", "Jane Jones"), DESCRIPTIONS.splitlines()[0]])
def test_same_party_or_missing_name_cannot_join(monkeypatch, description):
    with pytest.raises(ValueError, match="Unmatched"):
        official.match_code_totals(parse(monkeypatch), official.read_rdh_candidate_names(description))


@pytest.mark.parametrize("description", [DESCRIPTIONS + "\n" + DESCRIPTIONS.splitlines()[0], DESCRIPTIONS.replace("District 1-:-Jane", "District 2-:-Jane"), DESCRIPTIONS.replace("-:-Dem", "-:-Rep")])
def test_duplicate_or_scope_conflicting_readme_fails(description):
    with pytest.raises(ValueError):
        official.read_rdh_candidate_names(description)


def test_ambiguous_official_name_fails(monkeypatch):
    source = rows()
    source.append(["State Representative, District 1", "DEM", "Someone Else", 3, 0, 3])
    with pytest.raises(ValueError, match="Ambiguous official"):
        official.match_code_totals(parse(monkeypatch, source), official.read_rdh_candidate_names(DESCRIPTIONS))


def test_archive_is_required_without_extracted_directory_fallback(tmp_path):
    (tmp_path / official.ARCHIVE.with_suffix("")).mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        official.load_official_cells(tmp_path)


def test_archive_count_and_duplicate_physical_members_fail(tmp_path):
    from zipfile import ZipFile
    archive = tmp_path / official.ARCHIVE
    archive.parent.mkdir(parents=True)
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("2022-General-A.xls", b"fixture")
    with pytest.raises(ValueError, match="67"):
        official.load_official_cells(tmp_path)
    with pytest.warns(UserWarning, match="Duplicate name"):
        with ZipFile(archive, "a") as zipped:
            zipped.writestr("2022-General-A.xls", b"fixture")
    with pytest.raises(ValueError, match="Duplicate archive"):
        official.load_official_cells(tmp_path)


def span(text, x, y, width=80):
    return {"text": text, "bbox": [x, y, x + width, y + 13]}


def canvass_spans(merged="named"):
    prefix = [span("November 08, 2022", 72, 54),
              span("Certified by the State Canvassing Board", 72, 552),
              span("Total", 74, 113),
              span("State Senator, District 32", 200, 72),
              span("State Senator, District 33", 500, 72)]
    if merged == "named":
        headers = [span("Chris Elliott (R)", 146, 94), span("Write-In", 263, 94),
                   span("Vivian Davis Figures (D) Pete Riehm (R)", 380, 94, 190),
                   span("Write-In", 614, 94)]
        values = [41073, 768, 23203, 11401, 51]
    else:
        prefix[-2:] = [span("State Representative, District 103", 184, 75),
                       span("State Representative, District 104", 476, 75)]
        headers = [span("Barbara Drummond (D) Write-In", 146, 97, 160),
                   span("Margie Wilcox (R)", 380, 97),
                   span("Jon Dearman (L)", 497, 97), span("Write-In", 614, 97)]
        values = [6015, 219, 8871, 1960, 85]
    return prefix + headers + [span(f"{value:,}", x, 113, 25)
                               for value, x in zip(values, [228, 359, 462, 579, 715])]


@pytest.mark.parametrize("merged, page", [("named", 68), ("write_in", 182)])
def test_merged_canvass_headers_preserve_individual_values_and_boxes(merged, page):
    source = canvass_spans(merged)
    parsed = official.parse_canvass_page(source, page)
    assert len(parsed) == 5 and all(row["canvass_page"] == page for row in parsed)
    assert len({tuple(row["canvass_value_bbox"]) for row in parsed}) == 5
    pair = parsed[2:4] if merged == "named" else parsed[:2]
    assert pair[0]["canvass_header_bbox"] == pair[1]["canvass_header_bbox"]
    assert [row["canvass_header_token"] for row in pair] == [0, 1]
    assert [row["category"] for row in parsed] == ["named_candidate", "write_in", "named_candidate", "named_candidate", "write_in"]
    if merged == "named":
        assert [row["certified_votes"] for row in parsed] == [41073, 768, 23203, 11401, 51]
        assert [row["district"] for row in parsed] == [32, 32, 33, 33, 33]
    else:
        assert parsed[3]["party"] == "L"
        assert [row["district"] for row in parsed] == [103, 103, 104, 104, 104]


@pytest.mark.parametrize("mutation", ["number", "missing_number", "extra_number", "duplicate_number", "duplicate_header", "bad_header", "date", "district", "missing_writein"])
def test_canvass_layout_and_numeric_ambiguity_fail(mutation):
    source = canvass_spans()
    if mutation == "number": source[-1]["text"] = "1,2"
    if mutation == "missing_number": source.pop()
    if mutation == "extra_number": source.append(span("2", 750, 113))
    if mutation == "duplicate_number": source[-1]["bbox"] = source[-2]["bbox"]
    if mutation == "duplicate_header": source[7]["text"] = "Pete Riehm (R) Pete Riehm (R)"
    if mutation == "bad_header": source[7]["text"] += " unmatched"
    if mutation == "date": source[0]["text"] = "November 08, 2020"
    if mutation == "district": source[3]["text"] = "State Senator, District 99"
    if mutation == "missing_writein": source[6]["text"] = "Unknown"
    with pytest.raises(ValueError):
        official.parse_canvass_page(source, 68)


def reconciled_fixture(monkeypatch):
    cells = parse(monkeypatch)
    certified = pd.DataFrame([
        {"chamber": "house", "district": 1, "party": "D", "candidate_norm": "JANE DOE", "category": "named_candidate", "certified_votes": 7},
        {"chamber": "house", "district": 1, "party": "L", "candidate_norm": "SAM OTHER", "category": "named_candidate", "certified_votes": 2},
        {"chamber": "house", "district": 1, "party": "O", "candidate_norm": "WRITE IN", "category": "write_in", "certified_votes": 1},
        {"chamber": "senate", "district": 1, "party": "R", "candidate_norm": "JOHN ROE", "category": "named_candidate", "certified_votes": 9},
    ])
    return cells, certified


def test_canvass_reconciliation_preserves_unknown_precinct_cells(monkeypatch):
    cells, certified = reconciled_fixture(monkeypatch)
    before = cells.copy(deep=True)
    result = official.reconcile_canvass(cells, certified)
    assert result.reconciliation_status.eq("matched_certified_total").all()
    jane = result[result.candidate_norm.eq("JANE DOE")].iloc[0]
    assert jane.unknown_cells == 1 and jane.aggregation_status == "observed_cell_subtotal"
    assert set(result.party) == {"D", "R", "L", "O"}
    pd.testing.assert_frame_equal(cells, before)


@pytest.mark.parametrize("mutation, reason", [
    ("mismatch", "vote_mismatch"), ("missing", "missing_certified_candidate"),
    ("extra", "missing_precinct_candidate"), ("duplicate", "ambiguous_certified_key"),
    ("all_null", "unknown_vote_total"), ("unknown_certified", "unknown_vote_total"),
])
def test_canvass_reconciliation_retains_review_evidence(monkeypatch, mutation, reason):
    cells, certified = reconciled_fixture(monkeypatch)
    if mutation == "mismatch": certified.loc[0, "certified_votes"] = 8
    if mutation == "missing": certified = certified.iloc[1:]
    if mutation == "extra":
        extra = certified.iloc[[0]].copy()
        extra["candidate_norm"] = "SOMEONE ELSE"
        certified = pd.concat([certified, extra], ignore_index=True)
    if mutation == "duplicate": certified = pd.concat([certified, certified.iloc[[0]]], ignore_index=True)
    if mutation == "all_null": cells.loc[cells.candidate_norm.eq("JANE DOE"), "votes"] = pd.NA
    if mutation == "unknown_certified": certified.loc[0, "certified_votes"] = float("nan")
    result = official.reconcile_canvass(cells, certified)
    review = result[result.reconciliation_reason.eq(reason)]
    assert not review.empty and review.reconciliation_status.eq("review").all()


def test_independent_party_is_not_collapsed_into_libertarian(monkeypatch):
    source = rows()
    source[2][1] = "IND"
    cells = parse(monkeypatch, source)
    _, certified = reconciled_fixture(monkeypatch)
    certified.loc[1, "party"] = "I"
    result = official.reconcile_canvass(cells, certified)
    assert result.reconciliation_status.eq("matched_certified_total").all()
    assert result[result.candidate_norm.eq("SAM OTHER")].party.tolist() == ["I"]


@pytest.mark.parametrize("missing", [False, True])
def test_canvass_loader_requires_exact_full_district_universe(monkeypatch, tmp_path, missing):
    import fitz
    import hashlib
    pages = []
    for chamber, count in [("Senator", 35), ("Representative", 105)]:
        for district in range(1, count + 1):
            if missing and chamber == "Senator" and district == 35:
                continue
            spans = [span("November 08, 2022", 72, 54),
                     span("Certified by the State Canvassing Board", 72, 552),
                     span("Total", 74, 113), span(f"State {chamber}, District {district}", 200, 72),
                     span("Jane Doe (I)", 146, 94), span("Write-In", 263, 94),
                     span("5", 228, 113), span("0", 359, 113)]
            class Page:
                def get_text(self, kind, values=spans):
                    return {"blocks": [{"lines": [{"spans": values}]}]}
            pages.append(Page())
    class Document(list):
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr(fitz, "open", lambda **kwargs: Document(pages))
    path = tmp_path / "fixture.pdf"
    path.write_bytes(b"fixture bytes, positioned spans supplied by test")
    if missing:
        with pytest.raises(ValueError, match="exact 140"):
            official.load_certified_canvass(path)
    else:
        frame, metadata = official.load_certified_canvass(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert len(frame) == 280 and frame.canvass_sha256.eq(digest).all()
        assert metadata["legislative_contests"] == 140 and metadata["sha256"] == digest
