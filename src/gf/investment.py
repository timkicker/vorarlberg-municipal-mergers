"""Investment spending per inhabitant by municipal size, Vorarlberg 2020-2024.

Run from the repository root.
Writes data/derived/investment.txt.
"""

import csv
import pathlib
import sys

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import personnel  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
YEARS = range(2020, 2025)
CLASSES = ((0, 1000), (1000, 2000), (2000, 3500), (3500, 5000), (5000, 10000), (10000, float("inf")))
# columns of the closing account files of offenerhaushalt.at
COL_MVAG = "Mvag"  # MVAG code
COL_VALUE = "Wert"  # amount


def read(year: int) -> dict:
    """gkz -> (investment payments 34, investment receipts 33)."""
    out = {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        a = e = 0.0
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                mv = r[COL_MVAG][:2]
                if mv == "34":
                    a += personnel.num(r[COL_VALUE])
                elif mv == "33":
                    e += personnel.num(r[COL_VALUE])
        out[path.name.split("_")[1]] = (a, e)
    return out


def main() -> None:
    data = {y: read(y) for y in YEARS}
    pops = {y: ba.fag_pop(y) for y in YEARS}
    g = sorted(set.intersection(*(set(data[y]) for y in YEARS)) & set(pops[2024]))
    inv, rec = {}, {}
    for k in g:
        p = sum(pops[y][k] for y in YEARS)
        inv[k] = sum(data[y][k][0] for y in YEARS) / p
        rec[k] = sum(data[y][k][1] for y in YEARS) / p
    share = {k: rec[k] / inv[k] if inv[k] > 0 else float("nan") for k in g}
    out = ["Investment per inhabitant and year by size, 2020-2024 (investment.py)",
           "Source: offenerhaushalt RA FHH 2020-2024, MVAG 34 (investment payments), 33 (investment receipts); population base_amount.fag_pop",
           f"municipalities with all five years: {len(g)} of {len(pops[2024])}; files per year: " + ", ".join(f"{y} {len(data[y])}" for y in YEARS), "",
           "Class (population 2024) | municipalities | payments 34 median [P10, P90] | receipts 33 median | share 33/34 median"]
    q = lambda x: f"{np.median(x):,.0f} [{np.percentile(x, 10):,.0f}, {np.percentile(x, 90):,.0f}]"  # noqa: E731
    for lo, hi in CLASSES + ((0, float("inf")),):
        s = [k for k in g if lo <= pops[2024][k] < hi]
        lab = "all" if (lo, hi) == (0, float("inf")) else f"{lo:,}-{hi:,}"
        out.append(f"  {lab} | {len(s)} | {q([inv[k] for k in s])} | {np.median([rec[k] for k in s]):,.0f} | {np.nanmedian([share[k] for k in s]):.0%}")
    rho, p = spearmanr([pops[2024][k] for k in g], [inv[k] for k in g])
    out.append(f"\nSpearman population 2024 against payments 34 per inhabitant: rho {rho:+.2f}, p {p:.3f}")
    rho2, p2 = spearmanr([pops[2024][k] for k in g], [share[k] for k in g], nan_policy="omit")
    out.append(f"Spearman population 2024 against share 33/34: rho {rho2:+.2f}, p {p2:.3f}")
    out.append("\nOnly 2023-2024, because many files are missing for 2020-2022")
    yrs = (2023, 2024)
    h = sorted(set(data[2023]) & set(data[2024]) & set(pops[2024]))
    i2 = {k: sum(data[y][k][0] for y in yrs) / sum(pops[y][k] for y in yrs) for k in h}
    s2 = {k: sum(data[y][k][1] for y in yrs) / sum(data[y][k][0] for y in yrs) for k in h}
    for lo, hi in CLASSES + ((0, float("inf")),):
        s = [k for k in h if lo <= pops[2024][k] < hi]
        lab = "all" if (lo, hi) == (0, float("inf")) else f"{lo:,}-{hi:,}"
        out.append(f"  {lab} | {len(s)} | {q([i2[k] for k in s])} | share 33/34 median {np.median([s2[k] for k in s]):.0%}")
    rho3, p3 = spearmanr([pops[2024][k] for k in h], [i2[k] for k in h])
    out.append(f"  Spearman population against payments 34 per inhabitant: rho {rho3:+.2f}, p {p3:.3f}")
    miss = sorted(set(pops[2024]) - set(g), key=lambda k: pops[2024][k])
    out.append(f"\nmunicipalities without all five years: {len(miss)}, median population {np.median([pops[2024][k] for k in miss]):,.0f} against {np.median([pops[2024][k] for k in g]):,.0f} with")
    text = "\n".join(out)
    print(text)
    (DER / "investment.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
