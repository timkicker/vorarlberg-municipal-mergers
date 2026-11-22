"""Second home levy: category of the merged municipality (ZWAbgG § 5).

Run from the repository root.
Writes data/derived/second_homes.txt.
"""

import collections
import csv
import html
import re
import sys
import zipfile

import fag

ODS = fag.DER.parent / "raw" / "zag_{}.ods"
CUTS = ("Threshold 2000", "Threshold 3500", "Threshold 5000", "official planning region", "official region", "official district")
CAP = {"A": 2775, "B": 2115, "C": 1230}  # annual maximum per dwelling, as of 2023
RANK = {"A": 2, "B": 1, "C": 0}


def cat(share: float) -> str:
    return "A" if share > 0.30 else "B" if share > 0.15 else "C"


def read(year: int) -> dict:
    x = zipfile.ZipFile(str(ODS).format(year)).read("content.xml").decode()
    out = {}
    for r in re.findall(r"<table:table-row[^>]*>(.*?)</table:table-row>", x, re.S):
        vals = [html.unescape(re.sub(r"<[^>]+>", "", c or "")).strip()
                for _, c in re.findall(r"<table:table-cell([^>]*)(?:/>|>(.*?)</table:table-cell>)", r, re.S)]
        if len(vals) >= 4 and vals[1] in RANK and vals[2].isdigit():
            out[vals[0]] = (vals[1], int(vals[2]), int(vals[3]))
    return out


def main() -> None:
    z = read(2027)
    old = read(2026)
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    name = {r["gkz"]: r["municipality"] for r in rows}
    miss = sorted(set(name.values()) - set(z))
    assert not miss, f"names missing from the list: {miss}"
    bad = [n for n, (k, a, b) in z.items() if cat(b / (a + b)) != k]
    out = ["Second home levy: category of the merged municipality (second_homes.py)",
           "Source: list of the state ZAG 2027 (reference date 31.12.2025), ZWAbgG LGBl. 59/2023 as amended by 27/2024, § 5(1)",
           f"municipalities in the list: {len(z)}; control of the thresholds against the category in the list, deviations: {len(bad)} {bad}",
           "categories 2027: " + ", ".join(f"{k} {sum(v[0] == k for v in z.values())}" for k in "ABC")
           + "; different from 2026: " + str(sorted(n for n in z if n in old and old[n][0] != z[n][0])),
           f"dwellings without a main residence in total: {sum(v[2] for v in z.values()):,}", "",
           "Partition | municipalities with a lower category | their dwellings without main residence | with a higher category | upper bound of the loss m euro (dwellings x difference of the annual maximum) | examples lower"]
    for cut in CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(name[r["gkz"]])
        down, up, loss = [], [], 0.0
        for u in units.values():
            a = sum(z[n][1] for n in u)
            b = sum(z[n][2] for n in u)
            k = cat(b / (a + b))
            for n in u:
                if RANK[k] < RANK[z[n][0]]:
                    down.append((n, z[n][0], k, z[n][2]))
                    loss += z[n][2] * (CAP[z[n][0]] - CAP[k])
                elif RANK[k] > RANK[z[n][0]]:
                    up.append(n)
        top = sorted(down, key=lambda t: -t[3])[:5]
        out.append(f"  {cut} | {len(down)} | {sum(t[3] for t in down):,} | {len(up)} | {loss / 1e6:.1f} | "
                   + ", ".join(f"{n} {a}→{k} ({w:,})" for n, a, k, w in top))
    text = "\n".join(out)
    print(text)
    (fag.DER / "second_homes.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
