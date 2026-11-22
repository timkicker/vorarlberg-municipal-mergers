"""Vorarlberg 2020 to 2024 by size class: core administration, personnel, material costs and transfers.

Writes data/derived/size_trends.txt.
"""

import collections
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import personnel as pe  # noqa: E402

YEARS = (2020, 2021, 2022, 2023, 2024)
STATE_ITEMS = {"personnel (321)": "321", "material costs (322)": "322", "transfers to bodies of public law (3231)": "3231"}
# Columns of the offenerhaushalt.at files offenerhaushalt_*_YYYY_ra_fhh_gemeinde.csv
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_MVAG = "Mvag"  # MVAG code
COL_VALUE = "Wert"  # amount
# Columns of vbg_financing_accounts.csv (financing budget of the municipalities, open data of the state of Vorarlberg)
COL_ACCOUNTS_VALUE = "ra.berichtsjahr"  # value of the closed accounts in the reference year
COL_YEAR = "berichtsjahr"  # reference year


def core(year: int) -> dict:
    out = {}
    for path in sorted((pe.RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        v = collections.defaultdict(float)
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r[COL_SUBSECTION] in pe.CORE:
                    mv = r[COL_MVAG][:2]
                    if mv in ("31", "32"):
                        v[mv] += pe.num(r[COL_VALUE])
        out[path.name.split("_")[1]] = {"gross": v["32"], "net": v["32"] - v["31"]}
    return out


def state_accounts() -> dict:
    d = collections.defaultdict(dict)
    with open(pe.RAW / "vbg_financing_accounts.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r[COL_ACCOUNTS_VALUE] and r["mvag.code"] in STATE_ITEMS.values():
                d[(r["gkz"], int(r[COL_YEAR]))][r["mvag.code"]] = pe.num(r[COL_ACCOUNTS_VALUE])
    return d


def block(title, gs, val, pops, cls, lines):
    lines.append(title)
    lines.append("  class | municipalities | 2020 | 2022 | 2024 | growth 2020-24 | growth 2021-24 (EUR per inhabitant, sum of the class)")
    for c, lab in enumerate(pe.LABELS):
        mem = [g for g in gs if cls[g] == c]
        if not mem:
            continue
        pc = {y: sum(val(g, y) for g in mem) / sum(pops[y][g] for g in mem) for y in YEARS}
        lines.append(f"  {lab:<16} | {len(mem):>3} | {pc[2020]:>6,.0f} | {pc[2022]:>6,.0f} | {pc[2024]:>6,.0f} | {pc[2024] / pc[2020] - 1:+.0%} | {pc[2024] / pc[2021] - 1:+.0%}")
    pc = {y: sum(val(g, y) for g in gs) / sum(pops[y][g] for g in gs) for y in YEARS}
    lines.append(f"  {'all':<16} | {len(gs):>3} | {pc[2020]:>6,.0f} | {pc[2022]:>6,.0f} | {pc[2024]:>6,.0f} | {pc[2024] / pc[2020] - 1:+.0%} | {pc[2024] / pc[2021] - 1:+.0%}")
    lines.append("")


def main() -> None:
    pops = {y: ba.fag_pop(y) for y in YEARS}
    cls = {g: pe.klass(int(n)) for g, n in pops[2024].items()}
    c = {y: core(y) for y in YEARS}
    bal = sorted(set.intersection(*[set(c[y]) for y in YEARS]) & set(pops[2024]))
    lines = ["Vorarlberg 2020 to 2024 by size (size_trends.py)", "", f"core administration: {len(bal)} municipalities with a file in all five years", ""]
    for k in ("gross", "net"):
        block(f"core administration {k}, operating budget", bal, lambda g, y, k=k: c[y][g][k], pops, cls, lines)
    d = state_accounts()
    allg = sorted(pops[2024])
    for lab, code in STATE_ITEMS.items():
        block(lab + ", all municipalities", allg, lambda g, y, code=code: d[(g, y)].get(code, 0.0), pops, cls, lines)
    text = "\n".join(lines)
    print(text)
    (pe.OUT / "size_trends.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
