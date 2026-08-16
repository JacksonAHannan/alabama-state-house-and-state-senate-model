"""Normalize manually downloaded LegiScan Alabama JSON session archives.

Expected input: ZIP files downloaded from https://legiscan.com/AL/datasets in
data/raw/legiscan/alabama. The importer never modifies the raw archives.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "legiscan" / "alabama"
OUT = ROOT / "data" / "processed" / "legislative"
VOTE_ID_LABELS = {1: "Yea", 2: "Nay", 3: "Not Voting", 4: "Absent"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_year(value: object, source_name: str) -> int | None:
    candidates = [str(value or ""), source_name]
    for candidate in candidates:
        # Archive filenames separate years with underscores, which count as word
        # characters and therefore defeat a conventional ``\b`` boundary.
        match = re.search(r"(?<!\d)(20(?:1\d|2\d))(?!\d)", candidate)
        if match:
            return int(match.group(1))
    return None


def iter_archive_json(path: Path):
    """Yield (member name, decoded JSON) from ZIP or extracted JSON tree."""
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for member in sorted(archive.namelist()):
                if member.lower().endswith(".json") and not member.endswith("/"):
                    with archive.open(member) as handle:
                        yield member, json.load(io.TextIOWrapper(handle, encoding="utf-8-sig"))
    elif path.is_dir():
        for json_path in sorted(path.rglob("*.json")):
            yield str(json_path.relative_to(path)), json.loads(
                json_path.read_text(encoding="utf-8-sig")
            )


def payload(record: object, key: str) -> dict | None:
    if not isinstance(record, dict):
        return None
    value = record.get(key)
    if isinstance(value, dict):
        return value
    if key == "roll_call" and isinstance(record.get("rollcall"), dict):
        return record["rollcall"]
    if key == "person" and isinstance(record.get("people"), dict):
        return record["people"]
    required = {"bill": "bill_id", "roll_call": "roll_call_id", "person": "people_id"}
    return record if required[key] in record else None


def chamber_label(value: object) -> str:
    text = str(value or "").strip().lower()
    return {"1": "house", "2": "senate", "h": "house", "s": "senate"}.get(text, text)


def vote_label(vote: dict) -> str:
    for key in ["vote_text", "vote", "text"]:
        if vote.get(key) not in (None, ""):
            text = str(vote[key]).strip()
            return {
                "AYE": "Yea", "YES": "Yea", "YEA": "Yea",
                "NO": "Nay", "NAY": "Nay",
                "NV": "Not Voting", "NOT VOTING": "Not Voting",
                "ABSENT": "Absent",
            }.get(text.upper(), text)
    try:
        return VOTE_ID_LABELS.get(int(vote.get("vote_id")), str(vote.get("vote_id")))
    except (TypeError, ValueError):
        return ""


def normalize_name(value: object) -> str:
    text = re.sub(r"[^A-Z0-9 ]", " ", str(value or "").upper())
    tokens = [token for token in text.split() if token not in {"JR", "SR", "II", "III", "IV"}]
    return " ".join(tokens)


def parse_archives(paths: list[Path]) -> tuple[pd.DataFrame, ...]:
    bills: dict[int, dict] = {}
    rollcalls: dict[int, dict] = {}
    people: dict[tuple[int | None, int], dict] = {}
    votes: list[dict] = []
    manifests: list[dict] = []

    for archive_path in paths:
        source_name = archive_path.name
        manifests.append({
            "source_archive": source_name,
            "bytes": archive_path.stat().st_size if archive_path.is_file() else None,
            "sha256": sha256(archive_path) if archive_path.is_file() else None,
            "license": "CC BY 4.0",
            "source_url": "https://legiscan.com/AL/datasets",
        })
        for member, record in iter_archive_json(archive_path):
            bill = payload(record, "bill")
            if bill:
                bill_id = int(bill["bill_id"])
                session = bill.get("session") if isinstance(bill.get("session"), dict) else {}
                year = infer_year(session.get("session_name") or session.get("year"), source_name)
                bills[bill_id] = {
                    "bill_id": bill_id,
                    "session_id": session.get("session_id") or bill.get("session_id"),
                    "session_year": year,
                    "session_name": session.get("session_name") or bill.get("session_name"),
                    "bill_number": bill.get("bill_number") or bill.get("number"),
                    "title": bill.get("title"),
                    "description": bill.get("description"),
                    "status": bill.get("status"),
                    "status_date": bill.get("status_date"),
                    "url": bill.get("url"),
                    "state_link": bill.get("state_link"),
                    "source_archive": source_name,
                    "source_member": member,
                }

            roll = payload(record, "roll_call")
            if roll:
                roll_id = int(roll["roll_call_id"])
                year = infer_year(roll.get("date"), source_name)
                rollcalls[roll_id] = {
                    "roll_call_id": roll_id,
                    "bill_id": roll.get("bill_id"),
                    "session_year": year,
                    "vote_date": roll.get("date"),
                    "chamber": chamber_label(roll.get("chamber") or roll.get("chamber_id")),
                    "vote_description": roll.get("desc") or roll.get("description"),
                    "yea": roll.get("yea"), "nay": roll.get("nay"),
                    "not_voting": roll.get("nv"), "absent": roll.get("absent"),
                    "total": roll.get("total"), "passed": roll.get("passed"),
                    "url": roll.get("url"), "state_link": roll.get("state_link"),
                    "source_archive": source_name, "source_member": member,
                }
                individual = roll.get("votes") or roll.get("vote") or []
                if isinstance(individual, dict):
                    individual = list(individual.values())
                for item in individual:
                    if not isinstance(item, dict):
                        continue
                    votes.append({
                        "roll_call_id": roll_id,
                        "bill_id": roll.get("bill_id"),
                        "session_year": year,
                        "vote_date": roll.get("date"),
                        "chamber": chamber_label(roll.get("chamber") or roll.get("chamber_id")),
                        "people_id": item.get("people_id") or item.get("person_id"),
                        "vote_id": item.get("vote_id"),
                        "vote": vote_label(item),
                        "source_archive": source_name,
                    })

            person = payload(record, "person")
            if person:
                people_id = int(person["people_id"])
                year = infer_year(person.get("session_name") or person.get("year"), source_name)
                full_name = person.get("name") or " ".join(filter(None, [
                    person.get("first_name"), person.get("middle_name"),
                    person.get("last_name"), person.get("suffix"),
                ]))
                people[(year, people_id)] = {
                    "session_year": year, "people_id": people_id,
                    "name": full_name, "normalized_name": normalize_name(full_name),
                    "first_name": person.get("first_name"),
                    "middle_name": person.get("middle_name"),
                    "last_name": person.get("last_name"), "suffix": person.get("suffix"),
                    "party": person.get("party"), "party_id": person.get("party_id"),
                    "role": person.get("role"), "role_id": person.get("role_id"),
                    "district": person.get("district"), "source_archive": source_name,
                    "source_member": member,
                }

    bill_df = pd.DataFrame(bills.values())
    roll_df = pd.DataFrame(rollcalls.values())
    people_df = pd.DataFrame(people.values())
    vote_df = pd.DataFrame(votes)
    if not vote_df.empty:
        vote_df = vote_df.drop_duplicates(["roll_call_id", "people_id"], keep="last")
    manifest_df = pd.DataFrame(manifests)
    return bill_df, roll_df, people_df, vote_df, manifest_df


def candidate_matches(people: pd.DataFrame) -> pd.DataFrame:
    candidates = pd.read_csv(ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv")
    candidates["normalized_name"] = candidates.canonical_name.map(normalize_name)
    merged = people.merge(
        candidates,
        on="normalized_name",
        how="left", suffixes=("_legiscan", "_candidate"),
    )
    merged["years_before_election"] = merged["year"] - merged["session_year"]
    plausible = merged["person_id"].notna() & merged["years_before_election"].between(0, 8)
    merged["match_status"] = plausible.map({True: "exact_name_candidate", False: "unmatched_or_out_of_window"})
    # Party is deliberately not a match key: Alabama legislators sometimes switched parties.
    merged = merged[plausible | merged["person_id"].isna()].copy()
    return merged[[
        "session_year", "people_id", "name", "party", "role", "district_legiscan",
        "year", "years_before_election", "person_id", "canonical_candidate_id",
        "canonical_name", "canonical_party",
        "chamber", "district_candidate", "match_status", "source_archive",
    ]]


def main() -> None:
    if RAW.exists():
        paths = sorted(RAW.glob("*.zip")) + sorted(
            path for path in RAW.iterdir() if path.is_dir()
        )
    else:
        paths = []
    if not paths:
        raise FileNotFoundError(
            f"No LegiScan JSON archives found in {RAW}. Download Alabama API JSON ZIPs "
            "from https://legiscan.com/AL/datasets after free registration."
        )
    OUT.mkdir(parents=True, exist_ok=True)
    bills, rollcalls, people, votes, manifest = parse_archives(paths)
    if rollcalls.empty or votes.empty or people.empty:
        raise ValueError("Archives did not expose bill, roll-call, and people JSON payloads")
    bills.to_csv(OUT / "legiscan_alabama_bills.csv", index=False)
    rollcalls.to_csv(OUT / "legiscan_alabama_rollcalls.csv", index=False)
    people.to_csv(OUT / "legiscan_alabama_legislators.csv", index=False)
    votes.to_csv(OUT / "legiscan_alabama_individual_votes.csv", index=False)
    manifest.to_csv(OUT / "legiscan_source_manifest.csv", index=False)
    matches = candidate_matches(people)
    matches.to_csv(OUT / "legiscan_candidate_identity_matches.csv", index=False)

    tally = votes.groupby("roll_call_id").vote.value_counts().unstack(fill_value=0)
    qa = rollcalls[["roll_call_id", "yea", "nay", "not_voting", "absent", "total"]].merge(
        tally, on="roll_call_id", how="left"
    )
    qa["parsed_vote_count"] = tally.reindex(qa.roll_call_id).sum(axis=1).to_numpy()
    qa["reported_total_matches"] = pd.to_numeric(qa.total, errors="coerce").eq(qa.parsed_vote_count)
    qa.to_csv(OUT / "legiscan_rollcall_qa.csv", index=False)
    print(
        f"Imported {len(bills)} bills, {len(rollcalls)} roll calls, {len(votes)} individual votes, "
        f"and {len(people)} session-legislator records from {len(paths)} archives"
    )


if __name__ == "__main__":
    main()
