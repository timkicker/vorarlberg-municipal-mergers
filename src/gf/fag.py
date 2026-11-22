"""Municipal tax shares under the FAG 2024 for each set of merged units.

Writes data/derived/fag.txt and data/derived/fag_units.csv.
"""

import collections
import csv
import pathlib

from accounts_columns import COL_POPULATION_JAN1

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
DER = ROOT / "data" / "derived"

# Statutory cities other than Vienna (FAG 2024 § 11(9), § 13(6))
STATUTORY_CITIES = {"10101", "10201", "20101", "20201", "30101", "30201", "30301", "30401",
            "40101", "40201", "40301", "50101", "60101", "70101"}

# Advances 2025 in million euro, Austrian Association of Municipalities after BMF, table of March 2026
ADVANCE_VBG = 654.2
ADVANCE_AT = 13811.8
TRANSFER_TAX_MUNICIPALITIES = 0.93742 * 1304.1  # municipal share of the land transfer tax 2025, same table
STATE_GRANT_SHARE = 0.128  # kept back as state grants, FAG 2024 § 13(1)

# split between the states, FAG 2024 § 11(6) no. 2: by population, by graded population key, by fixed key
SHARE_POPULATION, SHARE_GRADED, SHARE_FIX = 0.17235, 0.58515, 0.2425
FIX_VBG = 0.05640  # Vorarlberg's fixed key, same paragraph

EXTRA_10, EXTRA_20 = 146.02, 175.01  # extra share per inhabitant in Vorarlberg, § 13(6)
CUTS = ["Threshold 2000", "Threshold 3500", "Threshold 5000",
        "official planning region", "official region", "official district"]
# columns of vbg_overnight_stays.csv of data.vorarlberg.gv.at
COL_YEAR = "berichtsjahr"  # reference year
COL_STAYS = "naechtigungen"  # overnight stays


def abs_factor(n: float, statutory: bool = False, vienna: bool = False) -> float:
    """Graded population of one municipality, § 11(9)."""
    if vienna or n > 50000:
        return n * 7 / 3
    if statutory:
        v = 2 * n
        if n > 45000:
            v += 10 / 3 * (n - 45000)
        return v
    if n <= 10000:
        v = n * (1 + 41 / 67)
        if n > 9000:
            v += 110 / 201 * (n - 9000)
        return v
    if n <= 20000:
        v = n * 5 / 3
        if n > 18000:
            v += 10 / 3 * (n - 18000)
        return v
    v = 2 * n
    if n > 45000:
        v += 10 / 3 * (n - 45000)
    return v


def advance_share(n: float) -> float:
    """Advance per inhabitant in Vorarlberg times inhabitants, § 13(6)."""
    if n <= 9300:
        return 0.0
    if n <= 10000:
        return (n - 9300) * EXTRA_10 * 10000 / 700
    if n <= 20000:
        v = EXTRA_10 * n
        if n > 18000:
            v += (n - 18000) * (EXTRA_20 - EXTRA_10) * 20000 / 2000
        return v
    return EXTRA_20 * n


def overnight(n: float, stays: float) -> float:
    """Amount for overnight stays, § 13(8)."""
    if n > 10000:
        return 0.0
    rate = 0.90 if n <= 9300 else 0.90 * (10000 - n) / 700
    return rate * max(0.0, stays - 1000)


def load_pop() -> dict:
    pop = collections.Counter()
    with open(RAW / "bevstand_2024.csv") as f:
        for r in csv.DictReader(f, delimiter=";"):
            g = r["C-GRGEMAKT-0"].split("-")[1]
            pop["90001" if g.startswith("9") else g] += int(r[COL_POPULATION_JAN1])
    return pop


def load_stays(year: int) -> dict:
    stays = collections.Counter()
    with open(RAW / "vbg_overnight_stays.csv") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if int(r[COL_YEAR]) == year:
                stays[r["gkz"]] += int(r[COL_STAYS] or 0)
    return stays


def austria_abs(pop: dict) -> tuple[float, float]:
    total = sum(abs_factor(n, g in STATUTORY_CITIES, g == "90001") for g, n in pop.items())
    vbg = sum(abs_factor(n) for g, n in pop.items() if g.startswith("8"))
    return total, vbg


def distribute(units: dict, pop: dict, stays: dict, pot: float) -> dict:
    """Net tax shares of each unit inside Vorarlberg, § 13(3)."""
    n = {u: sum(pop[g] for g in m) for u, m in units.items()}
    extra = {u: advance_share(n[u]) for u in units}
    night = {u: overnight(n[u], sum(stays.get(g, 0) for g in m)) for u, m in units.items()}
    ab = {u: abs_factor(n[u]) for u in units}
    rest = pot - sum(extra.values()) - sum(night.values())
    sab = sum(ab.values())
    return {u: {"inh": n[u], "extra": extra[u], "stays": night[u], "abs": rest * ab[u] / sab,
                "total": extra[u] + night[u] + rest * ab[u] / sab} for u in units}


def main() -> None:
    pop = load_pop()
    stays = load_stays(2023)
    vbg = sorted(g for g in pop if g.startswith("8"))
    out = []
    p = out.append

    pop_at, pop_v = sum(pop.values()), sum(pop[g] for g in vbg)
    abs_at, abs_v = austria_abs(pop)
    pool = ADVANCE_AT - TRANSFER_TAX_MUNICIPALITIES
    model_v = pool * (SHARE_POPULATION * pop_v / pop_at + SHARE_GRADED * abs_v / abs_at + SHARE_FIX * FIX_VBG)
    grest_v = TRANSFER_TAX_MUNICIPALITIES * pop_v / pop_at
    actual_v = ADVANCE_VBG - grest_v
    p("Shares of joint federal taxes under FAG 2024 per partition (fag.py)")
    p("")
    p(f"Population 1.1.2024: Austria {pop_at:,}, Vorarlberg {pop_v:,}, Vienna {pop['90001']:,}")
    p(f"Share of Vorarlberg: population {pop_v / pop_at:.4%}, graded key {abs_v / abs_at:.4%}")
    p(f"Pot of the uniform key {pool:,.1f} m; model Vorarlberg {model_v:,.1f} m, "
      f"advances without land transfer tax by population {actual_v:,.1f} m, "
      f"deviation {model_v / actual_v - 1:+.1%}")
    calib = 1.0
    if abs(model_v / actual_v - 1) > 0.05:
        calib = actual_v / model_v
        p(f"Deviation over 5 %, pot calibrated on Vorarlberg (factor {calib:.3f})")
    pool *= calib
    vienna_share = pool and (pool * (SHARE_POPULATION * pop["90001"] / pop_at
                                   + SHARE_GRADED * abs_factor(pop["90001"], vienna=True) / abs_at
                                   + SHARE_FIX * 0.30165)) / pool
    p(f"Share of Vienna as a municipality in the pot {vienna_share:.1%} (the ceiling in § 12 counts state and municipality together "
      f"and applies only above 30.4 % of both; not applied)")
    pot_v = actual_v * (1 - STATE_GRANT_SHARE) * 1e6  # without the land transfer tax, which follows local yield (§ 11(6)(1))
    stays_v = sum(stays.get(g, 0) for g in vbg)
    p(f"Pot for distribution in Vorarlberg without land transfer tax after deducting 12.8 %: {pot_v / 1e6:,.1f} m; overnight stays 2023 {stays_v:,}")
    p("")

    rows = list(csv.DictReader(open(DER / "pareto_partitions.csv")))
    cand = {r["name"]: r for r in csv.DictReader(open(DER / "pareto_candidates.csv"))}
    base_units = {g: [g] for g in vbg}
    base = distribute(base_units, pop, stays, pot_v)
    p(f"Today: extra share {sum(b['extra'] for b in base.values()) / 1e6:.1f} m, "
      f"overnight stay amount {sum(b['stays'] for b in base.values()) / 1e6:.1f} m, "
      f"municipalities over 10,000: {sum(1 for b in base.values() if b['inh'] > 10000)}")
    p("")
    head = ("Partition", "Units", "New over 10,000", "Net inflow m", "Savings m",
            "Extra share +m", "Overnight stays +m", "Winners m", "Losers m",
            "Unchanged m", "Unchanged % max", "With inflow m", "With inflow % max")
    p(" | ".join(head))
    units_by = []
    gkz_name = {r["gkz"]: r["municipality"] for r in rows}
    for cut in CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        abs_v1 = sum(abs_factor(sum(pop[g] for g in m)) for m in units.values())
        share0 = abs_v / abs_at
        share1 = abs_v1 / (abs_at - abs_v + abs_v1)
        inflow = pool * SHARE_GRADED * (share1 - share0) * (1 - STATE_GRANT_SHARE) * 1e6
        new = distribute(units, pop, stays, pot_v + inflow)
        same = distribute(units, pop, stays, pot_v)
        gain = loss = 0.0
        unchanged_d = 0.0
        unchanged_max = 0.0
        unchanged_in = 0.0
        unchanged_in_max = 0.0
        for u, m in units.items():
            before = sum(base[g]["total"] for g in m)
            d = same[u]["total"] - before
            if len(m) == 1:
                unchanged_d += d
                unchanged_max = min(unchanged_max, d / before)
                d_in = new[u]["total"] - before
                unchanged_in += d_in
                unchanged_in_max = min(unchanged_in_max, d_in / before)
            elif d >= 0:
                gain += d
            else:
                loss += d
            units_by.append({
                "partition": cut, "unit": u, "municipalities": len(m), "pop": new[u]["inh"],
                "before_eur": round(before), "after_without_inflow_eur": round(same[u]["total"]),
                "after_with_inflow_eur": round(new[u]["total"]),
                "diff_per_capita": round((new[u]["total"] - before) / new[u]["inh"], 1),
                "members": ";".join(gkz_name.get(g, g) for g in m)})
        crossed = sum(1 for u, m in units.items() if len(m) > 1 and new[u]["inh"] > 10000
                      and all(pop[g] <= 10000 for g in m))
        dva = sum(x["extra"] for x in same.values()) - sum(b["extra"] for b in base.values())
        dna = sum(x["stays"] for x in same.values()) - sum(b["stays"] for b in base.values())
        sav = float(cand[cut]["E_main"]) / 1e6 if cut in cand else float("nan")
        p(" | ".join([cut, str(len(units)), str(crossed), f"{inflow / 1e6:.1f}", f"{sav:.1f}",
                      f"{dva / 1e6:.1f}", f"{dna / 1e6:.1f}", f"{gain / 1e6:.1f}", f"{loss / 1e6:.1f}",
                      f"{unchanged_d / 1e6:.1f}", f"{unchanged_max:.1%}",
                      f"{unchanged_in / 1e6:.1f}", f"{unchanged_in_max:.1%}"]))
    p("")
    p("Winners, losers and unchanged: shift inside Vorarlberg without inflow from outside,")
    p("per unit against the sum of its predecessors. Savings: E_main from pareto_candidates.csv.")
    (DER / "fag.txt").write_text("\n".join(out) + "\n")
    with open(DER / "fag_units.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(units_by[0]))
        w.writeheader()
        w.writerows(units_by)
    print("\n".join(out))


if __name__ == "__main__":
    main()
