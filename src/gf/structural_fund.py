"""Structural fund (FAG 2024 § 26) for each set of merged units.

Writes data/derived/structural_fund.txt.
"""

import collections
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fag  # noqa: E402
from accounts_columns import COL_POPULATION_JAN1

RAW = fag.DER.parent / "raw"
# Columns of vbg_population_fag.csv and vbg_result_accounts.csv (open data of the state of Vorarlberg)
COL_YEAR = "berichtsjahr"  # reference year, both files
COL_POPULATION = "bevoelkerung"  # FAG population
COL_ACCOUNTS_VALUE = "ra.berichtsjahr"  # value of the closed accounts in the reference year


def ages(path: pathlib.Path) -> tuple[dict, dict]:
    """(total by gkz incl. 'AT', age bands by gkz incl. 'AT': [young, work, old])"""
    tot, band = collections.Counter(), collections.defaultdict(lambda: [0, 0, 0])
    for r in csv.DictReader(path.open(encoding="utf-8"), delimiter=";"):
        g = r["C-GRGEMAKT-0"].removeprefix("GRGEMAKT-")
        n = int(r[COL_POPULATION_JAN1])
        code = r["C-GALTEJ112-0"]
        age = 100 if code.startswith("GALT5J100") else int(code.removeprefix("GALTEJ112-")) - 1
        k = 0 if age < 15 else (1 if age <= 64 else 2)
        for key in (g, "AT"):
            tot[key] += n
            band[key][k] += n
    return tot, band


def fag_pop() -> dict:
    p = {}
    for r in csv.DictReader((RAW / "vbg_population_fag.csv").open(encoding="utf-8"), delimiter=";"):
        p[(r["gkz"], int(r[COL_YEAR]))] = float(r[COL_POPULATION])
    return p


def own_taxes() -> dict:
    t = {}
    for r in csv.DictReader((RAW / "vbg_result_accounts.csv").open(encoding="utf-8"), delimiter=";"):
        if r[COL_YEAR] == "2024" and r["mvag.code"] == "2111":
            t[r["gkz"]] = float(r[COL_ACCOUNTS_VALUE].replace(",", "."))
    return t


def amounts(m: list, d: dict, k: float) -> tuple[float, float, float, float]:
    old = sum(d["p0"][g] for g in m)
    new = sum(d["p1"][g] for g in m)
    a = 500 * (old * (1 + d["gB"]) - new)
    y, w, o = (sum(d["band"][g][i] for g in m) for i in range(3))
    b = 200 * ((y + o) - 1.1 * d["DB"] * w)
    tax = sum(d["tax"][g] for g in m)
    c = 0.10 * (0.75 * k * d["fkV"] * new - tax)
    return a, b, c, new


def main() -> None:
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv")))
    gk = [r["gkz"] for r in rows]
    t20, _ = ages(RAW / "bevstand_2020.csv")
    t24, band = ages(RAW / "bevstand_2024.csv")
    fp, tax = fag_pop(), own_taxes()
    d = {"p0": {g: fp[(g, 2020)] for g in gk}, "p1": {g: fp[(g, 2024)] for g in gk},
         "gB": 0.5 * (t24["AT"] / t20["AT"] - 1), "band": band, "tax": tax}
    yAT, wAT, oAT = band["AT"]
    d["DB"] = (yAT + oAT) / wAT
    d["fkV"] = sum(tax[g] for g in gk) / sum(d["p1"][g] for g in gk)
    out = ["Structural fund FAG 2024 § 26 per partition (structural_fund.py)",
           f"benchmarks: development {d['gB']:+.2%} (half of AT 2020-2024), dependency ratio AT {d['DB']:.3f}, "
           f"own levies Vorarlberg {d['fkV']:.0f} EUR per inhabitant", ""]
    for k in (1.0, 0.8, 1.2):
        out.append(f"mean fiscal strength times {k}")
        out.append("Partition | units | state quota m | change | municipalities in the key | share of merged units in the key")
        base_q = None
        for cut in ["Status quo"] + fag.CUTS:
            units = collections.defaultdict(list)
            for r in rows:
                units[r[cut]].append(r["gkz"])
            q = key_sum = key_merged = 0.0
            n_key = 0
            for m in units.values():
                a, b, c, n = amounts(m, d, k)
                if a + b + c > 0:
                    q += a + b + c
                    if a + c > 3 * n:
                        key_sum += a + c
                        n_key += 1
                        if len(m) > 1:
                            key_merged += a + c
            base_q = q if base_q is None else base_q
            share = key_merged / key_sum if key_sum else 0
            out.append(f"{cut} | {len(units)} | {q / 1e6:.2f} | {q / base_q - 1:+.0%} | {n_key} | {share:.0%}")
        out.append("")
    text = "\n".join(out)
    print(text)
    (fag.DER / "structural_fund.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
