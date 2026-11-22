"""Spending on elected bodies (sub-section 000) in Vorarlberg and the saving per set of merged units.

Writes data/derived/elected_bodies.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import personnel  # noqa: E402
import styria_control as sc  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
CLASSES = ((0, 1000), (1001, 2000), (2001, 5000), (5001, 10000), (10001, 10**9))
# columns of the closing account files of offenerhaushalt.at
COL_MVAG = "Mvag"  # MVAG code
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_VALUE = "Wert"  # amount


def organs(year: int = 2024) -> dict:
    out = {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        v = 0.0
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r[COL_SUBSECTION] != "000":
                    continue
                if r[COL_MVAG][:2] == "32":
                    v += personnel.num(r[COL_VALUE])
                elif r[COL_MVAG][:2] == "31":
                    v -= personnel.num(r[COL_VALUE])
        out[path.name.split("_")[1]] = v
    return out


def main() -> None:
    names = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(DER / "pareto_partitions.csv"))}
    by_name = {v: k for k, v in names.items()}
    o = organs()
    pop = ba.fag_pop(2024)
    g = [k for k in o if k in pop]
    e = np.array([pop[k] for k in g])
    y = np.array([o[k] for k in g])
    lines = ["Elected bodies (sub-section 000) in Vorarlberg, closing accounts 2024, net (elected_bodies.py)",
             f"municipalities with file and population: {len(g)} of 96; 000 net below zero: {int((y <= 0).sum())}", ""]
    lines.append("1. euros per inhabitant by size class: municipalities | median per inhabitant | total per inhabitant | median per municipality")
    for lo, hi in CLASSES:
        m = (e >= lo) & (e <= hi)
        if m.any():
            lines.append(f"  {lo}-{hi if hi < 10**9 else 'more'} | {m.sum()} | {np.median(y[m] / e[m]):.1f} | "
                         f"{y[m].sum() / e[m].sum():.1f} | {np.median(y[m]):,.0f}")
    X = np.column_stack([np.ones_like(e), e])
    (a, b), *_ = np.linalg.lstsq(X, y, rcond=None)
    r2 = 1 - ((y - X @ [a, b]) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    ok = y > 0
    (c, ex), *_ = np.linalg.lstsq(np.column_stack([np.ones(ok.sum()), np.log(e[ok])]), np.log(y[ok]), rcond=None)
    lines += ["", f"2. linear: a = {a:,.0f} euros per municipality, b = {b:.2f} euros per inhabitant, R² {r2:.2f}",
              f"   log-log (only 000 > 0, n {ok.sum()}): elasticity e = {ex:.3f}", ""]
    lin = lambda n: a + b * n  # noqa: E731
    lgl = lambda n: float(np.exp(c + ex * np.log(n)))  # noqa: E731

    units = collections.defaultdict(list)
    for r in csv.DictReader(open(DER / "fag_units.csv")):
        units[r["partition"]].append(r)
    lines.append("3. saving per partition, units of at least two municipalities")
    lines.append("partition | units | municipalities in them | inhabitants in them | linear m | log-log m | linear per inhabitant | log-log per inhabitant | observed sum before minus linear prediction after, only units with all files")
    for cut, rs in units.items():
        n = k = 0
        E = S1 = S2 = obs = 0.0
        nobs = 0
        for r in rs:
            gs = [by_name[mb] for mb in r["members"].split(";")]
            if len(gs) < 2:
                continue
            n += 1
            k += len(gs)
            inh = [pop[x] for x in gs]
            E += sum(inh)
            S1 += sum(lin(x) for x in inh) - lin(sum(inh))
            S2 += sum(lgl(x) for x in inh) - lgl(sum(inh))
            if all(x in o for x in gs):
                nobs += 1
                obs += sum(o[x] for x in gs) - lin(sum(inh))
        spread = abs(S1 - S2) / max(abs(S1), abs(S2)) if max(abs(S1), abs(S2)) else 0
        lines.append(f"{cut} | {n} | {k} | {E:,.0f} | {S1 / 1e6:.2f} | {S2 / 1e6:.2f} | {S1 / E:.1f} | {S2 / E:.1f} | "
                     f"{nobs} units: {obs / 1e6:.2f} m against linear after" + (" | models more than 30 % apart" if spread > 0.3 else ""))
    lines += ["", f"4. Styria against the Styrian controls: {-sc.effects_000()[0]:.1f} euros per inhabitant (styria_control.txt)"]
    text = "\n".join(lines)
    print(text)
    (DER / "elected_bodies.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
