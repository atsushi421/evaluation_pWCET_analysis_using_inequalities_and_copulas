#!/usr/bin/env python3
"""E2-14 estimates: end-to-end and decomposed estimators trained on the first 1e4 uniform-input runs
of results/e214/rand (fine granularity), reported relative to the median of the killer runs of
results/e214/killer (the reference that the adversarial input decides).

    .venv/bin/python ipoint/e214/estimate.py [--n-mc 1e7] [--methods CHB-COMONO,CHB-IND,CHB-COP]
"""
import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
from estimation import chb, tree  # noqa: E402
from estimation.data import Bench  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default=os.path.join(ROOT, "results", "e214"))
    ap.add_argument("--n-mc", type=float, default=1e7)
    ap.add_argument("--methods", default="CHB-COMONO,CHB-IND,CHB-COP")
    ap.add_argument("--out", default=None, help="output JSON (default <dir>/estimates.json)")
    a = ap.parse_args()
    b = Bench(os.path.join(a.dir, "rand"), "qsort-exam")
    k = np.load(os.path.join(a.dir, "killer", "qsort-exam", "parsed", "e2e_all.npy")).astype(float)
    kmed = float(np.median(k))
    w = b.e2e_window(*b.window_bounds(0))
    out = {"tick_ns": b.tick_ns, "n_mc": int(a.n_mc), "killer_runs": int(len(k)), "killer_median": kmed,
           "killer_max": float(k.max()), "rand_window_max": float(w.max()),
           "rand_ref": {str(p): v for p, v in b.references(tree.P_EVAL)["censored"].items()}, "methods": {}}
    us = b.tick_ns / 1e3
    print(f"rand window max {w.max() * us:.1f} us, killer median {kmed * us:.1f} us, max {k.max() * us:.1f} us", flush=True)

    def report(name, pw, t0, meta=None):
        out["methods"][name] = {"estimate_ticks": {str(p): pw[p] for p in tree.P_EVAL},
                                "vs_killer_median": {str(p): pw[p] / kmed for p in tree.P_EVAL},
                                "seconds": round(time.perf_counter() - t0, 1)}
        if meta:
            out["methods"][name]["tree"] = {u: {k: v for k, v in m.items() if k in ("parts", "composition", "model")}
                                            for u, m in meta.items() if isinstance(m, dict) and "parts" in m}
        print(name, "  ".join(f"{p:g}: {pw[p] / kmed:.3f}x" for p in tree.P_EVAL),
              f"[{out['methods'][name]['seconds']:.0f} s]", flush=True)

    t0 = time.perf_counter()
    report("E2E-CHB", tree.monotone_pwcet(chb.chb_leaf(w, tree.P_GRID_FULL, tree._seed("qsort-exam", 0, "e2e", "E2E-CHB")).pwcet), t0)
    t0 = time.perf_counter()
    report("E2E-MEMIK", tree.monotone_pwcet(chb.memik_leaf(w, tree.P_GRID_FULL, tree._seed("qsort-exam", 0, "e2e", "E2E-MEMIK")).pwcet), t0)
    for m in a.methods.split(","):
        t0 = time.perf_counter()
        pw, meta = tree.decomposed_estimate(b, m, 0, n_mc=int(a.n_mc))
        report(m, pw, t0, meta)
    with open(a.out or os.path.join(a.dir, "estimates.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)


if __name__ == "__main__":
    main()
