#!/usr/bin/env python3
"""Tightness table from the JSON files written by chb_cop_from_schema.py.

    .venv/bin/python tools/estimates_table.py --dir results/estimates [--p 1e-6] [--window 0]
        [--uncensored]
"""
import argparse
import glob
import json
import os

BENCH_ORDER = ["bsort100", "fir", "matmult", "edn", "ndes", "st", "lms", "prime",
               "cnt", "ludcmp", "select", "qsort-exam", "fdct", "sqrt"]
METHODS = ["E2E-CHB", "E2E-MEMIK", "E2E-CANTELLI", "E2E-EVT-PoT", "E2E-EVT-BM",
           "EVT-COP", "MEMIK-COP", "CHB-IND", "CHB-COMONO", "CHB-COP"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results/estimates")
    ap.add_argument("--p", default="1e-06")
    ap.add_argument("--window", default="0")
    ap.add_argument("--uncensored", action="store_true")
    ap.add_argument("--methods", default=",".join(METHODS), help="comma separated columns")
    ap.add_argument("--dirs", default=None, help="comma separated result dirs merged per benchmark (overrides --dir)")
    a = ap.parse_args()
    methods = a.methods.split(",")
    key = "tightness_uncensored" if a.uncensored else "tightness"
    p = str(float(a.p))
    rows = {}
    for dir_ in (a.dirs.split(",") if a.dirs else [a.dir]):
        for path in glob.glob(os.path.join(dir_, "*.json")):
            d = json.load(open(path))
            w = d["windows"].get(a.window, {})
            row = rows.setdefault(d["bench"], {m: None for m in methods})
            row.update({m: w[m][key][p] for m in methods if m in w and key in w[m]})
    benches = [b for b in BENCH_ORDER if b in rows] + sorted(set(rows) - set(BENCH_ORDER))
    print(f"tightness at p={p} ({'SMI-inclusive' if a.uncensored else 'SMI-censored'} reference), "
          f"window {a.window}")
    names = [m.replace('E2E-', 'E~').replace('CHB-FAM-', 'F~') for m in methods]
    width = [max(12, len(n) + 1) for n in names]
    print(f"{'bench':<11}" + "".join(f"{n:>{w}}" for n, w in zip(names, width)))
    for b in benches:
        cells = []
        for m, w in zip(methods, width):
            v = rows[b][m]
            cells.append(f"{v:>{w}.3f}" if isinstance(v, float) and v == v else f"{'-':>{w}}")
        print(f"{b:<11}" + "".join(cells))
    unsafe = {m: sum(1 for b in benches if isinstance(rows[b][m], float) and rows[b][m] == rows[b][m]
                     and rows[b][m] < 1.0) for m in methods}
    print(f"{'#unsafe':<11}" + "".join(f"{unsafe[m]:>{w}}" for m, w in zip(methods, width)))


if __name__ == "__main__":
    main()
