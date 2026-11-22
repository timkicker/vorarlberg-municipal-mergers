"""Savings per set of merged units at 2024 prices: elected bodies plus the rest of core administration.

Writes data/derived/savings_2024.txt and savings_2024_office_top.txt.
"""

import collections
import csv
import pathlib
import re
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import elected_bodies as eb  # noqa: E402
import pareto  # noqa: E402
import personnel  # noqa: E402
from costs import CORE  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
V_SHARE = 1 - np.exp(-0.035)  # Styrian effect on core administration without 000 (styria_control.txt, log -0.035), upper bound
# Columns of the offenerhaushalt.at files offenerhaushalt_*_YYYY_ra_fhh_gemeinde.csv
COL_MVAG = "Mvag"  # MVAG code
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_VALUE = "Wert"  # amount


def office_top() -> float:
    """Share at the top of the 95 % range of the Styrian office effect (styria_control.txt)."""
    line = next(x for x in (DER / "styria_control.txt").read_text().splitlines() if x.strip().startswith("Styrian control: log"))
    lo = float(re.search(r"\[([-+][\d.]+),", line).group(1))
    return 1 - np.exp(lo)


def cost_curve_estimates() -> dict[str, tuple[float, float]]:
    """Cost-curve estimate per partition in m EUR at prices of 2016-19 from robustness.txt, row df 4.

    The file gives the main factor; the cautious one is scaled from it with the factors of pareto.py.
    """
    lines = (DER / "robustness.txt").read_text(encoding="utf-8").splitlines()
    head = next(x for x in lines if "E m EUR:" in x)
    names = [c.strip() for c in head.split("E m EUR:")[1].split("|")]
    row = next(x for x in lines if x.strip().startswith("df 4 ") and "weighted" not in x)
    values = [float(v) for v in row.split()[2 + 6:2 + 6 + len(names) - 1]]
    return {n: (v, v * pareto.SCALE_LOW / pareto.SCALE_MAIN) for n, v in zip(names, values)}


def accounts(year: int = 2024) -> tuple[dict, dict]:
    """gkz -> core administration without 000, net; gkz -> total payments (MVAG 32 and 34)."""
    core, total = {}, {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        c = t = 0.0
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                mv, w = r[COL_MVAG][:2], personnel.num(r[COL_VALUE])
                if mv in ("32", "34"):
                    t += w
                sub = r[COL_SUBSECTION]
                if sub in CORE and sub != "000":
                    if mv == "32":
                        c += w
                    elif mv == "31":
                        c -= w
        g = path.name.split("_")[1]
        core[g], total[g] = c, t
    return core, total


def main() -> None:
    curve = cost_curve_estimates()
    names = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(DER / "pareto_partitions.csv"))}
    by_name = {v: k for k, v in names.items()}
    pop = ba.fag_pop(2024)
    o = eb.organs()
    g = [k for k in o if k in pop]
    e = np.array([pop[k] for k in g])
    y = np.array([o[k] for k in g])
    (a, b), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(e), e]), y, rcond=None)
    (c, ex), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(e), np.log(e)]), np.log(y), rcond=None)
    lin = lambda n: a + b * n  # noqa: E731
    lgl = lambda n: float(np.exp(c + ex * np.log(n)))  # noqa: E731

    core, total = accounts()
    have = [k for k in total if k in pop]
    tot96 = sum(total[k] for k in have) * sum(pop.values()) / sum(pop[k] for k in have)
    lines = ["Savings per partition, prices 2024: elected bodies (O) plus the rest of core administration (V) (savings_2024.py)",
             f"municipalities with a file 2024: {len(have)}; payments MVAG 32 and 34 of these municipalities {sum(total[k] for k in have) / 1e6:,.0f} m, "
             f"scaled up to 96 by population {tot96 / 1e6:,.0f} m",
             f"V upper bound: {V_SHARE:.1%} of the rest of core administration of the predecessors, lower bound 0", "",
             f"Partition | units | O m (smaller to larger fit) | V covered m (units) | V scaled up m | E24 m | E24 in % of spending | cost curve, factor {pareto.SCALE_MAIN:.2f} / {pareto.SCALE_LOW:.2f}, prices 2016-19"]
    tops = ["", f"Upper end with the office at the top of its 95 % range ({office_top():.1%}, factor {office_top() / V_SHARE:.2f})",
            "Partition | E24 upper m | in % of spending"]
    units = collections.defaultdict(list)
    for r in csv.DictReader(open(DER / "fag_units.csv")):
        units[r["partition"]].append(r)
    for cut, rs in units.items():
        n = ncov = 0
        O1 = O2 = Vcov = Ecov = Eall = 0.0
        for r in rs:
            gs = [by_name[m] for m in r["members"].split(";")]
            if len(gs) < 2:
                continue
            n += 1
            inh = [pop[x] for x in gs]
            Eall += sum(inh)
            O1 += sum(lin(x) for x in inh) - lin(sum(inh))
            O2 += sum(lgl(x) for x in inh) - lgl(sum(inh))
            if all(x in core for x in gs):
                ncov += 1
                Vcov += V_SHARE * sum(core[x] for x in gs)
                Ecov += sum(inh)
        Vall = Vcov / Ecov * Eall if Ecov else float("nan")
        lo, hi = min(O1, O2), max(O1, O2)
        old = curve.get(cut, (float("nan"), float("nan")))
        tops.append(f"{cut} | {(hi + Vall * office_top() / V_SHARE) / 1e6:.2f} | {(hi + Vall * office_top() / V_SHARE) / tot96:.2%}")
        lines.append(f"{cut} | {n} | {lo / 1e6:.2f} to {hi / 1e6:.2f} | {Vcov / 1e6:.2f} ({ncov}) | {Vall / 1e6:.2f} | "
                     f"{lo / 1e6:.2f} to {(hi + Vall) / 1e6:.2f} | {lo / tot96:.2%} to {(hi + Vall) / tot96:.2%} | {old[0]:.2f} / {old[1]:.2f}")
    text = "\n".join(lines)
    print(text)
    (DER / "savings_2024.txt").write_text(text + "\n")
    top = "\n".join(["Savings per partition with the office at the top of its range (savings_2024.py)"] + tops)
    print(top)
    (DER / "savings_2024_office_top.txt").write_text(top + "\n")


if __name__ == "__main__":
    sys.exit(main())
