"""Functional regions from commuter flows with Intramax under contiguity.

Intramax (Masser and Brown 1975) merges, step by step, the pair of regions
with the largest relative interaction
    T_ij / (O_i * D_j) + T_ji / (O_j * D_i),
where O and D are row and column totals of the flow matrix. Here only pairs
that share a border (data/derived/neighbours.csv, neighbour = 1) may merge, so
every region is contiguous. The matrix holds flows between the 96
municipalities plus non-commuters on the diagonal; flows abroad and to the
rest of Austria are left out of the totals. The procedure is deterministic.

The resulting partitions are compared with official groupings by the
adjusted Rand index. Three checks against the main result go to
data/derived/regions_robustness.txt: no diagonal, borders that touch in a
single point count as neighbours, and flows changed at random by up to 10 %.
"""

import csv
import pathlib
import sys
from math import comb

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
CUTS = (4, 8, 10, 19)
SEED, N_NOISE, NOISE = 12345, 20, 0.10
# Columns of vbg_regional_divisions.csv of data.vorarlberg.gv.at
COL_MUNICIPALITY = "gemeinde"  # municipality name
COL_DISTRICT = "bezirk"  # district
COL_PLANNING_REGION = "planungsregion"  # planning region
COMPARE = (COL_DISTRICT, "region", "region.str.fein", COL_PLANNING_REGION, "care.management.region")
COMPARE_NAME = {COL_DISTRICT: "district", COL_PLANNING_REGION: "planning region"}  # printed names


def ari(a: list, b: list) -> float:
    pairs = {}
    for x, y in zip(a, b):
        pairs[(x, y)] = pairs.get((x, y), 0) + 1
    ca, cb = {}, {}
    for (x, y), n in pairs.items():
        ca[x] = ca.get(x, 0) + n
        cb[y] = cb.get(y, 0) + n
    idx = sum(comb(n, 2) for n in pairs.values())
    sa, sb = sum(comb(n, 2) for n in ca.values()), sum(comb(n, 2) for n in cb.values())
    exp = sa * sb / comb(len(a), 2)
    return (idx - exp) / ((sa + sb) / 2 - exp)


def point_contacts(ix: dict) -> set:
    """Pairs whose borders touch in a single point (neighbour = 0 in neighbours.csv)."""
    return {(ix[r["gkz_a"]], ix[r["gkz_b"]]) for r in csv.DictReader((OUT / "neighbours.csv").open(encoding="utf-8")) if r["neighbour"] == "0"}


def robustness(rows: list, t: np.ndarray, adj: set, parts: dict) -> str:
    n = len(rows)
    ix = {r["gkz"]: i for i, r in enumerate(rows)}
    no_diag = t.copy()
    np.fill_diagonal(no_diag, 0)
    variants = {"no diagonal": intramax(no_diag, adj), "with point contacts": intramax(t, adj | point_contacts(ix))}
    rng = np.random.default_rng(SEED)
    off = ~np.eye(n, dtype=bool)
    noisy = []
    for _ in range(N_NOISE):
        tn = t.copy()
        tn[off] = t[off] * rng.uniform(1 - NOISE, 1 + NOISE, off.sum())
        noisy.append(intramax(tn, adj))
    out = ["Intramax regions, adjusted Rand index against the main result (regions.py)",
           f"flows changed at random by up to {NOISE:.0%}: {N_NOISE} runs, seed {SEED}", "",
           "regions | no diagonal | with point contacts | flows changed, min / median"]
    for k in CUTS:
        a = [ari(parts[k], cut(n, m, k)) for m in variants.values()]
        z = [ari(parts[k], cut(n, m, k)) for m in noisy]
        out.append(f"{k} | {a[0]:.2f} | {a[1]:.2f} | {min(z):.2f} / {float(np.median(z)):.2f}")
    return "\n".join(out)


def load():
    rows = list(csv.DictReader((RAW / "vbg_regional_divisions.csv").open(encoding="utf-8"), delimiter=";"))
    gkz = [r["gkz"] for r in rows]
    ix = {g: i for i, g in enumerate(gkz)}
    t = np.zeros((len(gkz), len(gkz)))
    for r in csv.DictReader((OUT / "commuters_2024.csv").open(encoding="utf-8")):
        if r["to"] in ix:
            t[ix[r["from_gkz"]], ix[r["to"]]] = int(r["count"])
    for r in csv.DictReader((OUT / "commuters_2024_municipalities.csv").open(encoding="utf-8")):
        t[ix[r["gkz"]], ix[r["gkz"]]] = int(r["non_commuters"])
    adj = {(ix[r["gkz_a"]], ix[r["gkz_b"]]) for r in csv.DictReader((OUT / "neighbours.csv").open(encoding="utf-8")) if r["neighbour"] == "1"}
    return rows, t, adj


def intramax(t: np.ndarray, adj: set, isolated: frozenset = frozenset()) -> list[tuple[int, int, float]]:
    """Return the merge sequence (kept, absorbed, objective). Cluster ids are row indices.

    Nodes in `isolated` have no neighbours, never merge and only enter the row and column totals.
    """
    t = t.copy()
    alive = set(range(len(t))) - set(isolated)
    nb = {i: set() for i in alive}
    nb.update({i: set() for i in isolated})
    for a, b in adj:
        nb[a].add(b)
        nb[b].add(a)
    merges = []
    while len(alive) > 1:
        o, d = t.sum(1), t.sum(0)
        best = None
        for i in alive:
            for j in nb[i]:
                if j <= i:
                    continue
                v = t[i, j] / (o[i] * d[j]) + t[j, i] / (o[j] * d[i])
                if best is None or v > best[2]:
                    best = (i, j, v)
        if best is None:
            raise SystemExit("neighbour graph not connected")
        i, j, v = best
        t[i, :] += t[j, :]
        t[:, i] += t[:, j]
        t[j, :] = 0
        t[:, j] = 0
        alive.remove(j)
        nb[i] |= nb.pop(j)
        nb[i] -= {i, j}
        for k in nb[i]:
            nb[k].discard(j)
            nb[k].add(i)
        merges.append((i, j, v))
    return merges


def cut(n: int, merges: list, k: int) -> list[int]:
    parent = list(range(n))
    for i, j, _ in merges[: n - k]:
        parent[j] = i

    def root(x):
        while parent[x] != x:
            x = parent[x]
        return x

    return [root(x) for x in range(n)]


def main() -> None:
    rows, t, adj = load()
    n = len(rows)
    merges = intramax(t, adj)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "intramax_steps.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["step", "regions_after", "stays", "absorbed", "objective"])
        for s, (i, j, v) in enumerate(merges, 1):
            w.writerow([s, n - s, rows[i][COL_MUNICIPALITY], rows[j][COL_MUNICIPALITY], f"{v:.6g}"])
    parts = {k: cut(n, merges, k) for k in CUTS}
    with (OUT / "intramax_regions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gkz", "municipality"] + [f"k{k}" for k in CUTS])
        for x, r in enumerate(rows):
            w.writerow([r["gkz"], r[COL_MUNICIPALITY]] + [rows[parts[k][x]][COL_MUNICIPALITY] for k in CUTS])
    text = robustness(rows, t, adj, parts)
    print(text)
    (OUT / "regions_robustness.txt").write_text(text + "\n")
    print("ARI       " + "  ".join(f"{COMPARE_NAME.get(c, c)[:14]:>14}" for c in COMPARE))
    for k in CUTS:
        print(f"k={k:<3}    " + "  ".join(f"{ari(parts[k], [r[c] for r in rows]):>14.2f}" for c in COMPARE))
    for k in (4, 8):
        groups = {}
        for x, r in enumerate(rows):
            groups.setdefault(rows[parts[k][x]][COL_MUNICIPALITY], []).append(r[COL_MUNICIPALITY])
        print(f"\nk={k}")
        for head, ms in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            print(f"  {head} ({len(ms)}): {', '.join(ms)}")


if __name__ == "__main__":
    sys.exit(main())
