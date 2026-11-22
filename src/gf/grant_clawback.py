"""Upper bound for the claw-back of FAG gains through the residual item of the Vorarlberg strengthening funds.

Writes data/derived/residual_items.txt.
"""

import collections
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fag  # noqa: E402
import personnel  # noqa: E402
import state_grants  # noqa: E402

RAW, DER = personnel.RAW, personnel.OUT
RATE = 0.75  # share of the gap paid, guideline on strengthening funds § 4 no. 9
# names in the table of question 29.01.017 that differ from the names in pareto_partitions.csv
ANSWER_NAMES = {"St. Anton i.M.": "St. Anton im Montafon"}
# columns of the closing account files of offenerhaushalt.at
COL_SUBSECTION = "Ansatz-Uab"  # budget sub-section
COL_ACCOUNT = "Konto-Grp"  # account group
COL_VALUE = "Wert"  # amount
COL_ANSWER_MUNICIPALITY = "Gemeinde"  # municipality name column in grants_by_municipality_29_01_017.csv


def structural(year: int = 2024) -> tuple[dict, set, dict]:
    """gkz -> strengthening funds in EUR (sub-section 940, account 861); set of gkz taken from the table of question 29.01.017 instead."""
    names = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(DER / "pareto_partitions.csv"))}
    s = {}
    for path in sorted((RAW / "offenerhaushalt").glob(f"offenerhaushalt_*_{year}_ra_fhh_gemeinde.csv")):
        g = path.name.split("_")[1]
        with open(path, encoding="utf-8-sig") as f:
            s[g] = sum(personnel.num(r[COL_VALUE]) for r in csv.DictReader(f, delimiter=";")
                       if r[COL_SUBSECTION] == "940" and r[COL_ACCOUNT] == "861")
    by_name = {v: k for k, v in names.items()}
    from_answer = set()
    with open(RAW / "grants_by_municipality_29_01_017.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            g = by_name.get(ANSWER_NAMES.get(r[COL_ANSWER_MUNICIPALITY], r[COL_ANSWER_MUNICIPALITY]))
            if g and g not in s:
                s[g] = float(r[f"BZ_FAG_{year}"])
                from_answer.add(g)
    assert len(s) == 96, len(s)
    return s, from_answer, names


def base_amount_lines() -> dict:
    """Change of the base amount per cut from state_grants.txt, m EUR."""
    out = {}
    for line in (DER / "state_grants.txt").read_text().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) > 3 and parts[0] in ("Threshold 2000", "Threshold 3500", "Threshold 5000",
                                            "official planning region", "official region", "official district"):
            out[parts[0]] = parts[3]  # change of the base amount for the merged units
    return out


def main() -> None:
    s, from_answer, names = structural()
    by_name = {v: k for k, v in names.items()}
    lines = [f"Strengthening funds 2024: {len(s) - len(from_answer)} municipalities from sub-section 940/account 861, "
             f"{len(from_answer)} from the table of question 29.01.017 (all state grants, too high): " + ", ".join(sorted(names[g] for g in from_answer)),
             f"sum of the 88 from offenerhaushalt {sum(v for g, v in s.items() if g not in from_answer) / 1e6:.2f} m, "
             f"state total according to the annual accounts report of the state 29.85 m", ""]
    steps = base_amount_lines()
    pop = fag.load_pop()
    lines.append("Partition | FAG gain merged | strengthening funds of the predecessors | upper bound claw-back | share of the gain | grants beside the base amount | upper bound beside the base amount | share | change of the base amount (state_grants.txt)")
    units = collections.defaultdict(list)
    for r in csv.DictReader(open(DER / "fag_units.csv")):
        units[r["partition"]].append(r)
    for cut, rows in units.items():
        G = S = B = R = B_rest = 0.0
        for r in rows:
            if int(r["municipalities"]) < 2:
                continue
            gain = float(r["after_with_inflow_eur"]) - float(r["before_eur"])
            if gain <= 0:
                continue
            members = r["members"].split(";")
            st = sum(s[by_name[m]] for m in members)
            G += gain
            S += st
            B += min(RATE * gain, st)
            rest = max(0.0, st - sum(state_grants.base_amount(pop[by_name[m]]) for m in members))
            R += rest
            B_rest += min(RATE * gain, rest)
        share = f"{B / G:.0%}" if G else "n. a."
        share2 = f"{B_rest / G:.0%}" if G else "n. a."
        lines.append(f"{cut} | {G / 1e6:+.1f} | {S / 1e6:.1f} | {B / 1e6:.1f} | {share} | {R / 1e6:.1f} | {B_rest / 1e6:.1f} | {share2} | {steps.get(cut, '?')}")
    text = "\n".join(lines)
    print(text)
    (DER / "residual_items.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
