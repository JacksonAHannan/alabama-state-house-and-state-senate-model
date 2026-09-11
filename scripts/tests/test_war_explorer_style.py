"""Characterize Alabama's page before sharing its presentation with the South."""
import hashlib

import build_war_story_page as story


def test_alabama_template_is_unchanged(monkeypatch):
    monkeypatch.setattr(story, "build_validation_panel_v6", lambda: "validation")
    monkeypatch.setattr(story, "build_attribution_panel", lambda: "attribution")
    assert hashlib.sha256(story.build_page({}).encode()).hexdigest() == (
        "a9f25a88f143ca2feae46be3d8a2e4ec1e11ec197fc539a07a23527c2bc7dc36"
    )
