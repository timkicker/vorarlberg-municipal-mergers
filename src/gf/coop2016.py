"""Parse the cooperation table of the 2016 study into records and memberships.

Source: Bussjaeger, Hornsteiner, Keuschnigg (2016), study on inter-municipal
cooperation in Vorarlberg, table appendix on PDF pages 79 to 116 (266 records).

The table has no ruling lines and every cell is vertically centred on its row,
so lines of a long cell sit above and below the row number. Records are found
by vertical whitespace instead: across all columns the line pitch inside a
record is at most 12 pt, the gap between records is 16 pt (measured over all
38 pages). A block without a record number continues the last record of the
previous page.
"""

import csv
import json
import pathlib
import re
import sys

import pdfplumber

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"

COLS = {"id": (55, 105), "name": (105, 225), "type": (225, 290), "short": (290, 410), "legal_form": (410, 555), "municipalities": (555, 900)}
PAGES = range(78, 116)  # zero based, PDF pages 79 to 116
COL_MUNICIPALITY = "gemeinde"  # municipality name column in vbg_regional_divisions.csv of data.vorarlberg.gv.at
# member cell text in the study that means the members keep changing
CHANGING_MEMBERS = "wechseln ständig"
# separators in the member column: comma and the German word for "and"
MEMBER_SEPARATORS = r",|\bund\b"

# Spelling in the source that maps to an official name (vbg_regional_divisions.csv).
# Each entry was checked by hand against the PDF.
ALIAS = {
    "St.Anton i. M": "St. Anton im Montafon",
    "St. Anton i. M": "St. Anton im Montafon",
    "St. Anton i.M": "St. Anton im Montafon",
    "St. Abnton i.M": "St. Anton im Montafon",
    "St.Anton": "St. Anton im Montafon",
    "St. Anton": "St. Anton im Montafon",
    "St. Anton im Montafon": "St. Anton im Montafon",
    "St Gallenkirch": "St. Gallenkirch",
    "St.Gallenkirch": "St. Gallenkirch",
    "St Gerold": "St. Gerold",
    "St.Gerold": "St. Gerold",
    "Langen": "Langen bei Bregenz",
    "Langen b. Bregenz": "Langen bei Bregenz",
    "Langen b. Br": "Langen bei Bregenz",
    "Klösterle am Arlberg": "Klösterle",
    "Warth am Arlberg": "Warth",
    "Schwarzenberg im Bregenzerwald": "Schwarzenberg",
    "Mittelberg-Riezlern": "Mittelberg",
    "Frstanz": "Frastanz",
    "Bartolomähberg": "Bartholomäberg",
    "Langegg": "Langenegg",
    "Sibragsgfäll": "Sibratsgfäll",
    "Thrüingerberg": "Thüringerberg",
    "Bürerberg": "Bürserberg",
    "Rötzis": "Röthis",  # alphabetical position between Reuthe and Satteins; Götzis is listed separately
    "Eichenb erg": "Eichenberg",
    "Zwischenwasse": "Zwischenwasser",
    "St. Anton iM": "St. Anton im Montafon",
    "Fontanella- Faschina": "Fontanella",
    "Raggal-Marul": "Raggal",
    # villages named instead of their municipality
    "Braz": "Innerbraz",
    "Riezlern": "Mittelberg",
    "Hirschegg": "Mittelberg",
}

# Members that are organisations, not municipalities. They are dropped and logged.
NOT_MUNICIPAL = {
    "Regionalentwicklung Bregenzerwald GmbH",
    "Regio Bregenzerwald",
    "Regio Vorderland",
    "LEADER Region",
    "ARA Meiningen",
    "Finanzverwaltung Vorderland",
    CHANGING_MEMBERS,
}

# Records whose member list is not in the member column. Read by hand from the PDF.
OVERRIDE = {
    263: (["Bregenz", "Lauterach", "Bludenz", "Nüziders", "Bürs"], "members only in the short description, examples: Bregenz for Lauterach, Bludenz for Nüziders and Dürs (= Bürs)"),
}
# member cell texts in the study that mean every municipality
ALL_MUNICIPALITIES = {"alle Gemeinden", "Vorarlberger Gemeindeverband (=alle Gemeinden)"}
STAND_MONTAFON = 198  # record whose member list defines "Stand Montafon"


def lines(words, lo, hi):
    """Words in [lo, hi) grouped into text lines by their top coordinate."""
    ws = sorted((w for w in words if lo <= w["x0"] < hi), key=lambda w: (round(w["top"]), w["x0"]))
    out = []
    for w in ws:
        if out and abs(out[-1]["top"] - w["top"]) < 3:
            out[-1]["text"] += " " + w["text"]
        else:
            out.append({"top": w["top"], "text": w["text"]})
    return out


GAP = 14  # pt; line pitch inside a record is 6 to 12, between records 16


def segments(words):
    """Split a page into records at vertical gaps wider than GAP across all columns."""
    ws = sorted(words, key=lambda w: w["top"])
    out = []
    for w in ws:
        if out and w["top"] - out[-1][-1]["top"] <= GAP:
            out[-1].append(w)
        else:
            out.append([w])
    return out


def join(grp):
    text = ""
    for l in grp:
        t = l["text"]
        if text.endswith("-") and t[:1].islower():
            text = text[:-1] + t
        else:
            text = (text + " " + t).strip()
    return text


def split_missing_commas(p, known):
    """'Feldkirch Frastanz' -> ['Feldkirch', 'Frastanz'] if every piece is known."""
    for sep in (". ", " "):
        if sep not in p:
            continue
        toks = p.split(sep)
        out, cur = [], ""
        for tok in toks:
            cur = (cur + " " + tok).strip() if cur else tok
            name = ALIAS.get(cur, cur)
            if name in known:
                out.append(name)
                cur = ""
        if not cur and len(out) > 1:
            return out
    return None


def members(rec, known, by_id, log):
    if rec["id"] in OVERRIDE:
        ms, why = OVERRIDE[rec["id"]]
        log.append((rec["id"], "override", why))
        return ms, []
    text = re.sub(r";", ",", rec["municipalities"]).replace("St, ", "St. ")  # record 84
    out, unknown = [], []
    for part in re.split(MEMBER_SEPARATORS, text):
        p = re.sub(r"\s+", " ", part).strip(" .")
        if not p:
            continue
        if p in ALL_MUNICIPALITIES or rec["municipalities"].strip() in ALL_MUNICIPALITIES:
            log.append((rec["id"], "all", p))
            return sorted(known), []
        if p == "Stand Montafon":
            log.append((rec["id"], "stand_montafon", f"members as record {STAND_MONTAFON}"))
            out.extend(by_id[STAND_MONTAFON])
            continue
        if p in NOT_MUNICIPAL:
            log.append((rec["id"], "not_municipality", p))
            continue
        name = ALIAS.get(p, p)
        if name != p:
            log.append((rec["id"], "alias", f"{p} -> {name}"))
        if name in known:
            out.append(name)
            continue
        parts = split_missing_commas(p, known)
        if parts:
            log.append((rec["id"], "comma", f"{p} -> {parts}"))
            out.extend(parts)
        else:
            unknown.append(p)
    return list(dict.fromkeys(out)), unknown


def main() -> None:
    known = {r[COL_MUNICIPALITY]: r["gkz"] for r in csv.DictReader((RAW / "vbg_regional_divisions.csv").open(encoding="utf-8"), delimiter=";")}
    pdf = pdfplumber.open(RAW / "ikz_study_2016.pdf")
    recs = []
    for pn in PAGES:
        p = pdf.pages[pn]
        words = [w for w in p.extract_words() if w["top"] > 110 or pn != 78]
        words = [w for w in words if w["top"] < p.height - 60]  # page number at the foot
        for seg in segments(words):
            ids = [w for w in seg if COLS["id"][0] <= w["x0"] < COLS["id"][1] and re.fullmatch(r"\d{1,3}", w["text"])]
            if len(ids) > 1:
                raise SystemExit(f"page {pn + 1}: several IDs in one block: {[w['text'] for w in ids]}")
            cells = {col: join(lines(seg, lo, hi)) for col, (lo, hi) in COLS.items() if col != "id"}
            if ids:
                recs.append({"id": int(ids[0]["text"]), "page": pn + 1, **cells})
            elif recs:  # record continued from the previous page
                for col, v in cells.items():
                    recs[-1][col] = (recs[-1][col] + " " + v).strip()
                recs[-1].setdefault("continued", []).append(pn + 1)
    OUT.mkdir(parents=True, exist_ok=True)
    problems, log, by_id = [], [], {}
    order = sorted(recs, key=lambda r: r["id"] != STAND_MONTAFON)  # resolve the reference first
    for r in order:
        ms, unk = members(r, known, by_id, log)
        r["members"], r["unknown"] = ms, unk
        by_id[r["id"]] = ms
        if unk or len(ms) < 2:
            problems.append(r)
    with (OUT / "coop2016_members.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["coop_id", "gkz", "municipality"])
        for r in recs:
            for m in r["members"]:
                w.writerow([r["id"], known[m], m])
    with (OUT / "coop2016_corrections.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["coop_id", "kind", "detail"])
        w.writerows(sorted(log, key=lambda x: x[0]))
    problems.sort(key=lambda r: r["id"])
    (OUT / "coop2016.json").write_text(json.dumps(recs, ensure_ascii=False, indent=1))
    ids = [r["id"] for r in recs]
    print("records", len(recs), "IDs without gaps", ids == list(range(1, len(recs) + 1)))
    print("corrections", len(log), "memberships", sum(len(r["members"]) for r in recs))
    print("problems", len(problems))
    for r in problems:
        print(f" {r['id']:>3} p.{r['page']} {r['name'][:40]!r} | {r['municipalities'][:90]!r} | unknown {r['unknown']}")


if __name__ == "__main__":
    sys.exit(main())
