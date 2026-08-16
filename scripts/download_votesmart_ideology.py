"""Download historical Vote Smart records for Alabama legislative candidates.

The current API requires a bearer token. Set ``VOTESMART_API_TOKEN`` in the
environment (or in the repository's ignored ``token.env`` file) before running.
Raw API responses are preserved verbatim and fingerprinted; normalization is a
separate step so that API schema changes do not destroy source evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "ideology" / "votesmart"
BASE_URL = "https://api.paas.votesmart.io"
DEFAULT_YEARS = (1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022)
OFFICE_TYPE = "L"
STATE = "AL"
PER_PAGE = 500


class VoteSmartError(RuntimeError):
    """A Vote Smart request failed or returned an unexpected response."""


def load_token() -> str:
    """Read the bearer token without ever printing or persisting it."""
    token = os.environ.get("VOTESMART_API_TOKEN", "").strip()
    if token:
        return token
    token_file = ROOT / "token.env"
    if token_file.exists():
        for line in token_file.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("VOTESMART_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise VoteSmartError(
        "Vote Smart returned 401 for anonymous requests. Set "
        "VOTESMART_API_TOKEN in the environment or token.env."
    )


def stable_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def response_rows(payload: Any) -> list[Any]:
    """Find the API's top-level collection without assuming one wrapper name."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("data", "results", "items", "candidates", "ratings", "rows"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def candidate_ids(payload: Any) -> list[int]:
    """Extract candidate IDs conservatively from a candidate-list response."""
    found: set[int] = set()
    for row in response_rows(payload):
        if not isinstance(row, dict):
            continue
        for key in ("candidateId", "candidate_id", "id"):
            value = row.get(key)
            try:
                if value is not None:
                    found.add(int(value))
                    break
            except (TypeError, ValueError):
                continue
    return sorted(found)


class VoteSmartClient:
    def __init__(self, token: str, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "alabama-legislative-cmo-research/1.0",
            }
        )

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.get(BASE_URL + path, params=params, timeout=90)
        if response.status_code == 401:
            raise VoteSmartError("Vote Smart rejected the bearer token (HTTP 401).")
        if response.status_code == 403:
            raise VoteSmartError(
                f"Vote Smart denied access to {path} (HTTP 403); this endpoint "
                "may require an additional entitlement."
            )
        response.raise_for_status()
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise VoteSmartError(f"Non-JSON response from {path}") from exc
        if not isinstance(payload, dict):
            return {"data": payload}
        return payload

    def get_all(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch every page while retaining page payloads and API metadata."""
        pages: list[dict[str, Any]] = []
        page = 1
        while True:
            query = {**params, "page": page, "perPage": PER_PAGE, "format": "json"}
            payload = self.get(path, query)
            pages.append(payload)
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            last_page = meta.get("lastPage") or meta.get("last_page")
            if last_page is not None:
                if page >= int(last_page):
                    break
            elif len(response_rows(payload)) < PER_PAGE:
                break
            page += 1
            if page > 10_000:
                raise VoteSmartError(f"Pagination safety limit reached for {path}")
        return {"endpoint": path, "request_parameters": params, "pages": pages}


def page_payloads(snapshot: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for page in snapshot.get("pages", []):
        if isinstance(page, dict):
            yield page


def snapshot_candidate_ids(snapshot: dict[str, Any]) -> list[int]:
    found: set[int] = set()
    for payload in page_payloads(snapshot):
        found.update(candidate_ids(payload))
    return sorted(found)


def write_snapshot(name: str, payload: dict[str, Any], manifest: list[dict[str, Any]]) -> None:
    content = stable_json_bytes(payload)
    target = RAW_DIR / f"{name}.json"
    target.write_bytes(content)
    manifest.append(
        {
            "filename": target.name,
            "endpoint": payload.get("endpoint"),
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    )


def download(client: VoteSmartClient, years: tuple[int, ...], include_addons: bool) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    year_arg = ",".join(map(str, years))
    manifest_files: list[dict[str, Any]] = []

    candidates = client.get_all(
        "/v2/candidates/by-office-type-state",
        {"officeTypeId": OFFICE_TYPE, "stateIds": STATE, "electionYears": year_arg},
    )
    write_snapshot("al_legislative_candidates_1994_2022", candidates, manifest_files)

    pct = client.get_all(
        "/v2/viz/pct/by-officetype-state",
        {"officeTypeId": OFFICE_TYPE, "stateId": STATE, "years": year_arg},
    )
    write_snapshot("al_legislative_pct_responses_1994_2022", pct, manifest_files)

    forms = client.get_all(
        "/v2/viz/pct/forms", {"officeTypeId": OFFICE_TYPE, "years": year_arg}
    )
    write_snapshot("state_legislative_pct_forms_1994_2022", forms, manifest_files)

    ids = snapshot_candidate_ids(candidates)
    for index, candidate_id in enumerate(ids, start=1):
        ratings = client.get_all(
            "/v2/ratings/by-candidate", {"candidateId": candidate_id}
        )
        write_snapshot(f"candidate_{candidate_id}_ratings", ratings, manifest_files)
        websites = client.get_all(
            "/v1/address/campaign/web-address/by-candidate",
            {"candidateId": candidate_id},
        )
        write_snapshot(f"candidate_{candidate_id}_campaign_websites", websites, manifest_files)
        if include_addons:
            # Endorsements require PCT row IDs, which are retained in the raw PCT
            # snapshot. They are normalized and requested in the downstream pass.
            pass
        if index % 50 == 0:
            print(f"Downloaded candidate-specific records for {index:,} / {len(ids):,}")

    manifest = {
        "source": "Vote Smart API",
        "base_url": BASE_URL,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "state": STATE,
        "office_type": OFFICE_TYPE,
        "years": list(years),
        "candidate_count": len(ids),
        "addons_requested": include_addons,
        "authentication": "bearer token used but not retained",
        "files": manifest_files,
    }
    (RAW_DIR / "manifest.json").write_bytes(stable_json_bytes(manifest))
    print(f"Saved {len(manifest_files):,} snapshots for {len(ids):,} candidates")


def parse_years(value: str) -> tuple[int, ...]:
    years = tuple(sorted({int(item.strip()) for item in value.split(",") if item.strip()}))
    if not years:
        raise argparse.ArgumentTypeError("at least one election year is required")
    return years


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--years", type=parse_years, default=DEFAULT_YEARS,
        help="comma-separated election years (default: 1994 through 2022 cycles)",
    )
    parser.add_argument(
        "--include-addons", action="store_true",
        help="request entitled endorsement/public-statement layers in later passes",
    )
    args = parser.parse_args()
    download(VoteSmartClient(load_token()), tuple(args.years), args.include_addons)


if __name__ == "__main__":
    main()
