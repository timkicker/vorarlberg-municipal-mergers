"""Statutory floor and ceiling of mayors' monthly pay per cut (Vorarlberg, LGBl.Nr. 54/2011 § 1).

Amounts as of 2011, not indexed. Run from the repository root.
Writes data/derived/mayor_pay.txt.
"""

import collections
import csv
import sys

import fag

CUTS = ("Status quo", "Threshold 2000", "Threshold 3500", "Threshold 5000", "official planning region")
FLOOR = ((500, 1653.29), (1000, 1806.67), (1500, 1968.62), (2000, 2156.13), (3000, 2292.46),
         (5000, 2445.88), (7000, 2965.74), (10000, 3357.78), (15000, 3766.78), (float("inf"), 4388.90))
CEIL = ((1000, 5113.35), (5000, 7243.85), (10000, 9800.53), (20000, 11931.11))


def band(p: float, table) -> float | None:
    for lim, v in table:
        if p <= lim:
            return v
    return None


def main() -> None:
    pop = {r["gkz"]: float(r["population"]) for r in csv.DictReader(open(fag.DER / "administration_2016_2019.csv", encoding="utf-8")) if r["gkz"].startswith("8")}
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    out = ["Range of mayors' pay per partition (mayor_pay.py)",
           "Source: ordinance LGBl.Nr. 54/2011 § 1(1) and (2), amounts as of 2011, without the overnight stay supplement", "",
           "Partition | mayors | sum of floors per month | change | sum of ceilings (units up to 20,000) | units over 20,000"]
    base = None
    for cut in CUTS:
        units = collections.defaultdict(float)
        for r in rows:
            units[r[cut]] += pop[r["gkz"]]
        lo = sum(band(p, FLOOR) for p in units.values())
        hi = [band(p, CEIL) for p in units.values()]
        base = base or lo
        out.append(f"  {cut} | {len(units)} | {lo:,.0f} | {lo / base - 1:+.1%} | {sum(h for h in hi if h):,.0f} | {sum(1 for h in hi if h is None)}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "mayor_pay.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
