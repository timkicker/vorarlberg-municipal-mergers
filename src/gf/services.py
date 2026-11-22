"""What is in each municipality: schools, childcare, fire brigade, town hall, post, doctor, food shop.

Writes data/derived/services.txt and data/derived/services.csv.
"""

import collections
import csv
import json
import pathlib
import sys

import osmium
import pyproj
from shapely.geometry import Point, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fag  # noqa: E402
import personnel  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
PBF = RAW / "osm_austria_261119.osm.pbf"
CACHE = RAW / "osm" / "services_vbg.json"
# Kind keys stored in the OSM cache services_vbg.json written by extract()
KIND_SCHOOL = "school"  # official schools
KIND_FIRE_BRIGADE = "fire_brigade"
KIND_TOWN_HALL = "town_hall"
KIND_POST = "post_office"
KIND_DOCTOR = "doctor_pharmacy"  # doctor or pharmacy
KIND_GROCERY = "grocery"  # food shop
# Kinds counted from the official lists only
KIND_PRIMARY = "primary_school"
KIND_MIDDLE = "middle_school"
KIND_CHILDCARE = "childcare"
# Column and values of vbg_schools.csv, the school list for Vorarlberg
COL_SCHOOL_TYPE = "haupttyp"  # main school type
TYPE_PRIMARY = "VS"  # type prefix of primary schools
TYPE_MIDDLE = "NMS"  # type code of middle schools
# kinds in output order, with the English column names
KINDS = (KIND_SCHOOL, KIND_PRIMARY, KIND_MIDDLE, KIND_CHILDCARE, KIND_FIRE_BRIGADE, KIND_TOWN_HALL, KIND_POST, KIND_DOCTOR, KIND_GROCERY)
COLUMN = {KIND_SCHOOL: "school", KIND_PRIMARY: "primary_school", KIND_MIDDLE: "middle_school", KIND_CHILDCARE: "childcare",
          KIND_FIRE_BRIGADE: "fire_brigade", KIND_TOWN_HALL: "town_hall", KIND_POST: "post_office", KIND_DOCTOR: "doctor_pharmacy",
          KIND_GROCERY: "grocery"}


def kind(tags) -> str | None:
    a, s, h = tags.get("amenity"), tags.get("shop"), tags.get("healthcare")
    if a == "school":
        return "school_osm"
    if a == "kindergarten":
        return "kindergarten_osm"
    if a == "fire_station":
        return KIND_FIRE_BRIGADE
    if a == "townhall":
        return KIND_TOWN_HALL
    if a == "post_office":
        return KIND_POST
    if a in ("doctors", "pharmacy") or h == "doctor":
        return KIND_DOCTOR
    if s in ("supermarket", "convenience"):
        return KIND_GROCERY
    return None


def extract(bbox) -> list:
    x0, y0, x1, y1 = bbox
    out = []
    flt = osmium.filter.KeyFilter("amenity", "shop", "healthcare")
    for o in osmium.FileProcessor(str(PBF), osmium.osm.NODE | osmium.osm.WAY).with_locations().with_filter(flt):
        k = kind(o.tags)
        if not k:
            continue
        if o.is_node():
            lon, lat = o.location.lon, o.location.lat
        else:
            locs = [n.location for n in o.nodes if n.location.valid()]
            if not locs:
                continue
            lon, lat = sum(p.lon for p in locs) / len(locs), sum(p.lat for p in locs) / len(locs)
        if x0 <= lon <= x1 and y0 <= lat <= y1:
            out.append((k, lon, lat, o.tags.get("name", "")))
    CACHE.write_text(json.dumps(out, ensure_ascii=False))
    return out


def classes(n: int) -> int:
    return personnel.klass(n)


def main() -> None:
    names = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(DER / "pareto_partitions.csv"))}
    geo = json.loads((RAW / "boundaries_statat_2026.geojson").read_text())
    polys = {f["properties"]["g_id"]: shape(f["geometry"]) for f in geo["features"] if f["properties"]["g_id"] in names}
    assert len(polys) == 96
    to_m = pyproj.Transformer.from_crs(4326, 31287, always_xy=True).transform
    to_deg = pyproj.Transformer.from_crs(31287, 4326, always_xy=True).transform
    x0, y0, x1, y1 = unary_union(list(polys.values())).bounds
    lons, lats = to_deg([x0, x0, x1, x1], [y0, y1, y0, y1])
    pts = json.loads(CACHE.read_text()) if CACHE.exists() else extract((min(lons), min(lats), max(lons), max(lats)))
    keys = list(polys)
    tree = STRtree([polys[k] for k in keys])
    cnt = collections.defaultdict(collections.Counter)
    for k, lon, lat, _ in pts:
        x, y = to_m(lon, lat)
        hit = tree.query(Point(x, y), predicate="within")
        if len(hit):
            cnt[keys[hit[0]]][k] += 1
    with open(RAW / "vbg_childcare_facilities.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            cnt[r["gkz"]][KIND_CHILDCARE] += 1
    with open(RAW / "vbg_schools.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            cnt[r["gkz"]][KIND_SCHOOL] += 1
            if r[COL_SCHOOL_TYPE].startswith(TYPE_PRIMARY):
                cnt[r["gkz"]][KIND_PRIMARY] += 1
            if TYPE_MIDDLE in r[COL_SCHOOL_TYPE]:
                cnt[r["gkz"]][KIND_MIDDLE] += 1
    pop = fag.load_pop()

    lines = [f"OSM objects in Vorarlberg: {sum(sum(c.values()) for c in cnt.values()) - sum(c[k] for c in cnt.values() for k in (KIND_CHILDCARE, KIND_SCHOOL, KIND_PRIMARY, KIND_MIDDLE))}, "
             f"official childcare: {sum(c[KIND_CHILDCARE] for c in cnt.values())}", ""]
    lines.append("1. share of municipalities with at least one facility, by population 2024")
    lines.append("  class | municipalities | " + " | ".join(COLUMN[k] for k in KINDS))
    by = collections.defaultdict(list)
    for g in names:
        by[classes(pop[g])].append(g)
    for c in sorted(by):
        gs = by[c]
        lines.append(f"  {personnel.LABELS[c]} | {len(gs)} | " + " | ".join(f"{sum(1 for g in gs if cnt[g][k]) / len(gs):.0%}" for k in KINDS))
    lines.append("  all | 96 | " + " | ".join(f"{sum(1 for g in names if cnt[g][k]) / 96:.0%}" for k in KINDS))
    lines.append("")
    both = sum(1 for g in names if cnt[g]["kindergarten_osm"] and cnt[g][KIND_CHILDCARE])
    lines.append(f"2. check childcare: municipalities with an official facility {sum(1 for g in names if cnt[g][KIND_CHILDCARE])}, "
                 f"with OSM kindergarten {sum(1 for g in names if cnt[g]['kindergarten_osm'])}, both {both}; "
                 f"facilities official {sum(cnt[g][KIND_CHILDCARE] for g in names)}, OSM {sum(cnt[g]['kindergarten_osm'] for g in names)}")
    lines.append("   municipalities with official, without OSM: " + ", ".join(sorted(names[g] for g in names if cnt[g][KIND_CHILDCARE] and not cnt[g]["kindergarten_osm"])))
    lines.append(f"   check schools: municipalities with an official school {sum(1 for g in names if cnt[g][KIND_SCHOOL])}, with OSM school {sum(1 for g in names if cnt[g]['school_osm'])}")
    lines.append("   without an official school: " + ", ".join(sorted(f"{names[g]} ({pop[g]})" for g in names if not cnt[g][KIND_SCHOOL])))
    lines.append("   without a primary school: " + ", ".join(sorted(f"{names[g]} ({pop[g]})" for g in names if not cnt[g][KIND_PRIMARY])))
    lines.append("   without a school in OSM: " + ", ".join(sorted(f"{names[g]} ({pop[g]})" for g in names if not cnt[g]["school_osm"])))
    lines.append("   without a fire brigade in OSM: " + ", ".join(sorted(f"{names[g]} ({pop[g]})" for g in names if not cnt[g][KIND_FIRE_BRIGADE])))
    lines.append("")

    lines.append("3. per partition: share of inhabitants outside the seat whose municipality has a town hall, primary school and fire brigade today (schools official)")
    units = collections.defaultdict(list)
    for r in csv.DictReader(open(DER / "fag_units.csv")):
        units[r["partition"]].append(r)
    by_name = {v: k for k, v in names.items()}
    for cut, rows in units.items():
        off = full = 0
        for r in rows:
            mem = [by_name[m] for m in r["members"].split(";")]
            if len(mem) < 2:
                continue
            seat = max(mem, key=lambda g: pop[g])
            for g in mem:
                if g == seat:
                    continue
                off += pop[g]
                if all(cnt[g][k] for k in (KIND_TOWN_HALL, KIND_PRIMARY, KIND_FIRE_BRIGADE)):
                    full += pop[g]
        lines.append(f"  {cut}: inhabitants outside the seat {off:,}, of these with all three {full / off:.0%}" if off else f"  {cut}: none")

    with open(DER / "services.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gkz", "municipality", "pop_2024", *(COLUMN[k] for k in KINDS), "kindergarten_osm", "school_osm"])
        for g in sorted(names):
            w.writerow([g, names[g], pop[g], *(cnt[g][k] for k in KINDS), cnt[g]["kindergarten_osm"], cnt[g]["school_osm"]])
    text = "\n".join(lines)
    print(text)
    (DER / "services.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
