"""Audit whether each 2026 forecast district is the same territory as the 2022 district.

A district may show its 2022 result on the 2026 map only if it is equivalent:
- primary: the official 2022 block assignment (Census 2022 SLD block equivalency file)
  and the 2024-election block assignment (RDH national file in the warehouse) place
  exactly the same blocks in the district; and
- display: the page's TIGER 2025 polygon overlaps the 2021 enacted-plan polygon with
  intersection-over-union of at least IOU_MIN in EPSG:5070. TIGER vintages differ from
  the enacted shapefile by boundary slivers, so exact polygon identity is not expected.

Senate 25 and 26 carry a condition: a 2025 court-ordered remedial plan redrew them; the
2021 plan was reinstated on 2026-05-29. The remedial geometry is not in the repository.
Read-only: the warehouse is opened with mode=ro.
"""
from __future__ import annotations

import gc
import hashlib
import json
import sqlite3
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data/raw/alabama_elections_and_geography"
CENSUS = ROOT / "data/raw/census"
WAREHOUSE = ROOT / "data/processed/elections/alabama_elections.sqlite"
OUT = ROOT / "data/processed/elections/alabama_2022_2026_plan_equivalence_v1"
IOU_MIN = 0.995
CONDITIONAL = {("senate", 25), ("senate", 26)}
CONDITION_NOTE = ("Conditional: a 2025 court-ordered remedial Senate plan redrew SD25 and SD26; the 2021 plan was "
                  "reinstated on 2026-05-29. Equivalence holds while the 2021 plan governs the 2026 general election.")
CHAMBERS = {
    "house": {"bef": ("sldl_2022.zip", "01_AL_SLDL22.txt", "SLDLST"), "baf_column": "lower_district",
              "page": (GEO / "tl_2025_01_sldl/tl_2025_01_sldl.shp", "SLDLST"),
              "enacted": (GEO / "al_sldl_2021_to_2023.zip", "2021 Alabama House Plan_shape file.shp", "DISTRICT")},
    "senate": {"bef": ("sldu_2022.zip", "01_AL_SLDU22.txt", "SLDUST"), "baf_column": "upper_district",
               "page": (GEO / "tl_2025_01_sldu/tl_2025_01_sldu.shp", "SLDUST"),
               "enacted": (GEO / "al_sldu_2021_to_2023.zip", "2021 Alabama Senate Plan_shape file.shp", "DISTRICT")},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def census_2022(zip_name: str, member: str, column: str) -> pd.Series:
    with zipfile.ZipFile(CENSUS / zip_name) as archive:
        table = pd.read_csv(archive.open(member), dtype=str)
    return table.set_index("GEOID")[column].astype(int)


def rdh_2024() -> pd.DataFrame:
    connection = sqlite3.connect(f"file:{WAREHOUSE.as_posix()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        return pd.read_sql(
            "select block_geoid, lower_district, upper_district from bridge_southern_block_district_assignment "
            "where state_code='AL' and source_file_id='RDH-NATIONAL-2024-SLD-BAF'", connection,
        ).set_index("block_geoid")
    finally:
        connection.close()


def block_differences(first: pd.Series, second: pd.Series) -> pd.Series:
    """Blocks in the symmetric difference of each district's block sets."""
    if not first.index.is_unique or not second.index.is_unique:
        raise ValueError("Block assignments must have one row per block")
    joined = pd.concat([first.rename("a"), second.rename("b")], axis=1, join="outer")
    if joined.isna().any().any():
        raise ValueError("Block assignment files cover different blocks")
    moved = joined[joined.a.ne(joined.b)]
    counts = pd.concat([moved.a, moved.b]).value_counts()
    districts = sorted(set(joined.a.astype(int)))
    return counts.reindex(districts, fill_value=0).astype(int)


def polygons(path: str, field: str) -> gpd.GeoSeries:
    frame = gpd.read_file(path, columns=[field]).to_crs(5070)
    frame["district"] = frame[field].astype(int)
    dissolved = frame.dissolve("district").geometry.make_valid()
    if not dissolved.index.is_unique:
        raise ValueError(f"Duplicate districts in {path}")
    return dissolved


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rdh = rdh_2024()
    rows = []
    for chamber, spec in CHAMBERS.items():
        official = census_2022(*spec["bef"])
        differences = block_differences(official, rdh[spec["baf_column"]].astype(int))
        page = polygons(*spec["page"])
        archive, member, field = spec["enacted"]
        enacted = polygons(f"/vsizip/{archive.as_posix()}/{member}", field)
        if set(page.index) != set(enacted.index) or set(page.index) != set(differences.index):
            raise ValueError(f"{chamber}: district sets differ between sources")
        for district in sorted(page.index):
            a, b = page[district], enacted[district]
            intersection, union = a.intersection(b).area, a.union(b).area
            iou = intersection / union
            blocks = int(differences[district])
            rows.append({
                "chamber": chamber, "district": int(district),
                "blocks_differ_2022_vs_2024": blocks,
                "polygon_iou_page_vs_2021_enacted": round(iou, 6),
                "polygon_sym_diff_km2": round((union - intersection) / 1e6, 4),
                "equivalent": bool(blocks == 0 and iou >= IOU_MIN),
                "condition": CONDITION_NOTE if (chamber, int(district)) in CONDITIONAL else "",
            })
        del page, enacted
        gc.collect()
    result = pd.DataFrame(rows).sort_values(["chamber", "district"])
    if result.duplicated(["chamber", "district"]).any() or len(result) != 140:
        raise ValueError("Expected exactly 105 House and 35 Senate districts")
    path = OUT / "district_equivalence.csv"
    result.to_csv(path, index=False)
    inputs = [CENSUS / "sldl_2022.zip", CENSUS / "sldu_2022.zip",
              GEO / "tl_2025_01_sldl/tl_2025_01_sldl.shp", GEO / "tl_2025_01_sldu/tl_2025_01_sldu.shp",
              GEO / "al_sldl_2021_to_2023.zip", GEO / "al_sldu_2021_to_2023.zip"]
    manifest = {
        "audit": "alabama_2022_2026_plan_equivalence_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "code_sha256": sha256(Path(__file__).resolve()),
        "rule": {"primary": "identical block sets: Census 2022 SLD BEF vs warehouse RDH-NATIONAL-2024-SLD-BAF",
                 "display": f"TIGER 2025 page polygon IoU >= {IOU_MIN} against the 2021 enacted shapefile, EPSG:5070"},
        "conditional_districts": [f"{c}-{d}" for c, d in sorted(CONDITIONAL)], "condition": CONDITION_NOTE,
        "inputs": [{"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(p)} for p in inputs]
                  + [{"table": "bridge_southern_block_district_assignment", "source_file_id": "RDH-NATIONAL-2024-SLD-BAF"}],
        "counts": {chamber: {"districts": int(len(part)), "equivalent": int(part.equivalent.sum())}
                   for chamber, part in result.groupby("chamber")},
        "output": {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "rows": int(len(result)), "sha256": sha256(path)},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"]), "min IoU", result.polygon_iou_page_vs_2021_enacted.min())


if __name__ == "__main__":
    main()
