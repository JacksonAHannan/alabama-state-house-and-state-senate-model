"""Validate LegiScan amendment-to-bill links against the official instrument header."""

from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "cmo_ideology"
DATA = ROOT / "data" / "processed" / "legislative"

TOKEN = re.compile(r"\b(HB|SB|HJR|SJR|H|S)\s*[- ]?\s*(\d{1,4})\b", re.I)


def normalize_bill(prefix: str, number: str) -> str:
    prefix = prefix.upper()
    prefix = {"H": "HB", "S": "SB"}.get(prefix, prefix)
    return f"{prefix}{int(number)}"


def header_bill_numbers(text: str) -> list[str]:
    # The instrument name and target bill occur at the beginning. Limiting the
    # scan prevents statutory citations later in a substitute from being
    # mistaken for its target bill.
    values = []
    for prefix, number in TOKEN.findall(text[:1200]):
        value = normalize_bill(prefix, number)
        if value not in values:
            values.append(value)
    return values


def main() -> None:
    manifest = pd.read_csv(DATA / "focal_amendment_text_manifest.csv")
    rows = []
    for row in manifest.drop_duplicates("amendment_id").itertuples(index=False):
        text = (ROOT / row.local_text).read_text(encoding="utf-8")
        references = header_bill_numbers(text)
        expected = str(row.bill_number).upper().replace(" ", "")
        if expected in references:
            status = "matched"
            referenced = expected
        elif references:
            status = "mismatch"
            referenced = references[0]
        else:
            status = "no_explicit_reference"
            referenced = ""
        rows.append({
            "amendment_id": int(row.amendment_id),
            "linked_bill_number": expected,
            "header_bill_number": referenced,
            "header_bill_candidates": "|".join(references),
            "bill_link_status": status,
            "position_inference_allowed": status == "matched",
            "validation_note": (
                "Official amendment header matches the linked bill."
                if status == "matched" else
                "Official amendment header names a different bill; exclude this LegiScan link."
                if status == "mismatch" else
                "No target bill was recoverable from the instrument header; manual verification required."
            ),
        })
    output = pd.DataFrame(rows).sort_values("amendment_id")
    output.to_csv(DATA / "focal_amendment_bill_link_validation.csv", index=False)
    print(output.bill_link_status.value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
