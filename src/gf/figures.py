"""Small CSV files for the figures of the paper, only from derived results."""

import csv
import pathlib
import re
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import elections  # noqa: E402
import styria_elections  # noqa: E402

OUT = elections.OUT
FIG = OUT / "figures"
CLASSES = (0, 750, 1500, 3000, 7500, np.inf)  # size classes


def write(name: str, header: list, rows: list) -> None:
    with (FIG / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    FIG.mkdir(exist_ok=True)

    # 1 cost curve and the Vorarlberg municipalities as a rug
    adm = [r for r in csv.DictReader((OUT / "administration_2016_2019.csv").open(encoding="utf-8")) if r["gkz"].startswith("8") and r["population"]]
    write("vbg_population.csv", ["population"], [[r["population"]] for r in adm])

    # 2 contested elections by size class, 2020 and 2025
    rows = []
    for year in (2020, 2025):
        d = elections.load(year)
        for i, (lo, hi) in enumerate(zip(CLASSES, CLASSES[1:])):
            m = [r["A"] for r in d if lo <= r["w"] < hi]
            rows.append([year, i, f"{lo:,.0f}".replace(",", "."), len(m), sum(m), f"{sum(m) / len(m):.3f}"])
    for year in ("2020", "2025"):
        write(f"competition_{year}.csv", ["class", "share", "lbl"], [[r[1], r[5], f"{r[4]}/{r[3]}"] for r in rows if str(r[0]) == year])

    # 3 lists on the ballot in Styria, merged against unchanged
    full = (OUT / "styria_elections.txt").read_text()

    def means(block: str) -> dict:
        out = {}
        for line in block.splitlines():
            for grp in ("merged", "unchanged"):
                if line.strip().startswith(f"Mean {grp}:"):
                    parts = line.split(":", 1)[1].split()
                    out[grp] = {int(parts[i].rstrip(":")): float(parts[i + 1]) for i in range(0, len(parts), 2)}
        return out

    vals = means(full.split("\nBefore as union")[0].split("\nL, lists")[1])
    union = means(full.split("\nU, lists")[1].split("\nM, lists")[0])["merged"]
    pre = [y for y in styria_elections.YEARS if y < 2015]
    write("styria_lists.csv", ["year", "merged", "unchanged"], [[y, vals["merged"][y], vals["unchanged"][y]] for y in styria_elections.YEARS])
    write("styria_union.csv", ["year", "merged"], [[y, union[y]] for y in pre + [min(y for y in styria_elections.YEARS if y >= 2015)]])

    # 3b event study of administrative costs, reference year 2013, 2014 left out.
    # Styrian controls from the cleaned panel (styria_checks.py, run 2), the other states
    # from styria.txt (no Styrian controls there, so the cleaning does not apply).
    st = (OUT / "styria.txt").read_text()
    gp = (OUT / "styria_checks.txt").read_text()
    ev = {}
    for key, text, head in (("sty", gp, "2 net without 2014 "), ("other", st, "Control other states only without 2014 ")):
        block = text.split(head)[1]
        line = next(x for x in block.splitlines() if "Event study" in x)
        ev[key] = {int(y): (float(a), float(b), float(c)) for y, a, b, c in re.findall(r"(\d{4}): ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]", line)}
    years = sorted(set(ev["sty"]) | {2013})
    rows = []
    for y in years:
        r = [y]
        for key, shift in (("sty", -0.15), ("other", 0.15)):
            a, b, c = ev[key].get(y, (0.0, 0.0, 0.0))
            r += [y + shift, a, b, c]
        rows.append(r)
    write("event_costs.csv", ["year", "x_sty", "sty", "sty_lo", "sty_hi", "x_other", "other", "other_lo", "other_hi"], rows)


if __name__ == "__main__":
    sys.exit(main())
