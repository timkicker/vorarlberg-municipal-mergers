"""Law of 1/n before the Styrian mergers of 2015: do smaller partners spend and borrow more in the last years?

Writes data/derived/free_riding.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria  # noqa: E402
from accounts_columns import COL_DEBT, COL_EXTRAORDINARY_SPENDING, COL_INHABITANTS, COL_ORDINARY_SPENDING

COLS = {"extraordinary spending": COL_EXTRAORDINARY_SPENDING, "debt": COL_DEBT, "ordinary spending": COL_ORDINARY_SPENDING}
BASE = {COL_EXTRAORDINARY_SPENDING: (2010, 2011, 2012), COL_DEBT: (2012,), COL_ORDINARY_SPENDING: (2010, 2011, 2012)}


def read() -> dict:
    d = collections.defaultdict(dict)
    for r in csv.DictReader((styria.RAW / "gemhh_at_2000_2019.csv").open(encoding="utf-8"), delimiter=";"):
        y = int(r["C-A10-0"].removeprefix("A10-"))
        g = r["C-C41-2"]
        if g.startswith("6") and 2010 <= y <= 2014:
            d[g][y] = {k: float(r[k] or 0) for k in list(COLS.values()) + [COL_INHABITANTS]}
    return d


def sample():
    mp, _ = styria.mapping()
    d = read()
    rows = []
    for g, (unit, share) in mp.items():
        if g == styria.GRAZ or share < styria.SPLIT_SHARE or g not in d or any(y not in d[g] for y in range(2010, 2015)):
            continue
        rows.append({"g": g, "unit": unit, "d": d[g]})
    size = collections.defaultdict(float)
    n = collections.Counter(r["unit"] for r in rows)
    for r in rows:
        size[r["unit"]] += r["d"][2013][COL_INHABITANTS]
    for r in rows:
        r["merged"] = n[r["unit"]] > 1
        r["freeride"] = 1 - r["d"][2013][COL_INHABITANTS] / size[r["unit"]] if r["merged"] else 0.0
    return rows


def change(r, col, year):
    pc = lambda y: r["d"][y][col] / r["d"][y][COL_INHABITANTS]  # noqa: E731
    return pc(year) - np.mean([pc(y) for y in BASE[col]])


def fit_a(rows, y):
    """Within-unit slope of y on freeride (unit fixed effects)."""
    by = collections.defaultdict(list)
    for r, v in zip(rows, y):
        by[r["unit"]].append((r["freeride"], v))
    x, z = [], []
    for vals in by.values():
        f = np.array([a for a, _ in vals])
        v = np.array([b for _, b in vals])
        x.extend(f - f.mean())
        z.extend(v - v.mean())
    x, z = np.array(x), np.array(z)
    return float((x @ z) / (x @ x))


def fit_b(rows, y):
    X = np.column_stack([np.ones(len(rows)), [float(r["merged"]) for r in rows], [r["freeride"] for r in rows]])
    b, *_ = np.linalg.lstsq(X, np.array(y), rcond=None)
    return b[1], b[2]


def boot(rows, fn, n_out):
    units = sorted({r["unit"] for r in rows})
    idx = collections.defaultdict(list)
    for i, r in enumerate(rows):
        idx[r["unit"]].append(i)
    rng = np.random.default_rng(styria.SEED)
    out = []
    for _ in range(styria.N_BOOT):
        pick = rng.choice(len(units), len(units))
        ii, rr = [], []
        for k, u in enumerate(pick):
            for i in idx[units[u]]:
                ii.append(i)
                rr.append(dict(rows[i], unit=f"{units[u]}#{k}"))
        out.append(fn(rr, ii))
    out = np.array(out).reshape(styria.N_BOOT, n_out)
    return np.percentile(out, [2.5, 97.5], axis=0)


def main() -> None:
    rows = sample()
    merged = [r for r in rows if r["merged"]]
    med = float(np.median([r["freeride"] for r in merged]))
    lines = ["Law of 1/n before the Styrian mergers (free_riding.py)", ""]
    lines.append(f"municipalities {len(rows)}, of which predecessors of merged units {len(merged)} in {len({r['unit'] for r in merged})} units")
    lines.append(f"freeride among the predecessors: median {med:.2f}, 10th to 90th percentile {np.percentile([r['freeride'] for r in merged], 10):.2f} to {np.percentile([r['freeride'] for r in merged], 90):.2f}")
    lines.append("")
    lines.append("outcome | year | A: freeride within the unit, EUR per inhabitant [95 %] | A at the median | B: merged [95 %] | B: freeride [95 %]")
    for name, col in COLS.items():
        for year in (2014, 2013):
            ya = [change(r, col, year) for r in merged]
            yb = [change(r, col, year) for r in rows]
            a = fit_a(merged, ya)
            ca = boot(merged, lambda rr, ii: [fit_a(rr, [ya[i] for i in ii])], 1)
            b1, b2 = fit_b(rows, yb)
            cb = boot(rows, lambda rr, ii: list(fit_b(rr, [yb[i] for i in ii])), 2)
            lines.append(f"  {name} | {year} | {a:+.0f} [{ca[0, 0]:+.0f}, {ca[1, 0]:+.0f}] | {a * med:+.0f} | {b1:+.0f} [{cb[0, 0]:+.0f}, {cb[1, 0]:+.0f}] | {b2:+.0f} [{cb[0, 1]:+.0f}, {cb[1, 1]:+.0f}]")
    text = "\n".join(lines)
    print(text)
    (styria.OUT / "free_riding.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
