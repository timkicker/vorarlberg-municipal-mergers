"""Transfers to merged Styrian units 2020 to 2024 against 2010 to 2014.

Reads data/raw/offenerhaushalt_styria/ (offenerhaushalt.at, variant Statistics Austria).
Writes data/derived/styria_transfers_2024.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_outcomes as so  # noqa: E402
import styria_transfers as stt  # noqa: E402
from accounts_columns import COL_INHABITANTS, COL_POPULATION_JAN1

NEW = (2020, 2021, 2022, 2023, 2024)
OH = s.RAW / "offenerhaushalt_styria"
# Columns of the offenerhaushalt.at files offenerhaushalt_*_ra_fhh_statistik_at.csv
COL_MUN_CODE = "Gemeindekennziffer"  # municipality code
COL_YEAR = "Jahr"  # year
COL_MVAG = "Mvag"  # MVAG code
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_VALUE = "Wert"  # amount
TARGETS = {"A94": tuple(str(i) for i in range(940, 948)), "grants": ("940",)}


def number(x: str) -> float:
    assert "." not in x, x
    return float(x.replace(",", "."))


def new_income() -> tuple[dict, collections.Counter]:
    """(gkz, year) -> {target: EUR}, only MVAG 31 and 33."""
    g, files = {}, collections.Counter()
    for f in sorted(OH.glob("offenerhaushalt_*_ra_fhh_statistik_at.csv")):
        _, gkz, year, *_ = f.name.split("_")
        y = int(year)
        acc = {k: 0.0 for k in TARGETS}
        with f.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter=";"):
                assert r[COL_MUN_CODE] == gkz and r[COL_YEAR] == year, f.name
                if r[COL_MVAG][:2] not in ("31", "33"):
                    continue
                for k, sub_codes in TARGETS.items():
                    if r[COL_SUBSECTION] in sub_codes:
                        acc[k] += number(r[COL_VALUE])
        g[(gkz, y)] = acc
        files[y] += 1
    return g, files


def population(y: int) -> dict:
    p = collections.Counter()
    with (s.RAW / f"bevstand_{y}.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            p[r["C-GRGEMAKT-0"].removeprefix("GRGEMAKT-")] += float(r[COL_POPULATION_JAN1])
    return p


def main() -> None:
    st, _others = so.units()
    old = stt.income()
    mp, _ = s.mapping()
    pre = collections.defaultdict(list)
    for code, (n, _share) in mp.items():
        pre[n].append(code)
    new, files = new_income()
    pop = {y: population(y) for y in NEW}
    known = {u["id"] for u in st}
    unknown = sorted({g for (g, _y) in new if g not in known})
    periods = s.PRE + NEW
    units, missing = [], collections.Counter()
    for u in st:
        raw = {}
        for t in s.PRE:
            raw[t] = {COL_INHABITANTS: u["raw"][t][COL_INHABITANTS],
                      "A94": sum(old[(c, t)]["A94"] for c in pre[u["id"]]),
                      "grants": sum(old[(c, t)]["grants"] for c in pre[u["id"]])}
        ok = True
        for t in NEW:
            if (u["id"], t) not in new or not pop[t].get(u["id"]):
                missing[t] += 1
                ok = False
                continue
            raw[t] = dict(new[(u["id"], t)], **{COL_INHABITANTS: pop[t][u["id"]]})
        if ok:
            units.append({"id": u["id"], "treated": u["treated"], "raw": raw})
    lines = ["Transfers to Styrian units 2020 to 2024 (styria_transfers_2024.py), EUR per inhabitant, Styrian control",
             f"Files per year: {dict(sorted(files.items()))}; codes not among the units of 2015: {unknown or 'none'}",
             f"Units in the backtest {len(st)} ({sum(u['treated'] for u in st)} merged); without file or population per year: "
             f"{dict(sorted(missing.items()))}; in panel {len(units)} ({sum(u['treated'] for u in units)} merged)", ""]
    rng = np.random.default_rng(s.SEED)
    runs = [("after 2020-24", s.PRE + NEW, set(NEW))] + [(f"only {t}", s.PRE + (t,), {t}) for t in NEW]
    for k, name in (("A94", "section 94 (940 to 947), MVAG 31 and 33"), ("grants", "state grants (940), MVAG 31 and 33")):
        lines.append(name)
        for run, per, post in runs:
            vals = [{t: u["raw"][t][k] / u["raw"][t][COL_INHABITANTS] for t in per} for u in units]
            r = so.estimate(units, vals, per, post, False, rng)
            lines.append(f"  {run} (n {r['n']}): {r['b']:+.1f}  95 % [{r['lo']:+.1f}, {r['hi']:+.1f}]")
        lines.append("  summed per inhabitant, year: merged / unchanged")
        for t in periods:
            row = []
            for tr in (True, False):
                g = [u for u in units if u["treated"] == tr]
                row.append(sum(u["raw"][t][k] for u in g) / sum(u["raw"][t][COL_INHABITANTS] for u in g))
            lines.append(f"    {t}: {row[0]:7.1f} / {row[1]:7.1f}")
        lines.append("")
    # the 2016-19 result on the reduced panel, to see what the missing files change
    lines.append("2016-19 against 2010-14 only for the units of this panel (gemua_at)")
    ids = {u["id"] for u in units}
    sub = [u for u in st if u["id"] in ids]
    for k in ("A94", "grants"):
        per = s.PRE + s.POST
        vals = [{t: sum(old[(c, t)][k] for c in (pre[u["id"]] if t in s.PRE else [u["id"]])) / u["raw"][t][COL_INHABITANTS]
                 for t in per} for u in sub]
        r = so.estimate(sub, vals, per, set(s.POST), False, rng)
        lines.append(f"  {k} (n {r['n']}): {r['b']:+.1f}  95 % [{r['lo']:+.1f}, {r['hi']:+.1f}]")
    text = "\n".join(lines)
    print(text)
    (s.OUT / "styria_transfers_2024.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
