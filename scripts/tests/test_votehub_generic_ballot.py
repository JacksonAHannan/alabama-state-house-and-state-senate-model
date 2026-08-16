import pandas as pd

from download_votehub_generic_ballot import normalize, summarize


def test_normalize_uses_two_party_margin():
    polls = [{"id": "x", "pollster": "Test", "end_date": "2026-08-01",
              "answers": [{"choice": "Dem", "pct": 48}, {"choice": "GOP", "pct": 44}]}]
    row = normalize(polls).iloc[0]
    assert row.dem_margin_raw == 4
    assert round(row.dem_margin_two_party, 6) == round(100 * 4 / 92, 6)


def test_summary_excludes_internal_and_partisan_polls():
    polls = []
    for ident, margin, internal, partisan in [("a", 2, False, None), ("b", 20, True, None),
                                               ("c", 30, False, "D")]:
        polls.append({"id": ident, "pollster": ident, "end_date": "2026-08-01",
                      "internal": internal, "partisan": partisan, "population": "lv",
                      "answers": [{"choice": "Dem", "pct": 50 + margin / 2},
                                  {"choice": "Rep", "pct": 50 - margin / 2}]})
    result = summarize(normalize(polls), pd.Timestamp("2026-08-02").date()).iloc[0]
    assert result.generic_ballot_dem_margin_two_party == 2
