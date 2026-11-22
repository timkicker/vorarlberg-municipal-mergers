"""Population 2050 as a switch for the threshold rules.

The Rand index is the adjusted Rand index from regions.ari.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import elections  # noqa: E402
import pareto  # noqa: E402
import regions  # noqa: E402

OUT, RAW = pareto.OUT, pareto.RAW
# Columns and values of vbg_projection.csv, the population forecast for the Vorarlberg municipalities
COL_POPULATION = "bevoelkerung"  # population
COL_FORECAST_YEAR = "prognosejahr"  # forecast year
COL_AGE_GROUP = "altersgruppe"  # age group
AGE_65_79 = "65 bis inkl. 79 Jahre"  # age group 65 to 79
AGE_80_PLUS = "über 80 Jahre"  # age group 80 and over
OLD = {AGE_65_79, AGE_80_PLUS}


def forecast() -> dict:
    """(gkz, year) -> (total, 65+)."""
    d = collections.defaultdict(lambda: [0.0, 0.0])
    for r in csv.DictReader((RAW / "vbg_projection.csv").open(encoding="utf-8"), delimiter=";"):
        v = float(r[COL_POPULATION].replace(",", "."))
        k = (r["gkz"], int(r[COL_FORECAST_YEAR]))
        d[k][0] += v
        d[k][1] += v * (r[COL_AGE_GROUP] in OLD)
    return d


def main() -> None:
    rows, t, adj = regions.load()
    gkz = [r["gkz"] for r in rows]
    adm = {r["gkz"]: r for r in csv.DictReader((OUT / "administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[g]["population"]) for g in gkz])
    cost = np.array([float(adm[g]["net"]) for g in gkz])
    curve = np.loadtxt(OUT / "cost_curve_net.csv", delimiter=",", skiprows=1)
    lc = lambda p: np.interp(np.log(p), np.log(curve[:, 0]), np.log(curve[:, 1]))  # noqa: E731
    f = forecast()
    p26 = np.array([f[(g, 2026)][0] for g in gkz])
    p50 = np.array([f[(g, 2050)][0] for g in gkz])
    o26 = np.array([f[(g, 2026)][1] for g in gkz]) / p26
    o50 = np.array([f[(g, 2050)][1] for g in gkz]) / p50
    lines = [f"forecast: {len(gkz)} municipalities, total 2026 {p26.sum():,.0f}, 2050 {p50.sum():,.0f}"]

    growth = p50 / p26 - 1
    x = np.log(p26)
    slope = lambda i: np.polyfit(x[i], growth[i], 1)[0]  # noqa: E731
    rng = np.random.default_rng(pareto.SEED)
    bs = [slope(rng.integers(0, len(x), len(x))) for _ in range(2000)]
    lines.append(f"\n1. growth 2026-2050 on log population 2026: slope {slope(np.arange(len(x))):+.4f} per log unit, 95 % [{np.percentile(bs, 2.5):+.4f}, {np.percentile(bs, 97.5):+.4f}]")
    for lo, hi in zip((0, 1000, 2000, 3500, 5000, 10000), (1000, 2000, 3500, 5000, 10000, np.inf)):
        m = (p26 >= lo) & (p26 < hi)
        lines.append(f"   {lo:>6,}-{hi:<7,.0f} {m.sum():>3} municipalities, growth weighted {p50[m].sum() / p26[m].sum() - 1:+.1%}, median {np.median(growth[m]):+.1%}, shrinking {np.sum(growth[m] < 0)}")

    el = {r["gkz"]: r for r in elections.load(2025)}
    wb = np.array([float(el[g]["w"]) for g in gkz])
    lines.append("\n2. share aged 65 and over, by eligible voters 2025 (weighted by population):")
    for lo, hi in zip(elections.CLASSES, elections.CLASSES[1:]):
        m = (wb >= lo) & (wb < hi)
        lines.append(f"   {lo:>6,.0f}-{hi:<7,.0f} {m.sum():>3} municipalities  2026 {np.sum(o26[m] * p26[m]) / p26[m].sum():.1%}  2050 {np.sum(o50[m] * p50[m]) / p50[m].sum():.1%}")
    lines.append(f"   total  2026 {np.sum(o26 * p26) / p26.sum():.1%}  2050 {np.sum(o50 * p50) / p50.sum():.1%}")

    def e(lab, p):
        lab = np.asarray(lab)
        c = cost / pop * p  # cost per head of 2016-19 applied to the new population
        s = 0.0
        for u in np.unique(lab):
            m = np.where(lab == u)[0]
            if len(m) > 1:
                s += np.sum(c[m] * (1 - np.exp(lc(p[m].sum()) - lc(p[m]))))
        return s * pareto.SCALE_MAIN

    lines.append("\n3. threshold rules | k old | k 2050 | adjusted Rand index old against 2050 | same units | E old | E 2050 (m EUR)")
    for lim in (2000, 3500, 5000):
        a = pareto.threshold_rule(t, adj, pop, lim)
        b = pareto.threshold_rule(t, adj, p50, lim)
        ua = {frozenset(i for i, l in enumerate(a) if l == u) for u in set(a)}
        ub = {frozenset(i for i, l in enumerate(b) if l == u) for u in set(b)}
        lines.append(f"   Threshold {lim}: {len(ua)} | {len(ub)} | {regions.ari(a, b):.3f} | {len(ua & ub)} | {e(a, pop) / 1e6:.2f} | {e(b, p50) / 1e6:.2f}")
    text = "\n".join(lines)
    print(text)
    (OUT / "population_2050.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
