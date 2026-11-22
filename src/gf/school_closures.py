"""Do primary schools close after a merger? Styria 2019/20 to 2024/25 by 2014 territory.

Writes data/derived/school_closures.txt.
"""

import collections
import json
import pathlib
import sys

import numpy as np
import pyproj
import shapely
from shapely.geometry import Point

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria  # noqa: E402

RAW, DER = styria.RAW, styria.OUT
SEED, N_BOOT = 12345, 2000
# Schulatlas GeoJSON s_YYYY.json: property with the school type, and the prefix of primary schools
PROP_TYPE = "TYP"  # school type
TYPE_PRIMARY = "VS"  # type prefix of primary schools
SIZES = ((0, 1000, "under 1,000"), (1000, 2000, "1,000 to 2,000"), (2000, 10**9, "over 2,000"))


def schools(year: str) -> list:
    d = json.loads((RAW / "schulatlas" / f"s_{year}.json").read_text())
    tr = pyproj.Transformer.from_crs(3857, 31287, always_xy=True).transform
    out = []
    for f in d["features"]:
        if f["properties"][PROP_TYPE].startswith(TYPE_PRIMARY) and f["geometry"]:
            out.append(Point(*tr(*f["geometry"]["coordinates"][:2])))
    return out


def has_primary_school(polys: dict, pts: list) -> set:
    keys = list(polys)
    tree = shapely.STRtree([polys[k] for k in keys])
    hit = set()
    for p in pts:
        for i in tree.query(p, predicate="within"):
            hit.add(keys[i])
    return hit


def main() -> None:
    m, _ = styria.mapping()
    _, pop = styria.money()
    size = collections.Counter(new for new, _ in m.values())
    group = {}
    for g, (new, _) in m.items():
        if size[new] == 1:
            group[g] = "no merger"
    for new in [n for n, k in size.items() if k > 1]:
        parts = [g for g, (n, _) in m.items() if n == new]
        seat = max(parts, key=lambda g: pop.get((g, 2014), 0))
        for g in parts:
            group[g] = "seat" if g == seat else "other parts"
    old = styria.polygons(2014, "6")
    vbg = styria.polygons(2014, "8")
    lines = []
    res = {}
    for name, polys in (("Styria", old), ("Vorarlberg", vbg)):
        a, b = has_primary_school(polys, schools("2019_20")), has_primary_school(polys, schools("2024_25"))
        res[name] = (a, b)
        lines.append(f"{name}: areas 2014 {len(polys)}, with primary school 2019/20 {len(a)}, 2024/25 {len(b)}, new {len(b - a)}")
    a, b = res["Styria"]
    rng = np.random.default_rng(SEED)
    lines.append("")
    lines.append("share of areas with a primary school 2019/20 that have none in 2024/25")
    lines.append("  group | size 2014 | areas | without primary school 2024/25 | share | 95 %")
    lost = {}
    for gr in ("no merger", "seat", "other parts"):
        for lo, hi, lab in SIZES + ((0, 10**9, "all"),):
            ids = [g for g in a if group.get(g) == gr and lo <= pop.get((g, 2014), 0) < hi]
            y = np.array([g not in b for g in ids], float)
            lost[(gr, lab)] = y
            if not len(y):
                continue
            bs = [y[rng.integers(0, len(y), len(y))].mean() for _ in range(N_BOOT)]
            lines.append(f"  {gr} | {lab} | {len(y)} | {int(y.sum())} | {y.mean():.1%} | [{np.percentile(bs, 2.5):.1%}, {np.percentile(bs, 97.5):.1%}]")
    va, vb = res["Vorarlberg"]
    lines.append(f"  Vorarlberg | all | {len(va)} | {len(va - vb)} | {len(va - vb) / len(va):.1%} |")
    lines.append("")
    lines.append("difference other parts minus no merger, same size")
    for _, _, lab in SIZES + ((0, 10**9, "all"),):
        t, c = lost[("other parts", lab)], lost[("no merger", lab)]
        if not len(t) or not len(c):
            continue
        bs = [t[rng.integers(0, len(t), len(t))].mean() - c[rng.integers(0, len(c), len(c))].mean() for _ in range(N_BOOT)]
        lines.append(f"  {lab}: {t.mean() - c.mean():+.1%}  95 % [{np.percentile(bs, 2.5):+.1%}, {np.percentile(bs, 97.5):+.1%}]  (n {len(t)} against {len(c)})")
    lines.append(f"areas 2014 without population 2014: {sum(1 for g in old if (g, 2014) not in pop)}")
    text = "\n".join(lines)
    print(text)
    (DER / "school_closures.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
