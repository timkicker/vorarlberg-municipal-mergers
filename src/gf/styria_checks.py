"""All Styrian checks on one panel, without the four controls whose area changed.

Writes data/derived/styria_checks.txt.
"""

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import styria as s  # noqa: E402
import styria_clean_controls as c  # noqa: E402


def thirds(us: list) -> None:
    cuts = np.quantile([u["y"][s.REF][2] for u in us], [1 / 3, 2 / 3])
    for u in us:
        u["group"] = int(np.searchsorted(cuts, u["y"][s.REF][2]))


def main() -> None:
    units, others, m = c.build()
    found, _ = c.changed(units, m)
    clean = [u for u in units if u["id"] not in found]
    assert len(clean) == 275 and sum(u["treated"] for u in clean) == 123, (len(clean), sum(u["treated"] for u in clean))
    no14 = {"years": tuple(t for t in s.YEARS if t != 2014), "ref": 2013}

    styr = [dict(u) for u in clean]
    thirds(styr)
    support = [u for u in clean if 1500 <= u["y"][s.REF][2] <= 6000]
    mixed = [dict(u) for u in clean + others]
    thirds(mixed)

    runs = [
        ("1 main net", clean, 0, False, {}),
        ("2 net without 2014", clean, 0, False, no14),
        ("3 gross", clean, 1, False, {}),
        ("4 gross without 2014", clean, 1, False, no14),
        ("5 weighted by population 2014", clean, 0, False, {"weighted": True}),
        ("6a year x Styrian size tercile", styr, 0, True, {}),
        ("6b same without 2014", styr, 0, True, no14),
        ("7a only 1,500 to 6,000 inhabitants", support, 0, False, {}),
        ("7b same without 2014", support, 0, False, no14),
        ("8 without split predecessors", [u for u in clean if not u["split"]], 0, False, {}),
        ("9a combined control group, year x size tercile", mixed, 0, True, {}),
        ("9b same without 2014", mixed, 0, True, no14),
    ]
    rng = np.random.default_rng(s.SEED)
    out = ["Styrian checks on the cleaned panel (styria_checks.py)",
           f"Panel {len(clean)} units, merged {sum(u['treated'] for u in clean)}, without {sorted(found)}"]
    main_b = None
    for name, us, col, gfe, kw in runs:
        r = s.boot(us, col, gfe, rng, **kw)
        main_b = r["b"] if main_b is None else main_b
        dev = r["b"] / main_b - 1
        out.append(f"{name} (n = {len(us)}, merged {sum(u['treated'] for u in us)}): log {r['b']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]"
                   f"  i.e. {np.expm1(r['b']):+.1%} ({np.expm1(r['lo']):+.1%} to {np.expm1(r['hi']):+.1%})  deviation from main {dev:+.0%}")
        if name[0] in "12":
            yrs = [t for t in r["years"] if t != r["ref"]]
            out.append(f"   Event study (reference {r['ref']}): " + "  ".join(f"{t}: {v:+.3f} [{lo:+.3f}, {hi:+.3f}]" for t, v, lo, hi in zip(yrs, r["es"], r["es_lo"], r["es_hi"])))
    text = "\n".join(out)
    print(text)
    (s.OUT / "styria_checks.txt").write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
