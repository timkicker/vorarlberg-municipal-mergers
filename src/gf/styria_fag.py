"""Test of the tax share model on the Styrian mergers of 2015.

Writes data/derived/styria_fag.txt.
"""

import collections
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_outcomes as so  # noqa: E402
from accounts_columns import COL_INHABITANTS, COL_TAX_SHARES

so.FIELDS = so.FIELDS + (COL_TAX_SHARES,)
XS_LOW, XS_MID = 7.23, 79.58  # Styria 2015, FAG 2008 § 11(7a)
F_LOW, F_MID = 1 + 41 / 67, 5 / 3  # § 9(10)


def extra_share(n: float) -> float:
    """Extra share per inhabitant times inhabitants, Styria 2015, up to 20,000."""
    if n <= 9300:
        return XS_LOW * n
    if n <= 10000:
        return XS_LOW * n + (n - 9300) * (XS_MID - XS_LOW) * 10000 / 700
    return XS_MID * n


def graded_pop(n: float) -> float:
    if n <= 10000:
        return n * F_LOW + (110 / 201 * (n - 9000) if n > 9000 else 0.0)
    return n * F_MID + (10 / 3 * (n - 18000) if n > 18000 else 0.0)


def tax_shares_pc(u: dict, t: int) -> float:
    return u["raw"][t][COL_TAX_SHARES] / u["raw"][t][COL_INHABITANTS]


def main() -> None:
    st, others = so.units()
    mp, _ = s.mapping()
    _, pop = s.money()
    preds = collections.defaultdict(list)
    for code, (n, _share) in mp.items():
        preds[n].append(code)
    for u in st:
        u["pre_pop"] = [pop[(c, s.REF)] for c in preds[u["id"]]] if u["treated"] else [u["raw"][s.REF][COL_INHABITANTS]]
        n16 = u["raw"][2016][COL_INHABITANTS]
        if not u["treated"]:
            u["cls"] = "unchanged"
        elif max(u["pre_pop"]) > 10000:
            u["cls"] = "predecessor over 10,000"
        elif n16 > 10000:
            u["cls"] = "crossed 10,000"
        else:
            u["cls"] = "merged under 10,000"
    allu = st + others
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    for u in others:
        u["cls"] = "other states"

    small = [u for u in st if u["cls"] == "unchanged" and u["raw"][2016][COL_INHABITANTS] <= 10000]
    # rest per unit of the graded key, approximated from unchanged small Styrian units in 2016
    rest_per_graded = (sum(u["raw"][2016][COL_TAX_SHARES] for u in small)
                    - sum(extra_share(u["raw"][2016][COL_INHABITANTS]) for u in small)) / sum(graded_pop(u["raw"][2016][COL_INHABITANTS]) for u in small)
    lines = ["FAG test on Styria 2015 (styria_fag.py)", "",
             f"Rest per unit of the graded key 2016, approximated from {len(small)} unchanged "
             f"Styrian units up to 10,000: {rest_per_graded:,.1f} EUR", ""]
    crossed = [u for u in st if u["cls"] == "crossed 10,000"]
    lines.append("1. Per unit: prediction against measurement, EUR per inhabitant")
    lines.append("  Unit | pop 2016 | predecessors | tax shares 2013 predecessors | prediction extra share | prediction key | prediction % | measured % against unchanged small")
    ctrl = np.mean([np.mean([tax_shares_pc(u, t) for t in s.POST]) / np.mean([tax_shares_pc(u, t) for t in so.BEFORE]) for u in small])
    preds_pct, meas_pct = [], []
    for u in sorted(crossed, key=lambda x: x["id"]):
        n = u["raw"][2016][COL_INHABITANTS]
        d_xs = (extra_share(n) - sum(extra_share(p) for p in u["pre_pop"])) / n
        d_graded = rest_per_graded * (graded_pop(n) - sum(graded_pop(p) for p in u["pre_pop"])) / n
        base = u["raw"][2013][COL_TAX_SHARES] / u["raw"][2013][COL_INHABITANTS]
        pred = (d_xs + d_graded) / base
        meas = np.mean([tax_shares_pc(u, t) for t in s.POST]) / np.mean([tax_shares_pc(u, t) for t in so.BEFORE]) / ctrl - 1
        preds_pct.append(pred)
        meas_pct.append(meas)
        lines.append(f"  {u['id']} | {n:,.0f} | {len(u['pre_pop'])} | {base:,.0f} | {d_xs:+.1f} | {d_graded:+.1f} | {pred:+.1%} | {meas:+.1%}")
    lines.append(f"  Mean: prediction {np.mean(preds_pct):+.1%}, measured {np.mean(meas_pct):+.1%}")
    lines.append("  Prediction without the loss of the overnight stay share of the beverage tax compensation; prices 2015, measurement 2016-19.")
    lines.append("")

    rng = np.random.default_rng(s.SEED)
    lines.append("2. Difference in differences, tax shares per inhabitant, log")
    for cls in ("crossed 10,000", "merged under 10,000", "predecessor over 10,000"):
        for name, base_set, fe in (("Styrian control", [u for u in st if u["cls"] == "unchanged"], False),
                                   ("combined control group", [u for u in allu if u["cls"] in ("unchanged", "other states")], True)):
            us = [dict(u, treated=(u["cls"] == cls)) for u in base_set + [u for u in st if u["cls"] == cls]]
            r = so.estimate(us, so.values(us, lambda v: v[COL_TAX_SHARES], True, False), s.YEARS, set(s.POST), fe, rng)
            k = sum(u["treated"] for u in us)
            lines.append(f"  {cls} ({k}), {name}: {np.expm1(r['b']):+.1%} ({np.expm1(r['lo']):+.1%} to {np.expm1(r['hi']):+.1%})")
    lines.append("")

    lines.append("3. Event study, units that crossed 10,000 against unchanged Styrian units, reference 2014, log")
    us = [dict(u, treated=(u["cls"] == "crossed 10,000")) for u in st if u["cls"] in ("unchanged", "crossed 10,000")]
    vals = so.values(us, lambda v: v[COL_TAX_SHARES], True, False)
    keep = [(u, v) for u, v in zip(us, vals) if v is not None]
    years = s.YEARS
    rows = [(i, u, v, t) for i, (u, v) in enumerate(keep) for t in years]
    unit = np.array([r[0] for r in rows])
    y = np.array([r[2][r[3]] for r in rows])
    tr = np.array([r[1]["treated"] for r in rows], float)
    yr = np.array([r[3] for r in rows])
    ev = [t for t in years if t != s.REF]
    X = np.column_stack([tr * (yr == t) for t in ev] + [(yr == t).astype(float) for t in ev])
    b = s.twfe(y, X, unit)[: len(ev)]
    n, T = len(keep), len(years)
    bs = []
    for _ in range(s.N_BOOT):
        pick = rng.integers(0, n, n)
        idx = (pick[:, None] * T + np.arange(T)).ravel()
        bs.append(s.twfe(y[idx], X[idx], np.repeat(np.arange(n), T))[: len(ev)])
    bs = np.array(bs)
    for j, t in enumerate(ev):
        lines.append(f"  {t}: {np.expm1(b[j]):+.1%} ({np.expm1(np.percentile(bs[:, j], 2.5)):+.1%} to {np.expm1(np.percentile(bs[:, j], 97.5)):+.1%})")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_fag.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
