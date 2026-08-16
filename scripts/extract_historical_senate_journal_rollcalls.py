"""Extract and audit Alabama Senate journal roll calls for 1998-2009."""
from __future__ import annotations

from pathlib import Path
import hashlib
import re

import fitz
import pandas as pd

from oe_normalize import normalize_name


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "alabama_legislature" / "senate_journals"
OUT = ROOT / "data" / "processed" / "legislative"
YEARS = range(1998, 2010)

ANCHOR = re.compile(
    r"\bYeas?\s+(\d+)\s+Nays?\s+(\d+)(?:\s+(?:Abstaining|Abstains?)\s+(\d+))?\b",
    re.I,
)
BILL = re.compile(r"\b(HB|SB|HJR|SJR|HR|SR)\s*[- ]?\s*(\d+)\b", re.I)
FINAL_PASSAGE = re.compile(
    r"(?:was\s+)?read\s+(?:a|the)\s+third\s+time(?:\s+at\s+length)?\s+and\s+"
    r"(?P<outcome>passed|failed(?:\s+to\s+pass)?)\b",
    re.I,
)


def clean_member_block(block: str) -> str:
    block = re.sub(
        r"\n\s*<<<PAGE\s+\d+>>>\s*\n.*?\b\d+(?:st|nd|rd|th)\s+Day[^\n]*\n(?:\s*(?:19|20)\d{2}\s*)?",
        " ", block, flags=re.I | re.S,
    )
    block = re.sub(
        r"\n\s*<<<PAGE\s+\d+>>>\s*\n\s*"
        r"(?:REGULAR|SPECIAL|ORGANIZATIONAL|EXTRAORDINARY) SESSION\s*\n\s*"
        r"\d+\s*\n\s*[^\n]*Day[^\n]*\n",
        " ", block, flags=re.I,
    )
    block = re.sub(
        r"\n\s*\d+\s*\n\s*JOURNAL OF THE SENATE[^\n]*\n\s*[^\n]*Day[^\n]*\n",
        " ", block, flags=re.I,
    )
    block = re.sub(r"\n\s*<<<PAGE\s+\d+>>>\s*\n", " ", block, flags=re.I)
    block = re.sub(r"\n\s*(?:REGULAR|SPECIAL|ORGANIZATIONAL|EXTRAORDINARY) SESSION\s*\n", " ", block, flags=re.I)
    # Repair typographic line-break hyphenation, but retain surname hyphens.
    block = re.sub(r"([A-Za-z])[-¬]\s*\n\s*([a-z])", r"\1\2", block)
    return block


def member_names(block: str) -> list[str]:
    text = clean_member_block(block)
    text = re.sub(r"\bSenators?:\s*", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" .,-")
    if not text:
        return []
    text = re.sub(r"\s+and\s+", ", ", text)
    return [name.strip(" .") for name in text.split(",") if name.strip(" .")]


def vote_block(after: str, labels: str, count: int) -> str | None:
    if count == 0:
        # A printed empty list is optional; the tally itself is authoritative.
        return ""
    match = re.search(
        rf"(?:^|\n)\s*(?:{labels}):\s*(.*?)(?:\s*-\s*{count}\s*(?:\n|$))",
        after, re.I | re.S,
    )
    return match.group(1) if match else None


def classify_motion(context: str) -> str:
    upper = context.upper()
    if "BUDGET ISOLATION RESOLUTION" in upper or re.search(r"\bB\.I\.R\.", upper):
        return "budget_isolation_resolution"
    if "CONFERENCE" in upper:
        return "conference_report"
    if "CONFIRMED BY THE SENATE" in upper or "APPOINTMENT" in upper:
        return "confirmation"
    if "AMENDMENT" in upper or "CONCURRED" in upper:
        return "amendment_or_concurrence"
    if "SUBSTITUTE" in upper:
        return "substitute"
    if "LAID ON THE TABLE" in upper or "TABLED" in upper:
        return "motion_to_table"
    if "ADJOURN" in upper:
        return "adjournment"
    return "other_recorded_motion"


def last_bill(context: str) -> tuple[str | None, int | None]:
    refs = BILL.findall(context)
    return (refs[-1][0].upper(), int(refs[-1][1])) if refs else (None, None)


def parse_document(text: str, session: str, asset: str, local_path: str) -> tuple[list[dict], list[dict], list[dict]]:
    rollcalls: list[dict] = []
    votes: list[dict] = []
    passage_events: list[dict] = []
    page_starts = [(m.start(), int(m.group(1))) for m in re.finditer(r"\n<<<PAGE (\d+)>>>\n", text)]
    anchors = list(ANCHOR.finditer(text))

    for ordinal, anchor in enumerate(anchors, 1):
        yea, nay, abstain = int(anchor.group(1)), int(anchor.group(2)), int(anchor.group(3) or 0)
        after = text[anchor.end():anchor.end() + 6500]
        blocks = {
            "Yea": vote_block(after, "Yeas?", yea),
            "Nay": vote_block(after, "Nays?", nay),
            "Abstain": vote_block(after, "Abstaining|Abstains?", abstain),
        }
        names = {key: member_names(value) if value is not None else [] for key, value in blocks.items()}
        context = re.sub(r"\s+", " ", text[max(0, anchor.start() - 3000):anchor.start()]).strip()
        bill_type, bill_number = last_bill(context)
        page = max((page for start, page in page_starts if start <= anchor.start()), default=None)
        token = f"{session}|{asset}|{ordinal}|{anchor.start()}"
        rollcall_id = "SJRC-" + hashlib.sha256(token.encode()).hexdigest()[:16].upper()
        parsed = {key: len(names[key]) for key in names}
        valid = parsed == {"Yea": yea, "Nay": nay, "Abstain": abstain}
        rollcalls.append({
            "rollcall_id": rollcall_id, "session": session, "session_year": int(session[:4]),
            "chamber": "senate", "asset": asset, "local_path": local_path, "page": page,
            "ordinal_in_document": ordinal, "source_char_offset": anchor.start(), "bill_type": bill_type,
            "bill_number": bill_number, "motion_type": classify_motion(context[-1800:]),
            "yea_total": yea, "nay_total": nay, "abstain_total": abstain,
            "parsed_yea": parsed["Yea"], "parsed_nay": parsed["Nay"], "parsed_abstain": parsed["Abstain"],
            "count_valid": valid, "context": context[-1800:],
        })
        for vote, named in names.items():
            for name in named:
                votes.append({
                    "rollcall_id": rollcall_id, "session_year": int(session[:4]), "chamber": "senate",
                    "member_name": name, "member_name_norm": normalize_name(name), "vote": vote,
                    "count_valid": valid,
                })

    for ordinal, event in enumerate(FINAL_PASSAGE.finditer(text), 1):
        context = re.sub(r"\s+", " ", text[max(0, event.start() - 2200):event.start()]).strip()
        bill_type, bill_number = last_bill(context)
        following = [(i + 1, a) for i, a in enumerate(anchors) if a.start() >= event.end()]
        nearest_ordinal, nearest = following[0] if following else (None, None)
        distance = nearest.start() - event.end() if nearest else None
        nearby = nearest is not None and distance <= 3000
        paired_rollcall = rollcalls[nearest_ordinal - 1] if nearby and nearest_ordinal is not None else None
        rollcall_has_names = bool(paired_rollcall and (
            paired_rollcall["parsed_yea"] + paired_rollcall["parsed_nay"] + paired_rollcall["parsed_abstain"] > 0
        ))
        same_measure = bool(
            paired_rollcall and bill_type and bill_number
            and paired_rollcall["bill_type"] == bill_type and paired_rollcall["bill_number"] == bill_number
        )
        matched = nearby and rollcall_has_names
        page = max((page for start, page in page_starts if start <= event.start()), default=None)
        token = f"{session}|{asset}|passage|{ordinal}|{event.start()}"
        passage_events.append({
            "passage_event_id": "SPASS-" + hashlib.sha256(token.encode()).hexdigest()[:16].upper(),
            "session": session, "session_year": int(session[:4]), "asset": asset, "local_path": local_path,
            "page": page, "source_char_offset": event.start(), "bill_type": bill_type, "bill_number": bill_number,
            "outcome_text": event.group("outcome"), "nearest_rollcall_ordinal": nearest_ordinal,
            "rollcall_distance_characters": distance, "named_rollcall_detected": matched,
            "matched_rollcall_id": paired_rollcall["rollcall_id"] if paired_rollcall else None,
            "matched_rollcall_count_valid": paired_rollcall["count_valid"] if paired_rollcall else None,
            "matched_rollcall_same_measure": same_measure,
            "audit_status": (
                "matched_same_measure_count_valid" if matched and same_measure and paired_rollcall["count_valid"]
                else "matched_same_measure_count_mismatch" if matched and same_measure
                else "review_measure_mismatch" if matched
                else "review_no_named_rollcall"
            ),
            "context": re.sub(r"\s+", " ", text[event.start():event.end() + 300])[:700],
        })
    # The event-to-roll-call link is more reliable than a broad context label:
    # Alabama commonly printed a BIR vote immediately before final passage.
    passage_rollcalls = {event["matched_rollcall_id"] for event in passage_events if event["named_rollcall_detected"]}
    for rollcall in rollcalls:
        if rollcall["rollcall_id"] in passage_rollcalls:
            rollcall["motion_type"] = "final_passage"
    return rollcalls, votes, passage_events


def extract_text(path: Path) -> tuple[str, int, int]:
    document = fitz.open(path)
    parts: list[str] = []
    characters = 0
    for page_number, page in enumerate(document, 1):
        content = page.get_text("text")
        characters += len(content)
        parts.append(f"\n<<<PAGE {page_number}>>>\n{content}")
    return "".join(parts), len(document), characters


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(RAW / "manifest.csv")
    manifest["session_year"] = pd.to_numeric(manifest.session.str[:4], errors="coerce")
    selected = manifest[
        manifest.session_year.isin(YEARS)
        & manifest.asset.str.contains("Day", case=False, na=False)
        & ~manifest.asset.str.contains("Index", case=False, na=False)
        & manifest.status.isin(["downloaded", "existing"])
    ]
    documents: list[dict] = []
    rollcalls: list[dict] = []
    votes: list[dict] = []
    passages: list[dict] = []
    for index, row in enumerate(selected.itertuples(index=False), 1):
        path = ROOT / row.local_path
        text, pages, characters = extract_text(path)
        rc, mv, pe = parse_document(text, row.session, row.asset, row.local_path)
        rollcalls.extend(rc); votes.extend(mv); passages.extend(pe)
        documents.append({
            "session": row.session, "session_year": int(row.session_year), "asset": row.asset,
            "local_path": row.local_path, "sha256": row.sha256, "pages": pages,
            "text_characters": characters, "rollcall_anchors": len(rc), "final_passage_events": len(pe),
        })
        if index % 50 == 0:
            print(f"Processed {index}/{len(selected)} journals; {len(rollcalls):,} roll calls", flush=True)

    documents_df = pd.DataFrame(documents)
    rollcalls_df = pd.DataFrame(rollcalls)
    votes_df = pd.DataFrame(votes)
    passages_df = pd.DataFrame(passages)
    documents_df.to_csv(OUT / "historical_senate_journal_documents.csv", index=False)
    rollcalls_df.to_csv(OUT / "historical_senate_journal_rollcalls.csv", index=False)
    votes_df.to_csv(OUT / "historical_senate_journal_member_votes.csv", index=False)
    passages_df.to_csv(OUT / "historical_senate_section63_audit.csv", index=False)

    years = pd.DataFrame({"session_year": list(YEARS)})
    qa = rollcalls_df.groupby("session_year", as_index=False).agg(
        rollcalls=("rollcall_id", "size"), valid_rollcalls=("count_valid", "sum"),
        bill_linked=("bill_number", lambda x: x.notna().sum()),
    ) if not rollcalls_df.empty else years.iloc[0:0]
    qa = years.merge(qa, on="session_year", how="left").fillna(0)
    doc_counts = documents_df.groupby("session_year").size() if not documents_df.empty else pd.Series(dtype=int)
    vote_counts = votes_df.groupby("session_year").size() if not votes_df.empty else pd.Series(dtype=int)
    valid_votes = votes_df[votes_df.count_valid].groupby("session_year").size() if not votes_df.empty else pd.Series(dtype=int)
    passage_counts = passages_df.groupby("session_year").size() if not passages_df.empty else pd.Series(dtype=int)
    matched_passages = passages_df[passages_df.named_rollcall_detected].groupby("session_year").size() if not passages_df.empty else pd.Series(dtype=int)
    verified_passages = passages_df[passages_df.audit_status.eq("matched_same_measure_count_valid")].groupby("session_year").size() if not passages_df.empty else pd.Series(dtype=int)
    qa["journal_pdfs"] = qa.session_year.map(doc_counts).fillna(0).astype(int)
    qa["source_gap"] = qa.journal_pdfs.eq(0)
    qa["member_votes"] = qa.session_year.map(vote_counts).fillna(0).astype(int)
    qa["valid_member_votes"] = qa.session_year.map(valid_votes).fillna(0).astype(int)
    qa["final_passage_events"] = qa.session_year.map(passage_counts).fillna(0).astype(int)
    qa["passage_events_with_named_rollcall"] = qa.session_year.map(matched_passages).fillna(0).astype(int)
    qa["passage_events_fully_verified"] = qa.session_year.map(verified_passages).fillna(0).astype(int)
    qa["section63_detection_share"] = qa.passage_events_with_named_rollcall / qa.final_passage_events.replace(0, pd.NA)
    qa["section63_verified_share"] = qa.passage_events_fully_verified / qa.final_passage_events.replace(0, pd.NA)
    qa["valid_share"] = qa.valid_rollcalls / qa.rollcalls.replace(0, pd.NA)
    qa.to_csv(OUT / "historical_senate_journal_rollcall_qa.csv", index=False)
    print(qa.to_string(index=False))


if __name__ == "__main__":
    main()
