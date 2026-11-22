"""Commuter flows of the 96 municipalities, commuter atlas of Statistics Austria, 31.10.2024.

Source is the register-based labour market statistics 2024 (layer ATLAS_PENDLER_CONFIG).
The list layer gives every destination of the out-commuters of one
municipality. Destination geo_id "8" is abroad: the atlas front end defines
code_ausl = '00008' and labels it as abroad (js/globals_ui.js,
js/uiHelper.js). The info layer gives out-commuters, in-commuters and non-commuters
per municipality; non-commuters are employed residents working in their own municipality
and fill the diagonal of the flow matrix.
"""

import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "commuters_2024_raw"
OUT = ROOT / "data" / "derived"
ABROAD = "abroad"
# fields of the info layer of the commuter atlas
KEY_OUT = "ausp"  # out-commuters
KEY_IN = "einp"  # in-commuters
KEY_NON = "nichtp"  # employed residents who work in their own municipality


def props(path: pathlib.Path) -> list[dict]:
    return [f["properties"] for f in json.loads(path.read_text())["features"]]


def main() -> None:
    gkz = [r["gkz"] for r in csv.DictReader((ROOT / "data/raw/vbg_regional_divisions.csv").open(encoding="utf-8"), delimiter=";")]
    flows, info, errors = [], {}, []
    for g in gkz:
        (i,) = props(RAW / f"info_{g}.json")
        assert i["geo_id"] == g
        info[g] = {k: int(i[k]) for k in (KEY_OUT, KEY_IN, KEY_NON)}
        dest = props(RAW / f"ausp_{g}.json")
        total = sum(d["v1"] for d in dest)
        if total != info[g][KEY_OUT]:
            errors.append(f"{g}: list {total}, {KEY_OUT} {info[g][KEY_OUT]}")
        for d in dest:
            to = ABROAD if d["geo_id"] == "8" else d["geo_id"]
            assert to == ABROAD or (len(to) == 5 and to != g), d
            flows.append((g, to, d["v1"]))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "commuters_2024.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["from_gkz", "to", "count"])
        w.writerows(sorted(flows))
    with (OUT / "commuters_2024_municipalities.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gkz", "out_commuters", "in_commuters", "non_commuters"])
        for g in gkz:
            w.writerow([g, info[g][KEY_OUT], info[g][KEY_IN], info[g][KEY_NON]])
    inside = {g for g in gkz}
    into = {g: 0 for g in gkz}
    for _a, b, n in flows:
        if b in inside:
            into[b] += n
    over = [g for g in gkz if into[g] > info[g][KEY_IN]]
    by = lambda pred: sum(n for a, b, n in flows if pred(b))  # noqa: E731
    print("flows", len(flows), f"difference list/{KEY_OUT}", errors or "none")
    print(f"in-commuters from Vbg larger than {KEY_IN}:", over or "never")
    print("out-commuters total", sum(n for *_, n in flows), "of these to Vbg", by(lambda b: b in inside), "abroad", by(lambda b: b == ABROAD), "rest of AT", by(lambda b: b not in inside and b != ABROAD))
    print("non-commuters total", sum(v[KEY_NON] for v in info.values()))


if __name__ == "__main__":
    sys.exit(main())
