"""Structural fund (FAG 2024 § 26) per set of merged units in euro, with the BMF inputs.

Writes data/derived/structural_fund_bmf.txt.
"""

import collections
import csv
import pathlib
import sys

import openpyxl

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import balance  # noqa: E402
import fag  # noqa: E402

RAW = fag.DER.parent / "raw"
POT = 120_000_000
PAID_2024 = 1_309_551  # Vorarlberg, sheet Zsfg of the same file


def read() -> tuple[dict, tuple]:
    ws = openpyxl.load_workbook(RAW / "bmf_fag26_2024.xlsx", read_only=True, data_only=True)["§26"]
    rows = list(ws.iter_rows(values_only=True))
    m = rows[5]
    scale = (m[8], m[15], m[24])  # half development, 1.1 x dependency ratio, 0.75 x strength per head
    mun = {}
    for r in rows[6:]:
        if isinstance(r[0], int) and r[0] >= 10000:
            mun[str(r[0])] = {"n": r[4], "n0": r[5], "y": r[11], "w": r[12], "o": r[13], "fk": r[23], "pos": r[28] or 0.0}
    return mun, scale


def amount(parts: list, scale: tuple) -> float:
    s = {k: sum(p[k] for p in parts) for k in ("n", "n0", "y", "w", "o", "fk")}
    a = -500 * (s["n"] - s["n0"] - s["n0"] * scale[0])
    b = 200 * ((s["y"] + s["o"]) - scale[1] * s["w"])
    c = 0.1 * (scale[2] * s["n"] - s["fk"])
    return a + b + c


def main() -> None:
    mun, scale = read()
    vbg = [g for g in mun if g.startswith("8")]
    rest = sum(max(amount([mun[g]], scale), 0) for g in mun if not g.startswith("8"))
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv")))
    assert sorted(r["gkz"] for r in rows) == sorted(vbg), "municipality codes differ"
    out = ["Structural fund FAG 2024 § 26 per partition with the BMF inputs (transfer 2024)",
           f"benchmarks: development {scale[0]:.4%}, dependency ratio {scale[1]:.4f}, fiscal strength {scale[2]:.2f} EUR per inhabitant",
           f"control: sum of positive amounts from the sheet {sum(v['pos'] for v in mun.values()):,.0f}, recomputed "
           f"{rest + sum(max(amount([mun[g]], scale), 0) for g in vbg):,.0f}", "",
           "Partition | units | positive sum Vorarlberg | state share EUR | change EUR | change %"]
    base = None
    for cut in ["Status quo"] + list(balance.NAMES):
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(mun[r["gkz"]])
        v = sum(max(amount(m, scale), 0) for m in units.values())
        share = POT * v / (rest + v)
        if base is None:
            base = share
            out.append(f"(Status quo against paid out: {share:,.0f} against {PAID_2024:,})")
        name = balance.NAMES.get(cut, cut)
        out.append(f"{name} | {len(units)} | {v:,.0f} | {share:,.0f} | {share - base:+,.0f} | {share / base - 1:+.0%}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "structural_fund_bmf.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
