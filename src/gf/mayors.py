"""Mayoral candidacies by size in Vorarlberg 2020 and 2025: missing candidates, women, age, turnover.

Writes data/derived/mayors.txt.
"""

import csv
import json
import pathlib
import re
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import elections  # noqa: E402
import fag  # noqa: E402

RAW = fag.DER.parent / "raw"
NAMES = fag.DER / "first_names.csv"
# Keys and values of gv_YYYY.json, the municipal election results of the state of Vorarlberg (open data).
KEY_RESULTS = "ergebnisse"  # list of municipalities
KEY_MAYOR_ELECTION = "buergermeisterwahl"  # mayoral election block
KEY_COUNCIL_ELECTION = "gemeinderatswahl"  # council election block
KEY_MODE = "wahlart"  # election mode, in both blocks
KEY_CANDIDATES = "kandidaten"  # mayoral candidates
KEY_NAME = "name"  # candidate entry, "title surname first name, birth year - yes/no"
KEY_VOTES = "stimmen"  # votes of a candidate
KEY_PERCENT = "prozent"  # vote share of a candidate
KEY_CODE = "schluessel"  # municipality code
KEY_ELIGIBLE = "wahlberechtigte"  # eligible voters
MODE_SEVERAL_CANDIDATES = "mehrereKandidaten"  # mayoral election with several candidates
MODE_ONE_CANDIDATE = "einKandidat"  # mayoral election with one candidate
MODE_MAJORITY_VOTE = "mehrheitswahl"  # council elected by majority vote, no list
MODE_ONE_LIST = "eineListe"  # council election with only one list
FLAG_NO = "nein"  # trailing flag of a candidate entry, "no"
FLAG_RE = r"\s+(?:-\s+)?(ja|nein)\s*$"  # trailing yes/no flag of a candidate entry
TITLE = re.compile(r"^(\(FH\)|Mag|Dr|DI|Dipl|Ing|MSc|BSc|BA|MA|MBA|MAS|Prof|DDr|Mmag|MMag|FH|Bakk|Bed|BEd|MEd|LL\.?M|PhD)[\w.\-()]*$")


def parse(raw: str) -> tuple[list, int | None, str | None]:
    """Return (name tokens, birth year, yes/no flag) from 'Mag. Surname Firstname, 1955 - ja'.

    The order of surname and first name is not the same in every entry, so the tokens stay unordered."""
    yn = None
    m = re.search(FLAG_RE, raw, flags=re.I)
    if m:
        yn = m.group(1).lower()
        raw = raw[: m.start()]
    year = None
    m = re.search(r",\s*(\d{4})\s*$", raw)
    if m:
        year = int(m.group(1))
        raw = raw[: m.start()]
    toks = [t for t in raw.replace(",", " ").split() if not TITLE.match(t)]
    return toks, year, yn


def load(year: int) -> list[dict]:
    d = json.load(open(RAW / f"gv_{year}.json", encoding="utf-8-sig"))
    out = []
    for e in d[KEY_RESULTS]:
        b = e.get(KEY_MAYOR_ELECTION) or {}
        mode = b.get(KEY_MODE)
        cands = []
        for k in b.get(KEY_CANDIDATES, []):
            toks, by, yn = parse(k[KEY_NAME])
            if yn == FLAG_NO:
                continue
            cands.append({"toks": toks, "by": by, "votes": k[KEY_VOTES], "pct": k[KEY_PERCENT]})
        won = None
        if mode == MODE_SEVERAL_CANDIDATES:
            won = max(cands, key=lambda c: c["votes"])
        elif mode == MODE_ONE_CANDIDATE and cands and cands[0]["pct"] > 50:
            won = cands[0]
        out.append({"gkz": e[KEY_CODE], "n": e[KEY_COUNCIL_ELECTION][KEY_ELIGIBLE], "mayor_mode": mode,
                    "council_mode": e[KEY_COUNCIL_ELECTION][KEY_MODE],
                    "cands": cands if mode in (MODE_SEVERAL_CANDIDATES, MODE_ONE_CANDIDATE) else [], "won": won})
    return out


def first_names() -> list[str]:
    s = set()
    for y in (2020, 2025):
        for g in load(y):
            for c in g["cands"]:
                s.update(c["toks"])
    return sorted(s)


if __name__ == "__main__" and sys.argv[1:] == ["names"]:
    print("\n".join(first_names()))


def sex_table() -> dict:
    """First names with sex. The list holds personal data and is not published; without it every candidate counts as unclear."""
    if not NAMES.exists():
        print(f"{NAMES} not found, the share of women is not computed", file=sys.stderr)
        return {}
    with open(NAMES) as f:
        return {r["first_name"]: r["sex"] for r in csv.DictReader(f)}


def sex(c: dict, tab: dict) -> str:
    hits = {tab[t] for t in c["toks"] if t in tab}
    return hits.pop() if len(hits) == 1 else "unclear"


if __name__ == "__main__" and sys.argv[1:] == ["check"]:
    tab = sex_table()
    for y in (2020, 2025):
        for g in load(y):
            for c in g["cands"]:
                hits = [t for t in c["toks"] if t in tab]
                if len(hits) != 1:
                    print(y, g["gkz"], c["toks"], hits)


def same(c1: dict, c2: dict) -> bool:
    """Same person if one set of name tokens contains the other (a dropped second first name)."""
    s1, s2 = set(c1["toks"]), set(c2["toks"])
    return s1 <= s2 or s2 <= s1


def klass(n: int) -> str:
    cl = elections.CLASSES
    for lo, hi in zip(cl[:-1], cl[1:]):
        if lo <= n < hi:
            return f"{lo:,.0f}-{hi:,.0f}" if hi != float("inf") else f"{lo:,.0f}+"
    raise ValueError(n)


def main() -> None:
    tab = sex_table()
    data = {y: load(y) for y in (2020, 2025)}
    labels = [klass(lo) for lo in elections.CLASSES[:-1]]
    out = ["Mayoral elections Vorarlberg 2020 and 2025 by eligible voters of the council election", ""]
    for y, gs in data.items():
        out.append(f"{y}: {len(gs)} municipalities")
        out.append("class | municipalities | without direct election | candidates per direct election | female candidates/candidates (unclear) | elected women/elected (unclear)"
                   + (" | median age cand. | median age elected | elected under 40" if y == 2020 else ""))
        rows = [("all", gs)] + [(lab, [g for g in gs if klass(g["n"]) == lab]) for lab in labels]
        for lab, grp in rows:
            direct = [g for g in grp if g["cands"]]
            cands = [c for g in direct for c in g["cands"]]
            won = [g["won"] for g in direct if g["won"]]
            cs = [sex(c, tab) for c in cands]; ws = [sex(c, tab) for c in won]
            line = (f"{lab} | {len(grp)} | {len(grp) - len(direct)} | "
                    f"{len(cands) / len(direct):.2f} | " if direct else f"{lab} | {len(grp)} | {len(grp)} | - | ")
            line += f"{cs.count('f')}/{len(cs) - cs.count('unclear')} ({cs.count('unclear')}) | {ws.count('f')}/{len(ws) - ws.count('unclear')} ({ws.count('unclear')})"
            if y == 2020:
                ac = [y - c["by"] for c in cands if c["by"]]; aw = [y - c["by"] for c in won if c["by"]]
                line += (f" | {statistics.median(ac):.0f} | {statistics.median(aw):.0f} | {sum(a < 40 for a in aw)}/{len(aw)}"
                         if aw else " | - | - | -")
            out.append(line)
        nodir = sum(1 for g in gs if not g["cands"]); notwon = sum(1 for g in gs if g["cands"] and not g["won"])
        for lab, grp in rows:
            nd = [g for g in grp if not g["cands"]]
            out.append(f"  without direct election {lab}: {sum(g['council_mode'] == MODE_MAJORITY_VOTE for g in nd)} with majority vote for the council (no list), "
                       f"{sum(g['council_mode'] != MODE_MAJORITY_VOTE for g in nd)} with list vote, of which {sum(g['council_mode'] == MODE_ONE_LIST for g in nd)} with only one list")
        out.append(f"  direct election without winner (sole candidate at most 50 % yes): {notwon}; without direct election: {nodir}")
        out.append("  more than one candidate: " + "  ".join(f"{lab} {sum(g['mayor_mode'] == MODE_SEVERAL_CANDIDATES for g in grp)}/{len(grp)}" for lab, grp in rows))
        out.append("")
    a = {g["gkz"]: g for g in data[2020]}; b = {g["gkz"]: g for g in data[2025]}
    both = [k for k in a if k in b and a[k]["won"] and b[k]["won"]]
    out.append(f"change in office 2020 to 2025, municipalities with a directly elected mayor in both years: {len(both)} (left out {len(a) - len(both)})")
    out.append("class (2025) | municipalities | change | of which only one candidate in 2025")
    for lab in ["all"] + labels:
        ks = [k for k in both if lab == "all" or klass(b[k]["n"]) == lab]
        ch = [k for k in ks if not same(a[k]["won"], b[k]["won"])]
        one = sum(1 for k in ch if b[k]["mayor_mode"] == MODE_ONE_CANDIDATE)
        out.append(f"{lab} | {len(ks)} | {len(ch)} | {one}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "mayors.txt").write_text(text + "\n")


if __name__ == "__main__" and not sys.argv[1:]:
    main()
