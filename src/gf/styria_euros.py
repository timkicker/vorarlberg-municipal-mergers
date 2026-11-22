"""Measured Styrian saving in core administration in euros, next to the state's 2011 estimate.

Writes data/derived/styria_euros.txt.
"""

import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_clean_controls as cc  # noqa: E402

ESTIMATE = 40.0
HEADINGS = (("cleaned main run", "Main cleaned:"), ("combined control group", "Combined control group"))


def runs() -> list[tuple[str, float, float, float]]:
    """Effect and 95 % bounds of two runs, read from styria_clean_controls.txt."""
    text = (s.OUT / "styria_clean_controls.txt").read_text()
    out = []
    for name, heading in HEADINGS:
        block = text.split(heading)[1]
        m = re.search(r"Effect log ([-+][\d.]+)  95 % \[([-+][\d.]+), ([-+][\d.]+)\]", block)
        out.append((name, *(float(x) for x in m.groups())))
    return out


def main() -> None:
    units, _, m = cc.build()
    found, _ = cc.changed(units, m)
    units = [u for u in units if u["id"] not in found]
    tr = [u for u in units if u["treated"]]
    k = sum(u["y"][t][0] for u in tr for t in s.POST) / len(s.POST) / 1e6
    out = ["Measured Styrian saving in core administration in m euros (styria_euros.py)",
           f"Units {len(units)}, merged {len(tr)}; net core administration costs of the merged units, mean 2016-2019: {k:.1f} m euros a year", "",
           "Run | b | saving m euros a year [from the bounds of the 95 % interval] | share of 40 m"]
    for name, b, lo, hi in runs():
        e = lambda x: k * (math.exp(-x) - 1)  # noqa: E731
        out.append(f"  {name} | {b:+.3f} | {e(b):.1f} [{e(hi):.1f}, {e(lo):.1f}] | {e(b) / ESTIMATE:.0%}")
    text = "\n".join(out)
    print(text)
    (s.OUT / "styria_euros.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
