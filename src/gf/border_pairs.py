"""Pairs of neighbours that cross 10,000 inhabitants only by merging: what the FAG 2024 pays them.

Run from the repository root. Writes data/derived/border_pairs.txt.
"""

import csv
import statistics
import sys

import fag

LIMIT = 10000


def main() -> None:
    pop = fag.load_pop()
    stays = fag.load_stays(2023)
    vbg = sorted(g for g in pop if g.startswith("8"))
    name = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(fag.DER / "pareto_partitions.csv"))}
    abs_at, abs_v = fag.austria_abs(pop)
    pool = fag.ADVANCE_AT - fag.TRANSFER_TAX_MUNICIPALITIES
    pot = fag.ADVANCE_VBG * (1 - fag.STATE_GRANT_SHARE) * 1e6
    base = fag.distribute({g: [g] for g in vbg}, pop, stays, pot)

    pairs = []
    for r in csv.DictReader(open(fag.DER / "neighbours.csv", encoding="utf-8")):
        a, b = r["gkz_a"], r["gkz_b"]
        if r["neighbour"] == "1" and pop[a] <= LIMIT and pop[b] <= LIMIT and pop[a] + pop[b] > LIMIT:
            pairs.append(tuple(sorted((a, b))))
    pairs = sorted(set(pairs))

    lines = ["Mergers that only just cross the 10,000 limit (border_pairs.py)", ""]
    lines.append("pair | population | gain total EUR | per inhabitant | of this from outside, kept by the pair, per inhabitant | in % of tax shares | loss of the other municipalities EUR")
    rows = []
    for a, b in pairs:
        units = {g: [g] for g in vbg if g not in (a, b)}
        units["P"] = [a, b]
        abs_v1 = sum(fag.abs_factor(sum(pop[g] for g in m)) for m in units.values())
        inflow = pool * fag.SHARE_GRADED * (abs_v1 / (abs_at - abs_v + abs_v1) - abs_v / abs_at) * (1 - fag.STATE_GRANT_SHARE) * 1e6
        new = fag.distribute(units, pop, stays, pot + inflow)
        before = base[a]["total"] + base[b]["total"]
        gain = new["P"]["total"] - before
        n = pop[a] + pop[b]
        others = sum(new[g]["total"] - base[g]["total"] for g in units if g != "P")
        own_in = inflow * new["P"]["abs"] / (new["P"]["abs"] + sum(new[g]["abs"] for g in units if g != "P"))
        rows.append((gain / before, gain / n))
        lines.append(f"  {name[a]} + {name[b]} | {n:,} | {gain:+,.0f} | {gain / n:+.0f} | {own_in / n:+.1f} | {gain / before:+.1%} | {others:+,.0f}")
    lines.append("")
    if rows:
        lines.append(f"median gain in % of tax shares {statistics.median(r[0] for r in rows):+.1%}, per inhabitant {statistics.median(r[1] for r in rows):+.0f} EUR, pairs {len(rows)}")
    lines.append("")
    lines.append("municipalities today between 8,000 and 10,000 inhabitants")
    for g in sorted((g for g in vbg if 8000 <= pop[g] <= LIMIT), key=lambda g: -pop[g]):
        lines.append(f"  {name[g]} | {pop[g]:,} | missing {LIMIT + 1 - pop[g]:,}")
    cand = {r["name"]: r for r in csv.DictReader(open(fag.DER / "pareto_candidates.csv"))}
    e = float(cand["Threshold 5000"]["E_main"])
    lines.append("")
    lines.append(f"administrative saving Threshold 5000: {e:,.0f} EUR a year, per inhabitant of Vorarlberg {e / sum(pop[g] for g in vbg):.1f}")
    text = "\n".join(lines)
    print(text)
    (fag.DER / "border_pairs.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
