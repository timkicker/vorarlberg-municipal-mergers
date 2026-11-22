"""Backtest: did the Styrian mergers of 2015 give voters more choice?

The 2005 and 2010 sheets carry municipality codes from before the district
mergers of 2012 and 2013, so they are matched to the 2015 units through the
boundaries of 1 January 2011 instead of 2014. Further measures are the union of
the predecessors' lists and the lists that won seats.
"""

import collections
import csv
import io
import pathlib
import sys
import zipfile

import numpy as np
import shapely

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402

PRE, POST, REF = (2005, 2010), (2015, 2020, 2025), 2010
YEARS = PRE + POST

# Column names and values in the municipal council election files (styria_council_elections_ogd.zip, open data of the state of Styria)
FILE_RESULT = "GRW_{}_endergebnis.csv"  # final result sheet per election year
COL_MUN_NO = "GEMNR"  # municipality code
COL_ELIGIBLE = "WAHLBE_GR"  # eligible voters, followed by the two-digit year
COL_VOTES = "STIMMEN_GR"  # votes per list, followed by the two-digit year
COL_SEATS = "MAND_GR"  # seats per list, followed by the two-digit year
COL_PARTY_VOTES_2005 = "PARTEISUMMEN_GR05"  # votes per list in the 2005 file
COL_PARTY_GROUP_2005 = "PARTEI_ZUORDNUNG"  # party assignment of the state in the 2005 file
COL_PARTY_GROUP_2010 = "PARTEI_ZU"  # party assignment of the state in the 2010 file
COL_LIST = "PARTEI"  # list name
OTHER_LISTS = "SONSTIGE LISTEN"  # party assignment for lists outside the parties


def _read(z: zipfile.ZipFile, year: int) -> tuple[list, list]:
    raw = z.read(FILE_RESULT.format(year))
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    return [c.strip().upper().replace(" ", "") for c in rows[0]], rows[1:]


def _num(v: str) -> int | None:
    v = (v or "").strip().replace(".", "")
    return int(v) if v else None


def _count(rows: list, gi: int, wi: int | None, si: int, voters: dict | None = None) -> dict:
    """gkz -> (eligible voters, lists with votes)."""
    d = {}
    for r in rows:
        if not r or not r[gi].strip() or _num(r[si]) is None:
            continue
        g = r[gi].strip()
        if voters is not None and g not in voters:
            continue
        w = voters[g] if voters is not None else _num(r[wi])
        d[g] = (w, d.get(g, (w, 0))[1] + 1)
    return d


def elections() -> dict:
    """year -> gkz -> (eligible voters, number of lists).

    Source is the open data release of the state of Styria (CC BY 4.0). The 2005
    file has no eligible voters, they come from the 2005 columns of the 2010
    file. Lists for 2005 come from the 2005 file itself, because for Oeblarn the 2010
    file has a different 2005 result, apparently the repeat election. A
    municipality that is missing from the 2010 file (St. Ruprecht-Falkendorf,
    merged before 2010) has no eligible voters for 2005 and is left out, as in
    the 2005 tables of the state.
    """
    out = {}
    with zipfile.ZipFile(s.RAW / "styria_council_elections_ogd.zip") as z:
        for y in (2010, 2015, 2020, 2025):
            h, rows = _read(z, y)
            yy = str(y)[2:]
            out[y] = _count(rows, h.index(COL_MUN_NO), h.index(f"{COL_ELIGIBLE}{yy}"), h.index(f"{COL_VOTES}{yy}"))
        h, rows = _read(z, 2010)
        v05 = {g: w for g, (w, _) in _count(rows, h.index(COL_MUN_NO), h.index(f"{COL_ELIGIBLE}05"), h.index(f"{COL_VOTES}05")).items()}
        h, rows = _read(z, 2005)
        out[2005] = _count(rows, h.index(COL_MUN_NO), None, h.index(COL_PARTY_VOTES_2005), voters=v05)
    return out


UNION_COLS = {2005: (COL_PARTY_VOTES_2005, None, COL_PARTY_GROUP_2005), 2010: (f"{COL_VOTES}10", f"{COL_SEATS}10", COL_PARTY_GROUP_2010)}
SEAT_YEARS = (2010, 2015, 2020, 2025)


def lists_detail(by_name: bool = False) -> dict:
    """year -> gkz -> list of (party key, seats or None) for every list with votes.

    The party key is the party assignment of the state (OEVP, SPOE, ...) so that
    local branches of one party count once. Other lists are keyed by their name.
    With by_name the key is always the list name as it stands in the data.
    """
    out = {}
    with zipfile.ZipFile(s.RAW / "styria_council_elections_ogd.zip") as z:
        for y in YEARS:
            h, rows = _read(z, y)
            yy = str(y)[2:]
            sc, mc, ac = UNION_COLS.get(y, (f"{COL_VOTES}{yy}", f"{COL_SEATS}{yy}", None))
            si, gi, pi = h.index(sc), h.index(COL_MUN_NO), h.index(COL_LIST)
            mi = h.index(mc) if mc else None
            ai = h.index(ac) if ac else None
            d = collections.defaultdict(list)
            for r in rows:
                if not r or not r[gi].strip() or _num(r[si]) is None:
                    continue
                grp = r[ai].strip().upper() if ai is not None else ""
                key = r[pi].strip().upper() if by_name or grp in ("", OTHER_LISTS) else grp
                d[r[gi].strip()].append((key, _num(r[mi]) if mi is not None else None))
            out[y] = d
    return out


PARTIES = ("ÖVP", "SPÖ", "FPÖ", "GRÜNE", "KPÖ", "NEOS")


def party(name: str) -> str | None:
    """One of the six parties for a list name or party assignment, else None."""
    u = name.upper()
    for p in PARTIES:
        if u.startswith(p) or p in u.split():
            return p
    return None


def did(units: list, key: str, years: tuple, post: tuple, ref: int, rng) -> dict:
    rows = [(i, u, y) for i, u in enumerate(units) for y in years]
    unit = np.array([r[0] for r in rows])
    yr = np.array([r[2] for r in rows])
    tr = np.array([r[1]["treated"] for r in rows], float)
    y = np.array([r[1][key][r[2]] for r in rows], float)
    fe = [(yr == t).astype(float) for t in years[1:]]
    Xd = np.column_stack([tr * np.isin(yr, post)] + fe)
    es_years = [t for t in years if t != ref]
    Xe = np.column_stack([tr * (yr == t) for t in es_years] + fe)
    b = s.twfe(y, Xd, unit)[0]
    e = s.twfe(y, Xe, unit)[: len(es_years)]
    n, T = len(units), len(years)
    bs, ebs = [], []
    for _ in range(s.N_BOOT):
        pick = rng.integers(0, n, n)
        idx = (pick[:, None] * T + np.arange(T)).ravel()
        nu = np.repeat(np.arange(n), T)
        bs.append(s.twfe(y[idx], Xd[idx], nu)[0])
        ebs.append(s.twfe(y[idx], Xe[idx], nu)[: len(es_years)])
    ebs = np.array(ebs)
    return {"b": b, "lo": np.percentile(bs, 2.5), "hi": np.percentile(bs, 97.5), "es_years": es_years, "es": e, "es_lo": np.percentile(ebs, 2.5, 0), "es_hi": np.percentile(ebs, 97.5, 0)}


def changed_after_2015() -> set:
    old, new = s.polygons(2015, "6"), s.polygons(2025, "6")
    codes = list(new)
    tree = shapely.STRtree([new[c] for c in codes])
    best = {}
    for g, p in old.items():
        b = max(((codes[i], p.intersection(new[codes[i]]).area / p.area) for i in tree.query(p)), key=lambda x: x[1])
        best[g] = b
    hosts = collections.Counter(c for c, _ in best.values())
    return {g for g, (c, share) in best.items() if share < s.SPLIT_SHARE or hosts[c] > 1}


EARLY = {"61102", "61103", "61117"}  # merged on 1 January 2013


def mapping_2011() -> dict:
    """2011 code -> 2015 unit with the largest overlap."""
    old, new = s.polygons(2011, "6"), s.polygons(2015, "6")
    codes = list(new)
    tree = shapely.STRtree([new[c] for c in codes])
    return {g: max(((codes[i], p.intersection(new[codes[i]]).area) for i in tree.query(p)), key=lambda x: x[1])[0] for g, p in old.items()}


def main() -> None:
    el = elections()
    mp = mapping_2011()
    pre = collections.defaultdict(list)
    for g, n in mp.items():
        pre[n].append(g)
    changed = changed_after_2015()
    lines = [f"Units with a change of area after 2015 (dropped): {sorted(changed)}"]
    for y in PRE:
        un = sorted(g for g in el[y] if g not in mp)
        lines.append(f"{y}: municipalities without assignment via 2011: {un}, eligible voters {sum(el[y][g][0] for g in un):,}")
    units, dropped = [], collections.Counter()
    for n, gs in sorted(pre.items()):
        if n == s.GRAZ:
            continue
        if n in changed:
            dropped["changed after 2015"] += 1
            continue
        if set(gs) & EARLY:
            dropped["merger 2013"] += 1
            continue
        v = {}
        for y in YEARS:
            if y in PRE:
                parts = [el[y][g] for g in gs if g in el[y]]
            else:
                parts = [el[y][n]] if n in el[y] else []
            if not parts:
                break
            w = sum(p[0] for p in parts)
            v[y] = (sum(p[0] * (p[1] > 1) for p in parts) / w, sum(p[0] * p[1] for p in parts) / w)
        if len(v) < len(YEARS):
            dropped["election missing"] += 1
            continue
        units.append({"id": n, "treated": len(gs) >= 2, "v": v})
    lines.append(f"Units {len(units)}, merged {sum(u['treated'] for u in units)}, unchanged {sum(not u['treated'] for u in units)}, dropped {dict(dropped)}")

    rng = np.random.default_rng(s.SEED)
    for u in units:
        u["A"] = {y: u["v"][y][0] for y in YEARS}
        u["L"] = {y: u["v"][y][1] for y in YEARS}
    for k, name in (("A", "A, share with more than one list"), ("L", "L, lists on the ballot")):
        r = did(units, k, YEARS, POST, REF, rng)
        lines.append(f"\n{name}")
        for grp, sel in (("merged", True), ("unchanged", False)):
            lines.append(f"  Mean {grp}: " + "  ".join(f"{t}: {np.mean([u[k][t] for u in units if u['treated'] == sel]):.3f}" for t in YEARS))
        lines.append(f"  Effect {r['b']:+.3f}  95 % [{r['lo']:+.3f}, {r['hi']:+.3f}]")
        lines.append("  Event study (reference 2010): " + "  ".join(f"{t}: {v:+.3f} [{lo:+.3f}, {hi:+.3f}]" for t, v, lo, hi in zip(r["es_years"], r["es"], r["es_lo"], r["es_hi"])))

    # union of the predecessors' lists and lists with seats
    det = lists_detail()
    ext = []
    for u in units:
        gs = pre[u["id"]]
        u["U"], u["M"], u["MU"] = {}, {}, {}
        for y in YEARS:
            if y in PRE:
                parts = [(el[y][g][0], det[y][g]) for g in gs if g in el[y] and g in det[y]]
                w = sum(p[0] for p in parts)
                u["U"][y] = len({key for _, ls in parts for key, _ in ls})
                if y in SEAT_YEARS:
                    u["M"][y] = sum(p[0] * sum(1 for _, m in p[1] if m) for p in parts) / w
                    u["MU"][y] = len({key for _, ls in parts for key, m in ls if m})
            else:
                ls = det[y].get(u["id"], [])
                u["U"][y] = len(ls)
                u["M"][y] = u["MU"][y] = sum(1 for _, m in ls if m)
        ext.append(u)
    lines.append("\nBefore as union of the predecessors' lists, parties counted once by the state's assignment")
    for k, name, years, post in (
        ("U", "U, lists on a joint ballot of the predecessors", YEARS, POST),
        ("M", "M, lists with a seat, weighted mean of the predecessors", SEAT_YEARS, POST),
        ("MU", "MU, lists with a seat, union of the predecessors", SEAT_YEARS, POST),
    ):
        r = did(ext, k, years, post, REF, rng)
        lines.append(f"\n{name}")
        for grp, sel in (("merged", True), ("unchanged", False)):
            lines.append(f"  Mean {grp}: " + "  ".join(f"{t}: {np.mean([u[k][t] for u in ext if u['treated'] == sel]):.3f}" for t in years))
        lines.append(f"  Effect {r['b']:+.3f}  95 % [{r['lo']:+.3f}, {r['hi']:+.3f}]")
        lines.append("  Event study (reference 2010): " + "  ".join(f"{t}: {v:+.3f} [{lo:+.3f}, {hi:+.3f}]" for t, v, lo, hi in zip(r["es_years"], r["es"], r["es_lo"], r["es_hi"])))
    # U by list name and lists of parties new to a unit
    det_n = lists_detail(by_name=True)
    for u in ext:
        gs = pre[u["id"]]
        u["UN"] = {}
        for y in YEARS:
            if y in PRE:
                u["UN"][y] = len({key for g in gs if g in el[y] and g in det_n[y] for key, _ in det_n[y][g]})
            else:
                u["UN"][y] = len(det_n[y].get(u["id"], []))
    r = did(ext, "UN", YEARS, POST, REF, rng)
    lines.append("\nUN, as U but every list name counted separately")
    for grp, sel in (("merged", True), ("unchanged", False)):
        lines.append(f"  Mean {grp}: " + "  ".join(f"{t}: {np.mean([u['UN'][t] for u in ext if u['treated'] == sel]):.3f}" for t in YEARS))
    lines.append(f"  Effect {r['b']:+.3f}  95 % [{r['lo']:+.3f}, {r['hi']:+.3f}]")

    lines.append("\nLists of a party that stood in no predecessor municipality of the unit in 2010")
    for grp, sel in (("merged", True), ("unchanged", False)):
        grp_units = [u for u in ext if u["treated"] == sel]
        for y in POST:
            cnt, with_new, by = 0, 0, collections.Counter()
            for u in grp_units:
                before = {party(k) for g in pre[u["id"]] for k, _ in det[2010].get(g, [])} - {None}
                new = [party(k) for k, _ in det[y].get(u["id"], []) if party(k) and party(k) not in before]
                cnt += len(new)
                with_new += bool(new)
                by.update(new)
            lines.append(f"  {grp} {y}: {cnt} new lists in {with_new} of {len(grp_units)} units ({with_new / len(grp_units):.0%}), {dict(by.most_common())}")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_elections.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
