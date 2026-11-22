"""Vorarlberg by size class: municipalities, inhabitants, net core administration per inhabitant.

Writes data/derived/overview.txt.
"""

import csv
import pathlib
import statistics

DER = pathlib.Path(__file__).resolve().parents[2] / "data" / "derived"
CLASSES = [(0, 1000, "under 1,000"), (1000, 2000, "1,000 to 1,999"), (2000, 3500, "2,000 to 3,499"),
           (3500, 10000, "3,500 to 9,999"), (10000, 1e9, "from 10,000")]


def main() -> None:
    rows = [r for r in csv.DictReader(open(DER / "administration_2016_2019.csv")) if r["state"] == "8"]
    total = sum(float(r["population"]) for r in rows)
    out = ["Vorarlberg by size, mean 2016 to 2019 (overview.py)", f"municipalities {len(rows)}, population {total:,.0f}", "",
           "Class | municipalities | share of population | core administration net per inhabitant (total) | median per municipality | without complete data"]
    for lo, hi, name in CLASSES:
        c = [r for r in rows if lo <= float(r["population"]) < hi]
        ok = [r for r in c if r["complete"] == "True"]
        inh = sum(float(r["population"]) for r in c)
        per = sum(float(r["net"]) for r in ok) / sum(float(r["population"]) for r in ok)
        med = statistics.median(float(r["net"]) / float(r["population"]) for r in ok)
        out.append(f"{name} | {len(c)} | {inh / total:.1%} | {per:.0f} | {med:.0f} | {len(c) - len(ok)}")
    ok = [r for r in rows if r["complete"] == "True"]
    out.append(f"all | {len(rows)} | 100% | {sum(float(r['net']) for r in ok) / sum(float(r['population']) for r in ok):.0f} | "
               f"{statistics.median(float(r['net']) / float(r['population']) for r in ok):.0f} | {len(rows) - len(ok)}")
    text = "\n".join(out)
    print(text)
    (DER / "overview.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
