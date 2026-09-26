#!/usr/bin/env python3
"""Run the ten pWCET estimators of the evaluation on one or more benchmarks.

Per benchmark and training window (10^4 runs, SMI-censored; window 0 is the
paper's main setting), estimates pWCET at p in {1e-4, 1e-5, 1e-6} with the
end-to-end methods (E2E-CHB, E2E-MEMIK, E2E-CANTELLI, E2E-EVT-PoT,
E2E-EVT-BM) and the decomposed methods (CHB-COP, CHB-IND, CHB-COMONO,
MEMIK-COP, EVT-COP), and reports tightness against the SMI-censored
empirical reference of all 10^7 runs (the SMI-inclusive reference is stored
alongside). Results: <out>/<bench>.json.

    .venv/bin/python tools/chb_cop_from_schema.py --traces ipoint/traces \
        --bench bsort100 --windows 0 --out results/estimates
"""
import argparse
import json
import os
import sys
import time
import traceback

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from estimation import chb, evt, tree  # noqa: E402
from estimation.data import WINDOW, Bench  # noqa: E402

E2E_METHODS = ("E2E-CHB", "E2E-MEMIK", "E2E-CANTELLI", "E2E-EVT-PoT", "E2E-EVT-BM")
# family ablation of the end-to-end CHB bound (not in 'all'): arctan only, and the envelope over
# arctan and tanh of the first submission
E2E_CHB_FAMILIES = {"E2E-CHB": chb.CHB_FAMILIES, "E2E-CHB-ATAN": ("atan",), "E2E-CHB-ENV": ("atan", "tanh")}
DECOMPOSED = ("CHB-COP", "CHB-IND", "CHB-COMONO", "MEMIK-COP", "EVT-COP")


def run_e2e(method: str, samples: np.ndarray, bench: str, window: int) -> tuple[dict, dict]:
    rng = tree._seed(bench, window, "e2e", method)
    if method in E2E_CHB_FAMILIES:
        r = chb.chb_leaf(samples, tree.P_GRID_FULL, rng, families=E2E_CHB_FAMILIES[method])
        mono = tree.monotone_pwcet(r.pwcet)          # same monotone curve as the unit-level marginals
        return {p: mono[p] for p in tree.P_EVAL}, {**r.detail, "raw_pwcet": {str(p): r.pwcet[p] for p in tree.P_EVAL}}
    if method == "E2E-MEMIK":
        r = chb.memik_leaf(samples, tree.P_GRID_FULL, rng)
        mono = tree.monotone_pwcet(r.pwcet)
        return {p: mono[p] for p in tree.P_EVAL}, {**r.detail, "raw_pwcet": {str(p): r.pwcet[p] for p in tree.P_EVAL}}
    if method == "E2E-CANTELLI":
        r = evt.cantelli_estimate(samples, tree.P_EVAL, rng=rng)
        return r.pop("estimate"), r
    if method == "E2E-EVT-PoT":
        fit = evt.pot_fit(samples)
        return {p: fit.quantile(p) for p in tree.P_EVAL}, fit.detail
    if method == "E2E-EVT-BM":
        r = evt.bm_estimate(samples, tree.P_EVAL)
        accepted = {b: v for b, v in r.items() if v["accepted"]}
        est = {}
        for p in tree.P_EVAL:
            vals = [v["estimate"][p] for v in accepted.values()]
            est[p] = float(np.median(vals)) if vals else float("nan")
        detail = {b: {k: v[k] for k in ("kappa", "qq_r2", "ks_pvalue", "accepted", "estimate")}
                  for b, v in r.items()}
        return est, {"blocks": detail, "n_accepted": len(accepted)}
    raise ValueError(method)


def run_bench(traces: str, bench_name: str, windows, methods, n_mc: int, out_dir: str,
              window_size: int = WINDOW, window_stride: int | None = None) -> dict:
    bench = Bench(traces, bench_name)
    refs = bench.references(tree.P_EVAL)
    result = {"bench": bench_name, "tick_ns": bench.tick_ns, "references": refs,
              "n_mc": n_mc, "window_size": window_size, "window_stride": window_stride or window_size,
              "windows": {}}
    for w in windows:
        lo, hi = bench.window_bounds(w, window_size, window_stride)
        e2e = bench.e2e_window(lo, hi)
        wres = {"n_train": int(len(e2e)), "runs": [lo, hi]}
        for method in methods:
            t0 = time.perf_counter()
            try:
                if method in E2E_METHODS or method in E2E_CHB_FAMILIES:
                    est, meta = run_e2e(method, e2e, bench_name, w)
                else:
                    pwcet, meta = tree.decomposed_estimate(bench, method, w, n_mc, window_size=window_size,
                                                           window_stride=window_stride)
                    est = {p: pwcet[p] for p in tree.P_EVAL}
                entry = {
                    "estimate_ticks": {str(p): est[p] for p in tree.P_EVAL},
                    "estimate_us": {str(p): est[p] * bench.tick_ns / 1e3 for p in tree.P_EVAL},
                    "tightness": {str(p): est[p] / refs["censored"][p] for p in tree.P_EVAL},
                    "tightness_uncensored": {str(p): est[p] / refs["uncensored"][p] for p in tree.P_EVAL},
                    "seconds": round(time.perf_counter() - t0, 2),
                    "meta": meta,
                }
            except Exception:
                entry = {"error": traceback.format_exc(),
                         "seconds": round(time.perf_counter() - t0, 2)}
            wres[method] = entry
            err = "ERROR" if "error" in entry else " ".join(
                f"{p:g}:{entry['tightness'][str(p)]:.3f}" for p in tree.P_EVAL)
            print(f"{bench_name} w{w} {method:<13} [{entry['seconds']:>7.1f}s] tightness {err}",
                  flush=True)
        result["windows"][str(w)] = wres
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{bench_name}.json")
    with open(path, "w") as f:
        json.dump(result, f, indent=1, default=float)
    print(f"wrote {path}", flush=True)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces", default="ipoint/traces")
    ap.add_argument("--bench", required=True, help="comma separated benchmark names")
    ap.add_argument("--windows", default="0", help="comma separated window indices")
    ap.add_argument("--window-size", type=float, default=WINDOW, help="runs per window (default 1e4)")
    ap.add_argument("--window-stride", type=float, default=0,
                    help="window w starts at run w * stride (default: consecutive windows)")
    ap.add_argument("--methods", default="all", help="comma separated, or 'all' / 'e2e' / 'decomposed'")
    ap.add_argument("--n-mc", type=float, default=1e8)
    ap.add_argument("--out", default="results/estimates")
    a = ap.parse_args()
    methods = {"all": E2E_METHODS + DECOMPOSED, "e2e": E2E_METHODS,
               "decomposed": DECOMPOSED}.get(a.methods, tuple(a.methods.split(",")))
    windows = [int(w) for w in a.windows.split(",")]
    for b in a.bench.split(","):
        run_bench(a.traces, b, windows, methods, int(a.n_mc), a.out, int(a.window_size),
                  int(a.window_stride) or None)


if __name__ == "__main__":
    main()
