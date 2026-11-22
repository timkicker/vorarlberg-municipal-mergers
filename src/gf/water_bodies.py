"""Water and sewage cooperations of 2016 (type W) against the merger cuts.

Run from the repository root.
Writes data/derived/water_bodies.txt.
"""

import collections
import csv
import json
import sys

import fag

CLASSES = ((0, 1000), (1000, 2000), (2000, 5000), (5000, 10000), (10000, float("inf")))


def main() -> None:
    coops = [c for c in json.loads((fag.DER / "coop2016.json").read_text(encoding="utf-8")) if c["type"] == "W"]
    names = {r["municipality"]: r["gkz"] for r in csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8"))}
    pop = fag.load_pop()
    units = collections.defaultdict(dict)
    for r in csv.DictReader(open(fag.DER / "fag_units.csv", encoding="utf-8")):
        for m in r["members"].split(";"):
            units[r["partition"]][m] = r["unit"]
    lines = ["Water associations 2016 (type W) against the partitions (water_bodies.py)", ""]
    sizes = [len(c["members"]) for c in coops]
    lines.append(f"cooperations {len(coops)}, members per cooperation median {sorted(sizes)[len(sizes) // 2]}, range {min(sizes)} to {max(sizes)}")
    lines.append("")
    lines.append("Partition | units | cooperations entirely inside one unit | share")
    for cut, m in units.items():
        missing = {g for c in coops for g in c["members"] if g not in m}
        inside = sum(len({m[g] for g in c["members"] if g in m}) == 1 for c in coops)
        note = f" (not assigned: {', '.join(sorted(missing))})" if missing else ""
        lines.append(f"  {cut} | {len(set(m.values()))} | {inside} | {inside / len(coops):.0%}{note}")
    lines.append("")
    member = {g for c in coops for g in c["members"]}
    lines.append("Municipalities in at least one W cooperation, by population 1.1.2024")
    for lo, hi in CLASSES:
        g = [n for n, k in names.items() if lo <= pop[k] < hi]
        inn = sum(n in member for n in g)
        name = f"from {lo:,}" if hi == float("inf") else f"{lo:,} to under {hi:,}"
        lines.append(f"  {name} | {len(g)} | {inn} | {inn / len(g):.0%}")
    lines.append(f"  all | {len(names)} | {sum(n in member for n in names)} | {sum(n in member for n in names) / len(names):.0%}")
    text = "\n".join(lines)
    print(text)
    (fag.DER / "water_bodies.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
