#!/usr/bin/env python3
"""Tables of the evaluation that come straight from the campaign artifacts and result JSONs.

    .venv/bin/python tools/tables.py [--traces ipoint/traces] [--out results/tables]

coverage.md  (E2-4)  branch alternatives, loop iterations and path signatures seen in the
                     training window (first 1e4 runs) and in all 1e7 COVERAGE runs
overhead.md  (E2-6)  OFF / TIMING / COVERAGE end-to-end statistics and probes per run
tails.md     (E2-7)  tail shape of the SMI-censored end-to-end time (all 1e7 runs) and of every
                     timed unit (every traced run): quantile / median, excess kurtosis, GPD shape
cost.md      (E2-10) analysis time per method (window 0, and mean over the other windows)
refci.md     (R3-11) distribution-free 95 % confidence interval of every reference quantile (order statistics)
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from scipy import stats as sps

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from estimation.data import Bench  # noqa: E402

BENCHES = ["bsort100", "fir", "matmult", "edn", "ndes", "st", "lms", "prime", "cnt", "ludcmp",
           "select", "qsort-exam"]
METHODS = ["E2E-CHB", "E2E-MEMIK", "E2E-CANTELLI", "E2E-EVT-PoT", "E2E-EVT-BM",
           "EVT-COP", "MEMIK-COP", "CHB-IND", "CHB-COMONO", "CHB-COP"]
QP = (1e-3, 1e-4, 1e-5, 1e-6)


def md(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def coverage(traces):
    rows = []
    audit = json.load(open(os.path.join(traces, "bounds_audit.json")))
    for b in BENCHES:
        c = json.load(open(os.path.join(traces, b, "coverage.json")))
        br = c["branches"].values()
        alts = lambda key: sum(v[key] for v in br)  # noqa: E731
        au = {x["loop"]: x for x in audit[b]}
        assert all(x["violating_runs"] == 0 for x in au.values()), b
        loops = [f"{u} {v['max_iters_per_run_train']}/{v['max_iters_per_run_all']} (bound {au[u]['bound']} x {au[u]['max_entries_per_run']})"
                 for u, v in c["loops"].items() if v["max_iters_per_run_all"] > 0]
        rows.append([b, f"{alts('observed_train')}/{alts('observed_all')}/{alts('static')}",
                     c.get("first_run_all_observed_alternatives_seen", "-"),
                     f"{c['path_signatures']['distinct_train']}/{c['path_signatures']['distinct_all']}",
                     "; ".join(loops) or "-"])
    return ("Alternatives observed in the first 1e4 runs / in all 1e7 runs / static; first run by which "
            "every alternative observed in 1e7 runs was seen; distinct path signatures (1e4 / 1e7); per "
            "loop: max iterations per run (1e4 / 1e7) and the static bound per entry x the max entries per "
            "run. The loop-bound audit found no run above the bound in 1e7 runs for any loop.\n\n"
            + md(["bench", "alternatives", "first run", "paths", "loops: max iters per run (1e4/1e7)"], rows))


def overhead(traces):
    rows = []
    for b in BENCHES:
        o = json.load(open(os.path.join(traces, b, "overhead.json")))
        f = lambda s, k: f"{o[s][k] / 1e3:.2f}"  # noqa: E731
        rows.append([b, f("off", "median_ns"), f("off", "p99_ns"), f("timing", "median_ns"), f("timing", "p99_ns"),
                     f"{o['overhead_ratio_median']:.3f}", f"{o['probes_per_run']['mean']:.0f}",
                     f"{o['coverage_overhead_ratio_mean']:.2f}"])
    return ("End-to-end time in us (OFF: 1e5 runs, TIMING: 1e7 runs, SMI runs included); TIMING/OFF median "
            "ratio; probes per run; COVERAGE/OFF mean ratio.\n\n"
            + md(["bench", "OFF med", "OFF p99", "TIMING med", "TIMING p99", "TIMING/OFF", "probes/run", "COV/OFF"], rows))


def tail_stats(x):
    x = np.asarray(x, dtype=float)
    med = float(np.median(x))
    n = len(x)
    q = {p: (float(np.quantile(x, 1 - p, method="higher")) / med if p * n >= 9 else None) for p in QP}
    thr = np.quantile(x, 0.99)
    exc = x[x > thr] - thr
    xi = float(sps.genpareto.fit(exc, floc=0)[0]) if len(exc) >= 50 and np.ptp(exc) > 0 else None
    return q, float(sps.kurtosis(x)), xi, n


def tails(traces):
    rows = []
    n_traced = set()
    fmt = lambda v, d=3: "-" if v is None else f"{v:.{d}f}"  # noqa: E731
    for b in BENCHES:
        bench = Bench(traces, b)
        n_traced.add(bench.n_traced)
        items = [("E2E (1e7, SMI-censored)", bench.e2e_all[bench._clean_e2e_mask])]
        for uid, u in bench.units.items():
            m = bench.clean_run_mask(u.runs)
            if m.sum() >= 1000 and np.median(u.vals[m]) > 0:     # empty units have no duration
                items.append((uid, u.vals[m]))
        for name, x in items:
            q, kurt, xi, n = tail_stats(x)
            rows.append([b, name, n] + [fmt(q[p]) for p in QP] + [fmt(kurt, 1), fmt(xi, 2)])
    return ("Quantile at 1-p divided by the median (shown when p*n >= 9, i.e. at least about ten exceedances), excess kurtosis, and GPD shape "
            "xi of the exceedances above the 0.99 quantile (MLE, location 0). Units: all instances in the "
            f"first {'/'.join(f'{n:.0e}' for n in sorted(n_traced))} (fully traced) runs, SMI runs removed.\n\n"
            + md(["bench", "series", "n", "q1e-3/med", "q1e-4/med", "q1e-5/med", "q1e-6/med", "ex. kurtosis", "xi(0.99)"], rows))


def cost(res_w0, res_mw):
    rows = []
    for b in BENCHES:
        d0 = json.load(open(os.path.join(res_w0, f"{b}.json")))["windows"]["0"]
        mw_path = os.path.join(res_mw, f"{b}.json")
        mw = json.load(open(mw_path))["windows"] if os.path.exists(mw_path) else {}
        cells = []
        for m in METHODS:
            s0 = d0.get(m, {}).get("seconds")
            ss = [w[m]["seconds"] for k, w in mw.items() if k != "0" and m in w and "seconds" in w[m]]
            cells.append("-" if s0 is None else (f"{s0:.1f}" + (f" ({np.mean(ss):.1f})" if ss else "")))
        rows.append([b] + cells)
    return ("Analysis time in seconds on one core of the Xeon Silver 4216 (window 0; in parentheses the mean "
            "over the other windows where available). The CHB methods of one job share the unit-level bounds, so a "
            "CHB method that runs after another one in the same job (CHB-IND and CHB-COMONO after CHB-COP on the "
            "two-part kernels, CHB-COMONO after CHB-IND on ndes, lms, ludcmp) shows the composition time only.\n\n"
            + md(["bench"] + METHODS, rows))


def refci(traces):
    """The reference is the order statistic X_(r) with r = ceil((1 - p) n) (method "higher"); the number of runs
    below the true (1 - p) quantile is Binomial(n, 1 - p), so [X_(l), X_(u)] with l, u the 2.5 % and 97.5 %
    binomial quantiles covers it with probability >= 95 %."""
    rows = []
    for b in BENCHES:
        bench = Bench(traces, b)
        xs = np.sort(bench.e2e_all[bench._clean_e2e_mask])
        n = len(xs)
        cells = []
        for p in (1e-4, 1e-5, 1e-6):
            r = int(np.ceil((1 - p) * n))
            lo, hi = sps.binom.ppf([0.025, 0.975], n, 1 - p).astype(int)
            ref = xs[min(r, n) - 1]
            cells.append(f"{xs[max(lo, 1) - 1] / ref:.3f}-{xs[min(hi + 1, n) - 1] / ref:.3f} ({n - hi - 1}-{n - lo})")
        rows.append([b, n] + cells)
    return ("Reference quantile (SMI-censored runs): 95 % distribution-free confidence interval relative to the reference "
            "value, and in brackets the number of runs above its ends.\n\n"
            + md(["bench", "runs", "p=1e-4", "p=1e-5", "p=1e-6"], rows))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces", default="ipoint/traces")
    ap.add_argument("--results", default="results/estimates")
    ap.add_argument("--multiwindow", default="results/estimates_multiwindow")
    ap.add_argument("--out", default="results/tables")
    ap.add_argument("--only", default="coverage,overhead,tails,cost,refci")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    jobs = {"coverage": lambda: coverage(a.traces), "overhead": lambda: overhead(a.traces),
            "tails": lambda: tails(a.traces), "cost": lambda: cost(a.results, a.multiwindow),
            "refci": lambda: refci(a.traces)}
    for name in a.only.split(","):
        text = jobs[name]()
        with open(os.path.join(a.out, f"{name}.md"), "w") as f:
            f.write(text)
        print(f"== {name}\n{text}")


if __name__ == "__main__":
    main()
