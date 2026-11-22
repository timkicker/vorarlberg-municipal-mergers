"""Council seats under § 34 GG (Vorarlberg municipal act) for each set of merged units.

Writes data/derived/council_seats.txt.
"""

import collections
import csv
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fag  # noqa: E402

STEPS = [(500, 9), (1000, 12), (1500, 15), (2000, 18), (2500, 21), (5000, 24), (8000, 27), (11000, 30), (15000, 33)]


def seats(n: float) -> int:
    for top, k in STEPS:
        if n <= top:
            return k
    return 36


def main() -> None:
    pop = fag.load_pop()
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv")))
    total = sum(pop[r["gkz"]] for r in rows)
    out = ["Seats in the municipal council under § 34 GG per partition (council_seats.py)", "",
           "partition | units (= mayors) | seats | inhabitants per seat median | statewide | "
           "predecessors with less than 1 seat under allocation by head count"]
    for cut in ["Status quo"] + fag.CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        m = 0
        ratios, thin = [], 0
        for g in units.values():
            n = sum(pop[x] for x in g)
            k = seats(n)
            m += k
            ratios.append(n / k)
            if len(g) > 1:
                thin += sum(1 for x in g if k * pop[x] / n < 1)
        out.append(f"{cut} | {len(units)} | {m} | {statistics.median(ratios):.0f} | {total / m:.0f} | {thin}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "council_seats.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
