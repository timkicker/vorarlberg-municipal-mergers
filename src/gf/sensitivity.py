"""Sensitivity checks: placebo runs across the states, turnout with size trends, the upper end
of the cost curve and the Styrian backtest with size trends.

Run from the repository root. Writes data/derived/sensitivity.txt.
"""

import collections
import contextlib
import io
import sys

import costs as c
import numpy as np
import styria as s
import styria_elections as se
import styria_outcomes as so
import turnout as tu
from accounts_columns import COL_INHABITANTS, COL_ORDINARY_SPENDING


def styria_size_trends() -> None:
    rng = np.random.default_rng(1)
    mp, new = s.mapping()
    m, pop = s.money()
    pre = collections.defaultdict(list)
    for g, (n, _share) in mp.items():
        pre[n].append(g)
    early = {n for n, gs in pre.items() if any((g, 2012) not in m for g in gs)}
    units = []
    for n, gs in sorted(pre.items()):
        if n == s.GRAZ or n in early:
            continue
        ys, ok = {}, True
        for t in s.YEARS:
            codes = gs if t in s.PRE else [n]
            if not all((c, t) in m and (c, t) in pop for c in codes):
                ok = False
                break
            ys[t] = (sum(m[(c, t)][0] for c in codes), sum(m[(c, t)][1] for c in codes), sum(pop[(c, t)] for c in codes))
        if ok and all(v[0] > 0 for v in ys.values()):
            units.append({"id": n, "treated": len(gs) >= 2, "pred": [(g, pop[(g, s.REF)]) for g in gs], "y": ys})
    print("units", len(units), "treated", sum(u["treated"] for u in units))
    p14 = lambda u: u["y"][2014][2]
    for lab, sel in (("merged", True), ("unchanged", False)):
        ps = np.array([p14(u) for u in units if u["treated"] == sel])
        print(f"  {lab}: population 2014 median {np.median(ps):,.0f}, mean {ps.mean():,.0f}, p10 {np.percentile(ps,10):,.0f}, p90 {np.percentile(ps,90):,.0f}")
    pp = np.array([p for u in units if u["treated"] for _, p in u["pred"]])
    print(f"  predecessors of the merged units: median {np.median(pp):,.0f}")

    def est(us, years=s.YEARS, ref=s.REF, group=None, cluster=None, nb=999):
        """DiD with unit FE, year FE (or group x year FE). Bootstrap over units or clusters."""
        T = len(years)
        rows = [(i, u, t) for i, u in enumerate(us) for t in years]
        unit = np.array([i for i, _, _ in rows])
        yr = np.array([t for *_, t in rows])
        tr = np.array([u["treated"] for _, u, _ in rows], float)
        y = np.log(np.array([u["y"][t][0] / u["y"][t][2] for _, u, t in rows]))
        if group is not None:
            grp = np.array([group(u) for _, u, _ in rows])
            fe = [((grp == g) & (yr == t)).astype(float) for g in sorted(set(grp)) for t in years[1:]]
        else:
            fe = [(yr == t).astype(float) for t in years[1:]]
        X = np.column_stack([tr * np.isin(yr, s.POST)] + fe)
        b = s.twfe(y, X, unit)[0]
        n = len(us)
        if cluster is None:
            cl = np.arange(n)
        else:
            labs = sorted(set(cluster(u) for u in us))
            cl = np.array([labs.index(cluster(u)) for u in us])
        members = [np.where(cl == c)[0] for c in range(cl.max() + 1)]
        bs = []
        for _ in range(nb):
            pick = np.concatenate([members[c] for c in rng.integers(0, len(members), len(members))])
            idx = (pick[:, None] * T + np.arange(T)).ravel()
            bs.append(s.twfe(y[idx], X[idx], np.repeat(np.arange(len(pick)), T))[0])
        return b, np.percentile(bs, 2.5), np.percentile(bs, 97.5), len(members)

    no14 = tuple(t for t in s.YEARS if t != 2014)
    cuts = np.quantile([p14(u) for u in units], [1 / 3, 2 / 3])
    terc = lambda u: int(np.searchsorted(cuts, p14(u)))
    print("Styrian size terciles", cuts)
    for name, kw in [
        ("main, bootstrap over units", {}),
        ("main, year x size tercile within Styria", {"group": terc}),
        ("main without 2014, year x size tercile", {"group": terc, "years": no14, "ref": 2013}),
    ]:
        b, lo, hi, k = est(units, **kw)
        print(f"{name}: {b:+.3f} [{lo:+.3f}, {hi:+.3f}]  clusters {k}")

    # common support: only units with 1,500 to 6,000 inhabitants in 2014
    cs = [u for u in units if 1500 <= p14(u) <= 6000]
    b, lo, hi, _ = est(cs)
    print(f"common support 1,500-6,000 inhabitants (n {len(cs)}, merged {sum(u['treated'] for u in cs)}): {b:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    b, lo, hi, _ = est(cs, years=no14, ref=2013)
    print(f"  same without 2014: {b:+.3f} [{lo:+.3f}, {hi:+.3f}]")


def state_placebo_core() -> None:
    m, pop = s.money()
    codes_by_year = {t: {k for (k, yy) in m if yy == t} for t in s.YEARS}
    stable = set.intersection(*codes_by_year.values())
    allm = []
    for g in sorted(stable):
        if g[0] == "9" or not all((g, t) in pop for t in s.YEARS) or pop[(g, s.REF)] >= 10000:
            continue
        ys = {t: (m[(g, t)][0], m[(g, t)][1], pop[(g, t)]) for t in s.YEARS}
        if all(v[0] > 0 for v in ys.values()):
            allm.append({"id": g, "y": ys})
    print("municipalities without change of area under 10,000:", collections.Counter(u["id"][0] for u in allm))

    def did(us, years):
        rows = [(i, u, t) for i, u in enumerate(us) for t in years]
        unit = np.array([i for i, _, _ in rows])
        yr = np.array([t for *_, t in rows])
        tr = np.array([u["treated"] for _, u, _ in rows], float)
        y = np.log(np.array([u["y"][t][0] / u["y"][t][2] for _, u, t in rows]))
        grp = np.array([u["group"] for _, u, _ in rows])
        fe = [((grp == g) & (yr == t)).astype(float) for g in sorted(set(grp)) for t in years[1:]]
        X = np.column_stack([tr * np.isin(yr, s.POST)] + fe)
        return s.twfe(y, X, unit)[0]

    no14 = tuple(t for t in s.YEARS if t != 2014)
    for state in "12345678":
        us = [dict(u, treated=u["id"][0] == state) for u in allm if u["id"][0] == state or u["id"][0] not in "6"]
        cuts = np.quantile([u["y"][s.REF][2] for u in us], [1 / 3, 2 / 3])
        for u in us:
            u["group"] = int(np.searchsorted(cuts, u["y"][s.REF][2]))
        print(f"state {state} (n {sum(u['treated'] for u in us)}) against the rest without Styria: with 2014 {did(us, s.YEARS):+.3f}, without 2014 {did(us, no14):+.3f}")


def state_placebo_ordinary() -> None:
    hh = so.municipal_accounts()
    m, pop = s.money()
    codes_by_year = {t: {k for (k, yy) in m if yy == t} for t in s.YEARS}
    stable = set.intersection(*codes_by_year.values())
    allm = [{"id": g} for g in sorted(stable) if g[0] != "9" and all((g, t) in hh for t in s.YEARS) and hh[(g, s.REF)][COL_INHABITANTS] < 10000 and all(m[(g, t)][0] > 0 for t in s.YEARS)]

    def did(us):
        rows = [(i, u, t) for i, u in enumerate(us) for t in s.YEARS]
        unit = np.array([i for i, _, _ in rows]); yr = np.array([t for *_, t in rows])
        tr = np.array([u["treated"] for _, u, _ in rows], float)
        y = np.log(np.array([hh[(u["id"], t)][COL_ORDINARY_SPENDING] / hh[(u["id"], t)][COL_INHABITANTS] for _, u, t in rows]))
        grp = np.array([u["group"] for _, u, _ in rows])
        fe = [((grp == g) & (yr == t)).astype(float) for g in sorted(set(grp)) for t in s.YEARS[1:]]
        return s.twfe(y, np.column_stack([tr * np.isin(yr, s.POST)] + fe), unit)[0]
    vals = {}
    for state in "12345678":
        us = [dict(u, treated=u["id"][0] == state) for u in allm if u["id"][0] == state or u["id"][0] != "6"]
        cuts = np.quantile([hh[(u["id"], s.REF)][COL_INHABITANTS] for u in us], [1/3, 2/3])
        for u in us: u["group"] = int(np.searchsorted(cuts, hh[(u["id"], s.REF)][COL_INHABITANTS]))
        vals[state] = did(us)
        print(f"state {state}: {vals[state]:+.3f}")
    o = np.array([v for k, v in vals.items() if k != "6"])
    print(f"SD over the 7 other states {o.std(ddof=1):.3f}")


def turnout_size_trends() -> None:
    ev = tu.styria_valid()
    mp = se.mapping_2011()
    pre = collections.defaultdict(list)
    for g, n in mp.items():
        pre[n].append(g)
    changed = se.changed_after_2015()
    units = []
    for n, gs in sorted(pre.items()):
        if n == s.GRAZ or n in changed or set(gs) & se.EARLY:
            continue
        v, w = {}, {}
        for y in se.YEARS:
            parts = [ev[y][g] for g in gs if g in ev[y]] if y in se.PRE else ([ev[y][n]] if n in ev[y] else [])
            if not parts:
                break
            v[y] = 100 * sum(p[1] for p in parts) / sum(p[0] for p in parts)
            w[y] = sum(p[0] for p in parts)
        if len(v) == len(se.YEARS):
            units.append({"id": n, "treated": len(gs) >= 2, "T": v, "W": w})
    print("units", len(units), "merged", sum(u["treated"] for u in units))
    for lab, sel in (("merged", True), ("unchanged", False)):
        ws = [u["W"][2015] for u in units if u["treated"] == sel]
        print(f"  {lab}: eligible voters 2015 median {np.median(ws):,.0f}")

    def did(us, group=None, years=se.YEARS, nb=999, rng=np.random.default_rng(2)):
        T = len(years)
        rows = [(i, u, t) for i, u in enumerate(us) for t in years]
        unit = np.array([r[0] for r in rows]); yr = np.array([r[2] for r in rows])
        tr = np.array([r[1]["treated"] for r in rows], float)
        y = np.array([r[1]["T"][r[2]] for r in rows])
        if group:
            grp = np.array([group(r[1]) for r in rows])
            fe = [((grp == g) & (yr == t)).astype(float) for g in sorted(set(grp)) for t in years[1:]]
        else:
            fe = [(yr == t).astype(float) for t in years[1:]]
        post = [t for t in years if t >= 2015]
        X = np.column_stack([tr * np.isin(yr, post)] + [tr * (yr == t) for t in post[1:]] + fe)  # effect 2015 plus the deviations in 2020 and 2025
        Xd = np.column_stack([tr * np.isin(yr, post)] + fe)
        b = s.twfe(y, Xd, unit)[0]
        bes = s.twfe(y, X, unit)[:len(post)]
        n = len(us); bs = []
        for _ in range(nb):
            pick = rng.integers(0, n, n)
            idx = (pick[:, None] * T + np.arange(T)).ravel()
            bs.append(s.twfe(y[idx], Xd[idx], np.repeat(np.arange(n), T))[0])
        return b, np.percentile(bs, 2.5), np.percentile(bs, 97.5), bes

    print("as turnout.py:", did(units)[:3])
    # size by electorate 2015 (territory after the merger), in thirds
    cuts = np.quantile([u["W"][2015] for u in units], [1 / 3, 2 / 3])
    g15 = lambda u: int(np.searchsorted(cuts, u["W"][2015]))
    b, lo, hi, bes = did(units, g15)
    print(f"year x size tercile by eligible voters 2015: {b:+.2f} [{lo:+.2f}, {hi:+.2f}]; 2015 {bes[0]:+.2f}, extra 2020 {bes[1]:+.2f}, extra 2025 {bes[2]:+.2f}")
    # by size in 2010 (sum of the predecessors), the mechanical size before the merger
    cuts10 = np.quantile([u["W"][2010] for u in units], [1 / 3, 2 / 3])
    g10 = lambda u: int(np.searchsorted(cuts10, u["W"][2010]))
    b, lo, hi, bes = did(units, g10)
    print(f"year x size tercile by eligible voters 2010 (sum of the predecessors): {b:+.2f} [{lo:+.2f}, {hi:+.2f}]")
    # common support
    cs = [u for u in units if 1200 <= u["W"][2015] <= 5000]
    b, lo, hi, _ = did(cs)
    print(f"common support 1,200-5,000 eligible voters 2015 (n {len(cs)}, merged {sum(u['treated'] for u in cs)}): {b:+.2f} [{lo:+.2f}, {hi:+.2f}]")
    # prediction from the Vorarlberg cross-section, -5.7 pp per log unit, for the Styrian units
    pr = [np.log(u["W"][2015] / np.mean([ev[2010][g][0] for g in pre[u["id"]] if g in ev[2010]])) for u in units if u["treated"]]
    print(f"mean log(eligible voters unit / mean predecessor) {np.mean(pr):.2f}; Vbg slope -5.7 x that = {-5.7 * np.mean(pr):+.1f} pp")


def curve_upper_end() -> None:
    rows = c.build()
    ok = [r for r in rows if r["complete"] and r["net"] > 0]
    inh = np.array([r["population"] for r in ok])
    st = np.array([r["statutory_city"] for r in ok])
    for lim in (10000, 20000, 50000, 100000):
        print(f"from {lim:>7,} inhabitants: {np.sum(inh >= lim):>3} municipalities, of which statutory cities {np.sum((inh >= lim) & st)}")
    print("Vorarlberg largest:", sorted([(round(r["population"]), r["gkz"]) for r in ok if r["state"] == "8"])[-3:])
    print("statutory cities n", st.sum(), "smallest", min(r["population"] for r in ok if r["statutory_city"]))

    def fit_curve(sel, knots_q=(0, .25, .5, .75, 1), drop_area=False):
        data = {"y": np.log(np.array([r["net"] / r["population"] for r in sel])), "x": np.log(np.array([r["population"] for r in sel])),
                "area": np.array([r["area_km2"] for r in sel]), "city": np.array([r["statutory_city"] for r in sel]),
                "state": np.array([r["state"] for r in sel])}
        knots = np.quantile(data["x"], knots_q)
        X = c.design(data, knots)
        if drop_area:
            X = np.delete(X, len(knots), axis=1)
        if data["city"].sum() == 0:
            X = np.delete(X, len(knots) + (0 if drop_area else 1), axis=1)
        beta, *_ = np.linalg.lstsq(X, data["y"], rcond=None)
        rel = lambda p: float(np.exp(c.ns_basis(np.log(np.array([p])), knots) @ beta[1:len(knots)] - c.ns_basis(np.log(np.array([1000.])), knots) @ beta[1:len(knots)])[0])
        return {p: rel(p) for p in (500, 3000, 10000, 50000, 100000)}, np.exp(knots)

    for name, sel, kw in (("as costs.py", ok, {}), ("without statutory cities", [r for r in ok if not r["statutory_city"]], {}),
                          ("without log area", ok, {"drop_area": True}), ("without municipalities from 50,000", [r for r in ok if r["population"] < 50000], {})):
        f, kn = fit_curve(sel, **kw)
        print(f"{name}: n {len(sel)}, knots {[round(k) for k in kn]}, " + ", ".join(f"c({p})={v:.2f}" for p, v in f.items()))


def main() -> None:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for title, f in (("Styria with size trends", styria_size_trends), ("State placebo, core administration", state_placebo_core),
                         ("State placebo, ordinary spending", state_placebo_ordinary), ("Turnout with size trends", turnout_size_trends),
                         ("Upper end of the cost curve", curve_upper_end)):
            print(f"\n== {title}")
            f()
    text = "Sensitivity checks (sensitivity.py)\n" + buf.getvalue()
    print(text)
    (c.OUT / "sensitivity.txt").write_text(text)


if __name__ == "__main__":
    sys.exit(main())
