"""Commuters abroad per municipality and per cut. Also the commuters the cut scoring leaves out.

Run from the repository root. Writes data/derived/cross_border.txt.
"""

import collections
import csv
import statistics
import sys

import fag

CUTS = ("Threshold 3500", "Threshold 5000", "official planning region")
CLASSES = ((0, 1000), (1000, 2000), (2000, 5000), (5000, 10000), (10000, float("inf")))


def main() -> None:
    pop = fag.load_pop()
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    name = {r["gkz"]: r["municipality"] for r in rows}
    info = {r["gkz"]: r for r in csv.DictReader(open(fag.DER / "commuters_2024_municipalities.csv", encoding="utf-8"))}
    abroad, other_state, total_out = collections.Counter(), collections.Counter(), collections.Counter()
    for r in csv.DictReader(open(fag.DER / "commuters_2024.csv", encoding="utf-8")):
        g, n = r["from_gkz"], int(r["count"])
        total_out[g] += n
        if r["to"] == "abroad":
            abroad[g] += n
        elif not r["to"].startswith("8"):
            other_state[g] += n
    emp = {g: int(info[g]["out_commuters"]) + int(info[g]["non_commuters"]) for g in name}
    share = {g: abroad[g] / emp[g] for g in name}
    A, E, O, L = sum(abroad.values()), sum(emp.values()), sum(total_out.values()), sum(other_state.values())
    out = ["Cross-border commuters, commuter atlas 31.10.2024 (cross_border.py)", "",
           f"1. commuters abroad {A:,}, employed at place of residence {E:,} ({A / E:.1%}), out-commuters {O:,} ({A / O:.1%})", "",
           "2. highest shares of the employed at place of residence"]
    for g in sorted(name, key=lambda x: -share[x])[:10]:
        out.append(f"  {name[g]} ({pop[g]:,} inhabitants) | {abroad[g]:,} | {share[g]:.1%}")
    out.append("  median by size:")
    for lo, hi in CLASSES:
        v = [share[g] for g in name if lo <= pop[g] < hi]
        lab = f"from {lo:,}" if hi == float("inf") else f"{lo:,} to under {hi:,}"
        out.append(f"    {lab} | {len(v)} | {statistics.median(v):.1%}")
    out += ["", "3. per partition: share per unit (smallest / largest), median of the range within the units with a merger, largest ranges"]
    for cut in CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        us = {u: sum(abroad[g] for g in m) / sum(emp[g] for g in m) for u, m in units.items()}
        spans = sorted(((max(share[g] for g in m) - min(share[g] for g in m), u) for u, m in units.items() if len(m) > 1), reverse=True)
        out.append(f"  {cut} | {min(us.values()):.1%} / {max(us.values()):.1%} | range median {statistics.median(s for s, _ in spans):.1%} | "
                   + ", ".join(f"{u} {s:.1%}" for s, u in spans[:3]))
    over = [g for g in name if (abroad[g] + other_state[g]) / total_out[g] > 0.25]
    out += ["", "4. out-commuters left out by ratio.py",
            f"  abroad {A:,} ({A / O:.1%}), other states {L:,} ({L / O:.1%}), together {(A + L) / O:.1%} of out-commuters",
            f"  municipalities with more than 25 % of out-commuters left out: {len(over)}" + (": " + ", ".join(
                f"{name[g]} {(abroad[g] + other_state[g]) / total_out[g]:.0%}" for g in sorted(over, key=lambda x: -(abroad[x] + other_state[x]) / total_out[x])) if over else "")]
    text = "\n".join(out)
    print(text)
    (fag.DER / "cross_border.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
