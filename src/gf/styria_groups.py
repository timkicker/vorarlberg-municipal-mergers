"""Styrian mergers by budget group, tax shares, charges and the run-up years.

Writes data/derived/styria_groups.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_outcomes as so  # noqa: E402
from accounts_columns import COL_DEBT, COL_EXTRAORDINARY_SPENDING, COL_FEES, COL_INHABITANTS, COL_ORDINARY_SPENDING, COL_REVENUE, COL_SPENDING, COL_TAX_SHARES

so.FIELDS = so.FIELDS + (COL_TAX_SHARES, COL_FEES)
GROUPS = tuple(str(i) for i in range(10))
NAMES = {"0": "Representative bodies and general administration", "1": "Public order and safety",
         "2": "Education, upbringing, sport and science", "3": "Art, culture and religion",
         "4": "Social welfare and housing subsidies", "5": "Health", "6": "Road and water engineering, transport",
         "7": "Economic development", "8": "Services", "9": "Public finance"}


def group_money() -> dict:
    """(gkz, year) -> {group: [gross, net]}"""
    g = collections.defaultdict(lambda: {k: [0.0, 0.0] for k in GROUPS})
    for y in s.YEARS:
        for r in csv.DictReader((s.RAW / f"gemua_at_{y}.csv").open(encoding="utf-8"), delimiter=";"):
            sub_code = r["C-VAUAB-0"].removeprefix("VAUAB-")
            out, inc = float(r[COL_SPENDING]), float(r[COL_REVENUE])
            cell = g[(r["C-C41-2"], y)][sub_code[0]]
            cell[0] += out
            cell[1] += out - inc
    return g


def attach_groups(st: list, others: list, gm: dict) -> None:
    mp, _ = s.mapping()
    pre = collections.defaultdict(list)
    for code, (n, _share) in mp.items():
        pre[n].append(code)
    for u in st:
        for t in s.YEARS:
            codes = pre[u["id"]] if t in s.PRE else [u["id"]]
            for k in GROUPS:
                u["raw"][t]["G" + k] = sum(gm[(c, t)][k][0] for c in codes)
                u["raw"][t]["N" + k] = sum(gm[(c, t)][k][1] for c in codes)
    for u in others:
        for t in s.YEARS:
            for k in GROUPS:
                u["raw"][t]["G" + k] = gm[(u["id"], t)][k][0]
                u["raw"][t]["N" + k] = gm[(u["id"], t)][k][1]


def run(us_pair: dict, fn, log: bool, rng, label: str) -> list[str]:
    lines = [label]
    for name, us in us_pair.items():
        r = so.estimate(us, so.values(us, fn, log, False), s.YEARS, set(s.POST), name != so.STYRIAN_CONTROL, rng)
        pct = f"  i.e. {np.expm1(r['b']):+.1%} ({np.expm1(r['lo']):+.1%} to {np.expm1(r['hi']):+.1%})" if log else " EUR"
        lines.append(f"  {name} (n {r['n']}, dropped {r['dropped']}): {r['b']:+.3f}  95 % [{r['lo']:+.3f}, {r['hi']:+.3f}]{pct}")
    return lines


def runup(us_pair: dict, fn, log: bool, rng, label: str) -> list[str]:
    per = {"base": (2010, 2011), "run-up": (2012, 2013, 2014), "after": s.POST}
    lines = [label]
    for name, us in us_pair.items():
        vals = []
        for u in us:
            pc = {p: np.mean([fn(u["raw"][t]) / u["raw"][t][COL_INHABITANTS] for t in ys]) for p, ys in per.items()}
            vals.append(None if log and any(v <= 0 for v in pc.values()) else
                        {k: (np.log(v) if log else v) for k, v in pc.items()})
        parts = []
        for p in ("run-up", "after"):
            sub = [{"base": v["base"], p: v[p]} if v else None for v in vals]
            r = so.estimate(us, sub, ("base", p), {p}, name != so.STYRIAN_CONTROL, rng)
            unit = f" ({np.expm1(r['b']):+.1%})" if log else " EUR"
            parts.append(f"{p} {r['b']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]{unit}")
        lines.append(f"  {name}: " + "; ".join(parts))
    return lines


def main() -> None:
    st, others = so.units()
    attach_groups(st, others, group_money())
    allu = st + others
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    pair = {so.STYRIAN_CONTROL: st, "combined control group, year x size tercile": allu}
    rng = np.random.default_rng(s.SEED)
    big = [u for u in st if u["treated"] and u["raw"][2016][COL_INHABITANTS] > 10000]
    crossed = big
    lines = [f"Styria {len(st)} units ({sum(u['treated'] for u in st)} merged), other states {len(others)}",
             f"merged units with more than 10,000 inhabitants in 2016: {len(crossed)} "
             f"({', '.join(sorted(u['id'] for u in crossed))})", ""]
    lines.append("A. Gross spending by budget group per inhabitant, log")
    for k in GROUPS:
        lines += run(pair, lambda v, k=k: v["G" + k], True, rng, f" Group {k} {NAMES[k]}")
    lines.append("")
    lines.append("B. Net spending by budget group per inhabitant, EUR")
    for k in GROUPS:
        lines += run(pair, lambda v, k=k: v["N" + k], False, rng, f" Group {k} {NAMES[k]}")
    lines.append("")
    lines.append("C. Revenue")
    lines += run(pair, lambda v: v[COL_TAX_SHARES], True, rng, " tax shares per inhabitant, log")
    lines += run(pair, lambda v: v[COL_FEES], True, rng, " fees per inhabitant, log")
    lines.append("")
    lines.append("D. Run-up, periods 2010-11, 2012-14, 2016-19, gap against 2010-11")
    lines += runup(pair, lambda v: v[COL_ORDINARY_SPENDING], True, rng, " ordinary spending per inhabitant, log")
    lines += runup(pair, lambda v: v[COL_EXTRAORDINARY_SPENDING], True, rng, " extraordinary spending per inhabitant, log")
    lines += runup(pair, lambda v: v[COL_DEBT], False, rng, " debt per inhabitant, EUR")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_groups.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
