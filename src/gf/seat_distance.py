"""Road travel time to the seat for the municipalities that lose their own seat, per cut.

Run from the repository root. Writes data/derived/seat_distance.txt.
"""

import collections
import csv
import sys

import balance as bl
import fag
import numpy as np


def main() -> None:
    pop = fag.load_pop()
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    name = {r["gkz"]: r["municipality"] for r in rows}
    fz = list(csv.reader((fag.DER / "travel_time_seat.csv").open(encoding="utf-8")))
    cols = fz[0][1:]
    T = {(r[0], c): float(v) for r in fz[1:] for c, v in zip(cols, r[1:])}
    total = sum(pop[g] for g in name)
    out = ["Way to the seat for municipalities that lose the seat (seat_distance.py)",
           "Source: travel_time_seat.csv (car, road network, without congestion and winter closures), seat = largest member by fag.load_pop 2024",
           "Mittelberg: substitute value beeline x 1.5 at 40 km/h (no road into the rest of the state)", "",
           "partition | municipalities without the seat | population | median min | weighted mean min | maximum | inhabitants of Vorarlberg over 15 min | over 30 min | three farthest"]
    for cut, label in bl.NAMES.items():
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        lose = []
        for m in units.values():
            seat = max(m, key=lambda g: pop[g])
            lose += [(g, T[(g, seat)], seat) for g in m if g != seat]
        t = np.array([x for _, x, _ in lose])
        w = np.array([pop[g] for g, _, _ in lose], dtype=float)
        mb = [g for g, _, s in lose if "Mittelberg" in (name[g], name[s])]
        far = sorted(lose, key=lambda x: -x[1])[:3]
        mark = lambda g, s: name[g] + (" (substitute)" if "Mittelberg" in (name[g], name[s]) else "")  # noqa: E731
        out.append(f"{label} | {len(lose)} | {w.sum():,.0f} | {np.median(t):.1f} | {(t * w).sum() / w.sum():.1f} | {t.max():.1f} | "
                   f"{w[t > 15].sum() / total:.1%} | {w[t > 30].sum() / total:.1%} | "
                   + ", ".join(f"{mark(g, s)} {x:.1f}" for g, x, s in far)
                   + (f" | substitute values via Mittelberg: {len(mb)} municipalities, {sum(pop[g] for g in mb):,} inhabitants" if mb else ""))
    text = "\n".join(out)
    print(text)
    (fag.DER / "seat_distance.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
