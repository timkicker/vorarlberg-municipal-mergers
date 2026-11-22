"""Cross-check the neighbour graph against OpenStreetMap boundaries.

OSM boundaries are drawn and maintained separately from the two official
sources, so agreement here is a check on data/derived/neighbours.csv, not just
on our geometry code. Relations are matched to municipalities by ref:at:gkz.
"""

import csv
import json
import pathlib
import sys

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from gf import adjacency as A  # noqa: E402

RAW = A.RAW
COL_MUNICIPALITY = "gemeinde"  # municipality name column in vbg_regional_divisions.csv of data.vorarlberg.gv.at


def load_osm() -> dict[str, object]:
    data = json.loads((RAW / "osm" / "vbg_admin8.json").read_text())
    tr = Transformer.from_crs("EPSG:4326", "EPSG:31287", always_xy=True)
    out = {}
    for el in data["elements"]:
        gkz = el.get("tags", {}).get("ref:at:gkz")
        if el["type"] != "relation" or not gkz:
            continue
        lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in el["members"] if m["type"] == "way" and m.get("role") in ("outer", "") and len(m.get("geometry", [])) > 1]
        poly = unary_union(list(polygonize(unary_union(lines))))
        out[gkz] = shapely.transform(poly, lambda c: np.column_stack(tr.transform(c[:, 0], c[:, 1])))
    return out


def main() -> None:
    names = {r["gkz"]: r[COL_MUNICIPALITY] for r in csv.DictReader((RAW / "vbg_regional_divisions.csv").open(encoding="utf-8"), delimiter=";")}
    osm = load_osm()
    missing = set(names) - set(osm)
    out = ["Neighbour pairs, official boundaries against OpenStreetMap (osm_check.py)", f"OSM relations with GKZ {len(osm)} missing {sorted(missing)}"]
    official = {(r["gkz_a"], r["gkz_b"]): float(r["border_m_statat"]) for r in csv.DictReader((A.OUT / "neighbours.csv").open(encoding="utf-8")) if r["neighbour"] == "1"}
    e = {k: v for k, v in A.edges({k: osm[k] for k in names if k in osm}).items() if v >= A.MIN_BORDER}
    out.append(f"neighbour pairs official {len(official)} OSM {len(e)} common {len(set(e) & set(official))}")
    for a, b in sorted(set(official) - set(e)):
        out.append(f"  official only {names[a]} {names[b]} {round(official[(a, b)], 1)} OSM {round(A.shared(osm[a], osm[b]), 1) if a in osm and b in osm else '-'}")
    for a, b in sorted(set(e) - set(official)):
        out.append(f"  OSM only {names[a]} {names[b]} {round(e[(a, b)], 1)}")
    text = "\n".join(out)
    print(text)
    (A.OUT / "osm_check.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
