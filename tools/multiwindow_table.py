#!/usr/bin/env python3
"""E2-3: tightness over the ten disjoint 1e4-run training windows (window 0 + windows 1..9).

    .venv/bin/python tools/multiwindow_table.py [--w0 results/estimates] [--mw results/estimates_multiwindow]

Prints, per method, the number of unsafe windows (tightness < 1) out of the windows with an
estimate, per p; then per benchmark and method mean, SD, min, max and unsafe count at --p.
"""
import argparse
import glob
import json
import os

import numpy as np

METHODS = ["E2E-CHB", "E2E-MEMIK", "E2E-CANTELLI", "E2E-EVT-PoT", "E2E-EVT-BM",
           "EVT-COP", "MEMIK-COP", "CHB-IND", "CHB-COMONO", "CHB-COP"]
BENCHES = ["bsort100", "fir", "matmult", "edn", "ndes", "st", "lms", "prime", "cnt", "ludcmp",
           "select", "qsort-exam"]
PS = ("0.0001", "1e-05", "1e-06")


def load(w0_dir, mw_dir):
    out = {}
    for b in BENCHES:
        wins = {}
        for d in (w0_dir, mw_dir):
            path = os.path.join(d, f"{b}.json")
            if os.path.exists(path):
                for w, e in json.load(open(path))["windows"].items():
                    wins.setdefault(w, {}).update(e)
        out[b] = wins
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--w0", default="results/estimates")
    ap.add_argument("--mw", default="results/estimates_multiwindow")
    ap.add_argument("--p", default="0.0001")
    ap.add_argument("--out", default="results/tables/multiwindow.md")
    a = ap.parse_args()
    data = load(a.w0, a.mw)
    lines = ["Unsafe windows (tightness < 1) / windows with an estimate, 12 benchmarks x 10 windows.\n",
             "| method | " + " | ".join(f"p={p}" for p in PS) + " |", "|---|" + "---|" * len(PS)]
    for m in METHODS:
        cells = []
        for p in PS:
            v = [w[m]["tightness"][p] for wins in data.values() for w in wins.values()
                 if m in w and "tightness" in w[m] and w[m]["tightness"][p] == w[m]["tightness"][p]]
            cells.append(f"{sum(x < 1 for x in v)}/{len(v)}")
        lines.append(f"| {m} | " + " | ".join(cells) + " |")
    lines += ["", f"Tightness at p={a.p}: mean, SD, [min, max] over windows, unsafe windows.\n",
              "| bench | " + " | ".join(METHODS) + " |", "|---|" + "---|" * len(METHODS)]
    for b, wins in data.items():
        cells = []
        for m in METHODS:
            v = np.array([w[m]["tightness"][a.p] for w in wins.values() if m in w and "tightness" in w[m]])
            v = v[np.isfinite(v)]
            cells.append("-" if not len(v) else
                         f"{v.mean():.3f}±{v.std(ddof=1) if len(v) > 1 else 0:.3f} [{v.min():.3f},{v.max():.3f}] {int((v < 1).sum())}/{len(v)}")
        lines.append(f"| {b} | " + " | ".join(cells) + " |")
    text = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
