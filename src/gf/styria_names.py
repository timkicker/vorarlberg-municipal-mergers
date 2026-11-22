"""Names of the Styrian municipalities formed in 2015 from at least two predecessors.

Run from the repository root.
Writes data/derived/styria_names.txt.
"""

import collections
import json
import re
import sys

import styria

# Status prefixes in the official municipality names (market town, town), stripped before comparing names
NAME_PREFIXES = r"^(markt|stadt|marktgemeinde|stadtgemeinde)\s+"
PREFIX = re.compile(NAME_PREFIXES, re.I)


def names(year: int) -> dict:
    geo = json.loads((styria.RAW / f"boundaries_statat_at_{year}.geojson").read_text())
    return {f["properties"]["g_id"]: f["properties"]["g_name"] for f in geo["features"] if f["properties"]["g_id"].startswith("6")}


def norm(s: str) -> str:
    return PREFIX.sub("", s.strip()).lower()


def classify(new: str, olds: list[str]) -> tuple[str, int]:
    n = norm(new)
    o = [norm(x) for x in olds]
    inside = sum(1 for x in o if x and x in n)
    if n in o:
        return "same", inside
    if inside >= 2:
        return "double name", inside
    if inside == 1:
        return "with part", inside
    return "new", inside


def main() -> None:
    mp, _ = styria.mapping()
    old_n, new_n = names(2014), names(2015)
    pre = collections.defaultdict(list)
    for g, (n, share) in mp.items():
        if share >= styria.SPLIT_SHARE:
            pre[n].append(g)
    units = {n: gs for n, gs in pre.items() if len(gs) >= 2}
    by = collections.defaultdict(list)
    lost = total = 0
    for n, gs in sorted(units.items()):
        olds = [old_n[g] for g in gs]
        cls, inside = classify(new_n[n], olds)
        by[cls].append((new_n[n], olds))
        total += len(olds)
        lost += len(olds) - inside
    out = ["Names of the Styrian merged municipalities 2015 (styria_names.py)", "",
           f"New municipalities with at least two predecessors (area share from {styria.SPLIT_SHARE:.0%}): {len(units)}", "",
           "Class | count | share | examples"]
    for cls in ("same", "double name", "with part", "new"):
        v = by[cls]
        ex = "; ".join(f"{a} <- {', '.join(b)}" for a, b in v[:3])
        out.append(f"  {cls} | {len(v)} | {len(v) / len(units):.0%} | {ex}")
    out += ["", f"Predecessor names in total: {total}, of which not contained in the new name: {lost} ({lost / total:.0%})"]
    text = "\n".join(out)
    print(text)
    (styria.RAW.parent / "derived" / "styria_names.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
