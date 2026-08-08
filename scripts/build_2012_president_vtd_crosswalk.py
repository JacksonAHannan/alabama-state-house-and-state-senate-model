"""Match normalized 2012 presidential precinct returns to 2010 Census VTDs."""

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_2014_precinct_crosswalk import (  # noqa: E402
    NON_GEOGRAPHIC_RE, build_crosswalk, normalize_for_match, normalize_name,
    read_vtds,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = pd.read_csv(root / "data" / "processed" / "presidential" /
                         "2012_president_precinct.csv")
    units = source[["county", "precinct"]].drop_duplicates().copy()
    units["county"] = units.county.map(normalize_name)
    units["result_precinct"] = units.precinct
    units["result_precinct_norm"] = units.precinct.map(normalize_name)
    units["result_match_norm"] = units.precinct.map(normalize_for_match)
    units["source_file"] = "2012General-PrecinctLevel.zip"
    units["source_layout"] = "normalized_2012"
    units["is_non_geographic"] = units.result_precinct_norm.str.contains(NON_GEOGRAPHIC_RE)
    units = units.drop(columns="precinct").drop_duplicates(
        ["county", "result_precinct_norm"])
    units.insert(0, "result_unit_id", range(1, len(units) + 1))

    sources = root / "Results and Shapefiles"
    vtds = read_vtds(sources / "tl_2012_01_vtd10.zip",
                     sources / "al_gen_22_prec" / "al_gen_22_st_prec.shp")
    crosswalk = build_crosswalk(units, vtds)

    votes = source.copy()
    votes["county"] = votes.county.map(normalize_name)
    votes["result_precinct_norm"] = votes.precinct.map(normalize_name)
    vote_qa = votes.merge(crosswalk[["county", "result_precinct_norm", "match_method",
                                     "accepted_match", "is_non_geographic", "vtd_geoid"]],
                          on=["county", "result_precinct_norm"], how="left", validate="many_to_one")
    summary = (vote_qa.groupby("match_method", dropna=False)
               .agg(precincts=("precinct", "size"), dem_votes=("dem_votes", "sum"),
                    rep_votes=("rep_votes", "sum"), two_party_votes=("two_party_votes", "sum"))
               .reset_index())
    summary["vote_share"] = summary.two_party_votes / vote_qa.two_party_votes.sum()

    output = root / "data" / "derived" / "crosswalks"
    crosswalk.to_csv(output / "2012_president_vtd_crosswalk.csv", index=False)
    vote_qa.to_csv(output / "2012_president_vtd_vote_qa.csv", index=False)
    summary.to_csv(output / "2012_president_vtd_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Accepted geographic vote coverage: "
          f"{vote_qa.loc[vote_qa.accepted_match, 'two_party_votes'].sum() / vote_qa.two_party_votes.sum():.2%}")


if __name__ == "__main__":
    main()
