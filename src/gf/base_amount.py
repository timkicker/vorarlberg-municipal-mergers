"""Upper bound for the base amount per inhabitant of the Vorarlberg strengthening funds.

Writes data/derived/base_amount.txt.
"""

import collections
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import grant_clawback as gc  # noqa: E402
import personnel  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
RATE = 0.75  # share of the gap paid, guideline on strengthening funds § 4 no. 9
STATE_TOTAL_2024 = 29_849_676  # state total 2024, statement of accounts 2024 (state parliament enclosure 79/2025, p. 108)
NO_GRANT_2022 = ("Bürs", "Götzis", "Höchst", "Lustenau", "Wolfurt")
HOSPITAL_2022 = RAW / "hospital_contributions_2022_29_01_160.csv"
# columns of the closing account files of offenerhaushalt.at
COL_MVAG = "Mvag"  # MVAG code
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_ACCOUNT = "Konto-Grp"  # account group
COL_ACCOUNT_TEXT = "Konto-Text"  # account label
COL_VALUE = "Wert"  # amount
CASINO = "spielbank"  # word in the account label of casino levies
# columns of vbg_population_fag.csv of data.vorarlberg.gv.at
COL_POPULATION = "bevoelkerung"  # FAG population
COL_YEAR = "berichtsjahr"  # reference year
# columns of hospital_contributions_2022_29_01_160.csv (answer to state parliament question 29.01.160)
COL_HOSPITAL_MUNICIPALITY = "gemeinde"  # municipality name
COL_HOSPITAL_2022 = "ra2022"  # hospital contribution, closing accounts 2022


def finance(year: int) -> tuple[dict, dict]:
    """gkz -> financial strength (§ 6) from the accounts of `year`; gkz -> hospital contributions."""
    fs, hospital = {}, {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        g = path.name.split("_")[1]
        v = sp = 0.0
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r[COL_MVAG][:2] not in ("31", "32"):
                    continue
                sub, k, w = r[COL_SUBSECTION], r[COL_ACCOUNT], personnel.num(r[COL_VALUE])
                if sub == "920" and k in ("830", "831", "833"):
                    v += w
                elif CASINO in r[COL_ACCOUNT_TEXT].lower():
                    v += w
                elif (sub, k) in (("925", "859"), ("941", "860"), ("411", "861"), ("560", "861")):
                    v += w
                elif (sub, k) in (("930", "751"), ("411", "751")):
                    v -= w
                elif (sub, k) == ("560", "751"):
                    v -= w
                    sp += w
        fs[g], hospital[g] = v, sp
    return fs, hospital


def fag_pop(year: int) -> dict:
    with open(RAW / "vbg_population_fag.csv", encoding="utf-8-sig") as f:
        return {r["gkz"]: float(r[COL_POPULATION]) for r in csv.DictReader(f, delimiter=";")
                if int(r[COL_YEAR]) == year}


def structural_files(year: int) -> dict:
    s = {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        with open(path, encoding="utf-8-sig") as f:
            s[path.name.split("_")[1]] = sum(personnel.num(r[COL_VALUE]) for r in csv.DictReader(f, delimiter=";")
                                             if r[COL_SUBSECTION] == "940" and r[COL_ACCOUNT] == "861")
    return s


def bound(rows: list, slack: int) -> tuple[float, list]:
    """Largest A with at most `slack` violations of S >= 0.75 * max(0, A*E - F)."""
    # each municipality allows A <= (F + S / 0.75) / E
    caps = sorted(((f + s / RATE) / e, g) for g, s, f, e in rows)
    return caps[slack][0], caps[: slack + 3]


def rest(a: float, f: float, e: float) -> float:
    return RATE * max(0.0, a * e - f)


def main() -> None:
    names = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(DER / "pareto_partitions.csv"))}
    by_name = {v: k for k, v in names.items()}
    s24 = structural_files(2024)
    fs22, sp22 = finance(2022)
    e24 = fag_pop(2024)
    lines = ["Base amount of the strengthening funds, upper bound (base_amount.py)", ""]

    # control: hospital contributions 2022 against question 29.01.160, question 18
    ctrl = {}
    with open(HOSPITAL_2022, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            ctrl[r[COL_HOSPITAL_MUNICIPALITY]] = float(r[COL_HOSPITAL_2022])
    dev = []
    for g, v in sp22.items():
        c = ctrl.get(gc.ANSWER_NAMES.get(names[g], names[g])) or ctrl.get(names[g])
        if c is None:
            dev.append((names[g], None))
        elif abs(v - c) > 0.05 * c:
            dev.append((names[g], (v - c) / c))
    lines.append(f"Control: hospital contributions 2022 against question 29.01.160: {len(sp22)} municipalities with a file, "
                 f"more than 5 % off or without comparison {len(dev)}: "
                 + ", ".join(f"{n} ({d:+.0%})" if d is not None else f"{n} (no comparison)" for n, d in sorted(dev, key=str)))
    lines.append("")

    rows = [(g, s24[g], fs22[g], e24[g]) for g in s24 if g in fs22 and g in e24]
    lines.append(f"municipalities with grants 2024, fiscal strength 2022 and population 31.10.2022: {len(rows)}")
    fsq = sorted(f / e for _g, _s, f, e in rows)
    lines.append(f"fiscal strength per inhabitant 2022 (rebuilt): median {fsq[len(fsq) // 2]:,.0f}, minimum {fsq[0]:,.0f}, maximum {fsq[-1]:,.0f} euro")
    a0, top0 = bound(rows, 0)
    a2, top2 = bound(rows, 2)
    lines.append(f"A_max without buffer {a0:,.0f} euro per inhabitant, with a buffer of two {a2:,.0f} euro per inhabitant")
    lines.append("  binding municipalities (bound per municipality, grants 2024, fiscal strength per inhabitant):")
    for cap, g in top2:
        _, s, f, e = next(r for r in rows if r[0] == g)
        lines.append(f"    {names[g]}: {cap:,.0f}; {s:,.0f} euro; {f / e:,.0f}")
    lines.append("")

    # cross-check 2022 with the five municipalities without any structural grant
    fs20, _ = finance(2020)
    e22 = fag_pop(2022)
    lines.append("Cross-check 2022 (fiscal strength 2020, population 31.10.2020), municipalities without grants according to the state:")
    for n in NO_GRANT_2022:
        g = by_name[n]
        if g in fs20 and g in e22:
            lines.append(f"  {n}: fiscal strength per inhabitant {fs20[g] / e22[g]:,.0f}, so A_2022 at most this much")
        else:
            lines.append(f"  {n}: no file 2020")
    lines.append("")

    for a in (a2, 0.9 * a2):
        below = [r for r in rows if r[3] * a > r[2]]
        tot = sum(rest(a, f, e) for _g, _s, f, e in rows)
        lines.append(f"At A = {a:,.0f}: below need {len(below)} of {len(rows)}, residual item of these municipalities "
                     f"{tot / 1e6:.2f} m euro = {tot / STATE_TOTAL_2024:.0%} of the state total 2024; "
                     f"their grants 2024 {sum(r[1] for r in rows) / 1e6:.2f} m")
    lines.append("")

    units = collections.defaultdict(list)
    for r in csv.DictReader(open(DER / "fag_units.csv")):
        units[r["partition"]].append(r)
    lines.append("Claw-back through the residual item per partition, only units of at least two municipalities with all data")
    lines.append("Partition | units with data / all | FAG gain of these units | loss at A_max | share | loss at 0.9 A_max | share")
    for cut, rs in units.items():
        n_all = n = 0
        G = L1 = L2 = 0.0
        for r in rs:
            if int(r["municipalities"]) < 2:
                continue
            n_all += 1
            gs = [by_name[m] for m in r["members"].split(";")]
            if not all(g in fs22 and g in e24 for g in gs):
                continue
            n += 1
            gain = float(r["after_with_inflow_eur"]) - float(r["before_eur"])
            F = sum(fs22[g] for g in gs)
            E = sum(e24[g] for g in gs)
            G += gain
            for a, acc in ((a2, 1), (0.9 * a2, 2)):
                loss = sum(rest(a, fs22[g], e24[g]) for g in gs) - rest(a, F + gain, E)
                if acc == 1:
                    L1 += loss
                else:
                    L2 += loss
        sh1 = f"{L1 / G:.0%}" if G > 0 else "n. a."
        sh2 = f"{L2 / G:.0%}" if G > 0 else "n. a."
        lines.append(f"{cut} | {n} / {n_all} | {G / 1e6:+.2f} | {L1 / 1e6:.2f} | {sh1} | {L2 / 1e6:.2f} | {sh2}")
    text = "\n".join(lines)
    print(text)
    (DER / "base_amount.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
