"""Partitions of Vorarlberg on a Pareto front of savings, commuter coherence and distance."""

import collections
import csv
import itertools
import json
import pathlib
import random
import sys

import networkx as nx
import numpy as np
from shapely.geometry import shape

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import regions  # noqa: E402
from accounts_columns import COL_EXTRAORDINARY_SPENDING, COL_ORDINARY_SPENDING
from coop_areas import random_partition  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
SEED = 12345
N_RANDOM = 2000
# Styrian effect on the elected bodies over the cost curve prediction of -0.255 (styria.txt): main run -0.145
# against the unchanged Styrian units (styria_control.txt), low run -0.040 against the other states only (styria.txt)
SCALE_MAIN, SCALE_LOW = 0.145 / 0.255, 0.040 / 0.255
THRESHOLDS = (500, 1000, 2000, 3500, 5000)
# Columns of vbg_regional_divisions.csv of data.vorarlberg.gv.at
COL_MUNICIPALITY = "gemeinde"  # municipality name
COL_DISTRICT = "bezirk"  # district
COL_PLANNING_REGION = "planungsregion"  # planning region
OFFICIAL = (COL_DISTRICT, "region", "region.str.fein", COL_PLANNING_REGION, "care.management.region")
OFFICIAL_NAME = {COL_DISTRICT: "district", "region": "region", "region.str.fein": "fine region",
                 COL_PLANNING_REGION: "planning region", "care.management.region": "care management region"}


def threshold_rule(t: np.ndarray, adj: set, pop: np.ndarray, limit: float) -> list[int]:
    """Merge the smallest unit below `limit` with the neighbour of highest Intramax value."""
    t = t.copy()
    n = len(t)
    label = list(range(n))
    size = pop.astype(float).copy()
    alive = set(range(n))
    nb = {i: set() for i in alive}
    for a, b in adj:
        nb[a].add(b)
        nb[b].add(a)
    while True:
        small = [i for i in alive if size[i] < limit and nb[i]]
        if not small:
            break
        i = min(small, key=lambda x: (size[x], x))
        o, d = t.sum(1), t.sum(0)
        j = max(nb[i], key=lambda j: (t[i, j] / (o[i] * d[j]) + t[j, i] / (o[j] * d[i]), -j))
        keep, gone = min(i, j), max(i, j)
        t[keep, :] += t[gone, :]
        t[:, keep] += t[:, gone]
        t[gone, :] = 0
        t[:, gone] = 0
        size[keep] += size[gone]
        alive.remove(gone)
        nb[keep] = (nb[keep] | nb.pop(gone)) - {keep, gone}
        for k in nb[keep]:
            nb[k].discard(gone)
            nb[k].add(keep)
        label = [keep if l == gone else l for l in label]
    return label


def candidates(rows: list, t: np.ndarray, adj: set, pop: np.ndarray, g: nx.Graph) -> tuple[dict, list]:
    """All candidate partitions, deterministic given SEED."""
    n = len(rows)
    cands = {"Status quo": list(range(n))}
    merges = regions.intramax(t, adj)
    for k in range(1, n):
        cands[f"Intramax k={k}"] = regions.cut(n, merges, k)
    for lim in THRESHOLDS:
        cands[f"Threshold {lim}"] = threshold_rule(t, adj, pop, lim)
    skipped = []
    for col in OFFICIAL:
        lab = [r[col] for r in rows]
        parts = collections.defaultdict(list)
        for i, l in enumerate(lab):
            parts[l].append(i)
        if all(nx.is_connected(g.subgraph(m)) for m in parts.values()):
            cands[f"official {OFFICIAL_NAME[col]}"] = lab
        else:
            skipped.append(col)
    rng = random.Random(SEED)
    for r in range(N_RANDOM):
        k = rng.randint(4, 95)
        cuts = sorted(rng.sample(range(1, n), k - 1))
        sizes = [b - a for a, b in zip([0] + cuts, cuts + [n])]
        lab = random_partition(g, sizes, rng)
        cands[f"random {r}"] = [lab[i] for i in range(n)]
    return cands, skipped


def main() -> None:
    rows, t, adj = regions.load()
    gkz = [r["gkz"] for r in rows]
    n = len(gkz)
    ix = {g: i for i, g in enumerate(gkz)}
    adm = {r["gkz"]: r for r in csv.DictReader((OUT / "administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[g]["population"]) for g in gkz])
    cost = np.array([float(adm[g]["net"]) for g in gkz])
    curve = np.loadtxt(OUT / "cost_curve_net.csv", delimiter=",", skiprows=1)
    lc = lambda p: np.interp(np.log(p), np.log(curve[:, 0]), np.log(curve[:, 1]))  # noqa: E731  # constant outside
    geo = json.loads((RAW / "boundaries_statat_2026.geojson").read_text())
    pts = {f["properties"]["g_id"]: shape(f["geometry"]).representative_point() for f in geo["features"]}
    xy = np.array([[pts[g].x, pts[g].y] for g in gkz])
    flows = [(ix[r["from_gkz"]], ix[r["to"]], int(r["count"])) for r in csv.DictReader((OUT / "commuters_2024.csv").open(encoding="utf-8")) if r["to"] in ix]
    fa, fb, fw = (np.array(x) for x in zip(*flows))
    members = collections.defaultdict(set)
    for r in csv.DictReader((OUT / "coop2016_members.csv").open(encoding="utf-8")):
        members[r["coop_id"]].add(ix[r["gkz"]])
    coops = [sorted(m) for m in members.values() if 2 <= len(m) < 90]
    pairs = [(np.array([a for a, _ in itertools.combinations(m, 2)]), np.array([b for _, b in itertools.combinations(m, 2)]), len(m)) for m in coops]
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(adj)

    def score(lab: list) -> dict:
        lab = np.asarray(lab)
        e = 0.0
        dist = 0.0
        for u in np.unique(lab):
            m = np.where(lab == u)[0]
            seat = m[np.argmax(pop[m])]
            dist += np.sum(pop[m] * np.hypot(*(xy[m] - xy[seat]).T)) / 1000
            if len(m) > 1:
                e += np.sum(cost[m] * (1 - np.exp(lc(pop[m].sum()) - lc(pop[m]))))
        f = fw[lab[fa] == lab[fb]].sum() / fw.sum()
        s = sum((lab[a] == lab[b]).sum() / (k - 1) for a, b, k in pairs) / sum(k / 2 for *_, k in pairs)
        sizes = collections.Counter(lab.tolist())
        return {"k": len(sizes), "E_main": e * SCALE_MAIN, "E_low": e * SCALE_LOW, "F": f, "D": dist / pop.sum(), "S": s, "min_pop": min(pop[lab == u].sum() for u in sizes)}

    cands, skipped = candidates(rows, t, adj, pop, g)

    res = {name: score(lab) for name, lab in cands.items()}
    names = list(res)
    E = np.array([res[x]["E_main"] for x in names])
    F = np.array([res[x]["F"] for x in names])
    D = np.array([res[x]["D"] for x in names])
    front = set()
    for i in range(len(names)):
        dom = (E >= E[i]) & (F >= F[i]) & (D <= D[i]) & ((E > E[i]) | (F > F[i]) | (D < D[i]))
        if not dom.any():
            front.add(names[i])

    total = []
    for r in csv.DictReader((RAW / "gemhh_at_2000_2019.csv").open(encoding="utf-8"), delimiter=";"):
        if r["C-C41-2"].startswith("8") and r["C-A10-0"] in {f"A10-{y}" for y in (2016, 2017, 2018, 2019)}:
            total.append((r["C-A10-0"], float(r[COL_ORDINARY_SPENDING]) + float(r[COL_EXTRAORDINARY_SPENDING])))
    per_year = sum(v for _, v in total) / 4
    best_low = max(res[x]["E_low"] for x in front)

    with (OUT / "pareto_candidates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "k", "E_main", "E_low", "F", "D_km", "S", "min_pop", "front_beeline"])  # roads.py adds T_min and front
        for x in names:
            v = res[x]
            w.writerow([x, v["k"], round(v["E_main"]), round(v["E_low"]), f"{v['F']:.4f}", f"{v['D']:.3f}", f"{v['S']:.4f}", round(v["min_pop"]), int(x in front)])
    with (OUT / "pareto_partitions.csv").open("w", newline="", encoding="utf-8") as f:
        named = [x for x in names if not x.startswith("random")]
        w = csv.writer(f)
        w.writerow(["gkz", "municipality"] + named)
        for i, r in enumerate(rows):
            w.writerow([r["gkz"], r[COL_MUNICIPALITY]] + [rows[cands[x][i]][COL_MUNICIPALITY] if isinstance(cands[x][i], (int, np.integer)) else cands[x][i] for x in named])

    lines = ["Front here with beeline distance (D km). The front of the paper with drive time is set by roads.py, column front in pareto_candidates.csv, see travel_time.txt.", f"candidates {len(names)}, on the front with beeline distance {len(front)} (of these random {sum(x.startswith('random') for x in front)})"]
    lines.append(f"official divisions not contiguous, left out: {skipped or 'none'}")
    lines.append(f"spending of the Vorarlberg municipalities 2016-2019, annual mean: {per_year / 1e6:,.1f} m EUR; 1 % = {per_year / 1e8:,.2f} m EUR")
    lines.append(f"largest E on the front with the cautious factor 0.16 (without 2014 it would be 0): {best_low / 1e6:,.2f} m EUR = {best_low / per_year:.2%} of spending")
    lines.append("\nnamed variants: front beeline | k | E 0.57 | E 0.16 (m EUR) | F | D km | S | smallest unit")
    for x in names:
        if x.startswith("random") or (x.startswith("Intramax") and res[x]["k"] not in (1, 2, 4, 8, 10, 19, 30, 40, 50, 60, 70, 80, 90)):
            continue
        v = res[x]
        lines.append(f"  {x:38} {'yes' if x in front else 'no '} {v['k']:>3} {v['E_main'] / 1e6:7.2f} {v['E_low'] / 1e6:7.2f} {v['F']:.3f} {v['D']:6.2f} {v['S']:.3f} {v['min_pop']:>8,.0f}")
    lines.append("\nIntramax cuts on the front: " + ", ".join(str(res[x]["k"]) for x in names if x.startswith("Intramax") and x in front))
    text = "\n".join(lines)
    print(text)
    (OUT / "pareto.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
