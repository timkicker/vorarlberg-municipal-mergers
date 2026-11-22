"""Travel time to the seat over the OSM road network instead of straight lines.

The 5 km margin is taken as the bounding box of the state buffered by 5 km,
which is a little wider than the buffer itself. Points are snapped to the
nearest component with at least MIN_COMP nodes.
"""

import csv
import json
import pathlib
import sys

import networkx as nx
import numpy as np
import osmium
import pyproj
from scipy import sparse
from scipy.sparse import csgraph
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from shapely.geometry import Point, shape
from shapely.ops import unary_union

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pareto  # noqa: E402
import regions  # noqa: E402

RAW, OUT = pareto.RAW, pareto.OUT
PBF = RAW / "osm_austria_261119.osm.pbf"
CACHE = RAW / "osm_vbg_roads.npz"
SPEED = {"motorway": 100, "trunk": 80, "primary": 70, "secondary": 60, "tertiary": 50, "unclassified": 40, "residential": 30, "living_street": 10}
LINK = 50
PLACES = {"town", "village", "city"}
FALLBACK_KMH, DETOUR = 40, 1.5
MIN_COMP = 1000
COL_MUNICIPALITY = "gemeinde"  # municipality name column in vbg_regional_divisions.csv of data.vorarlberg.gv.at


def speed(tag: str) -> float | None:
    if tag.endswith("_link") and tag[:-5] in SPEED:
        return LINK
    return SPEED.get(tag)


def extract(bbox) -> None:
    lon0, lat0, lon1, lat1 = bbox
    inside = lambda loc: lon0 <= loc.lon <= lon1 and lat0 <= loc.lat <= lat1  # noqa: E731
    edges, places = [], []
    for o in osmium.FileProcessor(str(PBF)).with_locations().with_filter(osmium.filter.KeyFilter("highway", "place")):
        if o.is_node() and o.tags.get("place") in PLACES and inside(o.location):
            places.append((o.tags.get("name", ""), o.location.lon, o.location.lat))
        elif o.is_way():
            v = speed(o.tags.get("highway", ""))
            if v is None:
                continue
            nodes = [(n.ref, n.lon, n.lat) for n in o.nodes if n.location.valid()]
            for (a, xa, ya), (b, xb, yb) in zip(nodes, nodes[1:]):
                if inside(osmium.osm.Location(xa, ya)) or inside(osmium.osm.Location(xb, yb)):
                    edges.append((a, b, xa, ya, xb, yb, v))
    e = np.array([x[2:] for x in edges], float)
    ids = np.array([x[:2] for x in edges], np.int64)
    np.savez_compressed(CACHE, e=e, ids=ids, pnames=np.array([p[0] for p in places]), pxy=np.array([p[1:] for p in places], float))


def main() -> None:
    rows, t, adj = regions.load()
    gkz = [r["gkz"] for r in rows]
    n = len(gkz)
    geo = json.loads((RAW / "boundaries_statat_2026.geojson").read_text())
    polys = {f["properties"]["g_id"]: shape(f["geometry"]) for f in geo["features"] if f["properties"]["g_id"] in set(gkz)}
    # boundaries are in EPSG:31287 (metres), OSM in degrees
    to_m = pyproj.Transformer.from_crs(4326, 31287, always_xy=True).transform
    to_deg = pyproj.Transformer.from_crs(31287, 4326, always_xy=True).transform
    x0, y0, x1, y1 = unary_union(list(polys.values())).buffer(5000).bounds
    lons, lats = to_deg([x0, x0, x1, x1], [y0, y1, y0, y1])
    bbox = (min(lons), min(lats), max(lons), max(lats))
    if not CACHE.exists():
        extract(bbox)
    z = np.load(CACHE)
    e, ids = z["e"], z["ids"]
    node_ids, inv = np.unique(ids.ravel(), return_inverse=True)
    inv = inv.reshape(-1, 2)
    xa, ya = to_m(e[:, 0], e[:, 1])
    xb, yb = to_m(e[:, 2], e[:, 3])
    minutes = np.hypot(xa - xb, ya - yb) / 1000 / e[:, 4] * 60
    nxy = np.zeros((len(node_ids), 2))
    nxy[inv[:, 0]] = np.column_stack([xa, ya])
    nxy[inv[:, 1]] = np.column_stack([xb, yb])
    a, b = inv.min(1), inv.max(1)
    ok = a != b
    best = {}
    for i, j, w in zip(a[ok], b[ok], np.maximum(minutes[ok], 1e-6)):
        if w < best.get((i, j), np.inf):
            best[(i, j)] = w
    ij = np.array(list(best), np.int64)
    m = sparse.coo_matrix((list(best.values()), (ij[:, 0], ij[:, 1])), shape=(len(node_ids),) * 2).tocsr()  # upper triangle, one entry per pair
    ncomp, comp = csgraph.connected_components(m, directed=False)
    # snap to the nearest node of any component with at least MIN_COMP nodes: snapping only to
    # the largest one bridged Mittelberg over the ridge (6 km) although its roads only reach
    # the rest of the state through Germany, outside the extract
    keep = np.where(np.bincount(comp)[comp] >= MIN_COMP)[0]
    tree = cKDTree(nxy[keep])

    pnames, pxy = z["pnames"], z["pxy"]
    ref = json.loads((RAW / "boundaries_statat_2026.geojson").read_text())
    rep = {f["properties"]["g_id"]: shape(f["geometry"]).representative_point() for f in ref["features"]}
    pts, fallback = [], []
    for r in rows:
        g = r["gkz"]
        cand = [to_m(x, y) for name, (x, y) in zip(pnames, pxy) if name == r[COL_MUNICIPALITY]]
        cand = [c for c in cand if polys[g].contains(Point(*c))]
        if cand:
            pts.append(cand[0])
        else:
            fallback.append(r[COL_MUNICIPALITY])
            pts.append((rep[g].x, rep[g].y))
    px, py = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    snap_d, snap_i = tree.query(np.column_stack([px, py]))
    src = keep[snap_i]
    T = csgraph.dijkstra(m, directed=False, indices=src)[:, src]
    air = np.hypot(px[:, None] - px[None, :], py[:, None] - py[None, :]) / 1000
    unreachable = np.isinf(T)
    T[unreachable] = air[unreachable] * DETOUR / FALLBACK_KMH * 60
    main_comp = np.bincount(comp).argmax()
    bad = sorted(rows[i][COL_MUNICIPALITY] for i in range(n) if comp[src[i]] != main_comp)

    adm = {r["gkz"]: r for r in csv.DictReader((OUT / "administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[g]["population"]) for g in gkz])
    gr = nx.Graph()
    gr.add_nodes_from(range(n))
    gr.add_edges_from(adj)
    cands, _ = pareto.candidates(rows, t, adj, pop, gr)
    old = {r["name"]: r for r in csv.DictReader((OUT / "pareto_candidates.csv").open(encoding="utf-8"))}
    names = list(cands)
    assert set(names) == set(old)

    def tt(lab) -> float:
        lab = np.asarray(lab)
        s = 0.0
        for u in np.unique(lab):
            mm = np.where(lab == u)[0]
            seat = mm[np.argmax(pop[mm])]
            s += np.sum(pop[mm] * T[mm, seat])
        return s / pop.sum()

    Tv = np.array([tt(cands[x]) for x in names])
    E = np.array([float(old[x]["E_main"]) for x in names])
    F = np.array([float(old[x]["F"]) for x in names])
    D = np.array([float(old[x]["D_km"]) for x in names])
    front_old = {x for x in names if old[x]["front_beeline"] == "1"}
    front_new = set()
    for i, x in enumerate(names):
        dom = (E >= E[i]) & (F >= F[i]) & (Tv <= Tv[i]) & ((E > E[i]) | (F > F[i]) | (Tv < Tv[i]))
        if not dom.any():
            front_new.add(x)
    rho = spearmanr(D, Tv).statistic

    lines = [
        f"road graph: {len(node_ids):,} nodes, {len(e):,} edges, components {ncomp}, of these with at least {MIN_COMP} nodes: {sorted(np.bincount(comp)[np.bincount(comp) >= MIN_COMP].tolist(), reverse=True)}",
        f"settlement points without a matching place node (substitute point): {len(fallback)} {fallback}",
        f"distance settlement point to road node: median {np.median(snap_d):.0f} m, max {snap_d.max():.0f} m",
        f"outside the largest component, to all others substitute beeline x {DETOUR} at {FALLBACK_KMH} km/h: {bad}, pairs {int(unreachable.sum() // 2)}",
        f"\nSpearman D (beeline) against T (drive time) over {len(names)} candidates: {rho:.3f}",
        f"front old {len(front_old)}, front new {len(front_new)}, on both {len(front_old & front_new)} ({len(front_old & front_new) / len(front_old):.0%} of the old)",
        "\nnamed variants: D km | T min | front old | front new",
    ]
    for x in names:
        if x.startswith("random") or (x.startswith("Intramax") and int(x.split("=")[1]) not in (1, 2, 4, 8, 10, 19, 30, 40, 50, 60, 70, 80, 90)):
            continue
        lines.append(f"  {x:38} {D[names.index(x)]:6.2f} {Tv[names.index(x)]:6.2f}  {'yes' if x in front_old else 'no '}  {'yes' if x in front_new else 'no'}")
    cols = [c for c in next(iter(old.values())) if c not in ("T_min", "front")]
    with (OUT / "pareto_candidates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols + ["T_min", "front"])
        for i, x in enumerate(names):
            w.writerow([old[x][c] for c in cols] + [f"{Tv[i]:.3f}", int(x in front_new)])
    with (OUT / "travel_time_seat.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["from_gkz"] + gkz)
        for i, g in enumerate(gkz):
            w.writerow([g] + [f"{v:.1f}" for v in T[i]])
    text = "\n".join(lines)
    print(text)
    (OUT / "travel_time.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
