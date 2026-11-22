"""Municipal debt: comparison of the states and shift of the debt burden per set of merged units.

Writes data/derived/debt.txt.
"""

import collections
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fag  # noqa: E402
from accounts_columns import COL_DEBT, COL_INHABITANTS

RAW = fag.DER.parent / "raw"
STATES = {"1": "Burgenland", "2": "Carinthia", "3": "Lower Austria", "4": "Upper Austria",
        "5": "Salzburg", "6": "Styria", "7": "Tyrol", "8": "Vorarlberg"}
# columns of gemhh_at_2000_2019.csv of Statistics Austria
# columns of the municipal finance tables of data.vorarlberg.gv.at
COL_YEAR = "berichtsjahr"  # reference year
COL_POPULATION = "bevoelkerung"  # FAG population, vbg_population_fag.csv
COL_LOANS_END = "darlehensendstand"  # outstanding loans at the end of the year, vbg_loans.csv
COL_LEASING_END = "finanzierungsleasing.endstand"  # finance leasing at the end of the year, vbg_loans.csv
COL_GUARANTEES_END = "haftungsendstand"  # guarantees at the end of the year, vbg_loans.csv
COL_MVAG_CODE = "mvag.code"  # MVAG code, vbg_asset_accounts.csv
COL_MVAG_LEVEL = "mvag.ebene"  # MVAG level, vbg_asset_accounts.csv
COL_END_VALUE = "endstand.rj"  # value at the end of the reference year, vbg_asset_accounts.csv


def num(x: str) -> float:
    return float(x.replace(",", ".")) if x not in ("", "NA") else 0.0


def main() -> None:
    debt, pop = collections.Counter(), collections.Counter()
    for r in csv.DictReader((RAW / "gemhh_at_2000_2019.csv").open(encoding="utf-8"), delimiter=";"):
        y = int(r["C-A10-0"].removeprefix("A10-"))
        g = r["C-C41-2"]
        if y >= 2010 and g[0] in STATES:
            debt[(g[0], y)] += float(r[COL_DEBT])
            pop[(g[0], y)] += float(r[COL_INHABITANTS])
    out = ["Debt of the municipalities (debt.py)", "", "Debt per inhabitant without Vienna, GemHH, EUR",
           "State | " + " | ".join(str(y) for y in range(2010, 2020))]
    for k, name in STATES.items():
        out.append(name + " | " + " | ".join(f"{debt[(k, y)] / pop[(k, y)]:,.0f}" for y in range(2010, 2020)))
    at = {y: sum(debt[(k, y)] for k in STATES) / sum(pop[(k, y)] for k in STATES) for y in range(2010, 2020)}
    out.append("all without Vienna | " + " | ".join(f"{at[y]:,.0f}" for y in range(2010, 2020)))

    fp = {}
    for r in csv.DictReader((RAW / "vbg_population_fag.csv").open(encoding="utf-8"), delimiter=";"):
        fp[(r["gkz"], int(r[COL_YEAR]))] = float(r[COL_POPULATION])
    dl = {}
    for r in csv.DictReader((RAW / "vbg_loans.csv").open(encoding="utf-8"), delimiter=";"):
        dl[(r["gkz"], int(r[COL_YEAR]))] = (num(r[COL_LOANS_END]),
                                         num(r[COL_LEASING_END]) + num(r[COL_GUARANTEES_END]))
    years = sorted({y for _, y in dl})
    out += ["", "Vorarlberg, municipal finance statistics of the state, EUR per inhabitant (FAG population)",
            "Year | loans | loans, leasing and guarantees"]
    for y in years:
        gk = [g for g, yy in dl if yy == y]
        p = sum(fp[(g, y)] for g in gk)
        out.append(f"{y} | {sum(dl[(g, y)][0] for g in gk) / p:,.0f} | {sum(sum(dl[(g, y)]) for g in gk) / p:,.0f}")

    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv")))
    Y = 2024
    out += ["", f"Shift of the burden in a merger, as of {Y}, m EUR and share of all debt",
            "Partition | loans shifted | share | with leasing and guarantees | share | largest givers (m)"]
    for cut in fag.CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        res = []
        for i in (0, 1):
            val = (lambda g: dl.get((g, Y), (0.0, 0.0))[0]) if i == 0 else (lambda g: sum(dl.get((g, Y), (0.0, 0.0))))  # Viktorsberg missing from 2022
            moved, give = 0.0, []
            for m in units.values():
                P = sum(fp[(g, Y)] for g in m)
                D = sum(val(g) for g in m)
                for g in m:
                    diff = val(g) - fp[(g, Y)] / P * D
                    if diff > 0:
                        moved += diff
                        give.append((diff, g))
            total = sum(val(r["gkz"]) for r in rows)
            res.append((moved, moved / total, sorted(give, reverse=True)[:3]))
        names = {r["gkz"]: r["municipality"] for r in rows}
        top = ", ".join(f"{names[g]} {d / 1e6:.1f}" for d, g in res[0][2])
        out.append(f"{cut} | {res[0][0] / 1e6:.1f} | {res[0][1]:.0%} | {res[1][0] / 1e6:.1f} | {res[1][1]:.0%} | {top}")
    net_worth(fp, dl, rows, out)
    text = "\n".join(out)
    print(text)
    (fag.DER / "debt.txt").write_text(text + "\n")


def net_worth(fp: dict, dl: dict, rows: list, out: list, Y: int = 2024) -> None:
    nw = {}
    for r in csv.DictReader((RAW / "vbg_asset_accounts.csv").open(encoding="utf-8"), delimiter=";"):
        if r[COL_YEAR] == str(Y) and r[COL_MVAG_CODE] == "12" and r[COL_MVAG_LEVEL] == "0":
            nw[r["gkz"]] = num(r[COL_END_VALUE])
    names = {r["gkz"]: r["municipality"] for r in rows}
    miss = [names[r["gkz"]] for r in rows if r["gkz"] not in nw]
    total = sum(nw.values())
    out += ["", f"Net assets (MVAG 12) {Y}: total {total / 1e6:,.0f} m EUR, missing: {', '.join(miss) or 'none'}",
            "Partition | net assets shifted m | share | largest givers (m)"]
    for cut in fag.CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        moved, give = 0.0, []
        for m in units.values():
            P = sum(fp[(g, Y)] for g in m)
            V = sum(nw.get(g, 0.0) for g in m)
            for g in m:
                diff = nw.get(g, 0.0) - fp[(g, Y)] / P * V
                if diff > 0:
                    moved += diff
                    give.append((diff, g))
        top = ", ".join(f"{names[g]} {d / 1e6:.1f}" for d, g in sorted(give, reverse=True)[:3])
        out.append(f"{cut} | {moved / 1e6:.1f} | {moved / total:.0%} | {top}")
    allp = sum(fp[(r["gkz"], Y)] for r in rows)
    out += ["", "Municipality | loans per inhabitant | net assets per inhabitant",
            f"Vorarlberg | {sum(dl.get((r['gkz'], Y), (0, 0))[0] for r in rows) / allp:,.0f} | {total / allp:,.0f}"]
    for name in ("Lech", "Brand", "Warth", "Tschagguns"):
        g = next(r["gkz"] for r in rows if r["municipality"] == name)
        out.append(f"{name} | {dl.get((g, Y), (0, 0))[0] / fp[(g, Y)]:,.0f} | {nw.get(g, 0) / fp[(g, Y)]:,.0f}")


if __name__ == "__main__":
    main()
