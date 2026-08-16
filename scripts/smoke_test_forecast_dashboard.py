"""Render the generated dashboard in a real headless browser and check startup."""
from __future__ import annotations

import subprocess
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "artifacts" / "site" / "alabama-2026-legislative-forecast.html"
BROWSERS = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
]


def main():
    browser = next((p for p in BROWSERS if p.exists()), None)
    if browser is None:
        raise SystemExit("No supported Chromium browser found")
    url = PAGE.resolve().as_uri()
    result = subprocess.run(
        [str(browser), "--headless", "--disable-gpu", "--dump-dom", url],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    rendered = result.stdout
    soup = BeautifulSoup(rendered, "html.parser")
    checks = {
        "no runtime error": soup.select_one("body > main.error") is None,
        "overview rendered": "Median Democratic seats" in rendered,
        "default race selected": "State House District 25" in rendered,
        "map paths interactive": 'role="button" tabindex="0"' in rendered,
        "table rendered": 'id="rows"><tr' in rendered,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit("Browser smoke checks failed: " + ", ".join(failed))
    print("Browser smoke checks passed: " + ", ".join(checks))


if __name__ == "__main__":
    main()
