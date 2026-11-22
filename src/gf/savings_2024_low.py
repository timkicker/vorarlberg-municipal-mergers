"""Lower variant for the elected-bodies part of E24, scaled to the Styrian effect against the combined control group.

Run from the repository root.
Writes data/derived/savings_2024_low.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import elected_bodies as eb  # noqa: E402
import savings_2024 as s24  # noqa: E402
import styria_control as sc  # noqa: E402

STYRIAN_000, COMBINED_000 = sc.effects_000()
SCALE = COMBINED_000 / STYRIAN_000  # 000 effect against the combined control group over effect against Styrian controls


def main() -> None:
    DER = s24.DER
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
    core, total = s24.accounts()
    have = [k for k in total if k in pop]
    tot96 = sum(total[k] for k in have) * sum(pop.values()) / sum(pop[k] for k in have)
    lines = ["Lower variant of the elected bodies in E24 (savings_2024_low.py)",
             f"factor {SCALE:.3f} = {COMBINED_000:.1f} / {STYRIAN_000:.1f} euro per inhabitant (combined control group against Styrian controls); spending 2024 scaled up {tot96 / 1e6:,.0f} m", "",
             "Partition | O m (smaller to larger fit) | O low m | E24 before m | E24 new m | in % of spending new"]
    units = collections.defaultdict(list)
    for r in csv.DictReader(open(DER / "fag_units.csv")):
        units[r["partition"]].append(r)
    for cut, rs in units.items():
        O1 = O2 = Vcov = Ecov = Eall = 0.0
        for r in rs:
            gs = [by_name[m] for m in r["members"].split(";")]
            if len(gs) < 2:
                continue
            inh = [pop[x] for x in gs]
            Eall += sum(inh)
            O1 += sum(lin(x) for x in inh) - lin(sum(inh))
            O2 += sum(lgl(x) for x in inh) - lgl(sum(inh))
            if all(x in core for x in gs):
                Vcov += s24.V_SHARE * sum(core[x] for x in gs)
                Ecov += sum(inh)
        Vall = Vcov / Ecov * Eall if Ecov else float("nan")
        lo, hi = min(O1, O2), max(O1, O2)
        low = lo * SCALE
        lines.append(f"{cut} | {lo / 1e6:.2f} to {hi / 1e6:.2f} | {low / 1e6:.2f} | {lo / 1e6:.2f} to {(hi + Vall) / 1e6:.2f} | "
                     f"{low / 1e6:.2f} to {(hi + Vall) / 1e6:.2f} | {low / tot96:.2%} to {(hi + Vall) / tot96:.2%}")
    text = "\n".join(lines)
    print(text)
    (DER / "savings_2024_low.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
