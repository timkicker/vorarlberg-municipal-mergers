"""Electoral competition and municipal size, Vorarlberg 2020 and 2025.

The logistic fit carries an L2 penalty of 1e-4 on the slope only as a numerical guard
against separation in bootstrap draws.
"""

import csv
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
N_BOOT, SEED = 2000, 12345
CLASSES = (0, 750, 1500, 3000, 7500, np.inf)
# keys and values of the election result files of apps.vorarlberg.at/wahlen
KEY_RESULTS = "ergebnisse"  # results per municipality
KEY_CODE = "schluessel"  # municipality code
KEY_COUNCIL = "gemeinderatswahl"  # municipal council election
KEY_MAYOR = "buergermeisterwahl"  # mayoral election
KEY_ELECTORATE = "wahlberechtigte"  # eligible voters
KEY_MODE = "wahlart"  # kind of election
MODE_SEVERAL_LISTS = "mehrereListen"  # more than one list
MODE_SEVERAL_CANDIDATES = "mehrereKandidaten"  # more than one candidate


def load(year: int) -> list[dict]:
    d = json.loads((RAW / f"gv_{year}.json").read_text(encoding="utf-8-sig"))[KEY_RESULTS]
    return [{
        "gkz": e[KEY_CODE],
        "w": e[KEY_COUNCIL][KEY_ELECTORATE],
        "A": int(e[KEY_COUNCIL][KEY_MODE] == MODE_SEVERAL_LISTS),
        "B": int((e.get(KEY_MAYOR) or {}).get(KEY_MODE) == MODE_SEVERAL_CANDIDATES),
    } for e in d]


def logit(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    X = np.column_stack([np.ones_like(x), x])
    b = np.zeros(2)
    pen = np.diag([0.0, 1e-4])
    for _ in range(100):
        p = 1 / (1 + np.exp(-X @ b))
        g = X.T @ (y - p) - pen @ b
        H = X.T @ (X * (p * (1 - p))[:, None]) + pen
        step = np.linalg.solve(H, g)
        b += step
        if np.abs(step).max() < 1e-10:
            break
    return b


def at(b: np.ndarray, p: float) -> float:
    return float(np.exp((np.log(p / (1 - p)) - b[0]) / b[1]))


def main() -> None:
    rng = np.random.default_rng(SEED)
    lines, models = [], {}
    for year in (2025, 2020):
        rows = load(year)
        x = np.log([r["w"] for r in rows])
        lines.append(f"\n{year}: {len(rows)} municipalities")
        for out in ("A", "B"):
            y = np.array([r[out] for r in rows], float)
            b = logit(x, y)
            bs = []
            for _ in range(N_BOOT):
                i = rng.integers(0, len(y), len(y))
                bs.append(logit(x[i], y[i]))
            bs = np.array(bs)
            models[(year, out)] = b
            cls = []
            for lo, hi in zip(CLASSES, CLASSES[1:]):
                m = [r[out] for r in rows if lo <= r["w"] < hi]
                cls.append(f"{lo:,.0f}-{hi:,.0f}: {sum(m)}/{len(m)}")
            s_lo, s_hi = np.percentile(bs[:, 1], [2.5, 97.5])
            verdict = "slope > 0" if s_lo > 0 else "slope < 0" if s_hi < 0 else "undecided"
            p50 = [at(v, 0.5) for v in bs if v[1] > 0]
            p90 = [at(v, 0.9) for v in bs if v[1] > 0]
            lines.append(f"  {out}: share {y.mean():.2f}; by eligible voters {'; '.join(cls)}")
            lines.append(f"     slope {b[1]:+.2f}  95 % [{s_lo:+.2f}, {s_hi:+.2f}]  {verdict}")
            if b[1] > 0:
                lines.append(f"     50 % at {at(b, 0.5):,.0f} eligible voters (95 % {np.percentile(p50, 2.5):,.0f} to {np.percentile(p50, 97.5):,.0f}), 90 % at {at(b, 0.9):,.0f} ({np.percentile(p90, 2.5):,.0f} to {np.percentile(p90, 97.5):,.0f})")

    # link to the Pareto variants, model 2025, outcome A
    rows = {r["gkz"]: r for r in load(2025)}
    b = models[(2025, "A")]
    tot = sum(r["w"] for r in rows.values())
    observed = sum(r["w"] for r in rows.values() if not r["A"]) / tot
    lines.append(f"\nStatus quo 2025: {observed:.1%} of eligible voters live in municipalities without a contested council election (observed)")
    zs = list(csv.DictReader((OUT / "pareto_partitions.csv").open(encoding="utf-8")))
    lines.append("Model 2025, share of eligible voters without a contested election, predicted:")
    for col in [c for c in zs[0] if c not in ("gkz", "municipality")]:
        units = {}
        for r in zs:
            units[r[col]] = units.get(r[col], 0) + rows[r["gkz"]]["w"]
        w = np.array(list(units.values()), float)
        p = 1 / (1 + np.exp(-(b[0] + b[1] * np.log(w))))
        if col.startswith("Intramax") and int(col.split("=")[1]) not in (4, 8, 10, 19, 30, 40, 50, 60, 70, 80, 90):
            continue
        lines.append(f"  {col:34} {len(w):>3} units  {np.sum(w * (1 - p)) / w.sum():.1%}")
    text = "\n".join(lines)
    print(text)
    (OUT / "elections.txt").write_text(text.strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
