"""Administrative cost function for all Austrian municipalities, 2016 to 2019."""

import collections
import csv
import json
import pathlib
import sys

import numpy as np
from accounts_columns import COL_INHABITANTS, COL_REVENUE, COL_SPENDING
from shapely.geometry import shape

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
YEARS = (2016, 2017, 2018, 2019)
CORE = {f"{i:03d}" for i in range(0, 35)} | {"091"}


def subsection_code(s: str) -> str:
    return s.removeprefix("VAUAB-")


def build() -> list[dict]:
    core_out = collections.defaultdict(dict)
    core_in = collections.defaultdict(dict)
    for y in YEARS:
        for r in csv.DictReader((RAW / f"gemua_at_{y}.csv").open(encoding="utf-8"), delimiter=";"):
            g = r["C-C41-2"]
            core_out[g].setdefault(y, 0.0)
            core_in[g].setdefault(y, 0.0)
            if subsection_code(r["C-VAUAB-0"]) in CORE:
                core_out[g][y] += float(r[COL_SPENDING])
                core_in[g][y] += float(r[COL_REVENUE])
    pop = collections.defaultdict(dict)
    for r in csv.DictReader((RAW / "gemhh_at_2000_2019.csv").open(encoding="utf-8"), delimiter=";"):
        y = int(r["C-A10-0"].removeprefix("A10-"))
        if y in YEARS:
            pop[r["C-C41-2"]][y] = float(r[COL_INHABITANTS])
    geo = json.loads((RAW / "boundaries_statat_at_2018.geojson").read_text())
    area = {f["properties"]["g_id"]: shape(f["geometry"]).area / 1e6 for f in geo["features"]}
    district = collections.Counter(g[:3] for g in area if not g.startswith("9"))
    rows = []
    for g in sorted(core_out):
        if g.startswith("9"):
            continue
        complete = all(y in core_out[g] for y in YEARS) and all(y in pop[g] for y in YEARS) and g in area
        rows.append({
            "gkz": g,
            "complete": complete,
            "population": np.mean([pop[g][y] for y in YEARS]) if complete else None,
            "gross": np.mean([core_out[g][y] for y in YEARS]) if complete else None,
            "net": np.mean([core_out[g][y] - core_in[g][y] for y in YEARS]) if complete else None,
            "area_km2": area.get(g),
            "statutory_city": district[g[:3]] == 1,
            "state": g[0],
        })
    return rows


def ns_basis(x: np.ndarray, knots: np.ndarray) -> np.ndarray:
    """Natural cubic spline basis (Hastie, Tibshirani, Friedman 2009, eq. 5.4 and 5.5).
    len(knots) = K gives K - 1 columns: x and K - 2 nonlinear terms."""
    k = knots

    def d(j):
        return (np.clip(x - k[j], 0, None) ** 3 - np.clip(x - k[-1], 0, None) ** 3) / (k[-1] - k[j])

    return np.column_stack([x] + [d(j) - d(len(k) - 2) for j in range(len(k) - 2)])


def design(data: dict, knots: np.ndarray) -> np.ndarray:
    states = sorted(set(data["state"]))
    fe = np.column_stack([(data["state"] == l).astype(float) for l in states[1:]])
    return np.column_stack([np.ones(len(data["y"])), ns_basis(data["x"], knots), np.log(data["area"]), data["city"].astype(float), fe])


def fit(data: dict, knots: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(design(data, knots), data["y"], rcond=None)
    return beta


def curve(beta: np.ndarray, grid: np.ndarray, knots: np.ndarray) -> np.ndarray:
    """Size effect only (spline part), up to a constant."""
    return ns_basis(grid, knots) @ beta[1 : len(knots)]


def summary(f: np.ndarray, grid: np.ndarray) -> dict:
    i = int(np.argmin(f))
    # smallest size from which doubling saves less than 5 %
    step = np.log(2)
    gain = np.interp(grid + step, grid, f, right=np.nan) - f  # log change per doubling
    flat = grid[np.where(gain > np.log(0.95))[0]]
    return {"min_pop": float(np.exp(grid[i])), "min_at_edge": i in (0, len(grid) - 1), "flat_from_pop": float(np.exp(flat[0])) if len(flat) else np.nan}


def estimate(rows: list[dict], var: str, n_boot: int = 2000, seed: int = 12345) -> dict:
    ok = [r for r in rows if r["complete"] and r[var] > 0]
    data = {
        "y": np.log(np.array([r[var] / r["population"] for r in ok])),
        "x": np.log(np.array([r["population"] for r in ok])),
        "area": np.array([r["area_km2"] for r in ok]),
        "city": np.array([r["statutory_city"] for r in ok]),
        "state": np.array([r["state"] for r in ok]),
    }
    knots = np.quantile(data["x"], [0, 0.25, 0.5, 0.75, 1])
    grid = np.linspace(data["x"].min(), data["x"].max(), 400)
    beta = fit(data, knots)
    f0 = curve(beta, grid, knots)
    rng = np.random.default_rng(seed)
    fs, sums = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, len(ok), len(ok))
        b = fit({k: v[idx] for k, v in data.items()}, knots)
        f = curve(b, grid, knots)
        fs.append(f - f[np.searchsorted(grid, np.log(1000))])
        sums.append(summary(f, grid))
    fs = np.array(fs)
    res = data["y"] - design(data, knots) @ beta
    r2 = 1 - res.var() / data["y"].var()
    return {
        "n": len(ok), "dropped": sum(1 for r in rows if r["complete"] and r[var] <= 0), "r2": r2,
        "grid": grid, "f": f0 - f0[np.searchsorted(grid, np.log(1000))], "lo": np.percentile(fs, 2.5, 0), "hi": np.percentile(fs, 97.5, 0),
        "point": summary(f0, grid), "boot": sums, "beta_area": beta[len(knots)], "beta_city": beta[len(knots) + 1],
    }


def main() -> None:
    rows = build()
    ok = [r for r in rows if r["complete"]]
    print("municipalities in the sub-section data", len(rows), "complete 2016-2019", len(ok))
    print("statutory cities", sorted(r["gkz"] for r in ok if r["statutory_city"]))
    with (OUT / "administration_2016_2019.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = []
    for var in ("net", "gross"):
        e = estimate(rows, var)
        mins = np.array([s["min_pop"] for s in e["boot"]])
        rand = np.mean([s["min_at_edge"] for s in e["boot"]])
        flat = np.array([s["flat_from_pop"] for s in e["boot"]])
        lines.append(f"\n{var}: n {e['n']}, dropped (<= 0) {e['dropped']}, R2 {e['r2']:.3f}, log area {e['beta_area']:+.3f}, statutory city {e['beta_city']:+.3f}")
        lines.append(f"  minimum at {e['point']['min_pop']:,.0f} inhabitants (at the edge: {e['point']['min_at_edge']}), bootstrap 95 % {np.percentile(mins, 2.5):,.0f} to {np.percentile(mins, 97.5):,.0f}, share at the edge {rand:.2f}")
        lines.append(f"  doubling saves < 5 % from {e['point']['flat_from_pop']:,.0f} inhabitants, bootstrap 95 % {np.nanpercentile(flat, 2.5):,.0f} to {np.nanpercentile(flat, 97.5):,.0f}")
        lines.append("  cost per inhabitant relative to 1,000 inhabitants (point, 95 %):")
        for inh in (300, 500, 1000, 2000, 3000, 5000, 10000, 20000, 50000, 100000):
            i = int(np.argmin(abs(e["grid"] - np.log(inh))))
            if abs(e["grid"][i] - np.log(inh)) < 0.05:
                lines.append(f"    {inh:>7,}: {np.exp(e['f'][i]):.2f}  ({np.exp(e['lo'][i]):.2f} to {np.exp(e['hi'][i]):.2f})")
        np.savetxt(OUT / f"cost_curve_{var}.csv", np.column_stack([np.exp(e["grid"]), np.exp(e["f"]), np.exp(e["lo"]), np.exp(e["hi"])]), delimiter=",", header="population,relative_to_1000,lo,hi", comments="", fmt="%.6g")
    text = "\n".join(lines)
    print(text)
    (OUT / "cost_function.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
