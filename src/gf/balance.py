"""Money balance per set of merged units from three points of view.

Puts together pareto.txt, fag.txt and state_grants.txt;
nothing is estimated here. Writes data/derived/balance.txt.
"""

import collections
import csv
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fag  # noqa: E402

RAW = fag.DER.parent / "raw"
NAMES = {"Threshold 2000": "Threshold 2000", "Threshold 3500": "Threshold 3500", "Threshold 5000": "Threshold 5000",
         "official planning region": "Planning regions", "official region": "Regions", "official district": "Districts"}


def core_net_rise() -> float:
    """Rise of core administration net per inhabitant of the merged Styrian units in 2014 over 2013,
    rounded to whole euros as printed in styria_transition.txt."""
    text = (fag.DER / "styria_transition.txt").read_text()
    return float(re.search(r"rise of core administration net in 2014: (-?\d+)", text).group(1))


CORE_NET = core_net_rise()  # EUR per inhabitant


def extra_upper() -> float:
    """Upper one-off cost per inhabitant: CORE_NET plus 3 x the upper 95 % bound of the extraordinary
    balance, 2014-16 minus 2017-19, Styrian control (styria_transition_net.txt)."""
    block = (fag.DER / "styria_transition_net.txt").read_text().split("extraordinary balance spending minus revenue")[1]
    block = block.split("Styrian control")[1].split("combined control group")[0]
    hi = float(re.search(r"2014-16 minus 2017-19: [-+][\d.]+ +95 % \[[-+][\d.]+, ([-+][\d.]+)\]", block).group(1))
    return CORE_NET + 3 * hi


EXTRA_HI = extra_upper()
COL_POPULATION = "bevoelkerung"  # FAG population column in vbg_population_fag.csv of data.vorarlberg.gv.at
COL_YEAR = "berichtsjahr"  # reference year column in vbg_population_fag.csv


def table(path: str, sep: str = "|") -> dict:
    rows = {}
    for line in (fag.DER / path).read_text().splitlines():
        parts = [p.strip() for p in line.split(sep)]
        if parts[0] in NAMES and len(parts) > 3:
            rows[parts[0]] = parts
    return rows


def pareto() -> dict:
    e = {}
    for line in (fag.DER / "pareto.txt").read_text().splitlines():
        m = re.match(r"\s+(Threshold \d+|official [a-z ]+?)\s+(yes|no)\s+(\d+)\s+(-?[\d.]+)\s+(-?[\d.]+)", line)
        if m and m.group(1) in NAMES:
            e[m.group(1)] = (float(m.group(4)), float(m.group(5)))
    return e


def merged_pop() -> dict:
    fp = {r["gkz"]: float(r[COL_POPULATION]) for r in
          csv.DictReader((RAW / "vbg_population_fag.csv").open(encoding="utf-8"), delimiter=";")
          if r[COL_YEAR] == "2024"}
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv")))
    out = {}
    for cut in NAMES:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        out[cut] = sum(fp[g] for m in units.values() if len(m) > 1 for g in m)
    return out


def span(a: float, b: float) -> str:
    lo, hi = min(a, b), max(a, b)
    return f"{lo:+.1f}" if abs(hi - lo) < 0.05 else f"{lo:+.1f} to {hi:+.1f}"


def main() -> None:
    e, f, lr, pop = pareto(), table("fag.txt"), table("state_grants.txt"), merged_pop()
    total_pop = sum(float(r[COL_POPULATION]) for r in csv.DictReader((RAW / "vbg_population_fag.csv").open(encoding="utf-8"),
                                                                     delimiter=";") if r[COL_YEAR] == "2024")
    old = ["", "Variant: the state grants the merged units lose shared by population instead of going entirely to the unchanged municipalities",
           "Partition | share of population merged | merged units with inflow | unchanged municipalities"]
    out = ["Money balance per partition, m EUR per year (balance.py)",
           "Ranges: savings with factor 0.16 and 0.57; state guidelines both ends; structural fund open, sign minus", "",
           "Partition | Vorarlberg total | merged units | same with inflow | unchanged municipalities | population in merged units | one-off m | years to break even"]
    for cut, name in NAMES.items():
        e57, e16 = e[cut]
        inflow = float(f[cut][3])
        win, lose, same_in = float(f[cut][7]), float(f[cut][8]), float(f[cut][11])
        lo, hi = (float(x) for x in re.findall(r"-?[\d.]+", lr[cut][7]))
        whole = span(e16 + inflow, e57 + inflow)
        mrg = span(win + lose + min(e16, e57) + lo, win + lose + max(e16, e57) + hi)
        same_out = float(f[cut][9])
        to_merged = inflow - (same_in - same_out)  # share of the inflow that reaches merged units
        mrg_in = span(win + lose + to_merged + min(e16, e57) + lo, win + lose + to_merged + max(e16, e57) + hi)
        same = span(same_in - hi, same_in - lo)  # fixed pot: the others get only the net change of the merged units
        p = pop[cut]
        once = (p * CORE_NET / 1e6, p * EXTRA_HI / 1e6)
        years = ", ".join(f"{once[0] / x:.0f} to {once[1] / x:.0f} (E {k})" for x, k in ((e57, "0.57"), (e16, "0.16")) if x > 0) or "never"
        sh = pop[cut] / total_pop
        old.append(f"{name} | {sh:.0%} | {span(win + lose + to_merged + min(e16, e57) + (1 - sh) * lo, win + lose + to_merged + max(e16, e57) + (1 - sh) * hi)}"
                   f" | {span(same_in - (1 - sh) * hi, same_in - (1 - sh) * lo)}")
        out.append(f"{name} | {whole} | {mrg} | {mrg_in} | {same} | {p:,.0f} | {once[0]:.1f} to {once[1]:.1f} | {years}")
    out += ["", f"one-off: core administration net {CORE_NET:.0f} EUR per inhabitant to {EXTRA_HI:.0f} EUR ({CORE_NET:.0f} plus three times the upper bound of the extraordinary balance 2014-16, Styria),",
            "per inhabitant of the merged units. Unchanged municipalities: FAG with inflow plus the balance of the state guidelines of the merged units with reversed sign."]
    out += old
    text = "\n".join(out)
    print(text)
    (fag.DER / "balance.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
