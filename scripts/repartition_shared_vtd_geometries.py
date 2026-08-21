"""Rebuild donor clips and partition VTDs shared by multiple precincts."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely import make_valid

from audit_historical_precinct_geography import OUT, donor_vtds, partition_shared_vtds, plans


def main() -> None:
    donors = donor_vtds().to_crs(5070)
    donors["geometry"] = donors.geometry.map(make_valid)
    donor_lookup = donors.set_index("donor_vtd_id").geometry
    for cycle in (1994, 1998, 2002, 2006):
        for chamber in ("house", "senate"):
            path = OUT / f"approximate_{cycle}_{chamber}_precincts.gpkg"
            data = gpd.read_file(path)
            plan_path, column = plans(cycle)[chamber]
            districts = gpd.read_file(plan_path).to_crs(5070)
            source_column = column if column in districts else "DISTRICT"
            districts["district"] = pd.to_numeric(districts[source_column], errors="raise").astype(int)
            districts["geometry"] = districts.geometry.map(make_valid)
            district_lookup = districts.set_index("district").geometry
            geometries = []
            for row in data.itertuples(index=False):
                if pd.isna(row.donor_vtd_id): geometries.append(None); continue
                geometries.append(make_valid(donor_lookup[row.donor_vtd_id].intersection(
                    district_lookup[int(row.district)])))
            data = gpd.GeoDataFrame(data.drop(columns="geometry"), geometry=geometries, crs=5070)
            data = partition_shared_vtds(data)
            data.to_file(path, layer=f"{cycle}_{chamber}", driver="GPKG")
            print(cycle, chamber, data.vtd_partition_method.value_counts().to_dict(), flush=True)


if __name__ == "__main__":
    main()
