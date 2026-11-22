"""Size steps of the Vorarlberg grant guideline for each set of merged units.

Writes data/derived/state_grants.txt.
"""

import collections
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fag  # noqa: E402

CITIES = {"80207", "80301", "80404", "80103", "80302"}


def base_amount(n: float) -> float:
    """Base amount of the state guideline for a unit of n inhabitants."""
    if n < 3000:
        return 200_000
    if n <= 6000:
        return 100_000
    return 0.0


def central_place(n: float, city: bool) -> float:
    if city:
        return 300_000
    if n > 20000:
        return 200_000
    if n >= 10000:
        return 80_000
    return 0.0


def village_parts(n: float, k: int) -> float:
    if n >= 10000 or k < 2:
        return 0.0
    return 200_000 if k == 2 else 300_000


def totals(units: dict, pop: dict) -> tuple[float, float, float]:
    s = z = o = 0.0
    for m in units.values():
        n = sum(pop[g] for g in m)
        s += base_amount(n)
        z += central_place(n, any(g in CITIES for g in m))
        o += village_parts(n, len(m))
    return s, z, o


def main() -> None:
    pop = fag.load_pop()
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv")))
    base = {r["gkz"]: [r["gkz"]] for r in rows}
    s0, z0, o0 = totals(base, pop)
    out = ["Size steps of the state guideline on state grants per partition (state_grants.py), m euro per year", "",
           f"Today: base amount {s0 / 1e6:.1f}, central place {z0 / 1e6:.1f}, village parts (not known, 0)", "",
           "Partition | units | base amount | change | central place | change | village parts at most | total change"]
    for cut in fag.CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        s, z, o = totals(units, pop)
        out.append(f"{cut} | {len(units)} | {s / 1e6:.1f} | {(s - s0) / 1e6:+.1f} | {z / 1e6:.1f} | {(z - z0) / 1e6:+.1f} | "
                   f"{o / 1e6:+.1f} | {(s - s0 + z - z0) / 1e6:+.1f} to {(s - s0 + z - z0 + o) / 1e6:+.1f}")
    out += ["", "The total of the strengthening funds is fixed. Every change goes into the residual item (§ 4 item 9)",
            "and shifts money between municipalities. Village parts: upper bound assuming every predecessor has a compulsory school."]
    text = "\n".join(out)
    print(text)
    (fag.DER / "state_grants.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
