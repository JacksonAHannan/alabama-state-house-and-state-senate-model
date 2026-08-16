"""Index Alabama Acts volumes from Internet Archive OCR, 1986-1998.

The Acts establish what became law and usually identify the originating bill,
sponsor, title, and approval date.  They do not establish individual votes.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "alabama_legislature" / "acts" / "internet_archive"
OUT = ROOT / "data" / "processed" / "legislative"
YEARS = range(1986, 1999)

ACT = re.compile(r"(?im)^\s*Act\s+No\.?\s+((?:19)?\d{2})\s*[-–—]\s*(\d+)\b")
BILL = re.compile(r"\b(H\s*\.?\s*[BJ]\s*\.?\s*R?\.?|S\s*\.?\s*[BJ]\s*\.?\s*R?\.?|H\s*\.?|S\s*\.?)\s*[-–—]?\s*(\d+)\b", re.I)
APPROVED = re.compile(r"(?im)^\s*(Approved|Became law without Governor'?s signature)\s+([^\n]+)")


def clean_text(value: str) -> str:
    value = value.replace("Â¬\n", "").replace("¬\n", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \t\r\n.-")


def normalize_measure(raw: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", raw).upper()
    aliases = {"HB": "HB", "SB": "SB", "HJR": "HJR", "SJR": "SJR"}
    return aliases.get(letters, letters)


def title_from_block(block: str) -> str | None:
    # Titles occur after the bill/sponsor header and before the operative text.
    stop = re.search(r"(?im)^\s*(WHEREAS\b|BE IT\b|Section\s+1\b|SYNOPSIS\b)", block)
    head = block[: stop.start()] if stop else block[:1800]
    lines = [clean_text(line) for line in head.splitlines()]
    candidates: list[str] = []
    for line in lines:
        if not line or ACT.search(line) or BILL.search(line):
            continue
        if re.fullmatch(r"\d+", line) or line.lower().startswith(("alabama laws", "time:")):
            continue
        letters = [c for c in line if c.isalpha()]
        if len(letters) >= 8 and sum(c.isupper() for c in letters) / len(letters) >= .86:
            candidates.append(line)
    if not candidates:
        return None
    # The chamber heading sometimes precedes the descriptive title.
    candidates = [c for c in candidates if c not in {"AN ACT", "HOUSE JOINT RESOLUTION", "SENATE JOINT RESOLUTION"}]
    return clean_text(" ".join(candidates[:4])) or None


def parse_volume(text: str, source_file: str, volume_year: int) -> list[dict]:
    matches = list(ACT.finditer(text))
    rows: list[dict] = []
    for ordinal, match in enumerate(matches, 1):
        end = matches[ordinal].start() if ordinal < len(matches) else len(text)
        block = text[match.start():end]
        header = block[:1200]
        bill = BILL.search(header)
        if bill is None:
            # In many scanned volumes the measure/sponsor line is printed at
            # the foot of the preceding page, immediately before the act label.
            prefix = text[max(0, match.start() - 1000):match.start()]
            prior_bills = list(BILL.finditer(prefix))
            bill = prior_bills[-1] if prior_bills else None
        approved = APPROVED.search(block)
        act_year_raw = int(match.group(1))
        act_year = 1900 + act_year_raw if act_year_raw < 100 else act_year_raw
        measure_type = normalize_measure(bill.group(1)) if bill else None
        measure_number = int(bill.group(2)) if bill else None
        token = f"{act_year}|{match.group(2)}"
        rows.append({
            "act_id": "ALACT-" + hashlib.sha256(token.encode()).hexdigest()[:16].upper(),
            "act_year": act_year,
            "act_number": int(match.group(2)),
            "act_citation": f"{act_year % 100:02d}-{int(match.group(2))}",
            "measure_type": measure_type,
            "measure_number": measure_number,
            "origin_chamber": measure_type[0] if measure_type else None,
            "title": title_from_block(header),
            "approval_label": approved.group(1) if approved else None,
            "approval_date_raw": clean_text(approved.group(2)) if approved else None,
            "source_volume_year": volume_year,
            "source_file": source_file,
            "ordinal_in_volume": ordinal,
            "ocr_block_characters": len(block),
        })
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW.glob("**/*_djvu.txt"))
    rows: list[dict] = []
    docs: list[dict] = []
    for path in files:
        match = re.search(r"(?:19)?(8[6-9]|9\d)", path.parent.name)
        if not match:
            continue
        year = 1900 + int(match.group(1))
        if year not in YEARS:
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        parsed = [row for row in parse_volume(text, path.relative_to(ROOT).as_posix(), year)
                  if row["act_year"] in YEARS]
        # Index pages and running headers can repeat an act citation. Retain the
        # richest occurrence per act within a physical source volume.
        richness = lambda row: (row["measure_number"] is not None) + (row["title"] is not None) + (row["approval_date_raw"] is not None)
        richest: dict[tuple[int, int], dict] = {}
        for row in parsed:
            key = (row["act_year"], row["act_number"])
            if key not in richest or richness(row) > richness(richest[key]):
                richest[key] = row
        parsed = list(richest.values())
        rows.extend(parsed)
        docs.append({
            "source_file": path.relative_to(ROOT).as_posix(),
            "source_volume_year": year,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "text_characters": len(text),
            "acts_parsed": len(parsed),
        })

    acts = pd.DataFrame(rows)
    documents = pd.DataFrame(docs)
    if acts.empty:
        raise RuntimeError("No historical Acts were parsed")
    # Volumes can overlap. Preserve every source observation and identify an
    # unambiguous canonical row only when observations agree on bill identity.
    acts["act_key"] = acts.act_year.astype(str) + "-" + acts.act_number.astype(str)
    agreement = acts.groupby("act_key").agg(
        source_observations=("source_file", "size"),
        distinct_measure_types=("measure_type", lambda x: x.dropna().nunique()),
        distinct_measure_numbers=("measure_number", lambda x: x.dropna().nunique()),
    )
    acts = acts.merge(agreement, on="act_key", how="left")
    acts["identity_conflict"] = (acts.distinct_measure_types > 1) | (acts.distinct_measure_numbers > 1)
    acts["is_canonical_observation"] = (~acts.identity_conflict) & ~acts.duplicated("act_key", keep="first")

    acts.to_csv(OUT / "historical_alabama_act_observations.csv", index=False)
    canonical = acts[acts.is_canonical_observation].copy()
    canonical.to_csv(OUT / "historical_alabama_acts.csv", index=False)
    documents.to_csv(OUT / "historical_alabama_act_documents.csv", index=False)
    qa = (acts.groupby("act_year", as_index=False)
          .agg(source_observations=("act_id", "size"), unique_acts=("act_key", "nunique"),
               canonical_acts=("is_canonical_observation", "sum"),
               measure_linked=("measure_number", lambda x: x.notna().sum()),
               titled=("title", lambda x: x.notna().sum()),
               identity_conflicts=("identity_conflict", "sum")))
    qa.to_csv(OUT / "historical_alabama_acts_qa.csv", index=False)
    print(qa.to_string(index=False))


if __name__ == "__main__":
    main()
