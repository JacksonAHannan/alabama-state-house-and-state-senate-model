"""Download and fingerprint the Shor--McCarty individual-legislator data.

Harvard Dataverse currently places an AWS WAF browser challenge in front of its
API.  A normal requests download is attempted first.  If challenged, this
script uses Selenium/Chrome only to acquire the WAF cookies, then performs the
same documented Dataverse API request with requests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "ideology"
DOI = "doi:10.7910/DVN/GZJOT3"
FILE_PERSISTENT_ID = f"{DOI}/6PK3W0"
FILENAME = "shor_mccarty_individual_legislators_1993_2018.tsv"
ACCESS_URL = (
    "https://dataverse.harvard.edu/api/access/datafile/:persistentId/"
    f"?persistentId={FILE_PERSISTENT_ID}"
)
LANDING_URL = f"https://dataverse.harvard.edu/dataset.xhtml?persistentId={DOI}"


def browser_session() -> requests.Session:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError as exc:
        raise RuntimeError(
            "Harvard Dataverse presented a browser challenge. Install Selenium "
            "(`python -m pip install selenium`) and rerun."
        ) from exc

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(LANDING_URL)
        time.sleep(5)
        session = requests.Session()
        session.headers["User-Agent"] = driver.execute_script(
            "return navigator.userAgent"
        )
        for cookie in driver.get_cookies():
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )
        return session
    finally:
        driver.quit()


def fetch(resolved_url: str | None = None) -> tuple[bytes, str]:
    if resolved_url:
        response = requests.get(resolved_url, timeout=90)
        response.raise_for_status()
        return response.content, response.url
    session = requests.Session()
    session.headers["User-Agent"] = "alabama-legislative-cmo-research/1.0"
    response = session.get(ACCESS_URL, timeout=90)
    if response.status_code in {202, 403} or response.headers.get("x-amzn-waf-action"):
        session = browser_session()
        response = session.get(ACCESS_URL, timeout=90)
    response.raise_for_status()
    if len(response.content) < 1_000_000:
        raise RuntimeError(
            f"Unexpectedly small response ({len(response.content):,} bytes); "
            "refusing to save it as the dataset."
        )
    return response.content, response.url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="replace local copy")
    parser.add_argument(
        "--resolved-url",
        help="temporary signed download URL obtained from Dataverse (not saved)",
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / FILENAME
    manifest_path = RAW_DIR / "shor_mccarty_manifest.json"
    if target.exists() and not args.force:
        print(f"Already present: {target}")
        return

    content, resolved_url = fetch(args.resolved_url)
    target.write_bytes(content)
    manifest = {
        "title": "Individual State Legislator Shor-McCarty Ideology Data, July 2020 update",
        "authors": ["Boris Shor"],
        "publisher": "Harvard Dataverse",
        "dataset_doi": DOI,
        "dataset_version": "1.0",
        "file_persistent_id": FILE_PERSISTENT_ID,
        "landing_url": LANDING_URL,
        "access_url": ACCESS_URL,
        "resolved_download_host": resolved_url.split("/", 3)[:3],
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "filename": FILENAME,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "coverage": "1993-2018",
        "license": "CC0 1.0",
    }
    # Store only the stable host components; the resolved S3 URL is signed and expires.
    manifest["resolved_download_host"] = "/".join(manifest["resolved_download_host"])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(content):,} bytes to {target}")
    print(f"SHA-256: {manifest['sha256']}")


if __name__ == "__main__":
    main()
