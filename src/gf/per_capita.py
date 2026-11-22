"""Money figures per inhabitant, for readability.

Divides existing results only. Writes data/derived/per_capita.txt.
"""

import csv
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import balance as bl  # noqa: E402
import fag  # noqa: E402

# Columns of vbg_population_fag.csv (FAG population of the state of Vorarlberg, open data)
COL_POPULATION = "bevoelkerung"  # population
COL_YEAR = "berichtsjahr"  # reference year
NUM = r"[+-]?\d+(?:\.\d+)?"


def ends(cell: str) -> list[float]:
    return [float(x) for x in re.findall(NUM, cell)]


def per(cell: str, n: float) -> str:
    if n < 1:
        return "no municipality"
    v = [x * 1e6 / n for x in ends(cell)]
    return " to ".join(f"{x:+,.0f}" for x in v)


def rows(path: str, keys) -> dict:
    out = {}
    for line in (fag.DER / path).read_text().splitlines():
        parts = [x.strip() for x in line.split("|")]
        if parts[0] in keys and parts[0] not in out:  # first table of the file
            out[parts[0]] = parts
    return out


def variant_rows() -> dict:
    """Second table of balance_2024_low.txt: state grants the merged units lose shared by population."""
    text = (fag.DER / "balance_2024_low.txt").read_text().split("Variant:")[1]
    return {p[0]: p for p in ([x.strip() for x in line.split("|")] for line in text.splitlines()) if p[0] in bl.NAMES.values()}


def main() -> None:
    fp = {r["gkz"]: float(r[COL_POPULATION]) for r in
          csv.DictReader((bl.RAW / "vbg_population_fag.csv").open(encoding="utf-8"), delimiter=";")
          if r[COL_YEAR] == "2024"}
    assert len(fp) == 96, len(fp)
    vbg = sum(fp.values())
    mp = bl.merged_pop()
    b = rows("balance_2024_low.txt", bl.NAMES.values())  # lower variant of the elected bodies, as in the paper
    e = rows("savings_2024_low.txt", bl.NAMES)
    variant = variant_rows()
    for name in ("Regions", "Districts"):  # as in figure_money.py: grants the merged units lose shared by population
        v = variant[name]
        b[name] = b[name][:3] + [v[2], v[3]] + b[name][5:]
    assert len(b) == len(e) == len(bl.NAMES), (len(b), len(e))
    out = ["Money figures per inhabitant, EUR per year, FAG population 2024, lower variant of the elected bodies (per_capita.py)",
           f"Vorarlberg {vbg:,.0f} inhabitants",
           "Regions and districts: state grants the merged units lose shared by population", "",
           "Partition | population merged | E24 per merged inhabitant | merged units with inflow per merged inhabitant | "
           "unchanged municipalities per inhabitant there | Vorarlberg total per inhabitant of Vorarlberg | Austria per inhabitant of Vorarlberg | one-off per merged inhabitant (total)"]
    for cut, name in bl.NAMES.items():
        m = mp[cut]
        r, s = b[name], e[cut]
        out.append(f"{name} | {m:,.0f} ({m / vbg:.0%}) | {per(s[4], m)} | {per(r[3], m)} | {per(r[4], vbg - m)} | "
                   f"{per(r[1], vbg)} | {per(r[5], vbg)} | {per(r[7], m)}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "per_capita.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
