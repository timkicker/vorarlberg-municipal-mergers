"""Duties tied to a population threshold: proactive publication (IFG § 4, 5,000) and Court of Audit (B-VG Art. 127a, 10,000).

Run from the repository root. Writes data/derived/size_duties.txt.
"""

import collections
import csv
import sys

import fag

LIMITS = (5000, 10000)


def row(name, sizes, total):
    out = [name, str(len(sizes))]
    for lim in LIMITS:
        big = [s for s in sizes if s >= lim]
        out.append(f"{len(big)} | {sum(big) / total:.0%}")
    return " | ".join(out)


def main() -> None:
    pop = fag.load_pop()
    vbg = {g: n for g, n in pop.items() if g.startswith("8")}
    total = sum(vbg.values())
    units = collections.defaultdict(list)
    for r in csv.DictReader(open(fag.DER / "fag_units.csv", encoding="utf-8")):
        units[r["partition"]].append(int(r["pop"]))
    lines = ["Duties at population thresholds (size_duties.py)", ""]
    lines.append("partition | units | from 5,000 units | share of population | from 10,000 units | share of population")
    lines.append("  " + row("Status quo", list(vbg.values()), total))
    for cut, sizes in units.items():
        if sum(sizes) != total:
            lines.append(f"  {cut}: population {sum(sizes):,} instead of {total:,}, left out")
            continue
        lines.append("  " + row(cut, sizes, total))
    text = "\n".join(lines)
    print(text)
    (fag.DER / "size_duties.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
