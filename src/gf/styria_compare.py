"""How similar Styria before the 2015 reform was to Vorarlberg: size, area, altitude, tax base, tourism.

Writes data/derived/styria_compare.txt.
"""

import collections
import csv
import json
import pathlib
import statistics
import sys

from accounts_columns import COL_DEBT, COL_FEES, COL_INHABITANTS, COL_ORDINARY_SPENDING, COL_OVERNIGHT_STAYS, COL_OWN_REVENUE, COL_TAX_SHARES
from shapely.geometry import shape

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW, DER = ROOT / "data" / "raw", ROOT / "data" / "derived"
GRAZ = "60101"
COL_ALTITUDE = "seehoehe_schwerpunkt"  # altitude of the population centre, column in altitude_municipalities_2020.csv (EU-DEM 25 m via opentopodata.org)
COLS = (COL_INHABITANTS, COL_OWN_REVENUE, COL_FEES, COL_TAX_SHARES, COL_ORDINARY_SPENDING, COL_DEBT)


def finances() -> dict:
    d = collections.defaultdict(dict)
    for r in csv.DictReader((RAW / "gemhh_at_2000_2019.csv").open(encoding="utf-8"), delimiter=";"):
        y = int(r["C-A10-0"].removeprefix("A10-"))
        if y in (2014, 2019):
            d[y][r["C-C41-2"]] = {k: float(r[k] or 0) for k in COLS}
    return d


def areas() -> dict:
    d = json.loads((RAW / "boundaries_statat_at_2014.geojson").read_text(encoding="utf-8"))
    return {f["properties"]["g_id"]: shape(f["geometry"]).area / 1e6 for f in d["features"]}


def altitude() -> dict:
    return {r["gkz"]: float(r[COL_ALTITUDE]) for r in csv.DictReader(open(RAW / "altitude_municipalities_2020.csv", encoding="utf-8"))}


def nights() -> dict:
    out = collections.Counter()
    for r in csv.DictReader(open(RAW / "tour_ua_land.csv", encoding="utf-8"), delimiter=";"):
        m = int(r["C-SDB_TIT-0"])
        y, mo = divmod(m, 100)
        tj = y + 1 if mo >= 11 else y
        if tj in (2014, 2019) and r["C-W96-0"] in ("W96-6", "W96-8"):
            out[(r["C-W96-0"], tj)] += float(r[COL_OVERNIGHT_STAYS] or 0)
    return out


def wmedian(vals: list[tuple[float, float]]) -> float:
    vals = sorted(vals)
    half, acc = sum(w for _, w in vals) / 2, 0.0
    for v, w in vals:
        acc += w
        if acc >= half:
            return v
    return vals[-1][0]


def column(fin, year, prefix, area, old, fin19, net_fees):
    g = {k: v for k, v in fin[year].items() if k.startswith(prefix) and k != GRAZ and v[COL_INHABITANTS] > 0}
    pop = {k: v[COL_INHABITANTS] for k, v in g.items()}
    n = sum(pop.values())
    tax = {k: (v[COL_OWN_REVENUE] - (v[COL_FEES] if net_fees else 0) + v[COL_TAX_SHARES]) for k, v in g.items()}
    a = {k: area[k] for k in g if k in area}
    g19 = {k: v[COL_INHABITANTS] for k, v in fin19.items() if k.startswith(prefix) and k != GRAZ and k in old}
    return {
        "Municipalities": len(g),
        "Population": n,
        "Median population": statistics.median(pop.values()),
        "Municipalities under 1,000": sum(p < 1000 for p in pop.values()) / len(g),
        "Municipalities under 2,000": sum(p < 2000 for p in pop.values()) / len(g),
        "Population in municipalities under 2,000": sum(p for p in pop.values() if p < 2000) / n,
        "Median area km²": statistics.median(a.values()),
        "Inhabitants per km²": sum(pop[k] for k in a) / sum(a.values()),
        "Altitude, weighted median m": wmedian([(old[k], g19[k]) for k in g19]),
        "Population above 800 m": sum(w for k, w in g19.items() if old[k] > 800) / sum(g19.values()),
        "Tax capacity per inhabitant, median": statistics.median(tax[k] / pop[k] for k in g),
        "Tax capacity per inhabitant, state": sum(tax.values()) / n,
        "Ordinary spending per inhabitant, median": statistics.median(v[COL_ORDINARY_SPENDING] / v[COL_INHABITANTS] for v in g.values()),
        "Debt per inhabitant, median": statistics.median(v[COL_DEBT] / v[COL_INHABITANTS] for v in g.values()),
    }


SHARES = {"Municipalities under 1,000", "Municipalities under 2,000", "Population in municipalities under 2,000", "Population above 800 m"}


def main() -> None:
    fin, area, old, ni = finances(), areas(), altitude(), nights()
    bad = sum(v[COL_FEES] > v[COL_OWN_REVENUE] + 0.5 for y in fin for v in fin[y].values())
    net_fees = bad == 0
    cols = {
        "Styria 2014": column(fin, 2014, "6", area, old, fin[2019], net_fees),
        "Vorarlberg 2014": column(fin, 2014, "8", area, old, fin[2019], net_fees),
        "Vorarlberg 2019": column(fin, 2019, "8", area, old, fin[2019], net_fees),
    }
    for y in (2014, 2019):
        for code, lab in (("W96-6", "Styria"), ("W96-8", "Vorarlberg")):
            state_pop = sum(v[COL_INHABITANTS] for k, v in fin[y].items() if k.startswith(code[-1]))
            key = f"{lab} {y}"
            if key in cols:
                cols[key]["Overnight stays per inhabitant, state with Graz"] = ni[(code, y)] / state_pop
    lines = ["Styria before the reform against Vorarlberg (styria_compare.py)", ""]
    lines.append(f"Fees included in the sum of municipal levies: {'yes, deducted' if net_fees else f'no, larger in {bad} rows, not deducted'}")
    lines.append("Styria without Graz except for overnight stays. Altitude on the 2020 boundaries, population 2019.")
    lines.append("")
    lines.append("Feature | " + " | ".join(cols) + " | deviation Vbg 2014 | flagged")
    st, vb = cols["Styria 2014"], cols["Vorarlberg 2014"]
    for k in st:
        vals = " | ".join(f"{c[k]:.0%}" if k in SHARES else f"{c[k]:,.0f}" if c[k] >= 100 or float(c[k]).is_integer() else f"{c[k]:,.1f}" for c in cols.values())
        if k in SHARES:
            dev = (vb[k] - st[k]) * 100
            flag = abs(dev) > 10
            ds = f"{dev:+.0f} point{'' if round(abs(dev)) == 1 else 's'}"
        else:
            dev = vb[k] / st[k] - 1
            flag = abs(dev) > 0.25
            ds = f"{dev:+.0%}"
        lines.append(f"  {k} | {vals} | {ds} | {'yes' if flag else 'no'}")
    text = "\n".join(lines)
    print(text)
    (DER / "styria_compare.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
