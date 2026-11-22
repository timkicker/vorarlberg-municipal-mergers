"""How many municipalities each cut draws into a merger, against the ten-municipality hurdle of Art. 35 LV.

Run from the repository root.
Writes data/derived/referendum_hurdle.txt.
"""

import collections
import csv
import sys

import fag


def main() -> None:
    pop = fag.load_pop()
    code = {r["municipality"]: r["gkz"] for r in csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8"))}
    cuts = collections.defaultdict(list)
    for r in csv.DictReader(open(fag.DER / "fag_units.csv", encoding="utf-8")):
        cuts[r["partition"]].append(r["members"].split(";"))
    lines = ["Municipalities in mergers per partition (referendum_hurdle.py)", ""]
    lines.append("partition | units with more than one member | municipalities in them | inhabitants in them | municipalities that lose the seat | most municipalities losing the seat in one unit")
    for cut, units in cuts.items():
        multi = [u for u in units if len(u) > 1]
        members = [g for u in multi for g in u]
        lose = [len(u) - 1 for u in multi]
        inh = sum(pop[code[g]] for g in members)
        lines.append(f"  {cut} | {len(multi)} | {len(members)} | {inh:,} | {sum(lose)} | {max(lose, default=0)}")
    text = "\n".join(lines)
    print(text)
    (fag.DER / "referendum_hurdle.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
