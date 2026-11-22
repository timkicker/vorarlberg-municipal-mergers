"""Party lists against local lists in the Vorarlberg municipal elections 2025 and 2020, by size.

Writes data/derived/party_labels.txt.
"""

import json
import pathlib
import re
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW, DER = ROOT / "data" / "raw", ROOT / "data" / "derived"
# Party names as they appear in list names of the source; a match marks a list with a party label.
PARTY = re.compile(r"ÖVP|Volkspartei|FPÖ|Freiheitlich|SPÖ|Sozialdemokrat|Grüne|NEOS|KPÖ|Kommunistisch", re.I)
STRONGEST_PARTY = re.compile(r"ÖVP|Volkspartei", re.I)  # list names of one party, counted in the last column
# Keys and values of gv_YYYY.json, the municipal election results of the state of Vorarlberg (open data).
KEY_RESULTS = "ergebnisse"  # list of municipalities
KEY_COUNCIL_ELECTION = "gemeinderatswahl"  # council election block
KEY_ELIGIBLE = "wahlberechtigte"  # eligible voters
KEY_MODE = "wahlart"  # election mode
KEY_LISTS = "listen"  # lists standing
KEY_LIST_NAME = "bezeichnung"  # name of a list
KEY_VOTES = "stimmen"  # votes of a list
MODE_SEVERAL_LISTS = "mehrereListen"  # several lists
MODE_ONE_LIST = "eineListe"  # only one list
MODE_MAJORITY_VOTE = "mehrheitswahl"  # majority vote, no list
BINS = ((0, 750), (750, 1500), (1500, 3000), (3000, 7500), (7500, float("inf")))
KINDS = (MODE_SEVERAL_LISTS, MODE_ONE_LIST, MODE_MAJORITY_VOTE)


def label(lo, hi):
    return f"from {lo:,}" if hi == float("inf") else f"{lo:,} to under {hi:,}"


def year(y: int, lines: list) -> None:
    d = json.loads((RAW / f"gv_{y}.json").read_text(encoding="utf-8-sig"))
    rows = [e[KEY_COUNCIL_ELECTION] for e in d[KEY_RESULTS]]
    lines.append(f"{y}: {len(rows)} municipalities")
    lines.append("  eligible voters | municipalities | several lists / one list / majority vote | mean lists | lists with party label | votes for party labels | strongest list with party label | list with ÖVP or Volkspartei")
    for lo, hi in BINS + ((0, float("inf")),):
        g = [r for r in rows if lo <= r[KEY_ELIGIBLE] < hi]
        kinds = " / ".join(str(sum(r[KEY_MODE] == k for r in g)) for k in KINDS)
        wl = [r for r in g if r.get(KEY_LISTS)]
        lists = [li for r in wl for li in r[KEY_LISTS]]
        n_party = sum(bool(PARTY.search(li[KEY_LIST_NAME])) for li in lists)
        votes = sum(li[KEY_VOTES] for li in lists)
        v_party = sum(li[KEY_VOTES] for li in lists if PARTY.search(li[KEY_LIST_NAME]))
        top = sum(bool(PARTY.search(max(r[KEY_LISTS], key=lambda li: li[KEY_VOTES])[KEY_LIST_NAME])) for r in wl)
        strongest = sum(any(STRONGEST_PARTY.search(li[KEY_LIST_NAME]) for li in r[KEY_LISTS]) for r in wl)
        name = "all" if hi == float("inf") and lo == 0 else label(lo, hi)
        mean = statistics.mean(len(r[KEY_LISTS]) for r in wl) if wl else 0
        lines.append(
            f"  {name} | {len(g)} | {kinds} | {mean:.1f} | {n_party}/{len(lists)} | {v_party / votes:.0%} | {top}/{len(wl)} | {strongest}/{len(wl)}"
        )
    lines.append("")


def main() -> None:
    lines = ["Party lists and local lists by municipal size (party_labels.py)", ""]
    for y in (2025, 2020):
        year(y, lines)
    text = "\n".join(lines)
    print(text)
    (DER / "party_labels.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
