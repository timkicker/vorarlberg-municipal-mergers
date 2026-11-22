"""Is the Styrian control group untreated? Elected bodies (000) apart, merged districts, fixed pot.

Writes data/derived/styria_control.txt.
"""

import collections
import csv
import pathlib
import re
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_outcomes as so  # noqa: E402
from accounts_columns import COL_INHABITANTS, COL_REVENUE, COL_SPENDING
from costs import CORE  # noqa: E402

MERGED_DISTRICTS = ("620", "621", "622", "623")  # Murtal, Bruck-Muerzzuschlag, Hartberg-Fuerstenfeld, Suedoststeiermark


def effects_000() -> tuple[float, float]:
    """Saving on the elected bodies (sub-section 000, EUR per inhabitant, positive) against the Styrian controls
    and against the combined control group, read from styria_control.txt."""
    block = (s.OUT / "styria_control.txt").read_text().split("1. Subsection 000 net alone")[1].split("\n\n")[0]
    val = {}
    for line in block.splitlines():
        m = re.match(r"\s*(Styrian control|Combined control group, year x size tercile): (-?[\d.]+) EUR", line)
        if m:
            val[m.group(1)] = -float(m.group(2))
    return val["Styrian control"], val["Combined control group, year x size tercile"]


def split_money() -> dict:
    """(gkz, year) -> {"without000": net core without 000, "u000": net 000}."""
    m = collections.defaultdict(lambda: {"without000": 0.0, "u000": 0.0})
    for y in s.YEARS:
        for r in csv.DictReader((s.RAW / f"gemua_at_{y}.csv").open(encoding="utf-8"), delimiter=";"):
            sub_code = r["C-VAUAB-0"].removeprefix("VAUAB-")
            if sub_code in CORE:
                net = float(r[COL_SPENDING]) - float(r[COL_REVENUE])
                m[(r["C-C41-2"], y)]["u000" if sub_code == "000" else "without000"] += net
    return m


def fmt(r: dict, log: bool) -> str:
    if log:
        return (f"log {r['b']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}] ({np.expm1(r['b']):+.1%}, "
                f"{np.expm1(r['lo']):+.1%} to {np.expm1(r['hi']):+.1%}), n {r['n']}, dropped {r['dropped']}")
    return f"{r['b']:+.1f} EUR per inhabitant [{r['lo']:+.1f}, {r['hi']:+.1f}], n {r['n']}, dropped {r['dropped']}"


def main() -> None:
    st, others = so.units()
    mp, _ = s.mapping()
    pre = collections.defaultdict(list)
    for code, (n, _share) in mp.items():
        pre[n].append(code)
    m = split_money()
    for u in st:
        for t in s.YEARS:
            codes = pre[u["id"]] if t in s.PRE else [u["id"]]
            for k in ("without000", "u000"):
                u["raw"][t][k] = sum(m[(c, t)][k] for c in codes)
    for u in others:
        for t in s.YEARS:
            u["raw"][t] = dict(u["raw"][t], **m[(u["id"], t)])
    allu = st + others
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    placebo = [dict(u, treated=True) for u in st if not u["treated"]] + others
    runs = [("Styrian control", st, False), ("Combined control group, year x size tercile", allu, True),
            ("Placebo: Styrian controls against other states, year x size tercile", placebo, True)]
    rng = np.random.default_rng(s.SEED)
    per, post = s.YEARS, set(s.POST)
    lines = ["Is the Styrian control group untreated? (styria_control.py)",
             f"Units Styria {len(st)} ({sum(u['treated'] for u in st)} merged), other states {len(others)}", ""]
    targets = [("1. Core administration net without 000, per inhabitant", lambda v: v["without000"], True),
               ("1. Subsection 000 net alone", lambda v: v["u000"], False),
               ("Consistency check: core administration net with 000 (backtest)", lambda v: v["net"] if "net" in v else v["without000"] + v["u000"], True)]
    for label, fn, log in targets:
        lines.append(label)
        for name, us, gfe in runs:
            r = so.estimate(us, so.values(us, fn, log, False), per, post, gfe, rng)
            lines.append(f"  {name}: {fmt(r, log)}")
        lines.append("")

    keep = [u for u in st if not u["id"].startswith(MERGED_DISTRICTS)]
    lines.append("2. Main run (net with 000, Styrian control) without the four districts merged in 2012/13")
    lines.append(f"  dropped {len(st) - len(keep)} units ({sum(u['treated'] for u in st) - sum(u['treated'] for u in keep)} merged)")
    r = so.estimate(keep, so.values(keep, lambda v: v["net"], True, False), per, post, False, rng)
    lines.append(f"  {fmt(r, True)}")
    lines.append("")

    e = sum(u["raw"][s.REF][COL_INHABITANTS] for u in st)
    sh = sum(u["raw"][s.REF][COL_INHABITANTS] for u in st if u["treated"]) / e
    lines.append(f"3. Fixed pot: population share of the merged units in the panel 2014 s = {sh:.3f}")
    # estimates printed in styria_transfers.txt and styria_transfers_2024.txt, typed here because those scripts run later
    for name, b in (("state grants 2016-19", -10.0), ("section 94 2020-24", -35.8)):
        lines.append(f"  {name}: estimated {b:+.1f}, with a fully fixed pot the loss of the merged units themselves {b * (1 - sh):+.1f} EUR per inhabitant")
    lines.append("")
    lines.append("4. Subsection 000 net in 2013 and 2014, all units of each group, m EUR (pay law of 2014)")
    for name, grp in (("merged", [u for u in st if u["treated"]]), ("unchanged", [u for u in st if not u["treated"]])):
        a13, a14 = (sum(u["raw"][y]["u000"] for u in grp) for y in (2013, 2014))
        inh = sum(u["raw"][2014][COL_INHABITANTS] for u in grp)
        lines.append(f"  {name}: {a13 / 1e6:.1f} to {a14 / 1e6:.1f} ({a14 / a13 - 1:+.0%}), "
                     f"rise {(a14 - a13) / inh:+.1f} EUR per inhabitant of 2014")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_control.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
