"""Build release-05 before/after overflow candidates for headless measurement.

Isolates the presentation delta: each side is the *published* docs page, and the
"after" side differs only by the theme stylesheet text
(scripts.site_brand.theme_css()) that republishing would inject. Nothing is
written under docs/. `before/` is byte-identical to the published page by
construction; `after/` swaps only the `<style id="blue-oxblood-theme">` block.

For the forecast and Alabama WAR methodology pages the same swap was also
verified against a fresh `--artifact-only` render of each builder themed once
with the new CSS (see ../build_candidates_from_artifacts.py).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import scripts.site_brand as brand  # noqa: E402

HERE = Path(__file__).resolve().parent
PAGES = ("methodology.html", "cmo-methodology.html", "southern-war-methodology.html")


def swap_theme(html: str, css: str) -> str:
    stripped = re.sub(r'<style id="blue-oxblood-theme">.*?</style>', "", html, flags=re.I | re.S)
    if stripped == html:
        raise AssertionError("published page has no blue-oxblood theme block")
    return stripped.replace("</head>", f'<style id="blue-oxblood-theme">{css}</style></head>', 1)


def main() -> None:
    for side in ("before", "after"):
        (HERE / side).mkdir(parents=True, exist_ok=True)
    css = brand.theme_css()
    for name in PAGES:
        published = (ROOT / "docs" / name).read_text(encoding="utf-8")
        (HERE / "before" / name).write_text(published, encoding="utf-8")
        (HERE / "after" / name).write_text(swap_theme(published, css), encoding="utf-8")
        print(f"wrote before/after {name}")


if __name__ == "__main__":
    main()
