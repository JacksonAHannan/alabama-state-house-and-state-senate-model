"""Validate that each focal sponsorship PDF names the bill in its queue metadata.

LegiScan occasionally associates an official instrument URL with the wrong bill record.
This check reads the internal bill number printed on the first PDF page and prevents a
mislinked document from being used for policy-direction adjudication.
"""

from pathlib import Path
import re

import pandas as pd
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
OUT = ROOT / "data" / "processed" / "legislative" / "sponsorship_bill_text_link_validation.csv"
OVERRIDES = ROOT / "data" / "processed" / "legislative" / "sponsorship_bill_text_overrides.csv"


def normalize_bill(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def printed_bill_number(pdf_path: Path) -> tuple[str, str, str]:
    try:
        reader = PdfReader(str(pdf_path))
        first_page = (reader.pages[0].extract_text() or "") if reader.pages else ""
        text = "\n".join(
            (page.extract_text() or "") for page in reader.pages[:3]
        )
    except Exception as exc:  # retain failures for explicit review
        return "", f"pdf_error:{type(exc).__name__}", ""
    # Alabama instruments normally print HB123, SB45, HJR7, HR12, etc. at the
    # top of page zero. Limit the search to the first 500 characters so a bill
    # referenced later in a synopsis cannot masquerade as the document header.
    head = first_page[:500].upper()
    match = re.search(r"(?<![A-Z0-9])(HJR|SJR|HB|SB|HR|SR)\s*0*(\d+)(?!\d)", head)
    if not match:
        return "", "header_not_found", text
    return f"{match.group(1)}{int(match.group(2))}", "parsed", text


STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "by", "code", "for", "from",
    "in", "of", "on", "or", "relating", "section", "secs", "state", "the",
    "to", "under", "with", "act", "alabama", "amended", "provided",
}


def title_similarity(title: object, text: str) -> float:
    def terms(value: str) -> set[str]:
        return {
            word for word in re.findall(r"[a-z]{3,}", value.lower())
            if word not in STOPWORDS
        }
    expected = terms(str(title))
    observed = terms(text[:5000])
    return len(expected & observed) / len(expected) if expected else 0.0


def main() -> None:
    queue = pd.read_csv(RESEARCH / "candidate_sponsorship_direction_review_queue.csv")
    bills = queue[[
        "bill_id", "bill_number", "session_year", "title", "text_doc_id",
        "text_document_type", "bill_text_path",
    ]].drop_duplicates("bill_id").copy()
    if OVERRIDES.exists():
        overrides = pd.read_csv(OVERRIDES)[[
            "bill_id", "official_source_url", "override_bill_text_path"
        ]]
        bills = bills.merge(overrides, on="bill_id", how="left", validate="one_to_one")
        bills["original_bill_text_path"] = bills["bill_text_path"]
        bills["bill_text_path"] = bills.override_bill_text_path.fillna(
            bills.bill_text_path
        )
        bills["text_source_override_applied"] = bills.override_bill_text_path.notna()
    else:
        bills["official_source_url"] = ""
        bills["override_bill_text_path"] = ""
        bills["original_bill_text_path"] = bills["bill_text_path"]
        bills["text_source_override_applied"] = False
    rows = []
    for _, row in bills.iterrows():
        path = ROOT / Path(str(row["bill_text_path"]))
        printed_raw, parse_status, text = printed_bill_number(path)
        expected = normalize_bill(row["bill_number"])
        # Some Alabama PDFs concatenate page number 1 to the bill header while
        # others do not. Reconcile against the known expected number instead of
        # blindly stripping a final digit from instruments such as HB611.
        printed = (
            expected if printed_raw in {expected, f"{expected}1"}
            else printed_raw
        )
        similarity = title_similarity(row["title"], text)
        status = (
            "matched" if (
                parse_status == "parsed" and printed == expected and similarity >= 0.20
            )
            else "content_mismatch" if (
                parse_status == "parsed" and printed == expected
            )
            else "mismatch" if parse_status == "parsed"
            else "unverified"
        )
        rows.append({
            **row.to_dict(),
            "expected_bill_number": expected,
            "printed_bill_number": printed,
            "parse_status": parse_status,
            "title_term_coverage": round(similarity, 4),
            "bill_text_link_status": status,
            "position_review_allowed": status == "matched",
        })
    result = pd.DataFrame(rows).sort_values(["session_year", "bill_number", "bill_id"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(result.bill_text_link_status.value_counts(dropna=False).to_string())
    mismatches = result.loc[result.bill_text_link_status.ne("matched"), [
        "bill_id", "session_year", "bill_number", "printed_bill_number",
        "parse_status", "title_term_coverage", "bill_text_link_status", "bill_text_path",
    ]]
    if not mismatches.empty:
        print(mismatches.to_string(index=False))


if __name__ == "__main__":
    main()
