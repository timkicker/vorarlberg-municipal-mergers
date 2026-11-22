"""Styrian backtest without sub-section 029 (office buildings), next to the Danish measure.

Units cleaned as in styria_clean_controls.py.
Writes data/derived/styria_no_buildings.txt.
"""

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_clean_controls as cc  # noqa: E402


def clean_units() -> tuple[list, dict]:
    units, _, m = cc.build()
    found, _ = cc.changed(units, m)
    return [u for u in units if u["id"] not in found], m


def gross(units: list, years: tuple) -> float:
    return sum(u["y"][t][1] for u in units if u["treated"] for t in years if t in u["y"])


def main() -> None:
    full, _ = clean_units()
    core = s.CORE
    s.CORE = core - {"029"}
    try:
        units, _ = clean_units()
    finally:
        s.CORE = core
    pre, post = tuple(s.PRE), tuple(s.POST)
    ids = {u["id"] for u in units} & {u["id"] for u in full}
    both_full = [u for u in full if u["id"] in ids]
    both_no = [u for u in units if u["id"] in ids]
    out = ["Backtest Styria without subsection 029 office buildings (styria_no_buildings.py), controls cleaned",
           f"Units with 029: {len(full)}, without 029: {len(units)} (merged {sum(u['treated'] for u in units)}), in both: {len(ids)}",
           "Share of 029 in gross spending of core administration, merged units (descriptive only):"]
    for name, yrs in (("before 2010-2014", pre), ("of which 2014", (2014,)), ("after 2016-2019", post)):
        g_full, g_no = gross(both_full, yrs), gross(both_no, yrs)
        out.append(f"  {name}: {1 - g_no / g_full:.1%}")
    no14 = tuple(t for t in s.YEARS if t != 2014)
    rng = np.random.default_rng(s.SEED)
    runs = (("1. net without 029, Styrian control, reference 2014", units, {}),
            ("2. net without 029, Styrian control, without 2014, reference 2013", units, {"years": no14, "ref": 2013}))
    for name, us, kw in runs:
        r = s.boot(us, 0, False, rng, **kw)
        out.append(f"\n{name} (n = {len(us)})")
        out.append(f"  Effect log {r['b']:+.4f}  95 % [{r['lo']:+.3f}, {r['hi']:+.3f}]  i.e. {np.expm1(r['b']):+.1%}")
        yrs = [t for t in r["years"] if t != r["ref"]]
        out.append(f"  Event study (reference {r['ref']}): " + "  ".join(f"{t}: {v:+.3f}" for t, v in zip(yrs, r["es"])))
    text = "\n".join(out)
    print(text)
    (s.OUT / "styria_no_buildings.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
