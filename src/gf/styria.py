"""Backtest: did the Styrian mergers of 1 January 2015 lower administrative costs?"""

import collections
import csv
import json
import pathlib
import sys

import numpy as np
import shapely
from shapely.geometry import shape

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from accounts_columns import COL_INHABITANTS, COL_REVENUE, COL_SPENDING
from costs import CORE  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
PRE = (2010, 2011, 2012, 2013, 2014)
POST = (2016, 2017, 2018, 2019)
YEARS = PRE + POST
REF = 2014
GRAZ = "60101"
SPLIT_SHARE = 0.95
N_BOOT, SEED = 2000, 12345


def polygons(year: int, prefix: str) -> dict:
    geo = json.loads((RAW / f"boundaries_statat_at_{year}.geojson").read_text())
    return {f["properties"]["g_id"]: shape(f["geometry"]) for f in geo["features"] if f["properties"]["g_id"].startswith(prefix)}


def mapping() -> tuple[dict, dict]:
    """2014 code -> (2015 code, share of its area in that unit)."""
    old, new = polygons(2014, "6"), polygons(2015, "6")
    codes = list(new)
    tree = shapely.STRtree([new[c] for c in codes])
    res = {}
    for g, p in old.items():
        best = max(((codes[i], p.intersection(new[codes[i]]).area) for i in tree.query(p)), key=lambda x: x[1])
        res[g] = (best[0], best[1] / p.area)
    return res, new


def money() -> tuple[dict, dict]:
    """(gkz, year) -> [net core, gross core], (gkz, year) -> population."""
    m = collections.defaultdict(lambda: [0.0, 0.0])
    for y in YEARS:
        for r in csv.DictReader((RAW / f"gemua_at_{y}.csv").open(encoding="utf-8"), delimiter=";"):
            key = (r["C-C41-2"], y)
            if r["C-VAUAB-0"].removeprefix("VAUAB-") in CORE:
                out, inc = float(r[COL_SPENDING]), float(r[COL_REVENUE])
                m[key][0] += out - inc
                m[key][1] += out
            else:
                m[key]  # register the municipality-year
    pop = {}
    for r in csv.DictReader((RAW / "gemhh_at_2000_2019.csv").open(encoding="utf-8"), delimiter=";"):
        y = int(r["C-A10-0"].removeprefix("A10-"))
        if y in YEARS:
            pop[(r["C-C41-2"], y)] = float(r[COL_INHABITANTS])
    return m, pop


def twfe(y: np.ndarray, X: np.ndarray, unit: np.ndarray, w: np.ndarray | None = None) -> np.ndarray:
    """OLS with unit fixed effects on a balanced panel, by demeaning within units.
    w: optional weights that are constant within a unit (weighted least squares)."""
    def dm(a):
        a = np.asarray(a, float)
        means = np.zeros((unit.max() + 1,) + a.shape[1:])
        np.add.at(means, unit, a)
        return a - (means / np.bincount(unit).reshape((-1,) + (1,) * (a.ndim - 1)))[unit]
    sw = np.ones(len(y)) if w is None else np.sqrt(w)
    beta, *_ = np.linalg.lstsq(dm(X) * sw[:, None], dm(y) * sw, rcond=None)
    return beta


def panel(units: list[dict], col: int, group_fe: bool, years: tuple = YEARS, ref: int = REF):
    """Stack a balanced panel. units: dicts with id, treated, group, y[year] -> (net, gross, pop)."""
    rows = [(i, u, t) for i, u in enumerate(units) for t in years]
    unit = np.array([i for i, _, _ in rows])
    yr = np.array([t for *_, t in rows])
    tr = np.array([u["treated"] for _, u, _ in rows], float)
    y = np.log(np.array([u["y"][t][col] / u["y"][t][2] for _, u, t in rows]))
    if group_fe:
        grp = np.array([u["group"] for _, u, _ in rows])
        fe = [((grp == g) & (yr == t)).astype(float) for g in sorted(set(grp)) for t in years[1:]]
    else:
        fe = [(yr == t).astype(float) for t in years[1:]]
    did = tr * np.isin(yr, POST)
    es = [tr * (yr == t) for t in years if t != ref]
    return y, unit, np.column_stack([did] + fe), np.column_stack(es + fe)


def boot(units: list[dict], col: int, group_fe: bool, rng, years: tuple = YEARS, ref: int = REF, weighted: bool = False) -> dict:
    y, unit, Xd, Xe = panel(units, col, group_fe, years, ref)
    T = len(years)
    w = np.repeat([u["y"][REF][2] for u in units], T) if weighted else None
    b = twfe(y, Xd, unit, w)[0]
    e = twfe(y, Xe, unit, w)[: T - 1]
    n = len(units)
    bs, es = [], []
    for _ in range(N_BOOT):
        pick = rng.integers(0, n, n)
        rows = (pick[:, None] * T + np.arange(T)).ravel()
        newunit = np.repeat(np.arange(n), T)
        bs.append(twfe(y[rows], Xd[rows], newunit, None if w is None else w[rows])[0])
        es.append(twfe(y[rows], Xe[rows], newunit, None if w is None else w[rows])[: T - 1])
    es = np.array(es)
    return {"b": b, "lo": np.percentile(bs, 2.5), "hi": np.percentile(bs, 97.5), "es": e, "es_lo": np.percentile(es, 2.5, 0), "es_hi": np.percentile(es, 97.5, 0), "years": years, "ref": ref}


def others_all(m: dict, pop: dict) -> list[dict]:
    """All municipalities outside Styria and Vienna without a change of area 2010 to 2019, any size."""
    codes_by_year = [{k for (k, yy) in m if yy == t} for t in YEARS]
    keep = sorted(g for g in set.intersection(*codes_by_year) if g[0] not in "69" and all((g, t) in pop for t in YEARS))
    return [{"id": g, "y": {t: (m[(g, t)][0], m[(g, t)][1], pop[(g, t)]) for t in YEARS}} for g in keep]


def describe(units: list[dict], rest: list[dict]) -> list[str]:
    """Descriptive sums that show where the difference between the control groups comes from.
    Net core administration per inhabitant as sum over units and years."""
    before, after = (2010, 2011, 2012, 2013), POST
    groups = (("Styria, merged", [u for u in units if u["treated"]]), ("Styria, unchanged", [u for u in units if not u["treated"]]),
              ("rest of Austria without Vienna, without change of area", rest))
    out = ["\nDescriptive: net core administration costs per inhabitant, sum over units and years, 2010-2013 against 2016-2019"]
    for name, us in groups:
        pc = {}
        for k, yrs in (("before", before), ("after", after)):
            pc[k] = sum(u["y"][t][0] for u in us for t in yrs) / sum(u["y"][t][2] for u in us for t in yrs)
        gr = sum(u["y"][t][2] for u in us for t in after) / sum(u["y"][t][2] for u in us for t in before) - 1
        out.append(f"  {name} (n = {len(us)}): population {gr:+.1%}, per inhabitant {pc['before']:.0f} -> {pc['after']:.0f} EUR, {pc['after'] / pc['before'] - 1:+.1%}")
    organs = collections.defaultdict(float)
    all_years = [y for y in range(2010, 2020) if (RAW / f"gemua_at_{y}.csv").exists()]
    for y in all_years:
        for r in csv.DictReader((RAW / f"gemua_at_{y}.csv").open(encoding="utf-8"), delimiter=";"):
            if r["C-VAUAB-0"].removeprefix("VAUAB-") == "000":
                organs[(r["C-C41-2"], y)] += float(r[COL_SPENDING]) - float(r[COL_REVENUE])
    out.append("  Subsection 000 (elected bodies), net, m EUR, sum over the units of the panel:")
    for name, us in groups[:2]:
        vals = []
        for y in all_years:
            codes = [c for u in us for c in ([g for g, _ in u["pred"]] if y < 2015 else [u["id"]])]
            vals.append(f"{y}: {sum(organs[(c, y)] for c in codes) / 1e6:.1f}")
        out.append(f"    {name}: " + "  ".join(vals))
    return out


def main() -> None:
    mp, new = mapping()
    m, pop = money()
    pre = collections.defaultdict(list)
    for g, (n, share) in mp.items():
        pre[n].append((g, share))
    split = {n for n, gs in pre.items() if any(s < SPLIT_SHARE for _, s in gs)}
    lines = [f"2014: {len(mp)} municipalities, 2015: {len(new)} units, without predecessor: {sorted(set(new) - set(pre))}"]
    lines.append(f"Units with a split predecessor (< {SPLIT_SHARE:.0%} of area): {len(split)}")
    # unit whose predecessors exist only from 2013 on (merged 2013)
    early = {n for n, gs in pre.items() if any((g, 2012) not in m for g, _ in gs)}
    lines.append(f"Units with a change of area in 2013: {sorted(early)}")
    units, dropped = [], collections.Counter()
    for n, gs in sorted(pre.items()):
        if n == GRAZ:
            dropped["Graz"] += 1
            continue
        if n in early:
            dropped["2013"] += 1
            continue
        ys = {}
        ok = True
        for t in YEARS:
            codes = [g for g, _ in gs] if t in PRE else [n]
            if not all((c, t) in m and (c, t) in pop for c in codes):
                ok = False
                break
            ys[t] = (sum(m[(c, t)][0] for c in codes), sum(m[(c, t)][1] for c in codes), sum(pop[(c, t)] for c in codes))
        if not ok:
            dropped["data missing"] += 1
            continue
        if any(v[0] <= 0 for v in ys.values()):
            dropped["net <= 0"] += 1
            continue
        units.append({"id": n, "treated": len(gs) >= 2, "split": n in split, "pred": [(g, pop[(g, REF)]) for g, _ in gs], "y": ys})
    lines.append(f"Units in panel {len(units)}, treated {sum(u['treated'] for u in units)}, control {sum(not u['treated'] for u in units)}, dropped {dict(dropped)}")

    # second control group: unchanged municipalities elsewhere, < 10,000 inhabitants
    codes_by_year = {t: {k for (k, yy) in m if yy == t} for t in YEARS}
    stable = set.intersection(*codes_by_year.values())
    others = []
    for g in sorted(stable):
        if g[0] in "69" or not all((g, t) in pop for t in YEARS) or pop[(g, REF)] >= 10000:
            continue
        ys = {t: (m[(g, t)][0], m[(g, t)][1], pop[(g, t)]) for t in YEARS}
        if all(v[0] > 0 for v in ys.values()):
            others.append({"id": g, "treated": False, "split": False, "pred": [], "y": ys})
    allu = units + others
    cuts = np.quantile([u["y"][REF][2] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["y"][REF][2]))
    lines.append(f"Second control group: {len(others)} municipalities of other states, bounds of the size terciles {cuts[0]:,.0f} and {cuts[1]:,.0f} inhabitants")

    # cross-section prediction from the net cost curve
    curve = np.loadtxt(OUT / "cost_curve_net.csv", delimiter=",", skiprows=1)
    lc = lambda p: np.interp(np.log(p), np.log(curve[:, 0]), np.log(curve[:, 1]))  # noqa: E731
    preds = []
    for u in units:
        if u["treated"]:
            ps = np.array([p for _, p in u["pred"]])
            before = np.log(np.sum(ps * np.exp(lc(ps))) / ps.sum())
            preds.append(lc(ps.sum()) - before)
    pred = float(np.mean(preds))
    lines.append(f"Cost curve prediction for the treated units: log {pred:+.3f}, i.e. {np.expm1(pred):+.1%}")

    rng = np.random.default_rng(SEED)
    runs = [
        ("Main: net, Styrian control", units, 0, False),
        ("Check: gross, Styrian control", units, 1, False),
        ("Check: net, without split predecessors", [u for u in units if not u["split"]], 0, False),
        ("Check: net, combined control group, year x size tercile", allu, 0, True),
        # shows why the two control groups disagree
        ("Placebo: Styrian controls against other states, net, year x size tercile",
         [dict(u, treated=True) for u in allu if u["id"].startswith("6") and not u["treated"]] + others, 0, True),
    ]
    runs = [(*r, {}) for r in runs]
    no14 = tuple(t for t in YEARS if t != 2014)
    tr_only = [u for u in units if u["treated"]]
    runs += [
        ("Main without 2014 (before 2010 to 2013)", units, 0, False, {"years": no14, "ref": 2013}),
        ("Combined control group without 2014", allu, 0, True, {"years": no14, "ref": 2013}),
        ("Control other states only", tr_only + others, 0, True, {}),
        ("Control other states only without 2014", tr_only + others, 0, True, {"years": no14, "ref": 2013}),
        ("Main weighted by population 2014", units, 0, False, {"weighted": True}),
    ]
    for name, us, col, gfe, kw in runs:
        r = boot(us, col, gfe, rng, **kw)
        lines.append(f"\n{name} (n = {len(us)})")
        lines.append(f"  Effect log {r['b']:+.3f}  95 % [{r['lo']:+.3f}, {r['hi']:+.3f}]  i.e. {np.expm1(r['b']):+.1%} ({np.expm1(r['lo']):+.1%} to {np.expm1(r['hi']):+.1%})")
        yrs = [t for t in r["years"] if t != r["ref"]]
        lines.append(f"  Event study (reference {r['ref']}): " + "  ".join(f"{t}: {v:+.3f} [{lo:+.3f}, {hi:+.3f}]" for t, v, lo, hi in zip(yrs, r["es"], r["es_lo"], r["es_hi"])))
    lines += describe(units, others_all(m, pop))
    text = "\n".join(lines)
    print(text)
    (OUT / "styria.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
