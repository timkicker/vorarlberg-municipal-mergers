"""Vorarlberg cross-section of elected bodies against the Styrian backtest.

Writes data/derived/organs_styria.txt.
"""

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import elected_bodies as eb  # noqa: E402
import styria as s  # noqa: E402
import styria_clean_controls as cc  # noqa: E402
import styria_control as sc  # noqa: E402

MEASURED = -sc.effects_000()[0]


def main() -> None:
    o = eb.organs()
    pop = ba.fag_pop(2024)
    g = [k for k in o if k in pop]
    e = np.array([pop[k] for k in g], float)
    y = np.array([o[k] for k in g], float)
    (a, b), *_ = np.linalg.lstsq(np.column_stack([np.ones_like(e), e]), y, rcond=None)
    ok = y > 0
    (c, ex), *_ = np.linalg.lstsq(np.column_stack([np.ones(ok.sum()), np.log(e[ok])]), np.log(y[ok]), rcond=None)
    lin = lambda n: a + b * n  # noqa: E731
    lgl = lambda n: float(np.exp(c + ex * np.log(n)))  # noqa: E731
    units, _, _ = cc.build()
    tr = [u for u in units if u["treated"]]
    inh = sum(p for u in tr for _, p in u["pred"])
    sv = {"linear": 0.0, "log-log": 0.0}
    for u in tr:
        ps = [p for _, p in u["pred"]]
        for name, f in (("linear", lin), ("log-log", lgl)):
            sv[name] += sum(f(p) for p in ps) - f(sum(ps))
    out = ["Cross-section of the elected bodies (Vorarlberg 2024) against the Styrian backtest (organs_styria_check.py)",
           f"Fits as elected_bodies.py: linear a = {a:,.0f} euros, b = {b:.2f} euros per inhabitant; log-log e = {ex:.3f} (n {ok.sum()})",
           f"Merged Styrian units {len(tr)}, predecessors {sum(len(u['pred']) for u in tr)}, population {s.REF} {inh:,.0f}", "",
           "Form | predicted saving m euros | per inhabitant"]
    for name, v in sv.items():
        out.append(f"  {name} | {v / 1e6:.2f} | {v / inh:.1f}")
    out.append(f"  measured (styria_control.txt, Styrian control) | | {-MEASURED:.1f}")
    lo, hi = sorted(v / inh for v in sv.values())
    m = -MEASURED
    verdict = "between the predictions" if lo <= m <= hi else ("far outside" if m < lo * 2 / 3 or m > hi else "outside but not far")
    out.append(f"Reading: {verdict}")
    text = "\n".join(out)
    print(text)
    (s.OUT / "organs_styria.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
