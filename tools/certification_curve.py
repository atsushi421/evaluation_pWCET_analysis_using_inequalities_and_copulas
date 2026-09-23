#!/usr/bin/env python3
"""E2-12: KL-certified envelope vs plug-in envelope on all 10^7 end-to-end samples.

The SMI-censored end-to-end times of every run are split as in chb_leaf
(first 10% calibration for the d grid, the rest for the moments). For each p
of a log grid, reports the empirical quantile of all clean runs (in-sample
reference), the plug-in saturating-Chebyshev envelope (E2E-CHB, monotonized by
tree.monotone_pwcet as the pipeline reports it; the raw
per-p values are kept under plugin_raw; the certified envelope scans the whole
k range at every p and is monotone by construction) and the certified envelope (Theorem: holds with probability >= 1 - alpha,
simultaneously over the grid; +inf below the floor 1 - e^{-tau}).
Also reports the certified envelope of the 10^4 training window 0 for comparison.

    .venv/bin/python tools/certification_curve.py --bench bsort100 --out results/certification
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from estimation import chb, tree  # noqa: E402
from estimation.data import Bench  # noqa: E402

P_CURVE = tuple(float(p) for p in np.logspace(-1, -7, 25))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces", default="ipoint/traces")
    ap.add_argument("--bench", required=True)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--out", default="results/certification")
    a = ap.parse_args()
    bench = Bench(a.traces, a.bench)
    clean = bench.e2e_all[bench._clean_e2e_mask]
    xs = np.sort(clean)
    emp = {p: float(xs[min(int(np.ceil((1 - p) * len(xs))) - 1, len(xs) - 1)]) for p in P_CURVE}
    out = {"bench": a.bench, "tick_ns": bench.tick_ns, "alpha": a.alpha, "p": list(P_CURVE),
           "empirical_all": [emp[p] for p in P_CURVE]}
    for name, samples in (("all", clean), ("window0", bench.e2e_window(*bench.window_bounds(0)))):
        t0 = time.perf_counter()
        r = chb.chb_leaf(samples, P_CURVE, tree._seed(a.bench, "cert", name), alpha=a.alpha)
        cert = r.detail["certificate"]
        mono = tree.monotone_pwcet(r.pwcet)
        out[name] = {"n_main": r.detail["n_main"], "n_calib": r.detail["n_calib"],
                     "tau": cert["tau"], "floor": cert["floor"], "grid_size": cert["grid_size"],
                     "plugin": [mono[p] for p in P_CURVE],
                     "plugin_raw": [r.pwcet[p] for p in P_CURVE],
                     "certified": [cert["pwcet"][p] for p in P_CURVE],
                     "choice": {str(p): r.detail["choice"][p] for p in P_CURVE},
                     "seconds": round(time.perf_counter() - t0, 1)}
        print(f"{a.bench} {name}: n_main {r.detail['n_main']} floor {cert['floor']:.3g} "
              f"[{out[name]['seconds']} s]", flush=True)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, f"{a.bench}.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    for i, p in enumerate(P_CURVE):
        e = emp[p]
        print(f"  p={p:9.2e} emp {e:10.0f}  plugin/emp {out['all']['plugin'][i] / e:7.3f}  "
              f"cert/emp {out['all']['certified'][i] / e:7.3f}  w0 cert/emp {out['window0']['certified'][i] / e:7.3f}")


if __name__ == "__main__":
    main()
