#!/usr/bin/env python3
"""E2-14 estimates: end-to-end and decomposed estimators trained on uniform-input windows of 1e4 runs
(fine granularity), reported relative to the median and maximum of the killer runs (the reference that
the adversarial input decides) and to the uniform-input reference. Kernels: qsort-exam (results/e214/
{rand,killer}, output estimates.json) and select (results/e214/select_{rand,killer}, output
estimates_select.json). A decomposed method suffixed @inst uses the per-instance loop rule.

    .venv/bin/python ipoint/e214/estimate.py [--bench select] [--windows 0,1] [--n-mc 1e7] [--methods ...]
"""
import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from chb_cop_from_schema import E2E_METHODS, run_e2e  # noqa: E402
from estimation import tree  # noqa: E402
from estimation.data import Bench  # noqa: E402

METHODS = ("E2E-CHB,E2E-MEMIK,E2E-CANTELLI,E2E-EVT-PoT,E2E-EVT-BM,CHB-COMONO,CHB-IND,CHB-COP,MEMIK-COP,EVT-COP,"
           "CHB-COMONO@inst,CHB-IND@inst,CHB-COP@inst")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default=os.path.join(ROOT, "results", "e214"))
    ap.add_argument("--bench", default="qsort-exam", choices=("qsort-exam", "select"))
    ap.add_argument("--windows", default="0,1")
    ap.add_argument("--n-mc", type=float, default=1e7)
    ap.add_argument("--methods", default=METHODS)
    ap.add_argument("--out", default=None, help="output JSON (default <dir>/estimates.json, estimates_select.json)")
    a = ap.parse_args()
    pre = "" if a.bench == "qsort-exam" else a.bench + "_"
    out_path = a.out or os.path.join(a.dir, "estimates.json" if not pre else f"estimates_{a.bench}.json")
    b = Bench(os.path.join(a.dir, pre + "rand"), a.bench)
    kb = Bench(os.path.join(a.dir, pre + "killer"), a.bench)
    k = kb.e2e_all[kb._clean_e2e_mask]
    kmed, kmax = float(np.median(k)), float(k.max())
    refs = b.references(tree.P_EVAL)["censored"]
    out = {"bench": a.bench, "tick_ns": b.tick_ns, "n_mc": int(a.n_mc), "killer_runs": int(len(k)), "killer_median": kmed,
           "killer_max": kmax, "rand_ref": {str(p): v for p, v in refs.items()}, "windows": {}}
    us = b.tick_ns / 1e3
    print(f"{a.bench}: killer median {kmed * us:.1f} us, max {kmax * us:.1f} us", flush=True)
    for w in (int(x) for x in a.windows.split(",")):
        lo, hi = b.window_bounds(w)
        e2e = b.e2e_window(lo, hi)
        res = out["windows"][str(w)] = {"rand_window_max": float(e2e.max()), "methods": {}}
        for m in a.methods.split(","):
            t0 = time.perf_counter()
            meta = None
            if m in E2E_METHODS:
                pw, _ = run_e2e(m, e2e, a.bench, w)
            else:
                pw, meta = tree.decomposed_estimate(b, m, w, n_mc=int(a.n_mc))
            e = res["methods"][m] = {"estimate_ticks": {str(p): pw[p] for p in tree.P_EVAL},
                                     "vs_killer_median": {str(p): pw[p] / kmed for p in tree.P_EVAL},
                                     "vs_killer_max": {str(p): pw[p] / kmax for p in tree.P_EVAL},
                                     "vs_rand_ref": {str(p): pw[p] / refs[p] for p in tree.P_EVAL},
                                     "seconds": round(time.perf_counter() - t0, 1)}
            if meta:
                e["tree"] = {u: {k: v for k, v in mm.items() if k in ("parts", "composition", "model")}
                             for u, mm in meta.items() if isinstance(mm, dict) and "parts" in mm}
            print(f"w{w} {m:16s}", "  ".join(f"{p:g}: {pw[p] / kmed:.3f}x" for p in tree.P_EVAL), f"[{e['seconds']:.0f} s]", flush=True)
            with open(out_path, "w") as f:
                json.dump(out, f, indent=1, default=float)


if __name__ == "__main__":
    main()
