"""Robustness of the cuts when commuters abroad and to other states enter the totals.

Run from the repository root. Writes data/derived/cuts_outside.txt.
"""

import collections
import csv
import sys

import numpy as np
import pareto
import regions

KS = (4, 8, 10, 19)
LIMITS = (2000, 3500, 5000)
COL_MUNICIPALITY = "gemeinde"  # municipality name column in vbg_regional_divisions.csv of data.vorarlberg.gv.at


def units(lab) -> set:
    parts = collections.defaultdict(set)
    for i, l in enumerate(lab):
        parts[l].add(i)
    return {frozenset(m) for m in parts.values()}


def changed(a, b) -> int:
    ua, ub = units(a), units(b)
    return sum(1 for i in range(len(a)) if next(m for m in ua if i in m) not in ub)


def main() -> None:
    rows, t, adj = regions.load()
    gkz = [r["gkz"] for r in rows]
    n = len(gkz)
    ix = {g: i for i, g in enumerate(gkz)}
    outside = np.zeros(n)
    for r in csv.DictReader((regions.OUT / "commuters_2024.csv").open(encoding="utf-8")):
        if r["to"] not in ix:
            outside[ix[r["from_gkz"]]] += int(r["count"])
    t2 = np.zeros((n + 1, n + 1))
    t2[:n, :n] = t
    t2[:n, n] = outside
    adm = {r["gkz"]: r for r in csv.DictReader((regions.OUT / "administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[g]["population"]) for g in gkz])
    pop2 = np.append(pop, 1e12)
    iso = frozenset({n})
    base_m = regions.intramax(t, adj)
    out_m = regions.intramax(t2, adj, iso)
    out = ["Partitions with the outside node (cuts_outside.py)", "",
           f"out-commuters to outside in the row totals: {outside.sum():,.0f}", "",
           "partition | ARI to the base case | municipalities with a changed unit | units base case / new"]
    pairs = []
    for k in KS:
        a = regions.cut(n, base_m, k)
        b = regions.cut(n + 1, out_m, k + 1)[:n]
        pairs.append((f"Intramax k={k}", a, b))
    for lim in LIMITS:
        a = pareto.threshold_rule(t, adj, pop, lim)
        b = pareto.threshold_rule(t2, adj, pop2, lim)[:n]
        pairs.append((f"Threshold {lim}", a, b))
    name = {r["gkz"]: r[COL_MUNICIPALITY] for r in rows}
    detail = []
    for lab, a, b in pairs:
        c = changed(a, b)
        out.append(f"  {lab} | {regions.ari(a, b):.3f} | {c} | {len(units(a))} / {len(units(b))}")
        if c and lab.startswith("Threshold"):
            gone = [m for m in units(a) if m not in units(b)]
            new = [m for m in units(b) if m not in units(a)]
            detail.append(f"  {lab}: gone " + "; ".join(", ".join(sorted(name[gkz[i]] for i in m)) for m in gone)
                          + " | new " + "; ".join(", ".join(sorted(name[gkz[i]] for i in m)) for m in new))
    out += ["", "changed units of the thresholds:"] + (detail or ["  none"])
    text = "\n".join(out)
    print(text)
    (regions.OUT / "cuts_outside.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
