"""Styrian backtest, gross core administration without the year 2014.

Units cleaned as in styria_clean_controls.py. Writes data/derived/styria_gross_no2014.txt.
"""

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_clean_controls as cc  # noqa: E402


def main() -> None:
    units, others, m = cc.build()
    found, _ = cc.changed(units, m)
    clean = [u for u in units if u["id"] not in found]
    allc = clean + others
    cuts = np.quantile([u["y"][s.REF][2] for u in allc], [1 / 3, 2 / 3])
    for u in allc:
        u["group"] = int(np.searchsorted(cuts, u["y"][s.REF][2]))
    no14 = tuple(t for t in s.YEARS if t != 2014)
    rng = np.random.default_rng(s.SEED)
    runs = (("1. gross, Styrian control, all years", clean, False, {}),
            ("2. gross, Styrian control, without 2014", clean, False, {"years": no14, "ref": 2013}),
            ("3. gross, combined control group, year x size tercile, without 2014", allc, True, {"years": no14, "ref": 2013}))
    out = ["Backtest Styria gross without 2014 (styria_gross_no14.py), controls cleaned",
           f"Units {len(clean)} (merged {sum(u['treated'] for u in clean)}), other states {len(others)}"]
    for name, us, gfe, kw in runs:
        r = s.boot(us, 1, gfe, rng, **kw)
        out.append(f"\n{name} (n = {len(us)})")
        out.append(f"  Effect log {r['b']:+.4f}  95 % [{r['lo']:+.3f}, {r['hi']:+.3f}]  i.e. {np.expm1(r['b']):+.1%}")
        yrs = [t for t in r["years"] if t != r["ref"]]
        out.append(f"  Event study (reference {r['ref']}): " + "  ".join(f"{t}: {v:+.3f}" for t, v in zip(yrs, r["es"])))
    text = "\n".join(out)
    print(text)
    (s.OUT / "styria_gross_no2014.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
