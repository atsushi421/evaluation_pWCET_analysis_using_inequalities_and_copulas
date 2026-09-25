#!/usr/bin/env python3
"""Identify runs hit by SMM interrupts (SMIs) and write a censoring artifact.

On the measurement machine, SMIs stop every core simultaneously for
76-245 us (plus a ~1 ms event about once per minute) at a fixed 8.34 s
period; they are invisible to /proc/interrupts (measured with a TSC gap
scan on two isolated cores, see the paper repo notes/smi_interference.md).
A hit adds the full SMI duration to the end-to-end time of the run it
lands in, far beyond any program-driven variation of the Malardalen
kernels, whose end-to-end spread above the median is a few us.

Rule: a run is censored when its end-to-end time exceeds a per-run
baseline by more than --margin-us (default 60, below the smallest SMI
but above every program tail):
  * default: baseline = the benchmark's median end-to-end time;
  * prime:   the program itself spans 40 ns - 400 us (trial division up
    to 32767 iterations), so the baseline is per-run: a + b * iters,
    where iters is the exact loop-iteration count of the same run taken
    from the COVERAGE build's per-run hit counters (identical seeds) and
    a, b are robust median fits.

Validation: the number of censored runs matches the exposure-based
expectation sum(e2e) * rate for every benchmark (--rate-hz, measured
0.24/s), i.e. the rule captures the SMI process and nothing else.

Writes per benchmark:
  parsed/smi_runs.npy     u8 run indices of censored runs (sorted)
  parsed/smi_censor.json  rule, counts, expectation, quantiles with and
                          without the censored runs
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ipoint_parse import summary_dtype  # noqa: E402

QUANTILES = (1e-4, 1e-5, 1e-6)


def qtile(a: np.ndarray, p: float) -> float:
    return float(np.quantile(a, 1.0 - p, method="higher"))


def prime_iters(bench_dir: str) -> np.ndarray:
    """Per-run trial-division iteration count from the COVERAGE summary."""
    schema = json.load(open(os.path.join(bench_dir, "schema_full.json")))
    bodies = [u for u in schema["units"] if u["kind"] == "loop_body"]
    if len(bodies) != 1:
        raise SystemExit(f"prime: expected one loop_body unit, got {[u['uid'] for u in bodies]}")
    entry_id = bodies[0]["entry"]
    cov = os.path.join(bench_dir, "coverage")
    meta = json.load(open(os.path.join(cov, "meta.json")))
    rows = np.fromfile(os.path.join(cov, "summary.bin"), dtype=summary_dtype(meta["max_id"]))
    if not np.array_equal(rows["run"], np.arange(len(rows), dtype=np.uint64)):
        raise SystemExit("prime: coverage summary is not in run order")
    return rows["hits"][:, entry_id].astype(np.int64), rows["seed"]


def censor_bench(bench_dir: str, bench: str, margin_us: float, rate_hz: float) -> dict:
    ov = json.load(open(os.path.join(bench_dir, "overhead.json")))
    tick_ns = ov["tick_ns"]
    e2e = np.load(os.path.join(bench_dir, "parsed", "e2e_all.npy")).astype(np.float64)
    margin = margin_us * 1e3 / tick_ns
    fit = None
    if bench == "prime":
        iters, cov_seed = prime_iters(bench_dir)
        if len(iters) != len(e2e):
            raise SystemExit(f"prime: coverage has {len(iters)} runs, timing {len(e2e)}")
        a = float(np.median(e2e[iters == 0]))
        big = iters >= 1000
        b = float(np.median((e2e[big] - a) / iters[big]))
        baseline = a + b * iters
        resid = e2e - baseline
        flag = resid > margin
        fit = {"a_ticks": a, "b_ticks_per_iter": b, "b_ns_per_iter": b * tick_ns,
               "n_fit_runs": int(big.sum()), "max_abs_resid_clean_us":
                   float(np.abs(resid[~flag]).max() * tick_ns / 1e3)}
    else:
        baseline = float(np.median(e2e))
        flag = e2e > baseline + margin
    censored = np.flatnonzero(flag).astype(np.uint64)
    kept = e2e[~flag]
    expected = float(e2e.sum() * tick_ns * 1e-9 * rate_hz)
    out = {
        "bench": bench,
        "rule": "e2e > baseline + margin; baseline = a + b*iters (coverage hits)" if bench == "prime"
                else "e2e > median + margin",
        "margin_us": margin_us,
        "smi_rate_hz": rate_hz,
        "tick_ns": tick_ns,
        "n_runs": int(len(e2e)),
        "n_censored": int(flag.sum()),
        "expected_smi_hits": expected,
        "fit": fit,
        "uncensored": {f"q{p:g}_us": qtile(e2e, p) * tick_ns / 1e3 for p in QUANTILES}
                      | {"max_us": float(e2e.max()) * tick_ns / 1e3},
        "censored": {f"q{p:g}_us": qtile(kept, p) * tick_ns / 1e3 for p in QUANTILES}
                    | {"max_us": float(kept.max()) * tick_ns / 1e3},
    }
    np.save(os.path.join(bench_dir, "parsed", "smi_runs.npy"), censored)
    with open(os.path.join(bench_dir, "parsed", "smi_censor.json"), "w") as f:
        json.dump(out, f, indent=1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces", default="traces")
    ap.add_argument("--bench", default="all", help="comma separated names or 'all' (= every subdirectory)")
    ap.add_argument("--margin-us", type=float, default=60.0)
    ap.add_argument("--rate-hz", type=float, default=0.24, help="measured SMI arrival rate")
    a = ap.parse_args()
    if a.bench == "all":
        benches = sorted(d for d in os.listdir(a.traces)
                         if os.path.isfile(os.path.join(a.traces, d, "overhead.json")))
    else:
        benches = a.bench.split(",")
    print(f"{'bench':<11} {'nCens':>6} {'expect':>7} {'q1e-6_unc':>10} {'q1e-6_cen':>10} "
          f"{'q1e-5_unc':>10} {'q1e-5_cen':>10} {'max_cen_us':>10}")
    for b in benches:
        r = censor_bench(os.path.join(a.traces, b), b, a.margin_us, a.rate_hz)
        u, c = r["uncensored"], r["censored"]
        print(f"{b:<11} {r['n_censored']:>6} {r['expected_smi_hits']:>7.1f} {u['q1e-06_us']:>10.2f} "
              f"{c['q1e-06_us']:>10.2f} {u['q1e-05_us']:>10.2f} {c['q1e-05_us']:>10.2f} {c['max_us']:>10.2f}")
        if r["fit"]:
            print(f"{'':<11} prime fit: a={r['fit']['a_ticks']:.0f} ticks, "
                  f"b={r['fit']['b_ns_per_iter']:.2f} ns/iter over {r['fit']['n_fit_runs']} runs, "
                  f"max |resid| of kept runs {r['fit']['max_abs_resid_clean_us']:.1f} us")


if __name__ == "__main__":
    main()
