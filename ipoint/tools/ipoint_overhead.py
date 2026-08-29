#!/usr/bin/env python3
"""Instrumentation overhead (experiment E2-6): compare the harness-measured
end-to-end time of the uninstrumented (OFF) build with the TIMING build and,
optionally, the COVERAGE build.

    ipoint_overhead.py --off DIR --timing DIR [--coverage DIR] [--out overhead.json]

The per-probe cost is estimated by regressing the TIMING harness time of every
run on its number of IPoint records (both from summary.bin).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ipoint_parse import load_summary  # noqa: E402


def stats(x: np.ndarray, tick_ns: float) -> dict:
    return {"n": int(len(x)), "min_ns": float(x.min() * tick_ns), "median_ns": float(np.median(x) * tick_ns),
            "mean_ns": float(x.mean() * tick_ns), "p99_ns": float(np.quantile(x, 0.99) * tick_ns),
            "max_ns": float(x.max() * tick_ns)}


def load(d: str):
    with open(os.path.join(d, "meta.json")) as f:
        meta = json.load(f)
    return meta, load_summary(d, meta)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--off", required=True)
    ap.add_argument("--timing", required=True)
    ap.add_argument("--coverage")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    m_off, s_off = load(a.off)
    m_t, s_t = load(a.timing)
    tick_ns = 1e9 / m_off["tsc_hz_start"]
    off = s_off["harness"].astype(np.float64)
    tim = s_t["harness"].astype(np.float64)
    nrec = s_t["nrec"].astype(np.float64) - 3  # minus the three sentinel records
    res = {"bench": m_off["bench"], "tick_ns": tick_ns, "off": stats(off, tick_ns), "timing": stats(tim, tick_ns),
           "probes_per_run": {"mean": float(nrec.mean()), "min": int(nrec.min()), "max": int(nrec.max())}}
    res["overhead_ratio_mean"] = float(tim.mean() / off.mean())
    res["overhead_ratio_median"] = float(np.median(tim) / np.median(off))
    res["overhead_abs_mean_ns"] = float((tim.mean() - off.mean()) * tick_ns)
    if nrec.std() > 0:
        slope, intercept = np.polyfit(nrec, tim, 1)
        res["per_probe_ns_regression"] = float(slope * tick_ns)
        res["regression_intercept_ns"] = float(intercept * tick_ns)
    if nrec.mean() > 0:
        res["per_probe_ns_mean_diff"] = float((tim.mean() - off.mean()) / nrec.mean() * tick_ns)
    if a.coverage:
        m_c, s_c = load(a.coverage)
        cov = s_c["harness"].astype(np.float64)
        res["coverage"] = stats(cov, tick_ns)
        res["coverage_overhead_ratio_mean"] = float(cov.mean() / off.mean())
    text = json.dumps(res, indent=1)
    if a.out:
        with open(a.out, "w") as f:
            f.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
