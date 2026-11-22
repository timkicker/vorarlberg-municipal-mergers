"""Municipal unions of the 2016 cooperation study and what a merger does to them.

Run from the repository root. Writes data/derived/unions.txt.
"""

import collections
import csv
import json
import sys

import fag

CUTS = ("Threshold 2000", "Threshold 3500", "Threshold 5000", "official planning region")
# Values of legal_form in coop2016.json, as written in the 2016 cooperation study
FORM_UNION_GG_SHORT = "Gemeindeverband gem. Gemeindegesetz"  # municipal union under the GG, abbreviated
FORM_UNION = "Gemeindeverband"  # municipal union
FORM_UNION_GG = "Gemeindeverband gemäß Gemeindegesetz"  # municipal union under the GG
FORM_SCHOOL_UNION = "Gemeindeverband als gesetzlicher Schulerhalter"  # municipal union that runs a school
FORM_REGISTRY_UNION = "zusammengeschlossene Standesamts- und Staatsbürgerschaftsverbände"  # registry office and citizenship unions
FORM_ADMIN_PARTNERSHIP = "Verwaltungsgemeinschaft"  # administrative partnership
FORM_WATER_UNION = "Wasserverband gemäß Wasserrechtsgesetz"  # water union under the WRG
GROUPS = {
    FORM_UNION_GG_SHORT: "municipal union (GG)",
    FORM_UNION: "municipal union (GG)",
    FORM_UNION_GG: "municipal union (GG)",
    FORM_SCHOOL_UNION: "school union",
    FORM_REGISTRY_UNION: "registry office union",
    FORM_ADMIN_PARTNERSHIP: "administrative partnership",
    FORM_WATER_UNION: "water union (WRG)",
}


def main() -> None:
    coops = {k["id"]: k for k in json.load(open(fag.DER / "coop2016.json", encoding="utf-8"))}
    mem = collections.defaultdict(set)
    for r in csv.DictReader(open(fag.DER / "coop2016_members.csv", encoding="utf-8")):
        mem[int(r["coop_id"])].add(r["gkz"])
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    sel = {i: GROUPS[k["legal_form"]] for i, k in coops.items() if k["legal_form"] in GROUPS and len(mem[i]) >= 2}
    out = ["Municipal unions after the merger (unions.txt, unions.py)", "",
           "unions with at least two assigned members per group: "
           + ", ".join(f"{g} {n}" for g, n in collections.Counter(sel.values()).most_common()), "",
           "partition | group | unions | (a) wholly in one unit | (b) fewer members | (c) unchanged | memberships before / after"]
    for cut in CUTS:
        unit = {r["gkz"]: r[cut] for r in rows}
        for grp in list(dict.fromkeys(GROUPS.values())) + ["all"]:
            ids = [i for i, g in sel.items() if grp in ("all", g)]
            a = b = c = before = after = 0
            for i in ids:
                u = {unit[g] for g in mem[i]}
                before += len(mem[i])
                after += len(u)
                if len(u) == 1:
                    a += 1
                elif len(u) < len(mem[i]):
                    b += 1
                else:
                    c += 1
            out.append(f"  {cut} | {grp} | {len(ids)} | {a} ({a / len(ids):.0%}) | {b} | {c} | {before} / {after}")
        out.append("")
    ex = [coops[i]["name"] for i in sel if len({{r["gkz"]: r["Threshold 3500"] for r in rows}[g] for g in mem[i]}) == 1]
    out.append("examples (a) at Threshold 3500: " + "; ".join(ex[:12]))
    text = "\n".join(out)
    print(text)
    (fag.DER / "unions.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
