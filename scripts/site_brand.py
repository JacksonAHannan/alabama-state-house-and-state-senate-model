"""Shared post-build branding for self-contained public HTML pages."""

from __future__ import annotations

import base64
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "dashboard" / "blue_oxblood_theme.css"
PORTRAIT = Path(r"C:\Users\User\Desktop\images.jfif")
SOCIAL_LINK = '<a href="https://x.com/electionsjack" target="_blank" rel="me noopener">@electionsjack</a>'


def portrait_uri() -> str:
    encoded = base64.b64encode(PORTRAIT.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def theme_css() -> str:
    return THEME.read_text(encoding="utf-8").replace("__PORTRAIT_URI__", portrait_uri())


def script_blocks(html: str) -> list[str]:
    return re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, flags=re.I | re.S)


def apply_theme(html: str) -> str:
    """Apply presentation changes without altering embedded scripts or payloads."""
    scripts_before = script_blocks(html)
    html = re.sub(r"@import\s+url\([^)]*fonts\.googleapis\.com[^)]*\)\s*;", "", html, flags=re.I)
    html = html.replace("</head>", f"<style id=\"blue-oxblood-theme\">{theme_css()}</style></head>", 1)
    html = html.replace("<body>", '<body data-site-theme="blue-oxblood">', 1)
    if SOCIAL_LINK not in html:
        html = html.replace("</nav>", SOCIAL_LINK + "</nav>", 1)
    replacements = {
        "What did Alabama's standout Democrats stand for?": "Alabama Legislator Issue Atlas",
        "The politics behind overperformance": "Candidate issue evidence",
        "An evidence atlas of the votes, bills, amendments, and public positions of 30 Democratic legislative candidates who substantially outran expectations from 2010 through 2022.":
            "Reviewed legislative votes, bills, amendments, public positions, and Vote Smart responses for the target candidate cohort.",
        "The issue mosaic": "Candidate issue matrix",
        "Comparative view": "Candidate comparison",
        "What this page measuresâ€”and what it does not": "Methods and limitations",
        "What this page measures—and what it does not": "Methods and limitations",
        "Direction is not certainty": "Evidence interpretation",
        "Color describes reviewed actions and candidate-supplied questionnaire positions. Opacity describes how much evidence exists; gray means we do not know.":
            "Color indicates the direction of reviewed evidence. Opacity indicates evidence volume. Gray indicates no directional evidence.",
        "Alabama Democrats have not overperformed in only one way. Some paired support for public investment with culturally conservative votes. Others assembled records centered on labor, civil rights, local economic development, or constituent service. This page shows those combinations without forcing every career onto a single national left–right line.":
            "The matrix reports reviewed directional evidence by candidate and issue family. Issue positions are displayed separately because candidates may combine positions that do not fall on a single left–right scale.",
        "How far Alabama legislative candidates ran ahead of or behind the modelâ€™s district-level expectation from 1994 through 2022.":
            "Historical legislative candidate margins relative to district-level expected margins, 1994–2022.",
        "How far Alabama legislative candidates ran ahead of or behind the model’s district-level expectation from 1994 through 2022.":
            "Historical legislative candidate margins relative to district-level expected margins, 1994–2022.",
        "<p>Winning a race is not the same thing as running a strong campaign. Candidate Margin Overperformance asks: <em>how much better or worse was a candidate's two-party margin than the model expected in that race?</em></p>":
            "<p>Candidate Margin Overperformance is the candidate's observed two-party margin minus the model's expected candidate margin.</p>",
        "Ideology and Democratic overperformance in Alabama": "Ideology and Electoral Performance",
        "Alabama's Democratic legislative survivors were not merely conservative compared with one another. On a nationally comparable scale, even much of the caucus's liberal wing sat well to the right of other Democrats—and candidates farther right repeatedly ran ahead of statewide and federal expectations.":
            "Historical associations between absolute candidate ideology, Candidate Margin Overperformance, and performance relative to statewide and federal baselines.",
        "The updated finding:": "Summary finding:",
        "Ideology no longer defines the expectation": "Ideology-blind expected margin",
        "The Democratic relationship is strong; the Republican mirror is suggestive": "Party-specific absolute-ideology estimates",
        "The parties barely overlap—and Shor observes officeholders": "Sample overlap and Shor coverage",
        "Do incumbency and money explain the relationship away?": "Incumbency and finance adjustment",
        "A culturally conservative, economically mixed coalition": "Issue-level estimates",
        "See the observations behind every issue": "Candidate-level issue evidence",
        "Congruence is a hypothesis, not a universal result": "District-position congruence",
        "The historical result is stable; the modern estimate is data-limited": "Era estimates and robustness",
        "What the page supports": "Interpretation and limitations",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    if script_blocks(html) != scripts_before:
        raise AssertionError("Branding transformation altered embedded JavaScript or data payloads")
    return html
