"""Fail when obsolete publication artifacts or forbidden dependencies return."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_PUBLIC = re.compile(r"^(cmo_v[23]_|preliminary_cmo_)")
CODE_SUFFIXES = {".py", ".js", ".css", ".sql", ".ps1"}


def failures() -> list[str]:
    problems: list[str] = []
    public_data = ROOT / "docs" / "data"
    if public_data.exists():
        for path in public_data.iterdir():
            if path.is_file() and LEGACY_PUBLIC.match(path.name):
                problems.append(f"legacy public export: {path.relative_to(ROOT)}")

    for base in (ROOT / "scripts", ROOT / "dashboard"):
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in CODE_SUFFIXES:
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"(?:ROOT\s*/\s*)?[\"']docs[\"']\s*/\s*[\"']data[\"']", text):
                problems.append(f"upstream code reads publication data: {path.relative_to(ROOT)}")
    canonical_builder = (ROOT / "scripts" / "build_war_story_page.py").read_text(encoding="utf-8")
    for legacy in ("cmo_v2_", "cmo_v3_", "preliminary_cmo_"):
        if re.search(rf"WAR\s*/\s*[\"']{legacy}", canonical_builder):
            problems.append(f"canonical CMO page builder consumes {legacy.rstrip('_')}")
    catalog = (ROOT / "project_docs" / "data_catalog.csv").read_text(encoding="utf-8")
    if "docs/data/preliminary_cmo" in catalog or "docs/data/cmo_v2_" in catalog or "docs/data/cmo_v3_" in catalog:
        problems.append("data catalog advertises a legacy public CMO export")
    return problems


def main() -> None:
    problems = failures()
    if problems:
        print("Repository hygiene audit failed:")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print("Repository hygiene audit passed: canonical publication boundary is clean.")


if __name__ == "__main__":
    main()
