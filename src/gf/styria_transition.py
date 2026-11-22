"""Transition costs of the Styrian mergers: event study 2010 to 2019 with 2015.

Writes data/derived/styria_transition.txt.
"""

import csv
import math
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402

s.YEARS = tuple(range(2010, 2020))  # adds the merger year 2015; PRE stays 2010 to 2014
import costs  # noqa: E402
import styria_outcomes as so  # noqa: E402
from accounts_columns import COL_DEBT, COL_EXTRAORDINARY_SPENDING, COL_INHABITANTS, COL_ORDINARY_SPENDING, COL_SPENDING

BASE = 2013
TRANS, LATER = (2014, 2015, 2016), (2017, 2018, 2019)


def core_gross() -> dict:
    g = {}
    for y in s.YEARS:
        for r in csv.DictReader((s.RAW / f"gemua_at_{y}.csv").open(encoding="utf-8"), delimiter=";"):
            if costs.subsection_code(r["C-VAUAB-0"]) in costs.CORE:
                k = (r["C-C41-2"], y)
                g[k] = g.get(k, 0.0) + float(r[COL_SPENDING])
    return g


def event(us: list, fn, log: bool, group_fe: bool, rng) -> list[tuple]:
    years = list(s.YEARS)
    keep = []
    for u in us:
        pc = [fn(u["raw"][t]) / u["raw"][t][COL_INHABITANTS] for t in years]
        if log and min(pc) <= 0:
            continue
        keep.append((u, np.log(pc) if log else np.array(pc)))
    n, T = len(keep), len(years)
    y = np.concatenate([v for _, v in keep])
    unit = np.repeat(np.arange(n), T)
    per = np.tile(np.arange(T), n)
    tr = np.repeat([float(u["treated"]) for u, _ in keep], T)
    ev = [tr * (per == p) for p in range(T) if years[p] != BASE]
    if group_fe:
        grp = np.repeat([u["group"] for u, _ in keep], T)
        fe = [((grp == g) & (per == p)).astype(float) for g in sorted(set(grp)) for p in range(1, T)]
    else:
        fe = [(per == p).astype(float) for p in range(1, T)]
    X = np.column_stack(ev + fe)
    k = len(ev)
    b = s.twfe(y, X, unit)[:k]
    bs = []
    for _ in range(s.N_BOOT):
        pick = rng.integers(0, n, n)
        idx = (pick[:, None] * T + np.arange(T)).ravel()
        bs.append(s.twfe(y[idx], X[idx], unit[:len(idx)])[:k])
    bs = np.array(bs)
    yrs = [t for t in years if t != BASE]
    # transition excess: mean of 2014-16 minus mean of 2017-19, per bootstrap draw
    ti = [yrs.index(t) for t in TRANS]
    li = [yrs.index(t) for t in LATER]
    ex = b[ti].mean() - b[li].mean()
    exb = bs[:, ti].mean(1) - bs[:, li].mean(1)
    rows = [(t, b[i], np.percentile(bs[:, i], 2.5), np.percentile(bs[:, i], 97.5)) for i, t in enumerate(yrs)]
    rows.append(("2014-16 minus 2017-19", ex, np.percentile(exb, 2.5), np.percentile(exb, 97.5)))
    return n, rows


def main() -> None:
    st, others = so.units()
    cg = core_gross()
    mp, _ = s.mapping()
    pre = {}
    for code, (nw, _sh) in mp.items():
        pre.setdefault(nw, []).append(code)
    in_st = {id(u) for u in st}
    for u in st + others:
        for t in s.YEARS:
            codes = (pre[u["id"]] if t in s.PRE else [u["id"]]) if id(u) in in_st else [u["id"]]
            u["raw"][t]["core"] = sum(cg.get((c, t), 0.0) for c in codes)
    allu = st + others
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    outcomes = (("core administration gross per inhabitant, log", lambda v: v["core"], True),
                ("ordinary spending per inhabitant, log", lambda v: v[COL_ORDINARY_SPENDING], True),
                ("extraordinary spending per inhabitant, EUR", lambda v: v[COL_EXTRAORDINARY_SPENDING], False),
                ("debt per inhabitant, EUR", lambda v: v[COL_DEBT], False))
    rng = np.random.default_rng(s.SEED)
    lines = [f"Event study Styria 2010-2019 with 2015, reference year {BASE} (styria_transition.py)",
             f"Styria {len(st)} units ({sum(u['treated'] for u in st)} merged), other states {len(others)}"]
    est = {}
    for name, fn, log in outcomes:
        lines.append(f"\n{name}")
        for label, us, gfe in (("Styrian control", st, False), ("combined control group, year x size tercile", allu, True)):
            n, rows = event(us, fn, log, gfe, rng)
            lines.append(f"  {label} (n {n})")
            for t, b, lo, hi in rows:
                lines.append(f"    {t}: {b:+.3f}  95 % [{lo:+.3f}, {hi:+.3f}]")
            if log:
                est[(name, label)] = dict((t, b) for t, b, _, _ in rows)
    merged = [u for u in st if u["treated"]]

    def level(field: str, t: int) -> float:
        return sum(u["raw"][t][field] for u in merged) / sum(u["raw"][t][COL_INHABITANTS] for u in merged)

    lines.append(f"\nMerged units, EUR per inhabitant (sum over units / population), {BASE} and 2014")
    for label, field in (("core administration gross", "core"), ("core administration net", "net"), ("ordinary spending", COL_ORDINARY_SPENDING)):
        lines.append(f"  {label}: {level(field, BASE):.0f} -> {level(field, 2014):.0f}")
    lines.append(f"  core administration revenue: {level('core', BASE) - level('net', BASE):.0f} -> {level('core', 2014) - level('net', 2014):.0f}")
    lines.append(f"  rise of core administration net in 2014: {level('net', 2014) - level('net', BASE):.0f}")
    lines.append(f"\nIn EUR per inhabitant of the merged units, on the {BASE} level: 2014 = level x (exp(b) - 1); 2014-16 minus 2017-19 = level x (exp(d) - 1) x 3")
    for name, field in (("core administration gross per inhabitant, log", "core"), ("ordinary spending per inhabitant, log", COL_ORDINARY_SPENDING)):
        for (n, label), e in est.items():
            if n == name:
                base = level(field, BASE)
                lines.append(f"  {name.split(' per')[0]}, {label}: 2014 {base * (math.exp(e[2014]) - 1):.0f}; "
                             f"2014-16 minus 2017-19 {base * (math.exp(e['2014-16 minus 2017-19']) - 1) * 3:.0f}")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_transition.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
