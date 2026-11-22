"""Public transport travel time to the seat for the municipalities that lose their own seat.

Run from the repository root.
Data: vmobil GTFS (company of the Austrian transport associations, sample data set of 03.07.2026) and
ÖBB GTFS 2026 (CC BY 4.0), both in data/raw/gtfs/, not in the repository.
Writes data/derived/transit.txt.
"""

import collections
import csv
import datetime
import io
import json
import pathlib
import sys
import zipfile

import numpy as np
import pyproj
from scipy.spatial import cKDTree
from shapely.geometry import Point, shape
from shapely.ops import unary_union

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import balance as bl  # noqa: E402
import fag  # noqa: E402
import regions  # noqa: E402
import roads  # noqa: E402

RAW = roads.RAW
FEEDS = ((RAW / "gtfs" / "vmobil_gtfs_20260703.zip", ""), (RAW / "gtfs" / "oebb_gtfs_2026.zip", "GTFS_Fahrplan_2026/"))
DAYS = (datetime.date(2026, 10, 13), datetime.date(2026, 5, 12))
STARTS = [7 * 3600 + 900 * i for i in range(9)]
LIMIT = 12 * 3600
ACCESS, TRANSFER, WALK_KMH, DETOUR, CHANGE = 800.0, 400.0, 4.5, 1.3, 120
MARGIN = 10000
VMOBIL_PUBLISHER = "Mobilitätsverbünde Österreich OG"  # publisher named in the attribution required by the vmobil GTFS licence
COL_MUNICIPALITY = "gemeinde"  # municipality name column in vbg_regional_divisions.csv of data.vorarlberg.gv.at
FELDKIRCH_STOP = "Feldkirch Bahnhof"  # stop name in the ÖBB GTFS
TO_M = pyproj.Transformer.from_crs(4326, 31287, always_xy=True).transform


def walk_s(d):
    return d * DETOUR / (WALK_KMH / 3.6)


def secs(t: str) -> int:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def table(z, prefix, name):
    return csv.DictReader(io.TextIOWrapper(z.open(prefix + name), encoding="utf-8-sig"))


def services(z, prefix, day) -> set:
    d, wd = day.strftime("%Y%m%d"), day.strftime("%A").lower()
    on = {r["service_id"] for r in table(z, prefix, "calendar.txt") if r[wd] == "1" and r["start_date"] <= d <= r["end_date"]}
    for r in table(z, prefix, "calendar_dates.txt"):
        if r["date"] == d:
            (on.add if r["exception_type"] == "1" else on.discard)(r["service_id"])
    return on


def rail_trips_feldkirch(day) -> int:
    """ÖBB trips on the day that stop at Feldkirch station."""
    path, prefix = FEEDS[1]
    with zipfile.ZipFile(path) as z:
        stops = {r["stop_id"] for r in table(z, prefix, "stops.txt") if r["stop_name"] == FELDKIRCH_STOP}
        on = services(z, prefix, day)
        trips = {r["trip_id"] for r in table(z, prefix, "trips.txt") if r["service_id"] in on}
        return len({r["trip_id"] for r in table(z, prefix, "stop_times.txt") if r["stop_id"] in stops and r["trip_id"] in trips})


def settlement_points(rows, polys):
    """Same rule as roads.py: OSM place node with the municipality's name inside its border, else the fallback point."""
    z = np.load(roads.CACHE)
    rep = {g: p.representative_point() for g, p in polys.items()}
    pts, fallback = {}, []
    for r in rows:
        g = r["gkz"]
        cand = [TO_M(x, y) for nm, (x, y) in zip(z["pnames"], z["pxy"]) if nm == r[COL_MUNICIPALITY]]
        cand = [c for c in cand if polys[g].contains(Point(*c))]
        if cand:
            pts[g] = cand[0]
        else:
            fallback.append(r[COL_MUNICIPALITY])
            pts[g] = (rep[g].x, rep[g].y)
    return pts, fallback


def main() -> None:
    rows, _, _ = regions.load()
    geo = json.loads((RAW / "boundaries_statat_2026.geojson").read_text())
    gk = {r["gkz"] for r in rows}
    polys = {f["properties"]["g_id"]: shape(f["geometry"]) for f in geo["features"] if f["properties"]["g_id"] in gk}
    area = unary_union(list(polys.values())).buffer(MARGIN)
    pts, fallback = settlement_points(rows, polys)
    text = "\n\n".join(analyse(day, rows, polys, area, dict(pts), fallback) for day in DAYS)
    text += "\n\nÖBB trips stopping at Feldkirch station: " + ", ".join(f"{d:%d.%m.%Y} {rail_trips_feldkirch(d)}" for d in sorted(DAYS))
    print(text)
    (fag.DER / "transit.txt").write_text(text + "\n")


def analyse(day, rows, polys, area, pts, fallback) -> str:
    gk = {r["gkz"] for r in rows}
    stops, conns, nstat = {}, [], []
    deps = collections.Counter()
    for path, prefix in FEEDS:
        with zipfile.ZipFile(path) as z:
            on = services(z, prefix, day)
            for r in table(z, prefix, "stops.txt"):
                if r["stop_lat"] and r["stop_id"] not in stops:
                    x, y = TO_M(float(r["stop_lon"]), float(r["stop_lat"]))
                    if area.contains(Point(x, y)):
                        stops[r["stop_id"]] = (x, y, r["stop_name"])
            trips = {r["trip_id"] for r in table(z, prefix, "trips.txt") if r["service_id"] in on}
            seq = collections.defaultdict(list)
            for r in table(z, prefix, "stop_times.txt"):
                if r["trip_id"] in trips:
                    seq[r["trip_id"]].append((int(r["stop_sequence"]), r["stop_id"], secs(r["arrival_time"]), secs(r["departure_time"])))
            n0 = len(conns)
            for tid, s in seq.items():
                s.sort()
                key = path.name + tid
                for a, b in zip(s, s[1:]):
                    if a[1] in stops and b[1] in stops:
                        conns.append((a[3], b[2], a[1], b[1], key))
                        deps[a[1]] += 1
            nstat.append(f"{path.name}: services on the reference day {len(on)}, trips {len(trips)}, connections in Vorarlberg with margin {len(conns) - n0}")
    sid = list(stops)
    six = {s: i for i, s in enumerate(sid)}
    xy = np.array([stops[s][:2] for s in sid])
    tree = cKDTree(xy)
    trip_ix = {}
    C = np.array([(d, a, six[u], six[v], trip_ix.setdefault(t, len(trip_ix))) for d, a, u, v, t in conns], dtype=np.int64)
    C = C[np.argsort(C[:, 0], kind="stable")]
    foot = [[(j, walk_s(np.hypot(*(xy[i] - xy[j])))) for j in tree.query_ball_point(xy[i], TRANSFER) if j != i] for i in range(len(sid))]

    pop = fag.load_pop()
    name = {r["gkz"]: r[COL_MUNICIPALITY] for r in rows}
    cuts = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    need = collections.defaultdict(set)
    plan = {}
    for cut in bl.NAMES:
        units = collections.defaultdict(list)
        for r in cuts:
            units[r[cut]].append(r["gkz"])
        lose = []
        for m in units.values():
            seat = max(m, key=lambda g: pop[g])
            lose += [(g, seat) for g in m if g != seat]
            for g in m:
                if g != seat:
                    need[g].add(seat)
        plan[cut] = lose
    # a settlement point without any stop within ACCESS (Laterns, whose fallback point lies
    # away from the village) moves to the stop inside the municipality with the most
    # departures on the day
    moved = []
    for g in sorted(gk):
        if not tree.query_ball_point(pts[g], ACCESS):
            inside = [i for i, s in enumerate(sid) if polys[g].contains(Point(*xy[i]))]
            if inside:
                best = max(inside, key=lambda i: deps[sid[i]])
                pts[g] = tuple(xy[best])
                moved.append(f"{[r[COL_MUNICIPALITY] for r in rows if r['gkz'] == g][0]} → {stops[sid[best]][2]}")
    near = {g: [(j, walk_s(np.hypot(*(xy[j] - np.array(pts[g]))))) for j in tree.query_ball_point(pts[g], ACCESS)] for g in gk}

    def run(g, t0):
        ready = np.full(len(sid), np.inf)
        arr = np.full(len(sid), np.inf)
        for j, w in near[g]:
            ready[j] = min(ready[j], t0 + w)
            arr[j] = min(arr[j], t0 + w)
        onboard = np.zeros(len(trip_ix), bool)
        lo = np.searchsorted(C[:, 0], t0)
        hi = np.searchsorted(C[:, 0], LIMIT, side="right")
        for d, a, u, v, tr in C[lo:hi]:
            if onboard[tr] or ready[u] <= d:
                onboard[tr] = True
                if a < arr[v]:
                    arr[v] = a
                    if a + CHANGE < ready[v]:
                        ready[v] = a + CHANGE
                    for j, w in foot[v]:
                        if a + w + CHANGE < ready[j]:
                            ready[j] = a + w + CHANGE
                            if a + w < arr[j]:
                                arr[j] = a + w
        return arr

    tt = {}
    for g in sorted(need):
        res = [run(g, t0) for t0 in STARTS]
        for seat in need[g]:
            direct = walk_s(np.hypot(*(np.array(pts[g]) - np.array(pts[seat]))))
            vals = []
            for t0, arr in zip(STARTS, res):
                best = min([arr[j] + w for j, w in near[seat]] + [np.inf])
                best = min(best, t0 + direct)
                vals.append((best - t0) / 60 if best <= LIMIT else np.inf)
            tt[(g, seat)] = float(np.median(vals))

    tt_car = list(csv.reader((fag.DER / "travel_time_seat.csv").open(encoding="utf-8")))
    car = {(r[0], c): float(v) for r in tt_car[1:] for c, v in zip(tt_car[0][1:], r[1:])}
    total = sum(pop[g] for g in name)
    out = ["Way to the seat by bus and train for municipalities that lose the seat (transit.py)",
           f"Source: vmobil GTFS ({VMOBIL_PUBLISHER}, sample data set 03.07.2026, licence with attribution), ÖBB GTFS 2026 (CC BY 4.0)",
           f"reference day {day:%d.%m.%Y} (Tuesday), departure 7:00 to 9:00 every 15 min, median over nine times, no arrival by 12:00 = no connection",
           f"on foot: access up to {ACCESS:.0f} m, transfer up to {TRANSFER:.0f} m, beeline x {DETOUR} at {WALK_KMH} km/h, {CHANGE} s minimum transfer; seat = largest member by fag.load_pop",
           *nstat, f"stops in Vorarlberg with {MARGIN // 1000} km margin: {len(sid)}, connections total {len(C)}, settlement points with substitute point {fallback}",
           f"settlement point moved to the stop with the most departures: {moved}; after that without a stop within {ACCESS:.0f} m: {sorted(name[g] for g in gk if not near[g])}", "",
           "partition | municipalities without the seat | median min | weighted mean min (only with a connection) | maximum | inhabitants of Vorarlberg over 30 min | over 60 min | no connection in the morning | median public transport/car | three farthest"]
    for cut, label in bl.NAMES.items():
        lose = plan[cut]
        t = np.array([tt[p] for p in lose])
        w = np.array([pop[g] for g, _ in lose], float)
        fin = np.isfinite(t)
        ratio = np.median([tt[p] / car[p] for p in lose if np.isfinite(tt[p]) and car[p] > 0])
        far = sorted(lose, key=lambda p: -tt[p])[:3]
        mb = [g for g, s in lose if "Mittelberg" in (name[g], name[s])]
        out.append(f"{label} | {len(lose)} | {np.median(t):.1f} | {(t[fin] * w[fin]).sum() / w[fin].sum():.1f} | {t.max():.1f} | "
                   f"{w[t > 30].sum() / total:.1%} | {w[t > 60].sum() / total:.1%} | {(~fin).sum()} ({w[~fin].sum():,.0f} inhabitants) | {ratio:.1f} | "
                   + ", ".join(f"{name[g]}→{name[s]} {tt[(g, s)]:.0f}" for g, s in far)
                   + (f" | via Mittelberg: {len(mb)} municipalities" if mb else ""))
    out += ["", "check, median min (public transport | car):"]
    ix = {v: k for k, v in name.items()}
    for a, b in (("Feldkirch", "Bregenz"), ("Warth", "Lech"), ("Laterns", "Rankweil")):
        g, s = ix[a], ix[b]
        if (g, s) not in tt:
            res = [run(g, t0) for t0 in STARTS]
            vals = [(min([arr[j] + w for j, w in near[s]] + [np.inf]) - t0) / 60 for t0, arr in zip(STARTS, res)]
            tt[(g, s)] = float(np.median([v if v * 60 + t0 <= LIMIT else np.inf for v, t0 in zip(vals, STARTS)]))
        out.append(f"  {a} → {b}: {tt[(g, s)]:.1f} | {car[(g, s)]:.1f}")
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
