"""Tourism, second homes and altitude in the cost curve and in the elected-bodies model.

Writes data/derived/tourism.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import costs  # noqa: E402
import elected_bodies as eb  # noqa: E402

RAW, DER = costs.RAW, costs.OUT
N_BOOT, SEED = 2000, 12345
SIZES = (300, 500, 2000, 5000, 10000)
COL_ALTITUDE = "seehoehe_schwerpunkt"  # altitude of the population centre, column in altitude_municipalities_2020.csv (EU-DEM 25 m via opentopodata.org)
# Columns of vbg_overnight_stays.csv (overnight stays, open data of the state of Vorarlberg)
COL_YEAR = "berichtsjahr"  # reference year
COL_NIGHTS = "naechtigungen"  # overnight stays
# Columns and values of vbg_residence_type.csv (population by type of residence, open data of the state of Vorarlberg)
COL_RES_YEAR = "jahr"  # year
COL_SEX = "geschlecht"  # sex
SEXES = ("männlich", "weiblich")  # values of COL_SEX for male and female
COL_RES_TYPE = "wohnsitzqualitaet"  # type of residence
COL_RES_POPULATION = "bevoelkerung"  # persons
MAIN_RESIDENCE = "Hauptwohnsitz"  # value of COL_RES_TYPE, main residence
FURTHER_RESIDENCE = "weiterer Wohnsitz"  # value of COL_RES_TYPE, further residence


def altitude() -> dict:
    return {r["gkz"]: float(r[COL_ALTITUDE]) for r in csv.DictReader(open(RAW / "altitude_municipalities_2020.csv"))}


def nights(years) -> dict:
    out = collections.defaultdict(float)
    for r in csv.DictReader(open(RAW / "vbg_overnight_stays.csv", encoding="utf-8-sig"), delimiter=";"):
        if int(r[COL_YEAR]) in years:
            out[r["gkz"]] += float(r[COL_NIGHTS] or 0)
    return {g: v / len(years) for g, v in out.items()}


def second_homes(years) -> dict:
    """gkz -> further residences per main residence, mean over years."""
    s = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in csv.DictReader(open(RAW / "vbg_residence_type.csv", encoding="utf-8-sig"), delimiter=";"):
        if r[COL_RES_YEAR] in years and r[COL_SEX] in SEXES:
            s[(r["gkz"], r[COL_RES_YEAR])][r[COL_RES_TYPE]] += float(r[COL_RES_POPULATION].replace(",", "."))
    per = collections.defaultdict(list)
    for (g, _y), v in s.items():
        if v[MAIN_RESIDENCE] > 0:
            per[g].append(v[FURTHER_RESIDENCE] / v[MAIN_RESIDENCE])
    return {g: float(np.mean(v)) for g, v in per.items() if len(v) == len(years)}


def curve_data(rows, old):
    ok = [r for r in rows if r["complete"] and r["net"] > 0 and r["gkz"] in old]
    return ok, {
        "y": np.log(np.array([r["net"] / r["population"] for r in ok])),
        "x": np.log(np.array([r["population"] for r in ok])),
        "area": np.array([r["area_km2"] for r in ok]),
        "city": np.array([r["statutory_city"] for r in ok]),
        "state": np.array([r["state"] for r in ok]),
        "old": np.array([old[r["gkz"]] / 100 for r in ok]),
    }


def design(d, knots, with_old):
    X = costs.design(d, knots)
    return np.column_stack([X, d["old"]]) if with_old else X


def fit(d, knots, with_old):
    beta, *_ = np.linalg.lstsq(design(d, knots, with_old), d["y"], rcond=None)
    return beta


def rel(beta, grid, knots):
    f = costs.curve(beta, grid, knots)
    return f - f[np.searchsorted(grid, np.log(1000))]


def at(grid, f, inh):
    return float(np.exp(np.interp(np.log(inh), grid, f)))


def part1(rows, old, lines):
    ok, d = curve_data(rows, old)
    knots = np.quantile(d["x"], [0, 0.25, 0.5, 0.75, 1])
    grid = np.linspace(d["x"].min(), d["x"].max(), 400)
    lines.append(f"1. Cost curve net, all of Austria, n {len(ok)}, altitude in 100 m")
    res = {}
    for with_old in (False, True):
        beta = fit(d, knots, with_old)
        f0 = rel(beta, grid, knots)
        rng = np.random.default_rng(SEED)
        pts, flats, ba_ = [], [], []
        for _ in range(N_BOOT):
            idx = rng.integers(0, len(ok), len(ok))
            db = {k: v[idx] for k, v in d.items()}
            b = fit(db, knots, with_old)
            f = rel(b, grid, knots)
            pts.append([at(grid, f, s) for s in SIZES])
            flats.append(costs.summary(f, grid)["flat_from_pop"])
            if with_old:
                ba_.append(b[-1])
        pts = np.array(pts)
        flat = costs.summary(f0, grid)["flat_from_pop"]
        res[with_old] = ([at(grid, f0, s) for s in SIZES], flat)
        lab = "with altitude" if with_old else "without altitude (as costs.py)"
        lines.append(f"  {lab}:" + (f" altitude {beta[-1]:+.4f} log per 100 m [{np.percentile(ba_, 2.5):+.4f}, {np.percentile(ba_, 97.5):+.4f}]" if with_old else ""))
        for j, s in enumerate(SIZES):
            lines.append(f"    {s:>6,} inhabitants: {res[with_old][0][j]:.3f} ({np.percentile(pts[:, j], 2.5):.3f} to {np.percentile(pts[:, j], 97.5):.3f})")
        lines.append(f"    doubling saves < 5 % from {flat:,.0f} inhabitants, bootstrap 95 % {np.nanpercentile(flats, 2.5):,.0f} to {np.nanpercentile(flats, 97.5):,.0f}")
    d500 = (res[True][0][1] - res[False][0][1]) * 100
    dflat = res[True][1] / res[False][1] - 1
    lines.append(f"  change from altitude: 500 inhabitants {d500:+.1f} percentage points, threshold {dflat:+.1%}")
    lines.append("")
    beta = fit(d, knots, False)
    resid = d["y"] - design(d, knots, False) @ beta
    return {r["gkz"]: e for r, e in zip(ok, resid)}


def part2(rows, resid, lines):
    pop = {r["gkz"]: r["population"] for r in rows if r["complete"]}
    n = nights(range(2016, 2020))
    w = second_homes([str(y) for y in range(2016, 2020)])
    g = [k for k in resid if k.startswith("8") and k in w]
    e = np.array([resid[k] for k in g])
    lines.append(f"2. Vorarlberg residuals of the curve without altitude, n {len(g)}")
    rng = np.random.default_rng(SEED)
    for lab, x in (("log(1 + overnight stays per inhabitant), 2016-19", np.log1p(np.array([n.get(k, 0.0) / pop[k] for k in g]))),
                   ("further residences per main residence, 2016-19", np.array([w[k] for k in g]))):
        slope = np.polyfit(x, e, 1)[0]
        bs = []
        for _ in range(N_BOOT):
            idx = rng.integers(0, len(g), len(g))
            if x[idx].std() > 0:
                bs.append(np.polyfit(x[idx], e[idx], 1)[0])
        lines.append(f"  {lab}: correlation {np.corrcoef(x, e)[0, 1]:+.2f}, slope {slope:+.3f} [{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}], mean {x.mean():.2f}, maximum {x.max():.2f}")
    lines.append("")


def units():
    names = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(DER / "pareto_partitions.csv"))}
    by_name = {v: k for k, v in names.items()}
    u = collections.defaultdict(list)
    for r in csv.DictReader(open(DER / "fag_units.csv")):
        gs = [by_name[m] for m in r["members"].split(";")]
        if len(gs) > 1:
            u[r["partition"]].append(gs)
    return u


def ols(X, y):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b


def savings(pred, pop, cov, u):
    out = {}
    for cut, us in u.items():
        s = 0.0
        for gs in us:
            inh = sum(pop[x] for x in gs)
            c = [sum(pop[x] * cov[x][j] for x in gs) / inh for j in range(len(cov[gs[0]]))]
            s += sum(pred(pop[x], cov[x]) for x in gs) - pred(inh, c)
        out[cut] = s / 1e6
    return out


def part34(lines):
    o = eb.organs()
    pop = ba.fag_pop(2024)
    n = nights([2023])
    w = second_homes(["2024"])
    allg = [k for k in pop]
    cov = {k: (n.get(k, 0.0) / pop[k], w.get(k, float("nan"))) for k in allg}
    missing_w = [k for k in allg if np.isnan(cov[k][1])]
    g = [k for k in o if k in pop and not np.isnan(cov[k][1])]
    e = np.array([pop[k] for k in g])
    y = np.array([o[k] for k in g])
    C = np.array([cov[k] for k in g])
    u = units()
    runs = {}
    b = ols(np.column_stack([np.ones_like(e), e]), y)
    runs["linear, main model"] = lambda m, c, b=b: b[0] + b[1] * m
    b = ols(np.column_stack([np.ones_like(e), np.log(e)]), np.log(y))
    runs["log-log, main model"] = lambda m, c, b=b: float(np.exp(b[0] + b[1] * np.log(m)))
    bl = ols(np.column_stack([np.ones_like(e), e, C]), y)
    runs["linear with covariates"] = lambda m, c, b=bl: b[0] + b[1] * m + b[2] * c[0] + b[3] * c[1]
    bg = ols(np.column_stack([np.ones_like(e), np.log(e), C]), np.log(y))
    runs["log-log with covariates"] = lambda m, c, b=bg: float(np.exp(b[0] + b[1] * np.log(m) + b[2] * c[0] + b[3] * c[1]))
    q = np.quantile(C[:, 0], 0.75)
    keep = C[:, 0] < q
    b = ols(np.column_stack([np.ones(keep.sum()), e[keep]]), y[keep])
    runs["linear without the top quarter of overnight stays"] = lambda m, c, b=b: b[0] + b[1] * m
    b = ols(np.column_stack([np.ones(keep.sum()), np.log(e[keep])]), np.log(y[keep]))
    runs["log-log without the top quarter of overnight stays"] = lambda m, c, b=b: float(np.exp(b[0] + b[1] * np.log(m)))
    lines.append(f"3./4. Elected bodies 2024, n {len(g)}; covariates overnight stays 2023 per inhabitant, further residences 2024 per main residence")
    lines.append(f"  municipalities without residence data: {missing_w}")
    lines.append(f"  linear with covariates: a {bl[0]:,.0f}, b {bl[1]:.2f} per inhabitant, overnight stays per inhabitant {bl[2]:+,.0f}, further residences per main residence {bl[3]:+,.0f}")
    lines.append(f"  log-log with covariates: elasticity {bg[1]:.3f}, overnight stays per inhabitant {bg[2]:+.4f}, further residences per main residence {bg[3]:+.3f}")
    lines.append(f"  top quarter of overnight stays: from {q:.1f} per inhabitant, {int((~keep).sum())} municipalities left out")
    cuts = list(u)
    lines.append("  Savings m | " + " | ".join(cuts))
    base = None
    for lab, f in runs.items():
        s = savings(f, pop, {k: (cov[k][0], 0.0 if np.isnan(cov[k][1]) else cov[k][1]) for k in allg}, u)
        lines.append(f"  {lab} | " + " | ".join(f"{s[c]:.2f}" for c in cuts))
        if lab.startswith("linear, main"):
            base = s
    lines.append("  (municipalities without residence data enter the prediction of the covariate runs with 0 further residences)")
    return base


def main() -> None:
    rows = costs.build()
    old = altitude()
    lines = ["Tourism, second homes and altitude (tourism.py)", ""]
    resid = part1(rows, old, lines)
    part2(rows, resid, lines)
    part34(lines)
    text = "\n".join(lines)
    print(text)
    (DER / "tourism.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
