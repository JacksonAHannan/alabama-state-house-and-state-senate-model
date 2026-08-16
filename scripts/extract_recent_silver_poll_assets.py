"""Extract reviewed generic-ballot cells from independently sourced A-range polls."""
from __future__ import annotations

from pathlib import Path

import fitz
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "polling" / "silver_recent"
OUT = ROOT / "data" / "processed" / "polling" / "silver_recent_generic_ballot_cells.csv"


def record(poll_id, pollster, grade, start, end, population, sample, dimension,
           group, dem, rep, source_file, table, method):
    return {
        "poll_id": poll_id, "pollster": pollster, "silver_grade": grade,
        "b_plus_or_better": True, "start_date": start, "end_date": end,
        "population": population, "sample_size": sample, "dimension": dimension,
        "group": group, "dem_pct": float(dem), "rep_pct": float(rep),
        "source_file": str((RAW / source_file).relative_to(ROOT)),
        "page_or_table": table, "extraction_method": method, "reviewed": True,
    }


def extract_echelon():
    filename = "echelon_2026_07_crosstabs.xlsx"
    frame = pd.read_excel(RAW / filename, "Crosstabs", header=None)
    question = str(frame.iloc[288, 0])
    if "QGenericCongressional" not in question:
        raise ValueError("Echelon generic-ballot table moved")
    labels = [str(x).replace("\n", " ").strip() for x in frame.iloc[7].tolist()]
    rep = frame.iloc[290]
    dem = frame.iloc[291]
    expected = {
        "all": ("overall", "Total"), "white": ("race", "White"),
        "black": ("race", "Black"), "hispanic": ("race", "Hispanic"),
        "echelon_hs_or_less": ("education", "HS or less"),
        "echelon_some_college": ("education", "Some college"),
        "echelon_bachelors": ("education", "Bachelor's"),
        "echelon_graduate": ("education", "Graduate"),
        "echelon_noncollege": ("education", "Non- College"),
        "echelon_college": ("education", "College"),
    }
    rows = []
    for group, (dimension, label) in expected.items():
        matches = [i for i, value in enumerate(labels) if " ".join(value.split()) == label]
        if len(matches) != 1:
            raise ValueError(f"Echelon expected one {label!r} column, found {matches}")
        col = matches[0]
        rows.append(record("supp_echelon_202607", "Echelon Insights", "A-",
                           "2026-07-09", "2026-07-13", "lv", 1004,
                           dimension, group, 100 * dem.iloc[col], 100 * rep.iloc[col],
                           filename, "QGenericCongressional", "echelon_xlsx_adapter_v1"))
    return rows


def extract_fox():
    filename = "fox_beacon_shaw_2026_07_crosstabs.pdf"
    document = fitz.open(RAW / filename)
    text = "\n".join(page.get_text() for page in document)
    if "If the election for Congress were held today" not in text:
        raise ValueError("Fox generic-ballot question not found")
    # Reviewed transcription of Q21, page 9. Values are guarded against the
    # PDF's extracted text so a replaced source file cannot pass silently.
    if "Democratic candidate\n53%\n50%\n55%\n49%\n66%\n56%" not in text:
        raise ValueError("Fox Q21 race banner does not match reviewed schema")
    cells = [
        ("overall", "all", 53, 46), ("race", "white", 49, 50),
        ("race", "nonwhite", 66, 34), ("race", "hispanic", 56, 44),
        ("education", "fox_college_degree", 58, 40),
        ("education", "fox_no_college_degree", 50, 50),
        ("race_education", "white_college", 57, 41),
        ("race_education", "white_noncollege", 43, 56),
    ]
    return [record("supp_fox_202607", "Beacon Research/Shaw & Co. Research", "A-",
                   "2026-07-17", "2026-07-20", "rv", 1003, dim, group, dem, rep,
                   filename, "PDF page 9, Q21", "fox_pdf_reviewed_adapter_v1")
            for dim, group, dem, rep in cells]


def extract_cygnal():
    definitions = [
        ("cygnal_2026_07_deck.pdf", "supp_cygnal_202607", "2026-06-30",
         "2026-07-01", 50, 44, "Democrats gained a point over the last month, now leading the generic ballot 50% to 44%"),
        ("cygnal_2026_08_deck.pdf", "supp_cygnal_202608", "2026-08-06",
         "2026-08-07", 49, 42, "they lead 49% to 42%, a D+7 margin"),
    ]
    rows = []
    for filename, poll_id, start, end, dem, rep, guard in definitions:
        document = fitz.open(RAW / filename)
        cover = " ".join(document[0].get_text().split())
        summary = " ".join(document[1].get_text().split())
        if start.replace("2026-", "").replace("-", "") and "n=1500" not in cover:
            raise ValueError(f"{filename}: unexpected cover")
        if guard not in summary:
            raise ValueError(f"{filename}: generic-ballot summary changed")
        rows.append(record(poll_id, "Cygnal", "A", start, end, "lv", 1500,
                           "overall", "all", dem, rep, filename,
                           "PDF page 2 summary", "cygnal_deck_topline_adapter_v1"))
    return rows


def extract_quinnipiac():
    filename = "quinnipiac_2026_06_release.pdf"
    document = fitz.open(RAW / filename)
    text = "\n".join(page.get_text() for page in document)
    guards = ["1,165 self-identified registered voters", "Republican Party     42%",
              "Democratic Party     49"]
    if not all(guard in text for guard in guards):
        raise ValueError("Quinnipiac House-control table changed")
    return [record("supp_quinnipiac_202606", "Quinnipiac University", "B+",
                   "2026-06-18", "2026-06-22", "rv", 1165, "overall", "all",
                   49, 42, filename, "PDF page 5, Q4",
                   "quinnipiac_pdf_topline_adapter_v1")]


def extract_cnbc_hart_pos():
    filename = "cnbc_hart_pos_2026_q2_topline.pdf"
    document = fitz.open(RAW / filename)
    text = " ".join(page.get_text() for page in document)
    normalized = " ".join(text.split())
    guards = ["Interviews: 1,000 voters nationwide", "Dates: July 8-12, 2026",
              "Study #260302", "Republican-controlled ... 45",
              "Democrat-controlled ...... 49"]
    if not all(guard in normalized for guard in guards):
        raise ValueError("CNBC Q2 congressional-control table changed")
    return [record("supp_cnbc_hart_pos_202607",
                   "Hart Research Associates/Public Opinion Strategies", "A-",
                   "2026-07-08", "2026-07-12", "rv", 1000, "overall", "all",
                   49, 45, filename, "PDF page 5, Q4",
                   "cnbc_hart_pos_pdf_topline_adapter_v1")]


def main():
    rows = (extract_echelon() + extract_fox() + extract_cygnal() +
            extract_quinnipiac() + extract_cnbc_hart_pos())
    result = pd.DataFrame(rows)
    result["dem_two_party_share"] = result.dem_pct / (result.dem_pct + result.rep_pct)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(f"Extracted {len(result)} reviewed cells from {result.poll_id.nunique()} polls")


if __name__ == "__main__":
    main()
