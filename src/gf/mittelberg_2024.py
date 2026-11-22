"""Threshold 5000 with Mittelberg as a unit of its own: E24 and money balance.

Same formulas as savings_2024.py, savings_2024_low.py, fag.py, state_grants.py and
balance_2024.py --low. Writes data/derived/mittelberg_2024.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import elected_bodies as eb  # noqa: E402
import fag  # noqa: E402
import savings_2024 as s24  # noqa: E402
import state_grants as lg  # noqa: E402
from savings_2024_low import SCALE  # noqa: E402

CUT = "Threshold 5000"
MITTELBERG = "80228"


def e24(units: dict, pop: dict, lin, lgl, core: dict) -> tuple[float, float, int]:
    """Lower end (lower variant of the elected bodies) and upper end in euro, number of merged units."""
    O1 = O2 = Vcov = Ecov = Eall = 0.0
    n = 0
    for gs in units.values():
        if len(gs) < 2:
            continue
        n += 1
        inh = [pop[x] for x in gs]
        Eall += sum(inh)
        O1 += sum(lin(x) for x in inh) - lin(sum(inh))
        O2 += sum(lgl(x) for x in inh) - lgl(sum(inh))
        if all(x in core for x in gs):
            Vcov += s24.V_SHARE * sum(core[x] for x in gs)
            Ecov += sum(inh)
    Vall = Vcov / Ecov * Eall
    return min(O1, O2) * SCALE, max(O1, O2) + Vall, n


def fag_parts(units: dict, pop: dict, stays: dict) -> dict:
    """Inflow and shifts inside Vorarlberg as in fag.main, euro."""
    vbg = sorted(g for g in pop if g.startswith("8"))
    pop_at, pop_v = sum(pop.values()), sum(pop[g] for g in vbg)
    abs_at, abs_v = fag.austria_abs(pop)
    pool = fag.ADVANCE_AT - fag.TRANSFER_TAX_MUNICIPALITIES
    model_v = pool * (fag.SHARE_POPULATION * pop_v / pop_at + fag.SHARE_GRADED * abs_v / abs_at + fag.SHARE_FIX * fag.FIX_VBG)
    actual_v = fag.ADVANCE_VBG - fag.TRANSFER_TAX_MUNICIPALITIES * pop_v / pop_at
    if abs(model_v / actual_v - 1) > 0.05:
        pool *= actual_v / model_v
    pot_v = actual_v * (1 - fag.STATE_GRANT_SHARE) * 1e6
    base = fag.distribute({g: [g] for g in vbg}, pop, stays, pot_v)
    abs_v1 = sum(fag.abs_factor(sum(pop[g] for g in m)) for m in units.values())
    inflow = pool * fag.SHARE_GRADED * (abs_v1 / (abs_at - abs_v + abs_v1) - abs_v / abs_at) * (1 - fag.STATE_GRANT_SHARE) * 1e6
    new = fag.distribute(units, pop, stays, pot_v + inflow)
    same = fag.distribute(units, pop, stays, pot_v)
    r = collections.Counter()
    for u, m in units.items():
        before = sum(base[g]["total"] for g in m)
        if len(m) == 1:
            r["same_out"] += same[u]["total"] - before
            r["same_in"] += new[u]["total"] - before
        else:
            r["merged"] += same[u]["total"] - before
    r["inflow"] = inflow
    r["over10k"] = sum(1 for u, m in units.items() if len(m) > 1 and new[u]["inh"] > 10000
                       and all(pop[g] <= 10000 for g in m))
    return r


def main() -> None:
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv")))
    main_units = collections.defaultdict(list)
    for r in rows:
        main_units[r[CUT]].append(r["gkz"])
    var_units = collections.defaultdict(list)
    for r in rows:
        var_units["Mittelberg" if r["gkz"] == MITTELBERG else r[CUT]].append(r["gkz"])
    assert {r["gkz"]: r["municipality"] for r in rows}[MITTELBERG] == "Mittelberg"
    assert any(MITTELBERG in m and len(m) > 1 for m in main_units.values())

    pop24 = ba.fag_pop(2024)
    o = eb.organs()
    g = [k for k in o if k in pop24]
    e = np.array([pop24[k] for k in g])
    y = np.array([o[k] for k in g])
    (a, b), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(e), e]), y, rcond=None)
    (c, ex), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(e), np.log(e)]), np.log(y), rcond=None)
    lin = lambda n: a + b * n  # noqa: E731
    lgl = lambda n: float(np.exp(c + ex * np.log(n)))  # noqa: E731
    core, _ = s24.accounts()

    popf, stays = fag.load_pop(), fag.load_stays(2023)
    base = {r["gkz"]: [r["gkz"]] for r in rows}
    s0, z0, _ = lg.totals(base, popf)

    out = ["Threshold 5000 with Mittelberg as a unit of its own, E24 and money balance, m EUR per year (mittelberg_2024.py)", "",
           "Partition | merged units | new over 10,000 | E24 (lower variant to upper bound) | inflow | "
           "Vorarlberg total | merged units with inflow | unchanged municipalities | Austria | other states"]
    for name, units in (("Threshold 5000", main_units), ("Threshold 5000, Mittelberg alone", var_units)):
        elo, ehi, n = e24(units, pop24, lin, lgl, core)
        f = fag_parts(units, popf, stays)
        s, z, oo = lg.totals(units, popf)
        lo, hi = s - s0 + z - z0, s - s0 + z - z0 + oo
        to_merged = f["inflow"] - (f["same_in"] - f["same_out"])
        M = 1e6
        out.append(f"{name} | {n} | {f['over10k']} | {elo / M:.1f} to {ehi / M:.1f} | {f['inflow'] / M:.1f} | "
                   f"{(elo + f['inflow']) / M:.1f} to {(ehi + f['inflow']) / M:.1f} | "
                   f"{(f['merged'] + to_merged + elo + lo) / M:.1f} to {(f['merged'] + to_merged + ehi + hi) / M:.1f} | "
                   f"{(f['same_in'] - hi) / M:.1f} to {(f['same_in'] - lo) / M:.1f} | {elo / M:.1f} to {ehi / M:.1f} | {-f['inflow'] / M:+.1f}")
    out += ["", "Cross-check: the first line must match balance_2024_low.txt (Threshold 5000) to within 0.1 m."]
    text = "\n".join(out)
    print(text)
    (fag.DER / "mittelberg_2024.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
