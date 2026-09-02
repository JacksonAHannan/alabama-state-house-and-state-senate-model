from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def test_geometry_manifest_is_complete_and_hashed() -> None:
    manifest = pd.read_csv(
        ROOT / "data/processed/source_audits/southern_legislative_geography_manifest.csv"
    )
    assert len(manifest) == 90
    assert not manifest.duplicated(["state_code", "cycle", "chamber"]).any()
    assert set(manifest.state_code) == {
        "AL", "AR", "FL", "GA", "KY", "LA", "MO", "MS", "NC", "OK", "SC", "TN", "TX", "VA"
    }
    for row in manifest.itertuples(index=False):
        path = ROOT / row.local_path
        assert path.exists()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row.sha256


def test_map_payload_contains_every_slice_outline_and_scored_race() -> None:
    payload = json.loads((DOCS / "data/southern_war_map_payload.json").read_text(encoding="utf-8"))
    assert payload["diagnostics"] == {
        "scheduledSlices": 90,
        "geometryFeatures": 7518,
        "scoredRaces": 3418,
        "candidateRows": 6836,
        "financeCompleteRaces": 2917,
    }
    assert len(payload["slices"]) == 90
    assert payload["slices"]["AL-2022-lower"]["districts"] == 105
    assert len(payload["slices"]["AL-2022-lower"]["races"]) == 25
    assert len(payload["slices"]["VA-2017-lower"]["races"]) == 0
    assert payload["slices"]["MO-2022-lower"]["coverage"]["financeComplete"] == 0
    names = payload["slices"]["AL-2022-lower"]["races"]
    assert names["12"]["demCandidate"] == "James C. Fields, Jr."
    assert names["27"]["demCandidate"] == "Herb Neu"
    assert names["47"]["demCandidate"] == "Christian Coleman"


def test_public_map_explains_missingness_backcast_and_finance() -> None:
    page = (DOCS / "southern-war.html").read_text(encoding="utf-8")
    method = (DOCS / "southern-war-methodology.html").read_text(encoding="utf-8")
    assert 'aria-label="Map filters"' in page
    assert 'tabindex="0"' in page
    assert "Missing WAR is not zero" in page
    assert "Fundraising unavailable" in page
    assert "post-2016-model backcast" in page
    assert "Southern WAR methodology" in method
    assert "620 strict 2016 races" in method
    assert "Missouri has no usable finance" in method
    assert "all 90 scheduled" in method
