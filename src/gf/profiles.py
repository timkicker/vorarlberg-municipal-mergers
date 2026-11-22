"""Profile per municipality for two cuts: travel time to the seat, tax shares, base grant, loans.

Run from the repository root. Writes data/derived/profiles.csv and data/derived/profiles.txt.
"""

import collections
import csv
import sys

import debt
import fag
import state_grants

CUTS = ("Threshold 3500", "Threshold 5000")
Y = 2024
# Columns of vbg_population_fag.csv and vbg_loans.csv (open data of the state of Vorarlberg)
COL_YEAR = "berichtsjahr"  # reference year, both files
COL_POPULATION = "bevoelkerung"  # FAG population
COL_LOANS_END = "darlehensendstand"  # outstanding loans at the end of the year


def tax_shares(units: dict, pop: dict, stays: dict) -> dict:
    """Net tax shares per unit as in fag.main, pot including the inflow from other states."""
    vbg = [g for g in pop if g.startswith("8")]
    pop_at, pop_v = sum(pop.values()), sum(pop[g] for g in vbg)
    abs_at, abs_v = fag.austria_abs(pop)
    pool = fag.ADVANCE_AT - fag.TRANSFER_TAX_MUNICIPALITIES
    model_v = pool * (fag.SHARE_POPULATION * pop_v / pop_at + fag.SHARE_GRADED * abs_v / abs_at + fag.SHARE_FIX * fag.FIX_VBG)
    actual_v = fag.ADVANCE_VBG - fag.TRANSFER_TAX_MUNICIPALITIES * pop_v / pop_at
    if abs(model_v / actual_v - 1) > 0.05:
        pool *= actual_v / model_v
    pot = fag.ADVANCE_VBG * (1 - fag.STATE_GRANT_SHARE) * 1e6
    abs_v1 = sum(fag.abs_factor(sum(pop[g] for g in m)) for m in units.values())
    inflow = pool * fag.SHARE_GRADED * (abs_v1 / (abs_at - abs_v + abs_v1) - abs_v / abs_at) * (1 - fag.STATE_GRANT_SHARE) * 1e6
    return fag.distribute(units, pop, stays, pot + inflow)


def loans() -> tuple[dict, dict]:
    fp, dl = {}, {}
    for r in csv.DictReader((debt.RAW / "vbg_population_fag.csv").open(encoding="utf-8"), delimiter=";"):
        if int(r[COL_YEAR]) == Y:
            fp[r["gkz"]] = float(r[COL_POPULATION])
    for r in csv.DictReader((debt.RAW / "vbg_loans.csv").open(encoding="utf-8"), delimiter=";"):
        if int(r[COL_YEAR]) == Y:
            dl[r["gkz"]] = debt.num(r[COL_LOANS_END])
    return fp, dl


def main() -> None:
    pop = fag.load_pop()
    stays = fag.load_stays(2023)
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    name = {r["gkz"]: r["municipality"] for r in rows}
    travel = {r["from_gkz"]: r for r in csv.DictReader(open(fag.DER / "travel_time_seat.csv", encoding="utf-8"))}
    fp, dl = loans()
    missing_loans = sorted(name[g] for g in name if g not in dl)
    base = tax_shares({g: [g] for g in name}, pop, stays)
    out_rows = []
    lines = ["Profile per municipality (profiles.py)", "",
             f"loans {Y} missing for: {', '.join(missing_loans) or 'none'} (counted as 0)", ""]
    for cut in CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        new = tax_shares(units, pop, stays)
        recs = []
        for u, m in units.items():
            n = sum(pop[g] for g in m)
            seat = max(m, key=lambda g: pop[g])
            fpu = sum(fp[g] for g in m)
            dlu = sum(dl.get(g, 0.0) for g in m)
            for g in m:
                rec = {
                    "partition": cut, "gkz": g, "municipality": name[g], "population": pop[g], "unit": u,
                    "members": len(m), "seat": name[seat], "drive_min": float(travel[g][seat]),
                    "shares_now_pc": base[g]["total"] / pop[g],
                    "shares_unit_pc": new[u]["total"] / n,
                    "base_now_pc": state_grants.base_amount(pop[g]) / pop[g],
                    "base_unit_pc": state_grants.base_amount(n) / n,
                    "loans_now_pc": dl.get(g, 0.0) / fp[g],
                    "loans_unit_pc": dlu / fpu,
                }
                rec["d_shares"] = rec["shares_unit_pc"] - rec["shares_now_pc"]
                rec["d_base"] = rec["base_unit_pc"] - rec["base_now_pc"]
                rec["d_loans"] = rec["loans_unit_pc"] - rec["loans_now_pc"]
                recs.append(rec)
        out_rows += recs
        merged = [r for r in recs if r["members"] > 1]
        lines.append(f"{cut}: {len(recs)} municipalities, of these in units with a merger {len(merged)}")
        for key, label, sign in (("d_shares", "tax shares", -1), ("d_base", "base grant", -1), ("d_loans", "loans", 1)):
            worse = [r for r in merged if sign * r[key] > 0.5]
            top = sorted(merged, key=lambda r: sign * r[key], reverse=True)[:5]
            lines.append(f"  {label}: worse {len(worse)}; largest: " + ", ".join(f"{r['municipality']} {r[key]:+,.0f}" for r in top))
        all3 = [r for r in merged if r["d_shares"] < -0.5 and r["d_base"] < -0.5 and r["d_loans"] > 0.5]
        lines.append(f"  worse in all three: {len(all3)}" + (": " + ", ".join(r["municipality"] for r in all3) if all3 else ""))
        far = [r for r in merged if r["drive_min"] > 20]
        lines.append(f"  over 20 minutes to the seat: {len(far)}" + (": " + ", ".join(f"{r['municipality']} {r['drive_min']:.0f}" for r in sorted(far, key=lambda r: -r['drive_min'])) if far else ""))
        lines.append("")
    with open(fag.DER / "profiles.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        for r in out_rows:
            w.writerow({k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()})
    text = "\n".join(lines)
    print(text)
    (fag.DER / "profiles.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
