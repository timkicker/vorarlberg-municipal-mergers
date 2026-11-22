"""CSV for the money figure: who gains per partition, from data/derived/balance_2024_low.txt only (merged units with inflow).

For regions and districts the merged units come from the second table (freed base amounts shared by
population), as in the balance table of the paper, footnote a.
"""

import csv
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import elections  # noqa: E402

OUT = elections.OUT
ROWS = (("Threshold 2000", "Threshold 2,000"), ("Threshold 3500", "Threshold 3,500"), ("Threshold 5000", "Threshold 5,000"),
        ("Planning regions", "Planning regions"), ("Regions", "Regions"), ("Districts", "Districts"))
COLS = {"austria": 5, "vbg": 1, "merged": 3}  # column index in the table of balance_2024_low.txt


def span(cell: str) -> tuple[float, float]:
    v = [float(x) for x in re.findall(r"[+-]?\d+\.\d+", cell)]
    return min(v), max(v)


def main() -> None:
    table, by_pop = {}, {}
    for line in (OUT / "balance_2024_low.txt").read_text().splitlines():
        cells = [c.strip() for c in line.split("|")]
        if cells[0] in dict(ROWS):
            (by_pop if cells[0] in table else table)[cells[0]] = cells
    for key in ("Regions", "Districts"):
        table[key][COLS["merged"]] = by_pop[key][2]
    out = OUT / "figures" / "money.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["y"] + [f"{k}_{e}" for k in COLS for e in ("lo", "hi", "mid")])
        for i, (key, _label) in enumerate(ROWS):
            row = [len(ROWS) - 1 - i]  # no label column: "2,000" would split under col sep=comma
            for col in COLS.values():
                lo, hi = span(table[key][col])
                row += [lo, hi, round((lo + hi) / 2, 2)]
            w.writerow(row)
    print(out.read_text())


if __name__ == "__main__":
    sys.exit(main())
