"""How different the partners of a merged unit are politically, from the state election 2024.

Writes data/derived/dissimilarity.txt.
"""

import collections
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tourism  # noqa: E402

RAW, DER = tourism.RAW, tourism.DER
# keys of lt_2024.json of apps.vorarlberg.at/wahlen
KEY_RESULTS = "ergebnisse"  # results per municipality
KEY_CODE = "schluessel"  # municipality code
KEY_PARTIES = "parteien"  # parties
KEY_PARTY_ID = "parteiID"  # party id
KEY_SHORT_NAME = "kurzbezeichnung"  # short name of the party
KEY_VOTES = "stimmen"  # votes


def votes() -> tuple[dict, dict]:
    d = json.loads((RAW / "lt_2024.json").read_text(encoding="utf-8-sig"))
    short = {p[KEY_PARTY_ID]: p[KEY_SHORT_NAME] for p in d[KEY_PARTIES]}
    out = {}
    for e in d[KEY_RESULTS]:
        out[e[KEY_CODE]] = {short[p[KEY_PARTY_ID]]: float(p[KEY_VOTES]) for p in e[KEY_PARTIES]}
    return out, short


def shares(v: dict) -> dict:
    s = sum(v.values())
    return {k: x / s for k, x in v.items()}


def dist(a: dict, b: dict) -> float:
    sa, sb = shares(a), shares(b)
    return 0.5 * sum(abs(sa.get(k, 0.0) - sb.get(k, 0.0)) for k in set(sa) | set(sb))


def top(v: dict) -> str:
    return max(v, key=v.get)


def main() -> None:
    v, _ = votes()
    names = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(DER / "pareto_partitions.csv"))}
    mun = {g: v[g] for g in names}
    state = collections.Counter()
    for x in mun.values():
        state.update(x)
    tot = {g: sum(x.values()) for g, x in mun.items()}
    ref = sum(tot[g] * dist(mun[g], state) for g in mun) / sum(tot.values())
    lines = ["Political dissimilarity of the partners, state election 2024 without postal votes (dissimilarity.py)", ""]
    lines.append(f"comparison, each municipality against the state, weighted: {ref:.3f}")
    lines.append("")
    lines.append("partition | units | mean against the unit | ratio to the state value | vote share with another first list | three most different predecessors")
    for cut, us in tourism.units().items():
        w = s = flip = 0.0
        each = []
        for gs in us:
            unit = collections.Counter()
            for g in gs:
                unit.update(mun[g])
            for g in gs:
                d = dist(mun[g], unit)
                each.append((d, names[g]))
                w += tot[g]
                s += tot[g] * d
                flip += tot[g] * (top(mun[g]) != top(unit))
        each.sort(reverse=True)
        worst = ", ".join(f"{n} {d:.2f}" for d, n in each[:3])
        lines.append(f"  {cut} | {len(us)} | {s / w:.3f} | {s / w / ref:.2f} | {flip / w:.0%} | {worst}")
    text = "\n".join(lines)
    print(text)
    (DER / "dissimilarity.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
