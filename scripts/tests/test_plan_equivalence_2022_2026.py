"""The 2022-result map may only color districts whose 2026 lines are the 2022 lines."""
import json
from pathlib import Path

import pandas as pd
import pytest

import audit_2022_2026_plan_equivalence as audit
import build_2026_forecast_dashboard as dashboard
from southern_war_release_gate import ReleaseGateError, sha256

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/elections/alabama_2022_2026_plan_equivalence_v1"


def test_block_differences_count_both_districts_of_a_moved_block():
    first = pd.Series([1, 1, 2, 2], index=["a", "b", "c", "d"])
    second = pd.Series([1, 2, 2, 2], index=["a", "b", "c", "d"])
    assert audit.block_differences(first, second).to_dict() == {1: 1, 2: 1}
    assert audit.block_differences(first, first).to_dict() == {1: 0, 2: 0}


def test_block_differences_refuse_mismatched_universes():
    with pytest.raises(ValueError):
        audit.block_differences(pd.Series([1], index=["a"]), pd.Series([1], index=["b"]))


def test_audit_covers_every_district_and_describes_the_page_geometry():
    table = pd.read_csv(OUT / "district_equivalence.csv")
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert table.groupby("chamber").size().to_dict() == {"house": 105, "senate": 35}
    assert not table.duplicated(["chamber", "district"]).any()
    declared = {item["path"]: item["sha256"] for item in manifest["inputs"] if "path" in item}
    for path in dashboard.MAPS.values():
        assert declared[path.relative_to(ROOT).as_posix()] == sha256(path)
    # Equivalence needs identical block sets; the polygon check only tolerates vintage slivers.
    assert (table.equivalent == (table.blocks_differ_2022_vs_2024.eq(0)
                                 & table.polygon_iou_page_vs_2021_enacted.ge(audit.IOU_MIN))).all()
    conditional = table[table.condition.notna()]
    assert set(zip(conditional.chamber, conditional.district)) == {("senate", 25), ("senate", 26)}


def test_dashboard_refuses_an_audit_of_other_geometry(tmp_path, monkeypatch):
    for name in ("district_equivalence.csv", "manifest.json"):
        (tmp_path / name).write_bytes((OUT / name).read_bytes())
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["inputs"]:
        if item.get("path", "").endswith("tl_2025_01_sldu.shp"):
            item["sha256"] = "0" * 64
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(dashboard, "PLAN_EQUIVALENCE", tmp_path)
    with pytest.raises(ReleaseGateError, match="current map geometry"):
        dashboard.plan_equivalence()


def test_dashboard_reads_one_flag_per_district():
    flags = dashboard.plan_equivalence()
    assert len(flags) == 140
    assert flags[("senate", 25)]["planNote"] and flags[("house", 1)]["planNote"] is None
    assert all(isinstance(value["samePlan"], bool) for value in flags.values())
