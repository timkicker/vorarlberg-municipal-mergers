"""Status quo with the population forecast to 2050: size disadvantage and base grant without any merger.

Run from the repository root. Writes data/derived/status_quo_trend.txt.
"""

import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pareto  # noqa: E402
import pop2050  # noqa: E402
import regions  # noqa: E402
import state_grants  # noqa: E402

OUT = pareto.OUT


def main() -> None:
    rows, _, _ = regions.load()
    gkz = [r["gkz"] for r in rows]
    adm = {r["gkz"]: r for r in csv.DictReader((OUT / "administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[g]["population"]) for g in gkz])
    cost = np.array([float(adm[g]["net"]) for g in gkz])
    curve = np.loadtxt(OUT / "cost_curve_net.csv", delimiter=",", skiprows=1)
    lc = lambda p: np.interp(np.log(p), np.log(curve[:, 0]), np.log(curve[:, 1]))  # noqa: E731
    f = pop2050.forecast()
    p26 = np.array([f[(g, 2026)][0] for g in gkz])
    p50 = np.array([f[(g, 2050)][0] for g in gkz])
    per_head = lambda p: cost / pop * np.exp(lc(p) - lc(pop))  # noqa: E731

    lines = ["Status quo with trend to 2050 (status_quo_trend.py)", ""]
    lines.append("1. municipalities below a limit | 2026 | 2050")
    for lim in (1000, 2000, 3000):
        lines.append(f"  below {lim:,} | {np.sum(p26 < lim)} | {np.sum(p50 < lim)}")
    c26 = np.sum(per_head(p26) * p26) * pareto.SCALE_MAIN
    c50 = np.sum(per_head(p50) * p50) * pareto.SCALE_MAIN
    c50_flat = np.sum(per_head(p26) * p50) * pareto.SCALE_MAIN
    lines.append("")
    lines.append("2. net cost of core administration in the status quo, m EUR a year (curve, scaled)")
    lines.append(f"  2026 {c26 / 1e6:.2f}, 2050 along the curve {c50 / 1e6:.2f}, 2050 with cost per inhabitant of 2026 {c50_flat / 1e6:.2f}")
    lines.append(f"  size disadvantage 2050 (difference) {(c50 - c50_flat) / 1e6:+.2f}")
    shrink = p50 < p26
    lines.append(f"  of this from shrinking municipalities ({shrink.sum()}) {np.sum((per_head(p50) - per_head(p26))[shrink] * p50[shrink]) * pareto.SCALE_MAIN / 1e6:+.2f}")
    s26 = sum(state_grants.base_amount(p) for p in p26)
    s50 = sum(state_grants.base_amount(p) for p in p50)
    lines.append("")
    lines.append(f"3. base grant of the state guideline in the status quo: 2026 {s26 / 1e6:.1f}, 2050 {s50 / 1e6:.1f} m EUR")
    lines.append("")
    lines.append("4. saving E 2050 of the threshold rules: see population_2050.txt, section 3")
    text = "\n".join(lines)
    print(text)
    (OUT / "status_quo_trend.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
