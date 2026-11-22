"""Styrian mergers split by legal form: by statute (StGsrG) or by council decision.

Writes data/derived/styria_voluntary.txt.
"""

import collections
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_outcomes as so  # noqa: E402
import styria_transfers as stt  # noqa: E402
from accounts_columns import COL_INHABITANTS, COL_ORDINARY_SPENDING

# New units named in StGsrG (LGBl. Nr. 31/2014) §§ 3 and 4 and recipients under § 5,
# read from the consolidated RIS text (LST40016424 to LST40016426).
STATUTE = [
    "Aflenz", "Bad Mitterndorf", "Bad Waltersdorf", "Dechantskirchen", "Deutschlandsberg", "Eggersdorf bei Graz",
    "Eibiswald", "Fehring", "Fernitz-Mellach", "Fürstenfeld", "Gnas", "Gratwein-Straßengel", "Großlobming",
    "Hirschegg-Pack", "Ilz", "Ilztal", "Kapfenberg", "Kindberg", "Kirchbach in der Steiermark", "Kirchberg an der Raab",
    "Köflach", "Landl", "Leibnitz", "Liezen", "Loipersdorf bei Fürstenfeld", "Mürzzuschlag", "Neudau",
    "Neumarkt in der Steiermark", "Paldau", "Passail", "Pischelsdorf am Kulm", "Pöllau", "Pölstal", "Raaba-Grambach",
    "Rohrbach an der Lafnitz", "Rottenmann", "Sankt Barbara im Mürztal", "Sankt Georgen an der Stiefing",
    "Sankt Marein bei Graz", "Sankt Margarethen bei Knittelfeld", "Sankt Martin im Sulmtal",
    "Sankt Peter am Ottersbach", "Sankt Ruprecht an der Raab", "Schladming", "Schwanberg", "Spielberg",
    "Stadl-Predlitz", "Stainz", "Straß-Spielfeld", "Sölk", "Teufenbach-Katsch", "Thörl", "Tragöß-Sankt Katharein",
    "Unterpremstätten-Zettling", "Waldbach-Mönichwald", "Weiz", "Wies", "Wildon",
]


def names2015() -> dict:
    d = json.load((s.RAW / "boundaries_statat_at_2015.geojson").open(encoding="utf-8"))
    out = collections.defaultdict(list)
    for f in d["features"]:
        p = f["properties"]
        if p["g_id"].startswith("6"):
            out[p["g_name"]].append(p["g_id"])
    return out


def fit(us, vals, periods, post, group_fe, rng):
    keep = [(u, v) for u, v in zip(us, vals) if v is not None]
    rows = [(i, u, v, t) for i, (u, v) in enumerate(keep) for t in periods]
    unit = np.array([r[0] for r in rows])
    per = np.array([periods.index(r[3]) for r in rows])
    isp = np.array([r[3] in post for r in rows], float)
    leg = np.array([r[1].get("form") == "statute" for r in rows], float)
    vol = np.array([r[1].get("form") == "voluntary" for r in rows], float)
    y = np.array([r[2][r[3]] for r in rows])
    if group_fe:
        grp = np.array([r[1]["group"] for r in rows])
        fe = [((grp == g) & (per == p)).astype(float) for g in sorted(set(grp)) for p in range(1, len(periods))]
    else:
        fe = [(per == p).astype(float) for p in range(1, len(periods))]
    X = np.column_stack([leg * isp, vol * isp] + fe)
    b = s.twfe(y, X, unit)[:2]
    n, T = len(keep), len(periods)
    bs = []
    for _ in range(s.N_BOOT):
        pick = rng.integers(0, n, n)
        idx = (pick[:, None] * T + np.arange(T)).ravel()
        bs.append(s.twfe(y[idx], X[idx], np.repeat(np.arange(n), T))[:2])
    bs = np.array(bs)
    ci = lambda a: (np.percentile(a, 2.5), np.percentile(a, 97.5))  # noqa: E731
    return {"n": n, "leg": (b[0], *ci(bs[:, 0])), "vol": (b[1], *ci(bs[:, 1])),
            "diff": (b[0] - b[1], *ci(bs[:, 0] - bs[:, 1]))}


def main() -> None:
    st, others = so.units()
    m, _pop = s.money()
    for u in others:
        for t in s.YEARS:
            u["raw"][t] = dict(u["raw"][t], net=m[(u["id"], t)][0])
    gm = stt.income()
    mp, _ = s.mapping()
    pre = collections.defaultdict(list)
    for code, (n, _share) in mp.items():
        pre[n].append(code)
    in_st = {id(u) for u in st}
    for u in st + others:
        for t in s.YEARS:
            codes = (pre[u["id"]] if t in s.PRE else [u["id"]]) if id(u) in in_st else [u["id"]]
            u["raw"][t]["A94"] = sum(gm[(c, t)]["A94"] for c in codes)
    nm = names2015()
    statute_ids, missing = set(), []
    for name in STATUTE:
        ids = nm.get(name, [])
        if len(ids) == 1:
            statute_ids.add(ids[0])
        else:
            missing.append(f"{name} ({len(ids)} matches)")
    for u in st:
        u["form"] = ("statute" if u["id"] in statute_ids else "voluntary") if u["treated"] else None
    allu = st + others
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    lines = ["Styria by legal form of the merger (styria_voluntary.py)",
             f"Names from the StGsrG: {len(STATUTE)}, assigned {len(statute_ids)}, without a unique match: "
             f"{', '.join(missing) or 'none'}"]
    for f in ("statute", "voluntary"):
        g = [u for u in st if u.get("form") == f]
        lines.append(f"  {f}: {len(g)} units in panel, mean population 2014 "
                     f"{np.mean([u['raw'][s.REF][COL_INHABITANTS] for u in g]):,.0f}")
    not_in_panel = statute_ids - {u["id"] for u in st if u["treated"]}
    lines.append(f"  named in the statute but not a merged unit in the panel: {sorted(not_in_panel)}")
    lines.append("")
    pair = {so.STYRIAN_CONTROL: st, "combined control group, year x size tercile": allu}
    rng = np.random.default_rng(s.SEED)
    targets = [("core administration net per inhabitant, log", lambda v: v["net"], True),
               ("ordinary spending per inhabitant, log", lambda v: v[COL_ORDINARY_SPENDING], True),
               ("section 94 per inhabitant, EUR", lambda v: v["A94"], False)]
    for label, fn, log in targets:
        lines.append(label)
        for cname, us in pair.items():
            vals = so.values(us, fn, log, False)
            r = fit(us, vals, s.YEARS, set(s.POST), cname != so.STYRIAN_CONTROL, rng)
            fmt = (lambda x: f"{x[0]:+.3f} [{x[1]:+.3f}, {x[2]:+.3f}] ({np.expm1(x[0]):+.1%})") if log else \
                  (lambda x: f"{x[0]:+.1f} [{x[1]:+.1f}, {x[2]:+.1f}]")
            lines.append(f"  {cname} (n {r['n']}): statute {fmt(r['leg'])}; voluntary {fmt(r['vol'])}; "
                         f"difference {fmt(r['diff'])}")
        lines.append("")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_voluntary.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
