"""Scenario: the Styrian fall in ordinary spending applied to Vorarlberg's merged units, 2024.

Writes data/derived/total_spending_2024.txt.
"""

import collections
import csv
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import personnel  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
# Columns of the offenerhaushalt.at files offenerhaushalt_*_YYYY_ra_fhh_gemeinde.csv
COL_MVAG = "Mvag"  # MVAG code
COL_VALUE = "Wert"  # amount


def rates() -> tuple[dict, float]:
    """Falls in ordinary spending as shares (upper bound, point, lower bound), read from styria_no2014.txt."""
    block = (DER / "styria_no2014.txt").read_text().split("ordinary spending per inhabitant, log")[1].split("\n\n")[0]

    def falls(label: str) -> tuple[float, float, float]:
        line = next(x for x in block.splitlines() if x.strip().startswith(label + ":"))
        point, lo, hi = (float(v) for v in re.search(r"\((-?[\d.]+)%, (-?[\d.]+)% to (-?[\d.]+)%\)", line).groups())
        return -hi / 100, -point / 100, -lo / 100

    out = {"Styria": falls("Styrian control, with 2014"), "combined": falls("combined control group, year x size tercile, with 2014")}
    return out, falls("Styrian control, without 2014")[1]


def operating(year: int = 2024) -> dict:
    out = {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        t = 0.0
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r[COL_MVAG][:2] == "32":
                    t += personnel.num(r[COL_VALUE])
        out[path.name.split("_")[1]] = t
    return out


def main() -> None:
    names = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(DER / "pareto_partitions.csv"))}
    by_name = {v: k for k, v in names.items()}
    pop = ba.fag_pop(2024)
    op = operating()
    have = [k for k in op if k in pop]
    all96 = sum(op[k] for k in have) * sum(pop.values()) / sum(pop[k] for k in have)
    RATES, NO2014 = rates()
    mid = RATES["Styria"][1]
    lines = ["Scenario: the Styrian fall in ordinary spending applied to Vorarlberg, 2024 (total_spending_2024.py)",
             f"MVAG 32 operating payments: {len(have)} municipalities with a file, scaled up to 96: {all96 / 1e6:,.0f} m", "",
             f"Partition | population merged | operating payments of the predecessors m (share with file) | Styria {RATES['Styria'][0]:.1%} / {mid:.1%} / {RATES['Styria'][2]:.1%} m | combined control group {RATES['combined'][0]:.1%} / {RATES['combined'][2]:.1%} m | {mid:.1%} in % of all 96 | {mid:.1%} per merged inhabitant | without 2014 {NO2014:.1%} m"]
    units = collections.defaultdict(list)
    for r in csv.DictReader(open(DER / "fag_units.csv")):
        units[r["partition"]].append(r)
    for cut, rs in units.items():
        inh = cov_inh = cov = 0.0
        for r in rs:
            gs = [by_name[m] for m in r["members"].split(";")]
            if len(gs) < 2:
                continue
            for g in gs:
                inh += pop[g]
                if g in op:
                    cov_inh += pop[g]
                    cov += op[g]
        base = cov * inh / cov_inh
        s = [base * x / 1e6 for x in RATES["Styria"]]
        m = [base * RATES["combined"][i] / 1e6 for i in (0, 2)]
        lines.append(f"{cut} | {inh:,.0f} | {base / 1e6:,.1f} ({cov_inh / inh:.0%}) | {s[0]:.1f} / {s[1]:.1f} / {s[2]:.1f} | {m[0]:.1f} / {m[1]:.1f}"
                     f" | {base * mid / all96:.2%} | {base * mid / inh:,.0f} | {base * NO2014 / 1e6:.1f}")
    text = "\n".join(lines)
    print(text)
    (DER / "total_spending_2024.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
