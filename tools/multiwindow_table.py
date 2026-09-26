#!/usr/bin/env python3
"""E2-3: tightness over the training windows of every benchmark.

    .venv/bin/python tools/multiwindow_table.py [--w0 results/estimates] [--mw results/estimates_multiwindow]
        [--benches b1,b2,...] [--p 0.0001] [--pairs A:B,...] [--out results/tables/multiwindow.md]

Per method and p: unsafe windows (tightness < 1) / windows with an estimate, the 95 % Clopper-Pearson
interval of the unsafe rate, and the median tightness. Per benchmark and method at --p: mean, SD,
[min, max] and unsafe windows. Per method pair at --p (windows where both have an estimate): the windows
unsafe for one method only with the exact McNemar test, and the median tightness ratio with the Wilcoxon
signed-rank test on the paired log ratios. --w0 and --mw may name the same directory.
"""
import argparse
import json
import os

import numpy as np
from scipy import stats

METHODS = ["E2E-CHB", "E2E-CHB-ATAN", "E2E-CHB-ENV", "E2E-MEMIK", "E2E-CANTELLI", "E2E-EVT-PoT", "E2E-EVT-BM",
           "EVT-COP", "MEMIK-COP", "CHB-IND", "CHB-COMONO", "CHB-COP", "CHB-IND@inst", "CHB-COP@inst"]
BENCHES = ["bsort100", "fir", "matmult", "edn", "ndes", "st", "lms", "prime", "cnt", "ludcmp",
           "select", "qsort-exam"]
PS = ("0.0001", "1e-05", "1e-06")
PAIRS = ("E2E-CHB:E2E-MEMIK,E2E-CHB:E2E-CHB-ATAN,E2E-CHB:E2E-CHB-ENV,CHB-COP:MEMIK-COP,"
         "CHB-COP:E2E-CHB,CHB-IND:E2E-CHB,CHB-COMONO:CHB-IND")


def load(w0_dir, mw_dir, benches=BENCHES):
    out = {}
    for b in benches:
        wins = {}
        for d in dict.fromkeys((w0_dir, mw_dir)):
            path = os.path.join(d, f"{b}.json")
            if os.path.exists(path):
                for w, e in json.load(open(path))["windows"].items():
                    wins.setdefault(w, {}).update(e)
        out[b] = wins
    return out


def tight(w, m, p):
    """Tightness of method m at p in window entry w, or None (no estimate, error, NaN)."""
    e = w.get(m)
    if not isinstance(e, dict) or "tightness" not in e:
        return None
    v = e["tightness"][p]
    return v if v == v else None


def cp(k, n):
    return stats.binomtest(k, n).proportion_ci(method="exact") if n else None


def pair_row(data, a, b, p):
    x, y = [], []
    for wins in data.values():
        for w in wins.values():
            ta, tb = tight(w, a, p), tight(w, b, p)
            if ta is not None and tb is not None:
                x.append(ta)
                y.append(tb)
    if not x:
        return None
    x, y = np.array(x), np.array(y)
    only_a, only_b = int(((x < 1) & (y >= 1)).sum()), int(((y < 1) & (x >= 1)).sum())
    mc = stats.binomtest(min(only_a, only_b), only_a + only_b).pvalue if only_a + only_b else 1.0
    fin = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    lr = np.log(x[fin] / y[fin])
    wx = stats.wilcoxon(lr).pvalue if np.count_nonzero(lr) else 1.0
    return (f"| {a} vs {b} | {len(x)} | {only_a} | {only_b} | {mc:.2g} | "
            f"{np.exp(np.median(lr)):.3f} | {wx:.2g} |")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--w0", default="results/estimates")
    ap.add_argument("--mw", default="results/estimates_multiwindow")
    ap.add_argument("--p", default="0.0001")
    ap.add_argument("--pairs", default=PAIRS, help="comma separated A:B method pairs ('' = none)")
    ap.add_argument("--out", default="results/tables/multiwindow.md")
    ap.add_argument("--benches", default=",".join(BENCHES), help="comma separated (e.g. cb1,...,cb7 for Autoware)")
    a = ap.parse_args()
    benches = a.benches.split(",")
    data = load(a.w0, a.mw, benches)
    present = {m for wins in data.values() for w in wins.values() for m in w}
    methods = [m for m in METHODS if m in present]
    n_win = {b: len(w) for b, w in data.items()}
    lines = [f"Unsafe windows (tightness < 1) / windows with an estimate, {len(benches)} benchmarks, windows per "
             f"benchmark {min(n_win.values())}-{max(n_win.values())}; 95 % Clopper-Pearson interval of the unsafe "
             "rate in %; median tightness.\n",
             "| method | " + " | ".join(f"p={p}" for p in PS) + " |", "|---|" + "---|" * len(PS)]
    for m in methods:
        cells = []
        for p in PS:
            v = [t for wins in data.values() for w in wins.values() if (t := tight(w, m, p)) is not None]
            if not v:
                cells.append("-")
                continue
            k, n = sum(x < 1 for x in v), len(v)
            ci = cp(k, n)
            cells.append(f"{k}/{n} [{100 * ci.low:.1f}, {100 * ci.high:.1f}] med {np.median(v):.3f}")
        lines.append(f"| {m} | " + " | ".join(cells) + " |")
    lines += ["", f"Tightness at p={a.p}: mean, SD, [min, max] over windows, unsafe windows.\n",
              "| bench | " + " | ".join(methods) + " |", "|---|" + "---|" * len(methods)]
    for b, wins in data.items():
        cells = []
        for m in methods:
            v = np.array([t for w in wins.values() if (t := tight(w, m, a.p)) is not None])
            v = v[np.isfinite(v)]
            cells.append("-" if not len(v) else
                         f"{v.mean():.3f}±{v.std(ddof=1) if len(v) > 1 else 0:.3f} [{v.min():.3f},{v.max():.3f}] "
                         f"{int((v < 1).sum())}/{len(v)}")
        lines.append(f"| {b} | " + " | ".join(cells) + " |")
    rows = [r for pr in a.pairs.split(",") if pr for r in [pair_row(data, *pr.split(":"), a.p)] if r]
    if rows:
        lines += ["", f"Paired comparison at p={a.p} over the windows where both methods have an estimate: windows "
                  "unsafe for A only and for B only, exact McNemar p-value, median tightness ratio A/B and "
                  "Wilcoxon signed-rank p-value of the log ratios.\n",
                  "| A vs B | windows | A only | B only | McNemar p | median A/B | Wilcoxon p |",
                  "|---|---|---|---|---|---|---|"] + rows
    text = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
