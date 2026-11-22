"""Upper bounds for further Vorarlberg grants that depend on size or financial strength.

Writes data/derived/size_grants.txt.
"""

import collections
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fag  # noqa: E402
import personnel  # noqa: E402
import social_fund  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
BASE, CAP = 23, 50  # § 9(1)(a) and (5), per cent
STRUCTURAL_SUPPORT = 3_000_000  # accountability report 2024, p. 94
# Columns of the offenerhaushalt.at files offenerhaushalt_*_YYYY_ra_fhh_gemeinde.csv
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_ACCOUNT = "Konto-Grp"  # account group
COL_ACCOUNT_TEXT = "Konto-Text"  # account text
COL_VALUE = "Wert"  # amount
TEXT_STATE_GRANT = "bedarf"  # part of the account text of state grants, lower case
BUILD = lambda a: a[:3] <= "029" or a[:2] == "21" or "36" <= a[:2] <= "38" or a[:3] == "817" or a[:2] == "82"  # noqa: E731


def size_bonus(n: int) -> int:
    """Percentage points by population, § 9(2)."""
    if n > 1500:
        return 0
    if n <= 600:
        return 10
    return 10 - -(-(n - 600) // 100)  # 601-700 -> 9, ..., 1401-1500 -> 1


def files(year: int) -> dict:
    """gkz -> (childcare grants, building transfers)."""
    out = {}
    for path in (RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv"):
        kb = bd = 0.0
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                a, k, w = r[COL_SUBSECTION], r[COL_ACCOUNT], personnel.num(r[COL_VALUE])
                if a.startswith("24") and k == "861" and TEXT_STATE_GRANT in r[COL_ACCOUNT_TEXT].lower():
                    kb += w
                if k == "301" and BUILD(a):
                    bd += w
        out[path.name.split("_")[1]] = (kb, bd)
    return out


def main() -> None:
    names = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(DER / "pareto_partitions.csv"))}
    by_name = {v: k for k, v in names.items()}
    pop = fag.load_pop()
    strength = social_fund.strength_61()
    avg = sum(strength.values()) / sum(pop[g] for g in strength)
    weak = {g for g in strength if strength[g] / pop[g] < avg}
    f24, f23 = files(2024), files(2023)
    assert len(f24) == len(f23) == 88
    under5k = sum(n for g, n in pop.items() if g in names and n <= 5000)
    lines = [f"Files 2024: childcare {sum(v[0] for v in f24.values()) / 1e6:.2f} m, building (account 301) {sum(v[1] for v in f24.values()) / 1e6:.2f} m; "
             f"2023: {sum(v[0] for v in f23.values()) / 1e6:.2f} and {sum(v[1] for v in f23.values()) / 1e6:.2f} m",
             f"files only 2024: {len(set(f24) - set(f23))}, only 2023: {len(set(f23) - set(f24))}",
             f"municipalities below the mean financial strength per inhabitant ({avg * 1e6:,.0f} EUR): {len(weak)} of {len(strength)}", ""]
    clawback = {}
    for line in (DER / "residual_items.txt").read_text().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) > 4 and parts[0] in ("Threshold 2000", "Threshold 3500", "Threshold 5000", "official planning region", "official region", "official district"):
            clawback[parts[0]] = float(parts[3])
    lines.append("Partition | FAG gain | childcare | building 2024 (mean 23/24) | structural support | total | share | with claw-back via the residual item | share | members without file")
    units = collections.defaultdict(list)
    for r in csv.DictReader(open(DER / "fag_units.csv")):
        units[r["partition"]].append(r)
    for cut, rows in units.items():
        G = K = B = Bm = S = 0.0
        miss = 0
        for r in rows:
            if int(r["municipalities"]) < 2:
                continue
            gain = float(r["after_with_inflow_eur"]) - float(r["before_eur"])
            if gain <= 0:
                continue
            G += gain
            mem = [by_name[m] for m in r["members"].split(";")]
            for g in mem:
                if g not in f24:
                    miss += 1
                    continue
                z = size_bonus(pop[g])
                share = z / (BASE + z) + ((CAP - BASE - z) / CAP if g in weak else 0.0)
                K += f24[g][0]
                B += min(1.0, share) * f24[g][1]
                Bm += min(1.0, share) * ((f24[g][1] + f23[g][1]) / 2 if g in f23 else f24[g][1])  # 2024 alone where 2023 is missing
            if int(r["pop"]) > 5000:
                S += STRUCTURAL_SUPPORT * sum(pop[g] for g in mem if pop[g] <= 5000) / under5k
        tot = K + B + S
        lines.append(f"{cut} | {G / 1e6:+.1f} | {K / 1e6:.1f} | {B / 1e6:.1f} ({Bm / 1e6:.1f}) | {S / 1e6:.1f} | {tot / 1e6:.1f} | {tot / G:.0%} | "
                     f"{tot / 1e6 + clawback[cut]:.1f} | {(tot + clawback[cut] * 1e6) / G:.0%} | {miss}")
    text = "\n".join(lines)
    print(text)
    (DER / "size_grants.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
