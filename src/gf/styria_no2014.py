"""Ordinary spending, revenue and elected bodies without 2014 and against the other states alone.

Writes data/derived/styria_no2014.txt.
"""

import collections
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_clean_controls as c  # noqa: E402
import styria_control as sc  # noqa: E402
import styria_outcomes as so  # noqa: E402
from accounts_columns import COL_INHABITANTS, COL_ORDINARY_REVENUE, COL_ORDINARY_SPENDING


def setup() -> tuple[list, list]:
    """The units of styria_control.main, with the split of core administration added."""
    st, others = so.units()
    mp, _ = s.mapping()
    pre = collections.defaultdict(list)
    for code, (n, _share) in mp.items():
        pre[n].append(code)
    m = sc.split_money()
    for u in st:
        for t in s.YEARS:
            codes = pre[u["id"]] if t in s.PRE else [u["id"]]
            for k in ("without000", "u000"):
                u["raw"][t][k] = sum(m[(cc, t)][k] for cc in codes)
    for u in others:
        for t in s.YEARS:
            u["raw"][t] = dict(u["raw"][t], **m[(u["id"], t)])
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in st + others], [1 / 3, 2 / 3])
    for u in st + others:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    return st, others


def main() -> None:
    st, others = setup()
    units, _, m = c.build()
    found, _ = c.changed(units, m)
    clean = [u for u in st if u["id"] not in found]
    merged = [u for u in st if u["treated"]]
    no14 = tuple(t for t in s.YEARS if t != 2014)
    controls = [("Styrian control", st, False), ("combined control group, year x size tercile", st + others, True),
                ("other states alone, year x size tercile", merged + others, True)]
    targets = [("ordinary spending per inhabitant, log", lambda v: v[COL_ORDINARY_SPENDING], True),
               ("ordinary revenue per inhabitant, log", lambda v: v[COL_ORDINARY_REVENUE], True),
               ("subsection 000 net per inhabitant, EUR", lambda v: v["u000"], False)]
    rng = np.random.default_rng(s.SEED)
    lines = ["Without 2014 and against the other states alone (styria_no2014.py)",
             f"Styria {len(st)} units ({len(merged)} merged), other states {len(others)}, cleaned {len(clean)}", ""]
    for label, fn, log in targets:
        lines.append(label)
        for name, us, gfe in controls:
            for tag, per in (("with 2014", s.YEARS), ("without 2014", no14)):
                r = so.estimate(us, so.values(us, fn, log, False), per, set(s.POST), gfe, rng)
                lines.append(f"  {name}, {tag}: {sc.fmt(r, log)}")
        lines.append("")
    lines.append("ordinary spending, cleaned panel, Styrian control")
    for tag, per in (("with 2014", s.YEARS), ("without 2014", no14)):
        r = so.estimate(clean, so.values(clean, lambda v: v[COL_ORDINARY_SPENDING], True, False), per, set(s.POST), False, rng)
        lines.append(f"  {tag}: {sc.fmt(r, True)}")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_no2014.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
