import geopandas as gpd
from shapely.geometry import box

from scripts.compare_precinct_snapshots import compare_frames, prepare


def frame(names, polygons):
    return gpd.GeoDataFrame({"county_fips":["001"]*len(names),"precinct_name":names,
      "precinct_code":names,"geometry":polygons},crs=5070)


def test_unchanged_and_rename_are_inferences_not_confirmed():
    old=frame(["A","B"],[box(0,0,1,1),box(1,0,2,1)])
    new=frame(["A","NEW B"],[box(0,0,1,1),box(1,0,2,1)])
    got=compare_frames(old,new)
    assert set(got.inferred_relationship)=={"unchanged","probable_rename_or_renumber"}
    assert got.verification_status.eq("inferred_from_snapshot_diff").all()


def test_split_and_consolidation_relationships():
    split=compare_frames(frame(["A"],[box(0,0,2,1)]),
                         frame(["A1","A2"],[box(0,0,1,1),box(1,0,2,1)]))
    assert split.inferred_relationship.eq("probable_split").all()
    merged=compare_frames(frame(["A1","A2"],[box(0,0,1,1),box(1,0,2,1)]),
                          frame(["A"],[box(0,0,2,1)]))
    assert merged.inferred_relationship.eq("probable_consolidation").all()


def test_boundary_adjustment_and_many_to_many():
    old=frame(["A","B"],[box(0,0,1,1),box(1,0,2,1)])
    adjusted=frame(["A","B"],[box(0,0,1.2,1),box(1.2,0,2,1)])
    got=compare_frames(old,adjusted)
    assert "probable_boundary_adjustment" in set(got.inferred_relationship)
