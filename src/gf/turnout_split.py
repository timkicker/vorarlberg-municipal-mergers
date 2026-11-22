"""Styrian turnout effect split by legal form and by number of predecessors.

Writes data/derived/turnout_split.txt.
"""

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_elections as se  # noqa: E402
import styria_voluntary as sv  # noqa: E402
import turnout as to  # noqa: E402


def fit2(units, a, b, rng):
    years = se.YEARS
    rows = [(i, u, y) for i, u in enumerate(units) for y in years]
    unit = np.array([r[0] for r in rows])
    yr = np.array([r[2] for r in rows])
    post = np.isin(yr, se.POST).astype(float)
    da = np.array([a(r[1]) for r in rows], float)
    db = np.array([b(r[1]) for r in rows], float)
    y = np.array([r[1]["T"][r[2]] for r in rows], float)
    fe = [(yr == t).astype(float) for t in years[1:]]
    X = np.column_stack([da * post, db * post] + fe)
    est = s.twfe(y, X, unit)[:2]
    n, T = len(units), len(years)
    bs = []
    for _ in range(s.N_BOOT):
        pick = rng.integers(0, n, n)
        idx = (pick[:, None] * T + np.arange(T)).ravel()
        bs.append(s.twfe(y[idx], X[idx], np.repeat(np.arange(n), T))[:2])
    bs = np.array(bs)
    ci = lambda v: f"[{np.percentile(v, 2.5):+.2f}, {np.percentile(v, 97.5):+.2f}]"  # noqa: E731
    return (f"{est[0]:+.2f} {ci(bs[:, 0])}", f"{est[1]:+.2f} {ci(bs[:, 1])}",
            f"{est[0] - est[1]:+.2f} {ci(bs[:, 0] - bs[:, 1])}")


def main() -> None:
    units, dropped = to.styria_units()
    nm = sv.names2015()
    statute = {nm[n][0] for n in sv.STATUTE if len(nm.get(n, [])) == 1}
    rng = np.random.default_rng(s.SEED)
    lines = [f"Turnout in Styria by kind of merger (turnout_split.py), valid votes per eligible voter, "
             f"units {len(units)}, dropped {dict(dropped)}", ""]
    splits = [
        ("Legal form", "by statute", lambda u: u["treated"] and u["id"] in statute,
         "voluntary", lambda u: u["treated"] and u["id"] not in statute),
        ("Number of predecessors", "two", lambda u: u["n_pre"] == 2, "three or more", lambda u: u["n_pre"] >= 3),
    ]
    for title, na, fa, nb, fb in splits:
        ca, cb = sum(map(fa, units)), sum(map(fb, units))
        ra, rb, rd = fit2(units, fa, fb, rng)
        lines.append(f"{title}: {na} n {ca}, {nb} n {cb}, unchanged n {sum(not u['treated'] for u in units)}")
        lines.append(f"  {na}: {ra} percentage points")
        lines.append(f"  {nb}: {rb} percentage points")
        lines.append(f"  difference {na} minus {nb}: {rd}")
        lines.append("")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "turnout_split.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
