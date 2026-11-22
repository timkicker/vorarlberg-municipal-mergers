"""Core administration costs of the Montafon municipalities before and after their joint finance
administration (August 2017), against the other Vorarlberg municipalities.

Run from the repository root. Writes data/derived/coop_montafon.txt.
"""

import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402

s.YEARS = tuple(range(2010, 2020))
YEARS = tuple(t for t in s.YEARS if t != 2017)
POST = (2018, 2019)
BASE, REF = 2016, 2016
TREATED = {"Bartholomäberg", "Gaschurn", "Lorüns", "St. Anton im Montafon", "St. Gallenkirch", "Schruns",
           "Silbertal", "Tschagguns", "Vandans"}
N_PERM, SEED = 2000, 12345


def design(us: list, col: int, years: tuple, event: bool):
    T = len(years)
    unit = np.repeat(np.arange(len(us)), T)
    yr = np.tile(np.array(years), len(us))
    y = np.log(np.concatenate([[u["y"][t][col] / u["y"][t][2] for t in years] for u in us]))
    grp = np.repeat([u["group"] for u in us], T)
    fe = [((grp == g) & (yr == t)).astype(float) for g in sorted(set(grp)) for t in years[1:]]
    return y, fe, unit, yr


def did(us: list, treated: np.ndarray, col: int) -> float:
    y, fe, unit, yr = design(us, col, YEARS, False)
    tr = np.repeat(treated.astype(float), len(YEARS))
    X = np.column_stack([tr * np.isin(yr, POST)] + fe)
    return s.twfe(y, X, unit)[0]


def event(us: list, treated: np.ndarray, col: int) -> list:
    y, fe, unit, yr = design(us, col, YEARS, True)
    tr = np.repeat(treated.astype(float), len(YEARS))
    ks = [t for t in YEARS if t != BASE]
    X = np.column_stack([tr * (yr == t) for t in ks] + fe)
    return list(zip(ks, s.twfe(y, X, unit)[:len(ks)]))


def main() -> None:
    m, pop = s.money()
    name = {r["gkz"]: r["municipality"] for r in csv.DictReader(open(s.OUT / "pareto_partitions.csv", encoding="utf-8"))}
    us = []
    for g, n in sorted(name.items()):
        if n == "Stallehr" or not all((g, t) in pop and (g, t) in m for t in s.YEARS):
            continue
        if pop[(g, REF)] >= 10000 and n not in TREATED:
            continue
        ys = {t: (m[(g, t)][0], m[(g, t)][1], pop[(g, t)]) for t in s.YEARS}
        if all(v[0] > 0 for v in ys.values()):
            us.append({"id": g, "name": n, "y": ys, "treated": n in TREATED})
    cuts = np.quantile([u["y"][REF][2] for u in us], [1 / 3, 2 / 3])
    for u in us:
        u["group"] = int(np.searchsorted(cuts, u["y"][REF][2]))
    tr = np.array([u["treated"] for u in us])
    ctrl = np.where(~tr)[0]
    missing = sorted(TREATED - {u["name"] for u in us if u["treated"]})
    out = ["Joint finance administration Montafon 2017: core administration before and after (coop_montafon.py)",
           f"municipalities {len(us)}, treated {int(tr.sum())}, missing among the treated: {missing or 'none'}",
           "years 2010-2016 and 2018-2019 (2017 left out), municipality FE and year x size third 2016", ""]
    rng = np.random.default_rng(SEED)
    for col, label in ((0, "net"), (1, "gross")):
        b = did(us, tr, col)
        perm = []
        for _ in range(N_PERM):
            fake = np.zeros(len(us), bool)
            fake[rng.choice(ctrl, int(tr.sum()), replace=False)] = True
            perm.append(did(us, fake, col))
        perm = np.array(perm)
        out.append(f"core administration {label}, log per inhabitant: effect {b:+.3f}; placebo effects 2.5-97.5 % [{np.percentile(perm, 2.5):+.3f}, "
                   f"{np.percentile(perm, 97.5):+.3f}]; share |placebo| >= |effect| {np.mean(np.abs(perm) >= abs(b)):.3f}")
        out.append("  event study, reference 2016: " + ", ".join(f"{t} {v:+.3f}" for t, v in event(us, tr, col)))
    text = "\n".join(out)
    print(text)
    (s.OUT / "coop_montafon.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
