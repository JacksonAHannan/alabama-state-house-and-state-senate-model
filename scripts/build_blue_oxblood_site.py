"""Build the public site, then apply the shared Blue/Oxblood presentation layer."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from scripts.site_brand import apply_theme, methods_landing
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from site_brand import apply_theme, methods_landing


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STAGE = ROOT / "artifacts" / "blue_oxblood_site"
IDEOLOGY_CANDIDATE = ROOT / "artifacts" / "site" / "ideology-performance.html"
CAUCUS_CANDIDATE = ROOT / "artifacts" / "site" / "caucuses.html"
BUILDERS = (
    "build_2026_forecast_dashboard.py",
    "build_war_story_page.py",
    "build_southern_war_map.py",
    "build_democratic_transition_page.py",
    "build_caucus_analysis_page.py",
    "build_legislator_ideology_page.py",
)
PUBLIC_PAGES = (
    "index.html",
    "methodology.html",
    "cmo.html",
    "cmo-methodology.html",
    "southern-war.html",
    "southern-war-methodology.html",
    "methods.html",
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
    (DOCS / "methods.html").write_text(methods_landing(), encoding="utf-8")
    (DOCS / "legislators.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="0; url=ideology-performance.html#issues">'
        '<link rel="canonical" href="ideology-performance.html#issues">'
        '<title>Candidate evidence · Jackson Hannan</title></head><body>'
        '<header><nav><a href="ideology-performance.html" aria-current="page">Ideology &amp; caucuses</a></nav></header>'
        '<main><p>The candidate evidence atlas has moved to '
        '<a href="ideology-performance.html#issues">Ideology &amp; caucuses</a>.</p></main></body></html>',
        encoding="utf-8",
    )
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
