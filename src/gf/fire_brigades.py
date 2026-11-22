"""Volunteer fire brigades by size and after the Styrian mergers (budget section 163).

Writes data/derived/fire_brigades.txt.
"""

import collections
import csv
import pathlib
import re
import statistics
import sys

import numpy as np
import pdfplumber

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fag  # noqa: E402
import styria as s  # noqa: E402
import styria_groups as sg  # noqa: E402
import styria_outcomes as so  # noqa: E402
from accounts_columns import COL_INHABITANTS, COL_REVENUE, COL_SPENDING

SUBSECTION = "VAUAB-163"  # sub-section 163 in the files of Statistics Austria
CLASSES = ((0, 1000), (1000, 2000), (2000, 5000), (5000, 10000), (10000, float("inf")))
DISTRICTS = {"801": "Bludenz", "802": "Bregenz", "803": "Dornbirn", "804": "Feldkirch"}
# text in the LFV annual report 2025
DISTRICT_HEAD = "Der Bezirk {}"  # heading of the page of a district
ACTIVE = r"([\d.]+)\s+aktive Frauen und Männer"  # number of active members
LOCAL = r"(\d+)\s+Ortsfeuerwehren"  # number of local fire brigades


def money163(years) -> dict:
    g = collections.defaultdict(lambda: [0.0, 0.0])
    for y in years:
        for r in csv.DictReader((s.RAW / f"gemua_at_{y}.csv").open(encoding="utf-8"), delimiter=";"):
            if r["C-VAUAB-0"] == SUBSECTION:
                cell = g[(r["C-C41-2"], y)]
                cell[0] += float(r[COL_SPENDING])
                cell[1] += float(r[COL_REVENUE])
    return g


def styria(lines: list) -> None:
    st, others = so.units()
    gm = money163(s.YEARS)
    mp, _ = s.mapping()
    pre = collections.defaultdict(list)
    for code, (n, _share) in mp.items():
        pre[n].append(code)
    in_st = {id(u) for u in st}
    for u in st + others:
        for t in s.YEARS:
            codes = (pre[u["id"]] if t in s.PRE else [u["id"]]) if id(u) in in_st else [u["id"]]
            u["raw"][t]["A163"] = sum(gm[(c, t)][0] for c in codes)
            u["raw"][t]["E163"] = sum(gm[(c, t)][1] for c in codes)
    allu = st + others
    cuts = np.quantile([u["raw"][s.REF][COL_INHABITANTS] for u in allu], [1 / 3, 2 / 3])
    for u in allu:
        u["group"] = int(np.searchsorted(cuts, u["raw"][s.REF][COL_INHABITANTS]))
    pair = {so.STYRIAN_CONTROL: st, "combined control group, year x size tercile": allu}
    rng = np.random.default_rng(s.SEED)
    lvl = np.mean([(u["raw"][t]["A163"] - u["raw"][t]["E163"]) / u["raw"][t][COL_INHABITANTS] for u in st for t in so.BEFORE])
    lines.append(f"1. Styria, subsection 163, EUR per inhabitant (net 2010-13 on average {lvl:,.1f})")
    lines += sg.run(pair, lambda v: v["A163"], False, rng, "  spending")
    lines += sg.run(pair, lambda v: v["E163"], False, rng, "  revenue")
    lines += sg.run(pair, lambda v: v["A163"] - v["E163"], False, rng, "  net")
    lines.append("")


def vorarlberg(lines: list) -> None:
    pop = {}
    for r in csv.DictReader((s.RAW / "gemhh_at_2000_2019.csv").open(encoding="utf-8"), delimiter=";"):
        if r["C-A10-0"] == "A10-2019" and r["C-C41-2"].startswith("8") and float(r[COL_INHABITANTS] or 0) > 0:
            pop[r["C-C41-2"]] = float(r[COL_INHABITANTS])
    gm = money163([2019])
    missing = [g for g in pop if (g, 2019) not in gm]
    lines.append(f"2. Vorarlberg 2019, subsection 163 net per inhabitant ({len(pop)} municipalities, without a line 163 and counted as 0: {len(missing)})")
    lines.append("  class | municipalities | median | quartiles")
    for lo, hi in CLASSES:
        v = [(gm[(g, 2019)][0] - gm[(g, 2019)][1]) / p for g, p in pop.items() if lo <= p < hi]
        q = statistics.quantiles(v, n=4) if len(v) > 1 else [v[0]] * 3
        name = f"from {lo:,}" if hi == float("inf") else f"{lo:,} to under {hi:,}"
        lines.append(f"  {name} | {len(v)} | {statistics.median(v):,.1f} | {q[0]:,.1f} to {q[2]:,.1f}")
    lines.append("")


def districts(lines: list) -> None:
    with pdfplumber.open(s.RAW / "lfv_annual_report_2025.pdf") as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    pop = fag.load_pop()
    lines.append("3. districts 2025 (annual report LFV, with works fire brigades), population 1.1.2024")
    lines.append("  district | population | municipalities | active members | per 1,000 inhabitants | local fire brigades | per municipality")
    for code, name in DISTRICTS.items():
        i = text.index(DISTRICT_HEAD.format(name))
        block = text[i:i + 1500]
        active = int(re.search(ACTIVE, block).group(1).replace(".", ""))
        local = int(re.search(LOCAL, block).group(1))
        mun = [g for g in pop if g.startswith(code)]
        n = sum(pop[g] for g in mun)
        lines.append(f"  {name} | {n:,} | {len(mun)} | {active:,} | {active / n * 1000:.1f} | {local} | {local / len(mun):.2f}")


def main() -> None:
    lines = ["Fire brigades by size and after the merger (fire_brigades.py)", ""]
    styria(lines)
    vorarlberg(lines)
    districts(lines)
    text = "\n".join(lines)
    print(text)
    (s.OUT / "fire_brigades.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
