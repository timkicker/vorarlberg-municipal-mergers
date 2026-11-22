"""Street names that would occur twice in a merged municipality and the addresses on them.

Run from the repository root.
Data: Austrian address register (BEV), reference date data of 01.04.2026.
Writes data/derived/street_names.txt.
"""

import collections
import csv
import io
import sys
import zipfile

import fag

ZIP = fag.DER.parent / "raw" / "bev_address_register_20260401.zip"
CUTS = ("Threshold 2000", "Threshold 3500", "Threshold 5000", "official planning region")
ADDRESS_REGISTER_NOTICE = "© Österreichisches Adressregister"  # mandatory attribution of the BEV address register licence
FILE_STREETS = "STRASSE.csv"  # street table in the BEV address register zip
FILE_ADDRESSES = "ADRESSE.csv"  # address table in the BEV address register zip
COL_STREET_NAME = "STRASSENNAME"  # column in STRASSE.csv of the BEV address register
COL_DELIVERY_PLACE = "ZUSTELLORT"  # column in STRASSE.csv of the BEV address register
COL_STREET_CODE = "SKZ"  # street code, in STRASSE.csv and ADRESSE.csv
COL_MUNICIPALITY_CODE = "GKZ"  # municipality code, in STRASSE.csv and ADRESSE.csv


def table(z: zipfile.ZipFile, name: str):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";")


def main() -> None:
    z = zipfile.ZipFile(ZIP)
    rows = list(csv.DictReader(open(fag.DER / "pareto_partitions.csv", encoding="utf-8")))
    name = {r["gkz"]: r["municipality"] for r in rows}
    streets = {r[COL_STREET_CODE]: r for r in table(z, FILE_STREETS) if r[COL_MUNICIPALITY_CODE].startswith("8")}
    addr = collections.Counter(r[COL_STREET_CODE] for r in table(z, FILE_ADDRESSES) if r[COL_MUNICIPALITY_CODE].startswith("8"))
    per = collections.defaultdict(lambda: collections.Counter())  # gkz -> name -> addresses
    count = collections.defaultdict(collections.Counter)  # gkz -> name -> streets
    for skz, s in streets.items():
        n = s[COL_STREET_NAME].strip().lower()
        per[s[COL_MUNICIPALITY_CODE]][n] += addr[skz]
        count[s[COL_MUNICIPALITY_CODE]][n] += 1
    addr_g = {g: sum(c.values()) for g, c in per.items()}
    inner = {g: [n for n, k in c.items() if k > 1] for g, c in count.items()}
    other_place = sum(1 for s in streets.values() if s[COL_DELIVERY_PLACE].strip().lower() != name.get(s[COL_MUNICIPALITY_CODE], "").strip().lower())
    out = ["Duplicate street names per partition (street_names.py)",
           f"{ADDRESS_REGISTER_NOTICE}, reference date data of 01.04.2026", "",
           f"streets {len(streets):,}, addresses {sum(addr_g.values()):,}, municipalities with streets {len(per)} of {len(name)}", "",
           "1. today",
           f"  municipalities with a name more than once: {sum(1 for v in inner.values() if v)}, duplicate names together {sum(len(v) for v in inner.values())}",
           "  " + ", ".join([f"{name.get(g, g)} {len(v)}" for g, v in sorted(inner.items(), key=lambda x: -len(x[1])) if v][:10]),
           f"  streets with delivery place unlike the municipality name: {other_place:,}", "",
           "2. per partition (only units with a merger)",
           "  partition | units | duplicate names | addresses to rename | share of the addresses of the units | most frequent names (municipalities)"]
    for cut in CUTS:
        units = collections.defaultdict(list)
        for r in rows:
            units[r[cut]].append(r["gkz"])
        multi = [m for m in units.values() if len(m) > 1]
        dup, moved, base = 0, 0, 0
        freq = collections.Counter()
        for m in multi:
            base += sum(addr_g.get(g, 0) for g in m)
            names = collections.defaultdict(list)
            for g in m:
                for n, a in per[g].items():
                    names[n].append(a)
            for n, al in names.items():
                if len(al) > 1:
                    dup += 1
                    moved += sum(al) - max(al)
                    freq[n] += len(al)
        top = ", ".join(f"{n} {k}" for n, k in freq.most_common(5))
        out.append(f"  {cut} | {len(multi)} | {dup:,} | {moved:,} | {moved / base:.1%} | {top}")
    text = "\n".join(out)
    print(text)
    (fag.DER / "street_names.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
