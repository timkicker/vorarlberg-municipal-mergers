"""Members that the Swiss rejection pattern (Strebel 2019) marks as the likeliest to block a merger.

Run from the repository root.
Writes data/derived/veto_pattern.txt.
"""

import collections
import csv
import sys

import fag

LARGE = 2230  # 90th percentile of population of the Swiss municipalities in Strebel (2019)
SHARE = 0.5


def main() -> None:
    pop = fag.load_pop()
    code = {r["municipality"]: r["gkz"] for r in csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8"))}
    cuts = collections.defaultdict(list)
    for r in csv.DictReader(open(fag.DER / "fag_units.csv", encoding="utf-8")):
        cuts[r["partition"]].append(r["members"].split(";"))
    lines = ["Members under the rejection pattern of Strebel 2019 (veto_pattern.py)", "",
             f"large: at least {LARGE:,} inhabitants, share of the unit under {SHARE:.0%}", "",
             "partition | units with merger | of which with such a member | share | such members | their inhabitants | members under 2.230 | largest"]
    for cut, units in cuts.items():
        multi = [u for u in units if len(u) > 1]
        hits, small, touched = [], 0, 0
        for u in multi:
            tot = sum(pop[code[g]] for g in u)
            h = [(pop[code[g]], g, pop[code[g]] / tot) for g in u if pop[code[g]] >= LARGE and pop[code[g]] / tot < SHARE]
            small += sum(pop[code[g]] < LARGE for g in u)
            touched += bool(h)
            hits += h
        top = ", ".join(f"{g} {p:,} ({s:.0%})" for p, g, s in sorted(hits, reverse=True)[:3])
        share = touched / len(multi) if multi else 0.0
        lines.append(f"  {cut} | {len(multi)} | {touched} | {share:.0%} | {len(hits)} | {sum(p for p, _, _ in hits):,} | {small} | {top}")
    lines.append("")
    lines.append(f"Vorarlberg municipalities with at least {LARGE:,} inhabitants: {sum(p >= LARGE for p in (pop[c] for c in code.values()))} of {len(code)}")
    text = "\n".join(lines)
    print(text)
    (fag.DER / "veto_pattern.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
