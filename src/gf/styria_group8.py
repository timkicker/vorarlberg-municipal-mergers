"""Budget group 8 of the Styrian mergers by section.

Writes data/derived/styria_group8.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_groups as sg  # noqa: E402
import styria_outcomes as so  # noqa: E402
from accounts_columns import COL_INHABITANTS, COL_REVENUE, COL_SPENDING

PARTS = [str(i) for i in range(80, 90) if i != 85] + ["850", "851", "852", "85 rest"]


def part(sub_code: str) -> str | None:
    if sub_code[0] != "8":
        return None
    if sub_code[:2] == "85":
        return sub_code[:3] if sub_code[:3] in ("850", "851", "852") else "85 rest"
    return sub_code[:2]


def money8() -> dict:
    g = collections.defaultdict(lambda: {k: [0.0, 0.0] for k in PARTS})
    for y in s.YEARS:
        for r in csv.DictReader((s.RAW / f"gemua_at_{y}.csv").open(encoding="utf-8"), delimiter=";"):
            p = part(r["C-VAUAB-0"].removeprefix("VAUAB-"))
            if p:
                cell = g[(r["C-C41-2"], y)][p]
                cell[0] += float(r[COL_SPENDING])
                cell[1] += float(r[COL_REVENUE])
    return g


def main() -> None:
    st, others = so.units()
    gm = money8()
    mp, _ = s.mapping()
    pre = collections.defaultdict(list)
    for code, (n, _share) in mp.items():
        pre[n].append(code)
    in_st = {id(u) for u in st}
    for u in st + others:
        for t in s.YEARS:
            codes = (pre[u["id"]] if t in s.PRE else [u["id"]]) if id(u) in in_st else [u["id"]]
            for k in PARTS:
                u["raw"][t]["A" + k] = sum(gm[(c, t)][k][0] for c in codes)
                u["raw"][t]["E" + k] = sum(gm[(c, t)][k][1] for c in codes)
    allu = st + others
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    pair = {so.STYRIAN_CONTROL: st, "combined control group, year x size tercile": allu}
    rng = np.random.default_rng(s.SEED)
    lines = ["Group 8 by section, Styria (styria_group8.py), EUR per inhabitant", ""]
    for k in PARTS:
        lvl = np.mean([u["raw"][t]["E" + k] / u["raw"][t][COL_INHABITANTS] for u in st for t in so.BEFORE])
        lines.append(f"Section {k} (revenue 2010-13 on average {lvl:,.1f} EUR per inhabitant)")
        lines += sg.run(pair, lambda v, k=k: v["A" + k], False, rng, "  spending")
        lines += sg.run(pair, lambda v, k=k: v["E" + k], False, rng, "  revenue")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_group8.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
