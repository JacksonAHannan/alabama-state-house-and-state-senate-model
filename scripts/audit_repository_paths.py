"""Fail when executable project files refer to retired root-level paths."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = [ROOT / "scripts", ROOT / "dashboard", ROOT / "project_docs", ROOT / "research"]
TEXT_SUFFIXES = {".py", ".js", ".css", ".md", ".json", ".csv", ".ps1"}
RETIRED = [
    "Results and Shapefiles",
    "Candidate Financial Information",
    "Candidate Information",
    "data-GiFps.csv",
    'ROOT / "Alabama 2026 Legislative Forecast.html"',
    'ROOT / "Alabama Legislative Candidate Margin Overperformance (CMO).html"',
]
REQUIRED = [
    ROOT / "data" / "raw" / "alabama_elections_and_geography",
    ROOT / "data" / "raw" / "finance" / "alabama",
    ROOT / "docs" / "index.html",
    ROOT / "docs" / "cmo.html",
    ROOT / "docs" / "legislators.html",
]


def violations() -> list[str]:
    found = []
    for base in SEARCH_ROOTS:
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            # Historical migration documentation is allowed to name old paths.
            if path in {
                ROOT / "project_docs" / "REPOSITORY_LAYOUT.md",
                ROOT / "scripts" / "audit_repository_paths.py",
            }:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for retired in RETIRED:
                if retired in text:
                    found.append(f"{path.relative_to(ROOT)}: {retired}")
    return found


def main() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.exists()]
    stale = violations()
    if missing or stale:
        if missing:
            print("Missing required paths:", *missing, sep="\n- ")
        if stale:
            print("Retired path references:", *stale, sep="\n- ")
        raise SystemExit(1)
    print(f"Repository path audit passed ({len(REQUIRED)} required paths checked).")


if __name__ == "__main__":
    main()
