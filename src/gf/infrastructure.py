"""Roads, water and sewers per inhabitant, the 2050 forecast and what a merger would spread.

Run from the repository root.
Writes data/derived/infrastructure.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import personnel  # noqa: E402
import pop2050  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
SUBSECTIONS = ("612", "850", "851")
CUTS = ("Threshold 2000", "Threshold 3500", "Threshold 5000", "official planning region")
CLASSES = ((0, 1000), (1000, 2000), (2000, 3500), (3500, 5000), (5000, 10000), (10000, float("inf")))
# columns of the closing account files of offenerhaushalt.at
COL_MVAG = "Mvag"  # MVAG code
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_VALUE = "Wert"  # amount


def read(year: int = 2024) -> dict:
    """gkz -> (net total, net operating)."""
    out = {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        tot = op = 0.0
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r[COL_SUBSECTION] not in SUBSECTIONS:
                    continue
                mv, w = r[COL_MVAG][:2], personnel.num(r[COL_VALUE])
                sign = {"32": 1, "34": 1, "31": -1, "33": -1}.get(mv, 0)
                tot += sign * w
                if mv in ("31", "32"):
                    op += sign * w
        out[path.name.split("_")[1]] = (tot, op)
    return out


def main() -> None:
    m = read()
    pop = ba.fag_pop(2024)
    f = pop2050.forecast()
    g = sorted(k for k in m if k in pop)
    rows = list(csv.DictReader(open(DER / "pareto_partitions.csv", encoding="utf-8")))
    out = ["Infrastructure per head: municipal roads 612, water 850, sewage 851 (infrastructure.py)",
           "Source: offenerhaushalt RA 2024, population base_amount.fag_pop(2024), forecast pop2050.forecast()",
           f"municipalities with a file: {len(g)} of {len(pop)}", "",
           "1. Net per inhabitant by size class: class | municipalities | total median [P10, P90] | operating median [P10, P90]"]
    pt = {k: m[k][0] / pop[k] for k in g}
    po = {k: m[k][1] / pop[k] for k in g}
    q = lambda x: f"{np.median(x):,.0f} [{np.percentile(x, 10):,.0f}, {np.percentile(x, 90):,.0f}]"  # noqa: E731
    for lo, hi in CLASSES:
        s = [k for k in g if lo <= pop[k] < hi]
        out.append(f"  {lo:,}-{hi:,} | {len(s)} | {q([pt[k] for k in s])} | {q([po[k] for k in s])}")
    out.append(f"  all | {len(g)} | {q(list(pt.values()))} | {q(list(po.values()))}")
    small = np.median([po[k] for k in g if pop[k] < 1000])
    out.append(f"  smallest class operating against all: {small / np.median(list(po.values())) - 1:+.1%}")
    out.append(f"  because the median of all is negative, the difference: operating {small - np.median(list(po.values())):+,.0f} EUR per inhabitant, total {np.median([pt[k] for k in g if pop[k] < 1000]) - np.median(list(pt.values())):+,.0f}")

    gr = {k: f[(k, 2050)][0] / f[(k, 2026)][0] - 1 for k in g}
    rho, p = spearmanr([po[k] for k in g], [gr[k] for k in g])
    out += ["", f"2. Spearman operating per inhabitant against growth 2026-2050: rho {rho:+.2f}, p {p:.3f}", "",
            "3. Denominator effect, costs fixed at 2024: class | operating per inhabitant 2026 | 2050 | change (weighted)"]
    for lo, hi in CLASSES:
        s = [k for k in g if lo <= pop[k] < hi]
        c = sum(m[k][1] for k in s)
        a, b = c / sum(f[(k, 2026)][0] for k in s), c / sum(f[(k, 2050)][0] for k in s)
        out.append(f"  {lo:,}-{hi:,} | {a:,.0f} | {b:,.0f} | {b / a - 1:+.1%}")

    out += ["", "4. Redistribution inside the units, operating: partition | units (all with a file) | costs in them m | volume m | share | units without full data"]
    for cut in CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        multi = [u for u in units.values() if len(u) > 1]
        full = [u for u in multi if all(k in m for k in u)]
        vol = ctot = 0.0
        for u in full:
            cu, pu = sum(m[k][1] for k in u), sum(pop[k] for k in u)
            vol += sum(max(0.0, m[k][1] - pop[k] / pu * cu) for k in u)
            ctot += cu
        gross = sum(abs(m[k][1]) for u in full for k in u)
        out.append(f"  {cut} | {len(full)} | {ctot / 1e6:,.1f} | {vol / 1e6:,.2f} | {vol / ctot:.1%} | {len(multi) - len(full)} | against the sum of absolute amounts {vol / gross:.1%}")
    text = "\n".join(out)
    print(text)
    (DER / "infrastructure.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
