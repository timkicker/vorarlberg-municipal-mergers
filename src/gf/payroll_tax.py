"""How unevenly the payroll tax lies between the members of a merged unit.

Run from the repository root.
Data: BMF, sheet § 26 of the 2026 transfer, municipal accounts 2024.
Writes data/derived/payroll_tax.txt.
"""

import collections
import csv
import statistics
import sys

import base_amount
import fag
import openpyxl

# Header cells of sheet § 26 in bmf_fag26_2026.xlsx of the BMF, checked before reading.
HEADER_ACCOUNTS = "Gemeindegebarung 2024"  # column group, municipal accounts 2024
HEADER_PAYROLL_TAX = "KommSt"  # column, payroll tax
CUTS = ("Threshold 2000", "Threshold 3500", "Threshold 5000", "official planning region")


def payroll_tax() -> dict:
    ws = openpyxl.load_workbook(fag.DER.parent / "raw" / "bmf_fag26_2026.xlsx", read_only=True, data_only=True)["§26"]
    assert ws.cell(4, 19).value == HEADER_ACCOUNTS and ws.cell(5, 21).value == HEADER_PAYROLL_TAX
    return {str(r[0]): float(r[20]) for r in ws.iter_rows(min_row=7, values_only=True) if isinstance(r[0], int) and 80000 < r[0] < 90000}


def main() -> None:
    k = payroll_tax()
    pop = base_amount.fag_pop(2024)
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    name = {r["gkz"]: r["municipality"] for r in rows}
    assert len(k) == 96 and set(k) == set(name) and set(name) <= set(pop)
    out = ["Payroll tax inside the merged units (payroll_tax.py)",
           "Source: BMF, sheet § 26 of the transfer 2026, municipal accounts 2024; population base_amount.fag_pop(2024)",
           f"payroll tax of all municipalities {sum(k.values()) / 1e6:,.1f} m EUR", "",
           "Partition | units | payroll tax in them m | volume above the per capita share m | share | median highest/lowest per inhabitant | municipalities above the per capita share | their share of population"]
    tops = {}
    for cut in CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        multi = [m for m in units.values() if len(m) > 1]
        vol = ktot = 0.0
        ratios, above, above_pop, all_pop, per = [], 0, 0.0, 0.0, []
        for m in multi:
            ku, eu = sum(k[g] for g in m), sum(pop[g] for g in m)
            v = 0.0
            for g in m:
                d = k[g] - pop[g] / eu * ku
                if d > 0:
                    v += d
                    above += 1
                    above_pop += pop[g]
            vol += v
            ktot += ku
            all_pop += eu
            pc = [k[g] / pop[g] for g in m]
            ratios.append(max(pc) / min(pc) if min(pc) > 0 else float("inf"))
            per.append((v, m, ku))
        med = statistics.median(ratios)
        out.append(f"  {cut} | {len(multi)} | {ktot / 1e6:,.1f} | {vol / 1e6:,.2f} | {vol / ktot:.1%} | {med:.2f} | {above} | {above_pop / all_pop:.1%}")
        tops[cut] = sorted(per, key=lambda x: -x[0])[:5]
    out += ["", "Five units with the largest volume (m EUR, share of the payroll tax of the unit, members with EUR per inhabitant)"]
    for cut in CUTS:
        out.append(f"  {cut}")
        for v, m, ku in tops[cut]:
            mem = ", ".join(f"{name[g]} {k[g] / pop[g]:,.0f}" for g in sorted(m, key=lambda g: -k[g] / pop[g]))
            out.append(f"    {v / 1e6:,.2f} | {v / ku:.0%} | {mem}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "payroll_tax.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
