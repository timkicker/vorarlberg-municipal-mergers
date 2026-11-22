"""Partitions in which every partner could plausibly agree."""

import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import elections  # noqa: E402
import pareto  # noqa: E402
import regions  # noqa: E402

OUT = pareto.OUT
LIMITS = (2000, 3500, 5000)
MAIN = (0.20, 15.0)
SWITCHES = ((0.10, 15.0), (0.30, 15.0), (0.20, 10.0), (0.20, 25.0))


def acceptable(m: list, pop: np.ndarray, T: np.ndarray, share: float, minutes: float) -> bool:
    m = np.asarray(m)
    seat = m[np.argmax(pop[m])]
    return bool(np.all(pop[m] / pop[m].sum() >= share) and np.all(T[m, seat] <= minutes))


def rule(t: np.ndarray, adj: set, pop: np.ndarray, limit: float, ok) -> tuple[list[int], int]:
    """pareto.threshold_rule, skipping merges whose resulting unit fails ok(members)."""
    t = t.copy()
    n = len(t)
    label = list(range(n))
    size = pop.astype(float).copy()
    members = {i: [i] for i in range(n)}
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
        cand = [j for j in nb[i] if ok is None or ok(members[i] + members[j])]
        if not cand:
            stuck.add(i)
            continue
        o, d = t.sum(1), t.sum(0)
        j = max(cand, key=lambda j: (t[i, j] / (o[i] * d[j]) + t[j, i] / (o[j] * d[i]), -j))
        keep, gone = min(i, j), max(i, j)
        t[keep, :] += t[gone, :]
        t[:, keep] += t[:, gone]
        t[gone, :] = 0
        t[:, gone] = 0
        size[keep] += size[gone]
        members[keep] += members.pop(gone)
        alive.remove(gone)
        stuck.discard(gone)
        stuck.discard(keep)  # a grown unit may now accept partners it refused before
        nb[keep] = (nb[keep] | nb.pop(gone)) - {keep, gone}
        for k in nb[keep]:
            nb[k].discard(gone)
            nb[k].add(keep)
        label = [keep if l == gone else l for l in label]
    return label, sum(size[i] < limit for i in alive)


def main() -> None:
    rows, t, adj = regions.load()
    gkz = [r["gkz"] for r in rows]
    adm = {r["gkz"]: r for r in csv.DictReader((OUT / "administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[g]["population"]) for g in gkz])
    cost = np.array([float(adm[g]["net"]) for g in gkz])
    curve = np.loadtxt(OUT / "cost_curve_net.csv", delimiter=",", skiprows=1)
    lc = lambda p: np.interp(np.log(p), np.log(curve[:, 0]), np.log(curve[:, 1]))  # noqa: E731
    ix = {g: i for i, g in enumerate(gkz)}
    tr = list(csv.reader((OUT / "travel_time_seat.csv").open(encoding="utf-8")))
    order = [ix[g] for g in tr[0][1:]]
    T = np.zeros((len(gkz),) * 2)
    for r in tr[1:]:
        T[ix[r[0]], order] = [float(v) for v in r[1:]]
    flows = [(ix[r["from_gkz"]], ix[r["to"]], int(r["count"])) for r in csv.DictReader((OUT / "commuters_2024.csv").open(encoding="utf-8")) if r["to"] in ix]
    fa, fb, fw = (np.array(x) for x in zip(*flows))
    el = {r["gkz"]: r for r in elections.load(2025)}
    wb = np.array([float(el[g]["w"]) for g in gkz])
    b = elections.logit(np.log(wb), np.array([el[g]["A"] for g in gkz], float))

    def score(lab) -> dict:
        lab = np.asarray(lab)
        e = tt = w_open = 0.0
        bad_units = bad_pop = 0
        for u in np.unique(lab):
            m = np.where(lab == u)[0]
            seat = m[np.argmax(pop[m])]
            tt += np.sum(pop[m] * T[m, seat])
            w = wb[m].sum()
            w_open += w * (1 - 1 / (1 + np.exp(-(b[0] + b[1] * np.log(w)))))
            if len(m) > 1:
                e += np.sum(cost[m] * (1 - np.exp(lc(pop[m].sum()) - lc(pop[m]))))
                if not acceptable(list(m), pop, T, *MAIN):
                    bad_units += 1
                    bad_pop += pop[m].sum()
        return {"k": len(np.unique(lab)), "E": e * pareto.SCALE_MAIN, "F": fw[lab[fa] == lab[fb]].sum() / fw.sum(), "T": tt / pop.sum(), "W": w_open / wb.sum(), "bad": bad_units, "bad_pop": bad_pop / pop.sum()}

    lines = ["1. threshold rules without condition: units with a merger | of these not acceptable voluntarily (20 %, 15 min) | share of inhabitants in them"]
    base = {}
    for lim in LIMITS:
        lab, _ = rule(t, adj, pop, lim, None)
        assert lab == pareto.threshold_rule(t, adj, pop, lim)
        s = score(lab)
        base[lim] = s
        merged = sum(1 for u in set(lab) if lab.count(u) > 1)
        lines.append(f"   Threshold {lim}: {merged} | {s['bad']} | {s['bad_pop']:.1%}")

    lines.append("\n2./3. threshold rule with condition | share | minutes | k | below threshold | E m EUR (share of without condition) | F | T min | without contested election")
    for lim in LIMITS:
        s = base[lim]
        lines.append(f"   Threshold {lim} without condition       {s['k']:>3}    -  {s['E'] / 1e6:5.2f} (100%)  {s['F']:.3f}  {s['T']:5.2f}  {s['W']:.1%}")
        for share, mins in (MAIN,) + SWITCHES:
            lab, below = rule(t, adj, pop, lim, lambda m, a=share, c=mins: acceptable(m, pop, T, a, c))
            s = score(lab)
            tag = "main case" if (share, mins) == MAIN else "switch"
            lines.append(f"   Threshold {lim} {share:.0%} {mins:>4.0f} min {tag:9} {s['k']:>3}  {below:>3}  {s['E'] / 1e6:5.2f} ({s['E'] / base[lim]['E']:.0%})  {s['F']:.3f}  {s['T']:5.2f}  {s['W']:.1%}")
    s0 = score(list(range(len(gkz))))
    lines.append(f"\nStatus quo: without contested election predicted {s0['W']:.1%}")
    text = "\n".join(lines)
    print(text)
    (OUT / "voluntary.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
