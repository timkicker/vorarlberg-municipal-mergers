"""Turnout by municipal size in Vorarlberg and after the Styrian mergers.

Writes data/derived/turnout.txt.
"""

import collections
import json
import pathlib
import sys
import zipfile

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import elections as el  # noqa: E402
import styria as s  # noqa: E402
import styria_elections as se  # noqa: E402

# Keys of gv_YYYY.json (municipal election results from the election website of the state of Vorarlberg)
KEY_RESULTS = "ergebnisse"  # list of municipalities
KEY_COUNCIL_ELECTION = "gemeinderatswahl"  # council election block
KEY_MAYOR_ELECTION = "buergermeisterwahl"  # mayoral election block
KEY_ELIGIBLE = "wahlberechtigte"  # eligible voters
KEY_CAST = "abgegebeneStimmen"  # votes cast
KEY_INVALID = "ungueltigeStimmen"  # invalid votes
KEY_MODE = "wahlart"  # election mode
COL_VALID = "GUEL_GR"  # valid votes in styria_council_elections_ogd.zip, followed by the two-digit year


def vorarlberg(year: int, rng) -> list[str]:
    d = json.loads((el.RAW / f"gv_{year}.json").read_text(encoding="utf-8-sig"))[KEY_RESULTS]
    w = np.array([e[KEY_COUNCIL_ELECTION][KEY_ELIGIBLE] for e in d], float)
    a = np.array([e[KEY_COUNCIL_ELECTION][KEY_CAST] for e in d], float)
    t = 100 * a / w
    out = [f"\nVorarlberg {year}: {len(d)} municipalities, turnout overall {100 * a.sum() / w.sum():.1f} %"]
    for lo, hi in zip(el.CLASSES[:-1], el.CLASSES[1:]):
        m = (w >= lo) & (w < hi)
        out.append(f"  eligible voters {lo:,.0f} to {hi:,.0f}: n {m.sum()}, turnout {100 * a[m].sum() / w[m].sum():.1f} %")
    x = np.log(w)
    slope = np.polyfit(x, t, 1)[0]
    bs = []
    for _ in range(el.N_BOOT):
        i = rng.integers(0, len(x), len(x))
        bs.append(np.polyfit(x[i], t[i], 1)[0])
    out.append(f"  slope per log unit of eligible voters: {slope:+.2f} percentage points  95 % [{np.percentile(bs, 2.5):+.2f}, {np.percentile(bs, 97.5):+.2f}]"
               f"  (ten times more eligible voters: {slope * np.log(10):+.1f})")
    inv = collections.defaultdict(lambda: [0, 0])
    for e in d:
        b = e.get(KEY_MAYOR_ELECTION) or {}
        if b.get(KEY_CAST):
            inv[b[KEY_MODE]][0] += b[KEY_INVALID]
            inv[b[KEY_MODE]][1] += b[KEY_CAST]
    for k, (u, n) in sorted(inv.items()):
        out.append(f"  mayoral election {k}: invalid {100 * u / n:.1f} % of votes cast")
    return out


def styria_valid() -> dict:
    """year -> gkz -> (eligible, valid votes)."""
    out = collections.defaultdict(dict)
    with zipfile.ZipFile(s.RAW / "styria_council_elections_ogd.zip") as z:
        for y in (2010, 2015, 2020, 2025):
            h, rows = se._read(z, y)
            yy = str(y)[2:]
            cols = [(y, h.index(f"{se.COL_ELIGIBLE}{yy}"), h.index(f"{COL_VALID}{yy}"))]
            if y == 2010:
                cols.append((2005, h.index(f"{se.COL_ELIGIBLE}05"), h.index(f"{COL_VALID}05")))
            gi = h.index(se.COL_MUN_NO)
            for r in rows:
                if not r or not r[gi].strip():
                    continue
                for yr, wi, vi in cols:
                    w, v = se._num(r[wi]), se._num(r[vi])
                    if w and v is not None:
                        out[yr].setdefault(r[gi].strip(), (w, v))
    return out


def styria_units() -> tuple[list, collections.Counter]:
    """Styrian units with valid turnout per election, same selection as styria_elections."""
    ev = styria_valid()
    mp = se.mapping_2011()
    pre = collections.defaultdict(list)
    for g, n in mp.items():
        pre[n].append(g)
    changed = se.changed_after_2015()
    units, dropped = [], collections.Counter()
    for n, gs in sorted(pre.items()):
        if n == s.GRAZ or n in changed or set(gs) & se.EARLY:
            dropped["dropped as in styria_elections"] += 1
            continue
        v = {}
        for y in se.YEARS:
            parts = [ev[y][g] for g in gs if g in ev[y]] if y in se.PRE else ([ev[y][n]] if n in ev[y] else [])
            if not parts:
                break
            v[y] = 100 * sum(p[1] for p in parts) / sum(p[0] for p in parts)
        if len(v) < len(se.YEARS):
            dropped["election missing"] += 1
            continue
        units.append({"id": n, "treated": len(gs) >= 2, "n_pre": len(gs), "T": v})
    return units, dropped


def styria(rng) -> list[str]:
    units, dropped = styria_units()
    r = se.did(units, "T", se.YEARS, se.POST, se.REF, rng)
    out = [f"\nStyria, valid turnout in per cent: units {len(units)}, merged {sum(u['treated'] for u in units)}, dropped {dict(dropped)}"]
    for grp, sel in (("merged", True), ("unchanged", False)):
        out.append(f"  mean {grp}: " + "  ".join(f"{t}: {np.mean([u['T'][t] for u in units if u['treated'] == sel]):.1f}" for t in se.YEARS))
    out.append(f"  effect {r['b']:+.2f} percentage points  95 % [{r['lo']:+.2f}, {r['hi']:+.2f}]")
    out.append("  event study (reference 2010): " + "  ".join(f"{t}: {v:+.2f} [{lo:+.2f}, {hi:+.2f}]" for t, v, lo, hi in zip(r["es_years"], r["es"], r["es_lo"], r["es_hi"])))
    return out


def main() -> None:
    rng = np.random.default_rng(el.SEED)
    lines = ["Turnout (turnout.py)"]
    for y in (2025, 2020):
        lines += vorarlberg(y, rng)
    lines += styria(rng)
    text = "\n".join(lines)
    print(text)
    (s.OUT / "turnout.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
