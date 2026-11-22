"""Fees and municipal taxes per municipality in Vorarlberg and what harmonising them inside a merged unit means.

Writes data/derived/fees.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import personnel  # noqa: E402
import tourism  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
FEES = {"Water": "850", "Sewage": "851", "Waste": "852"}
TAXES = {"Property tax B": "831", "Dog tax": "838", "Guest tax": "834", "Payroll tax": "833"}
# columns of the closing account files of offenerhaushalt.at
COL_MVAG = "Mvag"  # MVAG code
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_ACCOUNT = "Konto-Grp"  # account group
COL_VALUE = "Wert"  # amount


def read(year: int = 2024) -> dict:
    out = {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        v = collections.defaultdict(float)
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                mv, sub, kg, w = r[COL_MVAG][:2], r[COL_SUBSECTION], r[COL_ACCOUNT], personnel.num(r[COL_VALUE])
                for name, a in FEES.items():
                    if sub == a:
                        if mv == "31" and kg == "852":
                            v[name] += w
                        if mv == "31":
                            v[name + " in"] += w
                        elif mv == "32":
                            v[name + " out"] += w
                if mv == "31":
                    for name, k in TAXES.items():
                        if kg == k:
                            v[name] += w
        out[path.name.split("_")[1]] = v
    return out


def main() -> None:
    m = read()
    pop = ba.fag_pop(2024)
    g = [k for k in m if k in pop]
    lines = ["Fees and municipal levies 2024 per inhabitant (fees.py)", f"municipalities with a file: {len(g)} of {len(pop)}", ""]
    lines.append("1. Per municipality, EUR per inhabitant: item | municipalities with receipts | without | median | 10th to 90th percentile | cost coverage median (31 over 32 of the sub-section)")
    have = {}
    for name in list(FEES) + list(TAXES):
        with_ = [k for k in g if m[k][name] > 0]
        have[name] = set(with_)
        x = np.array([m[k][name] / pop[k] for k in with_])
        cov = ""
        if name in FEES:
            c = [m[k][name + " in"] / m[k][name + " out"] for k in with_ if m[k][name + " out"] > 0]
            cov = f" | {np.median(c):.2f}"
        lines.append(f"  {name} | {len(with_)} | {len(g) - len(with_)} | {np.median(x):.1f} | {np.percentile(x, 10):.1f} to {np.percentile(x, 90):.1f}{cov}")
    lines.append("")
    u = tourism.units()
    lines.append("2. Per partition, units of at least two municipalities, all predecessors with a file and receipts in the item")
    lines.append("Partition | item | units | range high/low, median | population share +10 % or more | population share -10 % or more | mean change EUR per inhabitant (absolute)")
    for cut, us in u.items():
        for name in list(FEES) + list(TAXES):
            spans, inh_all, up, down, section = [], 0.0, 0.0, 0.0, 0.0
            n = 0
            for gs in us:
                if not all(x in have[name] for x in gs):
                    continue
                n += 1
                per = {x: m[x][name] / pop[x] for x in gs}
                spans.append(max(per.values()) / min(per.values()))
                avg = sum(m[x][name] for x in gs) / sum(pop[x] for x in gs)
                for x in gs:
                    inh_all += pop[x]
                    ch = avg / per[x] - 1
                    up += pop[x] * (ch > 0.10)
                    down += pop[x] * (ch < -0.10)
                    section += pop[x] * abs(avg - per[x])
            if n:
                lines.append(f"  {cut} | {name} | {n} | {np.median(spans):.2f} | {up / inh_all:.0%} | {down / inh_all:.0%} | {section / inh_all:.1f}")
        lines.append("")
    text = "\n".join(lines)
    print(text)
    (DER / "fees.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
