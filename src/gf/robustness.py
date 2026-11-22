"""Sensitivity of the cost curve and the partitions, sections 3 to 8."""

import collections
import csv
import json
import pathlib
import random
import sys

import networkx as nx
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import costs  # noqa: E402
import pareto  # noqa: E402
import regions  # noqa: E402
import voluntary  # noqa: E402
from accounts_columns import COL_EXTRAORDINARY_SPENDING, COL_ORDINARY_SPENDING

OUT, RAW = pareto.OUT, pareto.RAW
SEED = 12345
COL_MUNICIPALITY = "gemeinde"  # municipality name column in vbg_regional_divisions.csv of data.vorarlberg.gv.at
# Keys of gv_YYYY.json, the municipal election results of the state of Vorarlberg (open data)
KEY_RESULTS = "ergebnisse"  # list of municipalities
KEY_COUNCIL_ELECTION = "gemeinderatswahl"  # council election block
KEY_MAYOR_ELECTION = "buergermeisterwahl"  # mayoral election block
KEY_MODE = "wahlart"  # election mode
NAMED = ["Threshold 1000", "Threshold 2000", "Threshold 3500", "Threshold 5000", "Intramax k=19", "Intramax k=40",
         "official planning region", "official care management region", "official region", "official district"]


def cost_data() -> dict:
    ok = [r for r in costs.build() if r["complete"] and r["net"] > 0]
    return {
        "y": np.log(np.array([r["net"] / r["population"] for r in ok])),
        "x": np.log(np.array([r["population"] for r in ok])),
        "area": np.array([r["area_km2"] for r in ok]),
        "city": np.array([r["statutory_city"] for r in ok]),
        "state": np.array([r["state"] for r in ok]),
    }


def fit_curve(d: dict, df: int, weighted: bool = False, extra: np.ndarray | None = None):
    knots = np.quantile(d["x"], np.linspace(0, 1, df + 1))
    X = costs.design(d, knots)
    if extra is not None:
        X = np.column_stack([X, extra])
    w = np.sqrt(np.exp(d["x"])) if weighted else np.ones(len(d["y"]))
    beta, *_ = np.linalg.lstsq(X * w[:, None], d["y"] * w, rcond=None)
    return beta, knots


def flat_from(f: np.ndarray, grid: np.ndarray, crit: float) -> float:
    gain = np.interp(grid + np.log(2), grid, f, right=np.nan) - f
    idx = np.where(gain > np.log(1 - crit))[0]
    return float(np.exp(grid[idx[0]])) if len(idx) else np.nan


def rel(f: np.ndarray, grid: np.ndarray, inh: float) -> float:
    return float(np.exp(np.interp(np.log(inh), grid, f) - np.interp(np.log(1000), grid, f)))


def main() -> None:
    lines = []
    d = cost_data()
    grid = np.linspace(d["x"].min(), d["x"].max(), 400)

    # partitions, costs and goals as in pareto.py and roads.py
    rows, t, adj = regions.load()
    gkz = [r["gkz"] for r in rows]
    names_of = [r[COL_MUNICIPALITY] for r in rows]
    n = len(gkz)
    ix = {g: i for i, g in enumerate(gkz)}
    adm = {r["gkz"]: r for r in csv.DictReader((OUT / "administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[g]["population"]) for g in gkz])
    cost = np.array([float(adm[g]["net"]) for g in gkz])
    gross = np.array([float(adm[g]["gross"]) for g in gkz])
    times = list(csv.reader((OUT / "travel_time_seat.csv").open(encoding="utf-8")))
    order = [ix[g] for g in times[0][1:]]
    T = np.zeros((n, n))
    for r in times[1:]:
        T[ix[r[0]], order] = [float(v) for v in r[1:]]
    flows = [(ix[r["from_gkz"]], ix[r["to"]], int(r["count"])) for r in csv.DictReader((OUT / "commuters_2024.csv").open(encoding="utf-8")) if r["to"] in ix]
    fa, fb, fw = (np.array(x) for x in zip(*flows))
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(adj)
    cands, _ = pareto.candidates(rows, t, adj, pop, g)
    total = [float(r[COL_ORDINARY_SPENDING]) + float(r[COL_EXTRAORDINARY_SPENDING]) for r in csv.DictReader((RAW / "gemhh_at_2000_2019.csv").open(encoding="utf-8"), delimiter=";")
             if r["C-C41-2"].startswith("8") and r["C-A10-0"] in {f"A10-{y}" for y in (2016, 2017, 2018, 2019)}]
    per_year = sum(total) / 4

    def saving(lab, lc) -> float:
        lab = np.asarray(lab)
        e = 0.0
        for u in np.unique(lab):
            m = np.where(lab == u)[0]
            if len(m) > 1:
                e += np.sum(cost[m] * (1 - np.exp(lc(pop[m].sum()) - lc(pop[m]))))
        return e * pareto.SCALE_MAIN

    # 3 specification band of the cost curve
    lines.append("3. specification band of the cost curve (net, factor 0.57 for E)")
    lines.append("   variant | threshold 5 % | 3 % | 10 % | c500 | c3000 | c50000 | E m EUR: " + " | ".join(NAMED) + " | largest E of all candidates (share of spending)")
    specs = [(f"df {k}", k, False) for k in (3, 4, 5, 6, 8)] + [("df 4, weighted by population", 4, True)]
    for label, df, wt in specs:
        beta, knots = fit_curve(d, df, wt)
        f = costs.curve(beta, grid, knots)
        lc = lambda p, f=f: np.interp(np.log(p), grid, f)  # noqa: E731  # constant outside the data
        es = {x: saving(cands[x], lc) for x in cands}
        best = max(es, key=es.get)
        lines.append(f"   {label:32} {flat_from(f, grid, .05):7,.0f} {flat_from(f, grid, .03):7,.0f} {flat_from(f, grid, .10):7,.0f}  {rel(f, grid, 500):.2f} {rel(f, grid, 3000):.2f} {rel(f, grid, 50000):.2f}  "
                     + " ".join(f"{es[x] / 1e6:6.2f}" for x in NAMED) + f"  {es[best] / 1e6:.2f} ({es[best] / per_year:.2%}, {best})")
    rng = np.random.default_rng(SEED)
    th = []
    for _ in range(2000):
        i = rng.integers(0, len(d["y"]), len(d["y"]))
        db = {k: v[i] for k, v in d.items()}
        beta, knots = fit_curve(db, 4)
        gb = np.linspace(db["x"].min(), db["x"].max(), 400)
        th.append(flat_from(costs.curve(beta, gb, knots), gb, .05))
    lines.append(f"   bootstrap with knots set anew (df 4): threshold 95 % {np.nanpercentile(th, 2.5):,.0f} to {np.nanpercentile(th, 97.5):,.0f}")

    # 4 Vorarlberg on its own
    v = d["state"] == "8"
    dv = {k: a[v] for k, a in d.items()}
    kv = np.quantile(dv["x"], [0, 1 / 3, 2 / 3, 1])

    def vbg(idx):
        X = np.column_stack([np.ones(len(idx)), costs.ns_basis(dv["x"][idx], kv), np.log(dv["area"][idx])])
        b, *_ = np.linalg.lstsq(X, dv["y"][idx], rcond=None)
        f = lambda e: (costs.ns_basis(np.atleast_1d(np.log(e)), kv) @ b[1:len(kv)])[0]  # noqa: E731
        return np.exp(f(3000) - f(1000)), np.exp(f(500) - f(1000))
    nv = int(v.sum())
    pt = vbg(np.arange(nv))
    bs = np.array([vbg(rng.integers(0, nv, nv)) for _ in range(2000)])
    lines.append(f"\n4. Vorarlberg alone (n = {nv}, spline df 3 and log area): c3000/c1000 {pt[0]:.2f} (95 % {np.percentile(bs[:, 0], 2.5):.2f} to {np.percentile(bs[:, 0], 97.5):.2f}), c500/c1000 {pt[1]:.2f} ({np.percentile(bs[:, 1], 2.5):.2f} to {np.percentile(bs[:, 1], 97.5):.2f})")
    inter = v * d["x"]
    b0, _ = fit_curve(d, 4, extra=inter)
    bb = []
    for _ in range(2000):
        i = rng.integers(0, len(d["y"]), len(d["y"]))
        bb.append(fit_curve({k: a[i] for k, a in d.items()}, 4, extra=inter[i])[0][-1])
    lines.append(f"   joint model, Vorarlberg x log population: {b0[-1]:+.3f} (95 % {np.percentile(bb, 2.5):+.3f} to {np.percentile(bb, 97.5):+.3f})")
    beta, knots = fit_curve(d, 4)
    f4 = costs.curve(beta, grid, knots)
    lines.append(f"   joint for comparison: c3000/c1000 {rel(f4, grid, 3000):.2f}, c500/c1000 {rel(f4, grid, 500):.2f}")

    # main curve as used in the paper, from cost_curve_net.csv
    curve = np.loadtxt(OUT / "cost_curve_net.csv", delimiter=",", skiprows=1)
    lcm = lambda p: np.interp(np.log(p), np.log(curve[:, 0]), np.log(curve[:, 1]))  # noqa: E731

    def travel(lab) -> float:
        lab = np.asarray(lab)
        s = 0.0
        for u in np.unique(lab):
            m = np.where(lab == u)[0]
            s += np.sum(pop[m] * T[m, m[np.argmax(pop[m])]])
        return s / pop.sum()

    def commuters(lab) -> float:
        lab = np.asarray(lab)
        return fw[lab[fa] == lab[fb]].sum() / fw.sum()

    # 5 Mittelberg as a unit of its own
    mb = names_of.index("Mittelberg")
    lines.append("\n5. Mittelberg as a unit of its own: variant | E before | E after | T before | T after | seat of the unit with Mittelberg before")
    for x in NAMED:
        lab = np.asarray(pd_lab(cands[x]))
        m = np.where(lab == lab[mb])[0]
        seat = names_of[m[np.argmax(pop[m])]]
        lab2 = lab.copy()
        lab2[mb] = -1
        rest = [i for i in m if i != mb]
        ok = not rest or nx.is_connected(g.subgraph(rest))
        lines.append(f"   {x:34} {saving(lab, lcm) / 1e6:5.2f} {saving(lab2, lcm) / 1e6:5.2f}  {travel(lab):5.2f} {travel(lab2):5.2f}  {seat}{'' if ok else ' (rest not contiguous)'}")

    # 6 local search
    lines.append("\n6. local search, 6000 steps: start | E F T at the start | E F T at the end | beats the start | moved municipalities")
    rs = random.Random(SEED)
    for x in ["Threshold 2000", "Threshold 3500", "Threshold 5000", "Intramax k=19", "official planning region"]:
        lab0 = np.asarray(pd_lab(cands[x]))
        s0 = np.array([saving(lab0, lcm), commuters(lab0), -travel(lab0)])
        lab, s = lab0.copy(), s0.copy()
        for _ in range(6000):
            i = rs.randrange(n)
            nbu = sorted({lab[j] for j in g[i] if lab[j] != lab[i]})
            if not nbu:
                continue
            rest = [k for k in range(n) if lab[k] == lab[i] and k != i]
            if rest and not nx.is_connected(g.subgraph(rest)):
                continue
            new = lab.copy()
            new[i] = rs.choice(nbu)
            sn = np.array([saving(new, lcm), commuters(new), -travel(new)])
            if np.all(sn >= s0 - 1e-9) and np.all(sn >= s - 1e-9) and np.any(sn > s + 1e-9):
                lab, s = new, sn
        beats = bool(np.all(s >= s0 - 1e-9) and np.any(s > s0 + 1e-9))
        moved = [names_of[i] for i in range(n) if lab[i] != lab0[i]]
        lines.append(f"   {x:24} {s0[0] / 1e6:5.2f} {s0[1]:.3f} {-s0[2]:5.2f} | {s[0] / 1e6:5.2f} {s[1]:.3f} {-s[2]:5.2f} | {'yes' if beats else 'no'} | {len(moved)} {moved[:6]}")

    # 7 voluntary rule at 2,000
    lab, _ = voluntary.rule(t, adj, pop, 2000, lambda m: voluntary.acceptable(m, pop, T, *voluntary.MAIN))
    lab = np.asarray(lab)
    units = [np.where(lab == u)[0] for u in np.unique(lab)]
    small = [m for m in units if pop[m].sum() < 2000]
    merged_small = [m for m in small if len(m) > 1]
    under1000 = np.where(pop < 1000)[0]
    with_partner = [i for i in under1000 if (lab == lab[i]).sum() > 1]
    lines.append(f"\n7. voluntary, threshold 2000, 20 % and 15 min: {len(small)} units below 2000, of these {len(merged_small)} mergers, {len(small) - len(merged_small)} alone")
    for m in sorted(small, key=lambda m: pop[m].sum()):
        lines.append(f"   {pop[m].sum():6,.0f} inhabitants: " + ", ".join(f"{names_of[i]} ({pop[i]:,.0f})" for i in m))
    lines.append(f"   municipalities below 1000: {len(under1000)}, of these with a partner {len(with_partner)}")
    lines.append("   arithmetic limit: a partner with p inhabitants must make up at least 20 %, so the unit has at most 5 p. Below 400 inhabitants every unit with it stays below 2000.")
    low = [m for m in units if pop[m].min() < 400 and len(m) > 1]
    lines.append(f"   units with a partner below 400: {len(low)}, of these from 2000: {sum(pop[m].sum() >= 2000 for m in low)}")

    # 8 shares, factor, election types
    vb = np.array([g.startswith("8") for g in gkz])
    lines.append(f"\n8. core administration Vorarlberg 2016-2019, annual mean: net {cost[vb].sum() / 1e6:.1f} m EUR = {cost[vb].sum() / per_year:.1%}, gross {gross[vb].sum() / 1e6:.1f} m EUR = {gross[vb].sum() / per_year:.1%} of spending ({per_year / 1e6:,.1f} m EUR)")
    lines.append(f"   factor as ratio of the percentages: {np.expm1(-0.145):.3f} / {np.expm1(-0.255):.3f} = {np.expm1(-0.145) / np.expm1(-0.255):.2f}, as ratio of the log values {0.145 / 0.255:.2f}")
    for year in (2020, 2025):
        dd = json.loads((RAW / f"gv_{year}.json").read_text(encoding="utf-8-sig"))[KEY_RESULTS]
        council = collections.Counter(e[KEY_COUNCIL_ELECTION][KEY_MODE] for e in dd)
        mayor = collections.Counter((e.get(KEY_MAYOR_ELECTION) or {}).get(KEY_MODE) for e in dd)
        lines.append(f"   election types {year}: municipal council {dict(council)}, mayor {dict(mayor)}")

    text = "\n".join(lines)
    print(text)
    (OUT / "robustness.txt").write_text(text.strip() + "\n")


def pd_lab(lab) -> list[int]:
    """Labels as consecutive integers."""
    m = {}
    return [m.setdefault(x, len(m)) for x in lab]


if __name__ == "__main__":
    sys.exit(main())
