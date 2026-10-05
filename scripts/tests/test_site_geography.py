"""Shared map geometry: projection frame, compact SVG paths, equal-area tiles, context layer."""
import re

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

import site_geography as sg


def absolute_points(path: str) -> list[tuple[float, float]]:
    """Decode one 'Mx,yl dx,dy ...Z' ring back to absolute coordinates."""
    start, rest = re.match(r"M([-\d.]+,[-\d.]+)(?:l([^Z]*))?Z", path).groups()
    x, y = map(float, start.split(","))
    points = [(x, y)]
    for step in (rest or "").split():
        dx, dy = map(float, step.split(","))
        x, y = x + dx, y + dy
        points.append((x, y))
    return points


def test_relative_paths_decode_to_the_projected_coordinates():
    frame = sg.frame_for((0, 0, 1000, 1000))
    square = box(100, 100, 400, 300)
    decoded = absolute_points(sg.svg_path(square, frame))
    expected = [frame.xy(x, y) for x, y in square.exterior.coords]
    assert len(decoded) == len(expected)
    for (x, y), (ex, ey) in zip(decoded, expected):
        assert abs(x - ex) < 0.051 and abs(y - ey) < 0.051


def test_tile_layout_gives_every_district_one_unique_cell_inside_the_view():
    frame = sg.frame_for((0, 0, 1000, 1000))
    outline = box(0, 0, 1000, 1000)
    points = {i: Point(50 + (i % 10) * 95, 50 + (i // 10) * 95) for i in range(60)}
    layout = sg.tile_layout(points, outline, frame)
    tiles = layout["tiles"]
    assert set(tiles) == set(points)
    assert len({tuple(xy) for xy in tiles.values()}) == len(points)
    half = layout["size"] / 2
    for x, y in tiles.values():
        assert frame.pad - 0.2 <= x - half and x + half <= frame.width - frame.pad + 0.2
        assert frame.pad - 0.2 <= y - half and y + half <= frame.height - frame.pad + 0.2
    assert sg.tile_layout(points, outline, frame) == layout  # deterministic


def test_tiles_keep_west_east_order_for_separated_districts():
    frame = sg.frame_for((0, 0, 1000, 1000))
    points = {"west": Point(100, 500), "east": Point(900, 500)}
    tiles = sg.tile_layout(points, box(0, 0, 1000, 1000), frame)["tiles"]
    assert tiles["west"][0] < tiles["east"][0]


@pytest.mark.skipif(not sg.COUNTIES.exists(), reason="context layer not built")
def test_alabama_context_layer_is_complete_and_shares_one_frame():
    counties = gpd.read_file(sg.COUNTIES)
    assert len(counties) == 67
    frame = sg.alabama_frame()
    context = sg.alabama_context(frame)
    assert context["counties"].count("M") >= 67
    assert {c["name"] for c in context["cities"]} == set(sg.CITY_LABELS)
    assert {m["name"] for m in context["metros"]} == set(sg.METROS)
    for city in context["cities"]:
        assert 0 <= city["x"] <= sg.VIEW_WIDTH and 0 <= city["y"] <= sg.VIEW_HEIGHT


@pytest.mark.skipif(not sg.CITIES.exists(), reason="context layer not built")
def test_metro_members_only_lists_districts_inside_each_preset():
    areas = sg.metro_areas()
    inside = areas["Birmingham"].centroid
    members = sg.metro_members({"in": inside, "out": Point(0, 0)})
    birmingham = next(m for m in members if m["name"] == "Birmingham")
    assert birmingham["members"] == ["in"]
