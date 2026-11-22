"""One-off merger grant of the state (cooperation guideline § 4(7), at least 100,000 EUR per
participating municipality) per cut, against the one-off costs of balance_2024.txt.

Run from the repository root. Writes data/derived/merger_grant.txt.
"""

import collections
import csv
import re
import sys

import balance as bl
import fag

GRANT = 0.1  # m EUR per participating municipality, lower bound


def main() -> None:
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    b24 = {p[0]: p for p in (l.split(" | ") for l in (fag.DER / "balance_2024.txt").read_text().splitlines()) if len(p) > 7}
    out = ["Merger grant of the state per partition, lower bound 0.1 m EUR per participating municipality (merger_grant.py)", "",
           "Partition | municipalities in merged units | grant m | one-off costs m (balance_2024) | grant / lower costs | grant / upper costs"]
    for cut, name in bl.NAMES.items():
        units = collections.Counter(r[cut] for r in rows)
        n = sum(c for c in units.values() if c > 1)
        lo, hi = (float(x) for x in re.findall(r"[\d.]+", b24[name][7]))
        g = n * GRANT
        out.append(f"{name} | {n} | {g:.1f} | {lo:.1f} to {hi:.1f} | {g / lo:.0%} | {g / hi:.0%}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "merger_grant.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
