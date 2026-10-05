"""Shared map geometry for the public pages.

Every district map on the site is drawn as inline SVG from geometry projected
into one equal-area projection (EPSG:5070), so a district's drawn area is
proportional to its land area and the three products read alike. This module
owns that projection, the SVG path encoding, the equal-area tile layouts used
by the "Tiles" view, and the Alabama context layer (county lines, city labels,
metro zoom presets).

The context layer is a derived display asset built by ``main()`` from two
registered Census files. It is never an analytical input.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
import shapely

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "site_geography"
CRS = "EPSG:5070"
VIEW_WIDTH, VIEW_HEIGHT, VIEW_PAD = 640, 700, 12

VTD_SOURCE = ROOT / "data" / "raw" / "alabama_elections_and_geography" / "tl_2012_01_vtd10.zip"
PLACE_SOURCE = ROOT / "data" / "raw" / "census" / "tl_2024_01_place.zip"
COUNTIES = OUT / "alabama_counties.geojson"
CITIES = OUT / "alabama_cities.csv"
MANIFEST = OUT / "manifest.json"
# Labelled cities: the state's four metro cores plus regional centers, chosen
# for orientation only. Metro presets also define the map's zoom shortcuts.
CITY_LABELS = (
    "Huntsville", "Florence", "Decatur", "Gadsden", "Birmingham",
    "Tuscaloosa", "Montgomery", "Auburn", "Dothan", "Mobile",
)
METROS = ("Birmingham", "Huntsville", "Montgomery", "Mobile")
METRO_BUFFER_METERS = 14_000
COUNTY_SIMPLIFY_METERS = 250


@dataclass(frozen=True)
class Frame:
    """Affine map from projected metres to SVG user units (y grows downward)."""

    minx: float
    miny: float
    maxx: float
    maxy: float
    width: float = VIEW_WIDTH
    height: float = VIEW_HEIGHT
    pad: float = VIEW_PAD

    @property
    def scale(self) -> float:
        return min((self.width - 2 * self.pad) / (self.maxx - self.minx),
                   (self.height - 2 * self.pad) / (self.maxy - self.miny))

    @property
    def offset(self) -> tuple[float, float]:
        return ((self.width - (self.maxx - self.minx) * self.scale) / 2,
                (self.height - (self.maxy - self.miny) * self.scale) / 2)

    def xy(self, x: float, y: float) -> tuple[float, float]:
        ox, oy = self.offset
        return ox + (x - self.minx) * self.scale, self.height - (oy + (y - self.miny) * self.scale)

    def box(self, minx: float, miny: float, maxx: float, maxy: float) -> list[float]:
        """An [x, y, width, height] SVG box for projected bounds."""
        x0, y1 = self.xy(minx, miny)
        x1, y0 = self.xy(maxx, maxy)
        return [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)]


def projected(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if frame.crs is None:
        raise ValueError("Map geometry has no coordinate reference system")
    result = frame.to_crs(CRS)
    result["geometry"] = result.geometry.make_valid()
    return result


def frame_for(bounds) -> Frame:
    minx, miny, maxx, maxy = (float(v) for v in bounds)
    return Frame(minx, miny, maxx, maxy)


def _polygons(geom):
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if hasattr(geom, "geoms"):
        return [part for item in geom.geoms for part in _polygons(item)]
    return []


def svg_path(geom, frame: Frame) -> str:
    """Encode polygon rings as an SVG path in the frame's user units."""

    def ring(coords) -> str:
        # Relative moves between points rounded to 0.1 units: compact, with no drift.
        points = [(round(x * 10), round(y * 10)) for x, y in (frame.xy(x, y) for x, y, *_ in coords)]
        steps = [f"{(x1 - x0) / 10:g},{(y1 - y0) / 10:g}" for (x0, y0), (x1, y1) in zip(points, points[1:])
                 if (x1, y1) != (x0, y0)]
        x0, y0 = points[0]
        return f"M{x0 / 10:g},{y0 / 10:g}" + ("l" + " ".join(steps) if steps else "") + "Z"

    return "".join(
        ring(polygon.exterior.coords) + "".join(ring(hole.coords) for hole in polygon.interiors)
        for polygon in _polygons(geom)
    )


def label_point(geom, frame: Frame) -> list[float]:
    point = geom.representative_point()
    x, y = frame.xy(point.x, point.y)
    return [round(x, 1), round(y, 1)]


def tile_layout(points: dict, outline, frame: Frame, *, fill: float = 1.06, spread: float = 0.3) -> dict:
    """Assign each district one equal-size square tile near its geographic position.

    Districts hold roughly equal populations, so equal tiles are the population
    view of the map. Representative points are first spread toward a rank-uniform
    layout (``spread``) so dense metros open up, then assigned to grid cells
    inside the state outline by minimum total squared distance. The layout is
    deterministic. Tile adjacency approximates geography; it does not certify it.
    """
    ids = list(points)
    if not ids:
        return {"size": 0.0, "tiles": {}}
    coords = np.array([[points[i].x, points[i].y] for i in ids], dtype=float)
    minx, miny, maxx, maxy = outline.bounds
    ranks = np.argsort(np.argsort(coords, axis=0), axis=0) / max(len(ids) - 1, 1)
    uniform = np.column_stack([minx + ranks[:, 0] * (maxx - minx), miny + ranks[:, 1] * (maxy - miny)])
    targets = (1 - spread) * coords + spread * uniform

    def cells(step: float) -> np.ndarray:
        xs, ys = np.meshgrid(np.arange(minx + step / 2, maxx, step), np.arange(miny + step / 2, maxy, step))
        grid = np.column_stack([xs.ravel(), ys.ravel()])
        if not len(grid):
            return grid
        return grid[shapely.contains_xy(outline.buffer(step * 0.35), grid[:, 0], grid[:, 1])]

    low, high = 1.0, max(maxx - minx, maxy - miny)
    for _ in range(40):
        step = (low + high) / 2
        if len(cells(step)) >= fill * len(ids):
            low = step
        else:
            high = step
    step = low
    grid = cells(step)
    cost = ((targets[:, None, :] - grid[None, :, :]) ** 2).sum(axis=2)
    rows, columns = linear_sum_assignment(cost)
    centers = np.array([frame.xy(*grid[column]) for column in columns])
    size = step * frame.scale
    # Fit the occupied grid, tile edges included, inside the padded view box.
    low_corner = centers.min(axis=0) - size / 2
    high_corner = centers.max(axis=0) + size / 2
    available = np.array([frame.width - 2 * frame.pad, frame.height - 2 * frame.pad])
    fit = min(1.0, float((available / (high_corner - low_corner)).min()))
    middle = (low_corner + high_corner) / 2
    view_middle = np.array([frame.width / 2, frame.height / 2])
    centers = view_middle + (centers - middle) * fit
    tiles = {ids[row]: [round(float(x), 1), round(float(y), 1)] for row, (x, y) in zip(rows, centers)}
    return {"size": round(size * fit, 2), "tiles": tiles}


def district_geometry(frame_gdf: gpd.GeoDataFrame, key: str, *, simplify: float | None = None,
                      frame: Frame | None = None, metros: bool = False) -> dict:
    """SVG paths, label points and equal-area tiles for one district map.

    ``frame_gdf`` must carry a ``key`` column of district identifiers. Geometry
    is projected to EPSG:5070 and optionally simplified in metres. Pass a shared
    ``frame`` (for Alabama, ``alabama_frame()``) so several maps and one context
    layer line up; otherwise the frame fits this map's bounds. ``metros`` adds the
    districts inside each Alabama metro preset for the tile view.
    """
    gdf = projected(frame_gdf)
    if simplify:
        simplified = gdf.geometry.simplify(simplify, preserve_topology=True)
        gdf["geometry"] = simplified.where(simplified.is_valid & ~simplified.is_empty, gdf.geometry)
    frame = frame or frame_for(gdf.total_bounds)
    outline = gdf.geometry.union_all()
    points = {row[key]: row.geometry.representative_point() for _, row in gdf.iterrows()}
    layout = tile_layout(points, outline, frame)
    drawn = {
        "viewBox": [0, 0, VIEW_WIDTH, VIEW_HEIGHT],
        "outline": svg_path(outline, frame),
        "districts": {row[key]: {"path": svg_path(row.geometry, frame), "label": label_point(row.geometry, frame)}
                      for _, row in gdf.iterrows()},
        "tileSize": layout["size"],
        "tiles": layout["tiles"],
    }
    if metros:
        drawn["metroMembers"] = metro_members(points)
    return drawn


def metro_areas() -> dict:
    """Projected zoom-preset areas for the Alabama metros."""
    table = pd.read_csv(CITIES)
    return {row.name: gpd.GeoSeries.from_wkt([row.metro_area_wkt], crs=CRS).iloc[0]
            for row in table.itertuples() if row.metro}


def metro_members(points: dict) -> list[dict]:
    """Districts whose representative point lies inside each metro preset, for the tile view."""
    return [{"name": name, "members": [str(i) for i in sorted(points) if area.contains(points[i])]}
            for name, area in metro_areas().items()]


def alabama_frame() -> Frame:
    """One statewide frame shared by every Alabama map and its context layer."""
    return frame_for(gpd.read_file(COUNTIES).to_crs(CRS).total_bounds)


def alabama_context(frame: Frame) -> dict:
    """County lines, city labels and metro zoom presets drawn in ``frame``."""
    if not (COUNTIES.exists() and CITIES.exists()):
        raise FileNotFoundError("Run scripts/site_geography.py to build the Alabama context layer")
    counties = gpd.read_file(COUNTIES).to_crs(CRS)
    table = pd.read_csv(CITIES)
    return {
        "counties": "".join(svg_path(geom, frame) for geom in counties.geometry),
        "cities": [{"name": row.name, "x": round(frame.xy(row.x, row.y)[0], 1),
                    "y": round(frame.xy(row.x, row.y)[1], 1)} for row in table.itertuples()],
        "metros": [{"name": name, "box": frame.box(*area.bounds)} for name, area in metro_areas().items()],
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    """Build the Alabama context layer from registered Census geometry."""
    OUT.mkdir(parents=True, exist_ok=True)
    vtds = gpd.read_file(f"zip://{VTD_SOURCE.as_posix()}")[["COUNTYFP10", "geometry"]]
    counties = vtds.dissolve("COUNTYFP10").reset_index().to_crs(CRS)
    counties["geometry"] = counties.geometry.make_valid().simplify(COUNTY_SIMPLIFY_METERS, preserve_topology=True)
    if len(counties) != 67:
        raise RuntimeError(f"Expected 67 Alabama counties, found {len(counties)}")
    counties.rename(columns={"COUNTYFP10": "county_fips"}).to_file(COUNTIES, driver="GeoJSON")

    places = gpd.read_file(f"zip://{PLACE_SOURCE.as_posix()}").to_crs(CRS)
    places = places[places.NAME.isin(CITY_LABELS) & places.LSAD.eq("25")]
    if sorted(places.NAME) != sorted(CITY_LABELS):
        raise RuntimeError(f"City label places not found uniquely: {sorted(places.NAME)}")
    rows = []
    for name in CITY_LABELS:
        place = places[places.NAME.eq(name)].iloc[0]
        point = place.geometry.representative_point()
        metro = name in METROS
        area = place.geometry.envelope.buffer(METRO_BUFFER_METERS).envelope if metro else None
        rows.append({"name": name, "geoid": place.GEOID, "x": round(point.x, 1), "y": round(point.y, 1),
                     "metro": metro, "metro_area_wkt": area.wkt if area is not None else ""})
    pd.DataFrame(rows).to_csv(CITIES, index=False)
    manifest = {
        "schema_version": 1,
        "purpose": "Display-only context layer for the public district maps; not an analytical input.",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "projection": CRS,
        "method": {
            "counties": ("2010 Census voting districts dissolved by county FIPS (Alabama county lines are "
                         f"unchanged since), simplified at {COUNTY_SIMPLIFY_METERS} m"),
            "cities": "Representative points of the named 2024 Census incorporated places (LSAD 25)",
            "metro_presets": (f"Envelope of the named city's 2024 place geometry buffered by "
                              f"{METRO_BUFFER_METERS:,} m; a zoom shortcut, not a metro definition"),
        },
        "sources": [
            {"path": str(VTD_SOURCE.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(VTD_SOURCE),
             "registry": "project_docs/audits/SOURCE_TERMS_AND_HYGIENE_2026_09_11.md (derived map output only)"},
            {"path": str(PLACE_SOURCE.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(PLACE_SOURCE),
             "registry": "SOURCE-REGIONS-001"},
        ],
        "outputs": [
            {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)}
            for path in (COUNTIES, CITIES)
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(counties)} counties and {len(rows)} city labels to {OUT}")


if __name__ == "__main__":
    main()
