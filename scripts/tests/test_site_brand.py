from __future__ import annotations

from scripts.site_brand import apply_theme, script_blocks, theme_css


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
