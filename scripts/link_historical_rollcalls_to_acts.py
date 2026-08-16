"""Link historical journal roll calls to enacted Acts without overstating motions."""
from __future__ import annotations

from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "legislative"


def normalized_measure(value: object) -> str | None:
    if pd.isna(value):
        return None
    return {"H": "HB", "S": "SB"}.get(str(value).upper(), str(value).upper())


def build_links(rollcalls: pd.DataFrame, acts: pd.DataFrame) -> pd.DataFrame:
    rc = rollcalls.copy()
    ac = acts.copy()
    rc["measure_type_norm"] = rc.bill_type.map(normalized_measure)
    ac["measure_type_norm"] = ac.measure_type.map(normalized_measure)
    ac = ac[ac.act_year.eq(1998) & ac.measure_number.notna()].copy()
    candidates = rc.merge(
        ac[["act_id", "act_year", "act_number", "act_citation", "measure_type_norm", "measure_number", "title"]],
        left_on=["session_year", "measure_type_norm", "bill_number"],
        right_on=["act_year", "measure_type_norm", "measure_number"],
        how="left",
    )
    counts = candidates.groupby("rollcall_id").act_id.transform(lambda x: x.notna().sum())
    candidates["act_match_count"] = counts
    candidates["act_link_status"] = counts.map({0: "no_act_match", 1: "unique_act_match"}).fillna("ambiguous_act_match")
    candidates["analytical_eligibility"] = candidates.count_valid & candidates.act_link_status.eq("unique_act_match")
    columns = [
        "rollcall_id", "session", "session_year", "bill_type", "bill_number", "motion_type", "count_valid",
        "act_id", "act_citation", "act_number", "title", "act_match_count", "act_link_status",
        "analytical_eligibility",
    ]
    return candidates[columns]


def main() -> None:
    acts = pd.read_csv(DATA / "historical_alabama_acts.csv")
    for chamber in ("house", "senate"):
        path = DATA / f"historical_{chamber}_journal_rollcalls.csv"
        if not path.exists():
            continue
        rollcalls = pd.read_csv(path)
        links = build_links(rollcalls, acts)
        links.to_csv(DATA / f"historical_{chamber}_rollcall_act_links.csv", index=False)
        qa = (links.groupby(["session_year", "act_link_status"], as_index=False)
              .agg(rows=("rollcall_id", "size"), unique_rollcalls=("rollcall_id", "nunique"),
                   count_valid=("count_valid", "sum"), analytical_eligible=("analytical_eligibility", "sum")))
        qa.to_csv(DATA / f"historical_{chamber}_rollcall_act_link_qa.csv", index=False)
        print(f"\n{chamber.upper()}")
        print(qa.to_string(index=False))


if __name__ == "__main__":
    main()
