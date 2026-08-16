"""Download authoritative replacements for known mislinked sponsorship texts."""

from pathlib import Path
import hashlib
import urllib.request

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "alabama_legislature" / "bill_text_overrides" / "2010FS"
OUT = ROOT / "data" / "processed" / "legislative" / "sponsorship_bill_text_overrides.csv"

REPAIRS = [
    (416092, "HB5", "HB5-Int.pdf"),
    (416076, "HB7", "HB7-Int.pdf"),
    (416049, "HB12", "HB12-Int.pdf"),
]


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    rows = []
    for bill_id, bill_number, filename in REPAIRS:
        url = (
            "https://alison.legislature.state.al.us/files/pdf/"
            f"SearchableInstruments/2010FS/PrintFiles/{filename}"
        )
        path = RAW / f"{bill_id}_{filename.lower()}"
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read()
        if not content.startswith(b"%PDF"):
            raise ValueError(f"Non-PDF response for {url}")
        path.write_bytes(content)
        rows.append({
            "bill_id": bill_id,
            "bill_number": bill_number,
            "session_name": "First Special Session 2010",
            "override_reason": "LegiScan/ALISON source URL incorrectly used 2010RS instead of 2010FS",
            "official_source_url": url,
            "override_bill_text_path": str(path.relative_to(ROOT)),
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
