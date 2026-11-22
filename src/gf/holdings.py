"""Holdings in companies and guarantees of Vorarlberg municipalities, 2024, by size and per cut.

Run from the repository root. Writes data/derived/holdings.txt.
"""

import collections
import csv
import statistics
import sys

import debt
import fag

Y = 2024
CODES = {"104": "holdings", "1041": "affiliated", "1042": "associated", "1043": "other"}
CLASSES = ((0, 1000), (1000, 2000), (2000, 5000), (5000, 10000), (10000, float("inf")))
# columns of the municipal finance tables of data.vorarlberg.gv.at
COL_YEAR = "berichtsjahr"  # reference year
COL_POPULATION = "bevoelkerung"  # FAG population, vbg_population_fag.csv
COL_MVAG_CODE = "mvag.code"  # MVAG code, vbg_asset_accounts.csv
COL_END_VALUE = "endstand.rj"  # value at the end of the reference year, vbg_asset_accounts.csv
COL_LOANS_END = "darlehensendstand"  # outstanding loans at the end of the year, vbg_loans.csv
COL_GUARANTEES_END = "haftungsendstand"  # guarantees at the end of the year, vbg_loans.csv
COL_LEASING_END = "finanzierungsleasing.endstand"  # finance leasing at the end of the year, vbg_loans.csv


def q(v):
    v = sorted(v)
    a, _, b = statistics.quantiles(v, n=4) if len(v) > 1 else (v[0],) * 3
    return a, statistics.median(v), b


def main() -> None:
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    name = {r["gkz"]: r["municipality"] for r in rows}
    hold = collections.defaultdict(float)
    for r in csv.DictReader((debt.RAW / "vbg_asset_accounts.csv").open(encoding="utf-8"), delimiter=";"):
        if r[COL_YEAR] == str(Y) and r[COL_MVAG_CODE] in CODES:
            hold[(r["gkz"], r[COL_MVAG_CODE])] += debt.num(r[COL_END_VALUE])
    fp, loan, guar, lease = {}, {}, {}, {}
    for r in csv.DictReader((debt.RAW / "vbg_population_fag.csv").open(encoding="utf-8"), delimiter=";"):
        if r[COL_YEAR] == str(Y):
            fp[r["gkz"]] = float(r[COL_POPULATION])
    for r in csv.DictReader((debt.RAW / "vbg_loans.csv").open(encoding="utf-8"), delimiter=";"):
        if r[COL_YEAR] == str(Y):
            loan[r["gkz"]] = debt.num(r[COL_LOANS_END])
            guar[r["gkz"]] = debt.num(r[COL_GUARANTEES_END])
            lease[r["gkz"]] = debt.num(r[COL_LEASING_END])
    gk = sorted(name)
    out = ["Holdings and guarantees of the municipalities (holdings.py)", ""]
    out.append(f"loans {Y} missing for: {', '.join(name[g] for g in gk if g not in loan) or 'none'}")
    out.append("")
    out.append(f"1. Totals {Y}, m EUR, and number of municipalities with a value above zero")
    for c, lab in CODES.items():
        v = [hold[(g, c)] for g in gk]
        out.append(f"  {c} {lab} | {sum(v) / 1e6:,.1f} | {sum(x > 0 for x in v)}")
    tl, tg, tle = sum(loan.values()), sum(guar.values()), sum(lease.values())
    out.append(f"  loans | {tl / 1e6:,.1f} | {sum(loan[g] > 0 for g in loan)}")
    out.append(f"  guarantees | {tg / 1e6:,.1f} | {sum(guar[g] > 0 for g in guar)}")
    out.append(f"  finance leasing | {tle / 1e6:,.1f} | {sum(lease[g] > 0 for g in lease)}")
    out.append(f"  guarantees in % of loans: {tg / tl:.1%}")
    out.append("")
    out.append("2. Per inhabitant by size (quartile 1 / median / quartile 3)")
    out.append("  Class | municipalities | holdings | guarantees")
    for lo, hi in CLASSES:
        g = [x for x in gk if lo <= fp[x] < hi]
        b = q([hold[(x, "104")] / fp[x] for x in g])
        h = q([guar.get(x, 0.0) / fp[x] for x in g])
        lab = f"from {lo:,}" if hi == float("inf") else f"{lo:,} to under {hi:,}"
        out.append(f"  {lab} | {len(g)} | " + " | ".join(f"{a:,.0f} / {m:,.0f} / {c:,.0f}" for a, m, c in (b, h)))
    out.append("")
    out.append("3. Highest guarantees per inhabitant")
    out.append("  Municipality | guarantees per inhabitant | loans per inhabitant | holdings per inhabitant")
    for g in sorted(gk, key=lambda x: -guar.get(x, 0.0) / fp[x])[:10]:
        out.append(f"  {name[g]} | {guar.get(g, 0) / fp[g]:,.0f} | {loan.get(g, 0) / fp[g]:,.0f} | {hold[(g, '104')] / fp[g]:,.0f}")
    out.append("")
    out.append("4. Guarantees that pass to other members per partition")
    out.append("  Partition | shifted m | share | largest givers (m)")
    for cut in fag.CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        moved, give = 0.0, []
        for m in units.values():
            P = sum(fp[g] for g in m)
            H = sum(guar.get(g, 0.0) for g in m)
            for g in m:
                d = guar.get(g, 0.0) - fp[g] / P * H
                if d > 0:
                    moved += d
                    give.append((d, g))
        top = ", ".join(f"{name[g]} {d / 1e6:.1f}" for d, g in sorted(give, reverse=True)[:3])
        out.append(f"  {cut} | {moved / 1e6:.1f} | {moved / tg:.0%} | {top}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "holdings.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
