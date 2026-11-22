"""Backtest Styria without control units whose area changed.

Builds the units exactly as styria.main does.
Writes data/derived/styria_clean_controls.txt.
"""

import collections
import pathlib
import sys

import numpy as np
import shapely

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402

GAIN = 0.01


def build():
    """The panel units and the other-states controls of styria.main, unchanged."""
    mp, _ = s.mapping()
    m, pop = s.money()
    pre = collections.defaultdict(list)
    for g, (n, share) in mp.items():
        pre[n].append((g, share))
    split = {n for n, gs in pre.items() if any(sh < s.SPLIT_SHARE for _, sh in gs)}
    early = {n for n, gs in pre.items() if any((g, 2012) not in m for g, _ in gs)}
    units = []
    for n, gs in sorted(pre.items()):
        if n == s.GRAZ or n in early:
            continue
        ys, ok = {}, True
        for t in s.YEARS:
            codes = [g for g, _ in gs] if t in s.PRE else [n]
            if not all((c, t) in m and (c, t) in pop for c in codes):
                ok = False
                break
            ys[t] = (sum(m[(c, t)][0] for c in codes), sum(m[(c, t)][1] for c in codes), sum(pop[(c, t)] for c in codes))
        if not ok or any(v[0] <= 0 for v in ys.values()):
            continue
        units.append({"id": n, "treated": len(gs) >= 2, "split": n in split, "pred": [(g, pop[(g, s.REF)]) for g, _ in gs], "y": ys})
    codes_by_year = {t: {k for (k, yy) in m if yy == t} for t in s.YEARS}
    others = []
    for g in sorted(set.intersection(*codes_by_year.values())):
        if g[0] in "69" or not all((g, t) in pop for t in s.YEARS) or pop[(g, s.REF)] >= 10000:
            continue
        ys = {t: (m[(g, t)][0], m[(g, t)][1], pop[(g, t)]) for t in s.YEARS}
        if all(v[0] > 0 for v in ys.values()):
            others.append({"id": g, "treated": False, "split": False, "pred": [], "y": ys})
    return units, others, m


def changed(units: list, m: dict) -> tuple[dict, list]:
    p11, p14, p15 = s.polygons(2011, "6"), s.polygons(2014, "6"), s.polygons(2015, "6")
    codes14 = list(p14)
    tree14 = shapely.STRtree([p14[c] for c in codes14])
    gone = [c for c in p11 if c not in p14]
    found = {}
    for u in units:
        if u["treated"]:
            continue
        n = u["id"]
        own = u["pred"][0][0]  # the single 2014 predecessor, whose code may differ from n
        notes = []
        a = p15[n]
        other = sum(a.intersection(p14[codes14[i]]).area for i in tree14.query(a) if codes14[i] != own)
        if other / a.area > GAIN:
            src = sorted(codes14[i] for i in tree14.query(a) if codes14[i] != own and a.intersection(p14[codes14[i]]).area / a.area > 0.001)
            notes.append(f"2015 gain {other / a.area:.1%} from {src}")
        b = p14[own]
        inside = [g for g in gone if p11[g].intersection(b).area / p11[g].area > 0.5]
        before = sum(p11[g].area for g in inside) + (p11[own].area if own in p11 else 0.0)
        if len(inside) + (own in p11) > 1:
            notes.append(f"2011-2014 merged: {sorted(inside + ([own] if own in p11 else []))}")
        elif before and abs(b.area / before - 1) > GAIN:
            notes.append(f"area 2011 to 2014 {b.area / before - 1:+.1%}")
        renamed = [g for g in inside if own not in p11]
        if renamed:
            u["renamed"] = renamed[0]
        if notes:
            found[n] = notes
    c10 = {k for (k, y) in m if y == 2010 and k.startswith("6")}
    c11 = {k for (k, y) in m if y == 2011 and k.startswith("6")}
    return found, sorted(c10 - c11)


def main() -> None:
    units, others, m = build()
    found, lost10 = changed(units, m)
    known = ("61055", "62265", "62274", "62205")
    out = ["Backtest Styria without controls whose area changed (styria_clean_controls.py)",
           f"Units in panel {len(units)}, treated {sum(u['treated'] for u in units)}, control {sum(not u['treated'] for u in units)}; other states {len(others)}",
           f"Controls with a change of area: {len(found)}"]
    out += [f"  {k}: {'; '.join(v)}" for k, v in sorted(found.items())]
    out.append("Known controls with a change of area: " + ", ".join(f"{k} {'found' if k in found else 'not found'}" for k in known))
    out.append(f"Controls whose code was only renumbered 2011 to 2014: {sum('renamed' in u for u in units)}")
    out.append(f"Styrian codes with budget data in 2010 but not in 2011: {lost10}")
    clean = [u for u in units if u["id"] not in found]
    allu, allc = units + others, clean + others
    for us in (allu, allc):
        cuts = np.quantile([u["y"][s.REF][2] for u in us], [1 / 3, 2 / 3])
        for u in us:
            u["group"] = int(np.searchsorted(cuts, u["y"][s.REF][2]))
    rng = np.random.default_rng(s.SEED)
    runs = (("Main: net, Styrian control (as styria.py)", units, False),
            ("Main cleaned: without changed controls", clean, False),
            ("Combined control group, year x size tercile (as styria.py)", allu, True),
            ("same cleaned", allc, True))
    for name, us, gfe in runs:
        r = s.boot(us, 0, gfe, rng)
        out.append(f"\n{name} (n = {len(us)}, Styrian controls {sum(not u['treated'] and u['id'].startswith('6') for u in us)})")
        out.append(f"  Effect log {r['b']:+.4f}  95 % [{r['lo']:+.3f}, {r['hi']:+.3f}]  i.e. {np.expm1(r['b']):+.1%}")
    text = "\n".join(out)
    print(text)
    (s.OUT / "styria_clean_controls.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
