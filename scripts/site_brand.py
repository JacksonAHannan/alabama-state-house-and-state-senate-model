"""Shared post-build branding for self-contained public HTML pages."""

from __future__ import annotations

import base64
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "dashboard" / "blue_oxblood_theme.css"
PORTRAIT = Path(r"C:\Users\User\Desktop\images.jfif")
PUBLIC_NAV = (
    ("index.html", "Forecast"),
    ("cmo.html", "CMO"),
    ("ideology-performance.html", "Ideology &amp; caucuses"),
    ("methods.html", "Methods"),
)
EXTERNAL_NAV = (
    ("https://github.com/JacksonAHannan", "GitHub"),
    ("https://www.instagram.com/topsoilintraining/", "Instagram"),
    ("https://substack.com/@jacksonhannan", "Substack"),
    ("https://www.linkedin.com/in/jackson-hannan", "LinkedIn"),
    ("https://x.com/electionsjack", "@electionsjack"),
)


def portrait_uri() -> str:
    encoded = base64.b64encode(PORTRAIT.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def theme_css() -> str:
    return THEME.read_text(encoding="utf-8").replace("__PORTRAIT_URI__", portrait_uri())


def script_blocks(html: str) -> list[str]:
    return re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, flags=re.I | re.S)


def active_public_page(html: str) -> str | None:
    """Read the source page's active route before replacing its local header."""
    match = re.search(
        r"<a\b(?=[^>]*\baria-current=[\"']page[\"'])(?=[^>]*\bhref=[\"']([^\"']+)[\"'])[^>]*>",
        html,
        flags=re.I,
    )
    if not match:
        return None
    route = match.group(1).split("#", 1)[0].split("?", 1)[0]
    if route in {"legislators.html", "caucuses.html"}:
        return "ideology-performance.html"
    if route in {"methodology.html", "cmo-methodology.html"}:
        return "methods.html"
    return route


def shared_header(active_page: str | None) -> str:
    """Return the single public masthead used by every substantive page."""
    internal = []
    for href, label in PUBLIC_NAV:
        current = ' aria-current="page"' if href == active_page else ""
        internal.append(f'<a href="{href}"{current}>{label}</a>')
    twitter_href, twitter_label = EXTERNAL_NAV[-1]
    return (
        '<a class="skip-link" href="#main-content">Skip to main content</a>'
        '<header class="site-header"><div class="site-header-inner">'
        '<a class="site-identity" href="index.html" aria-label="Jackson Hannan — Alabama legislative models">'
        '<span class="site-portrait" aria-hidden="true"></span>'
        '<span class="site-wordmark">Jackson Hannan<small>Alabama legislative models</small></span></a>'
        '<div class="site-nav-group"><nav class="site-nav" aria-label="Primary navigation">'
        + "".join(internal)
        + '</nav><a class="site-utility-link" href="'
        + twitter_href
        + '" target="_blank" rel="me noopener">'
        + twitter_label
        + "</a></div></div></header>"
    )


def normalize_header(html: str) -> str:
    """Replace the first page header while retaining the source page identity."""
    active_page = active_public_page(html)
    return re.sub(
        r"<header(?:\s[^>]*)?>.*?</header>",
        lambda _: shared_header(active_page),
        html,
        count=1,
        flags=re.I | re.S,
    )


def shared_footer() -> str:
    external = [
        f'<a href="{href}" target="_blank" rel="me noopener">{label}</a>'
        for href, label in EXTERNAL_NAV
    ]
    return (
        '<footer class="site-footer"><div><b>Jackson Hannan</b>'
        '<span>Alabama legislative models</span></div>'
        '<nav aria-label="Social links">'
        + "".join(external)
        + '</nav></footer>'
    )


def normalize_main(html: str) -> str:
    if re.search(r'<main\b[^>]*\bid=["\']main-content["\']', html, flags=re.I):
        return html
    return re.sub(r'<main\b([^>]*)>', r'<main id="main-content"\1>', html, count=1, flags=re.I)


def normalize_footer(html: str) -> str:
    if re.search(r'<footer(?:\s[^>]*)?>.*?</footer>', html, flags=re.I | re.S):
        return re.sub(
            r'<footer(?:\s[^>]*)?>.*?</footer>',
            lambda _: shared_footer(),
            html,
            count=1,
            flags=re.I | re.S,
        )
    return html.replace('</body>', shared_footer() + '</body>', 1)


def normalize_method_toc(html: str) -> str:
    """Add a compact native disclosure for long methodology navigation on phones."""
    match = re.search(r'<aside class="toc">(.*?)</aside>', html, flags=re.I | re.S)
    if not match or 'class="mobile-toc"' in html:
        return html
    links = re.findall(r'<a\b[^>]*href=["\'][^"\']+["\'][^>]*>.*?</a>', match.group(1), flags=re.I | re.S)
    if not links:
        return html
    mobile = (
        '<details class="mobile-toc"><summary>On this page</summary>'
        '<nav aria-label="On this page">' + ''.join(links) + '</nav></details>'
    )
    return html[:match.start()] + mobile + match.group(0) + html[match.end():]


def methods_landing() -> str:
    """Return the unthemed methods index; the standard build applies the shell."""
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Methodology for Jackson Hannan's Alabama legislative forecast, CMO, and ideology analysis">
<title>Methods · Jackson Hannan</title><style>
*{box-sizing:border-box}body{margin:0}.methods-shell{width:min(1000px,calc(100% - 40px));margin:auto;padding:52px 0 90px}.methods-hero{max-width:760px}.methods-hero h1{margin:0 0 16px}.methods-hero p{font:19px/1.6 Georgia,serif}.methods-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;margin-top:38px;background:#9db4c1;border:1px solid #9db4c1}.methods-card{display:flex;min-height:230px;flex-direction:column;background:#f8fbfc;padding:24px;color:#211b1b;text-decoration:none}.methods-card h2{margin:0 0 10px;font-size:24px}.methods-card p{margin:0 0 22px;line-height:1.55;color:#586772}.methods-card span{margin-top:auto;font-weight:700}.methods-notes{margin-top:44px;padding-top:20px;border-top:3px solid #743b42}.methods-notes p{max-width:760px;font:16px/1.65 Georgia,serif}@media(max-width:760px){.methods-shell{padding:38px 0 65px}.methods-grid{grid-template-columns:1fr}.methods-card{min-height:0}}
</style></head><body><header><nav><a href="methods.html" aria-current="page">Methods</a></nav></header><main>
<section class="methods-shell"><div class="methods-hero"><div class="kicker">Documentation</div><h1>Methods</h1><p>Definitions, data sources, validation, and limitations for the forecast, Candidate Margin Overperformance, and historical ideology analysis.</p></div>
<div class="methods-grid"><a class="methods-card" href="methodology.html"><h2>Forecast methodology</h2><p>National environment, district baselines, incumbency, fundraising, uncertainty, simulations, and historical testing.</p><span>Read forecast methods →</span></a><a class="methods-card" href="cmo-methodology.html"><h2>CMO methodology</h2><p>Ticket selection, Direct CMO, Southern historical comparison, residual candidate quality, and coverage limitations.</p><span>Read CMO methods →</span></a><a class="methods-card" href="ideology-performance.html#methods"><h2>Ideology methods</h2><p>Issue evidence, caucus clustering, Candidate Quality Index comparisons, era estimates, and interpretation limits.</p><span>Read ideology methods →</span></a></div>
<div class="methods-notes"><h2>Measure definitions</h2><p><b>CMO</b> is an observed legislative margin relative to a selected same-district ticket. <b>Candidate Quality Index (CQI)</b> estimates a repeatable, partially pooled candidate component. <b>Raw ticket comparisons</b> retain incumbency, fundraising, and other mechanisms that may contribute to durable performance.</p></div></section></main></body></html>'''


def apply_theme(html: str) -> str:
    """Apply presentation changes without altering embedded scripts or payloads."""
    scripts_before = script_blocks(html)
    html = re.sub(r"@import\s+url\([^)]*fonts\.googleapis\.com[^)]*\)\s*;", "", html, flags=re.I)
    html = re.sub(r'<style id="blue-oxblood-theme">.*?</style>', "", html,
                  flags=re.I | re.S)
    html = html.replace("</head>", f"<style id=\"blue-oxblood-theme\">{theme_css()}</style></head>", 1)
    html = html.replace("<body>", '<body data-site-theme="blue-oxblood">', 1)
    # The former standalone caucus page is now a compatibility route. Keep one
    # canonical navigation entry across every public page.
    html = re.sub(r'<a href="caucuses\.html"[^>]*>Caucuses</a>', "", html)
    if not re.search(r'<a href="ideology-performance\.html"', html):
        html = re.sub(
            r'(<a href="cmo\.html"[^>]*>.*?</a>)',
            r'\1<a href="ideology-performance.html">Ideology &amp; caucuses</a>',
            html,
            count=1,
            flags=re.S,
        )
    html = re.sub(
        r'(<a href="ideology-performance\.html"[^>]*>).*?(</a>)',
        r"\1Ideology &amp; caucuses\2",
        html,
        flags=re.S,
    )
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
    html = normalize_header(html)
    html = normalize_main(html)
    html = normalize_method_toc(html)
    html = normalize_footer(html)
    if script_blocks(html) != scripts_before:
        raise AssertionError("Branding transformation altered embedded JavaScript or data payloads")
    return html
