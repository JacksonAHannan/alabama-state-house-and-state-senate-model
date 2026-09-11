"""Acquire and validate MEDSL files needed by the Southern WAR panel audit."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "historical_statewide_elections" / "medsl_github"
MANIFEST = RAW_ROOT / "manifest.csv"
REPORT = ROOT / "project_docs" / "sources" / "MEDSL_SOUTHERN_GAP_ACQUISITION.md"
USER_AGENT = "Jackson-Hannan-Alabama-legislative-model source acquisition"


TARGETS = [
    {
        "state": "KY",
        "year": 2016,
        "repo": "official-precinct-returns",
        "branch": "master",
        "repo_path": "source/2016-ky-precinct.zip",
        "required_offices": ["STATE HOUSE", "STATE SENATE", "US PRESIDENT"],
        "ticket_candidates": {"HILLARY CLINTON": "DEMOCRAT", "DONALD TRUMP": "REPUBLICAN"},
    },
    {
        "state": "KY",
        "year": 2022,
        "repo": "2022-elections-official",
        "repo_path": "individual_states/2022-ky-local-precinct-general.zip",
        "required_offices": ["STATE HOUSE", "STATE SENATE", "US SENATE"],
    },
    {
        "state": "MO",
        "year": 2022,
        "repo": "2022-elections-official",
        "repo_path": "individual_states/2022-mo-local-precinct-general.zip",
        "required_offices": ["STATE HOUSE", "STATE SENATE", "US SENATE"],
    },
    {
        "state": "OK",
        "year": 2022,
        "repo": "2022-elections-official",
        "repo_path": "individual_states/2022-ok-local-precinct-general.zip",
        "required_offices": ["STATE HOUSE", "STATE SENATE", "GOVERNOR"],
    },
    {
        "state": "SC",
        "year": 2022,
        "repo": "2022-elections-official",
        "repo_path": "individual_states/2022-sc-local-precinct-general.zip",
        "required_offices": ["STATE HOUSE", "GOVERNOR"],
    },
    {
        "state": "AR",
        "year": 2024,
        "repo": "2024-elections-official",
        "repo_path": "individual_states/ar24.zip",
        "required_offices": ["STATE HOUSE", "STATE SENATE", "US PRESIDENT"],
    },
    {
        "state": "KY",
        "year": 2024,
        "repo": "2024-elections-official",
        "repo_path": "individual_states/ky24.zip",
        "required_offices": ["STATE HOUSE", "STATE SENATE", "US PRESIDENT"],
    },
    {
        "state": "OK",
        "year": 2024,
        "repo": "2024-elections-official",
        "repo_path": "individual_states/ok24.zip",
        "required_offices": ["STATE HOUSE", "STATE SENATE", "US PRESIDENT"],
    },
    {
        "state": "SC",
        "year": 2024,
        "repo": "2024-elections-official",
        "repo_path": "individual_states/sc24.zip",
        "required_offices": ["STATE HOUSE", "STATE SENATE", "US PRESIDENT"],
    },
    {
        "state": "TN",
        "year": 2024,
        "repo": "2024-elections-official",
        "repo_path": "individual_states/tn24.zip",
        "required_offices": ["STATE HOUSE", "STATE SENATE", "US PRESIDENT"],
    },
]


def _request_bytes(url: str, attempts: int = 4) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Download failed after {attempts} attempts: {url}") from last_error


def _metadata(repo: str, repo_path: str, branch: str = "main") -> dict[str, object]:
    quoted_path = "/".join(urllib.parse.quote(piece) for piece in repo_path.split("/"))
    url = f"https://api.github.com/repos/MEDSL/{repo}/contents/{quoted_path}?ref={urllib.parse.quote(branch)}"
    return json.loads(_request_bytes(url))


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _load_previous_manifest() -> dict[tuple[str, int], dict[str, str]]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(newline="", encoding="utf-8-sig") as handle:
        return {(row["state"], int(row["year"])): row for row in csv.DictReader(handle)}


def _validate_zip(content: bytes, target: dict[str, object]) -> dict[str, object]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"Corrupt ZIP member {bad_member} in {target['repo_path']}")
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_members:
            raise ValueError(f"No CSV member in {target['repo_path']}")
        offices: set[str] = set()
        parties_by_office: dict[str, set[str]] = {}
        candidates_by_office: dict[str, set[str]] = {}
        row_count = 0
        for member in csv_members:
            with archive.open(member) as raw_handle:
                text_handle = io.TextIOWrapper(raw_handle, encoding="utf-8-sig", errors="replace", newline="")
                reader = csv.DictReader(text_handle)
                required_columns = {"precinct", "office", "candidate", "votes", "state", "year"}
                missing_columns = required_columns.difference(reader.fieldnames or [])
                if missing_columns:
                    raise ValueError(f"{member} lacks columns {sorted(missing_columns)}")
                for row in reader:
                    row_count += 1
                    office = str(row.get("office", "")).strip().upper()
                    offices.add(office)
                    party = str(row.get("party_simplified", "")).strip().upper()
                    parties_by_office.setdefault(office, set()).add(party)
                    candidates_by_office.setdefault(office, set()).add(str(row.get("candidate", "")).strip().upper())

        missing_offices = set(target["required_offices"]).difference(offices)
        if missing_offices:
            raise ValueError(f"{target['repo_path']} lacks required offices {sorted(missing_offices)}")
        ticket_office = str(target["required_offices"][-1])
        ticket_parties = parties_by_office.get(ticket_office, set())
        named_ticket_parties = {
            party for candidate, party in dict(target.get("ticket_candidates", {})).items()
            if candidate in candidates_by_office.get(ticket_office, set())
        }
        if not (
            {"DEMOCRAT", "REPUBLICAN"}.issubset(ticket_parties)
            or {"DEMOCRATIC", "REPUBLICAN"}.issubset(ticket_parties)
            or {"DEMOCRAT", "REPUBLICAN"}.issubset(named_ticket_parties)
        ):
            raise ValueError(
                f"{target['repo_path']} ticket office {ticket_office} does not have both major parties: {sorted(ticket_parties)}"
            )
        return {
            "csv_members": "|".join(csv_members),
            "row_count": row_count,
            "office_count": len(offices),
            "required_offices_present": "|".join(target["required_offices"]),
            "ticket_major_parties_present": True,
        }


def _write_manifest(rows: list[dict[str, object]]) -> None:
    fields = [
        "provider",
        "state",
        "year",
        "repository",
        "branch",
        "repository_path",
        "github_blob_sha",
        "download_url",
        "local_path",
        "retrieved_utc",
        "bytes",
        "sha256",
        "csv_members",
        "row_count",
        "office_count",
        "required_offices_present",
        "ticket_major_parties_present",
        "validation_status",
    ]
    temp_path = MANIFEST.with_suffix(".csv.tmp")
    with temp_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp_path, MANIFEST)


def _write_report(rows: list[dict[str, object]]) -> None:
    lines = [
        "# MEDSL Southern gap acquisition",
        "",
        f"{len(rows)} individual-state files were acquired from MEDSL's official GitHub repositories. Source ZIP bytes are preserved unchanged under `data/raw/historical_statewide_elections/medsl_github/`.",
        "",
        "| State | Year | Required offices verified | Rows | Local file | SHA-256 |",
        "| --- | ---: | --- | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['state']} | {row['year']} | {str(row['required_offices_present']).replace('|', ', ')} | "
            f"{int(row['row_count']):,} | `{row['local_path']}` | `{row['sha256']}` |"
        )
    lines += [
        "",
        "Each ZIP passed archive integrity checks, contained the expected standardized CSV schema, included every required legislative/ticket office, and contained both major parties for the selected ticket office. GitHub blob identifiers and retrieval timestamps are retained in `manifest.csv`.",
        "",
        "These files are source evidence only. They are not considered integrated until a downstream normalization task reconciles precinct identifiers, aggregates ticket votes into legislative districts, validates statewide totals, and publishes an approved analytical mart.",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    previous = _load_previous_manifest()
    rows: list[dict[str, object]] = []
    for target in TARGETS:
        branch = str(target.get("branch", "main"))
        metadata = _metadata(str(target["repo"]), str(target["repo_path"]), branch)
        content = _request_bytes(str(metadata["download_url"]))
        if len(content) != int(metadata["size"]):
            raise ValueError(f"Size mismatch for {target['repo_path']}: {len(content)} != {metadata['size']}")
        digest = _sha256(content)
        validation = _validate_zip(content, target)
        destination = RAW_ROOT / str(target["year"]) / Path(str(target["repo_path"])).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing_digest = _sha256(destination.read_bytes())
            if existing_digest != digest:
                raise FileExistsError(
                    f"Raw source changed upstream; refusing to overwrite {destination}. "
                    f"existing={existing_digest} upstream={digest}"
                )
        else:
            temp_path = destination.with_suffix(destination.suffix + ".download")
            temp_path.write_bytes(content)
            os.replace(temp_path, destination)

        old = previous.get((str(target["state"]), int(target["year"])), {})
        retrieved = old.get("retrieved_utc") if old.get("sha256") == digest else None
        rows.append(
            {
                "provider": "MIT Election Data and Science Lab",
                "state": target["state"],
                "year": target["year"],
                "repository": f"MEDSL/{target['repo']}",
                "branch": branch,
                "repository_path": target["repo_path"],
                "github_blob_sha": metadata["sha"],
                "download_url": metadata["download_url"],
                "local_path": destination.relative_to(ROOT).as_posix(),
                "retrieved_utc": retrieved or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "bytes": len(content),
                "sha256": digest,
                **validation,
                "validation_status": "validated",
            }
        )
        print(f"Validated {target['state']} {target['year']}: {destination.name} ({len(content):,} bytes)")

    _write_manifest(rows)
    _write_report(rows)
    print(f"Wrote {MANIFEST.relative_to(ROOT)} with {len(rows)} records")


if __name__ == "__main__":
    main()
