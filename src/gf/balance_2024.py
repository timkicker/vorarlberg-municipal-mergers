"""Money balance per set of merged units with the 2024 savings (E24) and from the point of view of Austria.

Puts together savings_2024.txt, fag.txt and
state_grants.txt; nothing is estimated here. Writes data/derived/balance_2024.txt.
"""

import csv
import re
import sys

import balance as bl
import fag

LOW = "--low" in sys.argv  # lower variant of the elected bodies


def e24() -> dict:
    src, col = ("savings_2024_low.txt", 4) if LOW else ("savings_2024.txt", 5)
    out = {}
    for line in (fag.DER / src).read_text().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if parts[0] in bl.NAMES:
            lo, hi = (float(x) for x in re.findall(r"-?[\d.]+", parts[col]))
            out[parts[0]] = (lo, hi)
    return out


def main() -> None:
    e, f, lr, pop = e24(), bl.table("fag.txt"), bl.table("state_grants.txt"), bl.merged_pop()
    out = ["Money balance per partition with E24, m EUR per year (balance_2024.py)",
           "Ranges: E24 lower to upper bound" + (" (lower variant of the elected bodies)" if LOW else "") + "; state guidelines both ends", "",
           "Partition | Vorarlberg total | merged units | same with inflow | unchanged municipalities | "
           "Austria | municipalities of the other states | one-off m | years to break even, view of Austria | Vorarlberg / Austria"]
    total = sum(float(r[bl.COL_POPULATION]) for r in csv.DictReader((bl.RAW / "vbg_population_fag.csv").open(encoding="utf-8"),
                                                                delimiter=";") if r[bl.COL_YEAR] == "2024")
    old = ["", "Variant: the state grants the merged units lose shared by population instead of going entirely to the unchanged municipalities",
           "Partition | share of population merged | merged units with inflow | unchanged municipalities"]
    for cut, name in bl.NAMES.items():
        elo, ehi = e[cut]
        inflow = float(f[cut][3])
        win, lose, same_in, same_out = float(f[cut][7]), float(f[cut][8]), float(f[cut][11]), float(f[cut][9])
        lo, hi = (float(x) for x in re.findall(r"-?[\d.]+", lr[cut][7]))
        to_merged = inflow - (same_in - same_out)
        whole = bl.span(elo + inflow, ehi + inflow)
        mrg = bl.span(win + lose + elo + lo, win + lose + ehi + hi)
        mrg_in = bl.span(win + lose + to_merged + elo + lo, win + lose + to_merged + ehi + hi)
        p = pop[cut]
        once = (p * bl.CORE_NET / 1e6, p * bl.EXTRA_HI / 1e6)
        years = f"{once[0] / ehi:.1f} to {once[1] / elo:.0f}" if elo > 0 else "never"
        ratio = f"{(elo + inflow) / elo:.1f} to {(ehi + inflow) / ehi:.1f}"
        sh = p / total
        old.append(f"{name} | {sh:.0%} | {bl.span(win + lose + to_merged + elo + (1 - sh) * lo, win + lose + to_merged + ehi + (1 - sh) * hi)}"
                   f" | {bl.span(same_in - (1 - sh) * hi, same_in - (1 - sh) * lo)}")
        out.append(f"{name} | {whole} | {mrg} | {mrg_in} | {bl.span(same_in - hi, same_in - lo)} | {bl.span(elo, ehi)} | {-inflow:+.1f} | "
                   f"{once[0]:.1f} to {once[1]:.1f} | {years} | {ratio}")
    out += ["", "Austria: E24 only, the FAG inflow and the state grants are shifts between public budgets.",
            f"one-off: {bl.CORE_NET:.0f} to {bl.EXTRA_HI:.0f} EUR per inhabitant of the merged units (extraordinary balance, net). Years: low costs / upper savings to high costs / lower savings."]
    if LOW:
        out += old
    text = "\n".join(out)
    print(text)
    (fag.DER / ("balance_2024_low.txt" if LOW else "balance_2024.txt")).write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
