"""Merged units that cross political district or court district boundaries.

Writes data/derived/boundaries.txt.
"""

import collections
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW, DER = ROOT / "data" / "raw", ROOT / "data" / "derived"
# columns of vbg_court_districts.csv
COL_MUNICIPALITY = "gemeinde"  # municipality name
COL_COURT = "bezirksgericht"  # district court
DISTRICT_PREFIX = "Bezirk "  # prefix of the district names in the column "official district"


def main() -> None:
    pz = list(csv.DictReader(open(DER / "pareto_partitions.csv")))
    district = {r["municipality"]: r["official district"] for r in pz}
    court = {}
    for r in csv.DictReader(open(RAW / "vbg_court_districts.csv")):
        if r[COL_MUNICIPALITY] in court:
            raise SystemExit(f"duplicate: {r[COL_MUNICIPALITY]}")
        court[r[COL_MUNICIPALITY]] = r[COL_COURT]
    if set(court) != set(district) or len(court) != 96:
        raise SystemExit("court list does not cover exactly the 96 municipalities")
    units = collections.defaultdict(list)
    for r in csv.DictReader(open(DER / "fag_units.csv")):
        gs = r["members"].split(";")
        if len(gs) > 1:
            units[r["partition"]].append((r["unit"], gs, int(r["pop"])))
    lines = ["Units across district and court district boundaries (boundaries.py)", "",
             "partition | merged units | inhabitants in them | across a district boundary (units, inhabitants, share of inhabitants) | across a court district boundary (units, inhabitants, share of inhabitants)"]
    detail = []
    for cut, us in units.items():
        inh = sum(e for _, _, e in us)
        nb = eb = nc = ec = 0
        for name, gs, e in us:
            b = sorted({district[g] for g in gs})
            c = sorted({court[g] for g in gs})
            if len(b) > 1:
                nb += 1
                eb += e
            if len(c) > 1:
                nc += 1
                ec += e
            if len(b) > 1 or len(c) > 1:
                parts = []
                for g in gs:
                    parts.append(f"{g} ({district[g].replace(DISTRICT_PREFIX, '')}, court {court[g]})")
                detail.append(f"  {cut} | {name} | {e:,} inhabitants | districts {len(b)}, courts {len(c)} | " + "; ".join(parts))
        lines.append(f"{cut} | {len(us)} | {inh:,} | {nb}, {eb:,}, {eb / inh:.0%} | {nc}, {ec:,}, {ec / inh:.0%}")
    lines += ["", "units across boundaries:"] + detail
    text = "\n".join(lines)
    print(text)
    (DER / "boundaries.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
