"""Write normalized official Alabama SOS precinct results."""
import argparse
from pathlib import Path
from sos_precinct import YEAR_SOURCES, load_sos_year

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--years", type=int, nargs="+", default=sorted(YEAR_SOURCES)); args = parser.parse_args()
    output = args.root / "data" / "raw" / "sos_normalized"; output.mkdir(parents=True, exist_ok=True)
    for year in args.years:
        data = load_sos_year(args.root, year); path = output / f"{year}_general_precinct.csv"
        data.to_csv(path, index=False); print(f"{year}: {data.county_key.nunique()} counties, {len(data):,} rows")
if __name__ == "__main__": main()
