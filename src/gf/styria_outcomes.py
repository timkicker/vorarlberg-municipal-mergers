"""Other outcomes of the Styrian mergers, from GemHH.

F-SEIN_SUMME is used as is: it is smaller than F-SEIN_GEBUEHREN in 8470 of
22272 rows of 2010 to 2019, so it does not contain the charges.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
from accounts_columns import COL_DEBT, COL_EXTRAORDINARY_SPENDING, COL_INHABITANTS, COL_ORDINARY_REVENUE, COL_ORDINARY_SPENDING, COL_OWN_REVENUE

STYRIAN_CONTROL = "Styrian control"  # label of the Styrian control group; estimate() uses year effects only for the other labels
BEFORE = (2010, 2011, 2012, 2013)  # as in the descriptive table of the cost backtest
FIELDS = (COL_ORDINARY_SPENDING, COL_ORDINARY_REVENUE, COL_EXTRAORDINARY_SPENDING, COL_OWN_REVENUE, COL_DEBT, COL_INHABITANTS)
OUTCOMES = (
    # name, transform per capita values, log, periods collapsed
    ("ordinary spending per inhabitant, log", lambda v: v[COL_ORDINARY_SPENDING], True, False),
    ("extraordinary spending per inhabitant, log of the period mean", lambda v: v[COL_EXTRAORDINARY_SPENDING], True, True),
    ("ordinary result per inhabitant, EUR", lambda v: v[COL_ORDINARY_REVENUE] - v[COL_ORDINARY_SPENDING], False, False),
    ("debt per inhabitant, EUR", lambda v: v[COL_DEBT], False, False),
    ("municipal levies without fees per inhabitant, log", lambda v: v[COL_OWN_REVENUE], True, False),
)


def municipal_accounts() -> dict:
    d = {}
    for r in csv.DictReader((s.RAW / "gemhh_at_2000_2019.csv").open(encoding="utf-8"), delimiter=";"):
        y = int(r["C-A10-0"].removeprefix("A10-"))
        if y in s.YEARS:
            d[(r["C-C41-2"], y)] = {f: float(r[f]) for f in FIELDS}
    return d


def units() -> tuple[list, list]:
    """Same unit set as the cost backtest: (styrian units, others), each with raw sums per year."""
    mp, _ = s.mapping()
    m, pop = s.money()
    hh = municipal_accounts()
    pre = collections.defaultdict(list)
    for g, (n, share) in mp.items():
        pre[n].append((g, share))
    early = {n for n, gs in pre.items() if any((g, 2012) not in m for g, _ in gs)}
    st = []
    for n, gs in sorted(pre.items()):
        if n == s.GRAZ or n in early:
            continue
        ys, ok = {}, True
        for t in s.YEARS:
            codes = [g for g, _ in gs] if t in s.PRE else [n]
            if not all((c, t) in m and (c, t) in hh for c in codes):
                ok = False
                break
            ys[t] = {f: sum(hh[(c, t)][f] for c in codes) for f in FIELDS}
            ys[t]["net"] = sum(m[(c, t)][0] for c in codes)
        if ok and all(v["net"] > 0 for v in ys.values()):  # the cost backtest's exclusion
            st.append({"id": n, "treated": len(gs) >= 2, "raw": ys})
    codes_by_year = {t: {k for (k, yy) in m if yy == t} for t in s.YEARS}
    stable = set.intersection(*codes_by_year.values())
    others = []
    for g in sorted(stable):
        if g[0] in "69" or not all((g, t) in hh for t in s.YEARS) or hh[(g, s.REF)][COL_INHABITANTS] >= 10000:
            continue
        if all(m[(g, t)][0] > 0 for t in s.YEARS):  # same filter as the cost backtest
            others.append({"id": g, "treated": False, "raw": {t: hh[(g, t)] for t in s.YEARS}})
    return st, others


def values(us: list, fn, log: bool, collapse: bool):
    """Return (periods, list of per-unit dict period -> value) or None for units with invalid values."""
    out = []
    for u in us:
        pc = {t: fn(u["raw"][t]) / u["raw"][t][COL_INHABITANTS] for t in s.YEARS}
        if collapse:
            pc = {"before": np.mean([pc[t] for t in s.PRE]), "after": np.mean([pc[t] for t in s.POST])}
        if log and any(v <= 0 for v in pc.values()):
            out.append(None)
            continue
        out.append({k: (np.log(v) if log else v) for k, v in pc.items()})
    return out


def estimate(us: list, vals: list, periods: tuple, post: set, group_fe: bool, rng) -> dict:
    keep = [(u, v) for u, v in zip(us, vals) if v is not None]
    rows = [(i, u, v, t) for i, (u, v) in enumerate(keep) for t in periods]
    unit = np.array([r[0] for r in rows])
    per = np.array([periods.index(r[3]) for r in rows])
    tr = np.array([r[1]["treated"] for r in rows], float)
    y = np.array([r[2][r[3]] for r in rows])
    if group_fe:
        grp = np.array([r[1]["group"] for r in rows])
        fe = [((grp == g) & (per == p)).astype(float) for g in sorted(set(grp)) for p in range(1, len(periods))]
    else:
        fe = [(per == p).astype(float) for p in range(1, len(periods))]
    isp = np.array([r[3] in post for r in rows], float)
    X = np.column_stack([tr * isp] + fe)
    b = s.twfe(y, X, unit)[0]
    n, T = len(keep), len(periods)
    bs = []
    for _ in range(s.N_BOOT):
        pick = rng.integers(0, n, n)
        idx = (pick[:, None] * T + np.arange(T)).ravel()
        bs.append(s.twfe(y[idx], X[idx], np.repeat(np.arange(n), T))[0])
    return {"n": n, "dropped": len(us) - n, "b": b, "lo": np.percentile(bs, 2.5), "hi": np.percentile(bs, 97.5)}


def pooled(us: list, fn, collapse_label: str) -> str:
    """Summed per-capita table."""
    parts = []
    for name, sel in collapse_label:
        g = [u for u in us if sel(u)]
        a = sum(fn(u["raw"][t]) for u in g for t in BEFORE) / sum(u["raw"][t][COL_INHABITANTS] for u in g for t in BEFORE)
        b = sum(fn(u["raw"][t]) for u in g for t in s.POST) / sum(u["raw"][t][COL_INHABITANTS] for u in g for t in s.POST)
        parts.append(f"{name} {a:,.0f} -> {b:,.0f} EUR ({b - a:+,.0f}, {b / a - 1:+.1%})")
    return "  summed per inhabitant, 2010-13 -> 2016-19: " + "; ".join(parts)


def main() -> None:
    st, others = units()
    allu = st + others
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    lines = [f"Styria {len(st)} units ({sum(u['treated'] for u in st)} merged), other states {len(others)}"]
    groups = (("merged", lambda u: u["id"][0] == "6" and u["treated"]), ("unchanged", lambda u: u["id"][0] == "6" and not u["treated"]), ("rest of AT", lambda u: u["id"][0] != "6"))
    rng = np.random.default_rng(s.SEED)
    for name, fn, log, collapse in OUTCOMES:
        periods = ("before", "after") if collapse else s.YEARS
        post = {"after"} if collapse else set(s.POST)
        lines.append(f"\n{name}")
        for label, us in ((STYRIAN_CONTROL, st), ("combined control group, year x size tercile", allu)):
            r = estimate(us, values(us, fn, log, collapse), periods, post, label != STYRIAN_CONTROL, rng)
            pct = f"  i.e. {np.expm1(r['b']):+.1%} ({np.expm1(r['lo']):+.1%} to {np.expm1(r['hi']):+.1%})" if log else " EUR"
            lines.append(f"  {label} (n {r['n']}, dropped {r['dropped']}): {r['b']:+.3f}  95 % [{r['lo']:+.3f}, {r['hi']:+.3f}]{pct}")
        lines.append(pooled(allu, fn, groups))
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_outcomes.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
