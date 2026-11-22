"""Building land reserves by municipal size in Vorarlberg (ÖROK monitoring 2025, VoGIS zoning).

Writes data/derived/building_land.txt.
"""

import collections
import csv
import pathlib
import sqlite3
import statistics
import sys
import tempfile
import zipfile

from shapely import wkb, wkt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fag  # noqa: E402

RAW = fag.RAW
CLASSES = ((0, 1000), (1000, 2000), (2000, 5000), (5000, 10000), (10000, float("inf")))
ENVELOPE = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
# VoGIS uses the short names of two municipalities
ALIAS = {"Langen": "Langen bei Bregenz", "St. Anton": "St. Anton im Montafon"}
COL_MUNICIPALITY = "gemeinde"  # municipality name column in vogis_building_land.csv
# query on the GeoPackage of the ÖROK monitoring; table, columns and values as in the source
RESERVES_QUERY = "select GKZ, ANBINDUNG_VERKEHR, Shape from Baulandreserven_2025_OGD where BL_KZ = '8' and BAULANDRESERVE = 1"


def gpkg_area(blob: bytes) -> float:
    flags = blob[3]
    start = 8 + ENVELOPE[(flags >> 1) & 7]
    return wkb.loads(bytes(blob[start:])).area


def reserves() -> dict:
    out = collections.defaultdict(lambda: [0.0, 0.0])
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(RAW / "oerok_building_land_2025.zip") as z:
        name = next(n for n in z.namelist() if n.endswith(".gpkg"))
        path = z.extract(name, tmp)
        con = sqlite3.connect(path)
        for gkz, road, shape in con.execute(RESERVES_QUERY):
            a = gpkg_area(shape)
            cell = out[str(gkz)]
            cell[0] += a
            if str(road) == "0":
                cell[1] += a
        con.close()
    return out


def zoned(names: dict) -> tuple[dict, set]:
    csv.field_size_limit(10**9)
    code = {v: k for k, v in names.items()}
    out, unknown = collections.Counter(), set()
    for r in csv.DictReader((RAW / "vogis_building_land.csv").open(encoding="utf-8")):
        g = code.get(ALIAS.get(r[COL_MUNICIPALITY], r[COL_MUNICIPALITY]))
        if g is None:
            unknown.add(r[COL_MUNICIPALITY])
            continue
        out[g] += wkt.loads(r["the_geom"]).area
    return out, unknown


def q(v):
    v = sorted(v)
    if len(v) < 2:
        return v[0], v[0], v[0]
    a, m, b = statistics.quantiles(v, n=4)
    return a, statistics.median(v), b


def main() -> None:
    pop = {g: n for g, n in fag.load_pop().items() if g.startswith("8")}
    names = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8"))}
    res = reserves()
    zon, unknown = zoned(names)
    lines = ["Building land reserves by municipal size (building_land.py)", ""]
    lines.append(f"municipalities with reserves {len(res)}, with zoned building land {len(zon)}, names without assignment: {', '.join(sorted(unknown)) or 'none'}")
    over = [names[g] for g in pop if zon[g] and res[g][0] > zon[g]]
    lines.append(f"reserves larger than zoned building land: {', '.join(over) or 'none'}")
    lines.append("")
    lines.append("Class | municipalities | reserves m2 per inhabitant | zoned building land m2 per inhabitant | reserves in % of zoned building land | reserves without road access in %  (each quartile 1, median, quartile 3)")
    for lo, hi in CLASSES + ((0, float("inf")),):
        g = [x for x in pop if lo <= pop[x] < hi]
        cols = [
            q([res[x][0] / pop[x] for x in g]),
            q([zon[x] / pop[x] for x in g]),
            q([100 * res[x][0] / zon[x] for x in g if zon[x]]),
            q([100 * res[x][1] / res[x][0] for x in g if res[x][0]]),
        ]
        name = "all" if lo == 0 and hi == float("inf") else (f"from {lo:,}" if hi == float("inf") else f"{lo:,} to under {hi:,}")
        lines.append(f"  {name} | {len(g)} | " + " | ".join(f"{a:,.0f} / {m:,.0f} / {b:,.0f}" for a, m, b in cols))
    tr = sum(v[0] for v in res.values())
    tz = sum(zon.values())
    tp = sum(pop.values())
    lines.append("")
    lines.append(f"State: reserves {tr / 1e6:,.1f} km2, zoned building land {tz / 1e6:,.1f} km2, share {tr / tz:.1%}, per inhabitant {tr / tp:,.0f} m2, without road access {sum(v[1] for v in res.values()) / tr:.1%}")
    text = "\n".join(lines)
    print(text)
    (fag.DER / "building_land.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
