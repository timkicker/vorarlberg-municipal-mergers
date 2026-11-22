"""Scale factor with effect and cross-section prediction weighted alike.

Writes data/derived/scale_weighted.txt.
"""

import pathlib
import re
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_clean_controls as cc  # noqa: E402


def effect_after(path: pathlib.Path, head: str) -> float:
    """Log effect on the first "Effect log" line after the line starting with head."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, x in enumerate(lines) if x.strip().startswith(head))
    line = next(x for x in lines[start:] if "Effect log" in x)
    return float(re.search(r"Effect log ([-+][\d.]+)", line).group(1))


def curve_prediction() -> float:
    """Unweighted cost-curve prediction for the merged units as printed by styria.py."""
    text = (s.OUT / "styria.txt").read_text(encoding="utf-8")
    return float(re.search(r"Cost curve prediction for the treated units: log ([-+][\d.]+)", text).group(1))


def main() -> None:
    curve = np.loadtxt(s.OUT / "cost_curve_net.csv", delimiter=",", skiprows=1)
    lc = lambda p: np.interp(np.log(p), np.log(curve[:, 0]), np.log(curve[:, 1]))  # noqa: E731
    main_effect = effect_after(s.OUT / "styria_clean_controls.txt", "Main cleaned")
    weighted_effect = effect_after(s.OUT / "styria.txt", "Main weighted")
    units, _, _ = cc.build()
    preds, w = [], []
    for u in units:
        if u["treated"]:
            ps = np.array([p for _, p in u["pred"]], float)
            before = np.log(np.sum(ps * np.exp(lc(ps))) / ps.sum())
            preds.append(lc(ps.sum()) - before)
            w.append(ps.sum())
    preds, w = np.array(preds), np.array(w)
    pu, pw = preds.mean(), np.average(preds, weights=w)
    out = ["Scale factor with numerator and denominator weighted alike (scale_weighted.py)",
           f"merged units {len(preds)}, population 2014 {w.sum():,.0f}",
           f"prediction of the cost curve unweighted: log {pu:+.4f} (styria.py: {curve_prediction():+.3f})",
           f"prediction of the cost curve weighted by population 2014: log {pw:+.4f}", "",
           f"factor unweighted, cleaned main run: {main_effect:+.4f} / {pu:+.3f} = {main_effect / pu:.3f}",
           f"factor weighted (effect not cleaned, weighted): {weighted_effect:+.3f} / {pw:+.3f} = {weighted_effect / pw:.3f}",
           f"for comparison, weighted effect over unweighted prediction: {weighted_effect:+.3f} / {pu:+.3f} = {weighted_effect / pu:.2f}"]
    text = "\n".join(out)
    print(text)
    (s.OUT / "scale_weighted.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
