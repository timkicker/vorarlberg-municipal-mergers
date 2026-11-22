"""Transition costs net of extraordinary revenue: the event study of styria_transition.py
for extraordinary revenue and the extraordinary balance.

Writes data/derived/styria_transition_net.txt.
"""

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_outcomes as so  # noqa: E402
import styria_transition as tr  # noqa: E402  (sets s.YEARS to 2010-2019)
from accounts_columns import COL_EXTRAORDINARY_REVENUE, COL_EXTRAORDINARY_SPENDING, COL_INHABITANTS

so.FIELDS = so.FIELDS + (COL_EXTRAORDINARY_REVENUE,)


def main() -> None:
    st, others = so.units()
    allu = st + others
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    outcomes = (("extraordinary spending per inhabitant, EUR (as styria_transition)", lambda v: v[COL_EXTRAORDINARY_SPENDING]),
                ("extraordinary revenue per inhabitant, EUR", lambda v: v[COL_EXTRAORDINARY_REVENUE]),
                ("extraordinary balance spending minus revenue per inhabitant, EUR", lambda v: v[COL_EXTRAORDINARY_SPENDING] - v[COL_EXTRAORDINARY_REVENUE]))
    rng = np.random.default_rng(s.SEED)
    lines = [f"Event study Styria 2010-2019, extraordinary budget net, reference year {tr.BASE} (styria_transition_net.py)",
             f"Styria {len(st)} units ({sum(u['treated'] for u in st)} merged), other states {len(others)}"]
    for name, fn in outcomes:
        lines.append(f"\n{name}")
        for label, us, gfe in (("Styrian control", st, False), ("combined control group, year x size tercile", allu, True)):
            n, rows = tr.event(us, fn, False, gfe, rng)
            lines.append(f"  {label} (n {n})")
            for t, b, lo, hi in rows:
                lines.append(f"    {t}: {b:+.1f}  95 % [{lo:+.1f}, {hi:+.1f}]")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_transition_net.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
