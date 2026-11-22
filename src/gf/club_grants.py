"""Grants to non-profit organisations per inhabitant by size in 2024 and the cost of levelling up after a merger.

Run from the repository root.
Writes data/derived/club_grants.txt.
"""

import collections
import csv
import glob
import statistics
import sys

import debt
import fag

ACCOUNTS = ("757", "777")
NARROW = ("2", "3")
CLASSES = ((0, 1000), (1000, 2000), (2000, 5000), (5000, 10000), (10000, float("inf")))
CUTS = ("Threshold 3500", "Threshold 5000")
# columns of the closing account files of offenerhaushalt.at
COL_MUNICIPALITY_CODE = "Gemeindekennziffer"  # municipality code
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_ACCOUNT = "Konto-Grp"  # account group
COL_VALUE = "Wert"  # amount


def q(v):
    v = sorted(v)
    if len(v) < 2:
        return (v[0],) * 3 if v else (0.0,) * 3
    a, _, b = statistics.quantiles(v, n=4)
    return a, statistics.median(v), b


def load(accounts=ACCOUNTS) -> tuple[dict, dict]:
    narrow, wide = collections.defaultdict(float), collections.defaultdict(float)
    for f in sorted(glob.glob(str(debt.RAW / "offenerhaushalt" / "offenerhaushalt_*_2024_ra_fhh_gemeinde.csv"))):
        for r in csv.DictReader(open(f, encoding="utf-8"), delimiter=";"):
            if r[COL_ACCOUNT] not in accounts:
                continue
            g, v = r[COL_MUNICIPALITY_CODE], debt.num(r[COL_VALUE])
            wide[g] += v
            if r[COL_SUBSECTION][:1] in NARROW:
                narrow[g] += v
            narrow.setdefault(g, 0.0)
    return narrow, wide


def main() -> None:
    pop = fag.load_pop()
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    name = {r["gkz"]: r["municipality"] for r in rows}
    narrow, wide = load()
    have = set(wide) & set(name)
    missing = sorted(name[g] for g in name if g not in have)
    out = ["Grants to clubs 2024, accounts 757 and 777 (club_grants.py)", "",
           f"municipalities with data: {len(have)}, without: {len(missing)} ({', '.join(missing)})", "",
           f"total for the state (only municipalities with data): narrow {sum(narrow[g] for g in have) / 1e6:.2f} m, wide {sum(wide[g] for g in have) / 1e6:.2f} m EUR", "",
           "1. Per inhabitant by size (quartile 1 / median / quartile 3)", "  Class | municipalities | narrow | wide"]
    for lo, hi in CLASSES:
        g = [x for x in have if lo <= pop[x] < hi]
        e, w = q([narrow[x] / pop[x] for x in g]), q([wide[x] / pop[x] for x in g])
        lab = f"from {lo:,}" if hi == float("inf") else f"{lo:,} to under {hi:,}"
        out.append(f"  {lab} | {len(g)} | " + " | ".join(f"{a:,.0f} / {m:,.0f} / {c:,.0f}" for a, m, c in (e, w)))
    out += level_up(rows, pop, have, narrow, "2. Levelling up (narrow), extra costs per year")
    current, _ = load(("757",))
    out += level_up(rows, pop, have, current, "3. The same with account 757 only (current, without one-off capital transfers)")
    text = "\n".join(out)
    print(text)
    (fag.DER / "club_grants.txt").write_text(text + "\n")


def level_up(rows, pop, have, narrow, title) -> list:
    out = ["", title, "  Partition | units with merger | computed | without data | extra costs m | largest units (m)"]
    for cut in CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        multi = [(u, m) for u, m in units.items() if len(m) > 1]
        done, extra = [], 0.0
        for u, m in multi:
            if not all(g in have for g in m):
                continue
            top = max(narrow[g] / pop[g] for g in m)
            add = sum(top * pop[g] - narrow[g] for g in m)
            extra += add
            done.append((add, u))
        best = ", ".join(f"{u} {a / 1e6:.2f}" for a, u in sorted(done, reverse=True)[:3])
        out.append(f"  {cut} | {len(multi)} | {len(done)} | {len(multi) - len(done)} | {extra / 1e6:.2f} | {best}")
    return out


if __name__ == "__main__":
    sys.exit(main())
