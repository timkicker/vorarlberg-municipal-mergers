"""Do the 2016 cooperations follow official regions more than commuter regions?

Null partitions are drawn by random region
growing: regions are grown one after another, largest first, from a random
seed next to the area already assigned, by adding random frontier
municipalities. A region is kept only if the unassigned rest can still be
split into the remaining sizes; otherwise it is redrawn. This is not a uniform sample over all contiguous partitions, it is a
reproducible random baseline with the same sizes and contiguity.
"""

import collections
import csv
import itertools
import pathlib
import random
import sys

import networkx as nx
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
N_NULL, N_BOOT, SEED = 1000, 2000, 12345
# columns of vbg_regional_divisions.csv of data.vorarlberg.gv.at
COL_PLANNING_REGION = "planungsregion"  # planning region
COL_REGION = "region"  # region
PAIRS = (("planning_region", "k19"), ("region", "k8"))
# type codes in the table of the 2016 study and words in record names that mark regional bodies
CIRCULAR_TYPES = {"Ü", "G"}
REGIONAL_PLANNING = "Regionalplanung"  # regional planning
REGIO = "Regio"  # name part of the regional associations


def subset_sums_ok(comp_sizes: list[int], sizes: list[int]) -> bool:
    """Can components of the given sizes be filled exactly with the remaining region sizes?"""
    sizes = sorted(sizes, reverse=True)
    comps = sorted(comp_sizes, reverse=True)
    if sum(comps) != sum(sizes):
        return False

    def place(i, free):
        if i == len(sizes):
            return True
        seen = set()
        for c in range(len(free)):
            if free[c] >= sizes[i] and free[c] not in seen:
                seen.add(free[c])
                free[c] -= sizes[i]
                if place(i + 1, free):
                    return True
                free[c] += sizes[i]
        return False

    return place(0, comps)


def grow(g, free: set, size: int, seed, rng: random.Random) -> set | None:
    region = {seed}
    frontier = set(g[seed]) & free
    while len(region) < size and frontier:
        v = rng.choice(sorted(frontier))
        region.add(v)
        frontier = (frontier | set(g[v])) & (free - region)
    return region if len(region) == size else None


def random_partition(g: nx.Graph, sizes: list[int], rng: random.Random, tries: int = 50) -> dict:
    """Grow regions largest first. Seeds lie next to the area already assigned,
    so the rest stays in few pieces. A region that leaves an unsplittable rest
    is redrawn up to `tries` times before the whole partition starts over."""
    order = sorted(sizes, reverse=True)
    while True:
        free, label, done = set(g), {}, True
        for r, size in enumerate(order):
            rest = order[r + 1 :]
            edge = sorted({u for v in label for u in g[v]} & free) or sorted(free)
            for _ in range(tries):
                region = grow(g, free, size, rng.choice(edge), rng)
                if region is None:
                    continue
                comps = [len(c) for c in nx.connected_components(g.subgraph(free - region))]
                if subset_sums_ok(comps, rest):
                    break
            else:
                done = False
                break
            free -= region
            for v in region:
                label[v] = r
        if done:
            return label


def main() -> None:
    n_null = int(sys.argv[1]) if len(sys.argv) > 1 else N_NULL
    gl = list(csv.DictReader((RAW / "vbg_regional_divisions.csv").open(encoding="utf-8"), delimiter=";"))
    gkz = [r["gkz"] for r in gl]
    ix = {g: i for i, g in enumerate(gkz)}
    g = nx.Graph((r["gkz_a"], r["gkz_b"]) for r in csv.DictReader((OUT / "neighbours.csv").open(encoding="utf-8")) if r["neighbour"] == "1")
    intramax = {r["gkz"]: r for r in csv.DictReader((OUT / "intramax_regions.csv").open(encoding="utf-8"))}
    import json

    recs = {str(r["id"]): r for r in json.loads((OUT / "coop2016.json").read_text())}
    members = collections.defaultdict(set)
    for r in csv.DictReader((OUT / "coop2016_members.csv").open(encoding="utf-8")):
        members[r["coop_id"]].add(r["gkz"])
    coops = sorted(k for k, m in members.items() if 2 <= len(m) < 90)

    def circular(k):
        r = recs[k]
        return r["type"] in CIRCULAR_TYPES or REGIONAL_PLANNING in r["name"] or REGIO in r["name"]

    partitions = {
        "planning_region": {r["gkz"]: r[COL_PLANNING_REGION] for r in gl},
        "region": {r["gkz"]: r[COL_REGION] for r in gl},
        "k19": {k: v["k19"] for k, v in intramax.items()},
        "k8": {k: v["k8"] for k, v in intramax.items()},
    }
    rng = random.Random(SEED)
    nulls = {}
    for name, p in partitions.items():
        sizes = list(collections.Counter(p.values()).values())
        nulls[name] = [random_partition(g, sizes, rng) for _ in range(n_null)]
        print("null partitions", name, len(nulls[name]), file=sys.stderr)

    def within_matrix(labels: list[dict]) -> np.ndarray:
        """records x partitions: weight of each cooperation inside regions."""
        lab = np.array([[hash(l[x]) for x in gkz] for l in labels])
        out = np.zeros((len(coops), len(labels)))
        for a, k in enumerate(coops):
            m = [ix[x] for x in sorted(members[k])]
            xi, yi = np.array(list(itertools.combinations(m, 2))).T
            out[a] = (lab[:, xi] == lab[:, yi]).sum(1) / (len(m) - 1)
        return out

    total = np.array([len(members[k]) / 2 for k in coops])  # n(n-1)/2 pairs * 1/(n-1)
    mats = {name: within_matrix([partitions[name]] + nulls[name]) for name in partitions}
    brng = np.random.default_rng(SEED)
    boot = brng.multinomial(len(coops), np.full(len(coops), 1 / len(coops)), size=N_BOOT)

    lines = []
    for run, keep in (("all", np.ones(len(coops), bool)), ("without Regios/Leader", np.array([not circular(k) for k in coops]))):
        lines.append(f"\nrun {run}: {keep.sum()} cooperations")
        exc = {}
        for name, m in mats.items():
            mm, tt = m[keep], total[keep]
            s = mm.sum(0) / tt.sum()
            obs, null = s[0], s[1:]
            p = (np.sum(null >= obs) + 1) / (len(null) + 1)
            cb = boot[:, keep]
            sb = (cb @ mm) / (cb @ tt)[:, None]
            exc[name] = sb[:, 0] - sb[:, 1:].mean(1)
            lines.append(f"  {name:15} S {obs:.3f}  null mean {null.mean():.3f}  null max {null.max():.3f}  E {obs - null.mean():+.3f}  p {p:.4f}")
        for off, fun in PAIRS:
            d = exc[off] - exc[fun]
            lo, hi = np.percentile(d, [2.5, 97.5])
            verdict = "supported" if lo > 0 else "rejected" if hi < 0 else "undecided"
            lines.append(f"  D {off} - {fun}: {np.mean(d):+.3f}  95 % [{lo:+.3f}, {hi:+.3f}]  {verdict}")
    text = "\n".join(lines)
    print(text)
    (OUT / "coop_areas.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
