from __future__ import annotations

from scripts.site_brand import apply_theme, methods_landing, script_blocks, theme_css


def test_theme_embeds_portrait_and_uses_conventional_fonts() -> None:
    css = theme_css()
    assert "data:image/jpeg;base64," in css
    assert "Arial,Helvetica,sans-serif" in css
    assert "Georgia,'Times New Roman',serif" in css
    assert "Consolas,'Courier New',monospace" in css
    assert "fonts.googleapis.com" not in css


def test_transform_preserves_scripts_and_adds_brand_contract() -> None:
    source = """<!doctype html><html><head><style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Libre+Franklin');:root{--ink:#000}</style></head><body><header><div class='brand'>Jackson Hannan</div><nav><a href='index.html'>Forecast</a></nav></header><script>const DATA={x:1};</script></body></html>"""
    result = apply_theme(source)
    assert script_blocks(result) == script_blocks(source)
    assert 'data-site-theme="blue-oxblood"' in result
    assert 'id="blue-oxblood-theme"' in result
    assert "@electionsjack" in result
    assert "fonts.googleapis.com" not in result
    assert result.count(":root{--ink:#000}") == 1


def test_transform_uses_utilitarian_atlas_copy() -> None:
    result = apply_theme("<html><head></head><body><nav></nav><h1>What did Alabama's standout Democrats stand for?</h1><script>1</script></body></html>")
    assert "Alabama Legislator Issue Atlas" in result
    assert "What did Alabama's standout Democrats stand for?" not in result


def test_transform_uses_one_shared_header_and_preserves_active_route() -> None:
    source = '''<html><head></head><body><header><div class="brand">Old</div><nav>
    <a href="index.html">Forecast</a><a href="cmo.html" aria-current="page">CMO</a>
    <a href="legislators.html">Candidate atlas</a></nav></header><script>1</script></body></html>'''
    result = apply_theme(source)
    assert result.count('class="site-header"') == 1
    assert result.count('class="site-portrait"') == 1
    assert "Alabama legislative models" in result
    assert '<a href="cmo.html" aria-current="page">Alabama WAR</a>' in result
    assert result.count('aria-current="page"') == 1
    assert "Candidate atlas" not in result
    for label in ("Forecast", "WAR", "Ideology &amp; caucuses", "Methods",
                  "GitHub", "Instagram", "Substack", "LinkedIn", "@electionsjack"):
        assert label in result
    assert 'class="skip-link"' in result
    assert 'id="main-content"' not in result  # source fixture has no main element
    assert 'class="site-footer"' in result


def test_methodology_toc_gets_mobile_disclosure() -> None:
    source = '''<html><head></head><body><header><nav><a href="methodology.html" aria-current="page">Methodology</a></nav></header>
    <main><div class="method-grid"><aside class="toc"><b>On this page</b><a href="#one">One</a><a href="#two">Two</a></aside><article></article></div></main><script>1</script></body></html>'''
    result = apply_theme(source)
    assert 'class="mobile-toc"' in result
    assert result.count('href="#one"') == 2
    assert 'id="main-content"' in result


def test_legacy_atlas_route_marks_ideology_current() -> None:
    source = '''<html><head></head><body><header><nav>
    <a href="legislators.html" aria-current="page">Issue atlas</a>
    </nav></header><script>1</script></body></html>'''
    result = apply_theme(source)
    assert '<a href="ideology-performance.html" aria-current="page">Ideology &amp; caucuses</a>' in result
    assert "legislators.html" not in result


def test_white_interface_text_has_oxblood_backing() -> None:
    css = theme_css()
    assert "body>header,.site-head{background:var(--brand-accent)!important;color:#fff!important" in css
    assert "align-items:center;color:#fff!important" in css
    assert "header a{color:#f5e9e8!important" in css
    assert "button[aria-selected=true] *{color:inherit!important}" in css
    assert ".controls button.active,.map-modes button.active,.baseline-tabs button.active{background:var(--brand-accent)!important" in css
    assert ".racebox-head,.baseline-wikibox-head{background:var(--brand-accent)!important;color:#fff!important" in css
    assert ".racebox-sub{background:#f5e9e8!important;color:var(--brand-ink)!important}" in css
    assert ".badge.supported{color:#285642!important}" in css
    assert ".cell .n{color:var(--brand-ink)!important;background:var(--brand-panel-strong)!important" in css


def test_methods_landing_uses_public_war_name() -> None:
    html = methods_landing()
    assert "Alabama WAR" in html
    assert "race residual" in html
    assert "WAR comparisons" in html
    assert "<h2>Alabama WAR methodology</h2>" in html
    assert "Read WAR methods" in html
    assert "<h2>CMO methodology</h2>" not in html
    assert "Candidate Quality Index" not in html
    assert "CQI" not in html
