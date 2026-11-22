"""Childcare supply by municipal size, from the answer to state parliament question 29.01.322 (2021/22).

Run from the repository root.
Writes data/derived/childcare.txt.
"""

import collections
import csv
import re
import statistics
import subprocess
import sys

import base_amount as ba
import fag

PDF = fag.DER.parent / "raw" / "landtag_29_01_322_childcare_2022.pdf"
CLASSES = ((0, 1000), (1000, 2000), (2000, 3500), (3500, 5000), (5000, 10000), (10000, float("inf")))
# section heads in the PDF
SECTION_PLACES = "Anzahl Betreuungsplätze"  # number of places
SECTION_HOURS = "Anzahl Wochenöffnungszeit"  # weekly opening hours
SECTION_FULL_DAY = "Anzahl Einrichtungen nach Öffnungszeit"  # facilities by opening time
# headings of the forms of care in the PDF and the codes the PDF uses for them
FORM_KINDERGARTEN, FORM_CHILDCARE, FORM_PLAYGROUP = "KIGA", "KIBE", "SPG"
FORMS = {"Kindergarten": FORM_KINDERGARTEN, "Kinderbetreuung": FORM_CHILDCARE, "Spielgruppe": FORM_PLAYGROUP}
FORM_LABEL = {FORM_KINDERGARTEN: "kindergarten", FORM_CHILDCARE: "crèche", FORM_PLAYGROUP: "playgroup"}
ROW = re.compile(r"^(\S.*?)\s+(8\d{8})\s+(.+?)\s{2,}(?:(" + "|".join(FORMS.values()) + r")\s+)?([\d.,]+)\s+([\d.,]+)\s*$")


def num(x: str) -> float:
    return float(x.replace(".", "").replace(",", "."))


def gkz(stat: str) -> str:
    return "8" + stat[1:3] + stat[7:9]


def parse() -> tuple[list, list, list]:
    lines = subprocess.run(["pdftotext", "-layout", str(PDF), "-"], capture_output=True, text=True, check=True).stdout.splitlines()
    start = {k: next(i for i, l in enumerate(lines) if l.startswith(k)) for k in
             (SECTION_PLACES, SECTION_HOURS, SECTION_FULL_DAY)}
    places, hours, full = [], [], []
    form = None
    for l in lines[start[SECTION_PLACES]:start[SECTION_HOURS]]:
        s = l.strip()
        if s in FORMS:
            form = FORMS[s]
        m = ROW.match(l)
        if m:
            places.append(dict(town=m[1].strip(), stat=m[2], name=m[3].strip(), form=form, capacity=num(m[5]), children=num(m[6])))
    for l in lines[start[SECTION_HOURS]:start[SECTION_FULL_DAY]]:
        m = ROW.match(l)
        if m:
            hours.append(dict(town=m[1].strip(), stat=m[2], name=m[3].strip(), form=m[4], hours=num(m[5]), closed=num(m[6])))
    for l in lines[start[SECTION_FULL_DAY]:]:
        m = re.match(r"^(\S.*?)\s{2,}(.+?)\s{2,}(" + "|".join(FORMS.values()) + r")\s*$", l)
        if m:
            full.append(dict(town=m[1].strip(), name=m[2].strip(), form=m[3]))
    return places, hours, full


def main() -> None:
    places, hours, full = parse()
    pop = ba.fag_pop(2022)
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    name = {r["gkz"]: r["municipality"] for r in rows}
    assert set(name) <= set(pop) and len(name) == 96
    out = ["Childcare by municipal size, 2021/22 (childcare.py)",
           "Source: answer to state parliament question 29.01.322 of 28.07.2022, questions 6 to 10; population for the fiscal equalisation 2022",
           f"rows read: places {len(places)} (total places {sum(p['capacity'] for p in places):,.0f}, children {sum(p['children'] for p in places):,.0f}), "
           f"hours {len(hours)}, open 7:30-17:30 {len(full)}"]
    for f in FORMS.values():
        ps = [p for p in places if p["form"] == f]
        out.append(f"  {FORM_LABEL[f]}: {len(ps)} facilities, places {sum(p['capacity'] for p in ps):,.1f}, children {sum(p['children'] for p in ps):,.0f}")
    byname = {v: k for k, v in name.items()}
    bad = [p for p in places + hours if gkz(p["stat"]) not in name]
    for p in bad:
        p["stat"] = "8" + byname[p["town"]][1:3] + "0000" + byname[p["town"]][3:]
    out.append(f"statistics number without a valid municipality, assigned by the place column: {len(bad)} rows {sorted({p['name'] for p in bad})}")
    off = sum(1 for p in places + hours if name[gkz(p["stat"])].split()[0].rstrip(",") not in p["town"] and not p["town"].startswith(name[gkz(p["stat"])][:5]))
    out.append(f"place in the column differs from the place given by the statistics number: {off} rows (the number counts)")
    by_name = {h["name"]: gkz(h["stat"]) for h in hours}
    full_g, miss = set(), []
    for f in full:
        g = by_name.get(f["name"])
        if g is None:
            g = next((k for k, v in name.items() if v == f["town"]), None)
        if g is None:
            miss.append(f["name"])
        else:
            full_g.add(g)
    out.append(f"facilities 7:30-17:30 without assignment: {len(miss)} {miss}")
    out.append(f"municipalities with at least one facility 7:30-17:30: {len(full_g)} of 96")

    hrs = collections.defaultdict(lambda: collections.defaultdict(list))
    for h in hours:
        hrs[gkz(h["stat"])][h["form"]].append(h)
    childcare_capacity = collections.Counter()
    for p in places:
        if p["form"] in (FORM_CHILDCARE, FORM_PLAYGROUP):
            childcare_capacity[gkz(p["stat"])] += p["capacity"]
    has_creche = {gkz(p["stat"]) for p in places if p["form"] == FORM_CHILDCARE}

    med = lambda x: f"{statistics.median(x):.1f}" if x else "-"  # noqa: E731
    out += ["", "Class | municipalities | weekly hours kindergarten median (facilities) | crèche | closing days kindergarten | crèche | share of municipalities with 7:30-17:30 | places crèche+playgroup per 1,000 inhabitants | share of municipalities without crèche"]
    for lo, hi in CLASSES + ((0, float("inf")),):
        gs = [g for g in name if lo <= pop[g] < hi]
        hk = [h["hours"] for g in gs for h in hrs[g][FORM_KINDERGARTEN]]
        hb = [h["hours"] for g in gs for h in hrs[g][FORM_CHILDCARE]]
        ck = [h["closed"] for g in gs for h in hrs[g][FORM_KINDERGARTEN]]
        cb = [h["closed"] for g in gs for h in hrs[g][FORM_CHILDCARE]]
        lab = "all" if hi == float("inf") and lo == 0 else f"{lo:,}-{hi:,}"
        out.append(f"  {lab} | {len(gs)} | {med(hk)} ({len(hk)}) | {med(hb)} ({len(hb)}) | {med(ck)} | {med(cb)} | "
                   f"{sum(g in full_g for g in gs) / len(gs):.0%} | {sum(childcare_capacity[g] for g in gs) / sum(pop[g] for g in gs) * 1000:.1f} | "
                   f"{sum(g not in has_creche for g in gs) / len(gs):.0%}")

    out += ["", "Units with at least one facility 7:30-17:30: partition | units | with supply | share | population in units with supply"]
    tot = sum(pop[g] for g in name)
    for cut in ("Status quo", "Threshold 2000", "Threshold 3500"):
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        w = [u for u in units.values() if any(g in full_g for g in u)]
        out.append(f"  {cut} | {len(units)} | {len(w)} | {len(w) / len(units):.0%} | {sum(pop[g] for u in w for g in u) / tot:.1%}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "childcare.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
