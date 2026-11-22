"""Personnel cost of the Vorarlberg municipalities by size, 2020 and 2024.

Totals from the open data of the state of Vorarlberg (all 96), budget groups from the raw files of
offenerhaushalt.at (data/raw/offenerhaushalt/, not all municipalities).
Writes data/derived/personnel.txt.
"""

import collections
import csv
import pathlib
import sys

import numpy as np
from accounts_columns import COL_POPULATION_JAN1

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
CUTS = (1000, 2000, 3500, 7500, 15000)
LABELS = ("under 1,000", "1,000 to 2,000", "2,000 to 3,500", "3,500 to 7,500", "7,500 to 15,000", "over 15,000")
# Columns of vbg_financing_accounts.csv (financing budget of the municipalities, open data of the state of Vorarlberg)
COL_ACCOUNTS_VALUE = "ra.berichtsjahr"  # value of the closed accounts in the reference year
COL_YEAR = "berichtsjahr"  # reference year
COL_LABEL = "bezeichnung"  # text of the MVAG line
COL_MUNICIPALITY = "gemeinde"  # municipality name
LABEL_BALANCE = "Saldo"  # word in the label of a balance line
# Columns of the offenerhaushalt.at files offenerhaushalt_*_YYYY_ra_fhh_gemeinde.csv
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_ACCOUNT = "Konto-Grp"  # account group
COL_VALUE = "Wert"  # amount
CORE = {f"{i:03d}" for i in range(0, 35)} | {"091"}
SEED = 12345
N_BOOT = 2000


def num(s: str) -> float:
    return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)


def pop(year: int) -> dict:
    p = collections.Counter()
    with open(RAW / f"bevstand_{year}.csv") as f:
        for r in csv.DictReader(f, delimiter=";"):
            g = r["C-GRGEMAKT-0"].split("-")[1]
            if g.startswith("8"):
                p[g] += int(r[COL_POPULATION_JAN1])
    return p


def state_accounts() -> dict:
    """(gkz, year) -> {mvag code: RA value}, plus names."""
    d, names = collections.defaultdict(dict), {}
    with open(RAW / "vbg_financing_accounts.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r[COL_ACCOUNTS_VALUE] and r["mvag.code"] in ("32", "321", "3211", "3212", "3213"):
                if r["mvag.code"] == "32" and LABEL_BALANCE in r[COL_LABEL]:
                    continue
                d[(r["gkz"], int(r[COL_YEAR]))][r["mvag.code"]] = num(r[COL_ACCOUNTS_VALUE])
                names[r["gkz"]] = r[COL_MUNICIPALITY]
    return d, names


def ohh(year: int) -> dict:
    """gkz -> {group 0-9 personnel, core personnel, account 721, sum 5xx}."""
    out = {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        g = path.name.split("_")[1]
        v = collections.defaultdict(float)
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                k, a, w = r[COL_ACCOUNT], r[COL_SUBSECTION], num(r[COL_VALUE])
                if k.startswith("5"):
                    v["sum5"] += w
                    v[f"g{a[0]}"] += w
                    if a in CORE:
                        v["core"] += w
                if k == "721":
                    v["k721"] += w
                    if a in CORE:
                        v["core721"] += w
        out[g] = v
    return out


def klass(n: int) -> int:
    return int(np.searchsorted(CUTS, n, side="right"))


def table(rows: list, fn, title: str) -> list:
    """rows: (gkz, population, record). Sum per capita and median per class."""
    lines = [title, "  class | municipalities | total per inhabitant | median per inhabitant"]
    by = collections.defaultdict(list)
    for _g, n, rec in rows:
        by[klass(n)].append((n, fn(rec)))
    for c in range(len(LABELS)):
        xs = by.get(c, [])
        if not xs:
            continue
        s = sum(v for _, v in xs) / sum(n for n, _ in xs)
        med = float(np.median([v / n for n, v in xs]))
        lines.append(f"  {LABELS[c]:<16} | {len(xs):>3} | {s:>8,.0f} | {med:>8,.0f}" + ("  (under 5, do not read the median)" if len(xs) < 5 else ""))
    s = sum(fn(r) for _, _, r in rows) / sum(n for _, n, _ in rows)
    lines.append(f"  {'all':<16} | {len(rows):>3} | {s:>8,.0f} |")
    return lines


def slope(xs: np.ndarray, ys: np.ndarray, rng) -> tuple:
    X = np.column_stack([np.ones_like(xs), xs])
    b = np.linalg.lstsq(X, ys, rcond=None)[0][1]
    bs = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(xs), len(xs))
        bs.append(np.linalg.lstsq(X[i], ys[i], rcond=None)[0][1])
    return b, np.percentile(bs, 2.5), np.percentile(bs, 97.5)


def main() -> None:
    d, names = state_accounts()
    p20, p24 = pop(2020), pop(2024)
    lines = []
    tot = {y: sum(d[(g, y)]["3211"] + d[(g, y)]["3212"] for g in names) / 1e6 for y in range(2020, 2025)}
    lines.append("state total MVAG 3211+3212, EUR m: " + ", ".join(f"{y} {v:.1f}" for y, v in tot.items()))
    lines.append(f"municipalities in the state OGD: {len(names)}\n")

    r24 = [(g, p24[g], d[(g, 2024)]) for g in sorted(names)]
    r20 = [(g, p20[g], d[(g, 2020)]) for g in sorted(names)]
    lines += table(r24, lambda r: r["321"], "1. personnel cost total (MVAG 321) per inhabitant 2024, population 1.1.2024")
    share = collections.defaultdict(lambda: [0.0, 0.0])
    for _g, n, r in r24:
        share[klass(n)][0] += r["321"]
        share[klass(n)][1] += r["32"]
    lines.append("  share of operating payments (MVAG 32): " + ", ".join(f"{LABELS[c]} {a / b:.1%}" for c, (a, b) in sorted(share.items())))
    lines.append("")
    lines += table(r20, lambda r: r["321"], "2. personnel cost total (MVAG 321) per inhabitant 2020, population 1.1.2020")
    a20, a24 = collections.defaultdict(lambda: [0.0, 0]), collections.defaultdict(lambda: [0.0, 0])
    for g in names:
        c = klass(p24[g])  # class of 2024 for both years, so the groups stay the same
        a20[c][0] += d[(g, 2020)]["321"]
        a20[c][1] += p20[g]
        a24[c][0] += d[(g, 2024)]["321"]
        a24[c][1] += p24[g]
    lines.append("  change 2020 to 2024 per inhabitant, classes by 2024: " + ", ".join(f"{LABELS[c]} {(a24[c][0] / a24[c][1]) / (a20[c][0] / a20[c][1]) - 1:+.1%}" for c in sorted(a24)))
    lines.append("")

    o = ohh(2024)
    bad = []
    for g, v in o.items():
        ref = d[(g, 2024)]["3211"] + d[(g, 2024)]["3212"]
        if abs(v["sum5"] - ref) > 1:
            bad.append(f"{g} {names[g]} file {v['sum5']:,.2f} state {ref:,.2f}")
    miss = sorted(set(names) - set(o))
    lines.append(f"4. consistency of offenerhaushalt 2024: {len(o)} files, deviation of accounts 5xx from MVAG 3211+3212 above 1 EUR: {len(bad)}")
    lines += [f"  {b}" for b in bad]
    lines.append("  missing: " + "; ".join(f"{g} {names[g]} ({p24[g]:,} inhabitants)" for g in miss))
    cov = [(g, p24[g], d[(g, 2024)]) for g in sorted(o)]
    lines += table(cov, lambda r: r["321"], "  personnel cost total per inhabitant 2024, only municipalities with a file (to compare with 1.)")
    lines.append("")

    ro = [(g, p24[g], o[g]) for g in sorted(o)]
    lines.append("3. personnel cost (accounts 5xx) per budget group per inhabitant 2024, municipalities with a file")
    for k in range(10):
        lines += table(ro, lambda r, k=k: r[f"g{k}"], f" group {k}")
    lines += table(ro, lambda r: r["core"], " core administration (sub-sections 000 to 034 and 091), accounts 5xx")
    lines += table(ro, lambda r: r["k721"], " account 721 pay of elected bodies, all sub-sections")
    lines += table(ro, lambda r: r["core"] + r["core721"], " core administration with account 721")
    lines.append("")

    rng = np.random.default_rng(SEED)
    x = np.log([n for _, n, _ in r24])
    y = np.log([r["321"] / n for _, n, r in r24])
    b, lo, hi = slope(x, y, rng)
    lines.append(f"5. slope of log personnel cost total per inhabitant on log population, 2024 (n {len(r24)}): {b:+.3f}  95 % [{lo:+.3f}, {hi:+.3f}]")
    keep = [(n, r["core"] + r["core721"]) for _, n, r in ro if r["core"] + r["core721"] > 0]
    x = np.log([n for n, _ in keep])
    y = np.log([v / n for n, v in keep])
    b, lo, hi = slope(x, y, rng)
    lines.append(f"   slope core administration with account 721 (n {len(keep)}, dropped {len(ro) - len(keep)}): {b:+.3f}  95 % [{lo:+.3f}, {hi:+.3f}]")

    text = "\n".join(lines)
    print(text)
    (OUT / "personnel.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
