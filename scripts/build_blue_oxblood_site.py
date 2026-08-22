"""Build the public site, then apply the shared Blue/Oxblood presentation layer."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from scripts.site_brand import apply_theme
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from site_brand import apply_theme


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STAGE = ROOT / "artifacts" / "blue_oxblood_site"
IDEOLOGY_CANDIDATE = ROOT / "artifacts" / "site" / "ideology-performance.html"
CAUCUS_CANDIDATE = ROOT / "artifacts" / "site" / "caucuses.html"
BUILDERS = (
    "build_2026_forecast_dashboard.py",
    "build_war_story_page.py",
    "build_ideology_thesis_page.py",
    "build_caucus_analysis_page.py",
    "build_legislator_ideology_page.py",
)
PUBLIC_PAGES = (
    "index.html",
    "methodology.html",
    "cmo.html",
    "cmo-methodology.html",
    "ideology-performance.html",
    "caucuses.html",
    "legislators.html",
)


def main() -> None:
    for builder in BUILDERS:
        subprocess.run([sys.executable, str(ROOT / "scripts" / builder)], cwd=ROOT, check=True)
    if not IDEOLOGY_CANDIDATE.exists():
        raise FileNotFoundError(f"Missing reviewed ideology page candidate: {IDEOLOGY_CANDIDATE}")
    shutil.copy2(IDEOLOGY_CANDIDATE, DOCS / "ideology-performance.html")
    if not CAUCUS_CANDIDATE.exists():
        raise FileNotFoundError(f"Missing reviewed caucus page candidate: {CAUCUS_CANDIDATE}")
    shutil.copy2(CAUCUS_CANDIDATE, DOCS / "caucuses.html")
    STAGE.mkdir(parents=True, exist_ok=True)
    for filename in PUBLIC_PAGES:
        path = DOCS / filename
        raw = path.read_text(encoding="utf-8")
        themed = apply_theme(raw)
        path.write_text(themed, encoding="utf-8")
        (STAGE / filename).write_text(themed, encoding="utf-8")
        print(f"Themed {path.relative_to(ROOT)}")
    print(f"Blue/Oxblood site build complete: {DOCS}")


if __name__ == "__main__":
    main()
