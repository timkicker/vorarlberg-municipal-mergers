"""Yearly cost of one local head (GG § 27(3)) for every municipality absorbed in a merger.

Run from the repository root.
Writes data/derived/local_heads.txt.
"""

import collections
import csv
import sys

import fag

CUTS = ("Threshold 3500", "Threshold 5000")
MONTH_LOW, MONTH_HIGH, TIMES = 1213, 1630, 14
RATES = {"lower version (half the Feldkirch minimum rate)": MONTH_LOW * TIMES / 2,
         "Feldkirch minimum rate": MONTH_LOW * TIMES,
         "Feldkirch maximum rate": MONTH_HIGH * TIMES}


def organ_savings() -> dict:
    """Elected bodies, lower end (cautious factor) and upper end, read from savings_2024_low.txt."""
    out = {}
    for line in (fag.DER / "savings_2024_low.txt").read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if parts[0] in CUTS:
            out[parts[0]] = (float(parts[2]), float(parts[1].split(" to ")[1]))
    return out


def main() -> None:
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    organs = organ_savings()
    out = ["Local heads per absorbed municipality (local_heads.py)", "",
           "rates per year: " + ", ".join(f"{k} {v:,.0f} EUR" for k, v in RATES.items()), "",
           "Partition | units with merger | absorbed municipalities | costs m per rate | savings on elected bodies O m | costs in % of O"]
    for cut in CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        multi = [m for m in units.values() if len(m) > 1]
        n = sum(len(m) - 1 for m in multi)
        costs = [n * v / 1e6 for v in RATES.values()]
        lo, hi = organs[cut]
        out.append(f"  {cut} | {len(multi)} | {n} | " + " / ".join(f"{c:.2f}" for c in costs)
                   + f" | {lo:.2f} to {hi:.2f} | {costs[0] / hi:.0%} to {costs[-1] / lo:.0%}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "local_heads.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
