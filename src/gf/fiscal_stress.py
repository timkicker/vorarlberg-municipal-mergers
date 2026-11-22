"""Fiscal stress of the Vorarlberg municipalities 2020 to 2024 as frame for the savings.

Writes data/derived/fiscal_stress.txt.
"""

import collections
import csv
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import balance  # noqa: E402
import personnel  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
YEARS = range(2020, 2025)
# columns of the municipal finance tables of data.vorarlberg.gv.at
COL_YEAR = "berichtsjahr"  # reference year
COL_POPULATION = "bevoelkerung"  # FAG population, vbg_population_fag.csv
COL_MVAG_CODE = "mvag.code"  # MVAG code, vbg_financing_accounts.csv
COL_MVAG_LEVEL = "mvag.ebene"  # MVAG level, vbg_financing_accounts.csv
COL_SUM_LEVEL = "summenebene"  # sum level, vbg_financing_accounts.csv
COL_ACCOUNTS_VALUE = "ra.berichtsjahr"  # closing accounts of the reference year, vbg_financing_accounts.csv


def num(s: str) -> float:
    return float(s.replace(",", ".")) if s else 0.0


def load() -> dict:
    v = collections.defaultdict(float)
    with open(RAW / "vbg_financing_accounts.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            code = r[COL_MVAG_CODE] if r[COL_MVAG_LEVEL] != "SA1" else "SA1"
            if r[COL_SUM_LEVEL] == "329" and r[COL_MVAG_LEVEL] == "SA1":
                code = "SA1"
            if code in ("SA1", "361", "3615", "3112", "3231"):
                v[(int(r[COL_YEAR]), r["gkz"], code)] += num(r[COL_ACCOUNTS_VALUE])
    return v


def e24_range() -> dict:
    """Lower and upper end of E24 per partition, as in the paper."""
    out = {}
    for line in (DER / "savings_2024_low.txt").read_text().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if parts[0] in balance.NAMES:
            lo, hi = (float(x) for x in re.findall(r"-?[\d.]+", parts[4]))
            out[parts[0]] = (lo, hi)
    return out


def main() -> None:
    v = load()
    pop = {}
    with open(RAW / "vbg_population_fag.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            pop[(int(r[COL_YEAR]), r["gkz"])] = int(r[COL_POPULATION])
    gkz = sorted({g for (y, g, _) in v if y == 2024})
    lines = [f"municipalities with data 2024: {len(gkz)}", ""]
    lines.append("1. Free cash margin (balance 1 minus repayment 361) negative, number of municipalities")
    lines.append("  Year | municipalities | negative | negative without leasing (361 minus 3615)")
    fs = {}
    for y in YEARS:
        gs = [g for g in gkz if (y, g, "SA1") in v]
        a = {g: v[(y, g, "SA1")] - v[(y, g, "361")] for g in gs}
        b = {g: v[(y, g, "SA1")] - v[(y, g, "361")] + v[(y, g, "3615")] for g in gs}
        fs[y] = a
        lines.append(f"  {y} | {len(gs)} | {sum(x < 0 for x in a.values())} | {sum(x < 0 for x in b.values())}")
    lines.append("")
    lines.append("2. Total of all municipalities, m euro and euro per inhabitant")
    lines.append("  Year | tax shares 3112 | transfers to public law bodies 3231 | 3231 per inhabitant | share 3231 of 3112")
    tot = {}
    for y in YEARS:
        ts = sum(v[(y, g, "3112")] for g in gkz)
        tr = sum(v[(y, g, "3231")] for g in gkz)
        p = sum(pop.get((y, g), 0) for g in gkz)
        tot[y] = (ts, tr, p)
        lines.append(f"  {y} | {ts / 1e6:.1f} | {tr / 1e6:.1f} | {tr / p:.0f} | {tr / ts:.0%}")
    (e0, t0, _), (e1, t1, _) = tot[2020], tot[2024]
    lines.append(f"  growth 2020 to 2024: tax shares {e1 / e0 - 1:+.0%} ({(e1 - e0) / 1e6:+.1f} m), "
                 f"transfers 3231 {t1 / t0 - 1:+.0%} ({(t1 - t0) / 1e6:+.1f} m)")
    lines.append("")
    lines.append("3. Annual saving E24 per partition (savings_2024_low.txt, lower to upper end) against transfers 3231 in 2024")
    lines.append("  Partition | saving m | share of transfers 2024 | share of the growth of transfers 2020 to 2024")
    for cut, (lo, hi) in e24_range().items():
        lines.append(f"  {balance.NAMES[cut]} | {lo:.1f} to {hi:.1f} | {lo * 1e6 / t1:.1%} to {hi * 1e6 / t1:.1%} | "
                     f"{lo * 1e6 / (t1 - t0):.0%} to {hi * 1e6 / (t1 - t0):.0%}")
    lines.append("")
    lines.append("4. Free cash margin 2024 negative by size class (FAG population, reporting year 2024)")
    lines.append("  Class | municipalities | negative | share | cash margin per inhabitant, median")
    by = collections.defaultdict(list)
    for g in fs[2024]:
        by[personnel.klass(pop[(2024, g)])].append(g)
    for c in sorted(by):
        gs = by[c]
        neg = sum(fs[2024][g] < 0 for g in gs)
        med = sorted(fs[2024][g] / pop[(2024, g)] for g in gs)[len(gs) // 2]
        lines.append(f"  {personnel.LABELS[c]} | {len(gs)} | {neg} | {neg / len(gs):.0%} | {med:.0f}")
    text = "\n".join(lines)
    print(text)
    (DER / "fiscal_stress.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
