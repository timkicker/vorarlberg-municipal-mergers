"""Transfers received by merged Styrian units, checking the KDZ 2026 account.

Writes data/derived/styria_transfers.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_outcomes as so  # noqa: E402
from accounts_columns import COL_INHABITANTS, COL_REVENUE

TARGETS = {
    "grants": ("state grants (940)", ("940",)),
    "LAND": ("grants from the states (946, 947)", ("946", "947")),
    "A94": ("section 94 total (940 to 947)", tuple(str(i) for i in range(940, 948))),
}
RUNS = {
    "after 2016-19": (s.PRE + s.POST, set(s.POST)),
    "early 2016-17": (s.PRE + (2016, 2017), {2016, 2017}),
    "late 2018-19": (s.PRE + (2018, 2019), {2018, 2019}),
}


def income() -> dict:
    g = collections.defaultdict(lambda: {k: 0.0 for k in TARGETS})
    for y in s.YEARS:
        for r in csv.DictReader((s.RAW / f"gemua_at_{y}.csv").open(encoding="utf-8"), delimiter=";"):
            sub_code = r["C-VAUAB-0"].removeprefix("VAUAB-")
            for k, (_n, sub_codes) in TARGETS.items():
                if sub_code in sub_codes:
                    g[(r["C-C41-2"], y)][k] += float(r[COL_REVENUE])
    return g


def main() -> None:
    st, others = so.units()
    gm = income()
    mp, _ = s.mapping()
    pre = collections.defaultdict(list)
    for code, (n, _share) in mp.items():
        pre[n].append(code)
    in_st = {id(u) for u in st}
    for u in st + others:
        for t in s.YEARS:
            codes = (pre[u["id"]] if t in s.PRE else [u["id"]]) if id(u) in in_st else [u["id"]]
            for k in TARGETS:
                u["raw"][t][k] = sum(gm[(c, t)][k] for c in codes)
    allu = st + others
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    pair = {so.STYRIAN_CONTROL: st, "combined control group, year x size tercile": allu}
    rng = np.random.default_rng(s.SEED)
    lines = [f"Transfers to Styrian units (styria_transfers.py), EUR per inhabitant; "
             f"Styria {len(st)} units ({sum(u['treated'] for u in st)} merged), other states {len(others)}", ""]
    for k, (name, _sub_codes) in TARGETS.items():
        lines.append(name)
        for run, (periods, post) in RUNS.items():
            for cname, us in pair.items():
                vals = so.values(us, lambda v, k=k: v[k], False, False)
                r = so.estimate(us, vals, periods, post, cname != so.STYRIAN_CONTROL, rng)
                lines.append(f"  {run}, {cname} (n {r['n']}): {r['b']:+.1f}  95 % [{r['lo']:+.1f}, {r['hi']:+.1f}]")
        lines.append("  summed per inhabitant, year: merged / unchanged")
        for t in s.YEARS:
            row = []
            for tr in (True, False):
                g = [u for u in st if u["treated"] == tr]
                row.append(sum(u["raw"][t][k] for u in g) / sum(u["raw"][t][COL_INHABITANTS] for u in g))
            lines.append(f"    {t}: {row[0]:7.1f} / {row[1]:7.1f}")
        lines.append("")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_transfers.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
