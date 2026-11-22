"""Threshold rule rerun with Mittelberg given no neighbours (no road to the rest of the state).

Run from the repository root. Writes data/derived/mittelberg.txt.
"""

import collections
import csv
import sys

import numpy as np
import pareto
import regions

OUT = pareto.OUT
LIMITS = (2000, 3500, 5000)
COL_MUNICIPALITY = "gemeinde"  # municipality name column in vbg_regional_divisions.csv of data.vorarlberg.gv.at


def main() -> None:
    rows, t, adj = regions.load()
    gkz = [r["gkz"] for r in rows]
    name = [r[COL_MUNICIPALITY] for r in rows]
    n = len(gkz)
    ix = {g: i for i, g in enumerate(gkz)}
    adm = {r["gkz"]: r for r in csv.DictReader((OUT / "administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[g]["population"]) for g in gkz])
    cost = np.array([float(adm[g]["net"]) for g in gkz])
    times = list(csv.reader((OUT / "travel_time_seat.csv").open(encoding="utf-8")))
    order = [ix[g] for g in times[0][1:]]
    T = np.zeros((n, n))
    for r in times[1:]:
        T[ix[r[0]], order] = [float(v) for v in r[1:]]
    flows = [(ix[r["from_gkz"]], ix[r["to"]], int(r["count"])) for r in csv.DictReader((OUT / "commuters_2024.csv").open(encoding="utf-8")) if r["to"] in ix]
    fa, fb, fw = (np.array(x) for x in zip(*flows))
    curve = np.loadtxt(OUT / "cost_curve_net.csv", delimiter=",", skiprows=1)
    lc = lambda p: np.interp(np.log(p), np.log(curve[:, 0]), np.log(curve[:, 1]))  # noqa: E731

    def score(lab) -> tuple[float, float, float]:
        lab = np.asarray(lab)
        e = trav = 0.0
        for u in np.unique(lab):
            m = np.where(lab == u)[0]
            if len(m) > 1:
                e += np.sum(cost[m] * (1 - np.exp(lc(pop[m].sum()) - lc(pop[m]))))
            trav += np.sum(pop[m] * T[m, m[np.argmax(pop[m])]])
        return e * pareto.SCALE_MAIN, fw[lab[fa] == lab[fb]].sum() / fw.sum(), trav / pop.sum()

    def units(lab) -> dict:
        d = collections.defaultdict(list)
        for i, l in enumerate(lab):
            d[l].append(i)
        return {frozenset(m) for m in d.values()}

    mb = name.index("Mittelberg")
    nbrs = sorted(name[b if a == mb else a] for a, b in adj if mb in (a, b))
    adj2 = {(a, b) for a, b in adj if mb not in (a, b)}
    out = ["Threshold rule without neighbours for Mittelberg (mittelberg.py)", "",
           f"Mittelberg {pop[mb]:,.0f} inhabitants (basis administration_2016_2019), removed neighbours: {', '.join(nbrs)}", "",
           "threshold | E F T main | E F T variant | E F T robustness 5 (only taken out) | municipalities with another unit"]
    for lim in LIMITS:
        a = np.asarray(pareto.threshold_rule(t, adj, pop, lim))
        b = np.asarray(pareto.threshold_rule(t, adj2, pop, lim))
        r5 = a.copy()
        r5[mb] = -1
        ua, ub = units(a), units(b)
        moved = sorted(name[i] for i in range(n) if next(m for m in ua if i in m) not in ub)
        sa, sb, s5 = score(a), score(b), score(r5)
        f = lambda s: f"{s[0] / 1e6:5.2f} {s[1]:.3f} {s[2]:5.2f}"  # noqa: E731
        out.append(f"  {lim} | {f(sa)} | {f(sb)} | {f(s5)} | {len(moved)}: {', '.join(moved)}")
        for m in sorted(ub - ua, key=lambda m: -pop[list(m)].sum()):
            out.append(f"     new unit {pop[list(m)].sum():,.0f} inhabitants: {', '.join(sorted(name[i] for i in m))}")
        for m in sorted(ua - ub, key=lambda m: -pop[list(m)].sum()):
            out.append(f"     old unit {pop[list(m)].sum():,.0f} inhabitants: {', '.join(sorted(name[i] for i in m))}")
    text = "\n".join(out)
    print(text)
    (OUT / "mittelberg.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
