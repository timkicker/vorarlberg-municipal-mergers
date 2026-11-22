"""TikZ map panels for the map figure: unit borders and units below 2,000 inhabitants.

Writes data/derived/figures/map_data.tex.
"""

import csv
import json
import pathlib
import sys

import numpy as np
from shapely.geometry import MultiPolygon, shape
from shapely.ops import unary_union

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pareto  # noqa: E402
import regions  # noqa: E402
import voluntary  # noqa: E402

COL_MUNICIPALITY = "gemeinde"  # municipality name column in vbg_regional_divisions.csv of data.vorarlberg.gv.at

OUT, RAW = pareto.OUT, pareto.RAW
FIG = pathlib.Path(__file__).resolve().parents[2] / "data" / "derived" / "figures"
LIMIT = 2000
WIDTH_MM = 48
TOL = 150  # metres, simplification of the drawn outlines
# Place names: four towns for orientation on the first panel, the places the text names on the others.
PLACES = {"status": ["Bregenz", "Dornbirn", "Feldkirch", "Bludenz"], "threshold": [], "voluntary": ["Lech", "Laterns", "Gaißau"]}
ANCHOR = {"Bregenz": "west", "Dornbirn": "west", "Feldkirch": "east", "Bludenz": "west", "Lech": "east", "Laterns": "east", "Gaißau": "west"}


def path(geom, sx, x0, y0) -> str:
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    parts = []
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            c = np.asarray(ring.coords)
            parts.append(" -- ".join(f"({(x - x0) * sx:.2f},{(y - y0) * sx:.2f})" for x, y in c) + " -- cycle")
    return " ".join(parts)


def main() -> None:
    rows, t, adj = regions.load()
    gkz = [r["gkz"] for r in rows]
    geo = json.loads((RAW / "boundaries_statat_2026.geojson").read_text())
    poly = {f["properties"]["g_id"]: shape(f["geometry"]) for f in geo["features"]}
    poly = [poly[g].buffer(0) for g in gkz]
    adm = {r["gkz"]: r for r in csv.DictReader((OUT / "administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[g]["population"]) for g in gkz])
    ix = {g: i for i, g in enumerate(gkz)}
    times = list(csv.reader((OUT / "travel_time_seat.csv").open(encoding="utf-8")))
    order = [ix[g] for g in times[0][1:]]
    T = np.zeros((len(gkz),) * 2)
    for r in times[1:]:
        T[ix[r[0]], order] = [float(v) for v in r[1:]]

    variants = {
        "status": list(range(len(gkz))),
        "threshold": pareto.threshold_rule(t, adj, pop, LIMIT),
        "voluntary": voluntary.rule(t, adj, pop, LIMIT, lambda m: voluntary.acceptable(m, pop, T, *voluntary.MAIN))[0],
    }
    state = unary_union(poly)
    x0, y0, x1, y1 = state.bounds
    sx = WIDTH_MM / (x1 - x0)
    muni = " ".join(path(p.simplify(TOL), sx, x0, y0) for p in poly)
    lines = []
    for name, lab in variants.items():
        lab = np.asarray(lab)
        small, borders, n_small = [], [], 0
        for u in np.unique(lab):
            m = np.where(lab == u)[0]
            shp = unary_union([poly[i] for i in m]).buffer(1).buffer(-1).simplify(TOL)
            borders.append(path(shp, sx, x0, y0))
            if pop[m].sum() < LIMIT:
                small.append(path(shp, sx, x0, y0))
                n_small += 1
        lines.append(f"% {name}: {len(np.unique(lab))} units, {n_small} below {LIMIT}")
        lines.append(f"\\newcommand{{\\map{name}}}{{%")
        if small:
            lines.append(f"\\fill[blu!35] {' '.join(small)};")
        lines.append(f"\\draw[soft!45, line width=0.2pt] {muni};")
        lines.append(f"\\draw[black, line width=0.7pt, line join=round] {' '.join(borders)};")
        lines.append("}")
        k = len(np.unique(lab))
        lines.append(f"\\newcommand{{\\count{name}}}{{{k} units, {n_small} below 2,000}}")
    names = [r[COL_MUNICIPALITY] for r in rows]
    for name, places in PLACES.items():
        marks = []
        for place in places:
            q = poly[names.index(place)].representative_point()
            marks.append(f"\\fill ({(q.x - x0) * sx:.2f},{(q.y - y0) * sx:.2f}) circle (0.45pt) "
                         f"node[font=\\tiny, inner sep=0.6pt, fill=white, fill opacity=0.8, text opacity=1, anchor={ANCHOR.get(place, 'west')}] {{{place}}};")
        lines.append(f"\\newcommand{{\\places{name}}}{{{' '.join(marks)}}}")
    FIG.mkdir(parents=True, exist_ok=True)
    (FIG / "map_data.tex").write_text("\n".join(lines) + "\n")
    print("\n".join(x for x in lines if x.startswith("%")))


if __name__ == "__main__":
    sys.exit(main())
