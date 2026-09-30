#!/usr/bin/env python3
"""X3: mixing-rate sweep for the adversarial inputs of qsort-exam and select, without new measurements.

A training window of n = 10^4 runs holds K adversarial runs of the killer campaign and n - K runs of the uniform
campaign (results/e214/), in random order, and window (K, j) is drawn with the seed [K, j, 20260925]. The
estimate of a window depends only on K. The mixing rate rho enters only through the reference quantile and
through P(K) = Binom(n, rho), which tools/x3_summary.py combines. Entries already in the output are kept, so a
rerun resumes. With --like, the (window, method) entries of an existing output are recomputed. Run from the
repository root.

    .venv/bin/python tools/x3_mixing_sweep.py qsort-exam results/x3/x3_qsort-exam.json --ks 0,1,2 --windows 10 \
        --methods E2E-CHB,E2E-MEMIK,E2E-CANTELLI,E2E-EVT-PoT,E2E-EVT-BM,CHB-IND
    .venv/bin/python tools/x3_mixing_sweep.py select check.json --like results/x3/x3_select.json
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, ".")
sys.path.insert(0, "tools")
from estimation import tree  # noqa: E402
from estimation.data import Bench, UnitData  # noqa: E402
from chb_cop_from_schema import run_e2e  # noqa: E402

N = 10_000


def mix_bench(rb, kb, rand_runs, kill_runs, order, name, with_units=True):
    """One window [0, N): position i holds run src[i] of the random (0) or killer (1) campaign.
    Windows of end-to-end methods only skip the units."""
    src = np.r_[np.zeros(len(rand_runs), int), np.ones(len(kill_runs), int)][order]
    run = np.r_[rand_runs, kill_runs][order]
    m = Bench.__new__(Bench)
    m.bench, m.dir, m.schema, m.by_uid, m.tick_ns = name, None, rb.schema, rb.by_uid, rb.tick_ns
    m.e2e_all = np.where(src == 0, rb.e2e_all[np.where(src == 0, run, 0)], kb.e2e_all[np.where(src == 1, run, 0)])
    m.smi_runs = np.empty(0, dtype=np.uint64)
    m._clean_e2e_mask = np.ones(len(run), dtype=bool)
    m.n_traced = len(run)
    maps = []
    for s, b in ((0, rb), (1, kb)):
        mp = np.full(len(b.e2e_all), -1, dtype=np.int64)
        mp[run[src == s]] = np.flatnonzero(src == s)
        maps.append(mp)
    m.units = {}
    for uid in (rb.units if with_units else ()):
        vs, rs, ss = [], [], []
        for s, b in ((0, rb), (1, kb)):
            u = b.units.get(uid)
            if u is None:
                continue
            new = maps[s][u.runs]
            keep = new >= 0
            vs.append(u.vals[keep])
            rs.append(new[keep])
            if rb.units[uid].self_vals is not None:
                ss.append(u.self_vals[keep])
        r = np.concatenate(rs)
        o = np.argsort(r, kind="stable")
        m.units[uid] = UnitData(np.concatenate(vs)[o], r[o], np.concatenate(ss)[o] if ss else None)
    return m


def one(bench, key, methods):
    pre = "" if bench == "qsort-exam" else bench + "_"
    rb, kb = Bench(f"results/e214/{pre}rand", bench), Bench(f"results/e214/{pre}killer", bench)
    K, j = (int(x[1:]) for x in key.split("/"))
    g = np.random.default_rng([K, j, 20260925])
    rr = g.choice(np.flatnonzero(rb._clean_e2e_mask), N - K, replace=False)
    kk = g.choice(np.flatnonzero(kb._clean_e2e_mask), K, replace=False)
    mb = mix_bench(rb, kb, rr, kk, g.permutation(N), f"{bench}-mixK{K}j{j}",
                   with_units=not all(m.startswith("E2E-") for m in methods))
    out = {}
    for m in methods:
        t0 = time.perf_counter()
        if m.startswith("E2E-"):
            est, _ = run_e2e(m, mb.e2e_window(0, N), mb.bench, 0)
        else:
            est, _ = tree.decomposed_estimate(mb, m, 0, n_mc=int(1e7))
        out[m] = {str(p): float(est[p]) for p in tree.P_EVAL}
        print(key, m, " ".join(f"{est[p]:.0f}" for p in tree.P_EVAL), f"[{time.perf_counter() - t0:.0f}s]", flush=True)
    return key, out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("bench", choices=("qsort-exam", "select"))
    ap.add_argument("out")
    ap.add_argument("--ks", help="numbers K of adversarial runs per window, comma separated")
    ap.add_argument("--windows", type=int, default=10, help="windows per K")
    ap.add_argument("--methods", default="E2E-CHB,E2E-MEMIK,E2E-CANTELLI,E2E-EVT-PoT,E2E-EVT-BM,CHB-IND")
    ap.add_argument("--like", help="recompute the (window, method) entries of this output")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", "8")))
    a = ap.parse_args()
    if a.like:
        want = {k: list(v) for k, v in json.load(open(a.like)).items()}
    elif a.ks:
        want = {f"K{K}/j{j}": a.methods.split(",") for K in map(int, a.ks.split(",")) for j in range(a.windows)}
    else:
        ap.error("give --ks or --like")
    out = json.load(open(a.out)) if os.path.exists(a.out) else {}
    todo = [(a.bench, k, [m for m in ms if m not in out.get(k, {})]) for k, ms in want.items()]
    todo = [t for t in todo if t[2]]
    if todo:
        with ProcessPoolExecutor(a.workers) as ex:
            for key, rec in ex.map(one, *zip(*todo)):
                out.setdefault(key, {}).update(rec)
                json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
