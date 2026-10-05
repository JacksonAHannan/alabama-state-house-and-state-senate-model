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
BUILDERS = (
    "build_2026_forecast_dashboard.py",
    "build_war_story_page.py",
    "build_southern_war_map.py",
    "build_democratic_caucus_page.py",
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


CANDIDATES = {
    "index.html": ROOT / "artifacts" / "site" / "alabama-2026-legislative-forecast.html",
    "methodology.html": ROOT / "artifacts" / "site" / "forecast-methodology.html",
    "cmo.html": ROOT / "artifacts" / "site" / "alabama-legislative-cmo.html",
    "cmo-methodology.html": ROOT / "artifacts" / "site" / "cmo-methodology.html",
    "southern-war.html": ROOT / "artifacts" / "site" / "southern-war.html",
    "southern-war-methodology.html": ROOT / "artifacts" / "site" / "southern-war-methodology.html",
    "ideology-performance.html": IDEOLOGY_CANDIDATE,
}
PREVIEW_BUILDERS = (
    ("build_2026_forecast_dashboard.py", "--artifact-only"),
    ("build_war_story_page.py", "--artifact-only"),
    ("build_southern_war_map.py", "--artifact-only"),
    ("build_democratic_caucus_page.py",),
)


def redirect_page(target: str, title: str, label: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="refresh" content="0; url={target}">'
        f'<link rel="canonical" href="{target}">'
        f'<title>{title} · Jackson Hannan</title></head><body>'
        '<header><nav><a href="ideology-performance.html" aria-current="page">Ideology &amp; caucuses</a></nav></header>'
        f'<main><p>{label} <a href="{target}">Ideology &amp; caucuses</a>.</p></main></body></html>'
    )


def preview() -> None:
    """Render every page as a local candidate and theme it into the ignored stage folder.

    Nothing under docs/ is written. Unchanged downloads are copied from docs/data so
    links resolve; payloads written by artifact-only builders replace their copies.
    """
    stale = []
    for builder, *flags in PREVIEW_BUILDERS:
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / builder), *flags], cwd=ROOT)
        if result.returncode:
            stale.append(builder)
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "data").mkdir(parents=True)
    for source in (DOCS / "data").iterdir():
        if source.is_file():
            shutil.copy2(source, STAGE / "data" / source.name)
    artifact_data = ROOT / "artifacts" / "site" / "data"
    if artifact_data.exists():
        for source in artifact_data.iterdir():
            shutil.copy2(source, STAGE / "data" / source.name)
    pages = {name: path.read_text(encoding="utf-8") for name, path in CANDIDATES.items()}
    pages["methods.html"] = methods_landing()
    pages["caucuses.html"] = redirect_page("ideology-performance.html#groups", "Democratic caucuses",
                                           "The caucus explorer is now part of")
    pages["legislators.html"] = redirect_page("ideology-performance.html#issues", "Candidate evidence",
                                              "The candidate evidence atlas has moved to")
    for name, raw in pages.items():
        (STAGE / name).write_text(apply_theme(raw), encoding="utf-8")
    print(f"Preview site written to {STAGE}; docs/ untouched")
    for builder in stale:
        print(f"WARNING: {builder} refused or failed; its page is the previous local candidate, not this build")


def main() -> None:
    if "--preview" in sys.argv[1:]:
        preview()
        return
    for builder in BUILDERS:
        subprocess.run([sys.executable, str(ROOT / "scripts" / builder)], cwd=ROOT, check=True)
    if not IDEOLOGY_CANDIDATE.exists():
        raise FileNotFoundError(f"Missing reviewed ideology page candidate: {IDEOLOGY_CANDIDATE}")
    shutil.copy2(IDEOLOGY_CANDIDATE, DOCS / "ideology-performance.html")
    (DOCS / "caucuses.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="0; url=ideology-performance.html#groups">'
        '<link rel="canonical" href="ideology-performance.html#groups">'
        '<title>Democratic caucuses · Jackson Hannan</title></head><body>'
        '<header><nav><a href="ideology-performance.html" aria-current="page">Ideology &amp; caucuses</a></nav></header>'
        '<main><p>The caucus explorer is now part of '
        '<a href="ideology-performance.html#groups">Ideology &amp; caucuses</a>.</p></main></body></html>',
        encoding="utf-8",
    )
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
