"""Neighbour graph of the 96 municipalities with shared border length in metres.

Two independent boundary sources are used (Statistics Austria in EPSG:31287
and VoGIS in EPSG:31254). Both are metric, so lengths are computed in each source's
own CRS. Borders of neighbours rarely coincide to the millimetre, so the shared
length is the part of one boundary that lies within TOL metres of the other
polygon, averaged over both directions.
"""

import csv
import json
import pathlib
import sys

from shapely import STRtree
from shapely.geometry import shape

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
TOL = 2.0  # metres
# A point contact yields about 2.2 * TOL of "shared" border (4.5 and 5.0 m at
# TOL 2, shrinking linearly with TOL), the shortest real border is 33 m
# (Buch/Kennelbach, stable under TOL). Any value between 5 and 33 m gives the
# same graph.
MIN_BORDER = 10.0  # metres
COL_MUNICIPALITY = "gemeinde"  # municipality name column in vbg_regional_divisions.csv of data.vorarlberg.gv.at

SOURCES = {
    "statat": ("boundaries_statat_2026.geojson", "g_id"),
    "vogis": ("boundaries_vogis.geojson", "pgem_gesn"),
}


def load(name: str) -> dict[str, object]:
    fname, key = SOURCES[name]
    data = json.loads((RAW / fname).read_text())
    geoms = {str(f["properties"][key]): shape(f["geometry"]) for f in data["features"]}
    bad = [k for k, g in geoms.items() if not g.is_valid]
    if bad:
        geoms.update({k: geoms[k].buffer(0) for k in bad})
    return geoms


def shared(a, b) -> float:
    ab = a.boundary.intersection(b.buffer(TOL)).length
    ba = b.boundary.intersection(a.buffer(TOL)).length
    return (ab + ba) / 2


def edges(geoms: dict) -> dict[tuple[str, str], float]:
    keys = sorted(geoms)
    tree = STRtree([geoms[k] for k in keys])
    out = {}
    for i, k in enumerate(keys):
        for j in tree.query(geoms[k].buffer(TOL)):
            if j <= i:
                continue
            length = shared(geoms[k], geoms[keys[j]])
            if length > 0:
                out[(k, keys[j])] = length
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = {r["gkz"]: r[COL_MUNICIPALITY] for r in csv.DictReader((RAW / "vbg_regional_divisions.csv").open(encoding="utf-8"), delimiter=";")}
    result = {}
    for src in SOURCES:
        g = load(src)
        assert set(g) == set(names), f"{src}: GKZ differ: {set(g) ^ set(names)}"
        result[src] = edges(g)
        print(src, "edges", len(result[src]))
    pairs = sorted(set(result["statat"]) | set(result["vogis"]))
    with (OUT / "neighbours.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gkz_a", "name_a", "gkz_b", "name_b", "border_m_statat", "border_m_vogis", "neighbour"])
        for a, b in pairs:
            ls, lv = result["statat"].get((a, b), 0), result["vogis"].get((a, b), 0)
            w.writerow([a, names[a], b, names[b], round(ls, 1), round(lv, 1), int(min(ls, lv) >= MIN_BORDER)])
    print("written", OUT / "neighbours.csv", len(pairs))


if __name__ == "__main__":
    sys.exit(main())
