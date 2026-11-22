"""Partner size ratio: how many people end up as a small part and what a cap costs."""

import csv
import json
import pathlib
import sys

import numpy as np
from shapely.geometry import shape

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import elections  # noqa: E402
import pareto  # noqa: E402
import regions  # noqa: E402

OUT = pareto.OUT
SMALL_SHARE = 0.20
CAPS = (None, 10, 5, 3)
LIMITS = (2000, 3500, 5000)


def capped_rule(t: np.ndarray, adj: set, pop: np.ndarray, limit: float, cap: float | None) -> tuple[list[int], int]:
    """pareto.threshold_rule with a cap on largest / smallest member; returns labels and units left below limit."""
    t = t.copy()
    n = len(t)
    label = list(range(n))
    size = pop.astype(float).copy()
    hi, lo = size.copy(), size.copy()
    alive = set(range(n))
    nb = {i: set() for i in alive}
    for a, b in adj:
        nb[a].add(b)
        nb[b].add(a)
    stuck = set()
    while True:
        small = [i for i in alive if size[i] < limit and nb[i] and i not in stuck]
        if not small:
            break
        i = min(small, key=lambda x: (size[x], x))
        ok = [j for j in nb[i] if cap is None or max(hi[i], hi[j]) / min(lo[i], lo[j]) <= cap]
        if not ok:
            stuck.add(i)
            continue
        o, d = t.sum(1), t.sum(0)
        j = max(ok, key=lambda j: (t[i, j] / (o[i] * d[j]) + t[j, i] / (o[j] * d[i]), -j))
        keep, gone = min(i, j), max(i, j)
        t[keep, :] += t[gone, :]
        t[:, keep] += t[:, gone]
        t[gone, :] = 0
        t[:, gone] = 0
        size[keep] += size[gone]
        hi[keep], lo[keep] = max(hi[keep], hi[gone]), min(lo[keep], lo[gone])
        alive.remove(gone)
        stuck.discard(gone)
        nb[keep] = (nb[keep] | nb.pop(gone)) - {keep, gone}
        for k in nb[keep]:
            nb[k].discard(gone)
            nb[k].add(keep)
        label = [keep if l == gone else l for l in label]
    below = sum(size[i] < limit for i in alive)
    return label, below


def main() -> None:
    rows, t, adj = regions.load()
    gkz = [r["gkz"] for r in rows]
    ix = {g: i for i, g in enumerate(gkz)}
    adm = {r["gkz"]: r for r in csv.DictReader((OUT / "administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[g]["population"]) for g in gkz])
    cost = np.array([float(adm[g]["net"]) for g in gkz])
    curve = np.loadtxt(OUT / "cost_curve_net.csv", delimiter=",", skiprows=1)
    lc = lambda p: np.interp(np.log(p), np.log(curve[:, 0]), np.log(curve[:, 1]))  # noqa: E731
    geo = json.loads((pareto.RAW / "boundaries_statat_2026.geojson").read_text())
    pts = {f["properties"]["g_id"]: shape(f["geometry"]).representative_point() for f in geo["features"]}
    xy = np.array([[pts[g].x, pts[g].y] for g in gkz])
    flows = [(ix[r["from_gkz"]], ix[r["to"]], int(r["count"])) for r in csv.DictReader((OUT / "commuters_2024.csv").open(encoding="utf-8")) if r["to"] in ix]
    fa, fb, fw = (np.array(x) for x in zip(*flows))
    el = {r["gkz"]: r for r in elections.load(2025)}
    wb = np.array([float(el[g]["w"]) for g in gkz])
    x = np.log(wb)
    b = elections.logit(x, np.array([el[g]["A"] for g in gkz], float))

    def score(lab) -> dict:
        lab = np.asarray(lab)
        e = dist = 0.0
        m_small, r_max, h, w_open, w_all = 0.0, 1.0, 0, 0.0, wb.sum()
        for u in np.unique(lab):
            m = np.where(lab == u)[0]
            tot = pop[m].sum()
            seat = m[np.argmax(pop[m])]
            dist += np.sum(pop[m] * np.hypot(*(xy[m] - xy[seat]).T)) / 1000
            w = wb[m].sum()
            w_open += w * (1 - 1 / (1 + np.exp(-(b[0] + b[1] * np.log(w)))))
            if len(m) > 1:
                e += np.sum(cost[m] * (1 - np.exp(lc(tot) - lc(pop[m]))))
                m_small += pop[m][pop[m] / tot < SMALL_SHARE].sum()
                r_max = max(r_max, pop[m].max() / pop[m].min())
                h += int(pop[m].max() / tot > 0.5)
        return {"k": len(np.unique(lab)), "E": e * pareto.SCALE_MAIN, "F": fw[lab[fa] == lab[fb]].sum() / fw.sum(), "D": dist / pop.sum(), "M": m_small / pop.sum(), "R": r_max, "H": h, "W": w_open / w_all}

    lines = ["Part 1: named variants | k | M share of inhabitants as a small part (<20 %) | R largest ratio | H units with a partner >50 %"]
    zs = list(csv.DictReader((OUT / "pareto_partitions.csv").open(encoding="utf-8")))
    zix = {r["gkz"]: r for r in zs}
    for col in [c for c in zs[0] if c not in ("gkz", "municipality")]:
        if col.startswith("Intramax") and int(col.split("=")[1]) not in (4, 8, 10, 19, 30, 40, 50, 60, 70, 80, 90):
            continue
        names = [zix[g][col] for g in gkz]
        lab = [sorted(set(names)).index(v) for v in names]
        s = score(lab)
        lines.append(f"  {col:34} {s['k']:>3}  M {s['M']:.1%}  R {s['R']:>7.1f}  H {s['H']:>3}")

    lines.append("\nPart 2: threshold rule with a cap on the size ratio | k | below threshold | E m EUR (factor 0.57) | F | D km | M | R | without contested election")
    base = {}
    for limit in LIMITS:
        for cap in CAPS:
            lab, below = capped_rule(t, adj, pop, limit, cap)
            s = score(lab)
            if cap is None:
                base[limit] = s["E"]
            lines.append(f"  Threshold {limit} cap {str(cap or 'none'):>5}  {s['k']:>3}  {below:>3}  {s['E'] / 1e6:6.2f} ({s['E'] / base[limit]:.0%})  {s['F']:.3f}  {s['D']:5.2f}  {s['M']:.1%}  {s['R']:6.1f}  {s['W']:.1%}")
    text = "\n".join(lines)
    print(text)
    (OUT / "ratio.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
