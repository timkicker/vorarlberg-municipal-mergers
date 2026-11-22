"""Net tourism spending per municipality in Vorarlberg and what pooling it inside a merged unit means.

Writes data/derived/tourism_budget.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import fees  # noqa: E402
import personnel  # noqa: E402
import tourism  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
# Columns of the offenerhaushalt.at files offenerhaushalt_*_YYYY_ra_fhh_gemeinde.csv
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_ACCOUNT = "Konto-Grp"  # account group
COL_VALUE = "Wert"  # amount
COL_MVAG = "Mvag"  # MVAG code
SUBSECTIONS = ("770", "771")
STEP = 20.0


def read(year: int = 2024) -> dict:
    out = {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        v = collections.defaultdict(float)
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r[COL_SUBSECTION] not in SUBSECTIONS:
                    continue
                mv, acct, w = r[COL_MVAG][:2], r[COL_ACCOUNT], personnel.num(r[COL_VALUE])
                if mv in ("32", "34"):
                    v["net"] += w
                elif mv in ("31", "33"):
                    v["net"] -= w
                if mv == "32" and acct.startswith("75"):
                    v["associations"] += w
                if mv == "34" and acct[:2] == "08":
                    v["holdings"] += w
        out[path.name.split("_")[1]] = v
    return out


def q(x):
    return f"median {np.median(x):.1f}, 10th to 90th percentile {np.percentile(x, 10):.1f} to {np.percentile(x, 90):.1f}"


def main() -> None:
    m = read()
    pop = ba.fag_pop(2024)
    g = [k for k in pop if k in m]
    fee_table = fees.read()
    lines = ["Tourism in the municipal budget 2024, EUR per inhabitant (tourism_budget.py)",
             f"municipalities with a file: {len(g)} of {len(pop)}, without a file: {sorted(set(pop) - set(g))}", ""]
    net = np.array([m[k]["net"] / pop[k] for k in g])
    assoc = np.array([m[k]["associations"] / pop[k] for k in g])
    gt = np.array([fee_table[k]["Guest tax"] / pop[k] for k in g])
    lines.append(f"1. Tourism net (770, 771): {q(net)}, total {sum(m[k]['net'] for k in g) / 1e6:.1f} m")
    tot = sum(m[k]["net"] for k in g)
    top = sorted(g, key=lambda k: m[k]["net"] / pop[k], reverse=True)[:10]
    lines.append(f"   ten municipalities with the highest amount per inhabitant: {sum(m[k]['net'] for k in top) / tot:.0%} of the total; {', '.join(top)}")
    lines.append(f"   without booking: {sum(1 for k in g if m[k]['net'] == 0)}")
    lines.append(f"   of which contributions to associations (75x in MVAG 32): {q(assoc)}, total {sum(m[k]['associations'] for k in g) / 1e6:.1f} m")
    lines.append(f"   guest tax (834) for comparison: {q(gt)}, total {sum(fee_table[k]['Guest tax'] for k in g) / 1e6:.1f} m")
    lines.append(f"   payments for holdings (08x in MVAG 34): {sum(m[k]['holdings'] for k in g) / 1e6:.2f} m in {sum(1 for k in g if m[k]['holdings'])} municipalities")
    lines.append("")
    lines.append(f"2. Harmonisation per partition, units of at least two municipalities, all with a file; threshold {STEP:.0f} EUR per inhabitant")
    lines.append("Partition | units | population share burden rises | population share burden falls | mean size of the change EUR per inhabitant")
    for cut, us in tourism.units().items():
        n, inh, up, down, ab = 0, 0.0, 0.0, 0.0, 0.0
        for gs in us:
            if not all(x in m for x in gs):
                continue
            n += 1
            avg = sum(m[x]["net"] for x in gs) / sum(pop[x] for x in gs)
            for x in gs:
                ch = avg - m[x]["net"] / pop[x]
                inh += pop[x]
                up += pop[x] * (ch > STEP)
                down += pop[x] * (ch < -STEP)
                ab += pop[x] * abs(ch)
        lines.append(f"  {cut} | {n} | {up / inh:.0%} | {down / inh:.0%} | {ab / inh:.1f}")
    lines += ["", "3. Largest rise per partition: municipality, net EUR per inhabitant today and after sharing by head, member with the largest net amount in EUR, per inhabitant"]
    names = {}
    with open(DER / "neighbours.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            names[r["gkz_a"]], names[r["gkz_b"]] = r["name_a"], r["name_b"]
    for cut, us in tourism.units().items():
        best = None
        for gs in us:
            if len(gs) < 2 or not all(x in m for x in gs):
                continue
            avg = sum(m[x]["net"] for x in gs) / sum(pop[x] for x in gs)
            top_member = max(gs, key=lambda x: m[x]["net"])
            for x in gs:
                ch = avg - m[x]["net"] / pop[x]
                if best is None or ch > best[0]:
                    best = (ch, x, m[x]["net"] / pop[x], avg, top_member)
        if best:
            ch, x, before, after, tm = best
            lines.append(f"  {cut} | {names.get(x, x)} {before:.0f} to {after:.0f} | {names.get(tm, tm)} {m[tm]['net'] / pop[tm]:.0f}")
    text = "\n".join(lines)
    print(text)
    (DER / "tourism_budget.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
