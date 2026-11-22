"""Claw-back of FAG gains through the Vorarlberg social fund (Social Benefits Act § 61).

Writes data/derived/social_fund.txt.
"""

import collections
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import balance  # noqa: E402
import fag  # noqa: E402

RAW = fag.DER.parent / "raw"
POT = 76.4  # m EUR, half of the municipal share of the social fund 2026
# Columns of vbg_result_accounts.csv (operating statement of the municipalities, open data of the state of Vorarlberg)
COL_YEAR = "berichtsjahr"  # reference year
COL_ACCOUNTS_VALUE = "ra.berichtsjahr"  # value of the closed accounts in the reference year
# Header cells of sheet § 26 in bmf_fag26_2026.xlsx of the BMF, checked before reading
HEADER_ACCOUNTS = "Gemeindegebarung 2024"  # column group, municipal accounts 2024
HEADER_PAYROLL_TAX = "KommSt"  # column, payroll tax


def strength(codes: tuple) -> dict:
    s = collections.Counter()
    for r in csv.DictReader((RAW / "vbg_result_accounts.csv").open(encoding="utf-8"), delimiter=";"):
        if r[COL_YEAR] == "2024" and r["mvag.code"] in codes:
            s[r["gkz"]] += float(r[COL_ACCOUNTS_VALUE].replace(",", ".")) / 1e6
    return s


def taxes() -> dict:
    """Property tax A and B plus payroll tax 2024 per municipality, m EUR (BMF, sheet §26 of the 2026 transfer)."""
    import openpyxl

    ws = openpyxl.load_workbook(RAW / "bmf_fag26_2026.xlsx", read_only=True, data_only=True)["§26"]
    assert ws.cell(4, 19).value == HEADER_ACCOUNTS and ws.cell(5, 21).value == HEADER_PAYROLL_TAX
    s = {}
    for r in ws.iter_rows(min_row=7, values_only=True):
        if isinstance(r[0], int) and 80000 < r[0] < 90000:
            s[str(r[0])] = (r[18] + r[19] + r[20]) / 1e6
    return s


def strength_61() -> dict:
    """Financial strength under Social Benefits Act § 61 without the casino levy: tax shares plus property and payroll tax."""
    ea, tx = strength(("2112",)), taxes()
    assert len(tx) == 96 and set(tx) == set(ea), (len(tx), len(ea))
    return collections.Counter({g: ea[g] + tx[g] for g in ea})


def main() -> None:
    f = balance.table("fag.txt")
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv")))
    out = ["Claw-back through the social fund per partition, m EUR per year (social_fund.py)",
           f"half shared by financial strength {POT} m EUR, financial strength 2024 from the operating statement"]
    variants = (("under § 61: tax shares plus property and payroll tax (main calculation)", strength_61),
                ("tax shares plus own levies", lambda: strength(("2111", "2112"))),
                ("tax shares only (upper bound)", lambda: strength(("2112",))))
    for label, fn in variants:
        fs = fn()
        F = sum(fs[r["gkz"]] for r in rows)
        out += ["", f"{label}: financial strength of all municipalities {F:,.1f} m",
                "Partition | FAG gain merged | extra payment merged | share of the gain | lower payment unchanged"]
        for cut, name in balance.NAMES.items():
            units = collections.defaultdict(list)
            for r in rows:
                units[r[cut]].append(r["gkz"])
            Fm = sum(fs[g] for m in units.values() if len(m) > 1 for g in m)
            Fu = F - Fm
            inflow = float(f[cut][3])
            win, lose, same_out, same_in = (float(f[cut][i]) for i in (7, 8, 9, 11))
            dm = win + lose + inflow - (same_in - same_out)
            du = same_in
            before_m = POT * Fm / F
            after_m = POT * (Fm + dm) / (F + dm + du)
            after_u = POT * (Fu + du) / (F + dm + du)
            pay_m = after_m - before_m
            pay_u = after_u - POT * Fu / F
            share = f"{pay_m / dm:.0%}" if dm > 0 else "n. a."
            out.append(f"{name} | {dm:+.1f} | {pay_m:+.2f} | {share} | {pay_u:+.2f}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "social_fund.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
