"""Resort classes of the Vorarlberg Tourism Act before and after a merger.

Writes data/derived/resort_class.txt.
"""

import collections
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import base_amount as ba  # noqa: E402
import tourism  # noqa: E402

DER = tourism.DER
RANK = {"A": 3, "B": 2, "C": 1}


def cls(nights: float, inh: float) -> str:
    r = nights / inh
    return "A" if r >= 100 else "B" if r >= 40 else "C"


def main() -> None:
    pop = ba.fag_pop(2024)
    name = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(DER / "pareto_partitions.csv"))}
    n = tourism.nights([2024])
    now = {g: cls(n.get(g, 0.0), pop[g]) for g in pop}
    cnt = collections.Counter(now.values())
    lines = ["Resort classes under § 9 of the Tourism Act, overnight stays 2024, FAG population 2024 (resort_class.py)",
             f"municipalities today: A {cnt['A']}, B {cnt['B']}, C {cnt['C']}; over 100,000 overnight stays: {sum(n.get(g, 0) > 100000 for g in pop)}", "",
             "Partition | units | predecessor falls (municipalities, population) | rises | same | from A to B/C (municipalities, population) | share of population with a change among former A/B | units > 100,000 overnight stays (municipalities in them today > 100,000)"]
    det = []
    for cut, us in tourism.units().items():
        down = up = same = 0
        inh_d = inh_u = inh_s = 0.0
        a_out = 0
        inh_a_out = 0.0
        ab_all = ab_ch = 0.0
        big = bigpre = 0
        for gs in us:
            inh = sum(pop[g] for g in gs)
            nn = sum(n.get(g, 0.0) for g in gs)
            c = cls(nn, inh)
            if nn > 100000:
                big += 1
                bigpre += sum(n.get(g, 0) > 100000 for g in gs)
            ch = []
            for g in gs:
                d = RANK[c] - RANK[now[g]]
                if now[g] in "AB":
                    ab_all += pop[g]
                    ab_ch += pop[g] * (d != 0)
                if d < 0:
                    down += 1
                    inh_d += pop[g]
                    ch.append(f"{name[g]} {now[g]}>{c}")
                elif d > 0:
                    up += 1
                    inh_u += pop[g]
                    ch.append(f"{name[g]} {now[g]}>{c}")
                else:
                    same += 1
                    inh_s += pop[g]
                if now[g] == "A" and c != "A":
                    a_out += 1
                    inh_a_out += pop[g]
            if ch:
                det.append(f"  {cut} | {nn / inh:.0f} per inhabitant | " + ", ".join(ch))
        share = ab_ch / ab_all if ab_all else float("nan")
        lines.append(f"{cut} | {len(us)} | {down}, {inh_d:,.0f} | {up}, {inh_u:,.0f} | {same}, {inh_s:,.0f} | {a_out}, {inh_a_out:,.0f} | {share:.0%} | {big} ({bigpre})")
    lines += ["", "Changes per unit (municipality, class before > after):"] + det
    text = "\n".join(lines)
    print(text)
    (DER / "resort_class.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
