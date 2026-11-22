"""District bootstrap, state placebo for the elected bodies, net scenario and price level.

Writes data/derived/styria_bootstrap.txt.
"""

import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_clean_controls as c  # noqa: E402
import styria_no2014 as n14  # noqa: E402
import styria_outcomes as so  # noqa: E402
from accounts_columns import COL_CPI, COL_INHABITANTS, COL_ORDINARY_REVENUE, COL_ORDINARY_SPENDING

NO14 = tuple(t for t in s.YEARS if t != 2014)


def organs_fit() -> tuple[float, float, float]:
    """Measured Styrian saving on the elected bodies and the predictions of the log-log and the linear fit,
    EUR per inhabitant, read from organs_styria.txt."""
    rows = {}
    for line in (s.OUT / "organs_styria.txt").read_text().splitlines():
        parts = [x.strip() for x in line.split("|")]
        if len(parts) == 3 and parts[2].replace(".", "", 1).isdigit():
            rows[parts[0].split(" ")[0]] = float(parts[2])
    return rows["measured"], rows["log-log"], rows["linear"]


MEASURED, LOGLOG, LINEAR = organs_fit()  # EUR per inhabitant


def design(us: list, vals: list, periods: tuple, gfe: bool):
    """Rows of the two-way fixed effects model, as in styria_outcomes.estimate."""
    keep = [(u, v) for u, v in zip(us, vals) if v is not None]
    rows = [(i, u, v, t) for i, (u, v) in enumerate(keep) for t in periods]
    unit = np.array([r[0] for r in rows])
    per = np.array([periods.index(r[3]) for r in rows])
    tr = np.array([r[1]["treated"] for r in rows], float)
    y = np.array([r[2][r[3]] for r in rows])
    if gfe:
        grp = np.array([r[1]["group"] for r in rows])
        fe = [((grp == g) & (per == p)).astype(float) for g in sorted(set(grp)) for p in range(1, len(periods))]
    else:
        fe = [(per == p).astype(float) for p in range(1, len(periods))]
    isp = np.array([r[3] in s.POST for r in rows], float)
    return [u for u, _ in keep], y, np.column_stack([tr * isp] + fe), unit, len(periods)


def did(us, vals, periods, gfe) -> float:
    _, y, X, unit, _ = design(us, vals, periods, gfe)
    return s.twfe(y, X, unit)[0]


def by_district(us, vals, periods, gfe, rng) -> dict:
    """Point estimate and a bootstrap that draws districts (first three digits) with all their units."""
    kept, y, X, unit, T = design(us, vals, periods, gfe)
    b = s.twfe(y, X, unit)[0]
    dist = np.array([u["id"][:3] for u in kept])
    names = sorted(set(dist))
    members = {d: np.flatnonzero(dist == d) for d in names}
    bs = []
    for _ in range(s.N_BOOT):
        pick = np.concatenate([members[names[k]] for k in rng.integers(0, len(names), len(names))])
        idx = (pick[:, None] * T + np.arange(T)).ravel()
        bs.append(s.twfe(y[idx], X[idx], np.repeat(np.arange(len(pick)), T))[0])
    return {"n": len(kept), "d": len(names), "b": b, "lo": np.percentile(bs, 2.5), "hi": np.percentile(bs, 97.5)}


def fmt(r, log) -> str:
    if log:
        return (f"log {r['b']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}] ({np.expm1(r['b']):+.1%}, "
                f"{np.expm1(r['lo']):+.1%} to {np.expm1(r['hi']):+.1%}), n {r['n']}, districts {r['d']}")
    return f"{r['b']:+.1f} EUR per inhabitant [{r['lo']:+.1f}, {r['hi']:+.1f}], n {r['n']}, districts {r['d']}"


def vpi() -> dict:
    out = {}
    with open(s.RAW / "vpi15.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            z = r["C-VPIZR-0"].removeprefix("VPIZR-")
            if r["C-VPI5-0"] == "VPI-0" and len(z) == 4:
                out[int(z)] = float(r[COL_CPI].replace(",", "."))
    return out


def merged_population() -> list:
    rows = []
    for line in (s.OUT / "total_spending_2024.txt").read_text().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) > 2 and parts[1].replace(",", "").isdigit():
            rows.append((parts[0], int(parts[1].replace(",", ""))))
    return rows


def main() -> None:
    rng = np.random.default_rng(s.SEED)
    out = ["Bootstrap by district, state placebo for the elected bodies, net scenario, price level (styria_bootstrap.py)", ""]

    out.append("A. Bootstrap by district")
    units, _, m = c.build()
    found, _ = c.changed(units, m)
    clean = [u for u in units if u["id"] not in found]
    vals = [{t: np.log(u["y"][t][0] / u["y"][t][2]) for t in s.YEARS} for u in clean]
    out.append(f"  Main run cleaned, core administration net log, Styrian control: {fmt(by_district(clean, vals, s.YEARS, False, rng), True)}")
    st, others = n14.setup()
    for tag, per in (("with 2014", s.YEARS), ("without 2014", NO14)):
        v = so.values(st, lambda x: x[COL_ORDINARY_SPENDING], True, False)
        out.append(f"  ordinary spending log, Styrian control, {tag}: {fmt(by_district(st, v, per, False, rng), True)}")
    for name, us, gfe in (("Styrian control", st, False), ("combined control group", st + others, True)):
        for tag, per in (("with 2014", s.YEARS), ("without 2014", NO14)):
            v = so.values(us, lambda x: x["u000"], False, False)
            out.append(f"  000 net EUR, {name}, {tag}: {fmt(by_district(us, v, per, gfe, rng), False)}")

    out += ["", "B. State placebo, 000 net EUR per inhabitant, each other state against the remaining six"]
    for tag, per in (("with 2014", s.YEARS), ("without 2014", NO14)):
        res = {}
        for state in "1234578":
            us = [dict(u, treated=u["id"][0] == state) for u in others]
            cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in us], [1 / 3, 2 / 3])
            for u in us:
                u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
            res[state] = did(us, so.values(us, lambda x: x["u000"], False, False), per, True)
        sd = np.std(list(res.values()), ddof=1)
        out.append(f"  {tag}: " + ", ".join(f"state {k} {v:+.1f}" for k, v in res.items()) + f"; SD {sd:.1f}, double SD {2 * sd:.1f}")

    out += ["", "C. Net scenario: ordinary result per inhabitant, EUR"]
    res = {}
    for name, us, gfe in (("Styrian control", st, False), ("combined control group", st + others, True)):
        for tag, per in (("with 2014", s.YEARS), ("without 2014", NO14)):
            v = so.values(us, lambda x: x[COL_ORDINARY_REVENUE] - x[COL_ORDINARY_SPENDING], False, False)
            r = so.estimate(us, v, per, set(s.POST), gfe, rng)
            res[(name, tag)] = r["b"]
            out.append(f"  {name}, {tag}: {r['b']:+.1f} EUR per inhabitant [{r['lo']:+.1f}, {r['hi']:+.1f}], n {r['n']}")
    p = vpi()
    lift = p[2024] / np.mean([p[t] for t in s.POST])
    out.append(f"  m euros a year, population of the merged units times result; prices 2016-19 / with CPI (VPI) to 2024 (factor {lift:.3f})")
    for part, inh in merged_population():
        cells = [f"{k[0]} {k[1]} {inh * b / 1e6:.1f} / {inh * b * lift / 1e6:.1f}" for k, b in res.items()]
        out.append(f"  {part} ({inh:,} inhabitants): " + "; ".join(cells))

    out += ["", "D. Price level"]
    out.append("  VPI 2015=100, annual average: " + ", ".join(f"{t} {p[t]:.1f}" for t in (*s.POST, 2024)))
    out.append(f"  factor 2024 / mean 2016-19: {lift:.3f}")
    out.append(f"  measured {MEASURED:.1f} EUR per inhabitant, in 2024 prices {MEASURED * lift:.1f}; prediction log-log {LOGLOG}, linear {LINEAR}")
    text = "\n".join(out)
    print(text)
    (s.OUT / "styria_bootstrap.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
